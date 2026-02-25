@echo off
:: ClawDBot – Rust szerver indítása

echo === ClawDBot Rust Szerver ===
echo.

cd /d "%~dp0..\rust_server"

:: Cargo ellenőrzése
where cargo >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [HIBA] A Rust/Cargo nincs telepítve vagy nincs a PATH-ban!
    echo Telepits: https://rustup.rs
    pause
    exit /b 1
)

:: .env betöltése
if exist "..\\.env" (
    for /f "usebackq tokens=1,* delims==" %%A in ("..\\.env") do (
        if not "%%A"=="" set "%%A=%%B"
    )
)
set RUST_LOG=clawdbot_server=info,tower_http=info

:: Build cache és Cargo registry W: meghajtóra
set CARGO_TARGET_DIR=W:\openclaw_server_hosting\rust_server\target
set CARGO_HOME=W:\.cargo
set TEMP=W:\tmp
set TMP=W:\tmp

:: Fordítás (csak ha szükséges)
echo Rust szerver fordítása...
echo Target mappa: %CARGO_TARGET_DIR%
cargo build --release

if %ERRORLEVEL% NEQ 0 (
    echo [HIBA] A fordítás sikertelen!
    pause
    exit /b 1
)

echo.
echo Rust szerver indul: http://0.0.0.0:3000
echo.

cargo run --release

pause
