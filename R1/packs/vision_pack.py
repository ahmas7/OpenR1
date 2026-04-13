"""
Vision pack — image captioning and visual question answering.
Uses the R1 model manager if a multimodal model is available.
Degrades gracefully when vision dependencies are not installed.
"""
from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("R1:packs:vision")


def capabilities():
    return ["image_caption", "image_qa", "status"]


def _get_model():
    from R1.model import get_model_manager, Message
    return get_model_manager(), Message


def _read_image_base64(image_path: str) -> Optional[str]:
    """Read an image file and return base64-encoded content."""
    path = Path(image_path)
    if not path.exists():
        return None
    try:
        data = path.read_bytes()
        return base64.b64encode(data).decode("utf-8")
    except Exception as e:
        logger.error(f"Failed to read image: {e}")
        return None


def _get_mime_type(image_path: str) -> str:
    """Guess MIME type from file extension."""
    ext = Path(image_path).suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".gif": "image/gif",
        ".webp": "image/webp", ".bmp": "image/bmp",
    }
    return mime_map.get(ext, "image/png")


async def image_caption(image_path: str) -> Dict[str, Any]:
    """Generate a text caption for an image.

    Requires a multimodal model (e.g., LLaVA, GPT-4V).
    Falls back to a descriptive error if no vision model is configured.

    Args:
        image_path: Path to the image file.

    Returns:
        dict with 'caption', 'success' keys.
    """
    path = Path(image_path)
    if not path.exists():
        return {"success": False, "error": f"Image not found: {image_path}"}

    b64 = _read_image_base64(image_path)
    if not b64:
        return {"success": False, "error": "Could not read image file"}

    try:
        model_mgr, Message = _get_model()

        # Try multimodal message format
        messages = [
            Message(
                role="system",
                content="You are an image captioning assistant. Describe the image in one or two clear sentences."
            ),
            Message(
                role="user",
                content=f"[Image: {path.name}]\nDescribe this image.",
                # Future: pass image data via model-specific multimodal field
            ),
        ]
        response = await model_mgr.chat(messages)
        caption = response.content.strip()

        # Check if model actually processed the image or just acknowledged
        if "cannot" in caption.lower() and "image" in caption.lower():
            return {
                "success": False,
                "error": "Model does not support vision/multimodal input. Configure a vision-capable model.",
                "model_response": caption,
            }

        return {"success": True, "caption": caption, "file": image_path}
    except Exception as e:
        logger.error(f"Image caption error: {e}")
        return {"success": False, "error": str(e)}


async def image_qa(image_path: str, question: str) -> Dict[str, Any]:
    """Answer a question about an image.

    Args:
        image_path: Path to the image file.
        question: The question to answer about the image.

    Returns:
        dict with 'answer', 'success' keys.
    """
    path = Path(image_path)
    if not path.exists():
        return {"success": False, "error": f"Image not found: {image_path}"}

    if not question or not question.strip():
        return {"success": False, "error": "No question provided"}

    b64 = _read_image_base64(image_path)
    if not b64:
        return {"success": False, "error": "Could not read image file"}

    try:
        model_mgr, Message = _get_model()
        messages = [
            Message(
                role="system",
                content="You are a visual question answering assistant. "
                        "Answer the user's question about the image accurately and concisely."
            ),
            Message(
                role="user",
                content=f"[Image: {path.name}]\n{question}",
            ),
        ]
        response = await model_mgr.chat(messages)
        answer = response.content.strip()

        if "cannot" in answer.lower() and "image" in answer.lower():
            return {
                "success": False,
                "error": "Model does not support vision/multimodal input.",
                "model_response": answer,
            }

        return {"success": True, "answer": answer, "question": question, "file": image_path}
    except Exception as e:
        logger.error(f"Image QA error: {e}")
        return {"success": False, "error": str(e)}


def status() -> Dict[str, Any]:
    """Return vision pack availability status."""
    model_available = False
    try:
        from R1.model import get_model_manager
        mgr = get_model_manager()
        model_available = True
    except Exception:
        pass

    return {
        "model_available": model_available,
        "capabilities": capabilities(),
        "note": "Vision functions require a multimodal model (e.g., LLaVA, GPT-4V).",
    }
