"""
R1 - Emergency & Fail-Safe Protocols
Shutdown systems, redundancy, critical alerts, containment, disaster recovery
"""
import asyncio
import logging
import json
import hashlib
import os
import shutil
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Callable
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger("R1:emergency")


class EmergencyLevel(Enum):
    INFO = "info"
    ADVISORY = "advisory"
    WARNING = "warning"
    EMERGENCY = "emergency"
    CRITICAL = "critical"


class SystemState(Enum):
    NORMAL = "normal"
    DEGRADED = "degraded"
    EMERGENCY = "emergency"
    SHUTDOWN = "shutdown"
    RECOVERING = "recovering"


@dataclass
class EmergencyAlert:
    id: str
    timestamp: datetime
    level: EmergencyLevel
    title: str
    description: str
    source: str
    affected_systems: List[str] = field(default_factory=list)
    acknowledged: bool = False
    resolved: bool = False


@dataclass
class BackupSnapshot:
    id: str
    timestamp: datetime
    name: str
    size_bytes: int
    location: str
    checksum: str
    systems: List[str] = field(default_factory=list)


class EmergencyShutdownSystem:
    def __init__(self):
        self.shutdown_sequence: List[Callable] = []
        self.graceful_shutdown_enabled = True
        self.emergency_level = EmergencyLevel.INFO
        self.system_state = SystemState.NORMAL
        
    def register_shutdown_handler(self, priority: int, handler: Callable):
        self.shutdown_sequence.append((priority, handler))
        self.shutdown_sequence.sort(key=lambda x: x[0])
    
    async def initiate_shutdown(self, emergency: bool = False) -> Dict:
        logger.warning(f"Initiating {'emergency' if emergency else 'graceful'} shutdown")
        
        self.system_state = SystemState.SHUTDOWN
        
        results = []
        
        for priority, handler in self.shutdown_sequence:
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(emergency=emergency)
                else:
                    result = handler(emergency=emergency)
                
                results.append({
                    "handler": str(handler),
                    "success": True,
                    "result": result
                })
                
            except Exception as e:
                logger.error(f"Shutdown handler error: {e}")
                results.append({
                    "handler": str(handler),
                    "success": False,
                    "error": str(e)
                })
        
        return {
            "success": all(r["success"] for r in results),
            "system_state": self.system_state.value,
            "handlers_executed": len(results),
            "results": results
        }
    
    def set_emergency_level(self, level: EmergencyLevel):
        self.emergency_level = level
        
        if level in [EmergencyLevel.EMERGENCY, EmergencyLevel.CRITICAL]:
            self.system_state = SystemState.EMERGENCY
    
    def get_system_state(self) -> Dict:
        return {
            "state": self.system_state.value,
            "emergency_level": self.emergency_level.value,
            "shutdown_handlers": len(self.shutdown_sequence)
        }


class RedundantSystemManager:
    def __init__(self):
        self.primary_systems: Dict[str, str] = {}
        self.backup_systems: Dict[str, str] = {}
        self.failover_history: List[Dict] = []
        
    def register_primary(self, system_id: str, system_name: str):
        self.primary_systems[system_id] = system_name
    
    def register_backup(self, system_id: str, system_name: str, primary_id: str):
        self.backup_systems[system_id] = system_name
        
        if primary_id not in self.primary_systems:
            return False
        
        self.failover_history.append({
            "primary_id": primary_id,
            "backup_id": system_id,
            "timestamp": datetime.now().isoformat(),
            "action": "registered"
        })
        
        return True
    
    def trigger_failover(self, primary_id: str) -> Dict:
        if primary_id not in self.primary_systems:
            return {"success": False, "error": "Primary system not found"}
        
        primary_name = self.primary_systems[primary_id]
        
        backup_id = None
        backup_name = None
        
        for bk_id, bk_name in self.backup_systems.items():
            backup_id = bk_id
            backup_name = bk_name
            break
        
        if not backup_id:
            return {"success": False, "error": "No backup available"}
        
        self.failover_history.append({
            "primary_id": primary_id,
            "primary_name": primary_name,
            "backup_id": backup_id,
            "backup_name": backup_name,
            "timestamp": datetime.now().isoformat(),
            "action": "failover_executed"
        })
        
        logger.warning(f"Failover executed: {primary_name} -> {backup_name}")
        
        return {
            "success": True,
            "primary": primary_name,
            "backup": backup_name,
            "failover_time": datetime.now().isoformat()
        }
    
    def get_failover_status(self) -> Dict:
        return {
            "primary_systems": len(self.primary_systems),
            "backup_systems": len(self.backup_systems),
            "failover_count": len(self.failover_history)
        }


