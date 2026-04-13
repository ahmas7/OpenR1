"""
R1 v1 - Tool Audit Logger
Writes tool execution events to JSONL with rotation and read-back.
"""
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from ..config.settings import settings


@dataclass
class ToolAuditEvent:
    timestamp: str
    tool_name: str
    arguments: Dict[str, Any]
    success: bool
    output_preview: str
    error: str = ""


class ToolAuditLogger:
    def __init__(self, path: str = ""):
        base_dir = Path.home() / ".r1"
        base_dir.mkdir(parents=True, exist_ok=True)
        self.path = Path(path or (base_dir / "tool_audit.jsonl"))

    def log(self, event: ToolAuditEvent) -> None:
        self._rotate_if_needed()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(event)) + "\n")

    def read_recent(self, n: int = 20) -> List[Dict[str, Any]]:
        """Read the last N entries from the audit log.

        Args:
            n: Number of recent entries to return.

        Returns:
            List of audit event dicts, most recent last.
        """
        if not self.path.exists():
            return []

        try:
            lines = self.path.read_text(encoding="utf-8").strip().splitlines()
            recent = lines[-n:] if len(lines) > n else lines
            entries = []
            for line in recent:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            return entries
        except Exception:
            return []

    def clear(self) -> None:
        """Delete the audit log file (for testing)."""
        if self.path.exists():
            self.path.unlink(missing_ok=True)

    def count(self) -> int:
        """Return total number of audit entries."""
        if not self.path.exists():
            return 0
        try:
            return len(self.path.read_text(encoding="utf-8").strip().splitlines())
        except Exception:
            return 0

    def _rotate_if_needed(self) -> None:
        if not self.path.exists():
            return

        if self.path.stat().st_size < settings.audit_max_bytes:
            return

        max_files = max(1, settings.audit_max_files)
        for idx in range(max_files - 1, 0, -1):
            src = self.path.with_suffix(f".jsonl.{idx}")
            dst = self.path.with_suffix(f".jsonl.{idx + 1}")
            if src.exists():
                if idx + 1 > max_files:
                    src.unlink(missing_ok=True)
                else:
                    src.replace(dst)

        first_rot = self.path.with_suffix(".jsonl.1")
        self.path.replace(first_rot)
