# run_invoice_automation.py
from pypdf import PdfReader, PdfWriter
from Get_Value_Form_DataBase import SQL, fetch_df

from xmlrpc.client import _datetime

import pandas as pd
from typing import Any
from asyncio import timeout
import os
import time
from pathlib import Path
from typing import Optional
import pyautogui

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import time
from selenium.webdriver import ActionChains
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

# ---------------- CONFIG ----------------
URL = "https://com7.operations.dynamics.com/?cmp=GI&mi=DefaultDashboard"
EMAIL = "mis_pos@com7erp.onmicrosoft.com"
PASSWORD = "2025MISPOS@COM70"
DOWNLOAD_DIR = r"C:\Users\Administrator\Downloads"   # โฟลเดอร์ที่ไฟล์จะถูกดาวน์โหลดเข้า
OUTPUT_WAIT_SCREEN_SECONDS = 2


# ----------------------------------------



def init_driver(headless: bool = False) -> tuple:
    opts = Options()
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    driver.maximize_window()
    wait = WebDriverWait(driver, 20)
    return driver, wait

def login_and_navigate(driver, wait, email: str, password: str, url_override: str = None):
    """
    Login flow. If url_override is provided, navigate to that URL instead of the module-level URL.
    """
    target_url = url_override or URL
    driver.get(target_url)

    # Email
    email_el = wait.until(EC.element_to_be_clickable((By.ID, "i0116")))
    email_el.clear(); email_el.send_keys(email); email_el.send_keys(Keys.ENTER)
    time.sleep(2)

    # Password
    pwd = wait.until(EC.element_to_be_clickable((By.ID, "i0118")))
    pwd.clear(); pwd.send_keys(password); pwd.send_keys(Keys.ENTER)
    time.sleep(2)

    # "Stay signed in?" -> No
    no_btn = wait.until(EC.element_to_be_clickable((By.ID, "idBtn_Back")))
    no_btn.click()
    time.sleep(2)

    # รอหน้า Dashboard (use case-insensitive check)
    try:
        wait.until(lambda d: "defaultdashboard" in d.current_url.lower())
    except Exception:
        pass

    # ปิด About dialog (span id^=SysAbout_..._Close_label)
    css_close = "span[id^='SysAbout_'][id$='_Close_label']"
    try:
        close_span = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, css_close)))
        try:
            btn = close_span.find_element(By.XPATH, "./ancestor::button[1]")
            try:
                btn.click()
            except Exception:
                driver.execute_script("arguments[0].click();", btn)
        except Exception:
            try:
                close_span.click()
            except Exception:
                driver.execute_script("arguments[0].click();", close_span)
    except Exception:
        # ไม่มี dialog ก็ข้าม
        pass

    # คลิก Recent symbol (เหมือนเดิม)
    css_recent = "span.workspace-image.Recent-symbol"
    try:
        el_recent = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, css_recent)))
        try:
            el_recent.click()
        except Exception:
            driver.execute_script("arguments[0].click();", el_recent)
    except Exception:
        pass

    # ฟังก์ชันคืนค่า URL ปัจจุบันให้ caller ใช้ต่อได้ (optional)
    return driver.current_url




def return_value_Of_data(row_idx: int, col_name: str, df: pd.DataFrame = None, date_format: str = "%Y-%m-%d") -> Any:
    """
    คืนค่า cell ที่ตำแหน่ง (row_idx, col_name)
    - row_idx: positional index (0-based)
    - col_name: ชื่อคอลัมน์
    - df: ถ้าไม่ส่ง จะใช้ global 'df' (ถ้ามี)
    - คืน None หากเป็น NaN
    - คืนวันที่เป็นสตริงตาม date_format ถ้าค่าเป็น datetime-like
    """
    # หา DataFrame
    if df is None:
        df = globals().get("df")
        if df is None:
            raise ValueError("No DataFrame provided and global 'df' not found.")

    # ตรวจค่าพื้นฐาน
    if not isinstance(row_idx, int):
        raise TypeError("row_idx must be int (0-based).")
    if col_name not in df.columns:
        raise KeyError(f"Column '{col_name}' not found in DataFrame.")
    if row_idx < 0 or row_idx >= len(df):
        raise IndexError(f"row_idx {row_idx} out of range (0..{len(df)-1}).")

    val = df.iloc[row_idx][col_name]

    # ถ้าเป็น NaN -> คืน None
    if pd.isna(val):
        return None

    # กรณีเป็น pandas.Timestamp หรือ Python datetime.datetime -> format แล้วคืนเป็น string
    try:
        if isinstance(val, pd.Timestamp) or isinstance(val, _datetime):
            return pd.to_datetime(val).strftime(date_format)
    except Exception:
        # ป้องกันกรณีที่ isinstance(...) ล้ม (ป้องกัน unexpected types)
        pass

    # ถ้าเป็น numpy scalar ให้ convert เป็น native python
    try:
        if hasattr(val, "item"):
            return val.item()
    except Exception:
        pass

    # หากเป็นชนิดอื่น ๆ (string/number) คืนค่าตามเดิม (string ก็คืน string)
    return val

    


