import os
import subprocess
import logging

logger = logging.getLogger(__name__)

class AppLauncher:
    """
    Skill for launching Windows applications based on configured mappings or direct executable names.
    """
    def __init__(self, config: dict):
        self.app_mapping = config.get("apps", {})

    def open(self, app_name: str) -> tuple[bool, str]:
        """
        Attempts to launch the target application.
        Returns tuple: (success: bool, response_message: str)
        """
        clean_name = app_name.strip().lower()

        if "on phone" in clean_name or "on my phone" in clean_name:
            logger.warning(f"AppLauncher received phone-targeted command '{clean_name}'. Refusing desktop execution.")
            return False, f"I couldn't open {clean_name} on your PC, boss."

        executable = self.app_mapping.get(clean_name, clean_name)

        logger.info(f"Attempting to launch application: '{clean_name}' (Target executable: '{executable}')")

        try:
            # First attempt os.startfile for Windows native app names/protocol handlers
            if hasattr(os, "startfile"):
                try:
                    os.startfile(executable)
                    return True, f"Launching {clean_name} now"
                except Exception:
                    pass

            # Fallback to subprocess Popen
            subprocess.Popen(executable, shell=True)
            return True, f"Opening {clean_name}"

        except Exception as e:
            logger.error(f"Failed to launch application '{clean_name}': {e}")
            return False, f"I couldn't open {clean_name}. Please check if it's installed and added to PATH"
