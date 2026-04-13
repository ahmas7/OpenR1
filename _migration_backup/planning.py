"""
R1 - Strategic Command & Mission Planning Systems
Mission modeling, resource allocation, contingency planning, logistics
"""
import asyncio
import logging
import json
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Callable
from datetime import datetime, timedelta
from enum import Enum
import random

logger = logging.getLogger("R1:planning")


class MissionStatus(Enum):
    PLANNING = "planning"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ResourceStatus(Enum):
    AVAILABLE = "available"
    ALLOCATED = "allocated"
    IN_USE = "in_use"
    UNAVAILABLE = "unavailable"


@dataclass
class Mission:
    id: str
    name: str
    description: str
    status: MissionStatus
    objectives: List[Dict] = field(default_factory=list)
    tasks: List[Dict] = field(default_factory=list)
    resources: List[str] = field(default_factory=list)
    timeline: Dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class Resource:
    id: str
    name: str
    resource_type: str
    capacity: float
    available: float
    status: ResourceStatus
    assigned_missions: List[str] = field(default_factory=list)


@dataclass
class Contingency:
    id: str
    name: str
    trigger_condition: str
    response_plan: Dict
    priority: int
    enabled: bool = True


class MissionModeler:
    def __init__(self):
        self.missions: Dict[str, Mission] = {}
        
    def create_mission(self, name: str, description: str, objectives: List[str] = None) -> str:
        mission_id = hashlib.md5(f"{name}{datetime.now()}".encode()).hexdigest()[:12]
        
        mission = Mission(
            id=mission_id,
            name=name,
            description=description,
            status=MissionStatus.PLANNING,
            objectives=[
                {"id": hashlib.md5(obj.encode()).hexdigest()[:8], "description": obj, "completed": False}
                for obj in (objectives or [])
            ]
        )
        
        self.missions[mission_id] = mission
        
        return mission_id
    
    def add_task(self, mission_id: str, task_name: str, task_type: str, 
                 dependencies: List[str] = None, estimated_duration: int = None) -> bool:
        if mission_id not in self.missions:
            return False
        
        task = {
            "id": hashlib.md5(f"{task_name}{datetime.now()}".encode()).hexdigest()[:8],
            "name": task_name,
            "type": task_type,
            "status": "pending",
            "dependencies": dependencies or [],
            "estimated_duration": estimated_duration,
            "assigned_to": None,
            "completed_at": None
        }
        
        self.missions[mission_id].tasks.append(task)
        
        return True
    
    def start_mission(self, mission_id: str) -> bool:
        if mission_id not in self.missions:
            return False
        
        mission = self.missions[mission_id]
        mission.status = MissionStatus.READY
        mission.started_at = datetime.now()
        
        for task in mission.tasks:
            if not task.get("dependencies"):
                task["status"] = "ready"
        
        return True
    
    def update_task_status(self, mission_id: str, task_id: str, status: str) -> bool:
        if mission_id not in self.missions:
            return False
        
        mission = self.missions[mission_id]
        
        for task in mission.tasks:
            if task["id"] == task_id:
                task["status"] = status
                
                if status == "completed":
                    task["completed_at"] = datetime.now().isoformat()
                    self._update_dependent_tasks(mission, task_id)
                
                break
        
        self._check_mission_completion(mission_id)
        
        return True
    
    def _update_dependent_tasks(self, mission: Mission, completed_task_id: str):
        for task in mission.tasks:
            if completed_task_id in task.get("dependencies", []):
                all_deps_complete = all(
                    any(t["id"] == dep and t["status"] == "completed" 
                        for t in mission.tasks)
                    for dep in task.get("dependencies", [])
                )
                
                if all_deps_complete:
                    task["status"] = "ready"
    
    def _check_mission_completion(self, mission_id: str):
        mission = self.missions[mission_id]
        
        all_completed = all(
            task["status"] == "completed" 
            for task in mission.tasks
        )
        
        if all_completed and mission.tasks:
            mission.status = MissionStatus.COMPLETED
            mission.completed_at = datetime.now()
    
    def get_mission_status(self, mission_id: str) -> Optional[Dict]:
        if mission_id not in self.missions:
            return None
        
        mission = self.missions[mission_id]
        
        return {
            "id": mission.id,
            "name": mission.name,
            "status": mission.status.value,
            "progress": self._calculate_progress(mission),
            "tasks": {
                "total": len(mission.tasks),
                "completed": sum(1 for t in mission.tasks if t["status"] == "completed"),
                "in_progress": sum(1 for t in mission.tasks if t["status"] == "in_progress")
            }
        }
    
    def _calculate_progress(self, mission: Mission) -> float:
        if not mission.tasks:
            return 0.0
        
        completed = sum(1 for t in mission.tasks if t["status"] == "completed")
        
        return (completed / len(mission.tasks)) * 100

    def get_mission(self, mission_id: str) -> Optional[Mission]:
        return self.missions.get(mission_id)


