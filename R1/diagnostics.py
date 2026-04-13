"""
R1 - Diagnostics, Repair & Optimization Systems
Health monitoring, failure detection, performance benchmarking, self-repair
"""
import asyncio
import logging
import json
import hashlib
import psutil
import platform
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Callable
from datetime import datetime, timedelta
from enum import Enum
import subprocess
from collections import defaultdict

logger = logging.getLogger("R1:diagnostics")


class SystemStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class DiagnosticSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class DiagnosticResult:
    id: str
    timestamp: datetime
    test_name: str
    severity: DiagnosticSeverity
    status: SystemStatus
    message: str
    details: Dict = field(default_factory=dict)
    recommended_action: Optional[str] = None


@dataclass
class SystemHealth:
    overall_status: SystemStatus
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    network_stats: Dict = field(default_factory=dict)
    components: Dict[str, SystemStatus] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ComponentHealth:
    component_id: str
    component_name: str
    status: SystemStatus
    metrics: Dict[str, float] = field(default_factory=dict)
    last_check: datetime = field(default_factory=datetime.now)
    error_count: int = 0
    uptime_seconds: float = 0


class HealthMonitor:
    def __init__(self):
        self.component_health: Dict[str, ComponentHealth] = {}
        self.health_history: List[SystemHealth] = []
        
    async def get_system_health(self) -> SystemHealth:
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            net_io = psutil.net_io_counters()
            
            status = SystemStatus.HEALTHY
            
            if cpu_percent > 90 or memory.percent > 90 or disk.percent > 95:
                status = SystemStatus.CRITICAL
            elif cpu_percent > 70 or memory.percent > 80 or disk.percent > 85:
                status = SystemStatus.DEGRADED
            
            health = SystemHealth(
                overall_status=status,
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                disk_percent=disk.percent,
                network_stats={
                    "bytes_sent": net_io.bytes_sent,
                    "bytes_recv": net_io.bytes_recv,
                    "packets_sent": net_io.packets_sent,
                    "packets_recv": net_io.packets_recv
                },
                components=self._get_component_statuses()
            )
            
            self.health_history.append(health)
            
            if len(self.health_history) > 1000:
                self.health_history = self.health_history[-1000:]
            
            return health
            
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return SystemHealth(
                overall_status=SystemStatus.UNKNOWN,
                cpu_percent=0,
                memory_percent=0,
                disk_percent=0
            )
    
    def _get_component_statuses(self) -> Dict[str, SystemStatus]:
        statuses = {}
        
        try:
            statuses["cpu"] = SystemStatus.HEALTHY if psutil.cpu_percent(interval=0.1) < 80 else SystemStatus.DEGRADED
        except:
            statuses["cpu"] = SystemStatus.UNKNOWN
        
        try:
            mem = psutil.virtual_memory()
            statuses["memory"] = SystemStatus.HEALTHY if mem.percent < 80 else SystemStatus.DEGRADED
        except:
            statuses["memory"] = SystemStatus.UNKNOWN
        
        try:
            disk = psutil.disk_usage('/')
            statuses["disk"] = SystemStatus.HEALTHY if disk.percent < 85 else SystemStatus.DEGRADED
        except:
            statuses["disk"] = SystemStatus.UNKNOWN
        
        return statuses
    
    def register_component(self, component_id: str, component_name: str):
        self.component_health[component_id] = ComponentHealth(
            component_id=component_id,
            component_name=component_name,
            status=SystemStatus.HEALTHY
        )
    
    def update_component_status(
        self,
        component_id: str,
        status: SystemStatus,
        metrics: Optional[Dict[str, float]] = None,
    ):
        if component_id in self.component_health:
            comp = self.component_health[component_id]
            comp.status = status
            comp.last_check = datetime.now()
            
            if metrics:
                comp.metrics.update(metrics)
    
    def get_component_health(self, component_id: str) -> Optional[ComponentHealth]:
        return self.component_health.get(component_id)
    
    def get_all_component_health(self) -> List[Dict]:
        return [
            {
                "component_id": c.component_id,
                "component_name": c.component_name,
                "status": c.status.value,
                "metrics": c.metrics,
                "last_check": c.last_check.isoformat()
            }
            for c in self.component_health.values()
        ]


