# Changelog

## 0.1.3 — 2026-10-04

- Accept command acknowledgments that omit the inner result only when both response
  codes indicate success. Status reads still require a data result.
- Confirm display changes with bounded fresh status reads, without resending the command.
- Include the documented `id: 0` in NeoClassic display commands.
- Test delayed confirmation, unchanged state, read-only failure, and malformed acknowledgments.
- Record initial live display tests and cloud readings that lag beyond the
  confirmation window; retain the experimental-control warning.

## 0.1.2 — 2026-10-04

- Recognize live-observed `odorShieldBalanced` and `autoPro` status modes.
- Preserve those exact values as `cloud_mode` attributes without making them writable.
- Expose read-only status and existing display/child-lock readings as entity attributes.
- Include safe client error reasons in unavailable-state diagnostics and probe reports.
- Test that the newly readable modes remain blocked by the command allowlist.
- Verify live status on two US Vital Pet Pro units and one NeoClassic 450S after
  installation and a Home Assistant 2026.9.4 restart, with read-only mode enabled.

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

This is a development preview. Live status reads and initial display tests have
been performed on the owned US models. Other device-setting commands and the
Australian purifier variant remain untested.
