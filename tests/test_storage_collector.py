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
