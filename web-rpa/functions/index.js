/**
 * Scheduled Functions ของ Com7 RPA Log
 *
 *  1) clearSuccessLiveStatus  — เคลียร์การ์ด Success ทุกเที่ยงคืน
 *  2) timeoutStuckRunningBots — ตัดบอทที่ค้างสถานะ Running นานผิดปกติ
 *  3) pruneOldHistoryLogs     — ลบ log เก่าตาม retention (ค่าเริ่มต้น: DRY RUN ไม่ลบจริง)
 *
 * ทุกตัวแตะเฉพาะ Realtime Database — ไม่เกี่ยวกับ API (main.py) และไม่กระทบบอทที่ยิง log เข้ามา
 */
const { onSchedule } = require("firebase-functions/v2/scheduler");
const logger = require("firebase-functions/logger");
const admin = require("firebase-admin");

admin.initializeApp({
  databaseURL: "https://com7-rpa-log-default-rtdb.asia-southeast1.firebasedatabase.app/",
});

const REGION = "asia-southeast1";   // region เดียวกับ Realtime Database
const TZ = "Asia/Bangkok";

// สถานะที่ถือว่า "สำเร็จ" (รองรับหลายรูปแบบที่ระบบต่างๆ ส่งมา) ให้ตรงกับ normalizeStatus บน Dashboard
const SUCCESS_STATUSES = new Set([
  "success", "completed", "complete", "done", "ok", "passed", "finish", "finished",
]);

// สถานะที่ถือว่า "กำลังทำงาน" — ตรงกับ normalizeStatus บน Dashboard เช่นกัน
const RUNNING_STATUSES = new Set([
  "running", "start", "started", "in progress", "processing", "busy", "pending",
]);

/** แปลง "YYYY-MM-DD HH:MM:SS" (เวลาไทย) เป็น Date — ระบุ +07:00 ชัดเจน กัน server timezone เพี้ยน */
function parseBkk(s) {
  if (!s) return null;
  const d = new Date(String(s).trim().replace(" ", "T") + "+07:00");
  return isNaN(d.getTime()) ? null : d;
}

/** คืนวันที่ตามปฏิทินไทยในรูป "YYYY-MM-DD" */
function bkkDateKey(date) {
  return new Date(date.getTime() + 7 * 3600 * 1000).toISOString().slice(0, 10);
}

/** เวลาไทยรูปแบบเดียวกับที่ API เขียนลง DB */
function bkkStamp(date) {
  return new Date(date.getTime() + 7 * 3600 * 1000).toISOString().slice(0, 19).replace("T", " ");
}

/* ============================================================
   1) เคลียร์การ์ด Live ที่สถานะ Success ทุกเที่ยงคืน (เวลาไทย)
      - ลบเฉพาะใน rpa_live_status (การ์ดบนหน้า Live Dashboard)
      - ไม่แตะ rpa_history_logs (ประวัติเก็บครบเหมือนเดิม)
   ============================================================ */
exports.clearSuccessLiveStatus = onSchedule(
  {
    schedule: "0 0 * * *",        // ทุกวัน เวลา 00:00
    timeZone: TZ,
    region: REGION,
  },
  async () => {
    const ref = admin.database().ref("rpa_live_status");
    const snap = await ref.once("value");
    const data = snap.val() || {};

    const updates = {};
    let removed = 0;
    for (const [botName, info] of Object.entries(data)) {
      const status = String((info && info.status) || "").trim().toLowerCase();
      if (SUCCESS_STATUSES.has(status)) {
        updates[botName] = null;   // null = ลบ key นี้ทิ้ง
        removed++;
      }
    }

    if (removed > 0) {
      await ref.update(updates);
    }
    logger.info(`[clearSuccessLiveStatus] ลบการ์ด Success ออกจาก Live แล้ว ${removed} ตัว`);
    return null;
  }
);

/* ============================================================
   2) ตัดบอทที่ค้างสถานะ Running นานผิดปกติ -> Timeout

   ปัญหาเดิม: บอทที่ตายกลางทาง (หรือลืมยิง log ตอนจบ) จะค้างเป็น Running
   บนหน้า Live ตลอดไป — เคยเจอค้างข้ามเดือน กิน slot บนจอ TV และทำให้
   KPI "ค้าง/Stale" ชินตาจนไม่มีใครสนใจ

   ทำอะไร: บอทที่ Running แต่ไม่มีสัญญาณเกิน TIMEOUT_HOURS ชั่วโมง
           -> เปลี่ยนสถานะเป็น "Timeout" (Dashboard แสดงเป็น Failed สีแดง)
           -> คง status_datetime เดิมไว้ จะได้ยังเห็นว่า "เงียบมาตั้งแต่เมื่อไหร่"
           -> บันทึกลง rpa_history_logs ด้วย เพื่อให้ตามย้อนหลังได้

   ถ้าบอทกลับมายิง log ใหม่ API จะเขียนทับสถานะให้เองตามปกติ
   ============================================================ */
const TIMEOUT_HOURS = 12;   // ปรับได้ตามงานจริง — ตั้งเผื่อไว้สำหรับบอทที่รันยาว

