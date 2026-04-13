"""
R1 - Autonomous Decision Systems
Priority-based actions, ethical constraints, human override, adaptive rules
"""
import asyncio
import logging
import json
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Callable
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict

logger = logging.getLogger("R1:decisions")


class Priority(Enum):
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5


class DecisionStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    REJECTED = "rejected"
    REQUIRES_HUMAN = "requires_human"


@dataclass
class Decision:
    id: str
    timestamp: datetime
    action: str
    priority: Priority
    context: Dict[str, Any] = field(default_factory=dict)
    status: DecisionStatus = DecisionStatus.PENDING
    approved_by: Optional[str] = None
    executed_at: Optional[datetime] = None
    result: Optional[Dict] = None
    reason: Optional[str] = None


@dataclass
class EthicalConstraint:
    id: str
    name: str
    description: str
    constraint_type: str
    rule: str
    severity: str
    enabled: bool = True


@dataclass
class DecisionRule:
    id: str
    name: str
    condition: Callable[[Dict], bool]
    action: Callable[[Dict], Dict]
    priority: Priority
    requires_approval: bool
    auto_execute: bool


class PriorityActionSelector:
    def __init__(self):
        self.action_queue: List[Decision] = []
        self.executing_actions: Dict[str, Decision] = {}
        self.completed_actions: List[Decision] = []
        
    def add_action(self, action: str, priority: Priority, context: Dict = None) -> str:
        decision = Decision(
            id=hashlib.md5(f"{action}{datetime.now()}".encode()).hexdigest()[:12],
            timestamp=datetime.now(),
            action=action,
            priority=priority,
            context=context or {}
        )
        
        self.action_queue.append(decision)
        self.action_queue.sort(key=lambda d: d.priority.value)
        
        return decision.id
    
    def get_next_action(self) -> Optional[Decision]:
        if not self.action_queue:
            return None
        
        return self.action_queue[0]
    
    def approve_action(self, decision_id: str, approver: str = "system") -> bool:
        for decision in self.action_queue:
            if decision.id == decision_id:
                decision.status = DecisionStatus.APPROVED
                decision.approved_by = approver
                return True
        return False
    
    def reject_action(self, decision_id: str, reason: str) -> bool:
        for decision in self.action_queue:
            if decision.id == decision_id:
                decision.status = DecisionStatus.REJECTED
                decision.reason = reason
                return True
        return False
    
    def start_execution(self, decision_id: str) -> bool:
        for decision in self.action_queue:
            if decision.id == decision_id:
                decision.status = DecisionStatus.EXECUTING
                decision.executed_at = datetime.now()
                self.executing_actions[decision_id] = decision
                self.action_queue.remove(decision)
                return True
        return False
    
    def complete_execution(self, decision_id: str, result: Dict = None) -> bool:
        if decision_id in self.executing_actions:
            decision = self.executing_actions[decision_id]
            decision.status = DecisionStatus.COMPLETED
            decision.result = result
            
            self.completed_actions.append(decision)
            del self.executing_actions[decision_id]
            
            return True
        return False
    
    def get_queue_status(self) -> Dict:
        return {
            "pending": len(self.action_queue),
            "executing": len(self.executing_actions),
            "completed": len(self.completed_actions),
            "next_action": self.action_queue[0].action if self.action_queue else None
        }


