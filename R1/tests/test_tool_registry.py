"""
Tests for R1 Tool Registry
"""
import asyncio
import pytest

from R1.config.settings import settings
from R1.tools.base import BaseTool, ToolResult, SafetyLevel
from R1.tools.registry import ToolRegistry
from R1.tools.audit import ToolAuditLogger
from R1.tools.code_exec import CodeExecTool


class SafeTool(BaseTool):
    def __init__(self):
        super().__init__("safe_test", "a safe test tool", safety=SafetyLevel.SAFE)

    @property
    def input_schema(self):
        return {"type": "object", "properties": {"msg": {"type": "string"}}}

    async def execute(self, **kwargs):
        return ToolResult(success=True, output=f"ok: {kwargs.get('msg', '')}", tool_name=self.name)


class DangerousTool(BaseTool):
    def __init__(self):
        super().__init__("danger_test", "a dangerous test tool", safety=SafetyLevel.DANGEROUS)

    @property
    def input_schema(self):
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs):
        return ToolResult(success=True, output="danger executed", tool_name=self.name)


class FailingTool(BaseTool):
    def __init__(self):
        super().__init__("failing_test", "always fails", safety=SafetyLevel.SAFE)
        self.call_count = 0

    @property
    def input_schema(self):
        return {"type": "object", "properties": {}}

    @property
    def retry_max(self) -> int:
        return 2

    @property
    def retry_backoff_base(self) -> float:
        return 0.01  # Fast for testing

    async def execute(self, **kwargs):
        self.call_count += 1
        raise RuntimeError("always fails")


class RollbackTool(BaseTool):
    def __init__(self):
        super().__init__("rollback_test", "tool with rollback", safety=SafetyLevel.SAFE)
        self.rollback_called = False

    @property
    def input_schema(self):
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs):
        raise ValueError("non-retryable error")

    async def rollback(self, **kwargs):
        self.rollback_called = True
        return ToolResult(success=True, output="rolled back", tool_name=self.name)


class TestPolicyEnforcement:
    def test_safe_tool_allowed_on_any_policy(self):
        for policy in ("allow", "confirm", "deny"):
            settings.tool_policy = policy
            registry = ToolRegistry()
            registry.register(SafeTool())
            result = asyncio.run(registry.execute("safe_test", {"msg": "hello"}))
            assert result.success, f"Safe tool should be allowed with policy '{policy}'"

    def test_dangerous_tool_denied_by_confirm_policy(self):
        settings.tool_policy = "confirm"
        registry = ToolRegistry()
        registry.register(DangerousTool())
        result = asyncio.run(registry.execute("danger_test", {}))
        assert not result.success
        assert result.requires_confirmation

    def test_dangerous_tool_allowed_with_confirm(self):
        settings.tool_policy = "confirm"
        registry = ToolRegistry()
        registry.register(DangerousTool())
        result = asyncio.run(registry.execute("danger_test", {"_confirm": True}))
        assert result.success

    def test_dangerous_tool_denied_by_deny_policy(self):
        settings.tool_policy = "deny"
        registry = ToolRegistry()
        registry.register(DangerousTool())
        result = asyncio.run(registry.execute("danger_test", {}))
        assert not result.success

    def test_tool_not_found(self):
        registry = ToolRegistry()
        result = asyncio.run(registry.execute("nonexistent", {}))
        assert not result.success
        assert "not found" in result.error.lower()


class TestRetryLogic:
    def test_retries_on_failure(self):
        settings.tool_policy = "allow"
        registry = ToolRegistry()
        tool = FailingTool()
        registry.register(tool)
        result = asyncio.run(registry.execute("failing_test", {}))
        assert not result.success
        # Should have tried 3 times (1 initial + 2 retries)
        assert tool.call_count == 3


class TestRollback:
    def test_rollback_called_on_non_retryable_error(self):
        settings.tool_policy = "allow"
        registry = ToolRegistry()
        tool = RollbackTool()
        registry.register(tool)
        result = asyncio.run(registry.execute("rollback_test", {}))
        assert not result.success
        assert tool.rollback_called


class TestAuditLogging:
    def test_audit_logs_on_execution(self, tmp_path):
        settings.tool_policy = "allow"
        audit_path = tmp_path / "test_audit.jsonl"

        registry = ToolRegistry()
        registry._audit = ToolAuditLogger(str(audit_path))
        registry.register(SafeTool())

        asyncio.run(registry.execute("safe_test", {"msg": "audit test"}))

        entries = registry._audit.read_recent(10)
        assert len(entries) == 1
        assert entries[0]["tool_name"] == "safe_test"
        assert entries[0]["success"] is True

    def test_audit_logs_on_failure(self, tmp_path):
        settings.tool_policy = "allow"
        audit_path = tmp_path / "test_audit.jsonl"

        registry = ToolRegistry()
        registry._audit = ToolAuditLogger(str(audit_path))
        registry.register(FailingTool())

        asyncio.run(registry.execute("failing_test", {}))

        entries = registry._audit.read_recent(10)
        assert len(entries) >= 1
        # Last entry should be the final failure
        last = entries[-1]
        assert last["tool_name"] == "failing_test"
        assert last["success"] is False

    def test_audit_read_recent(self, tmp_path):
        audit_path = tmp_path / "test_audit.jsonl"
        audit = ToolAuditLogger(str(audit_path))

        from R1.tools.audit import ToolAuditEvent
        for i in range(5):
            audit.log(ToolAuditEvent(
                timestamp=f"2024-01-01T00:00:0{i}",
                tool_name=f"tool_{i}",
                arguments={},
                success=True,
                output_preview=f"output {i}"
            ))

        entries = audit.read_recent(3)
        assert len(entries) == 3
        assert entries[0]["tool_name"] == "tool_2"
        assert entries[2]["tool_name"] == "tool_4"

    def test_audit_clear(self, tmp_path):
        audit_path = tmp_path / "test_audit.jsonl"
        audit = ToolAuditLogger(str(audit_path))

        from R1.tools.audit import ToolAuditEvent
        audit.log(ToolAuditEvent(
            timestamp="2024-01-01T00:00:00",
            tool_name="test",
            arguments={},
            success=True,
            output_preview="output"
        ))

        assert audit.count() == 1
        audit.clear()
        assert audit.count() == 0


class TestCodeExecTool:
    def test_python_uses_safe_sandbox(self):
        tool = CodeExecTool()
        result = asyncio.run(tool.execute(code="print('safe path')", language="python"))
        assert result.success
        assert "safe path" in result.output

    def test_python_blocks_dangerous_code(self):
        tool = CodeExecTool()
        result = asyncio.run(tool.execute(code="import os\nprint(os.getcwd())", language="python"))
        assert not result.success
        assert "safety violation" in result.error.lower()
