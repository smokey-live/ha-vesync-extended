"""NeoClassic 450S humidifier entity."""

from homeassistant.components.humidifier import (
    HumidifierDeviceClass,
    HumidifierEntity,
    HumidifierEntityFeature,
)

from .const import HUMIDIFIER_MODES
from .entity import VeSyncExtendedEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    async_add_entities(
        VeSyncExtendedHumidifier(coordinator, device)
        for device in coordinator.client.devices.values()
        if not device.is_purifier
    )


class VeSyncExtendedHumidifier(VeSyncExtendedEntity, HumidifierEntity):
    """Power, target humidity and operating mode; cool mist only."""

    _attr_name = None
    _attr_device_class = HumidifierDeviceClass.HUMIDIFIER
    _attr_min_humidity = 30
    _attr_max_humidity = 80
    _attr_available_modes = list(HUMIDIFIER_MODES)

    def __init__(self, coordinator, device):
        super().__init__(coordinator, device, "humidifier")
        self._attr_supported_features = (
            HumidifierEntityFeature(0)
            if coordinator.client.read_only
            else HumidifierEntityFeature.MODES
        )

    @property
    def is_on(self):
        return self.device_state.power

    @property
    def current_humidity(self):
        return self.device_state.humidity

    @property
    def target_humidity(self):
        return self.device_state.target_humidity

    @property
    def mode(self):
        mode = self.device_state.mode
        return mode if mode in HUMIDIFIER_MODES else None

    @property
    def extra_state_attributes(self):
        return {
            "read_only": self.coordinator.client.read_only,
            "cloud_mode": self.device_state.mode,
            "display": self.device_state.display,
        }

    async def async_turn_on(self, **kwargs):
        await self.control("power", True)

    async def async_turn_off(self, **kwargs):
        await self.control("power", False)

    async def async_set_humidity(self, humidity):
        await self.control("humidity", humidity)

    async def async_set_mode(self, mode):
        await self.control("mode", mode)
