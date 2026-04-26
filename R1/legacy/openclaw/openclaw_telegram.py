"""
OpenClaw-Style Telegram Bot Integration for R1
Allows messaging the AI assistant from Telegram
"""
import os
import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger("R1:telegram")

# Try to import telegram library
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import (
        Application, CommandHandler, MessageHandler,
        CallbackQueryHandler, ContextTypes, filters
    )
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logger.warning("python-telegram-bot not installed. Run: pip install python-telegram-bot")

from R1.agent.runtime import get_runtime
from R1.legacy.openclaw.openclaw_persona import persona
from R1.memory.store import get_memory_store


class TelegramBot:
    """
    Telegram Bot for R1
    Chat with your AI assistant from anywhere via Telegram
    """

    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.application: Optional[Any] = None
        self.active = False
        self.allowed_users: List[int] = []  # For private bot mode
        self.user_sessions: Dict[int, str] = {}  # user_id -> session_id

    def is_configured(self) -> bool:
        """Check if Telegram bot is configured"""
        return TELEGRAM_AVAILABLE and bool(self.token)

    async def start(self) -> bool:
        """Start the Telegram bot"""
        if not self.is_configured():
            logger.error("Telegram bot not configured. Set TELEGRAM_BOT_TOKEN in .env")
            return False

        if self.active:
            return True

        try:
            self.application = Application.builder().token(self.token).build()

            # Add handlers
            self.application.add_handler(CommandHandler("start", self._cmd_start))
            self.application.add_handler(CommandHandler("help", self._cmd_help))
            self.application.add_handler(CommandHandler("voice", self._cmd_voice))
            self.application.add_handler(CommandHandler("briefing", self._cmd_briefing))
            self.application.add_handler(CommandHandler("memory", self._cmd_memory))
            self.application.add_handler(CommandHandler("persona", self._cmd_persona))
            self.application.add_handler(CommandHandler("reset", self._cmd_reset))
            self.application.add_handler(CommandHandler("tools", self._cmd_tools))

            # Message handlers
            self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
            self.application.add_handler(MessageHandler(filters.VOICE, self._handle_voice))

            # Callback for inline buttons
            self.application.add_handler(CallbackQueryHandler(self._handle_callback))

            # Start the bot
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()

            self.active = True
            logger.info("Telegram bot started successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to start Telegram bot: {e}")
            return False

    async def stop(self):
        """Stop the Telegram bot"""
        if self.application and self.active:
            await self.application.updater.stop()
            await self.application.stop()
            self.active = False
            logger.info("Telegram bot stopped")

    # === Command Handlers ===

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user

        # Initialize session for this user
        session_id = f"telegram_{user.id}"
        self.user_sessions[user.id] = session_id

        greeting = f"""
🦞 Welcome to R1, your personal AI assistant!

I can help you with:
• Answering questions
• Managing your calendar & tasks
• Running code & commands
• Remembering important info
• Sending emails & notifications

Commands:
/briefing - Get your morning briefing
/memory - View your stored memories
/tools - See available tools
/voice - Toggle voice mode
/reset - Clear our conversation
/persona - View my settings

Just message me naturally, or use /help for more info.
        """.strip()

        await update.message.reply_text(greeting)

        # Greet vocally if enabled
        if persona.config.voice_enabled:
            await persona.speak(f"Welcome{', ' + user.first_name if user.first_name else ''}! I'm {persona.config.name}, ready to help.")

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """
📚 R1 Commands:

/start - Start the bot
/briefing - Daily briefing
/memory - Show your memories
/persona - Assistant settings
/tools - List available tools
/voice - Toggle voice responses
/reset - Reset conversation
/help - Show this help

You can also:
• Send voice messages
• Share files for analysis
• Use natural language commands

Examples:
"Remind me to call mom at 5pm"
"Add meeting tomorrow at 2pm"
"What's on my calendar today?"
        """.strip()
        await update.message.reply_text(help_text)

    async def _cmd_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /voice command"""
        enabled = not persona.config.voice_enabled
        result = persona.toggle_voice(enabled)
        await update.message.reply_text(f"🔊 {result}")

    async def _cmd_briefing(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /briefing command"""
        await update.message.reply_text("⏳ Generating your briefing...")

        briefing = persona.generate_briefing()

        # Create inline keyboard
        keyboard = [
            [
                InlineKeyboardButton("📅 Calendar", callback_data="briefing_calendar"),
                InlineKeyboardButton("⏰ Reminders", callback_data="briefing_reminders"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(briefing, reply_markup=reply_markup)

    async def _cmd_memory(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /memory command"""
        facts = get_memory_store().get_all_facts()

        if not facts:
            await update.message.reply_text("🤔 I don't have any memories yet. Tell me something about yourself!")
            return

        lines = ["🧠 Here's what I remember about you:"]
        for key, value in facts.items():
            lines.append(f"  • {key}: {value}")

        await update.message.reply_text("\n".join(lines[:50]))  # Limit message size

    async def _cmd_persona(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /persona command"""
        summary = persona.get_summary()

        keyboard = [
            [
                InlineKeyboardButton("🎙️ Voice", callback_data="toggle_voice"),
                InlineKeyboardButton("🔔 Proactive", callback_data="toggle_proactive"),
            ],
            [
                InlineKeyboardButton("📢 Briefing Time", callback_data="set_briefing"),
                InlineKeyboardButton("📝 Rename", callback_data="rename_assistant"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(f"⚙️ {summary}", reply_markup=reply_markup)

    async def _cmd_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /reset command"""
        user_id = update.effective_user.id
        if user_id in self.user_sessions:
            old_session = self.user_sessions[user_id]
            # Create new session
            self.user_sessions[user_id] = f"telegram_{user_id}_{datetime.now().timestamp()}"

        await update.message.reply_text("🔄 Conversation reset! Starting fresh.")

    async def _cmd_tools(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /tools command"""
        from R1.tools.registry import get_tool_registry
        tools = get_tool_registry()

        tool_list = [f"• {t.name}: {t.description}" for t in tools.list_tools()]

        await update.message.reply_text("Available tools:\n\n" + "\n".join(tool_list))

    # === Message Handlers ===

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages"""
        user = update.effective_user
        message_text = update.message.text

        # Get or create session
        session_id = self.user_sessions.get(user.id)
        if not session_id:
            session_id = f"telegram_{user.id}"
            self.user_sessions[user.id] = session_id

        # Show typing indicator
        await update.message.chat.send_action(action="typing")

        # Process through AI
        try:
            runtime = get_runtime()
            await runtime.initialize()

            # Enhance with persona context
            persona_context = persona.get_context_prompt()
            enhanced_message = f"{persona_context}\n\nUser message: {message_text}"

            result = await runtime.chat(enhanced_message, session_id)
            response = result.get("response", "I'm here to help!")

            # Send response
            await update.message.reply_text(response)

            # Voice response if enabled
            if persona.config.voice_enabled:
                await persona.speak(response)

        except Exception as e:
            logger.error(f"Error processing Telegram message: {e}")
            await update.message.reply_text("❌ Sorry, I had an error processing that. Try again!")

    async def _handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle voice messages"""
        await update.message.reply_text("🎤 Voice messages coming soon! For now, please send text.")

    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button callbacks"""
        query = update.callback_query
        await query.answer()

        data = query.data

        if data == "toggle_voice":
            result = persona.toggle_voice()
            await query.edit_message_text(f"🔊 {result}")

        elif data == "toggle_proactive":
            enabled = not persona.config.proactive_enabled
            result = persona.set_proactive(enabled)
            await query.edit_message_text(f"🔔 {result}")

        elif data == "briefing_calendar":
            await query.edit_message_text("📅 Calendar feature coming soon!")

        elif data == "briefing_reminders":
            await query.edit_message_text("⏰ Reminders feature coming soon!")


class TelegramNotifier:
    """
    Send proactive notifications via Telegram
    """

    def __init__(self, bot: TelegramBot):
        self.bot = bot

    async def send_notification(self, user_id: int, message: str):
        """Send notification to a user"""
        if not self.bot.active:
            return False

        try:
            await self.bot.application.bot.send_message(
                chat_id=user_id,
                text=f"🔔 {message}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return False

    async def broadcast(self, message: str, user_ids: List[int] = None):
        """Broadcast message to multiple users"""
        if not user_ids:
            return

        for user_id in user_ids:
            await self.send_notification(user_id, message)


# Global instance
telegram_bot = TelegramBot()
telegram_notifier = TelegramNotifier(telegram_bot)


async def start_telegram() -> bool:
    """Start Telegram bot"""
    return await telegram_bot.start()


async def stop_telegram():
    """Stop Telegram bot"""
    await telegram_bot.stop()


def get_telegram_status() -> Dict[str, Any]:
    """Get Telegram bot status"""
    return {
        "configured": telegram_bot.is_configured(),
        "active": telegram_bot.active,
        "users": len(telegram_bot.user_sessions),
    }
