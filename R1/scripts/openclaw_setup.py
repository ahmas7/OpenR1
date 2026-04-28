"""
OpenClaw Setup Script for R1
Configures the personal AI assistant
"""
import os
import json
from pathlib import Path
from typing import Dict, Any

def create_env_template():
    """Create .env template with OpenClaw configuration"""

    env_template = """
# ═══════════════════════════════════════════════════════════
# OpenClaw Configuration for R1
# Your personal AI assistant settings
# ═══════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════
# AI Model Configuration
# ═══════════════════════════════════════════════════════════
R1_PROVIDER=ollama
R1_MODEL=qwen2.5:1.5b
OLLAMA_ENDPOINT=http://localhost:11434

# ═══════════════════════════════════════════════════════════
# OpenClaw Personal Assistant Settings
# ═══════════════════════════════════════════════════════════

# Assistant Name (what you call your AI)
ASSISTANT_NAME=R1

# Your name (so the AI knows who you are)
USER_NAME=

# Wake word (say this to activate voice mode)
WAKE_WORD=hey r1

# Voice settings
VOICE_ENABLED=true
VOICE_GENDER=neutral

# Proactive features
PROACTIVE_ENABLED=true
MORNING_BRIEFING=true
BRIEFING_TIME=08:00

# ═══════════════════════════════════════════════════════════
# Chat App Integrations (optional)
# ═══════════════════════════════════════════════════════════

# Telegram Bot
# Get token from @BotFather on Telegram
TELEGRAM_BOT_TOKEN=

# WhatsApp via Twilio
# Get credentials from https://twilio.com/console
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=

# Discord Bot
DISCORD_BOT_TOKEN=

# Slack Bot
SLACK_BOT_TOKEN=
SLACK_SIGNING_SECRET=

# ═══════════════════════════════════════════════════════════
# Email Integration (Gmail)
# ═══════════════════════════════════════════════════════════

# Gmail App Password (not your regular password!)
# Generate at: https://myaccount.google.com/apppasswords
GMAIL_USER=
GMAIL_APP_PASSWORD=

# Or use SMTP settings
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=

# ═══════════════════════════════════════════════════════════
# Calendar Integration
# ═══════════════════════════════════════════════════════════

# Google Calendar (optional)
# Requires Google Cloud project with Calendar API enabled
GOOGLE_CALENDAR_CREDENTIALS_PATH=

# ═══════════════════════════════════════════════════════════
# Weather
# ═══════════════════════════════════════════════════════════

# OpenWeatherMap API Key
# Get free key at: https://openweathermap.org/api
OPENWEATHER_API_KEY=
DEFAULT_CITY=New York

# ═══════════════════════════════════════════════════════════
# Spotify
# ═══════════════════════════════════════════════════════════

# Spotify Developer App
# Create at: https://developer.spotify.com/dashboard
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=

# ═══════════════════════════════════════════════════════════
# Advanced Settings
# ═══════════════════════════════════════════════════════════

# Enable legacy routes for backward compatibility
R1_ENABLE_LEGACY_ROUTES=false

# Job settings
R1_JOBS_ENABLED=true
R1_HEARTBEAT_SECONDS=60
R1_REMINDERS_SECONDS=300

# Safety settings
R1_TOOL_POLICY=confirm
R1_TOOL_RETRIES=1
R1_TOOL_AUTO_CONFIRM=false

# Stack settings
R1_STACK_ALLOW_RUN=false
""".strip()

    env_path = Path("E:/MYAI/R1/.env")

    if env_path.exists():
        print(f"⚠️  .env file already exists at {env_path}")
        print("   Backing up to .env.backup")
        env_path.rename(env_path.with_suffix('.env.backup'))

    env_path.write_text(env_template)
    print(f"✅ Created .env template at {env_path}")
    print("   Edit it to configure your OpenClaw assistant!")


def setup_persona():
    """Interactive persona setup"""
    print("\n🦞 OpenClaw Setup\n")
    print("Let's configure your personal AI assistant!\n")

    config = {}

    # Assistant name
    name = input("What would you like to name your assistant? [R1]: ").strip()
    config['name'] = name if name else "R1"

    # User name
    user_name = input("What's your name? (so your assistant knows you): ").strip()
    if user_name:
        config['user_name'] = user_name

    # Wake word
    wake = input(f"Wake word? (say this to activate voice) [{config['name'].lower()}]: ").strip()
    config['wake_word'] = wake if wake else config['name'].lower()

    # Voice preference
    voice = input("Enable voice? [Y/n]: ").strip().lower()
    config['voice_enabled'] = voice not in ['n', 'no']

    # Proactive
    proactive = input("Enable proactive features (reminders, check-ins)? [Y/n]: ").strip().lower()
    config['proactive_enabled'] = proactive not in ['n', 'no']

    if config.get('proactive_enabled', True):
        briefing_time = input("What time for morning briefing? [08:00]: ").strip()
        config['briefing_time'] = briefing_time if briefing_time else "08:00"

    # Save persona
    from R1.legacy.openclaw.openclaw_persona import persona
    for key, value in config.items():
        if hasattr(persona.config, key):
            setattr(persona.config, key, value)

    persona._save_config()

    print(f"\n✅ Persona configured!")
    print(f"   Assistant: {config['name']}")
    print(f"   Wake word: '{config.get('wake_word', 'r1')}'")


def show_quickstart():
    """Show quickstart guide"""
    print("""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   🦞 OpenClaw Quickstart                                  ║
║                                                           ║
╠═══════════════════════════════════════════════════════════╣
║                                                           ║
║  1. Start the server:                                     ║
║     python run_r1.py                                      ║
║                                                           ║
║  2. Open web interface:                                   ║
║     http://localhost:8000/openclaw.html                 ║
║                                                           ║
║  3. Voice control:                                        ║
║     Say your wake word to start talking                 ║
║                                                           ║
║  4. Telegram bot:                                         ║
║     Message your bot on Telegram                        ║
║                                                           ║
║  API Endpoints:                                           ║
║     GET  /openclaw/status         - System status        ║
║     POST /openclaw/chat           - Chat with assistant  ║
║     GET  /openclaw/persona        - Get persona          ║
║     POST /openclaw/persona        - Update persona       ║
║     POST /openclaw/voice/start    - Start voice mode     ║
║     POST /openclaw/proactive/     - Reminders, briefings ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
""")


def main():
    """Main setup function"""
    import sys

    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║   🦞 OpenClaw for R1 - Setup                              ║
    ║                                                           ║
    ║   Your local-first personal AI assistant                  ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """)

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "env":
            create_env_template()
        elif command == "persona":
            setup_persona()
        elif command == "help":
            show_quickstart()
        else:
            print(f"Unknown command: {command}")
            print("Available commands: env, persona, help")
    else:
        # Full setup
        create_env_template()
        print()
        setup_persona()
        print()
        show_quickstart()


if __name__ == "__main__":
    main()
