# Validation coverage

Checks are reproducible with `scripts/test.ps1` and Python unittest. Synthetic
telemetry/PNGs and an offscreen GDI bitmap replace private data. HWiNFO, a real
desktop screenshot, SSH accounts and stress tools are not required.

| Area | Coverage |
| --- | --- |
| SQLite | Metadata/value/event ingestion, WAL, deduplication, rollback, foreign keys |
| Native output | Non-finite initialization retains metadata; later values ingest |
| Units/profile | Legacy units, requested DDR5 rules and unrelated exclusions |
| Timing | Elapsed/uptime records and screenshot copy interval |
| Images | Binary upload, acknowledgement, hash/metadata and invalid input |
| Concurrency | Image and telemetry initialize one database concurrently |
| Startup | Process presence branches and native/managed event interoperability |
| Cleanup | Slow upload does not block native execution; cancellation releases resources |
| Geometry | Physical bounds under DPI-unaware caller; original context restored |
| Pixel copy | Both extreme corners of an offscreen bitmap are copied |

Receiver tests have run on Windows and WSL. Native fixtures and PowerShell tests
have run locally on Windows. Live HWiNFO/SSH smoke tests and accelerated lifecycle/
reconnect checks were performed during development; private operational data is
not distributed.

Limits:

- The full 600-second grace period was not waited out; accelerated tests exercise
  the same configurable timer path.
- A real multi-monitor screenshot after the DPI/async changes still needs manual
  visual acceptance on destination hardware. Geometry tests do not certify every
  display driver, HDR mode, lock screen or mixed-DPI topology.
- GitHub Actions is configured but has not run before the first remote push.
- This early project is not a stress-test stability certification or a CPU/RAM
  performance guarantee across hardware.
