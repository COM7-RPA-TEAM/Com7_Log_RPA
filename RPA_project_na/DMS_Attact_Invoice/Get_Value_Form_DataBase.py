# Get_Value_Form_DataBase.py
import os
import pyodbc
import pandas as pd
from datetime import datetime as _datetime
from typing import Any
import configparser
from pathlib import Path
from typing import Tuple, Optional, Dict, Any

# --- DB config & SQL ---




def fetch_df(sql,
             driver, server, database,
             uid, pwd, timeout=5):
    
    driver="SQL Server" 
    server="192.168.43.84" 
    database="RPA"
    uid="nene-mis_erp"
    pwd="np.123456"

    if not server or not database:
        raise RuntimeError("Missing DB connection params: server and/or database")

    # ตัวอย่าง conn_str ถูกต้อง: SERVER=...; DATABASE=...
    conn_str = f"DRIVER={driver};SERVER={server};DATABASE={database};UID={uid};PWD={pwd}"
    #conn_str = f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};Trusted_Connection=yes;"

    with pyodbc.connect(conn_str, timeout=timeout) as conn:
        df = pd.read_sql(sql, conn)
    return df

def return_value_Of_data(row_idx: int, col_name: str, df: pd.DataFrame, date_format: str = "%Y-%m-%d") -> Any:
    if row_idx < 0 or row_idx >= len(df):
        return None
    val = df.iloc[row_idx][col_name]
    if pd.isna(val):
        return None
    try:
        if isinstance(val, (pd.Timestamp, _datetime)):
            return pd.to_datetime(val).strftime(date_format)
    except Exception:
        pass
    try:
        if hasattr(val, "item"):
            return val.item()
    except Exception:
        pass
    return val



SQL = f""" 
WITH cte AS (
  SELECT *,
         ROW_NUMBER() OVER (PARTITION BY InvoiceId ORDER BY InvoiceDate DESC, SalesId DESC) AS rn
  FROM [RPA].[dbo].GI_SALES_INVOICE_LINES
  WHERE invoiceDate = CAST(DATEADD(DAY,-13,GETDATE()) AS date)
    AND serial IS NOT NULL
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
  CompleteFlag,
  CompleteDatetime
FROM cte
WHERE rn = 1;

  
"""


def mark_complete_success_by_serial(serial_value,
                                     key_column: str = "serial",   # default เป็น serial
                                     driver: str = "SQL Server",
                                     server: str = "192.168.43.84",
                                     database: str = "RPA",
                                     uid: str = "nene-mis_erp",
                                     pwd: str = "np.123456",
                                     timeout: int = 5) -> int:
    """
    อัปเดต CompleteFlag='Y' และ CompleteDatetime=GETDATE() โดยใช้ WHERE serial = serial_value
    คืนค่า: จำนวนแถวที่ถูกอัปเดต (int)
    """
    if not serial_value:
        return 0

    conn_str = f"DRIVER={driver};SERVER={server};DATABASE={database};UID={uid};PWD={pwd}"
    sql = f"""
    UPDATE [RPA].[dbo].[GI_SALES_INVOICE_LINES_UPLOADED]
    SET CompleteFlag = '1',
        CompleteDatetime = GETDATE()
    WHERE {key_column} = ? AND (CompleteFlag IS NULL OR CompleteFlag <> '1')
    """
    conn = None
    try:
        conn = pyodbc.connect(conn_str, timeout=timeout)
        cur = conn.cursor()
        cur.execute(sql, (serial_value,))
        conn.commit()
        return cur.rowcount
    except Exception as e:
        print("mark_complete_success_by_serial failed:", e)
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        raise
    finally:
        if conn:
            conn.close()


def mark_complete_error_by_serial(serial_value,
                                  error_msg: str = None,
                                  key_column: str = "serial",   # default เป็น serial
                                  error_column: str = "ErrorMessage",
                                  driver: str = "SQL Server",
                                  server: str = "192.168.43.84",
                                  database: str = "RPA",
                                  uid: str = "nene-mis_erp",
                                  pwd: str = "np.123456",
                                  timeout: int = 5) -> int:


    if not serial_value:
        return 0

    conn_str = f"DRIVER={driver};SERVER={server};DATABASE={database};UID={uid};PWD={pwd}"

    if error_msg and error_column:
        sql = f"""
        UPDATE [RPA].[dbo].[GI_SALES_INVOICE_LINES_UPLOADED]
        SET CompleteFlag = '0',
            CompleteDatetime = GETDATE(),
            {error_column} = ?
        WHERE {key_column} = ?
        """
        params = (error_msg, serial_value)
    else:
        sql = f"""
        UPDATE [RPA].[dbo].[GI_SALES_INVOICE_LINES_UPLOADED]
        SET CompleteFlag = '0',
            CompleteDatetime = GETDATE()
        WHERE {key_column} = ?
        """
        params = (serial_value,)

    conn = None
    try:
        conn = pyodbc.connect(conn_str, timeout=timeout)
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()
        return cur.rowcount
    except Exception as e:
        print("mark_complete_error_by_serial failed:", e)
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        raise
    finally:
        if conn:
            conn.close()

