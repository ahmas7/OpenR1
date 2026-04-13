import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

# Mock out heavy imports or env vars if needed before importing app
with patch('R1.api.server.load_dotenv'):
    from R1.api.server import app

client = TestClient(app)

@pytest.fixture
def mock_runtime():
    with patch('R1.api.server.get_runtime') as mock_get_runtime:
        mock_rt = AsyncMock()
        mock_rt.initialize = AsyncMock()
        mock_rt.chat = AsyncMock(return_value={"response": "test response", "session_id": "session123", "provider": "mock"})
        mock_rt.run_agent = AsyncMock(return_value={"success": True, "session_id": "agent123"})
        mock_rt.get_session_status = MagicMock(return_value={"status": "running", "session_id": "agent123", "goal": "test", "plan": {}, "iteration": 1})
        mock_rt.stop_session = AsyncMock()
        
        mock_session_manager = MagicMock()
        mock_session_manager.list_sessions.return_value = {"agent123": "running", "session123": "idle"}
        mock_rt.session_manager = mock_session_manager
        
        mock_get_runtime.return_value = mock_rt
        yield mock_rt

@pytest.fixture
def mock_model_manager():
    with patch('R1.api.server.get_model_manager') as mock_get_model_mgr:
        mock_mgr = AsyncMock()
        mock_mgr.health = AsyncMock(return_value={"healthy": True, "details": "ok"})
        mock_mgr.active_provider = MagicMock(return_value="mock_provider")
        
        mock_provider_info = MagicMock()
        mock_provider_info.id = "mock_provider"
        mock_provider_info.name = "Mock Provider"
        mock_provider_info.healthy = True
        mock_provider_info.reason = None
        mock_mgr.get_providers_status = AsyncMock(return_value=[mock_provider_info])
        
        mock_get_model_mgr.return_value = mock_mgr
        yield mock_mgr

@pytest.fixture
def mock_tool_registry():
    with patch('R1.api.server.get_tool_registry') as mock_get_registry:
        mock_registry = MagicMock()
        mock_tool = MagicMock()
        mock_tool.name = "test_tool"
        mock_registry.list_tools.return_value = [mock_tool]
        mock_get_registry.return_value = mock_registry
        yield mock_registry

@pytest.fixture
def mock_skills_runtime():
    with patch('R1.api.server.get_skills_runtime') as mock_get_skills:
        mock_runtime = AsyncMock()
        mock_runtime.initialize = AsyncMock()
        mock_runtime.discover_skills = MagicMock(return_value=[{"name": "test_skill"}])
        mock_get_skills.return_value = mock_runtime
        yield mock_runtime

def test_health_endpoint(mock_model_manager):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["provider"] == "mock_provider"
    assert data["model_health"]["healthy"] is True

def test_providers_endpoint(mock_model_manager):
    response = client.get("/providers")
    assert response.status_code == 200
    data = response.json()
    assert data["active_provider"] == "mock_provider"
    assert len(data["providers"]) == 1
    assert data["providers"][0]["id"] == "mock_provider"

def test_tools_endpoint(mock_tool_registry):
    response = client.get("/tools")
    assert response.status_code == 200
    data = response.json()
    assert "test_tool" in data["tools"]

def test_skills_endpoint(mock_skills_runtime):
    response = client.get("/skills")
    assert response.status_code == 200
    data = response.json()
    assert len(data["skills"]) == 1
    assert data["skills"][0]["name"] == "test_skill"

def test_chat_endpoint(mock_runtime):
    response = client.post("/chat", json={"message": "hello", "session_id": "session123"})
    assert response.status_code == 200
    data = response.json()
    assert data["response"] == "test response"
    assert data["session_id"] == "session123"
    assert data["provider"] == "mock"
    mock_runtime.chat.assert_called_once_with("hello", "session123")

def test_agent_run_endpoint(mock_runtime):
    response = client.post("/agent/run", json={"goal": "test goal", "session_id": "agent123"})
    assert response.status_code == 200
    mock_runtime.run_agent.assert_called_once_with("test goal", "agent123")

def test_agent_status_endpoint(mock_runtime):
    response = client.get("/agent/status/agent123")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert data["session_id"] == "agent123"
    mock_runtime.get_session_status.assert_called_once_with("agent123")

def test_agent_stop_endpoint(mock_runtime):
    response = client.post("/agent/stop/agent123")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    mock_runtime.stop_session.assert_called_once_with("agent123")

def test_list_sessions_endpoint(mock_runtime):
    response = client.get("/sessions")
    assert response.status_code == 200
    data = response.json()
    assert len(data["sessions"]) == 2
    session_ids = [s["session_id"] for s in data["sessions"]]
    assert "agent123" in session_ids
    assert "session123" in session_ids

