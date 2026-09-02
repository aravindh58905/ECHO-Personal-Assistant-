import os
import sys
import argparse
import subprocess

def get_startup_folder() -> str:
    """
    Returns absolute path to current user's Windows Startup folder.
    """
    appdata = os.getenv('APPDATA')
    if not appdata:
        raise EnvironmentError("APPDATA environment variable not found.")
    return os.path.join(appdata, 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')

def install_startup():
    """
    Creates a VBScript launcher in Windows Startup folder to run ECHO silently in background on log in.
    Supports both packaged executable (dist/friday/friday.exe) and Python source execution.
    """
    startup_dir = get_startup_folder()
    project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    vbs_path = os.path.join(startup_dir, 'FridayAssistantLauncher.vbs')

    # Check for packaged executable locations
    dist_exe = os.path.join(project_dir, 'dist', 'friday', 'friday.exe')
    root_exe = os.path.join(project_dir, 'friday.exe')

    if os.path.exists(dist_exe):
        exe_path = os.path.abspath(dist_exe)
        working_dir = os.path.dirname(exe_path)
        vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "{working_dir}"
WshShell.Run """{exe_path}""", 0, False
'''
        target_name = f"Packaged Executable ({exe_path})"

    elif os.path.exists(root_exe):
        exe_path = os.path.abspath(root_exe)
        working_dir = os.path.dirname(exe_path)
        vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "{working_dir}"
WshShell.Run """{exe_path}""", 0, False
'''
        target_name = f"Executable ({exe_path})"

    else:
        # Fallback to pythonw.exe main.py
        main_script = os.path.join(project_dir, 'main.py')
        python_dir = os.path.dirname(sys.executable)
        pythonw_exe = os.path.join(python_dir, 'pythonw.exe')
        if not os.path.exists(pythonw_exe):
            pythonw_exe = sys.executable

        vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "{project_dir}"
WshShell.Run """{pythonw_exe}""" "{main_script}"", 0, False
'''
        target_name = f"Python Script ({main_script})"
        working_dir = project_dir

    try:
        with open(vbs_path, 'w', encoding='utf-8') as f:
            f.write(vbs_content)
        print("\n" + "=" * 60)
        print(" [SUCCESS] Registered ECHO in Windows Startup!")
        print(f" Target: {target_name}")
        print(f" Launcher VBS created at:\n {vbs_path}")
        print(f" Working Directory: {working_dir}")
        print(" ECHO will now launch silently in background whenever you log into Windows.")
        print("=" * 60 + "\n")
    except Exception as e:
        print(f"[ERROR] Failed to write startup file: {e}")

def uninstall_startup():
    """
    Removes VBScript launcher from Windows Startup folder.
    """
    startup_dir = get_startup_folder()
    vbs_path = os.path.join(startup_dir, 'FridayAssistantLauncher.vbs')
    
    if os.path.exists(vbs_path):
        try:
            os.remove(vbs_path)
            print(f"[SUCCESS] Removed ECHO from Windows Startup: {vbs_path}")
        except Exception as e:
            print(f"[ERROR] Failed to remove startup launcher: {e}")
    else:
        print("ECHO is not registered in Windows Startup folder.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Windows Startup installer for ECHO AI Assistant")
    parser.add_argument('--uninstall', action='store_true', help="Remove ECHO from Windows Startup")
    args = parser.parse_args()

    if args.uninstall:
        uninstall_startup()
    else:
        install_startup()
