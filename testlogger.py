from selenium import webdriver
from selenium.webdriver.common.by import By
import time

# 1. Import ตัวช่วยเข้ามา และตั้งชื่อ Bot
from rpa_logger import DashboardLogger
log = DashboardLogger(bot_name="Test_Bot_06")

def run_rpa():
    try:
        # 2. เรียกใช้ log.send_log() ตามจุดต่างๆ ได้เลย!
        log.send_log(stage="1 - Start Open Browser", status="Running")
        
        driver = webdriver.Chrome()
        driver.get("https://google.com")
        time.sleep(2)

        log.send_log(stage="2 - Input Search Data", status="Running")
        # โค้ด Selenium ของคุณ
        # driver.find_element(By.NAME, "q").send_keys("Com7")

        log.send_log(stage="3 - Downloading Report", status="Running")
        # ... กระบวนการโหลดไฟล์ ...

        # 3. จบงานสำเร็จ
        log.send_log(stage="Completed", status="Success")

    except Exception as e:
        # 4. ดักจับ Error แล้วส่งขึ้น Dashboard ให้หัวหน้าเห็นทันที
        log.send_log(stage="Failed at some stage", status="Failed", error_message=str(e))
        
    finally:
        driver.quit()

if __name__ == "__main__":
    run_rpa()