# Deployed collector

Use PowerShell 7 (pwsh). The collector is build/hwtrace.exe; source and receiver.py are included for reference. DEPLOYMENT.json records the deployed commit and binary hash.

Before starting, configure the receiver computer's SSH service and key authentication from THIS tested machine. The key allowing deployment from the receiver to this machine does not automatically enable the reverse connection.

Copy collector.example.json to collector.json. Set ssh_command to a verified noninteractive SSH command which launches receiver.py with --db and --ack on the receiver. Python and database paths must be valid on the receiver. The receiver may run on Windows or Linux/WSL. If using Windows, test the remote command with that server's configured SSH shell and quote its paths accordingly. Keep private keys outside this project.

Enable HWiNFO Shared Memory Support and set its polling interval to 500 ms, then open Sensors. When ready, start manually:

```powershell
Set-Location C:\HWTrace
if (-not (Test-Path collector.json)) { Copy-Item collector.example.json collector.json }
# Edit collector.json before running the next command.
pwsh -NoProfile -File .\Start-HWTrace.ps1
```

The default process is TM5.exe and the post-exit delay is 600 seconds. Enter text followed by Enter for a manual marker. Ctrl+C stops the collector. No scheduled task, service, or startup entry is installed. The collector creates no local telemetry log or database.

The deployed collector.json selects a versioned executable so copying an update cannot replace the active collector. Startup-Capture.ps1 is loaded by Start-HWTrace.ps1. A manual script restart is required to load a changed profile or executable. If TM5 is already present, one startup desktop screenshot is sent to the receiver; otherwise no screenshot is taken. The receiver's image directory is next to its database, under screenshots. No startup task or service is installed.

Fullscreen capture is DPI-aware and asynchronous. Keep the capture/DesktopCapture.cs source alongside Startup-Capture.ps1; PowerShell loads it on demand. The startup screenshot thread waits for the native collector's startup signal and reclaims its own resources when finished. No background job or scheduled task remains after capture/upload.
