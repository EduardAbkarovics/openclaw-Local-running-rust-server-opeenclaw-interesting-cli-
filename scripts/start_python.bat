@echo off
:: ClawDBot – Python LLM szerver indítása

echo === ClawDBot Python LLM Szerver ===
echo.

cd /d "E:\openclaw_server_hosting\python_llm"

:: ── HF cache: W: meghajtón lévő models\ mappájába ────────────────────────────
set HF_HOME=W:\openclaw_server_hosting\models
set HF_HUB_CACHE=W:\openclaw_server_hosting\models
set HF_DATASETS_CACHE=W:\openclaw_server_hosting\models
set HUGGINGFACE_HUB_CACHE=W:\openclaw_server_hosting\models
set TRANSFORMERS_CACHE=W:\openclaw_server_hosting\models
set PIP_CACHE_DIR=W:\pip_cache
set TMPDIR=W:\tmp
set TEMP=W:\tmp
set TMP=W:\tmp
echo HF cache: %HF_HOME%

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
