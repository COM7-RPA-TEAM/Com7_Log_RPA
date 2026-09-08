# -*- coding: utf-8 -*-
"""
ตั้งค่าให้เทสรันได้โดย "ไม่แตะ Firebase จริง" แม้แต่ครั้งเดียว

main.py เชื่อม Firebase ตั้งแต่ตอน import (module level) ถ้าปล่อยไว้เทสจะไป
เขียน production เลย — เลยยัด firebase_admin ปลอมเข้า sys.modules ก่อน import
ทำให้ไม่ต้องติดตั้ง firebase-admin และไม่ต้องมี credential ในเครื่องด้วย
"""
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ให้ import main.py จาก root ของ repo ได้
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ---------- firebase_admin ปลอม ----------
_fake = types.ModuleType("firebase_admin")
# มีค่า truthy = main.py จะข้ามบล็อก initialize_app ไปเลย
_fake._apps = ["fake-app"]
_fake.initialize_app = MagicMock(name="initialize_app")

_credentials = types.ModuleType("firebase_admin.credentials")
_credentials.Certificate = MagicMock(name="Certificate")

_db = types.ModuleType("firebase_admin.db")
_db.reference = MagicMock(name="reference")

_fake.credentials = _credentials
_fake.db = _db

sys.modules["firebase_admin"] = _fake
sys.modules["firebase_admin.credentials"] = _credentials
sys.modules["firebase_admin.db"] = _db

fake_db = _db


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    import main
    return TestClient(main.app)


@pytest.fixture
def refs():
    """
    คืน dict {path: MagicMock} ของทุก db.reference(path) ที่ main.py เรียกในเทสนั้น
    ใช้ตรวจว่าเขียนลง path ไหน ด้วยข้อมูลอะไร
    """
    store = {}

    def _reference(path):
        if path not in store:
            store[path] = MagicMock(name=f"ref:{path}")
        return store[path]

    fake_db.reference.reset_mock(side_effect=True)
    fake_db.reference.side_effect = _reference
    yield store
    fake_db.reference.reset_mock(side_effect=True)
