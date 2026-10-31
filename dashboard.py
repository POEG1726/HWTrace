#!/usr/bin/env python3
"""Read-only local dashboard for an HWTrace SQLite database."""

import argparse
import json
import math
import sqlite3
import webbrowser
from contextlib import closing
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent / "web"


def connect(path):
    db = sqlite3.connect(
        Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=10
    )
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA query_only=ON")
    return db


def sessions(db):
    # Sequence is the collector's ordering; timestamps may change with the system clock.
    return [
        dict(r)
        for r in db.execute(
            """SELECT r.session, min(r.seq) first_seq, max(r.seq) last_seq,
        (SELECT timestamp FROM records x WHERE x.session=r.session ORDER BY seq LIMIT 1) started,
        (SELECT timestamp FROM records x WHERE x.session=r.session ORDER BY seq DESC LIMIT 1) updated,
        EXISTS(SELECT 1 FROM events e WHERE e.session=r.session AND e.event='collector_stop') stopped
        FROM records r GROUP BY r.session ORDER BY started DESC"""
        )
    ]


def sensors(db, session):
    return [
        dict(r)
        for r in db.execute(
            """SELECT sensor_id, sensor_instance, reading_id, sensor_name, reading_name, unit
        FROM sensors WHERE session=? ORDER BY sensor_name, reading_name, sensor_id, sensor_instance, reading_id""",
            (session,),
        )
    ]


def series(db, session, keys, max_points=2000, average=1, start=None, end=None):
    if not keys:
        return []
    if len(keys) > 50:
        raise ValueError("Select at most 50 sensors")
    if not 1 <= average <= 10000:
        raise ValueError("Invalid average")
    if (start is None) != (end is None):
        raise ValueError("Invalid time range")
    if start is not None:
        start, end = int(start), int(end)
        if start >= end:
            raise ValueError("Invalid time range")
        start, end = (
            datetime.fromtimestamp(t / 1000, timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
            for t in (start, end)
        )
    if average != 1 or start is not None:
        return averaged_series(db, session, keys, max_points, average, start, end)
    ids_list = []
    for key in keys:
        ids = tuple(int(x) for x in key.split(":"))
        if len(ids) != 3 or any(x < 0 or x > 0xFFFFFFFF for x in ids):
            raise ValueError("Invalid sensor ID")
        ids_list.append(ids)
    count = db.execute(
        "SELECT count(*) FROM records WHERE session=? AND kind='sample'", (session,)
    ).fetchone()[0]
    stride = max(1, math.ceil(count / max_points))
    # Select sample records by their ordinal, not by sequence modulo: event records
    # can change sequence parity, and an arbitrary stride can otherwise miss all samples.
    result = []
    for key, ids in zip(keys, ids_list):
        rows = db.execute(
            """WITH numbered AS (
            SELECT seq, timestamp, row_number() OVER (ORDER BY seq) AS n
            FROM records WHERE session=? AND kind='sample'
        ) SELECT n.timestamp, s.value FROM numbered n JOIN samples s
            ON s.session=? AND s.seq=n.seq AND s.sensor_id=? AND s.sensor_instance=? AND s.reading_id=?
            WHERE (n.n-1) % ?=0 OR n.n=? ORDER BY n.seq""",
            (session, session, *ids, stride, count),
        )
        points = [[r[0], r[1]] for r in rows]
        stats = db.execute(
            "SELECT min(value), max(value) FROM samples WHERE session=? AND sensor_id=? AND sensor_instance=? AND reading_id=?",
            (session, *ids),
        ).fetchone()
        result.append({"key": key, "points": points, "min": stats[0], "max": stats[1]})
    return result


def averaged_series(db, session, keys, max_points, average, start, end):
    result = []
    for key in keys:
        ids = tuple(int(x) for x in key.split(":"))
        if len(ids) != 3 or any(x < 0 or x > 0xFFFFFFFF for x in ids):
            raise ValueError("Invalid sensor ID")
        # Group consecutive actual samples first; downsample groups only afterwards.
        query = """WITH numbered AS (
          SELECT r.seq, r.timestamp, s.value, (row_number() OVER (ORDER BY r.seq)-1)/? AS bucket
          FROM records r JOIN samples s ON s.session=r.session AND s.seq=r.seq
          WHERE r.session=? AND s.sensor_id=? AND s.sensor_instance=? AND s.reading_id=?
            AND (? IS NULL OR (julianday(r.timestamp)>=julianday(?) AND julianday(r.timestamp)<=julianday(?)))
        ), grouped AS (
          SELECT bucket, max(seq) seq, avg(value) value, count(*) n FROM numbered GROUP BY bucket
        ) SELECT r.timestamp, g.value, g.n FROM grouped g JOIN records r ON r.session=? AND r.seq=g.seq ORDER BY g.bucket"""
        rows = db.execute(
            query, (average, session, *ids, start, start, end, session)
        ).fetchall()
        stride = max(1, math.ceil(len(rows) / max_points))
        selected = rows[::stride]
        if rows and selected[-1] != rows[-1]:
            selected.append(rows[-1])
        result.append(
            {
                "key": key,
                "points": [[r[0], r[1], r[2]] for r in selected],
                "min": min((r[1] for r in rows), default=None),
                "max": max((r[1] for r in rows), default=None),
            }
        )
    return result


def handler(db_path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            try:
                u = urlsplit(self.path)
                q = parse_qs(u.query)
                if u.path.startswith("/api/"):
                    with closing(connect(db_path)) as db:
                        if u.path == "/api/sessions":
                            data = sessions(db)
                        elif u.path == "/api/sensors":
                            data = sensors(db, q.get("session", [""])[0])
                        elif u.path == "/api/series":
                            data = series(
                                db,
                                q.get("session", [""])[0],
                                q.get("sensor", []),
                                average=int(q.get("average", ["1"])[0]),
                                start=q.get("start", [None])[0],
                                end=q.get("end", [None])[0],
                            )
                        else:
                            return self.send_error(404)
                    body = json.dumps(data, ensure_ascii=False, allow_nan=False).encode(
                        "utf-8"
                    )
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                else:
                    files = {
                        "/": ("index.html", "text/html"),
                        "/app.js": ("app.js", "text/javascript"),
                        "/style.css": ("style.css", "text/css"),
                    }
                    if u.path not in files:
                        return self.send_error(404)
                    name, mime = files[u.path]
                    body = (ROOT / name).read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", mime + "; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (sqlite3.Error, OSError, ValueError) as exc:
                self.send_error(400, str(exc))

    return Handler


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", required=True, help="Existing SQLite database")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument(
        "--open-browser",
        action="store_true",
        help="Open the dashboard in the default browser",
    )
    args = p.parse_args()
    with closing(connect(args.db)) as db:
        db.execute("SELECT 1 FROM records LIMIT 1").fetchone()
    server = ThreadingHTTPServer((args.host, args.port), handler(args.db))
    url = f"http://{args.host}:{server.server_port}/"
    print(f"Open {url}", flush=True)
    if args.open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
