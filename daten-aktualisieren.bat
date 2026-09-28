@echo off
chcp 65001 >nul
title Fantasy-Assistent: Daten aktualisieren
cd /d "%~dp0"

where uv >/dev/null 2>nul
if errorlevel 1 (
  echo  Das Programm "uv" ist noch nicht installiert. Siehe README.md, Schritt 2.
  pause
  exit /b 1
)

uv run fantasy update-data
echo.
pause