class FailureDetector:
    def __init__(self):
        self.failures: List[Dict] = []
        self.error_patterns: Dict[str, List[str]] = {}
        self.thresholds: Dict[str, float] = {
            "cpu_spike": 95.0,
            "memory_leak": 90.0,
            "disk_full": 95.0,
            "error_rate": 10.0
        }
        
    def detect_failures(self, health: SystemHealth) -> List[DiagnosticResult]:
        results = []
        
        if health.cpu_percent > self.thresholds["cpu_spike"]:
            results.append(DiagnosticResult(
                id=hashlib.md5(f"cpu{datetime.now()}".encode()).hexdigest()[:12],
                timestamp=datetime.now(),
                test_name="cpu_health",
                severity=DiagnosticSeverity.CRITICAL,
                status=SystemStatus.CRITICAL,
                message=f"CPU usage critically high: {health.cpu_percent}%",
                details={"cpu_percent": health.cpu_percent},
                recommended_action="Reduce CPU load or scale resources"
            ))
        
        if health.memory_percent > self.thresholds["memory_leak"]:
            results.append(DiagnosticResult(
                id=hashlib.md5(f"mem{datetime.now()}".encode()).hexdigest()[:12],
                timestamp=datetime.now(),
                test_name="memory_health",
                severity=DiagnosticSeverity.CRITICAL,
                status=SystemStatus.CRITICAL,
                message=f"Memory usage critically high: {health.memory_percent}%",
                details={"memory_percent": health.memory_percent},
                recommended_action="Free up memory or add more RAM"
            ))
        
        if health.disk_percent > self.thresholds["disk_full"]:
            results.append(DiagnosticResult(
                id=hashlib.md5(f"disk{datetime.now()}".encode()).hexdigest()[:12],
                timestamp=datetime.now(),
                test_name="disk_health",
                severity=DiagnosticSeverity.ERROR,
                status=SystemStatus.CRITICAL,
                message=f"Disk space critically low: {health.disk_percent}%",
                details={"disk_percent": health.disk_percent},
                recommended_action="Free up disk space"
            ))
        
        for result in results:
            self.failures.append({
                "id": result.id,
                "test_name": result.test_name,
                "severity": result.severity.value,
                "timestamp": result.timestamp.isoformat()
            })
        
        return results
    
    def analyze_logs(self, log_content: str) -> List[Dict]:
        issues = []
        
        error_patterns = [
            (r"ERROR", "error"),
            (r"EXCEPTION", "exception"),
            (r"FAILED", "failure"),
            (r"TIMEOUT", "timeout"),
            (r"OUT OF MEMORY", "memory"),
            (r"NULL POINTER", "null_pointer"),
        ]
        
        for pattern, issue_type in error_patterns:
            import re
            matches = re.finditer(pattern, log_content, re.IGNORECASE)
            
            for match in matches:
                line_start = log_content.rfind('\n', 0, match.start()) + 1
                line_end = log_content.find('\n', match.end())
                line_content = log_content[line_start:line_end] if line_end > 0 else log_content[line_start:]
                
                issues.append({
                    "type": issue_type,
                    "line": line_content[:100],
                    "position": match.start()
                })
        
        return issues
    
    def get_failure_summary(self) -> Dict:
        by_severity = {}
        
        for failure in self.failures:
            severity = failure.get("severity", "unknown")
            by_severity[severity] = by_severity.get(severity, 0) + 1
        
        return {
            "total_failures": len(self.failures),
            "by_severity": by_severity,
            "recent_failures": self.failures[-10:]
        }


