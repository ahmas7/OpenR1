"""
R1 v1 - GGUF Provider
"""
import httpx
from pathlib import Path
from typing import List
from .base import BaseProvider, Message, ModelResponse


class GGUFProvider(BaseProvider):
    def __init__(self, model_path: str):
        self.model_path = self._resolve_model_path(model_path)
        self._model_name = Path(self.model_path).name if self.model_path else "unknown"

    def _resolve_model_path(self, model_path: str) -> str:
        if not model_path:
            return ""
        
        candidate = Path(model_path).expanduser()
        if candidate.is_file() and candidate.suffix.lower() == ".gguf":
            return str(candidate)
        
        if candidate.is_dir():
            gguf_files = sorted(candidate.glob("*.gguf"), key=lambda p: p.stat().st_size, reverse=True)
            if gguf_files:
                return str(gguf_files[0])
        
        return ""

    @property
    def name(self) -> str:
        return f"gguf:{self._model_name}"

    async def health(self) -> dict:
        try:
            from R1.gguf_engine import get_gguf_engine
            engine = get_gguf_engine()
            status = engine.get_status()
            
            if not status.get("library_loaded"):
                return {"healthy": False, "reason": "llama-cpp-python not loaded"}
            
            if not self.model_path:
                return {"healthy": False, "reason": "No GGUF model configured"}
            
            return {
                "healthy": True,
                "model_loaded": engine.model_loaded,
                "model_path": engine.model_path,
            }
        except Exception as e:
            return {"healthy": False, "reason": str(e)}

    async def chat(self, messages: List[Message], **kwargs) -> ModelResponse:
        if not self.model_path:
            raise RuntimeError("GGUF model path not configured")
        
        from R1.gguf_engine import ChatMessage, get_gguf_engine
        
        engine = get_gguf_engine()
        
        if not engine.model_loaded or engine.model_path != self.model_path:
            result = engine.load_model(self.model_path)
            if not result.get("success"):
                raise RuntimeError(f"Failed to load GGUF model: {result.get('error')}")
        
        gguf_messages = [ChatMessage(role=m.role, content=m.content) for m in messages]
        result = engine.chat(gguf_messages, **kwargs)
        
        if not result.get("success"):
            raise RuntimeError(f"GGUF chat failed: {result.get('error')}")
        
        return ModelResponse(content=result["response"], model=self.name)
