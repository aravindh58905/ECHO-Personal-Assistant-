import subprocess
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


class PhoneControlSkill:
    """
    Skill for controlling a connected Android phone using ADB (Android Debug Bridge).
    Enables launching apps by friendly name mapped to package names.
    """
    def __init__(self, config: dict):
        self.config = config
        phone_cfg = config.get("phone_control", {})
        self.enabled = phone_cfg.get("enabled", True)
        self.adb_path = phone_cfg.get("adb_path", "adb")
        self.phone_apps = phone_cfg.get("phone_apps", {
            "instagram": "com.instagram.android",
            "whatsapp": "com.whatsapp",
            "youtube": "com.google.android.youtube",
            "camera": "com.android.camera",
            "chrome": "com.android.chrome",
            "photos": "com.google.android.apps.photos",
            "gallery": "com.google.android.apps.photos",
            "maps": "com.google.android.apps.maps",
            "spotify": "com.spotify.music"
        })

    def is_device_connected(self) -> Tuple[bool, str]:
        """
        Checks ADB device connection status using `adb devices`.
        Returns:
            Tuple[bool, str]: (is_connected, error_or_status_message)
        """
        cmd = [self.adb_path, "devices"]
        cmd_str = " ".join(cmd)
        logger.info(f"Checking ADB device connection status with command: '{cmd_str}'")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5
            )
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()

            logger.info(f"ADB devices check finished with exit code {result.returncode}. Stdout: '{stdout}' | Stderr: '{stderr}'")

            if "unauthorized" in stdout:
                logger.warning("ADB device is unauthorized. Please allow USB debugging on your phone.")
                return False, "Phone ADB authorization requested, boss. Please check your phone screen and allow USB debugging."

            lines = stdout.splitlines()
            connected_devices = []
            for line in lines[1:]:
                line = line.strip()
                if line and ("\tdevice" in line or line.endswith("device")):
                    connected_devices.append(line)

            if not connected_devices:
                logger.info("No ADB device connected.")
                return False, "No phone connected, boss."

            logger.info(f"Found {len(connected_devices)} connected ADB device(s): {connected_devices}")
            return True, ""

        except FileNotFoundError:
            logger.error(f"ADB executable not found at path: '{self.adb_path}'")
            return False, "ADB is not installed or not found in system PATH, boss."
        except subprocess.TimeoutExpired:
            logger.error("ADB device check timed out.")
            return False, "ADB device check timed out, boss."
        except Exception as e:
            logger.error(f"Failed to check ADB device status: {e}", exc_info=True)
            return False, "I ran into an issue connecting to your phone, boss."

    def open_app(self, app_name: str) -> str:
        """
        Launches an application on the connected Android phone via ADB monkey tool.

        Args:
            app_name (str): Friendly name of the application (e.g., 'instagram', 'whatsapp')

        Returns:
            str: Spoken response message.
        """
        if not self.enabled:
            logger.warning("Attempted phone control, but phone_control skill is disabled in configuration.")
            return "Phone control is currently disabled in your configuration, boss."

        clean_name = app_name.strip().lower()
        if not clean_name:
            return "Please specify which app to open on your phone, boss."

        # Confirm ADB connection before running launch command
        is_connected, err_msg = self.is_device_connected()
        if not is_connected:
            logger.warning(f"Cannot launch '{clean_name}' - device connection check failed: {err_msg}")
            return err_msg

        package_name = self.phone_apps.get(clean_name)
        if not package_name:
            for key, val in self.phone_apps.items():
                if key in clean_name or clean_name in key:
                    package_name = val
                    clean_name = key
                    break

        if not package_name:
            logger.warning(f"No package mapping found for phone app: '{app_name}'")
            return f"I don't have a package name configured for {app_name} on your phone, boss."

        cmd = [
            self.adb_path,
            "shell",
            "monkey",
            "-p", package_name,
            "-c", "android.intent.category.LAUNCHER",
            "1"
        ]
        cmd_str = " ".join(cmd)
        logger.info(f"Executing ADB launch command for '{clean_name}' (Package: '{package_name}'): '{cmd_str}'")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()

            logger.info(f"ADB launch command completed. Exit Code: {result.returncode} | Stdout: '{stdout}' | Stderr: '{stderr}'")

            if "No activities found to run" in stdout or "No activities found to run" in stderr:
                logger.warning(f"App package '{package_name}' not installed on target device.")
                return f"Could not launch {clean_name} on your phone. App package does not appear to be installed, boss."

            if result.returncode == 0 and ("Events injected" in stdout or not stderr):
                logger.info(f"Successfully confirmed launch of '{clean_name}' on phone.")
                return f"Opening {clean_name} on your phone, boss."
            else:
                logger.error(f"ADB command failed or returned non-zero code ({result.returncode}). Stdout: '{stdout}', Stderr: '{stderr}'")
                return f"That didn't work, boss. Failed to open {clean_name} on your phone."

        except subprocess.TimeoutExpired:
            logger.error(f"ADB command to launch '{clean_name}' timed out.")
            return f"Opening {clean_name} timed out, boss."
        except Exception as e:
            logger.error(f"Unexpected error launching '{clean_name}' via ADB: {e}", exc_info=True)
            return f"I couldn't open {clean_name} on your phone, boss."
