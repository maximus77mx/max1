"""สร้าง Interactive Standalone HTML (ไฟล์เดียว) จากข้อมูลใน Store

ข้อมูลถูกฝังเป็น JSON ในไฟล์ จึงเปิดดูได้ทันที/ส่งต่อทางอีเมลหรือแชตได้
(แผนที่พื้นหลังและไลบรารี Leaflet โหลดจาก CDN — ส่วนอื่นทำงานได้แม้ออฟไลน์)
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from importlib import resources
from pathlib import Path
from typing import Any

from .config import Settings
from .geo import TambonIndex, ensure_boundaries, province_layer, tambon_code_for, write_tambon_layers
from .storage import Store
from .utils import now_th

# ฟิลด์ใน extra ที่หน้า dashboard ใช้ (ตัดที่เหลือทิ้งเพื่อให้ไฟล์เล็ก)
_EXTRA_KEYS = ("min_bank", "ground_level", "storage_mcm", "inflow_mcm", "released_mcm", "river", "storage_percent",
               # ผลกระทบในพื้นที่ท่วม (GISTDA)
               "cells", "period", "building", "hospital", "school", "length_road", "rice_area", "cassava_area",
               "maize_area", "sugarcane_area", "para_area", "palm_area", "population", "household")


def _latest_geojson(raw_dir: Path | None) -> dict[str, Any] | None:
    if not raw_dir:
        return None
    files = sorted((raw_dir / "gistda").glob("*/*_flood_1day.geojson"))
    if not files:
        return None
    try:
        return json.loads(files[-1].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _latest_radar(store: Store) -> list[dict[str, Any]]:
    """ภาพเรดาร์ล่าสุดของแต่ละสถานี (ชื่อเดียวกัน = สถานีเดียวกัน)"""
    latest: dict[str, dict[str, Any]] = {}
    for r in store.query_reports(kind="radar_image", limit=500):
        key = r["title"]
        when = r["published_at"] or r["collected_at"]
        if key not in latest or when > latest[key]["t"]:
            latest[key] = {"title": r["title"], "url": r["url"], "t": when}
    return sorted(latest.values(), key=lambda x: x["title"])


def map_config(settings: Settings) -> dict[str, Any]:
    """ค่าที่หน้าเว็บใช้สร้างแผนที่ (key ของ sphere ต้องอยู่ในหน้าเว็บ เพราะเบราว์เซอร์เป็นผู้โหลด tile)"""
    cfg: dict[str, Any] = {}
    if settings.sphere_api_key:
        cfg["sphere"] = {"key": settings.sphere_api_key, "url": settings.sphere_tile_url}
    if settings.sphere_flood_wms_url:
        cfg["flood_wms"] = {
            "url": settings.sphere_flood_wms_url,
            "layers": settings.sphere_flood_wms_layers or "",
            "key": settings.sphere_api_key or "",
        }
    return cfg


def build_payload(
    store: Store,
    days: int = 7,
    province: str | None = None,
    note: str | None = None,
    settings: Settings | None = None,
    tambon_index: TambonIndex | None = None,
    province_geo: dict[str, Any] | None = None,
) -> dict[str, Any]:
    since = (now_th() - timedelta(days=days)).isoformat()
    rows = store.query_observations(since=since, province=province)
    rows.sort(key=lambda r: r["observed_at"])

    stations: dict[str, dict[str, Any]] = {}
    series: dict[str, list[list[Any]]] = {}
    for r in rows:
        key = f"{r['source']}|{r['kind']}|{r['station_id']}"
        st = stations.get(key)
        if st is None:
            st = stations[key] = {"k": key, "src": r["source"], "kind": r["kind"], "id": r["station_id"], "unit": r["unit"]}
            series[key] = []
        # ข้อมูลเชิงที่ตั้งใช้ค่าล่าสุดที่มี (แถวเรียงเก่า→ใหม่)
        for col, short in (("name", "name"), ("province", "prov"), ("amphoe", "amp"), ("lat", "lat"), ("lon", "lon")):
            if r[col] not in (None, ""):
                st[short] = r[col]
        if r["extra"]:
            extra = json.loads(r["extra"])
            kept = {k: extra[k] for k in _EXTRA_KEYS if extra.get(k) is not None}
            if kept:
                st["extra"] = kept
        series[key].append([r["observed_at"], r["value"], r["status"]])

    # ผูกแต่ละสถานีเข้ากับตำบล เพื่อให้หน้าเว็บรวมค่ารายตำบล/จังหวัดตามตัวกรองเวลาได้เอง
    tambons: dict[str, dict[str, Any]] = {}
    if tambon_index:
        for st in stations.values():
            code = tambon_code_for(st, tambon_index)
            if code:
                st["tc"] = code
                tambons[code] = tambon_index.meta[code]

    reports = []
    for r in store.query_reports(limit=200, exclude_kind="radar_image"):
        reports.append(
            {
                "source": r["source"], "kind": r["kind"], "title": r["title"], "url": r["url"],
                "published_at": r["published_at"] or r["collected_at"],
                "provinces": json.loads(r["provinces"] or "[]"),
                "metrics": json.loads(r["metrics"] or "{}"),
            }
        )

    return {
        "generated_at": now_th().isoformat(timespec="minutes"),
        "since": since,
        "days": days,
        "province": province,
        "note": note,
        "stations": list(stations.values()),
        "series": series,
        "reports": reports,
        "flood_geojson": _latest_geojson(store.raw_dir),
        "map": map_config(settings or Settings()),
        "radar": _latest_radar(store),
        "tambons": tambons,
        "tambon_list": tambon_index.search_list() if tambon_index else [],
        "province_geo": province_geo,
        "geo_base": "geo/" if tambon_index else None,
    }


def render(payload: dict[str, Any]) -> str:
    template = resources.files("thaiflood").joinpath("dashboard_template.html").read_text(encoding="utf-8")
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return template.replace("/*__DATA__*/null", data)


def write_dashboard(store: Store, output: Path, geo: bool = True, **kwargs: Any) -> Path:
    """geo=True: เพิ่มแผนที่ระบายสีรายจังหวัด/ตำบล — ขอบเขตจังหวัดฝังในหน้า ส่วนตำบลเขียนเป็นไฟล์ geo/ ข้างไฟล์ html"""
    settings = kwargs.get("settings") or Settings()
    if geo:
        try:
            tambon_path, province_path = ensure_boundaries(
                settings.data_dir, settings.tambon_geojson_url, settings.province_geojson_url
            )
            index = TambonIndex.from_file(tambon_path)
            kwargs["tambon_index"] = index
            kwargs["province_geo"] = province_layer(province_path, index.rai_by_province())
            write_tambon_layers(tambon_path, output.parent / "geo")
        except Exception as exc:  # ไม่มีเน็ต/URL เปลี่ยน — ยังสร้างหน้าได้ แค่ไม่มีแผนที่รายพื้นที่
            print(f"ข้ามแผนที่รายตำบล: {exc}")
    payload = build_payload(store, **kwargs)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(payload), encoding="utf-8")
    return output


def default_output_name() -> str:
    return f"thaiflood_{datetime.now().strftime('%Y%m%d_%H%M')}.html"
