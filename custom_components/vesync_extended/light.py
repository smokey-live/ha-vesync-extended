"""NeoClassic 450S tunable-white night light, independent of humidification."""

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ColorMode,
    LightEntity,
)
from homeassistant.exceptions import HomeAssistantError

from .const import MAX_LIGHT_KELVIN, MIN_LIGHT_KELVIN
from .entity import VeSyncExtendedEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    if coordinator.client.read_only:
        return
    async_add_entities(
        VeSyncExtendedLight(coordinator, device)
        for device in coordinator.client.devices.values()
        if not device.is_purifier
    )


class VeSyncExtendedLight(VeSyncExtendedEntity, LightEntity):
    """Read confirmed lamp state and change only the requested settings."""

    _attr_name = "Night light"
    _attr_supported_color_modes = {ColorMode.COLOR_TEMP}
    _attr_color_mode = ColorMode.COLOR_TEMP
    _attr_min_color_temp_kelvin = MIN_LIGHT_KELVIN
    _attr_max_color_temp_kelvin = MAX_LIGHT_KELVIN

    def __init__(self, coordinator, device):
        super().__init__(coordinator, device, "night_light")

    @property
    def available(self):
        return super().available and self.device_state.night_light is not None

    @property
    def is_on(self):
        return self.device_state.night_light

    @property
    def brightness(self):
        state = self.device_state
        value = (
            state.light_brightness
            if state.light_level == 1
            else state.light_brightness_level2
            if state.light_level == 2
            else None
        )
        return round(value * 255 / 100) if value is not None else None

    @property
    def color_temp_kelvin(self):
        return self.device_state.light_kelvin

    @property
    def extra_state_attributes(self):
        return {
            "brightness_l1": self.device_state.light_brightness,
            "brightness_l2": self.device_state.light_brightness_level2,
            "active_preset": (
                f"L{self.device_state.light_level}"
                if self.device_state.light_level in (1, 2)
                else None
            ),
        }

    async def async_turn_on(self, **kwargs):
        value = {"on": True}
        level = self.device_state.light_level
        if ATTR_EFFECT in kwargs:
            raise ValueError("Preset selection is not supported; use the VeSync app")
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            if type(brightness) is not int or not 0 <= brightness <= 255:
                raise ValueError("Brightness must be an integer from 0 to 255")
            if brightness == 0:
                await self.async_turn_off()
                return
            if level not in (1, 2):
                raise HomeAssistantError("The active night-light preset is unknown")
            value["level"] = level
            value["brightness"] = max(1, round(brightness * 100 / 255))
        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            kelvin = kwargs[ATTR_COLOR_TEMP_KELVIN]
            if type(kelvin) is not int or not MIN_LIGHT_KELVIN <= kelvin <= MAX_LIGHT_KELVIN:
                raise ValueError("Night-light temperature is outside its supported range")
            value["kelvin"] = round(kelvin / 100) * 100
        await self.control("light", value)

    async def async_turn_off(self, **kwargs):
        await self.control("light", {"on": False})
