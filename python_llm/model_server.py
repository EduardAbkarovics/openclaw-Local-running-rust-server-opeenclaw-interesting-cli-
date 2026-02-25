"""
ClawDBot - Python LLM Server
WizardLM 13B Code, FP16, multi-GPU (mindkét GPU automatikusan detektálva)
HTTP API: FastAPI + Uvicorn
"""

import os
import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, AsyncGenerator
from threading import Thread, Lock

_project_root = Path(__file__).resolve().parent.parent

_models_dir = os.environ.get("HF_HOME", r"E:\hf_cache")
for _hf_key in ("HF_HOME", "HF_HUB_CACHE", "HUGGINGFACE_HUB_CACHE", "TRANSFORMERS_CACHE"):
    os.environ[_hf_key] = _models_dir
print(f"[HF cache] -> {_models_dir}")

# .env betöltése (NEM írja felül a már beállított HF_HOME-t)
_env_path = _project_root / ".env"
if _env_path.exists():
    with open(_env_path, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ.setdefault(_k.strip(), _v.strip())

import torch

# ── Sebesség optimalizáció: TF32 (Ampere+ GPU-kon ~20% gyorsabb) ────────────
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True
torch.backends.cudnn.benchmark = True   # auto-tune konvolúciókhoz

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TextIteratorStreamer,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("clawdbot.llm")

# ---------------------------------------------------------------------------
# Konfiguráció – felülírható környezeti változókkal
# ---------------------------------------------------------------------------
MODEL_NAME = os.environ.get("MODEL_NAME", "WizardLM/WizardCoder-Python-13B-V1.0")
MAX_NEW_TOKENS = int(os.environ.get("MAX_NEW_TOKENS", "512"))
HOST = os.environ.get("LLM_HOST", "0.0.0.0")
PORT = int(os.environ.get("LLM_PORT", "8000"))
LOAD_IN_4BIT = os.environ.get("LOAD_IN_4BIT", "1").strip().lower() in {"1", "true", "yes"}

# ---------------------------------------------------------------------------
# GPU detektálás
# ---------------------------------------------------------------------------

def detect_gpus() -> dict:
    """Meghatározza az elérhető GPU-kat és azok VRAM-ját."""
    if not torch.cuda.is_available():
        log.warning("Nincs CUDA GPU! CPU módban fut.")
        return {"device_count": 0, "gpus": []}

    count = torch.cuda.device_count()
    gpus = []
    for i in range(count):
        props = torch.cuda.get_device_properties(i)
        vram_gb = props.total_memory / (1024 ** 3)
        gpus.append({
            "index": i,
            "name": props.name,
            "vram_gb": round(vram_gb, 2),
        })
        log.info(f"  GPU {i}: {props.name} | {vram_gb:.1f} GB VRAM")

    log.info(f"Talált GPU-k: {count} db")
    return {"device_count": count, "gpus": gpus}


def build_device_map(gpu_info: dict) -> str | dict:
    """
    Automatikus device_map: ha >=2 GPU van, 'auto' elegendő –
    a Hugging Face accelerate maga osztja szét a rétegeket.
    Ha csak 1 GPU van, 'cuda:0'-t használunk.
    Ha nincs GPU, 'cpu'-t.
    """
    count = gpu_info["device_count"]
    if count == 0:
        return "cpu"
    if count == 1:
        return "cuda:0"
    # 2+ GPU: accelerate auto-balancing
    log.info(f"Multi-GPU mód: {count} GPU között osztjuk szét a modellt.")
    return "auto"


def build_max_memory(gpu_info: dict) -> Optional[dict]:
    """
    Explicit memóriakorlát GPU-nként.
    18 GB-os teljes VRAM esetén megpróbálunk ~8.5 GB-ot hagyni mindkét kártyán.
    """
    count = gpu_info["device_count"]
    if count < 2:
        return None

    max_mem = {}
    for g in gpu_info["gpus"]:
        # Tartalékolunk 1 GB-ot a rendszernek
        safe_vram = max(1, g["vram_gb"] - 1)
        max_mem[g["index"]] = f"{safe_vram:.0f}GiB"

    # CPU fallback ha szükséges
    max_mem["cpu"] = "24GiB"
    log.info(f"Max memória GPU-nként: {max_mem}")
    return max_mem

# ---------------------------------------------------------------------------
# Globális modell + tokenizer
# ---------------------------------------------------------------------------
_model: Optional[AutoModelForCausalLM] = None
_tokenizer: Optional[AutoTokenizer] = None
_model_loading = False
_model_load_error: Optional[str] = None
_model_state_lock = Lock()


def load_model():
    global _model, _tokenizer, _model_loading, _model_load_error

    with _model_state_lock:
        if _model_loading or (_model is not None and _tokenizer is not None):
            return
        _model_loading = True
        _model_load_error = None

    try:
        gpu_info = detect_gpus()

        _tokenizer = AutoTokenizer.from_pretrained(
            MODEL_NAME,
            use_fast=True,
            trust_remote_code=True,
        )

        if gpu_info["device_count"] > 0:
            log.info(f"Modell betöltése: {MODEL_NAME}")
            log.info("Mód: GPU | device_map: auto (multi-GPU + CPU offload)")

            # GPU-nként max memória: hagyunk helyet a KV cache-nek és aktivációknak
            max_mem = {}
            for g in gpu_info["gpus"]:
                # 3 GB-ot hagyunk szabadon inference-hoz
                safe = max(1, int(g["vram_gb"]) - 3)
                max_mem[g["index"]] = f"{safe}GiB"
            max_mem["cpu"] = "16GiB"
            log.info(f"Max memória korlátok: {max_mem}")

            if LOAD_IN_4BIT:
                log.info("4-bit kvantizált betöltés engedélyezve (LOAD_IN_4BIT=1).")
                try:
                    quant_cfg = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_quant_type="nf4",
                        bnb_4bit_use_double_quant=True,
                        bnb_4bit_compute_dtype=torch.float16,
                    )
                    _model = AutoModelForCausalLM.from_pretrained(
                        MODEL_NAME,
                        device_map="auto",
                        max_memory=max_mem,
                        quantization_config=quant_cfg,
                        trust_remote_code=True,
                        low_cpu_mem_usage=True,
                    )
                except Exception as q_err:
                    log.warning(f"4-bit betöltés nem sikerült ({q_err}), fallback float16 módra.")
                    _model = AutoModelForCausalLM.from_pretrained(
                        MODEL_NAME,
                        torch_dtype=torch.float16,
                        device_map="auto",
                        max_memory=max_mem,
                        trust_remote_code=True,
                        low_cpu_mem_usage=True,
                    )
            else:
                _model = AutoModelForCausalLM.from_pretrained(
                    MODEL_NAME,
                    torch_dtype=torch.float16,
                    device_map="auto",
                    max_memory=max_mem,
                    trust_remote_code=True,
                    low_cpu_mem_usage=True,
                )
        else:
            log.warning("Nincs GPU -- CPU float32 modban fut (nagyon lassu!)")
            _model = AutoModelForCausalLM.from_pretrained(
                MODEL_NAME,
                torch_dtype=torch.float32,
                device_map="cpu",
                trust_remote_code=True,
                low_cpu_mem_usage=True,
            )

        _model.eval()

        # torch.compile Windows-on nem megbízható, kihagyva
        log.info("torch.compile() kihagyva (Windows kompatibilitás).")

        log.info("Modell sikeresen betöltve.")

        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                alloc = torch.cuda.memory_allocated(i) / (1024**3)
                total = torch.cuda.get_device_properties(i).total_memory / (1024**3)
                log.info(f"  GPU {i} mem: {alloc:.2f} / {total:.2f} GB használatban")
    except Exception as e:
        _model = None
        _tokenizer = None
        _model_load_error = str(e)
        log.error(f"Modell betöltési hiba: {e}", exc_info=True)
    finally:
        with _model_state_lock:
            _model_loading = False


