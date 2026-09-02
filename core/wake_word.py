import os
import time
import logging
import struct
import pvporcupine
import pyaudio
import speech_recognition as sr

logger = logging.getLogger(__name__)

class WakeWordDetector:
    """
    Offline wake-word detector using Picovoice Porcupine.
    Includes a fallback speech recognition loop when access key is missing.
    """
    def __init__(self, config: dict):
        self.config = config.get("picovoice", {})
        self.access_key = self.config.get("access_key", "").strip()
        self.wake_word = self.config.get("wake_word", "echo").lower()
        self.custom_path = self.config.get("custom_wake_word_path", "").strip()
        self.sensitivity = self.config.get("sensitivity", 0.5)

        self.porcupine = None
        self.pa = None
        self.audio_stream = None
        self.fallback_mode = False

        self._initialize_detector()

    def _initialize_detector(self):
        """
        Initializes Picovoice Porcupine engine or activates testing fallback.
        """
        if not self.access_key:
            self._activate_fallback("NO_API_KEY")
            return

        try:
            # Check for custom .ppn keyword file vs built-in keyword
            if self.custom_path and os.path.exists(self.custom_path):
                logger.info(f"Loading custom Porcupine model file: {self.custom_path}")
                self.porcupine = pvporcupine.create(
                    access_key=self.access_key,
                    keyword_paths=[self.custom_path],
                    sensitivities=[self.sensitivity]
                )
            else:
                # Built-in keyword validation
                builtin_keywords = list(pvporcupine.KEYWORDS)
                if self.wake_word not in builtin_keywords:
                    logger.warning(
                        f"Wake word '{self.wake_word}' is NOT a built-in Porcupine keyword! "
                        f"Built-in options: {builtin_keywords}. Defaulting to 'jarvis'."
                    )
                    self.wake_word = "jarvis"

                logger.info(f"Initializing Porcupine with built-in keyword: '{self.wake_word}'")
                self.porcupine = pvporcupine.create(
                    access_key=self.access_key,
                    keywords=[self.wake_word],
                    sensitivities=[self.sensitivity]
                )

            self.pa = pyaudio.PyAudio()
            self.audio_stream = self.pa.open(
                rate=self.porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=self.porcupine.frame_length
            )
            logger.info("Porcupine wake-word engine initialized successfully.")

        except Exception as e:
            logger.error(f"Failed to initialize Porcupine engine: {e}")
            self._activate_fallback(str(e))

    def _activate_fallback(self, reason: str):
        """
        Activates continuous speech recognition fallback mode.
        """
        self.fallback_mode = True
        print("\n" + "=" * 70)
        print(" [WARNING] PICOVOICE ACCESS KEY MISSING OR INVALID ")
        print(" Running in FALLBACK MODE using continuous Speech Recognition.")
        print(" CAUTION: Fallback mode is CPU/BATTERY HEAVY and meant for TESTING ONLY.")
        print(" Get a free AccessKey at https://console.picovoice.ai/ for zero-CPU background listening.")
        print("=" * 70 + "\n")
        logger.warning(f"Fallback mode activated (Reason: {reason}). Continuous STT will be used for wake detection.")
        
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True

    def listen_for_wake_word(self, stop_checker=None) -> bool:
        """
        Blocks until the wake word is detected or stop_checker returns True.
        Returns True when wake word triggers, False if interrupted/stopped.
        """
        if self.fallback_mode:
            return self._listen_fallback(stop_checker)
        else:
            return self._listen_porcupine(stop_checker)

    def _listen_porcupine(self, stop_checker) -> bool:
        """
        Low-CPU offline wake word loop via Porcupine.
        """
        try:
            while True:
                if stop_checker and stop_checker():
                    return False

                pcm = self.audio_stream.read(self.porcupine.frame_length, exception_on_overflow=False)
                pcm = struct.unpack_from("h" * self.porcupine.frame_length, pcm)

                keyword_index = self.porcupine.process(pcm)
                if keyword_index >= 0:
                    logger.info(f"Wake word '{self.wake_word}' detected by Porcupine!")
                    return True
        except Exception as e:
            logger.error(f"Error in Porcupine stream: {e}")
            time.sleep(0.5)
            return False

    def _listen_fallback(self, stop_checker) -> bool:
        """
        CPU/battery-heavy fallback loop checking for wake word in captured audio stream.
        Prints and logs transcribed text for real-time terminal feedback.
        """
        try:
            with sr.Microphone() as source:
                # Calibrate ambient noise once at stream start
                try:
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                except Exception as cal_err:
                    logger.warning(f"Microphone noise adjustment notice: {cal_err}")

                while True:
                    if stop_checker and stop_checker():
                        return False
                    
                    try:
                        audio = self.recognizer.listen(source, timeout=2.0, phrase_time_limit=4.0)
                        text = self.recognizer.recognize_google(audio).lower().strip()
                        
                        if text:
                            # Explicit terminal print and logger.info for real-time visibility
                            print(f"[Fallback Transcribed]: '{text}'")
                            logger.info(f"[Fallback Listener Stream]: Transcribed text: '{text}'")
                            
                            # Check if wake word or assistant name/phonetic variation appears in speech
                            target_names = [
                                self.wake_word, "echo", "eco", "eko", "heko", "ekko", "ecco",
                                "hey echo", "hey eco", "jarvis", "friday"
                            ]
                            if any(name in text for name in target_names):
                                print(f"[Fallback Triggered]: Matched wake word in '{text}'!")
                                logger.info(f"Wake word triggered in fallback mode via text: '{text}'")
                                return True

                    except sr.WaitTimeoutError:
                        # Normal timeout when no speech is detected in 2-second window
                        continue
                    except sr.UnknownValueError:
                        # Audio captured but no recognizable words
                        logger.debug("Fallback STT could not understand audio snippet.")
                        continue
                    except sr.RequestError as e:
                        logger.error(f"Fallback STT service error: {e}")
                        time.sleep(1.0)
        except Exception as e:
            logger.error(f"Fallback wake word loop error: {e}", exc_info=True)
            time.sleep(1.0)
            return False

    def cleanup(self):
        """
        Releases PyAudio and Porcupine resources.
        """
        try:
            if self.audio_stream:
                self.audio_stream.stop_stream()
                self.audio_stream.close()
            if self.porcupine:
                self.porcupine.delete()
            if self.pa:
                self.pa.terminate()
            logger.info("WakeWordDetector resources cleaned up.")
        except Exception as e:
            logger.warning(f"Error releasing WakeWordDetector resources: {e}")