class PerformanceBenchmark:
    def __init__(self):
        self.benchmarks: Dict[str, Dict] = {}
        self.results_history: Dict[str, List[Dict]] = defaultdict(list)
        
    async def run_benchmark(self, benchmark_type: str = "system") -> Dict:
        result = {
            "type": benchmark_type,
            "timestamp": datetime.now().isoformat(),
            "scores": {}
        }
        
        if benchmark_type == "system":
            result["scores"] = await self._benchmark_system()
        elif benchmark_type == "cpu":
            result["scores"] = await self._benchmark_cpu()
        elif benchmark_type == "memory":
            result["scores"] = await self._benchmark_memory()
        elif benchmark_type == "disk":
            result["scores"] = await self._benchmark_disk()
        
        self.results_history[benchmark_type].append(result)
        
        if len(self.results_history[benchmark_type]) > 100:
            self.results_history[benchmark_type] = self.results_history[benchmark_type][-100:]
        
        return result
    
    async def _benchmark_system(self) -> Dict:
        cpu_score = psutil.cpu_count() * psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        mem_score = mem.total / (1024 * 1024 * 1024)
        
        return {
            "cpu_score": cpu_score,
            "memory_gb": mem_score,
            "overall_score": (cpu_score + mem_score) / 2
        }
    
    async def _benchmark_cpu(self) -> Dict:
        import time
        
        start = time.time()
        
        total = 0
        for i in range(1000000):
            total += i
        
        elapsed = time.time() - start
        
        return {
            "operations": 1000000,
            "time_seconds": elapsed,
            "ops_per_second": 1000000 / elapsed if elapsed > 0 else 0
        }
    
    async def _benchmark_memory(self) -> Dict:
        import time
        
        start = time.time()
        
        data = []
        for i in range(10000):
            data.append({f"key_{j}": j for j in range(100)})
        
        elapsed = time.time() - start
        
        return {
            "objects_created": 10000,
            "time_seconds": elapsed,
            "memory_mb": len(str(data)) / (1024 * 1024)
        }
    
    async def _benchmark_disk(self) -> Dict:
        import tempfile
        import os
        
        test_file = tempfile.NamedTemporaryFile(delete=False)
        
        start = time.time()
        
        test_data = b"x" * (1024 * 1024)
        for _ in range(10):
            test_file.write(test_data)
        
        test_file.close()
        
        write_time = time.time() - start
        
        os.unlink(test_file.name)
        
        return {
            "bytes_written": 10 * 1024 * 1024,
            "time_seconds": write_time,
            "mb_per_second": (10 * 1024 * 1024) / (write_time * 1024 * 1024)
        }
    
    def compare_benchmarks(self, benchmark_type: str) -> Dict:
        if benchmark_type not in self.results_history:
            return {"error": "No benchmarks found"}
        
        results = self.results_history[benchmark_type]
        
        if len(results) < 2:
            return {"error": "Not enough data to compare"}
        
        latest = results[-1]
        previous = results[-2]
        
        comparison = {}
        
        for key in latest.get("scores", {}):
            if key in previous.get("scores", {}):
                diff = latest["scores"][key] - previous["scores"][key]
                percent_change = (diff / previous["scores"][key] * 100) if previous["scores"][key] != 0 else 0
                
                comparison[key] = {
                    "current": latest["scores"][key],
                    "previous": previous["scores"][key],
                    "change": diff,
                    "percent_change": percent_change
                }
        
        return comparison


