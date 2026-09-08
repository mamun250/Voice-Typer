import os
import sys
import shutil
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
ICON_PATH = BASE_DIR / "assets" / "icon.ico"

print("=" * 65)
print("     BUILDING NATIVE LIGHTWEIGHT VOICETYPER STANDALONE & SETUP")
print("=" * 65)

# Ensure no existing VoiceTyper instance is locking dist/VoiceTyper.exe
try:
    subprocess.run(["taskkill", "/f", "/im", "VoiceTyper.exe"], capture_output=True)
except Exception:
    pass

# Step 1: Build Standalone EXE using PyInstaller
cmd = [
    sys.executable,
    "-m", "PyInstaller",
    "--noconsole",
    "--onefile",
    f"--icon={str(ICON_PATH)}",
    "--name=VoiceTyper",
    f"--add-data={str(BASE_DIR / 'assets')};assets",
    "--collect-all=sounddevice",
    "--collect-all=pystray",
    "--collect-all=PIL",
    "--collect-all=qrcode",
    "--collect-all=cryptography",
    "--hidden-import=phone_server",
    "--hidden-import=phone_ui",
    "--hidden-import=tunnel",
    "--clean",
    "app.py"
]

print("\n[1/2] Compiling standalone executable with PyInstaller...")
subprocess.run(cmd, check=True)

dist_exe = BASE_DIR / "dist" / "VoiceTyper.exe"
if not dist_exe.exists():
    print(" [ERROR] PyInstaller build failed or VoiceTyper.exe not found.")
    sys.exit(1)

print(f" [SUCCESS] Standalone EXE created: {dist_exe.name} ({dist_exe.stat().st_size / (1024*1024):.2f} MB)")

# Step 2: Build Native Windows Installer (Setup.exe) using Inno Setup
print("\n[2/2] Building Windows Installer (VoiceTyper_Setup.exe) with Inno Setup...")

iscc_candidates = [
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
    Path(os.environ.get("ProgramFiles(x86)", "")) / "Inno Setup 6" / "ISCC.exe",
    Path(os.environ.get("ProgramFiles", "")) / "Inno Setup 6" / "ISCC.exe",
    Path(shutil.which("ISCC.exe") or "")
]

iscc_path = None
for candidate in iscc_candidates:
    if candidate and candidate.exists() and candidate.is_file():
        iscc_path = candidate
        break

if iscc_path:
    print(f" Found Inno Setup compiler: {iscc_path}")
    iss_file = BASE_DIR / "installer.iss"
    try:
        subprocess.run([str(iscc_path), str(iss_file)], check=True)
        setup_exe = BASE_DIR / "dist" / "VoiceTyper_Setup.exe"
        if setup_exe.exists():
            print(f" [SUCCESS] Native Windows Setup created: {setup_exe.name} ({setup_exe.stat().st_size / (1024*1024):.2f} MB)")
    except Exception as e:
        print(f" [WARNING] Inno Setup compilation failed: {e}")
else:
    print(" [NOTICE] Inno Setup (ISCC.exe) not found on system. VoiceTyper.exe is ready in dist/.")

print("\n" + "=" * 65)
print("                      BUILD COMPLETE!")
print(f"  • Standalone Portable EXE : dist/VoiceTyper.exe")
if (BASE_DIR / "dist" / "VoiceTyper_Setup.exe").exists():
    print(f"  • Windows Native Installer: dist/VoiceTyper_Setup.exe")
print("=" * 65)
