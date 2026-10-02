from __future__ import annotations

from typing import Any

import requests

from ..config import Settings
from ..models import CollectResult
from ..utils import make_session


class Source:
    """แหล่งข้อมูลหนึ่งแหล่ง: fetch_* ดึงข้อมูลดิบ, parse_* แปลงเป็น Observation/Report

    แยก fetch กับ parse ออกจากกัน เพื่อให้ทดสอบ parser ด้วย fixture ได้โดยไม่ต้องต่อเน็ต
    และสามารถ re-parse ไฟล์ raw ย้อนหลังได้ถ้าต้นทางเปลี่ยนโครงสร้าง
    """

    name: str = ""
    description: str = ""

    def __init__(self, settings: Settings | None = None, session: requests.Session | None = None) -> None:
        self.settings = settings or Settings()
        self.session = session or make_session(self.settings.user_agent)

    def get_json(self, url: str, **kwargs: Any) -> Any:
        resp = self.session.get(url, timeout=self.settings.timeout, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def get_text(self, url: str, **kwargs: Any) -> str:
        resp = self.session.get(url, timeout=self.settings.timeout, **kwargs)
        resp.raise_for_status()
        if resp.encoding is None or resp.encoding.lower() == "iso-8859-1":
            resp.encoding = resp.apparent_encoding  # เว็บไทยหลายแห่งไม่ส่ง charset มา
        return resp.text

    def collect(self) -> CollectResult:  # pragma: no cover - implemented by subclasses
        raise NotImplementedError
