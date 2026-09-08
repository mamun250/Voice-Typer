import sys
import time
import webbrowser
import threading
import sounddevice as sd
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from config import load_config, save_config, LANGUAGES
import autostart
from recorder import AudioRecorder
from transcriber import GeminiTranscriber

def get_asset_path(filename):
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / "assets" / filename
    return Path(__file__).parent / "assets" / filename

_active_options_window = None

def show_settings_window(parent=None, on_save_callback=None, on_open_phone_qr=None):
    global _active_options_window
    if _active_options_window is not None:
        try:
            if _active_options_window.winfo_exists():
                _active_options_window.deiconify()
                _active_options_window.lift()
                _active_options_window.focus_force()
                return _active_options_window
        except Exception:
            _active_options_window = None

    win = OptionsDialog(parent=parent, on_save_callback=on_save_callback, on_open_phone_qr=on_open_phone_qr)
    _active_options_window = win
    return win

class OptionsDialog(tk.Toplevel):
    def __init__(self, parent=None, on_save_callback=None, on_open_phone_qr=None):
        super().__init__(parent)
        self.on_save_callback = on_save_callback
        self.on_open_phone_qr = on_open_phone_qr
        self.config = load_config()

        self.title("Options")
        self.geometry("490x440")
        self.resizable(False, False)

        # Center on screen
        self.update_idletasks()
        w, h = 490, 440
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        self.lift()
        self.focus_force()

        icon_path = get_asset_path("icon.ico")
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except Exception:
                pass

        # Apply native Windows 'vista' theme
        self.style = ttk.Style(self)
        if 'vista' in self.style.theme_names():
            self.style.theme_use('vista')

        self._build_ui()
        self._load_values()

    def _build_ui(self):
        main_frame = ttk.Frame(self, padding=(10, 10, 10, 8))
        main_frame.pack(fill="both", expand=True)

        # Tabs (Notebook)
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill="both", expand=True, pady=(0, 10))

        # Tab 1: General
        self.tab_general = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(self.tab_general, text="General")
        self._build_general_tab()

        # Tab 2: Audio & Voice
        self.tab_audio = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(self.tab_audio, text="Audio")
        self._build_audio_tab()

        # Tab 3: Phone Link & Security
        self.tab_phone = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(self.tab_phone, text="Phone Link")
        self._build_phone_tab()

        # Tab 4: Hotkeys
        self.tab_hotkeys = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(self.tab_hotkeys, text="Hotkeys")
        self._build_hotkeys_tab()

        # Tab 5: API Key
        self.tab_api = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(self.tab_api, text="API Key")
        self._build_api_tab()

        # Bottom Button Row: [ OK ] [ Cancel ]
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x", side="bottom")

        btn_cancel = ttk.Button(btn_frame, text="Cancel", width=10, command=self.destroy)
        btn_cancel.pack(side="right", padx=(6, 0))

        btn_ok = ttk.Button(btn_frame, text="OK", width=10, command=self._save_and_close)
        btn_ok.pack(side="right")

    def _build_general_tab(self):
        # Checkboxes
        self.var_autostart = tk.BooleanVar()
        chk_autostart = ttk.Checkbutton(
            self.tab_general,
            text="Automatically start Voice Typer with Windows",
            variable=self.var_autostart
        )
        chk_autostart.pack(anchor="w", pady=(2, 6))

        self.var_beep = tk.BooleanVar()
        chk_beep = ttk.Checkbutton(
            self.tab_general,
            text="Play audio notifications (Beep sound on record/complete)",
            variable=self.var_beep
        )
        chk_beep.pack(anchor="w", pady=(0, 14))

        # Language selection
        lbl_lang = ttk.Label(self.tab_general, text="Language:")
        lbl_lang.pack(anchor="w", pady=(0, 4))

        self.lang_display_names = list(LANGUAGES.values())
        self.combo_lang = ttk.Combobox(
            self.tab_general,
            values=self.lang_display_names,
            state="readonly",
            width=42
        )
        self.combo_lang.pack(anchor="w", pady=(0, 8))
        self.combo_lang.bind("<<ComboboxSelected>>", self._on_language_changed)

        # Custom language entry (hidden unless custom selected)
        self.frame_custom = ttk.Frame(self.tab_general)
        lbl_c = ttk.Label(self.frame_custom, text="Custom language name (e.g. Russian, Italian):")
        lbl_c.pack(anchor="w")
        self.entry_custom_lang = ttk.Entry(self.frame_custom, width=35)
        self.entry_custom_lang.pack(anchor="w", pady=(2, 0))

    def _build_audio_tab(self):
        lbl_mic = ttk.Label(self.tab_audio, text="Microphone Device:")
        lbl_mic.pack(anchor="w", pady=(2, 4))

        mic_row = ttk.Frame(self.tab_audio)
        mic_row.pack(fill="x", pady=(0, 12))

        self.mic_devices = self._get_unique_microphones()
        mic_names = [name for _, name in self.mic_devices]
        self.combo_mic = ttk.Combobox(mic_row, values=mic_names, state="readonly", width=38)
        self.combo_mic.pack(side="left", padx=(0, 6))

        btn_refresh = ttk.Button(mic_row, text="Refresh", width=8, command=self._refresh_microphones)
        btn_refresh.pack(side="left")

        # Test Voice Section
        sep = ttk.Separator(self.tab_audio, orient="horizontal")
        sep.pack(fill="x", pady=(4, 10))

        lbl_test = ttk.Label(self.tab_audio, text="Test Microphone Input:")
        lbl_test.pack(anchor="w", pady=(0, 4))

        self.btn_test_voice = ttk.Button(
            self.tab_audio,
            text="Record 3 Seconds Test",
            command=self._start_voice_test
        )
        self.btn_test_voice.pack(anchor="w", pady=(0, 6))

        self.lbl_voice_status = ttk.Label(self.tab_audio, text="", wraplength=420)
        self.lbl_voice_status.pack(anchor="w")

        # Phone-as-Microphone section
        sep_phone = ttk.Separator(self.tab_audio, orient="horizontal")
        sep_phone.pack(fill="x", pady=(10, 8))

        lbl_phone = ttk.Label(self.tab_audio, text="No PC Microphone? Use Your Smartphone:", font=("Segoe UI", 9, "bold"))
        lbl_phone.pack(anchor="w", pady=(0, 4))

        btn_phone = ttk.Button(
            self.tab_audio,
            text="📱 Connect Phone as Microphone (QR Code)...",
            command=self._open_phone_qr
        )
        btn_phone.pack(anchor="w", pady=(0, 2))

    def _open_phone_qr(self):
        if self.on_open_phone_qr:
            self.on_open_phone_qr()

    def _build_phone_tab(self):
        lbl_title = ttk.Label(self.tab_phone, text="Connect Phone as Remote Microphone / Keyboard", font=("Segoe UI", 9, "bold"))
        lbl_title.pack(anchor="w", pady=(2, 6))

        lbl_desc = ttk.Label(
            self.tab_phone,
            text="Scan the QR code to speak via phone, type live into PC, and navigate cursor remotely.",
            wraplength=430,
            foreground="#555555"
        )
        lbl_desc.pack(anchor="w", pady=(0, 12))

        # Password Protection section
        lbl_pwd = ttk.Label(self.tab_phone, text="Phone Access Password (Optional):", font=("Segoe UI", 9, "bold"))
        lbl_pwd.pack(anchor="w", pady=(0, 4))

        lbl_pwd_info = ttk.Label(
            self.tab_phone,
            text="Set a PIN or password. If set, any device scanning the QR code or opening the link must enter this password to connect. Leave blank for open access.",
            wraplength=430,
            foreground="#666666"
        )
        lbl_pwd_info.pack(anchor="w", pady=(0, 6))

        pwd_row = ttk.Frame(self.tab_phone)
        pwd_row.pack(fill="x", pady=(0, 10))

        self.entry_phone_pwd = ttk.Entry(pwd_row, show="*", width=28)
        self.entry_phone_pwd.pack(side="left", padx=(0, 6))

        self.btn_show_pwd = ttk.Button(pwd_row, text="Show", width=6, command=self._toggle_pwd_visibility)
        self.btn_show_pwd.pack(side="left")

        sep = ttk.Separator(self.tab_phone, orient="horizontal")
        sep.pack(fill="x", pady=(8, 12))

        btn_qr = ttk.Button(
            self.tab_phone,
            text="📱 Open Phone QR Code & Connect Window...",
            command=self._open_phone_qr
        )
        btn_qr.pack(anchor="w")

    def _toggle_pwd_visibility(self):
        if self.entry_phone_pwd.cget("show") == "*":
            self.entry_phone_pwd.configure(show="")
            self.btn_show_pwd.configure(text="Hide")
        else:
            self.entry_phone_pwd.configure(show="*")
            self.btn_show_pwd.configure(text="Show")

    def _build_hotkeys_tab(self):
        lbl_hk = ttk.Label(self.tab_hotkeys, text="Voice Typing Shortcut:")
        lbl_hk.pack(anchor="w", pady=(4, 4))

        self.hotkey_options = [
            "F8 (Default)",
            "Ctrl + Shift + Space",
            "Ctrl + Alt + V",
            "F9",
            "F10"
        ]
        self.combo_hotkey = ttk.Combobox(
            self.tab_hotkeys,
            values=self.hotkey_options,
            state="readonly",
            width=30
        )
        self.combo_hotkey.pack(anchor="w", pady=(0, 12))

        lbl_info = ttk.Label(
            self.tab_hotkeys,
            text="Usage: Press the hotkey once to start speaking.\nPress it again when done to transcribe and auto-paste text.",
            foreground="#555555"
        )
        lbl_info.pack(anchor="w", pady=(4, 0))

    def _build_api_tab(self):
        lbl_api = ttk.Label(self.tab_api, text="Google Gemini API Key:")
        lbl_api.pack(anchor="w", pady=(2, 4))

        api_row = ttk.Frame(self.tab_api)
        api_row.pack(fill="x", pady=(0, 8))

        self.entry_api = ttk.Entry(api_row, show="*", width=38)
        self.entry_api.pack(side="left", padx=(0, 6))

        self.btn_show_key = ttk.Button(api_row, text="Show", width=6, command=self._toggle_key_visibility)
        self.btn_show_key.pack(side="left")

        btn_row = ttk.Frame(self.tab_api)
        btn_row.pack(anchor="w", pady=(0, 10))

        btn_get = ttk.Button(
            btn_row,
            text="Get Free API Key...",
            command=lambda: webbrowser.open("https://aistudio.google.com/app/apikey")
        )
        btn_get.pack(side="left", padx=(0, 6))

        self.btn_test_api = ttk.Button(btn_row, text="Test Connection", command=self._test_api_connection)
        self.btn_test_api.pack(side="left")

        self.lbl_api_status = ttk.Label(self.tab_api, text="", wraplength=420)
        self.lbl_api_status.pack(anchor="w")

    def _get_unique_microphones(self):
        devices = sd.query_devices()
        input_devs = []
        seen = set()
        for idx, dev in enumerate(devices):
            if dev['max_input_channels'] > 0:
                name = dev['name']
                if name not in seen:
                    seen.add(name)
                    input_devs.append((idx, name))
        return input_devs

    def _refresh_microphones(self):
        self.mic_devices = self._get_unique_microphones()
        mic_names = [name for _, name in self.mic_devices]
        self.combo_mic['values'] = mic_names
        if mic_names:
            self.combo_mic.set(mic_names[0])

    def _toggle_key_visibility(self):
        if self.entry_api.cget("show") == "*":
            self.entry_api.configure(show="")
            self.btn_show_key.configure(text="Hide")
        else:
            self.entry_api.configure(show="*")
            self.btn_show_key.configure(text="Show")

    def _on_language_changed(self, event=None):
        choice = self.combo_lang.get()
        if "Custom" in choice:
            self.frame_custom.pack(anchor="w", pady=(4, 0))
        else:
            self.frame_custom.pack_forget()

    def _load_values(self):
        # General tab
        self.var_autostart.set(autostart.is_autostart_enabled())
        self.var_beep.set(self.config.get("beep_enabled", True))

        saved_lang = self.config.get("language", "auto")
        disp_name = LANGUAGES.get(saved_lang, LANGUAGES["auto"])
        self.combo_lang.set(disp_name)
        if saved_lang == "custom":
            self.frame_custom.pack(anchor="w", pady=(4, 0))
            self.entry_custom_lang.delete(0, "end")
            self.entry_custom_lang.insert(0, self.config.get("custom_language", ""))
        else:
            self.frame_custom.pack_forget()

        # Audio tab
        saved_mic = self.config.get("microphone_device", None)
        mic_names = [name for _, name in self.mic_devices]
        if saved_mic and saved_mic in mic_names:
            self.combo_mic.set(saved_mic)
        elif mic_names:
            self.combo_mic.set(mic_names[0])

        # Hotkeys tab
        saved_hk = self.config.get("primary_hotkey", "F8 (Default)")
        self.combo_hotkey.set(saved_hk)

        # Phone tab
        self.entry_phone_pwd.delete(0, "end")
        self.entry_phone_pwd.insert(0, self.config.get("phone_password", ""))

        # API tab
        self.entry_api.delete(0, "end")
        self.entry_api.insert(0, self.config.get("gemini_api_key", ""))

    def _test_api_connection(self):
        api_key = self.entry_api.get().strip()
        if not api_key:
            self.lbl_api_status.configure(text="Please enter an API Key.", foreground="red")
            return

        self.lbl_api_status.configure(text="Testing connection...", foreground="#0284C7")
        self.btn_test_api.configure(state="disabled")

        def _test():
            import requests
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
                r = requests.get(url, timeout=6)
                if r.status_code == 200:
                    self.lbl_api_status.configure(text="Connection successful! API key is valid.", foreground="green")
                else:
                    self.lbl_api_status.configure(text=f"Failed (HTTP {r.status_code}): Invalid API key.", foreground="red")
            except Exception as e:
                self.lbl_api_status.configure(text=f"Connection error: {e}", foreground="red")
            finally:
                self.btn_test_api.configure(state="normal")

        threading.Thread(target=_test, daemon=True).start()

    def _start_voice_test(self):
        self.btn_test_voice.configure(state="disabled", text="Listening... Speak now...")
        self.lbl_voice_status.configure(text="", foreground="black")

        chosen_mic = self.combo_mic.get()
        dev_idx = None
        for idx, name in self.mic_devices:
            if name == chosen_mic:
                dev_idx = idx
                break

        def _run():
            try:
                rec = AudioRecorder(device=dev_idx)
                rec.start()
                time.sleep(3.0)
                wav_bytes = rec.stop()
                peak = rec.last_peak_amplitude

                if peak < 200:
                    self.lbl_voice_status.configure(
                        text=f"Audio level was very low (Peak: {peak}). Check microphone selection.",
                        foreground="#D97706"
                    )
                    return

                self.lbl_voice_status.configure(text="Transcribing with Gemini...", foreground="#0284C7")
                t = GeminiTranscriber()
                res = t.transcribe(wav_bytes)

                if res:
                    self.lbl_voice_status.configure(
                        text=f"Result: \"{res}\"",
                        foreground="green"
                    )
                else:
                    self.lbl_voice_status.configure(
                        text="No speech recognized. Please speak clearly into the mic.",
                        foreground="#D97706"
                    )
            except Exception as e:
                self.lbl_voice_status.configure(text=f"Error: {e}", foreground="red")
            finally:
                self.btn_test_voice.configure(state="normal", text="Record 3 Seconds Test")

        threading.Thread(target=_run, daemon=True).start()

    def _save_and_close(self):
        # 1. API Key
        self.config["gemini_api_key"] = self.entry_api.get().strip()

        # 2. Microphone
        self.config["microphone_device"] = self.combo_mic.get()

        # 3. Language
        selected_display = self.combo_lang.get()
        lang_code = "auto"
        for code, disp in LANGUAGES.items():
            if disp == selected_display:
                lang_code = code
                break
        self.config["language"] = lang_code
        self.config["custom_language"] = self.entry_custom_lang.get().strip()

        # 4. Hotkey
        hk_choice = self.combo_hotkey.get()
        self.config["primary_hotkey"] = hk_choice
        if "Ctrl + Shift + Space" in hk_choice:
            self.config["hotkeys"] = ["<ctrl>+<shift>+<space>", "<f8>"]
        elif "Ctrl + Alt + V" in hk_choice:
            self.config["hotkeys"] = ["<ctrl>+<alt>+v", "<f8>"]
        else:
            self.config["hotkeys"] = ["<f8>", "<ctrl>+<shift>+<space>", "<ctrl>+<alt>+v"]

        # 5. General preferences
        self.config["beep_enabled"] = bool(self.var_beep.get())

        want_autostart = bool(self.var_autostart.get())
        self.config["autostart"] = want_autostart
        if want_autostart:
            autostart.enable_autostart()
        else:
            autostart.disable_autostart()

        # 6. Phone password
        self.config["phone_password"] = self.entry_phone_pwd.get().strip()

        save_config(self.config)

        if self.on_save_callback:
            self.on_save_callback(self.config)

        self.destroy()

if __name__ == '__main__':
    root = tk.Tk()
    root.withdraw()
    show_settings_window(root)
    root.mainloop()
