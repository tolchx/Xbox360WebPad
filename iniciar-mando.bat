@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul 2>&1
title Xbox 360 WebPad - mando virtual
cd /d "%~dp0"

rem  El runtime portable trae su propio Python: que no se mezcle con el del sistema.
set "PYTHONNOUSERSITE=1"

set "PUERTO=8790"
set "REINSTALAR=0"

rem ------------------------------------------------------------------
rem  Argumentos
rem ------------------------------------------------------------------
:args
if "%~1"=="" goto finargs
if /i "%~1"=="--reinstalar" goto arg_reinstalar
if /i "%~1"=="--help" goto ayuda
if /i "%~1"=="-h" goto ayuda
set "PUERTO=%~1"
shift
goto args

:arg_reinstalar
set "REINSTALAR=1"
shift
goto args

:finargs

echo.
echo  ==============================================================
echo    XBOX 360 WEBPAD  -  mando virtual por celular
echo    Corre en esta PC, en paralelo al juego.
echo  ==============================================================
echo.

rem ------------------------------------------------------------------
rem  1) Driver ViGEmBus - el que hace aparecer el mando Xbox 360
rem ------------------------------------------------------------------
reg query "HKLM\SYSTEM\CurrentControlSet\Services\ViGEmBus" >nul 2>&1
if not errorlevel 1 goto driver_ok

echo   [1/4] Driver ViGEmBus: NO esta instalado.
echo         Se instala ahora. Windows va a pedir permiso de administrador.

set "DRVEXE="
for %%F in ("drivers\ViGEmBus*.exe") do if exist "%%~fF" set "DRVEXE=%%~fF"
if not defined DRVEXE goto driver_winget

echo         Usando el instalador incluido en la carpeta drivers ...
powershell -NoProfile -Command "$p = Start-Process -Verb RunAs -PassThru -FilePath '!DRVEXE!' -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-'; try { Wait-Process -Id $p.Id -Timeout 180 -ErrorAction Stop } catch { }"
reg query "HKLM\SYSTEM\CurrentControlSet\Services\ViGEmBus" >nul 2>&1
if not errorlevel 1 goto driver_verificar
echo         El instalador silencioso no termino: se abre el asistente.
echo         Completa los pasos y despues volve a correr este .bat.
powershell -NoProfile -Command "Start-Process -Verb RunAs -Wait -FilePath '!DRVEXE!'"
goto driver_verificar

:driver_winget
echo         No hay instalador incluido: se baja el driver con winget...
powershell -NoProfile -Command "Start-Process -Verb RunAs -Wait -FilePath winget -ArgumentList 'install','--id','ViGEm.ViGEmBus','-e','--accept-package-agreements','--accept-source-agreements'"

:driver_verificar
reg query "HKLM\SYSTEM\CurrentControlSet\Services\ViGEmBus" >nul 2>&1
if not errorlevel 1 goto driver_ok
echo.
echo   ERROR: el driver ViGEmBus sigue sin estar instalado.
echo   Correlo de nuevo con boton derecho - Ejecutar como administrador,
echo   o instalalo a mano desde:
echo        https://github.com/nefarius/ViGEmBus/releases
echo.
pause
exit /b 1

:driver_ok
echo   [1/4] Driver ViGEmBus: OK

rem  Aviso de version: la 1.17 de 2020 devuelve basura en la primera lectura de
rem  cada proceso. La 1.22 es la estable.
set "VERDRV="
for /f "usebackq tokens=*" %%V in (`powershell -NoProfile -Command "(Get-Item C:\Windows\System32\drivers\ViGEmBus.sys -ErrorAction SilentlyContinue).VersionInfo.FileVersion"`) do set "VERDRV=%%V"
if not defined VERDRV goto firewall
echo         Version del driver: !VERDRV!
if "!VERDRV:~0,4!"=="1.22" goto firewall
echo         NOTA: la version estable es la 1.22. Para actualizar:
echo               winget upgrade --id ViGEm.ViGEmBus -e
echo         Es opcional: el mando funciona igual.

rem ------------------------------------------------------------------
rem  2) Regla de firewall - para que el celular pueda entrar
rem ------------------------------------------------------------------
:firewall
netsh advfirewall firewall show rule name=Xbox360WebPad >nul 2>&1
if not errorlevel 1 goto firewall_ok

