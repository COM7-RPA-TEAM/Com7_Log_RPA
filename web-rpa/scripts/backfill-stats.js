/**
 * คำนวณ rpa_stats/daily ย้อนหลังจาก log ดิบ — ใช้ครั้งแรกหลัง deploy aggregateDailyStats
 * หรือเมื่อสงสัยว่าตัวเลขสรุปเพี้ยน (เช่นฟังก์ชันเคยล่ม)
 *
 * ใช้ statUpdatesFor ตัวเดียวกับ Cloud Function จึงจัดกลุ่มสถานะเหมือนกันทุกตัว
 *
 * วิธีใช้ (จากโฟลเดอร์ web-rpa):
 *   node scripts/backfill-stats.js 14 > stats.json
 *   firebase database:update /rpa_stats/daily stats.json --project com7-rpa-log
 *
 * database:update เขียนทับทีละ "วัน" ทั้งก้อน จึงรันซ้ำได้โดยตัวเลขไม่บวกซ้ำ
 * ⚠️ ดาวน์โหลด log ดิบตามจำนวนวันที่ระบุ (~0.4 MB ต่อวัน) — อย่าใส่จำนวนวันเยอะเกินจำเป็น
 */
const https = require("https");
const { _test } = require("../functions/index.js");

const DB = "https://com7-rpa-log-default-rtdb.asia-southeast1.firebasedatabase.app";
const days = Math.max(1, parseInt(process.argv[2] || "14", 10));

/** วันที่ตามปฏิทินไทย ย้อนหลัง n วัน -> "YYYY-MM-DD" */
function bkkDay(offsetDays) {
  const t = Date.now() + 7 * 3600 * 1000 - offsetDays * 86400000;
  return new Date(t).toISOString().slice(0, 10);
}

function getJson(url) {
  return new Promise((resolve, reject) => {
    https.get(url, (res) => {
      let body = "";
      res.setEncoding("utf8");
      res.on("data", (c) => { body += c; });
      res.on("end", () => {
        if (res.statusCode !== 200) return reject(new Error(`HTTP ${res.statusCode}: ${body.slice(0, 200)}`));
        resolve(JSON.parse(body));
      });
    }).on("error", reject);
  });
}

(async () => {
  const start = bkkDay(days - 1);
  const q = `orderBy=${encodeURIComponent('"status_datetime"')}`
    + `&startAt=${encodeURIComponent(`"${start}"`)}`
    + `&endAt=${encodeURIComponent('"9999"')}`;
  const logs = Object.values((await getJson(`${DB}/rpa_history_logs.json?${q}`)) || {});

  // สะสมเป็นโครงเดียวกับที่ฟังก์ชันเขียน: daily/{day}/all|bots|unknown
  const daily = {};
  for (const log of logs) {
    const updates = _test.statUpdatesFor(log, 1);
    if (!updates) continue;
    for (const [path, value] of Object.entries(updates)) {
      const parts = path.split("/").slice(2);          // ตัด "rpa_stats/daily"
      let node = daily;
      for (const key of parts.slice(0, -1)) node = node[key] = node[key] || {};
      const leaf = parts[parts.length - 1];
      if (typeof value === "number") node[leaf] = (node[leaf] || 0) + value;
      else if (leaf === "last_fail") node[leaf] = (node[leaf] || "") > value ? node[leaf] : value;
      else node[leaf] = value;
    }
  }

  process.stderr.write(`backfill: ${logs.length} logs, ${Object.keys(daily).length} days (from ${start})\n`);
  process.stdout.write(JSON.stringify(daily));
})().catch((err) => {
  process.stderr.write(`backfill failed: ${err.message}\n`);
  process.exit(1);
});
