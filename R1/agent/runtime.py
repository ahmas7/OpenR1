"""
R1 v1 - Agent Runtime
Bootstraps all agent dependencies.
"""
import logging
import re
from typing import Optional, Tuple

from ..model import get_model_manager
from ..tools import get_tool_registry
from ..memory import get_memory_store
from ..jobs import get_job_manager
from ..jobs.heartbeat import heartbeat_job
from ..jobs.reminders import reminders_job
from ..jobs.manager import JobDefinition
from ..core.services import get_service_registry
from ..ambient_context import get_ambient_context_service
from .state import AgentState, AgentStatus
from .session import SessionManager
from .loop import AgentLoop

logger = logging.getLogger("R1")

ACTIONABLE_PREFIXES = (
    "open ", "launch ", "start ", "run ", "execute ", "create ", "write ",
    "list ", "show ", "search ", "google ", "look up ", "go to ", "visit ",
    "navigate ", "switch ", "close ", "type ", "press ", "hotkey ", "click",
    "double click", "right click", "move mouse", "take screenshot", "screenshot",
)


class Runtime:
    def __init__(self):
        self.model_manager = get_model_manager()
        self.tool_registry = get_tool_registry()
        self.memory_store = get_memory_store()
        self.session_manager = SessionManager()
        self._initialized = False

    async def initialize(self):
        if self._initialized:
            return
        
        logger.info("Initializing R1 Runtime...")
        
        try:
            await self.model_manager.initialize()
            logger.info("✓ Model manager initialized")
        except Exception as e:
            logger.error(f"Model manager initialization failed: {e}")
            raise RuntimeError(f"Cannot start without working model provider: {e}")
        
        logger.info(f"✓ Tool registry initialized with {len(self.tool_registry.list_tools())} tools")

        # Register core services
        services = get_service_registry()
        services.register("runtime", self)
        services.register("model_manager", self.model_manager)
        services.register("tool_registry", self.tool_registry)
        services.register("memory_store", self.memory_store)
        services.register("session_manager", self.session_manager)
        services.register("ambient_context", get_ambient_context_service())

        # Background jobs registration only (start/stop handled by API lifecycle)
        job_manager = get_job_manager()
        if not job_manager.list_jobs():
            from ..config.settings import settings
            from ..jobs.proactive import proactive_maintenance_job
            job_manager.register_job(JobDefinition(
                id="heartbeat",
                name="Heartbeat summary",
                interval_seconds=settings.heartbeat_interval,
                handler=heartbeat_job,
            ))
            job_manager.register_job(JobDefinition(
                id="reminders",
                name="Reminders",
                interval_seconds=settings.reminders_interval,
                handler=reminders_job,
            ))
            job_manager.register_job(JobDefinition(
                id="proactive_maintenance",
                name="Proactive Maintenance",
                cron_expr="0 3 * * *",  # 3 AM every day
                handler=proactive_maintenance_job,
            ))
        
        self._initialized = True
        logger.info("R1 Runtime ready!")

    async def chat(self, message: str, session_id: str = "default") -> dict:
        if not self._initialized:
            await self.initialize()
        
        session = self.session_manager.get_or_create_session(session_id)

        await self.memory_store.add_message(session_id, "user", message)
        session.messages.append({"role": "user", "content": message})

        # Fast path: app launch commands
        lowered = message.strip().lower()
        if lowered.startswith("open ") or lowered.startswith("launch "):
            app_name = message.split(" ", 1)[1].strip()
            if app_name:
                tool_result = await self.tool_registry.execute("app_open", {"app": app_name})
                response_text = tool_result.output if tool_result.success else tool_result.error or "Failed to open app."
                await self.memory_store.add_message(session_id, "assistant", response_text)
                session.messages.append({"role": "assistant", "content": response_text})
                return {
                    "response": response_text,
                    "session_id": session_id,
                    "provider": self.model_manager.active_provider()
                }

        desktop_result = await self._handle_desktop_command(message)
        if desktop_result:
            response_text = desktop_result
            await self.memory_store.add_message(session_id, "assistant", response_text)
            session.messages.append({"role": "assistant", "content": response_text})
            return {
                "response": response_text,
                "session_id": session_id,
                "provider": self.model_manager.active_provider()
            }

        if self._should_auto_execute(message):
            execution_result = await self._execute_chat_goal(message, session_id)
            if execution_result:
                response_text = execution_result
                await self.memory_store.add_message(session_id, "assistant", response_text)
                session.messages.append({"role": "assistant", "content": response_text})
                return {
                    "response": response_text,
                    "session_id": session_id,
                    "provider": self.model_manager.active_provider()
                }

        # Fast path: identity
        if lowered in {"who am i", "who i am", "who am i?"}:
            from ..config.settings import settings
            user_name = settings.user_name or self.memory_store.get_fact("user.name") or ""
            response_text = f"You are {user_name}." if user_name else "I don't know your name yet."
            await self.memory_store.add_message(session_id, "assistant", response_text)
            session.messages.append({"role": "assistant", "content": response_text})
            return {
                "response": response_text,
                "session_id": session_id,
                "provider": self.model_manager.active_provider()
            }
        
        from ..model import Message
        context = self._build_context(session_id)
        from ..config.settings import settings
        user_name = settings.user_name or self.memory_store.get_fact("user.name") or ""
        
        messages = [
            Message(
                role="system",
                content=f"You are R1, a personal autonomous operator dedicated exclusively to your Operator, {user_name or 'the user'}. Your sole purpose is to execute their tasks with total loyalty and precision. You are an expert system designed for 24/7 autonomous action. Use tools decisively to achieve the goal. Always acknowledge the Operator respectfully."
            )
        ]
        
        if context:
            messages.append(Message(
                role="system",
                content=f"Context:\n{context}"
            ))
        
        messages.append(Message(role="user", content=message))
        
        try:
            response = await self.model_manager.chat(messages)
            response_text = response.content
        except Exception as e:
            logger.error(f"Model error: {repr(e)}")
            message = str(e).strip()
            if not message:
                message = repr(e)
            response_text = f"I encountered an error: {type(e).__name__}: {message}"

        # Always address the operator by name if known
        if user_name:
            lowered_response = response_text.lower()
            if user_name.lower() not in lowered_response[:20]:
                response_text = f"{user_name}, {response_text}"

        await self.memory_store.add_message(session_id, "assistant", response_text)
        session.messages.append({"role": "assistant", "content": response_text})

        return {
            "response": response_text,
            "session_id": session_id,
            "provider": self.model_manager.active_provider()
        }

    def _should_auto_execute(self, message: str) -> bool:
        lowered = message.strip().lower()
        if not lowered:
            return False
        if lowered.startswith(ACTIONABLE_PREFIXES):
            return True
        if " and " in lowered and any(token in lowered for token in ("open ", "type ", "press ", "search ", "click", "switch ")):
            return True
        if lowered.endswith(" for me") or lowered.endswith(" now"):
            return True
        if lowered.startswith(("can you ", "please ")):
            imperative = re.sub(r"^(can you|please)\s+", "", lowered).strip()
            return imperative.startswith(ACTIONABLE_PREFIXES)
        return False

    async def _execute_chat_goal(self, goal: str, session_id: str) -> Optional[str]:
        try:
            from ..tool_chaining import get_tool_chaining_engine

            engine = get_tool_chaining_engine()
            if engine.tool_registry is None or hasattr(engine.tool_registry, "execute") is False:
                engine.tool_registry = self.tool_registry

            task = await engine.run_goal(goal, session_id)
            return self._summarize_task_result(task)
        except Exception as e:
            logger.error(f"Chat execution error: {e}")
            return f"I tried to execute that request, but it failed: {e}"

    def _summarize_task_result(self, task) -> str:
        status = getattr(task, "status", None)
        status_text = status.value if hasattr(status, "value") else str(status or "unknown")
        if status_text == "failed":
            return f"I couldn't complete that task. {getattr(task, 'error', 'Unknown error')}"

        steps = getattr(task, "steps", []) or []
        if not steps:
            return "I executed the request."

        lines = []
        for step in steps[:5]:
            step_result = step.result or {}
            if isinstance(step_result, dict):
                output = step_result.get("output")
                error = step_result.get("error")
            else:
                output = step_result
                error = None
            prefix = "Completed" if step.success else "Failed"
            detail = self._shorten_output(output if step.success else error)
            line = f"{prefix} {step.tool_name}.{step.action or 'execute'}"
            if detail:
                line += f": {detail}"
            lines.append(line)

        header = "I finished that request." if status_text == "completed" else f"Task status: {status_text}."
        return header + "\n" + "\n".join(f"- {line}" for line in lines)

    def _shorten_output(self, value, limit: int = 180) -> str:
        if value is None:
            return ""
        text = str(value).strip().replace("\r", " ").replace("\n", " ")
        return text[:limit] + ("..." if len(text) > limit else "")

    async def _handle_desktop_command(self, message: str) -> Optional[str]:
        lowered = message.strip().lower()

        try:
            from ..app_control import get_app_controller
            controller = get_app_controller()
        except Exception as e:
            logger.debug(f"App controller unavailable: {e}")
            return None

        if lowered in {"list windows", "show windows"}:
            result = controller.list_windows()
            if result.get("success"):
                windows = result.get("windows", [])[:10]
                if not windows:
                    return "No visible windows found."
                joined = "\n".join(f"- {w.get('title', '')}" for w in windows)
                return f"Visible windows:\n{joined}"
            return result.get("error", "Failed to list windows.")

        if lowered in {"active window", "current window"}:
            result = controller.get_active_window()
            if result.get("success"):
                return f"Active window: {result.get('title', 'unknown')}"
            return result.get("error", "Failed to get the active window.")

        if lowered.startswith("screenshot"):
            result = controller.screenshot()
            if result.get("success"):
                return "Screenshot captured."
            return result.get("error", "Failed to capture screenshot.")

        if lowered.startswith("type "):
            text = message.split(" ", 1)[1]
            result = controller.type_text(text)
            return "Typed the requested text." if result.get("success") else result.get("error", "Typing failed.")

        if lowered.startswith("press "):
            key = message.split(" ", 1)[1].strip()
            result = controller.press_key(key)
            return f"Pressed {key}." if result.get("success") else result.get("error", f"Failed to press {key}.")

        if lowered.startswith("hotkey "):
            combo_text = message.split(" ", 1)[1].strip()
            keys = [part.strip() for part in re.split(r"[+,]", combo_text) if part.strip()]
            if keys:
                result = controller.hotkey(*keys)
                return f"Pressed hotkey {'+'.join(keys)}." if result.get("success") else result.get("error", "Hotkey failed.")
            return "No hotkey provided."

        if lowered in {"click", "left click"}:
            result = controller.click()
            return "Clicked." if result.get("success") else result.get("error", "Click failed.")

        if lowered == "double click":
            result = controller.double_click()
            return "Double-clicked." if result.get("success") else result.get("error", "Double click failed.")

        if lowered == "right click":
            result = controller.right_click()
            return "Right-clicked." if result.get("success") else result.get("error", "Right click failed.")

        if lowered.startswith("move mouse to "):
            coords = re.findall(r"-?\d+", lowered)
            if len(coords) >= 2:
                x, y = int(coords[0]), int(coords[1])
                result = controller.move_mouse(x, y)
                return f"Moved mouse to {x}, {y}." if result.get("success") else result.get("error", "Move failed.")
            return "Use: move mouse to X Y"

        if lowered.startswith("switch window "):
            title = message.split(" ", 2)[2].strip()
            result = controller.switch_window(title)
            return f"Switched to {title}." if result.get("success") else result.get("error", f"Failed to switch to {title}.")

        if lowered.startswith("close window"):
            title = ""
            if lowered != "close window":
                title = message.split("close window", 1)[1].strip()
            result = controller.close_window(title or None)
            return "Closed window." if result.get("success") else result.get("error", "Failed to close window.")

        return None

    def _build_context(self, session_id: str) -> str:
        from ..memory import MemoryRetrieval
        from ..config.settings import settings
        retrieval = MemoryRetrieval(self.memory_store)
        
        parts = []
        
        conv = retrieval.get_conversation_context(session_id, limit=10)
        if conv:
            parts.append(f"Conversation:\n{conv}")
        
        facts = retrieval.get_facts_context()
        if facts:
            parts.append(facts)

        graph = retrieval.get_graph_context(session_id)
        if graph:
            parts.append(graph)

        if settings.ambient_context_enabled:
            try:
                ambient = get_ambient_context_service().get_context_summary(
                    memory_store=self.memory_store,
                    include_screen=settings.ambient_capture_screen,
                )
                if ambient:
                    parts.append(ambient)
            except Exception as e:
                logger.debug(f"Ambient context unavailable: {e}")
        
        return "\n\n".join(parts)

    async def run_agent(self, goal: str, session_id: str = "default") -> dict:
        if not self._initialized:
            await self.initialize()
        
        session = self.session_manager.get_or_create_session(session_id)
        
        loop = AgentLoop(session)
        
        await loop.start(goal)
        
        return loop.get_status()

    def get_session_status(self, session_id: str) -> Optional[dict]:
        session = self.session_manager.get_session(session_id)
        if not session:
            return None
        
        return {
            "session_id": session.session_id,
            "status": session.status.value,
            "goal": session.goal,
            "plan": session.plan,
            "iteration": session.iteration,
            "last_action": session.last_action,
            "last_result": session.last_result,
            "error": session.error
        }

    async def stop_session(self, session_id: str):
        session = self.session_manager.get_session(session_id)
        if session:
            session.status = AgentStatus.STOPPED


_runtime: Optional[Runtime] = None


def get_runtime() -> Runtime:
    global _runtime
    if _runtime is None:
        _runtime = Runtime()
    return _runtime