class EthicalConstraintEngine:
    def __init__(self):
        self.constraints: List[EthicalConstraint] = []
        self.constraint_violations: List[Dict] = []
        
    def add_constraint(self, name: str, description: str, constraint_type: str, 
                      rule: str, severity: str = "high") -> str:
        constraint = EthicalConstraint(
            id=hashlib.md5(name.encode()).hexdigest()[:8],
            name=name,
            description=description,
            constraint_type=constraint_type,
            rule=rule,
            severity=severity
        )
        self.constraints.append(constraint)
        return constraint.id
    
    def check_constraints(self, action: str, context: Dict) -> Dict:
        violations = []
        
        for constraint in self.constraints:
            if not constraint.enabled:
                continue
            
            is_violated = self._evaluate_constraint(constraint, action, context)
            
            if is_violated:
                violations.append({
                    "constraint_id": constraint.id,
                    "name": constraint.name,
                    "type": constraint.constraint_type,
                    "severity": constraint.severity,
                    "description": constraint.description
                })
                
                self.constraint_violations.append({
                    "constraint_id": constraint.id,
                    "action": action,
                    "timestamp": datetime.now().isoformat()
                })
        
        return {
            "passed": len(violations) == 0,
            "violations": violations,
            "action": action
        }
    
    def _evaluate_constraint(self, constraint: EthicalConstraint, action: str, 
                            context: Dict) -> bool:
        rule = constraint.rule.lower()
        
        if "harm" in rule and context.get("harmful"):
            return True
        
        if "destructive" in rule and context.get("destructive_action"):
            return True
        
        if "unauthorized" in rule and not context.get("authorized"):
            return True
        
        if constraint.constraint_type == "safety":
            if context.get("safety_critical") and not context.get("safety_verified"):
                return True
        
        return False
    
    def enable_constraint(self, constraint_id: str) -> bool:
        for c in self.constraints:
            if c.id == constraint_id:
                c.enabled = True
                return True
        return False
    
    def disable_constraint(self, constraint_id: str) -> bool:
        for c in self.constraints:
            if c.id == constraint_id:
                c.enabled = False
                return True
        return False
    
    def get_constraints(self) -> List[Dict]:
        return [
            {
                "id": c.id,
                "name": c.name,
                "type": c.constraint_type,
                "enabled": c.enabled,
                "severity": c.severity
            }
            for c in self.constraints
        ]


class HumanOverrideSystem:
    def __init__(self):
        self.pending_overrides: List[Dict] = []
        self.override_history: List[Dict] = []
        
    def request_override(self, decision_id: str, reason: str, requester: str = "system") -> str:
        override_request = {
            "id": hashlib.md5(f"{decision_id}{datetime.now()}".encode()).hexdigest()[:12],
            "decision_id": decision_id,
            "reason": reason,
            "requester": requester,
            "status": "pending",
            "requested_at": datetime.now().isoformat()
        }
        
        self.pending_overrides.append(override_request)
        
        return override_request["id"]
    
    def approve_override(self, override_id: str, approver: str) -> bool:
        for override in self.pending_overrides:
            if override["id"] == override_id:
                override["status"] = "approved"
                override["approver"] = approver
                override["approved_at"] = datetime.now().isoformat()
                
                self.override_history.append(override.copy())
                self.pending_overrides.remove(override)
                
                return True
        return False
    
    def reject_override(self, override_id: str, rejector: str, reason: str) -> bool:
        for override in self.pending_overrides:
            if override["id"] == override_id:
                override["status"] = "rejected"
                override["rejector"] = rejector
                override["reason"] = reason
                override["rejected_at"] = datetime.now().isoformat()
                
                self.override_history.append(override.copy())
                self.pending_overrides.remove(override)
                
                return True
        return False
    
    def get_pending_overrides(self) -> List[Dict]:
        return self.pending_overrides


