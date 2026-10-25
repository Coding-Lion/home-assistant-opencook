"""UI setup, reconfiguration, and reauthentication for openCook."""

from hashlib import sha256
from typing import Any

try:
    import probatio as vol
except ImportError:  # Home Assistant before the probatio migration.
    import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .api import OpenCookAuthError, OpenCookClient, OpenCookError, normalize_url
from .const import CONF_HOUSEHOLD_CODE, CONF_URL, DOMAIN


def _schema(url: str = "http://homeassistant.local:8000") -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_URL, default=url): str,
            vol.Required(CONF_HOUSEHOLD_CODE): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
        }
    )


class OpenCookConfigFlow(ConfigFlow, domain=DOMAIN):
    """One config entry per household; validate without creating or changing data."""

    VERSION = 1

    async def _async_configure(self, step: str, user_input: dict[str, Any] | None):
        errors = {}
        entry = None
        if step == "reconfigure":
            entry = self._get_reconfigure_entry()
        elif step == "reauth_confirm":
            entry = self._get_reauth_entry()
        if user_input is not None:
            try:
                data = {
                    CONF_URL: normalize_url(user_input[CONF_URL]),
                    CONF_HOUSEHOLD_CODE: user_input[CONF_HOUSEHOLD_CODE].strip(),
                }
                if not data[CONF_HOUSEHOLD_CODE]:
                    raise OpenCookAuthError("Missing invite code")
                client = OpenCookClient(
                    async_get_clientsession(self.hass),
                    data[CONF_URL],
                    data[CONF_HOUSEHOLD_CODE],
                )
                await client.async_sync()
            except ValueError:
                errors["base"] = "invalid_url"
            except OpenCookAuthError:
                errors["base"] = "invalid_auth"
            except OpenCookError:
                errors["base"] = "cannot_connect"
            else:
                unique_id = sha256(data[CONF_HOUSEHOLD_CODE].encode()).hexdigest()
                await self.async_set_unique_id(unique_id)
                if entry is None or entry.unique_id != unique_id:
                    self._abort_if_unique_id_configured()
                if entry is not None:
                    # A refreshed code can replace a revoked credential. The entry's
                    # entity ID remains stable; new setups use the new credential hash.
                    self.hass.config_entries.async_update_entry(entry, unique_id=unique_id)
                    return self.async_update_reload_and_abort(
                        entry, data_updates=data, reason="reconfigure_successful"
                    )
                return self.async_create_entry(title=client.household_name, data=data)
        return self.async_show_form(
            step_id=step,
            data_schema=_schema(
                entry.data[CONF_URL] if entry else "http://homeassistant.local:8000"
            ),
            errors=errors,
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._async_configure("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._async_configure("reconfigure", user_input)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._async_configure("reauth_confirm", user_input)
