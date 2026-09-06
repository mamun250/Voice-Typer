import json
import sounddevice as sd
from pathlib import Path

CONFIG_FILE = Path(__file__).parent / "config.json"

def main():
    print("=" * 55)
    print("       মাইক্রোফোন সিলেক্টর (Microphone Selector)")
    print("=" * 55)
    
    devices = sd.query_devices()
    input_devices = []
    
    for idx, dev in enumerate(devices):
        if dev['max_input_channels'] > 0:
            input_devices.append((idx, dev['name']))
            
    print("আপনার কম্পিউটারে পাওয়া মাইক্রোফোনসমূহ:\n")
    for num, (idx, name) in enumerate(input_devices, 1):
        print(f"  [{num}] {name} (Device ID: {idx})")
        
    print("\nআপনি বর্তমানে কোন মাইক্রোফোনটি দিয়ে কথা বলতে চান?")
    choice = input("নম্বর লিখুন (যেমন 1 বা 2): ").strip()
    
    try:
        selected_idx = int(choice) - 1
        if 0 <= selected_idx < len(input_devices):
            chosen_name = input_devices[selected_idx][1]
            print(f"\n[✓] আপনি বেছে নিয়েছেন: {chosen_name}")
            
            with open(CONFIG_FILE, "r", encoding="utf-8-sig") as f:
                cfg = json.load(f)
                
            cfg["microphone_device"] = chosen_name
            
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
                
            print("[✓] config.json সফলভাবে আপডেট হয়েছে!")
        else:
            print("[!] ভুল নম্বর দেওয়া হয়েছে।")
    except Exception as e:
        print(f"[!] সমস্যা হয়েছে: {e}")

if __name__ == '__main__':
    main()