def _make_branch_mi_url(base_url: str, branch: str, mi: str):
    """Return base_url but with cmp=<branch> and mi=<mi> in query (doseq-safe)."""
    parsed = urlparse(base_url)
    qs = parse_qs(parsed.query)
    qs['cmp'] = [str(branch).strip().lower()]
    qs['mi'] = [mi]
    new_q = urlencode(qs, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_q, parsed.fragment))

def open_invoice_and_prepare_print(driver, wait, filter_value, base_url: str = None, gi_branch: str = None):
    """
    Updated start: navigate to CustInvoiceJournal using gi_branch (or base_url's cmp).
    After this navigation the function continues with your original logic to find/filter the invoice.
    """
    base = base_url or getattr(driver, "current_url", None) or URL

    if not gi_branch:
        try:
            parsed = urlparse(base)
            qs = parse_qs(parsed.query)
            gi_branch = qs.get('cmp', [None])[0]
        except Exception:
            gi_branch = None

    if not gi_branch:
        gi_branch = "GI"

    try:
        target_url = _make_branch_mi_url(base, gi_branch, "CustInvoiceJournal")
    except Exception:
        target_url = f"https://com7.operations.dynamics.com/?cmp={str(gi_branch).strip().lower()}&mi=CustInvoiceJournal"

    print("[DEBUG] open_invoice_and_prepare_print -> navigating to:", target_url)

    try:
        driver.get(target_url)
        wait.until(lambda d: ("custinvoicejournal" in d.current_url.lower()) or ("defaultdashboard" in d.current_url.lower()))
    except Exception:
        time.sleep(1.2)

    # Preferred SI filter path (CSS/id, no XPath):
    # 1) click filter header, 2) click/focus filter input, then type SI.
    si_header_selectors = [
        "#CustInvoiceJour_InvoiceNum_Grid_1695_0_header",
        "div[id^='CustInvoiceJour_InvoiceNum_Grid_'][id$='_0_header']",
        "div[id*='CustInvoiceJour_InvoiceNum_Grid_'][id$='_header']",
    ]
    si_input_selectors = [
        "#__FilterField_CustInvoiceJour_InvoiceNum_Grid_InvoiceId_Input_0_input",
        "input[id^='__FilterField_CustInvoiceJour_InvoiceNum_Grid_InvoiceId_Input_'][id$='_input']",
        "input[id*='FilterField_CustInvoiceJour_InvoiceNum_Grid_InvoiceId_Input_'][id$='_input']",
    ]
    elm = None
    try:
        header = None
        for s in si_header_selectors:
            try:
                header = WebDriverWait(driver, 2).until(EC.element_to_be_clickable((By.CSS_SELECTOR, s)))
                if header:
                    break
            except Exception:
                header = None
        if not header:
            raise RuntimeError("SI header not found by CSS selectors")

        try:
            header.click()
        except Exception:
            driver.execute_script("arguments[0].click();", header)
        time.sleep(0.35)

        for s in si_input_selectors:
            try:
                elm = WebDriverWait(driver, 2).until(EC.visibility_of_element_located((By.CSS_SELECTOR, s)))
                if elm:
                    break
            except Exception:
                elm = None
        if not elm:
            raise RuntimeError("SI input not found by CSS selectors")

        try:
            elm.click()
        except Exception:
            driver.execute_script("arguments[0].click();", elm)
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'}); arguments[0].focus();", elm)
        except Exception:
            pass
        time.sleep(0.3)
    except Exception:
        elm = None

    css_candidates = (
        "input[id*='QuickFilter_Input']",
        "input[id*='FilterField_CustInvoiceJour']",
        "input[id*='FilterField']",
        "input[id*='SalesOrderNumber']",
        "input[role='combobox']",
        "div[role='combobox'] input"
    )
    sel = ",".join(css_candidates)

    def _type_and_enter(elm, val):
        try:
            elm.clear()
        except Exception:
            pass
        try:
            for ch in str(val):
                elm.send_keys(ch)
                time.sleep(0.02)
            time.sleep(0.05)
            elm.send_keys(Keys.ENTER)
            return True
        except Exception:
            pass
        try:
            ActionChains(driver).move_to_element(elm).click().send_keys(str(val)).send_keys(Keys.ENTER).perform()
            return True
        except Exception:
            pass
        try:
            driver.execute_script(
                "const el=arguments[0], v=arguments[1];"
                "el.focus(); el.value = v;"
                "el.dispatchEvent(new Event('input',{bubbles:true}));"
                "el.dispatchEvent(new Event('change',{bubbles:true}));"
                "el.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));"
                "el.dispatchEvent(new KeyboardEvent('keyup',{key:'Enter',bubbles:true}));",
                elm, str(val)
            )
            return True
        except Exception:
            return False

    if not elm:
        try:
            elm = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, sel)))
        except Exception:
            elm = None

    if not elm:
        for frm in driver.find_elements(By.TAG_NAME, "iframe"):
            try:
                driver.switch_to.frame(frm)
                try:
                    elm = WebDriverWait(driver, 1).until(EC.visibility_of_element_located((By.CSS_SELECTOR, sel)))
                    driver.switch_to.default_content()
                    break
                except Exception:
                    driver.switch_to.default_content()
                    elm = None
                    continue
            except Exception:
                try:
                    driver.switch_to.default_content()
                except:
                    pass
                continue

    if not elm:
        try:
            js = (
                "const selectors = arguments[0].split(','); let el=null;"
                "for(const s of selectors){ try{ el=document.querySelector(s.trim()); if(el) break;}catch(e){} }"
                "return el;"
            )
            elm = driver.execute_script(js, sel)
        except Exception:
            elm = None

    if not elm:
        print("Warning: quick filter input not found.")
    else:
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'}); arguments[0].focus();", elm)
        except Exception:
            pass

        ok = _type_and_enter(elm, filter_value)
        if not ok:
            print("Warning: failed to type filter value.")

        time.sleep(2)

    try:
        v_btn = wait.until(EC.element_to_be_clickable((By.ID, "custinvoicejournal_1_View_button")))
        try:
            v_btn.click()
        except Exception:
            driver.execute_script("arguments[0].click();", v_btn)
    except Exception:
        try:
            driver.execute_script("var e=document.getElementById('custinvoicejournal_1_View_button'); if(e){e.click();}")
        except Exception:
            pass

    time.sleep(0.8)

    try:
        driver.execute_script(
            "var e = document.querySelector(\"span[id*='View_label']\"); if(e){ (e.closest('button')||e).click(); }"
        )
    except Exception:
        pass

    time.sleep(0.5)

    try:
        driver.execute_script(
            "var e = document.querySelector(\"span[id*='MIS_SalesReceiptNoteOriginalCopy']\"); if(e){ (e.closest('button')||e).click(); }"
        )
    except Exception:
        pass

    driver.execute_script("document.getElementById('custinvoicejournal_1_View_button').click();")
    driver.execute_script("document.getElementById('custinvoicejournal_1_View_button').click();")
    time.sleep(2)
    driver.execute_script("var e=document.querySelector(\"span[id*='MIS_SalesReceiptNoteOriginalCopy']\"); if(e){(e.closest('button')||e).click();}")

    return True


