# Changelog

## 0.1.1 — 2026-10-04

- Add setup using an existing official VeSync account without re-entering its password.
- Keep saved credentials inside Core and out of setup forms, including error responses.
- Check saved-account reuse, stale selections, and credential privacy in the HA smoke test.

## 0.1.0 — 2026-10-04

- Create a separate VeSync Extended integration for Vital Pet Pro and NeoClassic 450S.
- Reuse pyvesync 3.4.2 authentication without changing its device map or transport.
- Add a default read-only mode, exact-model discovery and normalized status handling.
- Implement candidate power, mode, three-speed purifier, humidity, display and child-lock controls.
- Add a read-only probe and diagnostics that omit account and device identifiers.
- Add protocol tests and a Home Assistant 2026.9.4 import/entity smoke test in CI.
- Withhold mist-level writes, lighting and scene/music features pending live verification.

This is a development preview. Live-device behavior has not yet been verified.
