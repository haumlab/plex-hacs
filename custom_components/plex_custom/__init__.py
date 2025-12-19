"""Plex Custom Control integration."""
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from plexapi.server import PlexServer

from .const import DOMAIN, CONF_SERVER_URL, CONF_TOKEN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["media_player"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Plex Custom Control from a config entry."""
    server_url = entry.data[CONF_SERVER_URL]
    token = entry.data[CONF_TOKEN]

    def get_plex_server():
        return PlexServer(server_url, token)

    try:
        plex_server = await hass.async_add_executor_job(get_plex_server)
    except Exception as ex:
        _LOGGER.error("Failed to connect to Plex server: %s", ex)
        return False

    async def async_update_data():
        """Fetch data from Plex API."""
        try:
            def fetch_data():
                return plex_server.sessions()
            return await hass.async_add_executor_job(fetch_data)
        except Exception as err:
            raise UpdateFailed(f"Error communicating with Plex: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="plex_custom",
        update_method=async_update_data,
        update_interval=timedelta(seconds=5),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "server": plex_server,
        "coordinator": coordinator,
        "session_ids": {},
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
