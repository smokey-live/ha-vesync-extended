"""VeSync Extended integration entry points."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .const import CONF_READ_ONLY, PLATFORMS

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load the account and fetch initial status before adding entities."""
    from homeassistant.const import CONF_COUNTRY, CONF_PASSWORD, CONF_USERNAME
    from homeassistant.helpers.aiohttp_client import async_get_clientsession
    from pyvesync import VeSync

    from .api import ExtendedClient
    from .coordinator import VeSyncExtendedCoordinator

    session = async_get_clientsession(hass)
    manager = VeSync(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        country_code=entry.data.get(CONF_COUNTRY, "US"),
        session=session,
        time_zone=hass.config.time_zone,
        redact=True,
    )
    client = ExtendedClient(
        manager,
        session,
        read_only=entry.options.get(CONF_READ_ONLY, entry.data.get(CONF_READ_ONLY, True)),
    )
    coordinator = VeSyncExtendedCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload all platforms. Home Assistant owns the shared HTTP session."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply changed options through a normal integration reload."""
    await hass.config_entries.async_reload(entry.entry_id)
