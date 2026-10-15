"""แผ่นดินไหวในประเทศไทยจาก USGS Earthquake Catalog (FDSN event web service — ฟรี ไม่ต้องใช้ key)

ดึงเหตุใน 30 วันล่าสุดภายในกรอบพิกัดของประเทศไทย ทุกรอบดึงซ้ำทั้งช่วง เพื่อรับค่าขนาดที่ USGS ปรับแก้ภายหลัง
(แถวเดิมถูกอัปเดต ไม่เพิ่มซ้ำ) — กรอบสี่เหลี่ยมกินพื้นที่ประเทศเพื่อนบ้านบางส่วน หน้า dashboard จึงคัดเฉพาะ
เหตุที่ศูนย์กลางอยู่ในขอบเขตตำบลของไทยอีกชั้น
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from ..models import CollectResult, Observation
from ..utils import TH_TZ, to_float
from .base import Source

THAILAND_BBOX = {"minlatitude": 5.6, "maxlatitude": 20.5, "minlongitude": 97.3, "maxlongitude": 105.7}


def _mag_status(mag: float | None) -> str | None:
    if mag is None:
        return None
    return "รุนแรง" if mag >= 5 else "ปานกลาง" if mag >= 4 else "เบา" if mag >= 3 else "เล็กน้อย"


def parse_events(payload: dict[str, Any]) -> list[Observation]:
    out = []
    for f in payload.get("features") or []:
        p = f.get("properties") or {}
        coords = (f.get("geometry") or {}).get("coordinates") or []
        if len(coords) < 2 or p.get("time") is None:
            continue
        mag = to_float(p.get("mag"))
        when = datetime.fromtimestamp(p["time"] / 1000, timezone.utc).astimezone(TH_TZ)
        extra = {
            "depth_km": to_float(coords[2]) if len(coords) > 2 else None,
            "mag_type": p.get("magType"),
            "felt": p.get("felt"),
            "mmi": to_float(p.get("mmi")),
            "alert": p.get("alert"),
            "usgs_url": p.get("url"),
        }
        out.append(
            Observation(
                source="usgs",
                kind="earthquake",
                station_id=str(f.get("id") or p.get("code")),
                observed_at=when.isoformat(timespec="seconds"),
                value=mag,
                unit="แมกนิจูด",
                name=p.get("place") or p.get("title"),
                lat=to_float(coords[1]),
                lon=to_float(coords[0]),
                status=_mag_status(mag),
                extra={k: v for k, v in extra.items() if v is not None},
            )
        )
    return out


class UsgsQuakeSource(Source):
    name = "usgs"
    description = "USGS — แผ่นดินไหวในประเทศไทย 30 วันล่าสุด (ขนาด ความลึก เวลา)"

    def collect(self) -> CollectResult:
        result = CollectResult(self.name)
        start = (datetime.now(timezone.utc) - timedelta(days=self.settings.quake_days)).strftime("%Y-%m-%dT%H:%M:%S")
        params = {"format": "geojson", "starttime": start, "minmagnitude": self.settings.quake_min_magnitude,
                  "orderby": "time", **THAILAND_BBOX}
        try:
            payload = self.get_json(self.settings.usgs_event_url, params=params)
        except Exception as exc:
            result.errors.append(str(exc))
            return result
        result.raw["events.geojson"] = payload
        result.observations = parse_events(payload)
        return result
