# --- GetdataFromGoogleSheet.py (เพิ่ม/แทน) ---
from typing import Dict, List, Tuple, Set, Callable, Optional
import os

# ถ้ามีตัวแปร SA_JSON / SPREADSHEET_ID อยู่แล้ว ให้ใช้ของคุณแทนค่าตัวอย่างด้านล่าง
SA_JSON = os.environ.get("SA_JSON_PATH", "invoice-dms-attach-and-post-2ea3e8ae219c.json")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "1Kr_SUUribnt-sjkdb7eYe4S_vNBW4OjM_-Ubhgd-Ox0")

# หากต้องการอ่านสดจาก Google Sheet ต้องติดตั้ง gspread / google-auth
try:
    from google.oauth2.service_account import Credentials
    import gspread
    GOOGLE_AVAILABLE = True
except Exception:
    GOOGLE_AVAILABLE = False

SCOPES_RW = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def _get_gspread_client(sa_json_path: str, scopes: list | None = None):
    """
    Return a gspread client using provided scopes (default: read+write).
    """
    if not GOOGLE_AVAILABLE:
        raise RuntimeError("gspread/google-auth not available")
    used_scopes = scopes if scopes else SCOPES_RW
    creds = Credentials.from_service_account_file(sa_json_path, scopes=used_scopes)
    return gspread.authorize(creds)

def read_invoice_ids_from_sheet(sa_json_path: str, spreadsheet_id: str,
                                sheet_name: Optional[str] = None,
                                invoice_col_index: int = 1) -> List[str]:
    """
    อ่าน Invoice IDs จากคอลัมน์ invoice_col_index (1 = A) เริ่มจากแถวที่ 2
    คืน list ของ id (unique, preserve order)
    """
    if not GOOGLE_AVAILABLE:
        raise RuntimeError("Google libs not installed/available")
    client = _get_gspread_client(sa_json_path)
    sh = client.open_by_key(spreadsheet_id)
    ws = sh.worksheet(sheet_name) if sheet_name else sh.get_worksheet(0)
    rows = ws.get_all_values()
    if not rows or len(rows) < 2:
        return []
        
    ids = []
    
    for r in rows[1:]:
        v = ""
        if len(r) >= invoice_col_index:
            v = str(r[invoice_col_index - 1]).strip()
        if v:
            ids.append(v)
    return list(dict.fromkeys(ids))

def get_db_invoice_set_via_fetch_df(fetcher: Optional[Callable[[], List[str]]] = None) -> Set[str]:
    """
    คืน set ของ Invoice IDs จาก DB
    - ถ้ามี fetcher ให้เรียก fetcher() ซึ่งต้องคืน list of ids
    - ถ้าไม่มี จะพยายาม import fetch_df และ SQL จาก Get_Value_Form_DataBase.py แล้วดึง
    """
    if fetcher:
        try:
            return set(str(x).strip() for x in fetcher() if x is not None and str(x).strip())
        except Exception as e:
            print("fetcher error:", e)
            return set()
    try:
        # ใช้ fetch_df(SQL) ที่มีในโปรเจคของคุณ (ปรับได้ถ้าต้องส่ง conn params)
        from Get_Value_Form_DataBase import fetch_df, SQL  # ต้องมีไฟล์นี้ใน path
    except Exception as e:
        print("Cannot import fetch_df/SQL:", e)
        return set()
    try:
        df = fetch_df(SQL)
    except Exception as e:
        print("fetch_df raised:", e)
        return set()
    if df is None or df.empty:
        return set()
    # ลองหาชื่อคอลัมน์ที่เป็นไปได้ของ InvoiceId
    for col in ("InvoiceId","InvoiceID","invoice_id","invoiceid","INVOICE_ID"):
        if col in df.columns:
            return set(str(x).strip() for x in df[col].astype(str).tolist() if str(x).strip())
    # fallback: ถ้ามีคอลัมน์เดียว ให้ใช้คอลัมน์นั้น
    if df.shape[1] == 1:
        return set(str(x).strip() for x in df.iloc[:,0].astype(str).tolist() if str(x).strip())
    print("No invoice-id column found in DB result. Columns:", df.columns.tolist())
    return set()

