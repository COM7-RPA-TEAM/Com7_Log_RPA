import datetime
from pathlib import Path
import time, re
import traceback
from xmlrpc.client import _datetime
import cv2
from typing import Optional, Union
import numpy as np
import pandas as pd
import pyautogui
from selenium.webdriver.common.action_chains import ActionChains
from Get_Value_Form_DataBase import fetch_df, SQL, return_value_Of_data
from run_invoice_automation import DOWNLOAD_DIR



from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.remote.webdriver import WebDriver

from Get_Value_Form_DataBase import return_value_Of_data

URLDMS = "https://globaldms.aionauto.com/login"
OUTPUT_DIR = Path(r"C:\Users\comseven\Downloads\captcha_shots"); OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
IMG_PATH = OUTPUT_DIR / "captcha.png"
PREPROC_PATH = OUTPUT_DIR / "captcha_preproc.png"

MIN_CONF = 0.95
REQUIRED_LEN = 4


POST_LOGIN_LOCATOR = (By.XPATH, "//aside//ul[contains(@class,'el-menu')]")

USERNAME = "giit_sala"
PASSWORD = "Gold@rama31"

def preprocess_and_save(img_path: Union[str, Path], out_preproc: Union[str, Path],
                        min_area=40, min_h=8, min_w=4, thicken=1) -> Optional[Path]:
    img_path, out_preproc = Path(img_path), Path(out_preproc)
    raw = cv2.imread(str(img_path))
    if raw is None: return None
    gray = cv2.cvtColor(raw, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 3)
    _, bin_inv = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    bin_inv = cv2.morphologyEx(bin_inv, cv2.MORPH_OPEN, np.ones((2,2), np.uint8), iterations=1)
    contours, _ = cv2.findContours(bin_inv, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    mask = np.zeros_like(bin_inv)
    for cnt in contours:
        x,y,w,h = cv2.boundingRect(cnt); area = cv2.contourArea(cnt)
        if area >= min_area and h >= min_h and w >= min_w:
            cv2.drawContours(mask, [cnt], -1, 255, -1)
    if thicken > 0: mask = cv2.dilate(mask, np.ones((thicken, thicken), np.uint8), iterations=1)
    result = cv2.bitwise_not(mask)
    out_preproc.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_preproc), result)
    return out_preproc

def clean_token(s): 
    return re.sub(r'[^A-Z0-9]', '', s.upper())

def compute_avg_conf_weighted(tokens):
    total_chars = sum(len(t) for t,_ in tokens)
    if total_chars == 0: return 0.0
    return sum(c*len(t) for t,c in tokens)/total_chars

def wait_login_result(driver, timeout=12):
    """รอผลหลัง submit: True=สำเร็จ, False=ล้มเหลว"""
    start = time.time()
    while time.time() - start < timeout:
        if "/login" not in driver.current_url:
            return True
        try:
            if driver.find_elements(*POST_LOGIN_LOCATOR):
                return True
        except Exception:
            pass
        # ถ้าเว็บโชว์ toast/error ของ Element-UI ให้ถือว่าไม่ผ่านเร็วขึ้น
        if driver.find_elements(By.CSS_SELECTOR, ".el-message--error, .el-form-item__error, .error"):
            return False
        time.sleep(0.3)
    return False



def init_driverDMS(url = None):
    """เปิด Chrome + กลับ WebDriver/Wait ที่พร้อมใช้งาน"""
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    # chrome_options.add_experimental_option("detach", True)  # ค้างเบราว์เซอร์หลังจบ (ถ้าต้องการ)
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    wait = WebDriverWait(driver, 20)
    driver.get(url)
    return driver, wait

def prepare_login_inputs(wait, username, password):
    """หา input ทั้ง 3 และกรอก user/pass ไว้ก่อน คืนค่า (username_box, password_box, captcha_box, img_elem)"""
    inputs = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "input.el-input__inner")))
    if len(inputs) < 3:
        raise RuntimeError("ไม่พบ input ครบ 3 ช่อง (user/pass/captcha)")
    username_box, password_box, captcha_box = inputs[0], inputs[1], inputs[2]
    username_box.clear(); username_box.send_keys(username)
    password_box.clear(); password_box.send_keys(password)
    img_elem = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "img.verification-code")))
    wait.until(lambda d: d.execute_script("return arguments[0].naturalWidth > 0;", img_elem))
    return username_box, password_box, captcha_box, img_elem

def change_language_via_keyboard(driver: WebDriver, tabs: int = 3, down_presses: int = 2, pause: float = 0.25):
    try:
        driver.execute_script("document.body.focus();")
    except Exception:
        pass
    ac = ActionChains(driver)
    for _ in range(tabs):
        ac = ac.send_keys(Keys.TAB).pause(0.05)
    ac = ac.send_keys(Keys.ENTER).pause(pause)
    for _ in range(down_presses):
        ac = ac.send_keys(Keys.ARROW_DOWN).pause(0.05)
    ac = ac.send_keys(Keys.ENTER)
    try:
        ac.perform()
        time.sleep(0.6)
    except Exception:
        # fallback: active_element sends
        try:
            el = driver.switch_to.active_element
            for _ in range(tabs):
                el.send_keys(Keys.TAB); time.sleep(0.05)
            el.send_keys(Keys.ENTER); time.sleep(pause)
            for _ in range(down_presses):
                el.send_keys(Keys.ARROW_DOWN); time.sleep(0.05)
            el.send_keys(Keys.ENTER); time.sleep(0.6)
        except Exception:
            pass

def click_three_buttons(driver: WebDriver,
                        sel1: str = "span.menuWidth",
                        sel2: str = "span.twoMenuWidth",
                        sel3: str = "span[id*='SalesReceiptNoteOriginalCopy']",
                        pause: float = 0.35) -> bool:
    js = "var e=document.querySelector(arguments[0]); if(e){ (e.closest('button')||e).click(); }"
    try: driver.execute_script(js, sel1)
    except: pass
    time.sleep(pause)
    try: driver.execute_script(js, sel2)
    except: pass
    time.sleep(pause)
    try: driver.execute_script(js, sel3)
    except: pass
    time.sleep(pause)
    return True

def change_lang_then_click_menus(driver: WebDriver, tabs=3, down_presses=2):
    change_language_via_keyboard(driver, tabs=tabs, down_presses=down_presses, pause=0.25)
    time.sleep(0.8)
    click_three_buttons(driver)

def find_and_click(driver, wait, selector: str, timeout: float = 6) -> bool:
    """
    พยายามหา element ด้วย WebDriverWait แล้วคลิก (robust).
    Fallbacks:
     - JS querySelector + click
     - search inside iframes
    คืน True ถ้าพยายามคลิกสำเร็จ (หรือ element ถูกคลิกด้วย JS)
    """
    # 1) try wait -> clickable
    try:
        el = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
        try:
            el.click()
        except Exception:
            driver.execute_script("arguments[0].click();", el)
        return True
    except Exception:
        pass

    # 2) try JS in main document
    try:
        clicked = driver.execute_script(
            "var sel=arguments[0]; var e=document.querySelector(sel); if(e){ (e.closest('button')||e).click(); return true;} return false;",
            selector
        )
        if clicked:
            return True
    except Exception:
        pass

    # 3) try inside iframes (best-effort)
    frames = driver.find_elements(By.TAG_NAME, "iframe")
    for frm in frames:
        try:
            driver.switch_to.frame(frm)
            # try JS inside frame
            try:
                clicked = driver.execute_script(
                    "var sel=arguments[0]; var e=document.querySelector(sel); if(e){ (e.closest('button')||e).click(); return true;} return false;",
                    selector
                )
                if clicked:
                    driver.switch_to.default_content()
                    return True
            except Exception:
                pass
            # try presence then click
            try:
                el = WebDriverWait(driver, 1).until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                try:
                    el.click()
                except:
                    driver.execute_script("arguments[0].click();", el)
                driver.switch_to.default_content()
                return True
            except Exception:
                driver.switch_to.default_content()
                continue
        except Exception:
            try:
                driver.switch_to.default_content()
            except:
                pass
            continue

    # ไม่พบ / ไม่สำเร็จ
    return False


