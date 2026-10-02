"""กรมอุตุนิยมวิทยา — พยากรณ์ฝนรายชั่วโมง (NWP API) และภาพเรดาร์ฝนล่าสุด

NWP API ต้องใช้ token (สมัครที่ https://data.tmd.go.th/nwpapi) ตั้ง env TMD_API_TOKEN
จุดพยากรณ์ตั้งได้ที่ TMD_POINTS="ชื่อ:lat:lon;..."
"""

from __future__ import annotations

from typing import Any

from ..models import CollectResult, Observation, Report
from ..utils import now_th, to_float, to_iso
from .base import Source

# cond ของ TMD NWP: 1 ท้องฟ้าแจ่มใส ... 5-8 ฝน ... 12 ฝนฟ้าคะนอง
CONDITIONS = {
    1: "ท้องฟ้าแจ่มใส", 2: "มีเมฆบางส่วน", 3: "เมฆเป็นส่วนมาก", 4: "มีเมฆมาก",
    5: "ฝนตกเล็กน้อย", 6: "ฝนปานกลาง", 7: "ฝนตกหนัก", 8: "ฝนฟ้าคะนอง",
    9: "อากาศหนาวจัด", 10: "อากาศหนาว", 11: "อากาศเย็น", 12: "อากาศร้อนจัด",
}


def parse_points(spec: str) -> list[tuple[str, float, float]]:
    points = []
    for chunk in spec.split(";"):
        parts = chunk.strip().split(":")
        if len(parts) == 3:
            points.append((parts[0], float(parts[1]), float(parts[2])))
    return points


def parse_forecast(payload: dict[str, Any], name: str) -> list[Observation]:
    out = []
    for item in payload.get("WeatherForecasts") or []:
        loc = item.get("location") or {}
        lat, lon = to_float(loc.get("lat")), to_float(loc.get("lon"))
        for fc in item.get("forecasts") or []:
            data = fc.get("data") or {}
            cond = data.get("cond")
            out.append(
                Observation(
                    source="tmd",
                    kind="rain_forecast",
                    station_id=f"{lat},{lon}",
                    name=name,
                    province=name,
                    lat=lat,
                    lon=lon,
                    observed_at=to_iso(fc.get("time")),
                    value=to_float(data.get("rain")),
                    unit="mm/h",
                    status=CONDITIONS.get(cond, str(cond) if cond is not None else None),
                    extra={"issued_at": now_th().isoformat(timespec="minutes")},
                )
            )
    return out


class TmdSource(Source):
    name = "tmd"
    description = "กรมอุตุนิยมวิทยา — พยากรณ์ฝนรายชั่วโมง + ภาพเรดาร์"

    def collect(self, hours: int = 48) -> CollectResult:
        result = CollectResult(self.name)
        if self.settings.tmd_token:
            url = f"{self.settings.tmd_nwp_base.rstrip('/')}/forecast/location/hourly/at"
            headers = {"authorization": f"Bearer {self.settings.tmd_token}", "accept": "application/json"}
            for name, lat, lon in parse_points(self.settings.tmd_points):
                try:
                    payload = self.get_json(
                        url, headers=headers,
                        params={"lat": lat, "lon": lon, "fields": "rain,cond", "duration": hours},
                    )
                    result.raw[f"forecast_{lat}_{lon}.json"] = payload
                    result.observations.extend(parse_forecast(payload, name))
                except Exception as exc:
                    result.errors.append(f"forecast {name}: {exc}")
        else:
            result.errors.append("ข้ามพยากรณ์: ยังไม่ได้ตั้ง TMD_API_TOKEN")

        try:
            resp = self.session.get(self.settings.tmd_radar_url, timeout=self.settings.timeout)
            resp.raise_for_status()
            ext = "gif" if "gif" in resp.headers.get("content-type", "") else "png"
            result.raw[f"radar.{ext}"] = resp.content
            result.reports.append(
                Report(
                    source="tmd",
                    kind="radar_image",
                    title="ภาพเรดาร์ฝนรวม (composite) ล่าสุด",
                    url=self.settings.tmd_radar_url,
                    published_at=now_th().isoformat(timespec="minutes"),
                )
            )
        except Exception as exc:
            result.errors.append(f"radar: {exc}")
        return result
