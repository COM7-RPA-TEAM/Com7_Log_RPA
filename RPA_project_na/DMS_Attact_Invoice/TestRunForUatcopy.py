# TestRunForUat.py  (ready-to-run, updated)
import datetime
from csv import reader
import os
import sys
import time
from httpcore import TimeoutException
import pyodbc
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver import ActionChains
from datetime import datetime as _datetime
from typing import Any
from pathlib import Path
from GetdataFromGoogleSheet import get_dms_credentials_from_sheet, get_matching_invoice_set
from GetdataFromGoogleSheet import get_value_from_sheet_by_key
from rpa_logger import DashboardLogger


# local module imports (assumes these exist and signatures match)
from Get_Value_Form_DataBase import (
    fetch_df,
    get_userpass_for_warehouse,
    return_value_Of_data,
    mark_complete_success_by_serial,
    mark_complete_error_by_serial,
)
from MainGetValueOfImagecopy import (
    change_lang_and_open_page,
    clean_token,
    click_for_save_button,
    click_for_save_button_first,
    click_send_and_confirm,
    click_sales_menu_sequence,
    click_three_buttons,
    fill_invoice_fields_in_order,
    fill_invoice_fields_in_order_first,
    fill_serial_input,
    fill_textarea_and_submit,
    init_driverDMS,
    prepare_login_inputs,
    preprocess_and_save,
    upload_latest_file_strict,
    wait_login_result,
    fill_textarea_and_submit_and_tab,
)
from run_invoice_automation import (
    init_driver,
    latest_file,
    login_and_navigate,
    open_invoice_and_prepare_print,
    print_page_2_via_pyautogui,
)

from GetdataFromGoogleSheet import (
    get_matching_invoice_set,
    write_status_back_to_sheet_by_invoice,
    read_invoice_ids_from_sheet,
)
from typhoon_ocr import ocr_document

# --------------------- config ---------------------
SA_JSON_LOCAL = r"C:\Users\Administrator\Desktop\PythonScriptAutomation\DMS_INVOICE_ACTACT\invoice-dms-attach-and-post-2ea3e8ae219c.json"
SHEET_ID_LOCAL = "1Kr_SUUribnt-sjkdb7eYe4S_vNBW4OjM_-Ubhgd-Ox0"
SHEET_NAME = "Sheet1"
INVOICE_COL_INDEX = 1  # 1 == column A
FLAG_COL_INDEX = 5
SCOPES_READ = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly"
]

DB_DRIVER = "SQL Server"
DB_SERVER = "192.168.43.84"
DB_DATABASE = "RPA"
DB_USER = "nene-mis_erp"
DB_PWD = "np.123456"

# XPath for the "send/submit" button after upload
SEND_BUTTON_XPATH = "/html/body/div[1]/div/div[2]/section/section/div/div[1]/div[2]/div[2]/div[1]/div[3]/table/tbody/tr/td[2]/div/span/button"
CONFIRM_BUTTON_XPATH = "//*[starts-with(@id,'el-popover-') or contains(@id,'el-popover')]/div[1]/button[2]"

# Typhoon OCR
TYPHOON_OCR_API_KEY = "sk-5GDFvDdaQa3B7D3AHpIyIpw0F8BO0rPzIDa6uKwqhF1Xhey9"
os.environ["TYPHOON_OCR_API_KEY"] = TYPHOON_OCR_API_KEY


EMAIL = "mis_pos@com7erp.onmicrosoft.com"
WEB_PASSWORD = "2025MISPOS@COM70"
DOWNLOAD_DIR = r"C:\Users\Administrator\Desktop\PythonScriptAutomation\DMS_INVOICE_ACTACT\for_dowload_file_pdf_invoice"

URLDMS = "https://globaldms.aionauto.com/login"
OUTPUT_DIR = Path(r"C:\Users\Administrator\Desktop\PythonScriptAutomation\DMS_INVOICE_ACTACT\for_image_captcha")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
IMG_PATH = OUTPUT_DIR / "captcha.png"
PREPROC_PATH = OUTPUT_DIR / "captcha_preproc.png"

MIN_CONF = 0.85
REQUIRED_LEN = 4

POST_LOGIN_LOCATOR = (By.XPATH, "//aside//ul[contains(@class,'el-menu')]")

HERE = Path(__file__).parent.resolve()
CFG_PATH = HERE / "CONFIG_DataBase.ini"

