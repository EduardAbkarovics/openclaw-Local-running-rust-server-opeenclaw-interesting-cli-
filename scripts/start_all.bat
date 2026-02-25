@echo off
:: ClawDBot – 3 ablak indítása

echo === ClawDBot indítása ===
echo.

:: Windows Terminal elérhető?
where wt >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Windows Terminal detektálva...
    goto :wt_mode
)

echo Windows Terminal nem talalhato -- normal ablakok...
goto :fallback

:wt_mode
:: wt: 3 külön tab (split-pane CMD-ből megbízhatatlan, tab mindig működik)
start "" wt --maximized new-tab --title "Python LLM" cmd /k "%~dp0start_python.bat"
timeout /t 1 /nobreak >nul
start "" wt -w 0 new-tab --title "Rust API" cmd /k "%~dp0start_rust.bat"
timeout /t 1 /nobreak >nul
start "" wt -w 0 new-tab --title "ClawDBot Chat" cmd /k "%~dp0start_chat.bat"
exit

:fallback
start "Python LLM"  cmd /k "%~dp0start_python.bat"
timeout /t 2 /nobreak >nul
start "Rust API"    cmd /k "%~dp0start_rust.bat"
timeout /t 2 /nobreak >nul
start "ClawDBot Chat" cmd /k "%~dp0start_chat.bat"
exit
