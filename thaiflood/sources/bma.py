"""สำนักการระบายน้ำ กทม. — จุดน้ำท่วมขังรายจุด

ทางหลัก: API ที่หน้า floodbangkok.bangkok.go.th ใช้เอง (ระบบ Directus, ไม่ต้องใช้ key)
  - items/sensor_profile      รายชื่อเซนเซอร์ทุกจุด (พิกัด ถนน เขต สถานะอุปกรณ์)
  - items/flood_notification  แจ้งเตือนความลึกน้ำ (ซม.) รายจุดทุก ~5 นาทีระหว่างท่วม
ทางสำรอง (ตั้ง BMA_API_BASE ว่าง): BMA_DDS_URL ที่เป็น JSON list ของจุด หรือหน้า HTML ที่มีตาราง
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
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


DEVICE_STATUS = {
    "normal": "ปกติ",
    "minor_flood": "น้ำท่วมขังเล็กน้อย",
    "flooding": "น้ำท่วมขัง",
    "malfunction": "อุปกรณ์ขัดข้อง",
}


def _parse_ts(value: Any) -> datetime | None:
    iso = to_iso(value)
    return datetime.fromisoformat(iso) if iso else None


def parse_sensor_api(profiles: Any, notifications: Any, now: datetime | None = None,
                     active_minutes: int = 60) -> list[Observation]:
    """รวมรายชื่อเซนเซอร์กับแจ้งเตือนล่าสุด → ความลึกน้ำปัจจุบันรายจุด

    จุดที่มีแจ้งเตือนภายใน active_minutes ถือว่ายังท่วมตามค่าล่าสุด จุดอื่นถือว่าแห้ง (0 ซม.)
    ยกเว้นอุปกรณ์ขัดข้อง หรือสถานะบอกว่าท่วมแต่ไม่มีค่าความลึก → ไม่ทราบค่า (None)
    """
    now = now or now_th()
    # บันทึกเป็นช่วงละ 5 นาที — รันซ้ำในช่วงเดียวกันจะอัปเดตแถวเดิม ไม่เพิ่มแถว
    stamp = now.replace(minute=now.minute - now.minute % 5, second=0, microsecond=0).isoformat(timespec="minutes")
    rows = profiles.get("data", []) if isinstance(profiles, dict) else profiles or []
    notes = notifications.get("data", []) if isinstance(notifications, dict) else notifications or []

    latest: dict[str, tuple[datetime, dict[str, Any]]] = {}
    for note in notes:
        sensor = note.get("sensor_profile")
        code = sensor.get("code") if isinstance(sensor, dict) else None
        ts = _parse_ts(note.get("noti_created_at") or note.get("date_created"))
        if code and ts and (code not in latest or ts > latest[code][0]):
            latest[code] = (ts, note)

    out = []
    for row in rows:
        code = row.get("code") or str(row.get("id"))
        device = row.get("device_status") or ""
        extra: dict[str, Any] = {"code": code, "road": row.get("road"), "main_road": row.get("main_road"),
                                 "device_status": device}
        value: float | None = 0.0
        status = DEVICE_STATUS.get(device, device or None)
        hit = latest.get(code)
        if device == "malfunction":
            value = None
        elif hit and now - hit[0] <= timedelta(minutes=active_minutes):
            note = hit[1]
            value = to_float(note.get("value"))
            extra.update(highest=to_float(note.get("heighest_value")), start_flood=to_iso(note.get("start_flood")),
                         reported_at=to_iso(note.get("noti_created_at")))
            if device == "normal":
                status = DEVICE_STATUS["flooding"]
        elif device in ("flooding", "minor_flood"):
            value = None  # สถานะบอกว่าท่วม แต่ไม่มีแจ้งเตือนความลึกล่าสุด
        out.append(
            Observation(
                source="bma",
                kind="street_flood",
                station_id=code,
                name=(row.get("name") or "").rstrip(" *") or code,
                province="กรุงเทพมหานคร",
                amphoe=row.get("district"),
                lat=to_float(row.get("lat")),
                lon=to_float(row.get("long") if row.get("long") is not None else row.get("lon")),
                observed_at=stamp,
                value=value,
                unit="cm",
                status=status,
                extra={k: v for k, v in extra.items() if v is not None},
            )
        )
    return out


class BmaSource(Source):
    name = "bma"
    description = "สำนักการระบายน้ำ กทม. — จุดน้ำท่วมขังรายจุด (ซม.)"

    def collect(self) -> CollectResult:
        if self.settings.bma_api_base:
            return self.collect_api()
        return self.collect_page()

    def collect_api(self) -> CollectResult:
        result = CollectResult(self.name)
        base = self.settings.bma_api_base.rstrip("/")
        try:
            profiles = self.get_json(f"{base}/sensor_profile", params={"limit": -1, "page": 0})
        except Exception as exc:
            result.errors.append(f"sensor_profile: {exc}")
            return result
        result.raw["sensor_profile.json"] = profiles
        notifications: Any = []
        try:
            notifications = self.get_json(f"{base}/flood_notification", params={
                "limit": 500, "page": 0, "fields": "*.*", "sort": "-noti_created_at"})
            result.raw["flood_notification.json"] = notifications
        except Exception as exc:  # ยังได้รายชื่อจุด/สถานะอุปกรณ์ แม้ไม่มีความลึก
            result.errors.append(f"flood_notification: {exc}")
        result.observations = parse_sensor_api(profiles, notifications,
                                               active_minutes=self.settings.bma_active_minutes)
        if not result.observations:
            result.errors.append("sensor_profile ไม่มีข้อมูล — ตรวจ BMA_API_BASE")
        return result

    def collect_page(self) -> CollectResult:
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
