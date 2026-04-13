"""
ORION-R1 System Awareness Module
Real-time monitoring: CPU, RAM, disk, network, processes, screen, apps
"""
import psutil
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import subprocess
import win32gui
import win32process

DATA_DIR = Path.home() / ".r1" / "awareness"
DATA_DIR.mkdir(parents=True, exist_ok=True)

class SystemAwareness:
    def __init__(self):
        self.history_file = DATA_DIR / "system_history.json"
        self.history = self._load_history()
        self.alerts = []

    def _load_history(self) -> List:
        if self.history_file.exists():
            try:
                return json.loads(self.history_file.read_text())
            except:
                return []
        return []

    def _save_snapshot(self, snapshot: Dict):
        self.history.append(snapshot)
        if len(self.history) > 1000:
            self.history = self.history[-1000:]
        self.history_file.write_text(json.dumps(self.history, indent=2))

    def get_cpu_info(self) -> Dict:
        return {
            "percent": psutil.cpu_percent(interval=0.1),
            "cores": psutil.cpu_count(logical=False),
            "logical_cores": psutil.cpu_count(logical=True),
            "freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None
        }

    def get_memory_info(self) -> Dict:
        mem = psutil.virtual_memory()
        return {
            "total_gb": round(mem.total / (1024**3), 2),
            "available_gb": round(mem.available / (1024**3), 2),
            "used_gb": round(mem.used / (1024**3), 2),
            "percent": mem.percent
        }

    def get_disk_info(self) -> List[Dict]:
        partitions = []
        for partition in psutil.disk_partitions(['C:\\']):
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                partitions.append({
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "total_gb": round(usage.total / (1024**3), 2),
                    "used_gb": round(usage.used / (1024**3), 2),
                    "free_gb": round(usage.free / (1024**3), 2),
                    "percent": usage.percent
                })
            except:
                pass
        return partitions

    def get_network_info(self) -> Dict:
        net_io = psutil.net_io_counters()
        return {
            "bytes_sent": net_io.bytes_sent,
            "bytes_recv": net_io.bytes_recv,
            "packets_sent": net_io.packets_sent,
            "packets_recv": net_io.packets_recv,
            "sent_mb": round(net_io.bytes_sent / (1024**2), 2),
            "recv_mb": round(net_io.bytes_recv / (1024**2), 2)
        }

    def get_processes(self, limit: int = 20) -> List[Dict]:
        procs = []
        for proc in list(psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']))[:limit]:
            try:
                procs.append(proc.info)
            except:
                pass
        return sorted(procs, key=lambda x: x.get('memory_percent', 0), reverse=True)

    def get_active_window(self) -> Optional[Dict]:
        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                title = win32gui.GetWindowText(hwnd)
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                process = psutil.Process(pid)
                return {
                    "title": title,
                    "process": process.name(),
                    "pid": pid
                }
        except:
            pass
        return None

    def get_battery_info(self) -> Optional[Dict]:
        battery = psutil.sensors_battery()
        if battery:
            return {
                "percent": battery.percent,
                "plugged_in": battery.power_plugged,
                "time_left": battery.secsleft if battery.secsleft != psutil.POWER_TIME_UNLIMITED else None
            }
        return None

    def get_full_status(self) -> Dict:
        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "cpu": self.get_cpu_info(),
            "memory": self.get_memory_info(),
            "disk": self.get_disk_info(),
            "network": self.get_network_info(),
            "processes": self.get_processes(10),
            "active_window": self.get_active_window(),
            "battery": self.get_battery_info()
        }
        self._save_snapshot(snapshot)
        return snapshot

    def check_alerts(self) -> List[Dict]:
        """Check for conditions that need user attention"""
        alerts = []

        mem = self.get_memory_info()
        if mem["percent"] > 90:
            alerts.append({"type": "warning", "message": f"Memory usage critical: {mem['percent']}%"})

        cpu = self.get_cpu_info()
        if cpu["percent"] > 90:
            alerts.append({"type": "warning", "message": f"CPU usage critical: {cpu['percent']}%"})

        disk = self.get_disk_info()
        for d in disk:
            if d["percent"] > 90:
                alerts.append({"type": "warning", "message": f"Disk {d['device']} nearly full: {d['percent']}%"})

        battery = self.get_battery_info()
        if battery and battery["percent"] < 20 and not battery["plugged_in"]:
            alerts.append({"type": "warning", "message": f"Battery low: {battery['percent']}%"})

        return alerts

    async def monitor_loop(self, interval: int = 10, callback=None):
        """Continuous monitoring with optional callback for alerts"""
        while True:
            status = self.get_full_status()
            alerts = self.check_alerts()

            if alerts and callback:
                for alert in alerts:
                    if alert not in self.alerts[-10:]:
                        self.alerts.append(alert)
                        await callback(alert)

            await asyncio.sleep(interval)


# Singleton instance
_awareness = None

def get_system_awareness() -> SystemAwareness:
    global _awareness
    if _awareness is None:
        _awareness = SystemAwareness()
    return _awareness
