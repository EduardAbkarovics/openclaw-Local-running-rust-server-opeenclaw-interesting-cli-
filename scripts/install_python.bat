@echo off
:: ClawDBot – Python függőségek telepítése
:: PyTorch CUDA 12.1 verzióval (módosítsd ha más CUDA-d van)

echo === ClawDBot Python telepítő ===
echo.

cd /d "%~dp0..\python_llm"

:: Virtuális környezet létrehozása
if not exist ".venv" (
    echo [1/3] Virtuális környezet létrehozása...
    python -m venv .venv
)

:: Aktiválás
call .venv\Scripts\activate.bat

echo [2/3] PyTorch CUDA 12.1 telepítése...
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

echo [3/3] Egyéb függőségek telepítése...
pip install -r requirements.txt

echo.
echo === Telepítés kész! ===
echo.
echo  Python LLM + Rust API + Chat terminal:  .\scripts\start_all.bat
echo  Csak chat (ha szerver mar fut):          .\scripts\start_chat.bat
echo  WSL tmux layout:  wsl bash scripts/start_tmux.sh
pause
