"""
R1 - Enhanced Skills System
Skill discovery, installation, and management
"""
import asyncio
import logging
import os
import shutil
import subprocess
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Set
from abc import ABC, abstractmethod
from enum import Enum
import tempfile
import hashlib
import re

logger = logging.getLogger("R1:skills")


class SkillSource(Enum):
    BUNDLED = "bundled"
    MANAGED = "managed"
    WORKSPACE = "workspace"
    LOCAL = "local"


class InstallKind(Enum):
    NPM = "node"
    PNPM = "pnpm"
    YARN = "yarn"
    BUN = "bun"
    BREW = "brew"
    DOWNLOAD = "download"
    GO = "go"
    UV = "uv"


@dataclass
class SkillInstallSpec:
    id: Optional[str] = None
    kind: InstallKind = InstallKind.NPM
    label: Optional[str] = None
    bins: List[str] = field(default_factory=list)
    os: List[str] = field(default_factory=list)
    formula: Optional[str] = None
    package: Optional[str] = None
    module: Optional[str] = None
    url: Optional[str] = None
    archive: Optional[str] = None
    extract: bool = False
    strip_components: int = 0
    target_dir: Optional[str] = None


@dataclass
class SkillMetadata:
    always: bool = False
    skill_key: Optional[str] = None
    primary_env: Optional[str] = None
    emoji: str = "🔧"
    homepage: Optional[str] = None
    os: List[str] = field(default_factory=list)
    requires_bins: List[str] = field(default_factory=list)
    requires_any_bins: List[str] = field(default_factory=list)
    requires_env: List[str] = field(default_factory=list)
    requires_config: List[str] = field(default_factory=list)
    install: List[SkillInstallSpec] = field(default_factory=list)


@dataclass
class SkillCommandSpec:
    name: str
    skill_name: str
    description: str
    dispatch_kind: str = "tool"
    tool_name: Optional[str] = None


@dataclass
class SkillEntry:
    name: str
    source: SkillSource
    file_path: str
    content: str
    metadata: Optional[SkillMetadata] = None
    frontmatter: Dict[str, str] = field(default_factory=dict)
    invocation_policy: Optional[Dict[str, bool]] = None
    installed: bool = False
    install_path: Optional[str] = None


@dataclass
class SkillSnapshot:
    prompt: str
    skills: List[Dict[str, Any]] = field(default_factory=list)
    skill_filter: Optional[List[str]] = None
    version: int = 1


class Skill(ABC):
    name: str = "base"
    description: str = "Base skill"
    triggers: List[str] = []
    
    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> "SkillResult":
        pass
    
    def can_handle(self, text: str) -> bool:
        text_lower = text.lower()
        return any(trigger in text_lower for trigger in self.triggers)


@dataclass
class SkillResult:
    success: bool
    output: str = ""
    error: Optional[str] = None
    data: Any = None


