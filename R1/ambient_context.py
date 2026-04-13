"""
R1 - Ambient context aggregation
Unifies system awareness, active app state, screenshot OCR, wake/voice state,
and coarse location hints into one runtime-friendly context snapshot.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("R1:ambient")

DATA_DIR = Path.home() / ".r1" / "ambient"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class AmbientContextService:
    def __init__(self):
        self.snapshot_file = DATA_DIR / "latest_snapshot.json"
        self.history_file = DATA_DIR / "history.json"
        self.history = self._load_history()

    def _load_history(self) -> list[Dict[str, Any]]:
        if self.history_file.exists():
            try:
                return json.loads(self.history_file.read_text(encoding="utf-8"))
            except Exception:
                return []
        return []

    def _save_snapshot(self, snapshot: Dict[str, Any]) -> None:
        self.snapshot_file.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
        self.history.append(snapshot)
        if len(self.history) > 200:
            self.history = self.history[-200:]
        self.history_file.write_text(json.dumps(self.history, indent=2), encoding="utf-8")

    def get_location_context(self, memory_store=None) -> Dict[str, Any]:
        location = None
        if memory_store:
            location = (
                memory_store.get_fact("user.location")
                or memory_store.get_fact("location")
                or memory_store.get_fact("workspace.location")
            )
        return {
            "source": "memory_fact" if location else "unavailable",
            "value": location,
        }

    def capture_screen_context(self) -> Dict[str, Any]:
        try:
            from .app_control import get_app_controller

            controller = get_app_controller()
            screenshot_path = DATA_DIR / "ambient_screen.png"
            shot = controller.screenshot(str(screenshot_path))
            result: Dict[str, Any] = {
                "available": bool(shot.get("success")),
                "path": str(screenshot_path) if shot.get("success") else None,
            }

            if not shot.get("success"):
                result["error"] = shot.get("error", "Screenshot unavailable")
                return result

            try:
                from PIL import Image
                import pytesseract

                text = pytesseract.image_to_string(Image.open(screenshot_path)).strip()
                if text:
                    result["ocr_text"] = text[:2000]
            except Exception as e:
                result["ocr_error"] = str(e)

            return result
        except Exception as e:
            return {"available": False, "error": str(e)}

    def get_voice_context(self) -> Dict[str, Any]:
        try:
            from .wake_word import get_wake_service

            return get_wake_service().status()
        except Exception as e:
            return {"available": False, "error": str(e)}

    def get_status_snapshot(self, memory_store=None, include_screen: bool = False) -> Dict[str, Any]:
        snapshot: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "system": {},
            "voice": self.get_voice_context(),
            "location": self.get_location_context(memory_store),
        }

        try:
            from .system_awareness import get_system_awareness

            snapshot["system"] = get_system_awareness().get_full_status()
        except Exception as e:
            snapshot["system"] = {"error": str(e)}

        if include_screen:
            snapshot["screen"] = self.capture_screen_context()

        self._save_snapshot(snapshot)
        return snapshot

    def get_latest_snapshot(self) -> Optional[Dict[str, Any]]:
        if self.snapshot_file.exists():
            try:
                return json.loads(self.snapshot_file.read_text(encoding="utf-8"))
            except Exception:
                return None
        return None

    def get_context_summary(self, memory_store=None, include_screen: bool = False) -> str:
        snapshot = self.get_status_snapshot(memory_store=memory_store, include_screen=include_screen)

        system = snapshot.get("system", {})
        lines = ["Ambient context:"]

        active_window = system.get("active_window") if isinstance(system, dict) else None
        if active_window:
            title = active_window.get("title") or "unknown"
            process = active_window.get("process") or "unknown"
            lines.append(f"- Active window: {title} ({process})")

        cpu = system.get("cpu", {}) if isinstance(system, dict) else {}
        mem = system.get("memory", {}) if isinstance(system, dict) else {}
        if cpu or mem:
            lines.append(
                f"- System load: CPU {cpu.get('percent', '?')}%, RAM {mem.get('percent', '?')}%"
            )

        location = snapshot.get("location", {})
        if location.get("value"):
            lines.append(f"- Known location: {location['value']}")

        screen = snapshot.get("screen", {})
        if screen.get("ocr_text"):
            preview = screen["ocr_text"][:300].replace("\n", " ")
            lines.append(f"- Screen OCR: {preview}")

        voice = snapshot.get("voice", {})
        if voice:
            wake_word = voice.get("wake_word")
            wake_listening = voice.get("wake_listening")
            if wake_word is not None:
                lines.append(f"- Voice wake word: {wake_word} (listening={wake_listening})")

        return "\n".join(lines)


_ambient_service: Optional[AmbientContextService] = None


def get_ambient_context_service() -> AmbientContextService:
    global _ambient_service
    if _ambient_service is None:
        _ambient_service = AmbientContextService()
    return _ambient_service
