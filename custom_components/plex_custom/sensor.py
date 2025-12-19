import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Plex sensor platform."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    plex_server = data["server"]

    async_add_entities([PlexSessionsSensor(coordinator, plex_server, entry)])

class PlexSessionsSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Plex sessions sensor."""

    def __init__(self, coordinator, server, entry):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._server = server
        self._entry = entry
        self._attr_name = f"Plex Sessions ({server.friendlyName})"
        self._attr_unique_id = f"{server.machineIdentifier}_sessions"
        self._attr_icon = "mdi:plex"

    @property
    def native_value(self):
        """Return the number of active sessions."""
        sessions = self.coordinator.data.get("sessions", [])
        return len(sessions)

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        sessions = self.coordinator.data.get("sessions", [])
        users = {}
        for session in sessions:
            user = session.usernames[0] if session.usernames else "Unknown"
            users[user] = users.get(user, 0) + 1
        
        return {
            "active_users": list(users.keys()),
            "session_details": [
                {
                    "user": session.usernames[0] if session.usernames else "Unknown",
                    "title": session.title,
                    "player": session.player.title,
                    "state": session.player.state
                }
                for session in sessions
            ]
        }

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._server.machineIdentifier)},
            "name": self._server.friendlyName,
            "manufacturer": "Plex",
            "model": "Plex Media Server",
            "sw_version": self._server.version,
        }