class ResourceAllocator:
    def __init__(self):
        self.resources: Dict[str, Resource] = {}
        
    def add_resource(self, name: str, resource_type: str, capacity: float) -> str:
        resource_id = hashlib.md5(f"{name}{datetime.now()}".encode()).hexdigest()[:8]
        
        resource = Resource(
            id=resource_id,
            name=name,
            resource_type=resource_type,
            capacity=capacity,
            available=capacity,
            status=ResourceStatus.AVAILABLE
        )
        
        self.resources[resource_id] = resource
        
        return resource_id
    
    def allocate_resource(self, resource_id: str, mission_id: str, amount: float) -> bool:
        if resource_id not in self.resources:
            return False
        
        resource = self.resources[resource_id]
        
        if resource.available < amount:
            return False
        
        resource.available -= amount
        resource.assigned_missions.append(mission_id)
        
        if resource.available == 0:
            resource.status = ResourceStatus.ALLOCATED
        
        return True
    
    def release_resource(self, resource_id: str, mission_id: str) -> bool:
        if resource_id not in self.resources:
            return False
        
        resource = self.resources[resource_id]
        
        if mission_id in resource.assigned_missions:
            resource.assigned_missions.remove(mission_id)
            resource.available = resource.capacity
            resource.status = ResourceStatus.AVAILABLE
        
        return True
    
    def get_available_resources(self, resource_type: str = None) -> List[Dict]:
        result = []
        
        for resource in self.resources.values():
            if resource_type and resource.resource_type != resource_type:
                continue
            
            if resource.status in [ResourceStatus.AVAILABLE, ResourceStatus.ALLOCATED]:
                result.append({
                    "id": resource.id,
                    "name": resource.name,
                    "type": resource.resource_type,
                    "capacity": resource.capacity,
                    "available": resource.available,
                    "status": resource.status.value
                })
        
        return result
    
    def optimize_allocation(self, mission_requirements: Dict[str, float]) -> Dict:
        allocations = {}
        
        for req_type, req_amount in mission_requirements.items():
            available = self.get_available_resources(req_type)
            
            if not available:
                allocations[req_type] = {"allocated": 0, "shortage": req_amount}
                continue
            
            total_available = sum(r["available"] for r in available)
            
            if total_available >= req_amount:
                allocations[req_type] = {"allocated": req_amount, "shortage": 0}
            else:
                allocations[req_type] = {"allocated": total_available, "shortage": req_amount - total_available}
        
        return allocations


