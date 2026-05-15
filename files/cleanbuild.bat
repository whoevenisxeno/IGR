@echo off
echo Cleaning build artifacts...
if exist dist rd /s /q dist
if exist build rd /s /q build
if exist obf_dist rd /s /q obf_dist
for /r "." /d %%d in (__pycache__) do if exist "%%d" rd /s /q "%%d" 2>nul
del /f /q *.spec 2>nul
del /f /q *.pyc 2>nul
del /f /q main_build.py 2>nul
del /f /q obf_main.py 2>nul
echo.
echo Done. Run build.bat to rebuild.
pause
