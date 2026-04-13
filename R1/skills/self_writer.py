"""
R1 - Self-Writing Skills System
Allows R1 to create, modify, and install new skills autonomously
"""
import os
import json
import logging
import hashlib
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger("R1:skills:self_writer")


@dataclass
class SkillManifest:
    """SKILL.md file structure"""
    name: str
    description: str
    version: str = "1.0.0"
    author: str = "R1"
    emoji: str = "🔧"
    commands: List[Dict] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    @classmethod
    def from_frontmatter(cls, content: str) -> 'SkillManifest':
        """Parse SKILL.md frontmatter"""
        import re

        # Extract frontmatter between --- markers
        match = re.search(r'---\n(.*?)\n---', content, re.DOTALL)
        if not match:
            raise ValueError("No frontmatter found")

        frontmatter = match.group(1)
        body = content[match.end():].strip()

        # Parse YAML-like frontmatter
        data = {}
        for line in frontmatter.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()

                # Parse lists
                if value.startswith('[') and value.endswith(']'):
                    items = value[1:-1].split(',')
                    data[key] = [item.strip().strip('"\'') for item in items if item.strip()]
                elif value.isdigit():
                    data[key] = int(value)
                else:
                    data[key] = value.strip('"\'')

        return cls(
            name=data.get('name', 'unknown'),
            description=data.get('description', 'No description'),
            version=data.get('version', '1.0.0'),
            author=data.get('author', 'R1'),
            emoji=data.get('emoji', '🔧'),
            commands=json.loads(data.get('commands', '[]')) if isinstance(data.get('commands'), str) else data.get('commands', []),
            dependencies=data.get('dependencies', []),
            permissions=data.get('permissions', []),
            tags=data.get('tags', []),
        )

    def to_frontmatter(self) -> str:
        """Convert to frontmatter string"""
        lines = [
            "---",
            f"name: {self.name}",
            f"description: {self.description}",
            f"version: {self.version}",
            f"author: {self.author}",
            f"emoji: {self.emoji}",
        ]

        if self.commands:
            lines.append(f"commands: {json.dumps(self.commands)}")
        if self.dependencies:
            lines.append(f"dependencies: [{', '.join(self.dependencies)}]")
        if self.permissions:
            lines.append(f"permissions: [{', '.join(self.permissions)}]")
        if self.tags:
            lines.append(f"tags: [{', '.join(self.tags)}]")

        lines.append("---")
        return '\n'.join(lines)


