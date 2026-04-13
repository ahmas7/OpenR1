"""
R1 v1 - Configuration Settings
"""
import os
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(env_path)


@dataclass
class Settings:
    # Provider settings
    provider: str = os.getenv("R1_PROVIDER", "ollama")
    model: str = os.getenv("R1_MODEL", "llama3.2:3b")
    gguf_model_path: str = os.getenv("GGUF_MODEL_PATH", "")
    ollama_endpoint: str = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434")
    include_reasoning: bool = os.getenv("R1_INCLUDE_REASONING", "false").lower() == "true"

    # AirLLM settings (run 70B+ models on 4GB+ VRAM)
    airllm_model_path: str = os.getenv("AIRLLM_MODEL_PATH", "")
    airllm_compression: str = os.getenv("AIRLLM_COMPRESSION", "")  # 4bit, 8bit, or empty
    airllm_layer_shards_path: str = os.getenv("AIRLLM_LAYER_SHARDS_PATH", "")
    airllm_hf_token: str = os.getenv("AIRLLM_HF_TOKEN", "")
    airllm_max_length: int = int(os.getenv("AIRLLM_MAX_LENGTH", "4096"))

    # Operator identity
    user_name: str = os.getenv("R1_USER_NAME", "")

    # Voice / wake word
    wake_word: str = os.getenv("R1_WAKE_WORD", "AR1")
    wake_enabled: bool = os.getenv("R1_WAKE_ENABLED", "true").lower() == "true"
    wake_open_ui: bool = os.getenv("R1_WAKE_OPEN_UI", "true").lower() == "true"
    voice_gender: str = os.getenv("R1_VOICE_GENDER", "male")
    
    # API settings
    host: str = os.getenv("R1_HOST", "0.0.0.0")
    port: int = int(os.getenv("R1_PORT", "8000"))
    
    # Memory settings
    memory_db_path: str = os.getenv("R1_MEMORY_DB", str(Path.home() / ".r1" / "memory.db"))
    ambient_capture_screen: bool = os.getenv("R1_AMBIENT_CAPTURE_SCREEN", "false").lower() == "true"
    ambient_context_enabled: bool = os.getenv("R1_AMBIENT_CONTEXT_ENABLED", "true").lower() == "true"
    
    # Execution settings
    max_iterations: int = 50
    tool_timeout: int = 30
    model_timeout: int = 60
    tool_retries: int = int(os.getenv("R1_TOOL_RETRIES", "1"))

    # Jobs / background work
    jobs_enabled: bool = os.getenv("R1_JOBS_ENABLED", "true").lower() == "true"
    heartbeat_interval: int = int(os.getenv("R1_HEARTBEAT_SECONDS", "60"))
    reminders_interval: int = int(os.getenv("R1_REMINDERS_SECONDS", "300"))
    reminders_file: str = os.getenv("R1_REMINDERS_FILE", str(Path.home() / ".r1" / "reminders.json"))

    # Tool safety policy
    tool_policy: str = os.getenv("R1_TOOL_POLICY", "confirm")  # allow | confirm | deny
    tool_auto_confirm: bool = os.getenv("R1_TOOL_AUTO_CONFIRM", "false").lower() == "true"

    # Audit log rotation
    audit_max_bytes: int = int(os.getenv("R1_AUDIT_MAX_BYTES", "5242880"))  # 5MB
    audit_max_files: int = int(os.getenv("R1_AUDIT_MAX_FILES", "3"))
    
    # Dev mode (allows stub provider)
    dev_mode: bool = os.getenv("R1_DEV_MODE", "false").lower() == "true"


settings = Settings()
