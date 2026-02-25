import os
import json
from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, db

app = FastAPI(title="RPA Logging API")

# ป้องกันการเชื่อมต่อ Firebase ซ้ำซ้อนตอน Cloud Run รีสตาร์ท
if not firebase_admin._apps:
    # 1. พยายามดึงกุญแจความลับ (Private Key) จากการตั้งค่าของ Cloud Run
    firebase_cert = os.environ.get("FIREBASE_CERT")
    
    if firebase_cert:
        # ถ้าเจอกุญแจ ให้แปลรหัสและเข้าแบบ VIP (แก้ปัญหา Error 401 Unauthorized 100%)
        cert_dict = json.loads(firebase_cert)
        cred = credentials.Certificate(cert_dict)
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://com7-rpa-log-default-rtdb.asia-southeast1.firebasedatabase.app/'
        })
        print("✅ เชื่อมต่อ Firebase สำเร็จ (ด้วย Private Key)")
    else:
        # 2. ถ้าไม่เจอกุญแจ ให้ลองเข้าด้วยสิทธิ์ Default
        firebase_admin.initialize_app(options={
            'databaseURL': 'https://com7-rpa-log-default-rtdb.asia-southeast1.firebasedatabase.app/'
        })
        print("✅ เชื่อมต่อ Firebase สำเร็จ (ด้วย Default IAM)")

# รูปแบบข้อมูลที่รับเข้ามา
class BotLog(BaseModel):
    bot_name: str
    status: str
    stage: str
    error_message: str = ""

@app.post("/api/v1/bot-log")
async def receive_bot_log(log: BotLog):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # อัปเดตข้อมูลลง Database ทันที
    ref = db.reference(f'rpa_live_status/{log.bot_name}')
    ref.update({
        'status': log.status,
        'stage': log.stage,
        'error_message': log.error_message,
        'last_update': timestamp
    })
    
    return {"message": "Success", "bot": log.bot_name, "time": timestamp}

@app.get("/")
def read_root():
    return {"message": "RPA Logging API is Running!"}