"""
ORION-R1 AGI Routes
System awareness, code sandbox, app control, memory graph, tool chaining, proactive agent
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio

router = APIRouter()

# Request/Response models
class CodeExecuteRequest(BaseModel):
    code: str
    variables: Optional[Dict] = None

class AppControlRequest(BaseModel):
    action: str
    params: Optional[Dict] = None

class MemorySearchRequest(BaseModel):
    query: str
    node_type: Optional[str] = None

class TaskCreateRequest(BaseModel):
    goal: str
    steps: Optional[List[Dict]] = None

class LinkNodesRequest(BaseModel):
    source_id: str
    target_id: str
    relation: str

# ==================== SYSTEM AWARENESS ====================

@router.get("/system/status")
async def get_system_status():
    """Get full system status (CPU, RAM, disk, network, processes)"""
    try:
        from R1.system_awareness import get_system_awareness
        awareness = get_system_awareness()
        status = awareness.get_full_status()
        return JSONResponse(status)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.get("/system/alerts")
async def get_system_alerts():
    """Check for system alerts"""
    try:
        from R1.system_awareness import get_system_awareness
        awareness = get_system_awareness()
        alerts = awareness.check_alerts()
        return JSONResponse({"alerts": alerts})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.get("/system/processes")
async def get_processes(limit: int = 20):
    """Get running processes"""
    try:
        from R1.system_awareness import get_system_awareness
        awareness = get_system_awareness()
        processes = awareness.get_processes(limit)
        return JSONResponse({"processes": processes})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.get("/system/active-window")
async def get_active_window():
    """Get currently active window"""
    try:
        from R1.system_awareness import get_system_awareness
        awareness = get_system_awareness()
        window = awareness.get_active_window()
        return JSONResponse({"window": window})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ==================== CODE SANDBOX ====================

@router.post("/code/execute")
async def execute_code(request: CodeExecuteRequest):
    """Execute Python code in sandbox"""
    try:
        from R1.code_sandbox import get_code_sandbox
        sandbox = get_code_sandbox()
        result = await sandbox.execute_async(request.code, request.variables)
        return JSONResponse(result.to_dict())
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.get("/code/history")
async def get_code_history(limit: int = 20):
    """Get code execution history"""
    try:
        from R1.code_sandbox import get_code_sandbox
        sandbox = get_code_sandbox()
        history = sandbox.get_execution_history(limit)
        return JSONResponse({"history": history})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.delete("/code/history")
async def clear_code_history():
    """Clear code execution history"""
    try:
        from R1.code_sandbox import get_code_sandbox
        sandbox = get_code_sandbox()
        sandbox.clear_history()
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ==================== APP CONTROL ====================

@router.post("/app/control")
async def app_control(request: AppControlRequest):
    """Control mouse/keyboard/windows"""
    try:
        from R1.app_control import get_app_controller
        controller = get_app_controller()

        action = request.action
        params = request.params or {}

        if hasattr(controller, action):
            if action == "hotkey" and isinstance(params.get("keys"), list):
                result = getattr(controller, action)(*params.get("keys"))
            else:
                result = getattr(controller, action)(**params)
            return JSONResponse(result)
        else:
            return JSONResponse({"error": f"Unknown action: {action}"}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.get("/app/windows")
async def list_windows():
    """List all visible windows"""
    try:
        from R1.app_control import get_app_controller
        controller = get_app_controller()
        result = controller.list_windows()
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.get("/app/mouse-position")
async def get_mouse_position():
    """Get current mouse position"""
    try:
        from R1.app_control import get_app_controller
        controller = get_app_controller()
        result = controller.get_mouse_position()
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.post("/app/screenshot")
async def take_screenshot(save_path: Optional[str] = None):
    """Take screenshot"""
    try:
        from R1.app_control import get_app_controller
        controller = get_app_controller()
        result = controller.screenshot(save_path)
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ==================== MEMORY GRAPH ====================

@router.post("/memory-graph/search")
async def search_memory(request: MemorySearchRequest):
    """Search memory graph"""
    try:
        from R1.memory_graph import get_memory_graph
        graph = get_memory_graph()
        results = graph.search(request.query, request.node_type)
        return JSONResponse({"results": results})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.post("/memory-graph/node")
async def add_memory_node(node_type: str, data: Dict):
    """Add node to memory graph"""
    try:
        from R1.memory_graph import get_memory_graph
        graph = get_memory_graph()
        node = graph.add_node(node_type, data)
        return JSONResponse({"node": node.to_dict()})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.post("/memory-graph/link")
async def link_nodes(request: LinkNodesRequest):
    """Link two nodes with a relationship"""
    try:
        from R1.memory_graph import get_memory_graph
        graph = get_memory_graph()
        edge = graph.add_edge(request.source_id, request.target_id, request.relation)
        return JSONResponse({"edge": edge.to_dict()})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.get("/memory-graph/nodes")
async def list_nodes(node_type: Optional[str] = None):
    """List memory nodes"""
    try:
        from R1.memory_graph import get_memory_graph
        graph = get_memory_graph()
        nodes = graph.list_nodes(node_type)
        return JSONResponse({"nodes": [n.to_dict() for n in nodes]})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.get("/memory-graph/stats")
async def get_memory_stats():
    """Get memory graph statistics"""
    try:
        from R1.memory_graph import get_memory_graph
        graph = get_memory_graph()
        stats = graph.get_stats()
        return JSONResponse(stats)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.get("/memory-graph/neighbors/{node_id}")
async def get_neighbors(node_id: str, depth: int = 1):
    """Get connected nodes"""
    try:
        from R1.memory_graph import get_memory_graph
        graph = get_memory_graph()
        result = graph.get_neighbors(node_id, depth)
        return JSONResponse({
            "center": result["center"].to_dict() if result["center"] else None,
            "neighbors": [n.to_dict() for n in result["neighbors"]]
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ==================== TOOL CHAINING ====================

@router.post("/task/create")
async def create_task(request: TaskCreateRequest):
    """Create a new autonomous task"""
    try:
        from R1.tool_chaining import get_tool_chaining_engine
        engine = get_tool_chaining_engine()
        steps = request.steps or []
        task = engine.create_task(request.goal, steps)
        return JSONResponse({"task": {"id": task.id, "goal": task.goal, "status": task.status.value}})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.post("/task/run/{task_id}")
async def run_task(task_id: str):
    """Run a task"""
    try:
        from R1.tool_chaining import get_tool_chaining_engine
        engine = get_tool_chaining_engine()
        task = await engine.run_task(task_id)
        return JSONResponse({"task": {"id": task.id, "status": task.status.value, "result": task.result}})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.post("/task/run-goal")
async def run_goal(goal: str, session_id: str = "default"):
    """Run a goal autonomously"""
    try:
        from R1.tool_chaining import get_tool_chaining_engine
        engine = get_tool_chaining_engine()
        task = await engine.run_goal(goal, session_id)
        return JSONResponse({"task": {"id": task.id, "goal": task.goal, "status": task.status.value, "result": task.result}})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.get("/task/{task_id}")
async def get_task(task_id: str):
    """Get task details"""
    try:
        from R1.tool_chaining import get_tool_chaining_engine
        engine = get_tool_chaining_engine()
        task = engine.get_task(task_id)
        if not task:
            return JSONResponse({"error": "Task not found"}, status_code=404)
        return JSONResponse({
            "id": task.id,
            "goal": task.goal,
            "status": task.status.value,
            "steps": [{"tool": s.tool_name, "action": s.action, "params": s.params, "success": s.success} for s in task.steps],
            "result": task.result
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.get("/task/list")
async def list_tasks(status: Optional[str] = None):
    """List tasks"""
    try:
        from R1.tool_chaining import get_tool_chaining_engine, TaskStatus
        engine = get_tool_chaining_engine()
        task_status = TaskStatus(status) if status else None
        tasks = engine.list_tasks(task_status)
        return JSONResponse({"tasks": [{"id": t.id, "goal": t.goal, "status": t.status.value} for t in tasks]})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.post("/task/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel a running task"""
    try:
        from R1.tool_chaining import get_tool_chaining_engine
        engine = get_tool_chaining_engine()
        success = engine.cancel_task(task_id)
        return JSONResponse({"success": success})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.get("/task/history")
