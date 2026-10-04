"""Vital Pet Pro power, presets, and three manual speeds."""

import math

from homeassistant.components.fan import FanEntity, FanEntityFeature

from .const import PURIFIER_MODES
from .entity import VeSyncExtendedEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    async_add_entities(
        VeSyncExtendedFan(coordinator, device)
        for device in coordinator.client.devices.values()
        if device.is_purifier
    )


class VeSyncExtendedFan(VeSyncExtendedEntity, FanEntity):
    """Expose actual state and confirm control results through a new status read."""

    _attr_name = None
    _attr_speed_count = 3
    _attr_preset_modes = list(PURIFIER_MODES)

    def __init__(self, coordinator, device):
        super().__init__(coordinator, device, "fan")
        if not coordinator.client.read_only:
            self._attr_supported_features = (
                FanEntityFeature.SET_SPEED
                | FanEntityFeature.PRESET_MODE
                | FanEntityFeature.TURN_ON
                | FanEntityFeature.TURN_OFF
            )
        else:
            self._attr_supported_features = FanEntityFeature(0)

    @property
    def is_on(self):
        return self.device_state.power

    @property
    def percentage(self):
        if self.is_on is False:
            return 0
        speed = self.device_state.speed
        return round(speed * 100 / 3) if speed is not None else None

    @property
    def preset_mode(self):
        return self.device_state.mode

    async def async_turn_on(self, percentage=None, preset_mode=None, **kwargs):
        await self.control("power", True)
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
        elif percentage is not None:
            await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs):
        await self.control("power", False)

    async def async_set_percentage(self, percentage):
        if not 0 <= percentage <= 100:
            raise ValueError("Percentage must be between 0 and 100")
        if percentage == 0:
            await self.async_turn_off()
        else:
            await self.control("speed", math.ceil(percentage * 3 / 100))

    async def async_set_preset_mode(self, preset_mode):
        await self.control("mode", preset_mode)