# Replace the existing get_matching_invoice_set(...) with this implementation

def get_matching_invoice_set(sa_json_path,
                             spreadsheet_id,
                             sheet_name: str | None = None,
                             invoice_col_index: int = 1,
                             fetcher=None):
    """
    Read invoice IDs from Google Sheet (column invoice_col_index, 1-based) and call `fetcher()` to get DB invoice IDs.
    Returns a set of normalized matching invoice IDs (uppercase, stripped).
    - sa_json_path: path to service-account JSON
    - spreadsheet_id: Google Sheet ID (the long id in URL)
    - sheet_name: optional sheet name (None -> first sheet)
    - invoice_col_index: 1-based column index where InvoiceId lives (1 = A)
    - fetcher: callable that returns a list of invoice id strings from DB
    """
    from google.oauth2.service_account import Credentials
    import gspread

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]

    # 1) Read sheet values
    sheet_ids = []
    try:
        creds = Credentials.from_service_account_file(sa_json_path, scopes=SCOPES)
        client = gspread.authorize(creds)
        sh = client.open_by_key(spreadsheet_id)
        ws = sh.worksheet(sheet_name) if sheet_name else sh.get_worksheet(0)
        rows = ws.get_all_values()  # list of rows (each row is list of cells)
        # if header exists, we still read all rows but skip empties
        col_idx = max(0, invoice_col_index - 1)
        for r in rows:
            if len(r) > col_idx:
                v = str(r[col_idx]).strip()
                if v:
                    sheet_ids.append(v)
    except Exception as e:
        print("[ERROR] reading Google Sheet:", e)
        sheet_ids = []

    # 2) Call fetcher to get DB list
    db_ids = []
    if callable(fetcher):
        try:
            db_ids = fetcher()
            if db_ids is None:
                db_ids = []
        except Exception as e:
            print("[ERROR] fetcher() raised exception:", e)
            db_ids = []
    else:
        print("[WARN] No fetcher provided or fetcher not callable. db_ids will be empty.")

    # 3) Normalize and intersect
    def norm(s):
        if s is None:
            return ""
        return str(s).strip().upper()

    set_sheet = {norm(x) for x in sheet_ids if norm(x)}
    set_db = {norm(x) for x in db_ids if norm(x)}
    matched = set_sheet & set_db

    # 4) Informative prints (no invalid print kwargs)
    print(f"[INFO] sheet unique ids: {len(set_sheet)}, db unique ids: {len(set_db)}, matched: {len(matched)}")
    if len(matched) > 0:
        # show a small sample
        sample = list(matched)[:50]
        print(f"[INFO] sample matched ({len(sample)}): {sample}")

    return matched


def get_matching_rows_from_sheet(sa_json_path: str, spreadsheet_id: str,
                                 sheet_name: Optional[str] = None,
                                 invoice_col_index: int = 1,
                                 fetcher: Optional[Callable[[], List[str]]] = None) -> List[Tuple[int, str]]:
    """
    คืน list of (sheet_row_number, invoice_id) ของแถวที่ match
    sheet_row_number เป็น 1-indexed (header = row 1)
    """
    matched = get_matching_invoice_set(sa_json_path, spreadsheet_id, sheet_name, invoice_col_index, fetcher=fetcher)
    if not matched:
        return []
    if not GOOGLE_AVAILABLE:
        # ถ้าไม่มี google lib ให้ใช้ env MOCK_SHEET_ROWS = "2:INV1,3:INV2,..."
        rows_env = os.environ.get("MOCK_SHEET_ROWS")
        if not rows_env:
            return []
        out = []
        for item in rows_env.split(","):
            if ":" in item:
                r, inv = item.split(":",1)
                try:
                    rn = int(r)
                except Exception:
                    continue
                if inv in matched:
                    out.append((rn, inv))
        return out
    client = _get_gspread_client(sa_json_path)
    sh = client.open_by_key(spreadsheet_id)
    ws = sh.worksheet(sheet_name) if sheet_name else sh.get_worksheet(0)
    rows = ws.get_all_values()
    out = []
    for idx, r in enumerate(rows[1:], start=2):
        val = ""
        if len(r) >= invoice_col_index:
            val = str(r[invoice_col_index-1]).strip()
        if val and val in matched:
            out.append((idx, val))
    return out

