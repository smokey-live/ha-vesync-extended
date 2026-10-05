"""One poll per device shared by all of its Home Assistant entities."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ApiError, AuthenticationError, DeviceOffline, DeviceState
from .const import CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class VeSyncExtendedCoordinator(DataUpdateCoordinator[dict[str, DeviceState]]):
    """Keep failures local to an individual device whenever possible."""

    def __init__(self, hass, entry, client):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(
                seconds=entry.options.get(
                    CONF_POLL_INTERVAL,
                    DEFAULT_POLL_INTERVAL,
                )
            ),
            always_update=False,
        )
        self.client = client

    async def _async_setup(self):
        try:
            await self.client.login()
            await self.client.discover()
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed("VeSync login failed") from err
        except ApiError as err:
            raise UpdateFailed("Could not discover VeSync devices") from err
        if not self.client.devices:
            raise UpdateFailed("No supported VeSync Extended devices found")

    async def _async_update_data(self):
        states = {}
        for cid, device in self.client.devices.items():
            try:
                states[cid] = await self.client.get_state(device)
            except AuthenticationError as err:
                raise ConfigEntryAuthFailed("VeSync session expired") from err
            except (DeviceOffline, ApiError) as err:
                states[cid] = DeviceState(error_code=err.code, error_reason=str(err))
            except TimeoutError:
                states[cid] = DeviceState(error_reason="Status request timed out")
        return states

    async def async_control(self, device, action, value):
        """Refresh the actual state after a successful command."""
        if not self.data.get(device.cid, DeviceState()).available:
            raise HomeAssistantError("This device has no validated status response")
        try:
            await self.client.command(device, action, value)
            state = await self.client.get_state(device)
            if action == "display":
                # Acknowledgments can precede the device's updated cloud status.
                # Read again without resending the setting command.
                for delay in (2, 4, 6):
                    if state.available and state.display is value:
                        break
                    await asyncio.sleep(delay)
                    state = await self.client.get_state(device)
                if not state.available or state.display is not value:
                    self.async_set_updated_data({**self.data, device.cid: state})
                    raise HomeAssistantError("Device did not confirm the requested display setting")
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed("VeSync session expired") from err
        except (ApiError, ValueError, TimeoutError) as err:
            raise HomeAssistantError(
                "VeSync control failed; check read-only mode and connectivity"
            ) from err
        self.async_set_updated_data({**self.data, device.cid: state})
