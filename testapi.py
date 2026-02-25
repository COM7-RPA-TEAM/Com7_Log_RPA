import requests
import datetime

# 🚨 เปลี่ยน URL ด้านล่างนี้ให้เป็น URL จาก Google Cloud Run ของคุณ
# สำคัญ: ต้องมี /api/v1/bot-log ต่อท้ายด้วยนะครับ
API_URL = "https://com7rpalog-436289358307.asia-southeast3.run.app/api/v1/bot-log"

payload = {
    "bot_name": "Test_Bot_07",
    "stage": "1 - Attach Invoice",
    "status": "Running",
    "status_datetime": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "error_message": "xxx"
}

print(f"กำลังส่งข้อมูลไปที่: {API_URL}")
try:
    response = requests.post(API_URL, json=payload)
    print("Status Code:", response.status_code)
    
    if response.status_code == 200:
        print("Response:", response.json())
    else:
        print("Error จาก Server:", response.text) # <--- ให้มันพ่นข้อความ Error ดิบๆ ออกมาเลย
except Exception as e:
    print("Error:", e)


    