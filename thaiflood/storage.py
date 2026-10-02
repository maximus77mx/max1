"""เก็บข้อมูลลง SQLite (ใช้ทำ historical) + เก็บ payload ดิบเป็นไฟล์ JSON"""

from __future__ import annotations

import csv
import json
import shutil
import sqlite3
from datetime import timedelta
from pathlib import Path
from typing import Any, Iterable

from .models import CollectResult, Observation, Report
from .utils import now_th

SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    source TEXT NOT NULL,
    kind TEXT NOT NULL,
    station_id TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    value REAL,
    unit TEXT,
    name TEXT,
    province TEXT,
    amphoe TEXT,
    tambon TEXT,
    lat REAL,
    lon REAL,
    status TEXT,
    extra TEXT,
    collected_at TEXT NOT NULL,
    PRIMARY KEY (source, kind, station_id, observed_at)
);
CREATE INDEX IF NOT EXISTS idx_obs_time ON observations (observed_at);
CREATE INDEX IF NOT EXISTS idx_obs_province ON observations (province, kind);

CREATE TABLE IF NOT EXISTS reports (
    source TEXT NOT NULL,
    kind TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT,
    published_at TEXT,
    summary TEXT,
    provinces TEXT,
    metrics TEXT,
    collected_at TEXT NOT NULL,
    PRIMARY KEY (source, kind, url)
);

CREATE TABLE IF NOT EXISTS runs (
    source TEXT NOT NULL,
    started_at TEXT NOT NULL,
    observations INTEGER,
    reports INTEGER,
    errors TEXT
);
"""

OBS_COLUMNS = [
    "source", "kind", "station_id", "observed_at", "value", "unit", "name", "province",
    "amphoe", "tambon", "lat", "lon", "status", "extra", "collected_at",
]


class Store:
    def __init__(self, db_path: Path, raw_dir: Path | None = None) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self.raw_dir = raw_dir
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ---------- write ----------
    def save(self, result: CollectResult, started_at: str | None = None) -> tuple[int, int]:
        collected_at = now_th().isoformat()
        n_obs = self.upsert_observations(result.observations, collected_at)
        n_rep = self.upsert_reports(result.reports, collected_at)
        self.conn.execute(
            "INSERT INTO runs VALUES (?,?,?,?,?)",
            (result.source, started_at or collected_at, n_obs, n_rep, json.dumps(result.errors, ensure_ascii=False)),
        )
        self.conn.commit()
        if self.raw_dir and result.raw:
            self.save_raw(result.source, result.raw)
        return n_obs, n_rep

    def upsert_observations(self, items: Iterable[Observation], collected_at: str) -> int:
        rows = [
            (
                o.source, o.kind, o.station_id, o.observed_at, o.value, o.unit, o.name, o.province,
                o.amphoe, o.tambon, o.lat, o.lon, o.status,
                json.dumps(o.extra, ensure_ascii=False) if o.extra else None, collected_at,
            )
            for o in items
            if o.observed_at
        ]
        self.conn.executemany(
            f"INSERT OR REPLACE INTO observations ({','.join(OBS_COLUMNS)}) "
            f"VALUES ({','.join('?' * len(OBS_COLUMNS))})",
            rows,
        )
        return len(rows)

    def upsert_reports(self, items: Iterable[Report], collected_at: str) -> int:
        rows = [
            (
                r.source, r.kind, r.url, r.title, r.published_at, r.summary,
                json.dumps(r.provinces, ensure_ascii=False),
                json.dumps(r.metrics, ensure_ascii=False), collected_at,
            )
            for r in items
        ]
        self.conn.executemany("INSERT OR REPLACE INTO reports VALUES (?,?,?,?,?,?,?,?,?)", rows)
        return len(rows)

    def save_raw(self, source: str, raw: dict[str, Any]) -> list[Path]:
        assert self.raw_dir is not None
        stamp = now_th()
        folder = self.raw_dir / source / stamp.strftime("%Y-%m-%d")
        folder.mkdir(parents=True, exist_ok=True)
        paths = []
        for name, payload in raw.items():
            path = folder / f"{stamp.strftime('%H%M%S')}_{name}"
            if isinstance(payload, bytes):
                path.write_bytes(payload)
            elif isinstance(payload, str):
                path.write_text(payload, encoding="utf-8")
            else:
                path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            paths.append(path)
        return paths

    # ---------- read ----------
    def query_observations(
        self,
        kind: str | None = None,
        province: str | None = None,
        since: str | None = None,
        until: str | None = None,
        source: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM observations WHERE 1=1"
        args: list[Any] = []
        for col, val in (("kind", kind), ("source", source)):
            if val:
                sql += f" AND {col} = ?"
                args.append(val)
        if province:
            sql += " AND province LIKE ?"
            args.append(f"%{province}%")
        if since:
            sql += " AND observed_at >= ?"
            args.append(since)
        if until:
            sql += " AND observed_at <= ?"
            args.append(until)
        sql += " ORDER BY observed_at DESC"
        if limit:
            sql += " LIMIT ?"
            args.append(limit)
        return [dict(r) for r in self.conn.execute(sql, args)]

    def query_reports(self, source: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        sql = "SELECT * FROM reports"
        args: list[Any] = []
        if source:
            sql += " WHERE source = ?"
            args.append(source)
        sql += " ORDER BY COALESCE(published_at, collected_at) DESC LIMIT ?"
        args.append(limit)
        return [dict(r) for r in self.conn.execute(sql, args)]

    def prune(self, keep_days: int) -> tuple[int, int]:
        """ลบ observations ที่เก่ากว่า keep_days และโฟลเดอร์ raw ที่เก่ากว่านั้น (คืน (แถว, โฟลเดอร์))"""
        cutoff = now_th() - timedelta(days=keep_days)
        n_rows = self.conn.execute("DELETE FROM observations WHERE observed_at < ?", (cutoff.isoformat(),)).rowcount
        self.conn.execute("DELETE FROM runs WHERE started_at < ?", (cutoff.isoformat(),))
        self.conn.commit()
        self.conn.execute("VACUUM")
        n_dirs = 0
        if self.raw_dir and self.raw_dir.exists():
            day = cutoff.strftime("%Y-%m-%d")
            for folder in self.raw_dir.glob("*/*"):
                if folder.is_dir() and folder.name < day:
                    shutil.rmtree(folder)
                    n_dirs += 1
        return n_rows, n_dirs

    def stats(self) -> list[dict[str, Any]]:
        sql = (
            "SELECT source, kind, COUNT(*) AS n, COUNT(DISTINCT station_id) AS stations, "
            "MIN(observed_at) AS first, MAX(observed_at) AS last "
            "FROM observations GROUP BY source, kind ORDER BY source, kind"
        )
        return [dict(r) for r in self.conn.execute(sql)]

    def export_csv(self, path: Path, **filters: Any) -> int:
        rows = self.query_observations(**filters)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig ให้ Excel อ่านไทยได้
            writer = csv.DictWriter(f, fieldnames=OBS_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        return len(rows)
