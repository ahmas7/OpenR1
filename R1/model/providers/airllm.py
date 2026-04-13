"""
R1 v1 - AirLLM Provider
Run 70B+ models on low-VRAM GPUs (4GB+) or CPU via layer sharding.
https://github.com/lyogavin/airllm

Unlike GGUF or Ollama, AirLLM splits the model layer-by-layer and loads
only one layer at a time into GPU/CPU memory during inference.
This means any HuggingFace model can run with minimal memory.
"""
import asyncio
import logging
import os
import threading
from pathlib import Path
from typing import List, Optional

import torch

from .base import BaseProvider, Message, ModelResponse

logger = logging.getLogger("R1")

# Lazy import — airllm is heavy
_airllm = None
_tokenizer = None
_model = None
_model_lock = threading.Lock()


def _get_airllm():
    """Lazily import airllm."""
    global _airllm
    if _airllm is None:
        from airllm import AutoModel
        _airllm = AutoModel
    return _airllm


def _get_model_and_tokenizer(model_path: str, compression: Optional[str] = None,
                             layer_shards_path: Optional[str] = None,
                             hf_token: Optional[str] = None,
                             max_length: int = 4096):
    """
    Initialize the AirLLM model and tokenizer (singleton pattern).

    AirLLM.AutoModel handles:
    - Auto-detecting the model type (Llama, Mistral, Qwen, etc.)
    - Splitting the model into layers saved to disk
    - Loading one layer at a time during inference

    Args:
        model_path: HuggingFace repo ID or local model path
        compression: '4bit' or '8bit' for quantization, or None
        layer_shards_path: Optional custom path to save split layers
        hf_token: HuggingFace token for gated models
        max_length: Maximum context length
    """
    global _model, _tokenizer

    if _model is not None:
        return _model, _tokenizer

    with _model_lock:
        if _model is not None:
            return _model, _tokenizer

        AutoModel = _get_airllm()

        logger.info(f"AirLLM: Loading model '{model_path}' (this may take a while)...")
        logger.info(f"AirLLM: compression={compression}, device={'cuda' if torch.cuda.is_available() else 'cpu'}")

        init_kwargs = {
            "compression": compression if compression in ("4bit", "8bit") else None,
            "layer_shards_saving_path": layer_shards_path,
        }
        if hf_token:
            init_kwargs["hf_token"] = hf_token

        _model = AutoModel.from_pretrained(model_path, **init_kwargs)
        _tokenizer = _model.tokenizer

        logger.info(f"AirLLM: Model loaded successfully: {_model.config.model_type}")
        return _model, _tokenizer


class AirLLMProvider(BaseProvider):
    """
    AirLLM provider — runs any HF model with layer sharding.
    Works on low-VRAM GPUs (4GB+) or CPU.
    """

    def __init__(self, model_path: str, compression: Optional[str] = None,
                 layer_shards_path: Optional[str] = None,
                 hf_token: Optional[str] = None, max_length: int = 4096):
        self.model_path = model_path
        self.compression = compression
        self.layer_shards_path = layer_shards_path
        self.hf_token = hf_token
        self.max_length = max_length
        self._short_name = model_path.split("/")[-1] if "/" in model_path else model_path
        self._initialized = False
        self._init_error: Optional[str] = None

    @property
    def name(self) -> str:
        return f"airllm:{self._short_name}"

    def _ensure_initialized(self):
        """Lazy-init the model on first use."""
        if self._initialized:
            if self._init_error:
                raise RuntimeError(self._init_error)
            return
        try:
            _get_model_and_tokenizer(
                model_path=self.model_path,
                compression=self.compression,
                layer_shards_path=self.layer_shards_path,
                hf_token=self.hf_token,
                max_length=self.max_length,
            )
            self._initialized = True
        except Exception as e:
            self._init_error = str(e)
            raise

    async def health(self) -> dict:
        try:
            self._ensure_initialized()
            return {
                "healthy": True,
                "model": self._short_name,
                "compression": self.compression or "none",
                "device": "cuda" if torch.cuda.is_available() else "cpu",
                "vram_gb": round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 1) if torch.cuda.is_available() else 0,
            }
        except Exception as e:
            return {
                "healthy": False,
                "reason": str(e),
            }

    def _build_prompt(self, messages: List[Message]) -> str:
        """Build a prompt string from the message list."""
        system_msgs = [m.content for m in messages if m.role == "system"]
        user_msgs = [m for m in messages if m.role in ("user", "assistant")]

        if system_msgs:
            parts = [f"System: {' '.join(system_msgs)}\n"]
        else:
            parts = ["System: You are R1 (Orion), an advanced AI assistant.\n"]

        for msg in user_msgs:
            if msg.role == "user":
                parts.append(f"User: {msg.content}\n")
            elif msg.role == "assistant":
                parts.append(f"Assistant: {msg.content}\n")

        parts.append("Assistant: ")
        return "".join(parts)

    async def chat(self, messages: List[Message], **kwargs) -> ModelResponse:
        self._ensure_initialized()

        _, model = _model, _tokenizer = _get_model_and_tokenizer(self.model_path)
        _, tokenizer = _get_model_and_tokenizer(self.model_path)

        prompt = self._build_prompt(messages)
        max_new_tokens = kwargs.get("max_tokens", 2048)
        temperature = kwargs.get("temperature", 0.7)

        # Run inference in thread pool (blocking call)
        def generate():
            input_ids = tokenizer(
                prompt,
                return_tensors="pt",
                return_attention_mask=False,
                truncation=True,
                max_length=self.max_length,
                padding=False,
            )

            if torch.cuda.is_available():
                input_ids = input_ids["input_ids"].cuda()
            else:
                input_ids = input_ids["input_ids"]

            with torch.no_grad():
                output = model.generate(
                    input_ids,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature,
                    use_cache=True,
                    return_dict_in_generate=True,
                )

            # Decode only the generated tokens (skip prompt)
            generated_ids = output.sequences[0][input_ids.shape[1]:]
            return tokenizer.decode(generated_ids, skip_special_tokens=True)

        response_text = await asyncio.to_thread(generate)

        # Extract reasoning if applicable
        final_answer, reasoning = self.extract_reasoning(response_text)
        if self.is_reasoning_model():
            from R1.config.settings import settings
            if settings.include_reasoning and reasoning:
                final_answer = f"[Reasoning]\n{reasoning}\n\n[Answer]\n{final_answer}"

        return ModelResponse(content=final_answer, model=self.name)

    def __repr__(self):
        return f"AirLLMProvider(model={self.model_path!r}, compression={self.compression!r})"
