@echo off
setlocal
python -m pip install --upgrade pip
python -m pip install -r requirements-v3.txt pyinstaller
pyinstaller --noconfirm --clean --windowed --name UniversalConverter app_v3.py
if errorlevel 1 (
  echo Build failed.
  exit /b 1
)
echo.
echo Build complete: dist\UniversalConverter\UniversalConverter.exe