class SkillManager:
    def __init__(self, skills_dir: Optional[str] = None, config_dir: Optional[str] = None):
        self.skills_dir = Path(skills_dir) if skills_dir else Path.home() / ".r1" / "skills"
        self.config_dir = Path(config_dir) if config_dir else Path.home() / ".r1" / "config"
        self.bundled_skills_dir = Path(__file__).parent / "bundled_skills"
        self.workspace_skills_dir = self.skills_dir / "workspace"
        self.installed_skills: Dict[str, SkillEntry] = {}
        self._skill_instances: Dict[str, Skill] = {}
        self._commands: Dict[str, SkillCommandSpec] = {}
        self._node_manager = "npm"
        
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.workspace_skills_dir.mkdir(parents=True, exist_ok=True)
        
        self._load_bundled_skills()
    
    def _load_bundled_skills(self):
        if self.bundled_skills_dir.exists():
            for skill_file in self.bundled_skills_dir.glob("*.md"):
                self._load_skill_file(skill_file, SkillSource.BUNDLED)
    
    def _load_skill_file(self, file_path: Path, source: SkillSource):
        try:
            content = file_path.read_text(encoding="utf-8")
            
            frontmatter = {}
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    fm_text = parts[1]
                    content = parts[2].strip()
                    
                    for line in fm_text.strip().split("\n"):
                        if ":" in line:
                            key, value = line.split(":", 1)
                            frontmatter[key.strip()] = value.strip()
            
            metadata = None
            if "name" in frontmatter:
                metadata = SkillMetadata(
                    emoji=frontmatter.get("emoji", "🔧"),
                    description=frontmatter.get("description", ""),
                )
            
            entry = SkillEntry(
                name=frontmatter.get("name", file_path.stem),
                source=source,
                file_path=str(file_path),
                content=content,
                metadata=metadata,
                frontmatter=frontmatter,
            )
            
            self.installed_skills[entry.name] = entry
            
        except Exception as e:
            logger.error(f"Failed to load skill from {file_path}: {e}")
    
    def load_workspace_skills(self):
        if not self.workspace_skills_dir.exists():
            return
        
        for skill_dir in self.workspace_skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_md = skill_dir / "SKILL.md"
                if skill_md.exists():
                    self._load_skill_file(skill_md, SkillSource.WORKSPACE)
    
    def discover_skills(self, roots: List[str]) -> List[SkillEntry]:
        discovered = []
        
        for root in roots:
            root_path = Path(root)
            if not root_path.exists():
                continue
            
            for item in root_path.rglob("SKILL.md"):
                try:
                    content = item.read_text(encoding="utf-8")
                    
                    frontmatter = {}
                    if content.startswith("---"):
                        parts = content.split("---", 2)
                        if len(parts) >= 3:
                            fm_text = parts[1]
                            
                            for line in fm_text.strip().split("\n"):
                                if ":" in line:
                                    key, value = line.split(":", 1)
                                    frontmatter[key.strip()] = value.strip()
                    
                    name = frontmatter.get("name", item.stem)
                    
                    entry = SkillEntry(
                        name=name,
                        source=SkillSource.LOCAL,
                        file_path=str(item),
                        content=content,
                        frontmatter=frontmatter,
                    )
                    
                    discovered.append(entry)
                    
                except Exception as e:
                    logger.error(f"Failed to discover skill at {item}: {e}")
        
        return discovered
    
    def build_skill_snapshot(self, skill_filter: Optional[List[str]] = None) -> SkillSnapshot:
        skills_list = []
        prompt_parts = ["<available_skills>"]
        
        for name, entry in self.installed_skills.items():
            if skill_filter and name not in skill_filter:
                continue
            
            skill_info = {"name": name}
            
            if entry.metadata:
                skill_info["primary_env"] = entry.metadata.primary_env
                if entry.metadata.requires_env:
                    skill_info["required_env"] = entry.metadata.requires_env
            
            skills_list.append(skill_info)
            prompt_parts.append(f"<skill>{name}</skill>")
        
        prompt_parts.append("</available_skills>")
        
        return SkillSnapshot(
            prompt="\n".join(prompt_parts),
            skills=skills_list,
            skill_filter=skill_filter,
            version=1,
        )
    
    def format_skills_for_prompt(self) -> str:
        lines = ["<available_skills>"]
        
        for name, entry in self.installed_skills.items():
            lines.append(f"<skill>{name}</skill>")
        
        lines.append("</available_skills>")
        return "\n".join(lines)
    
    async def install_skill(self, skill_name: str, spec: SkillInstallSpec) -> SkillResult:
        try:
            if spec.kind in [InstallKind.NPM, InstallKind.PNPM, InstallKind.YARN, InstallKind.BUN]:
                return await self._install_node_skill(skill_name, spec)
            elif spec.kind == InstallKind.BREW:
                return await self._install_brew_skill(skill_name, spec)
            elif spec.kind == InstallKind.DOWNLOAD:
                return await self._install_download_skill(skill_name, spec)
            else:
                return SkillResult(success=False, error=f"Unsupported install kind: {spec.kind}")
        except Exception as e:
            return SkillResult(success=False, error=str(e))
    
    async def _install_node_skill(self, skill_name: str, spec: SkillInstallSpec) -> SkillResult:
        package = spec.package or skill_name
        install_dir = self.workspace_skills_dir / skill_name
        
        install_dir.mkdir(parents=True, exist_ok=True)
        
        cmd = [self._node_manager, "install", package]
        
        if spec.kind == InstallKind.PNPM:
            cmd[0] = "pnpm"
        elif spec.kind == InstallKind.YARN:
            cmd[0] = "yarn"
        elif spec.kind == InstallKind.BUN:
            cmd[0] = "bun"
        
        try:
            result = subprocess.run(
                cmd,
                cwd=str(install_dir),
                capture_output=True,
                text=True,
                timeout=300,
            )
            
            if result.returncode == 0:
                return SkillResult(
                    success=True,
                    output=f"Installed {skill_name} to {install_dir}",
                    data={"path": str(install_dir)},
                )
            else:
                return SkillResult(success=False, error=result.stderr)
                
        except Exception as e:
            return SkillResult(success=False, error=str(e))
    
    async def _install_brew_skill(self, skill_name: str, spec: SkillInstallSpec) -> SkillResult:
        formula = spec.formula or skill_name
        
        cmd = ["brew", "install", formula]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )
            
            if result.returncode == 0:
                return SkillResult(success=True, output=f"Installed {formula} via Homebrew")
            else:
                return SkillResult(success=False, error=result.stderr)
                
        except Exception as e:
            return SkillResult(success=False, error=str(e))
    
    async def _install_download_skill(self, skill_name: str, spec: SkillInstallSpec) -> SkillResult:
        if not spec.url:
            return SkillResult(success=False, error="No URL specified for download")
        
        target_dir = Path(spec.target_dir) if spec.target_dir else self.workspace_skills_dir / skill_name
        target_dir.mkdir(parents=True, exist_ok=True)
        
        import httpx
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(spec.url)
                response.raise_for_status()
                
                archive_path = target_dir / f"{skill_name}.tar.gz"
                archive_path.write_bytes(response.content)
                
                if spec.extract:
                    import tarfile
                    with tarfile.open(archive_path) as tar:
                        tar.extractall(target_dir)
                
                return SkillResult(
                    success=True,
                    output=f"Downloaded {skill_name} to {target_dir}",
                    data={"path": str(target_dir)},
                )
            except Exception as e:
                return SkillResult(success=False, error=str(e))
    
    def uninstall_skill(self, skill_name: str) -> SkillResult:
        skill_dir = self.workspace_skills_dir / skill_name
        
        if not skill_dir.exists():
            return SkillResult(success=False, error=f"Skill {skill_name} not found")
        
        try:
            shutil.rmtree(skill_dir)
            if skill_name in self.installed_skills:
                del self.installed_skills[skill_name]
            
            return SkillResult(success=True, output=f"Uninstalled {skill_name}")
        except Exception as e:
            return SkillResult(success=False, error=str(e))
    
    def list_skills(self) -> List[Dict[str, Any]]:
        result = []
        
        for name, entry in self.installed_skills.items():
            result.append({
                "name": name,
                "source": entry.source.value,
                "file_path": entry.file_path,
                "installed": entry.installed,
                "metadata": {
                    "emoji": entry.metadata.emoji if entry.metadata else "🔧",
                    "always": entry.metadata.always if entry.metadata else False,
                } if entry.metadata else None,
            })
        
        return result
    
    def get_skill_commands(self) -> List[SkillCommandSpec]:
        commands = []
        
        for name, entry in self.installed_skills.items():
            if entry.frontmatter.get("commands"):
                try:
                    cmds = json.loads(entry.frontmatter["commands"])
                    for cmd in cmds:
                        commands.append(SkillCommandSpec(
                            name=cmd.get("name", name),
                            skill_name=name,
                            description=cmd.get("description", ""),
                            dispatch_kind=cmd.get("dispatch", "tool"),
                            tool_name=cmd.get("tool"),
                        ))
                except json.JSONDecodeError:
                    pass
        
        return commands
    
    async def handle(self, text: str, context: Dict[str, Any]) -> Optional[SkillResult]:
        for name, skill in self._skill_instances.items():
            if skill.can_handle(text):
                return await skill.execute(context)
        return None
    
    def register_skill_instance(self, skill: Skill):
        self._skill_instances[skill.name] = skill
    
    def get_skill(self, name: str) -> Optional[Skill]:
        return self._skill_instances.get(name)
    
    def set_node_manager(self, manager: str):
        if manager in ["npm", "pnpm", "yarn", "bun"]:
            self._node_manager = manager
    
    def matches_skill_filter(self, filter_list: Optional[List[str]]) -> bool:
        if not filter_list:
            return True
        return len(filter_list) > 0