def get_userpass_for_warehouse(warehouse_id: Any,
                               cfg_path: Path = None
                              ) -> Tuple[Optional[str], Optional[str]]:
    """
    Improved: read [WAREHOUSES] from INI (handles BOM, strips keys/values),
    prints debug info and returns (username, password) or (None,None) if not found.
    """
    # normalize input
    if warehouse_id is None:
        return None, None
    key = str(warehouse_id).strip()

    cfg = configparser.ConfigParser()
    cfg.optionxform = str  # keep key case as-is
    # read with utf-8-sig to tolerate BOM
    try:
        cfg.read(str(cfg_path), encoding="utf-8-sig")
    except Exception as e:
        print("Failed to read config:", e)
        return None, None

    if "WAREHOUSES" not in cfg:
        print("DEBUG: [WAREHOUSES] section not found in", cfg_path)
        return None, None

    # build a normalized dict of keys -> values (strip spaces and invisible chars)
    raw_items = dict(cfg["WAREHOUSES"].items())
    normalized = {}
    for k, v in raw_items.items():
        nk = k.strip().replace("\u00A0", "")  # also remove non-breaking spaces if any
        nv = v.strip()
        normalized[nk] = nv

    # debug: print what we actually read (helps find mismatches)
    print("DEBUG: WAREHOUSES keys read:", list(normalized.keys()))

    # direct lookup
    if key in normalized:
        val = normalized[key]
        parts = val.split(":", 1)
        username = parts[0].strip() if len(parts) >= 1 and parts[0].strip() != "" else None
        password = parts[1].strip() if len(parts) == 2 and parts[1].strip() != "" else None
        return username, password

    # try alternative matching: maybe keys are numbers without leading zeros etc.
    for nk, nv in normalized.items():
        if nk == key or nk.replace(" ", "") == key or nk == key.strip():
            parts = nv.split(":", 1)
            username = parts[0].strip() if len(parts) >= 1 and parts[0].strip() != "" else None
            password = parts[1].strip() if len(parts) == 2 and parts[1].strip() != "" else None
            return username, password
        # try numeric equality (if both convertable)
        try:
            if int(nk) == int(key):
                parts = nv.split(":", 1)
                username = parts[0].strip() if len(parts) >= 1 and parts[0].strip() != "" else None
                password = parts[1].strip() if len(parts) == 2 and parts[1].strip() != "" else None
                return username, password
        except Exception:
            pass

    # nothing matched
    print(f"DEBUG: warehouse_id '{key}' not found in [WAREHOUSES] (checked keys above).")
    return None, None



# if __name__ == "__main__":
    # ดึงข้อมูลจาก DB (ลองจับ exception ด้วย)
    # try:
    #     df = fetch_df(SQL,
    #                   driver="SQL Server",
    #                   server="192.168.43.84",
    #                   database="RPA",
    #                   uid="nene-mis_erp",
    #                   pwd="np.123456",
    #                   timeout=5)
    # except Exception as e:
    #     print("fetch_df failed:", e)
    #     raise

    # print("rows:", len(df))
    # # debug: แสดงแถวตัวอย่าง
    # if len(df) > 0:
    #     print(df.head())

    # # หา WarehouseId จากแถวแรก (debug)
    # warehouse_id = return_value_Of_data(0, "WarehouseId", df)
    # print("warehouse_id (repr):", repr(warehouse_id))

    # # วิธีที่แนะนำ: สร้าง Path แล้วส่งเข้า ฟังก์ชัน
    # cfg_path = Path(r"C:\Users\comseven\Desktop\back-up_EV7\CONFIG_DataBase.ini")
    # if not cfg_path.exists():
    #     print("CONFIG file not found:", cfg_path)
    # else:
    #     username, password = get_userpass_for_warehouse(warehouse_id, cfg_path=cfg_path)
    #     print("USERNAMEDMS =", username)
    #     print("PASSWORDDMS =", password)
    # print(df.head())
    # print("rows:", len(df))
    # print(df)
    # print(return_value_Of_data(0, "InvoiceId", df))
    # print(return_value_Of_data(0, "WarehouseId", df))


