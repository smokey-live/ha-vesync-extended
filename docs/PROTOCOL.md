# Protocol evidence and implementation decisions

## Discovery failure

The official Home Assistant integration on the initial installation uses pyvesync 3.4.2.
The cloud returns newer devices, but its device map has no `LAP-P501S-WUSR` or
`LUH-N451S-WUS` entries. This project requests the account's device list directly
and filters exact model identifiers. It does not mutate pyvesync's global map.

## Vital Pet Pro

Source: [pyvesync PR #532](https://github.com/webdjoe/pyvesync/pull/532), inspected 2026-10-04.
Inspected head: `70504e0ce8158732837d25886516e46e64674f12`.
The author reports read and write tests on `LAP-P501S-WUSR`. The maintainer requested
a dedicated feature map and evidence for the additional signature headers. Those
requests remain unresolved in the inspected change.

Status method: `getPurifierStatus`. Important fields are `powerSwitch`, `workMode`,
`fanSpeedLevel`, `manualSpeedLevel`, `PM25`, `filterLifePercent`, `screenSwitch` and
`childLockSwitch`. Light sensor and timer fields may be absent. No light-sensor
capability is advertised by this integration.

| Action | Method | Data |
| --- | --- | --- |
| Power | `setSwitch` | `powerSwitch: 0/1`, `switchIdx: 0` |
| Manual speed | `setLevel` | `levelIdx: 0`, `manualSpeedLevel: 1..3`, `levelType: wind` |
| Preset | `setPurifierMode` | `workMode: manual/auto/sleep/pet` |
| Display | `setDisplay` | `screenSwitch: 0/1` |
| Child lock | `setChildLock` | `childLockSwitch: 0/1` |

Selecting manual mode uses `setLevel` at speed 1, following pyvesync's distinction
between entering manual mode and selecting other presets.

Version 0.1.4 uses Home Assistant's ordered-list percentage helpers with levels
`[1, 2, 3]`, matching the approach in its
[official VeSync fan platform](https://github.com/home-assistant/core/blob/2026.9.4/homeassistant/components/vesync/fan.py).
The reported percentages are 33, 66 and 100; positive requests up to 33 select
level 1, up to 66 select level 2, and higher requests select level 3. Zero is a
power-off request. This makes every reported speed round-trip correctly, fixing
the prototype's rounded level-2 reading of 67, which its ceiling conversion
incorrectly sent back as level 3.

The candidate `_packFileSignature` algorithm and `_signOsInfo: Android` header
are applied only to this integration's purifier Bypass V2 requests. Authentication
and other integrations are unchanged. The signature is regenerated with each
request and after a token refresh. Live status requests succeeded on two US units.
Initial display commands were accepted; the physical display changed on one unit
and a later status read changed on the second. Subsequent power tests were
physically confirmed on one US unit; see the validation record for individual
control evidence. Live token-refresh behavior remains unverified.

## NeoClassic 450S

Sources: [Homebridge device profile](https://github.com/pschroeder89/homebridge-levoit-humidifiers/blob/main/src/api/deviceTypes.ts)
and [command implementation](https://github.com/pschroeder89/homebridge-levoit-humidifiers/blob/main/src/api/VeSyncFan.ts),
inspected 2026-10-04. Its support was added in version 1.21.0.
Inspected main commit: `15a814c5412507b75b59fb818089774545a8c870`.

Status method: `getHumidifierStatus`. New-format fields include `powerSwitch`,
`workMode`, `humidity`, `targetHumidity`, `screenSwitch` and `virtualLevel`.
This differs from the older OasisMist snake_case responses.

| Action | Method | Data |
| --- | --- | --- |
| Power | `setSwitch` | `powerSwitch: 0/1`, `id: 0` |
| Target humidity | `setTargetHumidity` | `targetHumidity: 30..80`, `id: 0` |
| Mode | `setHumidityMode` | `workMode: manual/auto/sleep` |
| Display | `setDisplay` | `screenSwitch: 0/1`, `id: 0` |

The Homebridge client uses POST for reads and PUT for writes. The initial prototype
follows that behavior for the humidifier; purifier requests follow pyvesync's POST
behavior. Both transport and device response codes are checked.

### NeoClassic tunable-white night light — 0.1.5

This model returns a nested `nightLight` object with `nightLightSwitch`,
`brightness`, `brightnessLevel2`, `nightLightLevel` and `colorTemperature`.
Its official app exposes two brightness presets, L1 and L2, a 1–100% slider,
and a white-temperature slider with endpoints 1700 and 5500 K in 100 K steps.
The integration reads only these fields, independently of humidifier power.
Invalid light fields remain unknown and do not invalidate other device readings.

A starting point for the newer command shape was a contributor's intercepted
[Sprout command report](https://github.com/orgs/home-assistant/discussions/901)
in the Home Assistant discussion (inspected 2026-10-04). That report concerns a
different model and does not establish NeoClassic support. Its range must not be
copied to this model. Candidate commands were then tested on the exact
`LUH-N451S-WUS`; see [validation](VALIDATION.md) for what each observation confirms.
Homebridge's older snake_case brightness method and RGB `rgbNightLight` parser
do not match the light schema observed on this NeoClassic unit.

| Requested light setting | Method | Data |
| --- | --- | --- |
| On/off | `setLightStatus` | `nightLightSwitch: 0/1`, `colorMode: white` |
| Select L1/L2 | `setLightStatus` | Same switch/color fields, `nightLightLevel: 1/2` |
| L1 brightness | `setLightStatus` | Same switch/color fields, `nightLightLevel: 1`, `brightness: 1..100` |
| L2 brightness | `setLightStatus` | Same switch/color fields, `nightLightLevel: 2`, `brightnessLevel2: 1..100` |
| White temperature | `setLightStatus` | Same switch/color fields, `colorTemperature: 1700..5500` in 100 K steps |

These fields may be combined in one command. Only requested settings are sent.
On/off never copies brightness or temperature from an older status response.
Brightness requires a known or explicitly selected preset and leaves the other
preset unchanged. Home Assistant's effect selector represents L1/L2; this is not
an RGB or animated light effect. Temperature requests are rounded to 100 K.
Status confirmation compares only the requested values, with the same bounded
read retries as display control. A stale response can report a confirmation
failure after the physical lamp has already changed; commands are not resent.

Homebridge's profile reports nine virtual mist levels. Its original
[device request](https://github.com/pschroeder89/homebridge-levoit-humidifiers/issues/109)
reports five mist levels. These may represent distinct physical and virtual scales;
that is an inference and is not yet tested. Mist state is readable, while mist
commands are intentionally not available.

## Capture limits

A normal Wireshark capture of the app's VeSync cloud connections shows TLS traffic,
not readable command bodies. Existing implementations provide enough evidence to
try basic controls first. Unknown lighting, audio and scene commands may still need
decrypted application traffic. No certificate-trust changes or app instrumentation
are required by this prototype.

## Live status findings — 2026-10-04

Read-only discovery succeeded for two `LAP-P501S-WUSR` units and one `LUH-N451S-WUS`.
All three returned successful outer and inner response codes with the documented
status fields. The initial parser rejected them because the current `workMode`
values differed from the older mode allowlist: `odorShieldBalanced` on both
purifiers and `autoPro` on the humidifier. The official app displayed the purifiers
in Auto mode. The official humidifier app displayed Auto with the Smart submode.
Homebridge's shared mode enum includes `autoPro`, but its inspected 450S profile
does not enable the separate `hasAutoProMode` flag; it does not verify a writable
mapping for this observed mode.

These exact values are now accepted by the status parser and preserved as the
`cloud_mode` entity attribute. Readable modes and command modes have separate
allowlists. The new status names are not offered as selectable modes and cannot
be sent as mode commands. Their write semantics, and any mapping from an older
`auto` command to the new modes, remain unverified.

Version 0.1.2 subsequently loaded all three devices in Home Assistant 2026.9.4
after a Core restart, with successful live status and read-only mode enabled.
See the [validation record](VALIDATION.md) for the comparison limits. No control
commands were issued during this verification.

Unavailable-state diagnostics now retain the client-generated error reason.
Those messages contain only fixed explanations and numeric HTTP/error codes;
they never include a raw cloud message or request/response body.

## Display acknowledgment findings — 2026-10-04

A live purifier display command returned outer code 0 and inner code 0, but its
inner envelope contained only `code` and `traceId`, with no `result`. Version 0.1.2
therefore reported an error even though a physical display change was observed.
Version 0.1.3 accepts this acknowledgment shape for writes only; it still rejects
missing inner envelopes, nonzero codes, and explicit null/malformed results.
Display controls read status again for confirmation, retrying reads after 2, 4
and 6 seconds when necessary. Commands are never resent by that confirmation loop.
The display test and restoration outcomes are recorded in [validation](VALIDATION.md).

Fresh status requests during these tests continued to return the previous display
value beyond that confirmation window, before later reads returned the new value.
The official app could also retain an earlier display setting. This establishes
that command acknowledgment, app indication, physical observation and status-read
confirmation are distinct evidence. It does not establish a fixed latency or the
cause of the delayed reporting. `screenState` and `screenSwitch` eventually agreed
on the inspected purifier readings; the parser continues to use `screenSwitch`.
No undocumented display-preference command was sent.