class SkillSelfWriter:
    """
    Enables R1 to create and modify its own skills.
    Skills are stored as SKILL.md files with frontmatter metadata.
    """

    def __init__(self, skills_dir: Path = None):
        self.skills_dir = skills_dir or Path.home() / ".r1" / "skills" / "workspace"
        self.skills_dir.mkdir(parents=True, exist_ok=True)

        self.registry_file = self.skills_dir / "registry.json"
        self.registry = self._load_registry()

        logger.info(f"SkillSelfWriter initialized at {self.skills_dir}")

    def _load_registry(self) -> Dict:
        """Load skill registry"""
        if self.registry_file.exists():
            try:
                return json.loads(self.registry_file.read_text())
            except:
                pass
        return {"skills": [], "created_by_r1": []}

    def _save_registry(self):
        """Save skill registry"""
        self.registry_file.write_text(json.dumps(self.registry, indent=2))

    def create_skill(self, name: str, description: str,
                     commands: List[Dict] = None,
                     body: str = "",
                     tags: List[str] = None,
                     permissions: List[str] = None) -> Dict:
        """
        Create a new skill file.

        Args:
            name: Skill name
            description: What the skill does
            commands: List of command definitions
            body: Skill implementation (shell commands, Python code, etc.)
            tags: Search tags
            permissions: Required permissions

        Returns:
            Dict with skill info or error
        """
        # Validate name
        if not name or not name.replace('_', '').replace('-', '').isalnum():
            return {"error": "Invalid skill name. Use alphanumeric, underscores, hyphens."}

        # Create skill directory
        skill_dir = self.skills_dir / name
        skill_dir.mkdir(exist_ok=True)

        # Create manifest
        manifest = SkillManifest(
            name=name,
            description=description,
            commands=commands or [],
            tags=tags or [],
            permissions=permissions or []
        )

        # Write SKILL.md
        skill_file = skill_dir / "SKILL.md"
        content = f"{manifest.to_frontmatter()}\n\n{body}"
        skill_file.write_text(content)

        # Update registry
        skill_info = {
            "name": name,
            "description": description,
            "path": str(skill_dir),
            "created_at": datetime.now().isoformat(),
            "created_by": "R1",
            "commands": commands or [],
            "tags": tags or []
        }
        self.registry["skills"].append(skill_info)
        self.registry["created_by_r1"].append(name)
        self._save_registry()

        logger.info(f"Created skill: {name}")

        return {
            "success": True,
            "skill": skill_info,
            "path": str(skill_file)
        }

    def update_skill(self, name: str, updates: Dict) -> Dict:
        """
        Update an existing skill.

        Args:
            name: Skill name
            updates: Dict of fields to update

        Returns:
            Dict with updated skill info or error
        """
        skill_dir = self.skills_dir / name
        skill_file = skill_dir / "SKILL.md"

        if not skill_file.exists():
            return {"error": f"Skill '{name}' not found"}

        try:
            # Read existing skill
            content = skill_file.read_text()
            manifest = SkillManifest.from_frontmatter(content)

            # Extract body (everything after frontmatter)
            import re
            match = re.search(r'---\n.*?\n---\n(.*)', content, re.DOTALL)
            body = match.group(1).strip() if match else ""

            # Apply updates
            for key, value in updates.items():
                if hasattr(manifest, key):
                    setattr(manifest, key, value)

            # Write updated skill
            new_content = f"{manifest.to_frontmatter()}\n\n{body}"
            skill_file.write_text(new_content)

            # Update registry
            for i, skill in enumerate(self.registry["skills"]):
                if skill["name"] == name:
                    self.registry["skills"][i].update({
                        "description": manifest.description,
                        "commands": manifest.commands,
                        "tags": manifest.tags,
                        "updated_at": datetime.now().isoformat()
                    })
                    break

            self._save_registry()

            logger.info(f"Updated skill: {name}")

            return {
                "success": True,
                "skill": {
                    "name": name,
                    "description": manifest.description,
                    "commands": manifest.commands
                }
            }

        except Exception as e:
            return {"error": str(e)}

    def delete_skill(self, name: str) -> Dict:
        """Delete a skill"""
        skill_dir = self.skills_dir / name

        if not skill_dir.exists():
            return {"error": f"Skill '{name}' not found"}

        try:
            # Remove directory
            import shutil
            shutil.rmtree(skill_dir)

            # Remove from registry
            self.registry["skills"] = [s for s in self.registry["skills"] if s["name"] != name]
            if name in self.registry["created_by_r1"]:
                self.registry["created_by_r1"].remove(name)
            self._save_registry()

            logger.info(f"Deleted skill: {name}")

            return {"success": True, "deleted": name}

        except Exception as e:
            return {"error": str(e)}

    def list_skills(self) -> List[Dict]:
        """List all skills"""
        return self.registry["skills"]

    def get_skill(self, name: str) -> Optional[Dict]:
        """Get skill details"""
        for skill in self.registry["skills"]:
            if skill["name"] == name:
                return skill
        return None

    def execute_skill(self, name: str, command: str = None,
                      args: Dict = None) -> Dict:
        """
        Execute a skill command.

        Args:
            name: Skill name
            command: Command to execute (from skill's commands list)
            args: Arguments for the command

        Returns:
            Execution result
        """
        skill_dir = self.skills_dir / name
        skill_file = skill_dir / "SKILL.md"

        if not skill_file.exists():
            return {"error": f"Skill '{name}' not found"}

        try:
            content = skill_file.read_text()
            manifest = SkillManifest.from_frontmatter(content)

            # Find command
            if command:
                cmd_def = None
                for cmd in manifest.commands:
                    if cmd.get("name") == command:
                        cmd_def = cmd
                        break

                if not cmd_def:
                    return {"error": f"Command '{command}' not found in skill '{name}'"}
            elif manifest.commands:
                cmd_def = manifest.commands[0]
            else:
                return {"error": f"No commands defined in skill '{name}'"}

            # Execute command
            cmd_type = cmd_def.get("type", "shell")
            cmd_action = cmd_def.get("action", "")

            if cmd_type == "shell":
                import subprocess
                result = subprocess.run(
                    cmd_action,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                return {
                    "success": result.returncode == 0,
                    "output": result.stdout,
                    "error": result.stderr
                }

            elif cmd_type == "python":
                # Execute Python code
                exec_globals = {"args": args or {}}
                exec(cmd_action, exec_globals)
                return {
                    "success": True,
                    "output": exec_globals.get("result", "Executed")
                }

            else:
                return {"error": f"Unknown command type: {cmd_type}"}

        except Exception as e:
            return {"error": str(e)}

    def discover_skills(self) -> List[str]:
        """Discover all SKILL.md files in the workspace"""
        skills = []
        for item in self.skills_dir.iterdir():
            if item.is_dir():
                skill_file = item / "SKILL.md"
                if skill_file.exists():
                    skills.append(item.name)
        return skills

    def generate_skill_from_pattern(self, pattern_name: str,
                                     trigger: str,
                                     response_template: str) -> Dict:
        """
        Generate a skill from an observed pattern.

        Args:
            pattern_name: Name for the pattern
            trigger: What triggers this skill
            response_template: Template for the response

        Returns:
            Created skill info
        """
        # Create a skill that responds to the trigger pattern
        skill_name = f"pattern_{hashlib.md5(trigger.encode()).hexdigest()[:8]}"

        # Generate command that matches the pattern
        commands = [{
            "name": "execute",
            "type": "response",
            "trigger": trigger,
            "action": response_template
        }]

        return self.create_skill(
            name=skill_name,
            description=f"Auto-generated skill for pattern: {pattern_name}",
            commands=commands,
            tags=["auto-generated", "pattern", pattern_name],
            body=f"# Pattern: {pattern_name}\n# Trigger: {trigger}\n# Response: {response_template}"
        )


# Global instance
_self_writer: Optional[SkillSelfWriter] = None


def get_skill_self_writer(skills_dir: Path = None) -> SkillSelfWriter:
    global _self_writer
    if _self_writer is None:
        _self_writer = SkillSelfWriter(skills_dir)
    return _self_writer


# ========== Pre-built Skill Templates ==========

def create_web_search_skill() -> SkillManifest:
    """Template for a web search skill"""
    return SkillManifest(
        name="web_search",
        description="Search the web for information",
        emoji="🔍",
        commands=[{
            "name": "search",
            "type": "shell",
            "action": "curl -s 'https://api.example.com/search?q={query}'"
        }],
        tags=["search", "web"],
        permissions=["browse"]
    )


def create_file_organizer_skill() -> SkillManifest:
    """Template for a file organization skill"""
    return SkillManifest(
        name="file_organizer",
        description="Organize files by type",
        emoji="📁",
        commands=[{
            "name": "organize",
            "type": "python",
            "action": """
import shutil
from pathlib import Path

download_dir = Path.home() / 'Downloads'
for f in download_dir.iterdir():
    if f.is_file():
        ext = f.suffix.lower()
        target_dir = download_dir / ext[1:] if ext else download_dir / 'other'
        target_dir.mkdir(exist_ok=True)
        shutil.move(str(f), str(target_dir / f.name))
result = 'Files organized'
"""
        }],
        tags=["files", "organization"],
        permissions=["filesystem_write"]
    )


def create_system_monitor_skill() -> SkillManifest:
    """Template for a system monitoring skill"""
    return SkillManifest(
        name="system_monitor",
        description="Monitor system resources",
        emoji="📊",
        commands=[{
            "name": "status",
            "type": "shell",
            "action": "echo 'CPU: $(top -bn1 | grep \"Cpu(s)\" | awk \"{print $2}\")%'"
        }],
        tags=["system", "monitoring"],
        permissions=["shell"]
    )
