"""Import and entity checks in the official Home Assistant image; no cloud calls."""

from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


async def main():
    from homeassistant.components.fan import FanEntityFeature
    from homeassistant.core import HomeAssistant
    from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError

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
    hass.config_entries = SimpleNamespace(async_entries=lambda domain: [])
    flow = VeSyncExtendedConfigFlow()
    flow.hass = hass
    form = await flow.async_step_user()
    assert form["type"] == "form"
    assert form["data_schema"]({"username": "test@example.invalid", "password": "test"})[
        "read_only"
    ]

    saved = SimpleNamespace(
        entry_id="saved-account",
        title="Saved VeSync account",
        data={"username": "test@example.invalid", "password": "synthetic-private-password"},
    )
    hass.config_entries = SimpleNamespace(async_entries=lambda domain: [saved])
    menu = await flow.async_step_user()
    assert menu["type"] == "menu" and menu["menu_options"] == ["existing_account", "manual"]
    saved_form = await flow.async_step_existing_account()
    assert "synthetic-private-password" not in repr(saved_form)
    selection = saved_form["data_schema"]({})
    assert selection["read_only"] and selection["account"] == saved.entry_id
    with (
        patch.object(flow, "_validate_account", AsyncMock(return_value={"base": "invalid_auth"})),
        patch.object(flow, "_finish_account", AsyncMock()) as finish,
    ):
        rejected = await flow.async_step_existing_account(selection)
        assert rejected["errors"] == {"base": "invalid_auth"}
        assert "synthetic-private-password" not in repr(rejected)
        finish.assert_not_awaited()
    with (
        patch.object(flow, "_validate_account", AsyncMock(return_value={})) as validate,
        patch.object(
            flow, "_finish_account", AsyncMock(return_value={"type": "create_entry"})
        ) as finish,
    ):
        result = await flow.async_step_existing_account(selection)
        assert result["type"] == "create_entry"
        assert validate.await_args.args[0]["password"] == saved.data["password"]
        assert finish.await_args.args[1]["read_only"]
    stale = await flow.async_step_existing_account({**selection, "account": "missing-account"})
    assert stale["errors"] == {"base": "existing_account_missing"}
    hass.config_entries = SimpleNamespace(async_entries=lambda domain: [])
    assert (await flow.async_step_existing_account())["reason"] == "no_existing_account"
    assert (await flow.async_step_manual())["type"] == "form"

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
    # Reapplying the displayed percentage must preserve each physical speed.
    for speed, percentage in ((1, 33), (2, 66), (3, 100)):
        coordinator.data[device.cid].speed = speed
        assert fan.percentage == percentage
        await fan.async_set_percentage(fan.percentage)
        assert calls[-1] == (device.cid, "speed", speed)
    for percentage, speed in ((1, 1), (33, 1), (34, 2), (66, 2), (67, 3), (100, 3)):
        await fan.async_set_percentage(percentage)
        assert calls[-1] == (device.cid, "speed", speed)
    await fan.async_set_percentage(0)
    assert calls[-1] == (device.cid, "power", False)
    for percentage in (-1, 101):
        count = len(calls)
        try:
            await fan.async_set_percentage(percentage)
        except ValueError:
            pass
        else:
            raise AssertionError("Out-of-range fan percentage was accepted")
        assert len(calls) == count
    coordinator.data[device.cid].speed = 0
    assert fan.percentage == 0
    coordinator.data[device.cid].power = False
    coordinator.data[device.cid].speed = 3
    assert fan.percentage == 0
    coordinator.data[device.cid].power = True
    humid = VeSyncExtendedHumidifier(coordinator, humidifier)
    assert humid.is_on is False and humid.current_humidity == 69 and humid.target_humidity == 45
    assert VeSyncExtendedSensor(coordinator, device, "pm25").native_value == 12
    assert VeSyncExtendedSwitch(coordinator, humidifier, "display", "Display").is_on is False
    coordinator.data[device.cid].mode = "odorShieldBalanced"
    coordinator.data[humidifier.cid].mode = "autoPro"
    assert fan.preset_mode is None and humid.mode is None
    assert fan.extra_state_attributes["cloud_mode"] == "odorShieldBalanced"
    assert humid.extra_state_attributes["cloud_mode"] == "autoPro"
    assert "odorShieldBalanced" not in fan.preset_modes
    assert "autoPro" not in humid.available_modes
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
    assert states[device.cid].error_reason == "Device offline"

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

    original_display = DeviceState(available=True, display=False, power=True, mode="manual")
    changed_display = DeviceState(available=True, display=True, power=True, mode="manual")
    writer = SimpleNamespace(
        command=AsyncMock(),
        get_state=AsyncMock(side_effect=[original_display, changed_display]),
    )
    poller.client = writer
    poller.async_set_updated_data({device.cid: original_display})
    with patch("custom_components.vesync_extended.coordinator.asyncio.sleep", AsyncMock()):
        await poller.async_control(device, "display", True)
    writer.command.assert_awaited_once_with(device, "display", True)
    assert writer.get_state.await_count == 2 and poller.data[device.cid].display is True

    writer.command.reset_mock()
    writer.get_state = AsyncMock(return_value=original_display)
    with patch("custom_components.vesync_extended.coordinator.asyncio.sleep", AsyncMock()):
        try:
            await poller.async_control(device, "display", True)
        except HomeAssistantError as err:
            assert "did not confirm" in str(err)
        else:
            raise AssertionError("Unchanged display was reported as a successful command")
    writer.command.assert_awaited_once()
    assert writer.get_state.await_count == 4 and poller.data[device.cid].display is False

    writer.command = AsyncMock(side_effect=ReadOnlyError("Controls disabled"))
    writer.get_state.reset_mock()
    try:
        await poller.async_control(device, "display", True)
    except HomeAssistantError:
        pass
    else:
        raise AssertionError("Read-only control failure was ignored")
    writer.get_state.assert_not_awaited()
    print(
        "HA imports, saved-account privacy, entity state, read-only, "
        "offline isolation, reauth, delayed display confirmation passed"
    )


if __name__ == "__main__":
    asyncio.run(main())
