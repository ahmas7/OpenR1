import asyncio

from R1.config.settings import settings
from R1.model import get_model_manager
from R1.tools.registry import ToolRegistry
from R1.tools.base import BaseTool, ToolResult, SafetyLevel


class DangerousTool(BaseTool):
    def __init__(self):
        super().__init__("danger", "dangerous tool", safety=SafetyLevel.DANGEROUS)

    @property
    def input_schema(self):
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs):
        return ToolResult(success=True, output="ok", tool_name=self.name)


def test_model_manager_dev_stub():
    settings.provider = "stub"
    settings.dev_mode = True

    mgr = get_model_manager()
    asyncio.run(mgr.initialize())
    assert mgr.active_provider() == "stub"


def test_tool_registry_policy_confirm():
    settings.tool_policy = "confirm"

    registry = ToolRegistry()
    registry.register(DangerousTool())

    denied = asyncio.run(registry.execute("danger", {}))
    assert not denied.success

    allowed = asyncio.run(registry.execute("danger", {"_confirm": True}))
    assert allowed.success


def test_agent_loop_done_signal(tmp_path, monkeypatch):
    from R1.agent.loop import AgentLoop
    from R1.agent.state import AgentState, AgentStatus
    from R1.model.providers.base import ModelResponse
    from R1.memory import store as memory_store

    settings.memory_db_path = str(tmp_path / "memory.db")
    memory_store._memory_store = None

    class FakeModel:
        async def chat(self, messages, **kwargs):
            return ModelResponse(content="DONE: ok", model="stub")

    monkeypatch.setattr("R1.agent.loop.get_model_manager", lambda: FakeModel())

    state = AgentState(session_id="test")
    loop = AgentLoop(state)
    asyncio.run(loop.start("say done"))

    assert state.status == AgentStatus.DONE
