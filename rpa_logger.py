import requests
import datetime

class DashboardLogger:
    def __init__(self, bot_name):
        self.bot_name = bot_name
        # ใส่ URL ของ API คุณไว้ตรงนี้ที่เดียวจบ
        self.api_url = "https://com7rpalog-436289358307.asia-southeast3.run.app/api/v1/bot-log"

    def send_log(self, stage, status, error_message=""):
        payload = {
            "bot_name": self.bot_name,
            "stage": stage,
            "status": status,
            "status_datetime": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error_message": error_message
        }
        try:
            # 🚨 ใส่ timeout=5 ไว้สำคัญมาก เพื่อไม่ให้บอทค้างถ้าเน็ตมีปัญหา
            requests.post(self.api_url, json=payload, timeout=5)
        except Exception as e:
            # ถ้าส่ง API ไม่สำเร็จ ก็แค่ปรินต์บอก ไม่ต้องให้บอทพัง
            print(f"⚠️ ไม่สามารถส่งข้อมูลขึ้น Dashboard ได้: {e}")