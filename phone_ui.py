import sys
import webbrowser
import tkinter as tk
from tkinter import ttk
from pathlib import Path
import qrcode
from PIL import Image, ImageTk
import pyperclip

def get_asset_path(filename):
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / "assets" / filename
    return Path(__file__).parent / "assets"

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
        self.https_url = phone_server.get_https_url() if phone_server else "https://localhost:8766"
        self.http_url = phone_server.get_http_url() if phone_server else "http://localhost:8765"
        self.mode_var = tk.StringVar(value="https")
        self.current_url = self.https_url

        self.title("Connect Phone as Microphone")
        self.geometry("460x600")
        self.resizable(False, False)

        # Center on screen
        self.update_idletasks()
        w, h = 460, 600
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
            text="Scan QR code with your phone camera on the same Wi-Fi.",
            font=("Segoe UI", 9),
            foreground="#555555"
        )
        lbl_subtitle.pack(anchor="center", pady=(0, 8))

        # Mode Selector Buttons
        mode_frame = ttk.Frame(container)
        mode_frame.pack(anchor="center", pady=(0, 10))

        self.btn_mode_https = ttk.Button(
            mode_frame,
            text="🔒 HTTPS Mode (Mic Permission)",
            command=lambda: self._set_mode("https"),
            width=26
        )
        self.btn_mode_https.pack(side="left", padx=(0, 6))

        self.btn_mode_http = ttk.Button(
            mode_frame,
            text="🌐 HTTP Mode (Fast / Direct)",
            command=lambda: self._set_mode("http"),
            width=24
        )
        self.btn_mode_http.pack(side="left")

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

        self.lbl_status = ttk.Label(bottom_row, text="🟢 Server Active on 192.168.0.177", foreground="#15803d", font=("Segoe UI", 8, "bold"))
        self.lbl_status.pack(side="left")

        btn_close = ttk.Button(bottom_row, text="Close", width=10, command=self.destroy)
        btn_close.pack(side="right", padx=(6, 0))

        btn_browser = ttk.Button(bottom_row, text="Open on PC", width=12, command=lambda: webbrowser.open(self.current_url))
        btn_browser.pack(side="right")

    def _set_mode(self, mode):
        self.mode_var.set(mode)
        if mode == "https":
            self.current_url = self.https_url
        else:
            self.current_url = self.http_url

        self.entry_url.configure(state="normal")
        self.entry_url.delete(0, "end")
        self.entry_url.insert(0, self.current_url)
        self.entry_url.configure(state="readonly")

        self._update_qr_image()
        self._update_guide_text()

    def _update_guide_text(self):
        if self.mode_var.get() == "https":
            guide = (
                "1. Connect Phone & PC to the same Wi-Fi.\n"
                "2. Scan this QR code with Phone Camera.\n"
                "3. Tap 'Tap to Speak' and allow Microphone permission!\n"
                "   (If prompted 'Connection not private', tap Advanced -> Proceed)"
            )
        else:
            guide = (
                "1. Connect Phone & PC to the same Wi-Fi.\n"
                "2. Scan this QR code with Phone Camera (Opens instantly!).\n"
                "3. Type or use phone keyboard mic & tap 'Send to PC'!"
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
        self.lbl_status.configure(text="✓ Link copied to clipboard!", foreground="#2563eb")
        self.after(2500, lambda: self.lbl_status.configure(text="🟢 Server Active on 192.168.0.177", foreground="#15803d"))
