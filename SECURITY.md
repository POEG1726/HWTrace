# Security and privacy

HWTrace handles hardware metadata and can capture an entire desktop when the
monitored process already exists. Images can include unrelated applications or
private information. The native executable alone does not take screenshots.
OpenSSH supplies transport encryption/authentication; verify host keys and use an
appropriately scoped key/account.

Receiver databases and PNGs are ordinary, unencrypted local files. Restrict access
and retention. Keep configuration, private keys, telemetry, screenshots, exports
and operational notes outside public commits. `.gitignore` covers common private
paths but is not a secret scanner.

Do not post credentials, real screenshots or private databases in public issues.
Use synthetic/redacted reproductions. If the repository enables GitHub private
vulnerability reporting, use its Security tab for sensitive reports. No public
contact address is embedded in this distribution.

The receiver is intended for a trusted SSH-authenticated collector, not anonymous
network input. It validates bounds and PNG headers but does not sandbox arbitrary
shell commands or fully decode/inspect PNG content.
