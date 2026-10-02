"""ค่าตั้งต้นของแต่ละแหล่งข้อมูล

ทุก URL override ได้ด้วย environment variable (ชื่ออยู่ในวงเล็บ) เพราะหน่วยงานรัฐ
เปลี่ยน path ของ API/หน้าเว็บบ่อย — แก้ผ่าน env ได้โดยไม่ต้องแก้โค้ด
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(_env("THAIFLOOD_DATA_DIR", "data")))
    # (connect, read) — เว็บที่บล็อก IP ต่างประเทศมักค้างที่ขั้น connect จึงตัดเร็ว
    timeout: tuple[float, float] = (
        float(_env("THAIFLOOD_CONNECT_TIMEOUT", "10")),
        float(_env("THAIFLOOD_TIMEOUT", "30")),
    )
    user_agent: str = _env(
        "THAIFLOOD_USER_AGENT",
        "thaiflood-collector/0.1 (+https://github.com/maximus77mx/max1)",
    )

    # --- ThaiWater (สสน.) — API สาธารณะที่หน้าเว็บ thaiwater.net ใช้เอง ---
    thaiwater_base: str = _env(
        "THAIWATER_BASE", "https://api-v3.thaiwater.net/api/v1/thaiwater30"
    )
    thaiwater_waterlevel_path: str = _env("THAIWATER_WATERLEVEL_PATH", "/public/waterlevel_load")
    thaiwater_rain_path: str = _env("THAIWATER_RAIN_PATH", "/public/rain_24h")
    # ลองตามลำดับจนเจอ path ที่ตอบกลับ (คั่นด้วย ,) — thailand_main มีข้อมูลเขื่อนอยู่ใน dam_data
    thaiwater_main_path: str = _env("THAIWATER_MAIN_PATH", "/public/thailand_main")
    # ฐานของลิงก์ภาพที่เป็น path สัมพัทธ์ (ภาพเรดาร์ ฯลฯ)
    thaiwater_media_base: str = _env("THAIWATER_MEDIA_BASE", "https://api-v3.thaiwater.net/")
    thaiwater_dam_path: str = _env("THAIWATER_DAM_PATH", "/public/dam_daily,/public/dam_load,/public/thailand_main")
    # กราฟย้อนหลังรายสถานี (historical) — {station_id}, {start}, {end} จะถูกแทนค่า
    thaiwater_waterlevel_graph_path: str = _env(
        "THAIWATER_WATERLEVEL_GRAPH_PATH",
        "/public/waterlevel_graph?station_type=tele_waterlevel"
        "&station_id={station_id}&start_date={start}&end_date={end}",
    )

    # --- GISTDA — พื้นที่น้ำท่วมจากดาวเทียม (ต้องขอ API key ที่ api-gateway.gistda.or.th) ---
    gistda_base: str = _env("GISTDA_BASE", "https://api-gateway.gistda.or.th/api/2.0/resources/features/flood")
    gistda_api_key: str | None = _env("GISTDA_API_KEY")
    gistda_page_size: int = int(_env("GISTDA_PAGE_SIZE", "5000"))
    gistda_read_timeout: float = float(_env("GISTDA_READ_TIMEOUT", "120"))
    gistda_time_budget: float = float(_env("GISTDA_TIME_BUDGET", "900"))  # วินาที — ข้อมูล 7 วันมีได้เป็นแสนรายการ

    # --- ปภ. — รายงานสถานการณ์สาธารณภัยรายวัน ---
    disaster_url: str = _env("DISASTER_URL", "https://www.disaster.go.th/th/sub-news-category-01.php")

    # --- สทนช. — ประกาศเตือนภัย ---
    onwr_url: str = _env("ONWR_URL", "https://www.onwr.go.th/?cat=37")

    # --- สำนักการระบายน้ำ กทม. — จุดน้ำท่วมขังรายจุด ---
    bma_url: str = _env("BMA_DDS_URL", "https://dds.bangkok.go.th/Floodmon/")

    # --- กรมอุตุนิยมวิทยา — NWP API (ต้องขอ token ที่ data.tmd.go.th) ---
    tmd_nwp_base: str = _env("TMD_NWP_BASE", "https://data.tmd.go.th/nwpapi/v1")
    tmd_token: str | None = _env("TMD_API_TOKEN")
    # URL ภาพเรดาร์ (ไม่ตั้ง = ไม่ดึง) เช่นลิงก์ภาพ composite ล่าสุดจากหน้าเรดาร์ของกรมอุตุฯ
    tmd_radar_url: str | None = _env("TMD_RADAR_URL")
    # --- GISTDA sphere — แผนที่พื้นหลังภาษาไทย + ชั้นข้อมูลบนหน้า dashboard ---
    # key นี้ถูกฝังในหน้าเว็บ (เบราว์เซอร์เป็นผู้โหลดแผนที่) ควรจำกัดโดเมนที่ใช้ key ได้ในหน้าจัดการ key
    sphere_api_key: str | None = _env("SPHERE_API_KEY")
    sphere_tile_url: str = _env(
        "SPHERE_TILE_URL",
        "https://basemap.sphere.gistda.or.th/tiles/{layer}/EPSG3857/{z}/{x}/{y}.{ext}?key={key}",
    )
    # ชั้นน้ำท่วมแบบ WMS (ใส่ URL และชื่อ layer จากเอกสาร sphere/GISTDA) — ไม่ตั้ง = ไม่แสดง
    sphere_flood_wms_url: str | None = _env("SPHERE_FLOOD_WMS_URL")
    sphere_flood_wms_layers: str | None = _env("SPHERE_FLOOD_WMS_LAYERS")

    # --- ขอบเขตการปกครองสำหรับแผนที่ระบายสีรายจังหวัด/ตำบล (GeoJSON, property แบบ tam_code/tam_th/pro_code) ---
    tambon_geojson_url: str = _env(
        "TAMBON_GEOJSON_URL",
        "https://raw.githubusercontent.com/chingchai/OpenGISData-Thailand/master/subdistricts.geojson",
    )
    province_geojson_url: str = _env(
        "PROVINCE_GEOJSON_URL",
        "https://raw.githubusercontent.com/chingchai/OpenGISData-Thailand/master/provinces.geojson",
    )

    # จุดพยากรณ์ฝน: "ชื่อ:lat:lon;ชื่อ:lat:lon"
    tmd_points: str = _env(
        "TMD_POINTS",
        "กรุงเทพมหานคร:13.7563:100.5018;เชียงใหม่:18.7883:98.9853;"
        "อุบลราชธานี:15.2287:104.8564;หาดใหญ่:7.0086:100.4747;"
        "นครสวรรค์:15.7047:100.1372;อยุธยา:14.3532:100.5689",
    )

    @property
    def db_path(self) -> Path:
        return self.data_dir / "thaiflood.sqlite3"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"


# รอบการดึงข้อมูลเริ่มต้น (วินาที) — ใช้โดย `thaiflood schedule`
DEFAULT_INTERVALS: dict[str, int] = {
    "thaiwater": 60 * 60,      # รายชั่วโมง
    "tmd": 3 * 60 * 60,        # พยากรณ์อัปเดตทุก ~3 ชม.
    "bma": 30 * 60,            # จุดน้ำท่วมขัง กทม. เปลี่ยนเร็วช่วงฝนตก
    "onwr": 3 * 60 * 60,
    "gistda": 12 * 60 * 60,    # ภาพดาวเทียมรายวัน (ข้อมูล 7 วันเป็นแสนรายการ — ไม่ดึงถี่)
    "disaster": 12 * 60 * 60,  # รายงาน ปภ. ออกวันละ 1–2 ครั้ง
}
