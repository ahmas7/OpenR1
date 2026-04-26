"""
OpenClaw-Style Proactive Agent System for R1
Heartbeats, reminders, check-ins, and autonomous actions
"""
import asyncio
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
import logging
import json
from pathlib import Path

from R1.legacy.openclaw.openclaw_persona import persona
from R1.memory.store import get_memory_store
from R1.jobs.manager import JobDefinition as JobDefinition

logger = logging.getLogger("R1:proactive")

REMINDERS_FILE = Path("E:/MYAI/R1/data/reminders.json")


@dataclass
class Reminder:
    """A reminder/task"""
    id: str
    title: str
    due_time: Optional[datetime] = None
    recurrence: Optional[str] = None  # daily, weekly, etc.
    category: str = "general"
    completed: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    priority: str = "normal"  # low, normal, high, urgent


@dataclass
class HeartbeatEvent:
    """Event triggered during heartbeat"""
    timestamp: datetime
    event_type: str
    data: Dict[str, Any] = field(default_factory=dict)


class ReminderManager:
    """
    Manages reminders and tasks
    """

    def __init__(self):
        self.reminders: List[Reminder] = []
        self._load_reminders()

    def _load_reminders(self):
        """Load reminders from file"""
        if REMINDERS_FILE.exists():
            try:
                data = json.loads(REMINDERS_FILE.read_text())
                for r in data:
                    self.reminders.append(Reminder(
                        id=r["id"],
                        title=r["title"],
                        due_time=datetime.fromisoformat(r["due_time"]) if r.get("due_time") else None,
                        recurrence=r.get("recurrence"),
                        category=r.get("category", "general"),
                        completed=r.get("completed", False),
                        priority=r.get("priority", "normal"),
                    ))
            except Exception as e:
                logger.error(f"Error loading reminders: {e}")

    def _save_reminders(self):
        """Save reminders to file"""
        data = []
        for r in self.reminders:
            data.append({
                "id": r.id,
                "title": r.title,
                "due_time": r.due_time.isoformat() if r.due_time else None,
                "recurrence": r.recurrence,
                "category": r.category,
                "completed": r.completed,
                "priority": r.priority,
            })
        REMINDERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        REMINDERS_FILE.write_text(json.dumps(data, indent=2))

    def add_reminder(self, title: str, due_time: Optional[datetime] = None,
                     recurrence: Optional[str] = None, priority: str = "normal") -> Reminder:
        """Add a new reminder"""
        reminder = Reminder(
            id=f"rem_{int(time.time())}",
            title=title,
            due_time=due_time,
            recurrence=recurrence,
            priority=priority,
        )
        self.reminders.append(reminder)
        self._save_reminders()
        return reminder

    def get_pending(self) -> List[Reminder]:
        """Get pending reminders"""
        return [r for r in self.reminders if not r.completed]

    def get_due_now(self) -> List[Reminder]:
        """Get reminders due now"""
        now = datetime.now()
        due = []
        for r in self.reminders:
            if not r.completed and r.due_time and r.due_time <= now:
                due.append(r)
        return due

    def complete_reminder(self, reminder_id: str) -> bool:
        """Mark a reminder as complete"""
        for r in self.reminders:
            if r.id == reminder_id:
                r.completed = True
                self._save_reminders()
                return True
        return False

    def delete_reminder(self, reminder_id: str) -> bool:
        """Delete a reminder"""
        for i, r in enumerate(self.reminders):
            if r.id == reminder_id:
                del self.reminders[i]
                self._save_reminders()
                return True
        return False


