@echo off
:: ClawDBot – Python függőségek telepítése
:: PyTorch CUDA 12.1  |  Python 3.12 szükséges (3.13+ nem támogatott!)

echo === ClawDBot Python telepítő ===
echo.

cd /d "%~dp0..\python_llm"

:: ── Python verzió ellenőrzése ────────────────────────────────────────────────
echo Python verzió ellenőrzése...
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo   Talált Python: %PYVER%

for /f "tokens=1,2 delims=." %%a in ("%PYVER%") do (
    set PYMAJ=%%a
    set PYMIN=%%b
)

:: Python 3.13+ esetén PyTorch CUDA nem elérhető - 3.12 kell
if %PYMIN% GEQ 13 (
    echo.
    echo [FIGYELEM] Python %PYVER% - PyTorch CUDA csak 3.9-3.12-ig tamogatott!
    echo            A GPU NEM fog mukodni ezzel a verzióval.
    echo.
    echo Megprobalok Python 3.12-t hasznalni a venvhez...
    where py >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        py -3.12 --version >nul 2>&1
        if %ERRORLEVEL% EQU 0 (
            echo [OK] Python 3.12 talalhato - ezt hasznalom.
            set PYTHON_CMD=py -3.12
            goto :create_venv
        )
        py -3.11 --version >nul 2>&1
        if %ERRORLEVEL% EQU 0 (
            echo [OK] Python 3.11 talalhato - ezt hasznalom.
            set PYTHON_CMD=py -3.11
            goto :create_venv
        )
    )
    echo.
    echo [HIBA] Python 3.11 vagy 3.12 nem talalhato!
    echo Telepitsd: https://www.python.org/downloads/release/python-3120/
    echo            es valaszd: "Add to PATH" + "py launcher"
    pause
    exit /b 1
) else (
    set PYTHON_CMD=python
)

:create_venv
:: ── Venv létrehozása ─────────────────────────────────────────────────────────
if exist ".venv" (
    echo [!] Régi .venv törlése...
    rmdir /s /q .venv
)
echo [1/3] Virtuális környezet létrehozása (%PYTHON_CMD%)...
%PYTHON_CMD% -m venv .venv
if %ERRORLEVEL% NEQ 0 (
    echo [HIBA] Venv létrehozása sikertelen!
    pause
    exit /b 1
)

:: ── Aktiválás ────────────────────────────────────────────────────────────────
call .venv\Scripts\activate.bat

:: ── Cache W: meghajtóra ──────────────────────────────────────────────────────
set PIP_CACHE_DIR=W:\pip_cache
set TMPDIR=W:\tmp
set TEMP=W:\tmp
set TMP=W:\tmp

:: ── PyTorch CUDA telepítése ──────────────────────────────────────────────────
echo [2/3] PyTorch CUDA 12.1 telepítése...
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

:: CUDA ellenőrzés
python -c "import torch; ok=torch.cuda.is_available(); print(f'  CUDA: {ok}  |  GPU-k: {torch.cuda.device_count()}')"
if %ERRORLEVEL% NEQ 0 (
    echo [FIGYELEM] CUDA ellenőrzés sikertelen!
)

:: ── Egyéb függőségek ─────────────────────────────────────────────────────────
echo [3/3] Egyéb függőségek telepítése...
pip install -r requirements.txt

echo.
echo === Telepítés kész! ===
echo.
echo  Python LLM + Rust API + Chat:  .\scripts\start_all.bat
echo  Csak chat (szerver mar fut):   .\scripts\start_chat.bat
echo  WSL tmux layout:               wsl bash scripts/start_tmux.sh
pause
