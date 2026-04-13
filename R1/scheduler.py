"""
R1 - Enhanced Scheduler with Cron Integration
Supports cron expressions, interval tasks, and one-shot reminders
"""
import asyncio
import logging
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Union
from enum import Enum

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from pytz import timezone

logger = logging.getLogger("R1:scheduler")


class TaskType(Enum):
    COMMAND = "command"
    WEBHOOK = "webhook"
    SKILL = "skill"
    REMINDER = "reminder"
    BRIEFING = "briefing"
    HEARTBEAT = "heartbeat"
    REFLECTION = "reflection"


class TaskState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScheduledTask:
    def __init__(self, id: str, name: str, task_type: TaskType,
                 cron_expr: str = None, interval_seconds: int = None,
                 run_at: datetime = None, enabled: bool = True,
                 handler: Callable = None, params: Dict = None,
                 timezone_str: str = "UTC"):
        self.id = id
        self.name = name
        self.task_type = task_type
        self.cron_expr = cron_expr
        self.interval_seconds = interval_seconds
        self.run_at = run_at
        self.enabled = enabled
        self.handler = handler
        self.params = params or {}
        self.timezone_str = timezone_str
        self.max_runs = None
        self.preserve_last_n = 10

    def get_trigger(self):
        tz = timezone(self.timezone_str)

        if self.cron_expr:
            parts = self.cron_expr.split()
            return CronTrigger(
                minute=parts[0] if len(parts) > 0 else "*",
                hour=parts[1] if len(parts) > 1 else "*",
                day=parts[2] if len(parts) > 2 else "*",
                month=parts[3] if len(parts) > 3 else "*",
                day_of_week=parts[4] if len(parts) > 4 else "*",
                timezone=tz
            )
        elif self.interval_seconds:
            return IntervalTrigger(seconds=self.interval_seconds, timezone=tz)
        elif self.run_at:
            return DateTrigger(run_date=self.run_at, timezone=tz)
        return None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.task_type.value,
            "cron_expr": self.cron_expr,
            "interval_seconds": self.interval_seconds,
            "run_at": self.run_at.isoformat() if self.run_at else None,
            "enabled": self.enabled,
            "params": self.params,
            "timezone": self.timezone_str
        }


class TaskRun:
    def __init__(self, task_id: str, run_id: str):
        self.task_id = task_id
        self.run_id = run_id
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None
        self.status = TaskState.PENDING
        self.output: Optional[str] = None
        self.error: Optional[str] = None
        self.duration_ms: Optional[int] = None

    def to_dict(self) -> Dict:
        return {
            "run_id": self.run_id,
            "task_id": self.task_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "duration_ms": self.duration_ms
        }


