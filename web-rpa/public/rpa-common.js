/* ============================================================
   rpa-common.js — ตรรกะที่ใช้ร่วมกันระหว่าง
     • index.html  (Dashboard หลัก)
     • tv.html     (TV Wallboard)

   เดิมโค้ดชุดนี้ถูก copy ไว้ทั้งสองไฟล์ ทำให้เวลาแก้ต้องไล่แก้ 2 ที่
   และเคยหลุดไม่ตรงกันมาแล้ว — รวมไว้ที่เดียวจะได้แก้ครั้งเดียวจบ

   หมายเหตุ: โหลดเป็น classic script (ไม่ใช่ module) ตัวแปร/ฟังก์ชันในไฟล์นี้
   จึงอยู่ใน global scope ให้ทั้งสองหน้าเรียกใช้ได้เลย
   ============================================================ */

/* คำที่แต่ละระบบส่งเข้ามา -> จัดกลุ่มเป็นสถานะมาตรฐาน
   (ต้องตรงกับ SUCCESS_STATUSES / RUNNING_STATUSES ใน web-rpa/functions/index.js) */
const RPA_STATUS_WORDS = {
  Success: ['success', 'completed', 'complete', 'done', 'ok', 'passed', 'finish', 'finished'],
  Failed: ['failed', 'fail', 'error', 'exception', 'crash', 'timeout'],
  Running: ['running', 'start', 'started', 'in progress', 'processing', 'busy', 'pending'],
};

/* จัดลำดับ: Failed → Stale → Running → Success (ตัวมีปัญหาขึ้นก่อนเสมอ) */
const STATE_ORDER = { Failed: 0, Stale: 1, Running: 2, Success: 3 };

const STATUS_META = {
  Running: { icon: 'fa-spinner fa-spin', label: 'Running' },
  Success: { icon: 'fa-circle-check', label: 'Success' },
  Failed: { icon: 'fa-circle-xmark', label: 'Failed' },
  Stale: { icon: 'fa-plug-circle-exclamation', label: 'ค้าง' },
  Unknown: { icon: 'fa-circle-question', label: 'Unknown' }
};

/** "YYYY-MM-DD HH:MM:SS" -> Date (null ถ้าแปลงไม่ได้) */
function parseDateTime(s) {
  if (!s) return null;
  const d = new Date(String(s).replace(' ', 'T'));
  return isNaN(d.getTime()) ? null : d;
}

/** "3 ชม.ที่แล้ว" */
function timeAgo(s) {
  const d = parseDateTime(s);
  if (!d) return s || '-';
  let diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 0) diff = 0;
  if (diff < 60) return 'เมื่อสักครู่';
  if (diff < 3600) return Math.floor(diff / 60) + ' นาทีที่แล้ว';
  if (diff < 86400) return Math.floor(diff / 3600) + ' ชม.ที่แล้ว';
  return Math.floor(diff / 86400) + ' วันที่แล้ว';
}

/** รวม status หลายรูปแบบจากแต่ละระบบให้เป็นมาตรฐานเดียว */
function normalizeStatus(raw) {
  const s = String(raw || '').trim().toLowerCase();
  if (RPA_STATUS_WORDS.Success.includes(s)) return 'Success';
  if (RPA_STATUS_WORDS.Failed.includes(s)) return 'Failed';
  if (RPA_STATUS_WORDS.Running.includes(s)) return 'Running';
  return raw || 'Unknown';
}

/** true = คำนี้อยู่ในรายการที่ระบบรู้จัก (ใช้เตือนเมื่อมีระบบส่งคำใหม่เข้ามา) */
function isKnownStatus(raw) {
  const s = String(raw || '').trim().toLowerCase();
  return !!s && (
    RPA_STATUS_WORDS.Success.includes(s) ||
    RPA_STATUS_WORDS.Failed.includes(s) ||
    RPA_STATUS_WORDS.Running.includes(s)
  );
}

/** สถานะ "ตามจริง": Running ที่เงียบเกิน staleMin นาที = Stale (ค้าง) */
function getEffectiveStatus(info, staleMin) {
  if (!info) return 'Unknown';
  const norm = normalizeStatus(info.status);
  if (norm === 'Running') {
    const d = parseDateTime(info.status_datetime);
    if (d && (Date.now() - d.getTime()) > staleMin * 60000) return 'Stale';
  }
  return norm;
}

/** "YYYY-MM-DD" ตามเวลาเครื่อง (ไม่ใส่ argument = วันนี้) */
function localDateKey(d) {
  const x = d || new Date();
  return x.getFullYear() + '-' + String(x.getMonth() + 1).padStart(2, '0') + '-' + String(x.getDate()).padStart(2, '0');
}

/** alias ให้อ่านง่ายเวลาหมายถึง "วันนี้" */
function todayKey() {
  return localDateKey(new Date());
}

function esc(s) {
  return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/** แปลง rpa_live_status เป็น array ที่เรียงแล้ว: [{ botName, info, eff }] */
function sortBots(liveData, staleMin) {
  if (!liveData) return [];
  return Object.keys(liveData).map(botName => {
    const info = liveData[botName];
    return { botName, info, eff: getEffectiveStatus(info, staleMin) };
  }).sort((a, b) => {
    const oa = STATE_ORDER[a.eff] ?? 9, ob = STATE_ORDER[b.eff] ?? 9;
    if (oa !== ob) return oa - ob;
    const x = a.info.status_datetime || '', y = b.info.status_datetime || '';
    return x < y ? 1 : x > y ? -1 : 0;   // ใหม่สุดขึ้นก่อน
  });
}

/** เรียง log ใหม่สุดขึ้นก่อน (status_datetime เป็น ASCII เทียบตรงๆ ได้ เร็วกว่า localeCompare มาก) */
function sortLogsDesc(logs) {
  return logs.sort((a, b) => {
    const x = a.status_datetime || '', y = b.status_datetime || '';
    return x < y ? 1 : x > y ? -1 : 0;
  });
}
