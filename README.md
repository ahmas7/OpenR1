# R1

Local-first FastAPI assistant platform with chat, skills, cron, webhooks, gateway, diagnostics, planning, voice, and operator tooling.

## Quick Start

### Option 1: Local mode (no Ollama needed)

R1 now includes a **local fallback provider** that works without Ollama, llama-cpp-python, or any external dependencies.

**PowerShell:**
```powershell
.\start_r1.ps1
```

**Batch file (double-click):**
```
start_r1.bat
```

**Manual:**
```powershell
.\.venv\Scripts\python.exe -m uvicorn R1.api.server:app --host 127.0.0.1 --port 8000
```

### Option 2: AirLLM mode (run 70B+ models on 4GB+ VRAM)

[AirLLM](https://github.com/lyogavin/airllm) splits models layer-by-layer so any HuggingFace model can run with minimal memory.

1. Set in `.env`:
```
R1_PROVIDER=airllm
AIRLLM_MODEL_PATH=meta-llama/Llama-3.1-70B-Instruct
AIRLLM_COMPRESSION=4bit    # optional: 4bit or 8bit for 3x speedup
AIRLLM_HF_TOKEN=hf_xxx      # needed for gated models like Llama
```

2. Start the server — the model will be downloaded and split on first load.

Popular models that work with AirLLM:
- **7B models** — fast, ~4GB VRAM
- **13B-34B models** — moderate, ~8GB VRAM
- **70B models** — Llama 3.1 70B, works on 4GB VRAM (slow on CPU)
- **405B models** — Llama 3.1 405B, works on 8GB VRAM

### Option 3: GGUF mode (full local LLM)

Install `llama-cpp-python` for full local inference with your GGUF model:
```powershell
.\.venv\Scripts\python.exe -m pip install llama-cpp-python
```
Then set `R1_PROVIDER=gguf` in `.env` and ensure `GGUF_MODEL_PATH` points to your `.gguf` file.

### Option 3: Ollama mode

Install [Ollama](https://ollama.com/), pull a model, and set `R1_PROVIDER=ollama` in `.env`.

## How Providers Work

R1 tries the configured provider first, then **automatically falls back** to a local provider if it's unavailable:

| Provider | Needs | Description |
|----------|-------|-------------|
| `airllm` | HuggingFace model ID or path | Run 70B+ models on 4GB+ VRAM via layer sharding |
| `gguf` | `llama-cpp-python` + `.gguf` file | Full local LLM inference |
| `ollama` | Ollama running + model pulled | Connects to local Ollama |
| `local` | Nothing | Built-in fallback (always works) |

## AI Stack (Spark + PyTorch/JAX + Rust)

See `R1/stack/README.md` for a real multi-language pipeline that includes Spark data processing, PyTorch/JAX training, and Rust inference serving wired into the R1 API.

## Main Endpoints

- `GET /health`
- `POST /chat`
- `GET /providers`
- `GET /skills`
- `GET /tools`
- `GET /sessions`
- `GET /memory/{session_id}`
- `POST /agent/run`
- `GET /agent/status/{session_id}`
- `POST /agent/stop/{session_id}`

## Safety and Tool Policy

R1 enforces a tool policy for dangerous tools:

- `R1_TOOL_POLICY=allow|confirm|deny` (default: `confirm`)
- `R1_TOOL_RETRIES` (default: `1`)
- `R1_TOOL_AUTO_CONFIRM` (default: `false`)

Filesystem writes and deletes create backups in `.r1_backups` by default.

Audit logs are rotated automatically:

- `R1_AUDIT_MAX_BYTES` (default: 5MB)
- `R1_AUDIT_MAX_FILES` (default: 3)

## Background Jobs

Heartbeat and reminders run in-process:

- `R1_JOBS_ENABLED` (default: `true`)
- `R1_HEARTBEAT_SECONDS` (default: `60`)
- `R1_REMINDERS_SECONDS` (default: `300`)

## Current Optional Dependencies

- GGUF inference quality/runtime depends on `llama-cpp-python`
- Live microphone STT on Windows still needs `PyAudio`
- Optional capability packs: `text-pack`, `code-pack`, `docs-pack`, `audio-pack`, `vision-pack`
