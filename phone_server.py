import os
import sys
import json
import time
import socket
import ssl
import threading
import logging
import secrets
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import ipaddress
import datetime
from tunnel import TunnelManager

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

# Full Bi-directional Synchronized UI
MOBILE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>Voice Typer Companion</title>
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
  padding: 16px 14px;
  user-select: none;
}

/* Status Pill */
.top-status {
  position: absolute;
  top: 14px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 14px;
  background: #ffffff;
  border: 1.5px solid #222222;
  border-radius: 999px;
  font-size: 0.76rem;
  font-weight: 700;
  box-shadow: 2px 2px 0px #222222;
  z-index: 10;
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
  margin-top: 26px;
  margin-bottom: 6px;
}
.mic-btn {
  width: 110px;
  height: 110px;
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
  width: 52px;
  height: 52px;
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
  height: 58px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 6px 0;
}
#waveCanvas {
  width: 320px;
  height: 54px;
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
  height: 42px;
  border-bottom: 2px solid #222222;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  background: #f5f3ef;
}
.window-dots {
  display: flex;
  align-items: center;
  gap: 7px;
}
.circle-dot {
  width: 11px;
  height: 11px;
  border-radius: 50%;
  border: 1.5px solid #222222;
}
.dot-red { background: #ff5f56; }
.dot-green { background: #27c93f; }
.dot-yellow { background: #ffbd2e; }

/* Live Mode Toggle */
.live-toggle-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
}
.live-label {
  font-size: 0.74rem;
  font-weight: 800;
  color: #10b981;
  letter-spacing: 0.3px;
  transition: color 0.2s;
}
.switch {
  position: relative;
  display: inline-block;
  width: 38px;
  height: 22px;
}
.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}
.slider {
  position: absolute;
  cursor: pointer;
  top: 0; left: 0; right: 0; bottom: 0;
  background-color: #e5e7eb;
  border: 1.5px solid #222222;
  transition: 0.2s;
  border-radius: 999px;
  box-shadow: 1px 1px 0px #222222;
}
.slider:before {
  position: absolute;
  content: "";
  height: 14px;
  width: 14px;
  left: 2px;
  bottom: 2px;
  background-color: #ffffff;
  border: 1.5px solid #222222;
  transition: 0.2s;
  border-radius: 50%;
}
input:checked + .slider {
  background-color: #10b981;
}
input:checked + .slider:before {
  transform: translateX(16px);
  background-color: #ffffff;
}

.window-body {
  padding: 14px;
  display: flex;
  flex-direction: column;
}
textarea {
  width: 100%;
  height: 125px;
  border: none;
  background: transparent;
  outline: none;
  resize: none;
  font-family: "Courier New", Courier, monospace, serif;
  font-size: 1.05rem;
  line-height: 1.45;
  color: #111111;
  user-select: text;
}
textarea::placeholder {
  color: #333333;
  opacity: 0.8;
  font-family: inherit;
  font-weight: 500;
}

/* Tactile Navigation Toolbar */
.nav-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1.5px dashed #cccccc;
}
.nav-btn {
  flex: 1;
  height: 35px;
  background: #ffffff;
  border: 1.5px solid #222222;
  border-radius: 8px;
  box-shadow: 2px 2px 0px #222222;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.95rem;
  font-weight: bold;
  cursor: pointer;
  color: #111111;
  user-select: none;
  transition: transform 0.05s, box-shadow 0.05s;
}
.nav-btn:active {
  transform: translate(1.5px, 1.5px);
  box-shadow: 0.5px 0.5px 0px #222222 !important;
}
.nav-btn.special {
  background: #f3f4f6;
  font-size: 0.85rem;
}

/* Action Buttons */
.btn-row {
  display: flex;
  gap: 10px;
  width: 100%;
  max-width: 340px;
  margin-top: 14px;
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
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%) translateY(100px);
  background: #222222;
  color: white;
  padding: 9px 20px;
  border-radius: 9999px;
  border: 2px solid #ffffff;
  font-size: 0.86rem;
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

