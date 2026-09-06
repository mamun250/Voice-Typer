import os
import sys
import subprocess
from pathlib import Path

STARTUP_DIR = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
SHORTCUT_PATH = STARTUP_DIR / "VoiceTyper.lnk"

def is_autostart_enabled() -> bool:
    return SHORTCUT_PATH.exists()

def enable_autostart(target_path: str = None) -> bool:
    try:
        STARTUP_DIR.mkdir(parents=True, exist_ok=True)
        if target_path is None:
            if getattr(sys, 'frozen', False):
                target_path = sys.executable
                work_dir = str(Path(sys.executable).parent)
            else:
                base_dir = Path(__file__).parent.resolve()
                target_path = str(base_dir / "run.bat")
                work_dir = str(base_dir)
        else:
            work_dir = str(Path(target_path).parent)

        ps_script = f"""
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut('{str(SHORTCUT_PATH)}')
$Shortcut.TargetPath = '{target_path}'
$Shortcut.WorkingDirectory = '{work_dir}'
$Shortcut.Description = 'Universal Voice Typer'
$Shortcut.Save()
"""
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], check=True, capture_output=True)
        return True
    except Exception as e:
        print(f"Error enabling autostart: {e}")
        return False

def disable_autostart() -> bool:
    try:
        if SHORTCUT_PATH.exists():
            SHORTCUT_PATH.unlink()
        return True
    except Exception as e:
        print(f"Error disabling autostart: {e}")
        return False
