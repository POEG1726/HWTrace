# Dashboard

The dashboard is an optional, read-only view of the receiver's existing SQLite
database. It uses Python's standard library and local HTML/CSS/JavaScript; there
is no npm build, runtime package installation or external chart service. The
interface currently uses Chinese labels. Times display in the browser's local
time zone, with milliseconds in hover details.

## Start and stop

Copy `dashboard.py` and the whole `web/` directory beside `receiver.py`, preserving
their relative paths, or run from a full checkout. Use Python 3.12+ on the machine
holding the database:

```sh
python dashboard.py --db /path/to/hwtrace.sqlite3 --open-browser
```

Open `http://127.0.0.1:8765/`. The optional `--open-browser` flag opens the browser
on the server machine. Use Ctrl+C in the terminal to stop the server. To choose
another port, add `--port 8766`. The dashboard requires an existing HWTrace
database; the receiver creates it when telemetry first arrives.

On Windows, double-click `Open-Dashboard.cmd` from a full checkout. It changes to
the project directory and uses `data/hwtrace.sqlite3`, trying `py -3` and then
`python` on PATH. Keep the terminal open while viewing. For another database or
Python installation, invoke `dashboard.py` directly with the desired executable.

Collection can continue while the dashboard reads the WAL database. It opens
SQLite with `mode=ro` and `query_only`; it does not add tables, change samples,
start the receiver or control HWiNFO/TM5. SQLite can still need access to WAL/SHM
sidecars. Keep the database on the receiver's local filesystem and use a coherent
SQLite backup when moving an active database; copying just its main file can
omit uncheckpointed data. The dashboard does not display events or screenshots.

## Sessions and controls

- **Latest session:** refreshes every five seconds. A new collector session resets
  this panel's selections. Older sessions are available in the history dropdown.
  The history panel is queried when selected or when its controls change.
- **Sensors:** search names, groups or units, then check up to 50 per panel.
  Sensor ID, instance and reading ID distinguish duplicate names. Charts group
  selected sensors by their stored unit; they do not convert compatible units.
- **Hover:** a crosshair shows each curve's nearest *plotted* point and its actual
  timestamp/value. It does not interpolate a sample at the cursor time.
- **Zoom:** drag horizontally at least eight pixels to request the selected time
  range from SQLite. Scroll a wheel or touchpad to pan that range; double-click
  to return one zoom level. These controls apply to each unit chart separately.
- **Average:** enter an integer from 1 to 10,000 per chart. Consecutive actual
  samples for each sensor within the range form groups; the final group may be
  smaller. The point's timestamp is that group's last sample, not its midpoint.
- **Temperature threshold:** each selected temperature sensor has a field in
  degrees Celsius. Names containing SPD, DIMM, DRAM, memory or memoria default
  to 50 °C; others default to 80 °C. Fahrenheit curves convert this guide to °F.
  Clear the field to disable highlighting. Red denotes the displayed value at or
  above the guide, including when averaged. These are visual guides, not hardware
  safety limits or alarms. Settings reset on session change or page reload.

Live refresh preserves chart canvases during hover and drag. Selections, averages,
thresholds and zoom state live only in the browser page and are not written to
the database or collector configuration.

## Interpret the data

A session is a collector run. SSH reconnects retain its ID, and the stored schema
does not reconstruct connection/disconnection boundaries. A recent last-record
timestamp does not prove that SSH is connected. A recorded `collector_stop`
indicates an orderly stop event; its absence is not proof of a running process.

Long results are reduced to approximately 2,000 points per sensor, retaining the
last point. This is positional downsampling, not peak-preserving aggregation.
Zooming re-queries the range; averaging happens before downsampling. Both can
hide brief peaks. Legend minima/maxima use all values in the requested range
before plot downsampling; with averaging enabled they describe the averaged
groups, not raw extrema. Consequently an extremum may not appear on the curve.

Ranges use recorded UTC timestamps. Clock adjustments can make them differ from
collector sequence order; the dashboard is not a monotonic-time analysis tool.
Large databases or many selected sensors can make queries slower than the
five-second refresh interval. Reduce selections or zoom into a shorter range.

## Access and privacy

`--host` defaults to `127.0.0.1`. The server has no authentication or TLS; any
client able to reach it can query stored sensor names, IDs and telemetry. Keep it
on loopback. To view a remote receiver securely, forward a local port over SSH:

```sh
ssh -N -L 8765:127.0.0.1:8765 telemetry@receiver.example.net
```

Run the dashboard on that receiver with its default host, then open
`http://127.0.0.1:8765/` locally. If that port is occupied, forward local port 8766
instead. A WSL receiver should run the dashboard within the same WSL distribution;
Windows can usually use localhost forwarding. Neither publishing source nor
starting this viewer uploads databases or screenshots to GitHub.

## Read-only HTTP endpoints

| Endpoint | Parameters | Response |
| --- | --- | --- |
| `/api/sessions` | None | Sessions, first/last sequence, timestamps, stop-event presence |
| `/api/sensors` | `session` | Sensor IDs, names and units for that session |
| `/api/series` | `session`, repeated `sensor=ID:INSTANCE:READING` | Per-sensor points, minimum and maximum |

`/api/series` also accepts `average=1..10000` and an optional paired `start`/`end`
in Unix epoch milliseconds with `start < end`. Up to 50 sensors are allowed.
Unaveraged full-session points are `[UTC timestamp, value]`; averaged or ranged
queries return `[UTC timestamp, value, actual group size]`. An unknown session
has no sensors/data. Invalid parameters return HTTP 400; unknown paths return
404. There are no mutation endpoints. The API is intended for this local viewer,
not as a hardened public service.
