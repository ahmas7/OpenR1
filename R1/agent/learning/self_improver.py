"""
R1 - Enhanced Self-Improving AI Engine
Analyzes, learns, and improves itself continuously with nightly reflection
"""
import os
import json
import time
import hashlib
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger("R1:self_improver")


class TrustLevel(Enum):
    STRANGER = "stranger"
    ACQUAINTANCE = "acquaintance"
    ASSOCIATE = "associate"
    PARTNER = "partner"
    OPERATOR = "operator"


class ImprovementType(Enum):
    PROMPT_UPDATE = "prompt_update"
    SKILL_ADDITION = "skill_addition"
    BUG_FIX = "bug_fix"
    PERFORMANCE = "performance"
    KNOWLEDGE_ADD = "knowledge_add"
    BEHAVIOR_CHANGE = "behavior_change"


@dataclass
class Lesson:
    id: str
    type: str
    description: str
    context: str
    success: bool
    timestamp: datetime
    applied: bool = False
    confidence: float = 0.5


@dataclass
class Pattern:
    id: str
    name: str
    trigger: str
    response: str
    success_rate: float
    times_used: int
    last_used: datetime


class SelfImprover:
    """
    R1's enhanced self-improvement system.
    Monitors performance, learns from interactions, and automatically improves.
    """

    def __init__(self, r1_home: Path = None):
        self.name = "R1-SelfImprover"
        self.version = "2.0"
        self.r1_home = r1_home or Path.home() / ".r1"

        # File paths
        self.memory_file = self.r1_home / "self_memory.json"
        self.improvements_file = self.r1_home / "improvements.json"
        self.lessons_file = self.r1_home / "lessons.json"
        self.patterns_file = self.r1_home / "patterns.json"
        self.trust_file = self.r1_home / "trust.json"
        self.reflection_file = self.r1_home / "reflections.json"

        # Ensure data directory exists
        self.r1_home.mkdir(parents=True, exist_ok=True)

        # Load existing data
        self.memory = self._load_json(self.memory_file, {"conversations": [], "learned": {}})
        self.improvements = self._load_json(self.improvements_file, [])
        self.lessons = self._load_json(self.lessons_file, [])
        self.patterns = self._load_json(self.patterns_file, [])
        self.trust_data = self._load_json(self.trust_file, self._default_trust_data())
        self.reflections = self._load_json(self.reflection_file, [])

        # Trust configuration
        self.trust_config = {
            "stranger": {"max_score": 20, "permissions": ["read", "chat"]},
            "acquaintance": {"max_score": 40, "permissions": ["read", "chat", "browse"]},
            "associate": {"max_score": 60, "permissions": ["read", "chat", "browse", "shell"]},
            "partner": {"max_score": 80, "permissions": ["read", "chat", "browse", "shell", "filesystem"]},
            "operator": {"max_score": 100, "permissions": ["full_access"]}
        }

        # Start time for uptime tracking
        self.start_time = time.time()

        logger.info(f"{self.name} v{self.version} initialized")
        logger.info(f"Loaded {len(self.lessons)} lessons, {len(self.patterns)} patterns")
        logger.info(f"Trust level: {self.trust_data.get('current_level', 'stranger')}")

    def _load_json(self, filepath: Path, default: Any) -> Any:
        """Load JSON file or return default"""
        if filepath.exists():
            try:
                return json.loads(filepath.read_text())
            except Exception as e:
                logger.error(f"Failed to load {filepath}: {e}")
        return default

    def _save_json(self, filepath: Path, data: Any):
        """Save data to JSON file"""
        try:
            filepath.write_text(json.dumps(data, indent=2, default=str))
        except Exception as e:
            logger.error(f"Failed to save {filepath}: {e}")

    def _default_trust_data(self) -> Dict:
        return {
            "current_level": TrustLevel.STRANGER.value,
            "scores": {
                "overall": 0,
                "coding": 0,
                "browsing": 0,
                "files": 0,
                "shell": 0
            },
            "history": [],
            "last_interaction": None
        }

    # ========== Learning Methods ==========

    def learn_from_interaction(self, user_input: str, ai_response: str,
                                outcome: str = None, tools_used: List[str] = None):
        """Learn from a conversation interaction"""
        interaction_id = hashlib.md5(f"{user_input}{datetime.now()}".encode()).hexdigest()[:8]

        # Store conversation
        self.memory["conversations"].append({
            "id": interaction_id,
            "user": user_input,
            "ai": ai_response,
            "outcome": outcome,
            "tools_used": tools_used or [],
            "timestamp": datetime.now().isoformat()
        })

        # Keep only last 1000 conversations
        if len(self.memory["conversations"]) > 1000:
            self.memory["conversations"] = self.memory["conversations"][-1000:]

        # Extract lesson if outcome is known
        if outcome:
            lesson = Lesson(
                id=interaction_id,
                type="interaction",
                description=f"Query: {user_input[:50]}...",
                context=json.dumps({"response": ai_response, "outcome": outcome}),
                success=outcome == "success",
                timestamp=datetime.now(),
                confidence=0.5
            )
            self.lessons.append(lesson)

        self._save_json(self.memory_file, self.memory)
        self._save_json(self.lessons_file, [self._lesson_to_dict(l) for l in self.lessons[-100:]])

    def _lesson_to_dict(self, lesson: Lesson) -> Dict:
        return {
            "id": lesson.id,
            "type": lesson.type,
            "description": lesson.description,
            "context": lesson.context,
            "success": lesson.success,
            "timestamp": lesson.timestamp.isoformat(),
            "confidence": lesson.confidence
        }

    # ========== Trust System ==========

    def update_trust(self, domain: str, success: bool, magnitude: int = 1):
        """Update trust score for a domain based on interaction outcome"""
        if domain not in self.trust_data["scores"]:
            self.trust_data["scores"][domain] = 0

        # Update score
        delta = magnitude if success else -magnitude
        self.trust_data["scores"][domain] = max(0, min(100,
            self.trust_data["scores"][domain] + delta))
        self.trust_data["scores"]["overall"] = max(0, min(100,
            self.trust_data["scores"]["overall"] + delta))

        # Record history
        self.trust_data["history"].append({
            "domain": domain,
            "success": success,
            "delta": delta,
            "timestamp": datetime.now().isoformat()
        })

        # Keep only last 500 history entries
        if len(self.trust_data["history"]) > 500:
            self.trust_data["history"] = self.trust_data["history"][-500:]

        self.trust_data["last_interaction"] = datetime.now().isoformat()

        # Recalculate trust level
        self._recalculate_trust_level()

        self._save_json(self.trust_file, self.trust_data)

        logger.info(f"Trust updated: {domain} {'+' if success else ''}{delta}, "
                   f"level now: {self.trust_data['current_level']}")

    def _recalculate_trust_level(self):
        """Recalculate overall trust level based on scores"""
        overall = self.trust_data["scores"]["overall"]

        if overall >= 80:
            self.trust_data["current_level"] = TrustLevel.OPERATOR.value
        elif overall >= 60:
            self.trust_data["current_level"] = TrustLevel.PARTNER.value
        elif overall >= 40:
            self.trust_data["current_level"] = TrustLevel.ASSOCIATE.value
        elif overall >= 20:
            self.trust_data["current_level"] = TrustLevel.ACQUAINTANCE.value
        else:
            self.trust_data["current_level"] = TrustLevel.STRANGER.value

    def get_trust_level(self) -> TrustLevel:
        """Get current trust level"""
        level_str = self.trust_data.get("current_level", "stranger")
        return TrustLevel(level_str)

    def get_permissions(self) -> List[str]:
        """Get permissions based on current trust level"""
        level = self.trust_data.get("current_level", "stranger")
        return self.trust_config.get(level, {}).get("permissions", [])

    def check_permission(self, action: str) -> bool:
        """Check if an action is permitted at current trust level"""
        permissions = self.get_permissions()

        # Full access means everything is allowed
        if "full_access" in permissions:
            return True

        return action in permissions

    # ========== Pattern Recognition ==========

    def detect_pattern(self, user_input: str, context: Dict = None) -> Optional[Pattern]:
        """Detect if input matches a known pattern"""
        input_lower = user_input.lower()

        for pattern in self.patterns:
            if pattern.trigger.lower() in input_lower:
                pattern.times_used += 1
                pattern.last_used = datetime.now()
                self._save_json(self.patterns_file, [self._pattern_to_dict(p) for p in self.patterns])
                return pattern

        return None

    def add_pattern(self, name: str, trigger: str, response: str, success: bool):
        """Add or update a pattern based on observed behavior"""
        # Check if pattern exists
        for pattern in self.patterns:
            if pattern.trigger == trigger:
                # Update existing
                pattern.success_rate = (pattern.success_rate * pattern.times_used + (1 if success else 0)) / (pattern.times_used + 1)
                pattern.times_used += 1
                pattern.last_used = datetime.now()
                self._save_json(self.patterns_file, [self._pattern_to_dict(p) for p in self.patterns])
                return

        # Create new pattern
        new_pattern = Pattern(
            id=hashlib.md5(f"{trigger}{datetime.now()}".encode()).hexdigest()[:8],
            name=name,
            trigger=trigger,
            response=response,
            success_rate=1.0 if success else 0.0,
            times_used=1,
            last_used=datetime.now()
        )
        self.patterns.append(new_pattern)
        self._save_json(self.patterns_file, [self._pattern_to_dict(p) for p in self.patterns])

    def _pattern_to_dict(self, pattern: Pattern) -> Dict:
        return {
            "id": pattern.id,
            "name": pattern.name,
            "trigger": pattern.trigger,
            "response": pattern.response,
            "success_rate": pattern.success_rate,
            "times_used": pattern.times_used,
            "last_used": pattern.last_used.isoformat()
        }

    # ========== Nightly Reflection ==========

    async def nightly_reflection(self, llm_callback=None) -> Dict[str, Any]:
        """
        Perform nightly reflection analyzing the day's interactions.
        Extracts lessons, identifies improvements, and updates behavior.
        """
        logger.info("Starting nightly reflection...")

        reflection_time = datetime.now()
        reflection_data = {
            "timestamp": reflection_time.isoformat(),
            "interactions_analyzed": 0,
            "lessons_extracted": 0,
            "improvements_suggested": 0,
            "patterns_updated": 0
        }

        # Get today's conversations
        today = datetime.now().date()
        todays_conversations = [
            c for c in self.memory.get("conversations", [])
            if datetime.fromisoformat(c["timestamp"]).date() == today
        ]

        reflection_data["interactions_analyzed"] = len(todays_conversations)

        # Analyze conversations for patterns
        success_count = 0
        failure_count = 0

        for conv in todays_conversations:
            if conv.get("outcome") == "success":
                success_count += 1
            elif conv.get("outcome") == "failure":
                failure_count += 1

        # Calculate success rate
        total = success_count + failure_count
        if total > 0:
            success_rate = success_count / total
            reflection_data["success_rate"] = success_rate

            # If success rate is low, suggest improvements
            if success_rate < 0.7:
                reflection_data["needs_improvement"] = True
                reflection_data["improvement_areas"] = [
                    "Response accuracy",
                    "Tool selection",
                    "Error handling"
                ]

        # Extract top lessons
        recent_lessons = sorted(
            self.lessons[-20:],
            key=lambda l: l.confidence,
            reverse=True
        )
        reflection_data["top_lessons"] = [
            {"description": l.description, "success": l.success, "confidence": l.confidence}
            for l in recent_lessons[:5]
        ]
        reflection_data["lessons_extracted"] = len(recent_lessons)

        # Identify patterns to reinforce or modify
        high_success_patterns = [
            p for p in self.patterns if p.success_rate > 0.8 and p.times_used > 3
        ]
        low_success_patterns = [
            p for p in self.patterns if p.success_rate < 0.5 and p.times_used > 3
        ]

        reflection_data["strong_patterns"] = len(high_success_patterns)
        reflection_data["weak_patterns"] = len(low_success_patterns)

        # Save reflection
        self.reflections.append(reflection_data)
        self._save_json(self.reflection_file, self.reflections[-30:])  # Keep last 30 days

        logger.info(f"Nightly reflection complete: {reflection_data['interactions_analyzed']} interactions, "
                   f"{reflection_data.get('success_rate', 0):.1%} success rate")

        return reflection_data

    # ========== Code Analysis ==========

    def analyze_code(self, code_file_path: str) -> Dict:
        """Analyze own code for improvements"""
        if not os.path.exists(code_file_path):
            return {"error": "File not found"}

        try:
            with open(code_file_path, 'r', encoding='utf-8') as f:
                code = f.read()

            analysis = {
                "file": code_file_path,
                "lines": len(code.split('\n')),
                "size": len(code),
                "hash": hashlib.md5(code.encode()).hexdigest(),
                "analyzed_at": datetime.now().isoformat()
            }

            # Simple pattern-based suggestions
            suggestions = []
            if "except:" in code:
                suggestions.append({"issue": "Bare except clause", "severity": "medium", "fix": "Use 'except Exception:'"})
            if "time.sleep" in code and "async" not in code:
                suggestions.append({"issue": "Using time.sleep (blocking)", "severity": "low", "fix": "Consider asyncio.sleep"})
            if code.count('\n') > 1000:
                suggestions.append({"issue": "File too large", "severity": "low", "fix": "Consider splitting into modules"})

            analysis["suggestions"] = suggestions

            return analysis
        except Exception as e:
            return {"error": str(e)}

    # ========== Statistics ==========

    def get_stats(self) -> Dict:
        """Get self-improvement statistics"""
        return {
            "conversations_learned": len(self.memory.get("conversations", [])),
            "lessons_stored": len(self.lessons),
            "patterns_recognized": len(self.patterns),
            "improvements_applied": len(self.improvements),
            "trust_level": self.trust_data.get("current_level", "stranger"),
            "trust_scores": self.trust_data.get("scores", {}),
            "reflections_completed": len(self.reflections),
            "uptime_hours": (time.time() - self.start_time) / 3600
        }

    def apply_improvement(self, improvement: Dict) -> bool:
        """Record an applied improvement"""
        improvement["applied_at"] = datetime.now().isoformat()
        self.improvements.append(improvement)
        self._save_json(self.improvements_file, self.improvements)
        return True


# Global instance
_improver: Optional[SelfImprover] = None


def get_self_improver(r1_home: Path = None) -> SelfImprover:
    global _improver
    if _improver is None:
        _improver = SelfImprover(r1_home)
    return _improver
