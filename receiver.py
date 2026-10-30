#!/usr/bin/env python3
"""HWTrace JSONL receiver. Run on the Linux host as an SSH command."""

import argparse
import base64
import hashlib
import os
from pathlib import Path
import re
import tempfile
import json
import math
import sqlite3
import sys

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS records (
  session TEXT NOT NULL, seq INTEGER NOT NULL, timestamp TEXT NOT NULL,
  kind TEXT NOT NULL, PRIMARY KEY(session, seq)
);
CREATE TABLE IF NOT EXISTS sensors (
  session TEXT NOT NULL, sensor_id INTEGER NOT NULL, sensor_instance INTEGER NOT NULL,
  reading_id INTEGER NOT NULL, sensor_name TEXT NOT NULL, reading_name TEXT NOT NULL,
  unit TEXT NOT NULL, reading_type INTEGER NOT NULL,
  PRIMARY KEY(session, sensor_id, sensor_instance, reading_id)
);
CREATE TABLE IF NOT EXISTS samples (
  session TEXT NOT NULL, seq INTEGER NOT NULL, sensor_id INTEGER NOT NULL,
  sensor_instance INTEGER NOT NULL, reading_id INTEGER NOT NULL, value REAL,
  PRIMARY KEY(session, seq, sensor_id, sensor_instance, reading_id),
  FOREIGN KEY(session, seq) REFERENCES records(session, seq),
  FOREIGN KEY(session, sensor_id, sensor_instance, reading_id)
    REFERENCES sensors(session, sensor_id, sensor_instance, reading_id)
);
CREATE TABLE IF NOT EXISTS record_timing (
  session TEXT NOT NULL, seq INTEGER NOT NULL, elapsed_ms INTEGER NOT NULL,
  PRIMARY KEY(session,seq), FOREIGN KEY(session,seq) REFERENCES records(session,seq)
);
CREATE TABLE IF NOT EXISTS record_uptime (
  session TEXT NOT NULL, seq INTEGER NOT NULL, uptime_ms INTEGER NOT NULL,
  PRIMARY KEY(session,seq), FOREIGN KEY(session,seq) REFERENCES records(session,seq)
);
CREATE TABLE IF NOT EXISTS startup_capture_timing (
  capture_id TEXT PRIMARY KEY, started_uptime_ms INTEGER NOT NULL,
  finished_uptime_ms INTEGER NOT NULL, finished_at TEXT NOT NULL,
  FOREIGN KEY(capture_id) REFERENCES startup_captures(capture_id)
);
CREATE TABLE IF NOT EXISTS startup_captures (
  capture_id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, source_host TEXT NOT NULL,
  process_name TEXT NOT NULL, path TEXT NOT NULL, sha256 TEXT NOT NULL, bytes INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
  session TEXT NOT NULL, seq INTEGER NOT NULL, event TEXT NOT NULL, detail TEXT NOT NULL,
  PRIMARY KEY(session, seq), FOREIGN KEY(session, seq) REFERENCES records(session, seq)
);
"""
MAX_LINE = 4 * 1024 * 1024


def integer(x):
    if type(x) is not int or not 0 <= x <= 0xFFFFFFFF:
        raise ValueError("expected uint32")
    return x


def string(x, limit=4096):
    if not isinstance(x, str) or not x or len(x) > limit:
        raise ValueError("expected nonempty string")
    return x


def key(obj):
    return tuple(
        integer(obj[k]) for k in ("sensor_id", "sensor_instance", "reading_id")
    )


def ingest(db, obj):
    if not isinstance(obj, dict) or obj.get("version") != 1:
        raise ValueError("unsupported protocol version")
    session, seq = string(obj["session"], 128), integer(obj["seq"])
    timestamp, kind = string(obj["timestamp"], 64), obj["kind"]
    if kind not in ("metadata", "sample", "event"):
        raise ValueError("unknown record kind")
    with db:
        inserted = db.execute(
            "INSERT OR IGNORE INTO records VALUES (?,?,?,?)",
            (session, seq, timestamp, kind),
        ).rowcount
        if not inserted:
            return False
        if "elapsed_ms" in obj:
            elapsed = obj["elapsed_ms"]
            if type(elapsed) is not int or not 0 <= elapsed <= 0x7FFFFFFFFFFFFFFF:
                raise ValueError("invalid elapsed_ms")
            db.execute(
                "INSERT INTO record_timing VALUES (?,?,?)", (session, seq, elapsed)
            )
        if "uptime_ms" in obj:
            uptime = obj["uptime_ms"]
            if type(uptime) is not int or not 0 <= uptime <= 0x7FFFFFFFFFFFFFFF:
                raise ValueError("invalid uptime_ms")
            db.execute(
                "INSERT INTO record_uptime VALUES (?,?,?)", (session, seq, uptime)
            )
        if kind == "metadata":
            for item in obj["sensors"]:
                sid, inst, rid = key(item)
                name = string(item["sensor_name"])
                reading = string(item["reading_name"])
                unit = item["unit"]
                if not isinstance(unit, str) or len(unit) > 128:
                    raise ValueError("invalid unit")
                typ = integer(item["reading_type"])
                db.execute(
                    """INSERT INTO sensors VALUES (?,?,?,?,?,?,?,?)
                    ON CONFLICT(session,sensor_id,sensor_instance,reading_id) DO UPDATE SET
                    sensor_name=excluded.sensor_name, reading_name=excluded.reading_name,
                    unit=excluded.unit, reading_type=excluded.reading_type""",
                    (session, sid, inst, rid, name, reading, unit, typ),
                )
        elif kind == "sample":
            for item in obj["values"]:
                sid, inst, rid = key(item)
                value = item["value"]
                if type(value) not in (int, float) or not math.isfinite(value):
                    raise ValueError("invalid value")
                db.execute(
                    "INSERT INTO samples VALUES (?,?,?,?,?,?)",
                    (session, seq, sid, inst, rid, value),
                )
        else:
            event = string(obj["event"], 128)
            detail = obj.get("detail", "")
            if not isinstance(detail, str) or len(detail) > 4096:
                raise ValueError("invalid event detail")
            db.execute(
                "INSERT INTO events VALUES (?,?,?,?)", (session, seq, event, detail)
            )
    return True


MAX_SCREENSHOT = 32 * 1024 * 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def store_screenshot(
    db_path,
    capture_id,
    timestamp,
    source_host,
    process_name,
    source,
    *,
    capture_tick_ms=None,
    capture_finished_tick_ms=None,
    capture_finished_at=None
):
    if not re.fullmatch(r"[0-9a-f]{32}", capture_id):
        raise ValueError("capture_id must be 32 lowercase hex characters")
    timestamp, source_host, process_name = (
        string(timestamp, 64),
        string(source_host, 256),
        string(process_name, 256),
    )
    timed = capture_tick_ms is not None or capture_finished_tick_ms is not None
    if timed:
        if (
            type(capture_tick_ms) is not int
            or type(capture_finished_tick_ms) is not int
            or not 0
            <= capture_tick_ms
            <= capture_finished_tick_ms
            <= 0x7FFFFFFFFFFFFFFF
        ):
            raise ValueError("invalid screenshot uptime interval")
        capture_finished_at = string(capture_finished_at, 64)
    data = source.read(MAX_SCREENSHOT + 1)
    if (
        len(data) > MAX_SCREENSHOT
        or len(data) < 33
        or not data.startswith(PNG_SIGNATURE)
        or data[12:16] != b"IHDR"
    ):
        raise ValueError("invalid or oversized PNG")
    width, height = int.from_bytes(data[16:20], "big"), int.from_bytes(
        data[20:24], "big"
    )
    if not 0 < width <= 32768 or not 0 < height <= 32768:
        raise ValueError("invalid PNG dimensions")
    root = Path(db_path).resolve().parent / "screenshots"
    root.mkdir(parents=True, exist_ok=True)
    dest = root / (capture_id + ".png")
    digest = hashlib.sha256(data).hexdigest()
    db = sqlite3.connect(db_path, timeout=10)
    temp = None
    try:
        db.executescript(SCHEMA)
        previous = db.execute(
            "SELECT sha256 FROM startup_captures WHERE capture_id=?", (capture_id,)
        ).fetchone()
        if previous:
            if previous[0] != digest:
                raise ValueError("capture_id already refers to another image")
            return dest
        with tempfile.NamedTemporaryFile(
            dir=root, prefix=".upload-", delete=False
        ) as stream:
            temp = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, dest)
        temp = None
        with db:
            db.execute(
                "INSERT INTO startup_captures VALUES (?,?,?,?,?,?,?)",
                (
                    capture_id,
                    timestamp,
                    source_host,
                    process_name,
                    str(dest),
                    digest,
                    len(data),
                ),
            )
            if timed:
                db.execute(
                    "INSERT INTO startup_capture_timing VALUES (?,?,?,?)",
                    (
                        capture_id,
                        capture_tick_ms,
                        capture_finished_tick_ms,
                        capture_finished_at,
                    ),
                )
        return dest
    finally:
        db.close()
        if temp is not None:
            temp.unlink(missing_ok=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", required=True, help="SQLite database path on the receiver")
    p.add_argument(
        "--ack", action="store_true", help="acknowledge each committed record on stdout"
    )
    p.add_argument("--startup-screenshot", metavar="CAPTURE_ID")
    p.add_argument("--captured-at")
    p.add_argument("--capture-finished-at")
    p.add_argument("--capture-tick-ms", type=int)
    p.add_argument("--capture-finished-tick-ms", type=int)
    p.add_argument("--source-host")
    p.add_argument("--process-name-b64")
    args = p.parse_args()
    if args.startup_screenshot:
        try:
            name = base64.b64decode(args.process_name_b64 or "", validate=True).decode(
                "utf-8"
            )
            store_screenshot(
                args.db,
                args.startup_screenshot,
                args.captured_at,
                args.source_host,
                name,
                sys.stdin.buffer,
                capture_tick_ms=args.capture_tick_ms,
                capture_finished_tick_ms=args.capture_finished_tick_ms,
                capture_finished_at=args.capture_finished_at,
            )
            sys.stdout.buffer.write(
                ("STORED " + args.startup_screenshot + "\n").encode("ascii")
            )
            sys.stdout.buffer.flush()
            return 0
        except (ValueError, TypeError, OSError, sqlite3.Error) as exc:
            print("HWTrace: screenshot upload failed: " + str(exc), file=sys.stderr)
            return 1
    db = sqlite3.connect(args.db, timeout=10)
    db.executescript(SCHEMA)
    for line in sys.stdin.buffer:
        try:
            if len(line) > MAX_LINE:
                raise ValueError("line too long")
            obj = json.loads(
                line, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x))
            )
            ingest(db, obj)
            if args.ack:
                sys.stdout.buffer.write(b"OK\n")
                sys.stdout.buffer.flush()
        except (
            ValueError,
            TypeError,
            KeyError,
            sqlite3.Error,
            UnicodeDecodeError,
        ) as exc:
            print("HWTrace: invalid record: " + str(exc), file=sys.stderr, flush=True)
            return 1
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
