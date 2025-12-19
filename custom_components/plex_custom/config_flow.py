import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from plexapi.server import PlexServer
from .const import DOMAIN, CONF_SERVER_URL, CONF_TOKEN

class PlexCustomConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Plex Custom Control."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                # Validate the connection
                def validate_plex():
                    return PlexServer(user_input[CONF_SERVER_URL], user_input[CONF_TOKEN])
                
                await self.hass.async_add_executor_job(validate_plex)
                
                return self.async_create_entry(title="Plex Server", data=user_input)
            except Exception:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_SERVER_URL): str,
                vol.Required(CONF_TOKEN): str,
            }),
            errors=errors,
        )
