"""
Docs pack — document parsing, formatting, and summarization.
Reads common document formats and uses the model for AI tasks.
"""
from __future__ import annotations

import csv
import io
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("R1:packs:docs")


def capabilities():
    return ["parse", "format_markdown", "summarize_doc"]


def _get_model():
    from R1.model import get_model_manager, Message
    return get_model_manager(), Message


def parse(file_path: str) -> Dict[str, Any]:
    """Read a file and return structured content.

    Supports: .txt, .md, .csv, .json, .log, .yaml/.yml

    Args:
        file_path: Path to the document file.

    Returns:
        dict with 'content', 'format', 'lines' keys.
    """
    path = Path(file_path)
    if not path.exists():
        return {"success": False, "error": f"File not found: {file_path}"}

    try:
        ext = path.suffix.lower()
        raw = path.read_text(encoding="utf-8", errors="replace")

        if ext == ".csv":
            reader = csv.DictReader(io.StringIO(raw))
            rows = list(reader)
            return {
                "success": True,
                "format": "csv",
                "content": raw[:2000],
                "rows": rows[:50],
                "total_rows": len(rows),
                "columns": reader.fieldnames or [],
            }

        if ext in (".json",):
            import json
            data = json.loads(raw)
            return {
                "success": True,
                "format": "json",
                "content": raw[:2000],
                "parsed": data if isinstance(data, (dict, list)) else {"value": data},
            }

        if ext in (".yaml", ".yml"):
            # Try to parse YAML but don't require pyyaml
            try:
                import yaml
                data = yaml.safe_load(raw)
                return {
                    "success": True,
                    "format": "yaml",
                    "content": raw[:2000],
                    "parsed": data,
                }
            except ImportError:
                pass

        # Default: text-like formats (.txt, .md, .log, etc.)
        lines = raw.splitlines()
        return {
            "success": True,
            "format": ext.lstrip(".") or "text",
            "content": raw[:5000],
            "lines": len(lines),
            "size_bytes": path.stat().st_size,
        }

    except Exception as e:
        logger.error(f"Parse error: {e}")
        return {"success": False, "error": str(e)}


async def format_markdown(text: str) -> Dict[str, Any]:
    """Convert unstructured text to clean Markdown.

    Args:
        text: Raw text to format.

    Returns:
        dict with 'markdown' and 'success' keys.
    """
    if not text or not text.strip():
        return {"success": False, "error": "Empty text provided"}

    try:
        model_mgr, Message = _get_model()
        messages = [
            Message(
                role="system",
                content="Convert the following text into well-structured Markdown. "
                        "Use headings, bullet points, and code blocks as appropriate. "
                        "Output ONLY the formatted Markdown."
            ),
            Message(role="user", content=text),
        ]
        response = await model_mgr.chat(messages)
        return {"success": True, "markdown": response.content.strip()}
    except Exception as e:
        logger.error(f"Format markdown error: {e}")
        return {"success": False, "error": str(e)}


async def summarize_doc(file_path: str, max_length: int = 300) -> Dict[str, Any]:
    """Read a document file and summarize its contents.

    Args:
        file_path: Path to the document.
        max_length: Approx max word count for the summary.

    Returns:
        dict with 'summary', 'file', and 'success' keys.
    """
    parsed = parse(file_path)
    if not parsed.get("success"):
        return parsed

    content = parsed.get("content", "")
    if not content:
        return {"success": False, "error": "Could not read file content"}

    try:
        model_mgr, Message = _get_model()
        messages = [
            Message(
                role="system",
                content=f"Summarize the following document in at most {max_length} words. "
                        "Include the document's purpose, key points, and any important details. "
                        "Output ONLY the summary."
            ),
            Message(role="user", content=content[:4000]),
        ]
        response = await model_mgr.chat(messages)
        return {
            "success": True,
            "summary": response.content.strip(),
            "file": file_path,
            "format": parsed.get("format", "unknown"),
        }
    except Exception as e:
        logger.error(f"Summarize doc error: {e}")
        return {"success": False, "error": str(e)}
