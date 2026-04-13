"""
R1 AI ASSISTANT - CONFIGURATION
Powered by local GGUF by default
"""
from pathlib import Path
import os

# ==================== PATHS ====================
CONFIG_DIR = Path(__file__).parent.absolute()
R1_ROOT = CONFIG_DIR.parent
PROJECT_ROOT = R1_ROOT.parent

DATA_DIR = R1_ROOT / "data"
LOGS_DIR = R1_ROOT / "data" / "logs"

DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ==================== IDENTITY ====================
APP_NAME = "R1"
VERSION = "1.0.0"
DESCRIPTION = "Production AI Assistant - Powered by a local GGUF model"

# ==================== AI CONFIG ====================
AI_CONFIG = {
    "provider": os.getenv("R1_PROVIDER", "gguf"),
    "model": os.getenv("R1_MODEL", os.getenv("GGUF_MODEL_PATH", str(PROJECT_ROOT / "models" / "GLM-4.7-Flash-Uncen-Hrt-NEO-CODE-MAX-imat-D_AU-IQ4_XS.gguf"))),
    "endpoint": "http://localhost:11434",
    "temperature": 0.7,
    "max_tokens": 500,
    "context_messages": 10,
    "system_prompt": """You are R1, an advanced AI assistant.

You are helpful, intelligent, and concise. Keep responses short."""
}

# ==================== DATABASE ====================
DATABASE_CONFIG = {
    "path": DATA_DIR / "r1_memory.db",
}

# ==================== API ====================
API_CONFIG = {
    "host": "0.0.0.0",
    "port": 8000,
    "cors_origins": ["*"],
}

# ==================== VOICE ====================
VOICE_CONFIG = {
    "enabled": True,
    "language": "en",
    "rate": 150,
}
