# OpenClaw alkalmazás lokális szerverrel (API kulcs nélkül)

A Rust szerver **OpenAI-kompatibilis** `/v1` API-t tesz elérhetővé, így a hivatalos **OpenClaw** alkalmazást (terminálból: `openclaw gateway`) használhatod a saját lokális LLM-eddel (DeepSeek R1, Python szerver) **API kulcs nélkül**.

## Lépések

### 1. Indítsd a lokális stacket

```bat
scripts\start_openclaw_deepseek_r1.bat
```

Ez elindítja:
- **DeepSeek R1** (agy) – Python LLM a `W:\openclaw_server_hosting\models` alatt
- **OpenClaw** (composer) – Rust szerver: `http://127.0.0.1:3000`
- **Chat** tab – saját terminál UI (opcionális)

### 2. OpenClaw konfiguráció

A Rust szerver a következő végpontokat adja:

- `GET http://127.0.0.1:3000/v1/models` – modell lista (egy elem: `openclaw-local`)
- `POST http://127.0.0.1:3000/v1/chat/completions` – OpenAI formátumú chat

**Egyszerű módszer:** a repóban van egy javított példa konfig, ami a lokális Rust szervert használja és megfelel az OpenClaw 2026 schemának:

- Másold át: `openclaw.json.example` → `C:\Users\<felhasználónév>\.openclaw\openclaw.json`
- A `deepseek` provider így a mi szerverünkre mutat: `http://127.0.0.1:3000/v1`, `api: "openai-completions"`.
- Eltávolítva a nem támogatott kulcsok (pl. `models.providers.deepseek.api: "deepseek"` → `"openai-completions"`, nincs `provider` az `agents.defaults.models` alatt, nincs felesleges `models["anthropic/..."]` stb.).

Ha saját konfigot szerkesztesz, a lényeg:

```json
"deepseek": {
  "baseUrl": "http://127.0.0.1:3000/v1",
  "apiKey": "openclaw-local",
  "api": "openai-completions",
  "models": [
    {
      "id": "openclaw-local",
      "name": "deepseek r1",
      "input": ["text"],
      "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 }
    }
  ]
}
```

Az `agents.defaults.model.primary` maradhat `"deepseek r1"` (a fenti modell `name` mezője).

### 3. OpenClaw indítása

Ha a konfig kész, futtasd:

```bash
openclaw gateway
```

A gateway a lokális Rust szervert fogja hívni (`http://127.0.0.1:3000/v1`), a Rust pedig a Python LLM-et (DeepSeek R1). Minden lokálisan fut, nincs szükség külső API kulcsra.

### Ellenőrzés

- Szerver fut: `curl http://127.0.0.1:3000/health`
- Modell lista: `curl http://127.0.0.1:3000/v1/models`
- LLM állapot: `curl http://127.0.0.1:3000/llm/health`
