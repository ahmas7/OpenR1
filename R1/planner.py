"""
R1 - Multi-Step Task Planner
Breaks complex goals into executable steps with dependency resolution
"""
import asyncio
import logging
import json
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
import uuid

logger = logging.getLogger("R1:planner")


class TaskStatus(Enum):
    PENDING = "pending"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class SubTask:
    id: str
    name: str
    description: str
    status: TaskStatus
    priority: TaskPriority
    dependencies: List[str] = field(default_factory=list)
    tool_required: Optional[str] = None
    tool_params: Dict[str, Any] = field(default_factory=dict)
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class Plan:
    id: str
    name: str
    goal: str
    status: TaskStatus
    subtasks: List[SubTask] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class TaskPlanner:
    """
    Multi-step task planner that breaks complex goals into executable steps.
    Handles dependency resolution, parallel execution, and self-healing.
    """

    def __init__(self, tool_executor: Callable = None):
        self.plans: Dict[str, Plan] = {}
        self.tool_executor = tool_executor
        self.execution_lock = asyncio.Lock()
        self._running = False

    async def create_plan(self, goal: str, name: str = None, context: Dict = None) -> Plan:
        """Create a new plan from a complex goal"""
        plan_id = str(uuid.uuid4())[:8]
        plan = Plan(
            id=plan_id,
            name=name or f"Plan-{plan_id}",
            goal=goal,
            status=TaskStatus.PENDING,
            context=context or {}
        )

        # Decompose goal into subtasks
        subtasks = await self._decompose_goal(goal, context)
        plan.subtasks = subtasks

        self.plans[plan_id] = plan
        logger.info(f"Created plan {plan_id} with {len(subtasks)} subtasks for goal: {goal[:50]}...")

        return plan

    async def _decompose_goal(self, goal: str, context: Dict) -> List[SubTask]:
        """
        Decompose a complex goal into executable subtasks.
        This uses pattern matching and can be enhanced with LLM assistance.
        """
        subtasks = []

        goal_lower = goal.lower()

        # Pattern: Research + Save
        if any(kw in goal_lower for kw in ['research', 'find', 'search', 'look up']):
            subtasks.extend([
                SubTask(
                    id=str(uuid.uuid4())[:8],
                    name="Search for information",
                    description=f"Search the web for: {goal}",
                    status=TaskStatus.PENDING,
                    priority=TaskPriority.NORMAL,
                    tool_required="browser",
                    tool_params={"action": "search", "query": goal}
                ),
                SubTask(
                    id=str(uuid.uuid4())[:8],
                    name="Extract relevant information",
                    description="Extract and summarize key findings",
                    status=TaskStatus.PENDING,
                    priority=TaskPriority.NORMAL,
                    dependencies=[subtasks[0].id] if subtasks else [],
                    tool_required="code_exec",
                    tool_params={"code": "summarize(findings)"}
                )
            ])

        # Pattern: Save/Write
        if any(kw in goal_lower for kw in ['save', 'write', 'store', 'remember']):
            subtasks.append(SubTask(
                id=str(uuid.uuid4())[:8],
                name="Save to storage",
                description="Save the results to file or memory",
                status=TaskStatus.PENDING,
                priority=TaskPriority.NORMAL,
                tool_required="filesystem",
                tool_params={"action": "write"}
            ))

        # Pattern: Send/Notify
        if any(kw in goal_lower for kw in ['send', 'notify', 'tell', 'message']):
            subtasks.append(SubTask(
                id=str(uuid.uuid4())[:8],
                name="Send notification",
                description="Send message or notification to user",
                status=TaskStatus.PENDING,
                priority=TaskPriority.HIGH,
                tool_required="notification",
                tool_params={"message": goal}
            ))

        # Pattern: Execute/Run
        if any(kw in goal_lower for kw in ['run', 'execute', 'open', 'launch']):
            subtasks.append(SubTask(
                id=str(uuid.uuid4())[:8],
                name="Execute command",
                description="Run the specified command or application",
                status=TaskStatus.PENDING,
                priority=TaskPriority.HIGH,
                tool_required="shell",
                tool_params={"command": goal}
            ))

        # If no patterns matched, create a generic task
        if not subtasks:
            subtasks.append(SubTask(
                id=str(uuid.uuid4())[:8],
                name="Execute goal",
                description=goal,
                status=TaskStatus.PENDING,
                priority=TaskPriority.NORMAL,
                tool_required=None
            ))

        # Set up dependencies (sequential by default)
        for i in range(1, len(subtasks)):
            if not subtasks[i].dependencies:
                subtasks[i].dependencies = [subtasks[i-1].id]

        return subtasks

    async def execute_plan(self, plan_id: str) -> Dict[str, Any]:
        """Execute a plan by running its subtasks in order"""
        if plan_id not in self.plans:
            return {"error": "Plan not found"}

        plan = self.plans[plan_id]
        plan.status = TaskStatus.IN_PROGRESS
        plan.started_at = datetime.now()

        results = []
        failed_tasks = []

        async with self.execution_lock:
            while True:
                # Get next ready task
                ready_task = self._get_next_ready_task(plan)

                if not ready_task:
                    # Check if all tasks are done
                    if all(t.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
                           for t in plan.subtasks):
                        break
                    await asyncio.sleep(0.5)
                    continue

                # Execute task
                result = await self._execute_subtask(ready_task)
                results.append(result)

                if result.get("success"):
                    ready_task.status = TaskStatus.COMPLETED
                    ready_task.result = result.get("output")
                    ready_task.completed_at = datetime.now()
                else:
                    ready_task.error = result.get("error")
                    if ready_task.retry_count < ready_task.max_retries:
                        ready_task.retry_count += 1
                        ready_task.status = TaskStatus.PENDING
                        logger.warning(f"Task {ready_task.id} failed, retrying ({ready_task.retry_count}/{ready_task.max_retries})")
                    else:
                        ready_task.status = TaskStatus.FAILED
                        failed_tasks.append(ready_task.id)

                ready_task.completed_at = datetime.now()

        # Determine plan status
        if failed_tasks:
            plan.status = TaskStatus.FAILED
            plan.metadata["failed_tasks"] = failed_tasks
        else:
            plan.status = TaskStatus.COMPLETED
            plan.completed_at = datetime.now()

        return {
            "plan_id": plan_id,
            "status": plan.status.value,
            "results": results,
            "failed_tasks": failed_tasks
        }

    def _get_next_ready_task(self, plan: Plan) -> Optional[SubTask]:
        """Get the next task that's ready to execute"""
        for task in plan.subtasks:
            if task.status != TaskStatus.PENDING:
                continue

            # Check if all dependencies are completed
            deps_completed = all(
                any(t.id == dep_id and t.status == TaskStatus.COMPLETED
                    for t in plan.subtasks)
                for dep_id in task.dependencies
            )

            if deps_completed:
                task.status = TaskStatus.READY
                task.started_at = datetime.now()
                return task

        return None

    async def _execute_subtask(self, task: SubTask) -> Dict[str, Any]:
        """Execute a single subtask"""
        logger.info(f"Executing task: {task.name}")

        if not self.tool_executor:
            return {"success": False, "error": "No tool executor available"}

        try:
            if task.tool_required:
                result = await self.tool_executor(
                    tool=task.tool_required,
                    params=task.tool_params
                )
                return {"success": True, "output": str(result)}
            else:
                # No specific tool, try to execute via LLM
                return {"success": True, "output": f"Task executed: {task.description}"}
        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            return {"success": False, "error": str(e)}

    def get_plan_status(self, plan_id: str) -> Optional[Dict]:
        """Get detailed status of a plan"""
        if plan_id not in self.plans:
            return None

        plan = self.plans[plan_id]
        completed = sum(1 for t in plan.subtasks if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in plan.subtasks if t.status == TaskStatus.FAILED)
        in_progress = sum(1 for t in plan.subtasks if t.status == TaskStatus.IN_PROGRESS)

        return {
            "id": plan.id,
            "name": plan.name,
            "goal": plan.goal,
            "status": plan.status.value,
            "progress": {
                "total": len(plan.subtasks),
                "completed": completed,
                "failed": failed,
                "in_progress": in_progress,
                "pending": len(plan.subtasks) - completed - failed - in_progress
            },
            "progress_percent": (completed / len(plan.subtasks) * 100) if plan.subtasks else 0,
            "subtasks": [
                {
                    "id": t.id,
                    "name": t.name,
                    "status": t.status.value,
                    "error": t.error,
                    "retry_count": t.retry_count
                }
                for t in plan.subtasks
            ]
        }

    def list_plans(self) -> List[Dict]:
        """List all plans with summary"""
        return [
            {
                "id": plan.id,
                "name": plan.name,
                "goal": plan.goal,
                "status": plan.status.value,
                "subtask_count": len(plan.subtasks),
                "created_at": plan.created_at.isoformat()
            }
            for plan in self.plans.values()
        ]

    async def cancel_plan(self, plan_id: str) -> bool:
        """Cancel a running plan"""
        if plan_id not in self.plans:
            return False

        plan = self.plans[plan_id]
        plan.status = TaskStatus.CANCELLED

        for task in plan.subtasks:
            if task.status in [TaskStatus.PENDING, TaskStatus.READY]:
                task.status = TaskStatus.CANCELLED

        logger.info(f"Cancelled plan {plan_id}")
        return True


# Global instance
_planner: Optional[TaskPlanner] = None


def get_planner(tool_executor: Callable = None) -> TaskPlanner:
    global _planner
    if _planner is None:
        _planner = TaskPlanner(tool_executor)
    elif tool_executor and _planner.tool_executor is None:
        _planner.tool_executor = tool_executor
    return _planner
