"""ThaiWater.net (สสน.) — ฝนรายชั่วโมง/24 ชม., ระดับน้ำในแม่น้ำ, น้ำในเขื่อน

ใช้ API สาธารณะชุดเดียวกับที่หน้าเว็บ thaiwater.net เรียก (api-v3.thaiwater.net)
โครงสร้าง JSON ที่รองรับ: {"data": [...]}, {"waterlevel_data": {"data": [...]}}, หรือ list ตรง ๆ
"""

from __future__ import annotations

import logging
from typing import Any

from urllib.parse import urljoin

from ..models import CollectResult, Observation, Report
from ..utils import dig, th, to_float, to_iso
from .base import Source

log = logging.getLogger("thaiflood")

# ระดับสถานการณ์ของ สสน. (situation_level)
SITUATION = {
    1: "น้อยวิกฤต",
    2: "น้อย",
    3: "ปกติ",
    4: "มาก",
    5: "ล้นตลิ่ง/วิกฤต",
}


def _rows(payload: Any, *keys: str) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in keys:
        node = payload.get(key)
        if isinstance(node, list):
            return node
        if isinstance(node, dict):
            # ซ้อนได้หลายชั้น เช่น thailand_main: {"dam": {"data": {"result": ..., "data": [...]}}}
            found = _rows(node)
            if found:
                return found
    data = payload.get("data")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return _rows(data, *keys)
    return []


def _describe(node: Any, depth: int = 0) -> str:
    """อธิบายโครงสร้าง JSON แบบย่อ (ใช้ใน log เมื่อ parser อ่านไม่ออก)"""
    if isinstance(node, dict):
        if depth >= 2:
            return f"dict({len(node)})"
        return "{" + ", ".join(f"{k}: {_describe(v, depth + 1)}" for k, v in list(node.items())[:12]) + "}"
    if isinstance(node, list):
        return f"list[{len(node)}]" + (f" of {_describe(node[0], depth + 1)}" if node and depth < 2 else "")
    return type(node).__name__


def _geo(row: dict[str, Any]) -> dict[str, str | None]:
    geocode = row.get("geocode") or {}
    return {
        "province": th(geocode.get("province_name")),
        "amphoe": th(geocode.get("amphoe_name")),
        "tambon": th(geocode.get("tumbon_name") or geocode.get("tambon_name")),
    }


def _station(row: dict[str, Any]) -> dict[str, Any]:
    st = row.get("station") or {}
    return {
        "station_id": str(st.get("id") or row.get("station_id") or row.get("id")),
        "name": th(st.get("tele_station_name") or st.get("station_name") or st.get("name")),
        "lat": to_float(st.get("tele_station_lat") or st.get("lat")),
        "lon": to_float(st.get("tele_station_long") or st.get("long") or st.get("lon")),
    }


def parse_waterlevel(payload: Any) -> list[Observation]:
    out = []
    for row in _rows(payload, "waterlevel_data"):
        st = row.get("station") or {}
        level = row.get("situation_level")
        out.append(
            Observation(
                source="thaiwater",
                kind="waterlevel",
                observed_at=to_iso(row.get("waterlevel_datetime") or row.get("datetime")),
                value=to_float(row.get("waterlevel_msl")),
                unit="m.MSL",
                status=SITUATION.get(level, str(level) if level is not None else None),
                extra={
                    k: v
                    for k, v in {
                        "waterlevel_m": to_float(row.get("waterlevel_m")),
                        "storage_percent": to_float(row.get("storage_percent")),
                        "discharge": to_float(row.get("discharge") or row.get("flow_rate")),
                        "min_bank": to_float(st.get("min_bank")),
                        "ground_level": to_float(st.get("ground_level")),
                        "river": th(dig(row, "river_name") or st.get("river_name")),
                        "agency": th(dig(row, "agency", "agency_shortname") or dig(row, "agency", "agency_name")),
                    }.items()
                    if v is not None
                },
                **_station(row),
                **_geo(row),
            )
        )
    return out


