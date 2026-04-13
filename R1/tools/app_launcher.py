"""
R1 v1 - App Launcher Tool (Windows)
"""
import os
import re
import subprocess
from typing import Dict, Any
from .base import BaseTool, ToolResult, SafetyLevel


APP_ALIASES = {
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "notepad": "notepad.exe",
    "explorer": "explorer.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "firefox": "firefox.exe",
}

URL_RE = re.compile(r"^https?://", re.IGNORECASE)
DOMAIN_RE = re.compile(r"^[a-z0-9.-]+\\.[a-z]{2,}(/.*)?$", re.IGNORECASE)


class AppLauncherTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="app_open",
            description="Open a local application by name or path.",
            safety=SafetyLevel.REVIEW
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "app": {"type": "string", "description": "App name or path (e.g., calculator, notepad)"},
            },
            "required": ["app"]
        }

    async def execute(self, app: str = "", **kwargs) -> ToolResult:
        if not app:
            return ToolResult(success=False, output=None, error="No app provided", tool_name=self.name)

        key = app.strip().lower()
        target = APP_ALIASES.get(key, app.strip())

        # If it's a URL or domain, open in default browser.
        if URL_RE.match(target) or DOMAIN_RE.match(target):
            if not URL_RE.match(target):
                target = f"https://{target}"
            return self._open_with_shell(target, label="URL")

        try:
            # Direct executable or path
            if os.path.isabs(target) or target.lower().endswith(".exe"):
                subprocess.Popen([target], shell=False)
                return ToolResult(success=True, output=f"Opened {app}", tool_name=self.name)

            # Try Start-Process on the name (Start menu resolution)
            if self._start_menu_launch(target):
                return ToolResult(success=True, output=f"Opened {app}", tool_name=self.name)

            # Try shell open as a fallback
            return self._open_with_shell(target, label="App")
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), tool_name=self.name)

    def _open_with_shell(self, target: str, label: str) -> ToolResult:
        try:
            subprocess.Popen(["cmd", "/c", "start", "", target], shell=False)
            return ToolResult(success=True, output=f"Opened {label}: {target}", tool_name=self.name)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), tool_name=self.name)

    def _start_menu_launch(self, name: str) -> bool:
        # Use PowerShell to find Start Menu apps and launch via AUMID
        ps = (
            "$app = Get-StartApps | Where-Object { $_.Name -like '*{name}*' } | Select-Object -First 1;"
            "if ($app) { Start-Process ('shell:AppsFolder\\' + $app.AppID); exit 0 } else { exit 1 }"
        ).format(name=name.replace("'", "''"))
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True,
            text=True
        )
        return proc.returncode == 0
