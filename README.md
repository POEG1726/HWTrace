# HWTrace

Hardware telemetry and event logging over SSH. A native Windows collector reads
HWiNFO Shared Memory every **500 ms** and streams JSONL to a Python receiver on
**Linux, WSL or Windows**. The receiver stores sensor metadata, samples and events
in SQLite with WAL enabled.

The collector keeps telemetry in a bounded RAM queue: it writes no local database,
telemetry log or screenshot file. SSH invokes the receiver as a command. An optional
read-only web dashboard visualizes the stored data separately.

> **Desktop capture:** the PowerShell launcher takes one full-desktop screenshot
> when the monitored process is already running. This includes all active monitors
> and can include other applications. Images are transferred to the configured
> receiver. Run the native executable directly if you do not want screenshots.

## What it does

- Select readings by configurable names; identify duplicates by HWiNFO sensor ID,
  sensor instance and reading ID, rather than display name alone.
- Store reading names, units, UTC timestamps and monotonic collection timing.
- Record process presence/exit and manual markers. Default process: `TM5.exe`.
- Continue for 10 minutes after the last monitored process exits; cancel the stop
  if it restarts. Never auto-stop before observing the process.
- Reconnect SSH and retry unacknowledged records; deduplicate retries in SQLite.
- Capture the physical-pixel desktop on a background thread, released by the
  collector's startup signal. Record the actual capture interval for alignment.

```text
Windows collector                         Linux / WSL / Windows receiver
HWiNFO Shared Memory -> native collector -- persistent SSH / JSONL --> SQLite
                       startup screenshot -- one-off SSH / PNG -----> screenshots/
```

## Requirements

Collector: Windows x64, HWiNFO running in Sensors mode with Shared Memory Support
and a **500 ms** polling interval, plus Windows OpenSSH Client. The optional
screenshot launcher needs PowerShell 7; PowerShell 7.6 was tested. Its screenshot
API requires Windows 10 1703 or later and an interactive desktop.

Receiver: Python **3.12+**, an SSH server, and a writable local directory. No Python
packages are required. Use the Linux filesystem for a WSL database.

Build: MinGW-w64 GCC, either on Windows or as a WSL cross compiler. No HWiNFO SDK
or third-party native library is needed.

## Build

From the repository root, with a Windows MinGW compiler on PATH:

```powershell
pwsh -NoProfile -File .\scripts\build.ps1 -Compiler gcc
```

Or cross-build using WSL:

```sh
sudo apt-get install gcc-mingw-w64-x86-64
```

```powershell
pwsh -NoProfile -File .\scripts\build.ps1 -UseWsl
```

The executable is `build/hwtrace.exe`. A direct compiler invocation also works:

```sh
x86_64-w64-mingw32-gcc -std=c11 -O2 -Wall -Wextra collector.c -o build/hwtrace.exe
```

Create `build/` before using the direct command.

## Configure and run

1. Copy `receiver.py` to the receiver and create its database directory.
2. Configure SSH key authentication **from the collector to the receiver**. Verify
   the server host key and confirm a noninteractive login works. An SSH key for
   the opposite direction does not configure this connection.
3. Copy `collector.example.json` to `collector.json`. Replace the SSH destination
   and receiver paths with your own. Keep credentials outside the repository.
4. Start HWiNFO Sensors, enable Shared Memory Support, and set polling to 500 ms.
5. On the collector's logged-in Windows desktop:

```powershell
pwsh -NoProfile -File .\Start-HWTrace.ps1
```

Type a line and press Enter for a manual marker. Press Ctrl+C to stop. The launcher
checks for the monitored process but does **not** launch TM5 or another stress tool.
When that process is absent, it skips screenshots and starts collection normally.

For telemetry without screenshots, use the native collector directly:

```powershell
$config = Get-Content .\collector.json -Raw | ConvertFrom-Json
.\build\hwtrace.exe .\ddr5.filter $config.ssh_command TM5.exe 600
```

[Deployment instructions](docs/deployment.md) include Linux/WSL and Windows
receiver examples. SSH invokes the receiver as needed; the optional dashboard
is started separately.

## Sensor profiles

