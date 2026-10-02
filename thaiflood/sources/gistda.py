"""GISTDA — พื้นที่น้ำท่วมจากภาพดาวเทียม (อัปเดตรายวัน)

ใช้ GISTDA API Gateway (ต้องสมัครรับ API key ฟรีที่ https://api-gateway.gistda.or.th
แล้วตั้ง env GISTDA_API_KEY) ผลลัพธ์เป็น GeoJSON FeatureCollection
ช่วงเวลาที่รองรับ: 1day, 3days, 7days, 30days
"""

from __future__ import annotations

import logging
import time
from typing import Any

from ..models import CollectResult, Observation
from ..utils import now_th, to_float, to_iso
from .base import Source

PERIODS = ("1day", "3days", "7days", "30days")
log = logging.getLogger("thaiflood")


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


# ฟิลด์ผลกระทบในข้อมูล H3 ของ GISTDA (รวมเป็นผลรวมรายตำบล)
IMPACT_KEYS = ("building", "hospital", "school", "length_road", "rice_area", "cassava_area", "maize_area",
               "sugarcane_area", "para_area", "palm_area", "population", "household")


def _feature_rai(props: dict[str, Any]) -> float | None:
    """พื้นที่ท่วม (ไร่) — รองรับทั้งข้อมูลรายตำบล (area_rai) และข้อมูลหกเหลี่ยม H3 (f_area + h3_area)"""
    rai = to_float(_pick(props, "area_rai", "rai", "AREA_RAI"))
    if rai is not None:
        return rai
    km2 = to_float(_pick(props, "area_km2", "area_sqkm"))
    if km2 is not None:
        return km2 * 625  # 1 ตร.กม. = 625 ไร่
    f_area = to_float(_pick(props, "f_area", "_area"))
    if f_area is None:
        return None
    # เดาหน่วยจากขนาดหกเหลี่ยม: H3 res 8 ≈ 0.74 ตร.กม. = 737,000 ตร.ม. = 460 ไร่
    ref = to_float(props.get("h3_area")) or f_area
    if ref > 10_000:
        return f_area / 1600  # ตารางเมตร → ไร่
    if ref < 5:
        return f_area * 625  # ตร.กม. → ไร่
    return f_area  # เป็นไร่อยู่แล้ว


class FloodAggregator:
    """รวม feature (เช่นหกเหลี่ยม H3 นับแสนชิ้น) เป็นค่ารายตำบลทีละหน้า ไม่ต้องเก็บทั้งหมดไว้ในหน่วยความจำ"""

    def __init__(self, period: str) -> None:
        self.period = period
        self.groups: dict[str, dict[str, Any]] = {}
        self.features = 0

    def add(self, features: list[dict[str, Any]]) -> None:
        for i, f in enumerate(features):
            self.features += 1
            props = f.get("properties") or {}
            code = _pick(props, "tb_idn", "tambon_code")
            key = str(code) if code else str(_pick(props, "_id", "id") or f.get("id") or f"{self.period}-{self.features}")
            g = self.groups.get(key)
            if g is None:
                g = self.groups[key] = {
                    "rai": None, "cells": 0, "lat": 0.0, "lon": 0.0, "n_xy": 0, "when": None,
                    "name": _pick(props, "tb_tn", "tambon"), "province": _pick(props, "pv_tn", "province", "pv_name"),
                    "amphoe": _pick(props, "ap_tn", "amphoe", "ap_name"), "impact": {},
                }
            rai = _feature_rai(props)
            if rai is not None:
                g["rai"] = (g["rai"] or 0) + rai
            g["cells"] += 1
            lat, lon = _centroid(f.get("geometry"))
            if lat is not None:
                g["lat"] += lat
                g["lon"] += lon
                g["n_xy"] += 1
            when = to_iso(_pick(props, "f_date", "date", "acq_date", "_createdAt"))
            if when and (g["when"] is None or when > g["when"]):
                g["when"] = when
            for k in IMPACT_KEYS:
                v = to_float(props.get(k))
                if v:
                    g["impact"][k] = g["impact"].get(k, 0) + v

    def observations(self) -> list[Observation]:
        fallback_time = now_th().replace(minute=0, second=0, microsecond=0).isoformat()
        out = []
        for key, g in self.groups.items():
            extra: dict[str, Any] = {"period": self.period, "cells": g["cells"]}
            extra.update({k: round(v, 2) for k, v in g["impact"].items()})
            out.append(
                Observation(
                    source="gistda",
                    kind="flood_area",
                    station_id=key,
                    observed_at=g["when"] or fallback_time,
                    value=round(g["rai"], 2) if g["rai"] is not None else None,
                    unit="rai",
                    name=g["name"],
                    province=g["province"],
                    amphoe=g["amphoe"],
                    tambon=g["name"],
                    lat=round(g["lat"] / g["n_xy"], 6) if g["n_xy"] else None,
                    lon=round(g["lon"] / g["n_xy"], 6) if g["n_xy"] else None,
                    extra=extra,
                )
            )
        return out