def parse_rain(payload: Any, kind: str = "rain_24h") -> list[Observation]:
    out = []
    value_key = {"rain_24h": "rain_24h", "rain_1h": "rain_1h", "rain_3h": "rain_3h"}.get(kind, kind)
    for row in _rows(payload, "rain_data", "rain_24h"):
        value = row.get(value_key, row.get("rain_value", row.get("value")))
        out.append(
            Observation(
                source="thaiwater",
                kind=kind,
                observed_at=to_iso(row.get("rainfall_datetime") or row.get("rain_datetime") or row.get("datetime")),
                value=to_float(value),
                unit="mm",
                **_station(row),
                **_geo(row),
            )
        )
    return out


def parse_dam(payload: Any) -> list[Observation]:
    out = []
    for row in _rows(payload, "dam_data", "dam_daily", "dam"):
        dam = row.get("dam") or {}
        out.append(
            Observation(
                source="thaiwater",
                kind="dam_storage",
                station_id=str(dam.get("id") or row.get("dam_id") or row.get("id")),
                name=th(dam.get("dam_name") or row.get("dam_name")),
                lat=to_float(dam.get("dam_lat")),
                lon=to_float(dam.get("dam_long")),
                observed_at=to_iso(row.get("dam_date") or row.get("date")),
                value=to_float(row.get("dam_storage_percent")),
                unit="%",
                extra={
                    k: v
                    for k, v in {
                        "storage_mcm": to_float(row.get("dam_storage")),
                        "uses_water_mcm": to_float(row.get("dam_uses_water")),
                        "uses_water_percent": to_float(row.get("dam_uses_water_percent")),
                        "inflow_mcm": to_float(row.get("dam_inflow")),
                        "released_mcm": to_float(row.get("dam_released")),
                    }.items()
                    if v is not None
                },
                **_geo(row),
            )
        )
    return out


_IMG_EXT = (".png", ".gif", ".jpg", ".jpeg", ".webp")


def _is_image(value: Any) -> bool:
    return isinstance(value, str) and value.split("?")[0].lower().endswith(_IMG_EXT)


def parse_radar(payload: Any, media_base: str) -> list[Report]:
    """หาภาพเรดาร์ในส่วน "radar" ของ thailand_main — ไม่ผูกกับชื่อฟิลด์ตายตัว:
    เดินทุก dict ที่มีค่าเป็นลิงก์ภาพ แล้วใช้ฟิลด์ชื่อ/เวลาที่อยู่ข้างกัน"""
    root = payload.get("radar", payload) if isinstance(payload, dict) else payload
    out: list[Report] = []
    seen: set[str] = set()

    def label_of(d: dict[str, Any]) -> str | None:
        for k, v in d.items():
            if any(w in k.lower() for w in ("name", "title", "station", "radar_type", "agency")) and not _is_image(v):
                text = th(v)
                if isinstance(text, str) and text.strip():
                    return text.strip()
        return None

    def time_of(d: dict[str, Any]) -> str | None:
        for k, v in d.items():
            if any(w in k.lower() for w in ("datetime", "date", "time")) and isinstance(v, (str, int, float)) and not _is_image(v):
                return to_iso(v)
        return None

    def walk(node: Any, parent_label: str | None) -> None:
        if isinstance(node, dict):
            label = label_of(node) or parent_label
            for k, v in node.items():
                if _is_image(v):
                    url = urljoin(media_base, v)
                    if url not in seen:
                        seen.add(url)
                        title = label or k
                        out.append(Report(source="thaiwater", kind="radar_image", title=f"เรดาร์ {title}",
                                          url=url, published_at=time_of(node)))
                else:
                    walk(v, label)
        elif isinstance(node, list):
            for item in node:
                if _is_image(item):
                    url = urljoin(media_base, item)
                    if url not in seen:
                        seen.add(url)
                        out.append(Report(source="thaiwater", kind="radar_image",
                                          title=f"เรดาร์ {parent_label or len(out) + 1}", url=url))
                else:
                    walk(item, parent_label)

    walk(root, None)
    return out