def _wait_for_file_ready(file_path: Path, timeout: float = 30.0, stable_seconds: float = 1.5) -> bool:
    start = time.time()
    last_size = -1
    stable_start = None
    while time.time() - start < timeout:
        if not file_path.exists():
            time.sleep(0.3)
            continue
        if file_path.suffix.lower() == ".crdownload":
            time.sleep(0.5)
            continue
        try:
            size = file_path.stat().st_size
        except Exception:
            time.sleep(0.3)
            continue
        if size == last_size and size > 0:
            if stable_start is None:
                stable_start = time.time()
            elif time.time() - stable_start >= stable_seconds:
                return True
        else:
            stable_start = None
        last_size = size
        time.sleep(0.3)
    return False




def latest_file(download_dir: str = DOWNLOAD_DIR) -> Optional[str]:
    files = [
        os.path.join(download_dir, f)
        for f in os.listdir(download_dir)
        if os.path.isfile(os.path.join(download_dir, f)) and f.lower().endswith(".pdf")
    ]
    return max(files, key=os.path.getmtime) if files else None

def _latest_file_path(path: Path) -> Optional[Path]:
    files = [p for p in path.iterdir() if p.is_file() and p.name.lower().endswith(".pdf")]
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def _wait_for_new_file(path: Path, timeout: float = 30.0) -> Optional[Path]:
    start = time.time()
    last = _latest_file_path(path)
    last_name = last.name if last else None
    while time.time() - start < timeout:
        cur = _latest_file_path(path)
        if cur and cur.name != last_name:
            return cur
        time.sleep(0.5)
    return _latest_file_path(path)

