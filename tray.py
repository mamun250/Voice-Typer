import sys
import threading
from pathlib import Path
from PIL import Image
import pystray
from pystray import MenuItem as item, Menu
import sounddevice as sd
from config import load_config, save_config, LANGUAGES
import autostart

def get_asset_path(filename):
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / "assets" / filename
    return Path(__file__).parent / "assets" / filename

class TrayManager:
    def __init__(self, on_open_settings=None, on_open_phone_qr=None, on_settings_changed=None, on_exit=None):
        self.on_open_settings = on_open_settings
        self.on_open_phone_qr = on_open_phone_qr
        self.on_settings_changed = on_settings_changed
        self.on_exit = on_exit
        self.icon = None
        self.is_paused = False
        self._load_icon_image()

    def _load_icon_image(self):
        icon_path = get_asset_path("icon.png")
        if icon_path.exists():
            self.icon_image = Image.open(str(icon_path))
        else:
            self.icon_image = Image.new('RGB', (64, 64), color=(37, 99, 235))

    def _open_settings(self, icon, item):
        if self.on_open_settings:
            self.on_open_settings()

    def _open_phone_qr(self, icon, item):
        if self.on_open_phone_qr:
            self.on_open_phone_qr()

    def update_menu(self):
        if self.icon:
            self.icon.menu = self._build_menu()

    def _set_mic(self, mic_name):
        def _callback(icon, item):
            cfg = load_config()
            cfg["microphone_device"] = mic_name
            save_config(cfg)
            if self.on_settings_changed:
                self.on_settings_changed(cfg)
            self.update_menu()
        return _callback

    def _set_language(self, lang_code):
        def _callback(icon, item):
            cfg = load_config()
            cfg["language"] = lang_code
            save_config(cfg)
            if self.on_settings_changed:
                self.on_settings_changed(cfg)
            self.update_menu()
        return _callback

    def _set_hotkey(self, hotkey_name):
        def _callback(icon, item):
            cfg = load_config()
            cfg["primary_hotkey"] = hotkey_name
            if "Ctrl + Shift + Space" in hotkey_name:
                cfg["hotkeys"] = ["<ctrl>+<shift>+<space>", "<f8>"]
            elif "Ctrl + Alt + V" in hotkey_name:
                cfg["hotkeys"] = ["<ctrl>+<alt>+v", "<f8>"]
            else:
                cfg["hotkeys"] = ["<f8>", "<ctrl>+<shift>+<space>", "<ctrl>+<alt>+v"]
            save_config(cfg)
            if self.on_settings_changed:
                self.on_settings_changed(cfg)
            self.update_menu()
        return _callback

    def _toggle_beep(self, icon, item):
        cfg = load_config()
        cfg["beep_enabled"] = not cfg.get("beep_enabled", True)
        save_config(cfg)
        if self.on_settings_changed:
            self.on_settings_changed(cfg)
        self.update_menu()

    def _toggle_autostart(self, icon, item):
        cfg = load_config()
        curr_auto = autostart.is_autostart_enabled()
        if curr_auto:
            autostart.disable_autostart()
            cfg["autostart"] = False
        else:
            autostart.enable_autostart()
            cfg["autostart"] = True
        save_config(cfg)
        self.update_menu()

    def _toggle_pause(self, icon, item):
        self.is_paused = not self.is_paused
        if self.icon:
            self.update_menu()
            self.icon.title = "Voice Typer (Paused)" if self.is_paused else "Voice Typer (Active)"

    def _exit_app(self, icon, item):
        if self.icon:
            self.icon.stop()
        if self.on_exit:
            self.on_exit()

    def _build_menu(self):
        cfg = load_config()
        curr_mic = cfg.get("microphone_device", "")
        curr_lang = cfg.get("language", "auto")
        curr_hotkey = cfg.get("primary_hotkey", "F8 (Default)")
        beep_on = cfg.get("beep_enabled", True)
        auto_on = autostart.is_autostart_enabled()

        # 1. Unique Microphones sub-menu
        devices = sd.query_devices()
        seen = set()
        mic_items = []
        for idx, dev in enumerate(devices):
            if dev['max_input_channels'] > 0:
                name = dev['name']
                if name in seen:
                    continue
                seen.add(name)
                is_selected = (name == curr_mic) or (not curr_mic and idx == sd.default.device[0])
                label = f"{'✓ ' if is_selected else '   '}{name}"
                mic_items.append(item(label, self._set_mic(name)))

        # 2. Language sub-menu
        lang_items = []
        popular_langs = [
            ("auto", "Auto-detect (Universal)"),
            ("bn", "Bengali (বাংলা)"),
            ("en", "English"),
            ("hi", "Hindi (हिन्दी)"),
            ("ar", "Arabic (العربية)")
        ]
        for code, disp in popular_langs:
            is_selected = (code == curr_lang)
            label = f"{'✓ ' if is_selected else '   '}{disp}"
            lang_items.append(item(label, self._set_language(code)))
        lang_items.append(item("   Other Languages (Options...)", self._open_settings))

        # 3. Hotkey sub-menu
        hotkey_options = [
            "F8 (Default)",
            "Ctrl + Shift + Space",
            "Ctrl + Alt + V"
        ]
        hotkey_items = []
        for hk in hotkey_options:
            is_selected = (hk == curr_hotkey)
            label = f"{'✓ ' if is_selected else '   '}{hk}"
            hotkey_items.append(item(label, self._set_hotkey(hk)))

        # Native Windows Tray Menu (All English)
        menu = Menu(
            item("Options...", self._open_settings, default=True),
            item("📱 Connect Phone (QR Code)...", self._open_phone_qr),
            Menu.SEPARATOR,
            item("Microphone", Menu(*mic_items)),
            item("Language", Menu(*lang_items)),
            item("Hotkeys", Menu(*hotkey_items)),
            Menu.SEPARATOR,
            item(f"{'✓ ' if beep_on else '   '}Beep Notifications", self._toggle_beep),
            item(f"{'✓ ' if auto_on else '   '}Start with Windows", self._toggle_autostart),
            Menu.SEPARATOR,
            item("Resume" if self.is_paused else "Pause", self._toggle_pause),
            item("Exit", self._exit_app)
        )
        return menu

    def start(self):
        self.icon = pystray.Icon(
            name="VoiceTyper",
            icon=self.icon_image,
            title="Voice Typer (Active)",
            menu=self._build_menu()
        )
        self.icon.run_detached()

    def stop(self):
        if self.icon:
            self.icon.stop()