class StrategicForecaster:
    def __init__(self):
        self.projections: List[Dict] = []
        
    def project_outcome(self, mission_id: str, current_state: Dict, 
                       time_horizon: int = 30) -> Dict:
        tasks = current_state.get("tasks", [])
        completed = sum(1 for t in tasks if t.get("status") == "completed")
        total = len(tasks)
        
        if total == 0:
            return {"projection": "unknown", "confidence": 0}
        
        completion_rate = completed / total
        days_elapsed = current_state.get("days_elapsed", 1)
        
        remaining_tasks = total - completed
        days_per_task = days_elapsed / completed if completed > 0 else 1
        
        estimated_days_remaining = remaining_tasks * days_per_task
        
        confidence = 0.9 if completion_rate > 0.5 else 0.6
        
        outcome = "on_track"
        if completion_rate < 0.3:
            outcome = "behind_schedule"
        elif completion_rate > 0.8:
            outcome = "ahead_of_schedule"
        
        return {
            "mission_id": mission_id,
            "outcome": outcome,
            "estimated_completion_days": estimated_days_remaining,
            "confidence": confidence,
            "completion_rate": completion_rate * 100,
            "projection_date": (datetime.now() + timedelta(days=int(estimated_days_remaining))).isoformat()
        }
    
    def compare_strategies(self, strategies: List[Dict]) -> Dict:
        scored = []
        
        for strategy in strategies:
            score = 0
            
            if "efficiency" in strategy:
                score += strategy["efficiency"] * 0.3
            if "cost" in strategy:
                score += (100 - strategy["cost"]) * 0.2
            if "time" in strategy:
                score += (30 - strategy["time"]) * 0.3 if strategy["time"] < 30 else 0
            if "risk" in strategy:
                score += (100 - strategy["risk"]) * 0.2
            
            scored.append({
                "strategy": strategy.get("name", "unnamed"),
                "score": score,
                "details": strategy
            })
        
        scored.sort(key=lambda x: x["score"], reverse=True)
        
        return {
            "best_strategy": scored[0]["strategy"] if scored else None,
            "all_strategies": scored
        }


class TimelineCoordinator:
    def __init__(self):
        self.activities: List[Dict] = []
        
    def add_activity(self, name: str, start_time: datetime, end_time: datetime,
                    assigned_to: str = None, dependencies: List[str] = None) -> str:
        activity_id = hashlib.md5(f"{name}{datetime.now()}".encode()).hexdigest()[:8]
        
        activity = {
            "id": activity_id,
            "name": name,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_minutes": (end_time - start_time).total_seconds() / 60,
            "assigned_to": assigned_to,
            "dependencies": dependencies or [],
            "status": "scheduled"
        }
        
        self.activities.append(activity)
        
        return activity_id
    
    def get_conflicts(self) -> List[Dict]:
        conflicts = []
        
        for i, act1 in enumerate(self.activities):
            for act2 in self.activities[i+1:]:
                if self._check_time_conflict(act1, act2):
                    conflicts.append({
                        "activity1": act1["name"],
                        "activity2": act2["name"],
                        "overlap": True
                    })
        
        return conflicts
    
    def _check_time_conflict(self, act1: Dict, act2: Dict) -> bool:
        start1 = datetime.fromisoformat(act1["start_time"])
        end1 = datetime.fromisoformat(act1["end_time"])
        start2 = datetime.fromisoformat(act2["start_time"])
        end2 = datetime.fromisoformat(act2["end_time"])
        
        return (start1 <= start2 < end1) or (start2 <= start1 < end2)
    
    def optimize_timeline(self) -> Dict:
        sorted_activities = sorted(
            self.activities, 
            key=lambda x: x["start_time"]
        )
        
        total_duration = sum(a["duration_minutes"] for a in sorted_activities)
        
        gaps = []
        for i in range(len(sorted_activities) - 1):
            gap = (datetime.fromisoformat(sorted_activities[i+1]["start_time"]) - 
                   datetime.fromisoformat(sorted_activities[i]["end_time"]))
            gaps.append(gap.total_seconds() / 60)
        
        return {
            "total_activities": len(sorted_activities),
            "total_duration_minutes": total_duration,
            "total_gaps_minutes": sum(gaps),
            "optimization_potential": "Consider parallel execution for independent tasks"
        }


