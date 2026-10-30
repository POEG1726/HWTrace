# Troubleshooting

## No telemetry

Verify SSH independently with key authentication, `BatchMode=yes` and host-key
checking. Confirm the receiver Python/script paths and a writable database
directory. Include `--ack`; stdout must contain only acknowledgements. Shell
banners, wrappers and interactive prompts can break the protocol.

## Shared memory unavailable

Run `build/hwtrace.exe --diagnose`. It is read-only, opens no SSH connection and
does not launch a stress tool. Additional read-only probes are under `tools/`.

- Win32 error 2 means the mapping was not found.
- Win32 error 5 means access was denied; this differs from an absent mapping.
- Mapping-view, region-size, allocation and header errors have separate diagnostics.

Check HWiNFO Shared Memory Support and the active Sensors window. A stored INI
value alone does not prove runtime publication. HWiNFO licensing/session limits
can affect availability. Restarting a stress tool is not a shared-memory fix.
Reinitializing HWiNFO can be a controlled experiment when it is safe to disturb
monitoring; it is not a guaranteed solution.

## Missing readings

Match rules against actual names/groups. CSVs can contain aggregates or renamed
columns which are not standalone readings. Names can be localized. Profiles load
at startup and allow 128 rules of up to 127 bytes. An empty file selects all
readings, subject to the 64 KiB record limit.

Legacy name fields use the Windows ANSI code page; legacy units use CP1252
(for example `B0 43` for degrees Celsius). Optional UTF-8 name extensions are not
currently read. Verify customized/non-ASCII names on your installation.

## Screenshots

Launch from the logged-in desktop. No worker is created if the monitored process
is absent. Capture uses physical monitor rectangles and a temporary thread DPI
context so scaling does not crop it. Active displays, including negative monitor
coordinates, are combined into one PNG.

The worker waits for the native startup signal. Scheduling can still delay it;
actual pixel-copy start/end are recorded. Slow uploads do not delay telemetry.
Errors use stderr. Check `startup_captures`, not only a pending event, for success.

## Drops and shutdown

The fixed ring drops new records when full; there is no local spool. A rejected
receiver record can block subsequent records until corrected or collection is
restarted. Reduce the profile if a record exceeds 64 KiB. Native shutdown allows
five seconds to drain. The launcher joins/cancels a pending screenshot worker.
Unsent/dropped native records produce nonzero exit status.
