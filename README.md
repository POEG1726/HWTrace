# HWTrace

A Windows native HWiNFO collector streams JSON Lines over a Windows-initiated SSH process to a Python 3 Linux receiver. The receiver stores readings, metadata and events in SQLite (WAL). The collector writes no local telemetry files.

## Build

Windows: install a C compiler such as MinGW-w64, then run:

```powershell
New-Item -ItemType Directory -Force build
x86_64-w64-mingw32-gcc -std=c11 -O2 -Wall -Wextra collector.c -o build/hwtrace.exe
```

Cross-build from WSL with `sudo apt install gcc-mingw-w64-x86-64` and run the same compiler command from the project directory. Build outputs are ignored by Git.

## Prepare and run

1. In HWiNFO, enable Shared Memory Support, open Sensors, and set its polling interval to 500 ms. Keep HWiNFO running. Some editions disable shared memory after a limited time.
2. Copy `receiver.py` to the Linux receiver. Prepare SSH key authentication and verify the host key with the usual OpenSSH tools. Ensure the Linux account can create and write the selected database directory. Use a local Linux filesystem for the database (particularly when using WSL).
3. Verify the SSH command independently, substituting your host, key and paths. The SSH connection must be noninteractive and stdout must be reserved for receiver acknowledgements:

```powershell
$remote = 'ssh.exe -i C:/Users/you/.ssh/id_ed25519 -o BatchMode=yes -o ConnectTimeout=5 -o ServerAliveInterval=5 -o ServerAliveCountMax=3 user@host python3 /home/user/hwtrace/receiver.py --db /home/user/hwtrace/data.sqlite3 --ack'
.\build\hwtrace.exe .\ddr5.filter $remote
```

Enter a line and press Enter to record a manual marker. Ctrl+C requests shutdown. The default monitored executable is `TM5.exe`; pass a different executable name as the third argument. A fourth argument changes the post-exit grace period in seconds (default 600), useful for testing. A running instance at collector startup is detected as a start. Process checks are every 500 ms; very short processes can be missed. After the process exits, a restart cancels the pending stop. No automatic stop occurs until the process has been observed at least once.

`ddr5.filter` contains case-insensitive reading-name substrings based on the provided CSV. `sensor substring|reading substring` restricts both fields. Empty filter files select all readings. This is selection, not a fixed list of supported hardware. IDs and names in the database can be inspected to refine the filter. Actual availability depends on HWiNFO and hardware; the laptop used for testing does not expose the DDR5 DIMM readings from the supplied CSV. HWiNFO IDs distinguish duplicate names within a session; verify identities again after hardware or HWiNFO changes.

## Reliability and storage

A 128-record fixed RAM ring decouples polling from SSH. The receiver commits each record before acknowledging it; the collector retries the oldest unacknowledged record after reconnect, and session/sequence deduplication prevents an acknowledged-or-not retry from duplicating it. Sensor metadata precedes samples, and is refreshed during sampling. The SSH command must include `--ack`. No local spool exists: a long outage can fill the queue, after which new records are dropped. The drop count appears on stderr; shutdown waits up to five seconds for queued records and exits nonzero if records remain or were dropped. Events can also be lost on overflow. A crash or power loss can lose unacknowledged in-memory records. SSH host-key checking and authentication are managed by OpenSSH; do not disable verification in production.

SQLite tables are `records`, `sensors`, `samples`, and `events`; timestamps are UTC ISO 8601. Sensor identity is `(session, sensor_id, sensor_instance, reading_id)`. Units and display names are stored in `sensors`. A metadata update replaces that identity's previous displayed metadata within the session; it is not a historical metadata table. SQLite and the collector do not assert that HWiNFO itself refreshed a value at every sample.

Run receiver tests with `python3 -m unittest discover -s tests -v`. Use `python3 receiver.py --db /path/to/db < stream.jsonl` for one-way ingestion without acknowledgements. Records are version 1 objects containing `session`, uint32 `seq`, `timestamp`, `kind`, and kind-specific `sensors`, `values`, or event fields. Invalid records stop ingestion without an acknowledgement.

The shared memory layout and defensive bounds checks were informed by [sensorwatch](https://github.com/lcjanke2020/sensorwatch) at commit `929e4d879f6276067ac9e95c420d60c3a653fabb`. Its license is reproduced in `SENSORWATCH-LICENSE.txt`.

For read-only acquisition diagnostics, run `.\build\hwtrace.exe --diagnose`. It reports the exact Windows error without opening SSH or starting collection. Live-target investigation details are in `docs/troubleshooting.md`.

Native regression fixtures can be built with the same MinGW compiler: `tests/test_native_units.c` and `tests/test_native_snapshot.c`. The latter emits JSONL exercising metadata for initially non-finite readings followed by a valid sample; feed it through the receiver to verify foreign-key-safe ingestion.