def click_menu_sequence(driver, wait: WebDriverWait,
                        selectors=None,
                        pause: float = 0.35,
                        per_click_timeout: float = 6.0) -> bool:
    """
    คลิกลำดับเมนูแบบ robust:
      selectors: list of CSS selectors ในลำดับที่จะคลิก (default เหมาะกับ UI ที่ส่งมา)
      wait: WebDriverWait ที่สร้างไว้ (เช่น WebDriverWait(driver, 20))
      pause: หน่วงสั้น ๆ ระหว่างคลิก
      per_click_timeout: wait timeout สำหรับหาแต่ละ element
    คืน True ถ้าพยายามคลิกครบ sequence อย่างน้อยบางขั้นตอนสำเร็จ (best-effort)
    """
    if selectors is None:
        # ค่าเริ่มต้นตามภาพ: เปิด dropdown -> เปิด submenu title -> คลิก item
        selectors = [
            "span.menuWidth",           # (หรือ selector ปุ่ม dropdown แรก)
            "div.el-submenu__title",    # subtitle ที่เห็นในภาพ (hover/click เพื่อโชว์ submenu)
            "li.el-menu-item"           # menu item จริงๆ (เลือกเฉพาะที่ต้องการถ้าจำเป็น)
        ]

    any_clicked = False

TARGET_PAGE = "https://globaldms.aionauto.com/thailand/#/salesorder/dcs/order/orderReportFact/index/salesordermanage/index"

