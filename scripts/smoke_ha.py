"""Import and entity checks in the official Home Assistant image; no cloud calls."""

from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


async def main():
    from homeassistant.components.fan import FanEntityFeature
    from homeassistant.core import HomeAssistant
    from homeassistant.exceptions import ConfigEntryAuthFailed

    from custom_components.vesync_extended.api import (
        AuthenticationError,
        Device,
        DeviceOffline,
        DeviceState,
        ExtendedClient,
        ReadOnlyError,
    )
    from custom_components.vesync_extended.config_flow import VeSyncExtendedConfigFlow
    from custom_components.vesync_extended.coordinator import VeSyncExtendedCoordinator
    from custom_components.vesync_extended.fan import VeSyncExtendedFan
    from custom_components.vesync_extended.humidifier import VeSyncExtendedHumidifier
    from custom_components.vesync_extended.sensor import VeSyncExtendedSensor
    from custom_components.vesync_extended.switch import VeSyncExtendedSwitch

    for module in ("coordinator", "diagnostics", "config_flow", "entity", "sensor", "switch"):
        importlib.import_module(f"custom_components.vesync_extended.{module}")

    hass = HomeAssistant("/tmp/vesync-extended-test")
    flow = VeSyncExtendedConfigFlow()
    flow.hass = hass
    form = await flow.async_step_user()
    assert form["type"] == "form"
    assert form["data_schema"]({"username": "test@example.invalid", "password": "test"})[
        "read_only"
    ]

    device = Device("fake-purifier", "Test purifier", "LAP-P501S-WUSR", "fake", "US")
    humidifier = Device("fake-humidifier", "Test humidifier", "LUH-N451S-WUS", "fake", "US")
    calls = []

    async def control(target, action, value):
        calls.append((target.cid, action, value))

    coordinator = SimpleNamespace(
        hass=hass,
        config_entry=None,
        last_update_success=True,
        client=SimpleNamespace(read_only=False),
        data={
            device.cid: DeviceState(available=True, power=True, mode="manual", speed=3, pm25=12),
            humidifier.cid: DeviceState(
                available=True,
                power=False,
                mode="auto",
                humidity=69,
                target_humidity=45,
                display=False,
            ),
        },
        async_control=control,
    )
    fan = VeSyncExtendedFan(coordinator, device)
    assert fan.is_on and fan.percentage == 100 and fan.speed_count == 3
    assert fan.supported_features & FanEntityFeature.SET_SPEED
    await fan.async_set_percentage(34)
    assert calls[-1] == (device.cid, "speed", 2)
    humid = VeSyncExtendedHumidifier(coordinator, humidifier)
    assert humid.is_on is False and humid.current_humidity == 69 and humid.target_humidity == 45
    assert VeSyncExtendedSensor(coordinator, device, "pm25").native_value == 12
    assert VeSyncExtendedSwitch(coordinator, humidifier, "display", "Display").is_on is False
    coordinator.data[device.cid] = DeviceState()
    assert not fan.available and fan.percentage is None

    coordinator.client.read_only = True
    assert not VeSyncExtendedFan(coordinator, device).supported_features
    client = ExtendedClient(SimpleNamespace(), SimpleNamespace(), read_only=True)
    try:
        await client.command(device, "power", True)
    except ReadOnlyError:
        pass
    else:
        raise AssertionError("Read-only mode issued a write")

    class PartialClient:
        devices = {device.cid: device, humidifier.cid: humidifier}

        async def get_state(self, target):
            if target.is_purifier:
                raise DeviceOffline("Device offline", -11300030)
            return coordinator.data[humidifier.cid]

    entry = SimpleNamespace(options={}, async_on_unload=lambda callback: None)
    poller = VeSyncExtendedCoordinator(hass, entry, PartialClient())
    states = await poller._async_update_data()
    assert not states[device.cid].available and states[humidifier.cid].available

    class ExpiredClient(PartialClient):
        async def get_state(self, target):
            raise AuthenticationError("Expired")

    poller.client = ExpiredClient()
    try:
        await poller._async_update_data()
    except ConfigEntryAuthFailed:
        pass
    else:
        raise AssertionError("Expired authentication did not trigger reauthentication")
    print("HA imports, config form, entity state, read-only, offline isolation, and reauth passed")


if __name__ == "__main__":
    asyncio.run(main())
