# Validation record

## Automated checks

Protocol tests use synthetic fixtures based on public implementations, not live
captures. They cover missing optional fields, distinct family command shapes,
write allowlists and ranges, read-only enforcement, nested API failures, pagination,
bounded authentication retry and refreshed credentials/signature headers.

The Home Assistant smoke test runs against the official `2026.9.4` image. It imports
all platforms, builds entities, checks feature flags and state conversion, and
checks that read-only access cannot issue a device command. Saved-account setup is
checked for credential reuse, no password in forms or error responses, and refusal
of a removed account. It does not contact VeSync.

Automated checks cannot establish that a device accepts a command. Record that
evidence separately below after testing the owned devices.

## Live test sequence

1. Run the probe in read-only mode. Confirm it discovers the two purifier units and
   one NeoClassic 450S, and receives a valid status schema from each.
2. Compare power, mode, PM2.5, filter life, current humidity and target humidity with
   the official VeSync app. Missing optional fields should remain unknown.
3. Install the integration with read-only mode enabled. Confirm Home Assistant
   displays all three devices without affecting the official VeSync entry.
4. Record each device's original settings locally. Enable controls for the test.
5. Test purifier power and each of its three speeds, then restore the original
   power/mode/speed. Verify both the app and a new status response.
6. Test supported purifier presets, display and child lock individually. Restore
   original values after each test. Do not reset filters or change schedules.
7. For the humidifier, first change and restore the display. Then verify target
   humidity and mode using values selected for the room's current conditions.
   Only test humidification with water present and restore the original power/mode/target.
8. Reload and restart. Verify state survives normal setup and rediscovery.
9. Confirm a deliberately unavailable device does not make other devices unavailable.
10. Investigate mist levels and advanced features in later changes.

## Device results

Read-only discovery was performed on 2026-10-04 in Home Assistant 2026.9.4.
Version 0.1.1 found all three target devices, but rejected their new `workMode`
values. A temporary read-only probe confirmed successful response envelopes;
0.1.2 adds the exact observed mode names without widening the write allowlist.

Version 0.1.2 was then installed through HACS. Home Assistant's configuration check
passed, and after a Core restart all three devices were available with nine entities.
The downloaded diagnostics confirmed version 0.1.2, read-only mode enabled, valid
status for each device and no reported device errors. The separate official VeSync
entry remains configured.

Power, purifier filter life, display and child-lock readings, and humidifier current
humidity/display were compared with the official app. The app showed Auto for both
purifiers while the cloud returned `odorShieldBalanced`; that observation does not
verify a writable alias. Home Assistant displayed the reported PM2.5, target
humidity and virtual mist level, but those exact values were not independently
confirmed in the app. The humidifier was off during this test. No device-setting
commands were sent.

The released code passed 41 protocol tests, Ruff checks, and the Home Assistant
2026.9.4 compatibility smoke test in
[CI](https://github.com/smokey-live/ha-vesync-extended/actions/runs/37233943162).
These checks do not replace live control testing.

| Model | Status | Control | Restart | Notes |
| --- | --- | --- | --- | --- |
| `LAP-P501S-WUSR` | Passed on two units | Not tested | Passed | Both available after Core restart; new cloud mode preserved |
| `LAP-P501S-AUSR` | Not tested | Not tested | Not tested | No owned unit available |
| `LUH-N451S-WUS` | Passed while powered off | Not tested | Passed | Physical versus virtual mist levels unresolved; powered-on behavior untested |

Do not publish credentials, tokens, names, MAC addresses, cloud IDs, home addresses,
network captures or raw authentication/device-list responses. A reviewed summary
of models, features, firmware versions and pass/fail outcomes is sufficient.