def change_lang_and_open_page(driver: WebDriver, wait: WebDriverWait,
                              target_url: str = TARGET_PAGE):
    """
    1) เปลี่ยนภาษาโดยคลิก 2 ปุ่มด้วย XPath
    2) ไปที่ target_url (driver.get)
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    lang_btn_xpath = "//*[@id=\"app\"]/div/div[2]/div[1]/div[4]/div[3]/span/span"
    thai_item_xpath = "/html/body/ul/li[3]"

    # รอให้ overlay หายก่อนคลิก
    try:
        WebDriverWait(driver, 6).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, ".el-loading-mask"))
        )
    except Exception:
        pass
    try:
        WebDriverWait(driver, 6).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, ".v-modal"))
        )
    except Exception:
        pass

    # 1) เปลี่ยนภาษาแบบคลิก
    ok1 = click_element_basic(driver, lang_btn_xpath, by="xpath", timeout=6.0, retries=2)
    time.sleep(0.4)
    ok2 = click_element_basic(driver, thai_item_xpath, by="xpath", timeout=6.0, retries=2)
    time.sleep(1.0)

    # 2) เปิดหน้าเป้าหมาย
    try:
        driver.get(target_url)
    except Exception:
        try:
            driver.execute_script("window.location.href = arguments[0];", target_url)
        except Exception:
            pass

    # รอให้หน้าโหลดเบื้องต้น
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.el-table__body-wrapper")))
    except Exception:
        time.sleep(1.0)

    return bool(ok1 and ok2)





def fill_textarea_and_submit(driver,
                             value,
                             textarea_sel: str = "textarea.el-textarea__inner, textarea.el-textarea__inner.el-textarea__inner",
                             button_sel: str = "button.el-button.el-button--primary, button.el-button--mini, button",
                             followup_icon_sel: str = "i.el-icon-edit-outline"):

    if value is None:
        return False
    s = str(value)
    # หา textarea (best-effort)
    ta = None
    try:
        ta = driver.find_element(By.CSS_SELECTOR, textarea_sel)
    except Exception:
        try:
            ta = driver.find_element(By.TAG_NAME, "textarea")
        except Exception:
            ta = None

    if ta:
        try:
            ta.clear()
        except Exception:
            try:
                driver.execute_script("arguments[0].value = '';", ta)
            except Exception:
                pass
        try:
            ta.click()
            time.sleep(0.03)
            ta.send_keys(s)
        except Exception:
            try:
                driver.execute_script(
                    "arguments[0].focus(); arguments[0].value = arguments[1];"
                    "arguments[0].dispatchEvent(new Event('input',{bubbles:true}));"
                    "arguments[0].dispatchEvent(new Event('change',{bubbles:true}));",
                    ta, s
                )
            except Exception:
                pass
        time.sleep(0.12)
    else:
        try:
            el = driver.find_element(By.CSS_SELECTOR, "input, div[contenteditable='true']")
            try:
                el.click()
                el.clear()
            except Exception:
                pass
            try:
                el.send_keys(s)
            except Exception:
                try:
                    driver.execute_script(
                        "arguments[0].focus(); arguments[0].value = arguments[1];"
                        "arguments[0].dispatchEvent(new Event('input',{bubbles:true}));"
                        "arguments[0].dispatchEvent(new Event('change',{bubbles:true}));",
                        el, s
                    )
                except Exception:
                    pass
            time.sleep(0.12)
        except Exception:
            return False

    # หาและคลิกปุ่ม "สอบถาม"
    btn = None
    try:
        btn = driver.find_element(By.CSS_SELECTOR, button_sel)
    except Exception:
        btn = None

    if btn is None:
        try:
            btn = driver.find_element(By.XPATH, "//button[contains(normalize-space(.),'สอบถาม') or contains(.,'สอบถาม')]")
        except Exception:
            btn = None

    if btn:
        try:
            btn.click()
        except Exception:
            try:
                driver.execute_script("arguments[0].click();", btn)
            except Exception:
                pass
        time.sleep(0.25)
    else:
        # ถ้าไม่เจอปุ่มสอบถาม ให้ยังพยายามกด followup ไอคอนได้ต่อไปไหม? นี่เลือกที่จะพยายามต่อ
        pass

    # ------------------ หลัง submit: กด followup icon ------------------
    def _try_click_selector(sel):
        # 1) try native find+click
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            try:
                el.click()
            except Exception:
                try:
                    driver.execute_script("arguments[0].click();", el)
                except Exception:
                    return False
            return True
        except Exception:
            pass
        # 2) try JS querySelector click
        try:
            clicked = driver.execute_script(
                "var e=document.querySelector(arguments[0]); if(e){ (e.closest('button')||e).click(); return true; } return false;",
                sel
            )
            if clicked:
                return True
        except Exception:
            pass
        # 3) try inside iframes
        try:
            frames = driver.find_elements(By.TAG_NAME, "iframe")
            for frm in frames:
                try:
                    driver.switch_to.frame(frm)
                    clicked = driver.execute_script(
                        "var e=document.querySelector(arguments[0]); if(e){ (e.closest('button')||e).click(); return true; } return false;",
                        sel
                    )
                    driver.switch_to.default_content()
                    if clicked:
                        return True
                except Exception:
                    try:
                        driver.switch_to.default_content()
                    except:
                        pass
                    continue
        except Exception:
            pass
        return False

    # พยายามคลิก followup icon หลายวิธี
    clicked_followup = _try_click_selector(followup_icon_sel)
    # ถ้า selector เป็น tag (i) อาจต้องคลิก parent button; ลองอีกแบบที่คลิก ancestor button ที่มี icon ภายใน
    if not clicked_followup:
        try:
            clicked_followup = driver.execute_script(
                "var s=arguments[0]; var e=document.querySelector(s); if(e){ var b=e.closest('button'); if(b){b.click(); return true;} } return false;",
                followup_icon_sel
            )
        except Exception:
            clicked_followup = False

    # ให้เวลา UI หลัง click
    time.sleep(0.25)
    return True
        
def fill_invoice_fields_in_order(driver, df, row_idx: int = 0):
    """
    Robust: ล้างค่าในช่องก่อน แล้วตั้งค่าใหม่ ตามลำดับ
    - ดึงค่าจาก df (InvoiceDate, serial, TotalAmount, InvoiceId)
    - หา element โดย keywords (placeholder/name/aria-label/label text)
    - ล้างช่อง (Ctrl+A, clear, JS set '') แล้วใส่ค่าโดย dispatch events+blur
    - คลิกปุ่ม 'สอบถาม' และคลิกไอคอน follow-up
    """
    def set_input_with_events(driver, el, val):
        js = """
        const el = arguments[0], val = arguments[1];
        try{ el.focus && el.focus(); }catch(e){}
        el.value = val;
        el.dispatchEvent(new Event('input',{bubbles:true}));
        el.dispatchEvent(new Event('change',{bubbles:true}));
        el.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));
        try{ el.blur && el.blur(); }catch(e){}
        return el.value;
        """
        try:
            return driver.execute_script(js, el, str(val))
        except Exception as e:
            # print("set_input_with_events error:", e)
            return None

    def clear_field(driver, el):
        """พยายามล้างค่าใน el ด้วยหลายวิธี แล้ว return True ถ้าค่าเป็น '' หรือ None"""
        try:
            # focus
            try:
                el.click()
            except Exception:
                try: driver.execute_script("arguments[0].focus();", el)
                except: pass
            time.sleep(0.03)
            # 1) Ctrl+A + Delete
            try:
                el.send_keys(Keys.CONTROL, "a")
                time.sleep(0.01)
                el.send_keys(Keys.DELETE)
                time.sleep(0.02)
            except Exception:
                pass
            # 2) try el.clear()
            try:
                el.clear()
                time.sleep(0.01)
            except Exception:
                pass
            # 3) force set empty by JS & dispatch events
            try:
                driver.execute_script(
                    "arguments[0].value = ''; arguments[0].dispatchEvent(new Event('input',{bubbles:true})); arguments[0].dispatchEvent(new Event('change',{bubbles:true}));",
                    el
                )
                time.sleep(0.01)
            except Exception:
                pass
            # 4) blur to ensure framework picks up
            try:
                el.send_keys(Keys.TAB)
            except Exception:
                try: driver.execute_script("arguments[0].blur();", el)
                except: pass
            # final check
            try:
                v = (el.get_attribute("value") or "").strip()
                return v == ""
            except Exception:
                return True
        except Exception:
            return False

    # ดึงค่าจาก df
    vals = {
        "InvoiceDate": return_value_Of_data(row_idx, "InvoiceDate", df),
        "serial":      return_value_Of_data(row_idx, "serial", df),
        "TotalAmount": return_value_Of_data(row_idx, "TotalAmount", df),
        "InvoiceId":   return_value_Of_data(row_idx, "InvoiceId", df),
    }

    keywords = {
        "InvoiceDate": ["เลือกวันที่","เลือก","date","calendar","InvoiceDate"],
        "serial":      ["โทรศัพท์","phone","mobile","serial","ชื่อ"],
        "TotalAmount": ["ราคาขาย","total","amount","ราคา","TotalAmount","LineAmount"],
        "InvoiceId":   ["ใบแจ้ง","หมายเลขใบ","Invoice","invoice","เลขใบ","InvoiceId"]
    }

    def find_input_by_keywords(driver, kws):
        # 1) try CSS attr contains
        for kw in kws:
            try:
                sel = f"input[placeholder*='{kw}'], input[name*='{kw}'], input[aria-label*='{kw}'], input[title*='{kw}']"
                els = driver.find_elements(By.CSS_SELECTOR, sel)
                if els:
                    return els[0], f"css_attr:{kw}"
            except Exception:
                pass
        # 2) label-based
        for kw in kws:
            try:
                xpath = f"//label[contains(normalize-space(.), '{kw}')]"
                labs = driver.find_elements(By.XPATH, xpath)
                if labs:
                    for lab in labs:
                        try:
                            cand = lab.find_element(By.XPATH, "following::input[1]")
                            return cand, f"label:{kw}"
                        except Exception:
                            continue
            except Exception:
                pass
        # 3) scan all inputs by attributes
        try:
            all_inputs = driver.find_elements(By.CSS_SELECTOR, "input")
            for inp in all_inputs:
                txt = " ".join(filter(None, [
                    (inp.get_attribute("placeholder") or "").lower(),
                    (inp.get_attribute("aria-label") or "").lower(),
                    (inp.get_attribute("name") or "").lower(),
                    (inp.get_attribute("id") or "").lower()
                ]))
                for kw in kws:
                    if kw.lower() in txt:
                        return inp, f"scan_attr:{kw}"
        except Exception:
            pass
        return None, None

    any_done = False
    for field, val in vals.items():
        if val is None:
            # skip ถ้าไม่มีค่า
            # print(f"[skip] {field} value is None")
            continue
        el, how = find_input_by_keywords(driver, keywords.get(field, []))
        if not el:
            # fallback: try base list (first available)
            try:
                base = driver.find_elements(By.CSS_SELECTOR, "input.el-input__inner")
                if base:
                    el = base[0]
                    how = "fallback:base_first"
                else:
                    el = None
            except Exception:
                el = None
        if not el:
            print(f"[WARN] element for {field} not found")
            continue

        try:
            try: driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            except: pass

            # ล้างช่องก่อน
            cleared = clear_field(driver, el)
            # ถ้า clear ไม่สำเร็จ ก็ยังพยายามตั้งค่าว่างด้วย JS บังคับ
            if not cleared:
                try:
                    driver.execute_script(
                        "arguments[0].value = ''; arguments[0].dispatchEvent(new Event('input',{bubbles:true})); arguments[0].dispatchEvent(new Event('change',{bubbles:true}));",
                        el
                    )
                except Exception:
                    pass
            time.sleep(0.04)

            # ใส่ค่าใหม่ (dispatch events ในฟังก์ชัน)
            res = set_input_with_events(driver, el, val)
            # เก็บสถานะ
            any_done = True
            # เบลอ/tab เพื่อให้ framework รับค่า
            try:
                el.send_keys(Keys.TAB)
            except Exception:
                try: driver.execute_script("arguments[0].blur();", el)
                except: pass
            time.sleep(0.08)
        except Exception as e:
            print(f"[ERR] failed set {field}: {e}")
            continue

    # คลิกปุ่ม 'สอบถาม' (best-effort)
    try:
        btn = None
        try:
            btn = driver.find_element(By.XPATH, "//button[contains(normalize-space(.),'สอบถาม') or contains(.,'สอบถาม')]")
        except Exception:
            pass
        if not btn:
            try:
                btn = driver.find_element(By.CSS_SELECTOR, "button.el-button.el-button--primary")
            except Exception:
                btn = None
        if btn:
            try:
                btn.click()
            except Exception:
                driver.execute_script("arguments[0].click();", btn)
            time.sleep(0.35)
    except Exception:
        pass

    # คลิก follow-up icon
    try:
        icon = None
        try:
            icon = driver.find_element(By.CSS_SELECTOR, "i.el-icon-edit-outline, i.el-icon-edit")
        except Exception:
            icon = None
        if icon:
            try:
                icon.click()
            except Exception:
                driver.execute_script("arguments[0].click();", icon)
            time.sleep(0.25)
    except Exception:
        pass

    return any_done

def upload_latest_file_strict(driver, file_path,
                              click_sel="div.el-upload.el-upload--picture-card",
                              wait_for_input=3.0,
                              after_wait=1.5):
    # คลิกพื้นที่อัปโหลด (best-effort)
    try:
        el = WebDriverWait(driver, 1).until(EC.element_to_be_clickable((By.CSS_SELECTOR, click_sel)))
        try:
            el.click()
        except Exception:
            driver.execute_script("arguments[0].click();", el)
    except Exception:
        pass

    # หา input[type=file] แล้วส่ง path เข้าไป (ส่งทันที ไม่เช็ค)
    time.sleep(0.25)
    inp = None
    try:
        inp = driver.find_element(By.CSS_SELECTOR, "input[type='file']")
        inp.send_keys(file_path)
    except Exception:
        # ถ้าไม่เจอ input แบบตรงๆ ลองหา elements แล้วใช้ตัวสุดท้าย
        try:
            cand = driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
            if cand:
                cand[-1].send_keys(file_path)
        except Exception:
            pass

    # รอเล็กน้อยให้ UI ปรากฏ แล้วพิมพ์ path/file -> tab x2 -> enter
    time.sleep(after_wait)
    try:
        # พิมพ์ path หรือชื่อไฟล์
        pyautogui.write(file_path, interval=0.02)
        time.sleep(0.08)
        pyautogui.press('tab'); time.sleep(0.06)
        pyautogui.press('tab'); time.sleep(0.06)
        pyautogui.press('enter')
    except Exception:
        # ถ้า pyautogui ล้ม ก็ไม่ทำอะไรต่อ
        pass

    return True

def click_for_save_button(driver, timeout=7) -> bool:
    """
    พยายามคลิกปุ่ม "บันทึก" แบบสั้น ๆ
    คืน True ถ้าคลิกได้ (หรือ JS คลิกสำเร็จ) / False ถ้าล้มเหลว
    """
    css = "button.el-button.el-button--primary.el-button--small"
    try:
        # รอให้ clickable แล้วคลิก (ปกติจะได้ผล)
        btn = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.CSS_SELECTOR, css)))
        try:
            btn.click()
            return True
        except Exception:
            driver.execute_script("arguments[0].click();", btn)
            return True
    except Exception:
        # fallback: หาโดย text (ไทย/ENG) แล้ว JS click
        try:
            js = """
            const targets = ['บันทึก','Save','ยืนยัน','ตกลง','Confirm','OK'];
            const buttons = Array.from(document.querySelectorAll('button'));
            for (const t of targets) {
              const found = buttons.find(b => b.innerText && b.innerText.trim().includes(t));
              if (found) { found.click(); return true; }
            }
            return false;
            """
            return bool(driver.execute_script(js))
        except Exception:
            return False
        

import time
from typing import List, Tuple, Union, Dict, Any

def _map_by(by: Union[str, object]):
    from selenium.webdriver.common.by import By
    if isinstance(by, str):
        b = by.lower()
        if b in ("css", "css_selector"):
            return By.CSS_SELECTOR
        if b in ("xpath",):
            return By.XPATH
        if b in ("id",):
            return By.ID
        if b in ("name",):
            return By.NAME
        if b in ("class", "class_name"):
            return By.CLASS_NAME
        if b in ("tag", "tag_name"):
            return By.TAG_NAME
    return by

def click_element_basic(driver, selector: str, by: Union[str, object] = "css", timeout: float = 6.0, retries: int = 2, wait_after: float = 0.25) -> bool:
    """Simple robust click helper - wait until clickable, try click, actionchain, then JS click fallback."""
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, WebDriverException

    by_mapped = _map_by(by)
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            wait = WebDriverWait(driver, timeout)
            elem = wait.until(EC.element_to_be_clickable((by_mapped, selector)))
            try:
                elem.click()
            except Exception:
                try:
                    ActionChains(driver).move_to_element(elem).pause(0.05).click(elem).perform()
                except Exception:
                    try:
                        driver.execute_script("arguments[0].click();", elem)
                    except Exception as e_js:
                        last_exc = e_js
                        raise
            time.sleep(wait_after)
            return True
        except (TimeoutException, StaleElementReferenceException, WebDriverException) as e:
            last_exc = e
            time.sleep(0.15)
            continue
        except Exception as e:
            last_exc = e
            time.sleep(0.15)
            continue
    return False

def click_send_and_confirm(
    driver,
    send_xpath: str,
    confirm_xpath: Optional[str] = None,
    timeout: float = 6.0,
    retries: int = 2,
    confirm_timeout: float = 6.0,
    confirm_retries: int = 2,
    wait_after_send: float = 0.5,
) -> bool:
    """
    Click the send/submit button, then click the confirm button in the popup.
    Uses JS selector strategy for send button first, then fallback to xpath click.
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    # Wait blocking overlays to disappear before clicking send.
    try:
        WebDriverWait(driver, timeout).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, ".el-loading-mask"))
        )
    except Exception:
        pass
    try:
        WebDriverWait(driver, timeout).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, ".v-modal"))
        )
    except Exception:
        pass

    # Click first send button via JS selectors (same strategy as test script).
    send_button_selectors = [
        "button.el-button.el-button--text.el-button--mini.el-popover_reference",
        "td.el-table_5_column_48 button.el-button--mini",
        "div.el-table__body-wrapper tbody tr:first-child td:nth-child(2) button",
    ]

    ok_send = False
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script(
                """
                const selectors = arguments[0];
                for (const s of selectors) {
                  const list = Array.from(document.querySelectorAll(s));
                  const target = list.find(el => {
                    const r = el.getBoundingClientRect();
                    const st = window.getComputedStyle(el);
                    return r.width > 0 && r.height > 0 && st.visibility !== 'hidden' && st.display !== 'none' && !el.disabled;
                  });
                  if (target) return true;
                }
                return false;
                """,
                send_button_selectors,
            )
        )
        ok_send = bool(
            driver.execute_script(
                """
                const selectors = arguments[0];
                let el = null;
                for (const s of selectors) {
                  const list = Array.from(document.querySelectorAll(s));
                  el = list.find(x => {
                    const r = x.getBoundingClientRect();
                    const st = window.getComputedStyle(x);
                    return r.width > 0 && r.height > 0 && st.visibility !== 'hidden' && st.display !== 'none' && !x.disabled;
                  });
                  if (el) break;
                }
                if (!el) return false;
                el.scrollIntoView({block:'center', inline:'center'});
                ['mouseover','mousedown','mouseup','click'].forEach(t =>
                    el.dispatchEvent(new MouseEvent(t, {bubbles:true, cancelable:true, view:window}))
                );
                return true;
                """,
                send_button_selectors,
            )
        )
    except Exception:
        ok_send = False

    # Keep legacy xpath click as fallback.
    if not ok_send:
        ok_send = click_element_basic(driver, send_xpath, by="xpath", timeout=timeout, retries=retries)
    if not ok_send:
        return False

    time.sleep(wait_after_send)
    if not confirm_xpath:
        confirm_xpath = "//*[starts-with(@id,'el-popover-') or contains(@id,'el-popover')]/div[1]/button[2]"

    ok_confirm = click_element_basic(driver, confirm_xpath, by="xpath", timeout=confirm_timeout, retries=confirm_retries)
    return ok_confirm



