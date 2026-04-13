"""
R1 - Skills & Plugins
Extensible capabilities system
"""
import asyncio
import re
from abc import ABC, abstractmethod
from typing import Dict, Any, Callable, Optional, List
from dataclasses import dataclass


@dataclass
class SkillResult:
    success: bool
    output: str = ""
    error: Optional[str] = None
    data: Any = None


class Skill(ABC):
    """Base class for all skills"""
    name: str = "base"
    description: str = "Base skill"
    triggers: List[str] = []
    
    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> SkillResult:
        pass
    
    def can_handle(self, text: str) -> bool:
        text_lower = text.lower()
        return any(trigger in text_lower for trigger in self.triggers)


class CalculatorSkill(Skill):
    name = "calculator"
    description = "Mathematical calculations"
    triggers = ["calculate", "compute", "what is", "how much", "="]
    
    async def execute(self, context: Dict[str, Any]) -> SkillResult:
        expression = context.get("expression", "")
        try:
            allowed = set("0123456789+-*/.() ")
            if not all(c in allowed for c in expression):
                return SkillResult(success=False, error="Invalid characters")
            result = eval(expression)
            return SkillResult(success=True, output=str(result))
        except Exception as e:
            return SkillResult(success=False, error=str(e))


class ShellSkill(Skill):
    name = "shell"
    description = "Execute shell commands"
    triggers = ["run ", "execute ", "shell ", "cmd "]
    
    async def execute(self, context: Dict[str, Any]) -> SkillResult:
        command = context.get("command", "")
        from R1.system import Shell
        result = await Shell.execute(command)
        return SkillResult(
            success=result.success,
            output=result.output,
            error=result.error
        )


class FileSkill(Skill):
    name = "files"
    description = "File operations"
    triggers = ["read file", "write file", "delete file", "list files", "create folder"]
    
    async def execute(self, context: Dict[str, Any]) -> SkillResult:
        action = context.get("action", "")
        path = context.get("path", "")
        content = context.get("content", "")
        
        from R1.system import FileSystem
        
        if "read" in action:
            result = FileSystem.read(path)
        elif "write" in action or "create" in action:
            result = FileSystem.write(path, content)
        elif "delete" in action:
            result = FileSystem.delete(path)
        elif "list" in action:
            result = FileSystem.list(path)
        elif "folder" in action:
            result = FileSystem.create_dir(path)
        else:
            return SkillResult(success=False, error="Unknown action")
        
        return SkillResult(success=result.success, output=result.output, error=result.error)


class WebSearchSkill(Skill):
    name = "search"
    description = "Search the web"
    triggers = ["search ", "find ", "google ", "lookup "]
    
    async def execute(self, context: Dict[str, Any]) -> SkillResult:
        query = context.get("query", "")
        from R1.browser import Browser
        async with Browser() as b:
            result = await b.search_google(query)
            return SkillResult(success=result.success, output=result.content, error=result.error)


class ReminderSkill(Skill):
    name = "reminder"
    description = "Set reminders"
    triggers = ["remind me", "reminder", "set alarm", "remember to"]
    
    def __init__(self):
        self.reminders: List[Dict[str, str]] = []
    
    async def execute(self, context: Dict[str, Any]) -> SkillResult:
        action = context.get("action", "")
        
        if "list" in action:
            if not self.reminders:
                return SkillResult(success=True, output="No reminders set")
            lines = [f"- {r['time']}: {r['task']}" for r in self.reminders]
            return SkillResult(success=True, output="\n".join(lines))
        
        return SkillResult(success=True, output="Reminder set")


class SystemInfoSkill(Skill):
    name = "system"
    description = "System information"
    triggers = ["system info", "cpu", "memory", "disk", "battery", "processes"]
    
    async def execute(self, context: Dict[str, Any]) -> SkillResult:
        query = context.get("query", "").lower()
        from R1.system import SystemInfo
        
        if "cpu" in query:
            info = SystemInfo.info()
            return SkillResult(success=True, output=f"CPU: {info['cpu_percent']}%")
        elif "memory" in query:
            info = SystemInfo.info()
            return SkillResult(success=True, output=f"Memory: {info['memory_percent']}%")
        elif "disk" in query:
            info = SystemInfo.info()
            return SkillResult(success=True, output=f"Disk: {info['disk_percent']}%")
        elif "battery" in query:
            info = SystemInfo.battery()
            if info:
                return SkillResult(success=True, output=f"Battery: {info['percent']}%")
            return SkillResult(success=False, error="No battery")
        else:
            info = SystemInfo.info()
            return SkillResult(success=True, output=str(info))


class SkillManager:
    def __init__(self):
        self.skills: Dict[str, Skill] = {}
        self._register_builtins()
    
    def _register_builtins(self):
        self.register(CalculatorSkill())
        self.register(ShellSkill())
        self.register(FileSkill())
        self.register(WebSearchSkill())
        self.register(ReminderSkill())
        self.register(SystemInfoSkill())
    
    def register(self, skill: Skill):
        self.skills[skill.name] = skill
    
    async def handle(self, text: str, context: Dict[str, Any]) -> Optional[SkillResult]:
        for skill in self.skills.values():
            if skill.can_handle(text):
                return await skill.execute(context)
        return None
    
    def list_skills(self) -> List[Dict[str, str]]:
        return [{"name": s.name, "description": s.description, "triggers": s.triggers} 
                for s in self.skills.values()]