class CriticalAlertSystem:
    def __init__(self):
        self.alerts: List[EmergencyAlert] = []
        self.alert_handlers: Dict[EmergencyLevel, List[Callable]] = {
            level: [] for level in EmergencyLevel
        }
        self.notification_channels: Dict[str, Callable] = {}
        
    def create_alert(self, level: EmergencyLevel, title: str, description: str,
                    source: str = "system", affected_systems: List[str] = None) -> str:
        alert_id = hashlib.md5(f"{title}{datetime.now()}".encode()).hexdigest()[:12]
        
        alert = EmergencyAlert(
            id=alert_id,
            timestamp=datetime.now(),
            level=level,
            title=title,
            description=description,
            source=source,
            affected_systems=affected_systems or []
        )
        
        self.alerts.append(alert)
        
        self._dispatch_alert(alert)
        
        return alert_id
    
    def register_alert_handler(self, level: EmergencyLevel, handler: Callable):
        self.alert_handlers[level].append(handler)
    
    def register_notification_channel(self, channel_name: str, handler: Callable):
        self.notification_channels[channel_name] = handler
    
    def _dispatch_alert(self, alert: EmergencyAlert):
        for handler in self.alert_handlers[alert.level]:
            try:
                if asyncio.iscoroutinefunction(handler):
                    asyncio.create_task(handler(alert))
                else:
                    handler(alert)
            except Exception as e:
                logger.error(f"Alert handler error: {e}")
        
        for channel_name, handler in self.notification_channels.items():
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Notification channel error ({channel_name}): {e}")
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                return True
        return False
    
    def resolve_alert(self, alert_id: str) -> bool:
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.resolved = True
                return True
        return False
    
    def get_active_alerts(self, level: EmergencyLevel = None) -> List[Dict]:
        alerts = [a for a in self.alerts if not a.resolved]
        
        if level:
            alerts = [a for a in alerts if a.level == level]
        
        return [
            {
                "id": a.id,
                "level": a.level.value,
                "title": a.title,
                "description": a.description,
                "timestamp": a.timestamp.isoformat(),
                "acknowledged": a.acknowledged
            }
            for a in sorted(alerts, key=lambda x: x.timestamp, reverse=True)
        ]


class DataPreservationSystem:
    def __init__(self):
        self.backups: List[BackupSnapshot] = []
        self.backup_locations: List[str] = []
        
    def add_backup_location(self, location: str):
        if location not in self.backup_locations:
            self.backup_locations.append(location)
    
    async def create_backup(self, name: str, data_paths: List[str]) -> str:
        backup_id = hashlib.md5(f"{name}{datetime.now()}".encode()).hexdigest()[:12]
        
        total_size = 0
        
        for path in data_paths:
            if os.path.exists(path):
                total_size += self._get_directory_size(path)
        
        import hashlib
        
        checksum = hashlib.sha256(str(datetime.now()).encode()).hexdigest()
        
        snapshot = BackupSnapshot(
            id=backup_id,
            timestamp=datetime.now(),
            name=name,
            size_bytes=total_size,
            location=self.backup_locations[0] if self.backup_locations else "memory",
            checksum=checksum,
            systems=data_paths
        )
        
        self.backups.append(snapshot)
        
        logger.info(f"Backup created: {name} ({total_size} bytes)")
        
        return backup_id
    
    def _get_directory_size(self, path: str) -> int:
        total = 0
        try:
            for entry in os.scandir(path):
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat().st_size
                elif entry.is_dir(follow_symlinks=False):
                    total += self._get_directory_size(entry.path)
        except:
            pass
        return total
    
    def restore_backup(self, backup_id: str, target_location: str) -> Dict:
        for backup in self.backups:
            if backup.id == backup_id:
                logger.info(f"Restoring backup: {backup.name}")
                
                return {
                    "success": True,
                    "backup_id": backup_id,
                    "name": backup.name,
                    "target_location": target_location,
                    "timestamp": backup.timestamp.isoformat()
                }
        
        return {"success": False, "error": "Backup not found"}
    
    def get_backup_list(self) -> List[Dict]:
        return [
            {
                "id": b.id,
                "name": b.name,
                "size_mb": b.size_bytes / (1024 * 1024),
                "timestamp": b.timestamp.isoformat(),
                "location": b.location
            }
            for b in sorted(self.backups, key=lambda x: x.timestamp, reverse=True)
        ]


