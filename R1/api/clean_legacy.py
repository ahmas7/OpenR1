import os

legacy_py = r"e:\MYAI\R1\R1\api\legacy.py"

with open(legacy_py, "r", encoding="utf-8") as f:
    lines = f.readlines()

# We need to remove:
# 1. app.add_middleware(...) block
# 2. @legacy_router.get("/")
# 3. @legacy_router.get("/health")
# 4. @legacy_router.get("/providers")
# 5. @legacy_router.get("/tools")
# 6. @legacy_router.get("/skills")
# 7. @legacy_router.get("/sessions")
# 8. @legacy_router.post("/chat")
# (anything that server.py natively handles at the root)

routes_to_remove = [
    "@legacy_router.get(\"/\")",
    "@legacy_router.get(\"/health\")",
    "@legacy_router.get(\"/providers\")",
    "@legacy_router.get(\"/tools\")",
    "@legacy_router.get(\"/skills\")",
    "@legacy_router.get(\"/sessions\")",
]

new_lines = []
skip = False
brace_count = 0
for i, line in enumerate(lines):
    if line.startswith("app.add_middleware("):
        skip = True
        
    if any(line.startswith(r) for r in routes_to_remove):
        skip = True
        
    if skip:
        if line.startswith("@legacy_router.") and not any(line.startswith(r) for r in routes_to_remove):
            skip = False
            
    if not skip:
        new_lines.append(line)

with open(legacy_py, "w", encoding="utf-8") as f:
    f.writelines(new_lines)
print("Cleaned up legacy.py")
