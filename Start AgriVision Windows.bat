@echo off
setlocal
cd /d "%~dp0"

where docker >nul 2>nul
if errorlevel 1 (
  echo Docker Desktop is not installed or docker is not on PATH.
  echo Install Docker Desktop, start it, then run this launcher again.
  pause
  exit /b 1
)

docker info >nul 2>nul
if errorlevel 1 (
  echo Docker Desktop is installed but not running.
  echo Start Docker Desktop, wait until it says Docker is running, then try again.
  pause
  exit /b 1
)

echo Starting AgriVision dashboard...
docker compose up --build -d
if errorlevel 1 (
  echo Failed to start AgriVision with docker compose.
  pause
  exit /b 1
)

echo Starting host service helper...
start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0scripts\service-helper-windows.ps1"

echo Opening AgriVision at http://127.0.0.1:8008
start "" "http://127.0.0.1:8008"
exit /b 0
