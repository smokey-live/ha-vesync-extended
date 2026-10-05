# Changelog

## 0.1.5 — 2026-10-04

- Add an independent NeoClassic 450S Night light entity for on/off, brightness,
  tunable-white temperature (1700–5500 K, 100 K steps) and L1/L2 saved readings.
- Normalize only the observed nested `nightLight` fields. Unknown light data
  leaves the lamp unavailable without breaking the humidifier's other entities.
- Use allowlisted partial `setLightStatus` commands so unrequested preset
  brightness and temperature are not overwritten with potentially stale readings.
- Confirm requested light values with bounded status reads, without resending
  commands or publishing an assumed state. Enforce read-only mode on light writes.
- Test both brightness mappings, round trips, limits, unsupported fields,
  missing state and delayed confirmation separately from live device evidence.
- Physically verify Home Assistant dim/warm and bright/cool changes without
  interrupting humidification. Remove the preset selector after a preset-only
  command was accepted but had no physical effect; reject that command shape.
- Document confirmation errors after physically successful brightness/temperature
  commands, separating device behavior from delayed cloud readings.

## 0.1.4 — 2026-10-04

- Use Home Assistant's standard ordered-speed conversion in both directions:
  levels 1, 2 and 3 report 33%, 66% and 100%. Reapplying a reported speed now
  preserves that level; the previous rounded 67% reading selected level 3.
- Check each speed's round trip, conversion boundaries, off and invalid requests
  in the Home Assistant 2026.9.4 smoke test.
- Record physically confirmed power-off and power-on tests on one US purifier
  and one NeoClassic 450S, plus an app- and cloud-confirmed target-humidity
  change and restoration. Other control outcomes are documented separately.
- Verify all three purifier speeds through Home Assistant, the official app and
  later cloud readings; restore Auto Balanced through the official app.

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

This is a development preview. See the validation record for individual control
outcomes on the owned US models. Additional controls and the Australian purifier
variant still require verification.
