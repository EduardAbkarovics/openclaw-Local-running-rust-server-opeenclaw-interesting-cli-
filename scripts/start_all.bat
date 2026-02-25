@echo off
:: ClawDBot – Windows Terminal split panes VAGY külön ablakok

echo === ClawDBot indítása ===
echo.

:: Windows Terminal (wt.exe) ellenőrzése
where wt >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Windows Terminal detektálva -- split pane módban indul...
    goto :wt_mode
)

echo Windows Terminal nem talalhato -- kulön ablakok modban indul...
goto :fallback

:wt_mode
:: 3 panel: bal=Chat (65%%), jobb felső=Python LLM, jobb alsó=Rust API
wt --maximized ^
  new-tab --title "ClawDBot Chat" --tabColor "#0d1117" cmd /k "%~dp0start_chat.bat" ^; ^
  split-pane -V --size 0.35 --title "Python LLM" cmd /k "%~dp0start_python.bat" ^; ^
  split-pane -H --size 0.5 --title "Rust API"    cmd /k "%~dp0start_rust.bat"
goto :end

:fallback
start "ClawDBot - Python LLM" cmd /k "%~dp0start_python.bat"
timeout /t 3 /nobreak >nul
start "ClawDBot - Rust API"   cmd /k "%~dp0start_rust.bat"
timeout /t 2 /nobreak >nul
start "ClawDBot - Chat"       cmd /k "%~dp0start_chat.bat"

:end
