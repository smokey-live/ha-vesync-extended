"""Display and purifier child lock controls."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory

from .entity import VeSyncExtendedEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    if coordinator.client.read_only:
        return
    entities = []
    for device in coordinator.client.devices.values():
        entities.append(VeSyncExtendedSwitch(coordinator, device, "display", "Display"))
        if device.is_purifier:
            entities.append(VeSyncExtendedSwitch(coordinator, device, "child_lock", "Child lock"))
    async_add_entities(entities)


class VeSyncExtendedSwitch(VeSyncExtendedEntity, SwitchEntity):
    """Only expose controls on an entry with write access enabled."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, device, key, name):
        super().__init__(coordinator, device, key)
        self.key = key
        self._attr_name = name

    @property
    def available(self):
        return super().available and getattr(self.device_state, self.key) is not None

    @property
    def is_on(self):
        return getattr(self.device_state, self.key)

    async def async_turn_on(self, **kwargs):
        await self.control(self.key, True)

    async def async_turn_off(self, **kwargs):
        await self.control(self.key, False)
