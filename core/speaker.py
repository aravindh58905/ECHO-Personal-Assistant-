import os
import sys
import time
import logging
import asyncio
import tempfile
import threading
import pyttsx3
import edge_tts
import pygame

logger = logging.getLogger(__name__)

class Speaker:
    """
    Text-to-Speech manager supporting edge-tts (high-quality natural voice)
    with pyttsx3 offline fallback and persona-consistent speech formatting.
    """
    def __init__(self, config: dict):
        self.config = config
        self.tts_config = config.get("tts", {})
        self.engine_type = self.tts_config.get("engine", "edge-tts").lower()
        self.voice = self.tts_config.get("voice", "en-US-ChristopherNeural")
        self.rate = self.tts_config.get("rate", "+0%")
        self.volume = self.tts_config.get("volume", "+0%")
        self.assistant_name = config.get("assistant", {}).get("name", "ECHO")
        self.honorific = config.get("assistant", {}).get("user_honorific", "boss")
        
        self.speech_lock = threading.Lock()
        
        # Initialize pygame mixer for audio playback
        try:
            pygame.mixer.init()
        except Exception as e:
            logger.warning(f"Pygame mixer initialization warning: {e}")

        # Initialize pyttsx3 fallback engine
        self.pyttsx3_engine = None
        try:
            self.pyttsx3_engine = pyttsx3.init()
            self.pyttsx3_engine.setProperty('rate', 185)
        except Exception as e:
            logger.warning(f"Failed to initialize pyttsx3 engine: {e}")

    def format_persona(self, text: str) -> str:
        """
        Formats response text to ensure consistent assistant persona.
        """
        text = text.strip()
        if not text:
            return ""
        
        # If text doesn't already contain honorific, prepend or append naturally
        text_lower = text.lower()
        if self.honorific not in text_lower and "sir" not in text_lower:
            if not text.endswith((".", "!", "?")):
                text += "."
            text = f"{text} {self.honorific.capitalize()}."
        return text

    def speak(self, text: str, format_persona: bool = True):
        """
        Main entrypoint for speaking text out loud.
        Thread-safe execution.
        """
        if not text:
            return

        final_text = self.format_persona(text) if format_persona else text
        logger.info(f"[{self.assistant_name} Speaking]: {final_text}")
        print(f"\n[{self.assistant_name}]: {final_text}\n")

        with self.speech_lock:
            success = False
            if self.engine_type == "edge-tts":
                success = self._speak_edge_tts(final_text)
            
            # Fallback to pyttsx3 if edge-tts fails or is selected
            if not success:
                self._speak_pyttsx3(final_text)

    def _speak_edge_tts(self, text: str) -> bool:
        """
        Synthesizes text using edge-tts and plays back via Pygame.
        Returns True if successful, False otherwise.
        """
        temp_file = None
        try:
            fd, temp_file = tempfile.mkstemp(suffix=".mp3")
            os.close(fd)

            async def _generate():
                communicate = edge_tts.Communicate(
                    text=text,
                    voice=self.voice,
                    rate=self.rate,
                    volume=self.volume
                )
                await communicate.save(temp_file)

            # Run edge-tts synthesis in asyncio loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    future = asyncio.run_coroutine_threadsafe(_generate(), loop)
                    future.result(timeout=10)
                else:
                    loop.run_until_complete(_generate())
            except RuntimeError:
                asyncio.run(_generate())

            if not os.path.exists(temp_file) or os.path.getsize(temp_file) == 0:
                return False

            # Play audio file via Pygame mixer
            if not pygame.mixer.get_init():
                pygame.mixer.init()

            pygame.mixer.music.load(temp_file)
            pygame.mixer.music.play()

            while pygame.mixer.music.get_busy():
                time.sleep(0.1)

            pygame.mixer.music.unload()
            return True

        except Exception as e:
            logger.warning(f"edge-tts synthesis failed ({e}). Falling back to pyttsx3.")
            return False
        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass

    def _speak_pyttsx3(self, text: str):
        """
        Offline fallback TTS engine using pyttsx3.
        """
        try:
            if self.pyttsx3_engine:
                self.pyttsx3_engine.say(text)
                self.pyttsx3_engine.runAndWait()
            else:
                logger.error("No working TTS engine available.")
        except Exception as e:
            logger.error(f"pyttsx3 error: {e}")
