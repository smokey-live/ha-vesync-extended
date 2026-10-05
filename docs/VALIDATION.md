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

### Power tests — 2026-10-04

With water present in the humidifier, Home Assistant sent explicit power-off
and power-on commands to one `LAP-P501S-WUSR` and one `LUH-N451S-WUS`. The owner
physically confirmed that the purifier stopped blowing air and ran again after
restoration, and that the humidifier stopped misting and resumed after restoration.
No control command was sent to the second purifier during these tests.

The Home Assistant action calls completed without a reported device error.
Immediate status reads can still show the older power value, as seen when the
purifier's UI returned to on after its physically confirmed off command. Explicit
on/off actions were used for restoration rather than toggling an outdated reading.
These observations verify the physical power behavior, not immediate cloud-state
confirmation or a guaranteed reporting delay.

### Target-humidity test — 2026-10-04

Home Assistant changed the `LUH-N451S-WUS` target from 59% to 60%. The official
app showed 60%, and a separate read-only client later obtained a fresh device
status with `targetHumidity: 60` and `workMode: autoPro`. The first Home Assistant
diagnostic download still showed 59%. This confirms the command and illustrates
that the app and API can report the changed target at different times.

An explicit Home Assistant command restored 59%, and the app showed that original
target again. After installing 0.1.4 and restarting Core, downloaded diagnostics
also confirmed 59%, power on, `autoPro`, display off and no device error. No mode,
mist-level or schedule command was sent during this test.

### Three-speed test — 2026-10-04

After installing 0.1.4, Home Assistant controlled one `LAP-P501S-WUSR` through
high, medium and low in that order. Each selection appeared in the official app
as Manual mode with the corresponding numbered speed. Separate downloaded
diagnostics later confirmed `workMode: manual` and levels 3, 2 and 1 respectively.

| Home Assistant selection | App speed | Later cloud speed | Home Assistant percentage |
| --- | --- | --- | --- |
| High (100% service request) | 3 | 3 | 100% |
| Medium (fan control) | 2 | 2 | 66% |
| Low (fan control) | 1 | 1 | 33% |

The medium and low selections were tested through Home Assistant's actual fan
control. The app updated before Home Assistant's reported percentage; a selected
radio button alone was not treated as confirmation. No command was resent while
waiting for the later status. Speed evidence is from app and cloud readings;
independent physical airflow confirmation was not recorded for these steps.

The official app restored the original Auto Balanced mode, with display off,
control lock off and mute unchanged. Using the official app for this restoration
does not verify how a Home Assistant `auto` command maps to `odorShieldBalanced`.
The second purifier received no setting commands and retained its recorded
power, mode, display and child-lock values throughout the speed tests.

Final downloaded diagnostics confirmed version 0.1.4 with read-only mode
re-enabled, all three devices available and no device error. The tested purifier
returned to `odorShieldBalanced`, power on, level 1, display off and child lock
off. The humidifier retained `autoPro`, power on, target 59% and display off.
The second purifier's recorded power, mode, speed, display and child lock also
matched its baseline. Advanced preset commands, child lock and mist-level writes
remain untested.

### Fan-speed conversion regression — 0.1.4

Code inspection found that level 2 reported 67% but a 67% request selected level 3.
The Home Assistant smoke test now checks that all three reported percentages
round-trip to the same level, along with the boundaries between levels, off,
unknown state and out-of-range input. Version 0.1.4 uses Home Assistant's standard
ordered-list helpers and reports 33%, 66% and 100%. These synthetic checks do not
establish live speed-control behavior.

Version 0.1.4 passed 53 protocol tests, Ruff checks and the Home Assistant 2026.9.4
smoke test, including the speed conversion checks, in
[CI](https://github.com/smokey-live/ha-vesync-extended/actions/runs/37254643514).
It was installed through HACS, passed `ha core check`, and loaded all three
supported devices after a Core restart. Downloaded runtime diagnostics confirmed
0.1.4, each device available and no device error.

### Display tests — 2026-10-04

Only display-setting commands were authorized and sent. Power, speed, mode,
humidity, child lock and schedules were not changed by the test client.

Display testing exposed an acknowledgment parsing issue in 0.1.2: a purifier
returned both success codes, but the integration rejected the envelope because it
omitted the inner data result. The owner observed the display turn on and later
confirmed it was off again after restoration. A later cloud read also reported
off. Version 0.1.3 corrects acknowledgment parsing and adds bounded display-state
confirmation. It was installed through HACS, passed the configuration check and
loaded all three devices after a Core restart.

On the second purifier, the display-off command was accepted but status reads
retained the earlier on setting through the short confirmation window. A later
fresh status response and Home Assistant's normal polling reported off. The
original on setting was restored and confirmed by a later Home Assistant status
read. Physical verification of this unit was not obtained during the test.

The humidifier's app display switch changed from off to on after its test command.
A pre-existing VeSync schedule also turned the humidifier on during the observation
period. No power command was sent, and this scheduled change is not evidence of
the integration's power control. Cloud status initially retained its earlier
values, then reported display on and power on in later reads and Home Assistant
polling. The display was restored to off, confirmed first in the app and then in
Home Assistant status. Physical verification of the humidifier display was not obtained.

Final downloaded diagnostics confirmed version 0.1.3, read-only mode re-enabled,
all three devices available, no reported device errors and display values matching
each unit's recorded baseline. The humidifier remained under its existing schedule.
At the end of these display-only tests, no power, speed, mode, humidity or
child-lock test had been claimed as successful.

These are partial control results. Version 0.1.3 can report "Device did not confirm
the requested display setting" despite a later display change. The cause and
maximum duration of the delayed reporting are unresolved. Neither an immediate
UI toggle nor a successful acknowledgment alone is treated as a confirmed change.
Other commands were untested at this stage.

Version 0.1.3 passed 53 protocol tests, Ruff checks and the Home Assistant 2026.9.4
smoke test in [CI](https://github.com/smokey-live/ha-vesync-extended/actions/runs/37251618362).

### Initial read-only installation

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
[CI](https://github.com/smokey-live/ha-vesync-extended/actions/runs/37234114098).
These checks do not replace live control testing.

| Model | Status | Control | Restart | Notes |
| --- | --- | --- | --- | --- |
| `LAP-P501S-WUSR` | Passed on two units | Power physically verified on one; three speeds verified in app/cloud; display partial | Passed | Auto Balanced restored with official app; preset commands and child lock untested; reporting delay unresolved |
| `LAP-P501S-AUSR` | Not tested | Not tested | Not tested | No owned unit available |
| `LUH-N451S-WUS` | Passed before and after power tests | Power physically verified; target change/restoration and display verified in app/cloud | Passed | Mode commands and mist scales untested; physical display unconfirmed; reporting delay unresolved |

Do not publish credentials, tokens, names, MAC addresses, cloud IDs, home addresses,
network captures or raw authentication/device-list responses. A reviewed summary
of models, features, firmware versions and pass/fail outcomes is sufficient.
