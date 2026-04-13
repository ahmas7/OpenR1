"""
R1 v1 - Shell Tool
"""
import asyncio
import logging
from typing import Dict, Any
from .base import BaseTool, ToolResult, SafetyLevel

logger = logging.getLogger("R1")


class ShellTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="shell",
            description="Execute shell commands. Use with caution.",
            safety=SafetyLevel.REVIEW
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"}
            },
            "required": ["command"]
        }

    async def execute(self, command: str = "", **kwargs) -> ToolResult:
        if not command:
            return ToolResult(success=False, output=None, error="No command provided", tool_name=self.name)

        logger.info(f"Executing shell: {command}")
        
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
            except asyncio.TimeoutError:
                process.kill()
                return ToolResult(
                    success=False,
                    output=None,
                    error="Command timed out after 30 seconds",
                    tool_name=self.name
                )

            output = stdout.decode() if stdout else ""
            error = stderr.decode() if stderr else ""
            
            if process.returncode != 0:
                return ToolResult(
                    success=False,
                    output=output,
                    error=error or f"Command exited with code {process.returncode}",
                    tool_name=self.name
                )
            
            return ToolResult(success=True, output=output, tool_name=self.name)

        except Exception as e:
            logger.error(f"Shell execution error: {e}")
            return ToolResult(success=False, output=None, error=str(e), tool_name=self.name)


_shell_tool: ShellTool = None

def get_shell_tool() -> ShellTool:
    global _shell_tool
    if _shell_tool is None:
        _shell_tool = ShellTool()
    return _shell_tool
