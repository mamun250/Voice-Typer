# 🎙️ Voice Typer (AI-Powered System-Wide Voice Typing)

A lightweight, powerful Windows desktop utility for fast and accurate voice typing into **any** application (Notepad, MS Word, Google Docs, Browser, Messaging apps, Search bar, etc.) powered by Google's latest **Gemini 3.5 Flash Lite** model.

Supports **Bengali**, **English**, **Hindi**, **Arabic**, and **Universal Auto-Detection**.

---

## ✨ Features

- ⚡ **Ultra-Fast & Accurate**: Powered by Gemini 3.5 Flash Lite with ~1.5–2s response latency.
- 🎯 **System-Wide Universal Typing**: Type directly wherever your mouse cursor is focused.
- 📱 **Phone as Microphone (QR Code)**: Don't have a PC microphone? Simply scan the QR code from your phone to speak or type directly into your PC!
- 🌊 **Live Dynamic Audio Waveform**: Real-time visual feedback of speech frequency and amplitude.
- ⌨️ **Global Hotkeys**:
  - F8 (Toggle recording)
  - Ctrl + Shift + Space
  - Ctrl + Alt + V
- 🔔 **Crystal Clear Sound Feedback**:
  - Double-Pip chime on record start
  - Descending tone on record stop
  - Sweet success chime on text paste
- 💻 **System Tray Integration**: Runs quietly in the background without cluttering the screen.
- 🛠️ **Full Settings Dialog**: Select microphone, configure language, change model, or set API keys anytime.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- A free Google Gemini API Key from [Google AI Studio](https://aistudio.google.com/app/apikey)

### Installation

1. Clone the repository:
   `ash
   git clone https://github.com/mamun250/Voice-Typer.git
   cd Voice-Typer
   `

2. Create and activate a virtual environment:
   `ash
   python -m venv .venv
   .venv\Scripts\activate
   `

3. Install dependencies:
   `ash
   pip install -r requirements.txt
   `

4. Configure your Gemini API Key:
   - Copy .env.example to .env:
     `ash
     cp .env.example .env
     `
   - Add your API Key into .env:
     `env
     GEMINI_API_KEY=your_gemini_api_key_here
     `

5. Run Voice Typer:
   `ash
   python app.py
   `

---

## 📦 Building Standalone Executable & Installer

- Build Portable .exe:
  `ash
  python build_exe.py
  `
- Build Windows Installer (Inno Setup):
  `ash
  ISCC.exe installer.iss
  `

---

## 📜 License
MIT License. Free for personal and commercial use.
