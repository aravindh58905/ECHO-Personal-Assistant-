import logging
import speech_recognition as sr

logger = logging.getLogger(__name__)

class Listener:
    """
    Speech Recognition wrapper for capturing spoken commands via PyAudio stream.
    Supports mic detection validation and robust exception isolation.
    """
    def __init__(self, config: dict):
        self.config = config.get("audio", {})
        self.recognizer = sr.Recognizer()
        
        # Configure thresholds
        self.recognizer.energy_threshold = self.config.get("energy_threshold", 300)
        self.recognizer.dynamic_energy_threshold = self.config.get("dynamic_energy_threshold", True)
        self.timeout = self.config.get("timeout", 5)
        self.phrase_time_limit = self.config.get("phrase_time_limit", 10)

        # Calibrate microphone ambient noise
        self._calibrate_microphone()

    @staticmethod
    def get_available_microphones() -> list[str]:
        """
        Enumerates available audio input devices.
        Returns list of microphone names.
        """
        try:
            mics = sr.Microphone.list_microphone_names()
            return mics if mics else []
        except Exception as e:
            logger.error(f"Error enumerating audio input devices: {e}")
            return []

    def _calibrate_microphone(self):
        """
        Adjusts recognizer energy threshold according to ambient noise level.
        """
        try:
            with sr.Microphone() as source:
                logger.info("Calibrating microphone ambient noise level...")
                self.recognizer.adjust_for_ambient_noise(source, duration=1.0)
                logger.info(f"Microphone calibrated. Energy threshold set to {self.recognizer.energy_threshold}")
        except Exception as e:
            logger.warning(f"Microphone calibration notice: {e}. PyAudio mic stream will initialize on demand.")

    def listen(self, timeout: float | None = None) -> str | None:
        """
        Listens to the microphone stream for a single spoken command phrase.
        Returns lowercased recognized text, or None if unrecognized/timed out.
        """
        effective_timeout = timeout if timeout is not None else self.timeout
        try:
            with sr.Microphone() as source:
                logger.info("Listening for command...")
                audio = self.recognizer.listen(
                    source,
                    timeout=effective_timeout,
                    phrase_time_limit=self.phrase_time_limit
                )

            logger.info("Processing captured audio...")
            # Speech recognition via Google Speech API (free default endpoint)
            command = self.recognizer.recognize_google(audio)
            command_text = command.strip().lower()
            logger.info(f"[Captured Speech]: '{command_text}'")
            return command_text

        except sr.WaitTimeoutError:
            logger.debug("Listening timed out waiting for phrase.")
            return None
        except sr.UnknownValueError:
            logger.info("Speech recognition could not understand audio.")
            return None
        except sr.RequestError as e:
            logger.error(f"Speech recognition service request error: {e}")
            return None
        except Exception as e:
            logger.error(f"Audio listening exception in Listener: {e}", exc_info=True)
            raise e  # Let caller catch mic streaming exceptions for recovery notice
