import time
import ctypes
import unicodedata
import pyperclip

user32 = ctypes.windll.user32

VK_BACK = 0x08
VK_TAB = 0x09
VK_RETURN = 0x0D
VK_ESCAPE = 0x1B
VK_SPACE = 0x20
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
VK_DELETE = 0x2E
VK_CONTROL = 0x11
VK_V = 0x56

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002

EXTENDED_KEYS = {
    VK_LEFT,
    VK_UP,
    VK_RIGHT,
    VK_DOWN,
    VK_DELETE,
    0x2D,  # VK_INSERT
    0x24,  # VK_HOME
    0x23,  # VK_END
    0x21,  # VK_PRIOR (PageUp)
    0x22,  # VK_NEXT (PageDown)
}

KEY_MAP = {
    'left': VK_LEFT,
    'right': VK_RIGHT,
    'up': VK_UP,
    'down': VK_DOWN,
    'backspace': VK_BACK,
    'enter': VK_RETURN,
    'return': VK_RETURN,
    'delete': VK_DELETE,
    'tab': VK_TAB,
    'space': VK_SPACE,
    'escape': VK_ESCAPE,
}

def count_clusters(text: str) -> int:
    """
    Counts the number of visual grapheme clusters in a string.
    Combines base characters with dependent vowel signs (কার), virama (হসন্ত), 
    and diacritics according to Unicode standard.
    """
    if not text:
        return 0
    clusters = 0
    prev_virama = False
    for ch in text:
        cat = unicodedata.category(ch)
        is_mark = cat in ('Mn', 'Mc', 'Me')
        is_virama = (ch == '\u09CD')
        if is_mark or prev_virama:
            pass
        else:
            clusters += 1
        prev_virama = is_virama
    return clusters

def char_to_cluster_index(text: str, char_idx: int) -> int:
    """
    Converts a Unicode character offset into visual grapheme cluster offset.
    Windows arrow keys navigate by grapheme clusters in complex scripts (like Bengali).
    """
    if char_idx <= 0 or not text:
        return 0
    char_idx = min(char_idx, len(text))
    return count_clusters(text[:char_idx])

def press_key(vk_code: int):
    """Simulates a single key press and release with proper scan code and extended key flag."""
    is_ext = vk_code in EXTENDED_KEYS
    scan = user32.MapVirtualKeyW(vk_code, 0)
    flags_down = KEYEVENTF_EXTENDEDKEY if is_ext else 0
    flags_up = flags_down | KEYEVENTF_KEYUP
    user32.keybd_event(vk_code, scan, flags_down, 0)
    time.sleep(0.008)
    user32.keybd_event(vk_code, scan, flags_up, 0)

def send_key(key_name: str, count: int = 1):
    """
    Sends a named keypress count times.
    Uses hardware scan codes and KEYEVENTF_EXTENDEDKEY for arrows/navigation,
    completely preventing NumLock interference or number typing.
    Uses reliable 8-12ms timing so Windows input queues never drop keys.
    """
    vk = KEY_MAP.get(key_name.lower())
    if not vk:
        return
    count = max(1, min(int(count), 1000))
    is_ext = vk in EXTENDED_KEYS
    scan = user32.MapVirtualKeyW(vk, 0)
    flags_down = KEYEVENTF_EXTENDEDKEY if is_ext else 0
    flags_up = flags_down | KEYEVENTF_KEYUP
    delay = 0.008 if count > 6 else 0.012

    for _ in range(count):
        user32.keybd_event(vk, scan, flags_down, 0)
        time.sleep(delay)
        user32.keybd_event(vk, scan, flags_up, 0)
        time.sleep(delay)

def move_cursor_delta(delta: int):
    """
    Moves the PC cursor relative to current position.
    delta > 0 -> move right
    delta < 0 -> move left
    """
    if delta == 0:
        return
    key = 'right' if delta > 0 else 'left'
    send_key(key, count=abs(delta))

def paste_text(text: str):
    """
    Safely copies text to Windows clipboard and sends Ctrl+V 
    to the active window without losing cursor focus.
    """
    if not text:
        return

    try:
        pyperclip.copy(text)
    except Exception:
        return
    
    # Brief pause to let Windows clipboard settle
    time.sleep(0.04)

    # Simulate Ctrl + V
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_V, 0, 0, 0)
    time.sleep(0.02)
    user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.02)

def type_live_text(text: str):
    """Types text live into the focused window."""
    if not text:
        return
    paste_text(text)

def apply_text_diff(old_text: str, old_cursor: int, new_text: str, new_cursor: int):
    """
    Synchronizes the PC active window with the text and cursor state 
    of the mobile text box using cluster-aware minimal diffs.
    Returns (new_text, new_cursor).
    """
    # Guard: if both are empty, do nothing
    if not old_text and not new_text:
        return "", 0

    new_cursor = max(0, min(new_cursor, len(new_text)))
    old_cursor = max(0, min(old_cursor, len(old_text)))

    if new_text == old_text:
        delta_clusters = char_to_cluster_index(new_text, new_cursor) - char_to_cluster_index(old_text, old_cursor)
        if delta_clusters != 0:
            move_cursor_delta(delta_clusters)
        return new_text, new_cursor

    # 1. Compute common prefix
    min_len = min(len(old_text), len(new_text))
    prefix_len = 0
    while prefix_len < min_len and old_text[prefix_len] == new_text[prefix_len]:
        prefix_len += 1

    # 2. Compute common suffix
    suffix_len = 0
    while (suffix_len < (len(old_text) - prefix_len) and 
           suffix_len < (len(new_text) - prefix_len) and 
           old_text[len(old_text) - 1 - suffix_len] == new_text[len(new_text) - 1 - suffix_len]):
        suffix_len += 1

    del_count = len(old_text) - prefix_len - suffix_len
    ins_text = new_text[prefix_len : len(new_text) - suffix_len]

    # 3. Move cursor to right after the region to delete using cluster delta
    del_target_pos = len(old_text) - suffix_len
    target_cluster = char_to_cluster_index(old_text, del_target_pos)
    curr_cluster = char_to_cluster_index(old_text, old_cursor)
    delta_to_del = target_cluster - curr_cluster
    if delta_to_del != 0:
        move_cursor_delta(delta_to_del)

    # 4. Perform deletion (clusters)
    if del_count > 0:
        del_clusters = char_to_cluster_index(old_text, del_target_pos) - char_to_cluster_index(old_text, prefix_len)
        send_key('backspace', count=max(1, del_clusters))

    # 5. Insert new text if any (special keys directly sent without clipboard)
    if ins_text:
        if ins_text == '\n':
            send_key('enter')
        elif len(ins_text) == 1 and ins_text == ' ':
            send_key('space')
        else:
            paste_text(ins_text)

    # 6. Move cursor to final desired cursor position
    cursor_after_ins = prefix_len + len(ins_text)
    final_cluster = char_to_cluster_index(new_text, new_cursor)
    after_ins_cluster = char_to_cluster_index(new_text, cursor_after_ins)
    delta_to_final = final_cluster - after_ins_cluster
    if delta_to_final != 0:
        move_cursor_delta(delta_to_final)

    return new_text, new_cursor
