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
from typing import Optional, AsyncGenerator

import torch
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TextIteratorStreamer,
    BitsAndBytesConfig,
)
from threading import Thread

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


def load_model():
    global _model, _tokenizer

    gpu_info = detect_gpus()
    device_map = build_device_map(gpu_info)
    max_memory = build_max_memory(gpu_info)

    log.info(f"Modell betöltése: {MODEL_NAME}")
    log.info(f"dtype: float16 | device_map: {device_map}")

    _tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME,
        use_fast=True,
        trust_remote_code=True,
    )

    load_kwargs = dict(
        torch_dtype=torch.float16,
        device_map=device_map,
        trust_remote_code=True,
        low_cpu_mem_usage=True,
    )
    if max_memory:
        load_kwargs["max_memory"] = max_memory

    _model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, **load_kwargs)
    _model.eval()

    log.info("Modell sikeresen betöltve.")

    # GPU memória kiírása betöltés után
    if torch.cuda.is_available():
        for i in range(torch.cuda.device_count()):
            alloc = torch.cuda.memory_allocated(i) / (1024**3)
            total = torch.cuda.get_device_properties(i).total_memory / (1024**3)
            log.info(f"  GPU {i} mem: {alloc:.2f} / {total:.2f} GB használatban")

# ---------------------------------------------------------------------------
# FastAPI lifespan (betöltés induláskor)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, load_model)
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
    """WizardCoder stílusú prompt formátum."""
    if req.system_prompt:
        return (
            f"### System:\n{req.system_prompt}\n\n"
            f"### Instruction:\n{req.prompt}\n\n"
            f"### Response:\n"
        )
    return f"### Instruction:\n{req.prompt}\n\n### Response:\n"


def _get_input_device() -> str:
    """Az első GPU (ahol az embedding van) – ide kerülnek az inputok."""
    if torch.cuda.is_available():
        return "cuda:0"
    return "cpu"


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
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "model_loaded": _model is not None,
        "gpus": gpu_info,
    }


@app.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest):
    if _model is None or _tokenizer is None:
        raise HTTPException(503, "A modell még nem töltődött be.")

    if req.stream:
        return await _stream_response(req)

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _generate_sync, req)
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

        thread = Thread(target=_model.generate, kwargs=gen_kwargs, daemon=True)
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
    with torch.no_grad():
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
