"""
R1 v1 - Code Execution Tool
"""
import logging
import asyncio
from typing import Dict, Any
from .base import BaseTool, ToolResult, SafetyLevel

logger = logging.getLogger("R1")


class CodeExecTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="code_exec",
            description="Execute Python code in a sandboxed environment.",
            safety=SafetyLevel.DANGEROUS
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code to execute"},
                "language": {"type": "string", "enum": ["python", "bash"], "default": "python"}
            },
            "required": ["code"]
        }

    async def execute(self, code: str = "", language: str = "python", **kwargs) -> ToolResult:
        if not code:
            return ToolResult(success=False, output=None, error="No code provided", tool_name=self.name)

        logger.info(f"Executing {language} code: {code[:100]}...")

        try:
            if language == "python":
                return await self._execute_python(code)
            elif language == "bash":
                return await self._execute_bash(code)
            else:
                return ToolResult(success=False, output=None, error=f"Unsupported language: {language}", tool_name=self.name)
        except Exception as e:
            logger.error(f"Code execution error: {e}")
            return ToolResult(success=False, output=None, error=str(e), tool_name=self.name)

    async def _execute_python(self, code: str) -> ToolResult:
        try:
            from R1.code_sandbox import get_code_sandbox

            result = await get_code_sandbox().execute_async(code)
            return ToolResult(
                success=result.success,
                output=result.output,
                error=result.error,
                tool_name=self.name
            )
        except ImportError:
            return ToolResult(
                success=False,
                output=None,
                error="Code executor not available",
                tool_name=self.name
            )

    async def _execute_bash(self, code: str) -> ToolResult:
        process = await asyncio.create_subprocess_shell(
            code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
        except asyncio.TimeoutError:
            process.kill()
            return ToolResult(success=False, output=None, error="Command timed out", tool_name=self.name)

        output = stdout.decode() if stdout else ""
        error = stderr.decode() if stderr else ""

        if process.returncode != 0:
            return ToolResult(success=False, output=output, error=error, tool_name=self.name)

        return ToolResult(success=True, output=output, tool_name=self.name)


_code_tool: CodeExecTool = None

def get_code_exec_tool() -> CodeExecTool:
    global _code_tool
    if _code_tool is None:
        _code_tool = CodeExecTool()
    return _code_tool