LOG_BOT_PATH = HERE / "Log_bot.xlsx"
LOG_BOT_COLUMNS = [
    "SalesId",
    "GI branch INV",
    "Serial(Vin Number)",
    "Warehouse DMS",
    "Status",
    "Message",
    "Error",
    "FinishedAt",
]



def format_error(function_name: str, message: str) -> str:
    fn = str(function_name or "").strip() or "unknown"
    msg = str(message or "").strip() or "Unknown error"
    return f"Error_{fn}: {msg}"

def append_bot_log(
    sales_id: Any,
    gi_branch: Any,
    serial_vin: Any,
    warehouse_dms: Any,
    error_text: str,
    finished_at: str,
    status_text: str = "",
    message_text: str = "",
    log_path: Path = LOG_BOT_PATH,
) -> None:
    columns = [
        "SalesId",
        "GI branch INV",
        "Serial(Vin Number)",
        "Warehouse DMS",
        "Status",
        "Message",
        "Error",
        "FinishedAt",
    ]

    raw_error = str(error_text or "").strip()
    resolved_status = str(status_text or "").strip()
    if not resolved_status:
        resolved_status = "ERROR" if raw_error else "SUCCESS"

    resolved_message = str(message_text or "").strip()
    if not resolved_message:
        resolved_message = raw_error or "Process completed successfully"

    # Keep legacy "Error" column meaningful: show SUCCESS text when no error.
    resolved_error = raw_error if raw_error else f"SUCCESS: {resolved_message}"

    row = {
        "SalesId": "" if sales_id is None else str(sales_id).strip(),
        "GI branch INV": "" if gi_branch is None else str(gi_branch).strip(),
        "Serial(Vin Number)": "" if serial_vin is None else str(serial_vin).strip(),
        "Warehouse DMS": "" if warehouse_dms is None else str(warehouse_dms).strip(),
        "Status": resolved_status,
        "Message": resolved_message,
        "Error": resolved_error,
        "FinishedAt": str(finished_at or "").strip(),
    }
    try:
        
        if log_path.exists():
            df_log = pd.read_excel(log_path)
        else:
            df_log = pd.DataFrame(columns=columns)
        # Backward-compatible for old log files that may not have new columns.
        for col in columns:
            if col not in df_log.columns:
                df_log[col] = ""

        dedupe_cols = [
            "SalesId",
            "GI branch INV",
            "Serial(Vin Number)",
            "Warehouse DMS",
            "Status",
            "Message",
            "Error",
        ]
        mask = pd.Series(True, index=df_log.index)
        for c in dedupe_cols:
            mask &= df_log[c].fillna("").astype(str).str.strip().eq(str(row[c]).strip())

        # If same log already exists, only refresh FinishedAt instead of appending duplicate rows.
        if mask.any():
            last_idx = df_log[mask].index[-1]
            df_log.loc[last_idx, "FinishedAt"] = row["FinishedAt"]
        else:
            df_log = pd.concat([df_log, pd.DataFrame([row])], ignore_index=True)

        df_log = df_log.reindex(columns=columns)
        df_log.to_excel(log_path, index=False)
    except Exception as e_log:
        print(f"[LOG] Failed to write {log_path}: {e_log}")







# SQL: adjust date filter if needed for testing
SQL = """ 
WITH cte AS (
  SELECT *,
         ROW_NUMBER() OVER (PARTITION BY InvoiceId ORDER BY InvoiceDate DESC, SalesId DESC) AS rn
  FROM [RPA].[dbo].GI_SALES_INVOICE_LINES
  WHERE serial IS NOT NULL
    AND serial NOT LIKE 'HACAAAB37S3D03916'
    AND serial NOT LIKE 'HACAAAB30S3D03790'
    AND serial NOT LIKE 'HACAAAB37S3D03558'
    AND serial NOT LIKE 'HACAAAB38S3D04038'
    AND serial NOT LIKE 'LNAT4AB3XR5G00131'
    AND serial NOT LIKE 'MRVAALB3XS6000528'
    AND serial NOT LIKE 'HACAAAB38S3D02516'
    AND lineamount <> 0
)
SELECT
  SalesId,
  InvoiceId,
  InvoiceDate,
  LineAmount,
  ROUND(LineAmount * 0.07, 2) AS vat,
  ROUND(LineAmount * 1.07, 2) AS TotalAmount,
  serial,
  WarehouseId,
  InvoiceDate,
  CompleteFlag,
  CompleteDatetime
FROM cte
WHERE rn = 1;
"""

