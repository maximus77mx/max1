import json
from pathlib import Path

from thaiflood.provinces import find_provinces
from thaiflood.sources.bma import parse_html_points, parse_json_points
from thaiflood.sources.bulletins import build_report, extract_metrics, find_bulletin_links, html_to_text
from thaiflood.sources.gistda import parse_flood
from thaiflood.sources.thaiwater import parse_dam, parse_rain, parse_waterlevel
from thaiflood.sources.tmd import parse_forecast, parse_points
from thaiflood.utils import parse_thai_date, to_float, to_iso

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def test_thaiwater_waterlevel():
    obs = parse_waterlevel(load("thaiwater_waterlevel.json"))
    assert len(obs) == 2
    first = obs[0]
    assert first.station_id == "101"
    assert first.name == "สะพานนวรัฐ"
    assert first.province == "เชียงใหม่" and first.tambon == "วัดเกต"
    assert first.value == 25.31 and first.unit == "m.MSL"
    assert first.status == "ล้นตลิ่ง/วิกฤต"
    assert first.observed_at == "2024-10-01T07:00:00+07:00"
    assert first.extra["min_bank"] == 25.20
    assert obs[1].status == "ปกติ"


def test_thaiwater_rain_and_dam():
    rain = parse_rain(load("thaiwater_rain.json"))
    assert [r.value for r in rain] == [125.5, 0.0]
    assert rain[0].amphoe == "แม่ริม"
    dam = parse_dam(load("thaiwater_dam.json"))
    assert dam[0].name == "เขื่อนภูมิพล"
    assert dam[0].value == 70.4 and dam[0].extra["storage_mcm"] == 9500.5
    assert dam[0].observed_at.startswith("2024-10-01")


def test_gistda_flood():
    obs = parse_flood(load("gistda_flood.geojson"))
    assert obs[0].province == "เชียงใหม่" and obs[0].value == 1520.5
    assert obs[0].lat is not None and 18.8 <= obs[0].lat <= 18.81
    assert obs[1].value == 1250  # 2 ตร.กม. -> 1250 ไร่
    assert obs[1].lat is None


def test_disaster_links_and_metrics():
    html = (FIX / "disaster_index.html").read_text(encoding="utf-8")
    links = find_bulletin_links(html, "https://www.disaster.go.th/th/list.php")
    assert [u for u, _ in links] == [
        "https://www.disaster.go.th/th/content-view.php?id=1",
        "https://www.disaster.go.th/upload/report.pdf",
    ]
    body = html_to_text((FIX / "disaster_report.html").read_text(encoding="utf-8"))
    assert "var x" not in body
    m = extract_metrics(body)
    assert m == {
        "provinces": 4, "districts": 18, "subdistricts": 75, "villages": 312,
        "households": 12345, "deaths": 3, "injured": 2,
    }
    rep = build_report("disaster", "situation_report", links[0][0], links[0][1], body)
    assert rep.published_at == "2024-10-01T00:00:00+07:00"
    assert rep.provinces == ["เชียงราย", "เชียงใหม่", "ลำพูน", "เลย"]


def test_find_provinces_ambiguous_words():
    assert find_provinces("ฝนไม่ตกเลย ตากผ้าได้") == []
    assert find_provinces("น้ำท่วม จ.ตาก และ กทม.") == ["ตาก", "กรุงเทพมหานคร"]


def test_bma_html_and_json():
    obs = parse_html_points((FIX / "bma_table.html").read_text(encoding="utf-8"))
    assert len(obs) == 2
    assert obs[0].name == "ถ.สุขุมวิท ซ.71" and obs[0].amphoe == "วัฒนา"
    assert obs[0].value == 15 and obs[0].status == "รถเล็กผ่านลำบาก"
    js = parse_json_points([{"id": "A1", "name": "แยกอโศก", "depth": "20", "lat": 13.73, "lng": 100.56}])
    assert js[0].station_id == "A1" and js[0].value == 20 and js[0].lon == 100.56


def test_tmd_forecast():
    obs = parse_forecast(load("tmd_forecast.json"), "กรุงเทพมหานคร")
    assert len(obs) == 2
    assert obs[0].value == 12.4 and obs[0].status == "ฝนฟ้าคะนอง"
    assert parse_points("ก:1.5:2;bad;ข:3:4") == [("ก", 1.5, 2.0), ("ข", 3.0, 4.0)]


def test_utils():
    assert to_float("1,234.5") == 1234.5
    assert to_float("๑๒") == 12
    assert to_float("-") is None
    assert to_iso("2567-10-01") == "2024-10-01T00:00:00+07:00"
    assert to_iso("2024-10-01T00:00:00Z") == "2024-10-01T00:00:00+00:00"
    dt = parse_thai_date("วันที่ ๓ ตุลาคม ๒๕๖๗ เวลา 08.30 น.")
    assert (dt.year, dt.month, dt.day, dt.hour, dt.minute) == (2024, 10, 3, 8, 30)