# (Optional) helper to write status back - only add if you also want write-back later
def write_status_back_to_sheet_by_row(sa_json_path: str,
                                      spreadsheet_id: str,
                                      sheet_name: Optional[str],
                                      status_map: Dict[int, str],
                                      status_col_index: int = 5) -> int:
    """
    อัปเดตสถานะตาม row number (1-based)
    status_map: dict mapping sheet_row_number (1-based) -> status string ('Y' or 'N')
    status_col_index: column index (1-based) ของคอลัมน์ Flag (default 5)
    คืนค่า: จำนวนแถวที่ถูกอัปเดต
    """
    if not GOOGLE_AVAILABLE:
        raise RuntimeError("gspread not available")
    client = _get_gspread_client(sa_json_path)
    sh = client.open_by_key(spreadsheet_id)
    ws = sh.worksheet(sheet_name) if sheet_name else sh.get_worksheet(0)

    data = []
    for rownum, status in status_map.items():
        if status is None:
            continue
        s = str(status).strip().upper()
        if s not in ("Y", "N"):
            # ถ้าอยากอนุญาตสถานะอื่น ให้ปรับที่นี่
            continue
        a1 = gspread.utils.rowcol_to_a1(rownum, status_col_index)
        rng = f"{ws.title}!{a1}"
        data.append({"range": rng, "values": [[s]]})

    if not data:
        return 0

    body = {"value_input_option": "USER_ENTERED", "data": data}
    ws.spreadsheet.values_batch_update(body)
    return len(data)


def write_status_back_to_sheet_by_invoice(sa_json_path: str,
                                          spreadsheet_id: str,
                                          sheet_name: Optional[str],
                                          invoice_status_map: Dict[str, str],
                                          invoice_col_index: int = 1,
                                          status_col_index: int = 5) -> int:
    """
    อัปเดตสถานะโดยให้ส่ง mapping ของ invoice_id -> status ('Y'|'N')
    - จะค้นหา row ของแต่ละ invoice ในคอลัมน์ invoice_col_index (1-based)
    - เขียนสถานะลงคอลัมน์ status_col_index (1-based)
    คืนค่า: จำนวนแถวที่ถูกอัปเดต
    """
    if not GOOGLE_AVAILABLE:
        raise RuntimeError("gspread not available")
    client = _get_gspread_client(sa_json_path, scopes=SCOPES_RW)
    sh = client.open_by_key(spreadsheet_id)
    ws = sh.worksheet(sheet_name) if sheet_name else sh.get_worksheet(0)

    # อ่านทั้ง sheet เพื่อ map invoice -> row
    rows = ws.get_all_values()  # includes header row
    invoice_to_row = {}
    col_idx = max(0, invoice_col_index - 1)
    for idx, r in enumerate(rows[1:], start=2):  # start=2 เพื่อข้าม header
        if len(r) > col_idx:
            val = str(r[col_idx]).strip()
            if val:
                invoice_to_row[val.upper()] = idx

    data = []
    for inv, status in invoice_status_map.items():
        if status is None:
            continue
        s = str(status).strip().upper()
        if s not in ("Y", "N"):
            continue
        rownum = invoice_to_row.get(str(inv).strip().upper())
        if not rownum:
            # ถ้าไม่พบ invoice ใน sheet จะข้าม
            continue
        a1 = gspread.utils.rowcol_to_a1(rownum, status_col_index)
        rng = f"{ws.title}!{a1}"
        data.append({"range": rng, "values": [[s]]})

    if not data:
        return 0

    body = {"value_input_option": "USER_ENTERED", "data": data}
    ws.spreadsheet.values_batch_update(body)
    return len(data)




