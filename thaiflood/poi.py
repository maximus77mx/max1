"""สถานที่ช่วยเหลือฉุกเฉินจาก OpenStreetMap: โรงพยาบาล, รพ.สต./ศูนย์บริการสาธารณสุข, สถานีตำรวจ,
สถานีดับเพลิง และที่ว่าการอำเภอ/สำนักงานเขต/เทศบาล

ดึงทั้งประเทศผ่าน Overpass API (ฟรี ไม่ต้องใช้ key) เดือนละครั้งแล้วเก็บไว้ที่ data/boundaries/poi_v2.json
หน้า dashboard โหลดไฟล์ย่อ geo/poi.json เฉพาะตอนเปิดดูจุด/ตำบล เพื่อแสดงสถานที่ใกล้ที่สุดพร้อมเบอร์โทร

เบอร์โทรมาจากผู้ร่วมแก้ไข OpenStreetMap — บางแห่งไม่มีเบอร์หรือเบอร์อาจเก่า หน้าเว็บจึงมีลิงก์ค้นหาใน Google Maps ให้ด้วย
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

import requests

log = logging.getLogger(__name__)

# h=โรงพยาบาล c=รพ.สต./ศูนย์บริการสาธารณสุข p=สถานีตำรวจ f=สถานีดับเพลิง t=ที่ว่าการอำเภอ/สำนักงานเขต/เทศบาล
KINDS = {"hospital": "h", "clinic": "c", "police": "p", "fire_station": "f", "townhall": "t"}
# ชื่อที่บอกว่าเป็นหน่วยบริการสาธารณสุขของรัฐระดับตำบล (คลินิกเอกชนไม่เอา)
HEALTH_CENTRE = r"ส่งเสริมสุขภาพ|สถานีอนามัย|ศูนย์บริการสาธารณสุข|ศูนย์สุขภาพชุมชน|รพ\.? ?สต"
CACHE_NAME = "poi_v2.json"  # เปลี่ยนชื่อเมื่อเพิ่มประเภท — ไม่ใช้ไฟล์เก่าที่ยังไม่มีประเภทใหม่

QUERY = f"""[out:json][timeout:300];
area["ISO3166-1"="TH"][admin_level=2]->.th;
(
  nwr["amenity"~"^(hospital|police|fire_station|townhall)$"](area.th);
  nwr["amenity"="clinic"]["name"~"{HEALTH_CENTRE.replace(chr(92), chr(92) * 2)}"](area.th);
  nwr["healthcare"="centre"](area.th);
);
out center tags;"""


def _phone(tags: dict[str, Any]) -> str | None:
    for key in ("phone", "contact:phone", "phone:th", "contact:mobile", "phone:mobile"):
        value = tags.get(key)
        if value:
            first = str(value).split(";")[0].strip()
            return first or None
    return None


def parse_overpass(payload: dict[str, Any]) -> list[list[Any]]:
    """แปลงผล Overpass เป็นแถวย่อ [ประเภท, ชื่อ, lat, lon, เบอร์] — ตัดรายการซ้ำ (node + way ของที่เดียวกัน)"""
    rows: list[list[Any]] = []
    seen: set[tuple[str, str, float, float]] = set()
    for el in payload.get("elements", []):
        tags = el.get("tags") or {}
        kind = KINDS.get(tags.get("amenity", "")) or ("c" if tags.get("healthcare") == "centre" else None)
        lat = el.get("lat", (el.get("center") or {}).get("lat"))
        lon = el.get("lon", (el.get("center") or {}).get("lon"))
        if not kind or lat is None or lon is None:
            continue
        name = tags.get("name:th") or tags.get("name") or tags.get("name:en") or ""
        if kind in ("h", "c") and re.search(HEALTH_CENTRE, name):
            kind = "c"  # รพ.สต. ที่ติดป้ายเป็น hospital — แยกออกจากโรงพยาบาลจริง
        elif kind == "c" and not re.search(HEALTH_CENTRE, name) and tags.get("healthcare") != "centre":
            continue
        key = (kind, name, round(lat, 3), round(lon, 3))
        if key in seen:
            continue
        seen.add(key)
        rows.append([kind, name.strip(), round(float(lat), 5), round(float(lon), 5), _phone(tags)])
    return rows


def ensure_pois(data_dir: Path, url: str, max_age_days: float = 30, session: Any = None,
                timeout: float = 300, user_agent: str = "thaiflood-collector") -> list[list[Any]]:
    """คืนรายการสถานที่ช่วยเหลือ — ใช้ไฟล์เก็บไว้ถ้ายังไม่เก่า ดึงใหม่ไม่ได้ก็ใช้ของเดิม ไม่มีเลยคืนรายการว่าง

    url คั่นหลาย server ด้วย , ได้ (ลองตามลำดับ) — Overpass ปฏิเสธคำขอที่ไม่ระบุ User-Agent (406)
    """
    cache = data_dir / "boundaries" / CACHE_NAME
    fresh = cache.exists() and time.time() - cache.stat().st_mtime < max_age_days * 86400
    if not fresh:
        errors = []
        headers = {"User-Agent": user_agent, "Accept": "application/json"}
        for endpoint in [u.strip() for u in url.split(",") if u.strip()]:
            try:
                resp = (session or requests).post(endpoint, data={"data": QUERY}, headers=headers, timeout=timeout)
                resp.raise_for_status()
                rows = parse_overpass(resp.json())
                if not rows:
                    raise ValueError("ไม่คืนข้อมูล")
            except Exception as exc:  # server ไม่ว่าง/ปฏิเสธ — ลองตัวถัดไป
                errors.append(f"{endpoint}: {exc}")
                continue
            cache.parent.mkdir(parents=True, exist_ok=True)
            tmp = cache.with_suffix(".part")
            tmp.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            tmp.replace(cache)
            counts = {k: sum(1 for r in rows if r[0] == k) for k in "hcpft"}
            log.info("poi: %d แห่งจาก OpenStreetMap (%s) %s", len(rows), endpoint, counts)
            return rows
        log.warning("poi: ดึงจาก Overpass ไม่ได้ (%s)%s", " | ".join(errors), " — ใช้ไฟล์เดิม" if cache.exists() else "")
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    return []


def write_poi_layer(rows: list[list[Any]], out_dir: Path) -> Path | None:
    if not rows:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "poi.json"
    path.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return path