class ThaiWaterSource(Source):
    name = "thaiwater"
    description = "สสน. ThaiWater — ฝน 24 ชม., ระดับน้ำแม่น้ำ, น้ำในเขื่อน (รายชั่วโมง/รายวัน)"

    def _url(self, path: str) -> str:
        return self.settings.thaiwater_base.rstrip("/") + path

    def collect(self) -> CollectResult:
        result = CollectResult(self.name)
        jobs = (
            ("waterlevel", self.settings.thaiwater_waterlevel_path, parse_waterlevel),
            ("rain_24h", self.settings.thaiwater_rain_path, parse_rain),
            ("dam", self.settings.thaiwater_dam_path, parse_dam),
        )
        cache: dict[str, Any] = {}
        for label, paths, parser in jobs:
            tried = []
            for path in [p.strip() for p in paths.split(",") if p.strip()]:
                try:
                    payload = cache[path] if path in cache else self.get_json(self._url(path))
                    cache[path] = payload
                except Exception as exc:  # แหล่งย่อยหนึ่งพังไม่ควรทำให้ทั้งรอบพัง
                    tried.append(f"{path}: {exc}")
                    continue
                obs = parser(payload)
                if not obs or all(o.value is None for o in obs):
                    keys = list(payload)[:8] if isinstance(payload, dict) else type(payload).__name__
                    if isinstance(payload, dict) and label == "dam" and "dam" in payload:
                        keys = f"{keys}, dam={_describe(payload['dam'])}"
                    sample = ""
                    if obs:  # เจอแถวแต่อ่านค่าไม่ได้ — แสดงชื่อฟิลด์ของแถวแรกไว้แก้ parser
                        first = _rows(payload, "dam_data", "dam_daily", "dam", "waterlevel_data", "rain_data")[:1]
                        sample = f", ฟิลด์แถวแรก={list(first[0])[:15] if first else '-'}"
                    tried.append(f"{path}: ตอบกลับแต่ไม่พบข้อมูล (keys={keys}{sample})")
                    continue
                result.raw[f"{label}.json"] = payload
                result.observations.extend(obs)
                tried = []
                break
            if tried:
                result.errors.append(f"{label}: " + " | ".join(tried))

        # ภาพเรดาร์ฝน (กรมอุตุฯ/กรมฝนหลวง) ที่ ThaiWater รวบรวมไว้ใน thailand_main
        path = self.settings.thaiwater_main_path
        try:
            main = cache[path] if path in cache else self.get_json(self._url(path))
            radar = main.get("radar") if isinstance(main, dict) else None
            log.info("thaiwater radar: %s", _describe(radar))
            reports = parse_radar(main, self.settings.thaiwater_media_base)
            if reports:
                result.reports.extend(reports)
                log.info("thaiwater radar: %d ภาพ เช่น %s", len(reports), [(r.title, r.url, r.published_at) for r in reports[:3]])
            else:
                result.errors.append(f"radar: ไม่พบลิงก์ภาพ — โครงสร้าง={_describe(radar)}")
        except Exception as exc:
            result.errors.append(f"radar: {exc}")
        return result

    def waterlevel_history(self, station_id: str, start: str, end: str) -> list[Observation]:
        """ดึงระดับน้ำย้อนหลังของสถานีเดียว (start/end = YYYY-MM-DD)"""
        path = self.settings.thaiwater_waterlevel_graph_path.format(station_id=station_id, start=start, end=end)
        payload = self.get_json(self._url(path))
        return parse_waterlevel_graph(payload, station_id)


def parse_waterlevel_graph(payload: Any, station_id: str) -> list[Observation]:
    """กราฟรายสถานี: {"data": {"graph_data": [{"datetime": ..., "value": ...}], ...}} หรือ list ของจุด"""
    node = payload.get("data", payload) if isinstance(payload, dict) else payload
    points = node.get("graph_data", node.get("data", [])) if isinstance(node, dict) else node
    meta = node if isinstance(node, dict) else {}
    out = []
    for p in points or []:
        out.append(
            Observation(
                source="thaiwater",
                kind="waterlevel",
                station_id=str(station_id),
                observed_at=to_iso(p.get("datetime") or p.get("waterlevel_datetime")),
                value=to_float(p.get("value", p.get("waterlevel_msl"))),
                unit="m.MSL",
                name=th(meta.get("station_name")),
                extra={"backfill": True},
            )
        )
    return out