# --------------------------------------------------

def main_fetch_db():
    try:
        df = fetch_df(
            SQL,
            driver=DB_DRIVER,
            server=DB_SERVER,
            database=DB_DATABASE,
            uid=DB_USER,
            pwd=DB_PWD,
            timeout=10,
        )
    except Exception as e:
        print("fetch_df failed:", e)
        return None, 0

    if df is None:
        return None, 0

    Count_row = len(df)
    
    return df, Count_row


def _my_db_fetcher_for_matching():
    """Return list of InvoiceIds (strings) from DB for matching with Google Sheet."""
    try:
        df_db = fetch_df(
            SQL,
            driver=DB_DRIVER,
            server=DB_SERVER,
            database=DB_DATABASE,
            uid=DB_USER,
            pwd=DB_PWD,
            timeout=10,
        )
    except Exception as e:
        print("Error calling fetch_df in fetcher:", e)
        return []

    if df_db is None or df_db.empty:
        return []

    for col in ("InvoiceId", "InvoiceID", "invoice_id", "invoiceid", "INVOICE_ID"):
        if col in df_db.columns:
            return [str(x).strip() for x in df_db[col].astype(str).tolist() if str(x).strip()]

    # fallback to first column if single column returned
    if df_db.shape[1] == 1:
        return [str(x).strip() for x in df_db.iloc[:, 0].astype(str).tolist() if str(x).strip()]

    print("Warning: cannot find InvoiceId column in DB result. Columns:", df_db.columns.tolist())
    return []


def safe_write_status(invoice_id: str, status: str):
    """Wrapper to write status to sheet and catch/log errors."""
    try:
        write_status_back_to_sheet_by_invoice(
            SA_JSON_LOCAL, SHEET_ID_LOCAL, SHEET_NAME,
            { invoice_id: status },
            invoice_col_index=INVOICE_COL_INDEX,
            status_col_index=5
        )
        print(f"[SHEET] wrote status {status!r} for invoice {invoice_id}")
    except Exception as e:
        print(f"[SHEET] Failed to write status {status!r} for invoice {invoice_id}: {e}")


def load_sheet_maps_once(
    sa_json_path,
    sheet_id,
    sheet_name,
    invoice_col_index=1,
    flag_col_index=5,
    serial_col_index=3,
    gi_col_index=2,
    warehouse_col_index=4,
):
    """Read Google Sheet once and build lookup maps for processing."""
    from google.oauth2.service_account import Credentials
    import gspread

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_file(sa_json_path, scopes=scopes)
    client = gspread.authorize(creds)
    sh = client.open_by_key(sheet_id)
    ws = sh.worksheet(sheet_name) if sheet_name else sh.get_worksheet(0)
    rows = ws.get_all_values()

    inv_idx = max(0, invoice_col_index - 1)
    flag_idx = max(0, flag_col_index - 1)
    serial_idx = max(0, serial_col_index - 1)
    gi_idx = max(0, gi_col_index - 1)
    wh_idx = max(0, warehouse_col_index - 1)

    invoice_flag_map = {}
    serial_gi_map = {}
    serial_wh_map = {}

    for r in rows[1:]:
        inv = str(r[inv_idx]).strip() if len(r) > inv_idx else ""
        flag = str(r[flag_idx]).strip() if len(r) > flag_idx else ""
        serial = str(r[serial_idx]).strip() if len(r) > serial_idx else ""
        gi_val = str(r[gi_idx]).strip() if len(r) > gi_idx else ""
        wh_val = str(r[wh_idx]).strip() if len(r) > wh_idx else ""

        if inv:
            invoice_flag_map[inv.upper()] = flag
        if serial:
            sk = serial.upper()
            serial_gi_map[sk] = gi_val
            serial_wh_map[sk] = wh_val

    return invoice_flag_map, serial_gi_map, serial_wh_map