class Scheduler:
    """
    Enhanced scheduler with cron support, reminders, and scheduled agents.
    """

    def __init__(self, config_dir: str = None):
        self.scheduler = AsyncIOScheduler()
        self.tasks: Dict[str, ScheduledTask] = {}
        self.runs: Dict[str, List[TaskRun]] = {}
        self._running = False

        # Configuration
        self.config_dir = Path(config_dir) if config_dir else Path.home() / ".r1"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.tasks_file = self.config_dir / "scheduled_tasks.json"

        # Load saved tasks
        self._load_tasks()

        # Built-in handlers
        self.handlers: Dict[TaskType, Callable] = {}

        logger.info(f"Scheduler initialized, config: {self.config_dir}")

    def _load_tasks(self):
        """Load tasks from file"""
        if self.tasks_file.exists():
            try:
                data = json.loads(self.tasks_file.read_text())
                for task_data in data.get("tasks", []):
                    task = ScheduledTask(
                        id=task_data["id"],
                        name=task_data["name"],
                        task_type=TaskType(task_data["type"]),
                        cron_expr=task_data.get("cron_expr"),
                        interval_seconds=task_data.get("interval_seconds"),
                        run_at=datetime.fromisoformat(task_data["run_at"]) if task_data.get("run_at") else None,
                        enabled=task_data.get("enabled", True),
                        params=task_data.get("params", {}),
                        timezone_str=task_data.get("timezone", "UTC")
                    )
                    self.tasks[task.id] = task
                    self.runs[task.id] = []
                logger.info(f"Loaded {len(self.tasks)} scheduled tasks")
            except Exception as e:
                logger.error(f"Failed to load tasks: {e}")

    def _save_tasks(self):
        """Save tasks to file"""
        data = {
            "tasks": [task.to_dict() for task in self.tasks.values()]
        }
        self.tasks_file.write_text(json.dumps(data, indent=2))

    def register_handler(self, task_type: TaskType, handler: Callable):
        """Register a handler for a task type"""
        self.handlers[task_type] = handler
        logger.info(f"Registered handler for {task_type.value}")

    async def start(self):
        """Start the scheduler"""
        if not self._running:
            self.scheduler.start()
            self._running = True

            # Schedule all enabled tasks
            for task in self.tasks.values():
                if task.enabled:
                    self._schedule_task(task)

            logger.info(f"Scheduler started with {len(self.tasks)} tasks")

    async def stop(self):
        """Stop the scheduler"""
        if self._running:
            self.scheduler.shutdown(wait=True)
            self._running = False
            logger.info("Scheduler stopped")

    def _schedule_task(self, task: ScheduledTask):
        """Schedule a task with APScheduler"""
        trigger = task.get_trigger()
        if not trigger:
            logger.error(f"No valid trigger for task {task.id}")
            return

        self.scheduler.add_job(
            self._run_task,
            trigger=trigger,
            args=[task.id],
            id=task.id,
            name=task.name,
            replace_existing=True
        )
        logger.info(f"Scheduled task: {task.id} ({task.name})")

    async def add_task(self, task: ScheduledTask) -> bool:
        """Add a new scheduled task"""
        try:
            self.tasks[task.id] = task
            self.runs[task.id] = []

            if task.enabled and self._running:
                self._schedule_task(task)

            self._save_tasks()
            logger.info(f"Added task: {task.id}")
            return True
        except Exception as e:
            logger.error(f"Failed to add task {task.id}: {e}")
            return False

    async def remove_task(self, task_id: str) -> bool:
        """Remove a scheduled task"""
        try:
            if task_id in self.scheduler.get_job_ids():
                self.scheduler.remove_job(task_id)
            del self.tasks[task_id]
            del self.runs[task_id]
            self._save_tasks()
            logger.info(f"Removed task: {task_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove task {task_id}: {e}")
            return False

    async def enable_task(self, task_id: str) -> bool:
        """Enable a task"""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.enabled = True
            if self._running:
                self._schedule_task(task)
            self._save_tasks()
            return True
        return False

    async def disable_task(self, task_id: str) -> bool:
        """Disable a task"""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.enabled = False
            try:
                self.scheduler.remove_job(task_id)
            except:
                pass
            self._save_tasks()
            return True
        return False

    async def _run_task(self, task_id: str):
        """Execute a scheduled task"""
        if task_id not in self.tasks:
            return

        task = self.tasks[task_id]
        run_id = f"{task_id}-{datetime.now().isoformat()}"
        run = TaskRun(task_id, run_id)
        run.status = TaskState.RUNNING

        self.runs[task_id].append(run)

        try:
            # Find handler
            handler = self.handlers.get(task.task_type)

            if handler:
                result = await handler(task.params)
                run.output = result if isinstance(result, str) else json.dumps(result)
                run.status = TaskState.SUCCESS
            else:
                # Generic execution
                run.output = f"Task {task.name} executed (no handler registered)"
                run.status = TaskState.SUCCESS

            logger.info(f"Task {task_id} completed")

        except Exception as e:
            run.error = str(e)
            run.status = TaskState.FAILED
            logger.error(f"Task {task_id} failed: {e}")

        run.end_time = datetime.now()
        run.duration_ms = int((run.end_time - run.start_time).total_seconds() * 1000)

        # Trim old runs
        if task.preserve_last_n and len(self.runs[task_id]) > task.preserve_last_n:
            self.runs[task_id] = self.runs[task_id][-task.preserve_last_n:]

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """Get a task by ID"""
        return self.tasks.get(task_id)

    def list_tasks(self) -> List[Dict]:
        """List all tasks with status"""
        result = []
        for task in self.tasks.values():
            next_run = None
            try:
                job = self.scheduler.get_job(task.id)
                if job and job.next_run_time:
                    next_run = job.next_run_time.isoformat()
            except:
                pass

            result.append({
                **task.to_dict(),
                "next_run": next_run,
                "running": self._running
            })
        return result

    def get_task_runs(self, task_id: str, limit: int = 10) -> List[Dict]:
        """Get recent runs for a task"""
        if task_id not in self.runs:
            return []
        runs = self.runs[task_id][-limit:]
        return [run.to_dict() for run in runs]

    async def run_task_now(self, task_id: str) -> bool:
        """Manually trigger a task"""
        if task_id not in self.tasks:
            return False

        await self._run_task(task_id)
        return True

    # ========== Convenience Methods ==========

    def add_cron_task(self, id: str, name: str, cron_expr: str,
                      task_type: TaskType, handler_params: Dict = None,
                      timezone_str: str = "UTC") -> ScheduledTask:
        """Add a cron-scheduled task"""
        task = ScheduledTask(
            id=id,
            name=name,
            task_type=task_type,
            cron_expr=cron_expr,
            timezone_str=timezone_str,
            params=handler_params or {}
        )
        asyncio.create_task(self.add_task(task))
        return task

    def add_interval_task(self, id: str, name: str, interval_seconds: int,
                          task_type: TaskType, handler_params: Dict = None) -> ScheduledTask:
        """Add an interval-based task"""
        task = ScheduledTask(
            id=id,
            name=name,
            task_type=task_type,
            interval_seconds=interval_seconds,
            params=handler_params or {}
        )
        asyncio.create_task(self.add_task(task))
        return task

    def add_reminder(self, id: str, message: str, run_at: datetime) -> ScheduledTask:
        """Add a one-time reminder"""
        task = ScheduledTask(
            id=id,
            name=f"Reminder: {message[:30]}",
            task_type=TaskType.REMINDER,
            run_at=run_at,
            params={"message": message}
        )
        asyncio.create_task(self.add_task(task))
        return task

    def is_running(self) -> bool:
        """Check if scheduler is running"""
        return self._running