class SkillInstaller:
    def __init__(self, skill_manager: SkillManager):
        self.skill_manager = skill_manager
        self._download_cache: Dict[str, str] = {}
    
    async def install_from_source(self, source: str, skill_name: str) -> SkillResult:
        if source.startswith("http://") or source.startswith("https://"):
            spec = SkillInstallSpec(
                kind=InstallKind.DOWNLOAD,
                url=source,
            )
            return await self.skill_manager.install_skill(skill_name, spec)
        elif source.startswith("npm:"):
            package = source[4:]
            spec = SkillInstallSpec(
                kind=InstallKind.NPM,
                package=package,
            )
            return await self.skill_manager.install_skill(skill_name, spec)
        elif source.startswith("brew:"):
            formula = source[5:]
            spec = SkillInstallSpec(
                kind=InstallKind.BREW,
                formula=formula,
            )
            return await self.skill_manager.install_skill(skill_name, spec)
        else:
            return SkillResult(success=False, error=f"Unknown source: {source}")
    
    async def install_from_manifest(self, manifest: Dict[str, Any]) -> List[SkillResult]:
        results = []
        
        skills = manifest.get("skills", [])
        
        for skill in skills:
            name = skill.get("name")
            source = skill.get("source")
            
            if not name or not source:
                continue
            
            result = await self.install_from_source(source, name)
            results.append(result)
        
        return results
    
    def validate_skill(self, skill_path: Path) -> bool:
        if not skill_path.exists():
            return False
        
        if not skill_path.is_dir():
            skill_file = skill_path
        else:
            skill_file = skill_path / "SKILL.md"
        
        if not skill_file.exists():
            return False
        
        try:
            content = skill_file.read_text(encoding="utf-8")
            
            if not content.startswith("---"):
                return False
            
            parts = content.split("---", 2)
            if len(parts) < 3:
                return False
            
            fm_text = parts[1]
            if "name:" not in fm_text:
                return False
            
            return True
        except Exception:
            return False
