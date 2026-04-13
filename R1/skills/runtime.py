"""
R1 v1 - Skills Runtime
Integration of skills with the agent runtime.
"""
import logging
from typing import Dict, Any, List, Optional

from .schema import SkillManifest, SkillInstance, SkillSource
from .registry import get_skills_registry, SkillRegistry
from .loader import get_skill_loader, SkillLoader

logger = logging.getLogger("R1:skills")


class SkillsRuntime:
    def __init__(self):
        self.registry: SkillRegistry = get_skills_registry()
        self.loader: SkillLoader = get_skill_loader()
        self._initialized = False
    
    async def initialize(self):
        """Initialize the skills runtime"""
        if self._initialized:
            return
        
        logger.info("Initializing SkillsRuntime...")
        
        from pathlib import Path
        workspace = Path.cwd()
        
        self.registry.add_discovery_path(workspace / "skills")
        self.registry.add_discovery_path(workspace / "plugins")
        self.registry.add_discovery_path(workspace / "workspace_skills")
        
        self.registry.discover_workspace_skills(workspace)
        
        self._initialized = True
        logger.info(f"SkillsRuntime initialized with {len(self.registry.list_skills())} skills")
    
    def discover_skills(self) -> List[Dict[str, Any]]:
        """Discover all available skills"""
        return self.registry.list_skills(include_unloaded=True)
    
    def list_loaded_skills(self) -> List[Dict[str, Any]]:
        """List loaded skills"""
        return self.registry.list_skills(include_unloaded=False)
    
    def load_skill(self, name: str) -> bool:
        """Load a skill by name"""
        return self.registry.load(name)
    
    def unload_skill(self, name: str) -> bool:
        """Unload a skill by name"""
        return self.registry.unload(name)
    
    def reload_skill(self, name: str) -> bool:
        """Reload a skill by name"""
        return self.registry.reload(name)
    
    def invoke_skill(self, name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke a skill with context - failure isolated"""
        try:
            return self.registry.invoke(name, context)
        except Exception as e:
            logger.error(f"Skill invocation failed for {name}: {e}")
            return {"success": False, "error": str(e), "isolated": True}
    
    def find_skills_for_goal(self, goal: str) -> List[SkillInstance]:
        """Find skills that might help with a goal"""
        matching_skills = []
        
        goal_lower = goal.lower()
        
        for skill in self.registry.list_skills():
            instance = self.registry.get(skill["manifest"]["name"])
            if not instance:
                continue
            
            for trigger in instance.manifest.triggers:
                if trigger.lower() in goal_lower:
                    matching_skills.append(instance)
                    break
        
        return matching_skills
    
    def get_skill_tools(self) -> List[Dict[str, Any]]:
        """Get tools exposed by loaded skills"""
        tools = []
        
        for skill_dict in self.registry.list_skills(include_unloaded=False):
            manifest = skill_dict["manifest"]
            tools.append({
                "name": f"skill:{manifest['name']}",
                "description": manifest.get("description", ""),
                "triggers": manifest.get("triggers", []),
                "tools_used": manifest.get("tools_used", [])
            })
        
        return tools


_skills_runtime: Optional[SkillsRuntime] = None


def get_skills_runtime() -> SkillsRuntime:
    global _skills_runtime
    if _skills_runtime is None:
        _skills_runtime = SkillsRuntime()
    return _skills_runtime
