# Com7 RPA Log — ระบบติดตามสถานะ RPA แบบรวมศูนย์

เก็บ Log สถานะการทำงานของ RPA/บอททุกตัวจากหลายระบบมาไว้ที่เดียว เพื่อดูภาพรวมแบบ Real-time ว่าตัวไหน **Running / Success / Failed / ค้าง** พร้อมประวัติย้อนหลังและกราฟวิเคราะห์

## 🔗 ลิงก์ใช้งานจริง

| | |
|---|---|
| 🖥️ **Dashboard** | https://com7-rpa-log.web.app |
| 📺 **TV Monitor (Wallboard)** | https://com7-rpa-log.web.app/tv.html — เปิดค้างบนจอ TV ได้เลย |
| 🔌 **API Endpoint** | `https://com7rpalog-436289358307.asia-southeast3.run.app/api/v1/bot-log` |
| 📖 **Swagger (ทดสอบ/เอกสาร API)** | https://com7rpalog-436289358307.asia-southeast3.run.app/docs |

---

## สถาปัตยกรรม

```
┌─────────────┐   POST log    ┌──────────────┐   write    ┌─────────────────┐
│  Bot (RPA)  │ ────────────> │  FastAPI     │ ────────>  │ Firebase        │
│ ทุกระบบ      │  /bot-log     │  (Cloud Run) │            │ Realtime DB     │
└─────────────┘               └──────────────┘            └────────┬────────┘
                                                                    │ live sync
                                                          ┌─────────▼────────┐
                                                          │ Web Dashboard    │
                                                          │ (Firebase Hosting)│
                                                          └──────────────────┘
```

- **API** เขียนข้อมูล 2 ที่ทุกครั้ง: `rpa_live_status/{bot_name}` (สถานะล่าสุด เขียนทับ) และ `rpa_history_logs` (ประวัติ push ใหม่ทุกครั้ง)
- **Dashboard** ฟัง Firebase แบบ Real-time ไม่ต้องรีเฟรช

---

## โครงสร้างโปรเจกต์

```
Com7-RPA-Log/
├── main.py              # FastAPI — รับ POST log แล้วเขียนลง Firebase
├── rpa_logger.py        # ตัวช่วยฝั่ง Python (DashboardLogger) ให้บอทเรียกใช้ง่าย
├── requirements.txt     # fastapi, uvicorn, pydantic, firebase-admin
├── Dockerfile           # build image สำหรับ Cloud Run
├── testapi.py           # สคริปต์ทดสอบยิง API
└── web-rpa/             # Firebase project (Hosting + Functions)
    ├── firebase.json
    ├── public/index.html  # หน้า Dashboard หลัก (Live / History / Analytics)
    ├── public/tv.html     # โหมดจอ TV / Wallboard (เปิดค้างบนจอ monitor)
    └── functions/         # Cloud Functions
        └── index.js       # งานอัตโนมัติ: เคลียร์การ์ด Success ทุกเที่ยงคืน
```

---

## ฟีเจอร์ Dashboard

- **Live Dashboard** — KPI สรุป (Running / Success / Failed / ค้าง / Success Rate วันนี้) **คลิก KPI เพื่อกรองตามสถานะได้เลย**, การ์ดสถานะบอทแบบ Real-time (เรียงตัวมีปัญหาขึ้นก่อนเสมอ), ค้นหา, มุมมอง Card/List
- **Alert Panel** — รวมรายการ Error และบอทค้างไว้บนสุด ดูปุ๊บรู้ปั๊บว่าอะไรพัง
- **Stale Detection** — บอทที่ `Running` แต่เงียบเกินเวลาที่กำหนด (ปรับได้บนหน้าจอ) จะถูกจับว่า "ค้าง/ไม่ตอบสนอง"
- **การแจ้งเตือน** — เปิดปุ่ม `Alert` แล้วจะมีเสียง + Browser Notification เมื่อมีบอท **Failed ตัวใหม่**
- **History Logs** — ตารางประวัติ + ฟิลเตอร์ (Status / ชื่อ Bot / ช่วงวันที่) + Export CSV + Pagination
- **Analytics** — กราฟแนวโน้ม Success vs Failed 7 วันล่าสุด, อันดับบอทที่พังบ่อย, สรุปรันวันนี้ / Success Rate 7 วัน / จำนวนบอท active
- **📺 TV Monitor Mode (`tv.html`)** — โหมด Wallboard สำหรับเปิดค้างบนจอ TV: ตัวหนังสือใหญ่อ่านไกล, นาฬิกา+วันที่, KPI แถบใหญ่, แบนเนอร์เตือนกระพริบเมื่อมีบอทพัง, การ์ดจัดเต็มจออัตโนมัติ + หมุนหน้าเองเมื่อบอทเยอะเกินจอ, ซ่อนเคอร์เซอร์อัตโนมัติ — ปรับ threshold ค้างผ่าน URL ได้ เช่น `tv.html?stale=60`
- **ธีม Dark / Light** — ดีไซน์ professional, จำธีมที่เลือกไว้, ตัวบอกสถานะการเชื่อมต่อ (LIVE/offline) บนแถบบน

