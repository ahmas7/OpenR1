# R1 Project Structure

## Directory Layout

```
R1/                          # Main project root
├── .cache/                  # Cache files (pytest, ruff, etc.)
├── .venv/                   # Python virtual environment
├── .vscode/                 # VS Code settings
├── R1/                      # Main Python package
│   ├── agent/               # Agent runtime, loop, session management
│   ├── api/                 # FastAPI server, routes, schemas
│   ├── config/              # Configuration management
│   ├── core/                # Core abstractions and interfaces
│   ├── data/                # Application data files
│   ├── gui/                 # Desktop GUI components
│   ├── integrations/        # Third-party integrations (Discord, Slack, Telegram)
│   ├── jobs/                # Background job system
│   ├── memory/              # Memory storage, embeddings, retrieval
│   ├── model/               # Model providers and interfaces
│   ├── packs/               # Feature packs/plugins
│   ├── scripts/             # Launch and utility scripts
│   ├── skills/              # AI skills system
│   ├── stack/               # Tech stack configuration
│   ├── tests/               # Test files
│   ├── tools/               # Tool implementations
│   ├── web/                 # Web frontend assets
│   └── workspace_skills/    # User-customizable skills
├── data/                    # External data files (YAML configs, etc.)
├── docs/                    # Documentation
├── logs/                    # Application logs
├── models/                  # ML model files
├── Real-ESRGAN/             # Image upscaling submodule
└── TTS/                     # Text-to-speech submodule
```

## Key Files

| File | Purpose |
|------|---------|
| `R1/scripts/run_r1.py` | Main server launcher |
| `R1/scripts/gui_launcher.py` | Desktop GUI launcher |
| `R1/scripts/verify_r1.py` | Health check script |
| `R1/scripts/openclaw_setup.py` | OpenClaw configuration |
| `.env` | Environment variables (not committed) |
| `.gitignore` | Git ignore rules |
| `.projectignore` | AI assistant ignore rules |

## Quick Start

```bash
# Start the server
python R1/scripts/run_r1.py

# Launch desktop GUI
python R1/scripts/gui_launcher.py

# Run health checks
python R1/scripts/verify_r1.py
```

## Architecture Overview

- **Agent Layer** (`R1/agent/`): Runtime loop, session management, state
- **API Layer** (`R1/api/`): REST endpoints, request/response schemas
- **Memory System** (`R1/memory/`, `R1/core/memory.py`): Short-term and persistent memory
- **Skills System** (`R1/skills/`): Extensible capability framework
- **Tools** (`R1/tools/`): Executable actions (shell, filesystem, browser)
- **Integrations** (`R1/integrations/`): Chat platforms, external services