/* Security Lock Screen Overlay */
.lock-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(26, 26, 26, 0.65);
  backdrop-filter: blur(5px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  z-index: 2000;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.25s ease;
}
.lock-overlay.active {
  opacity: 1;
  pointer-events: auto;
}
.lock-card {
  background: #fcfbf8;
  border: 2.5px solid #222222;
  border-radius: 18px;
  box-shadow: 6px 6px 0px #222222;
  padding: 24px 20px;
  width: 100%;
  max-width: 320px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  text-align: center;
}
.lock-icon {
  font-size: 2.5rem;
}
.lock-title {
  font-size: 1.2rem;
  font-weight: 800;
  color: #111111;
}
.lock-subtitle {
  font-size: 0.82rem;
  color: #555555;
  line-height: 1.4;
}
.lock-input {
  width: 100%;
  padding: 12px 14px;
  border: 2px solid #222222;
  border-radius: 10px;
  box-shadow: 3px 3px 0px #222222;
  font-size: 1.15rem;
  text-align: center;
  letter-spacing: 2px;
  outline: none;
  background: #ffffff;
}
.lock-input:focus {
  border-color: #10b981;
}
.lock-error {
  font-size: 0.78rem;
  color: #ef4444;
  font-weight: 700;
  display: none;
}
.shake {
  animation: shake 0.35s ease-in-out;
}
@keyframes shake {
  0%, 100% { transform: translateX(0); }
  20%, 60% { transform: translateX(-8px); }
  40%, 80% { transform: translateX(8px); }
}
</style>
</head>
<body>

<!-- Status Pill -->
<div class="top-status">
  <div class="dot-status" id="statusDot"></div>
  <span id="statusText">Connected to PC</span>
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
  <canvas id="waveCanvas" width="320" height="54"></canvas>
</div>

<!-- 3. Retro Window Card -->
<div class="window-card">
  <div class="window-header">
    <div class="window-dots">
      <div class="circle-dot dot-red"></div>
      <div class="circle-dot dot-yellow"></div>
      <div class="circle-dot dot-green"></div>
    </div>
    <div class="live-toggle-wrapper">
      <span class="live-label" id="liveLabel">⚡ LIVE SYNC ON</span>
      <label class="switch">
        <input type="checkbox" id="liveModeToggle" checked onchange="toggleLiveMode(this.checked)">
        <span class="slider"></span>
      </label>
    </div>
  </div>
  <div class="window-body">
    <textarea id="textBox" placeholder="Type Here......"></textarea>
    <!-- Tactile Cursor & Key Navigation -->
    <div class="nav-toolbar">
      <button type="button" class="nav-btn" onmousedown="event.preventDefault()" onclick="sendNavKey('left')" title="Left">◀</button>
      <button type="button" class="nav-btn" onmousedown="event.preventDefault()" onclick="sendNavKey('up')" title="Up">▲</button>
      <button type="button" class="nav-btn" onmousedown="event.preventDefault()" onclick="sendNavKey('down')" title="Down">▼</button>
      <button type="button" class="nav-btn" onmousedown="event.preventDefault()" onclick="sendNavKey('right')" title="Right">▶</button>
      <button type="button" class="nav-btn special" onmousedown="event.preventDefault()" onclick="sendNavKey('backspace')" title="Backspace">⌫</button>
      <button type="button" class="nav-btn special" onmousedown="event.preventDefault()" onclick="sendNavKey('enter')" title="Enter">↵</button>
    </div>
  </div>
</div>

<!-- Action Buttons -->
<div class="btn-row">
  <button type="button" class="btn btn-send" id="btnSend" onclick="sendText()">
    <span>⚡ Send to PC ↵</span>
  </button>
  <button type="button" class="btn btn-clear" onclick="clearText()">Clear</button>
</div>

<div class="toast" id="toast">
  <span id="toastIcon">✓</span>
  <span id="toastMsg">Pasted into PC!</span>
</div>

<!-- Password Lock Screen Overlay -->
<div class="lock-overlay" id="lockOverlay">
  <div class="lock-card">
    <div class="lock-icon">🔒</div>
    <div class="lock-title">Password Protected</div>
    <div class="lock-subtitle">Enter the password configured on your PC to connect and type.</div>
    <input type="password" id="authPwd" class="lock-input" placeholder="Enter Password" onkeydown="if(event.key==='Enter') submitPassword()">
    <div class="lock-error" id="lockError">Incorrect Password</div>
    <button class="btn btn-send" style="width: 100%;" onclick="submitPassword()">Unlock & Connect 🔓</button>
  </div>
