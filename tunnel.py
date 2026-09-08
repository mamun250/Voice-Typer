import sys
import os
import re
import time
import logging
import threading
import subprocess
import urllib.request
from pathlib import Path

if getattr(sys, 'frozen', False):
    APP_DIR = Path(sys.executable).parent.resolve()
else:
    APP_DIR = Path(__file__).parent.resolve()

CLOUDFLARED_DOWNLOAD_URL = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"

def get_cloudflared_path() -> Path:
    """Finds the cloudflared.exe binary."""
    # 1. Check PyInstaller _MEIPASS
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        p = Path(sys._MEIPASS) / "assets" / "cloudflared.exe"
        if p.exists():
            return p
        p2 = Path(sys._MEIPASS) / "cloudflared.exe"
        if p2.exists():
            return p2

    # 2. Check APP_DIR / assets
    p = APP_DIR / "assets" / "cloudflared.exe"
    if p.exists():
        return p

    # 3. Check APP_DIR root
    p = APP_DIR / "cloudflared.exe"
    if p.exists():
        return p

    # 4. Check relative to this file
    p = Path(__file__).parent.resolve() / "assets" / "cloudflared.exe"
    if p.exists():
        return p

    return APP_DIR / "assets" / "cloudflared.exe"

def ensure_cloudflared(progress_callback=None) -> bool:
    """Ensures cloudflared.exe exists, downloading if necessary."""
    target = get_cloudflared_path()
    if target.exists() and target.stat().st_size > 25000000:
        return True

    target.parent.mkdir(parents=True, exist_ok=True)
    logging.info(f"Downloading cloudflared to {target}...")

    try:
        def _hook(blocknum, blocksize, totalsize):
            if totalsize > 0 and progress_callback:
                percent = int(blocknum * blocksize * 100 / totalsize)
                progress_callback(min(percent, 100))

        urllib.request.urlretrieve(CLOUDFLARED_DOWNLOAD_URL, str(target), _hook)
        logging.info("cloudflared downloaded successfully.")
        return True
    except Exception as e:
        logging.error(f"Failed to download cloudflared: {e}")
        return False


class TunnelManager:
    """Manages the Cloudflare Quick Tunnel subprocess."""
    def __init__(self, local_port=8765, on_url_ready=None, on_status_change=None):
        self.local_port = local_port
        self.on_url_ready = on_url_ready
        self.on_status_change = on_status_change
        self.process = None
        self.tunnel_url = None
        self.is_running = False
        self._thread = None
        self._lock = threading.Lock()

    def start(self):
        with self._lock:
            if self.is_running and self.process and self.process.poll() is None:
                if self.tunnel_url and self.on_url_ready:
                    self.on_url_ready(self.tunnel_url)
                return

            self.tunnel_url = None
            self.is_running = True

        self._thread = threading.Thread(target=self._run_tunnel, daemon=True)
        self._thread.start()

    def _update_status(self, status_text):
        logging.info(f"[Tunnel] {status_text}")
        if self.on_status_change:
            try:
                self.on_status_change(status_text)
            except Exception:
                pass

    def _run_tunnel(self):
        exe_path = get_cloudflared_path()
        if not exe_path.exists():
            self._update_status("Downloading secure tunnel engine...")
            if not ensure_cloudflared():
                self._update_status("Error: Cloudflare engine missing")
                self.is_running = False
                return

        self._update_status("Starting Cloudflare Secure Tunnel...")
        cmd = [
            str(exe_path),
            "tunnel",
            "--url",
            f"http://127.0.0.1:{self.local_port}"
        ]

        # Hide console window on Windows
        creationflags = 0
        if sys.platform == "win32":
            creationflags = 0x08000000  # CREATE_NO_WINDOW

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="ignore",
                creationflags=creationflags
            )
        except Exception as e:
            self._update_status(f"Tunnel start failed: {e}")
            self.is_running = False
            return

        # Read stderr for the tunnel URL
        url_found = False
        while self.is_running and self.process and self.process.poll() is None:
            line = self.process.stderr.readline()
            if not line:
                time.sleep(0.1)
                continue

            match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
            if match and not url_found:
                self.tunnel_url = match.group(0)
                url_found = True
                self._update_status(f"Connected: {self.tunnel_url}")
                if self.on_url_ready:
                    try:
                        self.on_url_ready(self.tunnel_url)
                    except Exception as e:
                        logging.error(f"Error in on_url_ready callback: {e}")

        self.is_running = False

    def stop(self):
        with self._lock:
            self.is_running = False
            if self.process:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=2)
                except Exception:
                    try:
                        self.process.kill()
                    except Exception:
                        pass
                self.process = None
            self.tunnel_url = None

    def get_url(self):
        return self.tunnel_url
