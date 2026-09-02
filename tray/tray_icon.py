import time
import threading
import logging
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item

logger = logging.getLogger(__name__)

class TrayIconManager:
    """
    Manages Windows System Tray icon using pystray and dynamic Pillow graphics.
    Provides non-blocking background control for Status report, Pause/Resume, HUD Overlay, and Quit actions.
    """
    def __init__(self, assistant_name: str = "ECHO", on_quit_callback=None, status_provider=None, on_toggle_hud=None, on_toggle_dashboard=None):
        self.assistant_name = assistant_name
        self.on_quit_callback = on_quit_callback
        self.status_provider = status_provider  # Callback function returning status dict
        self.on_toggle_hud = on_toggle_hud
        self.on_toggle_dashboard = on_toggle_dashboard
        
        self.is_paused = False
        self.is_running = True
        self.icon = None
        self.thread = None

    def _create_image(self, width=64, height=64, paused=False):
        """
        Dynamically draws an AI core tray icon image (cyan active ring / orange paused ring).
        """
        image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Color palette
        ring_color = (255, 165, 0, 255) if paused else (0, 210, 255, 255)
        core_color = (200, 100, 0, 255) if paused else (0, 140, 240, 255)
        bg_dark = (15, 23, 42, 255)

        # Outer rounded dark base
        draw.ellipse((4, 4, width - 4, height - 4), fill=bg_dark, outline=ring_color, width=3)
        # Inner glowing core
        draw.ellipse((18, 18, width - 18, height - 18), fill=core_color)
        # Core highlight
        draw.ellipse((26, 26, width - 26, height - 26), fill=(255, 255, 255, 200))
        
        return image

    def _get_menu(self):
        """
        Builds dynamic right-click context menu including Status Report and HUD control.
        """
        pause_label = "Resume Listening" if self.is_paused else "Pause Listening"
        status_header = f"{self.assistant_name}: {'PAUSED' if self.is_paused else 'LISTENING'}"

        menu_items = [
            item(status_header, lambda icon, item: None, enabled=False),
            pystray.Menu.SEPARATOR,
            item("Status Report", self._show_status),
            item(pause_label, self._toggle_pause)
        ]

        if self.on_toggle_hud:
            menu_items.append(item("Show/Hide HUD Window", self._hud_toggle_action))
        if self.on_toggle_dashboard:
            menu_items.append(item("Expand/Collapse Dashboard", self._dashboard_toggle_action))

        menu_items.append(pystray.Menu.SEPARATOR)
        menu_items.append(item("Quit Assistant", self._quit))

        return pystray.Menu(*menu_items)

    def _hud_toggle_action(self, icon=None, item=None):
        if self.on_toggle_hud:
            logger.info("HUD visibility toggled via System Tray menu.")
            self.on_toggle_hud()

    def _dashboard_toggle_action(self, icon=None, item=None):
        if self.on_toggle_dashboard:
            logger.info("HUD dashboard expanded/collapsed via System Tray menu.")
            self.on_toggle_dashboard()


    def _show_status(self, icon=None, item=None):
        """
        Displays a system status notification popup showing uptime, command history, and engine states.
        """
        if self.status_provider:
            try:
                info = self.status_provider()
            except Exception as e:
                logger.error(f"Error fetching status info: {e}")
                info = {}
        else:
            info = {}

        uptime_str = info.get("uptime", "Unknown")
        picovoice_status = info.get("picovoice", "Active")
        llm_status = info.get("llm", "Active")
        last_cmd = info.get("last_command", "None")
        last_resp = info.get("last_response", "None")

        status_msg = (
            f"Uptime: {uptime_str}\n"
            f"Picovoice Engine: {picovoice_status}\n"
            f"Gemini LLM: {llm_status}\n"
            f"Last Command: \"{last_cmd}\"\n"
            f"Last Response: \"{last_resp}\""
        )
        
        logger.info(f"[Status Request via Tray Menu]:\n{status_msg}")

        try:
            if self.icon:
                self.icon.notify(status_msg, title=f"{self.assistant_name} Status Report")
        except Exception as e:
            logger.warning(f"Failed to display tray notification: {e}")

    def _toggle_pause(self, icon=None, item=None):
        """
        Toggles assistant listening state.
        """
        self.is_paused = not self.is_paused
        status = "Paused" if self.is_paused else "Active"
        logger.info(f"Tray menu toggled listening status: {status}")
        
        if self.icon:
            self.icon.icon = self._create_image(paused=self.is_paused)
            self.icon.menu = self._get_menu()
            self.icon.title = f"{self.assistant_name} ({status})"

    def _quit(self, icon=None, item=None):
        """
        Terminates tray icon and triggers application exit callback.
        """
        logger.info("Quit requested via System Tray menu.")
        self.is_running = False
        if self.icon:
            self.icon.stop()
        if self.on_quit_callback:
            self.on_quit_callback()

    def start(self):
        """
        Launches system tray icon in a dedicated daemon thread.
        """
        def _run():
            image = self._create_image(paused=self.is_paused)
            self.icon = pystray.Icon(
                self.assistant_name,
                image,
                title=f"{self.assistant_name} (Active)",
                menu=self._get_menu()
            )
            self.icon.run()

        self.thread = threading.Thread(target=_run, daemon=True)
        self.thread.start()
        logger.info("System Tray Icon thread started.")

    def stop(self):
        """
        Stops tray icon execution.
        """
        self.is_running = False
        if self.icon:
            self.icon.stop()
