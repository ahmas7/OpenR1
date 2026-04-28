"""
R1 - Wake Word Service
Always-on listener that triggers voice interaction.
"""
import threading
import time
from typing import Optional

from .voice_system import listen, speak, start_wake_listener, stop_wake_listener, get_status, set_wake_word, set_voice_preference
from ..agent.runtime import get_runtime
from ..config.settings import settings


class WakeWordService:
    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if self._running or not settings.wake_enabled:
            return False

        set_wake_word(settings.wake_word)
        set_voice_preference(settings.voice_gender)

        def on_wake():
            if settings.wake_open_ui:
                try:
                    import subprocess
                    subprocess.Popen(["cmd", "/c", "start", "", "http://localhost:8000"], shell=False)
                except Exception:
                    pass
            name = settings.user_name or ""
            if not name:
                try:
                    from .memory import get_memory_store
                    name = get_memory_store().get_fact("user.name") or ""
                except Exception:
                    name = ""
            speak(f"{name or 'Operator'}, I'm listening.", async_mode=True)
            time.sleep(0.4)
            text = listen(timeout=5)
            if text:
                runtime = get_runtime()
                response = runtime.chat(text)
                if hasattr(response, "__await__"):
                    import asyncio
                    response = asyncio.run(response)
                reply = response.get("response", "")
                if reply:
                    speak(reply, async_mode=True)

        started = start_wake_listener(on_wake)
        self._running = bool(started)
        return self._running

    def stop(self):
        self._running = False
        return stop_wake_listener()

    def status(self):
        data = get_status()
        data["wake_service_running"] = self._running
        data["wake_word"] = settings.wake_word
        data["voice_gender"] = settings.voice_gender
        return data


_wake_service: Optional[WakeWordService] = None


def get_wake_service() -> WakeWordService:
    global _wake_service
    if _wake_service is None:
        _wake_service = WakeWordService()
    return _wake_service
