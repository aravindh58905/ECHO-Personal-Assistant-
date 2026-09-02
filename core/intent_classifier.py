import re
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

INTENT_TRAINING_DATA = {
    "screen_vision": [
        "what am I looking at right now",
        "what is on my screen",
        "what's wrong here on my display",
        "what am I doing wrong on screen",
        "can you see what is on my screen",
        "look at my screen and help me",
        "check my current screen display",
        "help me with what is on my monitor"
    ],
    "open_phone_app": [
        "open application on my phone",
        "launch app on phone",
        "open instagram on my phone",
        "launch whatsapp on phone",
        "start youtube on my mobile phone",
        "open app on android phone"
    ],
    "open_app": [
        "open an application",
        "launch program software",
        "start an app",
        "fire up application",
        "run desktop program",
        "open software program"
    ],
    "next_track": [
        "skip to next song",
        "play next track",
        "go to next music",
        "skip this track",
        "advance to next audio track"
    ],
    "previous_track": [
        "go back to previous song",
        "play last track",
        "previous song please",
        "rewind to previous track",
        "go back one track"
    ],
    "play_pause_media": [
        "pause the playback",
        "resume playing music",
        "toggle media playback",
        "stop music audio",
        "pause or play track"
    ],
    "volume_up": [
        "turn the volume up",
        "make it louder",
        "increase audio level",
        "raise the sound",
        "turn up speakers"
    ],
    "volume_down": [
        "turn down the volume",
        "make it quieter",
        "decrease audio level",
        "lower the sound",
        "turn down speakers"
    ],
    "mute": [
        "mute all sound",
        "turn off audio",
        "silence the volume",
        "mute the computer",
        "toggle audio mute"
    ],
    "system_status": [
        "how is the computer doing",
        "check system hardware stats",
        "show memory and cpu status",
        "telemetry and battery status",
        "system resource utilization"
    ],
    "web_search": [
        "search the web for something",
        "look up information on internet",
        "find online details about query",
        "google search query",
        "search online in browser"
    ],
    "time_query": [
        "what is the current time",
        "tell me what time it is",
        "do you have the time",
        "check current clock time",
        "what time is it right now"
    ],
    "date_query": [
        "what is today's date",
        "tell me the day and date",
        "which day of the week is it",
        "check current date calendar",
        "what is today's day"
    ],
    "power_shutdown": [
        "turn off the computer",
        "shut down pc",
        "power down desktop system",
        "turn off my computer",
        "shutdown desktop machine"
    ],
    "power_restart": [
        "reboot the computer",
        "restart my pc",
        "reboot system machine",
        "restart windows desktop",
        "reboot windows system"
    ],
    "dictation": [
        "type out some text",
        "write down what I say",
        "dictate text into active window",
        "type this text out",
        "insert text into document"
    ],
    "spotify_play_song": [
        "play a track on spotify",
        "put on a song on spotify",
        "stream song spotify",
        "listen to music track spotify",
        "play music song spotify"
    ],
    "spotify_current_track": [
        "what track is currently playing",
        "identify this song",
        "tell me what music is playing",
        "name of current track",
        "what song is playing right now"
    ],
    "remember_fact": [
        "remember that I am a student",
        "remember my name is Aravindh",
        "remember that I like programming",
        "please remember that I live in Chennai",
        "remember my career goal is AI engineer"
    ],
    "recall_memory": [
        "what do you know about me",
        "what do you remember",
        "tell me what you know about me",
        "what facts do you remember about me",
        "what do you remember about me"
    ],
    "send_whatsapp": [
        "send a whatsapp message to mom saying hello",
        "send a whatsapp to mom",
        "message dad on whatsapp",
        "whatsapp my friend saying hello",
        "send dad a message saying I will be late",
        "whatsapp ragul saying meet me at 5",
        "send a whatsapp message to brother",
        "send mom a whatsapp message saying good morning"
    ]
}


