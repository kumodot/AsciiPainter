@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem ==============================================================
rem  ASCII Painter - single .exe build (onefile, windowed)
rem  Output: dist\ASCII_Painter_v<VERSION>.exe
rem  Saves go to a "saves" folder next to the .exe.
rem  Single-file exes start slower and trigger more antivirus warnings
rem  than the folder build (build_release.bat).
rem ==============================================================
set "APP_NAME=ASCII_Painter"

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

set "MAIN="
for /f "delims=" %%F in ('dir /b /o:n "ASCIIPAINT_v*.py" 2^>nul') do set "MAIN=%%F"
if not defined MAIN (
  echo ERROR: no ASCIIPAINT_v*.py found in this folder.
  exit /b 1
)

set "VERSION="
for /f "delims=" %%V in ('%PY% tools\get_version.py %MAIN%') do set "VERSION=%%V"
if not defined VERSION set "VERSION=dev"

echo Building %APP_NAME%_v%VERSION%.exe from %MAIN% ...

"%PY%" -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
  echo Installing requirements and PyInstaller...
  "%PY%" -m pip install -r requirements.txt pyinstaller
  if errorlevel 1 (
    echo ERROR: pip failed.
    exit /b 1
  )
)

if exist build rmdir /s /q build

"%PY%" -m PyInstaller --noconfirm --clean --onefile --noupx --noconsole ^
  --name "%APP_NAME%_v%VERSION%" ^
  --icon "%CD%\assets\icon.ico" ^
  --add-data "%CD%\assets;assets" ^
  --distpath "%CD%\dist" --workpath "%CD%\build\work" --specpath "%CD%\build" ^
  "%CD%\%MAIN%"
if errorlevel 1 (
  echo ERROR: build failed.
  exit /b 1
)

echo.
echo OK: dist\%APP_NAME%_v%VERSION%.exe
endlocal
