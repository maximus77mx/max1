"""คำสั่ง: thaiflood <sources|collect|schedule|backfill|stats|latest|reports|export|dashboard|prune|import-report>"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

from .collector import collect, run_schedule
from .dashboard import default_output_name, write_dashboard
from .config import DEFAULT_INTERVALS, Settings
from .sources import SOURCES
from .sources.bulletins import report_from_dict
from .sources.thaiwater import ThaiWaterSource
from .storage import Store
from .utils import now_th


def _store(settings: Settings) -> Store:
    return Store(settings.db_path, settings.raw_dir)


def cmd_sources(args: argparse.Namespace, settings: Settings) -> int:
    for name, cls in SOURCES.items():
        every = DEFAULT_INTERVALS.get(name, 0) // 60
        print(f"{name:10s} ทุก {every:>4d} นาที  {cls.description}")
    return 0


def cmd_collect(args: argparse.Namespace, settings: Settings) -> int:
    unknown = [n for n in args.source if n not in SOURCES]
    if unknown:
        print(f"ไม่รู้จักแหล่งข้อมูล: {', '.join(unknown)} (มี: {', '.join(SOURCES)})", file=sys.stderr)
        return 2
    with _store(settings) as store:
        summaries = collect(args.source or None, settings, store)
    failed = 0
    for s in summaries:
        flag = "OK " if not s.errors else ("ERR" if not (s.observations or s.reports) else "WARN")
        failed += flag == "ERR"
        print(f"[{flag}] {s.source:10s} obs={s.observations:<6d} reports={s.reports:<4d}")
        for e in s.errors:
            print(f"       - {e}")
    return 1 if failed == len(summaries) else 0


def cmd_schedule(args: argparse.Namespace, settings: Settings) -> int:
    intervals = dict(DEFAULT_INTERVALS)
    if args.source:
        intervals = {k: v for k, v in intervals.items() if k in args.source}
    print("เริ่มดึงข้อมูลตามรอบ (Ctrl+C เพื่อหยุด):", ", ".join(f"{k}={v // 60}น." for k, v in intervals.items()))
    try:
        run_schedule(settings, intervals)
    except KeyboardInterrupt:
        pass
    return 0


def cmd_backfill(args: argparse.Namespace, settings: Settings) -> int:
    """ดึงระดับน้ำย้อนหลังรายสถานีจาก ThaiWater ทีละช่วง (chunk) เพื่อไม่ให้ request ใหญ่เกิน"""
    src = ThaiWaterSource(settings)
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end) if args.end else now_th().date()
    total = 0
    with _store(settings) as store:
        for station in args.station:
            cursor = start
            while cursor <= end:
                chunk_end = min(cursor + timedelta(days=args.chunk_days - 1), end)
                try:
                    obs = src.waterlevel_history(station, cursor.isoformat(), chunk_end.isoformat())
                    n = store.upsert_observations(obs, now_th().isoformat())
                    store.conn.commit()
                    total += n
                    print(f"{station} {cursor}..{chunk_end}: {n} จุด")
                except Exception as exc:
                    print(f"{station} {cursor}..{chunk_end}: ผิดพลาด {exc}", file=sys.stderr)
                cursor = chunk_end + timedelta(days=1)
    print(f"รวม {total} จุด")
    return 0


def cmd_stats(args: argparse.Namespace, settings: Settings) -> int:
    with _store(settings) as store:
        rows = store.stats()
    if not rows:
        print("ยังไม่มีข้อมูล — ลอง `thaiflood collect`")
    for r in rows:
        print(f"{r['source']:10s} {r['kind']:14s} n={r['n']:<7d} จุด={r['stations']:<5d} {r['first']} → {r['last']}")
    return 0


def cmd_latest(args: argparse.Namespace, settings: Settings) -> int:
    """สรุปสถานการณ์ล่าสุด: สถานีวิกฤต, ฝนหนัก, จุดท่วมขัง กทม., ประกาศล่าสุด"""
    since = (now_th() - timedelta(hours=args.hours)).isoformat()
    with _store(settings) as store:
        wl = store.query_observations(kind="waterlevel", since=since, province=args.province)
        rain = store.query_observations(kind="rain_24h", since=since, province=args.province)
        street = store.query_observations(kind="street_flood", since=since)
        flood = store.query_observations(kind="flood_area", since=since, province=args.province)
        reports = store.query_reports(limit=5)

    def latest_per_station(rows):
        seen, out = set(), []
        for r in rows:  # rows เรียงใหม่→เก่าแล้ว
            if r["station_id"] not in seen:
                seen.add(r["station_id"])
                out.append(r)
        return out

    critical = [r for r in latest_per_station(wl) if r["status"] in ("มาก", "ล้นตลิ่ง/วิกฤต")]
    print(f"== ระดับน้ำ 'มาก/วิกฤต' ({len(critical)} สถานี)")
    for r in critical[: args.top]:
        print(f"  {r['status']:14s} {r['name'] or r['station_id']} ({r['province']}) {r['value']} {r['unit']} @ {r['observed_at']}")

    heavy = sorted((r for r in latest_per_station(rain) if (r["value"] or 0) >= 35), key=lambda r: -r["value"])
    print(f"== ฝน 24 ชม. ≥ 35 มม. ({len(heavy)} สถานี)")
    for r in heavy[: args.top]:
        print(f"  {r['value']:7.1f} มม. {r['name'] or r['station_id']} ({r['province']})")

    if flood:
        by_prov: dict[str, float] = {}
        for r in flood:
            by_prov[r["province"] or "?"] = by_prov.get(r["province"] or "?", 0) + (r["value"] or 0)
        print("== พื้นที่น้ำท่วมจากดาวเทียม (ไร่)")
        for prov, rai in sorted(by_prov.items(), key=lambda kv: -kv[1])[: args.top]:
            print(f"  {prov:20s} {rai:,.0f}")

    wet = [r for r in latest_per_station(street) if (r["value"] or 0) > 0]
    if wet:
        print(f"== จุดน้ำท่วมขัง กทม. ({len(wet)} จุด)")
        for r in sorted(wet, key=lambda r: -r["value"])[: args.top]:
            print(f"  {r['value']:5.0f} ซม. {r['name']} {r['amphoe'] or ''}")

    print("== รายงาน/ประกาศล่าสุด")
    for r in reports:
        print(f"  [{r['source']}] {r['published_at'] or r['collected_at'][:16]} {r['title']}")
        if r["metrics"] and r["metrics"] != "{}":
            print(f"      {r['metrics']}")
    return 0


def cmd_reports(args: argparse.Namespace, settings: Settings) -> int:
    with _store(settings) as store:
        rows = store.query_reports(source=args.source, limit=args.limit)
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))
    return 0


def cmd_export(args: argparse.Namespace, settings: Settings) -> int:
    with _store(settings) as store:
        n = store.export_csv(
            Path(args.output), kind=args.kind, province=args.province, since=args.since,
            until=args.until, source=args.source,
        )
    print(f"เขียน {n} แถวไปที่ {args.output}")
    return 0


def cmd_dashboard(args: argparse.Namespace, settings: Settings) -> int:
    with _store(settings) as store:
        if args.collect:
            collect(None, settings, store)
        out = write_dashboard(store, Path(args.output or default_output_name()), days=args.days, province=args.province, settings=settings, geo=not args.no_geo)
    print(f"สร้าง dashboard: {out.resolve()} ({out.stat().st_size / 1024:,.0f} KB) — เปิดด้วยเบราว์เซอร์ได้เลย")
    return 0


def cmd_probe_gistda(args: argparse.Namespace, settings: Settings) -> int:
    from .sources.gistda import GistdaSource

    for line in GistdaSource(settings).probe():
        print(line)
    return 0


def cmd_prune(args: argparse.Namespace, settings: Settings) -> int:
    with _store(settings) as store:
        rows, dirs = store.prune(args.keep_days)
    print(f"ลบ {rows} แถว และโฟลเดอร์ raw {dirs} โฟลเดอร์ ที่เก่ากว่า {args.keep_days} วัน")
    return 0


def cmd_import_report(args: argparse.Namespace, settings: Settings) -> int:
    """นำเข้ารายงานที่กรอกเอง (JSON object หรือ list) เช่นตัวเลขจาก PDF ของ ปภ."""
    data = json.loads(Path(args.file).read_text(encoding="utf-8"))
    items = data if isinstance(data, list) else [data]
    with _store(settings) as store:
        n = store.upsert_reports([report_from_dict(d) for d in items], now_th().isoformat())
        store.conn.commit()
    print(f"นำเข้า {n} รายงาน")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="thaiflood", description="รวบรวมข้อมูลน้ำท่วมประเทศไทย (Realtime + Historical)")
    p.add_argument("--data-dir", help="โฟลเดอร์เก็บ SQLite และไฟล์ raw (ค่าเริ่มต้น ./data)")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("sources", help="แสดงแหล่งข้อมูลทั้งหมด").set_defaults(func=cmd_sources)

    c = sub.add_parser("collect", help="ดึงข้อมูลหนึ่งรอบ")
    c.add_argument("source", nargs="*", metavar="SOURCE", help=f"เว้นว่าง = ทุกแหล่ง ({', '.join(SOURCES)})")
    c.set_defaults(func=cmd_collect)

    s = sub.add_parser("schedule", help="รันค้างไว้ ดึงตามรอบของแต่ละแหล่ง")
    s.add_argument("source", nargs="*", metavar="SOURCE")
    s.set_defaults(func=cmd_schedule)

    b = sub.add_parser("backfill", help="ดึงระดับน้ำย้อนหลังรายสถานี (ThaiWater)")
    b.add_argument("--station", action="append", required=True, help="station id (ใส่ซ้ำได้หลายสถานี)")
    b.add_argument("--start", required=True, help="YYYY-MM-DD")
    b.add_argument("--end", help="YYYY-MM-DD (ค่าเริ่มต้นวันนี้)")
    b.add_argument("--chunk-days", type=int, default=30)
    b.set_defaults(func=cmd_backfill)

    sub.add_parser("stats", help="สรุปข้อมูลที่เก็บแล้ว").set_defaults(func=cmd_stats)

    l = sub.add_parser("latest", help="สรุปสถานการณ์ล่าสุด")
    l.add_argument("--hours", type=int, default=24)
    l.add_argument("--province")
    l.add_argument("--top", type=int, default=15)
    l.set_defaults(func=cmd_latest)

    r = sub.add_parser("reports", help="รายงาน/ประกาศที่เก็บไว้ (JSON lines)")
    r.add_argument("--source")
    r.add_argument("--limit", type=int, default=20)
    r.set_defaults(func=cmd_reports)

    e = sub.add_parser("export", help="ส่งออก observations เป็น CSV")
    e.add_argument("output")
    e.add_argument("--kind")
    e.add_argument("--source")
    e.add_argument("--province")
    e.add_argument("--since")
    e.add_argument("--until")
    e.set_defaults(func=cmd_export)

    d = sub.add_parser("dashboard", help="สร้าง Interactive HTML ไฟล์เดียว จากข้อมูลที่เก็บไว้")
    d.add_argument("output", nargs="?", help="ชื่อไฟล์ (ค่าเริ่มต้น thaiflood_YYYYMMDD_HHMM.html)")
    d.add_argument("--days", type=int, default=7, help="ฝังข้อมูลย้อนหลังกี่วัน (ยิ่งมากไฟล์ยิ่งใหญ่)")
    d.add_argument("--province", help="ฝังเฉพาะจังหวัดนี้")
    d.add_argument("--collect", action="store_true", help="ดึงข้อมูลใหม่ทุกแหล่งก่อนสร้าง")
    d.add_argument("--no-geo", action="store_true", help="ไม่ทำแผนที่ระบายสีรายจังหวัด/ตำบล (ไม่ต้องดาวน์โหลดขอบเขต)")
    d.set_defaults(func=cmd_dashboard)

    sub.add_parser("probe-gistda", help="ตรวจการตอบกลับของ GISTDA API ทุกช่วงเวลา").set_defaults(func=cmd_probe_gistda)

    pr = sub.add_parser("prune", help="ลบข้อมูลเก่าเพื่อคุมขนาดฐานข้อมูล")
    pr.add_argument("--keep-days", type=int, required=True)
    pr.set_defaults(func=cmd_prune)

    i = sub.add_parser("import-report", help="นำเข้ารายงานจากไฟล์ JSON")
    i.add_argument("file")
    i.set_defaults(func=cmd_import_report)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    settings = Settings()
    if args.data_dir:
        settings.data_dir = Path(args.data_dir)
    return args.func(args, settings)


if __name__ == "__main__":
    sys.exit(main())