</div>

<script>
let isRecording = false;
let mediaRecorder = null;
let audioChunks = [];
let audioCtx = null;
let analyser = null;
let dataArray = null;
let animFrameId = null;

let liveMode = true;
let authToken = localStorage.getItem('vt_auth_token') || '';

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
    const norm = i / (numBars - 1);
    const envelope = Math.sin(norm * Math.PI);

    let h = 3;
    if (isRecording && dataArray) {
      const bin = Math.floor((i / numBars) * (dataArray.length * 0.7));
      const val = dataArray[bin] || 0;
      h = Math.max(3, (val / 255) * 26 * envelope + (Math.sin(time * 0.01 + i * 0.3) * 2));
    } else {
      const baseH = (Math.pow(envelope, 1.8) * 18);
      const breath = Math.sin(time * 0.003 + i * 0.2) * 2;
      h = Math.max(2, baseH + breath);
    }

    const x = i * (barWidth + barGap);
    const yTop = centerY - h;
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
  if (navigator.vibrate) navigator.vibrate(25);
  setTimeout(() => toast.classList.remove('show'), 2000);
}

function getAuthHeaders(extra = {}) {
  const headers = Object.assign({}, extra);
  if (authToken) {
    headers['Authorization'] = 'Bearer ' + authToken;
    headers['X-Auth-Token'] = authToken;
  }
  return headers;
}

// ----------------------------------------------------
// Synchronized Text Editing (Both Mobile & PC in sync)
// ----------------------------------------------------
let syncPending = false;
let syncRunning = false;
let syncTimer = null;

function scheduleSync() {
  if (syncTimer) clearTimeout(syncTimer);
  syncTimer = setTimeout(syncWithPC, 35);
}

async function syncWithPC() {
  if (!liveMode) return;
  if (syncRunning) {
    syncPending = true;
    return;
  }
  syncRunning = true;
  syncPending = false;

  const text = textBox.value;
  const cursor = textBox.selectionStart;

  try {
    const res = await fetch('/api/sync_text', {
      method: 'POST',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ text: text, cursor: cursor })
    });
    if (res.status === 401) {
      document.getElementById('lockOverlay').classList.add('active');
    }
  } catch (err) {
    console.warn('Sync failed:', err);
  } finally {
    syncRunning = false;
    if (syncPending) {
      syncWithPC();
    }
  }
}

// 1. Caret repositioning events on mobile & desktop (Standard W3C selectionchange)
document.addEventListener('selectionchange', () => {
  if (document.activeElement === textBox) {
    scheduleSync();
  }
});

// 2. Direct touch / pointer events on textbox for immediate mobile response
textBox.addEventListener('pointerup', scheduleSync);
textBox.addEventListener('touchend', () => setTimeout(scheduleSync, 40));
textBox.addEventListener('input', scheduleSync);
textBox.addEventListener('click', scheduleSync);
textBox.addEventListener('keyup', (e) => {
  scheduleSync();
});
textBox.addEventListener('select', scheduleSync);

function clearText() {
  textBox.value = '';
  textBox.setSelectionRange(0, 0);
  fetch('/api/reset_sync', {
    method: 'POST',
    headers: getAuthHeaders({ 'Content-Type': 'application/json' })
  }).catch(()=>{});
  showToast('Phone text cleared!');
}

function getPrevCluster(text, pos) {
  if (pos <= 0) return 0;
  if (typeof Intl !== 'undefined' && Intl.Segmenter) {
    const seg = new Intl.Segmenter('bn', { granularity: 'grapheme' });
    let last = 0;
    for (const s of seg.segment(text)) {
      if (s.index >= pos) break;
      last = s.index;
    }
    return last;
  }
  return Math.max(0, pos - 1);
}

