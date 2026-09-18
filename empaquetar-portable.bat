@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1
title Xbox 360 WebPad - empaquetar portable
cd /d "%~dp0"

echo.
echo  ==============================================================
echo    Empaquetar Xbox 360 WebPad como carpeta portable
echo    (Python + dependencias + driver, sin instalar nada)
echo  ==============================================================
echo.

set "PYCMD="
for %%V in (3.12 3.13 3.11 3) do (
  if not defined PYCMD (
    py -%%V --version >nul 2>&1 && set "PYCMD=py -%%V"
  )
)
if not defined PYCMD (
  python --version >nul 2>&1 && set "PYCMD=python"
)
if not defined PYCMD (
  echo  Necesito un Python instalado para armar el paquete.
  echo  Instalalo desde python.org ^(marca "Add python.exe to PATH"^).
  pause
  exit /b 1
)

%PYCMD% tools\empaquetar_portable.py %*
echo.
pause
