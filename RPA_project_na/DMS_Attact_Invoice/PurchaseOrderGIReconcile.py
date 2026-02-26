import os
import re
import cv2
import time 
import pyodbc
import base64
import tempfile
# import pdfplumber
import numpy as np 
import pandas as pd 

from datetime import datetime
from selenium import webdriver
from urllib.parse import urljoin
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys 
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    ElementNotInteractableException,
    ElementClickInterceptedException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException
)

from typhoon_ocr import ocr_document

def login_dms_gi_process(comp_login_info):

    attemp_start = 1 
    max_attemp = 3 
    while attemp_start <= max_attemp:
        try:

            opts = Options()
            prefs = {
                "download.default_directory": relative_download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True,
            }
            opts.add_experimental_option("prefs", prefs)

            driver = webdriver.Chrome(service=Service(),options=opts)
            driver.get(comp_login_info[3])
            driver.maximize_window()
            
            username_input =  WebDriverWait(    driver=driver, 
                                                timeout=180,
                                                poll_frequency=5,
                                                ignored_exceptions=(NoSuchElementException,StaleElementReferenceException,ElementNotInteractableException)
                                            ).until(EC.presence_of_element_located((By.XPATH,"//input[@placeholder='User name']")))
            username_input.send_keys(comp_login_info[1])

            password_input = WebDriverWait(    driver=driver, 
                                                timeout=180,
                                                poll_frequency=5,
                                                ignored_exceptions=(NoSuchElementException,StaleElementReferenceException,ElementNotInteractableException)
                                            ).until(EC.presence_of_element_located((By.XPATH,"//input[@placeholder='Password']")))
            password_input.send_keys(comp_login_info[2])

            img = WebDriverWait(    driver=driver, 
                                    timeout=180,
                                    poll_frequency=5,
                                    ignored_exceptions=(NoSuchElementException,StaleElementReferenceException,ElementNotInteractableException)
                                ).until(EC.presence_of_element_located((By.CSS_SELECTOR,"img.verification-code")))
            
            capcha_text = decode_capcha(img=img)

            capcha_code = WebDriverWait(    driver=driver, 
                                            timeout=180,
                                            poll_frequency=5,
                                            ignored_exceptions=(NoSuchElementException,StaleElementReferenceException,ElementNotInteractableException)
                                            ).until(EC.presence_of_element_located((By.XPATH,"//input[@placeholder='Verification code']")))
            capcha_code.send_keys(capcha_text)

            login = WebDriverWait(    driver=driver, 
                                            timeout=180,
                                            poll_frequency=5,
                                            ignored_exceptions=(NoSuchElementException,StaleElementReferenceException,ElementNotInteractableException)
                                            ).until(EC.presence_of_element_located((By.CSS_SELECTOR, "button.submit-form-action-button")))
            login.click()

            lang_icon = WebDriverWait(    driver=driver, 
                                            timeout=10,
                                            poll_frequency=5,
                                            ignored_exceptions=(NoSuchElementException,StaleElementReferenceException,ElementNotInteractableException)
                                            ).until(EC.presence_of_element_located((By.XPATH, '/html/body/div/div/div[2]/div[1]/div[4]/div[3]/span')))
            lang_icon.click()

            time.sleep(3)
            eng_btn = WebDriverWait(    driver=driver, 
                                            timeout=180,
                                            poll_frequency=5,
                                            ignored_exceptions=(NoSuchElementException,StaleElementReferenceException,ElementNotInteractableException)
                                            ).until(EC.presence_of_element_located((By.XPATH,'/html/body/ul/li[2]')))
            eng_btn.click()
            time.sleep(3)

            # xpath = //*[@id="app"]/div/div[1]/div/ul/div/li[11]/div/span
            # full xpath = /html/body/div/div/div[1]/div/ul/div/li[11]/div/span
            Fund_settlement = WebDriverWait(    driver=driver, 
                                            timeout=180,
                                            poll_frequency=5,
                                            ignored_exceptions=(NoSuchElementException,StaleElementReferenceException,ElementNotInteractableException)
                                            ).until(EC.presence_of_element_located((By.XPATH,'/html/body/div/div/div[1]/div/ul/div/li[11]/div/span')))
            Fund_settlement.click()

            # //*[@id="app"]/div/div[1]/div/ul/div/li[11]/ul/div[1]/li/div/span
            # /html/body/div/div/div[1]/div/ul/div/li[11]/ul/div[1]/li/div/span
            part_settlement = WebDriverWait(    driver=driver, 
                                            timeout=180,
                                            poll_frequency=5,
                                            ignored_exceptions=(NoSuchElementException,StaleElementReferenceException,ElementNotInteractableException)
                                            ).until(EC.presence_of_element_located((By.XPATH,'/html/body/div/div/div[1]/div/ul/div/li[11]/ul/div[1]/li/div/span')))
            part_settlement.click()
            time.sleep(2)

            # //*[@id="app"]/div/div[1]/div/ul/div/li[11]/ul/div[1]/li/ul/div[2]/a/li/span
            # /html/body/div/div/div[1]/div/ul/div/li[11]/ul/div[1]/li/ul/div[2]/a/li/span
            invoice = WebDriverWait(    driver=driver, 
                                            timeout=180,
                                            poll_frequency=5,
                                            ignored_exceptions=(NoSuchElementException,StaleElementReferenceException,ElementNotInteractableException)
                                            ).until(EC.presence_of_element_located((By.XPATH,'/html/body/div/div/div[1]/div/ul/div/li[11]/ul/div[1]/li/ul/div[2]/a/li/span')))
            invoice.click()
            time.sleep(2)

            #/html/body/div/div/div[2]/section/section/div/div[1]/div[1]/div[2]/div/button
            export_invoice = WebDriverWait(    driver=driver, 
                                            timeout=180,
                                            poll_frequency=5,
                                            ignored_exceptions=(NoSuchElementException,StaleElementReferenceException,ElementNotInteractableException)
                                            ).until(EC.presence_of_element_located((By.XPATH,'/html/body/div/div/div[2]/section/section/div/div[1]/div[1]/div[2]/div/button')))
            export_invoice.click()

            time.sleep(5000)
            return 0
        except Exception as error : 
            attemp_start = attemp_start + 1

