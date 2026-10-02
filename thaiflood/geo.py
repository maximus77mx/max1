"""ขอบเขตการปกครอง (จังหวัด/ตำบล) สำหรับแผนที่ระบายสีรายพื้นที่

- ดาวน์โหลด GeoJSON ขอบเขตครั้งแรกแล้วเก็บไว้ใน data/boundaries/ (ใช้ซ้ำทุกรอบ)
- หาว่าจุด (สถานี) อยู่ในตำบลไหนด้วย point-in-polygon + grid index (ไม่ต้องพึ่ง shapely)
- ย่อรูปทรง (Douglas–Peucker + ปัดทศนิยม) แล้วแยกไฟล์รายจังหวัด ให้หน้าเว็บโหลดเฉพาะจังหวัดที่ดู

ค่าเริ่มต้นใช้ชุดข้อมูลเปิดจาก github.com/chingchai/OpenGISData-Thailand
(property: tam_code/tam_th/amp_th/pro_code/pro_th/area_sqkm) — เปลี่ยนได้ที่ TAMBON_GEOJSON_URL / PROVINCE_GEOJSON_URL
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import requests

RAI_PER_SQKM = 625


def _download(url: str, dest: Path, timeout: float = 120) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    tmp = dest.with_suffix(".part")
    tmp.write_bytes(resp.content)
    tmp.replace(dest)
    return dest


def ensure_boundaries(data_dir: Path, tambon_url: str, province_url: str) -> tuple[Path, Path]:
    folder = data_dir / "boundaries"
    tambon, province = folder / "tambon.geojson", folder / "province.geojson"
    if not tambon.exists():
        _download(tambon_url, tambon)
    if not province.exists():
        _download(province_url, province)
    return tambon, province


# ---------- geometry ----------
def _polygons(geometry: dict[str, Any] | None) -> list[list[list[list[float]]]]:
    if not geometry:
        return []
    if geometry.get("type") == "Polygon":
        return [geometry["coordinates"]]
    if geometry.get("type") == "MultiPolygon":
        return geometry["coordinates"]
    return []


def _bbox(polys: list) -> tuple[float, float, float, float]:
    xs = [p[0] for poly in polys for p in poly[0]]
    ys = [p[1] for poly in polys for p in poly[0]]
    return min(xs), min(ys), max(xs), max(ys)


def _in_ring(x: float, y: float, ring: list[list[float]]) -> bool:
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def point_in_polygons(x: float, y: float, polys: list) -> bool:
    for poly in polys:
        if _in_ring(x, y, poly[0]) and not any(_in_ring(x, y, hole) for hole in poly[1:]):
            return True
    return False


def _rdp(points: list[list[float]], tol: float) -> list[list[float]]:
    """Douglas–Peucker แบบวนซ้ำ (ไม่ recursive เพื่อไม่ชน recursion limit กับเส้นยาว)"""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        ax, ay = points[a][0], points[a][1]
        bx, by = points[b][0], points[b][1]
        dx, dy = bx - ax, by - ay
        norm = math.hypot(dx, dy) or 1e-12
        best, idx = -1.0, -1
        for i in range(a + 1, b):
            d = abs(dy * points[i][0] - dx * points[i][1] + bx * ay - by * ax) / norm
            if d > best:
                best, idx = d, i
        if best > tol and idx > 0:
            keep[idx] = True
            stack += [(a, idx), (idx, b)]
    return [p for p, k in zip(points, keep) if k]


def simplify_geometry(geometry: dict[str, Any], tol: float, digits: int) -> dict[str, Any] | None:
    out = []
    for poly in _polygons(geometry):
        rings = []
        for k, ring in enumerate(poly):
            pts = _rdp(ring, tol)
            if len(pts) < 4:
                if k == 0:
                    pts = ring  # รูปเล็กกว่าค่าความคลาดเคลื่อน — คงรูปเดิมไว้ ไม่ให้ตำบลหาย
                else:
                    continue
            rings.append([[round(p[0], digits), round(p[1], digits)] for p in pts])
        if rings:
            out.append(rings)
    if not out:
        return None
    return {"type": "MultiPolygon", "coordinates": out}


# ---------- index ----------
class TambonIndex:
    """หา tam_code จากพิกัด (grid 0.25°) และเก็บข้อมูลประกอบของแต่ละตำบล"""

    CELL = 0.25

    def __init__(self, features: Iterable[dict[str, Any]]) -> None:
        self.meta: dict[str, dict[str, Any]] = {}
        self.shapes: dict[str, tuple[tuple[float, float, float, float], list]] = {}
        self.grid: dict[tuple[int, int], list[str]] = defaultdict(list)
        for f in features:
            p = f.get("properties") or {}
            code = str(p.get("tam_code") or "")
            polys = _polygons(f.get("geometry"))
            if not code or not polys:
                continue
            bbox = _bbox(polys)
            self.shapes[code] = (bbox, polys)
            area = p.get("area_sqkm")
            self.meta[code] = {
                "tc": code, "t": p.get("tam_th"), "a": p.get("amp_th"), "p": p.get("pro_th"),
                "pc": str(p.get("pro_code") or code[:2]),
                "ac": str(p.get("amp_code") or code[:4]),
                "rai": round(area * RAI_PER_SQKM) if isinstance(area, (int, float)) else None,
            }
            for gx in range(int(bbox[0] // self.CELL), int(bbox[2] // self.CELL) + 1):
                for gy in range(int(bbox[1] // self.CELL), int(bbox[3] // self.CELL) + 1):
                    self.grid[(gx, gy)].append(code)

    def rai_by_province(self) -> dict[str, int]:
        out: dict[str, int] = defaultdict(int)
        for m in self.meta.values():
            out[m["pc"]] += m["rai"] or 0
        return dict(out)

    def search_list(self) -> dict[str, Any]:
        """รายชื่อตำบลทั้งประเทศแบบกระชับสำหรับช่องค้นหาในหน้าเว็บ (ชื่ออำเภอ/จังหวัดเก็บครั้งเดียว)

        {"p": {pro_code: ชื่อจังหวัด}, "a": {amp_code: [ชื่ออำเภอ, pro_code]}, "t": [[tam_code, ชื่อตำบล, amp_code, ไร่]]}
        """
        prov: dict[str, str] = {}
        amp: dict[str, list[str]] = {}
        rows = []
        for m in sorted(self.meta.values(), key=lambda m: m["tc"]):
            prov[m["pc"]] = m["p"]
            amp.setdefault(m["ac"], [m["a"], m["pc"]])
            rows.append([m["tc"], m["t"], m["ac"], m["rai"]])
        return {"p": prov, "a": amp, "t": rows}

    @classmethod
    def from_file(cls, path: Path) -> "TambonIndex":
        return cls(json.loads(path.read_text(encoding="utf-8")).get("features") or [])

    def lookup(self, lat: float | None, lon: float | None) -> str | None:
        if lat is None or lon is None:
            return None
        for code in self.grid.get((int(lon // self.CELL), int(lat // self.CELL)), ()):
            (x0, y0, x1, y1), polys = self.shapes[code]
            if x0 <= lon <= x1 and y0 <= lat <= y1 and point_in_polygons(lon, lat, polys):
                return code
        return None


def tambon_code_for(station: dict[str, Any], index: TambonIndex) -> str | None:
    """GISTDA ส่งรหัสตำบลมาเป็น station_id อยู่แล้ว ที่เหลือหาจากพิกัด"""
    sid = str(station.get("id") or "")
    if station.get("src") == "gistda" and sid in index.meta:
        return sid
    return index.lookup(station.get("lat"), station.get("lon"))


# ---------- output for the web page ----------
def province_layer(
    path: Path, rai_by_code: dict[str, int] | None = None, tol: float = 0.015, digits: int = 3
) -> dict[str, Any]:
    """ขอบเขตจังหวัดแบบหยาบ (~1.5 กม.) ฝังในหน้าเว็บได้ ใช้เป็นภาพรวมทั้งประเทศ"""
    data = json.loads(path.read_text(encoding="utf-8"))
    features = []
    for f in data.get("features") or []:
        p = f.get("properties") or {}
        geom = simplify_geometry(f.get("geometry") or {}, tol, digits)
        if geom:
            pc = str(p.get("pro_code"))
            props = {"pc": pc, "p": p.get("pro_th"), "rai": (rai_by_code or {}).get(pc)}
            features.append({"type": "Feature", "properties": props, "geometry": geom})
    return {"type": "FeatureCollection", "features": features}


def write_tambon_layers(tambon_path: Path, out_dir: Path, tol: float = 0.0008, digits: int = 4) -> int:
    """เขียน geo/tambon_<pro_code>.json รายจังหวัด (ย่อรูป ~90 ม.) ให้หน้าเว็บโหลดเมื่อเลือกจังหวัด"""
    data = json.loads(tambon_path.read_text(encoding="utf-8"))
    by_prov: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for f in data.get("features") or []:
        p = f.get("properties") or {}
        geom = simplify_geometry(f.get("geometry") or {}, tol, digits)
        if geom and p.get("tam_code"):
            by_prov[str(p.get("pro_code") or str(p["tam_code"])[:2])].append(
                {"type": "Feature", "properties": {"tc": str(p["tam_code"])}, "geometry": geom}
            )
    out_dir.mkdir(parents=True, exist_ok=True)
    for pc, feats in by_prov.items():
        (out_dir / f"tambon_{pc}.json").write_text(
            json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":")), encoding="utf-8"
        )
    return len(by_prov)