# ใส่ใน MainGetValueOfImagecopy.py
import time
from selenium.webdriver.remote.webdriver import WebDriver
from typing import List, Tuple

def _js_click(driver: WebDriver, selector: str) -> bool:
    """
    ใช้ JS เพื่อหา element ด้วย querySelector แล้วคลิก (ถ้าเป็นปุ่มจะคลิกปุ่มที่ใกล้ที่สุด)
    คืนค่า True ถ้าคลิกสำเร็จ
    """
    js = """
    try {
      var e = document.querySelector(arguments[0]);
      if (!e) return false;
      var target = (e.closest && e.closest('button')) || e;
      target.click();
      return true;
    } catch (err) {
      return false;
    }
    """
    try:
        return bool(driver.execute_script(js, selector))
    except Exception:
        return False

def _js_click_xpath(driver: WebDriver, xpath: str) -> bool:
    """
    ใช้กับ XPath: evaluate แล้วคลิก node ที่เจอ
    (เรียกโดยส่ง selector ที่ขึ้นต้นด้วย 'xpath:')
    """
    js = """
    try {
      var xp = document.evaluate(arguments[0], document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
      var e = xp.singleNodeValue;
      if (!e) return false;
      var target = (e.closest && e.closest('button')) || e;
      target.click();
      return true;
    } catch (err) {
      return false;
    }
    """
    try:
        return bool(driver.execute_script(js, xpath))
    except Exception:
        return False





def click_sales_menu_sequence(
    driver: WebDriver,
    pause: float = 0.95
) -> bool:
    """
    คลิกตามลำดับ:
      1) เมนูหลัก (การจัดการการขาย)
      2) เมนูย่อย (การจัดการการขายจริง)
      3) เมนูรายการ (li.el-menu-item ชื่อ 'การดูแลคำสั่งซื้อขาย')
    คืนค่า True ถ้าทั้ง 3 สเต็ปคลิกสำเร็จ (otherwise False)
    """
    js_click = (
        "try {"
        "  var e = document.querySelector(arguments[0]);"
        "  if(!e) return false;"
        "  e.scrollIntoView({block:'center'});"
        "  var target = (e.closest && e.closest('button')) || e;"
        "  target.click();"
        "  return true;"
        "} catch(err) { return false; }"
    )

    # step1: main menu candidates (ปรับชื่อ class/attr ถ้ามี typo)
    step1: List[str] = [
        "span.menuWidth[title='การจัดการการขาย']",
        "span.menuWitdh[title='การจัดการการขาย']",  # สำรองกรณี typo/class ต่างกัน
        "span.menuWidth",
        "span.menuWitdh"
    ]

    # step2: submenu candidates (จากภาพ 'การจัดการการขายจริง')
    step2: List[str] = [
        "xpath://span[contains(normalize-space(.),'การจัดการการขายจริง')]",  # หากต้องการ XPath
        "span.menuWidth[title='การจัดการการขายจริง']",
        "span.menuWitdh[title='การจัดการการขายจริง']",
        "span.menuWidth",
    ]

    # step3: target item inside menu (li.el-menu-item containing the span text)
    step3: List[str] = [
        "li.el-menu-item span[title='การดูแลคำสั่งซื้อขาย']",
        "li.el-menu-item[role='menuitem'] span[title='การดูแลคำสั่งซื้อขาย']",
        "span[title='การดูแลคำสั่งซื้อขาย']",
        "li.el-menu-item"  # very broad fallback (visual check recommended)
    ]

    # helper: support xpath by prefix 'xpath:'
    def try_select_and_click(candidates: List[str]) -> (bool, str): # type: ignore
        for sel in candidates:
            if not sel: 
                continue
            if sel.startswith("xpath:") or sel.startswith("xpath://"):
                # JS evaluate XPath and click
                xpath = sel.split(":",1)[1] if ":" in sel else sel
                js_xpath = (
                    "try {"
                    "  var xp = document.evaluate(arguments[0], document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);"
                    "  var e = xp.singleNodeValue;"
                    "  if(!e) return false;"
                    "  var t = (e.closest && e.closest('button')) || e;"
                    "  t.click(); return true;"
                    "} catch(err) { return false; }"
                )
                try:
                    ok = bool(driver.execute_script(js_xpath, xpath))
                except Exception:
                    ok = False
            else:
                try:
                    ok = bool(driver.execute_script(js_click, sel))
                except Exception:
                    ok = False
            print(f"[MENU] try {sel} -> {ok}")
            if ok:
                return True, sel
        return False, ""

    ok1, used1 = try_select_and_click(step1)
    if not ok1:
        print("[MENU] step1 FAILED")
        return False
    time.sleep(pause)

    ok2, used2 = try_select_and_click(step2)
    if not ok2:
        print("[MENU] step2 FAILED")
        return False
    time.sleep(pause)

    ok3, used3 = try_select_and_click(step3)
    if not ok3:
        print("[MENU] step3 FAILED")
        return False
    time.sleep(pause)

    print(f"[MENU] sequence OK: step1={used1}, step2={used2}, step3={used3}")
    return True





