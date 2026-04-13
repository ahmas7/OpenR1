"""
Tests for R1 Skills System
"""
import pytest
import json
import tempfile
import shutil
from pathlib import Path


class TestSkillManifest:
    """Tests for skill manifest validation"""
    
    def test_valid_manifest(self):
        from R1.skills import SkillManifest
        
        data = {
            "name": "test_skill",
            "description": "A test skill",
            "version": "1.0.0",
            "entrypoint": "main.py",
            "triggers": ["test", "example"],
            "tools_used": ["shell"],
            "source": "workspace"
        }
        
        manifest = SkillManifest.from_dict(data)
        errors = manifest.validate()
        
        assert len(errors) == 0
        assert manifest.name == "test_skill"
        assert manifest.version == "1.0.0"
    
    def test_missing_name(self):
        from R1.skills import SkillManifest
        
        data = {
            "description": "A test skill without name"
        }
        
        manifest = SkillManifest.from_dict(data)
        errors = manifest.validate()
        
        assert "Skill name is required" in errors
    
    def test_missing_description(self):
        from R1.skills import SkillManifest
        
        data = {
            "name": "test_skill"
        }
        
        manifest = SkillManifest.from_dict(data)
        errors = manifest.validate()
        
        assert "Skill description is required" in errors
    
    def test_missing_entrypoint(self):
        from R1.skills import SkillManifest
        
        data = {
            "name": "test_skill",
            "description": "A test skill",
            "entrypoint": ""  # Explicitly empty
        }
        
        manifest = SkillManifest.from_dict(data)
        errors = manifest.validate()
        
        assert "Skill entrypoint is required" in errors
    
    def test_to_dict(self):
        from R1.skills import SkillManifest, SkillSource
        
        manifest = SkillManifest(
            name="test",
            description="Test skill",
            version="2.0.0",
            entrypoint="run.py",
            source=SkillSource.WORKSPACE
        )
        
        data = manifest.to_dict()
        
        assert data["name"] == "test"
        assert data["version"] == "2.0.0"
        assert data["source"] == "workspace"
    
    def test_load_from_file(self):
        from R1.skills import SkillManifest
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                "name": "file_skill",
                "description": "Loaded from file",
                "entrypoint": "main.py"
            }, f)
            temp_path = f.name
        
        try:
            manifest = SkillManifest.load_from_file(Path(temp_path))
            assert manifest.name == "file_skill"
            assert manifest.description == "Loaded from file"
        finally:
            Path(temp_path).unlink()


class TestSkillRegistry:
    """Tests for skill registry operations"""
    
    def test_register_unregister(self):
        from R1.skills import SkillRegistry, SkillManifest, SkillInstance, SkillStatus
        
        registry = SkillRegistry()
        
        manifest = SkillManifest(
            name="register_test",
            description="Test",
            entrypoint="main.py"
        )
        instance = SkillInstance(
            manifest=manifest,
            path=Path("/tmp/test"),
            status=SkillStatus.UNLOADED
        )
        
        registry.register(instance)
        
        assert registry.get("register_test") is not None
        
        result = registry.unregister("register_test")
        assert result is True
        assert registry.get("register_test") is None
    
    def test_list_skills(self):
        from R1.skills import SkillRegistry, SkillManifest, SkillInstance, SkillStatus
        
        registry = SkillRegistry()
        
        for i in range(3):
            manifest = SkillManifest(
                name=f"skill_{i}",
                description=f"Test skill {i}",
                entrypoint="main.py"
            )
            instance = SkillInstance(
                manifest=manifest,
                path=Path(f"/tmp/skill_{i}"),
                status=SkillStatus.UNLOADED
            )
            registry.register(instance)
        
        skills = registry.list_skills()
        
        assert len(skills) == 3
    
    def test_load_unload(self):
        from R1.skills import SkillRegistry, SkillManifest, SkillInstance, SkillStatus
        
        registry = SkillRegistry()
        
        manifest = SkillManifest(
            name="load_test",
            description="Test",
            entrypoint="main.py"
        )
        instance = SkillInstance(
            manifest=manifest,
            path=Path("/tmp/test"),
            status=SkillStatus.UNLOADED
        )
        registry.register(instance)
        
        result = registry.load("load_test")
        assert result is True
        assert instance.status == SkillStatus.LOADED
        
        result = registry.unload("load_test")
        assert result is True
        assert instance.status == SkillStatus.UNLOADED
    
    def test_reload(self):
        from R1.skills import SkillRegistry, SkillManifest, SkillInstance, SkillStatus
        
        registry = SkillRegistry()
        
        manifest = SkillManifest(
            name="reload_test",
            description="Test",
            entrypoint="main.py"
        )
        instance = SkillInstance(
            manifest=manifest,
            path=Path("/tmp/test"),
            status=SkillStatus.UNLOADED
        )
        registry.register(instance)
        
        registry.load("reload_test")
        assert instance.status == SkillStatus.LOADED
        
        result = registry.reload("reload_test")
        assert result is True


