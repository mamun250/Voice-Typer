import os
import sys
import json
import time
import socket
import ssl
import threading
import logging
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import ipaddress
import datetime

if getattr(sys, 'frozen', False):
    APP_DIR = Path(sys.executable).parent.resolve()
else:
    APP_DIR = Path(__file__).parent.resolve()

def get_local_ip():
    """Detect local LAN IP address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def generate_self_signed_cert(cert_path: Path, key_path: Path, local_ip: str):
    """Generate self-signed certificate for local HTTPS."""
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, u'VoiceTyperLocal'),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, u'Voice Typer Companion')
        ])

        san_list = [x509.DNSName('localhost'), x509.IPAddress(ipaddress.IPv4Address('127.0.0.1'))]
        try:
            san_list.append(x509.IPAddress(ipaddress.IPv4Address(local_ip)))
        except Exception:
            pass

        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1))
            .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365))
            .add_extension(
                x509.SubjectAlternativeName(san_list),
                critical=False,
            )
            .sign(key, hashes.SHA256())
        )

        key_path.write_bytes(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))
        cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        logging.info(f"Generated self-signed SSL cert for {local_ip}")
        return True
    except Exception as e:
        logging.error(f"Failed to generate SSL cert: {e}")
        return False

# Exact reproduction of user's requested Retro-Minimalist UI
MOBILE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>Voice Typer</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  background-color: #faf9f6;
  background-image: 
    linear-gradient(rgba(0, 0, 0, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 0, 0, 0.05) 1px, transparent 1px);
  background-size: 24px 24px;
  background-position: center top;
  color: #1a1a1a;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 20px 16px;
  user-select: none;
}

/* Status Pill */
.top-status {
  position: absolute;
  top: 16px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  background: #ffffff;
  border: 1.5px solid #222222;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 700;
  box-shadow: 2px 2px 0px #222222;
}
.dot-status {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #10b981;
}
.dot-status.offline {
  background: #ef4444;
}

/* 1. Red Mic Button */
.mic-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-top: 24px;
  margin-bottom: 8px;
}
.mic-btn {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  background: #f83b3b;
  border: none;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 8px 24px rgba(248, 59, 59, 0.4);
  transition: transform 0.15s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.2s;
  outline: none;
}
.mic-btn:active {
  transform: scale(0.94);
}
.mic-btn.recording {
  animation: mic-pulse 1.3s infinite ease-in-out;
  box-shadow: 0 0 0 12px rgba(248, 59, 59, 0.2), 0 8px 28px rgba(248, 59, 59, 0.5);
}
@keyframes mic-pulse {
  0% { transform: scale(1); }
  50% { transform: scale(1.06); }
  100% { transform: scale(1); }
}
.mic-icon-svg {
  width: 58px;
  height: 58px;
  stroke: #ffffff;
  stroke-width: 2.2;
  stroke-linecap: round;
  stroke-linejoin: round;
  fill: none;
}

/* 2. Audio Waveform Canvas */
.waveform-container {
  width: 100%;
  max-width: 340px;
  height: 72px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 12px 0;
}
#waveCanvas {
  width: 320px;
  height: 64px;
}

/* 3. Retro Window Card */
.window-card {
  background: #fcfbf8;
  border: 2px solid #222222;
  border-radius: 18px;
  box-shadow: 5px 6px 0px #222222;
  width: 100%;
  max-width: 340px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.window-header {
  height: 38px;
  border-bottom: 2px solid #222222;
  display: flex;
  align-items: center;
  padding: 0 14px;
  gap: 8px;
}
.circle-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 1.5px solid #222222;
}
.dot-red { background: #ff5f56; }
.dot-green { background: #27c93f; }
.dot-yellow { background: #ffbd2e; }

.window-body {
  padding: 16px;
  display: flex;
  flex-direction: column;
}
textarea {
  width: 100%;
  height: 140px;
  border: none;
  background: transparent;
  outline: none;
  resize: none;
  font-family: "Courier New", Courier, monospace, serif;
  font-size: 1.1rem;
  line-height: 1.5;
  color: #111111;
  user-select: text;
}
textarea::placeholder {
  color: #222222;
  opacity: 0.85;
  font-family: inherit;
  font-weight: 500;
}

/* Action Buttons */
.btn-row {
  display: flex;
  gap: 10px;
  width: 100%;
  max-width: 340px;
  margin-top: 16px;
}
.btn {
  padding: 12px 18px;
  border-radius: 12px;
  font-size: 0.95rem;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 2px solid #222222;
  transition: transform 0.1s, box-shadow 0.1s;
}
.btn:active {
  transform: translate(2px, 2px);
  box-shadow: 2px 2px 0px #222222 !important;
}
.btn-send {
  flex: 1;
  background: #222222;
  color: #ffffff;
  box-shadow: 4px 4px 0px #555555;
}
.btn-clear {
  background: #ffffff;
  color: #222222;
  box-shadow: 4px 4px 0px #222222;
  padding: 12px 16px;
}

/* Toast */
.toast {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%) translateY(100px);
  background: #222222;
  color: white;
  padding: 10px 22px;
  border-radius: 9999px;
  border: 2px solid #ffffff;
  font-size: 0.88rem;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 8px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.3);
  opacity: 0;
  transition: all 0.25s cubic-bezier(0.175, 0.885, 0.32, 1.275);
  z-index: 999;
}
.toast.show {
  transform: translateX(-50%) translateY(0);
  opacity: 1;
}

/* HTTPS Notice Banner */
.notice {
  background: #fffbeb;
  border: 1.5px solid #222222;
  box-shadow: 3px 3px 0px #222222;
  color: #1a1a1a;
  padding: 8px 12px;
  border-radius: 10px;
  font-size: 0.78rem;
  margin-bottom: 12px;
  max-width: 340px;
  text-align: center;
}
.notice a {
  color: #f83b3b;
  font-weight: 700;
  text-decoration: underline;
}
</style>
</head>
<body>

<div class="top-status">
  <div class="dot-status" id="statusDot"></div>
  <span id="statusText">Connected to PC</span>
</div>

<div class="notice" id="httpNotice" style="display: none;">
  🔒 <strong>Microphone requires HTTPS:</strong><br>
  <a href="" id="httpsLink">Tap here to switch to HTTPS mode</a>
</div>

<!-- 1. Red Mic Button -->
<div class="mic-container">
  <button class="mic-btn" id="micBtn" onclick="toggleMic()">
    <svg class="mic-icon-svg" viewBox="0 0 24 24">
      <rect x="9" y="3" width="6" height="11" rx="3" fill="#ffffff"></rect>
      <path d="M5 10a7 7 0 0 0 14 0"></path>
      <line x1="12" y1="17" x2="12" y2="21"></line>
      <line x1="8" y1="21" x2="16" y2="21"></line>
    </svg>
  </button>
</div>

<!-- 2. Audio Waveform Canvas -->
<div class="waveform-container">
  <canvas id="waveCanvas" width="320" height="64"></canvas>
</div>

<!-- 3. Retro Window Box -->
<div class="window-card">
  <div class="window-header">
    <div class="circle-dot dot-red"></div>
    <div class="circle-dot dot-green"></div>
    <div class="circle-dot dot-yellow"></div>
  </div>
  <div class="window-body">
    <textarea id="textBox" placeholder="Type Here......"></textarea>
  </div>
</div>

<!-- Action Buttons -->
<div class="btn-row">
  <button class="btn btn-send" onclick="sendText()">
    <span>⚡ Send to PC ↵</span>
  </button>
  <button class="btn btn-clear" onclick="clearText()">Clear</button>
</div>

<div class="toast" id="toast">
  <span id="toastIcon">✓</span>
  <span id="toastMsg">Pasted into PC!</span>
</div>

<script>
let isRecording = false;
let mediaRecorder = null;
let audioChunks = [];
let audioCtx = null;
let analyser = null;
let dataArray = null;
let animFrameId = null;

const canvas = document.getElementById('waveCanvas');
const ctx = canvas.getContext('2d');
const textBox = document.getElementById('textBox');

// Symmetrical Waveform Renderer
const numBars = 42;
const barWidth = 3.5;
const barGap = (canvas.width - (numBars * barWidth)) / (numBars - 1);
const centerY = canvas.height / 2;

function drawWaveform(time) {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = '#111111';
  ctx.lineCap = 'round';

  if (isRecording && analyser) {
    analyser.getByteFrequencyData(dataArray);
  }

  for (let i = 0; i < numBars; i++) {
    // Symmetrical bell-curve envelope for tapering at edges
    const norm = i / (numBars - 1);
    const envelope = Math.sin(norm * Math.PI);

    let h = 3; // minimum height
    if (isRecording && dataArray) {
      // Map bar index to frequency bin
      const bin = Math.floor((i / numBars) * (dataArray.length * 0.7));
      const val = dataArray[bin] || 0;
      h = Math.max(3, (val / 255) * 28 * envelope + (Math.sin(time * 0.01 + i * 0.3) * 2));
    } else {
      // Idle resting wave: gentle breathing sine curve matching screenshot
      const baseH = (Math.pow(envelope, 1.8) * 20);
      const breath = Math.sin(time * 0.003 + i * 0.2) * 2;
      h = Math.max(2, baseH + breath);
    }

    const x = i * (barWidth + barGap);
    const yTop = centerY - h;
    const yBottom = centerY + h;

    // Draw vertical bar with rounded tips
    ctx.beginPath();
    ctx.roundRect(x, yTop, barWidth, h * 2, barWidth / 2);
    ctx.fill();
  }

  animFrameId = requestAnimationFrame(drawWaveform);
}
requestAnimationFrame(drawWaveform);

function showToast(msg, isErr=false) {
  const toast = document.getElementById('toast');
  document.getElementById('toastMsg').innerText = msg;
  document.getElementById('toastIcon').innerText = isErr ? '⚠️' : '✓';
  toast.classList.add('show');
  if (navigator.vibrate) navigator.vibrate(30);
  setTimeout(() => toast.classList.remove('show'), 2200);
}

function clearText() {
  textBox.value = '';
}

function getHttpsUrl() {
  return 'https://' + location.hostname + ':{{HTTPS_PORT}}';
}

function checkProtocol() {
  const isSecure = window.isSecureContext || location.hostname === 'localhost' || location.hostname === '127.0.0.1';
  if (!isSecure && (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia)) {
    const notice = document.getElementById('httpNotice');
    const link = document.getElementById('httpsLink');
    link.href = getHttpsUrl();
    notice.style.display = 'block';
  }
}
checkProtocol();

// Microphone recording
async function toggleMic() {
  if (isRecording) {
    stopRecording();
  } else {
    startRecording();
  }
}

async function startRecording() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    window.location.href = getHttpsUrl();
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioChunks = [];

    // Set up Web Audio API Analyser for real-time waveform animation
    try {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const source = audioCtx.createMediaStreamSource(stream);
      analyser = audioCtx.createAnalyser();
      analyser.fftSize = 128;
      dataArray = new Uint8Array(analyser.frequencyBinCount);
      source.connect(analyser);
    } catch(e) {
      console.warn("Audio analyser error:", e);
    }

    let mimeType = '';
    if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
      mimeType = 'audio/webm;codecs=opus';
    } else if (MediaRecorder.isTypeSupported('audio/webm')) {
      mimeType = 'audio/webm';
    } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
      mimeType = 'audio/mp4';
    }

    mediaRecorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunks.push(e.data);
    };

    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach(t => t.stop());
      if (audioCtx) {
        audioCtx.close().catch(()=>{});
        audioCtx = null;
        analyser = null;
      }
      const audioBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType || 'audio/webm' });
      await uploadAudio(audioBlob);
    };

    mediaRecorder.start();
    isRecording = true;
    document.getElementById('micBtn').classList.add('recording');

    // Trigger start sound on PC
    fetch('/api/sound', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ sound: 'start' })
    }).catch(()=>{});

  } catch (err) {
    document.getElementById('micBtn').classList.remove('recording');
    showToast('Permission needed: ' + err.message, true);
  }
}

function stopRecording() {
  if (mediaRecorder && isRecording) {
    isRecording = false;
    document.getElementById('micBtn').classList.remove('recording');
    mediaRecorder.stop();

    // Trigger stop sound on PC
    fetch('/api/sound', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ sound: 'stop' })
    }).catch(()=>{});
  }
}

async function uploadAudio(blob) {
  showToast('Transcribing with Gemini...');
  try {
    const res = await fetch('/api/transcribe_audio', {
      method: 'POST',
      headers: {
        'Content-Type': blob.type || 'audio/webm'
      },
      body: blob
    });
    const data = await res.json();

    if (data.status === 'ok' && data.text) {
      const text = data.text.trim();
      if (textBox.value.trim()) {
        textBox.value += ' ' + text;
      } else {
        textBox.value = text;
      }
      showToast('Pasted to PC!');
    } else {
      showToast('No speech detected', true);
    }
  } catch (err) {
    showToast('Upload error', true);
  }
}

// Send text from box to PC
function sendText() {
  const text = textBox.value.trim();
  if (!text) {
    showToast('Type or speak something first', true);
    return;
  }
  fetch('/api/paste_text', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: text })
  })
  .then(res => res.json())
  .then(data => {
    showToast('Pasted to PC cursor!');
  })
  .catch(() => {
    showToast('Failed to reach PC', true);
  });
}

// Heartbeat
function checkConnection() {
  fetch('/api/ping')
    .then(r => r.json())
    .then(d => {
      document.getElementById('statusDot').classList.remove('offline');
      document.getElementById('statusText').innerText = 'Connected: ' + (d.pc_name || 'PC');
    })
    .catch(() => {
      document.getElementById('statusDot').classList.add('offline');
      document.getElementById('statusText').innerText = 'Reconnecting...';
    });
}
setInterval(checkConnection, 8000);
checkConnection();
</script>
</body>
</html>
"""

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 128

class PhoneRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    timeout = 15

    def log_message(self, format, *args):
        pass

    def _send_json(self, status_code, data):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.close_connection = True

    def do_GET(self):
        if self.path == '/' or self.path.startswith('/index'):
            server = getattr(self.server, 'app_server', None)
            https_p = str(server.https_port) if server else "8766"
            http_p = str(server.http_port) if server else "8765"
            html = MOBILE_HTML.replace('{{HTTPS_PORT}}', https_p).replace('{{HTTP_PORT}}', http_p)
            body = html.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(body)
            self.close_connection = True
        elif self.path == '/api/ping':
            self._send_json(200, {
                'status': 'ok',
                'app': 'VoiceTyper',
                'pc_name': socket.gethostname(),
                'active': True
            })
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        server = self.server.app_server

        if self.path == '/api/paste_text':
            body_bytes = self.rfile.read(content_length)
            try:
                data = json.loads(body_bytes.decode('utf-8'))
                text = data.get('text', '')
                key = data.get('key', '')
                if text and server.on_paste_text:
                    server.on_paste_text(text)
                elif key and server.on_special_key:
                    server.on_special_key(key)
                self._send_json(200, {'status': 'ok', 'pasted': len(text)})
            except Exception as e:
                self._send_json(400, {'status': 'error', 'message': str(e)})

        elif self.path == '/api/transcribe_audio':
            audio_bytes = self.rfile.read(content_length)
            content_type = self.headers.get('Content-Type', 'audio/webm')
            mime_type = content_type.split(';')[0].strip()
            if not mime_type:
                mime_type = 'audio/webm'

            text = ""
            if server.on_transcribe_audio:
                try:
                    text = server.on_transcribe_audio(audio_bytes, mime_type)
                except Exception as e:
                    logging.error(f"Audio transcription error: {e}")

            self._send_json(200, {'status': 'ok', 'text': text})

        elif self.path == '/api/sound':
            body_bytes = self.rfile.read(content_length)
            try:
                data = json.loads(body_bytes.decode('utf-8'))
                sound_name = data.get('sound', '')
                if server.on_play_sound:
                    server.on_play_sound(sound_name)
                self._send_json(200, {'status': 'ok'})
            except Exception as e:
                self._send_json(400, {'status': 'error', 'message': str(e)})
        else:
            self.send_error(404, "Not Found")