def start_model_loader() -> None:
    Thread(target=load_model, daemon=True, name="model-loader").start()

# ---------------------------------------------------------------------------
# FastAPI lifespan (betöltés induláskor)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # A szerver azonnal elindul; a modell betöltése háttérszálon történik.
    start_model_loader()
    yield
    log.info("Szerver leáll.")


app = FastAPI(
    title="ClawDBot LLM API",
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Request / Response modellek
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    prompt: str = Field(..., description="A bemenet prompt szövege")
    max_new_tokens: int = Field(MAX_NEW_TOKENS, ge=1, le=2048)
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    top_p: float = Field(0.95, ge=0.0, le=1.0)
    top_k: int = Field(50, ge=0)
    repetition_penalty: float = Field(1.1, ge=0.5, le=2.0)
    stream: bool = Field(False, description="Streaming válasz SSE-n keresztül")
    system_prompt: Optional[str] = Field(
        None,
        description="Opcionális rendszer prompt (a felhasználói prompt elé kerül)",
    )


class GenerateResponse(BaseModel):
    text: str
    tokens_generated: int
    elapsed_seconds: float
    model: str


# ---------------------------------------------------------------------------
# Generálási segédfüggvény
# ---------------------------------------------------------------------------

def _build_full_prompt(req: GenerateRequest) -> str:
    """Chat-típusú modellekhez natív chat template prompt."""
    if _tokenizer is None:
        return req.prompt

    messages = []
    if req.system_prompt:
        messages.append({"role": "system", "content": req.system_prompt})
    messages.append({"role": "user", "content": req.prompt})

    try:
        return _tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
    except Exception:
        # Fallback, ha adott tokenizer nem támogatja a chat template-et.
        if req.system_prompt:
            return f"{req.system_prompt}\n\nUser: {req.prompt}\nAssistant:"
        return f"User: {req.prompt}\nAssistant:"


def _get_input_device() -> str:
    """Az embedding réteg tényleges eszköze – ide kerülnek az inputok."""
    if _model is None or not torch.cuda.is_available():
        return "cpu"
    try:
        device = next(_model.parameters()).device
        return str(device)
    except StopIteration:
        return "cuda:0"


# ---------------------------------------------------------------------------
# Endpointok
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    gpu_info = []
    if torch.cuda.is_available():
        for i in range(torch.cuda.device_count()):
            alloc = torch.cuda.memory_allocated(i) / (1024**3)
            total = torch.cuda.get_device_properties(i).total_memory / (1024**3)
            gpu_info.append({
                "index": i,
                "name": torch.cuda.get_device_properties(i).name,
                "used_gb": round(alloc, 2),
                "total_gb": round(total, 2),
            })
    status = "ok" if _model is not None and _tokenizer is not None else "loading"
    if _model_load_error:
        status = "error"

    return {
        "status": status,
        "model": MODEL_NAME,
        "model_loaded": _model is not None,
        "model_loading": _model_loading,
        "error": _model_load_error,
        "gpus": gpu_info,
    }


@app.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest):
    if _model is None or _tokenizer is None:
        if _model_load_error:
            raise HTTPException(503, f"A modell betöltése hibára futott: {_model_load_error}")
        if _model_loading:
            raise HTTPException(503, "A modell betöltése folyamatban van. Próbáld újra rövidesen.")
        start_model_loader()
        raise HTTPException(503, "A modell inicializálása elindult. Próbáld újra rövidesen.")

    if req.stream:
        return await _stream_response(req)

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, _generate_sync, req)
    except torch.cuda.OutOfMemoryError as e:
        log.error(f"CUDA OOM: {e}")
        torch.cuda.empty_cache()
        raise HTTPException(503, f"CUDA memória tele: {e}")
    except Exception as e:
        log.error(f"Generálási hiba: {e}", exc_info=True)
        raise HTTPException(500, f"Generálási hiba: {e}")
    return result


