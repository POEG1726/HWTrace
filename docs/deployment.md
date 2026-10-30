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
| `process` | Executable name to observe; default `TM5.exe` |
| `grace_seconds` | Post-exit delay; default `600` |

Versioned executable paths can stage an update beside a running collector. Copies
do not hot-reload a process. Restart manually after updates, and keep the receiver
compatible with the collector/launcher.

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
