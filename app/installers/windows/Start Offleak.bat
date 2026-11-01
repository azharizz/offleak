@echo off
rem Starts the Offleak controller (local worker + setup dock) and opens the dock in your browser.
cd /d "%~dp0"
if not exist "python\python.exe" (
  echo Offleak is not set up yet. Run the Offleak installer again.
  pause
  exit /b 1
)
title Offleak
echo Offleak is running. Keep this window open while streaming; close it to stop.
"python\python.exe" -m offleak.obs.controller --open-dock
pause
