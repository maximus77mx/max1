"""สั่งดึงข้อมูลจากหลายแหล่งแล้วบันทึกลง Store + ตัวตั้งเวลาแบบง่าย (ไม่ต้องลง cron/celery)"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime

from .config import DEFAULT_INTERVALS, Settings
from .sources import SOURCES
from .storage import Store
from .utils import now_th

log = logging.getLogger("thaiflood")


@dataclass
class RunSummary:
    source: str
    observations: int
    reports: int
    errors: list[str]


def is_due(name: str, store: Store, intervals: dict[str, int] | None = None) -> bool:
    """ถึงรอบหรือยัง — นับจากรอบล่าสุดที่ได้ข้อมูลจริง (รอบที่ล้มเหลวจะลองใหม่ทันทีรอบถัดไป)"""
    last = store.last_success(name)
    if not last:
        return True
    every = (intervals or DEFAULT_INTERVALS).get(name, 0)
    elapsed = (now_th() - datetime.fromisoformat(last)).total_seconds()
    return elapsed >= every - 5 * 60  # เผื่อ 5 นาที ให้ cron ที่คลาดเล็กน้อยยังนับว่าถึงรอบ


def collect(
    names: list[str] | None, settings: Settings, store: Store, respect_intervals: bool = False
) -> list[RunSummary]:
    summaries = []
    for name in names or list(SOURCES):
        if name not in SOURCES:
            raise KeyError(f"ไม่รู้จักแหล่งข้อมูล '{name}' (มี: {', '.join(SOURCES)})")
        if respect_intervals and not is_due(name, store):
            log.info("%s: ยังไม่ถึงรอบ (ได้ข้อมูลล่าสุดเมื่อ %s) — ข้าม", name, store.last_success(name))
            continue
        started = now_th().isoformat()
        try:
            result = SOURCES[name](settings).collect()
        except Exception as exc:  # กันไม่ให้แหล่งหนึ่งล้มทั้งรอบ
            log.exception("%s ล้มเหลว", name)
            summaries.append(RunSummary(name, 0, 0, [repr(exc)]))
            continue
        n_obs, n_rep = store.save(result, started)
        for err in result.errors:
            log.warning("%s: %s", name, err)
        log.info("%s: %d observations, %d reports", name, n_obs, n_rep)
        summaries.append(RunSummary(name, n_obs, n_rep, result.errors))
    return summaries


def run_schedule(
    settings: Settings,
    intervals: dict[str, int] | None = None,
    max_cycles: int | None = None,
    sleep=time.sleep,
    clock=time.monotonic,
) -> None:
    """วนดึงข้อมูลแต่ละแหล่งตามรอบของตัวเอง (DEFAULT_INTERVALS) — รันค้างไว้เป็น service"""
    intervals = intervals or DEFAULT_INTERVALS
    next_due = {name: 0.0 for name in intervals}
    cycles = 0
    with Store(settings.db_path, settings.raw_dir) as store:
        while max_cycles is None or cycles < max_cycles:
            now = clock()
            due = [n for n, t in next_due.items() if t <= now]
            if due:
                collect(due, settings, store)
                for name in due:
                    next_due[name] = clock() + intervals[name]
                cycles += 1
            sleep(max(1.0, min(next_due.values()) - clock()))
