import asyncio

from R1.agent.runtime import Runtime
from R1.tool_chaining import ToolChainingEngine
from R1.tools import get_tool_registry


def test_runtime_detects_actionable_messages():
    runtime = Runtime()
    assert runtime._should_auto_execute("list files in .")
    assert runtime._should_auto_execute("please open notepad and type hello")
    assert not runtime._should_auto_execute("what is your status")


def test_tool_chaining_generates_executable_filesystem_plan():
    engine = ToolChainingEngine(get_tool_registry())
    steps = engine._generate_plan("list files in .")
    assert steps
    assert steps[0]["tool"] == "filesystem"
    assert steps[0]["action"] == "list"
    assert steps[0]["params"]["path"] == "."


def test_tool_chaining_runs_filesystem_goal():
    engine = ToolChainingEngine(get_tool_registry())

    async def run():
        task = await engine.run_goal("list files in .", session_id="test-chat-exec")
        assert task.status.value == "completed"
        assert task.steps[0].success is True
        assert isinstance(task.steps[0].result.get("output"), list)

    asyncio.run(run())
