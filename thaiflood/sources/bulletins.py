"""แหล่งข้อมูลแบบ "ประกาศ/รายงาน" บนหน้าเว็บ: ปภ. (disaster.go.th) และ สทนช. (onwr.go.th)

ทั้งสองแห่งไม่มี API สาธารณะ จึงอ่านหน้ารายการข่าว คัดลิงก์ที่เกี่ยวกับน้ำท่วม
แล้วเปิดอ่านเนื้อหาแต่ละฉบับเพื่อดึงตัวเลขผลกระทบ/รายชื่อจังหวัด
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

from ..models import CollectResult, Report
from ..provinces import find_provinces
from ..utils import parse_html, parse_thai_date, to_float
from .base import Source

FLOOD_KEYWORDS = ("อุทกภัย", "น้ำท่วม", "น้ำป่า", "น้ำหลาก", "ฝนตกหนัก", "ดินโคลนถล่ม", "ระดับน้ำ", "เตือนภัย", "สถานการณ์น้ำ")

# ตัวเลขผลกระทบในรายงาน ปภ. เช่น "รวม 12 จังหวัด 45 อำเภอ ... 1,234 ครัวเรือน ผู้เสียชีวิต 3 ราย"
_METRIC_PATTERNS = {
    "provinces": r"([\d,]+)\s*จังหวัด",
    "districts": r"([\d,]+)\s*อำเภอ",
    "subdistricts": r"([\d,]+)\s*ตำบล",
    "villages": r"([\d,]+)\s*หมู่บ้าน",
    "households": r"([\d,]+)\s*ครัวเรือน",
    "people": r"([\d,]+)\s*คน(?!ละ)",
    "deaths": r"(?:ผู้)?เสียชีวิต\s*(?:รวม|จำนวน)?\s*([\d,]+)\s*ราย",
    "injured": r"(?:ผู้)?บาดเจ็บ\s*(?:รวม|จำนวน)?\s*([\d,]+)\s*ราย",
    "missing": r"(?:ผู้)?สูญหาย\s*(?:รวม|จำนวน)?\s*([\d,]+)\s*ราย",
}


def html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    for ent, ch in (("&nbsp;", " "), ("&amp;", "&"), ("&quot;", '"'), ("&#39;", "'"), ("&lt;", "<"), ("&gt;", ">")):
        text = text.replace(ent, ch)
    return " ".join(text.split())


def extract_metrics(text: str) -> dict[str, int]:
    text = text.translate(str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789"))
    metrics: dict[str, int] = {}
    for key, pattern in _METRIC_PATTERNS.items():
        m = re.search(pattern, text)
        if m:
            value = to_float(m.group(1))
            if value is not None:
                metrics[key] = int(value)
    return metrics


def find_bulletin_links(html: str, base_url: str, keywords: tuple[str, ...] = FLOOD_KEYWORDS) -> list[tuple[str, str]]:
    links, _ = parse_html(html)
    seen: set[str] = set()
    out = []
    for href, text in links:
        if not href or href.startswith(("#", "javascript:", "mailto:")) or not text:
            continue
        if not any(k in text for k in keywords):
            continue
        url = urljoin(base_url, href)
        if url in seen:
            continue
        seen.add(url)
        out.append((url, text))
    return out


def build_report(source: str, kind: str, url: str, title: str, body_text: str = "") -> Report:
    full = f"{title} {body_text}"
    published = parse_thai_date(full)
    return Report(
        source=source,
        kind=kind,
        title=title,
        url=url,
        published_at=published.isoformat() if published else None,
        summary=body_text[:1000] or None,
        provinces=find_provinces(full),
        metrics=extract_metrics(body_text) if body_text else {},
    )


class _BulletinSource(Source):
    kind = ""
    list_url_attr = ""
    max_items = 10

    def collect(self) -> CollectResult:
        result = CollectResult(self.name)
        list_url = getattr(self.settings, self.list_url_attr)
        try:
            html = self.get_text(list_url)
            result.raw["index.html"] = html
        except Exception as exc:
            result.errors.append(f"index: {exc}")
            return result
        for url, title in find_bulletin_links(html, list_url)[: self.max_items]:
            body = ""
            if not url.lower().endswith(".pdf"):  # PDF เก็บเป็นลิงก์ ไม่แกะเนื้อหา
                try:
                    body = html_to_text(self.get_text(url))
                except Exception as exc:
                    result.errors.append(f"{url}: {exc}")
            result.reports.append(build_report(self.name, self.kind, url, title, body))
        return result


class DisasterSource(_BulletinSource):
    name = "disaster"
    description = "ปภ. — รายงานสถานการณ์รายวัน (จังหวัด/อำเภอ/ครัวเรือน/ผู้เสียชีวิต)"
    kind = "situation_report"
    list_url_attr = "disaster_url"


class OnwrSource(_BulletinSource):
    name = "onwr"
    description = "สทนช. — ประกาศเตือนภัยและพื้นที่เสี่ยงล่วงหน้า"
    kind = "warning"
    list_url_attr = "onwr_url"


def report_from_dict(data: dict[str, Any]) -> Report:
    """ใช้นำเข้ารายงานที่กรอกเอง (เช่นจาก PDF ของ ปภ.) ผ่าน CLI `thaiflood import-report`"""
    return Report(**data)
