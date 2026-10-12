import os
import urllib.request

from thaiflood import collector
from thaiflood.config import Settings, load_env_file
from thaiflood.models import CollectResult, Observation
from thaiflood.serve import serve, start_http
from thaiflood.utils import now_th


def test_env_file_loads_without_overriding(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('# comment\nTF_A=from-file\nexport TF_B="quoted"\nTF_C=from-file\n', encoding="utf-8")
    monkeypatch.delenv("TF_A", raising=False)
    monkeypatch.delenv("TF_B", raising=False)
    monkeypatch.setenv("TF_C", "already-set")
    load_env_file(env)
    assert os.environ["TF_A"] == "from-file" and os.environ["TF_B"] == "quoted" and os.environ["TF_C"] == "already-set"


def test_serve_builds_dashboard_and_http_serves_it(tmp_path, monkeypatch):
    class Src:
        def __init__(self, settings):
            pass

        def collect(self):
            return CollectResult("thaiwater", observations=[
                Observation("thaiwater", "rain_24h", "1", now_th().isoformat(), 12.0, "mm", lat=18.8, lon=99.0)])

    monkeypatch.setattr(collector, "SOURCES", {"thaiwater": Src})
    settings = Settings()
    settings.data_dir = tmp_path
    serve(settings, host="127.0.0.1", port=0, geo=False, max_cycles=1)
    index = tmp_path / "site" / "index.html"
    assert index.exists() and "thaiwater|rain_24h|1" in index.read_text(encoding="utf-8")

    server = start_http(tmp_path / "site", "127.0.0.1", 0)
    try:
        port = server.server_address[1]
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # localhost ไม่ผ่าน proxy
        with opener.open(f"http://127.0.0.1:{port}/index.html", timeout=5) as resp:
            assert resp.status == 200 and b"<!doctype html>" in resp.read(200)
    finally:
        server.shutdown()
