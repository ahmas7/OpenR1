"""
R1 - Infrastructure & Automation Control Systems
Facility automation, security access, power management, smart buildings
"""
import asyncio
import logging
import json
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Callable
from datetime import datetime, timedelta
from enum import Enum
import subprocess

logger = logging.getLogger("R1:infrastructure")


class DeviceStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    STANDBY = "standby"
    ERROR = "error"
    MAINTENANCE = "maintenance"


class AccessLevel(Enum):
    NONE = 0
    GUEST = 1
    USER = 2
    ADMIN = 3
    SUPER_ADMIN = 4


@dataclass
class Device:
    id: str
    name: str
    device_type: str
    status: DeviceStatus
    location: str
    capabilities: List[str] = field(default_factory=list)
    state: Dict[str, Any] = field(default_factory=dict)
    last_seen: datetime = field(default_factory=datetime.now)


@dataclass
class AccessLog:
    id: str
    timestamp: datetime
    user_id: str
    resource: str
    action: str
    result: str
    ip_address: Optional[str] = None


@dataclass
class Schedule:
    id: str
    name: str
    schedule_type: str
    cron_expression: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    recurrence: Optional[str] = None
    action: Dict = field(default_factory=dict)
    enabled: bool = True


class FacilityAutomation:
    def __init__(self):
        self.devices: Dict[str, Device] = {}
        self.automation_rules: List[Dict] = []
        self.schedules: List[Schedule] = []
        self.energy_usage: Dict[str, float] = {}
        
    def register_device(self, device: Device) -> bool:
        self.devices[device.id] = device
        logger.info(f"Registered device: {device.name}")
        return True
    
    def unregister_device(self, device_id: str) -> bool:
        if device_id in self.devices:
            del self.devices[device_id]
            return True
        return False
    
    def get_device(self, device_id: str) -> Optional[Device]:
        return self.devices.get(device_id)
    
    def get_devices_by_type(self, device_type: str) -> List[Device]:
        return [d for d in self.devices.values() if d.device_type == device_type]
    
    def get_devices_by_location(self, location: str) -> List[Device]:
        return [d for d in self.devices.values() if d.location == location]
    
    async def control_device(self, device_id: str, command: str, params: Dict = None) -> Dict:
        device = self.devices.get(device_id)
        if not device:
            return {"success": False, "error": "Device not found"}
        
        if device.status != DeviceStatus.ONLINE:
            return {"success": False, "error": f"Device is {device.status.value}"}
        
        params = params or {}
        
        if command == "turn_on":
            device.state["powered"] = True
            device.status = DeviceStatus.ONLINE
        elif command == "turn_off":
            device.state["powered"] = False
            device.status = DeviceStatus.STANDBY
        elif command == "set_value":
            for key, value in params.items():
                device.state[key] = value
        elif command == "reset":
            device.state = {}
            device.status = DeviceStatus.ONLINE
        
        device.last_seen = datetime.now()
        
        return {
            "success": True,
            "device_id": device_id,
            "command": command,
            "new_state": device.state
        }
    
    def add_automation_rule(self, name: str, trigger: Dict, action: Dict, conditions: List[Dict] = None):
        rule = {
            "id": hashlib.md5(name.encode()).hexdigest()[:8],
            "name": name,
            "trigger": trigger,
            "action": action,
            "conditions": conditions or [],
            "enabled": True,
            "created_at": datetime.now().isoformat()
        }
        self.automation_rules.append(rule)
        return rule["id"]
    
    async def evaluate_rules(self, event: Dict):
        triggered = []
        
        for rule in self.automation_rules:
            if not rule.get("enabled", True):
                continue
            
            trigger = rule.get("trigger", {})
            
            if self._matches_trigger(event, trigger):
                if self._check_conditions(event, rule.get("conditions", [])):
                    triggered.append(rule)
        
        for rule in triggered:
            await self._execute_rule_action(rule, event)
        
        return triggered
    
    def _matches_trigger(self, event: Dict, trigger: Dict) -> bool:
        event_type = trigger.get("type")
        
        if event_type == "device_state_change":
            return event.get("type") == "device_state" and event.get("device_id") == trigger.get("device_id")
        elif event_type == "time":
            return event.get("type") == "time" and event.get("time") == trigger.get("time")
        elif event_type == "manual":
            return event.get("type") == "manual"
        
        return False
    
    def _check_conditions(self, event: Dict, conditions: List[Dict]) -> bool:
        if not conditions:
            return True
        
        for condition in conditions:
            cond_type = condition.get("type")
            
            if cond_type == "device_state":
                device_id = condition.get("device_id")
                state_key = condition.get("state_key")
                expected = condition.get("value")
                
                device = self.devices.get(device_id)
                if not device:
                    return False
                if device.state.get(state_key) != expected:
                    return False
            
            elif cond_type == "time_range":
                pass
        
        return True
    
    async def _execute_rule_action(self, rule: Dict, event: Dict):
        action = rule.get("action", {})
        action_type = action.get("type")
        
        if action_type == "device_control":
            device_id = action.get("device_id")
            command = action.get("command")
            params = action.get("params", {})
            await self.control_device(device_id, command, params)
        
        elif action_type == "notify":
            logger.info(f"Automation notification: {action.get('message')}")


