"""
R1 v1 - Ollama Provider
"""
import httpx
from typing import List
from .base import BaseProvider, Message, ModelResponse
from ...config.settings import settings


class OllamaProvider(BaseProvider):
    def __init__(self, model: str = "llama3.2:3b", endpoint: str = "http://localhost:11434"):
        self.model = model
        self.endpoint = endpoint.rstrip("/")

    @property
    def name(self) -> str:
        return f"ollama:{self.model}"

    async def health(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.endpoint}/api/tags")
                if resp.status_code == 200:
                    return {"healthy": True}
                return {"healthy": False, "reason": f"Status {resp.status_code}"}
        except Exception as e:
            return {"healthy": False, "reason": str(e)}

    async def chat(self, messages: List[Message], **kwargs) -> ModelResponse:
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
        }

        timeout = max(5.0, float(settings.model_timeout))
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{self.endpoint}/api/chat", json=payload)
            if response.status_code == 404:
                prompt = "\n".join(f"{m.role}: {m.content}" for m in messages)
                response = await client.post(
                    f"{self.endpoint}/api/generate",
                    json={"model": self.model, "prompt": prompt, "stream": False},
                )

            if response.status_code >= 400:
                raise RuntimeError(f"Ollama error {response.status_code}: {response.text}")
            data = response.json()
            content = data.get("message", {}).get("content") or data.get("response", "")
            if not content:
                raise RuntimeError(f"Ollama returned no content for model '{self.model}'")

            # Process reasoning model output (e.g., DeepSeek-R1 <think> tags)
            include_reasoning = getattr(settings, 'include_reasoning', False)
            processed_content = self.process_response(content, include_reasoning=include_reasoning)

            return ModelResponse(content=processed_content, model=self.name)
