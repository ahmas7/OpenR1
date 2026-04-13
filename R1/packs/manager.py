"""
R1 v1 - Pack Manager
Lazy-load optional capability packs with unified invocation.
"""
from __future__ import annotations

import asyncio
import inspect
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger("R1:packs")


@dataclass
class PackInfo:
    name: str
    description: str
    available: bool


class PackManager:
    def __init__(self):
        self._packs: Dict[str, PackInfo] = {
            "text-pack": PackInfo("text-pack", "Text analysis and summarization helpers.", True),
            "code-pack": PackInfo("code-pack", "Code analysis and refactoring helpers.", True),
            "docs-pack": PackInfo("docs-pack", "Document parsing and formatting helpers.", True),
            "audio-pack": PackInfo("audio-pack", "Speech and audio helpers (optional deps).", True),
            "vision-pack": PackInfo("vision-pack", "Image and vision helpers (optional deps).", True),
        }
        self._loaded: Dict[str, object] = {}

    def list_packs(self) -> List[PackInfo]:
        return list(self._packs.values())

    def is_loaded(self, name: str) -> bool:
        return name in self._loaded

    def load(self, name: str) -> Optional[object]:
        if name in self._loaded:
            return self._loaded[name]
        if name not in self._packs:
            return None

        module_name = name.replace("-", "_")
        try:
            module = __import__(f"R1.packs.{module_name}", fromlist=["*"])
            self._loaded[name] = module
            logger.info(f"Loaded pack: {name}")
            return module
        except Exception as e:
            logger.error(f"Failed to load pack '{name}': {e}")
            return None

    def unload(self, name: str) -> bool:
        if name in self._loaded:
            del self._loaded[name]
            logger.info(f"Unloaded pack: {name}")
            return True
        return False

    def get_capabilities(self, name: str) -> List[str]:
        """Get available functions for a pack.

        Args:
            name: Pack name (e.g., 'text-pack').

        Returns:
            List of function names, or empty list if pack not found.
        """
        module = self.load(name)
        if not module:
            return []

        if hasattr(module, "capabilities") and callable(module.capabilities):
            return module.capabilities()

        # Fallback: discover public async/sync functions
        return [
            attr for attr in dir(module)
            if not attr.startswith("_")
            and callable(getattr(module, attr, None))
            and attr != "capabilities"
        ]

    async def run(self, pack_name: str, function_name: str, **kwargs) -> Dict[str, Any]:
        """Invoke a function from a pack.

        Args:
            pack_name: Pack name (e.g., 'text-pack').
            function_name: Function to call within the pack.
            **kwargs: Arguments to pass to the function.

        Returns:
            dict with function result or error.
        """
        module = self.load(pack_name)
        if not module:
            return {"success": False, "error": f"Pack '{pack_name}' not found or failed to load."}

        func = getattr(module, function_name, None)
        if not func or not callable(func):
            return {
                "success": False,
                "error": f"Function '{function_name}' not found in pack '{pack_name}'. "
                         f"Available: {self.get_capabilities(pack_name)}"
            }

        try:
            if inspect.iscoroutinefunction(func):
                result = await func(**kwargs)
            else:
                result = func(**kwargs)

            # Normalize result
            if isinstance(result, dict):
                return result
            return {"success": True, "result": result}
        except TypeError as e:
            return {"success": False, "error": f"Invalid arguments for '{function_name}': {e}"}
        except Exception as e:
            logger.error(f"Pack run error ({pack_name}.{function_name}): {e}")
            return {"success": False, "error": str(e)}

    def summary(self) -> Dict[str, Any]:
        """Return a summary of all packs and their status."""
        result = {}
        for name, info in self._packs.items():
            loaded = name in self._loaded
            caps = self.get_capabilities(name) if loaded else []
            result[name] = {
                "description": info.description,
                "available": info.available,
                "loaded": loaded,
                "capabilities": caps,
            }
        return result


_pack_manager: Optional[PackManager] = None


def get_pack_manager() -> PackManager:
    global _pack_manager
    if _pack_manager is None:
        _pack_manager = PackManager()
    return _pack_manager
