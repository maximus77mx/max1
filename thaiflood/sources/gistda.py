"""GISTDA — พื้นที่น้ำท่วมจากภาพดาวเทียม (อัปเดตรายวัน)

ใช้ GISTDA API Gateway (ต้องสมัครรับ API key ฟรีที่ https://api-gateway.gistda.or.th
แล้วตั้ง env GISTDA_API_KEY) ผลลัพธ์เป็น GeoJSON FeatureCollection
ช่วงเวลาที่รองรับ: 1day, 3days, 7days, 30days
"""

from __future__ import annotations

from typing import Any

from ..models import CollectResult, Observation
from ..utils import now_th, to_float, to_iso
from .base import Source

PERIODS = ("1day", "3days", "7days", "30days")


def _centroid(geometry: dict[str, Any] | None) -> tuple[float | None, float | None]:
    """จุดกึ่งกลางแบบคร่าว ๆ (เฉลี่ยพิกัด) — พอสำหรับปักหมุด/จัดกลุ่ม ไม่ใช่งานวัดพื้นที่"""
    if not geometry:
        return None, None
    coords: list[list[float]] = []

    def walk(node: Any) -> None:
        if isinstance(node, list) and node and isinstance(node[0], (int, float)):
            coords.append(node)  # type: ignore[arg-type]
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(geometry.get("coordinates"))
    if not coords:
        return None, None
    lon = sum(c[0] for c in coords) / len(coords)
    lat = sum(c[1] for c in coords) / len(coords)
    return round(lat, 6), round(lon, 6)


def _pick(props: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if props.get(key) not in (None, ""):
            return props[key]
    return None


def parse_flood(payload: dict[str, Any], period: str = "1day") -> list[Observation]:
    out = []
    fallback_time = now_th().replace(minute=0, second=0, microsecond=0).isoformat()
    for i, feature in enumerate(payload.get("features") or []):
        props = feature.get("properties") or {}
        lat, lon = _centroid(feature.get("geometry"))
        area_rai = to_float(_pick(props, "area_rai", "rai", "AREA_RAI"))
        if area_rai is None:
            area_km2 = to_float(_pick(props, "area_km2", "area_sqkm"))
            area_rai = area_km2 * 625 if area_km2 is not None else None  # 1 ตร.กม. = 625 ไร่
        station_id = _pick(props, "tb_idn", "tambon_code", "_id", "id") or feature.get("id") or f"{period}-{i}"
        out.append(
            Observation(
                source="gistda",
                kind="flood_area",
                station_id=str(station_id),
                observed_at=to_iso(_pick(props, "f_date", "date", "_createdAt", "acq_date")) or fallback_time,
                value=area_rai,
                unit="rai",
                name=_pick(props, "tb_tn", "tambon"),
                province=_pick(props, "pv_tn", "province", "pv_name"),
                amphoe=_pick(props, "ap_tn", "amphoe", "ap_name"),
                tambon=_pick(props, "tb_tn", "tambon"),
                lat=lat,
                lon=lon,
                extra={"period": period, "satellite": _pick(props, "satellite", "sat_name")},
            )
        )
    return out


class GistdaSource(Source):
    name = "gistda"
    description = "GISTDA — พื้นที่น้ำท่วมจากดาวเทียม (รายวัน, GeoJSON)"
    page_size = 1000
    _last_page: dict[str, Any] | None = None

    def fetch(self, period: str = "1day") -> dict[str, Any]:
        if period not in PERIODS:
            raise ValueError(f"period ต้องเป็นหนึ่งใน {PERIODS}")
        if not self.settings.gistda_api_key:
            raise RuntimeError("ยังไม่ได้ตั้ง GISTDA_API_KEY (สมัครที่ https://api-gateway.gistda.or.th)")
        url = f"{self.settings.gistda_base.rstrip('/')}/{period}"
        headers = {"API-Key": self.settings.gistda_api_key}
        features: list[dict[str, Any]] = []
        offset = 0
        while True:
            page = self.get_json(url, headers=headers, params={"limit": self.page_size, "offset": offset})
            self._last_page = page if isinstance(page, dict) else {"type": type(page).__name__}
            batch = (page.get("features") or page.get("data") or []) if isinstance(page, dict) else []
            features.extend(batch)
            if len(batch) < self.page_size:
                break
            offset += self.page_size
        return {"type": "FeatureCollection", "features": features}

    def collect(self, period: str = "1day") -> CollectResult:
        result = CollectResult(self.name)
        try:
            payload = self.fetch(period)
            result.raw[f"flood_{period}.geojson"] = payload  # เก็บ GeoJSON เต็มไว้ทำแผนที่
            result.observations = parse_flood(payload, period)
            if not result.observations:
                meta = {k: v for k, v in self._last_page.items() if k != "features"} if self._last_page else {}
                result.errors.append(f"API ตอบกลับ 0 พื้นที่ ({period}) — meta={str(meta)[:300]}")
        except Exception as exc:
            result.errors.append(str(exc))
        return result
