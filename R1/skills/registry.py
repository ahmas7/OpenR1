"""
R1 v1 - Skills Registry
Central registry for managing skills.
"""
import logging
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
from datetime import datetime

from .schema import SkillManifest, SkillInstance, SkillSource, SkillStatus

logger = logging.getLogger("R1:skills")


class SkillRegistry:
    def __init__(self):
        self._skills: Dict[str, SkillInstance] = {}
        self._handlers: Dict[str, Callable] = {}
        self._discovery_paths: List[Path] = []
    
    def add_discovery_path(self, path: Path):
        """Add a path to search for skills"""
        if path.exists() and path.is_dir():
            self._discovery_paths.append(path)
            logger.info(f"Added skill discovery path: {path}")
    
    def discover_workspace_skills(self, workspace_path: Path = None):
        """Discover skills in workspace directories"""
        if workspace_path is None:
            workspace_path = Path.cwd()
        
        skill_dirs = []
        
        for pattern in ["skills", "plugins", ".skills"]:
            skills_dir = workspace_path / pattern
            if skills_dir.exists() and skills_dir.is_dir():
                skill_dirs.append(skills_dir)
        
        for skills_dir in skill_dirs:
            for item in skills_dir.iterdir():
                if item.is_dir():
                    manifest_path = item / "skill.json"
                    if manifest_path.exists():
                        try:
                            manifest = SkillManifest.load_from_file(manifest_path)
                            instance = SkillInstance(
                                manifest=manifest,
                                path=item,
                                status=SkillStatus.UNLOADED
                            )
                            self.register(instance)
                            logger.info(f"Discovered skill: {manifest.name}")
                        except Exception as e:
                            logger.warning(f"Failed to load skill manifest from {manifest_path}: {e}")
    
    def register(self, instance: SkillInstance):
        """Register a skill instance"""
        name = instance.manifest.name
        self._skills[name] = instance
        logger.info(f"Registered skill: {name}")
    
    def unregister(self, name: str) -> bool:
        """Unregister a skill"""
        if name in self._skills:
            self._unload(name)
            del self._skills[name]
            logger.info(f"Unregistered skill: {name}")
            return True
        return False
    
    def get(self, name: str) -> Optional[SkillInstance]:
        """Get a skill by name"""
        return self._skills.get(name)
    
    def list_skills(self, include_unloaded: bool = True) -> List[Dict[str, Any]]:
        """List all registered skills"""
        result = []
        for name, instance in self._skills.items():
            if include_unloaded or instance.status == SkillStatus.LOADED:
                result.append(instance.to_dict())
        return result
    
    def list_by_trigger(self, trigger: str) -> List[SkillInstance]:
        """Find skills that match a trigger"""
        trigger_lower = trigger.lower()
        matching = []
        for instance in self._skills.values():
            if instance.status != SkillStatus.LOADED:
                continue
            for t in instance.manifest.triggers:
                if t.lower() in trigger_lower:
                    matching.append(instance)
                    break
        return matching
    
    def load(self, name: str) -> bool:
        """Load a skill by name"""
        instance = self._skills.get(name)
        if not instance:
            logger.warning(f"Skill not found: {name}")
            return False
        
        if instance.status == SkillStatus.LOADED:
            return True
        
        try:
            instance.status = SkillStatus.LOADED
            instance.loaded_at = datetime.now().isoformat()
            logger.info(f"Loaded skill: {name}")
            return True
        except Exception as e:
            instance.status = SkillStatus.ERROR
            instance.error = str(e)
            logger.error(f"Failed to load skill {name}: {e}")
            return False
    
    def _unload(self, name: str):
        """Unload a skill"""
        instance = self._skills.get(name)
        if instance:
            instance.status = SkillStatus.UNLOADED
            instance.loaded_at = None
            logger.info(f"Unloaded skill: {name}")
    
    def unload(self, name: str) -> bool:
        """Unload a skill by name"""
        if name in self._skills:
            self._unload(name)
            return True
        return False    
    def reload(self, name: str) -> bool:
        """Reload a skill"""
        self._unload(name)
        return self.load(name)
    
    def invoke(self, name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke a skill with context"""
        instance = self._skills.get(name)
        if not instance:
            return {"success": False, "error": f"Skill not found: {name}"}
        
        if instance.status != SkillStatus.LOADED:
            self.load(name)
        
        handler = self._handlers.get(name)
        if not handler:
            return {"success": False, "error": f"No handler for skill: {name}"}
        
        try:
            result = handler(context)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Skill invocation error: {e}")
            return {"success": False, "error": str(e)}
    
    def register_handler(self, name: str, handler: Callable):
        """Register a handler function for a skill"""
        self._handlers[name] = handler
        logger.info(f"Registered handler for skill: {name}")


_skills_registry: Optional[SkillRegistry] = None


def get_skills_registry() -> SkillRegistry:
    global _skills_registry
    if _skills_registry is None:
        _skills_registry = SkillRegistry()
    return _skills_registry
