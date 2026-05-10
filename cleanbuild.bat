@echo off
echo Cleaning build artifacts...
if exist dist rd /s /q dist
if exist build rd /s /q build
for /d %%d in (__pycache__) do rd /s /q "%%d" 2>nul
del /f /q *.spec 2>nul
del /f /q *.pyc 2>nul
del /f /q main_build.py 2>nul
echo.
echo Done. Run build.bat to rebuild.
pause
