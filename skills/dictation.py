import time
import logging
import pyautogui

logger = logging.getLogger(__name__)

class DictationSkill:
    """
    Skill for typing dictated spoken text directly into whichever Windows window currently holds keyboard focus.
    """
    @staticmethod
    def type_text(text: str) -> str:
        """
        Simulates keyboard keystrokes to type out the provided text string into the active window.
        """
        clean_text = text.strip()
        if not clean_text:
            return "What would you like me to type?"

        logger.info(f"Dictation triggered. Typing text: '{clean_text}'")

        # Small delay to ensure target window is active and focused
        time.sleep(0.5)

        try:
            # Type text using PyAutoGUI keystroke simulation
            pyautogui.write(clean_text, interval=0.01)
            return "Typing that out now"
        except Exception as e:
            logger.error(f"Failed to execute dictation typing: {e}")
            return f"Failed to type dictated text: {e}"
