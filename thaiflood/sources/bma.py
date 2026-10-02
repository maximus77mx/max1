"""สำนักการระบายน้ำ กทม. — จุดน้ำท่วมขังรายจุด

ระบบ Floodmon ของ กทม. แสดงจุดตรวจวัดน้ำท่วมขังบนถนน (ความลึก ซม.)
รองรับต้นทาง 2 แบบ: JSON (list ของจุด) หรือหน้า HTML ที่มีตาราง
ตั้ง BMA_DDS_URL ให้ชี้ไปยัง endpoint ที่ใช้งานได้จริงในขณะนั้น
"""

from __future__ import annotations

import json
import re
from typing import Any

from ..models import CollectResult, Observation
from ..utils import now_th, parse_html, to_float, to_iso
from .base import Source


def _pick(row: dict[str, Any], *keys: str) -> Any:
    lowered = {k.lower(): v for k, v in row.items()}
    for key in keys:
        if lowered.get(key) not in (None, ""):
            return lowered[key]
    return None


def parse_json_points(payload: Any) -> list[Observation]:
    rows = payload if isinstance(payload, list) else (payload.get("data") or payload.get("features") or [])
    out = []
    fallback = now_th().isoformat(timespec="minutes")
    for i, row in enumerate(rows):
        if "properties" in row:  # GeoJSON
            coords = (row.get("geometry") or {}).get("coordinates") or [None, None]
            row = {**row["properties"], "lon": coords[0], "lat": coords[1]}
        depth = to_float(_pick(row, "depth", "water_depth", "level", "value", "wl"))
        out.append(
            Observation(
                source="bma",
                kind="street_flood",
                station_id=str(_pick(row, "id", "code", "station_id", "sensor_id") or i),
                name=_pick(row, "name", "location", "station_name", "road"),
                province="กรุงเทพมหานคร",
                amphoe=_pick(row, "district", "khet", "เขต"),
                lat=to_float(_pick(row, "lat", "latitude")),
                lon=to_float(_pick(row, "lon", "lng", "long", "longitude")),
                observed_at=to_iso(_pick(row, "datetime", "updated_at", "time", "date")) or fallback,
                value=depth,
                unit="cm",
                status=_pick(row, "status", "traffic", "การจราจร"),
            )
        )
    return out


def parse_html_points(html: str) -> list[Observation]:
    """อ่านตารางที่มีคอลัมน์ ชื่อจุด/เขต/ระดับน้ำ(ซม.)/เวลา"""
    _, tables = parse_html(html)
    out = []
    fallback = now_th().isoformat(timespec="minutes")
    for table in tables:
        if len(table) < 2:
            continue
        header = [h.lower() for h in table[0]]

        def col(*words: str) -> int | None:
            for idx, h in enumerate(header):
                if any(w in h for w in words):
                    return idx
            return None

        c_name = col("จุด", "สถานที่", "ถนน", "location", "name")
        c_depth = col("ระดับ", "ความลึก", "ซม", "cm", "depth")
        if c_name is None or c_depth is None:
            continue
        c_khet = col("เขต", "district")
        c_time = col("เวลา", "time", "update")
        c_status = col("สถานะ", "จราจร", "status")
        for row in table[1:]:
            if len(row) <= max(c_name, c_depth):
                continue
            name = row[c_name]
            out.append(
                Observation(
                    source="bma",
                    kind="street_flood",
                    station_id=re.sub(r"\s+", "_", name)[:80],
                    name=name,
                    province="กรุงเทพมหานคร",
                    amphoe=row[c_khet] if c_khet is not None and c_khet < len(row) else None,
                    observed_at=(to_iso(row[c_time]) if c_time is not None and c_time < len(row) else None) or fallback,
                    value=to_float(row[c_depth]),
                    unit="cm",
                    status=row[c_status] if c_status is not None and c_status < len(row) else None,
                )
            )
    return out


class BmaSource(Source):
    name = "bma"
    description = "สำนักการระบายน้ำ กทม. — จุดน้ำท่วมขังรายจุด (ซม.)"

    def collect(self) -> CollectResult:
        result = CollectResult(self.name)
        try:
            text = self.get_text(self.settings.bma_url)
        except Exception as exc:
            result.errors.append(str(exc))
            return result
        try:
            payload = json.loads(text)
            result.raw["points.json"] = payload
            result.observations = parse_json_points(payload)
        except json.JSONDecodeError:
            result.raw["page.html"] = text
            result.observations = parse_html_points(text)
            if not result.observations:
                result.errors.append("ไม่พบตารางจุดน้ำท่วมขังในหน้า — ตรวจ BMA_DDS_URL")
        return result
