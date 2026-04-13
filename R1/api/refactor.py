import os
import re

server_path = r"e:\MYAI\R1\R1\api\server.py"
legacy_path = r"e:\MYAI\R1\R1\api\legacy.py"

with open(server_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# The clean, new API is in lines 1 to 479.
# The legacy endpoints, old startup event, and old logic start from line 480 (`@app.on_event("startup")`).
core_lines = lines[:479]
legacy_lines_raw = lines[479:]

# We will remove the duplicated middleware and root definition in legacy lines (around 699-712 of original, which is 220-233 of legacy_lines_raw)
# Actually, since legacy.py is just a router, we should replace `@app.` with `@legacy_router.` throughout it.

legacy_content = """import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse

legacy_router = APIRouter()
logger = logging.getLogger("R1.Legacy")

# Legacy config
OLLAMA_ENDPOINT = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434")
DEFAULT_GGUF_PATH = os.getenv(
    "GGUF_MODEL_PATH",
    str(Path(__file__).resolve().parents[2] / "models" / "GLM-4.7-Flash-Uncen-Hrt-NEO-CODE-MAX-imat-D_AU-IQ4_XS.gguf"),
)
OLLAMA_MODEL = os.getenv("R1_MODEL", DEFAULT_GGUF_PATH)
ACTIVE_PROVIDER = os.getenv("R1_PROVIDER", "gguf")
DATA_DIR = Path.home() / ".r1"
R1_CORE_AVAILABLE = True

# Legacy global state
brain = None
memory = None
skills = None
enhanced_skills = None
cron_manager = None
webhook_manager = None
gateway = None
LAST_PROVIDER_ERROR = None

"""

for line in legacy_lines_raw:
    # Skip middleware and WEB_DIR redefinitions
    if line.startswith("app.add_middleware") or line.strip() == "CORSMiddleware," or "allow_origins" in line or "allow_methods" in line or "allow_headers" in line or line.strip() == ")" or line.startswith("WEB_DIR ="):
        # We don't skip everything blindly, just let it be or comment it out
        pass
    
    # Replace @app. with @legacy_router.
    line = line.replace("@app.", "@legacy_router.")
    legacy_content += line

# Write legacy.py
with open(legacy_path, "w", encoding="utf-8") as f:
    f.write(legacy_content)

# Update server.py to include the legacy router
server_new_content = "".join(core_lines)
server_new_content += """
# ==================== LEGACY ROUTES ====================
try:
    from .legacy import legacy_router
    app.include_router(legacy_router)
    logger.info("Legacy routes loaded successfully.")
except Exception as e:
    logger.warning(f"Could not load legacy routes: {e}")

"""

with open(server_path, "w", encoding="utf-8") as f:
    f.write(server_new_content)

print(f"Refactor complete. legacy.py created with {len(legacy_content.splitlines())} lines. server.py updated to {len(server_new_content.splitlines())} lines.")