class PhoneServer:
    def __init__(self, http_port=8765, https_port=8766, on_paste_text=None, on_special_key=None, on_transcribe_audio=None, on_play_sound=None):
        self.http_port = http_port
        self.https_port = https_port
        self.on_paste_text = on_paste_text
        self.on_special_key = on_special_key
        self.on_transcribe_audio = on_transcribe_audio
        self.on_play_sound = on_play_sound

        self.local_ip = get_local_ip()
        self.http_server = None
        self.https_server = None
        self.http_thread = None
        self.https_thread = None
        self.is_running = False

    def start(self):
        if self.is_running:
            return

        # 1. Start HTTP Server with automatic port fallback
        for port in range(self.http_port, self.http_port + 10):
            try:
                srv = ThreadedHTTPServer(('0.0.0.0', port), PhoneRequestHandler)
                srv.app_server = self
                self.http_server = srv
                self.http_port = port
                self.http_thread = threading.Thread(target=self.http_server.serve_forever, daemon=True)
                self.http_thread.start()
                logging.info(f"Phone HTTP server running at http://{self.local_ip}:{self.http_port}")
                break
            except OSError as e:
                logging.warning(f"HTTP Port {port} busy ({e}), trying {port+1}...")

        # 2. Start HTTPS Server with automatic port fallback
        try:
            cert_path = APP_DIR / "phone_cert.pem"
            key_path = APP_DIR / "phone_key.pem"

            if not cert_path.exists() or not key_path.exists():
                generate_self_signed_cert(cert_path, key_path, self.local_ip)

            if cert_path.exists() and key_path.exists():
                start_p = self.https_port if self.https_port != self.http_port else self.http_port + 1
                for port in range(start_p, start_p + 10):
                    if port == self.http_port:
                        continue
                    try:
                        srv = ThreadedHTTPServer(('0.0.0.0', port), PhoneRequestHandler)
                        srv.app_server = self
                        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                        ctx.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
                        srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
                        self.https_server = srv
                        self.https_port = port
                        self.https_thread = threading.Thread(target=self.https_server.serve_forever, daemon=True)
                        self.https_thread.start()
                        logging.info(f"Phone HTTPS server running at https://{self.local_ip}:{self.https_port}")
                        break
                    except OSError as e:
                        logging.warning(f"HTTPS Port {port} busy ({e}), trying {port+1}...")
        except Exception as e:
            logging.warning(f"Could not start HTTPS server: {e}")

        self.is_running = True

    def stop(self):
        self.is_running = False
        if self.http_server:
            try:
                self.http_server.shutdown()
                self.http_server.server_close()
            except Exception:
                pass
        if self.https_server:
            try:
                self.https_server.shutdown()
                self.https_server.server_close()
            except Exception:
                pass

    def get_http_url(self):
        return f"http://{self.local_ip}:{self.http_port}"

    def get_https_url(self):
        return f"https://{self.local_ip}:{self.https_port}"
