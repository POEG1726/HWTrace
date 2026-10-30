#!/usr/bin/env python3
"""HWTrace JSONL receiver. Run on the Linux host as an SSH command."""
import argparse
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
CREATE TABLE IF NOT EXISTS events (
  session TEXT NOT NULL, seq INTEGER NOT NULL, event TEXT NOT NULL, detail TEXT NOT NULL,
  PRIMARY KEY(session, seq), FOREIGN KEY(session, seq) REFERENCES records(session, seq)
);
"""
MAX_LINE = 4 * 1024 * 1024

def integer(x):
    if type(x) is not int or not 0 <= x <= 0xffffffff:
        raise ValueError('expected uint32')
    return x

def string(x, limit=4096):
    if not isinstance(x, str) or not x or len(x) > limit:
        raise ValueError('expected nonempty string')
    return x

def key(obj):
    return tuple(integer(obj[k]) for k in ('sensor_id', 'sensor_instance', 'reading_id'))

def ingest(db, obj):
    if not isinstance(obj, dict) or obj.get('version') != 1:
        raise ValueError('unsupported protocol version')
    session, seq = string(obj['session'], 128), integer(obj['seq'])
    timestamp, kind = string(obj['timestamp'], 64), obj['kind']
    if kind not in ('metadata', 'sample', 'event'):
        raise ValueError('unknown record kind')
    with db:
        inserted = db.execute('INSERT OR IGNORE INTO records VALUES (?,?,?,?)',
                              (session, seq, timestamp, kind)).rowcount
        if not inserted:
            return False
        if kind == 'metadata':
            for item in obj['sensors']:
                sid, inst, rid = key(item)
                name = string(item['sensor_name'])
                reading = string(item['reading_name'])
                unit = item['unit']
                if not isinstance(unit, str) or len(unit) > 128:
                    raise ValueError('invalid unit')
                typ = integer(item['reading_type'])
                db.execute('''INSERT INTO sensors VALUES (?,?,?,?,?,?,?,?)
                    ON CONFLICT(session,sensor_id,sensor_instance,reading_id) DO UPDATE SET
                    sensor_name=excluded.sensor_name, reading_name=excluded.reading_name,
                    unit=excluded.unit, reading_type=excluded.reading_type''',
                    (session, sid, inst, rid, name, reading, unit, typ))
        elif kind == 'sample':
            for item in obj['values']:
                sid, inst, rid = key(item)
                value = item['value']
                if type(value) not in (int, float) or not math.isfinite(value):
                    raise ValueError('invalid value')
                db.execute('INSERT INTO samples VALUES (?,?,?,?,?,?)',
                           (session, seq, sid, inst, rid, value))
        else:
            event = string(obj['event'], 128)
            detail = obj.get('detail', '')
            if not isinstance(detail, str) or len(detail) > 4096:
                raise ValueError('invalid event detail')
            db.execute('INSERT INTO events VALUES (?,?,?,?)', (session, seq, event, detail))
    return True

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db', required=True, help='SQLite database path on the receiver')
    args = p.parse_args()
    db = sqlite3.connect(args.db, timeout=10)
    db.executescript(SCHEMA)
    for line in sys.stdin.buffer:
        try:
            if len(line) > MAX_LINE:
                raise ValueError('line too long')
            obj = json.loads(line, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
            ingest(db, obj)
        except (ValueError, TypeError, KeyError, sqlite3.Error, UnicodeDecodeError) as exc:
            print('HWTrace: invalid record: ' + str(exc), file=sys.stderr, flush=True)
            return 1
    db.close()
    return 0

if __name__ == '__main__':
    sys.exit(main())