def fill_serial_input(
    driver: WebDriver,
    serial_value: str,
    timeout: float = 6.0,
    pause_after: float = 0.4,
    selectors: list | None = None,
    # ปุ่มที่จะกดหลังกรอก (ลองทีละ selector ตามลำดับ)
    btn_selectors: list | None = None,
    tabs_after_btn: int = 4,
    tab_delay: float = 0.08,
    enter_after_tabs: bool = True
) -> bool:
    """
    หา input แล้วกรอกค่า serial_value
    - selectors: รายการ CSS selectors ที่จะลอง (ลำดับความสำคัญ)
    - btn_selectors: รายการ selectors สำหรับปุ่ม 'สอบถาม' หรือปุ่มที่จะกดหลังกรอก
      ถ้าไม่ระบุ จะใช้ default ที่มักเจอใน UI ของคุณ
    - tabs_after_btn: จำนวนครั้งที่จะกด Tab หลังกดปุ่ม
    - คืน True ถ้ากรอก+กดปุ่ม+Tab/Enter สำเร็จ, False ถ้าไม่พบ/กรอกไม่สำเร็จ
    """
    if selectors is None:
        selectors = [
            "input.el-input__inner[placeholder='VIN']",
            "input.el-input__inner[name='VIN']",
            "input.el-input__inner[title='VIN']",
            "input.el-input__inner",  # generic fallback (ระวังถ้ามีหลายช่อง)
        ]

    if btn_selectors is None:
        btn_selectors = [
            "button.el-button.el-button--primary.el-button--small",   # ตามรูป
            "button.el-button",                                       # generic
            "button[title='สอบถาม']",
            # xpath for button with Thai text 'สอบถาม' (ใช้ find_element(By.XPATH,...))
            "//button[contains(normalize-space(.),'สอบถาม')]",
        ]

    js_set = (
        "try {"
        "  var e = document.querySelector(arguments[0]);"
        "  if(!e) return false;"
        "  e.scrollIntoView({block:'center'});"
        "  e.focus();"
        "  e.value = arguments[1] || '';"
        "  var ev = new Event('input', {bubbles:true}); e.dispatchEvent(ev);"
        "  var ev2 = new Event('change', {bubbles:true}); e.dispatchEvent(ev2);"
        "  return true;"
        "} catch(err) { return false; }"
    )

    # 1) หา input แล้วกรอก
    for sel in selectors:
        try:
            WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
        except Exception:
            continue

        try:
            elem = driver.find_element(By.CSS_SELECTOR, sel)
        except Exception as e:
            # ไม่พบ element จริง ๆ
            # print(f"[SERIAL] find_element for {sel} failed: {e}")
            continue

        # scroll + focus
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'})", elem)
        except Exception:
            pass

        try:
            elem.click()
        except Exception:
            try:
                driver.execute_script("arguments[0].focus()", elem)
            except Exception:
                pass

        # try clear
        try:
            elem.clear()
        except Exception:
            try:
                driver.execute_script("arguments[0].value=''", elem)
            except Exception:
                pass

        # try send_keys
        try:
            elem.send_keys(serial_value)
            time.sleep(pause_after)
            # dispatch events to satisfy frameworks
            driver.execute_script(
                "var ev=new Event('input',{bubbles:true}); arguments[0].dispatchEvent(ev);"
                "var ev2=new Event('change',{bubbles:true}); arguments[0].dispatchEvent(ev2);",
                elem,
            )
            print(f"[SERIAL] typed via send_keys into selector: {sel}")
            did_set = True
        except Exception as e_send:
            print(f"[SERIAL] send_keys failed for {sel}: {e_send} -> trying JS set")
            try:
                ok = bool(driver.execute_script(js_set, sel, serial_value))
                time.sleep(pause_after)
                if ok:
                    print(f"[SERIAL] set value via JS for selector: {sel}")
                    did_set = True
                else:
                    print(f"[SERIAL] js_set returned False for selector: {sel}")
                    did_set = False
            except Exception as e_js:
                print(f"[SERIAL] js_set exception for {sel}: {e_js}")
                did_set = False

        if not did_set:
            # ลอง selector ถัดไป
            continue

        # 2) ถ้ากรอกสำเร็จ ให้พยายามกดปุ่ม 'สอบถาม' ตาม btn_selectors (ลองทีละตัว)
        btn_clicked = False
        for bsel in btn_selectors:
            try:
                if bsel.strip().startswith("//"):  # xpath
                    try:
                        btn = WebDriverWait(driver, 2.0).until(EC.element_to_be_clickable((By.XPATH, bsel)))
                        btn.click()
                        btn_clicked = True
                        print(f"[SERIAL] clicked button by XPATH: {bsel}")
                        break
                    except Exception:
                        continue
                else:
                    # CSS selector
                    try:
                        btn = WebDriverWait(driver, 2.0).until(EC.element_to_be_clickable((By.CSS_SELECTOR, bsel)))
                        btn.click()
                        btn_clicked = True
                        print(f"[SERIAL] clicked button by CSS: {bsel}")
                        break
                    except Exception:
                        continue
            except Exception as e_btn:
                # print(f"[SERIAL] button try exception for {bsel}: {e_btn}")
                continue

        # ถ้าหา/คลิกปุ่มไม่ได้ ให้พยายาม fallback: ลองกด Enter ใน input เอง
        if not btn_clicked:
            try:
                elem.send_keys(Keys.ENTER)
                time.sleep(0.15)
                print("[SERIAL] fallback: sent ENTER in input after typing")
                btn_clicked = True  # treat as progressed (UI may accept Enter)
            except Exception:
                print("[SERIAL] Could not click button and fallback ENTER failed")

        # 3) หลังกดปุ่ม (หรือ fallback) ให้กด Tab N ครั้ง แล้ว Enter (ถ้าต้องการ)
        try:
            actions = ActionChains(driver)
            for i in range(max(0, int(tabs_after_btn))):
                actions.send_keys(Keys.TAB)
                actions.perform()
                time.sleep(tab_delay)
            if enter_after_tabs:
                actions = ActionChains(driver)
                actions.send_keys(Keys.ENTER)
                actions.perform()
                time.sleep(0.12)
            print(f"[SERIAL] performed {tabs_after_btn} tabs and Enter={enter_after_tabs}")
        except Exception as e_actions:
            print("[SERIAL] Tab/Enter sequence failed:", e_actions)
            # แต่เราพิจารณาว่าการกรอกเบื้องต้นสำเร็จอยู่ดี -> คืน True
            return True

        # ถ้ามาถึงตรงนี้ ถือว่าสำเร็จครบขั้นตอน
        return True

    # ถ้าลูป selectors จบแล้วยังไม่สำเร็จ
    print("[SERIAL] Failed to set serial for any selector")
    return False


