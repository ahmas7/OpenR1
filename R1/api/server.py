import asyncio
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import httpx

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("R1")

# Config from environment
OLLAMA_ENDPOINT = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434")
DEFAULT_GGUF_PATH = os.getenv(
    "GGUF_MODEL_PATH",
    str(
        Path(__file__).resolve().parents[2]
        / "models"
        / "GLM-4.7-Flash-Uncen-Hrt-NEO-CODE-MAX-imat-D_AU-IQ4_XS.gguf"
    ),
)
OLLAMA_MODEL = os.getenv("R1_MODEL", DEFAULT_GGUF_PATH)
ACTIVE_PROVIDER = os.getenv("R1_PROVIDER", "gguf")

DATA_DIR = Path.home() / ".r1"
DATA_DIR.mkdir(exist_ok=True)


# Core imports
from R1.agent import get_runtime
from R1.model import get_model_manager
from R1.tools import get_tool_registry
from R1.memory import get_memory_store
from R1.skills import get_skills_runtime
from R1.jobs import get_job_manager
from R1.wake_word import get_wake_service
from R1 import voice_system

# Import schemas
from R1.api.schemas import (
    ChatRequest,
    ChatResponse,
    AgentRunRequest,
    AgentStatusResponse,
    AgentStopResponse,
    HealthResponse,
    ProviderInfo,
    ProvidersResponse,
    ToolsResponse,
    SkillsResponse,
    SkillActionRequest,
    SkillInvokeRequest,
    SkillValidateRequest,
    MemoryResponse,
    MemoryRememberRequest,
    MemoryRecallResponse,
    SessionsResponse,
    ErrorResponse,
    StackTrainRequest,
    StackTrainResponse,
    StackInferRequest,
    StackInferResponse,
    StackStatusResponse,
    JobInfoResponse,
    JobsListResponse,
    JobActionResponse,
    AuditEntryResponse,
    AuditListResponse,
    ReminderCreateRequest,
    ReminderResponse,
    RemindersListResponse,
    ReminderCancelResponse,
)

