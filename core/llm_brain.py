import os
import socket
import logging
from urllib.error import URLError
from dotenv import load_dotenv

# Load environment variables from .env file if present
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
    logger.warning("google-generativeai package is not installed. LLM fallback will be disabled.")

class LLMBrain:
    """
    Handles conversational LLM fallback responses using Google's Gemini API
    with persona prompt, robust error classification, short-term memory management,
    and persistent long-term memory injection.
    """
    def __init__(self, config: dict, memory_store=None):
        self.config = config.get("gemini", {})
        self.assistant_config = config.get("assistant", {})
        self.assistant_name = self.assistant_config.get("name", "ECHO")
        self.honorific = self.assistant_config.get("user_honorific", "boss")
        self.model_name = self.config.get("model", "gemini-1.5-flash")
        self.memory_store = memory_store
        
        self.history = []  # List of dicts: [{"role": "user"|"model", "parts": [str]}]
        self.max_history_turns = 4  # Retain up to 4 exchanges (8 messages)

        self.api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        self.is_ready = False

        if not HAS_GENAI:
            logger.warning("[LLM Brain Init]: google-generativeai module missing.")
        elif not self.api_key or self.api_key == "your_gemini_api_key_here":
            logger.warning("[LLM Brain Init]: GEMINI_API_KEY not found or unconfigured in .env.")
        else:
            try:
                genai.configure(api_key=self.api_key)
                self.is_ready = True
                logger.info(f"[LLM Brain Init]: Initialized successfully with model '{self.model_name}'.")
            except Exception as e:
                logger.error(f"[LLM Brain Init Error]: Failed to configure Gemini API: {e}")

    def _get_system_instruction(self) -> str:
        instruction = (
            f"You are {self.assistant_name}, a highly intelligent, loyal, sharp, and witty AI assistant for Windows PC. "
            f"You have a dry sense of humor inspired by JARVIS from Iron Man. "
            f"Always address the user as '{self.honorific}'. "
            f"Keep all responses very concise (2 to 3 sentences maximum), because your answers will be spoken aloud via text-to-speech. "
            f"Do not use markdown formatting, asterisks, bullet points, code blocks, or emojis."
        )

        if self.memory_store:
            facts = self.memory_store.get_all()
            if facts:
                facts_summary = "; ".join([f"{k}: {v}" for k, v in facts.items()])
                instruction += f" Known facts about the user: {facts_summary}."

        return instruction

    def ask(self, prompt: str) -> str | None:
        """
        Sends prompt to Gemini API with persona prompt and conversation memory.
        Returns generated reply string, or None if failed/unconfigured.
        Categorizes and logs specific failure modes (network, rate limit, empty response).
        """
        if not self.is_ready:
            logger.warning("[LLM Brain Warning]: Gemini API call skipped because API key is missing or unconfigured.")
            return None

        if not prompt or not prompt.strip():
            return None

        try:
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=self._get_system_instruction()
            )

            # Build messages history for context
            messages = list(self.history)
            messages.append({"role": "user", "parts": [prompt]})

            logger.info(f"[LLM Brain Querying Gemini ({self.model_name})]: '{prompt}'")
            response = model.generate_content(messages)
            
            if not response or not hasattr(response, 'text') or not response.text:
                logger.warning(f"[LLM Brain Warning]: Gemini API returned an empty or safety-blocked response for prompt: '{prompt}'.")
                return None

            reply_text = response.text.strip()
            # Clean markdown artifacts for smooth TTS playback
            clean_reply = reply_text.replace("*", "").replace("#", "").replace("`", "").strip()

            if not clean_reply:
                logger.warning("[LLM Brain Warning]: Cleaned Gemini response text was empty.")
                return None

            # Save to conversation memory
            self.history.append({"role": "user", "parts": [prompt]})
            self.history.append({"role": "model", "parts": [clean_reply]})

            # Trim history to max turns
            max_messages = self.max_history_turns * 2
            if len(self.history) > max_messages:
                self.history = self.history[-max_messages:]

            return clean_reply

        except ResourceExhausted as e:
            logger.error(f"[LLM Brain Error]: Gemini API rate limit or quota exceeded (ResourceExhausted / 429): {e}")
            return None
        except (socket.gaierror, URLError, ConnectionError) as e:
            logger.error(f"[LLM Brain Error]: Network / Internet connection failure querying Gemini API: {e}")
            return None
        except GoogleAPIError as e:
            err_msg = str(e)
            if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "quota" in err_msg.lower():
                logger.error(f"[LLM Brain Error]: Gemini API rate limit / quota error (429): {e}")
            else:
                logger.error(f"[LLM Brain Error]: Gemini API service error: {e}")
            return None
        except Exception as e:
            err_str = str(e).lower()
            if "connection" in err_str or "socket" in err_str or "unreachable" in err_str:
                logger.error(f"[LLM Brain Error]: Internet connection issue: {e}")
            elif "429" in err_str or "quota" in err_str:
                logger.error(f"[LLM Brain Error]: Gemini API rate limit exceeded: {e}")
            else:
                logger.error(f"[LLM Brain Error]: Unexpected failure during Gemini query: {e}")
            return None

    def reset_memory(self):
        """
        Resets short-term conversation memory.
        Call this whenever a rule-based intent is matched and executed.
        """
        if self.history:
            logger.info("LLMBrain conversation memory reset after rule-based command execution.")
            self.history = []
