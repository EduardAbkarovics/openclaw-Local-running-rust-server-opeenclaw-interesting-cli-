@echo off
:: Python LLM szerver – DeepSeek R1, W: meghajtóra
:: (start_openclaw_deepseek_r1.bat hívja; agy = ez a modell)

echo === DeepSeek R1 (agy) – Python LLM ===
echo.

cd /d "%~dp0..\python_llm"

set "HF_HOME=W:\openclaw_server_hosting\models"
set "HF_HUB_CACHE=%HF_HOME%"
set "HF_DATASETS_CACHE=%HF_HOME%"
set "HUGGINGFACE_HUB_CACHE=%HF_HOME%"
set "TRANSFORMERS_CACHE=%HF_HOME%"
set "PIP_CACHE_DIR=W:\pip_cache"
set "TMPDIR=W:\tmp"
set "TEMP=W:\tmp"
set "TMP=W:\tmp"

if exist "..\.env" (
    for /f "usebackq tokens=1,* delims==" %%A in ("..\.env") do (
        if not "%%A"=="" set "%%A=%%B"
    )
)
:: DeepSeek R1 mindig felülírja a .env MODEL_NAME-t (12 GB GPU)
set "MODEL_NAME=deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"
set "LOAD_IN_4BIT=1"
set "LLM_PORT=8000"
set "LLM_HOST=0.0.0.0"

echo HF cache: %HF_HOME%
echo Modell: %MODEL_NAME%
echo.

if not exist ".venv\Scripts\activate.bat" (
    echo [HIBA] Virtualis kornyezet hianyzik. Futtasd: scripts\install_python.bat
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, GPU-k: {torch.cuda.device_count()}')"
echo.
echo LLM szerver: http://%LLM_HOST%:%LLM_PORT%
echo.
python model_server.py
pause
