@echo off
chcp 65001 >nul
title Fantasy-Assistent
cd /d "%~dp0"

where uv >/dev/null 2>nul
if errorlevel 1 (
  echo.
  echo  Das Programm "uv" ist noch nicht installiert.
  echo  Bitte README.md lesen, Schritt 2: uv installieren.
  echo.
  pause
  exit /b 1
)

if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo  Einstellungsdatei .env wurde angelegt.
)

echo  Starte den Fantasy-Assistenten ... (beim ersten Mal dauert es 1-2 Minuten)
uv run fantasy
echo.
pause
