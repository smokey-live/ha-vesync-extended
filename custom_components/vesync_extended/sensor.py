"""Non-identifying humidity, PM2.5, filter-life, and mist status values."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfDensity

from .entity import VeSyncExtendedEntity

_SENSORS = {
    "pm25": ("PM2.5", SensorDeviceClass.PM25, UnitOfDensity.MICROGRAMS_PER_CUBIC_METER),
    "filter_life": ("Filter life", None, PERCENTAGE),
    "humidity": ("Humidity", SensorDeviceClass.HUMIDITY, PERCENTAGE),
    "mist_level": ("Mist level", None, None),
}


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    entities = []
    for device in coordinator.client.devices.values():
        keys = ("pm25", "filter_life") if device.is_purifier else ("humidity", "mist_level")
        entities.extend(VeSyncExtendedSensor(coordinator, device, key) for key in keys)
    async_add_entities(entities)


class VeSyncExtendedSensor(VeSyncExtendedEntity, SensorEntity):
    """Return unknown for missing optional values rather than inventing zeros."""

    def __init__(self, coordinator, device, key):
        super().__init__(coordinator, device, key)
        self.key = key
        self._attr_name, self._attr_device_class, self._attr_native_unit_of_measurement = _SENSORS[
            key
        ]
        if key != "mist_level":
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        return getattr(self.device_state, self.key)
