import json
import re

from thaiflood.cli import main
from thaiflood.dashboard import build_payload, render
from thaiflood.models import CollectResult, Observation, Report
from thaiflood.storage import Store
from thaiflood.utils import now_th


def seed(store):
    t = now_th().replace(microsecond=0)
    store.save(CollectResult("thaiwater", observations=[
        Observation("thaiwater", "waterlevel", "101", t.isoformat(), 25.3, "m.MSL", name="สะพานนวรัฐ </script>",
                    province="เชียงใหม่", lat=18.78, lon=99.0, status="มาก", extra={"min_bank": 25.2, "agency": "x"}),
        Observation("thaiwater", "waterlevel", "101", t.replace(hour=(t.hour + 23) % 24).isoformat(), 24.9, "m.MSL", province="เชียงใหม่"),
        Observation("thaiwater", "rain_24h", "5", t.isoformat(), 80, "mm", province="ลำพูน"),
    ]))
    store.save(CollectResult("disaster", reports=[Report("disaster", "situation_report", "รายงาน", "http://a", provinces=["เชียงใหม่"])]))


def test_payload_groups_series_per_station(tmp_path):
    with Store(tmp_path / "db.sqlite3") as store:
        seed(store)
        p = build_payload(store, days=3)
        assert len(p["stations"]) == 2
        wl = next(s for s in p["stations"] if s["kind"] == "waterlevel")
        assert wl["name"].startswith("สะพานนวรัฐ") and wl["extra"] == {"min_bank": 25.2}
        assert len(p["series"][wl["k"]]) == 2
        assert p["reports"][0]["provinces"] == ["เชียงใหม่"]
        assert len(build_payload(store, province="ลำพูน")["stations"]) == 1


def test_render_embeds_json_safely(tmp_path):
    with Store(tmp_path / "db.sqlite3") as store:
        seed(store)
        html = render(build_payload(store))
    assert "/*__DATA__*/" not in html
    assert html.count("</script>") == html.count("<script")  # ชื่อที่มี </script> ต้องไม่ปิดแท็กก่อนเวลา
    data = json.loads(re.search(r"const DATA = (.*?);\n", html).group(1).replace("<\\/", "</"))
    assert len(data["stations"]) == 2


def test_cli_dashboard(tmp_path):
    out = tmp_path / "d.html"
    assert main(["--data-dir", str(tmp_path), "dashboard", str(out), "--no-geo"]) == 0
    assert out.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_map_config_only_when_configured(tmp_path):
    from thaiflood.config import Settings

    s = Settings()
    s.sphere_api_key = None
    s.sphere_flood_wms_url = None
    with Store(tmp_path / "db.sqlite3") as store:
        assert build_payload(store, settings=s)["map"] == {}
        s.sphere_api_key = "abc"
        s.sphere_flood_wms_url = "https://example/wms"
        cfg = build_payload(store, settings=s)["map"]
    assert cfg["sphere"]["key"] == "abc" and "{layer}" in cfg["sphere"]["url"]
    assert cfg["flood_wms"]["url"] == "https://example/wms"