async def _stream_response(req: GenerateRequest) -> StreamingResponse:
    """Server-Sent Events alapú streaming."""

    async def event_generator() -> AsyncGenerator[str, None]:
        streamer = TextIteratorStreamer(
            _tokenizer, skip_prompt=True, skip_special_tokens=True
        )
        full_prompt = _build_full_prompt(req)
        inputs = _tokenizer(full_prompt, return_tensors="pt").to(_get_input_device())

        gen_kwargs = dict(
            **inputs,
            max_new_tokens=req.max_new_tokens,
            temperature=req.temperature,
            top_p=req.top_p,
            top_k=req.top_k,
            repetition_penalty=req.repetition_penalty,
            do_sample=req.temperature > 0,
            streamer=streamer,
            pad_token_id=_tokenizer.eos_token_id,
        )

        def _generate_no_grad(**kwargs):
            with torch.inference_mode():
                _model.generate(**kwargs)

        thread = Thread(target=_generate_no_grad, kwargs=gen_kwargs, daemon=True)
        thread.start()

        for token_text in streamer:
            yield f"data: {token_text}\n\n"

        thread.join()
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


def _generate_sync(req: GenerateRequest) -> GenerateResponse:
    full_prompt = _build_full_prompt(req)
    inputs = _tokenizer(full_prompt, return_tensors="pt").to(_get_input_device())
    input_len = inputs["input_ids"].shape[1]

    t0 = time.perf_counter()
    with torch.inference_mode():
        outputs = _model.generate(
            **inputs,
            max_new_tokens=req.max_new_tokens,
            temperature=req.temperature,
            top_p=req.top_p,
            top_k=req.top_k,
            repetition_penalty=req.repetition_penalty,
            do_sample=req.temperature > 0,
            pad_token_id=_tokenizer.eos_token_id,
        )
    elapsed = time.perf_counter() - t0

    # Csak az újonnan generált tokenek
    new_tokens = outputs[0][input_len:]
    text = _tokenizer.decode(new_tokens, skip_special_tokens=True)
    tokens_generated = len(new_tokens)

    return GenerateResponse(
        text=text,
        tokens_generated=tokens_generated,
        elapsed_seconds=round(elapsed, 3),
        model=MODEL_NAME,
    )


@app.get("/gpu_info")
async def gpu_info_endpoint():
    return detect_gpus()


# ---------------------------------------------------------------------------
# Belépési pont
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "model_server:app",
        host=HOST,
        port=PORT,
        log_level="info",
        workers=1,          # Több worker nem kompatibilis a GPU-megosztással
    )
