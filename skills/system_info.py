import psutil
import logging

logger = logging.getLogger(__name__)

class SystemInfoSkill:
    """
    Skill for gathering system metrics (battery level, CPU usage, RAM utilization).
    """
    @staticmethod
    def get_status() -> str:
        """
        Gathers system hardware stats and formats a spoken status response.
        """
        try:
            cpu_percent = psutil.cpu_percent(interval=0.5)
            memory = psutil.virtual_memory()
            ram_percent = memory.percent

            status_msg = f"CPU usage is at {cpu_percent} percent. Memory utilization is at {ram_percent} percent"

            # Battery status check
            battery = psutil.sensors_battery()
            if battery is not None:
                plug_str = "plugged in" if battery.power_plugged else "on battery"
                status_msg += f". Battery is at {int(battery.percent)} percent and currently {plug_str}"

            logger.info(f"System status retrieved: {status_msg}")
            return status_msg
        except Exception as e:
            logger.error(f"Error gathering system info: {e}")
            return "Unable to retrieve hardware telemetry at this moment"
