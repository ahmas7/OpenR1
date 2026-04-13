"""
ORION-R1 Tool Chaining Engine
Autonomous multi-step task execution with self-correction
"""
import asyncio
import json
import shlex
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

DATA_DIR = Path.home() / ".r1" / "tool_chaining"
DATA_DIR.mkdir(parents=True, exist_ok=True)

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class ToolCall:
    tool_name: str
    action: str
    params: Dict
    result: Any = None
    success: bool = False
    error: str = None
    retry_count: int = 0

@dataclass
class Task:
    id: str
    goal: str
    steps: List[ToolCall] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: str = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: str = None
    session_id: str = "default"

class ToolChainingEngine:
    def __init__(self, tool_registry=None):
        self.tool_registry = tool_registry
        self.tasks: Dict[str, Task] = {}
        self.task_file = DATA_DIR / "tasks.json"
        self._load_tasks()
        self.max_retries = 3

    def _load_tasks(self):
        if self.task_file.exists():
            try:
                data = json.loads(self.task_file.read_text())
                for t in data.get("tasks", []):
                    task = Task(
                        id=t["id"],
                        goal=t["goal"],
                        status=TaskStatus(t["status"]),
                        session_id=t.get("session_id", "default")
                    )
                    task.created_at = t.get("created_at", task.created_at)
                    task.completed_at = t.get("completed_at")
                    task.error = t.get("error")
                    task.result = t.get("result")
                    self.tasks[task.id] = task
            except:
                pass

    def _save_tasks(self):
        data = {
            "tasks": [
                {
                    "id": t.id,
                    "goal": t.goal,
                    "status": t.status.value,
                    "session_id": t.session_id,
                    "created_at": t.created_at,
                    "completed_at": t.completed_at,
                    "error": t.error,
                    "result": t.result
                }
                for t in self.tasks.values()
            ]
        }
        self.task_file.write_text(json.dumps(data, indent=2, default=str))

    def register_tool(self, tool_name: str, actions: Dict[str, Callable]):
        """Register a tool with its actions"""
        if self.tool_registry is None:
            self.tool_registry = {}
        self.tool_registry[tool_name] = actions

    async def execute_tool(self, tool_name: str, action: str, params: Dict) -> Dict:
        """Execute a single tool action"""
        if self.tool_registry:
            if hasattr(self.tool_registry, "execute") and isinstance(tool_name, str):
                merged = dict(params)
                if action and "action" not in merged:
                    merged["action"] = action
                result = await self.tool_registry.execute(tool_name, merged)
                return self._normalize_result(result)
            if tool_name in self.tool_registry:
                func = self.tool_registry[tool_name].get(action)
                if func:
                    if asyncio.iscoroutinefunction(func):
                        return await func(**params)
                    else:
                        return func(**params)

        # Fallback to built-in tools
        from R1.tools.filesystem import get_filesystem_tool
        from R1.tools.shell import get_shell_tool
        from R1.tools.code_exec import get_code_exec_tool
        from R1.tools.browser import get_browser_tool
        from R1.app_control import get_app_controller

        builtins = {
            "filesystem": get_filesystem_tool(),
            "shell": get_shell_tool(),
            "code_exec": get_code_exec_tool(),
            "browser": get_browser_tool()
        }

        if tool_name in builtins:
            tool = builtins[tool_name]
            merged = dict(params)
            if action and "action" not in merged:
                merged["action"] = action
            result = await tool.execute(**merged)
            return self._normalize_result(result)

        if tool_name == "app_control":
            controller = get_app_controller()
            if hasattr(controller, action):
                if action == "hotkey" and isinstance(params.get("keys"), list):
                    return getattr(controller, action)(*params["keys"])
                return getattr(controller, action)(**params)

        return {"success": False, "error": f"Tool {tool_name}.{action} not found"}

    def _normalize_result(self, result: Any) -> Dict:
        if hasattr(result, "success") and hasattr(result, "output"):
            return {
                "success": bool(result.success),
                "output": result.output,
                "error": getattr(result, "error", None),
                "requires_confirmation": getattr(result, "requires_confirmation", False),
            }
        if isinstance(result, dict):
            return result
        return {"success": True, "output": result}

    async def execute_step(self, step: ToolCall) -> Dict:
        """Execute a single step with retry logic"""
        for attempt in range(self.max_retries):
            step.retry_count = attempt
            try:
                result = await self.execute_tool(step.tool_name, step.action, step.params)
                step.result = result
                step.success = result.get("success", True)
                if step.success:
                    return result
                step.error = result.get("error", "Unknown error")
            except Exception as e:
                step.error = str(e)

            if attempt < self.max_retries - 1:
                await asyncio.sleep(0.5 * (attempt + 1))  # Exponential backoff

        return {"success": False, "error": step.error or "Max retries exceeded"}

    async def execute_task(self, task: Task, callback: Callable = None) -> Task:
        """Execute all steps in a task sequentially"""
        task.status = TaskStatus.RUNNING
        results = []

        for i, step in enumerate(task.steps):
            if callback:
                await callback(task, i, step)

            result = await self.execute_step(step)

            if not result.get("success", False):
                # Self-correction: try alternative approach
                if step.retry_count >= self.max_retries:
                    task.status = TaskStatus.FAILED
                    task.error = f"Step {i+1} failed: {step.error}"
                    task.completed_at = datetime.now().isoformat()
                    self._save_tasks()
                    return task

            results.append(result)

        task.status = TaskStatus.COMPLETED
        task.result = results
        task.completed_at = datetime.now().isoformat()
        self._save_tasks()
        return task

    def create_task(self, goal: str, steps: List[Dict], session_id: str = "default") -> Task:
        """Create a new task from a plan"""
        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        tool_calls = [
            ToolCall(
                tool_name=s.get("tool", "shell"),
                action=s.get("action", "run"),
                params=s.get("params", {})
            )
            for s in steps
        ]

        task = Task(id=task_id, goal=goal, steps=tool_calls, session_id=session_id)
        self.tasks[task_id] = task
        self._save_tasks()
        return task

    async def run_task(self, task_id: str, callback: Callable = None) -> Task:
        """Run an existing task"""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        return await self.execute_task(task, callback)

    async def run_goal(self, goal: str, session_id: str = "default", callback: Callable = None) -> Task:
        """
        Parse a goal and execute autonomously
        This is the main entry point for autonomous behavior
        """
        # For now, create simple tasks based on goal keywords
        # In production, this would use an LLM to generate the plan

        steps = self._generate_plan(goal)
        task = self.create_task(goal, steps, session_id)
        return await self.execute_task(task, callback)

    def _generate_plan(self, goal: str) -> List[Dict]:
        """Generate execution plan from goal (simple keyword-based for now)"""
        goal_lower = goal.lower()
        steps = []

        open_match = re.search(r"\b(?:open|launch|start)\s+(.+?)(?:\s+and\s+|$)", goal, re.IGNORECASE)
        if open_match:
            app_name = open_match.group(1).strip().strip(".")
            steps.append({"tool": "app_open", "action": "", "params": {"app": app_name}})

        switch_match = re.search(r"\bswitch to\s+(.+?)(?:\s+and\s+|$)", goal, re.IGNORECASE)
        if switch_match:
            steps.append({"tool": "app_control", "action": "switch_window", "params": {"title_contains": switch_match.group(1).strip()}})

        type_match = re.search(r"\btype\s+(.+?)(?:\s+and\s+(?:press|hit)\s+|$)", goal, re.IGNORECASE)
        if type_match:
            steps.append({"tool": "app_control", "action": "type_text", "params": {"text": type_match.group(1).strip().strip("'\"")}})

        press_match = re.search(r"\b(?:press|hit)\s+([a-z0-9+_, -]+)$", goal, re.IGNORECASE)
        if press_match:
            combo = press_match.group(1).strip()
            keys = [part.strip() for part in re.split(r"[+,]", combo) if part.strip()]
            if len(keys) > 1:
                steps.append({"tool": "app_control", "action": "hotkey", "params": {"keys": keys}})
            elif keys:
                steps.append({"tool": "app_control", "action": "press_key", "params": {"key": keys[0]}})

        if "list windows" in goal_lower or "show windows" in goal_lower:
            steps.append({"tool": "app_control", "action": "list_windows", "params": {}})

        if "active window" in goal_lower or "current window" in goal_lower:
            steps.append({"tool": "app_control", "action": "get_active_window", "params": {}})

        if "mouse position" in goal_lower:
            steps.append({"tool": "app_control", "action": "get_mouse_position", "params": {}})

        if "screenshot" in goal_lower:
            steps.append({"tool": "app_control", "action": "screenshot", "params": {}})

        move_match = re.search(r"\bmove mouse to\s+(-?\d+)\s+(-?\d+)", goal_lower)
        if move_match:
            steps.append({
                "tool": "app_control",
                "action": "move_mouse",
                "params": {"x": int(move_match.group(1)), "y": int(move_match.group(2))}
            })

        if "double click" in goal_lower:
            steps.append({"tool": "app_control", "action": "double_click", "params": {}})
        elif "right click" in goal_lower:
            steps.append({"tool": "app_control", "action": "right_click", "params": {}})
        elif re.search(r"\bclick\b", goal_lower):
            steps.append({"tool": "app_control", "action": "click", "params": {}})

        browse_match = re.search(r"\b(?:search for|google|look up)\s+(.+)", goal, re.IGNORECASE)
        if browse_match:
            steps.append({"tool": "browser", "action": "search", "params": {"query": browse_match.group(1).strip()}})

        navigate_match = re.search(r"\b(?:go to|navigate to|visit)\s+(https?://\S+|\S+\.\S+)", goal, re.IGNORECASE)
        if navigate_match:
            url = navigate_match.group(1).strip()
            if not re.match(r"^https?://", url, re.IGNORECASE):
                url = f"https://{url}"
            steps.append({"tool": "browser", "action": "navigate", "params": {"url": url}})

        if ("file" in goal_lower or "write" in goal_lower or "create" in goal_lower) and "output.txt" in goal_lower:
            steps.append({"tool": "filesystem", "action": "write", "params": {"path": "output.txt", "content": f"Generated: {goal}"}})

        list_match = re.search(r"\b(?:list|show)\s+(?:files|folder|directory)(?:\s+in\s+(.+))?", goal, re.IGNORECASE)
        if list_match:
            target = (list_match.group(1) or ".").strip().strip("'\"")
            steps.append({"tool": "filesystem", "action": "list", "params": {"path": target}})

        read_match = re.search(r"\bread\s+file\s+(.+)", goal, re.IGNORECASE)
        if read_match:
            steps.append({"tool": "filesystem", "action": "read", "params": {"path": read_match.group(1).strip().strip("'\"")}})

        run_match = re.search(r"\b(?:run|execute)\s+command\s+(.+)", goal, re.IGNORECASE)
        if run_match:
            steps.append({"tool": "shell", "action": "", "params": {"command": run_match.group(1).strip()}})

        if "code" in goal_lower or "calculate" in goal_lower:
            code_match = re.search(r"```(?:python)?\s*(.*?)```", goal, re.IGNORECASE | re.DOTALL)
            code = code_match.group(1).strip() if code_match else "print('Task executed')"
            steps.append({"tool": "code_exec", "action": "", "params": {"code": code}})

        if not steps:
            # Default: just acknowledge
            safe_goal = shlex.quote(goal)
            steps.append({"tool": "shell", "action": "", "params": {"command": f"echo Goal received: {safe_goal}"}})

        return steps

    def get_task(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)

    def list_tasks(self, status: TaskStatus = None, session_id: str = None) -> List[Task]:
        tasks = list(self.tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        if session_id:
            tasks = [t for t in tasks if t.session_id == session_id]
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)

    def cancel_task(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        if task and task.status == TaskStatus.RUNNING:
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now().isoformat()
            self._save_tasks()
            return True
        return False

    def get_task_history(self, limit: int = 20) -> List[Dict]:
        tasks = self.list_tasks()[:limit]
        return [
            {
                "id": t.id,
                "goal": t.goal,
                "status": t.status.value,
                "created_at": t.created_at,
                "completed_at": t.completed_at
            }
            for t in tasks
        ]


# Singleton
_engine = None

def get_tool_chaining_engine() -> ToolChainingEngine:
    global _engine
    if _engine is None:
        _engine = ToolChainingEngine()
    return _engine
