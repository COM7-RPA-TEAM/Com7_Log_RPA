# -*- coding: utf-8 -*-
"""
เทสของ API รับ log (main.py)

เน้นสัญญาที่ระบบอื่นพึ่งพาอยู่ — ถ้าเทสพวกนี้แดง แปลว่ามีบอทที่ใช้งานอยู่จะพัง
ทุกเทสใช้ Firebase ปลอม (ดู conftest.py) ไม่แตะข้อมูล production
"""
import re

ENDPOINT = "/api/v1/bot-log"
DT_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")


def test_root_health(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json() == {"message": "RPA Logging API is Running!"}


def test_minimal_payload_ok(client, refs):
    """ส่งแค่ bot_name + status ต้องผ่าน — เป็นรูปแบบที่ README บอกไว้ว่าใช้ได้"""
    r = client.post(ENDPOINT, json={"bot_name": "Bot_A", "status": "Running"})
    assert r.status_code == 200
    body = r.json()
    assert body["bot"] == "Bot_A"
    assert DT_PATTERN.match(body["time"]), f"รูปแบบเวลาไม่ถูก: {body['time']}"


def test_writes_to_both_live_and_history(client, refs):
    """ทุก log ต้องลง 2 ที่: live (เขียนทับ) + history (push ใหม่)"""
    client.post(ENDPOINT, json={
        "bot_name": "Bot_B",
        "status": "Failed",
        "stage": "3 - Submit",
        "error_message": "Element not found",
        "status_datetime": "2026-09-08 10:20:30",
    })

    assert "rpa_live_status/Bot_B" in refs, "ไม่ได้เขียน live status"
    assert "rpa_history_logs" in refs, "ไม่ได้เขียน history"

    live_payload = refs["rpa_live_status/Bot_B"].update.call_args[0][0]
    assert live_payload == {
        "status": "Failed",
        "stage": "3 - Submit",
        "error_message": "Element not found",
        "status_datetime": "2026-09-08 10:20:30",
    }
    # live ต้องใช้ update (เขียนทับ key เดิม) ไม่ใช่ push
    refs["rpa_live_status/Bot_B"].push.assert_not_called()

    hist_payload = refs["rpa_history_logs"].push.call_args[0][0]
    assert hist_payload["bot_name"] == "Bot_B"
    assert hist_payload["status"] == "Failed"
    assert hist_payload["status_datetime"] == "2026-09-08 10:20:30"


def test_client_timestamp_is_respected(client, refs):
    """ถ้าระบบที่ยิงเข้ามาส่งเวลามาเอง ต้องใช้ค่านั้น ห้ามเขียนทับ"""
    sent = "2026-01-02 03:04:05"
    r = client.post(ENDPOINT, json={"bot_name": "Bot_C", "status": "Success", "status_datetime": sent})
    assert r.json()["time"] == sent
    assert refs["rpa_live_status/Bot_C"].update.call_args[0][0]["status_datetime"] == sent


def test_server_stamps_time_when_missing(client, refs):
    """ไม่ส่งเวลามา -> server เติมให้ (เวลาไทย) ทั้งใน live และ history"""
    r = client.post(ENDPOINT, json={"bot_name": "Bot_D", "status": "Success"})
    stamped = r.json()["time"]
    assert DT_PATTERN.match(stamped)
    assert refs["rpa_live_status/Bot_D"].update.call_args[0][0]["status_datetime"] == stamped
    assert refs["rpa_history_logs"].push.call_args[0][0]["status_datetime"] == stamped


def test_null_timestamp_is_treated_as_missing(client, refs):
    """ส่ง status_datetime: null มา ต้องไม่พัง — server เติมเวลาให้แทน"""
    r = client.post(ENDPOINT, json={"bot_name": "Bot_E", "status": "Running", "status_datetime": None})
    assert r.status_code == 200
    assert DT_PATTERN.match(r.json()["time"])


def test_optional_fields_default_to_empty_string(client, refs):
    """ไม่ส่ง stage / error_message -> เป็น string ว่าง ไม่ใช่ None (Dashboard อ่านเป็น string)"""
    client.post(ENDPOINT, json={"bot_name": "Bot_F", "status": "Running"})
    payload = refs["rpa_live_status/Bot_F"].update.call_args[0][0]
    assert payload["stage"] == ""
    assert payload["error_message"] == ""


def test_thai_and_spaced_bot_name(client, refs):
    """ชื่อบอทที่ใช้จริงมีทั้งเว้นวรรค — ต้องเขียนลง path ตามชื่อนั้นตรงๆ"""
    client.post(ENDPOINT, json={"bot_name": "PV TO TFF ITOS", "status": "Success"})
    assert "rpa_live_status/PV TO TFF ITOS" in refs


def test_missing_status_is_rejected_without_writing(client, refs):
    """ขาด field บังคับ -> 422 และต้องไม่แตะ Firebase เลย"""
    r = client.post(ENDPOINT, json={"bot_name": "Bot_G"})
    assert r.status_code == 422
    assert refs == {}, "validation ไม่ผ่านแต่ยังเขียน DB"


def test_missing_bot_name_is_rejected_without_writing(client, refs):
    r = client.post(ENDPOINT, json={"status": "Running"})
    assert r.status_code == 422
    assert refs == {}


def test_empty_body_reports_both_missing_fields(client, refs):
    r = client.post(ENDPOINT, json={})
    assert r.status_code == 422
    missing = {tuple(d["loc"]) for d in r.json()["detail"]}
    assert ("body", "bot_name") in missing
    assert ("body", "status") in missing
    assert refs == {}
