import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse

legacy_router = APIRouter()
logger = logging.getLogger("R1.Legacy")

# Optional imports for legacy routes
try:
    from R1.providers import AIEngine, Message
except:
    AIEngine = None
    Message = None

try:
    from R1.cron import CronManager, CronJob
except:
    CronManager = None
    CronJob = None

try:
    from R1.webhooks import WebhookManager
except:
    WebhookManager = None

try:
    from R1.gateway import Gateway
except:
    Gateway = None

try:
    from R1.local_ai import get_orion_ai
except:
    pass

# Self-improving AI system
try:
    from R1.self_improver import get_self_improver
    SELF_IMPROVER_AVAILABLE = True
except:
    SELF_IMPROVER_AVAILABLE = False

# Voice system
try:
    from R1.voice_system import speak, stop_speaking, listen, get_status as voice_status, start_wake_listener, stop_wake_listener, WAKE_WORD
    VOICE_AVAILABLE = True
except:
    VOICE_AVAILABLE = False
    def speak(*args, **kwargs): return False
    def stop_speaking(): return True
    def listen(*args, **kwargs): return None



# Legacy config
OLLAMA_ENDPOINT = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434")
DEFAULT_GGUF_PATH = os.getenv(
    "GGUF_MODEL_PATH",
    str(Path(__file__).resolve().parents[2] / "models" / "GLM-4.7-Flash-Uncen-Hrt-NEO-CODE-MAX-imat-D_AU-IQ4_XS.gguf"),
)
OLLAMA_MODEL = os.getenv("R1_MODEL", DEFAULT_GGUF_PATH)
ACTIVE_PROVIDER = os.getenv("R1_PROVIDER", "gguf")
DATA_DIR = Path.home() / ".r1"
R1_CORE_AVAILABLE = True

# Legacy global state
brain = None
memory = None
skills = None
enhanced_skills = None
cron_manager = None
webhook_manager = None
gateway = None
LAST_PROVIDER_ERROR = None

@legacy_router.on_event("startup")
async def startup_event():
    logger.info("="*50)
    logger.info("STARTING R1 ORION AI")
    logger.info("Brain Provider: " + ACTIVE_PROVIDER)
    logger.info("Model: " + OLLAMA_MODEL)
    logger.info("="*50)
    
    # Initialize primary provider
    global brain, memory, skills, enhanced_skills, cron_manager, webhook_manager, gateway
    try:
        brain, config = await _ensure_brain()
        logger.info(f"✓ Active Brain: {brain.name} (requested: {ACTIVE_PROVIDER}, effective: {config['provider']})")
    except Exception as e:
        logger.warning(f"Provider startup issue: {e}")
        logger.info("Will use local AI as fallback")

    try:
        from R1.memory_persistent import memory as persistent_memory
        memory = persistent_memory
        logger.info("Persistent memory initialized")
    except Exception as e:
        logger.warning(f"Memory issue: {e}")

    try:
        from R1.plugins import SkillManager as PluginSkillManager
        skills = PluginSkillManager()
        logger.info("Plugin skills initialized")
    except Exception as e:
        logger.warning(f"Plugin skills issue: {e}")

    try:
        from R1.skills import SkillManager as WorkspaceSkillManager
        enhanced_skills = WorkspaceSkillManager()
        enhanced_skills.load_workspace_skills()
        logger.info("Workspace skills initialized")
    except Exception as e:
        logger.warning(f"Enhanced skills issue: {e}")
    
    # Initialize local AI
    try:
        from R1.local_ai import get_orion_ai
        ai = get_orion_ai()
        logger.info(f"✓ Local AI: {ai.name} v{ai.version}")
    except Exception as e:
        logger.warning(f"Local AI issue: {e}")

    try:
        if CronManager:
            cron_manager = CronManager(config_dir=str(DATA_DIR))
            await cron_manager.start()
            logger.info("Cron manager initialized")
    except Exception as e:
        logger.warning(f"Cron manager issue: {e}")
        cron_manager = None

    try:
        if WebhookManager:
            webhook_manager = WebhookManager(config_dir=str(DATA_DIR))
            logger.info("Webhook manager initialized")
    except Exception as e:
        logger.warning(f"Webhook manager issue: {e}")
        webhook_manager = None

    try:
        if Gateway:
            gateway = Gateway()
            logger.info("Gateway initialized")
    except Exception as e:
        logger.warning(f"Gateway issue: {e}")
        gateway = None
    
    logger.info("="*50)
    logger.info("R1 IS READY!")
    logger.info("="*50)


@legacy_router.on_event("shutdown")
async def shutdown_event():
    if cron_manager and cron_manager.is_running():
        await cron_manager.stop()


def _require_component(component, name: str):
    if component is None:
        raise HTTPException(status_code=503, detail=f"{name} is not available")
    return component


async def _ollama_available() -> bool:
    try:
        import httpx

        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{OLLAMA_ENDPOINT}/api/tags")
        return resp.status_code == 200
    except Exception:
        return False


