@echo off
setlocal
cd /d "%~dp0"

echo Creating virtual environment...
py -3 -m venv .venv
if errorlevel 1 goto fail

echo Installing requirements...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 goto fail

echo Building portable EXE...
pyinstaller --noconfirm --clean --onefile --windowed --name ZunioBooks app.py
if errorlevel 1 goto fail

echo.
echo Build complete.
echo EXE location: dist\ZunioBooks.exe
echo.
pause
exit /b 0

:fail
echo.
echo Build failed.
pause
exit /b 1
