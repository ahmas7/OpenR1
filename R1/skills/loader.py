"""
R1 v1 - Skills Loader
Lazy loading and skill module management.
"""
import logging
import importlib.util
import sys
from typing import Dict, Any, Optional, Callable
from pathlib import Path

from .schema import SkillManifest, SkillInstance, SkillSource, SkillStatus
from .registry import get_skills_registry

logger = logging.getLogger("R1:skills")


class SkillLoader:
    def __init__(self):
        self._loaded_modules: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}
    
    def discover_and_load(self, base_path: Path = None) -> int:
        """Discover and load all skills in a directory"""
        if base_path is None:
            base_path = Path.cwd() / "skills"
        
        if not base_path.exists():
            logger.info(f"Skills directory does not exist: {base_path}")
            return 0
        
        loaded_count = 0
        
        for item in base_path.iterdir():
            if item.is_dir():
                manifest_path = item / "skill.json"
                if manifest_path.exists():
                    if self.load_skill(item):
                        loaded_count += 1
        
        return loaded_count
    
    def load_skill(self, skill_path: Path) -> bool:
        """Load a skill from a directory"""
        try:
            manifest_path = skill_path / "skill.json"
            manifest = SkillManifest.load_from_file(manifest_path)
            
            instance = SkillInstance(
                manifest=manifest,
                path=skill_path,
                status=SkillStatus.LOADED
            )
            
            registry = get_skills_registry()
            registry.register(instance)
            
            main_file = skill_path / manifest.entrypoint
            if main_file.exists():
                module = self._load_module(manifest.name, main_file)
                if module:
                    self._loaded_modules[manifest.name] = module
                    
                    if hasattr(module, "register"):
                        handler = module.register()
                        if handler:
                            registry.register_handler(manifest.name, handler)
            
            logger.info(f"Loaded skill: {manifest.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load skill from {skill_path}: {e}")
            return False
    
    def _load_module(self, name: str, path: Path):
        """Dynamically load a Python module"""
        spec = importlib.util.spec_from_file_location(name, path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            return module
        return None
    
    def unload_skill(self, name: str) -> bool:
        """Unload a skill module"""
        if name in self._loaded_modules:
            del self._loaded_modules[name]
        
        if name in sys.modules:
            del sys.modules[name]
        
        registry = get_skills_registry()
        registry.unload(name)
        
        logger.info(f"Unloaded skill: {name}")
        return True
    
    def reload_skill(self, name: str) -> bool:
        """Reload a skill"""
        self.unload_skill(name)
        return self.load_skill(Path(f"skills/{name}"))
    
    def get_handler(self, name: str) -> Optional[Callable]:
        """Get a skill's handler function"""
        return self._factories.get(name)
    
    def register_factory(self, name: str, factory: Callable):
        """Register a factory function for lazy skill creation"""
        self._factories[name] = factory


_skill_loader: Optional[SkillLoader] = None


def get_skill_loader() -> SkillLoader:
    global _skill_loader
    if _skill_loader is None:
        _skill_loader = SkillLoader()
    return _skill_loader
