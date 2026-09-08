import os
import sys
import json
from pathlib import Path

if getattr(sys, 'frozen', False):
    APP_DIR = Path(sys.executable).parent.resolve()
else:
    APP_DIR = Path(__file__).parent.resolve()

CONFIG_FILE = APP_DIR / "config.json"
ENV_FILE = APP_DIR / ".env"

LANGUAGES = {
    "auto": "🌐 Auto-detect (যেকোনো ভাষা / Universal)",
    "bn": "🇧🇩 বাংলা (Bengali)",
    "en": "🇺🇸 English",
    "hi": "🇮🇳 हिन्दी (Hindi)",
    "ar": "🇸🇦 العربية (Arabic)",
    "ur": "🇵🇰 اردو (Urdu)",
    "es": "🇪🇸 Español (Spanish)",
    "fr": "🇫🇷 Français (French)",
    "de": "🇩🇪 Deutsch (German)",
    "ja": "🇯🇵 日本語 (Japanese)",
    "zh": "🇨🇳 中文 (Chinese)",
    "ru": "🇷🇺 Русский (Russian)",
    "tr": "🇹🇷 Türkçe (Turkish)",
    "custom": "✍️ Custom Language (অন্যান্য)"
}

DEFAULT_CONFIG = {
    "gemini_api_key": os.environ.get("GEMINI_API_KEY", ""),
    "microphone_device": None,
    "language": "auto",
    "custom_language": "",
    "primary_hotkey": "Ctrl+Shift+Space",
    "hotkeys": ["<f8>", "<ctrl>+<shift>+<space>", "<ctrl>+<alt>+v"],
    "autostart": False,
    "beep_enabled": True,
    "model": "gemini-3.5-flash-lite",
    "sample_rate": 16000,
    "channels": 1,
    "phone_password": ""
}

def load_config() -> dict:
    config = DEFAULT_CONFIG.copy()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8-sig") as f:
                user_cfg = json.load(f)
                config.update(user_cfg)
        except Exception:
            pass

    if ENV_FILE.exists():
        try:
            with open(ENV_FILE, "r", encoding="utf-8-sig") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        if k.strip() == "GEMINI_API_KEY" and v.strip():
                            config["gemini_api_key"] = v.strip()
        except Exception:
            pass

    return config

def save_config(cfg: dict):
    api_key = cfg.get("gemini_api_key", "").strip()
    if api_key:
        try:
            with open(ENV_FILE, "w", encoding="utf-8") as f:
                f.write(f"GEMINI_API_KEY={api_key}\n")
        except Exception:
            pass

    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving config: {e}")

def get_transcription_prompt(lang_code: str, custom_lang: str = "") -> str:
    if lang_code == "auto":
        return (
            "You are a universal speech transcriber. Transcribe the spoken audio with exact fidelity "
            "in the language spoken by the speaker (supporting Bengali, English, and all global languages). "
            "Preserve code-switching/mixed speech naturally. Add proper punctuation. Output ONLY the raw transcribed text. "
            "If silence or no human speech, return EMPTY_SPEECH."
        )
    elif lang_code == "bn":
        return (
            "Transcribe the spoken audio accurately into natural Bengali script (বাংলা). "
            "If English terms are spoken, write them naturally. Add punctuation (দাঁড়ি, কমা). "
            "Output ONLY the transcribed text. If silence or no speech, return EMPTY_SPEECH."
        )
    elif lang_code == "en":
        return (
            "Transcribe the spoken audio accurately into English with proper capitalization and punctuation. "
            "Output ONLY the transcribed text. If silence or no speech, return EMPTY_SPEECH."
        )
    elif lang_code == "custom" and custom_lang:
        return (
            f"Transcribe the spoken audio accurately in {custom_lang}. "
            "Add appropriate punctuation. Output ONLY the raw transcribed text without commentary. "
            "If silence or no speech, return EMPTY_SPEECH."
        )
    else:
        lang_name = LANGUAGES.get(lang_code, "the spoken language")
        return (
            f"Transcribe the spoken audio accurately in {lang_name}. "
            "Add proper punctuation. Output ONLY the raw transcribed text. "
            "If silence or no speech, return EMPTY_SPEECH."
        )
