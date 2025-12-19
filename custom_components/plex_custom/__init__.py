from datetime import timedelta
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from plexapi.server import PlexServer
from .const import DOMAIN, CONF_SERVER_URL, CONF_TOKEN

_LOGGER = logging.getLogger(__name__)

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
            def fetch_plex_data():
                data = {
                    "sessions": [],
                    "clients": [],
                    "devices": []
                }
                
                # 1. Get active sessions (most reliable for "Now Playing")
                try:
                    data["sessions"] = plex_server.sessions()
                except Exception as e:
                    _LOGGER.error("Error fetching Plex sessions: %s", e)

                # 2. Get currently reachable clients
                try:
                    data["clients"] = plex_server.clients()
                except Exception as e:
                    _LOGGER.error("Error fetching Plex clients: %s", e)

                # 3. Get all devices linked to the account
                try:
                    # Try to get account-level devices if possible
                    account = plex_server.myPlexAccount()
                    if account:
                        data["devices"] = [d for d in account.devices() if "client" in d.provides]
                except Exception as e:
                    _LOGGER.debug("Could not fetch account devices (normal if not signed in to MyPlex): %s", e)
                
                return data

            return await hass.async_add_executor_job(fetch_plex_data)
        except Exception as err:
            raise UpdateFailed(f"Error communicating with Plex API: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="plex_custom_data",
        update_method=async_update_data,
        update_interval=timedelta(seconds=10),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "server": plex_server,
        "coordinator": coordinator,
        "entities": set()
    }

    await hass.config_entries.async_forward_entry_setups(entry, ["media_player", "sensor"])

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["media_player", "sensor"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
