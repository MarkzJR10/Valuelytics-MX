@echo off
title Detener Valuelytics MX
chcp 65001 >nul
echo Buscando y deteniendo el proceso de Valuelytics MX (main.py)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | ForEach-Object { if ($_.CommandLine -like '*main.py*') { Stop-Process -Id $_.ProcessId -Force } }" >nul 2>&1
echo.
echo === Valuelytics MX detenido correctamente ===
echo.
pause
