"""
OpenClaw - Main Coordinator for R1 Personal AI Assistant
Brings together voice, chat, proactive features, and skills
"""
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from R1.openclaw_persona import persona
from R1.openclaw_voice import (
    start_voice_mode, stop_voice_mode,
    start_wake_word_listener, stop_wake_word_listener,
    get_voice_status, voice_conversation
)
from R1.openclaw_telegram import (
    start_telegram, stop_telegram, get_telegram_status
)
from R1.openclaw_proactive import (
    start_proactive, stop_proactive, get_proactive_status, add_reminder
)
from R1.openclaw_skills import skill_registry
from R1.agent import get_runtime

logger = logging.getLogger("R1:openclaw")


class OpenClaw:
    """
    OpenClaw Personal AI Assistant
    Your local-first AI that actually does things
    """

    def __init__(self):
        self.initialized = False
        self.voice_enabled = False
        self.telegram_enabled = False
        self.proactive_enabled = False

    async def initialize(self) -> bool:
        """Initialize the OpenClaw system"""
        if self.initialized:
            return True

        logger.info("🦞 Initializing OpenClaw...")

        # Initialize core AI runtime
        runtime = get_runtime()
        await runtime.initialize()

        # Start proactive agent (heartbeats, reminders)
        self.proactive_enabled = start_proactive()
        if self.proactive_enabled:
            logger.info("✓ Proactive agent started")

        # Start Telegram bot if configured
        telegram_status = get_telegram_status()
        if telegram_status["configured"]:
            self.telegram_enabled = await start_telegram()
            if self.telegram_enabled:
                logger.info("✓ Telegram bot started")

        self.initialized = True
        logger.info("✓ OpenClaw initialized successfully")
        return True

    async def shutdown(self):
        """Shutdown OpenClaw"""
        logger.info("Shutting down OpenClaw...")

        stop_voice_mode()
        stop_wake_word_listener()
        await stop_telegram()
        stop_proactive()

        self.initialized = False
        logger.info("OpenClaw shutdown complete")

    # === Voice Control ===

    def start_voice(self) -> bool:
        """Start voice conversation mode"""
        return start_voice_mode()

    def stop_voice(self):
        """Stop voice conversation mode"""
        stop_voice_mode()

    def enable_wake_word(self) -> bool:
        """Enable wake word listening"""
        return start_wake_word_listener()

    def disable_wake_word(self):
        """Disable wake word listening"""
        stop_wake_word_listener()

    # === Chat Interface ===

    async def chat(self, message: str, session_id: str = "default") -> str:
        """Process a chat message"""
        if not self.initialized:
            await self.initialize()

        # Check if it's a skill command first
        skill_response = await skill_registry.process_command(message)
        if skill_response:
            # Speak if voice is active
            if voice_conversation.active:
                await persona.speak(skill_response)
            return skill_response

        # Process through AI runtime
        runtime = get_runtime()

        # Enhance with persona context
        context = persona.get_context_prompt()
        enhanced_message = f"{context}\n\nUser: {message}"

        result = await runtime.chat(enhanced_message, session_id)
        response = result.get("response", "I'm here to help!")

        # Speak if voice is active
        if voice_conversation.active:
            await persona.speak(response)

        return response

    # === Proactive Features ===

    def add_reminder(self, title: str, when: Optional[str] = None) -> str:
        """Add a reminder"""
        return add_reminder(title, when)

    # === Status ===

    def get_status(self) -> Dict[str, Any]:
        """Get full system status"""
        return {
            "initialized": self.initialized,
            "assistant_name": persona.config.name,
            "user_name": persona.config.user_name,
            "voice": get_voice_status(),
            "telegram": get_telegram_status(),
            "proactive": get_proactive_status(),
            "skills": skill_registry.get_available_skills(),
        }

    def get_welcome_message(self) -> str:
        """Get welcome message"""
        return f"""
🦞 Welcome to OpenClaw - Your Personal AI Assistant

Assistant: {persona.config.name}
User: {persona.config.user_name or 'Not set'}

Commands:
  • voice          - Start voice conversation
  • telegram       - Check Telegram bot status
  • remind "task"  - Add a reminder
  • skills         - List available skills
  • status         - Show system status
  • help           - Show help

Just chat naturally and I'll help you out!
        """.strip()


# Global OpenClaw instance
openclaw = OpenClaw()


async def main():
    """Main entry point for OpenClaw"""
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║   🦞 OpenClaw for R1 - Personal AI Assistant              ║
    ║                                                           ║
    ║   Your AI that actually does things.                      ║
    ║   Voice, chat, memory, and skills - all local-first.      ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """)

    # Initialize
    await openclaw.initialize()

    # Print welcome
    print(openclaw.get_welcome_message())

    # Start wake word listener
    openclaw.enable_wake_word()
    print(f"\n👂 Wake word '{persona.config.wake_word}' is active. Say it to start talking!")

    # Simple REPL
    print("\nType 'exit' to quit, 'voice' for voice mode, or just chat:\n")

    while True:
        try:
            user_input = input("> ").strip()

            if not user_input:
                continue

            if user_input.lower() == "exit":
                print("Goodbye!")
                break

            elif user_input.lower() == "voice":
                print("🎤 Starting voice mode... (say 'stop listening' to exit)")
                openclaw.start_voice()

            elif user_input.lower() == "status":
                status = openclaw.get_status()
                print(f"\nStatus: {status}")

            elif user_input.lower() == "skills":
                skills = skill_registry.get_available_skills()
                print(f"\nAvailable skills: {', '.join(skills)}")

            elif user_input.lower() == "help":
                print(openclaw.get_welcome_message())

            elif user_input.lower().startswith("remind "):
                task = user_input[7:]
                result = openclaw.add_reminder(task)
                print(result)

            else:
                # Regular chat
                print("⏳ Thinking...")
                response = await openclaw.chat(user_input)
                print(f"🤖 {response}\n")

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")

    await openclaw.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
