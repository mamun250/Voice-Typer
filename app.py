import sys
import os
import io
import time
import threading
import logging
from pathlib import Path
import sounddevice as sd
from pynput import keyboard
import tkinter as tk

# Ensure UTF-8 output
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

if getattr(sys, 'frozen', False):
    APP_DIR = Path(sys.executable).parent.resolve()
else:
    APP_DIR = Path(__file__).parent.resolve()

LOG_FILE = APP_DIR / 'voice_typer.log'

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    encoding='utf-8'
)

from config import load_config, save_config
from recorder import (
    AudioRecorder,
    play_record_start_sound,
    play_record_stop_sound,
    play_paste_success_sound,
    play_startup_chime
)
from transcriber import GeminiTranscriber
from paste_engine import paste_text, type_live_text, move_cursor_delta, send_key, apply_text_diff
from tray import TrayManager
from settings_ui import show_settings_window
from phone_server import PhoneServer
from phone_ui import show_phone_qr_window
import ctypes

user32 = ctypes.windll.user32

STATE_IDLE = 'IDLE'
STATE_RECORDING = 'RECORDING'
STATE_PROCESSING = 'PROCESSING'

def resolve_input_device(mic_name):
    devices = sd.query_devices()
    default_idx = sd.default.device[0]
    if mic_name:
        for idx, dev in enumerate(devices):
            if dev['max_input_channels'] > 0:
                if mic_name.lower() in dev['name'].lower():
                    return idx, dev['name']
    name = devices[default_idx]['name'] if default_idx >= 0 else 'Default Mic'
    return default_idx, name

