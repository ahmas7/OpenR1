"""
R1 - AI Providers
Ollama, GGUF, OpenAI, Anthropic, and local fallback.
"""
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


@dataclass
class Message:
    role: str
    content: str


@dataclass
class Response:
    content: str
    model: str


class AIProvider(ABC):
    @abstractmethod
    async def chat(self, messages: List[Message], **kwargs) -> Response:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass


class OllamaProvider(AIProvider):
    def __init__(self, model: str = "llama3.2:3b", endpoint: str = "http://localhost:11434"):
        self.model = model
        self.endpoint = endpoint.rstrip("/")

    @property
    def name(self) -> str:
        return f"ollama:{self.model}"

    async def chat(self, messages: List[Message], **kwargs) -> Response:
        import httpx

        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(f"{self.endpoint}/api/chat", json=payload)
            if response.status_code == 404:
                # Older Ollama servers may expose only /api/generate.
                prompt = "\n".join(f"{m.role}: {m.content}" for m in messages)
                response = await client.post(
                    f"{self.endpoint}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                    },
                )

            response.raise_for_status()
            data = response.json()
            content = data.get("message", {}).get("content") or data.get("response", "")
            if not content:
                raise RuntimeError(f"Ollama returned no content for model '{self.model}'")
            return Response(content=content, model=self.name)


class GGUFProvider(AIProvider):
    def __init__(self, model: str = "", model_path: Optional[str] = None):
        self.requested_model = model_path or model or os.getenv("GGUF_MODEL_PATH", "")

    def _resolve_model_path(self) -> Optional[str]:
        if not self.requested_model:
            return None

        candidate = Path(self.requested_model).expanduser()
        if candidate.is_file() and candidate.suffix.lower() == ".gguf":
            return str(candidate)

        if candidate.is_dir():
            gguf_files = sorted(
                candidate.glob("*.gguf"),
                key=lambda path: path.stat().st_size,
                reverse=True,
            )
            if gguf_files:
                return str(gguf_files[0])

        return None

    @property
    def name(self) -> str:
        resolved = self._resolve_model_path()
        if resolved:
            return f"gguf:{Path(resolved).name}"
        if self.requested_model:
            return f"gguf:{self.requested_model}"
        return "gguf:unconfigured"

    async def chat(self, messages: List[Message], **kwargs) -> Response:
        from R1.gguf_engine import ChatMessage, get_gguf_engine

        engine = get_gguf_engine()
        resolved_path = self._resolve_model_path()
        if not resolved_path:
            raise RuntimeError(
                f"GGUF model not found. Expected a .gguf file in: {self.requested_model or 'GGUF_MODEL_PATH'}"
            )

        if (not engine.model_loaded) or engine.model_path != resolved_path:
            result = engine.load_model(resolved_path)
            if not result.get("success"):
                raise RuntimeError(result.get("error", "Failed to load GGUF model"))

        gguf_messages = [ChatMessage(role=m.role, content=m.content) for m in messages]
        result = engine.chat(gguf_messages, **kwargs)
        if not result.get("success"):
            raise RuntimeError(result.get("error", "GGUF chat failed"))

        return Response(content=result["response"], model=f"gguf:{result['model']}")


class OpenAIProvider(AIProvider):
    def __init__(self, model: str = "gpt-4o-mini", api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")

    @property
    def name(self) -> str:
        return f"openai:{self.model}"

    async def chat(self, messages: List[Message], **kwargs) -> Response:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY not configured")

        import httpx

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [{"role": m.role, "content": m.content} for m in messages],
                    "temperature": kwargs.get("temperature", 0.4),
                    "max_tokens": kwargs.get("max_tokens", 800),
                },
            )
            response.raise_for_status()
            data = response.json()
            return Response(
                content=data["choices"][0]["message"]["content"],
                model=self.name,
            )


class AnthropicProvider(AIProvider):
    def __init__(self, model: str = "claude-3-5-sonnet-latest", api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")

    @property
    def name(self) -> str:
        return f"anthropic:{self.model}"

    async def chat(self, messages: List[Message], **kwargs) -> Response:
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not configured")

        import httpx

        system_parts = [m.content for m in messages if m.role == "system"]
        user_messages = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role != "system"
        ]

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": self.model,
                    "system": "\n".join(system_parts),
                    "messages": user_messages,
                    "max_tokens": kwargs.get("max_tokens", 800),
                },
            )
            response.raise_for_status()
            data = response.json()
            text_parts = [block.get("text", "") for block in data.get("content", [])]
            return Response(content="".join(text_parts), model=self.name)


class LocalProvider(AIProvider):
    @property
    def name(self) -> str:
        return "local:r1"

    async def chat(self, messages: List[Message], **kwargs) -> Response:
        from R1.local_ai import get_orion_ai

        prompt = next((m.content for m in reversed(messages) if m.role == "user"), "")
        content = get_orion_ai().process(prompt)
        return Response(content=content, model=self.name)


class AIEngine:
    def __init__(self, provider: str = "ollama", **config):
        provider_name = (provider or "ollama").lower()
        self.provider_name = provider_name
        self.provider = self._build_provider(provider_name, config)

    def _build_provider(self, provider_name: str, config: dict) -> AIProvider:
        if provider_name == "gguf":
            return GGUFProvider(
                model=config.get("model", ""),
                model_path=config.get("model_path"),
            )
        if provider_name == "openai":
            return OpenAIProvider(
                model=config.get("model", "gpt-4o-mini"),
                api_key=config.get("api_key"),
            )
        if provider_name == "anthropic":
            return AnthropicProvider(
                model=config.get("model", "claude-3-5-sonnet-latest"),
                api_key=config.get("api_key"),
            )
        if provider_name == "local":
            return LocalProvider()
        return OllamaProvider(
            model=config.get("model", "llama3.2:3b"),
            endpoint=config.get("endpoint", "http://localhost:11434"),
        )

    async def chat(self, messages: List[Message], **kwargs) -> Response:
        return await self.provider.chat(messages, **kwargs)

    @property
    def name(self) -> str:
        return self.provider.name


def get_ai_engine(config: dict = None) -> AIEngine:
    config = config or {}
    return AIEngine(
        provider=config.get("provider", os.getenv("R1_PROVIDER", "ollama")),
        model=config.get("model", os.getenv("R1_MODEL", os.getenv("GGUF_MODEL_PATH", "llama3.2:3b"))),
        model_path=config.get("model_path", os.getenv("GGUF_MODEL_PATH", "")),
        endpoint=config.get("endpoint", os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434")),
        api_key=config.get("api_key"),
    )
