@echo off
:: ClawDBot – Chat terminál indítása

title ClawDBot - Chat

cd /d "%~dp0..\python_llm"

:: Venv ellenőrzése
if not exist ".venv\Scripts\activate.bat" (
    echo [HIBA] A virtualis kornyezet nem letezik!
    echo Futtasd elobb: scripts\install_python.bat
    pause
    exit /b 1
)

:: Virtuális környezet aktiválása
call .venv\Scripts\activate.bat

:: websockets ellenőrzése
python -c "import websockets" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo websockets telepítése...
    pip install websockets>=12.0 -q
)

:: Chat kliens indítása (belsőleg megvárja a szervert)
python chat_cli.py

pause
