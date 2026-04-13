"""
R1 v1 - Job Manager
In-process scheduler with interval and cron-expression support.
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Awaitable, Callable, Dict, List, Optional, Any

from ..config.settings import settings
from ..core.services import get_service_registry, ServiceRegistry

logger = logging.getLogger("R1")

JobHandler = Callable[[ServiceRegistry], Awaitable[None]]


# ---- Cron expression parser ----

class CronExpr:
    """Minimal 5-field cron parser: minute hour day_of_month month day_of_week."""

    _FIELDS = ("minute", "hour", "day", "month", "weekday")
    _RANGES = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 6))

    def __init__(self, expr: str):
        self.expr = expr.strip()
        parts = self.expr.split()
        if len(parts) != 5:
            raise ValueError(f"Cron expression must have 5 fields, got {len(parts)}: {expr}")
        self._sets = [self._parse_field(parts[i], *self._RANGES[i]) for i in range(5)]

    @staticmethod
    def _parse_field(field_str: str, low: int, high: int) -> set:
        """Parse a single cron field into a set of allowed values."""
        result = set()
        for part in field_str.split(","):
            part = part.strip()
            # step
            step = 1
            if "/" in part:
                part, step_str = part.split("/", 1)
                step = int(step_str)

            if part == "*":
                result.update(range(low, high + 1, step))
            elif "-" in part:
                lo, hi = part.split("-", 1)
                result.update(range(int(lo), int(hi) + 1, step))
            else:
                result.add(int(part))
        return result

    def matches(self, dt: datetime) -> bool:
        """Check if a datetime matches this cron expression."""
        vals = (dt.minute, dt.hour, dt.day, dt.month, dt.weekday())
        # weekday: Python uses 0=Monday, cron uses 0=Sunday
        cron_weekday = (dt.weekday() + 1) % 7
        vals_cron = (dt.minute, dt.hour, dt.day, dt.month, cron_weekday)
        return all(v in self._sets[i] for i, v in enumerate(vals_cron))

    def __repr__(self) -> str:
        return f"CronExpr({self.expr!r})"


@dataclass
class JobDefinition:
    id: str
    name: str
    interval_seconds: int = 0
    cron_expr: Optional[str] = None
    handler: JobHandler = None  # type: ignore[assignment]
    enabled: bool = True
    last_run: Optional[datetime] = None
    last_error: Optional[str] = None
    run_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "interval_seconds": self.interval_seconds,
            "cron_expr": self.cron_expr,
            "enabled": self.enabled,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "last_error": self.last_error,
            "run_count": self.run_count,
        }


class JobManager:
    def __init__(self):
        self._jobs: Dict[str, JobDefinition] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._running: bool = False

    def register_job(self, job: JobDefinition) -> None:
        self._jobs[job.id] = job
        logger.info(f"Registered job: {job.id} ({job.name}) every {job.interval_seconds}s"
                     + (f" cron={job.cron_expr}" if job.cron_expr else ""))

    def unregister_job(self, job_id: str) -> bool:
        if job_id in self._jobs:
            if job_id in self._tasks:
                self._tasks[job_id].cancel()
                del self._tasks[job_id]
            del self._jobs[job_id]
            return True
        return False

    def list_jobs(self) -> List[JobDefinition]:
        return list(self._jobs.values())

    def get_job(self, job_id: str) -> Optional[JobDefinition]:
        return self._jobs.get(job_id)

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        job = self._jobs.get(job_id)
        if not job:
            return None
        return {
            **job.to_dict(),
            "running": job_id in self._tasks and not self._tasks[job_id].done(),
        }

    def enable_job(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if not job:
            return False
        job.enabled = True
        # Start loop if manager is running
        if self._running and job_id not in self._tasks:
            self._tasks[job_id] = asyncio.create_task(self._run_job_loop(job))
        logger.info(f"Job enabled: {job_id}")
        return True

    def disable_job(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if not job:
            return False
        job.enabled = False
        if job_id in self._tasks:
            self._tasks[job_id].cancel()
            del self._tasks[job_id]
        logger.info(f"Job disabled: {job_id}")
        return True

    async def start(self) -> None:
        if self._running:
            return
        if not settings.jobs_enabled:
            logger.info("Jobs are disabled via settings.")
            return

        self._running = True
        for job in self._jobs.values():
            if job.enabled:
                self._tasks[job.id] = asyncio.create_task(self._run_job_loop(job))
        logger.info(f"Job manager started with {len(self._tasks)} active jobs")

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()
        logger.info("Job manager stopped")

    async def run_job_now(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if not job:
            return False
        await self._run_job_once(job)
        return True

    async def _run_job_loop(self, job: JobDefinition) -> None:
        # Cron-based: check every 60s if the expression matches
        if job.cron_expr:
            cron = CronExpr(job.cron_expr)
            while self._running and job.enabled:
                now = datetime.utcnow()
                if cron.matches(now):
                    await self._run_job_once(job)
                    # Wait past the current minute to avoid re-triggering
                    await asyncio.sleep(61)
                else:
                    await asyncio.sleep(30)
        else:
            # Interval-based
            while self._running and job.enabled:
                await self._run_job_once(job)
                await asyncio.sleep(max(1, job.interval_seconds))

    async def _run_job_once(self, job: JobDefinition) -> None:
        try:
            services = get_service_registry()
            await job.handler(services)
            job.last_run = datetime.utcnow()
            job.last_error = None
            job.run_count += 1
        except Exception as e:
            job.last_error = str(e)
            logger.error(f"Job failed: {job.id} - {e}")

    def summary(self) -> Dict[str, Any]:
        """Return a summary dict for observability."""
        active = sum(1 for j in self._jobs.values() if j.enabled)
        errors = [j.id for j in self._jobs.values() if j.last_error]
        return {
            "running": self._running,
            "total_jobs": len(self._jobs),
            "active_jobs": active,
            "jobs_with_errors": errors,
        }


_job_manager: Optional[JobManager] = None


def get_job_manager() -> JobManager:
    global _job_manager
    if _job_manager is None:
        _job_manager = JobManager()
    return _job_manager
