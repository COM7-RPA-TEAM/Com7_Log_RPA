# ใช้ Python เวอร์ชัน 3.10
FROM python:3.10-slim

# กำหนดโฟลเดอร์สำหรับทำงาน
WORKDIR /app

# ก๊อปปี้ไฟล์ทั้งหมดในโปรเจกต์เรา (main.py, requirements.txt) เข้าไป
COPY . /app

# ติดตั้ง Library ที่จำเป็น
RUN pip install --no-cache-dir -r requirements.txt

# สั่งรัน FastAPI เมื่อเซิร์ฟเวอร์เปิด
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]