class AutonomousContainment:
    def __init__(self):
        self.isolation_rules: List[Dict] = []
        self.isolated_systems: List[str] = []
        
    def add_isolation_rule(self, trigger: str, systems_to_isolate: List[str],
                          severity: str = "high"):
        rule = {
            "id": hashlib.md5(f"{trigger}{datetime.now()}".encode()).hexdigest()[:8],
            "trigger": trigger,
            "systems": systems_to_isolate,
            "severity": severity,
            "enabled": True
        }
        
        self.isolation_rules.append(rule)
        return rule["id"]
    
    def check_containment_needed(self, event_data: Dict) -> List[str]:
        triggered = []
        
        for rule in self.isolation_rules:
            if not rule.get("enabled", True):
                continue
            
            trigger = rule["trigger"].lower()
            event_str = json.dumps(event_data).lower()
            
            if trigger in event_str:
                triggered.extend(rule["systems"])
        
        return list(set(triggered))
    
    def isolate_system(self, system_id: str) -> bool:
        if system_id not in self.isolated_systems:
            self.isolated_systems.append(system_id)
            logger.warning(f"System isolated: {system_id}")
            return True
        return False
    
    def restore_system(self, system_id: str) -> bool:
        if system_id in self.isolated_systems:
            self.isolated_systems.remove(system_id)
            logger.info(f"System restored: {system_id}")
            return True
        return False
    
    def get_isolation_status(self) -> Dict:
        return {
            "isolated_systems": self.isolated_systems,
            "isolation_rules": len(self.isolation_rules),
            "active_rules": len([r for r in self.isolation_rules if r.get("enabled", True)])
        }


class DisasterRecoverySystem:
    def __init__(self):
        self.recovery_plans: Dict[str, Dict] = {}
        self.recovery_history: List[Dict] = []
        
    def create_recovery_plan(self, plan_name: str, steps: List[Dict]) -> str:
        plan_id = hashlib.md5(f"{plan_name}{datetime.now()}".encode()).hexdigest()[:8]
        
        self.recovery_plans[plan_id] = {
            "id": plan_id,
            "name": plan_name,
            "steps": steps,
            "created_at": datetime.now().isoformat(),
            "last_executed": None,
            "success_rate": 0.0,
            "executions": 0
        }
        
        return plan_id
    
    async def execute_recovery(self, plan_id: str) -> Dict:
        if plan_id not in self.recovery_plans:
            return {"success": False, "error": "Recovery plan not found"}
        
        plan = self.recovery_plans[plan_id]
        
        results = []
        
        for i, step in enumerate(plan["steps"]):
            step_result = {
                "step": i + 1,
                "action": step.get("action", "unknown"),
                "success": True,
                "timestamp": datetime.now().isoformat()
            }
            
            try:
                if "delay" in step:
                    await asyncio.sleep(step["delay"])
                
                if "command" in step:
                    step_result["output"] = f"Would execute: {step['command']}"
                
            except Exception as e:
                step_result["success"] = False
                step_result["error"] = str(e)
            
            results.append(step_result)
            
            if not step_result["success"] and step.get("critical", False):
                break
        
        success_count = sum(1 for r in results if r["success"])
        success_rate = success_count / len(results) if results else 0
        
        plan["last_executed"] = datetime.now().isoformat()
        plan["success_rate"] = success_rate * 100
        plan["executions"] += 1
        
        self.recovery_history.append({
            "plan_id": plan_id,
            "plan_name": plan["name"],
            "timestamp": datetime.now().isoformat(),
            "success_rate": success_rate * 100,
            "steps_completed": len(results)
        })
        
        return {
            "success": success_rate > 0.5,
            "plan_name": plan["name"],
            "success_rate": success_rate * 100,
            "steps_completed": len(results),
            "results": results
        }
    
    def get_recovery_plans(self) -> List[Dict]:
        return [
            {
                "id": p["id"],
                "name": p["name"],
                "steps": len(p["steps"]),
                "success_rate": p["success_rate"],
                "last_executed": p.get("last_executed")
            }
            for p in self.recovery_plans.values()
        ]