class SecurityAccessControl:
    def __init__(self):
        self.users: Dict[str, Dict] = {}
        self.access_logs: List[AccessLog] = []
        self.access_policies: Dict[str, Dict] = {}
        self.doors: Dict[str, Dict] = {}
        
    def add_user(self, user_id: str, name: str, access_level: AccessLevel = AccessLevel.USER):
        self.users[user_id] = {
            "name": name,
            "access_level": access_level.value,
            "badges": [],
            "created_at": datetime.now().isoformat(),
            "active": True
        }
        
    def remove_user(self, user_id: str) -> bool:
        if user_id in self.users:
            del self.users[user_id]
            return True
        return False
    
    def grant_access(self, user_id: str, resource: str) -> bool:
        if user_id not in self.users:
            return False
        
        user = self.users[user_id]
        policy = self.access_policies.get(resource, {})
        
        required_level = policy.get("required_level", AccessLevel.USER.value)
        
        if user["access_level"] >= required_level:
            self._log_access(user_id, resource, "grant", "success")
            return True
        
        self._log_access(user_id, resource, "grant", "denied")
        return False
    
    def check_access(self, user_id: str, resource: str) -> bool:
        if user_id not in self.users:
            return False
        
        user = self.users[user_id]
        
        if not user.get("active", True):
            return False
        
        policy = self.access_policies.get(resource, {})
        required_level = policy.get("required_level", AccessLevel.USER.value)
        
        return user["access_level"] >= required_level
    
    def set_access_policy(self, resource: str, policy: Dict):
        self.access_policies[resource] = policy
    
    def _log_access(self, user_id: str, resource: str, action: str, result: str):
        log = AccessLog(
            id=hashlib.md5(f"{user_id}{resource}{datetime.now()}".encode()).hexdigest()[:12],
            timestamp=datetime.now(),
            user_id=user_id,
            resource=resource,
            action=action,
            result=result
        )
        self.access_logs.append(log)
    
    def get_access_logs(self, user_id: str = None, limit: int = 100) -> List[Dict]:
        logs = self.access_logs
        
        if user_id:
            logs = [l for l in logs if l.user_id == user_id]
        
        logs = sorted(logs, key=lambda x: x.timestamp, reverse=True)
        
        return [
            {
                "id": l.id,
                "timestamp": l.timestamp.isoformat(),
                "user_id": l.user_id,
                "resource": l.resource,
                "action": l.action,
                "result": l.result
            }
            for l in logs[:limit]
        ]


