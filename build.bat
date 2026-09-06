@echo off
cd /d "%~dp0"
title Building VoiceTyper.exe
chcp 65001 >nul
echo Building Standalone VoiceTyper.exe...
echo.
".venv\Scripts\python.exe" build_exe.py
pause
