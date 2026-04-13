"""
R1 - Slack Integration
Multi-channel support with Slack
"""
import asyncio
import logging
import hashlib
import hmac
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
import json

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse

logger = logging.getLogger("R1:slack")


class DMPolicy(Enum):
    PAIRING = "pairing"
    OPEN = "open"
    NONE = "none"


@dataclass
class SlackConfig:
    bot_token: str = ""
    app_token: str = ""
    signing_secret: str = ""
    dm_policy: DMPolicy = DMPolicy.PAIRING
    allow_from: List[str] = field(default_factory=list)
    channel_id: Optional[str] = None
    prefix: str = "oc_"
    ignore_bots: bool = True
    socket_mode: bool = True


@dataclass
class SlackMessage:
    channel: str
    content: str
    user: str
    user_id: str
    is_dm: bool
    is_group: bool
    thread_ts: Optional[str] = None
    ts: str = ""
    files: List[Dict[str, Any]] = field(default_factory=list)
    subtype: str = ""


class SlackClient:
    def __init__(self, config: SlackConfig, message_handler: Optional[Callable] = None, router: Optional[Any] = None):
        self.config = config
        self.message_handler = message_handler
        self.router = router
        self.web_client: Optional[WebClient] = None
        self.socket_client: Optional[SocketModeClient] = None
        self.paired_users: set = set()
        self._running = False

    def _verify_request(self, timestamp: str, body: str, signature: str) -> bool:
        if not self.config.signing_secret:
            return True
        
        base_string = f"v0:{timestamp}:{body}"
        computed_signature = "v0=" + hmac.new(
            self.config.signing_secret.encode(),
            base_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(computed_signature, signature)

    async def start(self):
        self.web_client = WebClient(token=self.config.bot_token)

        if self.config.socket_mode and self.config.app_token:
            self.socket_client = SocketModeClient(
                app_token=self.config.app_token,
                web_client=self.web_client,
                on_message_request=self._handle_socket_message,
                onslash_command_request=self._handle_slash_command,
            )
            await self.socket_client.connect()
            logger.info("Slack Socket Mode connected")
        else:
            logger.info("Slack WebClient ready (no Socket Mode)")

        self._running = True

    async def _handle_socket_message(self, client: SocketModeClient, req: SocketModeRequest):
        if req.type == "events_api":
            payload = req.payload
            event = payload.get("event", {})
            
            if event.get("subtype") == "bot_message":
                return

            if self.config.ignore_bots and event.get("subtype") == "bot_message":
                return

            await self._handle_event(event)

        response = SocketModeResponse(envelope_id=req.envelope_id)
        await client.send_response(response)

    async def _handle_slash_command(self, client: SocketModeClient, req: SocketModeRequest):
        command = req.payload
        user_id = command.get("user_id", "")
        channel_id = command.get("channel_id", "")
        text = command.get("text", "")
        command_id = command.get("command", "")

        msg = SlackMessage(
            channel=f"slack:{channel_id}",
            content=text,
            user=user_id,
            user_id=user_id,
            is_dm=False,
            is_group=False,
            ts=command.get("ts", ""),
        )

        if self.message_handler:
            await self.message_handler(msg)
            return

        if self.router:
            try:
                from .base import InboundMessage
                inbound = InboundMessage(
                    transport="slack",
                    user_id=msg.user_id,
                    channel_id=msg.channel,
                    text=msg.content,
                    timestamp=msg.ts,
                    metadata={"thread_ts": msg.thread_ts}
                )
                outbound = await self.router.route(inbound)
                await self.send_message(msg.channel, outbound.text, thread_ts=msg.thread_ts)
            except Exception as e:
                logger.error(f"Router error: {e}")

        response = SocketModeResponse(envelope_id=req.envelope_id)
        await client.send_response(response)

    async def _handle_event(self, event: Dict[str, Any]):
        channel = event.get("channel", "")
        user = event.get("user", "")
        text = event.get("text", "")
        ts = event.get("ts", "")
        thread_ts = event.get("thread_ts")
        subtype = event.get("subtype", "")
        files = event.get("files", [])

        channel_type = event.get("channel_type", "")
        is_dm = channel_type == "im"
        is_group = channel_type == "mpim"

        if self.config.channel_id and channel != self.config.channel_id and not is_dm:
            return

        if is_dm and self.config.dm_policy == DMPolicy.NONE:
            return

        if is_dm and self.config.dm_policy == DMPolicy.PAIRING:
            if user not in self.paired_users:
                await self._send_dm(user, "To use R1, please pair first.")
                return

        if self.config.prefix and not is_dm:
            if not text.startswith(self.config.prefix):
                return
            text = text[len(self.config.prefix):].strip()

        msg = SlackMessage(
            channel=f"slack:{channel}",
            content=text,
            user=user,
            user_id=user,
            is_dm=is_dm,
            is_group=is_group,
            thread_ts=thread_ts,
            ts=ts,
            files=files,
            subtype=subtype,
        )

        if self.message_handler:
            await self.message_handler(msg)
            return

        if self.router:
            try:
                from .base import InboundMessage
                inbound = InboundMessage(
                    transport="slack",
                    user_id=msg.user_id,
                    channel_id=msg.channel,
                    text=msg.content,
                    timestamp=msg.ts,
                    metadata={"thread_ts": msg.thread_ts}
                )
                outbound = await self.router.route(inbound)
                await self.send_message(msg.channel, outbound.text, thread_ts=msg.thread_ts)
            except Exception as e:
                logger.error(f"Router error: {e}")

    async def _send_dm(self, user_id: str, text: str):
        if not self.web_client:
            return

        try:
            conversation = await self.web_client.conversations_open(users=[user_id])
            if conversation["ok"]:
                await self.web_client.chat_postMessage(
                    channel=conversation["channel"]["id"],
                    text=text
                )
        except SlackApiError as e:
            logger.error(f"Failed to send DM: {e}")

    async def send_message(self, channel_id: str, content: str, thread_ts: Optional[str] = None):
        if not self.web_client:
            return

        try:
            channel = channel_id.split(":")[-1]
            self.web_client.chat_postMessage(
                channel=channel,
                text=content,
                thread_ts=thread_ts
            )
        except SlackApiError as e:
            logger.error(f"Failed to send message: {e}")

    async def send_reply(self, channel_id: str, thread_ts: str, content: str):
        await self.send_message(channel_id, content, thread_ts=thread_ts)

    async def add_reaction(self, channel_id: str, ts: str, emoji: str):
        if not self.web_client:
            return

        try:
            channel = channel_id.split(":")[-1]
            self.web_client.reactions_add(
                channel=channel,
                timestamp=ts,
                name=emoji
            )
        except SlackApiError as e:
            logger.error(f"Failed to add reaction: {e}")

    async def typing(self, channel_id: str):
        if not self.web_client:
            return

        try:
            channel = channel_id.split(":")[-1]
            self.web_client.chat_postEphemeral(
                channel=channel,
                text=""
            )
        except SlackApiError as e:
            logger.error(f"Failed to show typing: {e}")

    async def upload_file(self, channel_id: str, content: str, filename: str):
        if not self.web_client:
            return

        try:
            channel = channel_id.split(":")[-1]
            self.web_client.files_upload(
                channels=channel,
                content=content,
                filename=filename
            )
        except SlackApiError as e:
            logger.error(f"Failed to upload file: {e}")

    async def approve_pairing(self, user_id: str):
        self.paired_users.add(user_id)

    async def stop(self):
        if self.socket_client:
            self.socket_client.close()
        self._running = False

    def is_running(self) -> bool:
        return self._running


class SlackNotifier:
    def __init__(self, client: SlackClient):
        self.client = client

    async def notify(self, channel_id: str, text: str):
        await self.client.send_message(channel_id, text)

    async def error(self, channel_id: str, text: str):
        await self.notify(channel_id, f"❌ Error: {text}")

    async def success(self, channel_id: str, text: str):
        await self.notify(channel_id, f"✅ Success: {text}")

    async def warning(self, channel_id: str, text: str):
        await self.notify(channel_id, f"⚠️ Warning: {text}")
