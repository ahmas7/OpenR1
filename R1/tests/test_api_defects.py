import importlib
import os
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient


def _reload_module(module_name: str):
    module = importlib.import_module(module_name)
    return importlib.reload(module)


def test_server_importable():
    """Verify that server.py is completely importable directly."""
    # Ensure legacy routes is disabled for pure core test
    with patch.dict(os.environ, {"R1_ENABLE_LEGACY_ROUTES": "false"}):
        server = _reload_module("R1.api.server")
        assert server.app is not None
        assert getattr(server, "brain", "not_found") == "not_found", "Stale global `brain` should be removed"

def test_legacy_importable():
    """Verify that legacy.py is importable if enabled."""
    with patch.dict(os.environ, {"R1_ENABLE_LEGACY_ROUTES": "true"}):
        legacy = _reload_module("R1.api.legacy")
        assert legacy.legacy_router is not None

def test_chat_schema_response():
    """Verify that /chat correctly has `provider` and not `ai` inline with schemas."""
    with patch.dict(os.environ, {"R1_ENABLE_LEGACY_ROUTES": "false"}):
        server = _reload_module("R1.api.server")
        with patch.object(server, "get_runtime") as mock_get_runtime:
            mock_rt = AsyncMock()
            mock_rt.initialize = AsyncMock()
            # Runtime now returns `provider` and tests that server.py schema maps it correctly
            mock_rt.chat = AsyncMock(return_value={"response": "test defect", "session_id": "sess01", "provider": "mock_gguf"})
            mock_get_runtime.return_value = mock_rt
            client = TestClient(server.app)
            
            response = client.post("/chat", json={"message": "hello context", "session_id": "sess01"})
            assert response.status_code == 200
            data = response.json()
            assert "provider" in data
            assert data["provider"] == "mock_gguf"
            assert "ai" not in data


def test_no_duplicate_core_routes_in_legacy_router():
    """Verify that legacy.py does not define routes owned by the core server."""
    with patch.dict(os.environ, {"R1_ENABLE_LEGACY_ROUTES": "true"}):
        legacy = _reload_module("R1.api.legacy")

        legacy_paths = {r.path for r in legacy.legacy_router.routes if hasattr(r, "path")}
        core_paths = {
            "/", "/chat", "/agent/run", "/agent/status/{session_id}",
            "/agent/stop/{session_id}", "/health", "/providers",
            "/tools", "/skills", "/sessions", "/memory/{session_id}",
            "/v1/health", "/v1/providers", "/v1/tools", "/v1/skills",
            "/v1/chat", "/v1/agent/run", "/v1/agent/status/{session_id}",
            "/v1/agent/stop/{session_id}", "/v1/memory/{session_id}",
            "/v1/skills/load", "/v1/skills/unload", "/v1/skills/reload",
            "/v1/skills/invoke", "/v1/skills/validate",
        }

        overlap = legacy_paths.intersection(core_paths)
        assert not overlap, f"Duplicate routes found in legacy.py: {sorted(overlap)}"


def test_enabling_legacy_routes_does_not_duplicate_core_path_methods():
    """Verify that enabling legacy routes does not create duplicate path+method ownership for core routes."""
    with patch.dict(os.environ, {"R1_ENABLE_LEGACY_ROUTES": "true"}):
        server = _reload_module("R1.api.server")

        core_route_methods = {
            ("/", "GET"),
            ("/health", "GET"),
            ("/providers", "GET"),
            ("/tools", "GET"),
            ("/skills", "GET"),
            ("/chat", "POST"),
            ("/agent/run", "POST"),
            ("/agent/status/{session_id}", "GET"),
            ("/agent/stop/{session_id}", "POST"),
            ("/sessions", "GET"),
            ("/memory/{session_id}", "GET"),
            ("/v1/health", "GET"),
            ("/v1/providers", "GET"),
            ("/v1/tools", "GET"),
            ("/v1/skills", "GET"),
            ("/v1/chat", "POST"),
            ("/v1/agent/run", "POST"),
            ("/v1/agent/status/{session_id}", "GET"),
            ("/v1/agent/stop/{session_id}", "POST"),
            ("/v1/memory/{session_id}", "GET"),
            ("/v1/skills/load", "POST"),
            ("/v1/skills/unload", "POST"),
            ("/v1/skills/reload", "POST"),
            ("/v1/skills/invoke", "POST"),
            ("/v1/skills/validate", "POST"),
        }

        route_counts = {}
        for route in server.app.routes:
            if not hasattr(route, "path"):
                continue
            for method in getattr(route, "methods", set()):
                key = (route.path, method)
                route_counts[key] = route_counts.get(key, 0) + 1

        duplicated = {key: count for key, count in route_counts.items() if key in core_route_methods and count > 1}
        assert not duplicated, f"Duplicate core path/method pairs found: {duplicated}"

