@echo off
cd /d "%~dp0"
title Universal Voice Typer (Gemini)
chcp 65001 >nul
echo ========================================================
echo          UNIVERSAL VOICE TYPER (GEMINI FLASH)
echo ========================================================
echo.
".venv\Scripts\python.exe" app.py
if errorlevel 1 (
    echo.
    echo [!] ???? ?????? ?????? ????????? ???? ??????
    pause
)