class PowerGridManager:
    def __init__(self):
        self.power_sources: Dict[str, Dict] = {}
        self.power_consumers: Dict[str, Dict] = {}
        self.power_history: List[Dict] = []
        
    def add_power_source(self, source_id: str, name: str, capacity_watts: float, source_type: str = "grid"):
        self.power_sources[source_id] = {
            "name": name,
            "capacity_watts": capacity_watts,
            "current_output": 0.0,
            "type": source_type,
            "status": "online"
        }
        
    def add_power_consumer(self, consumer_id: str, name: str, power_watts: float):
        self.power_consumers[consumer_id] = {
            "name": name,
            "power_watts": power_watts,
            "active": False
        }
    
    def get_total_capacity(self) -> float:
        return sum(s["capacity_watts"] for s in self.power_sources.values() if s["status"] == "online")
    
    def get_total_consumption(self) -> float:
        return sum(
            c["power_watts"] 
            for c in self.power_consumers.values() 
            if c["active"]
        )
    
    def get_power_balance(self) -> float:
        return self.get_total_capacity() - self.get_total_consumption()
    
    def toggle_consumer(self, consumer_id: str, active: bool) -> bool:
        if consumer_id not in self.power_consumers:
            return False
        
        power_needed = self.power_consumers[consumer_id]["power_watts"] if active else 0
        
        if active and power_needed > self.get_power_balance():
            logger.warning(f"Insufficient power for {consumer_id}")
            return False
        
        self.power_consumers[consumer_id]["active"] = active
        
        self.power_history.append({
            "timestamp": datetime.now().isoformat(),
            "consumer_id": consumer_id,
            "active": active,
            "consumption": self.get_total_consumption()
        })
        
        return True
    
    def optimize_power_distribution(self) -> Dict:
        total_capacity = self.get_total_capacity()
        total_consumption = self.get_total_consumption()
        balance = self.get_power_balance()
        
        recommendations = []
        
        if balance < 0:
            recommendations.append({
                "type": "power_shortage",
                "message": "Power demand exceeds supply",
                "action": "Reduce load or add power sources"
            })
        elif balance < total_capacity * 0.1:
            recommendations.append({
                "type": "low_reserve",
                "message": "Power reserve is low",
                "action": "Consider adding backup power"
            })
        
        for consumer_id, consumer in self.power_consumers.items():
            if consumer["active"] and consumer["power_watts"] > total_capacity * 0.3:
                recommendations.append({
                    "type": "high_consumer",
                    "message": f"{consumer['name']} uses {consumer['power_watts']}W ({consumer['power_watts']/total_capacity*100:.1f}%)",
                    "action": "Consider reducing usage"
                })
        
        return {
            "total_capacity": total_capacity,
            "total_consumption": total_consumption,
            "balance": balance,
            "utilization_percent": (total_consumption/total_capacity*100) if total_capacity > 0 else 0,
            "recommendations": recommendations
        }


class TransportControl:
    def __init__(self):
        self.vehicles: Dict[str, Dict] = {}
        self.routes: Dict[str, Dict] = {}
        self.active_trips: Dict[str, Dict] = {}
        
    def register_vehicle(self, vehicle_id: str, vehicle_type: str, capacity: int):
        self.vehicles[vehicle_id] = {
            "type": vehicle_type,
            "capacity": capacity,
            "status": "available",
            "location": None,
            "battery_level": 100 if vehicle_type == "ev" else None
        }
    
    def assign_route(self, vehicle_id: str, route_id: str) -> bool:
        if vehicle_id not in self.vehicles:
            return False
        if route_id not in self.routes:
            return False
        
        self.vehicles[vehicle_id]["status"] = "assigned"
        self.vehicles[vehicle_id]["current_route"] = route_id
        
        return True
    
    def update_vehicle_location(self, vehicle_id: str, lat: float, lon: float):
        if vehicle_id in self.vehicles:
            self.vehicles[vehicle_id]["location"] = {"lat": lat, "lon": lon}
    
    def get_vehicle_status(self, vehicle_id: str) -> Optional[Dict]:
        return self.vehicles.get(vehicle_id)
    
    def create_route(self, route_id: str, name: str, waypoints: List[Dict]):
        self.routes[route_id] = {
            "name": name,
            "waypoints": waypoints,
            "distance_km": sum(
                self._calculate_distance(wp1, wp2) 
                for wp1, wp2 in zip(waypoints[:-1], waypoints[1:])
            )
        }
    
    def _calculate_distance(self, wp1: Dict, wp2: Dict) -> float:
        import math
        lat1, lon1 = wp1.get("lat", 0), wp1.get("lon", 0)
        lat2, lon2 = wp2.get("lat", 0), wp2.get("lon", 0)
        
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c


class SmartBuildingManager:
    def __init__(self):
        self.zones: Dict[str, Dict] = {}
        self.sensors: Dict[str, Dict] = {}
        self.schedules: List[Schedule] = []
        
    def add_zone(self, zone_id: str, name: str, zone_type: str):
        self.zones[zone_id] = {
            "name": name,
            "type": zone_type,
            "temperature": 22.0,
            "humidity": 45,
            "lights": "off",
            "hvac": "auto",
            "occupancy": 0
        }
    
    def add_sensor(self, sensor_id: str, zone_id: str, sensor_type: str):
        self.sensors[sensor_id] = {
            "zone_id": zone_id,
            "type": sensor_type,
            "value": None,
            "last_reading": None
        }
    
    def update_sensor_reading(self, sensor_id: str, value: Any):
        if sensor_id in self.sensors:
            self.sensors[sensor_id]["value"] = value
            self.sensors[sensor_id]["last_reading"] = datetime.now().isoformat()
            
            zone_id = self.sensors[sensor_id]["zone_id"]
            self._process_sensor_data(zone_id, sensor_id, value)
    
    def _process_sensor_data(self, zone_id: str, sensor_id: str, value: Any):
        sensor = self.sensors[sensor_id]
        zone = self.zones.get(zone_id)
        
        if not zone:
            return
        
        sensor_type = sensor["type"]
        
        if sensor_type == "temperature":
            zone["temperature"] = value
            
            if value > 26:
                zone["hvac"] = "cooling"
            elif value < 18:
                zone["hvac"] = "heating"
            else:
                zone["hvac"] = "auto"
        
        elif sensor_type == "motion":
            zone["occupancy"] = zone.get("occupancy", 0) + (1 if value else -1)
            
            if value:
                zone["lights"] = "on"
    
    def set_zone_schedule(self, zone_id: str, schedule: Schedule):
        schedule.zone_id = zone_id
        self.schedules.append(schedule)
    
    def get_zone_status(self, zone_id: str) -> Optional[Dict]:
        return self.zones.get(zone_id)


