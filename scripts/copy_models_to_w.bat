@echo off
echo === HF cache masolas E:\hf_cache -> W:\openclaw_server_hosting\models ===
echo.

if not exist "W:\openclaw_server_hosting\models" (
    mkdir "W:\openclaw_server_hosting\models"
    echo Mappa letrehozva: W:\openclaw_server_hosting\models
)

echo Masolas indul... (25 GB, ez eltarthat egy darabig)
echo Log: E:\openclaw_server_hosting\hf_cache_copy.log
echo.

robocopy "E:\hf_cache" "W:\openclaw_server_hosting\models" /E /COPYALL /MT:8 /R:3 /W:5 /NP /LOG:"E:\openclaw_server_hosting\hf_cache_copy.log"

if %ERRORLEVEL% LEQ 7 (
    echo.
    echo === Masolas sikeres! ===
) else (
    echo.
    echo === HIBA tortent a masolas soran! (exit code: %ERRORLEVEL%) ===
    echo Nezd meg a log fajlt: E:\openclaw_server_hosting\hf_cache_copy.log
)

pause
