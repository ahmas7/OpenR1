"""
R1 - Multi-Provider LLM Support
Claude, OpenAI, Ollama, Google Gemini
"""
import os
import asyncio
from typing import List, Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class Message:
    role: str
    content: str


@dataclass
class Response:
    content: str
    model: str


class AIProvider:
    async def chat(self, messages: List[Message], **kwargs) -> Response:
        raise NotImplementedError
    
    @property
    def name(self) -> str:
        return "unknown"


class OllamaProvider(AIProvider):
    def __init__(self, model: str = "deepseek-r1:1.5b", endpoint: str = "http://localhost:11434"):
        self.model = model
        self.endpoint = endpoint
    
    @property
    def name(self) -> str:
        return f"ollama:{self.model}"
    
    async def chat(self, messages: List[Message], **kwargs) -> Response:
        import httpx
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            payload = {
                "model": self.model,
                "messages": [{"role": m.role, "content": m.content} for m in messages],
                "stream": False,
            }
            
            response = await client.post(f"{self.endpoint}/api/chat", json=payload)
            data = response.json()
            
            return Response(
                content=data["message"]["content"],
                model=self.name
            )


class OpenAIProvider(AIProvider):
    def __init__(self, model: str = "gpt-4o", api_key: str = None):
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
    
    @property
    def name(self) -> str:
        return f"openai:{self.model}"
    
    async def chat(self, messages: List[Message], **kwargs) -> Response:
        import httpx
        
        if not self.api_key:
            return Response(content="OpenAI API key not configured", model=self.name)
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model,
                "messages": [{"role": m.role, "content": m.content} for m in messages],
                "stream": False,
            }
            
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers=headers
            )
            data = response.json()
            
            return Response(
                content=data["choices"][0]["message"]["content"],
                model=self.name
            )


class ClaudeProvider(AIProvider):
    def __init__(self, model: str = "claude-3-5-sonnet-20241022", api_key: str = None):
        self.model = model
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
    
    @property
    def name(self) -> str:
        return f"claude:{self.model}"
    
    async def chat(self, messages: List[Message], **kwargs) -> Response:
        import httpx
        
        if not self.api_key:
            return Response(content="Anthropic API key not configured", model=self.name)
        
        system_msg = ""
        chat_messages = []
        
        for msg in messages:
            if msg.role == "system":
                system_msg = msg.content
            else:
                chat_messages.append({"role": msg.role, "content": msg.content})
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            headers = {
                "x-api-key": self.api_key,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01"
            }
            
            payload = {
                "model": self.model,
                "max_tokens": 4096,
                "messages": chat_messages
            }
            
            if system_msg:
                payload["system"] = system_msg
            
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                json=payload,
                headers=headers
            )
            data = response.json()
            
            return Response(
                content=data["content"][0]["text"],
                model=self.name
            )


class GeminiProvider(AIProvider):
    def __init__(self, model: str = "gemini-2.0-flash-exp", api_key: str = None):
        self.model = model
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
    
    @property
    def name(self) -> str:
        return f"gemini:{self.model}"
    
    async def chat(self, messages: List[Message], **kwargs) -> Response:
        import httpx
        
        if not self.api_key:
            return Response(content="Google AI API key not configured", model=self.name)
        
        contents = []
        for msg in messages:
            if msg.role != "system":
                contents.append({
                    "role": "user" if msg.role == "user" else "model",
                    "parts": [{"text": msg.content}]
                })
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
            
            payload = {
                "contents": contents,
                "generationConfig": {
                    "temperature": 0.9,
                    "maxOutputTokens": 2048,
                }
            }
            
            response = await client.post(url, json=payload)
            data = response.json()
            
            content = data["candidates"][0]["content"]["parts"][0]["text"]
            
            return Response(content=content, model=self.name)


class AIEngine:
    PROVIDERS = {
        "ollama": OllamaProvider,
        "openai": OpenAIProvider,
        "claude": ClaudeProvider,
        "gemini": GeminiProvider,
    }
    
    def __init__(self, provider: str = "ollama", **config):
        provider_class = self.PROVIDERS.get(provider, OllamaProvider)
        
        if provider == "ollama":
            self.provider = provider_class(
                model=config.get("model", "deepseek-r1:1.5b"),
                endpoint=config.get("endpoint", "http://localhost:11434")
            )
        elif provider == "openai":
            self.provider = provider_class(
                model=config.get("model", "gpt-4o"),
                api_key=config.get("api_key")
            )
        elif provider == "claude":
            self.provider = provider_class(
                model=config.get("model", "claude-3-5-sonnet-20241022"),
                api_key=config.get("api_key")
            )
        elif provider == "gemini":
            self.provider = provider_class(
                model=config.get("model", "gemini-2.0-flash-exp"),
                api_key=config.get("api_key")
            )
        else:
            self.provider = OllamaProvider()
    
    async def chat(self, messages: List[Message], **kwargs) -> Response:
        return await self.provider.chat(messages, **kwargs)
    
    @property
    def name(self) -> str:
        return self.provider.name
    
    def is_available(self) -> bool:
        """Check if provider is available"""
        if isinstance(self.provider, OllamaProvider):
            import httpx
            try:
                import requests
                r = requests.get("http://localhost:11434/api/tags", timeout=2)
                return r.status_code == 200
            except:
                return False
        return True


def get_ai_engine(config: dict = None) -> AIEngine:
    config = config or {}
    return AIEngine(
        provider=config.get("provider", "ollama"),
        model=config.get("model", "deepseek-r1:1.5b"),
        endpoint=config.get("endpoint", "http://localhost:11434"),
        api_key=config.get("api_key")
    )