def change_lang_and_open_page_FOR_test_po(
    driver: WebDriver,
    wait: WebDriverWait,
    target_url: str | None = None,   # <-- optional now
    tabs: int = 3,
    down_presses: int = 2,
    pause: float = 0.25,
    per_click_timeout: float = 6.0,
    retries_each: int = 3,
    wait_after_each: float = 0.6,
    click_xpath: str = "/html/body/div[1]/div/div[1]/div/ul/div/li[11]/ul/div[1]/li/ul/div[2]/a/li/span",
    click_xpath2: str = "/html/body/div/div/div[2]/section/section/div/div[1]/div[1]/div[2]/div/button/span"
) -> bool:
    """
    - เปลี่ยนภาษา (via keyboard helper) แล้ว (optionally) navigate
    - พยายามคลิก element ตาม `click_xpath` (เมนู)
    - ถ้าสำเร็จแล้ว จะคลิก `click_xpath2` ต่อ (ปุ่มในหน้าที่ถูกเปิด)
    - คืน True ถ้าทั้งสองคลิกสำเร็จ (หรือถ้ากดปุ่มที่สองไม่จำเป็นก็ยังคืน True ถ้าปุ่มแรกสำเร็จและปุ่มสองไม่เจอ)
    """
    try:
        change_language_via_keyboard(driver, tabs=tabs, down_presses=down_presses, pause=pause)
    except Exception as e:
        print("[WARN] change_language_via_keyboard failed or not available:", e)
    time.sleep(1.2)

    if target_url:
        try:
            driver.get(target_url)
        except Exception:
            try:
                driver.execute_script("window.location.href = arguments[0];", target_url)
            except Exception as e:
                print("[ERROR] cannot navigate to target_url:", e)
                return False

    # รอ DOM เบื้องต้น (best-effort)
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "aside, nav, ul.el-menu, div.el-submenu__title")))
    except Exception:
        time.sleep(1.0)

    time.sleep(0.4)

    def _try_click_xpath(xpath: str) -> bool:
        """พยายามคลิก xpath หลายวิธีพร้อม retry — คืน True ถ้าคลิกสำเร็จ"""
        js_xpath_click = (
            "try {"
            "  var xpath = arguments[0];"
            "  var node = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;"
            "  if(!node) return false;"
            "  var btn = node.closest('button') || node;"
            "  try { btn.scrollIntoView({block:'center'}); } catch(e) {};"
            "  btn.click();"
            "  return true;"
            "} catch(e) { return false; }"
        )
        last_exc = None
        for attempt in range(retries_each):
            try:
                WebDriverWait(driver, per_click_timeout).until(EC.presence_of_element_located((By.XPATH, xpath)))
            except Exception as e_wait:
                last_exc = e_wait
                time.sleep(0.25)
                continue

            try:
                elem = driver.find_element(By.XPATH, xpath)
            except Exception as e_find:
                elem = None
                last_exc = e_find

            if elem is not None:
                try:
                    elem.click()
                    print(f"[INFO] clicked native (xpath) '{xpath}' on attempt {attempt+1}")
                    time.sleep(wait_after_each)
                    return True
                except Exception as e_click:
                    last_exc = e_click
                    try:
                        driver.execute_script("arguments[0].click();", elem)
                        print(f"[INFO] clicked via JS element (xpath) '{xpath}' on attempt {attempt+1}")
                        time.sleep(wait_after_each)
                        return True
                    except Exception as e_js_elem:
                        last_exc = e_js_elem

            # JS XPath fallback
            try:
                js_ok = driver.execute_script(js_xpath_click, xpath)
                if js_ok:
                    print(f"[INFO] clicked via JS XPath fallback '{xpath}' on attempt {attempt+1}")
                    time.sleep(wait_after_each)
                    return True
                else:
                    last_exc = "js_xpath_click returned False"
            except Exception as e_js:
                last_exc = e_js

            time.sleep(0.25)

        print(f"[ERROR] failed to click XPath '{xpath}' after {retries_each} attempts. last_exc={last_exc}")
        return False

    # 1) คลิกเมนู/รายการหลัก (xpath แรก)
    ok1 = _try_click_xpath(click_xpath)
    if not ok1:
        # ถ้าเมนูหลักคลิกไม่ผ่าน อาจต้องลอง log nearby items for debugging
        try:
            spans = driver.find_elements(By.CSS_SELECTOR, "span.menuWidth, span.twoMenuWidth, li.el-menu-item span")
            sample_texts = []
            for e in spans[:40]:
                try:
                    t = (e.get_attribute("title") or e.text or "").strip()
                    if t:
                        sample_texts.append(t)
                except Exception:
                    continue
            print("[DEBUG] nearby candidate texts (first 40):", sample_texts)
        except Exception:
            pass
        return False

    # ให้เวลา UI ขยาย/โหลด เมนูย่อยก่อน
    time.sleep(wait_after_each + 0.4)

    # 2) คลิกปุ่ม/รายการที่สองตาม xpath2 (ถ้ามี)
    ok2 = _try_click_xpath(click_xpath2)
    if not ok2:
        # ถ้าปุ่มที่สองไม่สำคัญ ให้คืน True แต่แจ้งเตือน (ปรับตามต้องการ)
        print(f"[WARN] click xpath2 failed or not present: {click_xpath2} (continuing)")
        return True

    # give UI time to settle
    time.sleep(wait_after_each)
    return True



def fill_textarea_and_submit_and_tab(driver,
                                     value,
                                     textarea_sel: str = "textarea.el-textarea__inner, textarea.el-textarea__inner.el-textarea__inner",
                                     button_sel: str = "button.el-button.el-button--primary, button.el-button--mini, button",
                                     followup_icon_sel: str = "i.el-icon-edit-outline",
                                     vin_input_sel: str = "label[for='vin']",
                                     followup_btn_scope: str = "div.el-table__body-wrapper",
                                     tab_count: int = 4,
                                     tab_interval: float = 0.06):
    """
    เขียนข้อความลง textarea / input แล้วกดปุ่ม (เช่น 'สอบถาม')
    หลังจากกดปุ่มสำเร็จ จะคลิกปุ่มแรกที่เจอในกรอบตาราง (แทนการกด TAB/ENTER)
    คืนค่า True ถ้าทำครบ flow; False ถ้าไม่พบ input/textarea หรือเกิดปัญหาเบื้องต้น
    """

    if value is None:
        return False
    s = str(value)

    # หา textarea (best-effort)
    ta = None
    try:
        ta = driver.find_element(By.CSS_SELECTOR, textarea_sel)
    except Exception:
        try:
            ta = driver.find_element(By.TAG_NAME, "textarea")
        except Exception:
            ta = None

    try:
        if ta:
            try:
                ta.clear()
            except Exception:
                try:
                    driver.execute_script("arguments[0].value = '';", ta)
                except Exception:
                    pass
            try:
                ta.click()
                time.sleep(0.03)
                ta.send_keys(s)
            except Exception:
                try:
                    driver.execute_script(
                        "arguments[0].focus(); arguments[0].value = arguments[1];"
                        "arguments[0].dispatchEvent(new Event('input',{bubbles:true}));"
                        "arguments[0].dispatchEvent(new Event('change',{bubbles:true}));",
                        ta, s
                    )
                except Exception:
                    pass
            time.sleep(0.12)
        else:
            # เฉพาะ VIN input: หา input ใต้ label[for='vin'] เพื่อลดการคลิกผิดช่อง (เช่น search bar)
            vin_input = None
            if vin_input_sel:
                try:
                    label = driver.find_element(By.CSS_SELECTOR, vin_input_sel)
                    vin_input = label.find_element(By.XPATH, "./ancestor::div[contains(@class,'el-form-item')][1]//input[contains(@class,'el-input__inner')]")
                except Exception:
                    vin_input = None

            # หา input หรือ contenteditable (fallback)
            try:
                el = vin_input if vin_input is not None else driver.find_element(By.CSS_SELECTOR, "input, div[contenteditable='true']")
                try:
                    el.click()
                    try:
                        el.clear()
                    except Exception:
                        pass
                except Exception:
                    pass
                try:
                    el.send_keys(s)
                except Exception:
                    try:
                        driver.execute_script(
                            "arguments[0].focus(); arguments[0].value = arguments[1];"
                            "arguments[0].dispatchEvent(new Event('input',{bubbles:true}));"
                            "arguments[0].dispatchEvent(new Event('change',{bubbles:true}));",
                            el, s
                        )
                    except Exception:
                        pass
                time.sleep(0.12)
            except Exception:
                return False
    except Exception:
        return False

    # หาและคลิกปุ่ม "สอบถาม" (best-effort)
    btn = None
    try:
        btn = driver.find_element(By.CSS_SELECTOR, button_sel)
    except Exception:
        btn = None

    if btn is None:
        try:
            btn = driver.find_element(By.XPATH, "//button[contains(normalize-space(.),'สอบถาม') or contains(.,'สอบถาม')]")
        except Exception:
            btn = None

    if btn:
        clicked = False
        try:
            btn.click()
            clicked = True
        except Exception:
            try:
                driver.execute_script("arguments[0].click();", btn)
                clicked = True
            except Exception:
                clicked = False

        # รอสั้น ๆ หลังคลิก แล้วคลิกปุ่มแรกที่เจอในกรอบตาราง (แทนการกด TAB/ENTER)
        time.sleep(0.25)
        if clicked:
            try:
                js = """
                const scopeSel = arguments[0];
                const scope = scopeSel ? document.querySelector(scopeSel) : document;
                if (!scope) return false;
                const buttons = Array.from(scope.querySelectorAll('button'));
                const target = buttons.find(b => {
                  const r = b.getBoundingClientRect();
                  const st = window.getComputedStyle(b);
                  return r.width > 0 && r.height > 0 &&
                         st.visibility !== 'hidden' && st.display !== 'none' &&
                         !b.disabled;
                });
                if (!target) return false;
                target.scrollIntoView({block:'center', inline:'center'});
                ['mouseover','mousedown','mouseup','click'].forEach(t =>
                  target.dispatchEvent(new MouseEvent(t, {bubbles:true, cancelable:true, view:window}))
                );
                return true;
                """
                driver.execute_script(js, followup_btn_scope)
                time.sleep(0.25)
            except Exception:
                pass

        return True
    else:
        return False