class TestSkillLoader:
    """Tests for lazy loading"""
    
    def test_load_skill_from_directory(self):
        from R1.skills import SkillLoader, SkillRegistry, get_skills_registry
        
        # Create a temp skill directory
        temp_dir = Path(tempfile.mkdtemp())
        
        try:
            # Create skill.json
            skill_json = temp_dir / "test_skill" / "skill.json"
            skill_json.parent.mkdir()
            with open(skill_json, 'w') as f:
                json.dump({
                    "name": "test_skill",
                    "description": "Test skill",
                    "entrypoint": "main.py"
                }, f)
            
            # Create main.py
            main_py = temp_dir / "test_skill" / "main.py"
            with open(main_py, 'w') as f:
                f.write("""
def register():
    return lambda ctx: {"result": "success"}
""")
            
            # Load using loader
            loader = SkillLoader()
            result = loader.load_skill(temp_dir / "test_skill")
            
            # Verify
            registry = get_skills_registry()
            skill = registry.get("test_skill")
            assert skill is not None
            
        finally:
            shutil.rmtree(temp_dir)


class TestSkillInvocation:
    """Tests for skill invocation and failure isolation"""
    
    def test_successful_invocation(self):
        from R1.skills import SkillRegistry, SkillManifest, SkillInstance, SkillStatus
        
        registry = SkillRegistry()
        
        manifest = SkillManifest(
            name="echo_skill",
            description="Echoes input",
            entrypoint="main.py"
        )
        instance = SkillInstance(
            manifest=manifest,
            path=Path("/tmp/echo"),
            status=SkillStatus.LOADED
        )
        registry.register(instance)
        
        # Register a handler
        def echo_handler(context):
            return {"echoed": context.get("message", "no message")}
        
        registry.register_handler("echo_skill", echo_handler)
        registry.load("echo_skill")
        
        result = registry.invoke("echo_skill", {"message": "hello"})
        
        assert result["success"] is True
        assert result["result"]["echoed"] == "hello"
    
    def test_invocation_failure_isolation(self):
        from R1.skills import SkillRegistry, SkillManifest, SkillInstance, SkillStatus
        
        registry = SkillRegistry()
        
        manifest = SkillManifest(
            name="crash_skill",
            description="Crashes on invocation",
            entrypoint="main.py"
        )
        instance = SkillInstance(
            manifest=manifest,
            path=Path("/tmp/crash"),
            status=SkillStatus.LOADED
        )
        registry.register(instance)
        
        # Register a handler that raises an exception
        def crash_handler(context):
            raise RuntimeError("Intentional crash for testing")
        
        registry.register_handler("crash_skill", crash_handler)
        registry.load("crash_skill")
        
        result = registry.invoke("crash_skill", {})
        
        # Should return error, not raise
        assert result["success"] is False
        assert "error" in result
    
    def test_invocation_missing_skill(self):
        from R1.skills import SkillRegistry
        
        registry = SkillRegistry()
        
        result = registry.invoke("nonexistent_skill", {})
        
        assert result["success"] is False
        assert "not found" in result["error"].lower()