def _gguf_ready() -> tuple[bool, str | None]:
    try:
        from R1.gguf_engine import get_gguf_engine

        engine = get_gguf_engine()
        if not engine.get_status().get("library_loaded", False):
            return False, "llama-cpp-python is not installed"

        candidate = Path(DEFAULT_GGUF_PATH)
        if not candidate.exists():
            return False, f"GGUF model path not found: {candidate}"

        if candidate.is_dir() and not any(candidate.glob("*.gguf")):
            return False, f"No .gguf file found in: {candidate}"

        if candidate.is_file() and candidate.suffix.lower() != ".gguf":
            return False, f"Configured model is not a .gguf file: {candidate}"

        return True, None
    except Exception as e:
        return False, str(e)


async def _resolve_provider_config() -> dict:
    global LAST_PROVIDER_ERROR

    requested = (ACTIVE_PROVIDER or "local").lower()
    LAST_PROVIDER_ERROR = None

    if requested == "gguf":
        gguf_ok, gguf_error = _gguf_ready()
        if gguf_ok:
            return {
                "provider": "gguf",
                "model": OLLAMA_MODEL,
                "model_path": DEFAULT_GGUF_PATH,
                "endpoint": OLLAMA_ENDPOINT,
            }
        LAST_PROVIDER_ERROR = gguf_error
        if await _ollama_available():
            logger.warning(f"GGUF unavailable, falling back to Ollama: {gguf_error}")
            return {
                "provider": "ollama",
                "model": os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
                "model_path": DEFAULT_GGUF_PATH,
                "endpoint": OLLAMA_ENDPOINT,
            }
        logger.warning(f"GGUF unavailable, falling back to local provider: {gguf_error}")
        return {
            "provider": "local",
            "model": "local:r1",
            "model_path": DEFAULT_GGUF_PATH,
            "endpoint": OLLAMA_ENDPOINT,
        }

    if requested == "ollama":
        if await _ollama_available():
            return {
                "provider": "ollama",
                "model": OLLAMA_MODEL,
                "model_path": DEFAULT_GGUF_PATH,
                "endpoint": OLLAMA_ENDPOINT,
            }
        LAST_PROVIDER_ERROR = "Ollama is not reachable"
        gguf_ok, gguf_error = _gguf_ready()
        if gguf_ok:
            logger.warning("Ollama unavailable, falling back to GGUF")
            return {
                "provider": "gguf",
                "model": DEFAULT_GGUF_PATH,
                "model_path": DEFAULT_GGUF_PATH,
                "endpoint": OLLAMA_ENDPOINT,
            }
        logger.warning(f"Ollama unavailable, falling back to local provider: {gguf_error}")
        return {
            "provider": "local",
            "model": "local:r1",
            "model_path": DEFAULT_GGUF_PATH,
            "endpoint": OLLAMA_ENDPOINT,
        }

    return {
        "provider": requested,
        "model": OLLAMA_MODEL,
        "model_path": DEFAULT_GGUF_PATH,
        "endpoint": OLLAMA_ENDPOINT,
    }


async def _ensure_brain():
    global brain
    from R1.providers import get_ai_engine

    config = await _resolve_provider_config()
    if brain is None or getattr(brain, "provider_name", None) != config["provider"]:
        brain = get_ai_engine(config)
    return brain, config


def _memory_remember(key: str, value: str):
    store = _require_component(memory, "memory")
    if hasattr(store, "remember"):
        store.remember(key, value)
        return
    if hasattr(store, "learn_skill"):
        store.learn_skill(key, value, [])
        return
    raise HTTPException(status_code=501, detail="memory store does not support key/value writes")


def _memory_recall(key: str):
    store = _require_component(memory, "memory")
    if hasattr(store, "recall"):
        return store.recall(key)
    if hasattr(store, "get_facts"):
        return store.get_facts().get(key)
    raise HTTPException(status_code=501, detail="memory store does not support key/value reads")


@legacy_router.post("/providers/select")
async def select_provider(request: Request):
    global ACTIVE_PROVIDER, OLLAMA_MODEL, brain
    body = await request.json()
    provider = body.get("provider", ACTIVE_PROVIDER)
    model = body.get("model", OLLAMA_MODEL)

    from R1.providers import get_ai_engine

    ACTIVE_PROVIDER = provider
    OLLAMA_MODEL = model
    brain = get_ai_engine({
        "provider": provider,
        "model": model,
        "model_path": model if provider == "gguf" else DEFAULT_GGUF_PATH,
        "endpoint": OLLAMA_ENDPOINT,
    })
    return {"success": True, "provider": ACTIVE_PROVIDER, "model": OLLAMA_MODEL}


@legacy_router.get("/integrations/status")
async def integrations_status():
    from R1.chat_apps import chat_apps
    return chat_apps.get_status()


@legacy_router.get("/capabilities")
async def capabilities_list(request: Request):
    from R1.capabilities import list_capabilities
    domain = request.query_params.get("domain")
    status = request.query_params.get("status")
    return {"capabilities": list_capabilities(domain=domain, status=status)}


@legacy_router.get("/capabilities/summary")
async def capabilities_summary():
    from R1.capabilities import summarize_capabilities
    return summarize_capabilities()


@legacy_router.post("/capabilities/execute")
async def capabilities_execute(request: Request):
    from R1.capability_engine import capability_engine
    body = await request.json()
    domain = body.get("domain", "")
    action = body.get("action", "")
    payload = body.get("payload", {})
    return await capability_engine.execute(domain, action, payload)


