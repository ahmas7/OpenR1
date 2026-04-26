"""
OpenClaw-Style Voice Conversation System for R1
Continuous voice dialogue with natural turn-taking
"""
import asyncio
import threading
import queue
import time
from datetime import datetime
from typing import Optional, Callable, List, Dict, Any
import logging

from R1.audio.voice_system import listen, speak, get_status as get_voice_status
from R1.legacy.openclaw.openclaw_persona import persona
from R1.agent import get_runtime

logger = logging.getLogger("R1:voice_conversation")


class VoiceConversation:
    """
    Continuous voice conversation system
    Listens -> Transcribes -> Responds -> Speaks -> Listens again
    """

    def __init__(self):
        self.active = False
        self.conversation_thread = None
        self.message_queue = queue.Queue()
        self.response_queue = queue.Queue()
        self.session_id = "voice_session"
        self.silence_timeout = 30  # Seconds of silence before auto-stopping
        self.last_activity = None
        self.conversation_history: List[Dict[str, Any]] = []

    def start(self) -> bool:
        """Start voice conversation mode"""
        if self.active:
            return True

        if not get_voice_status()["stt_available"]:
            logger.error("Speech recognition not available")
            return False

        self.active = True
        self.last_activity = time.time()
        self.conversation_thread = threading.Thread(target=self._conversation_loop, daemon=True)
        self.conversation_thread.start()

        # Greet the user
        greeting = persona.greet()
        persona.speak(greeting, blocking=True)

        logger.info("Voice conversation started")
        return True

    def stop(self):
        """Stop voice conversation mode"""
        self.active = False
        if self.conversation_thread:
            self.conversation_thread.join(timeout=2)
        logger.info("Voice conversation stopped")

    def _conversation_loop(self):
        """Main conversation loop running in thread"""
        import asyncio

        # Create event loop for async operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Initialize runtime
        runtime = get_runtime()
        loop.run_until_complete(runtime.initialize())

        persona.speak("Listening...", blocking=False)

        while self.active:
            try:
                # Check for timeout
                if time.time() - self.last_activity > self.silence_timeout:
                    persona.speak("Going to sleep. Say my wake word to wake me up.", blocking=True)
                    self.active = False
                    break

                # Listen for speech
                text = listen(timeout=5)

                if text:
                    logger.info(f"Heard: {text}")
                    self.last_activity = time.time()

                    # Check for stop command
                    if any(phrase in text.lower() for phrase in ["stop listening", "go to sleep", "goodbye", "see you"]):
                        farewell = f"Goodbye{', ' + persona.config.user_name if persona.config.user_name else ''}!"
                        persona.speak(farewell, blocking=True)
                        self.active = False
                        break

                    # Process the message
                    response = loop.run_until_complete(self._process_message(text, runtime))

                    # Speak response
                    if response:
                        persona.speak(response, blocking=True)
                        time.sleep(0.5)  # Brief pause before listening again
                        if self.active:
                            persona.speak("Listening...", blocking=False)

            except Exception as e:
                logger.error(f"Conversation error: {e}")
                time.sleep(1)

        loop.close()

    async def _process_message(self, text: str, runtime) -> str:
        """Process user message and generate response"""
        # Add context from persona
        context = persona.get_context_prompt()

        # Enhance message with context
        enhanced_message = f"{context}\n\nUser: {text}\n\nRespond naturally and conversationally."

        try:
            result = await runtime.chat(enhanced_message, self.session_id)
            response = result.get("response", "I'm here to help!")

            # Store in conversation history
            self.conversation_history.append({
                "timestamp": datetime.now().isoformat(),
                "user": text,
                "assistant": response
            })

            # Keep only last 20 exchanges
            if len(self.conversation_history) > 20:
                self.conversation_history = self.conversation_history[-20:]

            return response

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return "I'm sorry, I didn't catch that. Could you repeat?"

    def get_conversation_summary(self) -> str:
        """Get summary of current conversation"""
        if not self.conversation_history:
            return "No conversation yet."

        lines = ["Conversation Summary:"]
        for i, exchange in enumerate(self.conversation_history[-5:], 1):
            lines.append(f"\n{i}. You: {exchange['user']}")
            lines.append(f"   {persona.config.name}: {exchange['assistant'][:100]}...")

        return "\n".join(lines)