function getNextCluster(text, pos) {
  if (pos >= text.length) return text.length;
  if (typeof Intl !== 'undefined' && Intl.Segmenter) {
    const seg = new Intl.Segmenter('bn', { granularity: 'grapheme' });
    for (const s of seg.segment(text)) {
      if (s.index > pos) return s.index;
    }
    return text.length;
  }
  return Math.min(text.length, pos + 1);
}

// Tactile Navigation Key
function sendNavKey(key) {
  if (navigator.vibrate) navigator.vibrate(15);
  textBox.focus();
  const start = textBox.selectionStart;
  const end = textBox.selectionEnd;

  if (key === 'left') {
    const newPos = getPrevCluster(textBox.value, start);
    textBox.setSelectionRange(newPos, newPos);
    scheduleSync();
  } else if (key === 'right') {
    const newPos = getNextCluster(textBox.value, start);
    textBox.setSelectionRange(newPos, newPos);
    scheduleSync();
  } else if (key === 'up' || key === 'down') {
    fetch('/api/send_key', {
      method: 'POST',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ key: key, count: 1 })
    }).catch(()=>{});
  } else if (key === 'backspace') {
    if (start !== end) {
      textBox.value = textBox.value.slice(0, start) + textBox.value.slice(end);
      textBox.setSelectionRange(start, start);
      scheduleSync();
    } else if (start > 0) {
      const prev = getPrevCluster(textBox.value, start);
      textBox.value = textBox.value.slice(0, prev) + textBox.value.slice(start);
      textBox.setSelectionRange(prev, prev);
      scheduleSync();
    } else {
      fetch('/api/send_key', {
        method: 'POST',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ key: 'backspace', count: 1 })
      }).catch(()=>{});
    }
  } else if (key === 'enter') {
    textBox.value = textBox.value.slice(0, start) + '\\n' + textBox.value.slice(start);
    textBox.setSelectionRange(start + 1, start + 1);
    scheduleSync();
  }
}

// Live Mode Toggle
function toggleLiveMode(enabled) {
  liveMode = enabled;
  const label = document.getElementById('liveLabel');
  const btnSend = document.getElementById('btnSend');

  if (liveMode) {
    label.innerText = '⚡ LIVE SYNC ON';
    label.style.color = '#10b981';
    btnSend.style.opacity = '0.7';
    if (!textBox.value) {
      fetch('/api/reset_sync', {
        method: 'POST',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' })
      }).catch(()=>{});
    } else {
      scheduleSync();
    }
    showToast('Live Sync ON (Mirrored on PC)');
  } else {
    label.innerText = '⚡ Live Mode';
    label.style.color = '#444444';
    btnSend.style.opacity = '1.0';
    showToast('Batch Mode (Use Send to PC)');
  }
}

// Send text from box to PC (Batch Mode Force)
function sendText() {
  const text = textBox.value;
  fetch('/api/paste_text', {
    method: 'POST',
    headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ text: text })
  })
  .then(res => {
    if (res.status === 401) {
      document.getElementById('lockOverlay').classList.add('active');
      throw new Error('Password required');
    }
    return res.json();
  })
  .then(() => {
    showToast('Pasted to PC!');
  })
  .catch(err => {
    if (err.message !== 'Password required') {
      showToast('Failed to reach PC', true);
    }
  });
}

// Check if PC requires password
async function checkAuthStatus() {
  try {
    const res = await fetch('/api/auth/status', {
      headers: getAuthHeaders()
    });
    const data = await res.json();
    if (data.password_required && !data.authenticated) {
      document.getElementById('lockOverlay').classList.add('active');
    } else {
      document.getElementById('lockOverlay').classList.remove('active');
    }
  } catch (err) {
    console.warn("Auth check failed:", err);
  }
}

