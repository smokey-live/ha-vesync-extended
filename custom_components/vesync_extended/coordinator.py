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


def control_confirmed(state, action, value):
    """Compare only settings requested by a display or night-light command."""
    if not state.available:
        return False
    if action == "display":
        return state.display is value
    if state.night_light is not value["on"]:
        return False
    if "level" in value and state.light_level != value["level"]:
        return False
    if "kelvin" in value and state.light_kelvin != value["kelvin"]:
        return False
    if "brightness" in value:
        actual = state.light_brightness if value["level"] == 1 else state.light_brightness_level2
        if actual != value["brightness"]:
            return False
    return True


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
            if action in {"display", "light"}:
                # Acknowledgments can precede the device's updated cloud status.
                # Read again without resending the setting command.
                for delay in (2, 4, 6):
                    if control_confirmed(state, action, value):
                        break
                    await asyncio.sleep(delay)
                    state = await self.client.get_state(device)
                if not control_confirmed(state, action, value):
                    self.async_set_updated_data({**self.data, device.cid: state})
                    name = "display" if action == "display" else "night-light"
                    raise HomeAssistantError(f"Device did not confirm the requested {name} setting")
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed("VeSync session expired") from err
        except (ApiError, ValueError, TimeoutError) as err:
            raise HomeAssistantError(
                "VeSync control failed; check read-only mode and connectivity"
            ) from err
        self.async_set_updated_data({**self.data, device.cid: state})