# ---------- main runner ----------
if __name__ == "__main__":
    logger = DashboardLogger(bot_name="Attact_invoice_to_DMS")
    logger.send_log(stage="Start job", status="Running")
    # --- 1) fetch db rows ---
    df, Count_row = main_fetch_db()
    if df is None or Count_row == 0:
        print("No rows returned from DB. Exiting.")
        sys.exit(0)
    
    # --- 2) get matching set between sheet and DB ---
    try:
        matched_set = get_matching_invoice_set(
            SA_JSON_LOCAL,
            SHEET_ID_LOCAL,
            sheet_name=SHEET_NAME,
            invoice_col_index=INVOICE_COL_INDEX,
            fetcher=_my_db_fetcher_for_matching,
            
        )
        logger.send_log(stage="matching set between sheet and DB", status="Running")
    except Exception as e:
        print("get_matching_invoice_set() failed:", e)
        matched_set = []
        logger.send_log(
        stage="get matching set between sheet and DB",
        status="Failed",
        error_message="get_matching_invoice_set"
        )

    try:
        sheet_invoice_ids = read_invoice_ids_from_sheet(
        SA_JSON_LOCAL,
        SHEET_ID_LOCAL,
        sheet_name=SHEET_NAME,
        invoice_col_index=INVOICE_COL_INDEX,
    )
    except Exception as e_sheet_ids:
        print("[WARN] read_invoice_ids_from_sheet() failed:", e_sheet_ids)
        sheet_invoice_ids = []
        logger.send_log(
        stage="get matching set between sheet and DB",
        status="Failed",
        error_message="[WARN] read_invoice_ids_from_sheet() failed:"
        )

    sheet_norm = set(str(x).strip() for x in sheet_invoice_ids if x is not None and str(x).strip())

    print(f"[INFO] matched invoices count: {len(matched_set)}")
    if not matched_set:
        print("[INFO] No matching InvoiceIDs between DB and Google Sheet. Exiting.")
        try:
            finished_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for si in sorted(sheet_norm):
                append_bot_log(
                sales_id="",
                gi_branch="",
                serial_vin="",
                warehouse_dms="",
                error_text=format_error("validate_si_match", f"ข้อมูล SI ไม่ตรง ({si})"),
                finished_at=finished_at,
            )
        except Exception as e_log_mismatch:
            print("[LOG] Failed to write SI mismatch logs:", e_log_mismatch)
        sys.exit(0)


# --- 3) determine invoice column in df ---
    invoice_col_in_df = None
    for c in ("InvoiceId", "InvoiceID", "invoice_id", "invoiceid", "INVOICE_ID"):
        if c in df.columns:
            invoice_col_in_df = c
            break
    if invoice_col_in_df is None:
        print("DataFrame from DB does not contain an InvoiceId-like column. Columns:", df.columns.tolist())
        sys.exit(1)




    # --- 3.1) read Sheet once and cache maps (avoid API 429 from many reads) ---
    try:
        invoice_flag_map, serial_gi_map, serial_wh_map = load_sheet_maps_once(
            SA_JSON_LOCAL,
            SHEET_ID_LOCAL,
            SHEET_NAME,
            invoice_col_index=INVOICE_COL_INDEX,
            flag_col_index=FLAG_COL_INDEX,
            serial_col_index=3,   # C = Serial
            gi_col_index=2,       # B = GI Branch
            warehouse_col_index=4 # D = Warehouse
        )
        print(
            f"[INFO] Sheet cache loaded: invoice_flags={len(invoice_flag_map)}, "
            f"serial_gi={len(serial_gi_map)}, serial_wh={len(serial_wh_map)}"
        )
    except Exception as e:
        print("[ERROR] failed to preload Sheet maps:", e)
        logger.send_log(
        stage="read Sheet once and cache maps",
        status="Failed",
        error_message="[ERROR] failed to preload Sheet maps"
        )
        sys.exit(1)

        # --- 4) pick selected indices in original df that match ---
    matched_norm = {str(x).strip() for x in matched_set if x is not None and str(x).strip()}
    selected_indices = df.index[
        df[invoice_col_in_df].astype(str).str.strip().isin(matched_norm)
    ].tolist()

    # Log only SI values from Sheet1 that are not found in DB.
    try:
        db_norm = {
            str(x).strip()
            for x in df[invoice_col_in_df].astype(str).tolist()
            if str(x).strip()
        }
        unmatched_sheet_ids = sorted(sheet_norm - db_norm)

        if unmatched_sheet_ids:
            finished_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for si in unmatched_sheet_ids:
                append_bot_log(
                    sales_id="",
                    gi_branch="",
                    serial_vin="",
                    warehouse_dms="",
                    error_text=format_error("validate_si_match", f"ข้อมูล SI ไม่ตรง ({si})"),
                    finished_at=finished_at,
                )
    except Exception as e_log_unmatched:
        print("[LOG] Failed to append Sheet1 unmatched SI logs:", e_log_unmatched)
        logger.send_log(
        stage="read Sheet once and cache maps",
        status="Failed",
        error_message="Failed to append Sheet1 unmatched SI logs"
        )




    print(f"[INFO] Selected rows to process (count): {len(selected_indices)}")
    if not selected_indices:
        print("[INFO] No DB rows correspond to matched invoices. Exiting.")
        sys.exit(0)

    # --- 4.1) keep only rows whose Sheet Flag is empty ---
    def _is_empty_flag(v):
        return v is None or str(v).strip() == ""

    selected_by_empty_flag = []
    for run_idx in selected_indices:
        invoice_id = str(df.loc[run_idx, invoice_col_in_df]).strip()
        if not invoice_id:
            continue
        flag_val = invoice_flag_map.get(invoice_id.upper(), "")

        if _is_empty_flag(flag_val):
            selected_by_empty_flag.append(run_idx)
        else:
            print(f"[SKIP] SI {invoice_id!r} -> Flag not empty ({str(flag_val).strip()!r})")

    selected_indices = selected_by_empty_flag
    print(f"[INFO] Selected rows with empty Sheet Flag (count): {len(selected_indices)}")
    if not selected_indices:
        print("[INFO] No rows with empty Sheet Flag. Exiting.")
        sys.exit(0)

    # --- 5) process each selected index ---
    for run_idx in selected_indices:
        logger.send_log(
        stage="Processing Invoice ",
        status="Running"
        )
        print(f"\n=== PROCESS df index {run_idx} ===")
        serial_val = None  # ensure defined
        latest = None
        filter_value = None
        driver_dms = None
        try:
            row = df.loc[run_idx]
            filter_value = str(row[invoice_col_in_df]).strip()
            serial = str(row.get("serial", "")).strip()
            serial_val = serial or None
            SalesId = row.get("SalesId")
            InvoiceDate = row.get("InvoiceDate")
            LineAmount = row.get("LineAmount")
            TotalAmount = row.get("TotalAmount")
            WarehouseId = row.get("WarehouseId")
            

            print("Row values:", filter_value, serial, SalesId, InvoiceDate, LineAmount, TotalAmount)

            # Flag was already filtered before this loop (empty only).

            if not filter_value:
                print(f"No InvoiceId for df index {run_idx} -> skip this row.")
                continue


            key_for_sheet = (serial or "").strip() if serial else (filter_value or "").strip()
            key_for_sheet_up = key_for_sheet.upper()

