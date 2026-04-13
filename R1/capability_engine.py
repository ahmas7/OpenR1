"""
R1 - Capability execution engine.
Routes generalized capability requests into existing R1 systems.
"""
from typing import Dict, Any


class CapabilityEngine:
    async def execute(self, domain: str, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        handler_name = f"_handle_{domain}"
        handler = getattr(self, handler_name, None)
        if not handler:
            return {"success": False, "error": f"Unsupported domain: {domain}"}
        return await handler(action, payload)

    async def _handle_cognition(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        from R1.cognitive import get_cognitive_system
        system = get_cognitive_system()
        prompt = payload.get("prompt") or payload.get("text") or action
        session_id = payload.get("session_id", "default")
        result = await system.process(prompt, session_id)
        return {"success": True, "domain": "cognition", "result": result}

    async def _handle_autonomous_execution(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        from R1.agent import agent
        request_text = payload.get("request") or payload.get("message") or action
        task = await agent.plan_task(request_text)
        return {
            "success": True,
            "domain": "autonomous_execution",
            "task_id": task.id,
            "steps": task.steps,
        }

    async def _handle_computer_control(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        from R1.system import Shell, FileSystem
        from R1.browser import BrowserController

        if action == "shell":
            result = await Shell.execute(payload.get("command", ""))
            return {"success": result.success, "domain": "computer_control", "output": result.output, "error": result.error}
        if action == "read_file":
            result = FileSystem.read(payload.get("path", ""))
            return {"success": result.success, "domain": "computer_control", "output": result.output, "error": result.error}
        if action == "browse":
            browser = await BrowserController.get(headless=True)
            result = await browser.navigate(payload.get("url", "https://example.com"))
            return {"success": result.success, "domain": "computer_control", "content": result.content, "error": result.error}
        return {"success": False, "error": f"Unsupported computer control action: {action}"}

    async def _handle_research(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        from R1.browser import BrowserController
        query = payload.get("query") or payload.get("prompt") or action
        browser = await BrowserController.get(headless=True)
        result = await browser.search_google(query)
        return {"success": result.success, "domain": "research", "results": result.data, "content": result.content, "error": result.error}

    async def _handle_coding(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        from R1.code_executor import code_executor
        if action == "python":
            result = await code_executor.execute_python(payload.get("code", ""))
        else:
            result = await code_executor.execute_shell(payload.get("command", payload.get("code", "")))
        return {
            "success": result.success,
            "domain": "coding",
            "output": result.output,
            "error": result.error,
            "execution_time": result.execution_time,
        }

    async def _handle_data_analysis(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        from R1.analytics import get_analytics_system
        analytics = get_analytics_system()
        if action == "trend":
            return {"success": True, "domain": "data_analysis", "result": analytics.analyze_trend(payload.get("metric", ""))}
        if action == "risk":
            return {"success": True, "domain": "data_analysis", "result": analytics.analyze_risk(payload.get("type", "general"), payload.get("factors", {}))}
        if action == "anomaly":
            analytics.detect_anomalies(payload.get("metric", ""), float(payload.get("value", 0)))
            return {"success": True, "domain": "data_analysis", "result": analytics.get_threat_summary()}
        return {"success": False, "error": f"Unsupported data analysis action: {action}"}

    async def _handle_content(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        from R1.providers import get_ai_engine, Message
        engine = get_ai_engine({"provider": payload.get("provider", "local"), "model": payload.get("model", "llama3.2:3b")})
        prompt = payload.get("prompt") or payload.get("text") or action
        response = await engine.chat([
            Message(role="system", content="You are a concise content generation assistant."),
            Message(role="user", content=prompt),
        ])
        return {"success": True, "domain": "content", "result": response.content, "model": response.model}

    async def _handle_business(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        from R1.planning import get_planning_system
        planning = get_planning_system()
        mission_id = planning.create_mission(
            payload.get("name", "Business Workflow"),
            payload.get("description", action),
            payload.get("objectives", []),
        )
        return {"success": True, "domain": "business", "mission_id": mission_id}

    async def _handle_multi_agent(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        from R1.agent import agent
        request_text = payload.get("request") or action
        task = await agent.plan_task(request_text)
        return {"success": True, "domain": "multi_agent", "coordination_plan": task.steps}

    async def _handle_self_improvement(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        from R1.diagnostics import get_diagnostics_system
        diagnostics = get_diagnostics_system()
        report = await diagnostics.generate_diagnostic_report()
        return {"success": True, "domain": "self_improvement", "report": report}


capability_engine = CapabilityEngine()