class AdaptiveRuleEngine:
    def __init__(self):
        self.rules: List[DecisionRule] = []
        self.rule_history: List[Dict] = []
        
    def add_rule(self, name: str, condition: Callable, action: Callable, 
                priority: Priority, requires_approval: bool = True, 
                auto_execute: bool = False) -> str:
        rule = DecisionRule(
            id=hashlib.md5(name.encode()).hexdigest()[:8],
            name=name,
            condition=condition,
            action=action,
            priority=priority,
            requires_approval=requires_approval,
            auto_execute=auto_execute
        )
        
        self.rules.append(rule)
        
        return rule.id
    
    def evaluate_rules(self, context: Dict) -> List[Decision]:
        triggered = []
        
        sorted_rules = sorted(self.rules, key=lambda r: r.priority.value)
        
        for rule in sorted_rules:
            try:
                if rule.condition(context):
                    decision = Decision(
                        id=hashlib.md5(f"{rule.name}{datetime.now()}".encode()).hexdigest()[:12],
                        timestamp=datetime.now(),
                        action=rule.name,
                        priority=rule.priority,
                        context=context
                    )
                    
                    triggered.append(decision)
                    
                    self.rule_history.append({
                        "rule_id": rule.id,
                        "rule_name": rule.name,
                        "triggered_at": datetime.now().isoformat(),
                        "context": context
                    })
                    
            except Exception as e:
                logger.error(f"Rule evaluation error for {rule.name}: {e}")
        
        return triggered
    
    def execute_rule(self, rule_id: str, context: Dict) -> Optional[Dict]:
        for rule in self.rules:
            if rule.id == rule_id:
                try:
                    result = rule.action(context)
                    return result
                except Exception as e:
                    logger.error(f"Rule execution error: {e}")
                    return None
        return None


class RiskAwareAutonomy:
    def __init__(self):
        self.autonomy_levels = {
            "full_auto": 5,
            "high_auto": 4,
            "moderate_auto": 3,
            "low_auto": 2,
            "supervised": 1,
            "manual": 0
        }
        self.current_level = "moderate_auto"
        self.risk_thresholds = {
            "critical": 0.9,
            "high": 0.7,
            "medium": 0.5,
            "low": 0.3
        }
        
    def set_autonomy_level(self, level: str) -> bool:
        if level in self.autonomy_levels:
            self.current_level = level
            return True
        return False
    
    def get_autonomy_level(self) -> str:
        return self.current_level
    
    def determine_approval_needed(self, risk_level: float) -> bool:
        autonomy_value = self.autonomy_levels.get(self.current_level, 3)
        
        if autonomy_value >= 4:
            return risk_level > self.risk_thresholds["critical"]
        elif autonomy_value >= 3:
            return risk_level > self.risk_thresholds["high"]
        elif autonomy_value >= 2:
            return risk_level > self.risk_thresholds["medium"]
        else:
            return True
    
    def adjust_autonomy_for_risk(self, risk_level: float):
        if risk_level >= self.risk_thresholds["critical"]:
            self.current_level = "supervised"
        elif risk_level >= self.risk_thresholds["high"]:
            self.current_level = "low_auto"


class DecisionTransparency:
    def __init__(self):
        self.decision_logs: List[Dict] = []
        
    def log_decision(self, decision: Decision, reasoning: str, factors: List[str]):
        log_entry = {
            "decision_id": decision.id,
            "action": decision.action,
            "priority": decision.priority.value,
            "status": decision.status.value,
            "reasoning": reasoning,
            "factors": factors,
            "timestamp": decision.timestamp.isoformat(),
            "context": decision.context
        }
        
        self.decision_logs.append(log_entry)
        
    def explain_decision(self, decision_id: str) -> Optional[Dict]:
        for log in self.decision_logs:
            if log["decision_id"] == decision_id:
                return {
                    "action": log["action"],
                    "reasoning": log["reasoning"],
                    "factors": log["factors"],
                    "timestamp": log["timestamp"]
                }
        return None
    
    def get_decision_history(self, limit: int = 50) -> List[Dict]:
        return self.decision_logs[-limit:]


class MultiObjectiveOptimizer:
    def __init__(self):
        self.objectives: Dict[str, float] = {}
        
    def add_objective(self, name: str, weight: float):
        self.objectives[name] = weight
    
    def optimize(self, options: List[Dict]) -> Dict:
        if not options:
            return {"error": "No options provided"}
        
        scored_options = []
        
        for option in options:
            score = 0.0
            
            for obj_name, weight in self.objectives.items():
                obj_value = option.get(obj_name, 0)
                score += obj_value * weight
            
            scored_options.append({
                "option": option,
                "score": score,
                "breakdown": {
                    obj_name: option.get(obj_name, 0) * weight 
                    for obj_name in self.objectives
                }
            })
        
        scored_options.sort(key=lambda x: x["score"], reverse=True)
        
        return {
            "best_option": scored_options[0]["option"],
            "score": scored_options[0]["score"],
            "all_options": scored_options
        }


