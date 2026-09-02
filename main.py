import os
import sys
import time
import signal
import logging
import threading
from logging.handlers import RotatingFileHandler
import yaml
from dotenv import load_dotenv

from core.speaker import Speaker
from core.listener import Listener
from core.wake_word import WakeWordDetector
from core.router import CommandRouter
from tray.tray_icon import TrayIconManager
from gui.hud import HUDManager

def get_base_dir() -> str:
    """
    Returns base directory: directory of exe when frozen with PyInstaller,
    or directory of main.py when running standard python script.
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

# Pre-load .env from base directory, falling back to frozen bundle path if needed
env_path = os.path.join(get_base_dir(), ".env")
if not os.path.exists(env_path) and getattr(sys, 'frozen', False):
    fallback_env = os.path.join(getattr(sys, '_MEIPASS', get_base_dir()), ".env")
    if os.path.exists(fallback_env):
        env_path = fallback_env

load_dotenv(dotenv_path=env_path)

def setup_logging():
    """
    Sets up file and console logging under logs/friday_assistant.log
    with RotatingFileHandler (5MB max size, 3 backup files).
    Configures root logger so all child modules (core.listener, core.router,
    core.intent_classifier, gui.hud, tray.tray_icon) write to file and console.
    """
    log_dir = os.path.join(get_base_dir(), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "friday_assistant.log")

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    logger = logging.getLogger("ECHO_Main")
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers on re-init
    if not root_logger.handlers:
        # Rotating File Handler: 5MB per log file, max 3 backups
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding='utf-8'
        )
        file_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    return logger


def load_config():
    """
    Loads config.yaml settings file. Looks in executable directory first,
    falling back to frozen bundle directory if present.
    """
    base_dir = get_base_dir()
    config_path = os.path.join(base_dir, "config.yaml")
    if not os.path.exists(config_path) and getattr(sys, 'frozen', False):
        fallback_cfg = os.path.join(getattr(sys, '_MEIPASS', base_dir), "config.yaml")
        if os.path.exists(fallback_cfg):
            config_path = fallback_cfg

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file missing at: {config_path}")
    
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def validate_startup_environment(config, logger):
    """
    Performs comprehensive pre-flight startup checks:
    - Microphone presence and enumeration
    - App mappings configuration
    - Gemini API key existence check
    - Picovoice Access Key check
    """
    logger.info("Performing pre-flight startup validation checks...")

    # 1. Check Microphone Detection
    available_mics = Listener.get_available_microphones()
    if not available_mics:
        logger.critical("CRITICAL: No microphone or audio input device detected on this system!")
        print("\n" + "!" * 65)
        print(" ERROR: NO MICROPHONE DETECTED")
        print(" Please connect a working microphone and restart ECHO.")
        print("!" * 65 + "\n")
        raise RuntimeError("No microphone detected. Please connect an input device and restart.")

    active_mic_name = available_mics[0] if available_mics else "Default Microphone"
    logger.info(f"Microphone detected ({len(available_mics)} total devices available). Using: '{active_mic_name}'")

    # 2. Check Apps Mapping
    apps_mapped = config.get("apps", {})
    apps_count = len(apps_mapped)
    if apps_count == 0:
        logger.warning("[Startup Warning]: 'apps' section in config.yaml is empty!")

    # 3. Check Gemini API Key
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    gemini_ok = bool(gemini_key and gemini_key != "your_gemini_api_key_here")

    # 4. Check Picovoice Access Key
    pico_key = config.get("picovoice", {}).get("access_key", "").strip()
    picovoice_ok = bool(pico_key)

    # Print Clean Startup Summary Box
    print("\n" + "=" * 65)
    print("  ECHO AI ASSISTANT - STARTUP SYSTEM CHECK")
    print(f"  ✓ Microphone: DETECTED ('{active_mic_name}')")
    print(f"  ✓ Configured Apps: {apps_count} apps mapped in config.yaml")
    print(f"  {'✓' if gemini_ok else '⚠'} Gemini API Key: {'FOUND' if gemini_ok else 'MISSING (Personality Mode Offline)'}")
    print(f"  {'✓' if picovoice_ok else '⚠'} Picovoice Key: {'FOUND' if picovoice_ok else 'MISSING (STT Fallback Active)'}")
    print("  All core systems operational, boss.")
    print("=" * 65 + "\n")

    return {
        "gemini_ok": gemini_ok,
        "picovoice_ok": picovoice_ok,
        "apps_count": apps_count,
        "mic_name": active_mic_name
    }

def main():
    logger = setup_logging()
    logger.info("Initializing Desktop AI Voice Assistant...")

    start_time = time.time()
    config = load_config()

    assistant_name = config.get("assistant", {}).get("name", "ECHO")
    honorific = config.get("assistant", {}).get("user_honorific", "boss")
    
    conversation_config = config.get("conversation", {})
    follow_up_enabled = conversation_config.get("follow_up_enabled", True)
    follow_up_timeout = conversation_config.get("follow_up_timeout_seconds", 8)

    gui_enabled = config.get("gui", {}).get("enabled", True)

    # 1. Pre-flight validation
    val_status = validate_startup_environment(config, logger)

    # 2. Initialize core components
    speaker = Speaker(config)
    listener = Listener(config)
    router = CommandRouter(config, speaker=speaker)
    wake_detector = WakeWordDetector(config)

    # 3. Handle Gemini missing warning spoken notice ONCE at startup if key is missing
    if not val_status["gemini_ok"]:
        logger.warning("Spoken startup warning: Personality mode is offline, no Gemini key found.")
        speaker.speak(f"Personality mode is offline, {honorific}, no Gemini key found.", format_persona=False)

    # 4. Status Provider & Background Telemetry Updater Thread
    running = True

    cached_telemetry = {
        "uptime": "0m 0s",
        "picovoice": "Active (Porcupine)" if not wake_detector.fallback_mode else "STT Fallback Mode",
        "llm": "Active" if router.llm_brain.is_ready else "Offline (No API key)",
        "last_command": "None",
        "last_response": "None",
        "mic_name": val_status["mic_name"],
        "spotify_track": "Checking..."
    }
    telemetry_lock = threading.Lock()

    def update_telemetry_loop():
        logger.info("Background telemetry updater loop started.")
        while running:
            try:
                elapsed = int(time.time() - start_time)
                hours, remainder = divmod(elapsed, 3600)
                minutes, seconds = divmod(remainder, 60)
                uptime_str = f"{hours}h {minutes}m {seconds}s" if hours > 0 else f"{minutes}m {seconds}s"

                spotify_track = router.spotify_control.get_current_track() if hasattr(router, "spotify_control") else "Unavailable"

                with telemetry_lock:
                    cached_telemetry["uptime"] = uptime_str
                    cached_telemetry["picovoice"] = "Active (Porcupine)" if not wake_detector.fallback_mode else "STT Fallback Mode"
                    cached_telemetry["llm"] = "Active" if router.llm_brain.is_ready else "Offline (No API key)"
                    cached_telemetry["last_command"] = router.last_command
                    cached_telemetry["last_response"] = router.last_response
                    cached_telemetry["mic_name"] = val_status["mic_name"]
                    cached_telemetry["spotify_track"] = spotify_track
            except Exception as e:
                logger.error(f"Error in background telemetry updater loop: {e}")
            time.sleep(3)

    telemetry_thread = threading.Thread(target=update_telemetry_loop, daemon=True)
    telemetry_thread.start()

    def get_status_info() -> dict:
        with telemetry_lock:
            return cached_telemetry.copy()

    # 5. Initialize HUD Manager if enabled
    hud = None
    if gui_enabled:
        hud = HUDManager(config, status_provider=get_status_info)

    def shutdown_handler():
        nonlocal running
        running = False
        logger.info("Shutdown signal received. Exiting loops...")
        if hud:
            hud.stop()

    # 7. Initialize System Tray Icon with Status Provider & HUD Callbacks
    tray = TrayIconManager(
        assistant_name=assistant_name,
        on_quit_callback=shutdown_handler,
        status_provider=get_status_info,
        on_toggle_hud=hud.toggle_visibility if hud else None,
        on_toggle_dashboard=hud.toggle_expanded if hud else None
    )
    tray.start()

    # 8. Handle OS interrupt signals cleanly
    def handle_signal(sig, frame):
        shutdown_handler()
        tray.stop()
    
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Helper function for speaking with HUD state updates
    def speak_with_hud(text: str, format_persona: bool = True):
        if hud:
            hud.set_state("speaking")
        speaker.speak(text, format_persona=format_persona)
        if hud:
            hud.set_state("idle")

    # 9. Spoken startup message
    speak_with_hud(f"Systems operational, {honorific}. Listening for wake word.", format_persona=False)

    # 10. Background Voice Assistant Listening Loop
    def run_voice_loop():
        nonlocal running
        mic_error_spoken = False  # Throttles mic recovery message so it's spoken only once per outage

        logger.info("Background Voice Assistant loop started.")
        try:
            while running and tray.is_running:
                if tray.is_paused:
                    if hud:
                        hud.set_state("idle")
                    time.sleep(0.5)
                    continue

                try:
                    if hud:
                        hud.set_state("idle")

                    # Listen for wake word (blocks until trigger or shutdown signal)
                    wake_triggered = wake_detector.listen_for_wake_word(
                        stop_checker=lambda: not running or not tray.is_running or tray.is_paused
                    )

                    if wake_triggered and running and not tray.is_paused:
                        mic_error_spoken = False  # Reset mic error notice flag on success
                        logger.info("Wake word triggered! Prompting user for command...")
                        
                        if hud:
                            hud.set_state("listening")
                        
                        speak_with_hud(f"Yes, {honorific}?", format_persona=False)

                        if hud:
                            hud.set_state("listening")

                        # Capture initial spoken command
                        command = listener.listen()
                        if command:
                            logger.info(f"Captured command phrase: '{command}'")
                            if hud:
                                hud.set_state("speaking")
                            
                            response = router.route(command)
                            
                            if hud:
                                hud.update_interaction(command, response)
                            
                            speaker.speak(response)

                            # Continuous follow-up listening loop (no wake word needed)
                            while follow_up_enabled and running and not tray.is_paused:
                                if hud:
                                    hud.set_state("listening")
                                
                                logger.info(f"Follow-up listening active (timeout: {follow_up_timeout}s)...")
                                follow_up_command = listener.listen(timeout=follow_up_timeout)
                                if follow_up_command:
                                    logger.info(f"Captured follow-up command phrase: '{follow_up_command}'")
                                    if hud:
                                        hud.set_state("speaking")
                                    
                                    response = router.route(follow_up_command)
                                    
                                    if hud:
                                        hud.update_interaction(follow_up_command, response)
                                    
                                    speaker.speak(response)
                                else:
                                    logger.info("Follow-up window timed out with no speech. Returning to wake-word mode.")
                                    break

                        else:
                            speak_with_hud(f"I didn't hear anything, {honorific}.", format_persona=False)

                except KeyboardInterrupt:
                    break
                except Exception as loop_err:
                    logger.error(f"Audio stream/listening loop exception: {loop_err}", exc_info=True)
                    if not mic_error_spoken:
                        speak_with_hud(f"I'm having trouble hearing you, {honorific}, let me try again.", format_persona=False)
                        mic_error_spoken = True
                    time.sleep(1.0)  # Sleep briefly to avoid CPU thrashing on persistent error

        except Exception as fatal_err:
            logger.critical(f"Unhandled exception in background voice loop: {fatal_err}", exc_info=True)
        finally:
            logger.info("Background Voice loop terminating...")

    # 11. Launch Voice Assistant Loop in Dedicated Daemon Thread
    voice_thread = threading.Thread(target=run_voice_loop, daemon=True)
    voice_thread.start()

    # 12. Main Thread Event Loop Execution
    try:
        if hud:
            # Tkinter GUI event loop runs on Main Thread
            hud.start()
        else:
            # Fallback block if GUI is disabled
            while running and tray.is_running:
                time.sleep(0.5)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received.")
    except Exception as top_err:
        logger.critical(f"Unhandled top-level exception in main: {top_err}", exc_info=True)
    finally:
        logger.info("Cleaning up resources and shutting down...")
        shutdown_handler()
        wake_detector.cleanup()
        tray.stop()
        print(f"\n[{assistant_name}]: Systems offline. Good day, {honorific}.\n")

if __name__ == "__main__":
    main()
