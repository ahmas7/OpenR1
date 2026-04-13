"""
R1 - Cron Jobs and Scheduled Tasks
Automated task scheduling
"""
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta
from enum import Enum
import json

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from pytz import timezone

logger = logging.getLogger("R1:cron")


class CronState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class CronJob:
    id: str
    name: str
    description: str = ""
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    enabled: bool = True
    max_runs: Optional[int] = None
    preserve_last_n: int = 10
    
    task_type: str = "command"
    command: Optional[str] = None
    webhook_url: Optional[str] = None
    skill: Optional[str] = None
    skill_args: Dict[str, Any] = field(default_factory=dict)
    
    timezone: str = "UTC"
    
    def get_trigger(self):
        if self.cron_expression:
            parts = self.cron_expression.split()
            return CronTrigger(
                minute=parts[0] if len(parts) > 0 else "*",
                hour=parts[1] if len(parts) > 1 else "*",
                day=parts[2] if len(parts) > 2 else "*",
                month=parts[3] if len(parts) > 3 else "*",
                day_of_week=parts[4] if len(parts) > 4 else "*",
                timezone=timezone(self.timezone),
            )
        elif self.interval_seconds:
            return IntervalTrigger(seconds=self.interval_seconds, timezone=timezone(self.timezone))
        else:
            return None


@dataclass
class CronRun:
    job_id: str
    run_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: CronState = CronState.PENDING
    output: Optional[str] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None


