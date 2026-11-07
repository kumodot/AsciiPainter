@echo off
rem Quick test: runs the newest ASCIIPAINT_v*.py from this folder.
cd /d "%~dp0"

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

set "MAIN="
for /f "delims=" %%F in ('dir /b /o:n "ASCIIPAINT_v*.py" 2^>nul') do set "MAIN=%%F"
if not defined MAIN (
  echo ERROR: no ASCIIPAINT_v*.py found in this folder.
  pause
  exit /b 1
)

"%PY%" -c "import pygame, numpy, PIL" >nul 2>nul
if errorlevel 1 (
  echo Installing requirements...
  "%PY%" -m pip install -r requirements.txt
)

echo Running %MAIN% ...
"%PY%" "%MAIN%"
if errorlevel 1 pause
