import sys
import os
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.wake_word import WakeWordDetector

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

def test_wake_word_initialization():
    config = {
        "picovoice": {
            "access_key": "",
            "wake_word": "echo"
        }
    }
    detector = WakeWordDetector(config)
    assert detector.fallback_mode is True, "Expected fallback_mode to be True when access_key is empty"
    assert detector.wake_word == "echo", f"Expected wake_word to be 'echo', got '{detector.wake_word}'"
    print("WakeWordDetector initialization test PASSED!")

if __name__ == "__main__":
    test_wake_word_initialization()
