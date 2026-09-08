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
├── testapi.py           # สคริปต์ทดสอบยิง API (ยิงเข้า production จริง — ระวัง)
├── requirements-dev.txt # ของที่ใช้รันเทสในเครื่อง
├── tests/               # เทสของ API (pytest + Firebase ปลอม ไม่แตะ production)
│   ├── conftest.py
│   └── test_api.py
└── web-rpa/             # Firebase project (Hosting + Functions + Rules)
    ├── firebase.json
    ├── database.rules.json  # Security Rules: อ่านเปิด / เขียนต้อง login
    ├── public/index.html    # หน้า Dashboard หลัก (Live / History / Analytics)
    ├── public/tv.html       # โหมดจอ TV / Wallboard (เปิดค้างบนจอ monitor)
    ├── public/rpa-common.js # ตรรกะที่ 2 หน้าใช้ร่วมกัน (normalize / stale / เรียง / escape)
    └── functions/           # Cloud Functions
        └── index.js         # งานอัตโนมัติ 3 ตัว (เคลียร์ Success / ตัดบอทค้าง / ลบ log เก่า)
```

---

## ฟีเจอร์ Dashboard

- **Live Dashboard** — KPI สรุป (Running / Success / Failed / ค้าง / Success Rate วันนี้) **คลิก KPI เพื่อกรองตามสถานะได้เลย**, การ์ดสถานะบอทแบบ Real-time (เรียงตัวมีปัญหาขึ้นก่อนเสมอ), ค้นหา, มุมมอง Card/List
- **Alert Panel** — รวมรายการ Error และบอทค้างไว้บนสุด ดูปุ๊บรู้ปั๊บว่าอะไรพัง
- **Stale Detection** — บอทที่ `Running` แต่เงียบเกินเวลาที่กำหนด (ปรับได้บนหน้าจอ) จะถูกจับว่า "ค้าง/ไม่ตอบสนอง"
- **การแจ้งเตือน** — เปิดปุ่ม `Alert` แล้วจะมีเสียง + Browser Notification เมื่อมีบอท **Failed ตัวใหม่**
- **History Logs** — ตารางประวัติ **10,000 รายการล่าสุด** + ฟิลเตอร์ (Status / ชื่อ Bot / ช่วงวันที่) + Export CSV + Pagination
- **Analytics** — กราฟแนวโน้ม Success vs Failed 7 วันล่าสุด, อันดับบอทที่พังบ่อย, สรุปรันวันนี้ / Success Rate 7 วัน / จำนวนบอท active
- **📺 TV Monitor Mode (`tv.html`)** — โหมด Wallboard สำหรับเปิดค้างบนจอ TV: ตัวหนังสือใหญ่อ่านไกล, นาฬิกา+วันที่, KPI แถบใหญ่, แบนเนอร์เตือนกระพริบเมื่อมีบอทพัง, การ์ดจัดเต็มจออัตโนมัติ + หมุนหน้าเองเมื่อบอทเยอะเกินจอ, **panel ประวัติล่าสุดไหลแบบ real-time ที่ขอบขวา** (ปรับจำนวนแถวตามความสูงจอเอง), ซ่อนเคอร์เซอร์อัตโนมัติ — ปรับ threshold ค้างผ่าน URL ได้ เช่น `tv.html?stale=60`
- **ธีม Dark / Light** — ดีไซน์ professional, จำธีมที่เลือกไว้, ตัวบอกสถานะการเชื่อมต่อ (LIVE/offline) บนแถบบน

> **หมายเหตุเรื่อง KPI "Success Rate วันนี้"** — คำนวณจาก query ที่ดึง log **ตามวันที่** (`startAt(วันนี้)`) แยกจากตาราง History ที่ดึงตามจำนวน
> เพราะถ้าอิงหน้าต่าง "N รายการล่าสุด" วันไหนบอทยิง log เยอะ (เคยเจอวันละ ~4,500 รายการ) หน้าต่างจะครอบคลุมไม่ถึงทั้งวัน แล้วเปอร์เซ็นต์จะเพี้ยนแบบไม่มีอะไรเตือน
> หน้าจอที่เปิดค้างข้ามคืนจะย้าย listener ไปวันใหม่ให้เองอัตโนมัติ

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

### `timeoutStuckRunningBots` — ตัดบอทที่ค้าง Running นานผิดปกติ

| | |
|---|---|
| **ทำงานเมื่อ** | ทุกชั่วโมง (cron `0 * * * *`, timezone `Asia/Bangkok`) |
| **แก้ปัญหาอะไร** | บอทที่ตายกลางทาง (หรือลืมยิง log ตอนจบ) จะค้างเป็น `Running` บนหน้า Live ตลอดไป — เคยเจอค้างข้ามเดือน กิน slot บนจอ TV และทำให้ KPI "ค้าง/Stale" ชินตาจนไม่มีใครสนใจ |
| **ทำอะไร** | บอทที่ `Running` แต่ไม่มีสัญญาณเกิน **`TIMEOUT_HOURS` (ค่าเริ่มต้น 12 ชม.)** → เปลี่ยนสถานะเป็น `Timeout` + ใส่ `error_message` บอกว่าเงียบมากี่ชั่วโมง + บันทึกลง `rpa_history_logs` |
| **คง `status_datetime` เดิมไว้** | จะได้ยังเห็นว่า "เงียบมาตั้งแต่เมื่อไหร่" (เพิ่มฟิลด์ `timeout_at` แยกไว้แทน) |
| **บน Dashboard** | `Timeout` ถูก normalize เป็น **Failed** (สีแดง) — ถือว่ารันที่ไม่จบ = ไม่สำเร็จ |
| **ถ้าบอทกลับมา** | API เขียนทับสถานะให้เองตามปกติ ไม่ต้องทำอะไร |

### `pruneOldHistoryLogs` — ลบ log เก่าตาม retention

| | |
|---|---|
| **ทำงานเมื่อ** | ทุกวัน **02:30 เวลาไทย** (cron `30 2 * * *`) |
| **แก้ปัญหาอะไร** | `rpa_history_logs` โตขึ้นทุกวันโดยไม่มีเพดาน ทำให้ค่า storage/bandwidth โตตาม และ query ช้าลงเรื่อยๆ |
| **ทำอะไร** | ลบ record ที่เก่ากว่า **`RETENTION_DAYS` (ค่าเริ่มต้น 180 วัน)** ครั้งละไม่เกิน `MAX_DELETES_PER_RUN` (5,000) กันฟังก์ชัน timeout |
| **ไม่แตะ** | `rpa_live_status` |

> ⚠️ **ฟังก์ชันนี้ลบข้อมูลถาวร กู้คืนไม่ได้**
> ค่าเริ่มต้นตั้ง **`DRY_RUN = true`** ไว้ คือ *นับให้ดูใน log เฉยๆ ยังไม่ลบจริง*
> ให้ deploy แล้วดู Logs ก่อนว่าจะลบเท่าไหร่ พอใจแล้วค่อยเปลี่ยนเป็น `false` แล้ว deploy ใหม่

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
| **Dashboard** | Firebase Hosting | ✅ **อัตโนมัติ** — push main แล้ว GitHub Actions deploy ให้ (ดูหัวข้อถัดไป) |
| **Scheduled Jobs** | Cloud Functions | `cd web-rpa && firebase deploy --only functions` (ต้องเป็นแพลน Blaze) — ตั้งใจให้ทำมือ |
| **Security Rules** | Realtime Database | `cd web-rpa && firebase deploy --only database` — ตั้งใจให้ทำมือ |

### Auto-deploy Hosting (GitHub Actions)

[`.github/workflows/deploy-firebase.yml`](.github/workflows/deploy-firebase.yml) จะ deploy Hosting ให้อัตโนมัติ
เมื่อมีการ push เข้า `main` ที่แตะไฟล์ใน `web-rpa/public/**`

**ต้องตั้ง secret ครั้งเดียวก่อนใช้งาน** — เลือกทางใดทางหนึ่ง

#### ทาง A: service account (แนะนำ)

สิทธิ์จำกัดอยู่แค่ Hosting ของโปรเจกต์นี้เท่านั้น เหมาะกับ credential ที่ฝังไว้ใน CI

1. [Google Cloud Console → Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts?project=com7-rpa-log) → **Create service account** (ตั้งชื่อ เช่น `github-hosting-deploy`)
2. ให้ role **Firebase Hosting Admin**
3. คลิกเข้า service account → แท็บ **Keys** → Add key → Create new key → **JSON** → ดาวน์โหลด
4. ใส่เป็น secret:

```bash
gh secret set FIREBASE_SERVICE_ACCOUNT --repo COM7-RPA-TEAM/Com7_Log_RPA < "C:\path\to\key.json"
```

#### ทาง B: FIREBASE_TOKEN (ตั้งง่ายกว่า)

2 คำสั่งจบ ไม่ต้องเข้า Console — แต่ token นี้คือสิทธิ์ของ **บัญชี Google ทั้งบัญชี** (ทุกโปรเจกต์) ไม่ได้จำกัดแค่ Hosting

```bash
firebase login:ci
```

```bash
gh secret set FIREBASE_TOKEN --repo COM7-RPA-TEAM/Com7_Log_RPA
```

> คำสั่งที่สองจะรอให้วาง token ที่ได้จากคำสั่งแรก แล้วกด Enter + Ctrl+Z + Enter
> **อย่าวาง token ลงในแชทหรือ commit ลง git**

workflow รองรับทั้งสองแบบ — ถ้ามี `FIREBASE_SERVICE_ACCOUNT` จะใช้ตัวนั้นก่อน ไม่มีจึงใช้ `FIREBASE_TOKEN`
ถ้าไม่มีทั้งคู่ job จะ fail พร้อมข้อความบอกสาเหตุ

> Cloud Functions และ Database Rules **ไม่ถูก deploy อัตโนมัติโดยตั้งใจ** เพราะมีผลกระทบสูง
> (ลบข้อมูล / ตัดสิทธิ์เข้าถึง) ควรมีคนตรวจแล้วกดเอง

---

## 🔒 ความปลอดภัย (Database Rules + Login)

เดิม Realtime Database เปิดทั้งอ่านและเขียนให้ทุกคน — ใครรู้ URL ก็ยิง REST อ่านหรือลบข้อมูลทิ้งได้
[`web-rpa/database.rules.json`](web-rpa/database.rules.json) เปลี่ยนเป็น:

| | |
|---|---|
| **อ่าน** | เปิดให้ทุกคน — จอ TV (`tv.html`) เปิดค้างได้โดยไม่ต้อง login |
| **เขียน** | ต้อง login — ปุ่มแก้/ลบบน Dashboard จะเด้งให้เข้าสู่ระบบด้วย Google ก่อน |
| **path อื่น** | ปิดทั้งอ่านและเขียน |
| **API + Cloud Functions** | **ไม่กระทบเลย** — ใช้ Firebase Admin SDK ซึ่ง bypass rules ทั้งหมด บอททุกตัวยิง log ได้เหมือนเดิม ไม่ต้องแก้อะไร |

### ⚠️ ลำดับการเปิดใช้งาน (ทำผิดลำดับปุ่มแก้/ลบจะใช้ไม่ได้)

1. **Firebase Console → Authentication → Sign-in method → เปิด Google**
2. **Firebase Console → Project settings → Your apps** คัดลอก `apiKey` ของ Web app
   มาเติมใน `firebaseConfig` ที่ [`web-rpa/public/index.html`](web-rpa/public/index.html)
   (ค่านี้เปิดเผยได้ตามปกติของ Firebase Web SDK)
3. Deploy Hosting (push main ก็พอ)
4. ทดสอบกดปุ่ม **เข้าสู่ระบบ** บนแถบบนของ Dashboard ว่า login ได้จริง
5. ค่อย `cd web-rpa && firebase deploy --only database` เพื่อบังคับใช้ rules

> ถ้ายังไม่เติม `apiKey` ระบบจะซ่อนปุ่มเข้าสู่ระบบ และปล่อยให้แก้/ลบได้เหมือนเดิม
> — หน้าเว็บไม่พัง แค่ยังไม่ได้บังคับ login

---

## 🧪 เทส

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt -r requirements-dev.txt
.venv\Scripts\python -m pytest -q
```

เทสใน [`tests/`](tests/) ครอบสัญญาของ API ที่ระบบอื่นพึ่งพาอยู่ — ส่งแค่ `bot_name` + `status` ได้,
server เติมเวลาให้เมื่อไม่ส่งมา, เวลาที่ client ส่งมาต้องไม่ถูกเขียนทับ, ทุก log ต้องลงทั้ง live และ history,
และ payload ที่ไม่ครบต้องถูกปฏิเสธ **โดยไม่แตะ Firebase**

ใช้ `firebase_admin` ปลอม (ดู [`tests/conftest.py`](tests/conftest.py)) จึงไม่ต้องมี credential
และไม่มีทางเขียนโดน production

> [`testapi.py`](testapi.py) กับ [`testlogger.py`](testlogger.py) เป็นสคริปต์ลองยิงด้วยมือ **ที่ยิงเข้า production จริง**
> ไม่ใช่ automated test — จะไปโผล่เป็นการ์ดบน Dashboard และ TV

---

## Tech Stack

- **Backend:** FastAPI + Pydantic (Python 3.10) บน Google Cloud Run
- **Database:** Firebase Realtime Database (asia-southeast1)
- **Frontend:** HTML + Bootstrap 5 + Chart.js + Firebase JS SDK (Firebase Hosting)
- **Scheduled Jobs:** Cloud Functions (Node.js 20, Gen 2) + Cloud Scheduler