---

## ⏰ งานอัตโนมัติ (Scheduled Jobs)

รันบน **Cloud Functions** (Gen 2) ผ่าน Cloud Scheduler — ทำงานบน server ของ Google เอง ไม่ต้องเปิดเครื่องค้างไว้

### `clearSuccessLiveStatus` — เคลียร์การ์ด Success ทุกเที่ยงคืน

| | |
|---|---|
| **ทำงานเมื่อ** | ทุกวัน **00:00 เวลาไทย** (cron `0 0 * * *`, timezone `Asia/Bangkok`) |
| **ทำอะไร** | ลบ bot ที่สถานะล่าสุด = Success ออกจาก `rpa_live_status` (การ์ดบนหน้า Live) เพื่อเริ่มวันใหม่แบบสะอาด เหลือเฉพาะตัวที่กำลังรัน/มีปัญหา |
| **ไม่แตะ** | `rpa_history_logs` — ประวัติยังเก็บครบทุก record |
| **นับว่า Success** | `Success / Completed / Complete / Done / OK / Passed / Finish / Finished` (ตรงกับ normalize บน Dashboard) |
| **Region** | `asia-southeast1` (เดียวกับ Realtime DB) |
| **โค้ด** | [`web-rpa/functions/index.js`](web-rpa/functions/index.js) |

**Deploy / แก้ไข schedule:**
```bash
cd web-rpa
firebase deploy --only functions
```
> ปรับเวลา/เงื่อนไขได้ที่ `web-rpa/functions/index.js` (ตัวแปร `schedule`, `timeZone`, `SUCCESS_STATUSES`) แล้ว deploy ใหม่

**ทดสอบ/ดู log:** Firebase Console → Functions → `clearSuccessLiveStatus` (ดู Logs / กด Test ได้)

---

## 📡 การใช้งาน API (สำหรับให้ระบบอื่นส่ง Log เข้ามา)

ส่ง Log สถานะการทำงานของ RPA/บอทขึ้น Dashboard

