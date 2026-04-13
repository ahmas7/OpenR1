# OpenClaw for R1

A personal AI assistant integration for R1, inspired by OpenClaw. Your local-first AI that actually does things.

## Features

### 🎤 Voice Control
- **Continuous Voice Conversation**: Natural back-and-forth dialogue
- **Wake Word Detection**: Say "hey r1" (or customize it) to activate
- **Text-to-Speech**: Your assistant speaks responses aloud
- **Voice Commands**: Quick commands for time, weather, briefings

### 💬 Chat Integrations
- **Telegram Bot**: Message your assistant from anywhere
- **WhatsApp**: Coming soon
- **Discord**: Coming soon
- **Web Interface**: Beautiful chat UI at `/openclaw.html`

### 🧠 Persistent Memory
- Learns your name, preferences, and habits
- Extracts facts from conversations
- Remembers important dates
- Maintains conversation history

### ⏰ Proactive Agent
- **Morning Briefings**: Daily summary at your chosen time
- **Reminders**: "Remind me to call mom in 30 minutes"
- **Check-ins**: Reaches out after periods of inactivity
- **Heartbeat**: Periodic status checks

### 🛠️ Built-in Skills
- **Email (Gmail)**: Send and check emails
- **Calendar**: Manage events and schedule
- **Todos**: Task management with priorities
- **Web Search**: DuckDuckGo integration
- **Weather**: Current conditions and forecasts
- **Spotify**: Control music playback
- **File Manager**: Read, write, search files

## Quick Start

### 1. Configure Environment

```bash
cd "E:/MYAI/R1"
python openclaw_setup.py
```

Or manually edit `.env`:

```bash
# Assistant Settings
ASSISTANT_NAME=R1
USER_NAME=YourName
WAKE_WORD=hey r1
VOICE_ENABLED=true
PROACTIVE_ENABLED=true
BRIEFING_TIME=08:00

# Telegram (optional)
TELEGRAM_BOT_TOKEN=your_token_here

# Gmail (optional)
GMAIL_USER=your.email@gmail.com
GMAIL_APP_PASSWORD=your_app_password

# Weather (optional)
OPENWEATHER_API_KEY=your_api_key
```

### 2. Start the Server

```bash
python run_r1.py
```

### 3. Access OpenClaw

- **Web Interface**: http://localhost:8000/openclaw.html
- **API**: http://localhost:8000/openclaw/
- **Telegram**: Message your bot

## API Endpoints

### Status
```bash
GET /openclaw/status
GET /openclaw/welcome
```

### Chat
```bash
POST /openclaw/chat
{
  "message": "Hello!",
  "session_id": "optional-session-id"
}
```

### Persona Management
```bash
GET /openclaw/persona
POST /openclaw/persona
{
  "name": "My Assistant",
  "user_name": "John",
  "voice_enabled": true,
  "proactive_enabled": true
}
```

### Voice Control
```bash
GET /openclaw/voice/status
POST /openclaw/voice/start
POST /openclaw/voice/stop
POST /openclaw/voice/wake/enable
POST /openclaw/voice/wake/disable
```

### Reminders & Proactive
```bash
GET /openclaw/proactive/status
POST /openclaw/proactive/reminder
{
  "title": "Call mom",
  "when": "in 30 minutes",
  "recurrence": "daily"
}
GET /openclaw/proactive/reminders
POST /openclaw/proactive/briefing
```

### Skills
```bash
GET /openclaw/skills
POST /openclaw/skills/execute
{
  "command": "what's the weather in New York"
}
```

## Commands You Can Say

### General
- "What can you do?"
- "What's my name?"
- "Remember that I like coffee"

### Voice Only
- "What's the time?"
- "What's today's date?"
- "Give me my briefing"
- "Stop listening" (to exit voice mode)

### Chat/Any Interface
- "Send email to john@example.com about meeting"
- "Add event team meeting tomorrow at 2pm"
- "Add todo buy groceries"
- "What's on my calendar?"
- "Search for Python tutorials"
- "What's the weather?"

## Architecture

```
R1/
├── openclaw.py              # Main coordinator
├── openclaw_persona.py      # Persona & memory
├── openclaw_voice.py        # Voice conversation
├── openclaw_telegram.py     # Telegram bot
├── openclaw_proactive.py    # Heartbeats & reminders
├── openclaw_skills.py       # Built-in skills
├── api/
│   ├── server.py            # Main FastAPI server
│   └── openclaw_routes.py   # API routes
└── web/
    └── openclaw.html        # Web interface
```

## Customization

### Change Assistant Name
```python
from R1.openclaw_persona import persona
persona.set_name("Jarvis")
```

### Add Custom Skill
```python
from R1.openclaw_skills import skill_registry

async def my_custom_skill(args):
    return "Skill executed!"

skill_registry.commands["custom command"] = my_custom_skill
```

### Schedule Custom Task
```python
from R1.openclaw_proactive import proactive_agent

proactive_agent.add_reminder("Custom task", "in 1 hour")
```

## Troubleshooting

### Voice Not Working
1. Check microphone permissions
2. Install dependencies: `pip install SpeechRecognition pyttsx3`
3. Check voice status: `GET /openclaw/voice/status`

### Telegram Bot Not Responding
1. Verify TELEGRAM_BOT_TOKEN in .env
2. Check bot is started: `GET /openclaw/telegram/status`
3. Message @BotFather to check bot status

### Reminders Not Working
1. Ensure PROACTIVE_ENABLED=true
2. Check R1_JOBS_ENABLED=true
3. Verify proactive agent is running: `GET /openclaw/proactive/status`

## Privacy & Security

- **Local-first**: Your data stays on your machine
- **Private by default**: No data sent to external services unless configured
- **Encrypted storage**: Facts and memories stored locally
- **You control the AI**: Fully open source and hackable

## Contributing

This is an open extension to R1. Feel free to:
- Add new skills
- Integrate new chat platforms
- Improve voice recognition
- Enhance the web interface

## License

Same as R1 - MIT License

---

**OpenClaw for R1** - Your AI assistant that actually does things.
