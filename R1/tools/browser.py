"""
R1 v1 - Browser Tool
"""
import logging
from typing import Dict, Any
from .base import BaseTool, ToolResult, SafetyLevel

logger = logging.getLogger("R1")

_browser_controller = None


async def _get_browser():
    global _browser_controller
    if _browser_controller is None:
        try:
            from R1.browser import BrowserController
            _browser_controller = await BrowserController.get(headless=True)
        except Exception as e:
            logger.warning(f"Browser not available: {e}")
            return None
    return _browser_controller


class BrowserTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="browser",
            description="Navigate, search, and interact with web pages.",
            safety=SafetyLevel.SAFE
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["navigate", "search", "click", "fill", "get_text", "screenshot"],
                    "description": "Action to perform"
                },
                "url": {"type": "string", "description": "URL for navigate action"},
                "query": {"type": "string", "description": "Search query"},
                "selector": {"type": "string", "description": "CSS selector for click/fill/get_text"},
                "value": {"type": "string", "description": "Value to fill"},
                "script": {"type": "string", "description": "JavaScript to execute"}
            },
            "required": ["action"]
        }

    async def execute(self, action: str = "navigate", url: str = "", query: str = "",
                     selector: str = "", value: str = "", script: str = "", **kwargs) -> ToolResult:
        try:
            browser = await _get_browser()
            if not browser:
                return ToolResult(success=False, output=None, error="Browser not available", tool_name=self.name)

            if action == "navigate":
                result = await browser.navigate(url or "https://www.google.com")
                return ToolResult(
                    success=result.success,
                    output=result.content[:500] if result.content else "",
                    error=result.error,
                    tool_name=self.name
                )

            elif action == "search":
                result = await browser.search_google(query)
                return ToolResult(
                    success=result.success,
                    output=result.data[:10] if result.data else [],
                    error=result.error,
                    tool_name=self.name
                )

            elif action == "click":
                result = await browser.click(selector)
                return ToolResult(
                    success=result.success,
                    output=result.content[:200] if result.content else "",
                    error=result.error,
                    tool_name=self.name
                )

            elif action == "fill":
                result = await browser.fill(selector, value)
                return ToolResult(
                    success=result.success,
                    output=result.content[:200] if result.content else "",
                    error=result.error,
                    tool_name=self.name
                )

            elif action == "get_text":
                result = await browser.get_text(selector)
                return ToolResult(
                    success=result.success,
                    output=result.content,
                    error=result.error,
                    tool_name=self.name
                )

            elif action == "screenshot":
                result = await browser.screenshot()
                return ToolResult(
                    success=result.success,
                    output=result.data,
                    error=result.error,
                    tool_name=self.name
                )

            else:
                return ToolResult(success=False, output=None, error=f"Unknown action: {action}", tool_name=self.name)

        except Exception as e:
            logger.error(f"Browser error: {e}")
            return ToolResult(success=False, output=None, error=str(e), tool_name=self.name)


_browser_tool: BrowserTool = None

def get_browser_tool() -> BrowserTool:
    global _browser_tool
    if _browser_tool is None:
        _browser_tool = BrowserTool()
    return _browser_tool
