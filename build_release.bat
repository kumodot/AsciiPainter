@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem ==============================================================
rem  ASCII Painter - safe release build (onedir, no UPX, windowed)
rem  Output: releases\ASCII_Painter_v<VERSION>_build\
rem  Tip: zip that folder before sharing (antivirus is happier with zips).
rem  PAL.txt is copied next to the .exe: edit it there to change palettes.
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

echo Building %APP_NAME% v%VERSION% from %MAIN% ...

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

"%PY%" -m PyInstaller --noconfirm --clean --onedir --noupx --noconsole ^
  --name "%APP_NAME%" ^
  --icon "%CD%\assets\icon.ico" ^
  --add-data "%CD%\assets;assets" ^
  --distpath "%CD%\build\dist" --workpath "%CD%\build\work" --specpath "%CD%\build" ^
  "%CD%\%MAIN%"
if errorlevel 1 (
  echo ERROR: build failed.
  exit /b 1
)

set "OUTDIR=releases\%APP_NAME%_v%VERSION%_build"
if not exist releases mkdir releases
if exist "%OUTDIR%" rmdir /s /q "%OUTDIR%"
xcopy /e /i /y "build\dist\%APP_NAME%" "%OUTDIR%" >nul
copy /y "assets\PAL.txt" "%OUTDIR%\PAL.txt" >nul

echo.
echo OK: %OUTDIR%\%APP_NAME%.exe
endlocal
