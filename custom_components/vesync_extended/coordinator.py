"""One poll per device shared by all of its Home Assistant entities."""

from __future__ import annotations

import logging
from copy import copy
from datetime import timedelta
from time import monotonic

from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ApiError, AuthenticationError, DeviceOffline, DeviceState
from .const import CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)
_PENDING_SECONDS = 180


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


def apply_requested_state(state, action, value):
    """Apply an acknowledged request while VeSync's status endpoint catches up."""
    state = copy(state)
    if action == "power":
        state.power = value
    elif action == "mode":
        state.mode = value
    elif action == "speed":
        state.speed = value
    elif action == "humidity":
        state.target_humidity = value
    elif action == "display":
        state.display = value
    elif action == "child_lock":
        state.child_lock = value
    elif action == "light":
        state.night_light = value["on"]
        if "level" in value:
            state.light_level = value["level"]
        if "brightness" in value:
            key = "light_brightness" if value["level"] == 1 else "light_brightness_level2"
            setattr(state, key, value["brightness"])
        if "kelvin" in value:
            state.light_kelvin = value["kelvin"]
    return state


def request_confirmed(state, action, value):
    """Return whether a fresh cloud state contains an acknowledged request."""
    if action in {"display", "light"}:
        return control_confirmed(state, action, value)
    if action == "power":
        return state.power is value
    if action == "mode":
        return state.mode == value or (value == "auto" and state.mode == "autoPro")
    if action == "speed":
        return state.speed == value
    if action == "humidity":
        return state.target_humidity == value
    if action == "child_lock":
        return state.child_lock is value
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
        self._pending = {}

    def _merge_pending(self, cid, state):
        now = monotonic()
        for key, (value, expires) in list(self._pending.items()):
            pending_cid, action = key
            if pending_cid != cid:
                continue
            if request_confirmed(state, action, value) or now >= expires:
                self._pending.pop(key, None)
            else:
                state = apply_requested_state(state, action, value)
        return state

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
                state = await self.client.get_state(device)
                states[cid] = self._merge_pending(cid, state)
            except AuthenticationError as err:
                raise ConfigEntryAuthFailed("VeSync session expired") from err
            except (DeviceOffline, ApiError) as err:
                states[cid] = DeviceState(error_code=err.code, error_reason=str(err))
            except TimeoutError:
                states[cid] = DeviceState(error_reason="Status request timed out")
        return states

    async def async_control(self, device, action, value):
        """Refresh the actual state after a successful command."""
        current = self.data.get(device.cid, DeviceState())
        if not current.available:
            raise HomeAssistantError("This device has no validated status response")
        if action == "display" and not device.is_purifier and current.mode == "sleep":
            raise HomeAssistantError(
                "The humidifier controls its display in Sleep mode; change mode first"
            )
        try:
            await self.client.command(device, action, value)
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed("VeSync session expired") from err
        except (ApiError, ValueError, TimeoutError) as err:
            detail = str(err) or type(err).__name__
            if isinstance(err, ApiError) and err.code is not None:
                detail = f"{detail} (code {err.code})"
            raise HomeAssistantError(f"VeSync control failed: {detail}") from err
        self._pending[(device.cid, action)] = (value, monotonic() + _PENDING_SECONDS)
        state = apply_requested_state(current, action, value)
        self.async_set_updated_data({**self.data, device.cid: state})
