"""
R1 - Discord Integration
Multi-channel support with Discord
"""
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
import json

import discord
from discord import app_commands

logger = logging.getLogger("R1:discord")


class DMPolicy(Enum):
    PAIRING = "pairing"
    OPEN = "open"
    NONE = "none"


@dataclass
class DiscordConfig:
    token: str = ""
    dm_policy: DMPolicy = DMPolicy.PAIRING
    allow_from: List[str] = field(default_factory=list)
    guild_id: Optional[str] = None
    channel_id: Optional[str] = None
    prefix: str = "oc_"
    ignore_bots: bool = True


@dataclass
class DiscordMessage:
    channel: str
    content: str
    author: str
    author_id: str
    is_dm: bool
    is_group: bool
    message_id: str
    timestamp: str
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    embeds: List[Dict[str, Any]] = field(default_factory=list)
    referenced_message: Optional[str] = None


class DiscordClient:
    def __init__(self, config: DiscordConfig, message_handler: Optional[Callable] = None, router: Optional[Any] = None):
        self.config = config
        self.message_handler = message_handler
        self.router = router
        self.client: Optional[discord.Client] = None
        self.tree: Optional[app_commands.CommandTree] = None
        self.paired_users: set = set()
        self.guild: Optional[discord.Guild] = None
        self.channel: Optional[discord.TextChannel] = None
        self._running = False

    async def start(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True
        intents.dm_messages = True
        intents.guild_messages = True
        intents.typing = True

        self.client = discord.Client(intents=intents)
        self.tree = app_commands.CommandTree(self.client)

        @self.client.event
        async def on_ready():
            logger.info(f"Discord bot logged in as {self.client.user}")
            if self.config.guild_id:
                self.guild = self.client.get_guild(int(self.config.guild_id))
                if self.guild:
                    await self.tree.sync(guild=self.guild)
                    logger.info(f"Synced commands to guild {self.guild.name}")
            if self.config.channel_id:
                self.channel = self.client.get_channel(int(self.config.channel_id))
            self._running = True

        @self.client.event
        async def on_message(message: discord.Message):
            await self._handle_message(message)

        @self.client.event
        async def on_dm_message(message: discord.Message):
            await self._handle_dm(message)

        try:
            await self.client.start(self.config.token)
        except Exception as e:
            logger.error(f"Failed to start Discord client: {e}")

    async def _handle_message(self, message: discord.Message):
        if message.author == self.client.user:
            return

        if self.config.ignore_bots and message.author.bot:
            return

        if message.guild and self.config.guild_id:
            if message.guild.id != int(self.config.guild_id):
                return
            if self.config.channel_id and message.channel.id != int(self.config.channel_id):
                return

        content = message.content
        if message.guild:
            if not content.startswith(self.config.prefix):
                return
            content = content[len(self.config.prefix):].strip()

        msg = DiscordMessage(
            channel=f"discord:{message.channel.id}",
            content=content,
            author=str(message.author),
            author_id=str(message.author.id),
            is_dm=isinstance(message.channel, discord.DMChannel),
            is_group=isinstance(message.channel, discord.GroupChannel),
            message_id=str(message.id),
            timestamp=message.created_at.isoformat(),
            attachments=[{"filename": a.filename, "url": a.url} for a in message.attachments],
        )

        if self.message_handler and message.guild:
            await self.message_handler(msg)
            return

        if self.router and message.guild:
            try:
                from .base import InboundMessage
                inbound = InboundMessage(
                    transport="discord",
                    user_id=msg.author_id,
                    channel_id=msg.channel,
                    text=msg.content,
                    timestamp=msg.timestamp,
                    metadata={"message_id": msg.message_id}
                )
                outbound = await self.router.route(inbound)
                await self.send_message(msg.channel, outbound.text)
            except Exception as e:
                logger.error(f"Router error: {e}")

    async def _handle_dm(self, message: discord.Message):
        author_id = str(message.author.id)
        
        if self.config.dm_policy == DMPolicy.NONE:
            return

        if self.config.dm_policy == DMPolicy.PAIRING:
            if author_id not in self.paired_users:
                code = self._generate_pairing_code()
                await message.author.send(
                    f"To use R1, please pair with code: **{code}**\n"
                    f"Run `/pair {code}` to approve."
                )
                return

        msg = DiscordMessage(
            channel=f"discord:dm:{author_id}",
            content=message.content,
            author=str(message.author),
            author_id=author_id,
            is_dm=True,
            is_group=False,
            message_id=str(message.id),
            timestamp=message.created_at.isoformat(),
        )

        if self.message_handler:
            await self.message_handler(msg)
            return

        if self.router:
            try:
                from .base import InboundMessage
                inbound = InboundMessage(
                    transport="discord",
                    user_id=msg.author_id,
                    channel_id=msg.channel,
                    text=msg.content,
                    timestamp=msg.timestamp,
                    metadata={"message_id": msg.message_id}
                )
                outbound = await self.router.route(inbound)
                await self.send_message(msg.channel, outbound.text)
            except Exception as e:
                logger.error(f"Router error: {e}")

    def _generate_pairing_code(self) -> str:
        import random
        import string
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

    async def approve_pairing(self, user_id: str, code: str):
        self.paired_users.add(user_id)

    async def send_message(self, channel_id: str, content: str, embed: Optional[discord.Embed] = None):
        if not self.client:
            return

        try:
            if channel_id.startswith("discord:dm:"):
                user_id = channel_id.split(":")[-1]
                user = await self.client.fetch_user(int(user_id))
                await user.send(content, embed=embed)
            else:
                channel = self.client.get_channel(int(channel_id.split(":")[-1]))
                if channel:
                    await channel.send(content, embed=embed)
        except Exception as e:
            logger.error(f"Failed to send message: {e}")

    async def send_reply(self, message_id: str, content: str):
        if not self.client:
            return

        try:
            channel = self.client.get_partial_messageable(int(message_id.split(":")[0]))
            msg = await channel.fetch_message(int(message_id.split(":")[1]))
            await msg.reply(content)
        except Exception as e:
            logger.error(f"Failed to send reply: {e}")

    async def add_reaction(self, message_id: str, emoji: str):
        if not self.client:
            return

        try:
            channel = self.client.get_partial_messageable(int(message_id.split(":")[0]))
            msg = await channel.fetch_message(int(message_id.split(":")[1]))
            await msg.add_reaction(emoji)
        except Exception as e:
            logger.error(f"Failed to add reaction: {e}")

    async def typing(self, channel_id: str):
        if not self.client:
            return

        try:
            channel = self.client.get_channel(int(channel_id.split(":")[-1]))
            if channel:
                async with channel.typing():
                    pass
        except Exception as e:
            logger.error(f"Failed to show typing: {e}")

    async def stop(self):
        if self.client:
            await self.client.close()
            self._running = False

    def is_running(self) -> bool:
        return self._running


class DiscordNotifier:
    def __init__(self, client: DiscordClient):
        self.client = client

    async def notify(self, channel_id: str, title: str, message: str, color: int = 0x5865F2):
        embed = discord.Embed(title=title, description=message, color=color)
        await self.client.send_message(channel_id, "", embed=embed)

    async def error(self, channel_id: str, message: str):
        await self.notify(channel_id, "Error", message, 0xFF0000)

    async def success(self, channel_id: str, message: str):
        await self.notify(channel_id, "Success", message, 0x00FF00)

    async def warning(self, channel_id: str, message: str):
        await self.notify(channel_id, "Warning", message, 0xFFA500)
