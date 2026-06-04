/**
 * Scheduled Function: เคลียร์การ์ด Live ที่สถานะ Success ทุกเที่ยงคืน (เวลาไทย)
 * - ลบเฉพาะใน rpa_live_status (การ์ดบนหน้า Live Dashboard)
 * - ไม่แตะ rpa_history_logs (ประวัติเก็บครบเหมือนเดิม)
 */
const { onSchedule } = require("firebase-functions/v2/scheduler");
const logger = require("firebase-functions/logger");
const admin = require("firebase-admin");

admin.initializeApp({
  databaseURL: "https://com7-rpa-log-default-rtdb.asia-southeast1.firebasedatabase.app/",
});

// สถานะที่ถือว่า "สำเร็จ" (รองรับหลายรูปแบบที่ระบบต่างๆ ส่งมา) ให้ตรงกับ normalizeStatus บน Dashboard
const SUCCESS_STATUSES = new Set([
  "success", "completed", "complete", "done", "ok", "passed", "finish", "finished",
]);

exports.clearSuccessLiveStatus = onSchedule(
  {
    schedule: "0 0 * * *",        // ทุกวัน เวลา 00:00
    timeZone: "Asia/Bangkok",     // เที่ยงคืนตามเวลาไทย
    region: "asia-southeast1",    // อยู่ region เดียวกับ Realtime Database
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