def process_dms_twoflows_and_update(
    driver_dms,
    serial_val,
    latest_file_path,
    df_row,
    filter_value,
    *,
    run_idx=None,
    safe_write_status_func=None,         # function(filter_value, status) -> bool (or raises)
    mark_success_func=None,              # function(serial_val) -> bool
    mark_error_func=None,                # function(serial_val, error_msg=None) -> bool
    fill_tab_func=None,                  # fill_textarea_and_submit_and_tab(driver, value, ...)
    fill_plain_func=None,                # fill_textarea_and_submit(driver, value, ...)
    fill_invoice_fields_func=None,       # fill_invoice_fields_in_order(driver, df, row_idx) or similar
    upload_file_func=None,               # upload_latest_file_strict(driver, file_path)
    click_save_func=None,                # click_for_save_button(driver)
    logger=print,
    wait_after_click=1.0
):
    """
    Executes two sequences:
      A) fill_textarea_and_submit_and_tab -> fill_invoice_fields_in_order -> upload -> click_save
      B) fill_textarea_and_submit -> fill_invoice_fields_in_order -> upload -> click_save
    If both sequences succeed => try to write sheet status "Y" AND mark DB success.
    Else => mark DB error + write sheet status "N".
    All helper functions should be passed in (or available in scope).
    Returns: (success: bool, msg: str)
    """
    try:
        if serial_val is None:
            return False, "serial_val is None"

        # --------- pre-check required helpers ----------
        required = {
            "safe_write_status_func": safe_write_status_func,
            "mark_success_func": mark_success_func,
            "mark_error_func": mark_error_func,
            "fill_tab_func": fill_tab_func,
            "fill_plain_func": fill_plain_func,
            "fill_invoice_fields_func": fill_invoice_fields_func,
            "upload_file_func": upload_file_func,
            "click_save_func": click_save_func
        }
        missing = [k for k,v in required.items() if v is None]
        if missing:
            return False, f"Missing helper(s): {missing}"

        # helper to mark error & write sheet 'N' (best-effort)
        def _mark_error_and_sheet(msg):
            try:
                logger("[INFO] marking DB error for serial:", serial_val, "msg:", msg)
                try:
                    mark_error_func(serial_val, error_msg=str(msg))
                except Exception as e_db:
                    logger("mark_complete_error_by_serial failed:", e_db)
                # ensure we attempt to write sheet 'N'
                try:
                    if filter_value and safe_write_status_func:
                        safe_write_status_func(filter_value, "N")
                except Exception as e_sheet:
                    logger("[SHEET] Failed to write status 'N':", e_sheet)
            except Exception as e_all:
                logger("Error in _mark_error_and_sheet:", e_all)

        # ---------- Sequence A: tabbed flow ----------
        logger("[INFO] Starting tabbed flow (A) for serial:", serial_val)
        ok_a = False
        try:
            # 1) fill textarea and submit + TAB+ENTER
            res_a = fill_tab_func(driver_dms, serial_val)   # should return True/False
            if not res_a:
                raise RuntimeError("fill_tab_func returned False")

            time.sleep(0.25)

            # 2) fill invoice fields
            # note: adjust signature to your function; here we expect it to accept (driver, df, row_idx)
            fill_invoice_fields_func(driver_dms, df_row if run_idx is None else df_row, run_idx)  # adapt if your function different
            time.sleep(0.25)

            # 3) upload latest file (must exist)
            if not latest_file_path:
                raise RuntimeError("No latest file to upload (A)")
            upload_file_func(driver_dms, latest_file_path)
            time.sleep(0.25)

            # 4) click save (pass driver)
            click_save_func(driver_dms)
            time.sleep(wait_after_click)

            ok_a = True
            logger("[INFO] Tabbed flow (A) succeeded for", serial_val)
        except Exception as e:
            logger("[WARN] Tabbed flow (A) failed for", serial_val, "err:", e)
            logger(traceback.format_exc()[:1000])
            ok_a = False

        # ---------- Sequence B: plain flow ----------
        logger("[INFO] Starting plain flow (B) for serial:", serial_val)
        ok_b = False
        try:
            # 1) fill textarea and submit (plain)
            res_b = fill_plain_func(driver_dms, serial_val)
            if not res_b:
                raise RuntimeError("fill_plain_func returned False")

            time.sleep(0.25)

            # 2) fill invoice fields
            fill_invoice_fields_func(driver_dms, df_row if run_idx is None else df_row, run_idx)
            time.sleep(0.25)

            # 3) upload
            if not latest_file_path:
                raise RuntimeError("No latest file to upload (B)")
            upload_file_func(driver_dms, latest_file_path)
            time.sleep(0.25)

            # 4) click save
            click_save_func(driver_dms)
            time.sleep(wait_after_click)

            ok_b = True
            logger("[INFO] Plain flow (B) succeeded for", serial_val)
        except Exception as e:
            logger("[WARN] Plain flow (B) failed for", serial_val, "err:", e)
            logger(traceback.format_exc()[:1000])
            ok_b = False

        # ---------- Decide final outcome ----------
        if ok_a and ok_b:
            # both succeeded -> attempt to write sheet 'Y' first, then mark DB success
            try:
                if safe_write_status_func and filter_value:
                    safe_write_status_func(filter_value, "Y")
                # only mark DB success after sheet write succeeded
                try:
                    mark_success_func(serial_val)
                except Exception as e_db:
                    # if DB update fails, try to write sheet 'N' to indicate failure
                    logger("mark_complete_success_by_serial failed:", e_db)
                    try:
                        if safe_write_status_func and filter_value:
                            safe_write_status_func(filter_value, "N")
                    except Exception as e_s2:
                        logger("[SHEET] fallback sheet write N failed:", e_s2)
                    return False, f"DB mark success failed: {e_db}"
                logger("[INFO] Invoice processed and marked success (Y) for", serial_val)
                return True, "Processed and marked success"
            except Exception as e_sheet_final:
                # sheet write failed — mark DB error and return
                logger("[SHEET] Failed to write status 'Y' for", serial_val, "err:", e_sheet_final)
                _mark_error_and_sheet(f"Sheet write failed: {e_sheet_final}")
                return False, f"Sheet write failed: {e_sheet_final}"
        else:
            # at least one sequence failed — mark DB error and write sheet 'N'
            _mark_error_and_sheet("One or both DMS upload flows failed")
            return False, "One or both flows failed"

    except Exception as outer_e:
        logger("Unexpected error in process_dms_twoflows_and_update:", outer_e)
        logger(traceback.format_exc()[:1000])
        try:
            if mark_error_func:
                mark_error_func(serial_val, error_msg=str(outer_e)[:2000])
            if safe_write_status_func and filter_value:
                safe_write_status_func(filter_value, "N")
        except Exception:
            pass
        return False, f"Unexpected error: {outer_e}"
# --- end function ---

try:
    import pandas as _pd
except Exception:
    _pd = None
try:
    import numpy as _np
except Exception:
    _np = None