# read GI branch from sheet (column B -> return_col_index=2)
            gi_branch = ""
            gi_val = serial_gi_map.get(key_for_sheet_up)
            if gi_val is not None:
                gi_branch = str(gi_val).strip()
            print("[DEBUG] gi_branch from cache:", repr(gi_branch))

            # ---------- Part A: open invoice in ERP and print ----------
            driver, wait = init_driver(headless=False)
            try:
                logger.send_log(stage="open invoice in ERP", status="Running")
                if gi_branch and str(gi_branch).strip():
                    branch_norm = str(gi_branch).strip().lower()   # normalize to lower-case (recommended)
                    new_url = f"https://com7.operations.dynamics.com/?cmp={branch_norm}&mi=DefaultDashboard"
                    print("[DEBUG] Navigating to branch URL:", new_url)
                else:
                    new_url = None
                post_login_url = login_and_navigate(driver, wait, EMAIL, WEB_PASSWORD, url_override=new_url)
                print("[DEBUG] login returned URL:", post_login_url)
                time.sleep(2)
                open_invoice_and_prepare_print(driver, wait, filter_value, base_url=post_login_url, gi_branch=gi_branch)
                time.sleep(11)
                # print to pdf/download (uses pyautogui etc.)
                latest = print_page_2_via_pyautogui(driver, serialname=serial)
                if latest:
                    print("Latest downloaded file:", latest)
                    logger.send_log(stage="downloaded file", status="Running")
                else:
                    print("Warning: download/processing failed, latest file not found")
                    latest = None
                    logger.send_log(
                    stage="downloaded file invoice",
                    status="Failed",
                    error_message="download/processing failed, latest file not found"
        )
            finally:
                try:
                    driver.quit()
                except Exception:
                    pass

            # ---------- Part B: DMS login / OCR / upload ----------
            driver_dms, wait_dms = init_driverDMS(url=URLDMS)

            # fetch DMS credentials for warehouse
            key_for_sheet = (serial or "").strip() if serial else (filter_value or "").strip()
            key_for_sheet_up = key_for_sheet.upper()