class ManufacturingControl:
    def __init__(self):
        self.production_lines: Dict[str, Dict] = {}
        self.jobs: Dict[str, Dict] = {}
        self.inventory: Dict[str, Dict] = {}
        
    def add_production_line(self, line_id: str, name: str, capacity: int):
        self.production_lines[line_id] = {
            "name": name,
            "capacity": capacity,
            "status": "idle",
            "current_job": None,
            "output_count": 0
        }
    
    def start_production(self, line_id: str, job_id: str) -> bool:
        if line_id not in self.production_lines:
            return False
        
        line = self.production_lines[line_id]
        
        if line["status"] != "idle":
            return False
        
        line["status"] = "running"
        line["current_job"] = job_id
        
        return True
    
    def stop_production(self, line_id: str) -> bool:
        if line_id not in self.production_lines:
            return False
        
        line = self.production_lines[line_id]
        
        if line["status"] == "running":
            line["status"] = "idle"
            line["current_job"] = None
        
        return True
    
    def create_job(self, job_id: str, product: str, quantity: int, materials: List[Dict]):
        self.jobs[job_id] = {
            "product": product,
            "quantity": quantity,
            "materials": materials,
            "status": "pending",
            "progress": 0,
            "created_at": datetime.now().isoformat()
        }
    
    def update_inventory(self, item_id: str, quantity: float, operation: str = "set"):
        if item_id not in self.inventory:
            self.inventory[item_id] = {"quantity": 0}
        
        if operation == "set":
            self.inventory[item_id]["quantity"] = quantity
        elif operation == "add":
            self.inventory[item_id]["quantity"] += quantity
        elif operation == "subtract":
            self.inventory[item_id]["quantity"] = max(0, self.inventory[item_id]["quantity"] - quantity)
    
    def get_inventory_status(self) -> List[Dict]:
        return [
            {"item_id": k, "quantity": v["quantity"]}
            for k, v in self.inventory.items()
        ]


class InfrastructureSystem:
    def __init__(self):
        self.facility = FacilityAutomation()
        self.security = SecurityAccessControl()
        self.power = PowerGridManager()
        self.transport = TransportControl()
        self.building = SmartBuildingManager()
        self.manufacturing = ManufacturingControl()
        
    def register_device(self, name: str, device_type: str, location: str, capabilities: List[str] = None):
        device_id = hashlib.md5(name.encode()).hexdigest()[:8]
        device = Device(
            id=device_id,
            name=name,
            device_type=device_type,
            status=DeviceStatus.ONLINE,
            location=location,
            capabilities=capabilities or []
        )
        return self.facility.register_device(device)
    
    async def control_device(self, device_name: str, command: str, params: Dict = None) -> Dict:
        for device_id, device in self.facility.devices.items():
            if device.name.lower() == device_name.lower():
                return await self.facility.control_device(device_id, command, params)
        
        return {"success": False, "error": "Device not found"}
    
    def check_security_access(self, user_id: str, resource: str) -> bool:
        return self.security.check_access(user_id, resource)
    
    def get_power_status(self) -> Dict:
        return self.power.optimize_power_distribution()
    
    def add_schedule(self, name: str, action: Dict, start_time: datetime = None, 
                     recurrence: str = None) -> str:
        schedule = Schedule(
            id=hashlib.md5(f"{name}{datetime.now()}".encode()).hexdigest()[:8],
            name=name,
            schedule_type="automation",
            start_time=start_time,
            recurrence=recurrence,
            action=action
        )
        self.facility.schedules.append(schedule)
        return schedule.id


_infrastructure_system: Optional[InfrastructureSystem] = None

def get_infrastructure_system() -> InfrastructureSystem:
    global _infrastructure_system
    if _infrastructure_system is None:
        _infrastructure_system = InfrastructureSystem()
    return _infrastructure_system
