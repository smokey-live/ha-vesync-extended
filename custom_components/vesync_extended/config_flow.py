"""Configuration and reauthentication for VeSync Extended."""

from __future__ import annotations

import voluptuous as vol
from aiohttp import ClientError
from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.const import CONF_COUNTRY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pyvesync import VeSync

from .api import ApiError, AuthenticationError, ExtendedClient
from .const import CONF_POLL_INTERVAL, CONF_READ_ONLY, DEFAULT_POLL_INTERVAL, DOMAIN


class VeSyncExtendedConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a VeSync account while leaving controls disabled initially."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        return await self._account_step("user", user_input)

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        return await self._account_step("reauth_confirm", user_input)

    async def _account_step(self, step_id, user_input):
        errors = {}
        if user_input is not None:
            user_input = dict(user_input)
            user_input[CONF_USERNAME] = user_input[CONF_USERNAME].strip().lower()
            user_input[CONF_COUNTRY] = user_input[CONF_COUNTRY].strip().upper()
            session = async_get_clientsession(self.hass)
            manager = VeSync(
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                country_code=user_input[CONF_COUNTRY],
                session=session,
                time_zone=self.hass.config.time_zone,
                redact=True,
            )
            client = ExtendedClient(manager, session)
            try:
                await client.login()
                devices = await client.discover()
                if not devices:
                    errors["base"] = "no_devices"
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except (ApiError, ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            if not errors:
                await self.async_set_unique_id(user_input[CONF_USERNAME])
                if step_id == "reauth_confirm":
                    self._abort_if_unique_id_mismatch(reason="wrong_account")
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(),
                        data_updates=user_input,
                    )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="VeSync Extended", data=user_input)
        defaults = user_input or {}
        if step_id == "reauth_confirm" and not defaults:
            defaults = self._get_reauth_entry().data
        schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_COUNTRY, default=defaults.get(CONF_COUNTRY, "US")): vol.All(
                    str, vol.Length(min=2, max=2)
                ),
                vol.Required(CONF_READ_ONLY, default=defaults.get(CONF_READ_ONLY, True)): bool,
            }
        )
        return self.async_show_form(step_id=step_id, data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return VeSyncExtendedOptionsFlow()


class VeSyncExtendedOptionsFlow(OptionsFlow):
    """Configure control access and the shared polling interval."""

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        defaults = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_READ_ONLY,
                        default=defaults.get(
                            CONF_READ_ONLY, self.config_entry.data.get(CONF_READ_ONLY, True)
                        ),
                    ): bool,
                    vol.Required(
                        CONF_POLL_INTERVAL,
                        default=defaults.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
                    ): vol.All(vol.Coerce(int), vol.Range(min=60, max=900)),
                }
            ),
        )
