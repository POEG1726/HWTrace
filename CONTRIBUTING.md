# Contributing

Keep changes small and the native collector dependency-free. Preserve its RAM-only
design. Keep generated artifacts and machine configuration out of Git; public
fixtures and bug reports should use synthetic data.

Build and test from the root:

```powershell
pwsh -NoProfile -File .\scripts\test.ps1 -Compiler gcc
# Or: pwsh -NoProfile -File .\scripts\test.ps1 -UseWsl
```

Python-only checks: `python -m unittest discover -s tests -v`.
C/C# formatting follows `.clang-format`; Python follows Black defaults. PowerShell
uses four-space indentation. Formatters are optional developer tools, not runtime
dependencies.

Document protocol changes, preserve reconnect deduplication, and isolate startup
capture from sampling. Tests must not capture a real desktop, start a stress tool
or depend on private SSH hosts. Redact names, network addresses, sensor serials,
personal paths, credentials and desktop contents before sharing a repro.

Preserve upstream license notices when adapting code. See [SECURITY.md](SECURITY.md).