# Global instance
_scheduler: Optional[Scheduler] = None


def get_scheduler(config_dir: str = None) -> Scheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = Scheduler(config_dir)
    return _scheduler


# ========== Pre-built Task Templates ==========

def create_morning_briefing_task(time: str = "08:00") -> ScheduledTask:
    """Create a morning briefing task"""
    hour, minute = map(int, time.split(":"))
    return ScheduledTask(
        id="morning_briefing",
        name="Morning Briefing",
        task_type=TaskType.BRIEFING,
        cron_expr=f"{minute} {hour} * * *",
        params={"type": "morning"}
    )


def create_evening_review_task(time: str = "21:00") -> ScheduledTask:
    """Create an evening review task"""
    hour, minute = map(int, time.split(":"))
    return ScheduledTask(
        id="evening_review",
        name="Evening Review",
        task_type=TaskType.REFLECTION,
        cron_expr=f"{minute} {hour} * * *",
        params={"type": "evening"}
    )


def create_heartbeat_task(interval_seconds: int = 60) -> ScheduledTask:
    """Create a heartbeat task"""
    return ScheduledTask(
        id="heartbeat",
        name="System Heartbeat",
        task_type=TaskType.HEARTBEAT,
        interval_seconds=interval_seconds,
        params={}
    )


def create_nightly_reflection_task(time: str = "03:00") -> ScheduledTask:
    """Create a nightly reflection task"""
    hour, minute = map(int, time.split(":"))
    return ScheduledTask(
        id="nightly_reflection",
        name="Nightly Reflection",
        task_type=TaskType.REFLECTION,
        cron_expr=f"{minute} {hour} * * *",
        params={"type": "nightly"}
    )