`ddr5.filter` is an initial memory-stability profile, not a hardware limitation.
Each non-comment line is a case-insensitive reading-name substring, or
`sensor-group substring|reading substring`. An empty right-hand substring selects
all readings in the matching group; an empty file selects all readings.

The profile covers CPU/die/CCD/core/L3/IO-die and VRM temperatures; SoC/VDDIO
voltages; DRAM bandwidth; MCLK/FCLK/UCLK and exposed memory timings; per-DIMM SPD
temperature, VDD/VDDQ/VPP, VIN/VOUT rails, power and PMIC flags; memory pressure and
WHEA counts. Actual availability depends on HWiNFO and hardware. It stores
individual core/L3 readings rather than inventing CSV aggregate averages.

Profiles are loaded at startup. Restart the collector to apply a change. Names
can be localized or customized; inspect HWiNFO or stored metadata when refining
rules. Stable IDs distinguish duplicates within a session, but verify them again
after hardware or HWiNFO changes.

## Storage, timing and limits

The database contains `records`, `sensors`, `samples`, `events`, `record_timing`,
`record_uptime`, `startup_captures` and `startup_capture_timing`. PNGs are saved
beside it in `screenshots/`. [Protocol and schema](docs/protocol.md) explain joins
and capture-to-sample alignment.

- The RAM ring has 128 slots of 64 KiB. A record must fit in one slot. Snapshot and
  screenshot memory are additional; footprint depends on the selected hardware.
- A full ring drops new records, including events. Shutdown allows five seconds
  to drain and returns nonzero for pending/dropped records. There is no disk spool.
- A receiver acknowledgement follows the SQLite commit. This supports reconnect
  retries; it does not make crashes or extended outages lossless.
- Process presence is checked every 500 ms and aggregated by executable name.
  Brief processes can be missed. A start event for an already-running process is
  a detection timestamp, not its original start time.
- Capture/upload is asynchronous. Pixel-copy start/end UTC and boot-time clocks
  align it to samples; this is not an atomic or hard-real-time screenshot.
- HWiNFO may stop publishing shared memory independently of the collector. The
  collector retries; it cannot recover samples that HWiNFO never exposed.

## Test and troubleshoot

```powershell
pwsh -NoProfile -File .\scripts\test.ps1 -UseWsl
```

For a Windows compiler, use `-Compiler gcc` instead of `-UseWsl`. Dashboard
interaction tests also require Node.js 18+ (development only, no npm packages).
Tests use synthetic
readings/images and offscreen bitmaps; they do not capture your desktop, launch
stress tools or require HWiNFO. Python-only receiver tests also run on Linux:

```sh
python3 -m unittest discover -s tests -v
```

Read-only shared-memory diagnostics:

```powershell
.\build\hwtrace.exe --diagnose
```

See [troubleshooting](docs/troubleshooting.md), [validation coverage](docs/validation.md)
and [contributing](CONTRIBUTING.md).

## Web dashboard

On the receiver, run the dashboard against an existing database:

```sh
python dashboard.py --db /path/to/hwtrace.sqlite3 --open-browser
```

On Windows, double-click `Open-Dashboard.cmd` to use `data/hwtrace.sqlite3`.
Keep its command window open; close it to stop the dashboard. Python 3.12+ is
required; Node.js is only needed for developer tests.

Open `http://127.0.0.1:8765/`. The interface currently uses Chinese labels and
browser-local time. It shows the latest collector session with five-second
refreshes and lets you select older sessions. Search and select up to 50 sensors
per panel, grouped into charts by unit. Hover for plotted values and timestamps;
drag to zoom, scroll to pan and double-click to go back one zoom level. Each chart
supports sample-group averages and temperature sensors have editable visual
thresholds. Legends show stable IDs and extrema for the current range.

The dashboard reads SQLite without changing telemetry or controlling collection.
It has no login and listens on localhost by default. Long results are downsampled;
averages and plots can hide brief peaks. The last-record timestamp is a freshness
indicator, not proof of an active SSH connection. See the [dashboard guide](docs/dashboard.md)
for controls, interpretation, remote access and HTTP endpoints.

## License

[MIT](LICENSE). Upstream acknowledgements and preserved license text are in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
