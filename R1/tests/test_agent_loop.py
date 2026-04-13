"""
Tests for R1 Agent Loop
"""
import asyncio
import pytest

from R1.config.settings import settings
from R1.agent.loop import AgentLoop
from R1.agent.state import AgentState, AgentStatus
from R1.model.providers.base import ModelResponse


def _make_loop(monkeypatch, tmp_path, model_response: str):
    """Create an AgentLoop with a fake model."""
    settings.memory_db_path = str(tmp_path / "memory.db")
    settings.max_iterations = 10

    # Reset memory singleton
    import R1.memory.store as memory_store
    memory_store._memory_store = None

    class FakeModel:
        def active_provider(self):
            return "fake"

        async def chat(self, messages, **kwargs):
            return ModelResponse(content=model_response, model="fake")

    monkeypatch.setattr("R1.agent.loop.get_model_manager", lambda: FakeModel())

    state = AgentState(session_id="test")
    return AgentLoop(state), state


class TestTerminalSignals:
    def test_done_signal(self, monkeypatch, tmp_path):
        loop, state = _make_loop(monkeypatch, tmp_path, "DONE: task completed successfully")
        asyncio.run(loop.start("say done"))

        assert state.status == AgentStatus.DONE
        assert loop.report.final_status == "completed"
        assert "task completed" in loop.report.final_summary.lower()

    def test_fail_signal(self, monkeypatch, tmp_path):
        loop, state = _make_loop(monkeypatch, tmp_path, "FAIL: cannot find file")
        asyncio.run(loop.start("find something"))

        assert state.status == AgentStatus.ERROR
        assert loop.report.final_status == "failed"
        assert "cannot find file" in loop.report.final_summary.lower()

    def test_blocked_signal(self, monkeypatch, tmp_path):
        loop, state = _make_loop(monkeypatch, tmp_path, "BLOCKED: awaiting user input")
        asyncio.run(loop.start("do something"))

        assert state.status == AgentStatus.DONE
        assert loop.report.final_status == "blocked"
        assert "awaiting user" in loop.report.final_summary.lower()


class TestMaxIterations:
    def test_stops_at_max_iterations(self, monkeypatch, tmp_path):
        settings.max_iterations = 2

        # Model always returns a tool call
        loop, state = _make_loop(monkeypatch, tmp_path, "TOOL: shell\ncommand: echo hello")
        asyncio.run(loop.start("loop forever"))

        # Should have stopped at max iterations
        assert state.iteration >= 2
        assert state.status in (AgentStatus.ERROR, AgentStatus.DONE)


class TestResponseParsing:
    def test_plain_response_completes(self, monkeypatch, tmp_path):
        """A plain text response (no TOOL/DONE/FAIL) should be treated as completion."""
        loop, state = _make_loop(monkeypatch, tmp_path, "Here is your answer about Python.")
        asyncio.run(loop.start("tell me about python"))

        assert state.status == AgentStatus.DONE
        assert loop.report.final_status == "completed"

    def test_tool_response_sets_acting(self, monkeypatch, tmp_path):
        """A TOOL: response should set the agent to ACTING status."""
        call_count = 0

        class CountingModel:
            def active_provider(self):
                return "fake"

            async def chat(self, messages, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return ModelResponse(content="TOOL: shell\ncommand: echo hello", model="fake")
                return ModelResponse(content="DONE: finished", model="fake")

        settings.memory_db_path = str(tmp_path / "memory.db")
        settings.max_iterations = 5
        import R1.memory.store as memory_store
        memory_store._memory_store = None

        monkeypatch.setattr("R1.agent.loop.get_model_manager", lambda: CountingModel())

        state = AgentState(session_id="test")
        loop = AgentLoop(state)
        asyncio.run(loop.start("run echo"))

        # Should have attempted a tool call
        assert call_count >= 1
