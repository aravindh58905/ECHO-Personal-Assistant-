import time
import ctypes
import logging

logger = logging.getLogger(__name__)

# Windows Virtual Key Codes for Media and Volume control
VK_VOLUME_MUTE = 0xAD       # 173
VK_VOLUME_DOWN = 0xAE       # 174
VK_VOLUME_UP = 0xAF         # 175
VK_MEDIA_NEXT_TRACK = 0xB0  # 176
VK_MEDIA_PREV_TRACK = 0xB1  # 177
VK_MEDIA_STOP = 0xB2        # 178
VK_MEDIA_PLAY_PAUSE = 0xB3  # 179

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002

class MediaControlSkill:
    """
    Skill for controlling global Windows media playback and system volume using native Win32 ctypes API calls.
    Works globally regardless of which application currently has window focus.
    Includes exception handling to ensure OS API issues don't crash the assistant.
    """
    def __init__(self, config: dict):
        self.config = config.get("media", {})
        self.volume_step = self.config.get("volume_step", 4)

    def _send_key(self, vk_code: int) -> bool:
        """
        Simulates a key down and key up event for a Windows virtual key code.
        Returns True if successful, False otherwise.
        """
        try:
            # Key down
            ctypes.windll.user32.keybd_event(vk_code, 0, KEYEVENTF_EXTENDEDKEY, 0)
            time.sleep(0.05)
            # Key up
            ctypes.windll.user32.keybd_event(vk_code, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)
            return True
        except Exception as e:
            logger.error(f"Failed to send Win32 virtual key code 0x{vk_code:X}: {e}")
            return False

    def play_pause(self) -> str:
        """Toggles media play / pause state."""
        logger.info("Sending Media Play/Pause command")
        if self._send_key(VK_MEDIA_PLAY_PAUSE):
            return "Toggling playback"
        return "I couldn't adjust media, boss."

    def next_track(self) -> str:
        """Skips to the next media track."""
        logger.info("Sending Media Next Track command")
        if self._send_key(VK_MEDIA_NEXT_TRACK):
            return "Skipping to the next track"
        return "I couldn't skip the track, boss."

    def prev_track(self) -> str:
        """Rewinds to the previous media track."""
        logger.info("Sending Media Previous Track command")
        if self._send_key(VK_MEDIA_PREV_TRACK):
            return "Playing previous track"
        return "I couldn't change the track, boss."

    def volume_up(self) -> str:
        """Increases system master volume by configured steps."""
        logger.info(f"Increasing master volume by {self.volume_step} steps")
        try:
            for _ in range(self.volume_step):
                self._send_key(VK_VOLUME_UP)
                time.sleep(0.02)
            return "Volume increased"
        except Exception as e:
            logger.error(f"Volume up error: {e}")
            return "I couldn't adjust the volume, boss."

    def volume_down(self) -> str:
        """Decreases system master volume by configured steps."""
        logger.info(f"Decreasing master volume by {self.volume_step} steps")
        try:
            for _ in range(self.volume_step):
                self._send_key(VK_VOLUME_DOWN)
                time.sleep(0.02)
            return "Volume decreased"
        except Exception as e:
            logger.error(f"Volume down error: {e}")
            return "I couldn't adjust the volume, boss."

    def mute(self) -> str:
        """Toggles system volume mute state."""
        logger.info("Toggling volume mute")
        if self._send_key(VK_VOLUME_MUTE):
            return "Toggling mute"
        return "I couldn't adjust audio mute, boss."
