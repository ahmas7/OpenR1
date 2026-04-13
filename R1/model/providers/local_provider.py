"""
R1 v1 - Local Provider
Simple fallback that works without Ollama, llama-cpp-python, or any external deps.
Provides basic conversational responses using template-based generation.
"""
import re
import random
from typing import List
from .base import BaseProvider, Message, ModelResponse


# Simple response patterns for when no real model is available
_GREETING_PATTERNS = [
    (r'\b(hi|hello|hey|greetings|good morning|good afternoon|good evening)\b', [
        "Hello! How can I help you today?",
        "Hi there! What can I do for you?",
        "Hey! What's on your mind?",
    ]),
]

_QUESTION_PATTERNS = [
    (r'\b(what can you do|what are you|who are you|capabilities)\b', [
        "I'm R1, a local AI assistant. I can help with questions, coding, writing, analysis, and more. I run entirely on your machine with no cloud dependencies!",
    ]),
    (r'\b(how are you|how do you feel)\b', [
        "I'm running well and ready to help! What do you need?",
    ]),
]

_UNKNOWN_RESPONSES = [
    "I received your message. Currently running in local fallback mode with no external model loaded. To enable full AI capabilities, set up a GGUF model or Ollama.",
    "Message received. I'm in local mode without a language model. You can configure a GGUF model in .env to get full AI responses.",
    "Got it! I'm running in basic mode right now. Set R1_PROVIDER=gguf in .env and ensure llama-cpp-python is installed for full capabilities.",
]


def _match_patterns(message: str, patterns: list) -> str | None:
    for pattern, responses in patterns:
        if re.search(pattern, message, re.IGNORECASE):
            return random.choice(responses)
    return None


def _build_contextual_response(messages: List[Message]) -> str:
    if not messages:
        return "Hello! I'm R1, your local AI assistant. How can I help?"

    last_user = None
    for msg in reversed(messages):
        if msg.role == "user":
            last_user = msg.content
            break

    if not last_user:
        return "Hello! What can I help you with?"

    message = last_user.strip()

    # Check greetings
    response = _match_patterns(message, _GREETING_PATTERNS)
    if response:
        return response

    # Check questions about capabilities
    response = _match_patterns(message, _QUESTION_PATTERNS)
    if response:
        return response

    # Echo-style responses for unknown input
    if len(message) < 5:
        return "Could you tell me more about what you'd like help with?"

    if message.endswith('?'):
        return random.choice(_UNKNOWN_RESPONSES)

    return f"I've received your message. I'm currently running in local fallback mode. To get full AI responses, configure a GGUF model in your .env file and ensure llama-cpp-python is installed."


class LocalProvider(BaseProvider):
    """Simple local provider that works without any external dependencies."""

    def __init__(self):
        self._model_name = "local:fallback"

    @property
    def name(self) -> str:
        return self._model_name

    async def health(self) -> dict:
        return {
            "healthy": True,
            "reason": "Local fallback provider - no external model needed",
        }

    async def chat(self, messages: List[Message], **kwargs) -> ModelResponse:
        response = _build_contextual_response(messages)
        return ModelResponse(content=response, model=self.name)
