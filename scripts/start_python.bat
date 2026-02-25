@echo off
:: ClawDBot – Python LLM szerver indítása

echo === ClawDBot Python LLM Szerver ===
echo.

cd /d "%~dp0..\python_llm"

:: Venv ellenőrzése
if not exist ".venv\Scripts\activate.bat" (
    echo [HIBA] A virtualis kornyezet nem letezik!
    echo Futtasd elobb: scripts\install_python.bat
    pause
    exit /b 1
)

:: .env betöltése (javított elérési út)
if exist "..\\.env" (
    for /f "usebackq tokens=1,* delims==" %%A in ("..\\.env") do (
        if not "%%A"=="" set "%%A=%%B"
    )
)

:: Virtuális környezet aktiválása
call .venv\Scripts\activate.bat

echo GPU-k detektálása...
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, GPU-k: {torch.cuda.device_count()}')"

echo.
echo Python LLM szerver indul: http://0.0.0.0:%LLM_PORT%
echo Modell: %MODEL_NAME%
echo.

python model_server.py

pause