class IntentClassifier:
    """
    Local embedding-based semantic intent classifier powered by sentence-transformers (all-MiniLM-L6-v2).
    Precomputes training phrase embeddings at startup and performs fast cosine similarity matching.
    """
    def __init__(self, config: dict):
        self.config = config
        intent_cfg = config.get("intent_classification", {})
        self.enabled = intent_cfg.get("enabled", True)
        self.threshold = float(intent_cfg.get("confidence_threshold", 0.65))

        self.model = None
        self.phrase_labels = []
        self.phrase_embeddings = None
        self.is_ready = False

        if self.enabled:
            self._initialize_model()

    def _initialize_model(self):
        """
        Loads sentence-transformers model and precomputes training embeddings once at startup.
        """
        try:
            logger.info("Initializing SentenceTransformer model ('all-MiniLM-L6-v2') for semantic intent classification...")
            from sentence_transformers import SentenceTransformer, util
            self._util = util

            # Load local model (cached locally after first download)
            self.model = SentenceTransformer("all-MiniLM-L6-v2")

            # Prepare training dataset and labels
            phrases = []
            self.phrase_labels = []
            for intent, intent_phrases in INTENT_TRAINING_DATA.items():
                for p in intent_phrases:
                    phrases.append(p)
                    self.phrase_labels.append(intent)

            # Precompute and cache embeddings matrix at startup
            self.phrase_embeddings = self.model.encode(phrases, convert_to_tensor=True)
            self.is_ready = True
            logger.info(f"IntentClassifier initialized successfully. Precomputed embeddings for {len(phrases)} phrases across {len(INTENT_TRAINING_DATA)} intents.")

        except ImportError:
            logger.warning("sentence-transformers package is not installed. Semantic intent classification will be disabled.")
            self.is_ready = False
        except Exception as e:
            logger.error(f"Failed to initialize IntentClassifier model: {e}", exc_info=True)
            self.is_ready = False

    def classify(self, command: str) -> Tuple[Optional[str], float]:
        """
        Calculates cosine similarity between user command and precomputed phrase embeddings.
        Returns (intent_name, score) if score >= threshold, else (None, score).
        """
        if not self.is_ready or not command or not command.strip():
            return None, 0.0

        try:
            clean_cmd = command.strip().lower()
            cmd_embedding = self.model.encode(clean_cmd, convert_to_tensor=True)
            
            # Compute cosine similarity against precomputed training matrix
            cosine_scores = self._util.cos_sim(cmd_embedding, self.phrase_embeddings)[0]
            
            # Find best match
            best_idx = int(cosine_scores.argmax())
            best_score = float(cosine_scores[best_idx])
            best_intent = self.phrase_labels[best_idx]

            if best_score >= self.threshold:
                logger.info(f"[Semantic Match Found]: Intent='{best_intent}', Confidence={best_score:.4f} (Threshold: {self.threshold})")
                return best_intent, round(best_score, 4)
            else:
                logger.info(f"[Semantic Low Confidence]: Best Intent='{best_intent}', Score={best_score:.4f} < Threshold={self.threshold}")
                return None, round(best_score, 4)

        except Exception as e:
            logger.error(f"Error during intent classification for '{command}': {e}")
            return None, 0.0

    @staticmethod
    def extract_entity(command: str, intent: str) -> str:
        """
        Extracts argument/entity payloads (app name, song title, search query, text)
        when matching parameterized intents semantically.
        """
        cmd = re.sub(r'[^\w\s]+$', '', command.strip().lower()).strip()

        if intent == "open_phone_app":
            clean = re.sub(r"^(?:can you|please|could you)?\s*(?:open|launch|start|fire up|run)\s+(?:up\s+)?(?:the\s+)?(?:app|application|program|software)?\s*", "", cmd).strip()
            clean = re.sub(r"\s+(?:on|from)\s+(?:my\s+)?(?:mobile\s+)?phone[.\s!?]*$", "", clean).strip()
            clean = re.sub(r"\s+(?:app|application)$", "", clean).strip()
            return clean if clean else cmd

        elif intent == "open_app":
            # Remove leading action verbs
            clean = re.sub(r"^(?:can you|please|could you)?\s*(?:open|launch|start|fire up|run)\s+(?:up\s+)?(?:the\s+)?(?:app|application|program|software)?\s*", "", cmd).strip()
            clean = re.sub(r"\s+(?:app|application|program|software)$", "", clean).strip()
            return clean if clean else cmd

        elif intent == "spotify_play_song":
            clean = re.sub(r"^(?:can you|please)?\s*(?:play|put on|stream|listen to)\s+(?:the\s+)?(?:song|track|music)?\s*", "", cmd).strip()
            clean = re.sub(r"\s+(?:on spotify|in spotify|spotify)$", "", clean).strip()
            clean = re.sub(r"^(?:on spotify|in spotify|spotify)\s*", "", clean).strip()
            return clean if clean else cmd

        elif intent == "web_search":
            clean = re.sub(r"^(?:can you|please)?\s*(?:search|google|look up|find info about|search for)\s+(?:for\s+)?", "", cmd).strip()
            clean = re.sub(r"\s+(?:on google|in browser|on web|online)$", "", clean).strip()
            return clean if clean else cmd

        elif intent == "dictation":
            clean = re.sub(r"^(?:can you|please)?\s*(?:type|write|dictate|insert)\s+(?:out\s+)?(?:down\s+)?", "", cmd).strip()
            return clean if clean else cmd

        elif intent == "remember_fact":
            clean = re.sub(r"^(?:can you|please)?\s*(?:remember\s+that|remember)\s*", "", cmd).strip()
            return clean if clean else cmd

        elif intent == "screen_vision":
            return cmd

        return cmd

    @staticmethod
    def extract_whatsapp_entities(command: str) -> Tuple[str, str]:
        """
        Extracts contact name and message payload from WhatsApp commands.
        Returns (contact_name, message_text).
        """
        cmd = re.sub(r'[^\w\s,!?\'-]+$', '', command.strip().lower()).strip()

        # Pattern A: "... to [contact] saying [message]" or "... [contact] saying [message]"
        m = re.search(
            r"^(?:send\s+(?:a\s+)?whatsapp\s+(?:message\s+)?to|whatsapp|message|send\s+whatsapp\s+to)\s+(.+?)\s+saying\s+(.+)$",
            cmd
        )
        if m:
            return m.group(1).strip(), m.group(2).strip()

        # Pattern B: "send [contact] a (whatsapp) message saying [message]"
        m = re.search(
            r"^send\s+(.+?)\s+a\s+(?:whatsapp\s+)?message\s+saying\s+(.+)$",
            cmd
        )
        if m:
            return m.group(1).strip(), m.group(2).strip()

        # Fallback Pattern C: "send a whatsapp to [contact]" or "message [contact] on whatsapp"
        m = re.search(
            r"^(?:send\s+(?:a\s+)?whatsapp\s+(?:message\s+)?to|whatsapp|message|send\s+whatsapp\s+to)\s+(.+?)(?:\s+on\s+whatsapp)?$",
            cmd
        )
        if m:
            contact = m.group(1).strip()
            contact = re.sub(r"\s+on\s+whatsapp$", "", contact).strip()
            return contact, ""

        return "", ""
