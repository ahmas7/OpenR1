"""
R1 v1 - Base Tool Interface
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional
from enum import Enum


class SafetyLevel(Enum):
    SAFE = "safe"
    REVIEW = "review"
    DANGEROUS = "dangerous"


@dataclass
class ToolResult:
    success: bool
    output: Any
    error: Optional[str] = None
    tool_name: str = ""
    requires_confirmation: bool = False


class BaseTool(ABC):
    def __init__(self, name: str, description: str, safety: SafetyLevel = SafetyLevel.SAFE):
        self.name = name
        self.description = description
        self.safety = safety

    @property
    @abstractmethod
    def input_schema(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        pass

    @property
    def retry_on(self):
        return (TimeoutError, ConnectionError, RuntimeError)

    @property
    def retry_max(self) -> int:
        return 0

    @property
    def retry_backoff_base(self) -> float:
        return 0.5

    async def rollback(self, **kwargs) -> Optional["ToolResult"]:
        """Optional rollback action when tool execution fails after all retries.
        Override in subclasses to implement cleanup/undo logic.
        Returns None if no rollback is needed."""
        return None
