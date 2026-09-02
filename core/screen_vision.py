import os
import io
import socket
import logging
from urllib.error import URLError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
    from google.api_core.exceptions import GoogleAPIError, ResourceExhausted
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False
    GoogleAPIError = Exception
    ResourceExhausted = Exception
    logger.warning("google-generativeai package is not installed. Screen vision will be disabled.")

try:
    from PIL import Image, ImageGrab
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    logger.warning("Pillow (PIL) library is not installed. Screen vision screenshot capture requires Pillow.")


class ScreenVisionSkill:
    """
    Multimodal Screen Vision Skill for ECHO.
    Captures active screen display upon explicit user query and sends it alongside
    the prompt to Gemini API for visual context reasoning.
    """
    def __init__(self, config: dict, speaker=None):
        self.config = config
        self.vision_config = config.get("screen_vision", {})
        self.enabled = self.vision_config.get("enabled", True)

        self.assistant_config = config.get("assistant", {})
        self.assistant_name = self.assistant_config.get("name", "ECHO")
        self.honorific = self.assistant_config.get("user_honorific", "boss")

        # Reuses the exact single model name from config.yaml -> gemini.model
        self.gemini_config = config.get("gemini", {})
        self.model_name = self.gemini_config.get("model", "gemini-3.5-flash")

        self.speaker = speaker
        self.api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        self.is_ready = False

        if not self.enabled:
            logger.info("ScreenVisionSkill is disabled in configuration.")
        elif not HAS_GENAI:
            logger.warning("[Screen Vision Init]: google-generativeai package missing.")
        elif not HAS_PIL:
            logger.warning("[Screen Vision Init]: PIL/Pillow package missing.")
        elif not self.api_key or self.api_key == "your_gemini_api_key_here":
            logger.warning("[Screen Vision Init]: GEMINI_API_KEY not found or unconfigured.")
        else:
            try:
                genai.configure(api_key=self.api_key)
                self.is_ready = True
                logger.info(f"[Screen Vision Init]: Initialized successfully using model '{self.model_name}'.")
            except Exception as e:
                logger.error(f"[Screen Vision Init Error]: Failed to configure Gemini API: {e}")

    def _get_system_instruction(self) -> str:
        return (
            f"You are {self.assistant_name}, a highly intelligent, sharp, and witty AI assistant for Windows PC. "
            f"You are analyzing a screenshot of the user's computer screen to answer their question. "
            f"Always address the user as '{self.honorific}'. "
            f"Keep all responses very concise (2 to 3 sentences maximum), because your answers will be spoken aloud via text-to-speech. "
            f"Do not use markdown formatting, asterisks, bullet points, code blocks, or emojis."
        )

    def capture_screenshot(self) -> Image.Image | None:
        """
        Captures active screen display using multi-backend fallback strategy:
        1. mss (if available)
        2. PIL.ImageGrab
        3. pyautogui (if available)
        """
        if not HAS_PIL:
            logger.error("[Screen Vision]: Cannot capture screenshot because Pillow is missing.")
            return None

        # 1. Try mss
        try:
            import mss
            with mss.mss() as sct:
                monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                sct_img = sct.grab(monitor)
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                logger.info(f"[Screen Vision]: Captured screenshot via mss ({img.width}x{img.height}).")
                return img
        except Exception as e:
            logger.debug(f"[Screen Vision]: mss grab unvailable or failed ({e}). Trying PIL.ImageGrab...")

        # 2. Try PIL.ImageGrab
        try:
            img = ImageGrab.grab()
            if img:
                logger.info(f"[Screen Vision]: Captured screenshot via PIL.ImageGrab ({img.width}x{img.height}).")
                return img
        except Exception as e:
            logger.warning(f"[Screen Vision]: PIL.ImageGrab failed ({e}). Trying pyautogui fallback...")

        # 3. Try pyautogui
        try:
            import pyautogui
            img = pyautogui.screenshot()
            if img:
                logger.info(f"[Screen Vision]: Captured screenshot via pyautogui ({img.width}x{img.height}).")
                return img
        except Exception as e:
            logger.error(f"[Screen Vision]: All screenshot capture methods failed: {e}")

        return None

    def capture_and_ask(self, question: str) -> str:
        """
        Executes screen capture and queries Gemini Multimodal API with visual context.
        Provides pre-speech audio acknowledgment prior to network execution.
        """
        if not self.enabled:
            logger.warning("[Screen Vision]: Query attempted but screen_vision is disabled in config.")
            return f"Screen vision is currently disabled in your configuration, {self.honorific}."

        if not self.is_ready:
            logger.warning("[Screen Vision]: Gemini vision query skipped because API key or modules are unavailable.")
            return f"I can't see your screen right now, {self.honorific}. Please check your Gemini API key."

        clean_question = question.strip() if question else "What am I looking at?"

        # Pre-speech audio acknowledgment before API latency
        if self.speaker:
            try:
                logger.info("[Screen Vision]: Triggering pre-speech audio acknowledgment.")
                self.speaker.speak(f"Let me take a look, {self.honorific}.", format_persona=False)
            except Exception as e:
                logger.warning(f"[Screen Vision]: Pre-speech acknowledgment exception: {e}")

        logger.info(f"[Screen Vision Request Started]: Question='{clean_question}', Model='{self.model_name}'")

        # Capture screenshot
        image = self.capture_screenshot()
        if not image:
            logger.error("[Screen Vision Error]: Screenshot capture yielded None.")
            return f"I couldn't see your screen just now, {self.honorific}."

        try:
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=self._get_system_instruction()
            )

            # Query Gemini API with [image, text] multimodal payload
            logger.info(f"[Screen Vision Querying Gemini ({self.model_name})]: Sending screenshot image + question.")
            response = model.generate_content([image, clean_question])

            if not response or not hasattr(response, 'text') or not response.text:
                logger.warning("[Screen Vision Warning]: Gemini API returned an empty or safety-blocked response.")
                return f"I couldn't analyze your screen just now, {self.honorific}."

            reply_text = response.text.strip()
            # Clean markdown artifacts for TTS playback
            clean_reply = reply_text.replace("*", "").replace("#", "").replace("`", "").strip()

            if not clean_reply:
                logger.warning("[Screen Vision Warning]: Cleaned vision response text was empty.")
                return f"I couldn't process what's on your screen, {self.honorific}."

            logger.info(f"[Screen Vision Success]: Received response from Gemini API: '{clean_reply}'")
            return clean_reply

        except ResourceExhausted as e:
            logger.error(f"[Screen Vision Error]: Gemini API quota or rate limit exceeded: {e}")
            return f"I hit a rate limit trying to analyze your screen, {self.honorific}."
        except (socket.gaierror, URLError, ConnectionError) as e:
            logger.error(f"[Screen Vision Error]: Network connection error: {e}")
            return f"I couldn't reach the network to check your screen, {self.honorific}."
        except GoogleAPIError as e:
            logger.error(f"[Screen Vision Error]: Gemini API service error: {e}")
            return f"I ran into an issue processing your screen image, {self.honorific}."
        except Exception as e:
            logger.error(f"[Screen Vision Error]: Unexpected failure analyzing screen: {e}", exc_info=True)
            return f"I couldn't see your screen just now, {self.honorific}."
