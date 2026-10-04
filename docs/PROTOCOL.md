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

The candidate `_packFileSignature` algorithm and `_signOsInfo: Android` header
are applied only to this integration's purifier Bypass V2 requests. Authentication
and other integrations are unchanged. The signature is regenerated with each
request and after a token refresh. Live verification is required.

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
| Display | `setDisplay` | `screenSwitch: 0/1` |

The Homebridge client uses POST for reads and PUT for writes. The initial prototype
follows that behavior for the humidifier; purifier requests follow pyvesync's POST
behavior. Both transport and device response codes are checked.

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
