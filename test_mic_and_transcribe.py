import sys
import time
import numpy as np
import sounddevice as sd
from recorder import AudioRecorder
from transcriber import GeminiTranscriber, load_config
from app import get_input_device

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("=" * 60)
print("             VOICE INPUT TEST (ভয়েস ইনপুট টেস্ট)")
print("=" * 60)

cfg = load_config()
cfg_mic = cfg.get('microphone_device', None)
dev_idx, dev_name = get_input_device(cfg_mic)

print(f"[*] নির্বাচিত মাইক্রোফোন: [{dev_idx}] {dev_name}")
print("\n৩ সেকেন্ড পর রেকর্ডিং শুরু হবে। মাইকের কাছে এসে কথা বলুন...")

for i in [3, 2, 1]:
    print(f"  {i}...")
    time.sleep(1)

print("\n🎙️ [রেকর্ড হচ্ছে...] এখন বাংলা বা ইংরেজিতে কিছু বলুন (৪ সেকেন্ড)...")
rec = AudioRecorder(device=dev_idx)
rec.start()
time.sleep(4)
wav_bytes = rec.stop()
peak = rec.last_peak_amplitude

print(f"\n[✓] রেকর্ডিং শেষ। অডিও সাইজ: {len(wav_bytes)} বাইট | পিক ভলিউম লেভেল: {peak}")

if peak < 250:
    print(f"\n[⚠️ সতর্কবার্তা] আপনার মাইক থেকে কোনো আওয়াজ পাওয়া যায়নি (ভলিউম: {peak})!")
    print(f"  -> সম্ভবত আপনি অন্য মাইকে কথা বলছেন।")
    print(f"  -> আপনি কি 'Microphone (fifine AM8 Pro)' ব্যবহার করছেন?")
    print(f"  -> 'select_mic.bat' চালিয়ে সঠিক মাইকটি নির্বাচন করুন।")
else:
    print("\n⏳ গুগলে পাঠানো হচ্ছে ট্রান্সক্রিপশনের জন্য...")
    t = GeminiTranscriber()
    res = t.transcribe(wav_bytes)
    print("=" * 60)
    print(f"✍️ গুগল যা শুনেছে: \"{res}\"")
    print("=" * 60)
    if res:
        print("[✓] টেস্ট সফল! গুগল আপনার কণ্ঠ নিখুঁতভাবে বুঝতে পারছে।")
    else:
        print("[!] গুগল কোনো স্পষ্ট কথা শনাক্ত করতে পারেনি। একটু স্পষ্ট করে বলুন।")

print("\nএন্টার চাপলে উইন্ডো বন্ধ হবে...")
input()
