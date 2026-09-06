import sys
import time
import numpy as np
import sounddevice as sd
from pynput import keyboard

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print('=' * 60)
print('          VOICE TYPER DIAGNOSTIC TOOL')
print('=' * 60)

# 1. Check audio devices
input_devices = []
for idx, dev in enumerate(sd.query_devices()):
    if dev['max_input_channels'] > 0:
        input_devices.append((idx, dev['name']))

print('Found Microphones:')
for idx, name in input_devices:
    default_mark = ' [DEFAULT]' if idx == sd.default.device[0] else ''
    print(f'  [{idx}] {name}{default_mark}')

print('\n' + '=' * 60)
print('Step 1: Testing Key Detection. Press F8 or any key now!')
print('(Press ESC when done with key testing)')
print('=' * 60)

def on_press(key):
    try:
        key_str = key.name if hasattr(key, 'name') else key.char
    except Exception:
        key_str = str(key)
    print(f'  -> Key Pressed: [{key_str}] (Raw: {key})')
    if key == keyboard.Key.esc:
        return False

with keyboard.Listener(on_press=on_press) as listener:
    listener.join()

print('\nKey test finished.')