class ProactiveAgent:
    """
    Proactive AI Agent that initiates actions
    Heartbeats, check-ins, briefings, autonomous tasks
    """

    def __init__(self):
        self.active = False
        self.heartbeat_thread = None
        self.heartbeat_interval = 60  # seconds
        self.reminder_manager = ReminderManager()
        self.last_briefing_date = None
        self.check_in_enabled = True
        self.event_handlers: Dict[str, List[Callable]] = {}
        self.user_activity_log: List[Dict] = []

    def start(self) -> bool:
        """Start the proactive agent"""
        if self.active:
            return True

        self.active = True
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()

        logger.info("Proactive agent started")
        return True

    def stop(self):
        """Stop the proactive agent"""
        self.active = False
        if self.heartbeat_thread:
            self.heartbeat_thread.join(timeout=5)
        logger.info("Proactive agent stopped")

    def _heartbeat_loop(self):
        """Main heartbeat loop"""
        while self.active:
            try:
                self._on_heartbeat()
                time.sleep(self.heartbeat_interval)
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                time.sleep(10)

    def _on_heartbeat(self):
        """Called every heartbeat"""
        now = datetime.now()

        # Check for morning briefing
        if persona.config.morning_briefing and persona.config.proactive_enabled:
            self._check_morning_briefing(now)

        # Check for due reminders
        self._check_reminders(now)

        # Periodic check-ins
        self._check_checkins(now)

        # Log activity
        self._log_activity("heartbeat", {"time": now.isoformat()})

    def _check_morning_briefing(self, now: datetime):
        """Check if it's time for morning briefing"""
        if self.last_briefing_date == now.date():
            return  # Already did briefing today

        try:
            briefing_hour, briefing_minute = map(int, persona.config.briefing_time.split(":"))
            if now.hour == briefing_hour and now.minute >= briefing_minute:
                self._send_morning_briefing()
                self.last_briefing_date = now.date()
        except ValueError:
            logger.error("Invalid briefing time format")

    def _send_morning_briefing(self):
        """Send morning briefing to user"""
        briefing = persona.generate_briefing()

        # Speak it
        if persona.config.voice_enabled:
            asyncio.run_coroutine_threadsafe(
                persona.speak(briefing, blocking=True),
                asyncio.get_event_loop()
            )

        # Log
        self._log_activity("briefing", {"content": briefing[:100]})

        logger.info("Morning briefing sent")

    def _check_reminders(self, now: datetime):
        """Check for due reminders"""
        due_reminders = self.reminder_manager.get_due_now()

        for reminder in due_reminders:
            self._trigger_reminder(reminder)

    def _trigger_reminder(self, reminder: Reminder):
        """Trigger a reminder"""
        message = f"⏰ Reminder: {reminder.title}"

        # Speak it
        if persona.config.voice_enabled:
            asyncio.run_coroutine_threadsafe(
                persona.speak(message, blocking=False),
                asyncio.get_event_loop()
            )

        # Handle recurrence
        if reminder.recurrence:
            if reminder.recurrence == "daily":
                reminder.due_time = reminder.due_time + timedelta(days=1)
            elif reminder.recurrence == "weekly":
                reminder.due_time = reminder.due_time + timedelta(weeks=1)
            elif reminder.recurrence == "hourly":
                reminder.due_time = reminder.due_time + timedelta(hours=1)
        else:
            reminder.completed = True

        self.reminder_manager._save_reminders()
        self._log_activity("reminder", {"title": reminder.title})

    def _check_checkins(self, now: datetime):
        """Periodic check-ins"""
        if not self.check_in_enabled or not persona.config.proactive_enabled:
            return

        # Check if user has been inactive for a while
        if len(self.user_activity_log) >= 2:
            last_activity = self.user_activity_log[-1]
            last_time = datetime.fromisoformat(last_activity["time"])
            hours_inactive = (now - last_time).total_seconds() / 3600

            # Check in after 4 hours of inactivity (but not too frequently)
            if hours_inactive > 4 and hours_inactive < 5:
                check_in_messages = [
                    "Hey! Just checking in. How's it going?",
                    "Hi there! Haven't heard from you in a bit. Everything okay?",
                    f"Hey{', ' + persona.config.user_name if persona.config.user_name else ''}! Need anything?",
                ]
                import random
                message = random.choice(check_in_messages)

                if persona.config.voice_enabled:
                    asyncio.run_coroutine_threadsafe(
                        persona.speak(message, blocking=False),
                        asyncio.get_event_loop()
                    )

    def _log_activity(self, activity_type: str, data: Dict):
        """Log user activity"""
        self.user_activity_log.append({
            "type": activity_type,
            "time": datetime.now().isoformat(),
            "data": data,
        })

        # Keep last 100 entries
        if len(self.user_activity_log) > 100:
            self.user_activity_log = self.user_activity_log[-100:]

    # === Public Methods ===

    def add_reminder(self, title: str, when: Optional[str] = None,
                     recurrence: Optional[str] = None) -> str:
        """Add a reminder"""
        due_time = None
        if when:
            try:
                # Parse relative time
                if when.lower().startswith("in "):
                    parts = when.lower().replace("in ", "").split()
                    if len(parts) >= 2:
                        amount = int(parts[0])
                        unit = parts[1].rstrip("s")  # remove plural
                        if unit == "minute":
                            due_time = datetime.now() + timedelta(minutes=amount)
                        elif unit == "hour":
                            due_time = datetime.now() + timedelta(hours=amount)
                        elif unit == "day":
                            due_time = datetime.now() + timedelta(days=amount)
                else:
                    # Try to parse as absolute time
                    due_time = datetime.fromisoformat(when)
            except Exception:
                pass

        reminder = self.reminder_manager.add_reminder(title, due_time, recurrence)
        return f"Reminder set: '{title}'{' at ' + when if when else ''}"

    def get_todays_reminders(self) -> str:
        """Get today's reminders"""
        reminders = self.reminder_manager.get_pending()
        if not reminders:
            return "No pending reminders."

        lines = ["Your reminders:"]
        for r in reminders[:10]:
            due = f" (Due: {r.due_time.strftime('%Y-%m-%d %H:%M')})" if r.due_time else ""
            lines.append(f"  • {r.title}{due}")

        return "\n".join(lines)

    def on_event(self, event_type: str, handler: Callable):
        """Register event handler"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)

    def get_status(self) -> Dict[str, Any]:
        """Get proactive agent status"""
        return {
            "active": self.active,
            "reminders_pending": len(self.reminder_manager.get_pending()),
            "reminders_due_now": len(self.reminder_manager.get_due_now()),
            "proactive_enabled": persona.config.proactive_enabled,
            "morning_briefing": persona.config.morning_briefing,
            "briefing_time": persona.config.briefing_time,
            "last_briefing": self.last_briefing_date.isoformat() if self.last_briefing_date else None,
            "recent_activity": len(self.user_activity_log),
        }


# Global proactive agent instance
proactive_agent = ProactiveAgent()


def start_proactive() -> bool:
    """Start proactive agent"""
    return proactive_agent.start()


def stop_proactive():
    """Stop proactive agent"""
    proactive_agent.stop()


def add_reminder(title: str, when: Optional[str] = None, recurrence: Optional[str] = None) -> str:
    """Add a reminder"""
    return proactive_agent.add_reminder(title, when, recurrence)


def get_proactive_status() -> Dict[str, Any]:
    """Get proactive agent status"""
    return proactive_agent.get_status()