class SelfRepairEngine:
    def __init__(self):
        self.repair_actions: Dict[str, Callable] = {}
        self.repair_history: List[Dict] = []
        self.auto_repair_enabled = True
        
    def register_repair_action(self, issue_type: str, repair_func: Callable):
        self.repair_actions[issue_type] = repair_func
    
    async def attempt_repair(self, issue_type: str, context: Dict = None) -> Dict:
        if not self.auto_repair_enabled:
            return {"success": False, "reason": "Auto-repair disabled"}
        
        if issue_type not in self.repair_actions:
            return {"success": False, "reason": f"No repair action for {issue_type}"}
        
        try:
            repair_func = self.repair_actions[issue_type]
            result = await repair_func(context or {})
            
            self.repair_history.append({
                "issue_type": issue_type,
                "timestamp": datetime.now().isoformat(),
                "success": result.get("success", False),
                "details": result
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Repair error for {issue_type}: {e}")
            return {"success": False, "error": str(e)}
    
    async def repair_high_memory(self, context: Dict) -> Dict:
        try:
            import gc
            gc.collect()
            
            return {
                "success": True,
                "action": "Garbage collection executed",
                "freed_memory_mb": "estimated 10-50 MB"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def repair_disk_space(self, context: Dict) -> Dict:
        try:
            import tempfile
            import os
            
            temp_dir = tempfile.gettempdir()
            files_removed = 0
            bytes_freed = 0
            
            for item in os.listdir(temp_dir):
                try:
                    path = os.path.join(temp_dir, item)
                    if os.path.isfile(path):
                        size = os.path.getsize(path)
                        os.remove(path)
                        files_removed += 1
                        bytes_freed += size
                except:
                    pass
            
            return {
                "success": True,
                "action": f"Cleaned {files_removed} temp files",
                "bytes_freed": bytes_freed
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_repair_history(self, limit: int = 50) -> List[Dict]:
        return self.repair_history[-limit:]


class MaintenanceScheduler:
    def __init__(self):
        self.scheduled_maintenance: List[Dict] = []
        
    def schedule_maintenance(self, name: str, scheduled_time: datetime, task: str, 
                           recurring: str = None) -> str:
        import uuid
        maintenance_id = str(uuid.uuid4())[:8]
        
        maintenance = {
            "id": maintenance_id,
            "name": name,
            "scheduled_time": scheduled_time.isoformat(),
            "task": task,
            "recurring": recurring,
            "status": "scheduled",
            "created_at": datetime.now().isoformat()
        }
        
        self.scheduled_maintenance.append(maintenance)
        
        return maintenance_id
    
    def get_upcoming_maintenance(self, hours: int = 24) -> List[Dict]:
        now = datetime.now()
        cutoff = now + timedelta(hours=hours)
        
        upcoming = []
        
        for m in self.scheduled_maintenance:
            if m["status"] != "scheduled":
                continue
            
            sched_time = datetime.fromisoformat(m["scheduled_time"])
            
            if now <= sched_time <= cutoff:
                upcoming.append(m)
        
        return sorted(upcoming, key=lambda x: x["scheduled_time"])
    
    def cancel_maintenance(self, maintenance_id: str) -> bool:
        for m in self.scheduled_maintenance:
            if m["id"] == maintenance_id:
                m["status"] = "cancelled"
                return True
        return False


class DiagnosticReporter:
    def __init__(self):
        self.reports: List[Dict] = []
        
    async def generate_report(self, include_components: bool = True) -> Dict:
        health_monitor = HealthMonitor()
        failure_detector = FailureDetector()
        
        system_health = await health_monitor.get_system_health()
        failures = failure_detector.detect_failures(system_health)
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "system_status": system_health.overall_status.value,
            "health_metrics": {
                "cpu_percent": system_health.cpu_percent,
                "memory_percent": system_health.memory_percent,
                "disk_percent": system_health.disk_percent
            },
            "failures": [
                {
                    "test": f.test_name,
                    "severity": f.severity.value,
                    "message": f.message,
                    "action": f.recommended_action
                }
                for f in failures
            ]
        }
        
        if include_components:
            report["components"] = health_monitor.get_all_component_health()
        
        self.reports.append(report)
        
        if len(self.reports) > 100:
            self.reports = self.reports[-100:]
        
        return report
    
    def get_report_history(self, limit: int = 10) -> List[Dict]:
        return self.reports[-limit:]


class DiagnosticsSystem:
    def __init__(self):
        self.health_monitor = HealthMonitor()
        self.failure_detector = FailureDetector()
        self.benchmark = PerformanceBenchmark()
        self.repair = SelfRepairEngine()
        self.maintenance = MaintenanceScheduler()
        self.reporter = DiagnosticReporter()
        
        self._register_default_repairs()
        
    def _register_default_repairs(self):
        self.repair.register_repair_action("high_memory", self.repair.repair_high_memory)
        self.repair.register_repair_action("disk_full", self.repair.repair_disk_space)
        
    async def run_diagnostics(self) -> Dict:
        health = await self.health_monitor.get_system_health()
        failures = self.failure_detector.detect_failures(health)
        
        return {
            "status": health.overall_status.value,
            "metrics": {
                "cpu": health.cpu_percent,
                "memory": health.memory_percent,
                "disk": health.disk_percent
            },
            "failures": len(failures),
            "details": [
                {"test": f.test_name, "message": f.message}
                for f in failures
            ]
        }
    
    async def run_benchmark(self, benchmark_type: str = "system") -> Dict:
        return await self.benchmark.run_benchmark(benchmark_type)
    
    async def attempt_auto_repair(self, issue_type: str) -> Dict:
        return await self.repair.attempt_repair(issue_type)
    
    async def generate_diagnostic_report(self) -> Dict:
        return await self.reporter.generate_report()


_diagnostics_system: Optional[DiagnosticsSystem] = None

def get_diagnostics_system() -> DiagnosticsSystem:
    global _diagnostics_system
    if _diagnostics_system is None:
        _diagnostics_system = DiagnosticsSystem()
    return _diagnostics_system
