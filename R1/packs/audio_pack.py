"""
Audio pack — text-to-speech and speech-to-text wrappers.
Wraps existing R1 voice subsystems. Degrades gracefully when
audio dependencies are not installed.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("R1:packs:audio")


def capabilities():
    return ["text_to_speech", "speech_to_text"]


def _check_tts_available() -> bool:
    """Check if TTS subsystem is available."""
    try:
        from R1 import voice_system
        return True
    except ImportError:
        return False


def _check_stt_available() -> bool:
    """Check if speech recognition is available."""
    try:
        from R1 import voice_system
        return True
    except ImportError:
        return False


def text_to_speech(text: str, async_mode: bool = True) -> Dict[str, Any]:
    """Convert text to speech using the R1 voice system.

    Args:
        text: The text to speak.
        async_mode: If True, return immediately while audio plays in background.

    Returns:
        dict with 'success' and optional 'error' keys.
    """
    if not text or not text.strip():
        return {"success": False, "error": "Empty text provided"}

    if not _check_tts_available():
        return {
            "success": False,
            "error": "TTS not available. Install audio dependencies (e.g., pyttsx3 or gTTS).",
        }

    try:
        from R1 import voice_system
        result = voice_system.speak(text, async_mode=async_mode)
        return {"success": bool(result), "text": text[:100]}
    except Exception as e:
        logger.error(f"TTS error: {e}")
        return {"success": False, "error": str(e)}


def speech_to_text(timeout: int = 5) -> Dict[str, Any]:
    """Listen to the microphone and transcribe speech.

    Args:
        timeout: Max seconds to listen for.

    Returns:
        dict with 'text', 'success' keys.
    """
    if not _check_stt_available():
        return {
            "success": False,
            "error": "STT not available. Install audio dependencies (e.g., SpeechRecognition, pyaudio).",
        }

    try:
        from R1 import voice_system
        text = voice_system.listen(timeout=timeout)
        if text:
            return {"success": True, "text": text}
        return {"success": False, "error": "No speech detected within timeout."}
    except Exception as e:
        logger.error(f"STT error: {e}")
        return {"success": False, "error": str(e)}


def status() -> Dict[str, Any]:
    """Return the availability status of audio capabilities."""
    return {
        "tts_available": _check_tts_available(),
        "stt_available": _check_stt_available(),
        "capabilities": capabilities(),
    }
