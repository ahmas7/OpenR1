"""
R1 v1 - Heartbeat Job
Periodic status summary for observability.
"""
import logging
from datetime import datetime

from ..tools import get_tool_registry
from ..skills import get_skills_runtime
from ..model import get_model_manager
from ..jobs.reminders import get_reminder_queue

logger = logging.getLogger("R1")


async def heartbeat_job(services) -> None:
    runtime = services.get("runtime")
    model_mgr = get_model_manager()
    tools = get_tool_registry()
    skills = get_skills_runtime()
    reminders = get_reminder_queue()

    try:
        await runtime.initialize()
        await skills.initialize()
    except Exception as e:
        # Avoid crashing the heartbeat on initialization errors
        logger.warning(f"Heartbeat initialization error: {e}")

    # Job manager summary
    job_summary = {}
    try:
        from ..jobs import get_job_manager
        job_summary = get_job_manager().summary()
    except Exception as e:
        logger.warning(f"Heartbeat job summary error: {e}")

    summary = {
        "timestamp": datetime.utcnow().isoformat(),
        "provider": model_mgr.active_provider(),
        "tools": len(tools.list_tools()),
        "skills": len(skills.discover_skills()) if skills else 0,
        "sessions": len(runtime.session_manager.list_sessions()) if runtime else 0,
        "pending_reminders": reminders.pending_count(),
        "jobs": job_summary,
    }

    logger.info(f"Heartbeat: {summary}")