class AutonomousDecisionSystem:
    def __init__(self):
        self.action_selector = PriorityActionSelector()
        self.ethics = EthicalConstraintEngine()
        self.human_override = HumanOverrideSystem()
        self.rules = AdaptiveRuleEngine()
        self.autonomy = RiskAwareAutonomy()
        self.transparency = DecisionTransparency()
        self.optimizer = MultiObjectiveOptimizer()
        
        self._setup_default_constraints()
        
    def _setup_default_constraints(self):
        self.ethics.add_constraint(
            "prevent_harm",
            "Prevent actions that could cause harm to users or systems",
            "safety",
            "action must not be harmful",
            "critical"
        )
        
        self.ethics.add_constraint(
            "preserve_data",
            "Prevent destructive actions without confirmation",
            "data_safety",
            "require confirmation for destructive actions",
            "high"
        )
        
        self.ethics.add_constraint(
            "respect_privacy",
            "Do not access or share private information inappropriately",
            "privacy",
            "maintain user privacy",
            "high"
        )
        
        self.ethics.add_constraint(
            "maintain_transparency",
            "All decisions should be explainable",
            "transparency",
            "provide reasoning for decisions",
            "medium"
        )
    
    async def make_decision(self, action: str, context: Dict = None, 
                           priority: Priority = Priority.NORMAL) -> Dict:
        context = context or {}
        
        constraint_check = self.ethics.check_constraints(action, context)
        
        if not constraint_check["passed"]:
            return {
                "decision": "blocked",
                "reason": "ethical_constraint_violation",
                "violations": constraint_check["violations"]
            }
        
        risk_level = context.get("risk_level", 0.3)
        
        approval_needed = self.autonomy.determine_approval_needed(risk_level)
        
        decision_id = self.action_selector.add_action(action, priority, context)
        
        if not approval_needed:
            self.action_selector.approve_action(decision_id, "auto_system")
            
            if self.autonomy.get_autonomy_level() != "manual":
                self.action_selector.start_execution(decision_id)
                
                result = {"executed": True, "mode": "auto"}
                self.action_selector.complete_execution(decision_id, result)
                
                self.transparency.log_decision(
                    Decision(
                        id=decision_id,
                        timestamp=datetime.now(),
                        action=action,
                        priority=priority,
                        status=DecisionStatus.COMPLETED
                    ),
                    f"Auto-approved due to low risk (level: {risk_level})",
                    ["risk_level", "autonomy_setting"]
                )
                
                return {
                    "decision_id": decision_id,
                    "status": "executed",
                    "mode": "automatic"
                }
        
        return {
            "decision_id": decision_id,
            "status": "approval_required",
            "reason": "requires_human_approval",
            "risk_level": risk_level
        }
    
    def approve_decision(self, decision_id: str, approver: str = "human") -> bool:
        return self.action_selector.approve_action(decision_id, approver)
    
    def request_human_override(self, decision_id: str, reason: str) -> str:
        return self.human_override.request_override(decision_id, reason)
    
    def get_pending_decisions(self) -> List[Dict]:
        return [
            {
                "id": d.id,
                "action": d.action,
                "priority": d.priority.value,
                "timestamp": d.timestamp.isoformat()
            }
            for d in self.action_selector.action_queue
        ]
    
    def get_system_status(self) -> Dict:
        return {
            "autonomy_level": self.autonomy.get_autonomy_level(),
            "queue_status": self.action_selector.get_queue_status(),
            "active_constraints": len([c for c in self.ethics.constraints if c.enabled]),
            "pending_overrides": len(self.human_override.get_pending_overrides())
        }


_decision_system: Optional[AutonomousDecisionSystem] = None

def get_decision_system() -> AutonomousDecisionSystem:
    global _decision_system
    if _decision_system is None:
        _decision_system = AutonomousDecisionSystem()
    return _decision_system
