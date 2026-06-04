import os
import json
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI
from pydantic import BaseModel
import firebase_admin
from firebase_admin import credentials, db

app = FastAPI(title="RPA Logging API")

# โซนเวลาไทย (Asia/Bangkok = UTC+7) ใช้ตอน Server ประทับเวลาให้อัตโนมัติ
BKK = timezone(timedelta(hours=7))

# ป้องกันการเชื่อมต่อ Firebase ซ้ำซ้อน
if not firebase_admin._apps:
    firebase_cert = os.environ.get("FIREBASE_CERT")
    
    if firebase_cert:
        cert_dict = json.loads(firebase_cert)
        cred = credentials.Certificate(cert_dict)
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://com7-rpa-log-default-rtdb.asia-southeast1.firebasedatabase.app/'
        })
        print("✅ เชื่อมต่อ Firebase สำเร็จ (ด้วย Private Key)")
    else:
        firebase_admin.initialize_app(options={
            'databaseURL': 'https://com7-rpa-log-default-rtdb.asia-southeast1.firebasedatabase.app/'
        })
        print("✅ เชื่อมต่อ Firebase สำเร็จ (ด้วย Default IAM)")

class BotLog(BaseModel):
    # --- บังคับ (Required) ---
    bot_name: str                          # ชื่อบอท/RPA (ใช้เป็น Key บน Live Dashboard ต้องไม่ซ้ำกัน)
    status: str                            # สถานะ เช่น Running / Success / Failed

    # --- ไม่บังคับ (Optional) ---
    stage: str = ""                        # ขั้นตอนปัจจุบัน เช่น "Download Report"
    error_message: str = ""                # ข้อความ error (ใส่เมื่อ status = Failed)
    status_datetime: str | None = None     # เวลา "YYYY-MM-DD HH:MM:SS" — ถ้าไม่ส่งมา Server จะเติมให้เอง (เวลาไทย)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"bot_name": "Finance_SendPO", "status": "Running", "stage": "1 - Open Browser"},
                {"bot_name": "Finance_SendPO", "status": "Failed", "stage": "3 - Submit", "error_message": "Element not found"}
            ]
        }
    }

@app.post("/api/v1/bot-log")
async def receive_bot_log(log: BotLog):
    # ถ้าระบบที่ยิงเข้ามาส่ง status_datetime มา -> ใช้ค่านั้น (พฤติกรรมเดิมไม่เปลี่ยน)
    # ถ้าไม่ส่งมา (None หรือว่าง) -> Server เติมเวลาไทยให้อัตโนมัติ
    status_datetime = log.status_datetime or datetime.now(BKK).strftime("%Y-%m-%d %H:%M:%S")

    # ==========================================
    # งานที่ 1: อัปเดตสถานะล่าสุด (สำหรับแสดงบนหน้า Live Dashboard)
    # (ใช้ชื่อบอทเป็น Key -> ข้อมูลเก่าจะถูกเขียนทับเสมอ)
    # ==========================================
    live_ref = db.reference(f'rpa_live_status/{log.bot_name}')
    live_ref.update({
        'status': log.status,
        'stage': log.stage,
        'error_message': log.error_message,
        'status_datetime': status_datetime
    })

    # ==========================================
    # งานที่ 2: บันทึกประวัติการรันทั้งหมด (Historical Log สำหรับนำไปวิเคราะห์)
    # (ใช้ .push() -> สร้าง Record ใหม่ทุกครั้งที่ยิงเข้ามา ไม่มีการเขียนทับ)
    # ==========================================
    history_ref = db.reference('rpa_history_logs')
    history_ref.push({
        'bot_name': log.bot_name,
        'status': log.status,
        'stage': log.stage,
        'error_message': log.error_message,
        'status_datetime': status_datetime
    })

    return {"message": "Success - Logged to both Live and History", "bot": log.bot_name, "time": status_datetime}

@app.get("/")
def read_root():
    return {"message": "RPA Logging API is Running!"}