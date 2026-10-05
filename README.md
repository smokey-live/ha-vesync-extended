# VeSync Extended for Home Assistant

Experimental support for newer Levoit products that pyvesync 3.4.2 does not discover.
This custom integration has its own `vesync_extended` domain and can run alongside
Home Assistant's official VeSync integration. It selects only the exact models below.

**Status: development preview. Version 0.1.5 has verified live status reads in
Home Assistant 2026.9.4 for two `LAP-P501S-WUSR` purifiers and one `LUH-N451S-WUS`
humidifier. Power-off and power-on were physically confirmed on one US purifier
and the humidifier. All three purifier speeds and a humidifier target change
were confirmed in the app and later cloud readings. Night-light on/off,
brightness and visible warm/cool changes were physically confirmed on the
humidifier. Controls remain experimental; see the
[live validation record](docs/VALIDATION.md). Read-only mode is enabled by default.
Protocol tests use synthetic fixtures.**

Version 0.1.5 adds a separate NeoClassic 450S **Night light** entity with on/off,
brightness and tunable-white temperature (1700–5500 K). The brightness slider edits the
preset reported active by the cloud, while `brightness_l1`, `brightness_l2` and
`active_preset` expose the saved readings. Selecting L1/L2 alone was accepted but
had no physical effect, so a preset selector is not offered. It does not switch humidification on or off.
Live Home Assistant brightness/temperature commands changed the lamp and the
app, but cloud readings retained earlier values beyond the short confirmation
window. Home Assistant can therefore report a confirmation error after a
successful physical change. Check the lamp/app before repeating a command.

Version 0.1.4 fixes the three-speed percentage conversion using Home Assistant's
standard 33%, 66% and 100% levels. Initial display tests also found delayed cloud
status and a command acknowledgment issue corrected in 0.1.3.

| Product | VeSync cloud identifier | Readings and candidate controls |
| --- | --- | --- |
| Vital Pet Pro air purifier | `LAP-P501S-WUSR`, `LAP-P501S-AUSR` | Power, three speeds, manual/auto/sleep/pet, PM2.5, filter life, display, child lock |
| NeoClassic 450S cool-mist humidifier | `LUH-N451S-WUS` | Power, manual/auto/sleep, current and target humidity, display, mist-level reading, tunable-white night light, saved L1/L2 readings |

Product labels may omit the region suffix. The integration matches the identifier
returned by the cloud, rather than assuming that similarly named products share a protocol.
Devices already handled by the official integration are excluded here.

Status reads also recognize the observed `odorShieldBalanced` purifier mode and
`autoPro` humidifier mode. Their exact cloud names appear in the entity's
`cloud_mode` attribute. They are not added to the selectable modes or command
allowlist, because a status response alone does not verify how to set that mode.

Mist-level writes, music, scenes, schedules, firmware updates and filter
resets are not implemented. The reported physical and virtual mist-level ranges
need verification before exposing a mist control. The NeoClassic 450S has no warm-mist control.

## Installation for testing

Requires Home Assistant 2026.9.4 or later. This version is the initial compatibility target;
later releases require their own validation. The integration depends on the same
`pyvesync==3.4.2` package as that release's official VeSync integration.

1. Back up the Home Assistant configuration.
2. Copy `custom_components/vesync_extended` into the Home Assistant configuration's
   `custom_components` directory. Do not rename it to `vesync`.
3. Restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration → VeSync Extended**.
5. Choose **Use an existing VeSync account** if the official integration is already
   configured, or enter credentials manually. Select the account and two-letter
   country code. Keep **Read-only mode** enabled for the first test. Saved credentials
   are reused inside Home Assistant; the setup form never receives the password.
6. Compare the live readings with the VeSync app. Unknown or incompatible responses
   leave the affected device unavailable rather than guessing its state.
7. After verifying status, use the integration's options to disable read-only mode
   for reversible control tests. Read-only mode is enforced by the client even if
   a service tries to call a control directly.

In HACS, this repository may also be added as a **custom repository** in the
**Integration** category. It is not listed in the default HACS catalog.

The default polling interval is 60 seconds per device, shared by all entities.
Options allow increasing it up to 900 seconds. Reload the integration to discover
devices added to the account after setup.

## Read-only probe

The probe authenticates, lists the exact supported models, and requests status.
It sends no device-setting commands. Its output contains model identifiers and an
explicit whitelist of status values; it omits email, tokens, names, MAC addresses,
cloud IDs and request bodies.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install 'pyvesync==3.4.2'
.venv/bin/python scripts/probe.py
```

The password prompt is hidden. Credentials are never accepted as command-line arguments.
In a Python environment with access to the Home Assistant configuration and dependencies,
`python scripts/probe.py --ha-config /config` can use the existing official VeSync
entry without displaying or copying its credentials. This requires exactly one official
VeSync config entry. It only reads `.storage/core.config_entries`; it never edits it.

Save a local report with `--output live-results/status.json`. The `live-results`
directory is ignored by Git. Review any report before deliberately sharing it.

## Development and validation

```sh
python3 -m venv .venv
.venv/bin/python -m pip install 'pyvesync==3.4.2' pytest pytest-asyncio ruff
.venv/bin/python -m pytest
.venv/bin/ruff check .
```

CI also imports the integration and checks entity behavior inside the official
Home Assistant 2026.9.4 container. See [validation](docs/VALIDATION.md) for the live
test checklist and [protocol notes](docs/PROTOCOL.md) for the implementation evidence.
Record behavior changes in [CHANGELOG.md](CHANGELOG.md).

## Troubleshooting and rollback

- Authentication uses pyvesync's existing login flow. If it cannot authenticate
  the account, the new device handlers will not solve that separate problem.
- The integration uses the VeSync cloud API; it does not provide local-only control.
- An offline or incompatible device affects its own entities. A successful cloud
  response with an inner device error is treated as a failure.
- A display command can be accepted and take effect before the cloud reports its
  new state. Version 0.1.3 checks immediately and after 2, 4 and 6 seconds. If it
  reports that the device did not confirm the setting, check the physical device
  and wait for normal polling before repeating the command. Live tests observed
  delayed readings beyond this confirmation window. An acknowledgment alone is
  not proof of the final device state.
- Night-light commands use the same bounded confirmation reads. The lamp's state
  and sliders show actual cloud readings, which can lag behind a physical change.
  Allow polling to catch up before making another preset/brightness adjustment.
  An on/off request leaves saved brightness and temperature unchanged; a brightness
  request changes only its specified preset. White temperature is rounded to the
  app's 100 K steps. RGB colors, transitions and blinking effects are not exposed.
- Removing the VeSync Extended config entry unloads its entities. To remove the
  files, move `custom_components/vesync_extended` outside `custom_components` and
  restart Home Assistant. The official VeSync entry is independent.
- Diagnostic downloads omit account and device identifiers. Raw VeSync debug logs
  and packet captures may contain secrets; do not attach them to public issues.

## Credits

- [pyvesync](https://github.com/webdjoe/pyvesync) supplies authentication and request defaults.
- [pyvesync PR #532](https://github.com/webdjoe/pyvesync/pull/532) reports real-device
  Vital Pet Pro support and a candidate request-signature algorithm. It remains
  unmerged; this integration does not claim upstream approval.
- [Homebridge Levoit Humidifiers](https://github.com/pschroeder89/homebridge-levoit-humidifiers)
  documents NeoClassic 450S support and the newer camelCase command fields.

This project is independent of Levoit, VeSync, Home Assistant and those upstream projects.
Original project code is Apache-2.0 licensed. See [NOTICE](NOTICE) for attribution.
