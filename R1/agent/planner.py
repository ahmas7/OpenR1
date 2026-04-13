"""
R1 v1 - Planner
Turns goals into steps and tracks execution.
"""
import json
import logging
import re
from typing import Dict, Any, List, Optional

logger = logging.getLogger("R1")


class Planner:
    def __init__(self):
        pass

    def create_plan(self, goal: str) -> Dict[str, Any]:
        return {
            "goal": goal,
            "steps": [],
            "blocked": False,
            "blocked_reason": "",
            "created_at": None
        }

    async def plan_from_model(self, goal: str, model_response: str) -> Dict[str, Any]:
        try:
            json_match = re.search(r'\{.*\}', model_response, re.DOTALL)
            if json_match:
                plan_data = json.loads(json_match.group())
                if "steps" in plan_data:
                    for i, step in enumerate(plan_data["steps"]):
                        if "id" not in step:
                            step["id"] = str(i + 1)
                        if "status" not in step:
                            step["status"] = "pending"
                    return plan_data
        except Exception as e:
            logger.warning(f"Failed to parse plan from model: {e}")
        
        return self._simple_plan(goal)

    def _simple_plan(self, goal: str) -> Dict[str, Any]:
        steps = []
        
        goal_lower = goal.lower()
        
        if any(w in goal_lower for w in ["search", "find", "look up"]):
            steps.append({"id": "1", "title": "Search the web", "status": "pending"})
        elif any(w in goal_lower for w in ["open", "go to", "visit", "browse"]):
            steps.append({"id": "1", "title": "Navigate to URL", "status": "pending"})
        elif any(w in goal_lower for w in ["write", "create", "save"]):
            steps.append({"id": "1", "title": "Write/create file", "status": "pending"})
        elif any(w in goal_lower for w in ["run", "execute", "command"]):
            steps.append({"id": "1", "title": "Execute command", "status": "pending"})
        elif any(w in goal_lower for w in ["read", "check", "show"]):
            steps.append({"id": "1", "title": "Read file", "status": "pending"})
        
        if not steps:
            steps.append({"id": "1", "title": "Process request", "status": "pending"})
        
        return {
            "goal": goal,
            "steps": steps,
            "blocked": False
        }

    def update_step_status(self, plan: Dict[str, Any], step_id: str, status: str, result: str = "") -> Dict[str, Any]:
        for step in plan.get("steps", []):
            if step.get("id") == step_id:
                step["status"] = status
                if result:
                    step["result"] = result
                break
        return plan

    def get_next_step(self, plan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        for step in plan.get("steps", []):
            if step.get("status") == "pending" or step.get("status") == "in_progress":
                return step
        return None

    def get_completed_steps(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [s for s in plan.get("steps", []) if s.get("status") == "done"]

    def is_plan_complete(self, plan: Dict[str, Any]) -> bool:
        for step in plan.get("steps", []):
            if step.get("status") != "done":
                return False
        return True

    def mark_blocked(self, plan: Dict[str, Any], reason: str):
        plan["blocked"] = True
        plan["blocked_reason"] = reason

    def unmark_blocked(self, plan: Dict[str, Any]):
        plan["blocked"] = False
        plan["blocked_reason"] = ""
