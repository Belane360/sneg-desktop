@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -3.12 -m venv .venv
if errorlevel 1 goto error
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto error
.venv\Scripts\python.exe main.py
if errorlevel 1 goto error
exit /b 0
:error
echo Не удалось запустить приложение. Проверьте Python 3.12 и доступ к интернету.
pause
exit /b 1
