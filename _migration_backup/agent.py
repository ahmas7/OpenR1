"""
R1 - Autonomous Agent System
Multi-step task planning, self-correction, background tasks
"""
import asyncio
import json
import re
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING = "waiting"


@dataclass
class Task:
    id: str
    description: str
    steps: List[Dict[str, Any]] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    retries: int = 0
    max_retries: int = 3


class AgentTool:
    """Base class for agent tools"""
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError


class Agent:
    def __init__(self, llm=None):
        self.llm = llm
        self.tasks: Dict[str, Task] = {}
        self.tools: Dict[str, AgentTool] = {}
        self.task_history: List[Dict] = []
    
    def register_tool(self, tool: AgentTool):
        self.tools[tool.name] = tool
    
    async def plan_task(self, user_request: str) -> Task:
        """Break down user request into steps"""
        if not self.llm:
            return self._simple_plan(user_request)
        
        prompt = f"""Break down this request into clear, executable steps.
Each step should be atomic and actionable.

Request: {user_request}

Respond in JSON format:
{{
    "task_id": "unique_id",
    "description": "overall task description",
    "steps": [
        {{"step": 1, "action": "action_type", "detail": "what to do", "tool": "optional_tool_name"}},
        ...
    ]
}}

Available tools: {', '.join(self.tools.keys())}

Respond ONLY with JSON, no other text."""

        try:
            response = await self.llm.chat([
                {"role": "user", "content": prompt}
            ])
            content = response.content
            
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                task = Task(
                    id=data.get("task_id", f"task_{datetime.now().timestamp()}"),
                    description=data.get("description", user_request),
                    steps=data.get("steps", [])
                )
                self.tasks[task.id] = task
                return task
        except Exception as e:
            print(f"Planning error: {e}")
        
        return self._simple_plan(user_request)
    
    def _simple_plan(self, user_request: str) -> Task:
        """Simple fallback planning"""
        task_id = f"task_{datetime.now().timestamp()}"
        
        if any(word in user_request.lower() for word in ["search", "find", "look up"]):
            steps = [{"step": 1, "action": "search", "detail": user_request, "tool": "browser"}]
        elif any(word in user_request.lower() for word in ["open", "go to", "visit"]):
            steps = [{"step": 1, "action": "navigate", "detail": user_request, "tool": "browser"}]
        elif any(word in user_request.lower() for word in ["run", "execute", "command"]):
            steps = [{"step": 1, "action": "shell", "detail": user_request, "tool": "shell"}]
        else:
            steps = [{"step": 1, "action": "chat", "detail": user_request, "tool": "llm"}]
        
        task = Task(id=task_id, description=user_request, steps=steps)
        self.tasks[task.id] = task
        return task
    
    async def execute_task(self, task_id: str, context: Dict = None) -> Task:
        """Execute a planned task with self-correction"""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        task.status = TaskStatus.RUNNING
        context = context or {}
        results = []
        
        for i, step in enumerate(task.steps):
            step_num = step.get("step", i + 1)
            action = step.get("action", "")
            detail = step.get("detail", "")
            tool_name = step.get("tool", "")
            
            try:
                result = await self._execute_step(action, detail, tool_name, context)
                results.append({"step": step_num, "success": True, "result": result})
                context[f"step_{step_num}_result"] = result
                
            except Exception as e:
                error_msg = str(e)
                results.append({"step": step_num, "success": False, "error": error_msg})
                
                if task.retries < task.max_retries:
                    task.retries += 1
                    task.status = TaskStatus.WAITING
                    await asyncio.sleep(1)
                    continue
                else:
                    task.status = TaskStatus.FAILED
                    task.error = error_msg
                    break
        
        if task.status == TaskStatus.RUNNING:
            task.status = TaskStatus.COMPLETED
            task.result = results
            task.completed_at = datetime.now()
        
        self.task_history.append({
            "task_id": task_id,
            "description": task.description,
            "status": task.status.value,
            "results": results
        })
        
        return task
    
    async def _execute_step(self, action: str, detail: str, tool_name: str, context: Dict) -> Any:
        """Execute a single step"""
        tool = self.tools.get(tool_name) if tool_name else None
        
        if tool:
            return await tool.execute(detail=detail, context=context, action=action)
        
        if action == "search" or "search" in action:
            from R1.browser import BrowserController
            browser = await BrowserController.get()
            return await browser.search_google(detail)
        
        elif action == "navigate":
            from R1.browser import BrowserController
            browser = await BrowserController.get()
            url = detail
            for word in ["open", "go to", "visit"]:
                url = url.replace(word, "")
            url = url.strip()
            if not url.startswith("http"):
                url = "https://" + url
            return await browser.navigate(url)
        
        elif action == "shell" or "run" in action:
            from R1.system import Shell
            cmd = detail
            for word in ["run", "execute", "command"]:
                cmd = cmd.replace(word, "")
            cmd = cmd.strip()
            result = await Shell.execute(cmd)
            return result.output if result.success else result.error
        
        elif action == "chat" or action == "llm":
            if self.llm:
                response = await self.llm.chat([{"role": "user", "content": detail}])
                return response.content
            return "LLM not available"
        
        else:
            if self.llm:
                response = await self.llm.chat([{"role": "user", "content": detail}])
                return response.content
            return f"Unknown action: {action}"
    
    async def execute_with_retry(self, task_id: str, max_retries: int = 3) -> Task:
        """Execute task with automatic retry on failure"""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        for attempt in range(max_retries):
            task = await self.execute_task(task_id)
            if task.status == TaskStatus.COMPLETED:
                return task
            if task.retries >= max_retries:
                break
            await asyncio.sleep(2 ** attempt)
        
        return task
    
    def get_task_status(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)
    
    def list_tasks(self) -> List[Dict]:
        return [
            {
                "id": t.id,
                "description": t.description,
                "status": t.status.value,
                "created_at": t.created_at.isoformat()
            }
            for t in self.tasks.values()
        ]
    
    def get_history(self) -> List[Dict]:
        return self.task_history


agent = Agent()