def parse_flood(payload: dict[str, Any], period: str = "1day") -> list[Observation]:
    agg = FloodAggregator(period)
    agg.add(payload.get("features") or [])
    return agg.observations()


class GistdaSource(Source):
    name = "gistda"
    description = "GISTDA — พื้นที่น้ำท่วมจากดาวเทียม (รายวัน, รวมรายตำบล)"
    _last_page: dict[str, Any] | None = None

    @property
    def page_size(self) -> int:
        return self.settings.gistda_page_size

    def _get_page(self, url: str, offset: int) -> dict[str, Any]:
        # ลิงก์ที่ API ส่งกลับมีรูปแบบ ?api_key=... จึงส่ง key ทั้งใน header และ query
        # skipGeometry: ไม่ต้องใช้รูปหกเหลี่ยม (ระบุตำแหน่งจากรหัสตำบล) ทำให้ตอบเร็วและเล็กลง (ถ้า API ไม่รองรับก็แค่ไม่สนใจ)
        params = {"limit": self.page_size, "offset": offset, "api_key": self.settings.gistda_api_key, "skipGeometry": "true"}
        resp = self.session.get(url, headers={"API-Key": self.settings.gistda_api_key}, params=params,
                                timeout=(self.settings.timeout[0], self.settings.gistda_read_timeout))
        resp.raise_for_status()
        page = resp.json()
        return page if isinstance(page, dict) else {"type": type(page).__name__}

    def fetch_aggregate(self, period: str) -> tuple[FloodAggregator, dict[str, Any], list[dict[str, Any]] | None]:
        """ดึงทุกหน้าแล้วรวมรายตำบล — คืน (aggregator, meta, features ถ้าน้อยพอจะเก็บเป็น raw)"""
        if period not in PERIODS:
            raise ValueError(f"period ต้องเป็นหนึ่งใน {PERIODS}")
        if not self.settings.gistda_api_key:
            raise RuntimeError("ยังไม่ได้ตั้ง GISTDA_API_KEY (สมัครที่ https://api-gateway.gistda.or.th)")
        url = f"{self.settings.gistda_base.rstrip('/')}/{period}"
        agg = FloodAggregator(period)
        keep: list[dict[str, Any]] | None = []
        started, offset, pages = time.monotonic(), 0, 0
        meta: dict[str, Any] = {}
        while True:
            page = self._get_page(url, offset)
            self._last_page = page
            pages += 1
            batch = page.get("features") or page.get("data") or []
            meta = {k: page[k] for k in ("numberMatched", "timeStamp") if k in page}
            agg.add(batch)
            if keep is not None:
                keep.extend(batch)
                if len(keep) > 5000:
                    keep = None  # ใหญ่เกินจะเก็บ raw ทั้งก้อน
            if len(batch) < self.page_size:
                break
            offset += len(batch)
            if time.monotonic() - started > self.settings.gistda_time_budget:
                meta["truncated"] = True
                break
        meta.update(pages=pages, features=agg.features, seconds=round(time.monotonic() - started))
        return agg, meta, keep

    def fetch(self, period: str = "1day") -> dict[str, Any]:
        _, _, features = self.fetch_aggregate(period)
        return {"type": "FeatureCollection", "features": features or []}

    def probe(self) -> list[str]:
        """ตรวจการตอบกลับของ API ทุกช่วงเวลา (สำหรับหาสาเหตุเมื่อได้ 0 พื้นที่) — ไม่พิมพ์ key"""
        lines = []
        url_base = self.settings.gistda_base.rstrip("/")
        key = self.settings.gistda_api_key or ""
        for period in PERIODS:
            for label, kw in (
                ("header", {"headers": {"API-Key": key}, "params": {"limit": 5}}),
                ("query", {"params": {"limit": 5, "api_key": key}}),
            ):
                try:
                    resp = self.session.get(f"{url_base}/{period}", timeout=self.settings.timeout, **kw)
                    info = f"{resp.status_code} {resp.headers.get('content-type', '')}"
                    try:
                        body = resp.json()
                    except ValueError:
                        lines.append(f"{period} [{label}] {info} — ไม่ใช่ JSON: {resp.text[:200]!r}")
                        continue
                    if isinstance(body, dict):
                        feats = body.get("features") or []
                        meta = {k: body[k] for k in ("numberMatched", "numberReturned", "timeStamp", "totalFeatures", "message", "error") if k in body}
                        links = [f"{l.get('rel')}:{l.get('title') or ''}" for l in body.get("links", []) if isinstance(l, dict)]
                        props = {k: (str(v)[:40] if v is not None else None) for k, v in (feats[0].get("properties") or {}).items()} if feats else {}
                        lines.append(f"{period} [{label}] {info} keys={list(body)[:10]} features={len(feats)} meta={meta} links={links} props={props}")
                    else:
                        lines.append(f"{period} [{label}] {info} — {type(body).__name__}")
                except Exception as exc:
                    lines.append(f"{period} [{label}] ผิดพลาด: {exc}")
        return [l.replace(key, "***") if key else l for l in lines]

    def collect(self, period: str = "1day") -> CollectResult:
        """ดึงช่วงล่าสุดก่อน ถ้าว่าง (ดาวเทียมยังไม่ผ่าน/ไม่มีท่วม) ขยายไปช่วงที่ยาวขึ้น"""
        result = CollectResult(self.name)
        empty = []
        for p in PERIODS[PERIODS.index(period):]:
            try:
                agg, meta, features = self.fetch_aggregate(p)
            except Exception as exc:
                result.errors.append(f"{p}: {exc}")
                break
            observations = agg.observations()
            if observations:
                result.observations = observations
                result.raw[f"summary_{p}.json"] = meta
                if features:
                    result.raw["flood_1day.geojson"] = {"type": "FeatureCollection", "features": features}  # dashboard วาด polygon จากไฟล์นี้
                if meta.get("truncated"):
                    result.errors.append(f"{p}: ดึงไม่ครบเพราะเกินเวลาที่กำหนด — ได้ {meta['features']:,} จาก {meta.get('numberMatched', '?'):,} รายการ")
                log.info("gistda %s: %s รายการ, %s หน้า, %s วินาที → %s ตำบล", p, meta["features"], meta["pages"], meta["seconds"], len(observations))
                break
            info = {k: meta[k] for k in ("numberMatched", "timeStamp") if k in meta}
            empty.append(f"{p}={info or 'ไม่มี feature'}")
        if empty and not result.observations:
            result.errors.append("API ตอบกลับ 0 พื้นที่ทุกช่วง: " + ", ".join(empty))
        elif empty:
            result.errors.append("ช่วงสั้นกว่าไม่มีข้อมูล ใช้ช่วงยาวขึ้นแทน: " + ", ".join(empty))
        return result
