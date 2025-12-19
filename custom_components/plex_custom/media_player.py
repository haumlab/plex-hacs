import logging
from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Plex media player platform."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    plex_server = data["server"]
    known_entities = data["entities"]

    @callback
    def async_check_entities():
        """Check for new clients and add them."""
        new_entities = []
        clients = coordinator.data.get("clients", [])
        
        for client in clients:
            if client.machineIdentifier not in known_entities:
                _LOGGER.debug("Found new Plex client: %s", client.title)
                entity = PlexCustomMediaPlayer(coordinator, client, plex_server)
                new_entities.append(entity)
                known_entities.add(client.machineIdentifier)
        
        if new_entities:
            async_add_entities(new_entities)

    # Register listener for new entities
    entry.async_on_unload(coordinator.async_add_listener(async_check_entities))
    
    # Initial check
    async_check_entities()

class PlexCustomMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    """Representation of a Plex client as a media player."""

    def __init__(self, coordinator, client, server):
        """Initialize the Plex client."""
        super().__init__(coordinator)
        self._client = client
        self._server = server
        self._name = client.title
        self._unique_id = client.machineIdentifier

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def state(self):
        """Return the state of the device."""
        sessions = self.coordinator.data.get("sessions", [])
        active_session = next((s for s in sessions if s.player.machineIdentifier == self._unique_id), None)
        
        if active_session:
            state = active_session.player.state
            if state == 'playing':
                return MediaPlayerState.PLAYING
            if state == 'paused':
                return MediaPlayerState.PAUSED
            if state == 'buffering':
                return MediaPlayerState.BUFFERING
        return MediaPlayerState.IDLE

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return (
            MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.STOP
            | MediaPlayerEntityFeature.NEXT_TRACK
            | MediaPlayerEntityFeature.PREVIOUS_TRACK
            | MediaPlayerEntityFeature.VOLUME_SET
        )

    @property
    def media_title(self):
        """Title of current playing media."""
        sessions = self.coordinator.data.get("sessions", [])
        active_session = next((s for s in sessions if s.player.machineIdentifier == self._unique_id), None)
        return active_session.title if active_session else None

    @property
    def media_artist(self):
        """Artist of current playing media."""
        sessions = self.coordinator.data.get("sessions", [])
        active_session = next((s for s in sessions if s.player.machineIdentifier == self._unique_id), None)
        if active_session and active_session.type == 'track':
            return getattr(active_session, 'grandparentTitle', None)
        return None

    @property
    def media_image_url(self):
        """Image URL of current playing media."""
        sessions = self.coordinator.data.get("sessions", [])
        active_session = next((s for s in sessions if s.player.machineIdentifier == self._unique_id), None)
        if active_session:
            return active_session.thumbUrl
        return None

    def media_play(self):
        """Send play command."""
        self._client.play()

    def media_pause(self):
        """Send pause command."""
        self._client.pause()

    def media_stop(self):
        """Send stop command."""
        self._client.stop()

    def media_next_track(self):
        """Send next track command."""
        self._client.skipNext()

    def media_previous_track(self):
        """Send previous track command."""
        self._client.skipPrevious()

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._client.setVolume(int(volume * 100))
