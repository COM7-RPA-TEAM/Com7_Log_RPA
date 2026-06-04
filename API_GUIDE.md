# คู่มือใช้งาน RPA Logging API (ฉบับง่าย)

ส่ง Log สถานะการทำงานของ RPA/บอท ขึ้น Dashboard กลาง เพื่อดูภาพรวมว่าตัวไหน Running / Success / Failed

> **Dashboard:** ดูผลแบบ Real-time ได้ที่หน้าเว็บ Dashboard
> **ทดลองยิง API จากเบราว์เซอร์ได้เลย (Swagger):** https://com7rpalog-436289358307.asia-southeast3.run.app/docs

---

## 1. ยิงไปที่ไหน

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `https://com7rpalog-436289358307.asia-southeast3.run.app/api/v1/bot-log` |
| **Header** | `Content-Type: application/json` |
| **Body** | JSON (ตามตารางด้านล่าง) |

---

## 2. ส่ง Parameter อะไรบ้าง

| Parameter | บังคับ? | ชนิด | คำอธิบาย |
|-----------|:------:|------|----------|
| `bot_name` | ✅ **ใช่** | string | ชื่อบอท/RPA — **ต้องไม่ซ้ำกับระบบอื่น** (ใช้เป็น Key บน Live Dashboard ถ้าซ้ำจะทับกัน) |
| `status` | ✅ **ใช่** | string | สถานะ → ใช้ `Running` / `Success` / `Failed` (เพื่อให้ขึ้นสีถูก) |
| `stage` | ❌ ไม่ | string | ขั้นตอนปัจจุบัน เช่น `"2 - Download Report"` (ไม่ส่ง = ว่าง) |
| `error_message` | ❌ ไม่ | string | ข้อความ Error ใส่ตอน `status = Failed` |
| `status_datetime` | ❌ ไม่ | string | เวลา `YYYY-MM-DD HH:MM:SS` — **ไม่ต้องส่งก็ได้ ระบบจะเติมเวลาไทยให้อัตโนมัติ** |

> 💡 **ง่ายสุด:** ส่งแค่ `bot_name` กับ `status` ก็พอ ที่เหลือ optional

### Body ที่สั้นที่สุด
```json
{ "bot_name": "Finance_SendPO", "status": "Running" }
```

### Body แบบเต็ม (ตอนบอทพัง)
```json
{
  "bot_name": "Finance_SendPO",
  "status": "Failed",
  "stage": "3 - Submit Form",
  "error_message": "Element not found: #submit-btn"
}
```

---

## 3. ตัวอย่างการเรียกใช้ (ก๊อปไปใช้ได้เลย)

### 🐍 Python — ใช้ตัวช่วย `rpa_logger.py` (แนะนำ)
```python
from rpa_logger import DashboardLogger

log = DashboardLogger(bot_name="Finance_SendPO")

log.send_log(stage="1 - Open Browser", status="Running")
# ... ทำงาน ...
log.send_log(stage="Completed", status="Success")

# ตอนพัง
log.send_log(stage="3 - Submit", status="Failed", error_message=str(e))
```

### 🐍 Python — ยิงตรง (ไม่ใช้ตัวช่วย)
```python
import requests

requests.post(
    "https://com7rpalog-436289358307.asia-southeast3.run.app/api/v1/bot-log",
    json={"bot_name": "Finance_SendPO", "status": "Running", "stage": "1 - Start"},
    timeout=5
)
```

### 💻 PowerShell
```powershell
$body = @{ bot_name = "Finance_SendPO"; status = "Success"; stage = "Completed" } | ConvertTo-Json
Invoke-RestMethod -Method Post `
  -Uri "https://com7rpalog-436289358307.asia-southeast3.run.app/api/v1/bot-log" `
  -ContentType "application/json" -Body $body
```

### 🌐 curl
```bash
curl -X POST "https://com7rpalog-436289358307.asia-southeast3.run.app/api/v1/bot-log" \
  -H "Content-Type: application/json" \
  -d '{"bot_name":"Finance_SendPO","status":"Running","stage":"1 - Start"}'
```

### 🤖 UiPath / Power Automate (HTTP Request)
- **Method:** POST
- **URL:** `https://com7rpalog-436289358307.asia-southeast3.run.app/api/v1/bot-log`
- **Headers:** `Content-Type = application/json`
- **Body:** `{"bot_name":"Finance_SendPO","status":"Running","stage":"1 - Start"}`

---

## 4. ควรยิงตอนไหน (แนะนำ)

| จังหวะ | status | ตัวอย่าง |
|--------|--------|----------|
| เริ่มงาน / เปลี่ยนขั้นตอน | `Running` | `{"bot_name":"X","status":"Running","stage":"2 - Download"}` |
| ทำงานเสร็จ | `Success` | `{"bot_name":"X","status":"Success","stage":"Completed"}` |
| เกิด Error | `Failed` | `{"bot_name":"X","status":"Failed","error_message":"..."}` |

> ⚠️ ยิง `Running` เมื่อเริ่มทุกครั้ง — ถ้าบอทค้าง/ตายไปเฉยๆ Dashboard จะจับได้ว่า "ค้าง" (Running แต่เงียบนานเกินกำหนด)

---

## 5. ผลลัพธ์ที่ได้กลับ (Response)

สำเร็จจะได้ HTTP `200` พร้อม:
```json
{
  "message": "Success - Logged to both Live and History",
  "bot": "Finance_SendPO",
  "time": "2026-06-04 11:35:50"
}
```

> เคล็ดลับ: ฝั่งบอทควรตั้ง `timeout=5` และครอบ try/except ไว้ เพื่อไม่ให้บอทค้าง/พัง หากเครือข่ายมีปัญหา (ตัวช่วย `rpa_logger.py` ทำให้แล้ว)
