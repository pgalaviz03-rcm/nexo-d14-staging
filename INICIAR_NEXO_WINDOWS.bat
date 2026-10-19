@echo off
setlocal
chcp 65001 >nul
title NEXO D14 - Servidor local
cd /d "%~dp0"
set "PYTHONUTF8=1"
if not exist "app\main.py" (
  echo Extrae primero todo el ZIP de NEXO a una carpeta.
  goto :finish
)
if defined NEXO_PYTHON_EXE goto :check_python
if exist ".venv\Scripts\python.exe" (
  set "NEXO_PYTHON_EXE=%CD%\.venv\Scripts\python.exe"
  goto :check_python
)
where py >nul 2>&1
if errorlevel 1 (
  echo No se encontro Python instalado. El acceso de Windows a la tienda no sirve para ejecutar NEXO.
  echo En esta computadora usa ABRIR_NEXO_LOCAL.bat, junto al paquete extraido.
  echo En otra computadora instala Python 3.12 desde https://www.python.org/downloads/ y vuelve a abrir este archivo.
  goto :finish
)
py -3.12 -m venv .venv
if errorlevel 1 goto :setup_error
set "NEXO_PYTHON_EXE=%CD%\.venv\Scripts\python.exe"
:check_python
if not exist "%NEXO_PYTHON_EXE%" goto :setup_error
"%NEXO_PYTHON_EXE%" -c "import fastapi,uvicorn,sqlalchemy,dotenv" >nul 2>&1
if errorlevel 1 (
  echo Preparando dependencias de NEXO. La primera vez requiere Internet.
  "%NEXO_PYTHON_EXE%" -m pip install -r requirements.txt
  if errorlevel 1 goto :setup_error
)
echo.
echo NEXO D14 - COPIA LOCAL EN ESTA COMPUTADORA
echo Conserva esta ventana abierta mientras usas NEXO.
echo En el primer inicio apareceran aqui el usuario y la clave local. Guardalos de forma privada.
echo.
"%NEXO_PYTHON_EXE%" -u iniciar.py
goto :finish
:setup_error
echo No fue posible preparar Python o las dependencias. Conserva el mensaje de error para revisarlo.
:finish
pause
endlocal