class VoiceTyperApp:
    def __init__(self):
        self.config = load_config()
        self.transcriber = GeminiTranscriber()
        self.state = STATE_IDLE
        self._lock = threading.Lock()
        self.last_toggle_time = 0
        self.hotkey_listener = None

        self.root = tk.Tk()
        self.root.withdraw()

        self._apply_config(self.config)

        self.synced_text = ""
        self.synced_cursor = 0

        # Phone Server for Phone-as-Mic
        self.phone_server = PhoneServer(
            http_port=8765,
            https_port=8766,
            on_paste_text=self._on_phone_paste_text,
            on_special_key=self._on_phone_special_key,
            on_transcribe_audio=self._on_phone_transcribe_audio,
            on_play_sound=self._on_phone_play_sound,
            on_live_input=self._on_phone_live_input,
            on_move_cursor=self._on_phone_move_cursor,
            on_sync_text=self._on_phone_sync_text,
            on_reset_sync=self._on_phone_reset_sync,
            password=self.config.get("phone_password", "")
        )
        self.phone_server.start()

        self.tray = TrayManager(
            on_open_settings=self.open_settings,
            on_open_phone_qr=self.open_phone_qr,
            on_settings_changed=self.on_settings_changed,
            on_exit=self.stop
        )

    def _apply_config(self, cfg):
        self.config = cfg
        self.beep_enabled = cfg.get("beep_enabled", True)
        self.device_idx, self.device_name = resolve_input_device(cfg.get("microphone_device"))
        
        self.recorder = AudioRecorder(
            sample_rate=cfg.get("sample_rate", 16000),
            channels=cfg.get("channels", 1),
            device=self.device_idx
        )
        self.hotkeys = cfg.get("hotkeys", ["<f8>", "<ctrl>+<shift>+<space>", "<ctrl>+<alt>+v"])

    def open_settings(self):
        self.root.after(0, self._show_settings_on_main_thread)

    def _show_settings_on_main_thread(self):
        show_settings_window(
            parent=self.root,
            on_save_callback=self.on_settings_changed,
            on_open_phone_qr=self.open_phone_qr
        )

    def open_phone_qr(self):
        self.root.after(0, self._show_phone_qr_on_main_thread)

    def _show_phone_qr_on_main_thread(self):
        show_phone_qr_window(parent=self.root, phone_server=self.phone_server)

    def _on_phone_reset_sync(self):
        self.synced_text = ""
        self.synced_cursor = 0
        logging.info("[Phone] Synced text state reset.")

    def _on_phone_paste_text(self, text: str):
        if self.tray.is_paused or not text:
            return
        logging.info(f"[Phone] Received text: '{text}'")
        paste_text(text)
        self.synced_text = ""
        self.synced_cursor = 0
        if self.beep_enabled:
            play_paste_success_sound()

    def _on_phone_sync_text(self, text: str, cursor: int):
        if self.tray.is_paused:
            return
        self.synced_text, self.synced_cursor = apply_text_diff(
            self.synced_text,
            self.synced_cursor,
            text,
            cursor
        )

    def _on_phone_live_input(self, text: str):
        if self.tray.is_paused or not text:
            return
        type_live_text(text)

    def _on_phone_move_cursor(self, delta: int):
        if self.tray.is_paused or delta == 0:
            return
        move_cursor_delta(delta)

    def _on_phone_special_key(self, key: str, count: int = 1):
        if self.tray.is_paused:
            return
        send_key(key, count=count)

    def _on_phone_transcribe_audio(self, audio_bytes: bytes, mime_type: str) -> str:
        if self.tray.is_paused or not audio_bytes:
            return ""
        if self.beep_enabled:
            play_record_stop_sound()
        logging.info(f"[Phone] Transcribing {len(audio_bytes)} bytes ({mime_type})...")
        text = self.transcriber.transcribe(audio_bytes, mime_type=mime_type)
        if text:
            logging.info(f"[Phone] Transcribed: '{text}'")
            paste_text(text)
            if self.beep_enabled:
                play_paste_success_sound()
        return text

    def _on_phone_play_sound(self, sound_name: str):
        if not self.beep_enabled or self.tray.is_paused:
            return
        if sound_name == 'start':
            play_record_start_sound()
        elif sound_name == 'stop':
            play_record_stop_sound()
        elif sound_name == 'success':
            play_paste_success_sound()

    def on_settings_changed(self, new_cfg):
        logging.info("Settings updated by user.")
        self._apply_config(new_cfg)
        if hasattr(self, 'phone_server') and self.phone_server:
            self.phone_server.set_password(new_cfg.get("phone_password", ""))
        self._restart_hotkey_listener()
        self.tray.update_menu()

    def toggle(self):
        if self.tray.is_paused:
            return

        now = time.time()
        if now - self.last_toggle_time < 0.35:
            return
        self.last_toggle_time = now

        if self.state == STATE_IDLE:
            self._start_recording()
        elif self.state == STATE_RECORDING:
            self._stop_and_transcribe()

    def _start_recording(self):
        with self._lock:
            if self.state != STATE_IDLE:
                return
            self.state = STATE_RECORDING

        if self.beep_enabled:
            play_record_start_sound()

        self.recorder.start()
        logging.info(f"Recording started on: {self.device_name}")

    def _stop_and_transcribe(self):
        with self._lock:
            if self.state != STATE_RECORDING:
                return
            self.state = STATE_PROCESSING

        start_time = time.time()
        if self.beep_enabled:
            play_record_stop_sound()

        logging.info("Recording stopped. Sending to Gemini...")

        def _worker():
            try:
                wav_bytes = self.recorder.stop()
                if not wav_bytes or len(wav_bytes) < 1000:
                    return

                text = self.transcriber.transcribe(wav_bytes)
                elapsed = time.time() - start_time
                logging.info(f"Transcribed ({elapsed:.2f}s): '{text}'")

                if text:
                    paste_text(text)
                    if self.beep_enabled:
                        play_paste_success_sound()
            except Exception as e:
                logging.error(f"Transcription error: {e}", exc_info=True)
            finally:
                with self._lock:
                    self.state = STATE_IDLE

        threading.Thread(target=_worker, daemon=True).start()

    def _start_hotkey_listener(self):
        bindings = {hk: self.toggle for hk in self.hotkeys}
        try:
            self.hotkey_listener = keyboard.GlobalHotKeys(bindings)
            self.hotkey_listener.start()
            logging.info(f"GlobalHotKeys listening on: {list(bindings.keys())}")
        except Exception as e:
            logging.error(f"Failed to start hotkey listener: {e}", exc_info=True)

    def _restart_hotkey_listener(self):
        if self.hotkey_listener:
            try:
                self.hotkey_listener.stop()
            except Exception:
                pass
        self._start_hotkey_listener()

    def run(self):
        play_startup_chime()
        self._start_hotkey_listener()
        self.tray.start()
        logging.info("Voice Typer running with System Tray and Startup Sound.")

        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        if self.hotkey_listener:
            try:
                self.hotkey_listener.stop()
            except Exception:
                pass
        if hasattr(self, 'phone_server') and self.phone_server:
            try:
                self.phone_server.stop()
            except Exception:
                pass
        if self.tray:
            self.tray.stop()
        try:
            self.root.quit()
        except Exception:
            pass
        os._exit(0)

if __name__ == '__main__':
    app = VoiceTyperApp()
    app.run()
