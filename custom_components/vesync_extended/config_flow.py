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
        if user_input is None and self._existing_accounts():
            return self.async_show_menu(step_id="user", menu_options=["existing_account", "manual"])
        return await self._account_step("user", user_input)

    async def async_step_manual(self, user_input=None):
        return await self._account_step("manual", user_input)

    def _existing_accounts(self):
        """Keep saved credentials inside Core; expose only account choices to the form."""
        return {
            entry.entry_id: entry
            for entry in self.hass.config_entries.async_entries("vesync")
            if isinstance(entry.data.get(CONF_USERNAME), str)
            and entry.data[CONF_USERNAME]
            and isinstance(entry.data.get(CONF_PASSWORD), str)
            and entry.data[CONF_PASSWORD]
        }

    async def async_step_existing_account(self, user_input=None):
        accounts = self._existing_accounts()
        if not accounts:
            return self.async_abort(reason="no_existing_account")
        errors = {}
        if user_input is not None:
            entry = accounts.get(user_input["account"])
            if entry is None:
                errors["base"] = "existing_account_missing"
            else:
                account_data = {
                    CONF_USERNAME: entry.data[CONF_USERNAME].strip().lower(),
                    CONF_PASSWORD: entry.data[CONF_PASSWORD],
                    CONF_COUNTRY: user_input[CONF_COUNTRY].strip().upper(),
                    CONF_READ_ONLY: user_input[CONF_READ_ONLY],
                }
                errors = await self._validate_account(account_data)
                if not errors:
                    return await self._finish_account("user", account_data)
        defaults = user_input or {}
        return self.async_show_form(
            step_id="existing_account",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "account", default=defaults.get("account", next(iter(accounts)))
                    ): (vol.In({entry_id: entry.title for entry_id, entry in accounts.items()})),
                    vol.Required(CONF_COUNTRY, default=defaults.get(CONF_COUNTRY, "US")): vol.All(
                        str, vol.Length(min=2, max=2)
                    ),
                    vol.Required(CONF_READ_ONLY, default=defaults.get(CONF_READ_ONLY, True)): bool,
                }
            ),
            errors=errors,
        )

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
            errors = await self._validate_account(user_input)
            if not errors:
                return await self._finish_account(step_id, user_input)
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

    async def _validate_account(self, account_data):
        session = async_get_clientsession(self.hass)
        manager = VeSync(
            account_data[CONF_USERNAME],
            account_data[CONF_PASSWORD],
            country_code=account_data[CONF_COUNTRY],
            session=session,
            time_zone=self.hass.config.time_zone,
            redact=True,
        )
        client = ExtendedClient(manager, session)
        try:
            await client.login()
            if not await client.discover():
                return {"base": "no_devices"}
        except AuthenticationError:
            return {"base": "invalid_auth"}
        except (ApiError, ClientError, TimeoutError):
            return {"base": "cannot_connect"}
        return {}

    async def _finish_account(self, step_id, account_data):
        await self.async_set_unique_id(account_data[CONF_USERNAME])
        if step_id == "reauth_confirm":
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data_updates=account_data
            )
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="VeSync Extended", data=account_data)

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