async def get_task_history(limit: int = 20):
    """Get task history"""
    try:
        from R1.tool_chaining import get_tool_chaining_engine
        engine = get_tool_chaining_engine()
        history = engine.get_task_history(limit)
        return JSONResponse({"history": history})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ==================== PROACTIVE AGENT ====================

@router.get("/proactive/suggestions")
async def get_suggestions(include_dismissed: bool = False):
    """Get proactive suggestions"""
    try:
        from R1.proactive_agent import get_proactive_agent
        agent = get_proactive_agent()
        suggestions = agent.get_suggestions(include_dismissed)
        return JSONResponse({
            "suggestions": [
                {"id": s.id, "type": s.type, "title": s.title, "message": s.message, "priority": s.priority.value}
                for s in suggestions
            ]
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.post("/proactive/suggestion/{suggestion_id}/dismiss")
async def dismiss_suggestion(suggestion_id: str):
    """Dismiss a suggestion"""
    try:
        from R1.proactive_agent import get_proactive_agent
        agent = get_proactive_agent()
        agent.dismiss_suggestion(suggestion_id)
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.post("/proactive/suggestion/{suggestion_id}/act")
async def act_on_suggestion(suggestion_id: str):
    """Mark suggestion as acted upon"""
    try:
        from R1.proactive_agent import get_proactive_agent
        agent = get_proactive_agent()
        agent.act_on_suggestion(suggestion_id)
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.get("/proactive/patterns")
async def get_patterns():
    """Get learned user patterns"""
    try:
        from R1.proactive_agent import get_proactive_agent
        agent = get_proactive_agent()
        patterns = agent.get_patterns()
        return JSONResponse({
            "patterns": [
                {"id": p.id, "type": p.pattern_type, "confidence": p.confidence, "occurrences": p.occurrences}
                for p in patterns
            ]
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.post("/proactive/check")
async def check_proactive():
    """Run proactive checks and return new suggestions"""
    try:
        from R1.proactive_agent import get_proactive_agent
        from R1.system_awareness import get_system_awareness

        agent = get_proactive_agent()
        awareness = get_system_awareness()
        status = awareness.get_full_status()

        suggestions = await agent.check_and_suggest(status, {})
        return JSONResponse({
            "suggestions": [
                {"id": s.id, "type": s.type, "title": s.title, "message": s.message, "priority": s.priority.value}
                for s in suggestions
            ]
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ==================== AGI STATUS ====================

@router.get("/agi/status")
async def get_agi_status():
    """Get overall AGI system status"""
    try:
        from R1.system_awareness import get_system_awareness
        from R1.code_sandbox import get_code_sandbox
        from R1.memory_graph import get_memory_graph
        from R1.tool_chaining import get_tool_chaining_engine
        from R1.proactive_agent import get_proactive_agent

        awareness = get_system_awareness()
        sandbox = get_code_sandbox()
        graph = get_memory_graph()
        engine = get_tool_chaining_engine()
        agent = get_proactive_agent()

        return JSONResponse({
            "system": awareness.get_full_status(),
            "code_sandbox": {"executions": len(sandbox.get_execution_history())},
            "memory_graph": graph.get_stats(),
            "tasks": {"total": len(engine.tasks), "active": len([t for t in engine.tasks.values() if t.status.value == "running"])},
            "suggestions": len([s for s in agent.suggestions.values() if not s.dismissed]),
            "patterns": len(agent.patterns)
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
