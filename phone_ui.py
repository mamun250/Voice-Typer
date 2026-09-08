import sys
import webbrowser
import tkinter as tk
from tkinter import ttk
from pathlib import Path
import qrcode
from PIL import Image, ImageTk
import pyperclip
from config import load_config, save_config

def get_asset_path(filename):
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / "assets" / filename
    return Path(__file__).parent / "assets" / filename

_active_phone_window = None

def show_phone_qr_window(parent=None, phone_server=None):
    global _active_phone_window
    if _active_phone_window is not None:
        try:
            if _active_phone_window.winfo_exists():
                _active_phone_window.deiconify()
                _active_phone_window.lift()
                _active_phone_window.focus_force()
                return _active_phone_window
        except Exception:
            _active_phone_window = None

    win = PhoneQRDialog(parent=parent, phone_server=phone_server)
    _active_phone_window = win
    return win

class PhoneQRDialog(tk.Toplevel):
    def __init__(self, parent=None, phone_server=None):
        super().__init__(parent)
        self.phone_server = phone_server
        self.http_url = phone_server.get_http_url() if phone_server else "http://localhost:8765"
        self.cloudflare_url = phone_server.get_tunnel_url() if phone_server else None

        self.mode_var = tk.StringVar(value="cloudflare")
        self.current_url = self.cloudflare_url if self.cloudflare_url else self.http_url
        self.is_tunnel_connecting = (self.cloudflare_url is None)

        self.title("Connect Phone as Microphone")
        self.geometry("490x670")
        self.resizable(False, False)

        # Center on screen
        self.update_idletasks()
        w, h = 490, 670
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

        self.style = ttk.Style(self)
        if 'vista' in self.style.theme_names():
            self.style.theme_use('vista')

        self._build_ui()

        # If Cloudflare tunnel not started yet, start it now!
        if self.phone_server:
            if not self.cloudflare_url:
                self.phone_server.start_tunnel(
                    on_url_ready=self._on_tunnel_url_ready,
                    on_status_change=self._on_tunnel_status_change
                )

    def _on_tunnel_url_ready(self, url):
        self.cloudflare_url = url
        self.is_tunnel_connecting = False
        self.after(0, self._apply_tunnel_url, url)

    def _apply_tunnel_url(self, url):
        if self.mode_var.get() == "cloudflare":
            self.current_url = url
            self.entry_url.configure(state="normal")
            self.entry_url.delete(0, "end")
            self.entry_url.insert(0, self.current_url)
            self.entry_url.configure(state="readonly")
            self._update_qr_image()
            self._update_guide_text()
            self.lbl_status.configure(text="🟢 Cloudflare HTTPS Active (Valid SSL)", foreground="#15803d")

    def _on_tunnel_status_change(self, status):
        def _update():
            if self.is_tunnel_connecting and self.mode_var.get() == "cloudflare":
                self.lbl_status.configure(text=f"⏳ {status}", foreground="#2563eb")
        self.after(0, _update)

    def _build_ui(self):
        container = ttk.Frame(self, padding=(18, 12, 18, 12))
        container.pack(fill="both", expand=True)

        # Header
        lbl_title = ttk.Label(
            container,
            text="📱 Use Phone as PC Microphone",
            font=("Segoe UI", 12, "bold")
        )
        lbl_title.pack(anchor="center", pady=(0, 2))

        lbl_subtitle = ttk.Label(
            container,
            text="Scan QR code with your phone camera to connect instantly.",
            font=("Segoe UI", 9),
            foreground="#555555"
        )
        lbl_subtitle.pack(anchor="center", pady=(0, 8))

        # Mode Selector Buttons
        mode_frame = ttk.Frame(container)
        mode_frame.pack(anchor="center", pady=(0, 10))

        self.btn_mode_cf = ttk.Button(
            mode_frame,
            text="⚡ Cloudflare HTTPS (Zero Warnings)",
            command=lambda: self._set_mode("cloudflare"),
            width=30
        )
        self.btn_mode_cf.pack(side="left", padx=(0, 6))

        self.btn_mode_wifi = ttk.Button(
            mode_frame,
            text="🌐 Local Wi-Fi (LAN)",
            command=lambda: self._set_mode("wifi"),
            width=20
        )
        self.btn_mode_wifi.pack(side="left")

        # Password setting box
        pwd_card = ttk.Frame(container)
        pwd_card.pack(anchor="center", fill="x", pady=(0, 8))

        pwd_row = ttk.Frame(pwd_card)
        pwd_row.pack(anchor="center")

        lbl_p = ttk.Label(pwd_row, text="🔒 PIN / Password:", font=("Segoe UI", 8, "bold"))
        lbl_p.pack(side="left", padx=(0, 6))

        self.entry_pwd = ttk.Entry(pwd_row, width=12, show="*")
        curr_pwd = self.phone_server.password if self.phone_server else ""
        self.entry_pwd.insert(0, curr_pwd)
        self.entry_pwd.pack(side="left", padx=(0, 4))

        self.btn_eye = ttk.Button(pwd_row, text="👁", width=3, command=self._toggle_pwd_visibility)
        self.btn_eye.pack(side="left", padx=(0, 4))

        btn_save_pwd = ttk.Button(pwd_row, text="Save PIN", width=9, command=self._save_password)
        btn_save_pwd.pack(side="left", padx=(0, 4))

        btn_clear_pwd = ttk.Button(pwd_row, text="Clear", width=6, command=self._clear_password)
        btn_clear_pwd.pack(side="left")

        # Password status label
        self.lbl_pwd_info = ttk.Label(
            pwd_card,
            text="🔒 Password Active (Phone must enter this PIN)" if curr_pwd else "🔓 Open Access (No password required)",
            font=("Segoe UI", 8),
            foreground="#b45309" if curr_pwd else "#15803d"
        )
        self.lbl_pwd_info.pack(anchor="center", pady=(3, 0))

        # QR Code Frame
        qr_frame = ttk.Frame(container, relief="solid", borderwidth=1)
        qr_frame.pack(anchor="center", pady=(0, 10))

        self.lbl_qr = ttk.Label(qr_frame)
        self.lbl_qr.pack(padx=6, pady=6)
        self._update_qr_image()

        # URL Box & Copy button
        url_row = ttk.Frame(container)
        url_row.pack(fill="x", pady=(0, 10))

        self.entry_url = ttk.Entry(url_row, font=("Segoe UI", 9))
        self.entry_url.insert(0, self.current_url)
        self.entry_url.configure(state="readonly")
        self.entry_url.pack(side="left", fill="x", expand=True, padx=(0, 6))

        btn_copy = ttk.Button(url_row, text="Copy Link", width=10, command=self._copy_link)
        btn_copy.pack(side="left")

        # Instructions card
        self.info_frame = ttk.LabelFrame(container, text=" Easy 3-Step Setup ", padding=(12, 8))
        self.info_frame.pack(fill="x", pady=(0, 10))

        self.lbl_guide = ttk.Label(self.info_frame, text="", font=("Segoe UI", 8), justify="left")
        self.lbl_guide.pack(anchor="w")
        self._update_guide_text()

        # Status & Bottom Buttons
        bottom_row = ttk.Frame(container)
        bottom_row.pack(fill="x", side="bottom")

        initial_status = "🟢 Cloudflare HTTPS Active (Valid SSL)" if self.cloudflare_url else "⏳ Connecting Cloudflare Secure Tunnel..."
        initial_color = "#15803d" if self.cloudflare_url else "#2563eb"
        self.lbl_status = ttk.Label(bottom_row, text=initial_status, foreground=initial_color, font=("Segoe UI", 8, "bold"))
        self.lbl_status.pack(side="left")

        btn_close = ttk.Button(bottom_row, text="Close", width=10, command=self.destroy)
        btn_close.pack(side="right", padx=(6, 0))

        btn_browser = ttk.Button(bottom_row, text="Open on PC", width=12, command=lambda: webbrowser.open(self.current_url))
        btn_browser.pack(side="right")

    def _toggle_pwd_visibility(self):
        if self.entry_pwd.cget("show") == "*":
            self.entry_pwd.configure(show="")
            self.btn_eye.configure(text="🔒")
        else:
            self.entry_pwd.configure(show="*")
            self.btn_eye.configure(text="👁")

    def _save_password(self):
        new_pwd = self.entry_pwd.get().strip()
        cfg = load_config()
        cfg["phone_password"] = new_pwd
        save_config(cfg)
        if self.phone_server:
            self.phone_server.set_password(new_pwd)

        if new_pwd:
            self.lbl_pwd_info.configure(
                text="🔒 Password Active! (Phone must enter this PIN)",
                foreground="#b45309"
            )
        else:
            self.lbl_pwd_info.configure(
                text="🔓 Open Access (No password required)",
                foreground="#15803d"
            )

    def _clear_password(self):
        self.entry_pwd.delete(0, "end")
        self._save_password()

    def _set_mode(self, mode):
        self.mode_var.set(mode)
        if mode == "cloudflare":
            if self.cloudflare_url:
                self.current_url = self.cloudflare_url
                self.lbl_status.configure(text="🟢 Cloudflare HTTPS Active (Valid SSL)", foreground="#15803d")
            else:
                self.current_url = self.http_url
                self.lbl_status.configure(text="⏳ Connecting Cloudflare Secure Tunnel...", foreground="#2563eb")
        else:
            self.current_url = self.http_url
            self.lbl_status.configure(text="🌐 Local Wi-Fi Active", foreground="#15803d")

        self.entry_url.configure(state="normal")
        self.entry_url.delete(0, "end")
        self.entry_url.insert(0, self.current_url)
        self.entry_url.configure(state="readonly")

        self._update_qr_image()
        self._update_guide_text()

    def _update_guide_text(self):
        if self.mode_var.get() == "cloudflare":
            guide = (
                "1. Scan this QR code with Phone Camera (Wi-Fi or Mobile Data).\n"
                "2. Page opens with valid HTTPS green lock—no scary warnings!\n"
                "3. Tap the red Mic button, allow microphone, and speak!"
            )
        else:
            guide = (
                "1. Connect Phone & PC to the same Wi-Fi network.\n"
                "2. Scan this QR code with Phone Camera (Opens instantly).\n"
                "3. Type manually or use keyboard dictation and tap 'Send to PC'!"
            )
        self.lbl_guide.configure(text=guide)

    def _update_qr_image(self):
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=6,
            border=2
        )
        qr.add_data(self.current_url)
        qr.make(fit=True)
        img_qr = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        img_qr = img_qr.resize((190, 190), Image.Resampling.LANCZOS)

        self.qr_photo = ImageTk.PhotoImage(img_qr)
        self.lbl_qr.configure(image=self.qr_photo)

    def _copy_link(self):
        pyperclip.copy(self.current_url)
        old_text = self.lbl_status.cget("text")
        old_color = self.lbl_status.cget("foreground")
        self.lbl_status.configure(text="✓ Link copied to clipboard!", foreground="#2563eb")
        self.after(2500, lambda: self.lbl_status.configure(text=old_text, foreground=old_color))
