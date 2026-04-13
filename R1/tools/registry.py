"""
R1 v1 - Tool Registry
Manages tool registration, execution, and schema generation.
"""
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from .base import BaseTool, ToolResult, SafetyLevel
from .policy import evaluate_policy
from .audit import ToolAuditLogger, ToolAuditEvent
from ..config.settings import settings

logger = logging.getLogger("R1")


@dataclass
class ToolInfo:
    name: str
    description: str
    input_schema: Dict[str, Any]
    safety: SafetyLevel


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._audit = ToolAuditLogger()

    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name} (safety: {tool.safety.value})")

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def list_tools(self) -> List[ToolInfo]:
        return [
            ToolInfo(
                name=tool.name,
                description=tool.description,
                input_schema=tool.input_schema,
                safety=tool.safety
            )
            for tool in self._tools.values()
        ]

    def get_schemas(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema
                }
            }
            for tool in self._tools.values()
        ]

    async def execute(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        tool = self._tools.get(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                output=None,
                error=f"Tool not found: {tool_name}",
                tool_name=tool_name
            )

        decision = evaluate_policy(tool.safety)
        if decision.requires_confirmation:
            confirm = bool(arguments.get("_confirm"))
            if not confirm:
                return ToolResult(
                    success=False,
                    output=None,
                    error=decision.reason,
                    tool_name=tool_name,
                    requires_confirmation=True
                )
        elif not decision.allowed:
            return ToolResult(
                success=False,
                output=None,
                error=decision.reason or "Tool execution denied by policy.",
                tool_name=tool_name
            )

        if tool.safety == SafetyLevel.DANGEROUS:
            logger.warning(f"Executing dangerous tool: {tool_name}")

        safe_args = dict(arguments)
        safe_args.pop("_confirm", None)

        default_attempts = max(1, settings.tool_retries + 1)
        attempts = max(1, tool.retry_max + 1) if tool.retry_max else default_attempts
        backoff_base = max(0.0, tool.retry_backoff_base)

        for attempt in range(1, attempts + 1):
            try:
                result = await tool.execute(**safe_args)
                self._audit.log(ToolAuditEvent(
                    timestamp=datetime.utcnow().isoformat(),
                    tool_name=tool_name,
                    arguments=safe_args,
                    success=result.success,
                    output_preview=str(result.output)[:500] if result.output is not None else "",
                    error=result.error or ""
                ))
                return result
            except Exception as e:
                retryable = isinstance(e, tool.retry_on)
                logger.error(f"Tool execution error (attempt {attempt}/{attempts}): {e}")
                if attempt >= attempts:
                    self._audit.log(ToolAuditEvent(
                        timestamp=datetime.utcnow().isoformat(),
                        tool_name=tool_name,
                        arguments=safe_args,
                        success=False,
                        output_preview="",
                        error=str(e)
                    ))
                    return ToolResult(success=False, output=None, error=str(e), tool_name=tool_name)
                if not retryable:
                    await self._try_rollback(tool, safe_args)
                    return ToolResult(success=False, output=None, error=str(e), tool_name=tool_name)
                await asyncio.sleep(backoff_base * (2 ** (attempt - 1)))

    async def _try_rollback(self, tool: BaseTool, args: Dict[str, Any]) -> None:
        """Attempt rollback on a tool after failure."""
        try:
            rollback_result = await tool.rollback(**args)
            if rollback_result:
                logger.info(f"Rollback executed for tool '{tool.name}': {rollback_result.output}")
                self._audit.log(ToolAuditEvent(
                    timestamp=datetime.utcnow().isoformat(),
                    tool_name=f"{tool.name}:rollback",
                    arguments=args,
                    success=rollback_result.success,
                    output_preview=str(rollback_result.output)[:500] if rollback_result.output else "",
                    error=rollback_result.error or ""
                ))
        except Exception as e:
            logger.warning(f"Rollback failed for tool '{tool.name}': {e}")


def create_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    
    from .shell import ShellTool
    from .filesystem import FilesystemTool
    from .browser import BrowserTool
    from .code_exec import CodeExecTool
    from .app_launcher import AppLauncherTool
    
    registry.register(ShellTool())
    registry.register(FilesystemTool())
    registry.register(BrowserTool())
    registry.register(CodeExecTool())
    registry.register(AppLauncherTool())
    
    return registry


_tool_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = create_default_registry()
    return _tool_registry
