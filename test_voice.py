import sys
import time
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
from recorder import AudioRecorder
from transcriber import GeminiTranscriber
import sounddevice as sd

print('1. Audio Device:')
default_in = sd.query_devices(kind='input')
name = default_in.get('name', 'Unknown')
print(f'   Device: {name}')

t = GeminiTranscriber()
print(f'2. Transcriber Model: {t.model}')

print('3. Recording 3 seconds test...')
r = AudioRecorder()
r.start()
time.sleep(3)
wav_bytes = r.stop()
print(f'   Captured: {len(wav_bytes)} bytes')

if len(wav_bytes) > 2000:
    print('4. Sending to Gemini...')
    result = t.transcribe(wav_bytes)
    print(f'   Result: \"{result}\"')
print('Done!')
