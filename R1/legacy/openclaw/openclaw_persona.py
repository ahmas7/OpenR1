"""
OpenClaw-Style Persona System for R1
Creates a personalized AI assistant with memory, preferences, and character
"""

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import asyncio

from R1.memory.store import get_memory_store
from R1.audio.voice_system import speak, set_voice_preference

PERSONA_FILE = Path("E:/MYAI/R1/data/persona.json")


@dataclass
class PersonaConfig:
    """AI Assistant Persona Configuration"""

    name: str = "R1"  # User can name their assistant
    gender: str = "neutral"  # male, female, neutral
    personality: str = "helpful, friendly, and proactive"
    voice_enabled: bool = True
    voice_rate: int = 150
    wake_word: str = "hey r1"
    language: str = "en"
    timezone: str = "UTC"

    # Communication preferences
    proactive_enabled: bool = True
    morning_briefing: bool = True
    briefing_time: str = "08:00"
    check_ins_enabled: bool = True

    # User info learned over time
    user_name: str = ""
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    user_habits: List[str] = field(default_factory=list)
    important_dates: Dict[str, str] = field(default_factory=dict)

    # System
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


class PersonaManager:
    """Manages the AI assistant's persona and user memory"""

    def __init__(self):
        self.config = self._load_config()
        self._setup_voice()

    def _load_config(self) -> PersonaConfig:
        """Load persona from file or create default"""
        if PERSONA_FILE.exists():
            try:
                data = json.loads(PERSONA_FILE.read_text())
                return PersonaConfig(**data)
            except Exception as e:
                print(f"Error loading persona: {e}")
        return PersonaConfig()

    def _save_config(self):
        """Save persona to file"""
        self.config.updated_at = datetime.now().isoformat()
        PERSONA_FILE.parent.mkdir(parents=True, exist_ok=True)
        PERSONA_FILE.write_text(json.dumps(asdict(self.config), indent=2))

    def _setup_voice(self):
        """Configure voice settings"""
        if self.config.gender in ["male", "female"]:
            set_voice_preference(self.config.gender)

    # === Configuration Methods ===

    def set_name(self, name: str):
        """Set assistant's name"""
        self.config.name = name
        self._save_config()
        return f"I'll now respond to {name}"

    def set_user_name(self, name: str):
        """Set user's name"""
        self.config.user_name = name
        self._save_config()
        get_memory_store().set_fact("user_name", name, "personal")
        return f"Nice to meet you, {name}! I'll remember that."

    def set_personality(self, description: str):
        """Set assistant's personality"""
        self.config.personality = description
        self._save_config()
        return f"Personality updated: {description}"

    def set_wake_word(self, word: str):
        """Change the wake word"""
        self.config.wake_word = word.lower()
        self._save_config()
        from R1.audio.voice_system import set_wake_word

        set_wake_word(word.lower())
        return f"Wake word set to: '{word}'"

    def toggle_voice(self, enabled: bool = None):
        """Toggle voice responses"""
        if enabled is None:
            self.config.voice_enabled = not self.config.voice_enabled
        else:
            self.config.voice_enabled = enabled
        self._save_config()
        return f"Voice {'enabled' if self.config.voice_enabled else 'disabled'}"

    def set_proactive(self, enabled: bool):
        """Enable/disable proactive behavior"""
        self.config.proactive_enabled = enabled
        self._save_config()
        return f"Proactive mode {'enabled' if enabled else 'disabled'}"

    def set_briefing_time(self, time_str: str):
        """Set daily briefing time (HH:MM format)"""
        self.config.briefing_time = time_str
        self.config.morning_briefing = True
        self._save_config()
        return f"Daily briefing set for {time_str}"

    # === Memory & Context ===

    def learn_preference(self, key: str, value: Any):
        """Learn a user preference"""
        self.config.user_preferences[key] = value
        self._save_config()
        get_memory_store().set_fact(f"preference_{key}", str(value), "preferences")
        return f"Got it! I'll remember that you prefer {key}: {value}"

    def add_habit(self, habit: str):
        """Add a user habit"""
        if habit not in self.config.user_habits:
            self.config.user_habits.append(habit)
            self._save_config()
        return f"Noted: {habit}"

    def add_important_date(self, name: str, date: str):
        """Add an important date"""
        self.config.important_dates[name] = date
        self._save_config()
        return f"I'll remember {name} on {date}"

    def get_context_prompt(self) -> str:
        """Get persona context for LLM prompts"""
        lines = [
            f"You are {self.config.name}, a personal AI assistant.",
            f"Your personality: {self.config.personality}.",
        ]

        if self.config.user_name:
            lines.append(f"The user's name is {self.config.user_name}.")

        if self.config.user_preferences:
            lines.append("User preferences:")
            for k, v in self.config.user_preferences.items():
                lines.append(f"  - {k}: {v}")

        if self.config.user_habits:
            lines.append(f"User habits: {', '.join(self.config.user_habits)}")

        lines.append("You have persistent memory and learn from each conversation.")
        lines.append(
            "You can be proactive - suggest actions, give reminders, check in."
        )

        return "\n".join(lines)

    def get_summary(self) -> str:
        """Get persona summary"""
        return f"""
Assistant Name: {self.config.name}
Wake Word: "{self.config.wake_word}"
Personality: {self.config.personality}
Voice: {"Enabled" if self.config.voice_enabled else "Disabled"}
Proactive Mode: {"On" if self.config.proactive_enabled else "Off"}
Daily Briefing: {"On at " + self.config.briefing_time if self.config.morning_briefing else "Off"}

User Profile:
  Name: {self.config.user_name or "Not set"}
  Preferences: {len(self.config.user_preferences)} learned
  Habits: {len(self.config.user_habits)} tracked
        """.strip()

    # === Voice Interaction ===

    async def speak(self, text: str, blocking: bool = False):
        """Speak text if voice is enabled"""
        if self.config.voice_enabled:
            speak(text, async_mode=not blocking)

    def greet(self) -> str:
        """Generate a greeting"""
        hour = datetime.now().hour
        time_greeting = (
            "morning"
            if 5 <= hour < 12
            else "afternoon"
            if 12 <= hour < 18
            else "evening"
        )

        name_part = f", {self.config.user_name}" if self.config.user_name else ""

        greetings = [
            f"Good {time_greeting}{name_part}! I'm {self.config.name}, your personal assistant.",
            f"Hey{name_part}! Ready to help you out.",
            f"Hello{name_part}! What can I do for you today?",
        ]
        import random

        return random.choice(greetings)

    def generate_briefing(self) -> str:
        """Generate a morning briefing"""
        from datetime import datetime

        lines = [
            f"Good morning{', ' + self.config.user_name if self.config.user_name else ''}! Here's your briefing:"
        ]

        # Time and date
        now = datetime.now()
        lines.append(f"\n📅 Today is {now.strftime('%A, %B %d')}.")

        # Check calendar
        from R1.tools import tools

        try:
            loop = asyncio.get_event_loop()
            calendar_result = loop.run_until_complete(tools.calendar.get_events())
            if calendar_result.get("success"):
                events = calendar_result.get("events", [])
                today_events = [
                    e for e in events if e.get("date") == now.strftime("%Y-%m-%d")
                ]
                if today_events:
                    lines.append(f"\n📋 You have {len(today_events)} event(s) today:")
                    for e in today_events[:5]:
                        lines.append(f"  • {e.get('time', 'TBD')}: {e.get('title')}")
                else:
                    lines.append("\n📋 No events scheduled for today.")
        except Exception:
            pass

        # Check reminders
        lines.append("\n💡 I'm here if you need anything today!")

        return "\n".join(lines)


# Global persona manager instance
persona = PersonaManager()