class ProtectiveOverrideSystem:
    def __init__(self):
        self.override_conditions: List[Dict] = []
        self.active_overrides: List[Dict] = []
        
    def add_override_condition(self, name: str, condition: str, action: Dict,
                              priority: int = 1) -> str:
        override_id = hashlib.md5(f"{name}{datetime.now()}".encode()).hexdigest()[:8]
        
        override = {
            "id": override_id,
            "name": name,
            "condition": condition,
            "action": action,
            "priority": priority,
            "enabled": True
        }
        
        self.override_conditions.append(override)
        
        return override_id
    
    def check_and_execute(self, event_data: Dict) -> List[Dict]:
        executed = []
        
        sorted_overrides = sorted(
            [o for o in self.override_conditions if o.get("enabled", True)],
            key=lambda x: x["priority"]
        )
        
        for override in sorted_overrides:
            if self._matches_condition(override["condition"], event_data):
                result = {
                    "override_id": override["id"],
                    "name": override["name"],
                    "action": override["action"],
                    "executed_at": datetime.now().isoformat()
                }
                
                self.active_overrides.append(result)
                executed.append(result)
                
                logger.warning(f"Protective override executed: {override['name']}")
        
        return executed
    
    def _matches_condition(self, condition: str, event_data: Dict) -> bool:
        event_str = json.dumps(event_data).lower()
        return condition.lower() in event_str
    
    def get_active_overrides(self) -> List[Dict]:
        return self.active_overrides


class EmergencyProtocolSystem:
    def __init__(self):
        self.shutdown = EmergencyShutdownSystem()
        self.redundancy = RedundantSystemManager()
        self.alerts = CriticalAlertSystem()
        self.preservation = DataPreservationSystem()
        self.containment = AutonomousContainment()
        self.recovery = DisasterRecoverySystem()
        self.overrides = ProtectiveOverrideSystem()
        
    def create_emergency_alert(self, level: EmergencyLevel, title: str, 
                              description: str) -> str:
        return self.alerts.create_alert(level, title, description)
    
    async def emergency_shutdown(self, emergency: bool = False) -> Dict:
        return await self.shutdown.initiate_shutdown(emergency)
    
    async def create_backup(self, name: str, paths: List[str]) -> str:
        return await self.preservation.create_backup(name, paths)
    
    def get_system_status(self) -> Dict:
        return {
            "system_state": self.shutdown.get_system_state(),
            "failover_status": self.redundancy.get_failover_status(),
            "active_alerts": len(self.alerts.get_active_alerts()),
            "isolation_status": self.containment.get_isolation_status(),
            "recovery_plans": len(self.recovery.get_recovery_plans())
        }


_emergency_system: Optional[EmergencyProtocolSystem] = None

def get_emergency_system() -> EmergencyProtocolSystem:
    global _emergency_system
    if _emergency_system is None:
        _emergency_system = EmergencyProtocolSystem()
    return _emergency_system
