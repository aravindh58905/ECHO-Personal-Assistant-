import subprocess
import logging

logger = logging.getLogger(__name__)

class PowerControlSkill:
    """
    Skill for PC power operations (Shutdown, Restart, Sleep) with explicit safety confirmation.
    """
    def __init__(self):
        self.pending_action = None

    def request_power_action(self, action_type: str) -> str:
        """
        Registers a pending power action and prompts the user for confirmation.
        """
        action_type = action_type.lower()
        if action_type in ["shutdown", "shut down", "turn off"]:
            self.pending_action = "shutdown"
            return "Are you sure you want to shut down the computer?"
        elif action_type in ["restart", "reboot"]:
            self.pending_action = "restart"
            return "Are you sure you want to restart the system?"
        elif action_type in ["sleep", "suspend"]:
            self.pending_action = "sleep"
            return "Are you sure you want to put the computer to sleep?"
        else:
            return "Unrecognized power management command."

    def execute_pending(self, user_confirmation: str) -> tuple[bool, str]:
        """
        Executes or cancels pending power action depending on user response.
        """
        if not self.pending_action:
            return False, "No power action is currently pending."

        confirmation = user_confirmation.lower().strip()
        action = self.pending_action
        self.pending_action = None  # Reset pending state

        affirmative_tokens = ["yes", "confirm", "do it", "sure", "yep", "proceed"]
        if any(token in confirmation for token in affirmative_tokens):
            return self._run_os_command(action)
        else:
            logger.info("Power action cancelled by user confirmation response.")
            return False, "Power control command cancelled."

    def _run_os_command(self, action: str) -> tuple[bool, str]:
        """
        Executes native Windows power CLI commands.
        """
        try:
            if action == "shutdown":
                logger.warning("Executing Windows Shutdown command (shutdown /s /t 10)")
                subprocess.run("shutdown /s /t 10", shell=True)
                return True, "Initiating system shutdown in 10 seconds."
            elif action == "restart":
                logger.warning("Executing Windows Restart command (shutdown /r /t 10)")
                subprocess.run("shutdown /r /t 10", shell=True)
                return True, "Rebooting system in 10 seconds."
            elif action == "sleep":
                logger.info("Putting Windows PC to sleep mode")
                subprocess.run("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
                return True, "Putting system into sleep mode."
            return False, "Unknown action execution error."
        except Exception as e:
            logger.error(f"Error executing power command '{action}': {e}")
            return False, f"Failed to execute power operation: {e}"
