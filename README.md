# VeSync Extended for Home Assistant

Experimental support for newer Levoit products that pyvesync 3.4.2 does not discover.
This custom integration has its own `vesync_extended` domain and can run alongside
Home Assistant's official VeSync integration. It selects only the exact models below.

**Status: development preview. Version 0.1.2 has verified live status reads in
Home Assistant 2026.9.4 for two `LAP-P501S-WUSR` purifiers and one `LUH-N451S-WUS`
humidifier. Device-setting commands remain unverified. Read-only mode is enabled
by default. Protocol tests use synthetic fixtures.**

| Product | VeSync cloud identifier | Readings and candidate controls |
| --- | --- | --- |
| Vital Pet Pro air purifier | `LAP-P501S-WUSR`, `LAP-P501S-AUSR` | Power, three speeds, manual/auto/sleep/pet, PM2.5, filter life, display, child lock |
| NeoClassic 450S cool-mist humidifier | `LUH-N451S-WUS` | Power, manual/auto/sleep, current and target humidity, display, mist-level reading |

Product labels may omit the region suffix. The integration matches the identifier
returned by the cloud, rather than assuming that similarly named products share a protocol.
Devices already handled by the official integration are excluded here.

Status reads also recognize the observed `odorShieldBalanced` purifier mode and
`autoPro` humidifier mode. Their exact cloud names appear in the entity's
`cloud_mode` attribute. They are not added to the selectable modes or command
allowlist, because a status response alone does not verify how to set that mode.

Mist-level writes, lighting, music, scenes, schedules, firmware updates and filter
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
