# Protocol and storage

The persistent SSH connection carries UTF-8 JSONL on stdin. After committing each
record, the receiver replies with exactly `OK\n` on stdout. Diagnostics use stderr.
Duplicate `(session, seq)` records are acknowledged, allowing retries when a
connection fails between commit and acknowledgement. Invalid records terminate
ingestion without acknowledgement.

| Record field | Meaning |
| --- | --- |
| `version` | `1` |
| `session` | Collector-generated session identifier |
| `seq` | Unsigned 32-bit sequence within the session |
| `timestamp` | Collector UTC ISO 8601 timestamp |
| `kind` | `metadata`, `sample` or `event` |
| `elapsed_ms` | Monotonic time since collector initialization |
| `uptime_ms` | Collector computer's boot-time clock |

Older records may omit monotonic fields. Timestamps are not receiver arrival
times. Clock resolution is platform-dependent; millisecond fields do not imply
sub-millisecond accuracy.

`metadata` contains a `sensors` array with `sensor_id`, `sensor_instance`,
`reading_id`, `sensor_name`, `reading_name`, `reading_type` and `unit`. IDs are
unsigned 32-bit HWiNFO values; display names need not be unique.

`sample` contains a `values` array: the same three IDs plus a finite numeric
`value`. Metadata includes selected sensors even when values are non-finite;
non-finite sample values are skipped. Each metadata/sample pair uses one immutable
snapshot. Metadata must exist before a sample references it.

`event` has `event` and optional `detail`. Events include collector start/stop,
observed process start/exit, waiting, auto-stop, manual markers, source availability
and startup capture context/status. A start event for an existing process means
first detection. Presence is aggregated by executable name rather than each PID.

## SQLite

| Table | Contents |
| --- | --- |
| `records` | Session, sequence, UTC timestamp and kind |
| `sensors` | Session-scoped IDs, names, type and units |
| `samples` | Values linked to records and sensors |
| `events` | Event names and details |
| `record_timing` | Optional elapsed time per record |
| `record_uptime` | Optional system uptime per record |
| `startup_captures` | PNG path, capture-start UTC, host, process, hash and size |
| `startup_capture_timing` | Capture-finish UTC and pixel-copy uptime interval |

WAL and foreign keys are enabled. A malformed record rolls back its transaction.
The first record for a session/sequence wins; do not reuse that pair for different
payloads. Metadata updates replace displayed metadata for an identity within the
session; historical metadata versions are not retained.

## Startup PNG upload

A separate SSH process runs the receiver command with appended flags:

```text
--startup-screenshot CAPTURE_ID --captured-at UTC
--capture-finished-at UTC --capture-tick-ms N --capture-finished-tick-ms N
--source-host HOST --process-name-b64 BASE64
```

The body is raw PNG bytes. `CAPTURE_ID` is 32 lowercase hex characters. The receiver
bounds uploads to 32 MiB, checks PNG signature/IHDR/dimensions, writes an atomic
file under `screenshots/` beside the database, and stores SHA-256/metadata. It is
not a full PNG decoder or malware scanner. Success returns `STORED CAPTURE_ID\n`.

The `startup_context` and `startup_screenshot_pending` event details contain the
capture ID. Pending does not guarantee success; join `startup_captures` to confirm
completion. Later worker failures go to stderr.

To align data, compare `record_uptime.uptime_ms` with the capture's
`started_uptime_ms` and `finished_uptime_ms`. These clocks originate on the same
collector. Use the pixel-copy interval rather than upload completion. A screenshot
is copied over an interval, not atomically sampled.
