import asyncio
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from plexapi.server import PlexServer
from plexapi.myplex import MyPlexAccount
from .const import DOMAIN, CONF_SERVER_URL, CONF_TOKEN

class PlexCustomConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Plex Custom Control."""

    VERSION = 1

    def __init__(self):
        """Initialize the flow."""
        self._pin = None
        self._token = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        return await self.async_step_auth_type()

    async def async_step_auth_type(self, user_input=None):
        """Choose authentication type."""
        if user_input is not None:
            if user_input["type"] == "pin":
                return await self.async_step_pin()
            return await self.async_step_manual()

        return self.async_show_form(
            step_id="auth_type",
            data_schema=vol.Schema({
                vol.Required("type", default="pin"): vol.In({
                    "pin": "Plex.tv PIN (Recommended)",
                    "manual": "Manual Token"
                })
            })
        )

    async def async_step_manual(self, user_input=None):
        """Manual token entry."""
        errors = {}
        if user_input is not None:
            self._token = user_input[CONF_TOKEN]
            return await self.async_step_server()

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({
                vol.Required(CONF_TOKEN): str,
            }),
            errors=errors,
        )

    async def async_step_pin(self, user_input=None):
        """PIN authentication flow."""
        if self._pin is None:
            def get_pin():
                return MyPlexAccount.requestPin(headers={"X-Plex-Product": "Plex Custom Control"})
            
            self._pin = await self.hass.async_add_executor_job(get_pin)

        if user_input is not None:
            # Check if PIN is authenticated
            def check_pin():
                return self._pin.check()
            
            authenticated = await self.hass.async_add_executor_job(check_pin)
            if authenticated:
                self._token = self._pin.authToken
                return await self.async_step_server()
            
            return self.async_show_form(
                step_id="pin",
                description_placeholders={
                    "code": self._pin.code,
                    "url": "https://plex.tv/link"
                },
                errors={"base": "not_authenticated"}
            )

        return self.async_show_form(
            step_id="pin",
            description_placeholders={
                "code": self._pin.code,
                "url": "https://plex.tv/link"
            }
        )

    async def async_step_server(self, user_input=None):
        """Select or enter server URL."""
        errors = {}
        if user_input is not None:
            try:
                def validate_plex():
                    return PlexServer(user_input[CONF_SERVER_URL], self._token)
                
                await self.hass.async_add_executor_job(validate_plex)
                
                return self.async_create_entry(
                    title="Plex Server",
                    data={
                        CONF_SERVER_URL: user_input[CONF_SERVER_URL],
                        CONF_TOKEN: self._token
                    }
                )
            except Exception:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="server",
            data_schema=vol.Schema({
                vol.Required(CONF_SERVER_URL): str,
            }),
            errors=errors,
        )
