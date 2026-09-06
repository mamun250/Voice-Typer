@echo off
cd /d "%~dp0"
chcp 65001 >nul
".venv\Scripts\python.exe" test_mic_and_transcribe.py
