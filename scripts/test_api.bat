@echo off
:: ClawDBot – API tesztek (curl szükséges)

echo === ClawDBot API Tesztek ===
echo.

echo [1] Rust szerver health check...
curl -s http://localhost:3000/health
echo.
echo.

echo [2] Python LLM health check (Rust-on keresztül)...
curl -s http://localhost:3000/llm/health
echo.
echo.

echo [3] Chat teszt (REST)...
curl -s -X POST http://localhost:3000/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\": \"Írj egy Python függvényt, ami visszaadja a prímszámokat 100-ig!\"}"
echo.
echo.

echo [4] Közvetlen Python LLM teszt...
curl -s -X POST http://localhost:8000/generate ^
  -H "Content-Type: application/json" ^
  -d "{\"prompt\": \"Hello, mi a Fibonacci sorozat?\", \"max_new_tokens\": 100}"
echo.

echo.
echo === Tesztek vége ===
pause
