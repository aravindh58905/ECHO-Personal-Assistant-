import re
import datetime
import logging
from skills.open_app import AppLauncher
from skills.system_info import SystemInfoSkill
from skills.web_search import WebSearchSkill
from skills.power_control import PowerControlSkill
from skills.media_control import MediaControlSkill
from skills.dictation import DictationSkill
from skills.spotify_control import SpotifyControlSkill
from skills.phone_control import PhoneControlSkill
from skills.whatsapp_control import WhatsAppControlSkill
from core.screen_vision import ScreenVisionSkill
from core.llm_brain import LLMBrain
from core.intent_classifier import IntentClassifier
from core.memory_store import MemoryStore

logger = logging.getLogger(__name__)

class CommandRouter:
    """
    Three-tier command router supporting:
    1. Layer 1: Fast exact string & regex pattern matching (zero overhead).
    2. Layer 2: Local sentence embedding semantic intent classification (SentenceTransformers).
    3. Layer 3: LLM chit-chat fallback (Gemini API).
    """
    def __init__(self, config: dict, speaker=None):
        self.config = config
        self.speaker = speaker
        self.app_launcher = AppLauncher(config)
        self.system_info = SystemInfoSkill()
        self.web_search = WebSearchSkill()
        self.power_control = PowerControlSkill()
        self.media_control = MediaControlSkill(config)
        self.dictation = DictationSkill()
        self.spotify_control = SpotifyControlSkill()
        self.phone_control = PhoneControlSkill(config)
        self.whatsapp_control = WhatsAppControlSkill(config)
        self.screen_vision = ScreenVisionSkill(config, speaker=speaker)
        self.memory_store = MemoryStore(config)
        self.llm_brain = LLMBrain(config, memory_store=self.memory_store)
        self.intent_classifier = IntentClassifier(config)
        self.honorific = config.get("assistant", {}).get("user_honorific", "boss")
        
        self.last_command = "None"
        self.last_response = "None"

    def route(self, command: str) -> str:
        """
        Parses text input and dispatches command to skill handlers across 3 routing layers.
        Returns spoken response message. Wraps all actions to prevent crashes.
        """
        if not command or not command.strip():
            return "I didn't catch that command. Could you repeat it?"

        cmd = re.sub(r'[^\w\s]+$', '', command.lower().strip()).strip()
        self.last_command = command
        logger.info(f"[Router Received Command]: '{cmd}' (Raw: '{command}')")

        try:
            # Layer 1: Exact / Regex Pattern Matching (Fast, zero cost)
            response = self._dispatch_exact_intent(cmd)
            if response is not None:
                logger.info(f"[Exact Intent Match Triggered]: '{cmd}' -> Response: '{response}'")
                self.last_response = response
                return response

            # Layer 2: Semantic Intent Classification (Sentence-Transformers)
            intent, confidence = self.intent_classifier.classify(cmd)
            if intent is not None:
                logger.info(f"[Semantic Intent Match]: Intent='{intent}', Confidence={confidence:.4f} for command '{cmd}'")
                response = self._dispatch_semantic_intent(cmd, intent)
                if response is not None:
                    self.last_response = response
                    logger.info(f"[Router Response Spoken via Semantic Match]: '{response}'")
                    return response

            # Layer 3: Gemini LLM Chit-Chat Fallback
            logger.info(f"[Semantic Intent Low Confidence]: Score={confidence:.4f} < Threshold={self.intent_classifier.threshold}. Falling back to LLM Brain for: '{cmd}'")
            llm_response = self.llm_brain.ask(cmd)
            response = llm_response if llm_response else "I didn't understand that command. Could you rephrase it?"

        except Exception as e:
            logger.error(f"[Router Error]: Unhandled exception processing command '{cmd}': {e}", exc_info=True)
            response = "I couldn't do that, boss."

        self.last_response = response
        logger.info(f"[Router Response Spoken]: '{response}'")
        return response

    def _dispatch_exact_intent(self, cmd: str) -> str | None:
        """
        Layer 1: Internal exact string and regex intent matcher.
        Returns response string if matched, or None if no exact match found.
        """
        # 0. Screen Vision Queries ("what's wrong here", "what am i looking at", "what's on my screen", "can you see this")
        screen_keywords = [
            "what's wrong here", "what is wrong here", "what am i doing wrong",
            "what am i looking at", "what's on my screen", "what is on my screen",
            "can you see this", "look at my screen", "check my screen", "help me with this screen"
        ]
        if any(kw in cmd for kw in screen_keywords):
            self.llm_brain.reset_memory()
            return self.screen_vision.capture_and_ask(cmd)

        # 1. Handle pending confirmation state (e.g. for power management actions)
        if self.power_control.pending_action:
            self.llm_brain.reset_memory()
            _, response = self.power_control.execute_pending(cmd)
            return response

        # 2. Spotify Queries (Currently Playing Track)
        if any(kw in cmd for kw in ["what's playing", "what song is this", "current song", "what's the song", "currently playing"]):
            self.llm_brain.reset_memory()
            return self.spotify_control.get_current_track()

        # 3. Spotify Song Search & Playback Control ("play [song name]", "put on [song name]")
        spotify_play_match = re.search(r"^(?:play|put on)\s+(.+?)(?:\s+on spotify)?$", cmd)
        if spotify_play_match:
            song_target = spotify_play_match.group(1).strip()
            # Exclude generic playback keywords so bare media controls still use Windows virtual keys
            generic_playback_words = ["music", "song", "playback", "audio", "track", "something"]
            if song_target not in generic_playback_words:
                self.llm_brain.reset_memory()
                return self.spotify_control.play_song(song_target)

        # 4. Media Playback & Volume Control (Windows Media Keys Fallback)
        if any(kw in cmd for kw in ["next song", "skip song", "next track", "skip track"]):
            self.llm_brain.reset_memory()
            return self.media_control.next_track()

        if any(kw in cmd for kw in ["previous song", "last song", "go back", "previous track"]):
            self.llm_brain.reset_memory()
            return self.media_control.prev_track()

        if any(kw in cmd for kw in ["pause music", "pause song", "pause playback"]):
            self.llm_brain.reset_memory()
            return self.media_control.play_pause()

        if any(kw in cmd for kw in ["play music", "resume music", "resume song", "resume playback"]):
            self.llm_brain.reset_memory()
            return self.media_control.play_pause()

        # Simple "pause" / "play" / "resume" when standing alone or in short phrase
        if cmd in ["pause", "stop music"]:
            self.llm_brain.reset_memory()
            return self.media_control.play_pause()

        if cmd in ["play", "resume"]:
            self.llm_brain.reset_memory()
            return self.media_control.play_pause()

        if any(kw in cmd for kw in ["volume up", "increase volume", "louder"]):
            self.llm_brain.reset_memory()
            return self.media_control.volume_up()

        if any(kw in cmd for kw in ["volume down", "lower volume", "quieter"]):
            self.llm_brain.reset_memory()
            return self.media_control.volume_down()

        if any(kw in cmd for kw in ["mute audio", "mute sound", "mute volume", "mute"]):
            self.llm_brain.reset_memory()
            return self.media_control.mute()

        # 5. Time & Date commands
        if any(kw in cmd for kw in ["what time", "current time", "tell me the time"]):
            self.llm_brain.reset_memory()
            now = datetime.datetime.now()
            time_str = now.strftime("%I:%M %p")
            return f"The current time is {time_str}"

        if any(kw in cmd for kw in ["what date", "today's date", "what day is it"]):
            self.llm_brain.reset_memory()
            now = datetime.datetime.now()
            date_str = now.strftime("%A, %B %d, %Y")
            return f"Today is {date_str}"

        # 6. System Status / Telemetry
        if any(kw in cmd for kw in ["system status", "battery", "cpu", "ram usage", "system info"]):
            self.llm_brain.reset_memory()
            return self.system_info.get_status()

        # 7. WhatsApp Messaging ("send a whatsapp message to [contact] saying [message]", etc.)
        whatsapp_match = re.search(
            r"^(?:send\s+(?:a\s+)?whatsapp\s+(?:message\s+)?to|whatsapp|send\s+whatsapp\s+to|message)\s+(.+?)\s+saying\s+(.+)$",
            cmd
        )
        if not whatsapp_match:
            whatsapp_match = re.search(
                r"^send\s+(.+?)\s+a\s+(?:whatsapp\s+)?message\s+saying\s+(.+)$",
                cmd
            )
        if whatsapp_match:
            contact = whatsapp_match.group(1).strip()
            message = whatsapp_match.group(2).strip()
            self.llm_brain.reset_memory()
            return self.whatsapp_control.send_message(contact, message)

        # 8. Open / Launch Applications on Phone vs Desktop
        phone_match = re.search(r"(?:open|launch|start)\s+(.+?)\s+on\s+(?:my\s+)?(?:mobile\s+)?phone[.\s!?]*$", cmd)
        if phone_match:
            target_app = phone_match.group(1).strip()
            self.llm_brain.reset_memory()
            return self.phone_control.open_app(target_app)

        open_match = re.search(r"(?:open|launch|start)\s+(.+)", cmd)
        if open_match:
            target_app = open_match.group(1).strip()
            # Safety check: If app name ends with phone target, reroute to phone_control
            phone_submatch = re.search(r"^(.+?)\s+on\s+(?:my\s+)?(?:mobile\s+)?phone[.\s!?]*$", target_app)
            if phone_submatch:
                real_target = phone_submatch.group(1).strip()
                self.llm_brain.reset_memory()
                return self.phone_control.open_app(real_target)

            # Exclude search phrases misidentified as apps
            if not target_app.startswith("google") and not target_app.startswith("browser"):
                self.llm_brain.reset_memory()
                _, response = self.app_launcher.open(target_app)
                return response

        # 8. Web Search commands
        search_match = re.search(r"(?:search|google|look up)\s+(?:for\s+)?(.+)", cmd)
        if search_match:
            search_query = search_match.group(1).strip()
            search_query = re.sub(r"^(?:on google|in browser)\s+", "", search_query).strip()
            self.llm_brain.reset_memory()
            return self.web_search.search(search_query)

        # 9. Voice Dictation commands
        dictate_match = re.search(r"^(?:write|type|dictate)\s+(.+)", cmd)
        if dictate_match:
            self.llm_brain.reset_memory()
            dictation_text = dictate_match.group(1).strip()
            return self.dictation.type_text(dictation_text)

        # 10. Memory Store commands ("remember that...", "what do you remember")
        remember_match = re.search(r"^(?:remember\s+that|remember)\s+(.+)", cmd)
        if remember_match:
            fact_text = remember_match.group(1).strip()
            return self._handle_remember_fact(fact_text)

        if any(kw in cmd for kw in ["what do you know about me", "what do you remember", "what facts do you remember", "tell me what you know about me"]):
            return self._handle_recall_memory()

        # 11. Power Management (Shutdown, Restart, Sleep)
        if any(kw in cmd for kw in ["shut down", "shutdown", "turn off pc", "restart", "reboot", "sleep mode"]):
            for power_kw in ["shutdown", "shut down", "restart", "reboot", "sleep"]:
                if power_kw in cmd:
                    self.llm_brain.reset_memory()
                    return self.power_control.request_power_action(power_kw)

        # 12. Greeting / Identity queries
        if any(kw in cmd for kw in ["who are you", "what is your name", "identify yourself"]):
            self.llm_brain.reset_memory()
            name = self.config.get("assistant", {}).get("name", "ECHO")
            return f"I am {name}, your personal AI assistant."

        if any(kw in cmd for kw in ["hello", "hi", "hey"]):
            self.llm_brain.reset_memory()
            return "Hello! How can I assist you today?"

        return None

    def _dispatch_semantic_intent(self, cmd: str, intent: str) -> str | None:
        """
        Layer 2: Dispatches semantically matched intent label to skill handlers.
        """
        self.llm_brain.reset_memory()

        if intent == "spotify_current_track":
            return self.spotify_control.get_current_track()

        elif intent == "spotify_play_song":
            song_target = IntentClassifier.extract_entity(cmd, "spotify_play_song")
            return self.spotify_control.play_song(song_target)

        elif intent == "next_track":
            return self.media_control.next_track()

        elif intent == "previous_track":
            return self.media_control.prev_track()

        elif intent == "play_pause_media":
            return self.media_control.play_pause()

        elif intent == "volume_up":
            return self.media_control.volume_up()

        elif intent == "volume_down":
            return self.media_control.volume_down()

        elif intent == "mute":
            return self.media_control.mute()

        elif intent == "time_query":
            now = datetime.datetime.now()
            return f"The current time is {now.strftime('%I:%M %p')}"

        elif intent == "date_query":
            now = datetime.datetime.now()
            return f"Today is {now.strftime('%A, %B %d, %Y')}"

        elif intent == "system_status":
            return self.system_info.get_status()

        elif intent == "open_phone_app":
            target_app = IntentClassifier.extract_entity(cmd, "open_phone_app")
            return self.phone_control.open_app(target_app)

        elif intent == "open_app":
            target_app = IntentClassifier.extract_entity(cmd, "open_app")
            _, response = self.app_launcher.open(target_app)
            return response

        elif intent == "web_search":
            query = IntentClassifier.extract_entity(cmd, "web_search")
            return self.web_search.search(query)

        elif intent == "dictation":
            dict_text = IntentClassifier.extract_entity(cmd, "dictation")
            return self.dictation.type_text(dict_text)

        elif intent == "remember_fact":
            fact_text = IntentClassifier.extract_entity(cmd, "remember_fact")
            return self._handle_remember_fact(fact_text)

        elif intent == "recall_memory":
            return self._handle_recall_memory()

        elif intent == "power_shutdown":
            return self.power_control.request_power_action("shutdown")

        elif intent == "power_restart":
            return self.power_control.request_power_action("restart")

        elif intent == "screen_vision":
            return self.screen_vision.capture_and_ask(cmd)

        elif intent == "send_whatsapp":
            contact, message = IntentClassifier.extract_whatsapp_entities(cmd)
            return self.whatsapp_control.send_message(contact, message)

        return None

    def _handle_remember_fact(self, fact_text: str) -> str:
        """
        Stores user fact in MemoryStore and returns spoken confirmation.
        """
        self.llm_brain.reset_memory()
        if not fact_text:
            return f"I didn't catch what you wanted me to remember, {self.honorific}."
        
        self.memory_store.add_fact(fact_text)
        return f"Got it, {self.honorific}. I've committed that to memory."

    def _handle_recall_memory(self) -> str:
        """
        Retrieves all stored memories and returns a concise spoken persona summary.
        """
        self.llm_brain.reset_memory()
        facts = self.memory_store.get_all()
        if not facts:
            return f"I don't have any saved facts about you yet, {self.honorific}."

        formatted_facts = []
        for key, val in facts.items():
            if key == "name":
                formatted_facts.append(f"your name is {val}")
            else:
                formatted_facts.append(val)

        summary = ", ".join(formatted_facts)
        return f"Here is what I remember about you, {self.honorific}: {summary}."
