# Deployment

## Receiver setup

Use an SSH server on Linux/WSL or Windows. The collector account needs permission
to run Python and write the database directory. Configure SSH keys and host-key
verification outside the repository. Test a noninteractive login before collection.

Linux/WSL: copy `receiver.py` to `~/hwtrace/` and create `~/hwtrace/data/`. Replace
the example host and paths in this collector-side SSH command:

```text
ssh.exe -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=5 -o ServerAliveInterval=5 -o ServerAliveCountMax=3 telemetry@receiver.example.net python3 /home/telemetry/hwtrace/receiver.py --db /home/telemetry/hwtrace/data/hwtrace.sqlite3 --ack
```

Windows: copy `receiver.py` to `C:\HWTrace`, create `C:\HWTrace\data`, and substitute
the actual Python installation path:

```text
ssh.exe -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=5 -o ServerAliveInterval=5 -o ServerAliveCountMax=3 telemetry@receiver.example.net C:/Python312/python.exe C:/HWTrace/receiver.py --db C:/HWTrace/data/hwtrace.sqlite3 --ack
```

The server shell controls quoting. Test paths containing spaces independently.
Use a direct Python receiver command, not a pipeline or wrapper: the launcher
appends receiver arguments for startup images.

For WSL2 NAT, LAN access may require a port forward and firewall rule. The WSL
address can change. See [WSL networking](https://learn.microsoft.com/en-us/windows/wsl/networking).
Keep the receiver awake during collection.

## Collector files

Preserve these relative paths on the Windows collector:

```text
build/hwtrace.exe
Start-HWTrace.ps1
Startup-Capture.ps1
capture/DesktopCapture.cs
ddr5.filter
collector.example.json
```

Copy the example to `collector.json` and edit:

| Field | Meaning |
| --- | --- |
| `ssh_command` | Noninteractive receiver command, including `--ack` |
| `executable` | Collector executable relative to the launcher |
| `filter` | Filter file relative to the launcher |
| `process` | Comma-separated executable names; default `TM5.exe,y-cruncher.exe` |
| `grace_seconds` | Post-exit delay; default `600` |

Versioned executable paths can stage an update beside a running collector. Copies
do not hot-reload a process. Restart manually after updates, and keep the receiver
compatible with the collector/launcher.

Run either TM5 or y-cruncher without editing the configuration between tests.
Existing configurations containing only `TM5.exe` keep that behavior: change
`process` to `TM5.exe,y-cruncher.exe` to enable both. Single executable names remain
supported; a list accepts up to 16 unique names, matched without regard to case.
Wildcards and executable paths are not accepted.

The `y-cruncher.exe` entry also detects optimized executables whose names start
with a digit in a `Binaries` directory with a sibling `y-cruncher.exe` launcher in
the parent directory, even when that launcher is not running. Inspecting these
workers requires permission to query their executable path; keep the installed
directory layout. Custom layouts can instead list exact executable names.
Startup screenshot detection uses the same native check. Process start/exit
events identify each configured name; a y-cruncher launcher/worker transition
counts as one monitored tool while at least one is observed. These events report
process presence, not test iterations, calculation failures or error counts.

Collection waits indefinitely until a configured test is first observed, then
continues for `grace_seconds` after all observed test processes exit. Detection
of either test during that interval cancels the pending stop. No test program is
launched by HWTrace.

## Manual startup

Enable HWiNFO Shared Memory Support, open Sensors and choose a 500 ms polling
interval. From PowerShell 7 on the logged-in collector desktop:

```powershell
Set-Location C:\HWTrace
pwsh -NoProfile -File .\Start-HWTrace.ps1
```

The script does not launch HWiNFO or the monitored process. If the process already
exists, one physical-pixel desktop PNG is captured on a background thread as
collection begins. Otherwise no screenshot worker is created. An unavailable
desktop or failed image upload does not stop telemetry; inspect stderr.

No task, service, remote repository or startup entry is installed by the scripts.
Screenshots remain on the receiver until removed. Stop receiver writers before
deleting a database or its WAL/SHM files.

## Optional dashboard on the receiver

The SSH receiver needs no persistent HTTP server. For a browser view, also copy
`dashboard.py` and `web/` to the receiver (or use a full checkout), then run:

```sh
python dashboard.py --db /path/to/hwtrace.sqlite3 --open-browser
```

On Windows, `Open-Dashboard.cmd` opens `data/hwtrace.sqlite3` from the project
directory. The dashboard is a separate process; restarting it does not restart
collection. Its default address is `http://127.0.0.1:8765/`. Keep the listener on
loopback and use an SSH tunnel for remote viewing. See the
[dashboard guide](dashboard.md) for controls, file requirements and limitations.
