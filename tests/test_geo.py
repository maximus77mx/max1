import json
from pathlib import Path

from thaiflood.dashboard import build_payload
from thaiflood.geo import TambonIndex, province_layer, simplify_geometry, tambon_code_for, write_tambon_layers
from thaiflood.models import CollectResult, Observation
from thaiflood.storage import Store
from thaiflood.utils import now_th

FIX = Path(__file__).parent / "fixtures" / "tambon_small.geojson"


def test_lookup_respects_holes_and_bbox():
    idx = TambonIndex.from_file(FIX)
    assert idx.lookup(18.78, 99.0) == "500105"
    assert idx.lookup(18.785, 99.025) == "500106"
    assert idx.lookup(18.7775, 99.0175) is None  # อยู่ในรู (hole) ของ 500106
    assert idx.lookup(15.0, 100.0) is None and idx.lookup(None, 99.0) is None
    assert idx.meta["500105"]["rai"] == 1250 and idx.rai_by_province() == {"50": 3750}


def test_gistda_station_uses_its_tambon_code():
    idx = TambonIndex.from_file(FIX)
    assert tambon_code_for({"src": "gistda", "id": "500106", "lat": 0, "lon": 0}, idx) == "500106"
    assert tambon_code_for({"src": "thaiwater", "id": "x", "lat": 18.78, "lon": 99.0}, idx) == "500105"


def test_simplify_keeps_small_shapes_and_rounds():
    geom = {"type": "Polygon", "coordinates": [[[0, 0], [0.00001, 0], [0.00001, 0.00001], [0, 0]]]}
    out = simplify_geometry(geom, tol=1, digits=4)
    assert out["type"] == "MultiPolygon" and len(out["coordinates"][0][0]) == 4


def test_tambon_files_and_payload(tmp_path):
    assert write_tambon_layers(FIX, tmp_path / "geo") == 1
    data = json.loads((tmp_path / "geo" / "tambon_50.json").read_text(encoding="utf-8"))
    assert {f["properties"]["tc"] for f in data["features"]} == {"500105", "500106"}
    prov = province_layer(FIX, {"50": 3750})  # ใช้ไฟล์ตำบลแทนจังหวัดก็ได้ ขอแค่มี pro_code
    assert prov["features"][0]["properties"]["rai"] == 3750

    idx = TambonIndex.from_file(FIX)
    t = now_th().isoformat()
    with Store(tmp_path / "db.sqlite3") as store:
        store.save(CollectResult("x", observations=[
            Observation("thaiwater", "rain_24h", "r1", t, 50, "mm", lat=18.78, lon=99.0, province="เชียงใหม่"),
            Observation("thaiwater", "rain_24h", "r2", t, 5, "mm", lat=10.0, lon=99.0),
        ]))
        p = build_payload(store, tambon_index=idx, province_geo=prov)
    tcs = {s["id"]: s.get("tc") for s in p["stations"]}
    assert tcs == {"r1": "500105", "r2": None}
    assert set(p["tambons"]) == {"500105"} and p["geo_base"] == "geo/"


def test_search_list_is_compact():
    sl = TambonIndex.from_file(FIX).search_list()
    assert sl["p"] == {"50": "เชียงใหม่"}
    assert sl["a"] == {"5001": ["เมืองเชียงใหม่", "50"]}
    assert sl["t"] == [["500105", "ช้างคลาน", "5001", 1250], ["500106", "วัดเกต", "5001", 2500]]
