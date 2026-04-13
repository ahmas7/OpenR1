"""
R1 v1 - Filesystem Tool
"""
import logging
from pathlib import Path
from typing import Dict, Any, List
from .base import BaseTool, ToolResult, SafetyLevel

logger = logging.getLogger("R1")


class FilesystemTool(BaseTool):
    def __init__(self, allowed_root: str = ""):
        super().__init__(
            name="filesystem",
            description="Read, write, and list files in the filesystem.",
            safety=SafetyLevel.REVIEW
        )
        self.allowed_root = Path(allowed_root) if allowed_root else None

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["read", "write", "list", "delete"],
                    "description": "Action to perform"
                },
                "path": {"type": "string", "description": "File or directory path"},
                "content": {"type": "string", "description": "Content to write (for write action)"},
                "backup": {"type": "boolean", "description": "Create backup before write/delete"}
            },
            "required": ["action", "path"]
        }

    def _resolve_path(self, path: str) -> Path:
        p = Path(path).expanduser().resolve()
        if self.allowed_root:
            if not str(p).startswith(str(self.allowed_root)):
                raise PermissionError(f"Path outside allowed root: {path}")
        return p

    async def execute(self, action: str = "read", path: str = "", content: str = "", backup: bool = True, **kwargs) -> ToolResult:
        if not path:
            return ToolResult(success=False, output=None, error="No path provided", tool_name=self.name)

        try:
            p = self._resolve_path(path)
            
            if action == "read":
                if not p.exists():
                    return ToolResult(success=False, output=None, error="File not found", tool_name=self.name)
                if p.is_dir():
                    return ToolResult(success=False, output=None, error="Path is a directory", tool_name=self.name)
                text = p.read_text(encoding="utf-8")
                return ToolResult(success=True, output=text, tool_name=self.name)
            
            elif action == "write":
                if backup and p.exists() and p.is_file():
                    backup_path = p.parent / ".r1_backups"
                    backup_path.mkdir(parents=True, exist_ok=True)
                    backup_file = backup_path / f"{p.name}.bak"
                    backup_file.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8")
                return ToolResult(success=True, output=f"Written to {p}", tool_name=self.name)
            
            elif action == "list":
                if not p.exists():
                    return ToolResult(success=False, output=None, error="Directory not found", tool_name=self.name)
                if not p.is_dir():
                    return ToolResult(success=False, output=None, error="Path is not a directory", tool_name=self.name)
                
                items = []
                for item in p.iterdir():
                    items.append({
                        "name": item.name,
                        "is_dir": item.is_dir(),
                        "size": item.stat().st_size if item.is_file() else 0
                    })
                return ToolResult(success=True, output=items, tool_name=self.name)
            
            elif action == "delete":
                if not p.exists():
                    return ToolResult(success=False, output=None, error="Path not found", tool_name=self.name)
                if p.is_dir():
                    import shutil
                    if backup:
                        backup_path = p.parent / ".r1_backups"
                        backup_path.mkdir(parents=True, exist_ok=True)
                        shutil.make_archive(str(backup_path / p.name), "zip", str(p))
                    shutil.rmtree(p)
                else:
                    if backup:
                        backup_path = p.parent / ".r1_backups"
                        backup_path.mkdir(parents=True, exist_ok=True)
                        backup_file = backup_path / f"{p.name}.bak"
                        backup_file.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
                    p.unlink()
                return ToolResult(success=True, output=f"Deleted {p}", tool_name=self.name)
            
            else:
                return ToolResult(success=False, output=None, error=f"Unknown action: {action}", tool_name=self.name)
                
        except PermissionError as e:
            return ToolResult(success=False, output=None, error=str(e), tool_name=self.name)
        except Exception as e:
            logger.error(f"Filesystem error: {e}")
            return ToolResult(success=False, output=None, error=str(e), tool_name=self.name)


_fs_tool: FilesystemTool = None

def get_filesystem_tool() -> FilesystemTool:
    global _fs_tool
    if _fs_tool is None:
        _fs_tool = FilesystemTool()
    return _fs_tool