class CronManager:
    def __init__(self, config_dir: Optional[str] = None):
        self.scheduler = AsyncIOScheduler()
        self.jobs: Dict[str, CronJob] = {}
        self.runs: Dict[str, List[CronRun]] = {}
        self.config_dir = config_dir
        self.task_handler: Optional[Callable] = None
        self._running = False
        
        if config_dir:
            from pathlib import Path
            self.jobs_file = Path(config_dir) / "cron_jobs.json"
            self._load_jobs()
    
    def _load_jobs(self):
        if hasattr(self, 'jobs_file') and self.jobs_file.exists():
            try:
                data = json.loads(self.jobs_file.read_text())
                for job_data in data.get("jobs", []):
                    job = CronJob(
                        id=job_data["id"],
                        name=job_data["name"],
                        description=job_data.get("description", ""),
                        cron_expression=job_data.get("cron_expression"),
                        interval_seconds=job_data.get("interval_seconds"),
                        enabled=job_data.get("enabled", True),
                        max_runs=job_data.get("max_runs"),
                        command=job_data.get("command"),
                        webhook_url=job_data.get("webhook_url"),
                        skill=job_data.get("skill"),
                        skill_args=job_data.get("skill_args", {}),
                        timezone=job_data.get("timezone", "UTC"),
                    )
                    self.jobs[job.id] = job
                    self.runs[job.id] = []
            except Exception as e:
                logger.error(f"Failed to load cron jobs: {e}")
    
    def _save_jobs(self):
        if hasattr(self, 'jobs_file'):
            data = {
                "jobs": [
                    {
                        "id": job.id,
                        "name": job.name,
                        "description": job.description,
                        "cron_expression": job.cron_expression,
                        "interval_seconds": job.interval_seconds,
                        "enabled": job.enabled,
                        "max_runs": job.max_runs,
                        "command": job.command,
                        "webhook_url": job.webhook_url,
                        "skill": job.skill,
                        "skill_args": job.skill_args,
                        "timezone": job.timezone,
                    }
                    for job in self.jobs.values()
                ]
            }
            self.jobs_file.write_text(json.dumps(data, indent=2))
    
    def set_task_handler(self, handler: Callable):
        self.task_handler = handler
    
    async def start(self):
        if not self._running:
            self.scheduler.start()
            self._running = True
            
            for job in self.jobs.values():
                if job.enabled:
                    self._schedule_job(job)
            
            logger.info(f"Cron manager started with {len(self.jobs)} jobs")
    
    async def stop(self):
        if self._running:
            self.scheduler.shutdown(wait=True)
            self._running = False
            logger.info("Cron manager stopped")
    
    def _schedule_job(self, job: CronJob):
        trigger = job.get_trigger()
        if not trigger:
            logger.error(f"No valid trigger for job {job.id}")
            return
        
        self.scheduler.add_job(
            self._run_job,
            trigger=trigger,
            args=[job.id],
            id=job.id,
            name=job.name,
            replace_existing=True,
        )
    
    async def add_job(self, job: CronJob) -> bool:
        try:
            self.jobs[job.id] = job
            self.runs[job.id] = []
            
            if job.enabled:
                self._schedule_job(job)
            
            self._save_jobs()
            logger.info(f"Added cron job: {job.id}")
            return True
        except Exception as e:
            logger.error(f"Failed to add job {job.id}: {e}")
            return False
    
    async def remove_job(self, job_id: str) -> bool:
        try:
            self.scheduler.remove_job(job_id)
            del self.jobs[job_id]
            del self.runs[job_id]
            self._save_jobs()
            logger.info(f"Removed cron job: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove job {job_id}: {e}")
            return False
    
    async def enable_job(self, job_id: str) -> bool:
        if job_id in self.jobs:
            job = self.jobs[job_id]
            if not job.enabled:
                job.enabled = True
                self._schedule_job(job)
                self._save_jobs()
            return True
        return False
    
    async def disable_job(self, job_id: str) -> bool:
        if job_id in self.jobs:
            job = self.jobs[job_id]
            if job.enabled:
                job.enabled = False
                try:
                    self.scheduler.remove_job(job_id)
                except Exception:
                    pass
                self._save_jobs()
            return True
        return False
    
    async def run_job(self, job_id: str) -> Optional[CronRun]:
        if job_id not in self.jobs:
            return None
        
        job = self.jobs[job_id]
        return await self._run_job(job_id)
    
    async def _run_job(self, job_id: str) -> Optional[CronRun]:
        if job_id not in self.jobs:
            return None
        
        job = self.jobs[job_id]
        run_id = f"{job_id}-{datetime.now().isoformat()}"
        
        run = CronRun(
            job_id=job_id,
            run_id=run_id,
            start_time=datetime.now(),
            status=CronState.RUNNING,
        )
        
        self.runs[job_id].append(run)
        
        try:
            output = None
            
            if self.task_handler:
                result = await self.task_handler(job)
                output = result.output if hasattr(result, 'output') else str(result)
            
            run.end_time = datetime.now()
            run.status = CronState.SUCCESS
            run.output = output
            run.duration_ms = int((run.end_time - run.start_time).total_seconds() * 1000)
            
            logger.info(f"Cron job {job_id} completed in {run.duration_ms}ms")
            
        except Exception as e:
            run.end_time = datetime.now()
            run.status = CronState.FAILED
            run.error = str(e)
            run.duration_ms = int((run.end_time - run.start_time).total_seconds() * 1000)
            
            logger.error(f"Cron job {job_id} failed: {e}")
        
        if job.max_runs:
            runs = self.runs[job_id]
            if len(runs) > job.preserve_last_n:
                self.runs[job_id] = runs[-job.preserve_last_n:]
        
        return run
    
    def get_job(self, job_id: str) -> Optional[CronJob]:
        return self.jobs.get(job_id)
    
    def list_jobs(self) -> List[Dict[str, Any]]:
        result = []
        for job in self.jobs.values():
            result.append({
                "id": job.id,
                "name": job.name,
                "description": job.description,
                "cron_expression": job.cron_expression,
                "interval_seconds": job.interval_seconds,
                "enabled": job.enabled,
                "max_runs": job.max_runs,
                "next_run": self._get_next_run_time(job.id),
            })
        return result
    
    def get_job_runs(self, job_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        if job_id not in self.runs:
            return []
        
        runs = self.runs[job_id][-limit:]
        return [
            {
                "run_id": run.run_id,
                "start_time": run.start_time.isoformat(),
                "end_time": run.end_time.isoformat() if run.end_time else None,
                "status": run.status.value,
                "output": run.output,
                "error": run.error,
                "duration_ms": run.duration_ms,
            }
            for run in runs
        ]
    
    def _get_next_run_time(self, job_id: str) -> Optional[str]:
        job = self.scheduler.get_job(job_id)
        if job and job.next_run_time:
            return job.next_run_time.isoformat()
        return None
    
    def is_running(self) -> bool:
        return self._running


class CronRunner:
    def __init__(self, cron_manager: CronManager):
        self.cron_manager = cron_manager
    
    async def run_scheduled_task(self, job: CronJob) -> CronRun:
        run_id = f"{job.id}-{datetime.now().isoformat()}"
        
        run = CronRun(
            job_id=job.id,
            run_id=run_id,
            start_time=datetime.now(),
            status=CronState.RUNNING,
        )
        
        try:
            if job.task_type == "command" and job.command:
                import subprocess
                result = subprocess.run(
                    job.command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                run.output = result.stdout if result.returncode == 0 else result.stderr
                run.status = CronState.SUCCESS if result.returncode == 0 else CronState.FAILED
            
            elif job.task_type == "webhook" and job.webhook_url:
                import httpx
                async with httpx.AsyncClient() as client:
                    response = await client.post(job.webhook_url)
                    run.output = response.text
                    run.status = CronState.SUCCESS if response.status_code < 400 else CronState.FAILED
            
            elif job.task_type == "skill" and job.skill:
                if self.cron_manager.task_handler:
                    result = await self.cron_manager.task_handler(job)
                    run.output = result.output if hasattr(result, 'output') else str(result)
                    run.status = CronState.SUCCESS
            
        except Exception as e:
            run.status = CronState.FAILED
            run.error = str(e)
        
        run.end_time = datetime.now()
        run.duration_ms = int((run.end_time - run.start_time).total_seconds() * 1000)
        
        return run