echo   [2/4] Abriendo el puerto %PUERTO% en el firewall. Pide permiso de admin.
powershell -NoProfile -Command "$p = Start-Process -Verb RunAs -PassThru -WindowStyle Hidden -FilePath netsh -ArgumentList 'advfirewall','firewall','add','rule','name=Xbox360WebPad','dir=in','action=allow','protocol=TCP','localport=%PUERTO%','profile=private,domain'; try { Wait-Process -Id $p.Id -Timeout 90 -ErrorAction Stop } catch { }" >nul 2>&1
netsh advfirewall firewall show rule name=Xbox360WebPad >nul 2>&1
if not errorlevel 1 goto firewall_creada
echo         NOTA: no se pudo crear la regla. Si el celular no conecta,
echo               corre este .bat con boton derecho - Ejecutar como administrador.
goto runtime

:firewall_creada
echo         Regla de firewall creada para el puerto %PUERTO%.
goto runtime

:firewall_ok
echo   [2/4] Regla de firewall: OK

rem ------------------------------------------------------------------
rem  3) Python y dependencias
rem     a) runtime portable incluido: no se instala nada
rem     b) si no esta, se arma un entorno con el Python del sistema
rem ------------------------------------------------------------------
:runtime
if exist "runtime\python\python.exe" goto runtime_portable

set "PYCMD="
for %%V in (3.12 3.13 3.11 3) do (
  if not defined PYCMD py -%%V --version >nul 2>&1 && set "PYCMD=py -%%V"
)
if defined PYCMD goto runtime_tengo_python
python --version >nul 2>&1 && set "PYCMD=python"
if defined PYCMD goto runtime_tengo_python

echo   [3/4] Python no encontrado. Se instala Python 3.12 con winget...
powershell -NoProfile -Command "Start-Process -Verb RunAs -Wait -FilePath winget -ArgumentList 'install','--id','Python.Python.3.12','-e','--accept-package-agreements','--accept-source-agreements'"
set "PYCMD=py -3.12"
py -3.12 --version >nul 2>&1
if not errorlevel 1 goto runtime_tengo_python
echo.
echo   ERROR: Python no esta disponible. Instalalo desde python.org
echo          marca la opcion "Add python.exe to PATH" y volve a intentar.
echo.
pause
exit /b 1

:runtime_tengo_python
if "%REINSTALAR%"=="1" if exist ".venv\.deps-ok" del /q ".venv\.deps-ok" >nul 2>&1
if exist ".venv\Scripts\python.exe" goto runtime_venv_listo
echo   [3/4] Creando el entorno de Python .venv ... una sola vez.
%PYCMD% -m venv .venv
if not errorlevel 1 goto runtime_venv_listo
echo   ERROR: no se pudo crear el entorno virtual de Python.
pause
exit /b 1

:runtime_venv_listo
if exist ".venv\.deps-ok" goto runtime_deps_ok
echo   [3/4] Instalando dependencias: aiohttp, vgamepad, qrcode ...
if exist "wheels\" goto runtime_con_wheels
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
set "PIPERR=%errorlevel%"
goto runtime_deps_verificar

:runtime_con_wheels
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q --find-links wheels -r requirements.txt
set "PIPERR=%errorlevel%"

:runtime_deps_verificar
if not "%PIPERR%"=="0" goto runtime_deps_error
echo ok> ".venv\.deps-ok"
echo         Dependencias listas.
goto runtime_listo

:runtime_deps_error
echo.
echo   ERROR: no se pudieron instalar las dependencias.
echo   Revisa la conexion a internet y volve a intentar.
echo.
pause
exit /b 1

:runtime_deps_ok
echo   [3/4] Dependencias: OK

:runtime_listo
set "PYEXE=%~dp0.venv\Scripts\python.exe"
goto arrancar

:runtime_portable
set "PYEXE=%~dp0runtime\python\python.exe"
echo   [3/4] Python portable incluido: OK - no hay que instalar nada

rem ------------------------------------------------------------------
rem  4) Servidor + mando virtual
rem ------------------------------------------------------------------
:arrancar
echo   [4/4] Revisando el puerto MIDI (para Resolume / QLC+)...
"%PYEXE%" tools\midi_listo.py
echo.
echo   Arrancando el servidor en el puerto %PUERTO%...
echo.
echo   Deja esta ventana abierta mientras jugas, podes minimizarla.
echo   Ctrl+C para salir.
echo.

"%PYEXE%" server.py --port %PUERTO% --open
echo.
echo  Servidor detenido.
echo.
pause
exit /b 0

:ayuda
echo.
echo  Uso:  iniciar-mando.bat [puerto] [--reinstalar]
echo.
echo    puerto         puerto del servidor, por defecto 8790
echo    --reinstalar   vuelve a instalar las dependencias de Python
echo.
echo  El mando web queda en  http://IP-DE-ESTA-PC:PUERTO/pad
echo  El panel con el QR queda en  http://127.0.0.1:PUERTO/
echo.
echo  Si existe la carpeta runtime\python se usa ese Python portable y no
echo  hace falta tener Python instalado en la maquina.
echo.
pause
exit /b 0
