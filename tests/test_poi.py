import json
import os
import time

from thaiflood.poi import ensure_pois, parse_overpass, write_poi_layer

PAYLOAD = {"elements": [
    {"type": "node", "id": 1, "lat": 13.7649, "lon": 100.5383,
     "tags": {"amenity": "hospital", "name": "Rajavithi Hospital", "name:th": "โรงพยาบาลราชวิถี", "phone": "+66 2 206 2900;+66 2 354 8108"}},
    {"type": "way", "id": 2, "center": {"lat": 13.76491, "lon": 100.53829},  # อาคารเดียวกันแบบ way — ต้องตัดซ้ำ
     "tags": {"amenity": "hospital", "name:th": "โรงพยาบาลราชวิถี"}},
    {"type": "node", "id": 3, "lat": 13.75, "lon": 100.52, "tags": {"amenity": "police", "name": "สน.พญาไท", "contact:phone": "02 354 5000"}},
    {"type": "node", "id": 4, "lat": 13.74, "lon": 100.51, "tags": {"amenity": "fire_station"}},
    {"type": "node", "id": 5, "lat": 13.73, "lon": 100.50, "tags": {"amenity": "school", "name": "ไม่เกี่ยว"}},
]}


def test_parse_overpass_keeps_emergency_places_with_phone():
    rows = parse_overpass(PAYLOAD)
    assert rows == [
        ["h", "โรงพยาบาลราชวิถี", 13.7649, 100.5383, "+66 2 206 2900"],
        ["p", "สน.พญาไท", 13.75, 100.52, "02 354 5000"],
        ["f", "", 13.74, 100.51, None],
    ]


def test_ensure_pois_caches_and_falls_back(tmp_path):
    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return PAYLOAD

    class Ok:
        calls = 0

        def post(self, url, data=None, timeout=None):
            Ok.calls += 1
            assert "amenity" in data["data"]
            return Resp()

    class Down:
        def post(self, *a, **kw):
            raise ConnectionError("blocked")

    assert ensure_pois(tmp_path, "http://x", session=Down()) == []  # ไม่มีเน็ต + ไม่มีไฟล์เดิม
    assert len(ensure_pois(tmp_path, "http://x", session=Ok())) == 3
    assert len(ensure_pois(tmp_path, "http://x", session=Ok())) == 3 and Ok.calls == 1  # ยังไม่เก่า ใช้ไฟล์เดิม
    cache = tmp_path / "boundaries" / "poi.json"
    old = time.time() - 40 * 86400
    os.utime(cache, (old, old))
    assert len(ensure_pois(tmp_path, "http://x", session=Down())) == 3  # เก่าแต่ดึงใหม่ไม่ได้ — ใช้ของเดิม
    out = write_poi_layer(json.loads(cache.read_text(encoding="utf-8")), tmp_path / "site" / "geo")
    assert out and json.loads(out.read_text(encoding="utf-8"))[0][1] == "โรงพยาบาลราชวิถี"
    assert write_poi_layer([], tmp_path / "x") is None