async function submitPassword() {
  const pwdInput = document.getElementById('authPwd');
  const errEl = document.getElementById('lockError');
  const pwd = pwdInput.value.trim();
  errEl.style.display = 'none';

  if (!pwd) {
    errEl.innerText = 'Please enter a password';
    errEl.style.display = 'block';
    return;
  }

  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: pwd })
    });
    const data = await res.json();

    if (res.ok && data.token) {
      authToken = data.token;
      localStorage.setItem('vt_auth_token', authToken);
      document.getElementById('lockOverlay').classList.remove('active');
      pwdInput.value = '';
      showToast('Unlocked & Connected!');
      checkConnection();
      syncWithPC();
    } else {
      errEl.innerText = data.message || 'Incorrect password!';
      errEl.style.display = 'block';
      pwdInput.classList.add('shake');
      setTimeout(() => pwdInput.classList.remove('shake'), 400);
    }
  } catch (e) {
    errEl.innerText = 'Connection error. Try again.';
    errEl.style.display = 'block';
  }
}

// Microphone recording
async function toggleMic() {
  if (isRecording) {
    stopRecording();
  } else {
    startRecording();
  }
}

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioChunks = [];

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

    fetch('/api/sound', {
      method: 'POST',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ sound: 'start' })
    }).catch(()=>{});

  } catch (err) {
    document.getElementById('micBtn').classList.remove('recording');
    showToast('Mic permission needed: ' + err.message, true);
  }
}

function stopRecording() {
  if (mediaRecorder && isRecording) {
    isRecording = false;
    document.getElementById('micBtn').classList.remove('recording');
    mediaRecorder.stop();

    fetch('/api/sound', {
      method: 'POST',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ sound: 'stop' })
    }).catch(()=>{});
  }
}

