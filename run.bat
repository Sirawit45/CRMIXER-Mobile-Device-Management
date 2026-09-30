@echo off
title CRMIXER Mobile Device Management v0.5.4
cd /d "%~dp0"

python desktop_app.py

if %ERRORLEVEL% NEQ 0 (
    echo [Fallback] Starting Web Launcher mode...
    python start.py
)