class ContingencyPlanner:
    def __init__(self):
        self.contingencies: Dict[str, Contingency] = {}
        
    def add_contingency(self, name: str, trigger: str, response: Dict, 
                       priority: int = 1) -> str:
        contingency_id = hashlib.md5(f"{name}{datetime.now()}".encode()).hexdigest()[:8]
        
        contingency = Contingency(
            id=contingency_id,
            name=name,
            trigger_condition=trigger,
            response_plan=response,
            priority=priority
        )
        
        self.contingencies[contingency_id] = contingency
        
        return contingency_id
    
    def check_contingency(self, condition: str) -> List[Contingency]:
        triggered = []
        
        for contingency in self.contingencies.values():
            if not contingency.enabled:
                continue
            
            if contingency.trigger_condition.lower() in condition.lower():
                triggered.append(contingency)
        
        triggered.sort(key=lambda c: c.priority)
        
        return triggered
    
    def execute_contingency(self, contingency_id: str, context: Dict = None) -> Dict:
        if contingency_id not in self.contingencies:
            return {"success": False, "error": "Contingency not found"}
        
        contingency = self.contingencies[contingency_id]
        response = contingency.response_plan
        
        logger.info(f"Executing contingency: {contingency.name}")
        
        return {
            "success": True,
            "contingency": contingency.name,
            "response": response,
            "context": context
        }
    
    def enable_contingency(self, contingency_id: str) -> bool:
        if contingency_id in self.contingencies:
            self.contingencies[contingency_id].enabled = True
            return True
        return False
    
    def disable_contingency(self, contingency_id: str) -> bool:
        if contingency_id in self.contingencies:
            self.contingencies[contingency_id].enabled = False
            return True
        return False


class LogisticsOptimizer:
    def __init__(self):
        self.routes: List[Dict] = []
        
    def add_route(self, origin: str, destination: str, waypoints: List[str] = None,
                 distance_km: float = None, estimated_time_minutes: int = None) -> str:
        route_id = hashlib.md5(f"{origin}{destination}{datetime.now()}".encode()).hexdigest()[:8]
        
        if not distance_km:
            distance_km = self._estimate_distance(origin, destination)
        
        route = {
            "id": route_id,
            "origin": origin,
            "destination": destination,
            "waypoints": waypoints or [],
            "distance_km": distance_km,
            "estimated_time_minutes": estimated_time_minutes or int(distance_km / 60 * 60),
            "status": "planned"
        }
        
        self.routes.append(route)
        
        return route_id
    
    def _estimate_distance(self, origin: str, destination: str) -> float:
        return random.uniform(10, 500)
    
    def optimize_routes(self, deliveries: List[Dict]) -> Dict:
        if not deliveries:
            return {"error": "No deliveries provided"}
        
        total_distance = 0
        optimized_order = []
        
        for delivery in deliveries:
            total_distance += delivery.get("distance_km", 100)
            optimized_order.append(delivery["destination"])
        
        return {
            "total_distance_km": total_distance,
            "total_deliveries": len(deliveries),
            "route_order": optimized_order,
            "estimated_time_hours": total_distance / 60
        }


class PlanningSystem:
    def __init__(self):
        self.missions = MissionModeler()
        self.resources = ResourceAllocator()
        self.forecaster = StrategicForecaster()
        self.timeline = TimelineCoordinator()
        self.contingencies = ContingencyPlanner()
        self.logistics = LogisticsOptimizer()
    
    def create_mission(self, name: str, description: str, objectives: List[str] = None) -> str:
        return self.missions.create_mission(name, description, objectives)
    
    def add_mission_task(self, mission_id: str, task_name: str, task_type: str) -> bool:
        return self.missions.add_task(mission_id, task_name, task_type)
    
    def get_mission(self, mission_id: str) -> Optional[Mission]:
        return self.missions.get_mission(mission_id)
    
    def allocate_resources(self, mission_id: str, resource_requirements: Dict[str, float]) -> Dict:
        return self.resources.optimize_allocation(resource_requirements)
    
    def create_contingency(self, name: str, trigger: str, response: Dict) -> str:
        return self.contingencies.add_contingency(name, trigger, response)
    
    def get_mission_status(self, mission_id: str) -> Dict:
        return self.missions.get_mission_status(mission_id)
    
    def forecast_mission(self, mission_id: str) -> Dict:
        mission = self.missions.get_mission(mission_id)
        if not mission:
            return {"error": "Mission not found"}
        
        current_state = {
            "tasks": mission.tasks,
            "days_elapsed": (datetime.now() - mission.created_at).days
        }
        
        return self.forecaster.project_outcome(mission_id, current_state)


_planning_system: Optional[PlanningSystem] = None

def get_planning_system() -> PlanningSystem:
    global _planning_system
    if _planning_system is None:
        _planning_system = PlanningSystem()
    return _planning_system
