"""
R1 v1 - Base Provider Interface
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
import re


@dataclass
class Message:
    role: str
    content: str


@dataclass
class ModelResponse:
    content: str
    model: str


class BaseProvider(ABC):
    """Base class for all model providers."""

    # Reasoning model identifiers (models that output <think> tags)
    REASONING_MODELS = [
        "deepseek-r1",
        "deepseek-reasoner",
        "qwq",  # Qwen QwQ reasoning model
        "o1",   # OpenAI o1
        "o3",   # OpenAI o3
    ]

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    async def chat(self, messages: List[Message], **kwargs) -> ModelResponse:
        pass

    @abstractmethod
    async def health(self) -> dict:
        pass

    def is_reasoning_model(self) -> bool:
        """Check if this is a reasoning model that outputs <think> tags."""
        model_name = self.name.lower()
        return any(r in model_name for r in self.REASONING_MODELS)

    def extract_reasoning(self, content: str) -> tuple[str, Optional[str]]:
        """
        Extract reasoning chain and final answer from model output.

        Reasoning models like DeepSeek-R1 wrap their thinking in <think>...</think> tags.
        This extracts both the reasoning chain and the final answer.

        Returns:
            Tuple of (final_answer, reasoning_chain or None)
        """
        # Match <think>...</think> tags (multiline, non-greedy)
        think_pattern = r'<think>(.*?)</think>'
        think_match = re.search(think_pattern, content, re.DOTALL)

        if think_match:
            reasoning = think_match.group(1).strip()
            # Remove <think> block from content to get final answer
            final_answer = re.sub(think_pattern, '', content, flags=re.DOTALL).strip()
            return final_answer, reasoning

        # No reasoning tags found - return content as-is
        return content.strip(), None

    def process_response(self, content: str, include_reasoning: bool = False) -> str:
        """
        Process model response, optionally including reasoning chain.

        Args:
            content: Raw model output
            include_reasoning: If True, prepend reasoning to final answer

        Returns:
            Processed response string
        """
        final_answer, reasoning = self.extract_reasoning(content)

        if include_reasoning and reasoning:
            return f"[Reasoning]\n{reasoning}\n\n[Answer]\n{final_answer}"

        return final_answer
