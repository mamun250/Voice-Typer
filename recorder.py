import sys
import io
import wave
import threading
import winsound
from pathlib import Path
import numpy as np
import sounddevice as sd

def get_sound_path(filename):
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / "assets" / filename
    return Path(__file__).parent / "assets" / filename

def _play_wav_async(filename, fallback_freq=1200, fallback_ms=100):
    """Play a sound file using Windows native audio subsystem without blocking."""
    try:
        path = get_sound_path(filename)
        if path.exists():
            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
            return
    except Exception:
        pass
    
    # Fallback to system beep if sound file failed
    def _beep():
        try:
            winsound.Beep(fallback_freq, fallback_ms)
        except Exception:
            pass
    threading.Thread(target=_beep, daemon=True).start()

def play_record_start_sound():
    """Crisp, bright double-beep when recording starts."""
    _play_wav_async("start.wav", fallback_freq=1200, fallback_ms=100)

def play_record_stop_sound():
    """Clear descending tone when recording stops."""
    _play_wav_async("stop.wav", fallback_freq=800, fallback_ms=100)

def play_paste_success_sound():
    """Pleasant confirmation chime when text is pasted."""
    _play_wav_async("success.wav", fallback_freq=1500, fallback_ms=80)

def play_startup_chime():
    """Pleasant ascending chord when the app launches."""
    _play_wav_async("startup.wav", fallback_freq=1000, fallback_ms=150)

def play_beep_async(freq, duration_ms):
    """Generic fallback beep."""
    def _beep():
        try:
            winsound.Beep(freq, duration_ms)
        except Exception:
            pass
    threading.Thread(target=_beep, daemon=True).start()

class AudioRecorder:
    def __init__(self, sample_rate: int = 16000, channels: int = 1, device=None):
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device
        self.is_recording = False
        self._frames = []
        self._stream = None
        self._lock = threading.Lock()
        self.last_peak_amplitude = 0

    def start(self):
        with self._lock:
            self._frames = []
            self.is_recording = True
            self.last_peak_amplitude = 0

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype='int16',
            device=self.device,
            callback=self._audio_callback
        )
        self._stream.start()

    def _audio_callback(self, indata, frames, time_info, status):
        if self.is_recording:
            with self._lock:
                self._frames.append(indata.copy())

    def stop(self) -> bytes:
        self.is_recording = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        with self._lock:
            if not self._frames:
                return b""
            audio_data = np.concatenate(self._frames, axis=0)
            self.last_peak_amplitude = int(np.max(np.abs(audio_data))) if len(audio_data) > 0 else 0

        wav_io = io.BytesIO()
        with wave.open(wav_io, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_data.tobytes())

        return wav_io.getvalue()
