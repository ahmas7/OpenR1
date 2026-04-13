"""
R1 v1 - Skills Schema
Canonical skill manifest format.
"""
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum


class SkillSource(Enum):
    BUNDLED = "bundled"
    WORKSPACE = "workspace"
    LOCAL = "local"


class SkillStatus(Enum):
    UNLOADED = "unloaded"
    LOADED = "loaded"
    ERROR = "error"


@dataclass
class SkillManifest:
    name: str
    description: str
    version: str = "1.0.0"
    entrypoint: str = "main.py"
    triggers: List[str] = field(default_factory=list)
    tools_used: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    source: SkillSource = SkillSource.LOCAL
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "SkillManifest":
        return SkillManifest(
            name=data.get("name", ""),
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            entrypoint=data.get("entrypoint", "main.py"),
            triggers=data.get("triggers", []),
            tools_used=data.get("tools_used", []),
            dependencies=data.get("dependencies", []),
            config=data.get("config", {}),
            source=SkillSource(data.get("source", "local"))
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "entrypoint": self.entrypoint,
            "triggers": self.triggers,
            "tools_used": self.tools_used,
            "dependencies": self.dependencies,
            "config": self.config,
            "source": self.source.value
        }
    
    @staticmethod
    def load_from_file(path: Path) -> "SkillManifest":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return SkillManifest.from_dict(data)
    
    def validate(self) -> List[str]:
        errors = []
        if not self.name:
            errors.append("Skill name is required")
        if not self.description:
            errors.append("Skill description is required")
        if not self.entrypoint:
            errors.append("Skill entrypoint is required")
        return errors


@dataclass
class SkillInstance:
    manifest: SkillManifest
    path: Path
    status: SkillStatus = SkillStatus.UNLOADED
    loaded_at: Optional[str] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "manifest": self.manifest.to_dict(),
            "path": str(self.path),
            "status": self.status.value,
            "loaded_at": self.loaded_at,
            "error": self.error
        }