def fill_invoice_fields_in_order_first(driver, df, row_idx):
    """
    Robust drop-in replacement.
    - Accept InvoiceDate as scalar / pd.Timestamp / pd.Series (will coerce to scalar)
    - Click dropdown input then send ArrowDown + Enter via ActionChains (with small retries)
    - Fill dates from InvoiceDate (parsed to YYYY-MM-DD), fill TotalAmount, LineAmount, SalesId
    - Returns True on success, raises RuntimeError on failure
    """
    import time, re
    from datetime import datetime as _dt
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver import ActionChains
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    # small setter with JS fallback
    def _set_input_value(el, val):
        try:
            el.clear()
        except Exception:
            pass
        try:
            el.click()
        except Exception:
            pass
        try:
            el.send_keys(str(val))
            time.sleep(0.06)
            return True
        except Exception:
            pass
        try:
            driver.execute_script(
                "arguments[0].focus(); arguments[0].value = arguments[1];"
                "arguments[0].dispatchEvent(new Event('input',{bubbles:true}));"
                "arguments[0].dispatchEvent(new Event('change',{bubbles:true}));",
                el, str(val)
            )
            time.sleep(0.06)
            return True
        except Exception:
            return False

    # parse invoice date robustly (handle pd.Series, Timestamp, string, datetime)
    def _to_ymd(val):
        if val is None:
            return None
        # if pandas Series (e.g. row['InvoiceDate'] unexpectedly a Series), extract scalar
        try:
            import pandas as _pd
        except Exception:
            _pd = None

        # if Series -> take first non-null element or .item()
        try:
            if _pd is not None and isinstance(val, _pd.Series):
                # if single-element series -> .iat[0], else try .item() if length ==1
                if val.size == 1:
                    scalar = val.iat[0]
                    val = scalar
                else:
                    # choose first non-null
                    nonn = val.dropna()
                    if len(nonn) >= 1:
                        val = nonn.iat[0]
                    else:
                        val = None
        except Exception:
            pass

        if val is None:
            return None

        # try pandas parse if available
        if _pd is not None:
            try:
                ts = _pd.to_datetime(val, errors="coerce")
                if not _pd.isna(ts):
                    return ts.strftime("%Y-%m-%d")
            except Exception:
                pass

        # datetime-like objects
        try:
            if hasattr(val, "to_pydatetime"):
                dt = val.to_pydatetime()
                return dt.strftime("%Y-%m-%d")
        except Exception:
            pass
        try:
            if isinstance(val, _dt):
                return val.strftime("%Y-%m-%d")
        except Exception:
            pass

        s = str(val).strip()
        # ISO-like prefix
        if len(s) >= 10 and re.match(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}", s[:10]):
            cand = s[:10].replace("/", "-")
            m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", cand)
            if m:
                y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
                return f"{y}-{mo:02d}-{d:02d}"

        # try list of formats
        fmts = ["%Y-%m-%d","%Y/%m/%d","%d/%m/%Y","%d-%m-%Y","%Y-%m-%d %H:%M:%S","%Y%m%d"]
        for f in fmts:
            try:
                dt = _dt.strptime(s, f)
                return dt.strftime("%Y-%m-%d")
            except Exception:
                continue

        return None

    # --- main ---
    row = df.loc[row_idx]
    total = row.get("TotalAmount", "")
    line = row.get("LineAmount", "")
    salesid = row.get("InvoiceId", "")
    inv_raw = row.get("InvoiceDate", None)

    invoice_date = _to_ymd(inv_raw)
    if not invoice_date:
        # show debug info and fail loudly so you can see DB value
        raise RuntimeError(f"Cannot parse InvoiceDate for row {row_idx}: {repr(inv_raw)} (type={type(inv_raw)})")

    # XPaths (user-provided)
    xp_input_dropdown = "/html/body/div/div/div[2]/section/section/div/div[2]/form/div[1]/div[2]/div[2]/div/div[2]/div/div/div[1]/input"
    xp_date_sale = "/html/body/div/div/div[2]/section/section/div/div[2]/form/div[1]/div[2]/div[2]/div/div[5]/div/div/input"
    xp_total = "/html/body/div/div/div[2]/section/section/div/div[2]/form/div[1]/div[2]/div[2]/div/div[7]/div/div/input"
    xp_line = "/html/body/div/div/div[2]/section/section/div/div[2]/form/div[1]/div[2]/div[2]/div/div[8]/div/div/input"
    xp_sales = "/html/body/div/div/div[2]/section/section/div/div[2]/form/div[1]/div[2]/div[2]/div/div[9]/div/div/input"
    xp_date_ticket = "/html/body/div/div/div[2]/section/section/div/div[2]/form/div[1]/div[2]/div[2]/div/div[11]/div/div/input"

    try:
        # 1) click dropdown input
        inp = driver.find_element(By.XPATH, xp_input_dropdown)
        try:
            inp.click()
        except Exception:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", inp)
            driver.execute_script("arguments[0].click();", inp)
        time.sleep(0.62)

        # 2) robust approach: ActionChains send ArrowDown once then Enter, with 2 retries
        ac = ActionChains(driver)
        success_dropdown = False
        for attempt in range(2):
            try:
                ac.reset_actions()
            except Exception:
                pass
            try:
                ActionChains(driver).send_keys_to_element(inp, Keys.ARROW_DOWN).send_keys_to_element(inp, Keys.ENTER).perform()
            except Exception:
                try:
                    # fallback: send to body
                    b = driver.find_element(By.TAG_NAME, "body")
                    ActionChains(driver).send_keys_to_element(b, Keys.ARROW_DOWN).send_keys_to_element(b, Keys.ENTER).perform()
                except Exception:
                    pass
            time.sleep(0.68)

            # quick verification: if input value changed or dropdown overlay not visible, accept
            try:
                after = inp.get_attribute("value") or inp.get_attribute("textContent") or ""
                if after and after.strip() != "":
                    success_dropdown = True
                    break
            except Exception:
                # check if overlay disappeared by trying to find any dropdown UL
                try:
                    ul = driver.find_elements(By.XPATH, "//div[contains(@class,'el-select-dropdown')]//ul")
                    if not ul:
                        success_dropdown = True
                        break
                except Exception:
                    # can't determine -> continue
                    pass
            # not successful -> small retry
        if not success_dropdown:
            # last-ditch: try to click first visible li if exists
            try:
                li = WebDriverWait(driver, 1.0).until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[2]/div[1]/div[1]/ul/li[1]")))
                try:
                    li.click()
                    time.sleep(0.62)
                    success_dropdown = True
                except Exception:
                    pass
            except Exception:
                pass

        if not success_dropdown:
            raise RuntimeError("dropdown selection failed (ArrowDown+Enter and li click attempts exhausted)")

        # 3) sale date <- invoice_date
        el_date_sale = driver.find_element(By.XPATH, xp_date_sale)
        if not _set_input_value(el_date_sale, invoice_date):
            raise RuntimeError("failed to set sale date")
        try:
            el_date_sale.send_keys(Keys.ENTER)
        except Exception:
            pass
        time.sleep(0.62)

        # 4) TotalAmount
        el_total = driver.find_element(By.XPATH, xp_total)
        try:
            t = str(total).replace(",","").strip()
            t = f"{float(t):.2f}" if t!="" else ""
        except Exception:
            t = str(total)
        if not _set_input_value(el_total, t):
            raise RuntimeError("failed to set TotalAmount")
        time.sleep(0.62)

        # 5) LineAmount
        el_line = driver.find_element(By.XPATH, xp_line)
        try:
            l = str(line).replace(",","").strip()
            l = f"{float(l):.2f}" if l!="" else ""
        except Exception:
            l = str(line)
        if not _set_input_value(el_line, l):
            raise RuntimeError("failed to set LineAmount")
        time.sleep(0.62)

        # 6) SalesId
        el_sales = driver.find_element(By.XPATH, xp_sales)
        if not _set_input_value(el_sales, salesid):
            raise RuntimeError("failed to set SalesId")
        time.sleep(0.62)

        # 7) ticket date <- invoice_date
        el_ticket = driver.find_element(By.XPATH, xp_date_ticket)
        if not _set_input_value(el_ticket, invoice_date):
            raise RuntimeError("failed to set ticket date")
        try:
            el_ticket.send_keys(Keys.ENTER)
        except Exception:
            pass
        time.sleep(0.62)

    except Exception as e:
        raise RuntimeError("fill_invoice_fields_in_order_first failed: " + str(e))

    print(f"[fill_invoice_fields_in_order_first] done for SalesId: {salesid}, InvoiceDate: {invoice_date}")
    return True



def click_for_save_button_first(driver, timeout=7):
    """
    Click the save button (user-provided xpath).
    Returns True if clicked, False otherwise.
    """
    xp_save = "/html/body/div[1]/div/div[2]/section/section/div/div[2]/form/div[2]/button[3]/span"

    try:
        # wait until the element (span inside button) is present & clickable
        el = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.XPATH, xp_save)))
    except Exception:
        # not found or not clickable
        try:
            # last-chance: try to find the button element (parent) and click it
            btn_parent = driver.find_element(By.XPATH, xp_save + "/ancestor::button[1]")
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn_parent)
            driver.execute_script("arguments[0].click();", btn_parent)
            time.sleep(0.8)
            return True
        except Exception:
            return False

    # try normal click, fallback to JS click
    try:
        el.click()
        time.sleep(0.5)
        return True
    except Exception:
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            driver.execute_script("arguments[0].click();", el)
            time.sleep(0.5)
            return True
        except Exception:
            return False



# ----------------- simple test harness (append to end of MainGetValueOfImagecopy.py) -----------------
# if __name__ == "__main__":
    
# --------------------------------------------------------------------------------------------------------

    
