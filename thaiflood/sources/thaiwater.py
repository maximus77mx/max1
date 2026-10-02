"""ThaiWater.net (สสน.) — ฝนรายชั่วโมง/24 ชม., ระดับน้ำในแม่น้ำ, น้ำในเขื่อน

ใช้ API สาธารณะชุดเดียวกับที่หน้าเว็บ thaiwater.net เรียก (api-v3.thaiwater.net)
โครงสร้าง JSON ที่รองรับ: {"data": [...]}, {"waterlevel_data": {"data": [...]}}, หรือ list ตรง ๆ
"""

from __future__ import annotations

from typing import Any

from ..models import CollectResult, Observation
from ..utils import dig, th, to_float, to_iso
from .base import Source

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
        if isinstance(node, dict) and isinstance(node.get("data"), list):
            return node["data"]
        if isinstance(node, list):
            return node
    data = payload.get("data")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return _rows(data, *keys)
    return []


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
    for row in _rows(payload, "dam_data", "dam_daily"):
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
        for label, path, parser in jobs:
            try:
                payload = self.get_json(self._url(path))
                result.raw[f"{label}.json"] = payload
                result.observations.extend(parser(payload))
            except Exception as exc:  # แหล่งย่อยหนึ่งพังไม่ควรทำให้ทั้งรอบพัง
                result.errors.append(f"{label}: {exc}")
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
