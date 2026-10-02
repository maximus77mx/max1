"""โครงสร้างข้อมูลกลาง ที่ทุกแหล่งแปลงมาให้อยู่ในรูปเดียวกัน"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Observation:
    """ค่าตรวจวัดเชิงตัวเลข ณ จุด/สถานี และเวลาหนึ่ง (ฝน ระดับน้ำ น้ำในเขื่อน น้ำท่วมขัง ฯลฯ)"""

    source: str          # thaiwater | gistda | bma | tmd ...
    kind: str            # waterlevel | rain_24h | dam_storage | flood_area | street_flood | rain_forecast
    station_id: str
    observed_at: str     # ISO-8601 (เวลาไทย +07:00 ถ้าต้นทางไม่ระบุ)
    value: float | None
    unit: str
    name: str | None = None
    province: str | None = None
    amphoe: str | None = None
    tambon: str | None = None
    lat: float | None = None
    lon: float | None = None
    status: str | None = None   # ระดับสถานการณ์/สี/ข้อความสถานะจากต้นทาง
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Report:
    """ข้อมูลเชิงเอกสาร: รายงานสถานการณ์ ประกาศเตือนภัย ภาพเรดาร์ ฯลฯ"""

    source: str          # disaster | onwr | tmd
    kind: str            # situation_report | warning | radar_image
    title: str
    url: str
    published_at: str | None = None
    summary: str | None = None
    provinces: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)  # เช่น จังหวัด/อำเภอ/ครัวเรือน/ผู้เสียชีวิต

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CollectResult:
    source: str
    observations: list[Observation] = field(default_factory=list)
    reports: list[Report] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)  # ชื่อไฟล์ -> payload ดิบ (เก็บไว้ย้อนดู/แปลงใหม่)
    errors: list[str] = field(default_factory=list)
