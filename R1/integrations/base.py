"""
R1 v1 - Integration Base
Normalized inbound/outbound message format and routing helpers.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

from ..agent import get_runtime


@dataclass
class InboundMessage:
    transport: str
    user_id: str
    channel_id: str
    text: str
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OutboundMessage:
    channel_id: str
    text: str
    reply_to: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


def map_session_id(transport: str, user_id: str, channel_id: str) -> str:
    raw = f"{transport}:{user_id}:{channel_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class IntegrationRouter:
    def __init__(self):
        self.runtime = get_runtime()

    async def route(self, message: InboundMessage) -> OutboundMessage:
        session_id = map_session_id(message.transport, message.user_id, message.channel_id)
        await self.runtime.initialize()
        result = await self.runtime.chat(message.text, session_id=session_id)
        return OutboundMessage(
            channel_id=message.channel_id,
            text=result.get("response", ""),
            metadata={
                "session_id": session_id,
                "provider": result.get("provider")
            }
        )

    @staticmethod
    def now_iso() -> str:
        return datetime.utcnow().isoformat()
