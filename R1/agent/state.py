"""
R1 v1 - Agent State
Current task/session state.
"""
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class AgentStatus(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    ACTING = "acting"
    WAITING = "waiting"
    DONE = "done"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass
class AgentState:
    session_id: str
    status: AgentStatus = AgentStatus.IDLE
    goal: str = ""
    plan: Dict[str, Any] = field(default_factory=dict)
    current_step: int = 0
    iteration: int = 0
    last_action: str = ""
    last_result: Optional[str] = ""
    messages: List[Dict[str, str]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    error: Optional[str] = None

    def update(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.now()
