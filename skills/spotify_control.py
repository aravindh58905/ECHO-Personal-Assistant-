import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    from spotipy.exceptions import SpotifyException
    HAS_SPOTIPY = True
except ImportError:
    HAS_SPOTIPY = False
    SpotifyException = Exception
    logger.warning("spotipy package is not installed. Spotify integration will be disabled.")

class SpotifyControlSkill:
    """
    Skill for searching songs and controlling playback via Spotify Web API (Spotipy).
    Requires a Spotify Premium account and SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET in .env.
    """
    def __init__(self):
        self.client_id = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
        self.client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "").strip()
        self.redirect_uri = "http://127.0.0.1:8888/callback"
        self.scope = "user-modify-playback-state user-read-playback-state user-read-currently-playing"
        
        # Save token cache to .spotify_cache in project root / executable directory
        if getattr(sys, 'frozen', False):
            project_root = os.path.dirname(sys.executable)
        else:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.cache_path = os.path.join(project_root, ".spotify_cache")

        # Fallback: If running as executable and .spotify_cache doesn't exist, try copying from parent source directory
        if getattr(sys, 'frozen', False) and not os.path.exists(self.cache_path):
            parent_cache = os.path.abspath(os.path.join(project_root, '..', '.spotify_cache'))
            if os.path.exists(parent_cache):
                try:
                    import shutil
                    shutil.copy(parent_cache, self.cache_path)
                    logger.info(f"[Spotify Init]: Copied existing .spotify_cache from source directory to {self.cache_path}")
                except Exception as e:
                    logger.warning(f"[Spotify Init]: Could not copy parent .spotify_cache: {e}")

        self.sp = None
        self.is_configured = False

        self._initialize_spotify()

    def _initialize_spotify(self):
        """
        Initializes Spotipy with OAuth flow and token caching in non-blocking mode.
        """
        if not HAS_SPOTIPY:
            logger.warning("[Spotify Init]: spotipy module is not installed.")
            return

        if not self.client_id or not self.client_secret or self.client_id == "your_spotify_client_id_here":
            logger.warning("[Spotify Init]: SPOTIFY_CLIENT_ID or SPOTIFY_CLIENT_SECRET missing in .env.")
            return

        try:
            auth_manager = SpotifyOAuth(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=self.redirect_uri,
                scope=self.scope,
                cache_path=self.cache_path,
                open_browser=False  # Set to False so background telemetry checks never pop open a browser or block
            )
            self.sp = spotipy.Spotify(auth_manager=auth_manager)
            self.is_configured = True
            logger.info(f"[Spotify Init]: Spotify Control Skill initialized successfully (Cache: {self.cache_path}).")
        except Exception as e:
            logger.error(f"[Spotify Init Error]: Failed to initialize Spotify OAuth: {e}")

    def is_authenticated(self) -> bool:
        """
        Checks if a valid or refreshable cached token exists without triggering interactive browser OAuth.
        """
        if not self.is_configured or not self.sp:
            return False
        try:
            token_info = self.sp.auth_manager.cache_handler.get_cached_token()
            if not token_info:
                return False
            if self.sp.auth_manager.is_token_expired(token_info):
                # Attempt silent token refresh
                token_info = self.sp.auth_manager.refresh_access_token(token_info['refresh_token'])
            return token_info is not None
        except Exception as e:
            logger.debug(f"[Spotify Auth Check]: Non-blocking token check failed: {e}")
            return False

    def play_song(self, song_name: str) -> str:
        """
        Searches Spotify for the given song name, selects top track result, and starts playback.
        Returns spoken response status message.
        """
        if not self.is_configured or not self.sp:
            return "Spotify client credentials are not configured in .env, boss."

        clean_song = song_name.strip()
        if not clean_song:
            return "What song would you like me to play on Spotify, boss?"

        logger.info(f"[Spotify Skill]: Searching for track: '{clean_song}'")

        try:
            # 1. Search Spotify for track
            results = self.sp.search(q=clean_song, limit=1, type="track")
            tracks = results.get("tracks", {}).get("items", [])

            if not tracks:
                logger.info(f"[Spotify Skill]: No track results found for query '{clean_song}'")
                return f"I couldn't find {clean_song} on Spotify, boss."

            top_track = tracks[0]
            track_uri = top_track["uri"]
            track_name = top_track["name"]
            artist_name = top_track["artists"][0]["name"] if top_track.get("artists") else "Unknown Artist"

            # 2. Locate active or available playback device
            devices_res = self.sp.devices()
            devices = devices_res.get("devices", []) if devices_res else []

            if not devices:
                logger.warning("[Spotify Skill]: No active or available Spotify devices detected.")
                return "Please open Spotify on your PC or phone first, boss."

            # Prefer active device, or fallback to first available device
            active_device = next((d for d in devices if d.get("is_active")), None)
            target_device_id = active_device["id"] if active_device else devices[0]["id"]

            # 3. Trigger playback via Web API
            self.sp.start_playback(device_id=target_device_id, uris=[track_uri])
            logger.info(f"[Spotify Skill]: Successfully started playback of '{track_name}' by '{artist_name}'")
            return f"Playing {track_name} by {artist_name} on Spotify, boss."

        except SpotifyException as spe:
            logger.error(f"[Spotify API Exception]: {spe}")
            status_code = getattr(spe, "http_status", 0)
            reason = str(spe).lower()

            if status_code == 403 or "premium" in reason:
                return "This needs Spotify Premium to work, boss."
            elif status_code == 404 or "no active device" in reason:
                return "Please open Spotify on your PC or phone first, boss."
            else:
                return "I ran into a Spotify API error, boss."
        except Exception as e:
            logger.error(f"[Spotify Skill Error]: Unexpected error playing '{clean_song}': {e}", exc_info=True)
            return "I couldn't play that song on Spotify, boss."

    def get_current_track(self) -> str:
        """
        Queries Spotify Web API for currently playing track details.
        Non-blocking and safe for background telemetry checks.
        """
        if not self.is_configured or not self.sp:
            return "Spotify: Not configured"

        if not self.is_authenticated():
            return "Spotify: Not connected"

        try:
            playback = self.sp.current_playback()
            if playback and playback.get("is_playing") and playback.get("item"):
                item = playback["item"]
                song_title = item.get("name", "Unknown Track")
                artists = ", ".join(a["name"] for a in item.get("artists", [])) if item.get("artists") else "Unknown Artist"
                return f"Playing: {song_title} - {artists}"
            elif playback and not playback.get("is_playing"):
                return "Spotify: Paused"
            else:
                return "Spotify: Idle"
        except SpotifyException as spe:
            logger.error(f"[Spotify Exception]: {spe}")
            return "Spotify: API Error"
        except Exception as e:
            logger.error(f"[Spotify Skill Error]: Error fetching current track: {e}")
            return "Spotify: Unavailable"
