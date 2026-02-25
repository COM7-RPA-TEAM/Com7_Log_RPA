import os
import json
from fastapi import FastAPI
from pydantic import BaseModel
import firebase_admin
from firebase_admin import credentials, db

app = FastAPI(title="RPA Logging API")

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

# 1. ปรับปรุงรูปแบบข้อมูลให้ตรงกับ Payload ใหม่
class BotLog(BaseModel):
    bot_name: str
    stage: str
    status: str
    status_datetime: str  # <--- เพิ่มตัวแปรนี้เข้ามารับเวลาจาก Bot
    error_message: str = ""

@app.post("/api/v1/bot-log")
async def receive_bot_log(log: BotLog):
    # 2. ไม่ต้องใช้ datetime ของฝั่ง API แล้ว ใช้ log.status_datetime ที่รับมาได้เลย
    ref = db.reference(f'rpa_live_status/{log.bot_name}')
    
    ref.update({
        'status': log.status,
        'stage': log.stage,
        'error_message': log.error_message,
        'status_datetime': log.status_datetime  # <--- บันทึกลง Firebase ด้วย Key ใหม่
    })
    
    return {"message": "Success", "bot": log.bot_name, "time": log.status_datetime}

@app.get("/")
def read_root():
    return {"message": "RPA Logging API is Running!"}