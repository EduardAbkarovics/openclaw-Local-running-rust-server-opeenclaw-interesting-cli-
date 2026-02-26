@echo off
:: OpenClaw DeepSeek R1 indítás
:: Modell (agy) = DeepSeek R1, W: meghajtóra töltve
:: Composer = OpenClaw (Rust szerver)
:: 12 GB GPU: DeepSeek-R1-Distill-Qwen-7B

echo === OpenClaw + DeepSeek R1 ^(W: meghajto^) ===
echo Agy: DeepSeek R1 modell, Composer: OpenClaw
echo.

:: W: meghajtó – modell cache
set "HF_HOME=W:\openclaw_server_hosting\models"
set "HF_HUB_CACHE=%HF_HOME%"
set "HF_DATASETS_CACHE=%HF_HOME%"
set "HUGGINGFACE_HUB_CACHE=%HF_HOME%"
set "TRANSFORMERS_CACHE=%HF_HOME%"
set "PIP_CACHE_DIR=W:\pip_cache"
set "TMPDIR=W:\tmp"
set "TEMP=W:\tmp"
set "TMP=W:\tmp"

:: .env betöltése (ha van), majd DeepSeek R1 felülírja a MODEL_NAME-t
if exist "%~dp0..\.env" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%~dp0..\.env") do (
        if not "%%A"=="" set "%%A=%%B"
    )
)
set "MODEL_NAME=deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"
set "LOAD_IN_4BIT=1"
set "LLM_PORT=8000"
set "LLM_HOST=0.0.0.0"
:: Composer = OpenClaw bot ^(Rust szerver + chat neve^)
set "CLAWDBOT_BOT_NAME=OpenClaw"

echo HF cache: %HF_HOME%
echo Modell: %MODEL_NAME%
echo.

:: Windows Terminal vagy sima CMD ablakok (a gyerek process örökli a környezetet)
where wt >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Windows Terminal – 4 tab: DeepSeek R1 ^(agy^), OpenClaw ^(composer^), Chat UI, OpenClaw Gateway
    start "" wt --maximized new-tab --title "DeepSeek R1 (agy)" cmd /k "%~dp0start_python_deepseek_r1.bat"
    timeout /t 2 /nobreak >nul
    start "" wt -w 0 new-tab --title "OpenClaw (composer)" cmd /k "%~dp0start_rust.bat"
    timeout /t 1 /nobreak >nul
    start "" wt -w 0 new-tab --title "OpenClaw Chat" cmd /k "%~dp0start_chat.bat"
    timeout /t 1 /nobreak >nul
    start "" wt -w 0 new-tab --title "OpenClaw Gateway" cmd /k "openclaw gateway"
    exit
)

echo Windows Terminal nem elerheto – normal ablakok...
start "DeepSeek R1 (agy)" cmd /k "%~dp0start_python_deepseek_r1.bat"
timeout /t 2 /nobreak >nul
start "OpenClaw (composer)" cmd /k "%~dp0start_rust.bat"
timeout /t 1 /nobreak >nul
start "OpenClaw Chat" cmd /k "%~dp0start_chat.bat"
timeout /t 1 /nobreak >nul
start "OpenClaw Gateway" cmd /k "openclaw gateway"
exit