> 💡 **ทดลองยิง API จากเบราว์เซอร์ได้เลยที่ [Swagger UI](https://com7rpalog-436289358307.asia-southeast3.run.app/docs)** — กด "Try it out" ได้โดยไม่ต้องเขียนโค้ด

### 1. ยิงไปที่ไหน

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `https://com7rpalog-436289358307.asia-southeast3.run.app/api/v1/bot-log` |
| **Header** | `Content-Type: application/json` |
| **Body** | JSON (ตามตารางด้านล่าง) |

### 2. ส่ง Parameter อะไรบ้าง

| Parameter | บังคับ? | ชนิด | คำอธิบาย |
|-----------|:------:|------|----------|
| `bot_name` | ✅ **ใช่** | string | ชื่อบอท/RPA — **ต้องไม่ซ้ำกับระบบอื่น** (ใช้เป็น Key บน Live Dashboard ถ้าซ้ำจะทับกัน) |
| `status` | ✅ **ใช่** | string | สถานะ → ใช้ `Running` / `Success` / `Failed` (เพื่อให้ขึ้นสีถูก) |
| `stage` | ❌ ไม่ | string | ขั้นตอนปัจจุบัน เช่น `"2 - Download Report"` (ไม่ส่ง = ว่าง) |
| `error_message` | ❌ ไม่ | string | ข้อความ Error ใส่ตอน `status = Failed` |
| `status_datetime` | ❌ ไม่ | string | เวลา `YYYY-MM-DD HH:MM:SS` — **ไม่ต้องส่งก็ได้ ระบบจะเติมเวลาไทย (UTC+7) ให้อัตโนมัติ** |

> **ง่ายสุด:** ส่งแค่ `bot_name` กับ `status` ก็พอ ที่เหลือ optional

**Body ที่สั้นที่สุด**
```json
{ "bot_name": "Finance_SendPO", "status": "Running" }
```

**Body แบบเต็ม (ตอนบอทพัง)**
```json
{
  "bot_name": "Finance_SendPO",
  "status": "Failed",
  "stage": "3 - Submit Form",
  "error_message": "Element not found: #submit-btn"
}
```

### 3. ตัวอย่างการเรียกใช้ (ก๊อปไปใช้ได้เลย)

**🐍 Python — ใช้ตัวช่วย `rpa_logger.py` (แนะนำ)**
```python
from rpa_logger import DashboardLogger

log = DashboardLogger(bot_name="Finance_SendPO")

log.send_log(stage="1 - Open Browser", status="Running")
# ... ทำงาน ...
log.send_log(stage="Completed", status="Success")

# ตอนพัง
log.send_log(stage="3 - Submit", status="Failed", error_message=str(e))
```

**🐍 Python — ยิงตรง (ไม่ใช้ตัวช่วย)**
```python
import requests

requests.post(
    "https://com7rpalog-436289358307.asia-southeast3.run.app/api/v1/bot-log",
    json={"bot_name": "Finance_SendPO", "status": "Running", "stage": "1 - Start"},
    timeout=5
)
```

**💻 PowerShell**
```powershell
$body = @{ bot_name = "Finance_SendPO"; status = "Success"; stage = "Completed" } | ConvertTo-Json
Invoke-RestMethod -Method Post `
  -Uri "https://com7rpalog-436289358307.asia-southeast3.run.app/api/v1/bot-log" `
  -ContentType "application/json" -Body $body
```

**🌐 curl**
```bash
curl -X POST "https://com7rpalog-436289358307.asia-southeast3.run.app/api/v1/bot-log" \
  -H "Content-Type: application/json" \
  -d '{"bot_name":"Finance_SendPO","status":"Running","stage":"1 - Start"}'
```

**🤖 UiPath / Power Automate (HTTP Request)**
- **Method:** POST
- **URL:** `https://com7rpalog-436289358307.asia-southeast3.run.app/api/v1/bot-log`
- **Headers:** `Content-Type = application/json`
- **Body:** `{"bot_name":"Finance_SendPO","status":"Running","stage":"1 - Start"}`

### 4. ควรยิงตอนไหน (แนะนำ)

| จังหวะ | status | ตัวอย่าง |
|--------|--------|----------|
| เริ่มงาน / เปลี่ยนขั้นตอน | `Running` | `{"bot_name":"X","status":"Running","stage":"2 - Download"}` |
| ทำงานเสร็จ | `Success` | `{"bot_name":"X","status":"Success","stage":"Completed"}` |
| เกิด Error | `Failed` | `{"bot_name":"X","status":"Failed","error_message":"..."}` |

> ⚠️ ยิง `Running` เมื่อเริ่มทุกครั้ง — ถ้าบอทค้าง/ตายไปเฉยๆ Dashboard จะจับได้ว่า "ค้าง" (Running แต่เงียบนานเกินกำหนด)

### 5. ผลลัพธ์ที่ได้กลับ (Response)

สำเร็จจะได้ HTTP `200` พร้อม:
```json
{
  "message": "Success - Logged to both Live and History",
  "bot": "Finance_SendPO",
  "time": "2026-06-04 11:35:50"
}
```

> เคล็ดลับ: ฝั่งบอทควรตั้ง `timeout=5` และครอบ try/except ไว้ เพื่อไม่ให้บอทค้าง/พัง หากเครือข่ายมีปัญหา (ตัวช่วย `rpa_logger.py` ทำให้แล้ว)

---

## รันในเครื่อง (Local Development)

**API**
```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8080
# เปิด http://localhost:8080/docs
```

**Dashboard**
```bash
cd web-rpa
firebase serve --only hosting
```

---

## Deploy

| ส่วน | ปลายทาง | วิธี |
|------|---------|------|
| **API** | Cloud Run | `git push origin main` → Cloud Build build Dockerfile + deploy อัตโนมัติ |
| **Dashboard** | Firebase Hosting | `cd web-rpa && firebase deploy --only hosting` |
| **Scheduled Jobs** | Cloud Functions | `cd web-rpa && firebase deploy --only functions` (ต้องเป็นแพลน Blaze) |

---

## Tech Stack

- **Backend:** FastAPI + Pydantic (Python 3.10) บน Google Cloud Run
- **Database:** Firebase Realtime Database (asia-southeast1)
- **Frontend:** HTML + Bootstrap 5 + Chart.js + Firebase JS SDK (Firebase Hosting)
- **Scheduled Jobs:** Cloud Functions (Node.js 20, Gen 2) + Cloud Scheduler
