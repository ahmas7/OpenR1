"""
R1 v1 - Model Manager
Manages model providers with explicit health checks and failover.
"""
import logging
from typing import List, Optional
from dataclasses import dataclass

from .providers.base import BaseProvider, Message, ModelResponse
from .providers.ollama import OllamaProvider
from .providers.gguf import GGUFProvider
from .providers.airllm import AirLLMProvider
from .providers.local_provider import LocalProvider
from .providers.local_stub import LocalStubProvider
from ..config.settings import settings

logger = logging.getLogger("R1")


@dataclass
class ProviderInfo:
    id: str
    name: str
    healthy: bool
    reason: Optional[str] = None


class ModelManager:
    def __init__(self):
        self._provider: Optional[BaseProvider] = None
        self._provider_name: str = ""
        self._initialized: bool = False

    async def initialize(self):
        if self._initialized:
            return

        logger.info("Initializing ModelManager...")

        requested = settings.provider.lower()

        # Try the requested provider first
        if requested == "gguf":
            if settings.gguf_model_path:
                try:
                    provider = GGUFProvider(settings.gguf_model_path)
                    health = await provider.health()
                    if health.get("healthy"):
                        self._provider = provider
                        self._provider_name = "gguf"
                        logger.info(f"✓ GGUF provider initialized: {provider.name}")
                        self._initialized = True
                        return
                    else:
                        logger.warning(f"GGUF not healthy: {health.get('reason')}")
                except Exception as e:
                    logger.warning(f"GGUF initialization failed: {e}")
            else:
                logger.warning("GGUF requested but GGUF_MODEL_PATH not set")

        if requested == "ollama":
            try:
                provider = OllamaProvider(settings.model, settings.ollama_endpoint)
                health = await provider.health()
                if health.get("healthy"):
                    self._provider = provider
                    self._provider_name = "ollama"
                    logger.info(f"✓ Ollama provider initialized: {provider.name}")
                    self._initialized = True
                    return
                else:
                    logger.warning(f"Ollama not healthy: {health.get('reason')}")
            except Exception as e:
                logger.warning(f"Ollama initialization failed: {e}")

        if requested == "airllm":
            if settings.airllm_model_path:
                try:
                    provider = AirLLMProvider(
                        model_path=settings.airllm_model_path,
                        compression=settings.airllm_compression,
                        layer_shards_path=settings.airllm_layer_shards_path,
                        hf_token=settings.airllm_hf_token,
                        max_length=settings.airllm_max_length,
                    )
                    health = await provider.health()
                    if health.get("healthy"):
                        self._provider = provider
                        self._provider_name = "airllm"
                        logger.info(f"✓ AirLLM provider initialized: {provider.name}")
                        self._initialized = True
                        return
                    else:
                        logger.warning(f"AirLLM not healthy: {health.get('reason')}")
                except Exception as e:
                    logger.warning(f"AirLLM initialization failed: {e}")
            else:
                logger.warning("AirLLM requested but AIRLLM_MODEL_PATH not set")

        # Local fallback provider - always available, no external deps
        logger.info("Falling back to local provider (no external model needed)")
        self._provider = LocalProvider()
        self._provider_name = "local"
        logger.info("✓ Local fallback provider initialized")
        self._initialized = True
        return

    def active_provider(self) -> str:
        return self._provider_name

    async def health(self) -> dict:
        if not self._provider:
            return {"healthy": False, "reason": "Not initialized"}
        return await self._provider.health()

    async def chat(self, messages: List[Message], **kwargs) -> ModelResponse:
        if not self._provider:
            await self.initialize()
        
        if not self._provider:
            raise RuntimeError("No provider available")
        
        return await self._provider.chat(messages, **kwargs)

    async def get_providers_status(self) -> List[ProviderInfo]:
        providers_info = []

        # Check GGUF
        try:
            if settings.gguf_model_path:
                provider = GGUFProvider(settings.gguf_model_path)
                health = await provider.health()
                providers_info.append(ProviderInfo(
                    id="gguf",
                    name=provider.name,
                    healthy=health.get("healthy", False),
                    reason=health.get("reason")
                ))
        except Exception as e:
            providers_info.append(ProviderInfo(id="gguf", name="gguf", healthy=False, reason=str(e)))

        # Check Ollama
        try:
            provider = OllamaProvider(settings.model, settings.ollama_endpoint)
            health = await provider.health()
            providers_info.append(ProviderInfo(
                id="ollama",
                name=provider.name,
                healthy=health.get("healthy", False),
                reason=health.get("reason")
            ))
        except Exception as e:
            providers_info.append(ProviderInfo(id="ollama", name="ollama", healthy=False, reason=str(e)))

        # Check AirLLM
        try:
            if settings.airllm_model_path:
                provider = AirLLMProvider(
                    model_path=settings.airllm_model_path,
                    compression=settings.airllm_compression,
                    layer_shards_path=settings.airllm_layer_shards_path,
                    hf_token=settings.airllm_hf_token,
                )
                health = await provider.health()
                providers_info.append(ProviderInfo(
                    id="airllm",
                    name=provider.name,
                    healthy=health.get("healthy", False),
                    reason=health.get("reason")
                ))
        except Exception as e:
            providers_info.append(ProviderInfo(id="airllm", name="airllm", healthy=False, reason=str(e)))

        # Local provider - always available
        local = LocalProvider()
        local_health = await local.health()
        providers_info.append(ProviderInfo(
            id="local",
            name=local.name,
            healthy=local_health.get("healthy", False),
            reason=local_health.get("reason")
        ))

        return providers_info


_model_manager: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager
