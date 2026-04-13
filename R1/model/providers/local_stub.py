"""
R1 v1 - Local Stub Provider
WARNING: This provider is for development only. It provides fake AI responses.
"""
from typing import List
from .base import BaseProvider, Message, ModelResponse


class LocalStubProvider(BaseProvider):
    """Stub provider that returns fake responses. Use only in dev mode."""
    
    @property
    def name(self) -> str:
        return "stub:dev-only"

    async def health(self) -> dict:
        return {
            "healthy": True,
            "warning": "This is a stub provider - not for production use"
        }

    async def chat(self, messages: List[Message], **kwargs) -> ModelResponse:
        user_msg = next((m.content for m in messages if m.role == "user"), "")
        return ModelResponse(
            content=f"[STUB] Processed: {user_msg[:50]}... (Configure a real provider for actual AI responses)",
            model=self.name
        )