exports.timeoutStuckRunningBots = onSchedule(
  {
    schedule: "0 * * * *",        // ทุกชั่วโมง
    timeZone: TZ,
    region: REGION,
  },
  async () => {
    const db = admin.database();
    const liveRef = db.ref("rpa_live_status");
    const snap = await liveRef.once("value");
    const data = snap.val() || {};

    const now = new Date();
    const cutoffMs = TIMEOUT_HOURS * 3600 * 1000;
    const updates = {};
    const stuck = [];

    for (const [botName, info] of Object.entries(data)) {
      const status = String((info && info.status) || "").trim().toLowerCase();
      if (!RUNNING_STATUSES.has(status)) continue;     // สนใจเฉพาะตัวที่ยัง Running อยู่

      const last = parseBkk(info && info.status_datetime);
      if (!last) continue;                             // ไม่มีเวลา -> ไม่แตะ ปลอดภัยไว้ก่อน

      const silentMs = now.getTime() - last.getTime();
      if (silentMs <= cutoffMs) continue;

      const hours = Math.floor(silentMs / 3600000);
      updates[`${botName}/status`] = "Timeout";
      updates[`${botName}/error_message`] =
        `ไม่มีสัญญาณอัปเดตเกิน ${TIMEOUT_HOURS} ชม. (เงียบมาแล้ว ${hours} ชม.) — ระบบตัดเป็น Timeout อัตโนมัติ`;
      updates[`${botName}/timeout_at`] = bkkStamp(now);
      // ตั้งใจไม่แตะ status_datetime — เก็บเวลาสัญญาณสุดท้ายไว้ให้เห็นว่าเงียบมานานแค่ไหน

      stuck.push({ botName, hours, stage: (info && info.stage) || "", last: info.status_datetime });
    }

    if (stuck.length === 0) {
      logger.info("[timeoutStuckRunningBots] ไม่มีบอทค้าง");
      return null;
    }

    await liveRef.update(updates);

    // บันทึกประวัติไว้ด้วย จะได้เห็นย้อนหลังว่าโดนตัดตอนไหน
    const historyRef = db.ref("rpa_history_logs");
    await Promise.all(stuck.map(({ botName, hours, stage }) =>
      historyRef.push({
        bot_name: botName,
        status: "Timeout",
        stage: stage,
        error_message: `ไม่มีสัญญาณอัปเดตเกิน ${TIMEOUT_HOURS} ชม. (เงียบมาแล้ว ${hours} ชม.) — ระบบตัดเป็น Timeout อัตโนมัติ`,
        status_datetime: bkkStamp(now),
      })
    ));

    logger.warn(
      `[timeoutStuckRunningBots] ตัดบอทค้าง ${stuck.length} ตัว: ` +
      stuck.map((s) => `${s.botName} (เงียบ ${s.hours} ชม. ตั้งแต่ ${s.last})`).join(", ")
    );
    return null;
  }
);

/* ============================================================
   3) ลบ log เก่าออกจาก rpa_history_logs ตาม retention

   ปัญหาเดิม: ประวัติโตขึ้นทุกวันโดยไม่มีเพดาน ทำให้ค่า storage/bandwidth
   โตตาม และ query ช้าลงเรื่อยๆ

   ⚠️ ฟังก์ชันนี้ "ลบข้อมูลถาวร" กู้คืนไม่ได้
      ค่าเริ่มต้นตั้งเป็น DRY_RUN = true คือ *นับให้ดูเฉยๆ ไม่ลบจริง*
      ให้ deploy แล้วดู log ก่อนว่าจะลบเท่าไหร่ พอใจแล้วค่อยเปลี่ยนเป็น false
   ============================================================ */
const DRY_RUN = true;              // ⚠️ เปลี่ยนเป็น false เมื่อพร้อมลบจริง
const RETENTION_DAYS = 180;        // เก็บย้อนหลังกี่วัน
const MAX_DELETES_PER_RUN = 5000;  // เพดานต่อรอบ กันฟังก์ชัน timeout

exports.pruneOldHistoryLogs = onSchedule(
  {
    schedule: "30 2 * * *",       // ทุกวัน 02:30 (ช่วงที่บอทไม่ค่อยรัน)
    timeZone: TZ,
    region: REGION,
  },
  async () => {
    const cutoff = bkkDateKey(new Date(Date.now() - RETENTION_DAYS * 86400000));
    const ref = admin.database().ref("rpa_history_logs");

    // endAt(cutoff) = ทุก record ที่ status_datetime อยู่ก่อนเที่ยงคืนของวัน cutoff
    const snap = await ref
      .orderByChild("status_datetime")
      .endAt(cutoff)
      .limitToFirst(MAX_DELETES_PER_RUN)
      .once("value");

    const updates = {};
    let count = 0;
    snap.forEach((child) => { updates[child.key] = null; count++; });

    if (count === 0) {
      logger.info(`[pruneOldHistoryLogs] ไม่มี log เก่ากว่า ${cutoff} (retention ${RETENTION_DAYS} วัน)`);
      return null;
    }

    if (DRY_RUN) {
      logger.warn(
        `[pruneOldHistoryLogs] DRY RUN — พบ log เก่ากว่า ${cutoff} จำนวน ${count} รายการ ` +
        `(เพดานรอบละ ${MAX_DELETES_PER_RUN}) ยังไม่ลบจริง ` +
        `ถ้าต้องการลบให้ตั้ง DRY_RUN = false แล้ว deploy ใหม่`
      );
      return null;
    }

    await ref.update(updates);
    logger.info(`[pruneOldHistoryLogs] ลบ log เก่ากว่า ${cutoff} แล้ว ${count} รายการ`);
    return null;
  }
);
