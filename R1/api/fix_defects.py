import os

server_py = r"e:\MYAI\R1\R1\api\server.py"
legacy_py = r"e:\MYAI\R1\R1\api\legacy.py"

with open(server_py, "r", encoding="utf-8") as f:
    server_lines = f.readlines()

with open(legacy_py, "r", encoding="utf-8") as f:
    legacy_lines = f.readlines()

# 1. Extract the legacy imports from server.py (lines 47 to 91 roughly)
start_idx = -1
end_idx = -1
for i, line in enumerate(server_lines):
    if "# Optional imports for legacy routes" in line:
        start_idx = i
    if "# Import schemas" in line:
        end_idx = i
        break

legacy_imports = server_lines[start_idx:end_idx]

# Remove legacy imports and legacy globals from server.py
# Legacy globals are around:
# brain = None
# ...
# LAST_PROVIDER_ERROR = None
new_server_lines = []
skip_globals = False
for i, line in enumerate(server_lines):
    if line.startswith("brain = None"):
        skip_globals = True
    if skip_globals and line.startswith("LAST_PROVIDER_ERROR = None"):
        skip_globals = False
        continue
    
    if skip_globals:
        continue
    
    # Filter out empty line after LAST_PROVIDER_ERROR sometimes
    if line.strip() == "# Legacy global state for backward compatibility":
        continue
        
    if start_idx <= i < end_idx:
        continue
        
    # Remove the broad try/except at the bottom
    if "# ==================== LEGACY ROUTES ====================" in line:
        break
        
    new_server_lines.append(line)

new_server_lines.append("# ==================== LEGACY ROUTES ====================\n")
new_server_lines.append("ENABLE_LEGACY_ROUTES = os.getenv(\"R1_ENABLE_LEGACY_ROUTES\", \"false\").lower() == \"true\"\n")
new_server_lines.append("\n")
new_server_lines.append("if ENABLE_LEGACY_ROUTES:\n")
new_server_lines.append("    from .legacy import legacy_router\n")
new_server_lines.append("    app.include_router(legacy_router)\n")
new_server_lines.append("    logger.info(\"Legacy routes enabled and loaded.\")\n")
new_server_lines.append("else:\n")
new_server_lines.append("    logger.info(\"Legacy routes are disabled via R1_ENABLE_LEGACY_ROUTES.\")\n")

with open(server_py, "w", encoding="utf-8") as f:
    f.writelines(new_server_lines)

# 2. Inject legacy imports into legacy.py
# Paste them after the router definition or initial imports
insert_idx = 0
for i, line in enumerate(legacy_lines):
    if "legacy_router = APIRouter()" in line:
        insert_idx = i + 2
        break

new_legacy_lines = legacy_lines[:insert_idx] + ["\n"] + legacy_imports + ["\n"] + legacy_lines[insert_idx:]

# 3. Remove /v1/* duplicates and /chat from legacy.py
final_legacy_lines = []
skip_block = False
brace_count = 0
for line in new_legacy_lines:
    if line.startswith("@legacy_router.get(\"/v1/") or line.startswith("@legacy_router.post(\"/v1/"):
        skip_block = True
    elif line.startswith("@legacy_router.post(\"/chat\")"):
        skip_block = True
        
    if skip_block:
        if line.startswith("@legacy_router.") and not (line.startswith("@legacy_router.get(\"/v1/") or line.startswith("@legacy_router.post(\"/v1/") or line.startswith("@legacy_router.post(\"/chat\")")):
            skip_block = False
            
    if not skip_block:
        final_legacy_lines.append(line)

# Clean up # ==================== R1 V1 CORE ENDPOINTS ==================== boundaries
final_legacy_lines2 = []
for line in final_legacy_lines:
    if "R1 V1 CORE ENDPOINTS" in line:
        continue
    final_legacy_lines2.append(line)

with open(legacy_py, "w", encoding="utf-8") as f:
    f.writelines(final_legacy_lines2)

print("Applied fixes to server.py and legacy.py")
