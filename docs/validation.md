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
| Process detection | Exact/case-insensitive lists, invalid names, y-cruncher launcher and direct optimized worker, unrelated-binary exclusion, native/startup parity |
| Test lifecycle | Per-tool events, failed snapshot retention, grace cancellation on test changes, never-seen and zero-grace cases |
| Cleanup | Slow upload does not block native execution; cancellation releases resources |
| Geometry | Physical bounds under DPI-unaware caller; original context restored |
| Pixel copy | Both extreme corners of an offscreen bitmap are copied |
| Dashboard queries | Session/sensor identity, ordinal downsampling, range queries, partial averages and extrema |
| Dashboard HTTP | Static files/API, invalid requests, read-only database access and connection cleanup |
| Dashboard interactions | Zoom, pan, averaging requests and canvas/hover/drag preservation during refresh |

Receiver tests have run on Windows and WSL. Native fixtures and PowerShell tests
have run locally on Windows. Live HWiNFO/SSH smoke tests and accelerated lifecycle/
reconnect checks were performed during development; private operational data is
not distributed.

Dashboard interaction checks run with `node tests/test_dashboard_ui.js` (Node.js
18+, no npm dependencies), and are included in `scripts/test.ps1` and CI. They
execute the browser code with a synthetic DOM/canvas, not a real browser. HTTP
checks use an ephemeral loopback server and synthetic database. These checks do
not certify every browser layout, touch gesture or rendering environment.

Limits:

- The full 600-second grace period was not waited out; accelerated tests exercise
  the same configurable timer path.
- A real multi-monitor screenshot after the DPI/async changes still needs manual
  visual acceptance on destination hardware. Geometry tests do not certify every
  display driver, HDR mode, lock screen or mixed-DPI topology.
- GitHub Actions runs Linux Python/dashboard checks and the full Windows build
  and test script. Consult the repository's Actions tab for the result of a
  particular commit; local success alone does not certify a hosted run.
- This early project is not a stress-test stability certification or a CPU/RAM
  performance guarantee across hardware.
