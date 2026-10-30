# Deployed collector

Use PowerShell 7 (pwsh). The collector is build/hwtrace.exe; source and receiver.py are included for reference. DEPLOYMENT.json records the deployed commit and binary hash.

Before starting, configure the receiver computer's SSH service and key authentication from THIS tested machine. The key allowing deployment from the receiver to this machine does not automatically enable the reverse connection.

Copy collector.example.json to collector.json. Set ssh_command to a verified noninteractive SSH command which launches receiver.py with --db and --ack on the receiver. Python and database paths must be valid on the receiver. The receiver may run on Windows or Linux/WSL. If using Windows, test the remote command with that server's configured SSH shell and quote its paths accordingly. Keep private keys outside this project.

Enable HWiNFO Shared Memory Support and set its polling interval to 500 ms, then open Sensors. When ready, start manually:

```powershell
Set-Location C:\HWTrace
Copy-Item collector.example.json collector.json
# Edit collector.json before running the next command.
pwsh -NoProfile -File .\Start-HWTrace.ps1
```

The default process is TM5.exe and the post-exit delay is 600 seconds. Enter text followed by Enter for a manual marker. Ctrl+C stops the collector. No scheduled task, service, or startup entry is installed. The collector creates no local telemetry log or database.
