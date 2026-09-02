# ECHO / JARVIS - Local Desktop AI Voice Assistant

A complete, local, background desktop AI voice assistant inspired by JARVIS/ECHO. Built for Windows with continuous wake-word detection, speech recognition, natural text-to-speech, system tray control, OS automation skills, and Windows Startup launch capability.

---

## ⚡ Important Requirements & Compatibility

> [!IMPORTANT]
> **Python Version Requirement**: Target **Python 3.11 or Python 3.12** (NOT Python 3.14).
> PyAudio and Picovoice Porcupine require prebuilt C-extension wheels that are available for Python 3.11/3.12 on Windows.

> [!TIP]
> **Windows PyAudio Installation**: If `pip install pyaudio` fails on your machine, install it using `pipwin`:
> ```bash
> pip install pipwin
> pipwin install pyaudio
> ```

---

## 🚀 Quick Setup Guide

### 1. Create Virtual Environment (Python 3.11 or 3.12)

Open PowerShell / CMD in the project folder (`d:\Friday AI`):

```powershell
# Create a dedicated virtual environment with Python 3.11 or 3.12
py -3.11 -m venv .venv

# Activate environment
.venv\Scripts\Activate.ps1
```

### 2. Install Dependencies

```powershell
# Upgrade pip and setuptools
python -m pip install --upgrade pip

# Install project requirements
pip install -r requirements.txt
```

*Note: If `PyAudio` installation throws a build error, run `pip install pipwin` followed by `pipwin install pyaudio`.*

---

## 🔑 Picovoice AccessKey & Wake Word Configuration

ECHO uses **Picovoice Porcupine** for zero-CPU offline wake-word detection.

### Getting a Free Picovoice AccessKey
1. Sign up for a free developer account at [https://console.picovoice.ai/](https://console.picovoice.ai/).
2. Copy your **AccessKey** from the dashboard.
3. Open `config.yaml` and paste your key:

```yaml
picovoice:
  access_key: "YOUR_PICOVOICE_ACCESS_KEY_HERE"
  wake_word: "jarvis"  # Built-in keywords: jarvis, computer, alexa, porcupine, bumblebee
```

### Using a Custom Wake Word ("friday")
> [!NOTE]
> "friday" is **NOT** a built-in keyword in Porcupine. The default wake word is set to `"jarvis"`.
> To use "friday" as your wake word:
> 1. Go to [Picovoice Console -> Porcupine](https://console.picovoice.ai/ppn).
> 2. Create a custom wake word phrase `"Friday"`, set platform to **Windows**, and download the `.ppn` model file.
> 3. Save the `.ppn` file in this folder (e.g. `friday_windows.ppn`).
> 4. In `config.yaml`, set:
>    ```yaml
>    custom_wake_word_path: "friday_windows.ppn"
>    ```

### ⚠️ No-API-Key Fallback Mode Warning
If you launch ECHO without setting a Picovoice AccessKey:
- The assistant falls back to continuous Speech-to-Text for wake-word detection.
- **WARNING**: Fallback mode is **CPU & Battery Heavy**! It is intended strictly for rapid initial testing without an API key, not for running continuously in the background.

---

## 🎮 Running ECHO

```powershell
python main.py
```

Upon launching:
1. ECHO will announce *"Systems operational, boss. Listening for wake word."*
2. A sleek AI core icon will appear in your **Windows System Tray** (notification area).
3. Say your wake word (*"Jarvis"* or custom wake word) to activate.
4. When ECHO responds (*"Yes, boss?"*), speak your command.

---

## 🗣️ Supported Voice Commands & Skills

| Command Spoken | Action Executed | Skill File |
| :--- | :--- | :--- |
| **"Open Chrome"** / **"Launch VSCode"** / **"Open Spotify"** | Launches target application (configured in `config.yaml`) | `skills/open_app.py` |
| **"What time is it?"** / **"What's today's date?"** | Spoken time or date | `core/router.py` |
| **"System status"** / **"Battery level"** / **"CPU usage"** | Reads CPU %, RAM utilization %, and battery status | `skills/system_info.py` |
| **"Search quantum computing on Google"** | Opens default web browser with search query | `skills/web_search.py` |
| **"Shut down the PC"** / **"Restart system"** / **"Sleep mode"** | Triggers confirmation prompt (*"Are you sure, boss?"*) before execution | `skills/power_control.py` |
| **"Who are you?"** | Identifies assistant name and persona | `core/router.py` |

---

## 📌 System Tray Controls

Look for the AI Core icon in your Windows Taskbar (near the clock):
- **Right-Click Menu Options**:
  - **Status Display**: Shows if listening is active or paused.
  - **Pause Listening / Resume Listening**: Temporarily stop wake word detection without quitting.
  - **Quit Assistant**: Safely shuts down audio streams and exits application.

---

## ⚙️ Registering Auto-Start on Windows Login

To make ECHO launch automatically in the background when you turn on or log into your Windows laptop:

```powershell
python scripts/setup_startup.py
```

This creates a silent VBScript launcher in your Windows Startup folder (`shell:startup`) that runs ECHO in windowless mode (`pythonw.exe main.py`).

To remove ECHO from Windows Startup:
```powershell
python scripts/setup_startup.py --uninstall
```

---

## 📋 Manual Test Checklist

Follow this checklist to verify your setup step-by-step:

- [ ] **1. Dependencies & Python Version**
  - Verify Python version: `python --version` (Should be 3.11.x or 3.12.x).
  - Verify PyAudio & Porcupine load without C-wheel errors.
- [ ] **2. Audio Output (TTS)**
  - Run `python main.py` and verify you hear *"Systems operational, boss."* out loud.
- [ ] **3. System Tray Presence**
  - Check the notification area in the Windows taskbar. You should see a glowing cyan AI core icon titled `ECHO (Active)`. Right-click and test **Pause Listening**.
- [ ] **4. Microphone & Wake Word**
  - Say **"Jarvis"** (or your wake word).
  - Verify ECHO responds out loud with *"Yes, boss?"* and logs the wake event.
- [ ] **5. Skill Execution**
  - Say **"System status"**. Verify ECHO reads back CPU, RAM, and battery stats.
  - Say **"Open Notepad"**. Verify Notepad opens on Windows.
  - Say **"Shut down the PC"**. Verify ECHO asks *"Are you sure you want to shut down the computer?"* for confirmation. Say **"Cancel"** or **"No"** to cancel safely.

---

## 🔮 Stretch Goals & Future Enhancements

1. **LLM Intent Classification**: Upgrade `core/router.py` from regex rule matching to local Ollama / OpenAI API calls for complex multi-step reasoning.
2. **Personal Routine Memory**: Add SQLite or JSON persistence (`skills/memory.py`) to remember user preferences, home layout, or schedule reminders.
3. **Iron Man Desktop HUD**: Replace the system tray icon with a transparent, frameless PyQt5/Electron arc-reactor overlay on screen.
