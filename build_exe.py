import os
import sys
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
ICON_PATH = BASE_DIR / "assets" / "icon.ico"

print("=" * 60)
print("      BUILDING NATIVE LIGHTWEIGHT VOICETYPER.EXE")
print("=" * 60)

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
    "--clean",
    "app.py"
]

print("Running command:")
print(" ".join(cmd))
print("\nCompiling standalone executable...\n")

subprocess.run(cmd, check=True)

dist_exe = BASE_DIR / "dist" / "VoiceTyper.exe"
if dist_exe.exists():
    print("=" * 60)
    print(f" [SUCCESS] Standalone EXE created successfully!")
    print(f" Location: {dist_exe}")
    print(f" File Size: {dist_exe.stat().st_size / (1024*1024):.2f} MB")
    print("=" * 60)
else:
    print(" [ERROR] Build failed or output file not found.")