async function uploadAudio(blob) {
  showToast('Transcribing with Gemini...');
  try {
    const res = await fetch('/api/transcribe_audio', {
      method: 'POST',
      headers: getAuthHeaders({
        'Content-Type': blob.type || 'audio/webm'
      }),
      body: blob
    });
    const data = await res.json();

    if (data.status === 'ok' && data.text) {
      showToast('Transcribed to PC!');
    } else {
      showToast('No speech detected', true);
    }
  } catch (err) {
    showToast('Upload error', true);
  }
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
checkAuthStatus();
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
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Auth-Token')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Auth-Token')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.close_connection = True

    def _is_authenticated(self) -> bool:
        server = getattr(self.server, 'app_server', None)
        if not server:
            return True
        return server.check_auth_header(self.headers)

    def do_GET(self):
        server = getattr(self.server, 'app_server', None)

        if self.path == '/' or self.path.startswith('/index'):
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
        elif self.path == '/api/auth/status':
            has_pwd = bool(server and server.password)
            authed = self._is_authenticated()
            self._send_json(200, {
                'status': 'ok',
                'password_required': has_pwd,
                'authenticated': authed
            })
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        server = getattr(self.server, 'app_server', None)
        if not server:
            self.send_error(500, "Server Error")
            return

        # 1. Login endpoint (Open)
        if self.path == '/api/auth/login':
            body_bytes = self.rfile.read(content_length)
            try:
                data = json.loads(body_bytes.decode('utf-8'))
                pwd = data.get('password', '').strip()
                if not server.password or pwd == server.password.strip():
                    token = server.generate_auth_token()
                    self._send_json(200, {'status': 'ok', 'token': token})
                else:
                    self._send_json(401, {'status': 'error', 'message': 'Incorrect Password!'})
            except Exception as e:
                self._send_json(400, {'status': 'error', 'message': str(e)})
            return

        # 2. Protected endpoints check
        if not self._is_authenticated():
            self._send_json(401, {'status': 'error', 'message': 'Password required / Unauthorized'})
            return

        # 3. Synchronize full text & cursor (Full bi-directional editing)
        if self.path == '/api/sync_text':
            body_bytes = self.rfile.read(content_length)
            try:
                data = json.loads(body_bytes.decode('utf-8'))
                text = data.get('text', '')
                cursor = int(data.get('cursor', len(text)))
                if server.on_sync_text:
                    server.on_sync_text(text, cursor)
                self._send_json(200, {'status': 'ok'})
            except Exception as e:
                self._send_json(400, {'status': 'error', 'message': str(e)})

        # 3b. Reset synchronization state
        elif self.path == '/api/reset_sync':
            if hasattr(server, 'on_reset_sync') and server.on_reset_sync:
                server.on_reset_sync()
            self._send_json(200, {'status': 'ok'})

        # 4. Batch paste text
        elif self.path == '/api/paste_text':
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

        # 5. Live input character/text
        elif self.path == '/api/live_input':
            body_bytes = self.rfile.read(content_length)
            try:
                data = json.loads(body_bytes.decode('utf-8'))
                text = data.get('text', '')
                if text:
                    if server.on_live_input:
                        server.on_live_input(text)
                    elif server.on_paste_text:
                        server.on_paste_text(text)
                self._send_json(200, {'status': 'ok'})
            except Exception as e:
                self._send_json(400, {'status': 'error', 'message': str(e)})

        # 6. Move cursor delta
        elif self.path == '/api/move_cursor':
            body_bytes = self.rfile.read(content_length)
            try:
                data = json.loads(body_bytes.decode('utf-8'))
                delta = int(data.get('delta', 0))
                if delta != 0 and server.on_move_cursor:
                    server.on_move_cursor(delta)
                self._send_json(200, {'status': 'ok'})
            except Exception as e:
                self._send_json(400, {'status': 'error', 'message': str(e)})

        # 7. Send special key (left, right, up, down, backspace, enter)
        elif self.path == '/api/send_key':
            body_bytes = self.rfile.read(content_length)
            try:
                data = json.loads(body_bytes.decode('utf-8'))
                key = data.get('key', '')
                count = int(data.get('count', 1))
                if key and server.on_special_key:
                    server.on_special_key(key, count=count)
                self._send_json(200, {'status': 'ok'})
            except Exception as e:
                self._send_json(400, {'status': 'error', 'message': str(e)})

        # 8. Audio transcription
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

        # 9. Play sound
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
    def __init__(
        self,
        http_port=8765,
        https_port=8766,
        on_paste_text=None,
        on_special_key=None,
        on_transcribe_audio=None,
        on_play_sound=None,
        on_live_input=None,
        on_move_cursor=None,
        on_sync_text=None,
        on_reset_sync=None,
        password=""
    ):
        self.http_port = http_port
        self.https_port = https_port
        self.on_paste_text = on_paste_text
        self.on_special_key = on_special_key
        self.on_transcribe_audio = on_transcribe_audio
        self.on_play_sound = on_play_sound
        self.on_live_input = on_live_input
        self.on_move_cursor = on_move_cursor
        self.on_sync_text = on_sync_text
        self.on_reset_sync = on_reset_sync
        self.password = (password or "").strip()
        self.valid_tokens = set()

        self.local_ip = get_local_ip()
        self.http_server = None
        self.https_server = None
        self.http_thread = None
        self.https_thread = None
        self.is_running = False
        self.tunnel_manager = None

    def set_password(self, new_password: str):
        self.password = (new_password or "").strip()
        self.valid_tokens.clear()
        logging.info("Phone access password updated.")

    def generate_auth_token(self) -> str:
        token = secrets.token_hex(16)
        self.valid_tokens.add(token)
        return token

    def check_auth_header(self, headers) -> bool:
        if not self.password:
            return True
        auth_hdr = headers.get('Authorization', '')
        token = ""
        if auth_hdr.startswith('Bearer '):
            token = auth_hdr[7:].strip()
        if not token:
            token = headers.get('X-Auth-Token', '').strip()
        return token in self.valid_tokens

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
        self.tunnel_manager = TunnelManager(local_port=self.http_port)
        try:
            self.start_tunnel()
        except Exception as e:
            logging.warning(f"Could not pre-warm tunnel: {e}")

    def start_tunnel(self, on_url_ready=None, on_status_change=None):
        if not self.tunnel_manager:
            self.tunnel_manager = TunnelManager(local_port=self.http_port)
        if on_url_ready:
            self.tunnel_manager.on_url_ready = on_url_ready
        if on_status_change:
            self.tunnel_manager.on_status_change = on_status_change
        self.tunnel_manager.start()

    def stop_tunnel(self):
        if self.tunnel_manager:
            self.tunnel_manager.stop()

    def get_tunnel_url(self):
        if self.tunnel_manager:
            return self.tunnel_manager.get_url()
        return None

    def stop(self):
        self.is_running = False
        if self.tunnel_manager:
            try:
                self.tunnel_manager.stop()
            except Exception:
                pass
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