# normalize (optional) - if sheet values are uppercase in your sheet, use upper()
# key_for_sheet = key_for_sheet.upper()

            warehouse_from_sheet = None
            warehouse_from_sheet = serial_wh_map.get(key_for_sheet_up)
            print("[DEBUG] warehouse_from_sheet =", warehouse_from_sheet, "for key", key_for_sheet)

# decide which warehouse to use (sheet value preferred)
            if warehouse_from_sheet and str(warehouse_from_sheet).strip():
                used_warehouse = str(warehouse_from_sheet).strip()
            else:
                used_warehouse = WarehouseId  # fallback to DB value

# now call existing function that maps warehouse -> username/password
            USERNAMEDMS, PASSWORDDMS = get_userpass_for_warehouse(used_warehouse, cfg_path=CFG_PATH)
            print(f"[DEBUG] Using warehouse {used_warehouse} -> USERNAMEDMS={USERNAMEDMS!r}")



            print(f"[DEBUG] WarehouseId={WarehouseId}, USERNAMEDMS={USERNAMEDMS!r}")

            if not USERNAMEDMS or not PASSWORDDMS:
                err_msg = f"No DMS credentials found for WarehouseId={WarehouseId}"
                print("[WARN]", err_msg)
                if serial_val:
                    try:
                        mark_complete_error_by_serial(serial_val, error_msg=err_msg)
                    except Exception as e_mark:
                        print("Failed to mark error in DB:", e_mark)
                try:
                    driver_dms.quit()
                except Exception:
                    pass
                # write N to sheet since cannot proceed
                if filter_value:
                    safe_write_status(filter_value, "N")
                continue

            # prepare login inputs (may raise)
            username_box, password_box, captcha_box, img_elem = prepare_login_inputs(wait_dms, USERNAMEDMS, PASSWORDDMS)

            attempt = 0
            captcha_fail_count = 0

            # login loop
            while True:
                attempt += 1
                try:
                    wait_dms.until(lambda d: d.execute_script("return arguments[0].naturalWidth > 0;", img_elem))
                except Exception:
                    pass
                src_ref = img_elem.get_attribute("src")

                # OCR sub-loop (read captcha)
                while True:
                    logger.send_log(stage="Login DMS", status="Running")
                    img_elem.screenshot(str(IMG_PATH))
                    preproc = preprocess_and_save(IMG_PATH, PREPROC_PATH)
                    read_file = str(preproc) if preproc else str(IMG_PATH)

                    tmp = ""
                    avg_conf = 0.0
                    try:
                        raw_text = ocr_document(str(read_file))
                        tmp = clean_token(raw_text or "")
                        avg_conf = 1.0 if tmp else 0.0
                    except Exception as e_ocr:
                        print(f"[OCR] typhoon_ocr error: {e_ocr}")
                        tmp = ""
                        avg_conf = 0.0

                    print(f"[Attempt {attempt}] read='{tmp}' len={len(tmp)} conf={avg_conf:.3f}")

                    if len(tmp) == REQUIRED_LEN and avg_conf >= MIN_CONF:
                        code = tmp
                        break

                    try:
                        img_elem.click()
                        wait_dms.until(lambda d: img_elem.get_attribute("src") != src_ref)
                    except Exception:
                        try:
                            img_elem = wait_dms.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "img.verification-code")))
                            wait_dms.until(lambda d: img_elem.get_attribute("src") != src_ref)
                        except Exception:
                            pass
                    src_ref = img_elem.get_attribute("src")
                    time.sleep(0.4)

                if img_elem.get_attribute("src") != src_ref:
                    print("⚠️ captcha changed while preparing -> retry whole attempt")
                    continue

                try:
                    captcha_box.clear()
                    captcha_box.send_keys(code)
                    password_box.send_keys(Keys.ENTER)
                    print(f"➡️ Sent captcha '{code}' and Enter")
                except Exception as e_send:
                    print("Error sending captcha/enter:", e_send)
                    try:
                        password_box.send_keys(Keys.ENTER)
                    except Exception:
                        pass

                ok = wait_login_result(driver_dms, timeout=12)
                if ok:
                    print("✅ LOGIN successful")
                    captcha_fail_count = 0
                    time.sleep(1.8)
                    logger.send_log(
                    stage="LOGIN DMS",
                    status="Success"
                    )
                    break
                else:
                    print("❌ LOGIN failed -> refresh captcha")
                    captcha_fail_count += 1
                    if captcha_fail_count >= 3:
                        print("♻️ CAPTCHA failed 3 times -> restart browser")
                        try:
                            driver_dms.quit()
                        except Exception:
                            pass
                        time.sleep(1.0)
                        driver_dms, wait_dms = init_driverDMS(url=URLDMS)
                        username_box, password_box, captcha_box, img_elem = prepare_login_inputs(wait_dms, USERNAMEDMS, PASSWORDDMS)
                        captcha_fail_count = 0
                        attempt = 0
                        continue

                    try:
                        img_elem = wait_dms.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "img.verification-code")))
                        img_elem.click()
                        src_ref = img_elem.get_attribute("src")
                    except Exception:
                        pass
                    time.sleep(0.6)

            # after login: continue workflow
            time.sleep(10)
            change_lang_and_open_page(driver_dms, wait_dms)
            time.sleep(1.2)

            # ========= HERE: click menu sequence first, THEN fill serial input =========
            ok_seq = False
            try:
                ok_seq = click_sales_menu_sequence(driver_dms, pause=0.6)
                print("[MENU] click_sales_menu_sequence ->", ok_seq)
            except Exception as e_seq:
                print("[MENU] click_sales_menu_sequence exception:", e_seq)
                ok_seq = False

            time.sleep(0.6)

            # Fill serial input after menu sequence (required)
            ok_serial = False
            try:
                ok_serial = fill_serial_input(driver_dms, serial, timeout=6.0, pause_after=0.4)
                print("[SERIAL] fill_serial_input ->", ok_serial)
                time.sleep(3)
                
            except Exception as e_fill:
                print("[SERIAL] fill_serial_input exception:", e_fill)
                ok_serial = False

            # If sequence didn't open necessary submenu, fallback to click_three_buttons once
            # if not ok_seq:
            #     try:
            #         print("[MENU] sequence failed, trying fallback click_three_buttons()")
            #         click_three_buttons(driver_dms)
            #         time.sleep(0.6)
            #     except Exception as e_fallback:
            #         print("[MENU] fallback click_three_buttons exception:", e_fallback)

            # # small pause to let UI settle
            # time.sleep(1.2)

            # continue: fill/upload workflow - use values from df (row)
            


            # ---- REPLACEMENT: unified A + B flows with DB/Sheet updates ----
            last_exc = None
            s_val = serial_val if (serial_val and str(serial_val).strip()) else serial

            ok_a = False
            ok_b = False

            # Attempt A: tabbed flow
            try:
                res_a = fill_textarea_and_submit_and_tab(driver_dms, value=serial)
                if not res_a:
                    raise RuntimeError("fill_textarea_and_submit_and_tab returned False")
                time.sleep(2.2)

                fill_invoice_fields_in_order_first(driver_dms, df, row_idx=run_idx)
                time.sleep(3.2)
                # click_for_save_button(driver_dms)

                if latest:
                    upload_latest_file_strict(driver_dms, file_path=latest)
                    time.sleep(1.5)
                    # try calling save with driver; fallback to no-arg if signature differs
                    try:
                        click_for_save_button_first(driver_dms)
                    except TypeError:
                        click_for_save_button()
                else:
                    raise RuntimeError("No latest file to upload (A)")
                ok_a = True
                print("[FLOW] Attempt A (tabbed) succeeded for", s_val)
            except Exception as e_a:
                last_exc = e_a
                print("[FLOW] Attempt A (tabbed) failed for", s_val, "err:", e_a)

            time.sleep(2.6)

            # Attempt B: plain flow
            try:
                # click_three_buttons(driver_dms)
                res_b = fill_textarea_and_submit(driver_dms, value=serial)
                if not res_b:
                    raise RuntimeError("fill_textarea_and_submit returned False")
                time.sleep(2.2)

                # fill_invoice_fields_in_order(driver_dms, df, row_idx=run_idx)
                # time.sleep(1.2)

                if latest:
                    upload_latest_file_strict(driver_dms, file_path=latest)
                    time.sleep(1.5)
                    click_for_save_button(driver_dms)
                    # try:
                    #     click_for_save_button(driver_dms)
                    #     # click "send/submit" and confirm popup
                    #     time.sleep(1.5)
                    #     click_send_and_confirm(
                    #         driver_dms,
                    #         SEND_BUTTON_XPATH,
                    #         confirm_xpath=CONFIRM_BUTTON_XPATH,
                    #         timeout=6.0,
                    #         retries=2,
                    #         confirm_timeout=6.0,
                    #         confirm_retries=2,
                    #     )
                    #     #กดส่งงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงง
                    # except TypeError:
                    #     click_for_save_button()   
                    #     # click "send/submit" and confirm popup
                    #     time.sleep(1.5)
                    #     click_send_and_confirm(
                    #         driver_dms,
                    #         SEND_BUTTON_XPATH,
                    #         confirm_xpath=CONFIRM_BUTTON_XPATH,
                    #         timeout=6.0,
                    #         retries=2,
                    #         confirm_timeout=6.0,
                    #         confirm_retries=2,
                    #     )
                    #     #กดส่งงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงงง
                else:
                    raise RuntimeError("No latest file to upload (B)")
                ok_b = True
                print("[FLOW] Attempt B (plain) succeeded for", s_val)
            except Exception as e_b:
                last_exc = e_b
                print("[FLOW] Attempt B (plain) failed for", s_val, "err:", e_b)

            # Decide outcome: require BOTH A and B success
            if ok_a and ok_b:
                # try writing sheet 'Y' first
                logger.send_log(
                stage="Attact File ",
                status="Success"
                )
                sheet_ok = False
                try:
                    if filter_value:
                        safe_write_status(filter_value, "Y")
                    sheet_ok = True
                    logger.send_log(
                    stage="Stamp in GoogleSheet ",
                    status="Success"
                    )
                except Exception as e_sheet:
                    print("[SHEET] Failed to write status 'Y' for invoice", filter_value, "err:", e_sheet)
                    sheet_ok = False

                if sheet_ok:
                    try:
                        if s_val:
                            updated = mark_complete_success_by_serial(s_val)
                            print(f"[DB] Marked SUCCESS for serial={s_val}, rows updated={updated}")
                    except Exception as e_db_succ:
                        print("[DB] mark_complete_success_by_serial failed:", e_db_succ)
                        # attempt to revert sheet to N to avoid inconsistent state
                        try:
                            if filter_value:
                                safe_write_status(filter_value, "N")
                        except Exception as e_sheet2:
                            print("[SHEET] Failed to revert sheet to 'N':", e_sheet2)
                        # mark DB error fallback
                        try:
                            if s_val:
                                mark_complete_error_by_serial(s_val, error_msg=str(e_db_succ)[:1000])
                        except Exception as e_db2:
                            print("[DB] fallback mark_complete_error_by_serial failed:", e_db2)
                        print("[FLOW] Treated as failure due to DB update error")
                        continue
                else:
                    # sheet write failed -> mark DB error and continue
                    try:
                        if s_val:
                            mark_complete_error_by_serial(s_val, error_msg="Sheet write Y failed")
                    except Exception as e_db_err2:
                        print("[DB] mark_complete_error_by_serial failed:", e_db_err2)
                    try:
                        if filter_value:
                            safe_write_status(filter_value, "N")
                    except Exception as e_sheet3:
                        print("[SHEET] Failed to write status 'N' after sheet Y failure:", e_sheet3)
                    continue

            else:
                # one or both flows failed -> mark error & write N
                try:
                    if s_val:
                        mark_complete_error_by_serial(s_val, error_msg=str(last_exc)[:1000])
                        print(f"[DB] Marked ERROR for serial={s_val}")
                except Exception as e_db_err:
                    print("[DB] mark_complete_error_by_serial failed:", e_db_err)
                try:
                    if filter_value:
                        safe_write_status(filter_value, "N")
                except Exception as e_sheet_err:
                    print("[SHEET] Failed to write status 'N' for invoice", filter_value, "err:", e_sheet_err)
                continue
            # ---- END replacement ----
            # ---- attach missing except/finally for per-invoice try ----
        except Exception as e_outer:
            # unexpected outer error for this invoice - mark N
            err_text = str(e_outer)[:1000]
            print("Unhandled exception during process run:", err_text)
            try:
                if serial_val:
                    mark_complete_error_by_serial(serial_val, error_msg=err_text)
            except Exception as e_db2:
                print("DB update (error) failed:", e_db2)
            try:
                if filter_value:
                    safe_write_status(filter_value, "N")
            except Exception as e_sheet_outer:
                print("[SHEET] Failed to write status 'N' in outer except:", e_sheet_outer)
            # proceed to next invoice
            continue
        finally:
            # ensure DMS driver closed if exists
            try:
                if driver_dms:
                    driver_dms.quit()
            except Exception:
                pass