class TestSkillsRuntime:
    """Tests for skills runtime integration"""
    
    def test_runtime_initialization(self):
        from R1.skills import SkillsRuntime
        import asyncio
        
        runtime = SkillsRuntime()
        
        # Just verify it can be created
        assert runtime.registry is not None
        assert runtime.loader is not None
    
    def test_find_skills_for_goal(self):
        from R1.skills import SkillsRuntime, SkillRegistry, SkillManifest, SkillInstance, SkillStatus
        import asyncio
        
        runtime = SkillsRuntime()
        
        # Manually register a skill with triggers
        manifest = SkillManifest(
            name="time_skill",
            description="Handles time queries",
            entrypoint="main.py",
            triggers=["time", "timestamp", "clock"]
        )
        instance = SkillInstance(
            manifest=manifest,
            path=Path("/tmp/time"),
            status=SkillStatus.LOADED
        )
        runtime.registry.register(instance)
        runtime.registry.load("time_skill")
        
        # Find skills
        matches = runtime.find_skills_for_goal("what time is it")
        
        assert len(matches) > 0
        assert matches[0].manifest.name == "time_skill"
    
    def test_get_skill_tools(self):
        from R1.skills import SkillsRuntime, SkillRegistry, SkillManifest, SkillInstance, SkillStatus
        
        runtime = SkillsRuntime()
        
        manifest = SkillManifest(
            name="tool_skill",
            description="Exposes as tool",
            entrypoint="main.py",
            triggers=["tool"]
        )
        instance = SkillInstance(
            manifest=manifest,
            path=Path("/tmp/tool"),
            status=SkillStatus.LOADED
        )
        runtime.registry.register(instance)
        runtime.registry.load("tool_skill")
        
        tools = runtime.get_skill_tools()
        
        assert len(tools) > 0
        tool_names = [t["name"] for t in tools]
        assert "skill:tool_skill" in tool_names


class TestAgentSkillIntegration:
    """Tests for agent loop skill integration"""
    
    def test_parse_skill_action(self):
        from R1.agent.loop import AgentLoop
        from R1.agent.state import AgentState
        
        state = AgentState(session_id="test")
        loop = AgentLoop(state)
        
        # Test parsing a SKILL: response
        response = """SKILL: timestamp
context: {"format": "iso"}"""
        
        loop._parse_action(response)
        
        # The skill_name should be extracted correctly
        assert "skill:" in loop.state.last_action
        assert loop.state.last_result.get("_is_skill") is True
    
    def test_parse_tool_action(self):
        from R1.agent.loop import AgentLoop
        from R1.agent.state import AgentState
        
        state = AgentState(session_id="test")
        loop = AgentLoop(state)
        
        response = """TOOL: shell
command: ls"""
        
        loop._parse_action(response)
        
        assert loop.state.last_action == "shell"
        assert loop.state.last_result.get("command") == "ls"
    
    def test_failure_isolation_in_act(self):
        import asyncio
        from R1.agent.loop import AgentLoop
        from R1.agent.state import AgentState, AgentStatus
        
        state = AgentState(session_id="test")
        loop = AgentLoop(state)
        
        # Set up state for skill invocation with a non-existent skill
        loop.state.last_action = "skill:nonexistent"
        loop.state.last_result = {
            "skill_name": "nonexistent",
            "context": {},
            "_is_skill": True
        }
        loop.state.status = AgentStatus.ACTING
        
        # Run the act method - should handle error gracefully
        asyncio.run(loop._act())
        
        # The error should be captured in last_result, not raised
        assert loop.state.last_result is not None
        assert "not found" in str(loop.state.last_result).lower() or "error" in str(loop.state.last_result).lower()


class TestSkillDiscovery:
    """Tests for skill discovery"""
    
    def test_discover_workspace_skills(self):
        from R1.skills import SkillRegistry, SkillManifest, SkillInstance, SkillStatus
        import tempfile
        from pathlib import Path
        import json
        
        # Create temp directory with skills
        temp_dir = Path(tempfile.mkdtemp())
        
        try:
            # Create skills directory
            skills_dir = temp_dir / "skills"
            skills_dir.mkdir()
            
            # Create a skill
            skill_dir = skills_dir / "discovered_skill"
            skill_dir.mkdir()
            
            with open(skill_dir / "skill.json", "w") as f:
                json.dump({
                    "name": "discovered_skill",
                    "description": "A discovered skill",
                    "entrypoint": "main.py"
                }, f)
            
            # Create main.py
            with open(skill_dir / "main.py", "w") as f:
                f.write("def register():\n    return lambda ctx: {'result': 'ok'}\n")
            
            # Discover
            registry = SkillRegistry()
            registry.discover_workspace_skills(temp_dir)
            
            # Verify
            skill = registry.get("discovered_skill")
            assert skill is not None
            
        finally:
            import shutil
            shutil.rmtree(temp_dir)
    
    def test_add_discovery_path(self):
        from R1.skills import SkillRegistry
        import tempfile
        from pathlib import Path
        
        temp_dir = Path(tempfile.mkdtemp())
        
        try:
            registry = SkillRegistry()
            registry.add_discovery_path(temp_dir)
            
            assert temp_dir in registry._discovery_paths
            
        finally:
            import shutil
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
