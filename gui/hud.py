import time
import math
import logging
import threading
import tkinter as tk
from tkinter import ttk
import psutil

logger = logging.getLogger(__name__)

class HUDState:
    """
    Thread-safe container tracking current assistant state, last command, and HUD visibility.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self.state = "idle"  # "idle", "listening", "speaking"
        self.last_command = "None"
        self.last_response = "None"
        self.visible = True
        self.expanded = False

    def set_state(self, state: str):
        with self._lock:
            self.state = state

    def update_interaction(self, command: str, response: str):
        with self._lock:
            if command:
                self.last_command = command
            if response:
                self.last_response = response

    def set_visible(self, visible: bool):
        with self._lock:
            self.visible = visible

    def set_expanded(self, expanded: bool):
        with self._lock:
            self.expanded = expanded

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "state": self.state,
                "last_command": self.last_command,
                "last_response": self.last_response,
                "visible": self.visible,
                "expanded": self.expanded
            }


class HUDWindow:
    """
    JARVIS-styled HUD visual overlay built with Tkinter.
    Provides a small floating draggable widget with animated blue arc-reactor,
    expandable into a full system telemetry dashboard.
    """
    def __init__(self, state_container: HUDState, config: dict, status_provider=None):
        self.state_container = state_container
        self.config = config
        self.status_provider = status_provider

        gui_cfg = config.get("gui", {})
        self.position_corner = gui_cfg.get("position", "bottom_right").lower()
        self.opacity = float(gui_cfg.get("opacity", 0.92))
        self.always_on_top = bool(gui_cfg.get("always_on_top", True))
        self.assistant_name = config.get("assistant", {}).get("name", "ECHO")

        self.root = tk.Tk()
        self.root.title(f"{self.assistant_name} HUD")
        
        # Configure window style (frameless, dark background, topmost, alpha)
        self.root.overrideredirect(True)
        if self.always_on_top:
            self.root.wm_attributes("-topmost", True)
        try:
            self.root.wm_attributes("-alpha", self.opacity)
        except Exception:
            pass  # Fallback for systems not supporting alpha channel

        self.bg_color = "#070b14"
        self.border_color = "#00f0ff"
        self.card_bg = "#0d1527"
        self.text_primary = "#e0f7ff"
        self.text_dim = "#5c88a3"
        self.accent_blue = "#00f0ff"
        self.accent_dark_blue = "#005588"
        self.accent_alert = "#00d2ff"

        self.root.configure(bg=self.bg_color)

        # Dragging mechanics
        self._drag_x = 0
        self._drag_y = 0

        # Animation variables
        self.angle = 0.0
        self.pulse_phase = 0.0

        # Dimensions
        self.small_width = 160
        self.small_height = 180
        self.large_width = 440
        self.large_height = 540

        self.current_is_expanded = False
        self.is_running = True

        # Build initial UI
        self._build_small_hud()
        self._position_window(self.small_width, self.small_height)

        # Telemetry update timer
        self.last_telemetry_check = 0.0
        self.cached_telemetry = {"cpu": "0%", "ram": "0%", "battery": "N/A", "spotify": "Checking..."}

        # Start animation loop (~30 FPS)
        self.root.after(33, self._animate_loop)

        # Handle window close cleanly
        self.root.protocol("WM_DELETE_WINDOW", self.hide)

    def _position_window(self, width: int, height: int):
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        margin = 30

        if self.position_corner == "top_left":
            x, y = margin, margin
        elif self.position_corner == "top_right":
            x, y = screen_w - width - margin, margin
        elif self.position_corner == "bottom_left":
            x, y = margin, screen_h - height - margin
        else:  # bottom_right (default)
            x, y = screen_w - width - margin, screen_h - height - margin

        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _start_drag(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_drag(self, event):
        x = self.root.winfo_x() + (event.x - self._drag_x)
        y = self.root.winfo_y() + (event.y - self._drag_y)
        self.root.geometry(f"+{x}+{y}")

    def _build_small_hud(self):
        # Clear existing widgets
        for widget in self.root.winfo_children():
            widget.destroy()

        self.container_frame = tk.Frame(self.root, bg=self.bg_color, highlightbackground=self.border_color, highlightthickness=1)
        self.container_frame.pack(fill=tk.BOTH, expand=True)

        # Bind mouse dragging
        self.container_frame.bind("<Button-1>", self._start_drag)
        self.container_frame.bind("<B1-Motion>", self._on_drag)

        # Arc Reactor Canvas
        self.canvas = tk.Canvas(
            self.container_frame,
            width=140,
            height=130,
            bg=self.bg_color,
            bd=0,
            highlightthickness=0
        )
        self.canvas.pack(padx=10, pady=(10, 0))
        self.canvas.bind("<Button-1>", self._on_canvas_click)

        # Status Label
        self.lbl_status = tk.Label(
            self.container_frame,
            text="ECHO • IDLE",
            font=("Segoe UI", 9, "bold"),
            fg=self.accent_blue,
            bg=self.bg_color
        )
        self.lbl_status.pack(pady=(2, 6))
        self.lbl_status.bind("<Button-1>", self._on_canvas_click)

    def _on_canvas_click(self, event):
        # If click was a static click (not drag start), toggle expansion
        snap = self.state_container.snapshot()
        self.toggle_expanded(not snap["expanded"])

    def _build_dashboard(self):
        for widget in self.root.winfo_children():
            widget.destroy()

        self.container_frame = tk.Frame(self.root, bg=self.bg_color, highlightbackground=self.border_color, highlightthickness=2)
        self.container_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # Header bar
        header = tk.Frame(self.container_frame, bg=self.card_bg, height=40)
        header.pack(fill=tk.X, side=tk.TOP)
        header.bind("<Button-1>", self._start_drag)
        header.bind("<B1-Motion>", self._on_drag)

        lbl_title = tk.Label(
            header,
            text=f"  ◈  {self.assistant_name} SYSTEM HUD  ◈",
            font=("Segoe UI", 10, "bold"),
            fg=self.accent_blue,
            bg=self.card_bg
        )
        lbl_title.pack(side=tk.LEFT, padx=10, pady=8)
        lbl_title.bind("<Button-1>", self._start_drag)
        lbl_title.bind("<B1-Motion>", self._on_drag)

        btn_collapse = tk.Button(
            header,
            text=" 🗕 Collapse ",
            font=("Segoe UI", 8, "bold"),
            fg=self.text_primary,
            bg="#162540",
            activebackground=self.accent_blue,
            activeforeground=self.bg_color,
            bd=0,
            relief=tk.FLAT,
            command=lambda: self.toggle_expanded(False)
        )
        btn_collapse.pack(side=tk.RIGHT, padx=10, pady=6)

        # Main Body Notebook / Content Area
        content = tk.Frame(self.container_frame, bg=self.bg_color, padx=15, pady=10)
        content.pack(fill=tk.BOTH, expand=True)

        # Top Visual Section: Arc Reactor + Core State Badge
        top_row = tk.Frame(content, bg=self.bg_color)
        top_row.pack(fill=tk.X, pady=(0, 10))

        self.canvas = tk.Canvas(
            top_row,
            width=130,
            height=130,
            bg=self.bg_color,
            bd=0,
            highlightthickness=0
        )
        self.canvas.pack(side=tk.LEFT, padx=(10, 20))

        state_box = tk.Frame(top_row, bg=self.card_bg, padx=15, pady=15, highlightbackground=self.accent_dark_blue, highlightthickness=1)
        state_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(state_box, text="SYSTEM STATUS", font=("Segoe UI", 8, "bold"), fg=self.text_dim, bg=self.card_bg).pack(anchor="w")
        self.lbl_dash_state = tk.Label(state_box, text="IDLE / WAITING", font=("Segoe UI", 12, "bold"), fg=self.accent_blue, bg=self.card_bg)
        self.lbl_dash_state.pack(anchor="w", pady=(4, 8))

        self.lbl_mic_info = tk.Label(state_box, text="Mic: Active Stream", font=("Segoe UI", 8), fg=self.text_primary, bg=self.card_bg)
        self.lbl_mic_info.pack(anchor="w")

        # Telemetry Card (CPU / RAM / Battery)
        telemetry_card = tk.Frame(content, bg=self.card_bg, padx=12, pady=10, highlightbackground=self.accent_dark_blue, highlightthickness=1)
        telemetry_card.pack(fill=tk.X, pady=5)

        tk.Label(telemetry_card, text="HARDWARE TELEMETRY", font=("Segoe UI", 8, "bold"), fg=self.text_dim, bg=self.card_bg).pack(anchor="w", pady=(0, 4))
        
        stats_frame = tk.Frame(telemetry_card, bg=self.card_bg)
        stats_frame.pack(fill=tk.X)

        self.lbl_cpu = tk.Label(stats_frame, text="CPU: 0%", font=("Segoe UI", 9, "bold"), fg=self.text_primary, bg=self.card_bg)
        self.lbl_cpu.pack(side=tk.LEFT, expand=True, anchor="w")

        self.lbl_ram = tk.Label(stats_frame, text="RAM: 0%", font=("Segoe UI", 9, "bold"), fg=self.text_primary, bg=self.card_bg)
        self.lbl_ram.pack(side=tk.LEFT, expand=True, anchor="w")

        self.lbl_battery = tk.Label(stats_frame, text="Battery: 100%", font=("Segoe UI", 9, "bold"), fg=self.text_primary, bg=self.card_bg)
        self.lbl_battery.pack(side=tk.LEFT, expand=True, anchor="w")

        # Media Card (Spotify Track)
        spotify_card = tk.Frame(content, bg=self.card_bg, padx=12, pady=10, highlightbackground=self.accent_dark_blue, highlightthickness=1)
        spotify_card.pack(fill=tk.X, pady=5)

        tk.Label(spotify_card, text="SPOTIFY PLAYBACK", font=("Segoe UI", 8, "bold"), fg=self.text_dim, bg=self.card_bg).pack(anchor="w", pady=(0, 2))
        self.lbl_spotify = tk.Label(spotify_card, text="Nothing playing", font=("Segoe UI", 9, "italic"), fg=self.accent_blue, bg=self.card_bg, anchor="w", justify="left")
        self.lbl_spotify.pack(fill=tk.X)

        # Last Interaction Card
        log_card = tk.Frame(content, bg=self.card_bg, padx=12, pady=10, highlightbackground=self.accent_dark_blue, highlightthickness=1)
        log_card.pack(fill=tk.BOTH, expand=True, pady=5)

        tk.Label(log_card, text="LAST COMMAND & RESPONSE", font=("Segoe UI", 8, "bold"), fg=self.text_dim, bg=self.card_bg).pack(anchor="w", pady=(0, 4))
        
        self.lbl_last_cmd = tk.Label(log_card, text="User: None", font=("Segoe UI", 9), fg=self.text_primary, bg=self.card_bg, anchor="w", wraplength=380, justify="left")
        self.lbl_last_cmd.pack(fill=tk.X, pady=(0, 4))

        self.lbl_last_resp = tk.Label(log_card, text="ECHO: Ready, boss.", font=("Segoe UI", 9), fg=self.accent_blue, bg=self.card_bg, anchor="w", wraplength=380, justify="left")
        self.lbl_last_resp.pack(fill=tk.X)

        # Footer Collapse Bar
        footer = tk.Frame(self.container_frame, bg=self.bg_color, pady=8)
        footer.pack(fill=tk.X, side=tk.BOTTOM)

        btn_close_hud = tk.Button(
            footer,
            text="Return to Floating HUD",
            font=("Segoe UI", 9, "bold"),
            fg=self.bg_color,
            bg=self.accent_blue,
            activebackground="#80f5ff",
            bd=0,
            relief=tk.FLAT,
            padx=20,
            pady=4,
            command=lambda: self.toggle_expanded(False)
        )
        btn_close_hud.pack(anchor="center")

    def toggle_expanded(self, expand: bool):
        self.state_container.set_expanded(expand)
        if expand != self.current_is_expanded:
            self.current_is_expanded = expand
            if expand:
                self._build_dashboard()
                self._position_window(self.large_width, self.large_height)
            else:
                self._build_small_hud()
                self._position_window(self.small_width, self.small_height)

    def _draw_arc_reactor(self, state: str):
        if not hasattr(self, 'canvas') or not self.canvas:
            return

        self.canvas.delete("all")
        w = int(self.canvas.cget("width"))
        h = int(self.canvas.cget("height"))
        cx, cy = w // 2, h // 2

        # Color & Speed presets based on state
        if state == "listening":
            base_color = "#00f0ff"
            glow_color = "#80f8ff"
            speed = 0.12
            pulse_speed = 0.15
            status_text = "LISTENING..."
        elif state == "speaking":
            base_color = "#00d2ff"
            glow_color = "#ffffff"
            speed = 0.18
            pulse_speed = 0.25
            status_text = "SPEAKING..."
        else:  # "idle"
            base_color = "#0077bb"
            glow_color = "#00f0ff"
            speed = 0.04
            pulse_speed = 0.05
            status_text = f"{self.assistant_name} • IDLE"

        self.angle += speed
        self.pulse_phase += pulse_speed

        # Calculate breathing pulse radius
        pulse_val = math.sin(self.pulse_phase)
        core_r = 18 + int(pulse_val * 4)

        # 1. Outer Tech Ring (ticks)
        outer_r = 48
        num_ticks = 12
        for i in range(num_ticks):
            a = self.angle + (i * (2 * math.pi / num_ticks))
            x1 = cx + (outer_r - 4) * math.cos(a)
            y1 = cy + (outer_r - 4) * math.sin(a)
            x2 = cx + (outer_r + 4) * math.cos(a)
            y2 = cy + (outer_r + 4) * math.sin(a)
            self.canvas.create_line(x1, y1, x2, y2, fill=base_color, width=2)

        # 2. Outer Circle
        self.canvas.create_oval(cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r, outline=base_color, width=2)

        # 3. Rotating Inner Concentric Arc Segments
        mid_r = 34
        arc_extent = 70
        deg1 = math.degrees(self.angle) % 360
        deg2 = (deg1 + 180) % 360
        self.canvas.create_arc(cx - mid_r, cy - mid_r, cx + mid_r, cy + mid_r, start=deg1, extent=arc_extent, style=tk.ARC, outline=glow_color, width=3)
        self.canvas.create_arc(cx - mid_r, cy - mid_r, cx + mid_r, cy + mid_r, start=deg2, extent=arc_extent, style=tk.ARC, outline=glow_color, width=3)

        # 4. Glowing Core
        self.canvas.create_oval(cx - core_r, cy - core_r, cx + core_r, cy + core_r, fill=base_color, outline=glow_color, width=2)
        inner_r = max(2, core_r - 8)
        self.canvas.create_oval(cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r, fill="#ffffff", outline="")

        if not self.current_is_expanded and hasattr(self, 'lbl_status'):
            self.lbl_status.config(text=status_text, fg=base_color)

    def _update_telemetry(self):
        now = time.time()
        if now - self.last_telemetry_check > 2.0:
            self.last_telemetry_check = now
            try:
                cpu = f"{psutil.cpu_percent()}%"
                ram = f"{psutil.virtual_memory().percent}%"
                battery_obj = psutil.sensors_battery()
                if battery_obj:
                    plug_str = "⚡" if battery_obj.power_plugged else "🔋"
                    bat = f"{int(battery_obj.percent)}% {plug_str}"
                else:
                    bat = "Desktop 🔌"
            except Exception:
                cpu, ram, bat = "N/A", "N/A", "N/A"

            spotify_str = "Checking..."
            if self.status_provider:
                try:
                    info = self.status_provider()
                    spotify_str = info.get("spotify_track", "Nothing playing")
                except Exception:
                    spotify_str = "Spotify Offline"

            self.cached_telemetry = {
                "cpu": cpu,
                "ram": ram,
                "battery": bat,
                "spotify": spotify_str
            }

    def _animate_loop(self):
        if not self.is_running:
            return

        try:
            snap = self.state_container.snapshot()

            # Handle visibility toggle from Tray or API
            if snap["visible"] and not self.root.winfo_viewable():
                self.root.deiconify()
            elif not snap["visible"] and self.root.winfo_viewable():
                self.root.withdraw()

            # Handle expand/collapse state changes triggered externally
            if snap["expanded"] != self.current_is_expanded:
                self.toggle_expanded(snap["expanded"])

            # Redraw animated Arc Reactor
            self._draw_arc_reactor(snap["state"])

            # Update Dashboard elements if expanded
            if self.current_is_expanded:
                self._update_telemetry()
                
                state_upper = snap["state"].upper()
                if hasattr(self, 'lbl_dash_state'):
                    self.lbl_dash_state.config(text=f"{state_upper} MODE")
                
                if hasattr(self, 'lbl_cpu'):
                    self.lbl_cpu.config(text=f"CPU: {self.cached_telemetry['cpu']}")
                    self.lbl_ram.config(text=f"RAM: {self.cached_telemetry['ram']}")
                    self.lbl_battery.config(text=f"Battery: {self.cached_telemetry['battery']}")
                    self.lbl_spotify.config(text=self.cached_telemetry['spotify'])

                if hasattr(self, 'lbl_last_cmd'):
                    self.lbl_last_cmd.config(text=f"User: \"{snap['last_command']}\"")
                    self.lbl_last_resp.config(text=f"{self.assistant_name}: \"{snap['last_response']}\"")

        except Exception as e:
            logger.error(f"Error in HUD animation loop: {e}")

        if self.is_running:
            self.root.after(33, self._animate_loop)

    def show(self):
        self.state_container.set_visible(True)
        self.root.deiconify()

    def hide(self):
        self.state_container.set_visible(False)
        self.root.withdraw()

    def close(self):
        self.is_running = False
        try:
            self.root.destroy()
        except Exception:
            pass


class HUDManager:
    """
    Manager interface running the HUD event loop and providing thread-safe state hooks.
    """
    def __init__(self, config: dict, status_provider=None):
        self.config = config
        self.status_provider = status_provider
        self.state_container = HUDState()
        self.window = None

    def start(self):
        """
        Initializes Tkinter window on current thread and starts event loop.
        """
        logger.info("Initializing HUD Visual Overlay...")
        self.window = HUDWindow(self.state_container, self.config, self.status_provider)
        self.window.root.mainloop()

    def set_state(self, state: str):
        self.state_container.set_state(state)

    def update_interaction(self, command: str, response: str):
        self.state_container.update_interaction(command, response)

    def toggle_visibility(self):
        snap = self.state_container.snapshot()
        self.state_container.set_visible(not snap["visible"])

    def toggle_expanded(self):
        snap = self.state_container.snapshot()
        self.state_container.set_expanded(not snap["expanded"])

    def stop(self):
        if self.window:
            self.window.close()
