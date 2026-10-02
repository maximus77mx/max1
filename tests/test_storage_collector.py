import json
from pathlib import Path

from thaiflood import collector
from thaiflood.cli import main
from thaiflood.config import Settings
from thaiflood.models import CollectResult, Observation, Report
from thaiflood.sources.thaiwater import ThaiWaterSource
from thaiflood.storage import Store

FIX = Path(__file__).parent / "fixtures"


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class FakeSession:
    """จำลอง requests.Session: เลือก fixture ตาม path ของ URL"""

    routes = {
        "waterlevel_load": "thaiwater_waterlevel.json",
        "rain_24h": "thaiwater_rain.json",
        "dam_daily": "thaiwater_dam.json",
        "thailand_main": "thaiwater_main.json",
    }

    def get(self, url, **kwargs):
        for key, fname in self.routes.items():
            if key in url:
                return FakeResponse(json.loads((FIX / fname).read_text(encoding="utf-8")))
        raise ConnectionError(f"no route for {url}")


def obs(value, at="2024-10-01T07:00:00+07:00"):
    return Observation("thaiwater", "rain_24h", "1", at, value, "mm", province="เชียงใหม่")


def test_store_upsert_is_idempotent(tmp_path):
    with Store(tmp_path / "db.sqlite3", tmp_path / "raw") as store:
        store.save(CollectResult("thaiwater", observations=[obs(10)], raw={"x.json": {"a": 1}}))
        store.save(CollectResult("thaiwater", observations=[obs(12)]))  # ค่าอัปเดตของเวลาเดิม
        store.save(CollectResult("thaiwater", observations=[obs(5, "2024-10-01T08:00:00+07:00")]))
        rows = store.query_observations(kind="rain_24h")
        assert [r["value"] for r in rows] == [5, 12]
        assert store.stats()[0]["n"] == 2
        assert store.query_observations(since="2024-10-01T07:30:00+07:00")[0]["value"] == 5
        assert list((tmp_path / "raw" / "thaiwater").glob("*/*_x.json"))

        store.save(CollectResult("disaster", reports=[Report("disaster", "situation_report", "t", "http://a", metrics={"deaths": 1})]))
        assert json.loads(store.query_reports()[0]["metrics"]) == {"deaths": 1}

        out = tmp_path / "out.csv"
        assert store.export_csv(out, province="เชียง") == 2
        assert out.read_text(encoding="utf-8-sig").startswith("source,kind")


def test_thaiwater_collect_with_fake_session():
    result = ThaiWaterSource(Settings(), session=FakeSession()).collect()
    assert not result.errors
    kinds = {o.kind for o in result.observations}
    assert kinds == {"waterlevel", "rain_24h", "dam_storage"}
    assert set(result.raw) == {"waterlevel.json", "rain_24h.json", "dam.json"}
    radar = {r.title: r for r in result.reports}
    assert radar["เรดาร์ สทิงพระ"].url == "https://api-v3.thaiwater.net/product/radar/stp/stp240_latest.gif"
    assert radar["เรดาร์ สทิงพระ"].published_at.startswith("2026-10-02T15:10")
    assert radar["เรดาร์ เชียงราย"].url == "https://example.org/cri.png"


def test_collect_isolates_failures(tmp_path, monkeypatch):
    class Boom:
        def __init__(self, settings):
            pass

        def collect(self):
            raise RuntimeError("down")

    class Ok(Boom):
        def collect(self):
            return CollectResult("ok", observations=[obs(1)])

    monkeypatch.setattr(collector, "SOURCES", {"boom": Boom, "ok": Ok})
    with Store(tmp_path / "db.sqlite3") as store:
        summaries = collector.collect(None, Settings(), store)
    assert [(s.source, s.observations, bool(s.errors)) for s in summaries] == [("boom", 0, True), ("ok", 1, False)]


