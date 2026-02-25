import os
from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime
import firebase_admin
from firebase_admin import db

app = FastAPI(title="RPA Logging API")

# เชื่อมต่อ Firebase (ไม่ต้องใช้ไฟล์ JSON เพราะ Google Cloud จะจัดการสิทธิ์ให้เอง)
# 🚨 เปลี่ยน URL ด้านล่างเป็นของคุณที่ก็อปปี้มาจากขั้นตอนที่ 1
firebase_admin.initialize_app(options={
    'databaseURL': 'https://com7-rpa-log-default-rtdb.asia-southeast1.firebasedatabase.app/'
})

# กำหนดรูปแบบข้อมูลที่ Bot จะส่งมา
class BotLog(BaseModel):
    bot_name: str
    status: str
    stage: str
    error_message: str = ""

@app.post("/api/v1/bot-log")
async def receive_bot_log(log: BotLog):
    # ดึงเวลาปัจจุบัน (เวลาไทย UTC+7)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # อัปเดตข้อมูลลง Firebase (สร้างโฟลเดอร์ชื่อ rpa_live_status และตามด้วยชื่อ Bot)
    ref = db.reference(f'rpa_live_status/{log.bot_name}')
    ref.update({
        'status': log.status,
        'stage': log.stage,
        'error_message': log.error_message,
        'last_update': timestamp
    })
    
    return {"message": "Success", "bot": log.bot_name, "time": timestamp}

# หน้าแรกสำหรับทดสอบว่า API รันอยู่หรือไม่
@app.get("/")
def read_root():
    return {"message": "RPA Logging API is Running!"}