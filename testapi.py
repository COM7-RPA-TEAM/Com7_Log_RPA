import requests

# 🚨 เปลี่ยน URL ด้านล่างนี้ให้เป็น URL จาก Google Cloud Run ของคุณ
# สำคัญ: ต้องมี /api/v1/bot-log ต่อท้ายด้วยนะครับ
API_URL = "https://com7rpalog-436289358307.asia-southeast3.run.app/api/v1/bot-log"

payload = {
    "bot_name": "Test_Bot_02",
    "status": "Running",
    "stage": "1 - Open Browser",
    "error_message": ""
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


    