@legacy_router.get("/ollama/models")
async def list_ollama_models():
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{OLLAMA_ENDPOINT}/api/tags")
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                return {"success": True, "models": [{"name": m["name"]} for m in models]}
            return {"success": False, "error": "Ollama not running"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@legacy_router.post("/ollama/set-model")
async def set_ollama_model(request: Request):
    global OLLAMA_MODEL
    body = await request.json()
    model = body.get("model", "")
    if model:
        OLLAMA_MODEL = model
        return {"success": True, "model": model}
    return {"success": False, "error": "No model specified"}


@legacy_router.get("/ollama/status")
async def ollama_status():
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_ENDPOINT}/api/tags")
            if resp.status_code == 200:
                return {"available": True, "model": OLLAMA_MODEL, "models": resp.json().get("models", [])}
            return {"available": False}
    except Exception as e:
        return {"available": False, "error": str(e)}


@legacy_router.get("/self/stats")
async def get_self_stats():
    """Get self-improvement statistics"""
    if not SELF_IMPROVER_AVAILABLE:
        return {"error": "Self-improver not available"}
    try:
        improver = get_self_improver()
        return improver.get_stats()
    except Exception as e:
        return {"error": str(e)}


@legacy_router.get("/self/learned")
async def get_learned():
    """Get all learned things"""
    if not SELF_IMPROVER_AVAILABLE:
        return {"error": "Self-improver not available"}
    try:
        improver = get_self_improver()
        return {"learned": improver.memory.get("learned", {})}
    except Exception as e:
        return {"error": str(e)}


@legacy_router.post("/self/analyze")
async def analyze_code(request: Request):
    """Analyze own code for improvements"""
    if not SELF_IMPROVER_AVAILABLE:
        return {"error": "Self-improver not available"}
    
    body = await request.json()
    file_path = body.get("path", "R1/api/server.py")
    
    try:
        improver = get_self_improver()
        return improver.suggest_improvements(file_path)
    except Exception as e:
        return {"error": str(e)}


@legacy_router.post("/self/improve")
async def apply_improvement(request: Request):
    """Apply an improvement to the codebase"""
    if not SELF_IMPROVER_AVAILABLE:
        return {"error": "Self-improver not available"}
    
    body = await request.json()
    improvement = body.get("improvement", {})
    
    try:
        improver = get_self_improver()
        improver.apply_improvement(improvement)
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}


