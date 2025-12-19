import logging
from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

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
        
        # 1. Get clients currently connected to the server
        clients = coordinator.data.get("clients", [])
        
        # 2. Get clients from active sessions
        sessions = coordinator.data.get("sessions", [])
        
        # 3. Get all devices linked to the server
        devices = coordinator.data.get("devices", [])
        
        discovered = {}
        
        # Add devices first (as they are the most stable)
        for device in devices:
            if "client" in device.provides:
                discovered[device.clientIdentifier] = device

        # Add active clients (might have more info)
        for client in clients:
            discovered[client.machineIdentifier] = client
            
        # Add session players
        for session in sessions:
            if session.player.machineIdentifier not in discovered:
                discovered[session.player.machineIdentifier] = session.player

        for machine_id, client in discovered.items():
            if machine_id not in known_entities:
                _LOGGER.debug("Found Plex device: %s (%s)", client.name if hasattr(client, 'name') else client.title, machine_id)
                entity = PlexCustomMediaPlayer(coordinator, client, plex_server, entry)
                new_entities.append(entity)
                known_entities.add(machine_id)
        
        if new_entities:
            async_add_entities(new_entities)

    # Register listener for new entities
    entry.async_on_unload(coordinator.async_add_listener(async_check_entities))
    
    # Initial check
    async_check_entities()

class PlexCustomMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    """Representation of a Plex client as a media player."""

    def __init__(self, coordinator, client, server, entry):
        """Initialize the Plex client."""
        super().__init__(coordinator)
        self._client = client
        self._server = server
        self._entry = entry
        self._name = getattr(client, 'name', getattr(client, 'title', 'Unknown Plex Client'))
        self._unique_id = getattr(client, 'clientIdentifier', getattr(client, 'machineIdentifier', None))
        self._last_position = None
        self._last_update = None

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self._name,
            "manufacturer": "Plex",
            "model": getattr(self._client, "product", "Plex Client"),
            "via_device": (DOMAIN, self._server.machineIdentifier),
        }

    def _get_active_session(self):
        """Get the active session for this client."""
        sessions = self.coordinator.data.get("sessions", [])
        return next((s for s in sessions if s.player.machineIdentifier == self._unique_id), None)

    @property
    def state(self):
        """Return the state of the device."""
        session = self._get_active_session()
        if session:
            state = session.player.state
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
            | MediaPlayerEntityFeature.SEEK
        )

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        session = self._get_active_session()
        if session:
            if session.type == 'movie':
                return MediaType.MOVIE
            if session.type == 'episode':
                return MediaType.TVSHOW
            if session.type == 'track':
                return MediaType.MUSIC
        return None

    @property
    def media_title(self):
        """Title of current playing media."""
        session = self._get_active_session()
        return session.title if session else None

    @property
    def media_artist(self):
        """Artist of current playing media."""
        session = self._get_active_session()
        if session:
            if session.type == 'track':
                return getattr(session, 'grandparentTitle', None)
            if session.type == 'episode':
                return getattr(session, 'grandparentTitle', None) # Show title
        return None

    @property
    def media_album_name(self):
        """Album name of current playing media."""
        session = self._get_active_session()
        if session and session.type == 'track':
            return getattr(session, 'parentTitle', None)
        return None

    @property
    def media_album_artist(self):
        """Album artist of current playing media."""
        session = self._get_active_session()
        if session and session.type == 'track':
            return getattr(session, 'grandparentTitle', None)
        return None

    @property
    def media_series_title(self):
        """Series title of current playing media."""
        session = self._get_active_session()
        if session and session.type == 'episode':
            return getattr(session, 'grandparentTitle', None)
        return None

    @property
    def media_season(self):
        """Season of current playing media."""
        session = self._get_active_session()
        if session and session.type == 'episode':
            return getattr(session, 'parentIndex', None)
        return None

    @property
    def media_episode(self):
        """Episode of current playing media."""
        session = self._get_active_session()
        if session and session.type == 'episode':
            return getattr(session, 'index', None)
        return None

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        session = self._get_active_session()
        if session and session.duration:
            return session.duration / 1000
        return None

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        session = self._get_active_session()
        if session and session.viewOffset:
            return session.viewOffset / 1000
        return None

    @property
    def media_position_updated_at(self):
        """When was the position last updated."""
        if self.state in [MediaPlayerState.PLAYING, MediaPlayerState.PAUSED]:
            return dt_util.utcnow()
        return None

    @property
    def media_image_url(self):
        """Image URL of current playing media."""
        session = self._get_active_session()
        if session:
            return session.thumbUrl
        return None

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        session = self._get_active_session()
        if session:
            return {
                "user": session.usernames[0] if session.usernames else None,
                "player": session.player.title,
                "address": session.player.address,
                "media_key": session.ratingKey,
            }
        return {}

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

    def media_seek(self, position):
        """Send seek command."""
        self._client.seekTo(int(position * 100))
