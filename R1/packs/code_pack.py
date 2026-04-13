"""
Code pack — AI-powered code analysis, refactoring, and explanation.
Uses the R1 model manager for all AI operations.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("R1:packs:code")


def capabilities():
    return ["analyze", "refactor", "explain"]


def _get_model():
    from R1.model import get_model_manager, Message
    return get_model_manager(), Message


async def analyze(code: str, language: str = "auto") -> Dict[str, Any]:
    """Analyze code for complexity, issues, and suggestions.

    Args:
        code: Source code to analyze.
        language: Programming language (or 'auto' for detection).

    Returns:
        dict with 'analysis' text and 'success' keys.
    """
    if not code or not code.strip():
        return {"success": False, "error": "Empty code provided"}

    try:
        model_mgr, Message = _get_model()
        lang_hint = f" The code is written in {language}." if language != "auto" else ""
        messages = [
            Message(
                role="system",
                content=f"You are a senior code reviewer.{lang_hint} Analyze the following code and provide:\n"
                        "1. **Complexity**: Estimated complexity and structure quality\n"
                        "2. **Issues**: Bugs, anti-patterns, or security concerns\n"
                        "3. **Suggestions**: Concrete improvements\n"
                        "Be concise and actionable."
            ),
            Message(role="user", content=f"```\n{code}\n```"),
        ]
        response = await model_mgr.chat(messages)
        return {"success": True, "analysis": response.content.strip(), "language": language}
    except Exception as e:
        logger.error(f"Code analyze error: {e}")
        return {"success": False, "error": str(e)}


async def refactor(code: str, instructions: str = "improve readability and maintainability") -> Dict[str, Any]:
    """Refactor code based on instructions.

    Args:
        code: Source code to refactor.
        instructions: What kind of refactoring to apply.

    Returns:
        dict with 'refactored' code and 'explanation' keys.
    """
    if not code or not code.strip():
        return {"success": False, "error": "Empty code provided"}

    try:
        model_mgr, Message = _get_model()
        messages = [
            Message(
                role="system",
                content=f"Refactor the following code to: {instructions}.\n"
                        "Output the refactored code in a fenced code block, then a brief explanation "
                        "of what you changed and why."
            ),
            Message(role="user", content=f"```\n{code}\n```"),
        ]
        response = await model_mgr.chat(messages)
        content = response.content.strip()

        # Try to separate code from explanation
        refactored = content
        explanation = ""
        if "```" in content:
            parts = content.split("```")
            if len(parts) >= 3:
                code_block = parts[1]
                # Remove language identifier from first line if present
                lines = code_block.split("\n", 1)
                if len(lines) > 1 and not lines[0].strip().startswith(("def ", "class ", "import ", "from ", "#")):
                    refactored = lines[1].strip()
                else:
                    refactored = code_block.strip()
                explanation = "```".join(parts[2:]).strip()

        return {"success": True, "refactored": refactored, "explanation": explanation}
    except Exception as e:
        logger.error(f"Code refactor error: {e}")
        return {"success": False, "error": str(e)}


async def explain(code: str) -> Dict[str, Any]:
    """Explain code in plain English.

    Args:
        code: Source code to explain.

    Returns:
        dict with 'explanation' text and 'success' keys.
    """
    if not code or not code.strip():
        return {"success": False, "error": "Empty code provided"}

    try:
        model_mgr, Message = _get_model()
        messages = [
            Message(
                role="system",
                content="Explain what the following code does in plain English. "
                        "Be clear and concise. Assume the reader has basic programming knowledge "
                        "but may not know the specific language or framework."
            ),
            Message(role="user", content=f"```\n{code}\n```"),
        ]
        response = await model_mgr.chat(messages)
        return {"success": True, "explanation": response.content.strip()}
    except Exception as e:
        logger.error(f"Code explain error: {e}")
        return {"success": False, "error": str(e)}
