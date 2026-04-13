"""
ORION-R1 Proactive Agent
Anticipates user needs, auto-notifies, self-starts tasks
"""
import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

DATA_DIR = Path.home() / ".r1" / "proactive"
DATA_DIR.mkdir(parents=True, exist_ok=True)

class Priority(Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

@dataclass
class ProactiveSuggestion:
    id: str
    type: str  # notification, task, reminder, action
    title: str
    message: str
    priority: Priority
    context: Dict
    suggested_action: Dict
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    dismissed: bool = False
    acted_upon: bool = False

@dataclass
class UserPattern:
    id: str
    pattern_type: str  # time_based, app_based, file_based, conversation_based
    trigger: Dict
    action: Dict
    confidence: float = 0.0
    occurrences: int = 0
    last_triggered: str = None

class ProactiveAgent:
    def __init__(self):
        self.suggestions: Dict[str, ProactiveSuggestion] = {}
        self.patterns: Dict[str, UserPattern] = {}
        self.suggestion_file = DATA_DIR / "suggestions.json"
        self.patterns_file = DATA_DIR / "patterns.json"
        self.callbacks: List[Callable] = []
        self.monitoring = False
        self._load()

    def _load(self):
        if self.suggestion_file.exists():
            try:
                data = json.loads(self.suggestion_file.read_text())
                for s in data.get("suggestions", []):
                    self.suggestions[s["id"]] = ProactiveSuggestion(
                        id=s["id"],
                        type=s["type"],
                        title=s["title"],
                        message=s["message"],
                        priority=Priority(s.get("priority", "normal")),
                        context=s.get("context", {}),
                        suggested_action=s.get("suggested_action", {}),
                        created_at=s.get("created_at"),
                        dismissed=s.get("dismissed", False),
                        acted_upon=s.get("acted_upon", False)
                    )
            except:
                pass

        if self.patterns_file.exists():
            try:
                data = json.loads(self.patterns_file.read_text())
                for p in data.get("patterns", []):
                    self.patterns[p["id"]] = UserPattern(
                        id=p["id"],
                        pattern_type=p["pattern_type"],
                        trigger=p.get("trigger", {}),
                        action=p.get("action", {}),
                        confidence=p.get("confidence", 0.0),
                        occurrences=p.get("occurrences", 0),
                        last_triggered=p.get("last_triggered")
                    )
            except:
                pass

    def _save(self):
        # Save suggestions
        self.suggestion_file.write_text(json.dumps({
            "suggestions": [
                {
                    "id": s.id,
                    "type": s.type,
                    "title": s.title,
                    "message": s.message,
                    "priority": s.priority.value,
                    "context": s.context,
                    "suggested_action": s.suggested_action,
                    "created_at": s.created_at,
                    "dismissed": s.dismissed,
                    "acted_upon": s.acted_upon
                }
                for s in self.suggestions.values()
            ]
        }, indent=2))

        # Save patterns
        self.patterns_file.write_text(json.dumps({
            "patterns": [
                {
                    "id": p.id,
                    "pattern_type": p.pattern_type,
                    "trigger": p.trigger,
                    "action": p.action,
                    "confidence": p.confidence,
                    "occurrences": p.occurrences,
                    "last_triggered": p.last_triggered
                }
                for p in self.patterns.values()
            ]
        }, indent=2))

    def register_callback(self, callback: Callable):
        """Register callback for notifications"""
        self.callbacks.append(callback)

    async def notify(self, suggestion: ProactiveSuggestion):
        """Send notification to user"""
        self.suggestions[suggestion.id] = suggestion
        self._save()

        for callback in self.callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(suggestion)
                else:
                    callback(suggestion)
            except:
                pass

    # === PATTERN LEARNING ===

    def record_action(self, action_type: str, context: Dict):
        """Record user action for pattern learning"""
        # Look for matching patterns
        for pattern in self.patterns.values():
            if self._matches_trigger(pattern.trigger, context):
                pattern.occurrences += 1
                pattern.confidence = min(1.0, pattern.occurrences / 10)  # Cap at 1.0
                pattern.last_triggered = datetime.now().isoformat()

        self._save()

    def _matches_trigger(self, trigger: Dict, context: Dict) -> bool:
        """Check if context matches a trigger"""
        for key, value in trigger.items():
            if key not in context:
                return False
            if isinstance(value, dict):
                for k, v in value.items():
                    if context[key].get(k) != v:
                        return False
            elif context[key] != value:
                return False
        return True

    def learn_pattern(self, pattern_type: str, trigger: Dict, action: Dict) -> UserPattern:
        """Learn a new pattern from user behavior"""
        pattern_id = f"pattern_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        pattern = UserPattern(
            id=pattern_id,
            pattern_type=pattern_type,
            trigger=trigger,
            action=action,
            confidence=0.1,
            occurrences=1
        )
        self.patterns[pattern_id] = pattern
        self._save()
        return pattern

    # === PROACTIVE CHECKS ===

    async def check_and_suggest(self, system_status: Dict, user_context: Dict) -> List[ProactiveSuggestion]:
        """Check conditions and generate suggestions"""
        suggestions = []

        # System-based suggestions
        suggestions.extend(await self._check_system(system_status))

        # Time-based suggestions
        suggestions.extend(await self._check_time(user_context))

        # Pattern-based suggestions
        suggestions.extend(await self._check_patterns(user_context))

        # Task-based suggestions
        suggestions.extend(await self._check_tasks(user_context))

        return suggestions

    async def _check_system(self, status: Dict) -> List[ProactiveSuggestion]:
        """Check system conditions"""
        suggestions = []

        # High resource usage
        if status.get("memory", {}).get("percent", 0) > 85:
            suggestions.append(ProactiveSuggestion(
                id=f"suggest_{datetime.now().timestamp()}_mem",
                type="notification",
                title="High Memory Usage",
                message=f"Memory at {status['memory']['percent']}%. Consider closing apps.",
                priority=Priority.HIGH,
                context={"metric": "memory", "value": status["memory"]["percent"]},
                suggested_action={"tool": "app_control", "action": "list_windows"}
            ))

        if status.get("disk", [{}])[0].get("percent", 0) > 90:
            suggestions.append(ProactiveSuggestion(
                id=f"suggest_{datetime.now().timestamp()}_disk",
                type="notification",
                title="Disk Space Low",
                message="Disk is over 90% full. Clean up recommended.",
                priority=Priority.HIGH,
                context={"metric": "disk"},
                suggested_action={"tool": "filesystem", "action": "list_files", "params": {"directory": "C:/"}}
            ))

        # Battery
        battery = status.get("battery")
        if battery and battery.get("percent", 100) < 30 and not battery.get("plugged_in"):
            suggestions.append(ProactiveSuggestion(
                id=f"suggest_{datetime.now().timestamp()}_battery",
                type="notification",
                title="Battery Low",
                message=f"Battery at {battery['percent']}%. Plug in soon.",
                priority=Priority.URGENT if battery["percent"] < 15 else Priority.NORMAL,
                context={"metric": "battery"},
                suggested_action={"type": "notification", "message": "Plug in your charger!"}
            ))

        return suggestions

    async def _check_time(self, context: Dict) -> List[ProactiveSuggestion]:
        """Time-based suggestions"""
        suggestions = []
        now = datetime.now()

        # Morning briefing
        if now.hour == 8 and now.minute < 30:
            suggestions.append(ProactiveSuggestion(
                id=f"suggest_{now.strftime('%Y%m%d')}_morning",
                type="reminder",
                title="Morning Briefing",
                message="Good morning! Want me to summarize your day?",
                priority=Priority.NORMAL,
                context={"time": "morning"},
                suggested_action={"tool": "calendar", "action": "get_events"}
            ))

        # End of day
        if now.hour == 17 and now.minute < 30:
            suggestions.append(ProactiveSuggestion(
                id=f"suggest_{now.strftime('%Y%m%d')}_eod",
                type="reminder",
                title="End of Day",
                message="Wrapping up? Want me to save your work?",
                priority=Priority.NORMAL,
                context={"time": "end_of_day"},
                suggested_action={"tool": "filesystem", "action": "save_backup"}
            ))

        return suggestions

    async def _check_patterns(self, context: Dict) -> List[ProactiveSuggestion]:
        """Pattern-based suggestions"""
        suggestions = []

        for pattern in self.patterns.values():
            if pattern.confidence > 0.5 and self._matches_trigger(pattern.trigger, context):
                if pattern.last_triggered:
                    last = datetime.fromisoformat(pattern.last_triggered)
                    if (datetime.now() - last).total_seconds() < 3600:  # Don't repeat within an hour
                        continue

                suggestions.append(ProactiveSuggestion(
                    id=f"suggest_pattern_{pattern.id}",
                    type="suggestion",
                    title="Pattern Detected",
                    message=f"I noticed you often do this. Want me to help?",
                    priority=Priority.LOW,
                    context={"pattern_id": pattern.id},
                    suggested_action=pattern.action
                ))

        return suggestions

    async def _check_tasks(self, context: Dict) -> List[ProactiveSuggestion]:
        """Task-based suggestions"""
        suggestions = []

        # Check for pending tasks from memory
        # This would integrate with the task system
        return suggestions

    # === USER ACTIONS ===

    def dismiss_suggestion(self, suggestion_id: str):
        if suggestion_id in self.suggestions:
            self.suggestions[suggestion_id].dismissed = True
            self._save()

    def act_on_suggestion(self, suggestion_id: str):
        if suggestion_id in self.suggestions:
            self.suggestions[suggestion_id].acted_upon = True
            self._save()

    def get_suggestions(self, include_dismissed: bool = False) -> List[ProactiveSuggestion]:
        suggestions = list(self.suggestions.values())
        if not include_dismissed:
            suggestions = [s for s in suggestions if not s.dismissed]
        return sorted(suggestions, key=lambda s: s.created_at, reverse=True)

    def get_patterns(self) -> List[UserPattern]:
        return list(self.patterns.values())

    # === MONITORING LOOP ===

    async def start_monitoring(self, interval: int = 60, get_status_callback: Callable = None):
        """Start proactive monitoring"""
        self.monitoring = True

        while self.monitoring:
            if get_status_callback:
                try:
                    status = await get_status_callback()
                    suggestions = await self.check_and_suggest(status, {})
                    for s in suggestions:
                        await self.notify(s)
                except:
                    pass

            await asyncio.sleep(interval)

    def stop_monitoring(self):
        self.monitoring = False


# Singleton
_agent = None

def get_proactive_agent() -> ProactiveAgent:
    global _agent
    if _agent is None:
        _agent = ProactiveAgent()
    return _agent
