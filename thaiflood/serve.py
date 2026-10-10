"""รันทุกอย่างในเครื่องเดียว: ดึงข้อมูลตามรอบ → สร้าง dashboard ใหม่ → เปิดหน้าเว็บให้คนใน LAN เข้าดู

    thaiflood serve                # http://localhost:8000
    thaiflood serve --port 8080 --every 10
"""

from __future__ import annotations

import functools
import logging
import socket
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .collector import collect
from .config import Settings
from .dashboard import write_dashboard
from .storage import Store

log = logging.getLogger("thaiflood")


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # ไม่ต้องพิมพ์ทุก request
        pass


def lan_address() -> str:
    """IP ของเครื่องในวง LAN (ให้คนอื่นในออฟฟิศเปิดดูได้)"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))  # ไม่ได้ส่งข้อมูลจริง แค่ให้ระบบเลือก interface
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def start_http(site_dir: Path, host: str, port: int) -> ThreadingHTTPServer:
    site_dir.mkdir(parents=True, exist_ok=True)
    handler = functools.partial(_QuietHandler, directory=str(site_dir))
    server = ThreadingHTTPServer((host, port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def serve(
    settings: Settings,
    host: str = "0.0.0.0",
    port: int = 8000,
    every_minutes: float = 10,
    days: int = 7,
    geo: bool = True,
    max_cycles: int | None = None,
) -> None:
    site = settings.data_dir / "site"
    server = start_http(site, host, port)
    print(f"เปิด dashboard ได้ที่ http://localhost:{port}/  (เครื่องอื่นใน LAN: http://{lan_address()}:{port}/)")
    print(f"ดึงข้อมูลทุก {every_minutes:g} นาที (แต่ละแหล่งตามรอบของตัวเอง) — กด Ctrl+C เพื่อหยุด")
    cycles = 0
    try:
        with Store(settings.db_path, settings.raw_dir) as store:
            while max_cycles is None or cycles < max_cycles:
                started = time.monotonic()
                summaries = collect(None, settings, store, respect_intervals=True)
                got = sum(s.observations + s.reports for s in summaries)
                if got or cycles == 0 or not (site / "index.html").exists():
                    write_dashboard(store, site / "index.html", geo=geo, days=days, settings=settings)
                    log.info("อัปเดต dashboard แล้ว (%d รายการใหม่)", got)
                cycles += 1
                if max_cycles is not None and cycles >= max_cycles:
                    break
                time.sleep(max(5.0, every_minutes * 60 - (time.monotonic() - started)))
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
