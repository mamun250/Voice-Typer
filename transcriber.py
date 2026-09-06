import os
import base64
import requests
import threading
from pathlib import Path
from config import load_config, get_transcription_prompt

class GeminiTranscriber:
    def __init__(self):
        self.session = requests.Session()
        self._prewarm()

    def _prewarm(self):
        def _warm():
            try:
                cfg = load_config()
                api_key = cfg.get("gemini_api_key", "")
                if api_key:
                    url = f'https://generativelanguage.googleapis.com/v1beta/models?key={api_key}'
                    self.session.get(url, timeout=5)
            except Exception:
                pass
        threading.Thread(target=_warm, daemon=True).start()

    def transcribe(self, audio_bytes: bytes, mime_type: str = 'audio/wav') -> str:
        if not audio_bytes or len(audio_bytes) < 500:
            return ""

        cfg = load_config()
        api_key = cfg.get("gemini_api_key", "").strip()
        if not api_key:
            raise ValueError("Gemini API Key সেট করা নেই! সেটিংস থেকে আপনার API Key প্রবেশ করান।")

        lang = cfg.get("language", "auto")
        custom_lang = cfg.get("custom_language", "")
        prompt = get_transcription_prompt(lang, custom_lang)
        model = cfg.get("model", "gemini-3.5-flash-lite")

        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

        models_to_try = [
            model,
            'gemini-flash-lite-latest',
            'gemini-3.5-transcribe'
        ]

        last_error = None
        for m in models_to_try:
            url = f'https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}'
            payload = {
                'contents': [{
                    'parts': [
                        {'text': prompt},
                        {
                            'inline_data': {
                                'mime_type': mime_type,
                                'data': audio_b64
                            }
                        }
                    ]
                }],
                'generationConfig': {
                    'temperature': 0.0
                }
            }

            try:
                resp = self.session.post(url, json=payload, timeout=8)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get('candidates', [])
                    if not candidates:
                        return ""
                    parts = candidates[0].get('content', {}).get('parts', [])
                    if not parts:
                        return ""
                    text = parts[0].get('text', '').strip()
                    if text in ('EMPTY_SPEECH', 'NOTHING', 'NOTHING_SAID'):
                        return ""
                    if (text.startswith('"') and text.endswith('"')) or (text.startswith('“') and text.endswith('”')):
                        text = text[1:-1].strip()
                    return text
                else:
                    last_error = f"HTTP {resp.status_code}: {resp.text[:150]}"
            except Exception as e:
                last_error = str(e)

        print(f"[Transcriber Error] All fast models failed: {last_error}")
        return ""
