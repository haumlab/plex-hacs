"""Media player platform for Plex Custom Control."""
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
    """Set up Plex media player from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    plex_server = data["server"]
    session_ids = data["session_ids"]

    @callback
    def async_update_items():
        """Add new media players for new sessions."""
        new_entities = []
        sessions = coordinator.data or []

        for session in sessions:
            session_key = session.sessionKey
            if session_key not in session_ids:
                _LOGGER.debug("New Plex session: %s on %s", session.title, session.player.title)
                entity = PlexMediaPlayer(coordinator, plex_server, session)
                session_ids[session_key] = entity
                new_entities.append(entity)

        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(async_update_items))
    async_update_items()


class PlexMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    """Representation of a Plex device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, server, session):
        """Initialize the Plex device."""
        super().__init__(coordinator)
        self._server = server
        self._session_key = session.sessionKey
        self._machine_id = session.player.machineIdentifier
        self._player_title = session.player.title
        self._attr_unique_id = f"plex_{self._machine_id}"
        self._attr_name = self._player_title

    @property
    def _session(self):
        """Get the current session for this player."""
        sessions = self.coordinator.data or []
        for session in sessions:
            if session.player.machineIdentifier == self._machine_id:
                return session
        return None

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._machine_id)},
            "name": self._player_title,
            "manufacturer": "Plex",
            "model": "Media Player",
            "via_device": (DOMAIN, self._server.machineIdentifier),
        }

    @property
    def state(self):
        """Return the state of the player."""
        session = self._session
        if not session:
            return MediaPlayerState.IDLE
        state = session.player.state
        if state == "playing":
            return MediaPlayerState.PLAYING
        if state == "paused":
            return MediaPlayerState.PAUSED
        if state == "buffering":
            return MediaPlayerState.BUFFERING
        return MediaPlayerState.IDLE

    @property
    def available(self):
        """Return True if the player is available."""
        return True

    @property
    def supported_features(self):
        """Return supported features."""
        return (
            MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.STOP
            | MediaPlayerEntityFeature.NEXT_TRACK
            | MediaPlayerEntityFeature.PREVIOUS_TRACK
        )

    @property
    def media_content_type(self):
        """Return the content type."""
        session = self._session
        if not session:
            return None
        if session.type == "movie":
            return MediaType.MOVIE
        if session.type == "episode":
            return MediaType.TVSHOW
        if session.type == "track":
            return MediaType.MUSIC
        return MediaType.VIDEO

    @property
    def media_title(self):
        """Return the title."""
        session = self._session
        if not session:
            return None
        return session.title

    @property
    def media_series_title(self):
        """Return the series title (for TV shows)."""
        session = self._session
        if session and session.type == "episode":
            return getattr(session, "grandparentTitle", None)
        return None

    @property
    def media_season(self):
        """Return the season number."""
        session = self._session
        if session and session.type == "episode":
            return getattr(session, "parentIndex", None)
        return None

    @property
    def media_episode(self):
        """Return the episode number."""
        session = self._session
        if session and session.type == "episode":
            return getattr(session, "index", None)
        return None

    @property
    def media_artist(self):
        """Return the artist (for music)."""
        session = self._session
        if session and session.type == "track":
            return getattr(session, "grandparentTitle", None)
        return None

    @property
    def media_album_name(self):
        """Return the album name."""
        session = self._session
        if session and session.type == "track":
            return getattr(session, "parentTitle", None)
        return None

    @property
    def media_duration(self):
        """Return the duration in seconds."""
        session = self._session
        if session and session.duration:
            return session.duration / 1000
        return None

    @property
    def media_position(self):
        """Return the current position in seconds."""
        session = self._session
        if session and session.viewOffset:
            return session.viewOffset / 1000
        return None

    @property
    def media_position_updated_at(self):
        """Return when position was last updated."""
        if self.state in (MediaPlayerState.PLAYING, MediaPlayerState.PAUSED):
            return dt_util.utcnow()
        return None

    @property
    def media_image_url(self):
        """Return the image URL."""
        session = self._session
        if session:
            return session.thumbUrl
        return None

    @property
    def extra_state_attributes(self):
        """Return extra attributes."""
        session = self._session
        if session:
            return {
                "user": session.usernames[0] if session.usernames else None,
                "player_address": getattr(session.player, "address", None),
                "player_device": getattr(session.player, "device", None),
                "player_platform": getattr(session.player, "platform", None),
                "player_product": getattr(session.player, "product", None),
            }
        return {}

    def _get_client(self):
        """Get a controllable client."""
        try:
            clients = self._server.clients()
            for client in clients:
                if client.machineIdentifier == self._machine_id:
                    return client
        except Exception as e:
            _LOGGER.debug("Could not get client: %s", e)
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