def decode_capcha(img):
    b64_str = img.screenshot_as_base64

    if "," in b64_str:
        b64_str = b64_str.split(",")[1]

    img_bytes = base64.b64decode(b64_str)

    img_array = np.frombuffer(img_bytes, dtype=np.uint8)
    
    img_cv2 = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

        # แปลง BGR (ของ cv2) → RGB (easyocr ใช้แบบนี้จะเนียนกว่า)
    img_rgb = cv2.cvtColor(img_cv2, cv2.COLOR_BGR2GRAY)

    with open('verfication_code.png','wb') as f:
        f.write(img_bytes)

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        temp_path = tmp.name
        cv2.imwrite(temp_path, img_rgb)

    
    capcha_text = ocr_document(temp_path).replace(' ','')
    print(capcha_text)
    
    return capcha_text

def etl_parts_invoicing_info(gi_filepath):
    info = pd.read_excel(gi_filepath)
    index_cols = ["Purchase order number", "order no", "business type","dealer name", "dealer code"]

    wide = (
        info.pivot_table(
            index=index_cols,
            columns="bill type",
            values=["billing no", "invoice date"],
            aggfunc="first"   
        )
    )

    wide.columns = [f"{bill.replace(' ','')}_{val.replace(' ','')}" for val, bill in wide.columns]
    parts_info = wide.reset_index()

    print(parts_info)

    return parts_info

def extract_invoice_amount_info(inv_pdf_filepath="SparePartsTaxInvoice-TITI2024100060.pdf"):

    with pdfplumber.open(inv_pdf_filepath) as pdf:

        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            # print(text)
            try: 
                pbv = re.search('Sub-total (\d[\d,]*(?:\.\d+)?)',text).groups()[0].replace(',','')
                vat = re.search('VAT (\d[\d,]*(?:\.\d+)?)',text).groups()[0].replace(',','')
                pav = re.search('Grand total (\d[\d,]*(?:\.\d+)?)',text).groups()[0].replace(',','')
                print(pbv,vat,pav)
            except:
                pbv = np.NAN
                vat = np.NAN
                pav = np.NAN
    
    return (pbv,vat,pav)

if __name__ == "__main__":
    based_path = os.getcwd()
    os.environ["TYPHOON_OCR_API_KEY"] = "sk-5GDFvDdaQa3B7D3AHpIyIpw0F8BO0rPzIDa6uKwqhF1Xhey9"

    gi_info_path = os.path.join(based_path,'Configuration','GI_UsernamePassword.xlsx')

    gi_login_info = pd.read_excel(gi_info_path)
    print(gi_login_info.columns)
    
    for index,company_info in gi_login_info.iterrows():
        
        comcode = company_info['NO.']
        username = company_info['User DMS']
        password = company_info['Password']
        link = company_info['Link']

        print(comcode,username,password,link) 
        relative_download_dir = company_info['RelativePath']

        if os.path.exists(os.path.join(based_path,relative_download_dir)):
            pass
        else:
            os.mkdir(os.path.join(based_path,relative_download_dir))

        comp_login_info = (comcode,username,password,link,relative_download_dir)
        login_dms_gi_process( comp_login_info = comp_login_info )
        

        # break

    # etl_parts_invoicing_info()
    # extract_invoice_amount_info()