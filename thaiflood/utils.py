"""ฟังก์ชันช่วย: HTTP, เวลา, ตัวเลข, HTML"""

from __future__ import annotations

import re
import time
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

TH_TZ = timezone(timedelta(hours=7))

THAI_MONTHS = {
    "ม.ค.": 1, "มกราคม": 1, "ก.พ.": 2, "กุมภาพันธ์": 2, "มี.ค.": 3, "มีนาคม": 3,
    "เม.ย.": 4, "เมษายน": 4, "พ.ค.": 5, "พฤษภาคม": 5, "มิ.ย.": 6, "มิถุนายน": 6,
    "ก.ค.": 7, "กรกฎาคม": 7, "ส.ค.": 8, "สิงหาคม": 8, "ก.ย.": 9, "กันยายน": 9,
    "ต.ค.": 10, "ตุลาคม": 10, "พ.ย.": 11, "พฤศจิกายน": 11, "ธ.ค.": 12, "ธันวาคม": 12,
}
_THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")


def make_session(user_agent: str, retries: int = 3) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers["User-Agent"] = user_agent
    return session


def now_th() -> datetime:
    return datetime.now(TH_TZ)


def to_iso(value: Any) -> str | None:
    """แปลงเวลาหลายรูปแบบเป็น ISO-8601 พร้อม timezone (ไม่มี tz ถือเป็นเวลาไทย)"""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        ts = value / 1000 if value > 1e11 else value
        return datetime.fromtimestamp(ts, TH_TZ).isoformat()
    text = str(value).strip().translate(_THAI_DIGITS)
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            return datetime.strptime(text.replace("Z", "+0000"), fmt).isoformat()
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            dt = datetime.strptime(text, fmt)
            if dt.year > 2400:  # พ.ศ.
                dt = dt.replace(year=dt.year - 543)
            return dt.replace(tzinfo=TH_TZ).isoformat()
        except ValueError:
            pass
    thai = parse_thai_date(text)
    return thai.isoformat() if thai else text


def parse_thai_date(text: str) -> datetime | None:
    """เช่น '15 ต.ค. 2567', 'วันที่ 3 ตุลาคม 2567 เวลา 08.00 น.'"""
    text = text.translate(_THAI_DIGITS)
    m = re.search(r"(\d{1,2})\s*(" + "|".join(re.escape(k) for k in THAI_MONTHS) + r")\s*(\d{2,4})", text)
    if not m:
        return None
    day, month, year = int(m.group(1)), THAI_MONTHS[m.group(2)], int(m.group(3))
    if year < 100:
        year += 2500
    if year > 2400:
        year -= 543
    hour = minute = 0
    t = re.search(r"(\d{1,2})[.:](\d{2})\s*น", text[m.end():])
    if t:
        hour, minute = int(t.group(1)), int(t.group(2))
    try:
        return datetime(year, month, day, hour, minute, tzinfo=TH_TZ)
    except ValueError:
        return None


def to_float(value: Any) -> float | None:
    if value in (None, "", "-", "N/A"):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).translate(_THAI_DIGITS).replace(",", "").strip()
    try:
        return float(text)
    except ValueError:
        m = re.search(r"-?\d+(?:\.\d+)?", text)
        return float(m.group()) if m else None


def th(value: Any) -> str | None:
    """ชื่อจาก ThaiWater มักมาเป็น {"th": ..., "en": ...}"""
    if isinstance(value, dict):
        return value.get("th") or value.get("en") or next(iter(value.values()), None)
    return value


def dig(obj: Any, *path: str, default: Any = None) -> Any:
    for key in path:
        if not isinstance(obj, dict):
            return default
        obj = obj.get(key)
        if obj is None:
            return default
    return obj


class _LinkTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self.tables: list[list[list[str]]] = []
        self._href: str | None = None
        self._text: list[str] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []
        elif tag == "table":
            self.tables.append([])
        elif tag == "tr" and self.tables:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join("".join(self._text).split())))
            self._href = None
        elif tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None and self.tables:
            if self._row:
                self.tables[-1].append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)
        if self._cell is not None:
            self._cell.append(data)


def parse_html(html: str) -> tuple[list[tuple[str, str]], list[list[list[str]]]]:
    """คืน (links[(href, text)], tables[rows[cells]]) — ไม่ต้องพึ่ง bs4"""
    parser = _LinkTableParser()
    parser.feed(html)
    return parser.links, parser.tables


def polite_sleep(seconds: float = 1.0) -> None:
    time.sleep(seconds)
