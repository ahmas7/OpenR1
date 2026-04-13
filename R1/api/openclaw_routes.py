"""
OpenClaw API Routes for R1
Extends the R1 API with OpenClaw features
"""
import os
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from R1.openclaw import openclaw
from R1.openclaw_persona import persona
from R1.openclaw_voice import (
    start_voice_mode, stop_voice_mode,
    start_wake_word_listener, stop_wake_word_listener,
    get_voice_status
)
from R1.openclaw_proactive import (
    get_proactive_status, add_reminder,
    proactive_agent
)
from R1.openclaw_skills import skill_registry
from R1.openclaw_telegram import get_telegram_status

router = APIRouter(prefix="/openclaw", tags=["openclaw"])


# === Request/Response Models ===

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"
    use_voice: Optional[bool] = False


class PersonaUpdateRequest(BaseModel):
    name: Optional[str] = None
    user_name: Optional[str] = None
    personality: Optional[str] = None
    voice_enabled: Optional[bool] = None
    wake_word: Optional[str] = None
    proactive_enabled: Optional[bool] = None
    briefing_time: Optional[str] = None


class ReminderRequest(BaseModel):
    title: str
    when: Optional[str] = None
    recurrence: Optional[str] = None


class SkillCommandRequest(BaseModel):
    command: str
    args: Optional[Dict[str, Any]] = None


# === OpenClaw Status ===

@router.get("/status")
async def openclaw_status():
    """Get OpenClaw system status"""
    return openclaw.get_status()


@router.get("/welcome")
async def openclaw_welcome():
    """Get welcome message"""
    return {
        "welcome": openclaw.get_welcome_message(),
        "persona": persona.get_summary(),
    }


# === Chat Interface ===

@router.post("/chat")
async def openclaw_chat(request: ChatRequest):
    """Chat with OpenClaw"""
    try:
        response = await openclaw.chat(request.message, request.session_id)
        return {
            "response": response,
            "timestamp": datetime.utcnow().isoformat(),
            "session_id": request.session_id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Persona Management ===

@router.get("/persona")
async def get_persona():
    """Get current persona settings"""
    return {
        "name": persona.config.name,
        "user_name": persona.config.user_name,
        "personality": persona.config.personality,
        "voice_enabled": persona.config.voice_enabled,
        "wake_word": persona.config.wake_word,
        "proactive_enabled": persona.config.proactive_enabled,
        "morning_briefing": persona.config.morning_briefing,
        "briefing_time": persona.config.briefing_time,
        "user_preferences": persona.config.user_preferences,
        "user_habits": persona.config.user_habits,
    }


@router.post("/persona")
async def update_persona(request: PersonaUpdateRequest):
    """Update persona settings"""
    results = []

    if request.name:
        results.append(persona.set_name(request.name))

    if request.user_name:
        results.append(persona.set_user_name(request.user_name))

    if request.personality:
        results.append(persona.set_personality(request.personality))

    if request.voice_enabled is not None:
        results.append(persona.toggle_voice(request.voice_enabled))

    if request.wake_word:
        results.append(persona.set_wake_word(request.wake_word))

    if request.proactive_enabled is not None:
        results.append(persona.set_proactive(request.proactive_enabled))

    if request.briefing_time:
        results.append(persona.set_briefing_time(request.briefing_time))

    return {
        "updated": True,
        "results": results,
        "persona": persona.get_summary(),
    }


# === Voice Control ===

@router.get("/voice/status")
async def voice_status():
    """Get voice system status"""
    return get_voice_status()


@router.post("/voice/start")
async def voice_start():
    """Start voice conversation mode"""
    success = openclaw.start_voice()
    return {"success": success, "active": get_voice_status()["conversation_active"]}


@router.post("/voice/stop")
async def voice_stop():
    """Stop voice conversation mode"""
    openclaw.stop_voice()
    return {"success": True, "active": False}


@router.post("/voice/wake/enable")
async def voice_wake_enable():
    """Enable wake word listener"""
    success = openclaw.enable_wake_word()
    return {"success": success}


@router.post("/voice/wake/disable")
async def voice_wake_disable():
    """Disable wake word listener"""
    openclaw.disable_wake_word()
    return {"success": True}


# === Proactive Features ===

@router.get("/proactive/status")
async def proactive_status():
    """Get proactive agent status"""
    return get_proactive_status()


@router.post("/proactive/reminder")
async def create_reminder(request: ReminderRequest):
    """Create a new reminder"""
    result = add_reminder(request.title, request.when, request.recurrence)
    return {"success": True, "message": result}


@router.get("/proactive/reminders")
async def list_reminders():
    """List pending reminders"""
    return {"reminders": proactive_agent.reminder_manager.get_pending()}


@router.post("/proactive/briefing")
async def trigger_briefing():
    """Trigger morning briefing manually"""
    briefing = persona.generate_briefing()

    # Speak if enabled
    if persona.config.voice_enabled:
        await persona.speak(briefing, blocking=False)

    return {
        "briefing": briefing,
        "spoken": persona.config.voice_enabled,
    }


# === Skills ===

@router.get("/skills")
async def list_skills():
    """List available OpenClaw skills"""
    return {
        "skills": skill_registry.get_available_skills(),
    }


@router.post("/skills/execute")
async def execute_skill(request: SkillCommandRequest):
    """Execute a skill command"""
    import asyncio

    try:
        result = await skill_registry.process_command(request.command)
        return {
            "success": result is not None,
            "result": result,
            "command": request.command,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "command": request.command,
        }


# === Telegram ===

@router.get("/telegram/status")
async def telegram_status():
    """Get Telegram bot status"""
    return get_telegram_status()


# === Quick Actions ===

@router.post("/quick/greet")
async def quick_greet():
    """Trigger greeting"""
    greeting = persona.greet()
    if persona.config.voice_enabled:
        await persona.speak(greeting, blocking=False)
    return {"greeting": greeting, "spoken": persona.config.voice_enabled}


@router.post("/quick/learn")
async def quick_learn(request: Request):
    """Learn user preference"""
    body = await request.json()
    key = body.get("key")
    value = body.get("value")

    if not key or value is None:
        raise HTTPException(status_code=400, detail="key and value required")

    result = persona.learn_preference(key, value)
    return {"success": True, "result": result}


# === Memory ===

@router.get("/memory/facts")
async def get_facts():
    """Get learned facts about user"""
    from R1.memory_persistent import memory
    return {"facts": memory.get_facts()}
