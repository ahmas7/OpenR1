"""
ORION-R1 App Control Layer
Keyboard/mouse automation, window management, app integration
"""
import asyncio
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import pyautogui
import pyperclip

pyautogui.FAILSAFE = True

DATA_DIR = Path.home() / ".r1" / "app_control"
DATA_DIR.mkdir(parents=True, exist_ok=True)

class AppController:
    def __init__(self):
        self.action_log = DATA_DIR / "actions.json"
        self._load_log()

    def _load_log(self):
        if self.action_log.exists():
            try:
                self.log = json.loads(self.action_log.read_text())
            except:
                self.log = []
        else:
            self.log = []

    def _save_log(self):
        if len(self.log) > 500:
            self.log = self.log[-500:]
        self.action_log.write_text(json.dumps(self.log, indent=2, default=str))

    def _log_action(self, action: str, details: Dict):
        self.log.append({
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details
        })
        self._save_log()

    # === MOUSE CONTROL ===

    def move_mouse(self, x: int, y: int, duration: float = 0.5) -> Dict:
        """Move mouse to coordinates"""
        pyautogui.moveTo(x, y, duration=duration)
        self._log_action("move_mouse", {"x": x, "y": y})
        return {"success": True, "position": {"x": x, "y": y}}

    def click(self, button: str = "left", clicks: int = 1, interval: float = 0.1) -> Dict:
        """Click mouse button"""
        pyautogui.click(button=button, clicks=clicks, interval=interval)
        self._log_action("click", {"button": button, "clicks": clicks})
        return {"success": True}

    def double_click(self) -> Dict:
        """Double click"""
        pyautogui.doubleClick()
        self._log_action("double_click", {})
        return {"success": True}

    def right_click(self) -> Dict:
        """Right click"""
        pyautogui.rightClick()
        self._log_action("right_click", {})
        return {"success": True}

    def scroll(self, amount: int) -> Dict:
        """Scroll mouse wheel"""
        pyautogui.scroll(amount)
        self._log_action("scroll", {"amount": amount})
        return {"success": True}

    def get_mouse_position(self) -> Dict:
        """Get current mouse position"""
        pos = pyautogui.position()
        return {"x": pos.x, "y": pos.y}

    def drag(self, x: int, y: int, duration: float = 0.5) -> Dict:
        """Drag mouse to coordinates"""
        pyautogui.dragTo(x, y, duration=duration)
        self._log_action("drag", {"x": x, "y": y})
        return {"success": True}

    # === KEYBOARD CONTROL ===

    def press_key(self, key: str, presses: int = 1, interval: float = 0.1) -> Dict:
        """Press a key"""
        pyautogui.press(key, presses=presses, interval=interval)
        self._log_action("press_key", {"key": key})
        return {"success": True}

    def hotkey(self, *keys: str) -> Dict:
        """Press hotkey combination"""
        pyautogui.hotkey(*keys)
        self._log_action("hotkey", {"keys": keys})
        return {"success": True}

    def type_text(self, text: str, interval: float = 0.05) -> Dict:
        """Type text"""
        pyautogui.write(text, interval=interval)
        self._log_action("type_text", {"text": text[:50] + "..." if len(text) > 50 else text})
        return {"success": True}

    def paste_text(self, text: str) -> Dict:
        """Paste text from clipboard"""
        pyperclip.copy(text)
        pyautogui.hotkey('ctrl', 'v')
        self._log_action("paste_text", {"text_length": len(text)})
        return {"success": True}

    def copy_text(self) -> Dict:
        """Copy selected text to clipboard"""
        pyautogui.hotkey('ctrl', 'c')
        self._log_action("copy_text", {})
        return {"success": True, "clipboard": pyperclip.paste()}

    # === WINDOW MANAGEMENT ===

    def open_app(self, app_name: str) -> Dict:
        """Open an application"""
        try:
            subprocess.Popen(app_name, shell=True)
            self._log_action("open_app", {"app": app_name})
            return {"success": True, "app": app_name}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def close_window(self, title_contains: str = None) -> Dict:
        """Close active or matching window"""
        try:
            if title_contains:
                import win32gui
                def callback(hwnd, windows):
                    if win32gui.IsWindowVisible(hwnd):
                        title = win32gui.GetWindowText(hwnd)
                        if title_contains.lower() in title.lower():
                            windows.append(hwnd)
                windows = []
                win32gui.EnumWindows(callback, windows)
                for hwnd in windows:
                    win32gui.PostMessage(hwnd, 0x0010, 0, 0)  # WM_CLOSE
            else:
                pyautogui.hotkey('alt', 'f4')
            self._log_action("close_window", {"title_contains": title_contains})
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def minimize_window(self) -> Dict:
        """Minimize active window"""
        pyautogui.hotkey('win', 'down')
        self._log_action("minimize_window", {})
        return {"success": True}

    def maximize_window(self) -> Dict:
        """Maximize active window"""
        pyautogui.hotkey('win', 'up')
        self._log_action("maximize_window", {})
        return {"success": True}

    def switch_window(self, title_contains: str) -> Dict:
        """Switch to window by title"""
        try:
            import win32gui
            def callback(hwnd, windows):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if title_contains.lower() in title.lower():
                        windows.append(hwnd)
            windows = []
            win32gui.EnumWindows(callback, windows)
            if windows:
                win32gui.SetForegroundWindow(windows[0])
                self._log_action("switch_window", {"title_contains": title_contains})
                return {"success": True}
            return {"success": False, "error": "Window not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_active_window(self) -> Dict:
        """Get active window info"""
        try:
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            return {"success": True, "title": title, "hwnd": hwnd}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_windows(self) -> Dict:
        """List all visible windows"""
        try:
            import win32gui
            windows = []
            def callback(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if title:
                        windows.append({"title": title, "hwnd": hwnd})
            win32gui.EnumWindows(callback, None)
            return {"success": True, "windows": windows}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # === SCREENSHOT ===

    def screenshot(self, save_path: str = None) -> Dict:
        """Take screenshot"""
        try:
            screenshot = pyautogui.screenshot()
            if save_path:
                screenshot.save(save_path)
                self._log_action("screenshot", {"saved_to": save_path})
                return {"success": True, "saved_to": save_path}
            self._log_action("screenshot", {})
            return {"success": True, "size": screenshot.size}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_screen_size(self) -> Dict:
        """Get screen dimensions"""
        size = pyautogui.size()
        return {"width": size.width, "height": size.height}

    # === PRESET ACTIONS ===

    def select_all(self) -> Dict:
        """Select all (Ctrl+A)"""
        return self.hotkey('ctrl', 'a')

    def undo(self) -> Dict:
        """Undo (Ctrl+Z)"""
        return self.hotkey('ctrl', 'z')

    def redo(self) -> Dict:
        """Redo (Ctrl+Y)"""
        return self.hotkey('ctrl', 'y')

    def save(self) -> Dict:
        """Save (Ctrl+S)"""
        return self.hotkey('ctrl', 's')

    def new_tab(self) -> Dict:
        """New tab (Ctrl+T)"""
        return self.hotkey('ctrl', 't')

    def close_tab(self) -> Dict:
        """Close tab (Ctrl+W)"""
        return self.hotkey('ctrl', 'w')

    def find(self) -> Dict:
        """Find (Ctrl+F)"""
        return self.hotkey('ctrl', 'f')

    def get_action_history(self, limit: int = 20) -> List[Dict]:
        return self.log[-limit:]


# Singleton
_controller = None

def get_app_controller() -> AppController:
    global _controller
    if _controller is None:
        _controller = AppController()
    return _controller