class WakeWordListener:
    """
    Background wake word listener
    Activates voice conversation when wake word is detected
    """

    def __init__(self):
        self.active = False
        self.listener_thread = None
        self.on_wake: Optional[Callable] = None
        self.conversation = VoiceConversation()

    def start(self, on_wake_callback: Optional[Callable] = None) -> bool:
        """Start wake word listening"""
        if self.active:
            return True

        if not get_voice_status()["stt_available"]:
            logger.error("Speech recognition not available for wake word")
            return False

        self.active = True
        self.on_wake = on_wake_callback

        self.listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listener_thread.start()

        logger.info(f"Wake word listener started (word: '{persona.config.wake_word}')")
        return True

    def stop(self):
        """Stop wake word listening"""
        self.active = False
        self.conversation.stop()
        if self.listener_thread:
            self.listener_thread.join(timeout=2)
        logger.info("Wake word listener stopped")

    def _listen_loop(self):
        """Continuous listening loop"""
        while self.active:
            try:
                # Listen for wake word
                text = listen(timeout=3)

                if text:
                    wake_word = persona.config.wake_word.lower()
                    if wake_word in text.lower() or wake_word.replace(" ", "") in text.lower().replace(" ", ""):
                        logger.info(f"Wake word detected: {text}")

                        # Trigger callback or start conversation
                        if self.on_wake:
                            self.on_wake()
                        else:
                            self._on_wake_default()

            except Exception as e:
                logger.error(f"Wake word error: {e}")
                time.sleep(1)

    def _on_wake_default(self):
        """Default wake behavior - start conversation"""
        if not self.conversation.active:
            self.conversation.start()


class VoiceCommandProcessor:
    """
    Process voice commands even when not in full conversation mode
    Quick commands like "what's the weather", "set a timer", etc.
    """

    QUICK_COMMANDS = {
        "time": ["what time is it", "what's the time", "current time"],
        "date": ["what day is it", "what's today", "today's date"],
        "weather": ["what's the weather", "how's the weather", "weather today"],
        "briefing": ["morning briefing", "daily briefing", "what's on today"],
        "stop": ["stop listening", "go to sleep", "goodbye"],
    }

    def __init__(self):
        self.active = False

    def process(self, text: str) -> Optional[str]:
        """
        Process quick voice command
        Returns response if handled, None if should go to full AI
        """
        text_lower = text.lower()

        # Check for quick commands
        for cmd_type, phrases in self.QUICK_COMMANDS.items():
            if any(phrase in text_lower for phrase in phrases):
                return self._handle_command(cmd_type)

        return None

    def _handle_command(self, cmd_type: str) -> str:
        """Handle specific quick command"""
        from datetime import datetime

        if cmd_type == "time":
            now = datetime.now()
            return f"It's {now.strftime('%I:%M %p')}"

        elif cmd_type == "date":
            now = datetime.now()
            return f"Today is {now.strftime('%A, %B %d, %Y')}"

        elif cmd_type == "weather":
            return "I don't have weather data configured yet. You can add a weather skill!"

        elif cmd_type == "briefing":
            return persona.generate_briefing()

        elif cmd_type == "stop":
            return "Going to sleep. Wake me up anytime!"

        return None


# Global instances
voice_conversation = VoiceConversation()
wake_listener = WakeWordListener()
command_processor = VoiceCommandProcessor()


def start_voice_mode() -> bool:
    """
    Start full voice conversation mode
    """
    return voice_conversation.start()


def stop_voice_mode():
    """
    Stop voice conversation mode
    """
    voice_conversation.stop()


def start_wake_word_listener(on_wake: Optional[Callable] = None) -> bool:
    """
    Start background wake word listener
    """
    return wake_listener.start(on_wake)


def stop_wake_word_listener():
    """
    Stop background wake word listener
    """
    wake_listener.stop()


def is_voice_active() -> bool:
    """Check if voice system is active"""
    return voice_conversation.active or wake_listener.active


def get_voice_status() -> Dict[str, Any]:
    """Get voice system status"""
    return {
        "conversation_active": voice_conversation.active,
        "wake_listener_active": wake_listener.active,
        "wake_word": persona.config.wake_word,
        "voice_enabled": persona.config.voice_enabled,
        "conversation_length": len(voice_conversation.conversation_history),
    }
