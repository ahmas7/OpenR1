"""
R1 v1 - Reminders Job
Persistent reminder queue with delivery through memory and integrations.
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config.settings import settings

logger = logging.getLogger("R1")


@dataclass
class Reminder:
    id: str
    session_id: str
    text: str
    due_at: str  # ISO 8601
    created_at: str
    delivered: bool = False
    delivered_at: Optional[str] = None

    def is_due(self) -> bool:
        try:
            due = datetime.fromisoformat(self.due_at)
            return datetime.utcnow() >= due and not self.delivered
        except (ValueError, TypeError):
            return False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Reminder":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class ReminderQueue:
    """Persistent in-memory reminder queue backed by a JSON file."""

    def __init__(self, path: Optional[str] = None):
        self._path = Path(path or settings.reminders_file)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._reminders: List[Reminder] = []
        self._load()

    # ---- public API ----

    def add(self, session_id: str, text: str, due_at: str) -> Reminder:
        """Create a new reminder and persist it."""
        reminder = Reminder(
            id=uuid.uuid4().hex[:12],
            session_id=session_id,
            text=text,
            due_at=due_at,
            created_at=datetime.utcnow().isoformat(),
        )
        self._reminders.append(reminder)
        self._save()
        logger.info(f"Reminder created: {reminder.id} due at {due_at}")
        return reminder

    def list_pending(self) -> List[Reminder]:
        """Return all un-delivered reminders."""
        return [r for r in self._reminders if not r.delivered]

    def list_all(self) -> List[Reminder]:
        return list(self._reminders)

    def get(self, reminder_id: str) -> Optional[Reminder]:
        for r in self._reminders:
            if r.id == reminder_id:
                return r
        return None

    def cancel(self, reminder_id: str) -> bool:
        """Cancel (delete) a reminder."""
        before = len(self._reminders)
        self._reminders = [r for r in self._reminders if r.id != reminder_id]
        if len(self._reminders) < before:
            self._save()
            return True
        return False

    def deliver_due(self) -> List[Reminder]:
        """Mark all due reminders as delivered and return them."""
        delivered = []
        for r in self._reminders:
            if r.is_due():
                r.delivered = True
                r.delivered_at = datetime.utcnow().isoformat()
                delivered.append(r)
        if delivered:
            self._save()
        return delivered

    def pending_count(self) -> int:
        return len(self.list_pending())

    # ---- persistence ----

    def _load(self) -> None:
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                self._reminders = [Reminder.from_dict(d) for d in data]
                logger.debug(f"Loaded {len(self._reminders)} reminders from {self._path}")
            except Exception as e:
                logger.warning(f"Failed to load reminders: {e}")
                self._reminders = []
        else:
            self._reminders = []

    def _save(self) -> None:
        try:
            self._path.write_text(
                json.dumps([r.to_dict() for r in self._reminders], indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"Failed to save reminders: {e}")


# ---- singleton ----

_reminder_queue: Optional[ReminderQueue] = None


def get_reminder_queue() -> ReminderQueue:
    global _reminder_queue
    if _reminder_queue is None:
        _reminder_queue = ReminderQueue()
    return _reminder_queue


# ---- job handler ----

async def reminders_job(services) -> None:
    """Background job handler: deliver due reminders to memory and log."""
    queue = get_reminder_queue()
    delivered = queue.deliver_due()

    if not delivered:
        return

    # Write delivered reminders into memory so the agent sees them
    memory = services.get("memory_store")
    if not memory:
        try:
            from ..memory import get_memory_store
            memory = get_memory_store()
        except Exception as e:
            logger.warning(f"Could not get memory store for reminders: {e}")

    for r in delivered:
        logger.info(f"Reminder delivered: [{r.id}] {r.text}")
        if memory:
            try:
                memory.add_message(
                    r.session_id,
                    "system",
                    f"[Reminder] {r.text}",
                )
            except Exception as e:
                logger.warning(f"Could not write reminder to memory: {e}")
