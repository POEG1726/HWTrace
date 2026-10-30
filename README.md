# HWTrace

HWTrace is under development. The Linux receiver accepts version 1 JSON Lines on standard input and stores sensor metadata, samples, and events in SQLite with WAL enabled. The Windows collector and the end-to-end system are not yet implemented.

Run on Linux with Python 3:

```sh
python3 receiver.py --db /path/to/hwtrace.sqlite3 < stream.jsonl
python3 -m unittest discover -s tests
```

Each record has `version: 1`, a unique `session` string, a per-session uint32 `seq`, an ISO 8601 `timestamp`, and `kind`: `metadata`, `sample`, or `event`. Metadata contains `sensors` entries with `sensor_id`, `sensor_instance`, `reading_id`, `sensor_name`, `reading_name`, `reading_type` (HWiNFO numeric type), and `unit`. Samples contain `values`, each with the same three IDs and a finite numeric `value`. Metadata must precede samples. Events contain `event` and optional `detail`. Duplicate session/sequence pairs are ignored; malformed records terminate ingestion and roll back that record. A transport-level acknowledgement and loss policy have not yet been implemented.

The reference [sensorwatch](https://github.com/lcjanke2020/sensorwatch) reader was inspected at commit `929e4d879f6276067ac9e95c420d60c3a653fabb`; its layout and bounds checks are useful, but its Python reader does not retain stable IDs in its reading model. No code from it has been copied so far.