INVOICE_PDF_DIR = Path(r"C:\Users\Administrator\Desktop\PythonScriptAutomation\DMS_INVOICE_ACTACT\for_dowload_file_pdf_invoice")
def print_page_2_via_pyautogui(driver, serialname,
                               download_selector: str = "#download",
                               download_dir: str = DOWNLOAD_DIR,
                               dest_dir: Path = INVOICE_PDF_DIR,
                               wait_ready: float = 15.0,
                               wait_download: float = 30.0) -> Optional[str]:
    """
    Click download button via JS, wait for download, move to dest_dir,
    extract page 2 only, overwrite file. Returns new file path or None.
    """
    if not serialname:
        return None

    # best-effort focus on top-level document
    try:
        driver.switch_to.default_content()
    except Exception:
        pass

    # wait for page ready
    try:
        WebDriverWait(driver, wait_ready).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
    except Exception:
        pass

    # click download button (main doc)
    clicked = False
    try:
        clicked = bool(driver.execute_script(
            "var el = document.querySelector(arguments[0]);"
            "if(!el) return false;"
            "el.scrollIntoView({block:'center', inline:'center'});"
            "['mouseover','mousedown','mouseup','click'].forEach(function(t){"
            "  el.dispatchEvent(new MouseEvent(t, {bubbles:true, cancelable:true, view:window}));"
            "});"
            "return true;",
            download_selector
        ))
    except Exception:
        clicked = False

    # try in iframes if not found/clicked
    if not clicked:
        try:
            frames = driver.find_elements(By.TAG_NAME, "iframe")
        except Exception:
            frames = []
        for frm in frames:
            try:
                driver.switch_to.frame(frm)
                clicked = bool(driver.execute_script(
                    "var el = document.querySelector(arguments[0]);"
                    "if(!el) return false;"
                    "el.scrollIntoView({block:'center', inline:'center'});"
                    "['mouseover','mousedown','mouseup','click'].forEach(function(t){"
                    "  el.dispatchEvent(new MouseEvent(t, {bubbles:true, cancelable:true, view:window}));"
                    "});"
                    "return true;",
                    download_selector
                ))
                driver.switch_to.default_content()
                if clicked:
                    break
            except Exception:
                try:
                    driver.switch_to.default_content()
                except Exception:
                    pass

    # wait for download and move file
    dl_path = Path(download_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    latest = _wait_for_new_file(dl_path, timeout=wait_download)
    if not latest:
        return None

    # wait until download file is fully written
    if not _wait_for_file_ready(latest, timeout=wait_download):
        return None

    suffix = latest.suffix or ".pdf"
    dest_path = dest_dir / f"invoice-{serialname}{suffix}"
    try:
        latest.replace(dest_path)
    except Exception:
        # fallback: copy then remove if replace fails
        try:
            dest_path.write_bytes(latest.read_bytes())
            latest.unlink(missing_ok=True)
        except Exception:
            return None

    # keep only page 2
    try:
        reader = PdfReader(str(dest_path))
        if len(reader.pages) < 2:
            return str(dest_path)
        writer = PdfWriter()
        writer.add_page(reader.pages[1])  # page 2 (0-based)
        with open(dest_path, "wb") as f:
            writer.write(f)
    except Exception:
        return str(dest_path)

    return str(dest_path)
    

# ----------------- main -----------------
def main(filter_value: str):
    driver, wait = init_driver(headless=False)
    try:
        login_and_navigate(driver, wait, EMAIL, PASSWORD)
        open_invoice_and_prepare_print(driver, wait)


        time.sleep(1)
        print("Please ensure the browser window is focused. Starting print sequence in 2s...")
        time.sleep(2)

        print_page_2_via_pyautogui()

        # รอให้ดาวน์โหลดเสร็จเล็กน้อย
        time.sleep(5)

        latest = print_page_2_via_pyautogui(driver, serialname=filter_value)

        if latest:
            print("Latest downloaded file:", latest)
        else:
            print("No files found after download")

        # ถ้าต้องการค้างเพื่อดูผล ให้เพิ่ม sleep หรือลบ driver.quit()
        time.sleep(2)

    finally:
        try:
            driver.quit()
        except Exception:
            pass

# if __name__ == "__main__":
#     # main()