app = FastAPI(title="R1 API", version="2.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup():
    runtime = get_runtime()
    await runtime.initialize()
    job_manager = get_job_manager()
    await job_manager.start()
    try:
        from R1.config.settings import settings

        if settings.wake_enabled:
            get_wake_service().start()
    except Exception:
        pass

    # Initialize OpenClaw
    try:
        from R1.openclaw import openclaw

        await openclaw.initialize()
        logger.info("✓ OpenClaw initialized")
    except Exception as e:
        logger.error(f"OpenClaw initialization error: {e}")


@app.on_event("shutdown")
async def _shutdown():
    job_manager = get_job_manager()
    await job_manager.stop()

    # Shutdown OpenClaw
    try:
        from R1.openclaw import openclaw

        await openclaw.shutdown()
        logger.info("✓ OpenClaw shutdown")
    except Exception as e:
        logger.error(f"OpenClaw shutdown error: {e}")


# Web UI
WEB_DIR = Path(__file__).parent.parent / "web"
STACK_DIR = Path(__file__).parent.parent / "stack"
STACK_ALLOW_RUN = os.getenv("R1_STACK_ALLOW_RUN", "false").lower() == "true"
RUST_INFER_URL = os.getenv("R1_RUST_INFER_URL", "http://localhost:7071")

DATA_JOB_SCRIPT = STACK_DIR / "data" / "spark_job.py"
TRAIN_PYTORCH_SCRIPT = STACK_DIR / "training" / "train_pytorch.py"
TRAIN_JAX_SCRIPT = STACK_DIR / "training" / "train_jax.py"


@app.get("/")
async def root():
    return FileResponse(str(WEB_DIR / "index.html"))


# ==================== CORE ROUTES ====================


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check - returns core runtime status"""
    try:
        model_mgr = get_model_manager()
        model_health = await model_mgr.health()

        return HealthResponse(
            status="healthy" if model_health.get("healthy") else "degraded",
            timestamp=datetime.utcnow().isoformat(),
            provider=model_mgr.active_provider(),
            model_health=model_health,
        )
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


@app.get("/providers", response_model=ProvidersResponse)
async def list_providers():
    """List available model providers"""
    try:
        model_mgr = get_model_manager()
        providers = await model_mgr.get_providers_status()

        return ProvidersResponse(
            active_provider=model_mgr.active_provider(),
            providers=[
                ProviderInfo(id=p.id, name=p.name, healthy=p.healthy, reason=p.reason)
                for p in providers
            ],
        )
    except Exception as e:
        logger.error(f"Providers error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/tools", response_model=ToolsResponse)
async def list_tools():
    """List available tools"""
    try:
        tools = get_tool_registry()
        return ToolsResponse(tools=[t.name for t in tools.list_tools()])
    except Exception as e:
        logger.error(f"Tools error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/skills", response_model=SkillsResponse)
async def list_skills():
    """List all available skills"""
    try:
        runtime = get_skills_runtime()
        await runtime.initialize()
        return SkillsResponse(skills=runtime.discover_skills())
    except Exception as e:
        logger.error(f"Skills error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Simple chat with the AI"""
    try:
        runtime = get_runtime()
        await runtime.initialize()
        result = await runtime.chat(request.message, request.session_id)
        return ChatResponse(**result)
    except Exception as e:
        logger.error(f"Chat error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/agent/run")
async def run_agent(request: AgentRunRequest):
    """Run agent with a goal"""
    try:
        if not request.goal:
            return JSONResponse({"error": "goal is required"}, status_code=400)

        runtime = get_runtime()
        await runtime.initialize()
        result = await runtime.run_agent(request.goal, request.session_id)
        return result
    except Exception as e:
        logger.error(f"Agent run error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/agent/status/{session_id}")
async def agent_status(session_id: str):
    """Get agent session status"""
    try:
        runtime = get_runtime()
        status = runtime.get_session_status(session_id)

        if not status:
            return JSONResponse({"error": "Session not found"}, status_code=404)

        return status
    except Exception as e:
        logger.error(f"Agent status error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/agent/stop/{session_id}")
async def stop_agent(session_id: str):
    """Stop an agent session"""
    try:
        runtime = get_runtime()
        await runtime.stop_session(session_id)
        return {"success": True, "session_id": session_id}
    except Exception as e:
        logger.error(f"Agent stop error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/sessions")
async def list_sessions():
    """List all active sessions"""
    try:
        runtime = get_runtime()
        sessions_map = runtime.session_manager.list_sessions()
        return {
            "sessions": [
                {
                    "session_id": session_id,
                    "status": status.value if hasattr(status, "value") else str(status),
                }
                for session_id, status in sessions_map.items()
            ]
        }
    except Exception as e:
        logger.error(f"Sessions error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/memory/{session_id}")
async def get_memory(session_id: str):
    """Get memory for a session"""
    try:
        memory = get_memory_store()
        return MemoryResponse(
            conversation=memory.get_conversation(session_id),
            facts=memory.get_all_facts(),
            tool_history=memory.get_tool_history(session_id),
        )
    except Exception as e:
        logger.error(f"Memory error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/voice/status")
async def voice_status():
    """Get voice system status"""
    try:
        wake = get_wake_service()
        return wake.status()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/voice/speak")
async def voice_speak(request: Request):
    """Speak text via TTS"""
    try:
        body = await request.json()
        text = body.get("text", "")
        ok = voice_system.speak(text, async_mode=True)
        return {"success": bool(ok)}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/voice/stop")
async def voice_stop():
    """Stop active speech output"""
    try:
        ok = voice_system.stop_speaking()
        return {"success": bool(ok)}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/voice/listen")
async def voice_listen():
    """Listen once and return transcribed text"""
    try:
        text = voice_system.listen(timeout=5)
        return {"text": text or ""}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/voice/wake/start")
async def voice_wake_start():
    """Start wake word listener"""
    try:
        wake = get_wake_service()
        started = wake.start()
        return {"success": bool(started)}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/voice/wake/stop")
async def voice_wake_stop():
    """Stop wake word listener"""
    try:
        wake = get_wake_service()
        stopped = wake.stop()
        return {"success": bool(stopped)}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/memory/remember")
async def memory_remember(request: MemoryRememberRequest):
    """Store a key-value fact"""
    try:
        memory = get_memory_store()
        await memory.set_fact(request.key, request.value, request.category)
        return {"success": True, "key": request.key}
    except Exception as e:
        logger.error(f"Memory remember error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/memory/recall/{key}", response_model=MemoryRecallResponse)
async def memory_recall(key: str):
    """Recall a fact by key"""
    try:
        memory = get_memory_store()
        value = memory.get_fact(key)
        return MemoryRecallResponse(key=key, value=value)
    except Exception as e:
        logger.error(f"Memory recall error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


# ==================== AI STACK ROUTES ====================


def _run_script(args):
    proc = subprocess.run(args, capture_output=True, text=True)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


@app.get("/ai/stack/status", response_model=StackStatusResponse)
async def stack_status():
    return StackStatusResponse(
        available=STACK_DIR.exists(),
        allow_run=STACK_ALLOW_RUN,
        data_job=str(DATA_JOB_SCRIPT),
        train_pytorch=str(TRAIN_PYTORCH_SCRIPT),
        train_jax=str(TRAIN_JAX_SCRIPT),
        rust_infer_url=RUST_INFER_URL,
    )


@app.post("/ai/stack/train", response_model=StackTrainResponse)
async def stack_train(request: StackTrainRequest):
    if not STACK_ALLOW_RUN:
        return JSONResponse(
            {"error": "R1_STACK_ALLOW_RUN is not enabled"}, status_code=403
        )

    scripts = []
    if request.run_data_job:
        scripts.append(
            [
                sys.executable,
                str(DATA_JOB_SCRIPT),
                "--rows",
                str(request.rows),
            ]
        )

    if request.engine.lower() == "jax":
        train_script = TRAIN_JAX_SCRIPT
    else:
        train_script = TRAIN_PYTORCH_SCRIPT

    scripts.append(
        [
            sys.executable,
            str(train_script),
            "--epochs",
            str(request.epochs),
            "--lr",
            str(request.lr),
            "--rows",
            str(request.rows),
        ]
    )

    stdout_all = []
    stderr_all = []
    for args in scripts:
        code, out, err = await asyncio.to_thread(_run_script, args)
        stdout_all.append(out)
        stderr_all.append(err)
        if code != 0:
            return StackTrainResponse(
                success=False,
                stdout="\n".join(stdout_all),
                stderr="\n".join(stderr_all),
            )

    return StackTrainResponse(
        success=True, stdout="\n".join(stdout_all), stderr="\n".join(stderr_all)
    )


@app.post("/ai/stack/infer", response_model=StackInferResponse)
async def stack_infer(request: StackInferRequest):
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.post(
                f"{RUST_INFER_URL}/infer", json={"features": request.features}
            )
            resp.raise_for_status()
            payload = resp.json()
            return StackInferResponse(prediction=float(payload.get("prediction", 0.0)))
        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=502, detail=f"Rust inference unavailable: {e}"
            )


# ==================== SKILLS API ====================


@app.post("/skills/load")
async def load_skill(request: SkillActionRequest):
    """Load a skill by name"""
    try:
        if not request.name:
            return JSONResponse({"error": "skill name is required"}, status_code=400)

        runtime = get_skills_runtime()
        await runtime.initialize()
        success = runtime.load_skill(request.name)
        return {"success": success, "name": request.name}
    except Exception as e:
        logger.error(f"Skill load error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/skills/unload")
async def unload_skill(request: SkillActionRequest):
    """Unload a skill by name"""
    try:
        if not request.name:
            return JSONResponse({"error": "skill name is required"}, status_code=400)

        runtime = get_skills_runtime()
        success = runtime.unload_skill(request.name)
        return {"success": success, "name": request.name}
    except Exception as e:
        logger.error(f"Skill unload error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/skills/reload")
async def reload_skill(request: SkillActionRequest):
    """Reload a skill by name"""
    try:
        if not request.name:
            return JSONResponse({"error": "skill name is required"}, status_code=400)

        runtime = get_skills_runtime()
        success = runtime.reload_skill(request.name)
        return {"success": success, "name": request.name}
    except Exception as e:
        logger.error(f"Skill reload error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/skills/invoke")
async def invoke_skill(request: SkillInvokeRequest):
    """Invoke a skill with context"""
    try:
        if not request.name:
            return JSONResponse({"error": "skill name is required"}, status_code=400)

        runtime = get_skills_runtime()
        await runtime.initialize()
        result = runtime.invoke_skill(request.name, request.context)
        return result
    except Exception as e:
        logger.error(f"Skill invoke error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/skills/validate")
async def validate_skill(request: SkillValidateRequest):
    """Validate a skill manifest"""
    try:
        from R1.skills import SkillManifest

        manifest = SkillManifest(
            name=request.name,
            description=request.description,
            version=request.version,
            entrypoint=request.entrypoint,
            triggers=request.triggers,
            tools_used=request.tools_used,
            dependencies=request.dependencies,
            config=request.config,
        )
        errors = manifest.validate()

        if errors:
            return {"valid": False, "errors": errors}
        return {"valid": True, "manifest": manifest.to_dict()}
    except Exception as e:
        return {"valid": False, "errors": [str(e)]}


# ==================== JOBS API ====================


@app.get("/jobs", response_model=JobsListResponse)
async def list_jobs():
    """List all registered background jobs with status"""
    try:
        jm = get_job_manager()
        jobs = []
        for j in jm.list_jobs():
            status = jm.get_job_status(j.id) or {}
            jobs.append(JobInfoResponse(**status))
        return JobsListResponse(jobs=jobs)
    except Exception as e:
        logger.error(f"Jobs list error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/jobs/{job_id}/run", response_model=JobActionResponse)
async def run_job(job_id: str):
    """Trigger a job to run immediately"""
    try:
        jm = get_job_manager()
        success = await jm.run_job_now(job_id)
        if not success:
            return JSONResponse({"error": f"Job '{job_id}' not found"}, status_code=404)
        return JobActionResponse(success=True, job_id=job_id, message="Job executed")
    except Exception as e:
        logger.error(f"Job run error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/jobs/{job_id}/enable", response_model=JobActionResponse)
async def enable_job(job_id: str):
    """Enable a background job"""
    try:
        jm = get_job_manager()
        success = jm.enable_job(job_id)
        if not success:
            return JSONResponse({"error": f"Job '{job_id}' not found"}, status_code=404)
        return JobActionResponse(success=True, job_id=job_id, message="Job enabled")
    except Exception as e:
        logger.error(f"Job enable error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/jobs/{job_id}/disable", response_model=JobActionResponse)
async def disable_job(job_id: str):
    """Disable a background job"""
    try:
        jm = get_job_manager()
        success = jm.disable_job(job_id)
        if not success:
            return JSONResponse({"error": f"Job '{job_id}' not found"}, status_code=404)
        return JobActionResponse(success=True, job_id=job_id, message="Job disabled")
    except Exception as e:
        logger.error(f"Job disable error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


# ==================== AUDIT API ====================


@app.get("/audit/recent", response_model=AuditListResponse)
async def audit_recent(limit: int = 20):
    """Return the most recent tool audit log entries"""
    try:
        from R1.tools.audit import ToolAuditLogger

        audit = ToolAuditLogger()
        entries = audit.read_recent(min(limit, 100))
        return AuditListResponse(
            entries=[AuditEntryResponse(**e) for e in entries],
            total=len(entries),
        )
    except Exception as e:
        logger.error(f"Audit read error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


# ==================== REMINDERS API ====================


@app.get("/reminders", response_model=RemindersListResponse)
async def list_reminders():
    """List all pending reminders"""
    try:
        from R1.jobs.reminders import get_reminder_queue

        queue = get_reminder_queue()
        reminders = queue.list_pending()
        return RemindersListResponse(
            reminders=[ReminderResponse(**r.to_dict()) for r in reminders]
        )
    except Exception as e:
        logger.error(f"Reminders list error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/reminders", response_model=ReminderResponse)
async def create_reminder(request: ReminderCreateRequest):
    """Create a new reminder"""
    try:
        from R1.jobs.reminders import get_reminder_queue

        queue = get_reminder_queue()
        reminder = queue.add(request.session_id, request.text, request.due_at)
        return ReminderResponse(**reminder.to_dict())
    except Exception as e:
        logger.error(f"Reminder create error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.delete("/reminders/{reminder_id}", response_model=ReminderCancelResponse)
async def cancel_reminder(reminder_id: str):
    """Cancel a pending reminder"""
    try:
        from R1.jobs.reminders import get_reminder_queue

        queue = get_reminder_queue()
        success = queue.cancel(reminder_id)
        if not success:
            return JSONResponse({"error": "Reminder not found"}, status_code=404)
        return ReminderCancelResponse(success=True, id=reminder_id)
    except Exception as e:
        logger.error(f"Reminder cancel error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


# ==================== V1 COMPATIBILITY ALIASES ====================
# These routes exist for backward compatibility with v1 clients


@app.get("/v1/health")
async def v1_health():
    """R1 v1 health check - alias for /health"""
    return await health()


@app.get("/v1/providers")
async def v1_providers():
    """R1 v1 providers - alias for /providers"""
    return await list_providers()


@app.get("/v1/tools")
async def v1_tools():
    """R1 v1 tools - alias for /tools"""
    return await list_tools()


@app.get("/v1/skills")
async def v1_skills():
    """R1 v1 skills - alias for /skills"""
    return await list_skills()


@app.post("/v1/chat")
async def v1_chat(request: Request):
    """R1 v1 chat - delegates to /chat"""
    body = await request.json()
    return await chat(
        ChatRequest(
            message=body.get("message", ""),
            session_id=body.get("session_id", "default"),
        )
    )


@app.post("/v1/agent/run")
async def v1_agent_run(request: Request):
    """R1 v1 agent run - delegates to /agent/run"""
    body = await request.json()
    return await run_agent(
        AgentRunRequest(
            goal=body.get("goal", ""), session_id=body.get("session_id", "default")
        )
    )


@app.get("/v1/agent/status/{session_id}")
async def v1_agent_status(session_id: str):
    """R1 v1 agent status - delegates to /agent/status"""
    return await agent_status(session_id)


@app.post("/v1/agent/stop/{session_id}")
async def v1_agent_stop(session_id: str):
    """R1 v1 agent stop - delegates to /agent/stop"""
    return await stop_agent(session_id)


@app.get("/v1/memory/{session_id}")
async def v1_memory(session_id: str):
    """R1 v1 memory - delegates to /memory"""
    return await get_memory(session_id)


@app.post("/v1/skills/load")
async def v1_skills_load(request: Request):
    """R1 v1 skills load - delegates to /skills/load"""
    body = await request.json()
    return await load_skill(SkillActionRequest(name=body.get("name", "")))


@app.post("/v1/skills/unload")
async def v1_skills_unload(request: Request):
    """R1 v1 skills unload - delegates to /skills/unload"""
    body = await request.json()
    return await unload_skill(SkillActionRequest(name=body.get("name", "")))


@app.post("/v1/skills/reload")
async def v1_skills_reload(request: Request):
    """R1 v1 skills reload - delegates to /skills/reload"""
    body = await request.json()
    return await reload_skill(SkillActionRequest(name=body.get("name", "")))


@app.post("/v1/skills/invoke")
async def v1_skills_invoke(request: Request):
    """R1 v1 skills invoke - delegates to /skills/invoke"""
    body = await request.json()
    return await invoke_skill(
        SkillInvokeRequest(name=body.get("name", ""), context=body.get("context", {}))
    )


@app.post("/v1/skills/validate")
async def v1_skills_validate(request: Request):
    """R1 v1 skills validate - delegates to /skills/validate"""
    body = await request.json()
    return await validate_skill(SkillValidateRequest(**body))


# ==================== LEGACY ROUTES ====================
ENABLE_LEGACY_ROUTES = os.getenv("R1_ENABLE_LEGACY_ROUTES", "false").lower() == "true"

if ENABLE_LEGACY_ROUTES:
    from R1.api.legacy import legacy_router

    app.include_router(legacy_router)
    logger.info("Legacy routes enabled and loaded.")
else:
    logger.info("Legacy routes are disabled via R1_ENABLE_LEGACY_ROUTES.")

# Import and include OpenClaw routes
from R1.api.openclaw_routes import router as openclaw_router
from R1.api.agi_routes import router as agi_router

app.include_router(openclaw_router)
app.include_router(agi_router)
logger.info("OpenClaw routes loaded.")
logger.info("AGI routes loaded.")
