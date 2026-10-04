"""Shared device identity and availability handling."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import DeviceState
from .const import DOMAIN


class VeSyncExtendedEntity(CoordinatorEntity):
    """Base for an entity backed by one validated cloud device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, device, key):
        super().__init__(coordinator, context=device.cid)
        self.device = device
        self._attr_unique_id = f"{device.cid}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.cid)},
            manufacturer="Levoit",
            model=device.model,
            name=device.name,
            sw_version=device.firmware,
        )

    @property
    def device_state(self):
        return self.coordinator.data.get(self.device.cid, DeviceState())

    @property
    def available(self):
        return super().available and self.device_state.available

    async def control(self, action, value):
        await self.coordinator.async_control(self.device, action, value)
