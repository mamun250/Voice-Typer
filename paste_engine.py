import time
import ctypes
import pyperclip

user32 = ctypes.windll.user32
VK_CONTROL = 0x11
VK_V = 0x56
KEYEVENTF_KEYUP = 0x0002

def paste_text(text: str):
    """
    Safely copies text to Windows clipboard and sends Ctrl+V 
    to the active window without losing cursor focus.
    """
    if not text:
        return

    # Put text into clipboard
    pyperclip.copy(text)
    
    # Brief pause to let Windows clipboard settle
    time.sleep(0.05)

    # Simulate Ctrl + V
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_V, 0, 0, 0)
    time.sleep(0.03)
    user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
