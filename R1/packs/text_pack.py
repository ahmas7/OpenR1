"""
Text pack — lightweight text analysis and manipulation helpers.
Uses the R1 model manager for AI-powered operations.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("R1:packs:text")


def capabilities():
    return ["summarize", "rewrite", "extract"]


def _get_model():
    """Lazy-load the model manager."""
    from R1.model import get_model_manager, Message
    return get_model_manager(), Message


async def summarize(text: str, max_length: int = 200) -> Dict[str, Any]:
    """Summarize text using the AI model.

    Args:
        text: The text to summarize.
        max_length: Approximate max word count for the summary.

    Returns:
        dict with 'summary' and 'success' keys.
    """
    if not text or not text.strip():
        return {"success": False, "error": "Empty text provided"}

    try:
        model_mgr, Message = _get_model()
        messages = [
            Message(
                role="system",
                content=f"You are a concise summarizer. Summarize the following text in at most {max_length} words. "
                        "Output ONLY the summary, no preamble."
            ),
            Message(role="user", content=text),
        ]
        response = await model_mgr.chat(messages)
        return {"success": True, "summary": response.content.strip()}
    except Exception as e:
        logger.error(f"Summarize error: {e}")
        return {"success": False, "error": str(e)}


async def rewrite(text: str, style: str = "professional") -> Dict[str, Any]:
    """Rewrite text in a given style.

    Args:
        text: The text to rewrite.
        style: The target style (e.g., professional, casual, formal, concise, creative).

    Returns:
        dict with 'rewritten' and 'success' keys.
    """
    if not text or not text.strip():
        return {"success": False, "error": "Empty text provided"}

    try:
        model_mgr, Message = _get_model()
        messages = [
            Message(
                role="system",
                content=f"Rewrite the following text in a {style} style. "
                        "Output ONLY the rewritten text, no explanations."
            ),
            Message(role="user", content=text),
        ]
        response = await model_mgr.chat(messages)
        return {"success": True, "rewritten": response.content.strip()}
    except Exception as e:
        logger.error(f"Rewrite error: {e}")
        return {"success": False, "error": str(e)}


async def extract(text: str, pattern: str = "key facts") -> Dict[str, Any]:
    """Extract structured data from text.

    Args:
        text: The text to extract from.
        pattern: What to extract (e.g., "key facts", "dates", "names", "emails").

    Returns:
        dict with 'extracted' list and 'success' keys.
    """
    if not text or not text.strip():
        return {"success": False, "error": "Empty text provided"}

    try:
        model_mgr, Message = _get_model()
        messages = [
            Message(
                role="system",
                content=f"Extract {pattern} from the following text. "
                        "Return each item on its own line, prefixed with '- '. "
                        "Output ONLY the extracted items."
            ),
            Message(role="user", content=text),
        ]
        response = await model_mgr.chat(messages)
        items = [
            line.lstrip("- ").strip()
            for line in response.content.strip().splitlines()
            if line.strip()
        ]
        return {"success": True, "extracted": items}
    except Exception as e:
        logger.error(f"Extract error: {e}")
        return {"success": False, "error": str(e)}