@legacy_router.post("/self/write")
async def self_write_code(request: Request):
    """R1 writes code to improve itself"""
    if not SELF_IMPROVER_AVAILABLE:
        return {"error": "Self-improver not available"}
    
    body = await request.json()
    file_path = body.get("path", "")
    code = body.get("code", "")
    
    if not file_path or not code:
        return {"error": "path and code required"}
    
    try:
        # Write the code
        full_path = Path(file_path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(code, encoding='utf-8')
        
        # Log the improvement
        improver = get_self_improver()
        improver.apply_improvement({
            "type": "code_write",
            "path": file_path,
            "timestamp": datetime.now().isoformat()
        })
        
        return {"success": True, "path": file_path}
    except Exception as e:
        return {"error": str(e)}


# ==================== VOICE ENDPOINTS ====================

@legacy_router.get("/voice/status")
async def get_voice_status():
    """Get voice system status"""
    if not VOICE_AVAILABLE:
        return {"available": False, "error": "Voice system not available"}
    return voice_status()


@legacy_router.post("/voice/speak")
async def voice_speak(request: Request):
    """Make R1 speak the given text"""
    body = await request.json()
    text = body.get("text", "")
    
    if not text:
        return {"success": False, "error": "No text provided"}
    
    if VOICE_AVAILABLE:
        speak(text)
        return {"success": True, "speaking": True}
    return {"success": False, "error": "TTS not available"}


@legacy_router.post("/voice/stop")
async def voice_stop():
    """Stop R1 from speaking"""
    if VOICE_AVAILABLE:
        stop_speaking()
        return {"success": True, "speaking": False}
    return {"success": False}


@legacy_router.post("/voice/listen")
async def voice_listen():
    """Listen for speech (returns text)"""
    if not VOICE_AVAILABLE:
        return {"success": False, "error": "STT not available"}
    
    text = listen(timeout=5)
    if text:
        return {"success": True, "text": text}
    return {"success": False, "error": "No speech detected"}


@legacy_router.post("/voice/wake/start")
async def voice_wake_start():
    """Start wake word listener"""
    if not VOICE_AVAILABLE:
        return {"success": False, "error": "STT not available"}
    
    def on_wake():
        logger.info("Wake word detected!")
    
    start_wake_listener(on_wake)
    return {"success": True, "wake_word": WAKE_WORD}


@legacy_router.post("/voice/wake/stop")
async def voice_wake_stop():
    """Stop wake word listener"""
    if VOICE_AVAILABLE:
        stop_wake_listener()
    return {"success": True}


@legacy_router.get("/skills/enhanced")
async def list_enhanced_skills():
    manager = _require_component(enhanced_skills, "enhanced skill manager")
    return {"skills": manager.list_skills()}


@legacy_router.post("/skills/enhanced/install")
async def install_skill(request: Request):
    body = await request.json()
    skill_name = body.get("name", "")
    source = body.get("source", "")
    
    from R1.skills import SkillInstallSpec, InstallKind
    
    if source.startswith("npm:"):
        spec = SkillInstallSpec(kind=InstallKind.NPM, package=source[4:])
    elif source.startswith("brew:"):
        spec = SkillInstallSpec(kind=InstallKind.BREW, formula=source[5:])
    elif source.startswith("http"):
        spec = SkillInstallSpec(kind=InstallKind.DOWNLOAD, url=source)
    else:
        raise HTTPException(status_code=400, detail="Invalid source")
    
    manager = _require_component(enhanced_skills, "enhanced skill manager")
    result = await manager.install_skill(skill_name, spec)
    return {"success": result.success, "output": result.output, "error": result.error}


@legacy_router.post("/skills/enhanced/uninstall")
async def uninstall_skill(request: Request):
    body = await request.json()
    skill_name = body.get("name", "")
    manager = _require_component(enhanced_skills, "enhanced skill manager")
    result = manager.uninstall_skill(skill_name)
    return {"success": result.success, "output": result.output, "error": result.error}


@legacy_router.post("/tts")
async def text_to_speech(request: Request):
    body = await request.json()
    text = body.get("text", "")
    if not text:
        return {"error": "No text provided"}
    
    audio_b64 = await tts_engine.speak(text)
    if audio_b64:
        return {"audio": audio_b64, "format": "wav"}
    return {"error": "TTS failed"}


browser_controller = None

async def get_browser():
    global browser_controller
    if browser_controller is None:
        from R1.browser import BrowserController
        browser_controller = await BrowserController.get(headless=True)
    return browser_controller


@legacy_router.post("/browser/open")
async def browser_open(request: Request):
    body = await request.json()
    url = body.get("url", "https://www.google.com")
    browser = await get_browser()
    result = await browser.navigate(url)
    return {"success": result.success, "content": result.content, "error": result.error}


@legacy_router.post("/browser/screenshot")
async def browser_screenshot(request: Request = None):
    browser = await get_browser()
    result = await browser.screenshot()
    return {"success": result.success, "image": result.data, "error": result.error}


@legacy_router.post("/browser/search")
async def browser_search(request: Request):
    body = await request.json()
    query = body.get("query", "")
    browser = await get_browser()
    result = await browser.search_google(query)
    return {"success": result.success, "results": result.data[:5] if result.data else [], "error": result.error}


@legacy_router.post("/browser/click")
async def browser_click(request: Request):
    body = await request.json()
    selector = body.get("selector", "")
    browser = await get_browser()
    result = await browser.click(selector)
    return {"success": result.success, "content": result.content, "error": result.error}


@legacy_router.post("/browser/fill")
async def browser_fill(request: Request):
    body = await request.json()
    selector = body.get("selector", "")
    value = body.get("value", "")
    browser = await get_browser()
    result = await browser.fill(selector, value)
    return {"success": result.success, "content": result.content, "error": result.error}


@legacy_router.post("/browser/get")
async def browser_get(request: Request):
    body = await request.json()
    selector = body.get("selector", "")
    browser = await get_browser()
    result = await browser.get_text(selector)
    return {"success": result.success, "content": result.content, "error": result.error}


@legacy_router.post("/browser/execute")
async def browser_execute(request: Request):
    body = await request.json()
    script = body.get("script", "")
    browser = await get_browser()
    result = await browser.execute(script)
    return {"success": result.success, "result": result.content, "error": result.error}


@legacy_router.post("/shell")
async def run_shell(request: Request):
    body = await request.json()
    command = body.get("command", "")
    result = await Shell.execute(command)
    return {"success": result.success, "output": result.output, "error": result.error}


@legacy_router.get("/system")
async def system_info():
    return SystemInfo.info()


@legacy_router.post("/file/read")
async def file_read(request: Request):
    body = await request.json()
    path = body.get("path", "")
    result = FileSystem.read(path)
    return {"success": result.success, "content": result.output, "error": result.error}


@legacy_router.post("/file/write")
async def file_write(request: Request):
    body = await request.json()
    path = body.get("path", "")
    content = body.get("content", "")
    result = FileSystem.write(path, content)
    return {"success": result.success, "output": result.output, "error": result.error}


@legacy_router.post("/file/list")
async def file_list(request: Request):
    body = await request.json()
    path = body.get("path", ".")
    result = FileSystem.list(path)
    return {"success": result.success, "files": result.output, "error": result.error}


@legacy_router.post("/upload")
async def upload_file(request: Request):
    try:
        from R1.multimodal import multimodal
        
        content = await request.body()
        filename = request.headers.get("X-Filename", "uploaded_file")
        
        result = await multimodal.handle_upload(content, filename)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@legacy_router.post("/code/execute")
async def code_execute(request: Request):
    try:
        from R1.code_executor import code_executor
        
        body = await request.json()
        code = body.get("code", "")
        language = body.get("language", "python")
        
        if language == "python":
            result = await code_executor.execute_python(code)
        else:
            result = await code_executor.execute_shell(code)
        
        return {
            "success": result.success,
            "output": result.output,
            "error": result.error,
            "execution_time": result.execution_time
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@legacy_router.get("/agent/tasks")
async def agent_tasks():
    from R1.agent import agent
    return {"tasks": agent.list_tasks()}


@legacy_router.post("/agent/execute")
async def agent_execute(request: Request):
    try:
        from R1.agent import agent
        
        body = await request.json()
        task_type = body.get("type", "chat")
        
        if task_type == "plan":
            task = await agent.plan_task(body.get("message", ""))
            return {"task_id": task.id, "steps": task.steps}
        elif task_type == "run":
            task = await agent.execute_task(body.get("task_id", ""))
            return {"task_id": task.id, "status": task.status.value, "result": task.result}
        
        return {"error": "Unknown task type"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@legacy_router.get("/memory/conversations")
async def memory_conversations():
    from R1.memory_persistent import memory
    convos = memory.get_conversations(50)
    return {
        "conversations": [
            {
                "id": c.id,
                "timestamp": c.timestamp,
                "user": c.user_message,
                "ai": c.ai_response
            }
            for c in convos
        ]
    }


@legacy_router.get("/memory/facts")
async def memory_facts():
    from R1.memory_persistent import memory
    facts = memory.get_facts()
    return {"facts": facts}


@legacy_router.get("/tools/email")
async def tools_email():
    from R1.tools import tools
    return {"configured": tools.email.is_configured()}


@legacy_router.post("/tools/email/send")
async def tools_email_send(request: Request):
    from R1.tools import tools
    body = await request.json()
    return await tools.email.send_email(
        body.get("to", ""),
        body.get("subject", ""),
        body.get("body", "")
    )


@legacy_router.get("/tools/calendar")
async def tools_calendar(request: Request):
    from R1.tools import tools
    date = request.query_params.get("date")
    return await tools.calendar.get_events(date)


@legacy_router.post("/tools/calendar")
async def tools_calendar_add(request: Request):
    from R1.tools import tools
    body = await request.json()
    return await tools.calendar.add_event(
        body.get("title", ""),
        body.get("date", ""),
        body.get("time", ""),
        body.get("description", "")
    )


@legacy_router.post("/memory/remember")
async def memory_remember(request: Request):
    body = await request.json()
    key = body.get("key", "")
    value = body.get("value", "")
    _memory_remember(key, value)
    return {"success": True, "key": key}


@legacy_router.get("/memory/recall/{key}")
async def memory_recall(key: str):
    value = _memory_recall(key)
    return {"key": key, "value": value}


@legacy_router.get("/cron/jobs")
async def list_cron_jobs():
    manager = _require_component(cron_manager, "cron manager")
    return {"jobs": manager.list_jobs()}


@legacy_router.post("/cron/jobs")
async def create_cron_job(request: Request):
    manager = _require_component(cron_manager, "cron manager")
    body = await request.json()
    job = CronJob(
        id=body.get("id", ""),
        name=body.get("name", ""),
        description=body.get("description", ""),
        cron_expression=body.get("cron_expression"),
        interval_seconds=body.get("interval_seconds"),
        command=body.get("command"),
        webhook_url=body.get("webhook_url"),
        skill=body.get("skill"),
        skill_args=body.get("skill_args", {}),
        timezone=body.get("timezone", "UTC"),
    )
    success = await manager.add_job(job)
    return {"success": success}


@legacy_router.post("/cron/jobs/{job_id}/run")
async def run_cron_job(job_id: str):
    manager = _require_component(cron_manager, "cron manager")
    run = await manager.run_job(job_id)
    if run:
        return {"success": True, "run_id": run.run_id, "status": run.status.value}
    return {"success": False, "error": "Job not found"}


@legacy_router.post("/cron/jobs/{job_id}/enable")
async def enable_cron_job(job_id: str):
    manager = _require_component(cron_manager, "cron manager")
    success = await manager.enable_job(job_id)
    return {"success": success}


@legacy_router.post("/cron/jobs/{job_id}/disable")
async def disable_cron_job(job_id: str):
    manager = _require_component(cron_manager, "cron manager")
    success = await manager.disable_job(job_id)
    return {"success": success}


@legacy_router.delete("/cron/jobs/{job_id}")
async def delete_cron_job(job_id: str):
    manager = _require_component(cron_manager, "cron manager")
    success = await manager.remove_job(job_id)
    return {"success": success}


@legacy_router.get("/webhooks")
async def list_webhooks():
    manager = _require_component(webhook_manager, "webhook manager")
    return {"webhooks": manager.list_webhooks()}


@legacy_router.post("/webhooks")
async def create_webhook(request: Request):
    manager = _require_component(webhook_manager, "webhook manager")
    body = await request.json()
    webhook = manager.add_webhook(
        name=body.get("name", ""),
        url=body.get("url", ""),
        events=body.get("events", []),
        secret=body.get("secret"),
    )
    return {"webhook": {"id": webhook.id, "name": webhook.name, "url": webhook.url}}


@legacy_router.delete("/webhooks/{webhook_id}")
async def delete_webhook(webhook_id: str):
    manager = _require_component(webhook_manager, "webhook manager")
    success = manager.delete_webhook(webhook_id)
    return {"success": success}


@legacy_router.post("/webhooks/trigger")
async def trigger_webhook(request: Request):
    manager = _require_component(webhook_manager, "webhook manager")
    body = await request.json()
    event = body.get("event", "")
    payload = body.get("payload", {})
    source = body.get("source", "api")
    results = await manager.trigger(event, payload, source)
    return {"results": results}


@legacy_router.get("/gateway/sessions")
async def list_gateway_sessions():
    gateway_instance = _require_component(gateway, "gateway")
    return {"sessions": list(gateway_instance.sessions.values())}


@legacy_router.get("/gateway/agents")
async def list_gateway_agents():
    gateway_instance = _require_component(gateway, "gateway")
    return {"agents": list(gateway_instance.agents.values())}


@legacy_router.post("/gateway/message/send")
async def gateway_send_message(request: Request):
    gateway_instance = _require_component(gateway, "gateway")
    body = await request.json()
    to = body.get("to", "")
    message = body.get("message", "")
    await gateway_instance.conn_manager.send_message(to, {
        "type": "message",
        "content": message,
        "timestamp": datetime.now().isoformat(),
    })
    return {"success": True}


@legacy_router.post("/gateway/broadcast")
async def gateway_broadcast(request: Request):
    gateway_instance = _require_component(gateway, "gateway")
    body = await request.json()
    message = body.get("message", "")
    await gateway_instance.conn_manager.broadcast({
        "type": "broadcast",
        "content": message,
        "timestamp": datetime.now().isoformat(),
    })
    return {"success": True}


# ============================================
# NEW SYSTEM ENDPOINTS
# Cognitive, Voice, Security, Analytics, etc.
# ============================================

@legacy_router.get("/systems/status")
async def all_systems_status():
    """Get status of all integrated systems"""
    from R1.unified import get_r1_system
    r1 = get_r1_system()
    return await r1.get_full_status()


@legacy_router.get("/operations/overview")
async def operations_overview():
    """Unified safe operations dashboard summary"""
    overview = {
        "timestamp": datetime.utcnow().isoformat(),
        "platform": "R1 Enterprise Command",
        "mode": "civilian-safe",
        "domains": [
            "cognitive",
            "voice",
            "analytics",
            "diagnostics",
            "decisions",
            "planning",
            "infrastructure",
            "emergency",
            "chat_apps",
        ],
    }

    try:
        from R1.cognitive import get_cognitive_system
        cognitive = get_cognitive_system()
        overview["cognitive"] = {
            "contexts": len(cognitive.context.frames),
            "knowledge_nodes": len(cognitive.knowledge.nodes),
            "active_hypotheses": len(cognitive.hypothesis.get_active_hypotheses()),
            "workload": cognitive.workload.get_workload_summary(),
        }
    except Exception as e:
        overview["cognitive"] = {"error": str(e)}

    try:
        from R1.voice import get_voice_system
        voice = get_voice_system()
        overview["voice"] = {
            "state": voice.state.value,
            "languages": len(voice.languages.supported_languages),
            "sessions": len(voice.dialogue.sessions),
            "enrolled_voices": len(voice.auth.enrolled_users),
        }
    except Exception as e:
        overview["voice"] = {"error": str(e)}

    try:
        from R1.analytics import get_analytics_system
        analytics = get_analytics_system()
        overview["analytics"] = {
            "summary": analytics.get_threat_summary(),
            "tracked_metrics": len(analytics.trends.time_series),
            "maintenance_assets": len(analytics.maintenance.equipment),
        }
    except Exception as e:
        overview["analytics"] = {"error": str(e)}

    try:
        from R1.diagnostics import get_diagnostics_system
        diagnostics = get_diagnostics_system()
        overview["diagnostics"] = await diagnostics.run_diagnostics()
    except Exception as e:
        overview["diagnostics"] = {"error": str(e)}

    try:
        from R1.decisions import get_decision_system
        decisions = get_decision_system()
        overview["decisions"] = decisions.get_system_status()
    except Exception as e:
        overview["decisions"] = {"error": str(e)}

    try:
        from R1.planning import get_planning_system
        planning = get_planning_system()
        overview["planning"] = {
            "missions": len(planning.missions.missions),
            "resources": len(planning.resources.resources),
            "contingencies": len(planning.contingencies.contingencies),
            "routes": len(planning.logistics.routes),
        }
    except Exception as e:
        overview["planning"] = {"error": str(e)}

    try:
        from R1.infrastructure import get_infrastructure_system
        infrastructure = get_infrastructure_system()
        overview["infrastructure"] = {
            "devices": len(infrastructure.facility.devices),
            "users": len(infrastructure.security.users),
            "power": infrastructure.get_power_status(),
        }
    except Exception as e:
        overview["infrastructure"] = {"error": str(e)}

    try:
        from R1.emergency import get_emergency_system
        emergency = get_emergency_system()
        overview["emergency"] = emergency.get_system_status()
    except Exception as e:
        overview["emergency"] = {"error": str(e)}

    try:
        from R1.chat_apps import chat_apps
        overview["chat_apps"] = chat_apps.get_status()
    except Exception as e:
        overview["chat_apps"] = {"error": str(e)}

    try:
        from R1.capabilities import summarize_capabilities
        overview["capabilities"] = summarize_capabilities()
    except Exception as e:
        overview["capabilities"] = {"error": str(e)}

    return overview


# --- COGNITIVE SYSTEM ---
@legacy_router.post("/cognitive/process")
async def cognitive_process(request: Request):
    """Process with cognitive reasoning engine"""
    from R1.cognitive import get_cognitive_system
    body = await request.json()
    prompt = body.get("prompt", "")
    session_id = body.get("session_id", "default")
    cognitive = get_cognitive_system()
    return await cognitive.process(prompt, session_id)


@legacy_router.get("/cognitive/context/{session_id}")
async def cognitive_context(session_id: str):
    """Get conversation context"""
    from R1.cognitive import get_cognitive_system
    cognitive = get_cognitive_system()
    return cognitive.context.get_conversation_summary(session_id)


@legacy_router.post("/cognitive/learn")
async def cognitive_learn(request: Request):
    """Learn from interaction"""
    from R1.cognitive import get_cognitive_system
    body = await request.json()
    cognitive = get_cognitive_system()
    return await cognitive.learning.learn_from_interaction(body)


# --- VOICE SYSTEM ---
@legacy_router.post("/voice/process")
async def voice_process(request: Request):
    """Process voice command"""
    from R1.voice import get_voice_system
    body = await request.json()
    text = body.get("text", "")
    session_id = body.get("session_id", "default")
    voice = get_voice_system()
    return await voice.process_command(text, session_id)


@legacy_router.post("/voice/respond")
async def voice_respond(request: Request):
    """Voice system text response"""
    from R1.voice import get_voice_system
    body = await request.json()
    text = body.get("text", "")
    voice = get_voice_system()
    return await voice.respond(text, blocking=False)


@legacy_router.get("/voice/languages")
async def voice_languages():
    """Get supported languages"""
    from R1.voice import get_voice_system
    voice = get_voice_system()
    return {"languages": voice.languages.supported_languages}


# --- CYBERSECURITY SYSTEM ---
@legacy_router.post("/security/scan")
async def security_scan(request: Request):
    """Scan for malware"""
    from R1.cybersecurity import get_cybersecurity_system
    body = await request.json()
    path = body.get("path", ".")
    security = get_cybersecurity_system()
    return security.scan_for_malware(path)


@legacy_router.post("/security/analyze")
async def security_analyze_request(request: Request):
    """Analyze request for threats"""
    from R1.cybersecurity import get_cybersecurity_system
    body = await request.json()
    security = get_cybersecurity_system()
    return security.analyze_request(body)


@legacy_router.post("/security/encrypt")
async def security_encrypt(request: Request):
    """Encrypt data"""
    from R1.cybersecurity import get_cybersecurity_system
    body = await request.json()
    import base64
    data = body.get("data", "")
    data_bytes = base64.b64decode(data) if isinstance(data, str) else data
    security = get_cybersecurity_system()
    encrypted = security.encrypt_data(data_bytes)
    return {"encrypted": base64.b64encode(encrypted).decode()}


@legacy_router.post("/security/auth")
async def security_auth(request: Request):
    """Authenticate user"""
    from R1.cybersecurity import get_cybersecurity_system
    body = await request.json()
    user_id = body.get("user_id", "")
    password = body.get("password", "")
    security = get_cybersecurity_system()
    return security.authenticate(user_id, password)


# --- ANALYTICS SYSTEM ---
@legacy_router.post("/analytics/risk")
async def analytics_risk(request: Request):
    """Analyze risk"""
    from R1.analytics import get_analytics_system
    body = await request.json()
    risk_type = body.get("type", "general")
    factors = body.get("factors", {})
    analytics = get_analytics_system()
    return analytics.analyze_risk(risk_type, factors)


@legacy_router.post("/analytics/anomaly")
async def analytics_anomaly(request: Request):
    """Detect anomaly"""
    from R1.analytics import get_analytics_system
    body = await request.json()
    metric = body.get("metric", "")
    value = body.get("value", 0.0)
    analytics = get_analytics_system()
    analytics.detect_anomalies(metric, value)
    return {"success": True}


@legacy_router.get("/analytics/threats")
async def analytics_threats():
    """Get threat summary"""
    from R1.analytics import get_analytics_system
    analytics = get_analytics_system()
    return analytics.get_threat_summary()


@legacy_router.get("/analytics/trend/{metric}")
async def analytics_trend(metric: str):
    """Analyze trend"""
    from R1.analytics import get_analytics_system
    analytics = get_analytics_system()
    return analytics.analyze_trend(metric)


# --- DIAGNOSTICS SYSTEM ---
@legacy_router.get("/diagnostics/health")
async def diagnostics_health():
    """Get system health"""
    from R1.diagnostics import get_diagnostics_system
    diag = get_diagnostics_system()
    return await diag.run_diagnostics()


@legacy_router.get("/diagnostics/benchmark")
async def diagnostics_benchmark(request: Request):
    """Run benchmark"""
    from R1.diagnostics import get_diagnostics_system
    diag = get_diagnostics_system()
    benchmark_type = request.query_params.get("type", "system")
    return await diag.run_benchmark(benchmark_type)


@legacy_router.post("/diagnostics/repair")
async def diagnostics_repair(request: Request):
    """Attempt auto-repair"""
    from R1.diagnostics import get_diagnostics_system
    body = await request.json()
    issue_type = body.get("issue_type", "")
    diag = get_diagnostics_system()
    return await diag.attempt_auto_repair(issue_type)


@legacy_router.get("/diagnostics/report")
async def diagnostics_report():
    """Generate diagnostic report"""
    from R1.diagnostics import get_diagnostics_system
    diag = get_diagnostics_system()
    return await diag.generate_diagnostic_report()


# --- DECISIONS SYSTEM ---
@legacy_router.post("/decisions/make")
async def decisions_make(request: Request):
    """Make autonomous decision"""
    from R1.decisions import get_decision_system, Priority
    body = await request.json()
    action = body.get("action", "")
    context = body.get("context", {})
    priority = body.get("priority", 3)
    decisions = get_decision_system()
    return await decisions.make_decision(action, context, Priority(priority))


@legacy_router.get("/decisions/pending")
async def decisions_pending():
    """Get pending decisions"""
    from R1.decisions import get_decision_system
    decisions = get_decision_system()
    return {"decisions": decisions.get_pending_decisions()}


@legacy_router.get("/decisions/status")
async def decisions_status():
    """Get decision system status"""
    from R1.decisions import get_decision_system
    decisions = get_decision_system()
    return decisions.get_system_status()


# --- PLANNING SYSTEM ---
@legacy_router.post("/planning/mission")
async def planning_create_mission(request: Request):
    """Create mission"""
    from R1.planning import get_planning_system
    body = await request.json()
    planning = get_planning_system()
    mission_id = planning.create_mission(
        body.get("name", ""),
        body.get("description", ""),
        body.get("objectives", [])
    )
    return {"mission_id": mission_id}


@legacy_router.get("/planning/mission/{mission_id}")
async def planning_get_mission(mission_id: str):
    """Get mission status"""
    from R1.planning import get_planning_system
    planning = get_planning_system()
    return planning.get_mission_status(mission_id)


@legacy_router.post("/planning/mission/{mission_id}/task")
async def planning_add_task(request: Request, mission_id: str):
    """Add task to mission"""
    from R1.planning import get_planning_system
    body = await request.json()
    planning = get_planning_system()
    success = planning.add_mission_task(
        mission_id,
        body.get("name", ""),
        body.get("type", "generic")
    )
    return {"success": success}


@legacy_router.get("/planning/resources")
async def planning_resources():
    """Get available resources"""
    from R1.planning import get_planning_system
    planning = get_planning_system()
    return {"resources": planning.resources.get_available_resources()}


# --- EMERGENCY SYSTEM ---
@legacy_router.post("/emergency/alert")
async def emergency_alert(request: Request):
    """Create emergency alert"""
    from R1.emergency import get_emergency_system, EmergencyLevel
    body = await request.json()
    emergency = get_emergency_system()
    alert_id = emergency.create_emergency_alert(
        EmergencyLevel(body.get("level", "info")),
        body.get("title", ""),
        body.get("description", "")
    )
    return {"alert_id": alert_id}


@legacy_router.get("/emergency/alerts")
async def emergency_alerts():
    """Get active alerts"""
    from R1.emergency import get_emergency_system
    emergency = get_emergency_system()
    return {"alerts": emergency.alerts.get_active_alerts()}


@legacy_router.post("/emergency/shutdown")
async def emergency_shutdown(request: Request):
    """Emergency shutdown"""
    from R1.emergency import get_emergency_system
    body = await request.json()
    emergency = get_emergency_system()
    return await emergency.emergency_shutdown(body.get("emergency", False))


@legacy_router.get("/emergency/status")
async def emergency_status():
    """Get emergency system status"""
    from R1.emergency import get_emergency_system
    emergency = get_emergency_system()
    return emergency.get_system_status()


# --- INFRASTRUCTURE SYSTEM ---
@legacy_router.get("/infrastructure/status")
async def infrastructure_status():
    """Get infrastructure status"""
    from R1.infrastructure import get_infrastructure_system
    infra = get_infrastructure_system()
    return infra.get_power_status()


@legacy_router.post("/infrastructure/device/control")
async def infrastructure_control_device(request: Request):
    """Control device"""
    from R1.infrastructure import get_infrastructure_system
    body = await request.json()
    infra = get_infrastructure_system()
    return await infra.control_device(
        body.get("device_name", ""),
        body.get("command", ""),
        body.get("params", {})
    )


@legacy_router.post("/infrastructure/security/access")
async def infrastructure_check_access(request: Request):
    """Check security access"""
    from R1.infrastructure import get_infrastructure_system
    body = await request.json()
    infra = get_infrastructure_system()
    return {"access_granted": infra.check_security_access(
        body.get("user_id", ""),
        body.get("resource", "")
    )}


# --- UNIFIED COMMAND ---
@legacy_router.post("/command")
async def unified_command(request: Request):
    """Unified command processor"""
    from R1.unified import get_r1_system
    body = await request.json()
    command = body.get("command", "")
    context = body.get("context", {})
    r1 = get_r1_system()
    return await r1.process_command(command, context)


# Catch-all for static files (MUST BE LAST)
@legacy_router.get("/{path:path}")
async def serve_static(path: str):
    file_path = WEB_DIR / path
    if file_path.exists() and file_path.is_file():
        return FileResponse(str(file_path))
    return FileResponse(str(WEB_DIR / "index.html"))

def open_browser():
    import webbrowser
    webbrowser.open("http://127.0.0.1:8000")

if __name__ == "__main__":
    threading.Thread(target=open_browser, daemon=True).start()
    print("\n" + "="*50)
    print("  ORION-R1 CONTROL INTERFACE")
    print("  Opening browser at http://localhost:8000")
    print("="*50 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