def get_dms_credentials_from_sheet(sa_json_path: str,
                                   sheet_id: str,
                                   sheet_name: str,
                                   match_value,
                                   key_col_index: int = 1,
                                   creds_col_index: int = 4):
    """
    Lookup DMS username/password from Google Sheet.
    - match_value: the key to match (we'll use serial first; pass serial or invoice id)
    - key_col_index: column index where the key (invoice/serial) is stored (1-based)
    - creds_col_index: column index where credential string is stored (1-based) - you said column D -> 4
    Returns (username, password) or (None, None) if not found/parse fail.
    Credential cell is parsed by splitting on [:,|,;,] — if only username present returns (username,"").
    """
    # require _get_gspread_client() to exist in this file (your existing helper)
    client = _get_gspread_client(sa_json_path)  # uses default RW scopes in your patched file
    sh = client.open_by_key(sheet_id)
    ws = sh.worksheet(sheet_name)

    # read the key column (to find matching row)
    col_values = ws.col_values(key_col_index)  # 1-based
    target = str(match_value).strip() if match_value is not None else ""
    if not target:
        return None, None

    # find first row index matching target exactly (strip both)
    row_idx = None
    for i, v in enumerate(col_values, start=1):
        if str(v).strip() == target:
            row_idx = i
            break

    if row_idx is None:
        # not found
        return None, None

    # read credentials cell
    try:
        creds_cell = ws.cell(row_idx, creds_col_index).value or ""
    except Exception:
        creds_cell = ""

    creds = str(creds_cell).strip()
    if not creds:
        return None, None

    # parse by common separators
    for sep in [":", ",", "|", ";"]:
        if sep in creds:
            parts = [p.strip() for p in creds.split(sep, 1)]
            username = parts[0]
            password = parts[1] if len(parts) > 1 else ""
            return username, password

    # if no separator, return username only
    return creds, ""


def get_value_from_sheet_by_key(sa_json_path: str,
                                sheet_id: str,
                                sheet_name: str,
                                match_value,
                                key_col_index: int = 3,
                                return_col_index: int = 4):
    """
    หาแถวที่มีค่า match_value ในคอลัมน์ key_col_index (1-based)
    แล้วคืนค่าของเซลล์ที่อยู่ในคอลัมน์ return_col_index ของแถวนั้น
    ตัวอย่าง: match_value = serial, key_col_index=3 (C), return_col_index=4 (D -> Warehouse)
    คืนค่าเป็น string หรือ None ถ้าไม่พบ
    """
    client = _get_gspread_client(sa_json_path)  # ใช้ client ที่มี scope RW แล้ว (ตามแพตช์ก่อนหน้า)
    sh = client.open_by_key(sheet_id)
    ws = sh.worksheet(sheet_name)

    # อ่านทั้งคอลัมน์ของ key เพื่อหา row
    col_values = ws.col_values(key_col_index)
    target = str(match_value).strip() if match_value is not None else ""
    if not target:
        return None

    row_idx = None
    for i, v in enumerate(col_values, start=1):
        if str(v).strip() == target:
            row_idx = i
            break

    if row_idx is None:
        return None

    try:
        return_val = ws.cell(row_idx, return_col_index).value
        return return_val if return_val is not None else None
    except Exception:
        return None
    


def get_sheet_invoice_flag_map(sa_json_path, spreadsheet_id, sheet_name=None, invoice_col_index=1, flag_col_index=5):
    from google.oauth2.service_account import Credentials
    import gspread

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_file(sa_json_path, scopes=scopes)
    client = gspread.authorize(creds)
    sh = client.open_by_key(spreadsheet_id)
    ws = sh.worksheet(sheet_name) if sheet_name else sh.get_worksheet(0)
    rows = ws.get_all_values()

    inv_idx = invoice_col_index - 1
    flag_idx = flag_col_index - 1

    out = {}
    for r in rows[1:]:  # ข้าม header
        inv = str(r[inv_idx]).strip().upper() if len(r) > inv_idx else ""
        flag = str(r[flag_idx]).strip() if len(r) > flag_idx else ""
        if inv:
            out[inv] = flag
    return out



# if __name__ == "__main__":
    




