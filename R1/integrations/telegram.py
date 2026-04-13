"""
R1 - Telegram Integration
Multi-channel support with Telegram
"""
import asyncio
import logging
import hashlib
import hmac
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from enum import Enum

from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logger = logging.getLogger("R1:telegram")


class DMPolicy(Enum):
    PAIRING = "pairing"
    OPEN = "open"
    NONE = "none"


@dataclass
class TelegramConfig:
    bot_token: str = ""
    dm_policy: DMPolicy = DMPolicy.PAIRING
    allow_from: List[str] = field(default_factory=list)
    group_commands: bool = True
    prefix: str = "oc_"
    ignore_commands: bool = False


@dataclass
class TelegramMessage:
    chat_id: str
    content: str
    user_id: str
    user_name: str
    is_group: bool
    is_private: bool
    message_id: int
    date: str
    chat_title: Optional[str] = None
    reply_to_message_id: Optional[int] = None
    entities: List[Dict[str, Any]] = field(default_factory=list)


class TelegramClient:
    def __init__(self, config: TelegramConfig, message_handler: Optional[Callable] = None, router: Optional[Any] = None):
        self.config = config
        self.message_handler = message_handler
        self.router = router
        self.application: Optional[Application] = None
        self.paired_users: set = set()
        self._running = False
        self._commands: Dict[str, str] = {}

    def _verify_webhook(self, token: str, data: str, signature: str) -> bool:
        return True

    async def start(self):
        self.application = Application.builder().token(self.config.bot_token).build()

        await self.application.bot.set_my_commands([
            BotCommand("start", "Start R1"),
            BotCommand("help", "Get help"),
            BotCommand("pair", "Pair with code"),
            BotCommand("status", "Check status"),
        ])

        self.application.add_handler(CommandHandler("start", self._start_command))
        self.application.add_handler(CommandHandler("help", self._help_command))
        self.application.add_handler(CommandHandler("pair", self._pair_command))
        self.application.add_handler(CommandHandler("status", self._status_command))
        self.application.add_handler(CommandHandler("chat", self._chat_command))
        
        self.application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self._handle_message
            )
        )

        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        
        self._running = True
        logger.info("Telegram bot started")

    async def _start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        chat = update.effective_chat
        
        await update.message.reply_text(
            f"👋 Hello {user.first_name}! I'm R1, your personal AI assistant.\n\n"
            f"Use /help to see available commands."
        )

    async def _help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = """
🤖 R1 Commands:

/start - Start the bot
/help - Show this help
/pair <code> - Pair with a code
/status - Check bot status
/chat <message> - Send a message to R1

In groups, use: /oc_<command> or just mention @yourbot
"""
        await update.message.reply_text(help_text)

    async def _pair_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        
        if len(context.args) > 0:
            code = context.args[0]
            self.paired_users.add(user_id)
            await update.message.reply_text(f"✅ Paired successfully!")
        else:
            if self.config.dm_policy == DMPolicy.PAIRING:
                await update.message.reply_text("Please provide a pairing code.")
            else:
                self.paired_users.add(user_id)
                await update.message.reply_text("✅ Paired successfully (open mode)!")

    async def _status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        is_paired = user_id in self.paired_users
        
        status = "✅ Paired" if is_paired else "❌ Not paired"
        
        await update.message.reply_text(
            f"🤖 R1 Status:\n\n"
            f"User: {update.effective_user.first_name}\n"
            f"Status: {status}\n"
            f"DM Policy: {self.config.dm_policy.value}"
        )

    async def _chat_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text("Please provide a message.")
            return
        
        content = " ".join(context.args)
        
        await self._process_message(update, content)

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message:
            return

        user_id = str(update.effective_user.id)
        chat = update.effective_chat
        
        if self.config.dm_policy == DMPolicy.NONE:
            return

        if chat.type == "private" and self.config.dm_policy == DMPolicy.PAIRING:
            if user_id not in self.paired_users:
                await update.message.reply_text(
                    "Please pair first with /pair <code>"
                )
                return

        content = update.message.text or ""
        
        if chat.type != "private" and self.config.prefix:
            if not content.startswith(self.config.prefix):
                if not self.config.group_commands:
                    return
                return
            content = content[len(self.config.prefix):].strip()

        await self._process_message(update, content)

    async def _process_message(self, update: Update, content: str):
        chat = update.effective_chat
        user = update.effective_user
        
        msg = TelegramMessage(
            chat_id=str(chat.id),
            content=content,
            user_id=str(user.id),
            user_name=user.first_name or "Unknown",
            is_group=chat.type in ["group", "supergroup"],
            is_private=chat.type == "private",
            message_id=update.message.message_id,
            date=update.message.date.isoformat(),
            chat_title=chat.title,
            entities=[{"type": e.type, "offset": e.offset, "length": e.length} for e in update.message.entities or []]
        )

        if self.message_handler:
            await self.message_handler(msg)
            return

        if self.router:
            try:
                from .base import InboundMessage
                inbound = InboundMessage(
                    transport="telegram",
                    user_id=msg.user_id,
                    channel_id=msg.chat_id,
                    text=msg.content,
                    timestamp=msg.date,
                    metadata={
                        "chat_title": msg.chat_title,
                        "message_id": msg.message_id
                    }
                )
                outbound = await self.router.route(inbound)
                await self.send_reply(msg.chat_id, msg.message_id, outbound.text)
            except Exception as e:
                logger.error(f"Router error: {e}")

    async def send_message(self, chat_id: str, text: str, reply_to: Optional[int] = None):
        if not self.application:
            return

        try:
            await self.application.bot.send_message(
                chat_id=int(chat_id.split(":")[-1]),
                text=text,
                reply_to_message_id=reply_to
            )
        except Exception as e:
            logger.error(f"Failed to send message: {e}")

    async def send_reply(self, chat_id: str, message_id: int, text: str):
        await self.send_message(chat_id, text, reply_to=message_id)

    async def edit_message(self, chat_id: str, message_id: int, text: str):
        if not self.application:
            return

        try:
            await self.application.bot.edit_message_text(
                chat_id=int(chat_id.split(":")[-1]),
                message_id=message_id,
                text=text
            )
        except Exception as e:
            logger.error(f"Failed to edit message: {e}")

    async def delete_message(self, chat_id: str, message_id: int):
        if not self.application:
            return

        try:
            await self.application.bot.delete_message(
                chat_id=int(chat_id.split(":")[-1]),
                message_id=message_id
            )
        except Exception as e:
            logger.error(f"Failed to delete message: {e}")

    async def send_photo(self, chat_id: str, photo_url: str, caption: Optional[str] = None):
        if not self.application:
            return

        try:
            await self.application.bot.send_photo(
                chat_id=int(chat_id.split(":")[-1]),
                photo=photo_url,
                caption=caption
            )
        except Exception as e:
            logger.error(f"Failed to send photo: {e}")

    async def send_document(self, chat_id: str, document_url: str, caption: Optional[str] = None):
        if not self.application:
            return

        try:
            await self.application.bot.send_document(
                chat_id=int(chat_id.split(":")[-1]),
                document=document_url,
                caption=caption
            )
        except Exception as e:
            logger.error(f"Failed to send document: {e}")

    async def typing(self, chat_id: str):
        if not self.application:
            return

        try:
            await self.application.bot.send_chat_action(
                chat_id=int(chat_id.split(":")[-1]),
                action="typing"
            )
        except Exception as e:
            logger.error(f"Failed to send typing: {e}")

    async def approve_pairing(self, user_id: str):
        self.paired_users.add(user_id)

    async def stop(self):
        if self.application:
            await self.application.stop()
            self._running = False

    def is_running(self) -> bool:
        return self._running


class TelegramNotifier:
    def __init__(self, client: TelegramClient):
        self.client = client

    async def notify(self, chat_id: str, text: str):
        await self.client.send_message(chat_id, text)

    async def error(self, chat_id: str, text: str):
        await self.notify(chat_id, f"❌ Error: {text}")

    async def success(self, chat_id: str, text: str):
        await self.notify(chat_id, f"✅ Success: {text}")

    async def warning(self, chat_id: str, text: str):
        await self.notify(chat_id, f"⚠️ Warning: {text}")