def test_schedule_runs_each_source_on_its_interval(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(collector, "collect", lambda names, s, st: calls.append(sorted(names)))
    t = [0.0]
    settings = Settings()
    settings.data_dir = tmp_path
    collector.run_schedule(
        settings, {"fast": 10, "slow": 30}, max_cycles=4,
        sleep=lambda s: t.__setitem__(0, t[0] + s), clock=lambda: t[0],
    )
    assert calls == [["fast", "slow"], ["fast"], ["fast"], ["fast", "slow"]]


def test_cli_stats_and_import(tmp_path, capsys):
    report = tmp_path / "r.json"
    report.write_text(json.dumps({"source": "disaster", "kind": "situation_report", "title": "manual", "url": "pdf://1",
                                  "metrics": {"households": 10}}, ensure_ascii=False), encoding="utf-8")
    assert main(["--data-dir", str(tmp_path), "import-report", str(report)]) == 0
    assert main(["--data-dir", str(tmp_path), "stats"]) == 0
    assert main(["--data-dir", str(tmp_path), "collect", "nope"]) == 2
    assert main(["--data-dir", str(tmp_path), "latest"]) == 0
    assert "manual" in capsys.readouterr().out


def test_prune_removes_old_rows(tmp_path):
    from datetime import timedelta

    from thaiflood.utils import now_th

    old = (now_th() - timedelta(days=40)).isoformat()
    with Store(tmp_path / "db.sqlite3", tmp_path / "raw") as store:
        store.save(CollectResult("thaiwater", observations=[obs(1, old), obs(2, now_th().isoformat())]))
        (tmp_path / "raw" / "thaiwater" / "2000-01-01").mkdir(parents=True)
        assert store.prune(30) == (1, 1)
        assert [r["value"] for r in store.query_observations()] == [2]


def test_thaiwater_dam_falls_back_to_next_path():
    class Session(FakeSession):
        routes = {"waterlevel_load": "thaiwater_waterlevel.json", "rain_24h": "thaiwater_rain.json",
                  "thailand_main": "thaiwater_main.json"}

    settings = Settings()
    settings.thaiwater_dam_path = "/public/dam_daily,/public/thailand_main"
    result = ThaiWaterSource(settings, session=Session()).collect()
    assert not result.errors
    assert any(o.kind == "dam_storage" for o in result.observations)


def test_gistda_empty_reports_meta():
    from thaiflood.sources.gistda import GistdaSource

    class Session:
        def get(self, url, **kw):
            return FakeResponse({"type": "FeatureCollection", "features": [], "numberMatched": 0})

    settings = Settings()
    settings.gistda_api_key = "k"
    result = GistdaSource(settings, session=Session()).collect()
    assert result.observations == [] and "numberMatched" in result.errors[0]
    assert "30days" in result.errors[0]


def test_gistda_falls_back_to_longer_period():
    from thaiflood.sources.gistda import GistdaSource

    feature = json.loads((FIX / "gistda_flood.geojson").read_text(encoding="utf-8"))

    class Session:
        def get(self, url, **kw):
            return FakeResponse(feature if url.endswith("/7days") else {"features": []})

    settings = Settings()
    settings.gistda_api_key = "k"
    result = GistdaSource(settings, session=Session()).collect()
    assert len(result.observations) == 2 and result.observations[0].extra["period"] == "7days"
    assert "flood_1day.geojson" in result.raw


def test_gistda_probe_masks_key_and_reports_shape():
    from thaiflood.sources.gistda import GistdaSource

    class Resp(FakeResponse):
        status_code = 200
        headers = {"content-type": "application/geo+json"}
        text = ""

    class Session:
        def get(self, url, **kw):
            return Resp({"type": "FeatureCollection", "features": [], "numberMatched": 0,
                         "links": [{"rel": "self", "href": url + "?api_key=SECRET"}]})

    settings = Settings()
    settings.gistda_api_key = "SECRET"
    lines = GistdaSource(settings, session=Session()).probe()
    assert len(lines) == 8 and all("SECRET" not in l for l in lines)
    assert "numberMatched" in lines[0] and "features=0" in lines[0]


def test_respect_intervals_skips_recent_success(tmp_path, monkeypatch):
    calls = []

    class Src:
        def __init__(self, settings):
            pass

        def collect(self):
            calls.append(1)
            return CollectResult("thaiwater", observations=[obs(1)])

    monkeypatch.setattr(collector, "SOURCES", {"thaiwater": Src})
    with Store(tmp_path / "db.sqlite3") as store:
        collector.collect(None, Settings(), store, respect_intervals=True)
        collector.collect(None, Settings(), store, respect_intervals=True)  # ยังไม่ถึงรอบ
        collector.collect(None, Settings(), store)  # ไม่สนรอบ
    assert len(calls) == 2


def test_gistda_falls_back_to_request_variant_that_returns_data():
    from thaiflood.sources.gistda import GistdaSource

    cell = {"properties": {"tb_idn": "410415", "tb_tn": "ต.กุมภวาปี", "ap_tn": "อ.กุมภวาปี", "pv_tn": "จ.อุดรธานี",
                           "f_area": "19855.2", "h3_area": "121604.8", "building": "2"}}
    seen = []

    class Session:
        def get(self, url, params=None, **kw):
            seen.append(dict(params))
            if params.get("skipGeometry") or params["limit"] > 1000:
                return FakeResponse({"features": [], "numberMatched": 0})
            batch = [cell] * 2 if params["offset"] == 0 else [cell]
            return FakeResponse({"features": batch[: params["limit"]], "numberMatched": 3})

    settings = Settings()
    settings.gistda_api_key = "k"
    agg, meta, _ = GistdaSource(settings, session=Session()).fetch_aggregate("7days")
    assert meta["variant"] == {"limit": 1000} and agg.features == 2
    o = agg.observations()[0]
    assert (o.province, o.amphoe, o.name) == ("อุดรธานี", "กุมภวาปี", "กุมภวาปี")
    assert o.value == round(2 * 19855.2 / 1600, 2) and o.extra["building"] == 4
