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
        
        sessions = coordinator.data.get("sessions", [])
        clients = coordinator.data.get("clients", [])
        devices = coordinator.data.get("devices", [])
        
        discovered = {}
        
        # 1. Process Account Devices (Persistent)
        for device in devices:
            machine_id = getattr(device, 'clientIdentifier', None)
            if machine_id:
                discovered[machine_id] = {
                    "obj": device,
                    "name": device.name,
                    "type": "device"
                }

        # 2. Process Active Clients (Reachable)
        for client in clients:
            machine_id = getattr(client, 'machineIdentifier', None)
            if machine_id:
                discovered[machine_id] = {
                    "obj": client,
                    "name": client.title,
                    "type": "client"
                }
            
        # 3. Process Session Players (Currently Playing)
        for session in sessions:
            player = session.player
            machine_id = getattr(player, 'machineIdentifier', None)
            if machine_id:
                # Sessions often have the most up-to-date title/info
                if machine_id not in discovered:
                    discovered[machine_id] = {
                        "obj": player,
                        "name": player.title,
                        "type": "player"
                    }

        for machine_id, info in discovered.items():
            if machine_id not in known_entities:
                _LOGGER.info("Registering Plex device: %s (%s)", info["name"], machine_id)
                entity = PlexCustomMediaPlayer(coordinator, info["obj"], plex_server, entry)
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

    def __init__(self, coordinator, client_obj, server, entry):
        """Initialize the Plex client."""
        super().__init__(coordinator)
        self._client_obj = client_obj
        self._server = server
        self._entry = entry
        
        # Handle different object types (MyPlexDevice, PlexClient, or Session Player)
        self._name = getattr(client_obj, 'name', getattr(client_obj, 'title', 'Unknown Plex Client'))
        self._unique_id = getattr(client_obj, 'clientIdentifier', getattr(client_obj, 'machineIdentifier', None))
        
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
            "model": getattr(self._client_obj, "product", "Plex Client"),
            "via_device": (DOMAIN, self._server.machineIdentifier),
        }

    def _get_active_session(self):
        """Get the active session for this client."""
        sessions = self.coordinator.data.get("sessions", [])
        return next((s for s in sessions if s.player.machineIdentifier == self._unique_id or s.player.clientIdentifier == self._unique_id), None)

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

    def _get_client(self):
        """Get a controllable client object."""
        # 1. Check if it's already a PlexClient (from sessions or clients list)
        if hasattr(self._client_obj, 'play'):
            return self._client_obj
            
        # 2. If it's a MyPlexDevice, try to connect to it
        if hasattr(self._client_obj, 'connect'):
            try:
                return self._client_obj.connect()
            except Exception:
                pass
                
        # 3. Try to find it in the current reachable clients
        clients = self.coordinator.data.get("clients", [])
        for client in clients:
            if client.machineIdentifier == self._unique_id:
                return client
                
        return None

    def media_play(self):
        """Send play command."""
        client = self._get_client()
        if client:
            client.play()

    def media_pause(self):
        """Send pause command."""
        client = self._get_client()
        if client:
            client.pause()

    def media_stop(self):
        """Send stop command."""
        client = self._get_client()
        if client:
            client.stop()

    def media_next_track(self):
        """Send next track command."""
        client = self._get_client()
        if client:
            client.skipNext()

    def media_previous_track(self):
        """Send previous track command."""
        client = self._get_client()
        if client:
            client.skipPrevious()

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        client = self._get_client()
        if client:
            client.setVolume(int(volume * 100))

    def media_seek(self, position):
        """Send seek command."""
        client = self._get_client()
        if client:
            client.seekTo(int(position * 100))
