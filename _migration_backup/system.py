"""
R1 - System Access
Shell commands, file operations, system info
"""
import os
import asyncio
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class CommandResult:
    success: bool
    output: str = ""
    error: Optional[str] = None
    return_code: int = 0


class Shell:
    """Execute shell commands"""
    
    @staticmethod
    async def execute(command: str, timeout: int = 30) -> CommandResult:
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                return CommandResult(
                    success=proc.returncode == 0,
                    output=stdout.decode(),
                    error=stderr.decode() if stderr else None,
                    return_code=proc.returncode
                )
            except asyncio.TimeoutError:
                proc.kill()
                return CommandResult(success=False, error="Command timed out", return_code=-1)
        except Exception as e:
            return CommandResult(success=False, error=str(e))
    
    @staticmethod
    def execute_sync(command: str, timeout: int = 30) -> CommandResult:
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                timeout=timeout,
                text=True
            )
            return CommandResult(
                success=result.returncode == 0,
                output=result.stdout,
                error=result.stderr if result.stderr else None,
                return_code=result.returncode
            )
        except Exception as e:
            return CommandResult(success=False, error=str(e))


class FileSystem:
    """File operations"""
    
    @staticmethod
    def read(path: str) -> CommandResult:
        try:
            file_path = Path(path)
            if not file_path.exists():
                return CommandResult(success=False, error="File not found")
            content = file_path.read_text(encoding="utf-8")
            return CommandResult(success=True, output=content)
        except Exception as e:
            return CommandResult(success=False, error=str(e))
    
    @staticmethod
    def write(path: str, content: str) -> CommandResult:
        try:
            file_path = Path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return CommandResult(success=True, output=f"Written: {path}")
        except Exception as e:
            return CommandResult(success=False, error=str(e))
    
    @staticmethod
    def append(path: str, content: str) -> CommandResult:
        try:
            file_path = Path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.append_text(content + "\n", encoding="utf-8")
            return CommandResult(success=True, output=f"Appended to: {path}")
        except Exception as e:
            return CommandResult(success=False, error=str(e))
    
    @staticmethod
    def delete(path: str) -> CommandResult:
        try:
            file_path = Path(path)
            if file_path.is_file():
                file_path.unlink()
            elif file_path.is_dir():
                shutil.rmtree(file_path)
            return CommandResult(success=True, output=f"Deleted: {path}")
        except Exception as e:
            return CommandResult(success=False, error=str(e))
    
    @staticmethod
    def list(path: str = ".") -> CommandResult:
        try:
            dir_path = Path(path)
            if not dir_path.exists():
                return CommandResult(success=False, error="Directory not found")
            items = []
            for item in dir_path.iterdir():
                items.append(f"{'d' if item.is_dir() else 'f'} {item.name}")
            return CommandResult(success=True, output="\n".join(items))
        except Exception as e:
            return CommandResult(success=False, error=str(e))
    
    @staticmethod
    def create_dir(path: str) -> CommandResult:
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            return CommandResult(success=True, output=f"Created: {path}")
        except Exception as e:
            return CommandResult(success=False, error=str(e))
    
    @staticmethod
    def copy(src: str, dst: str) -> CommandResult:
        try:
            shutil.copy2(src, dst)
            return CommandResult(success=True, output=f"Copied {src} to {dst}")
        except Exception as e:
            return CommandResult(success=False, error=str(e))
    
    @staticmethod
    def move(src: str, dst: str) -> CommandResult:
        try:
            shutil.move(src, dst)
            return CommandResult(success=True, output=f"Moved {src} to {dst}")
        except Exception as e:
            return CommandResult(success=False, error=str(e))


class SystemInfo:
    """Get system information"""
    
    @staticmethod
    def info() -> Dict[str, Any]:
        import platform
        import psutil
        
        return {
            "platform": platform.system(),
            "platform_version": platform.version(),
            "platform_release": platform.release(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "hostname": platform.node(),
            "cpu_count": psutil.cpu_count(),
            "cpu_percent": psutil.cpu_percent(),
            "memory_total": psutil.virtual_memory().total,
            "memory_available": psutil.virtual_memory().available,
            "memory_percent": psutil.virtual_memory().percent,
            "disk_total": psutil.disk_usage('/').total,
            "disk_used": psutil.disk_usage('/').used,
            "disk_percent": psutil.disk_usage('/').percent,
        }
    
    @staticmethod
    def processes() -> List[Dict[str, Any]]:
        import psutil
        return [
            {"pid": p.pid, "name": p.name(), "cpu": p.cpu_percent(), "memory": p.memory_percent()}
            for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent'])[:10]
        ]
    
    @staticmethod
    def network() -> Dict[str, Any]:
        import psutil
        net = psutil.net_io_counters()
        return {
            "bytes_sent": net.bytes_sent,
            "bytes_recv": net.bytes_recv,
            "packets_sent": net.packets_sent,
            "packets_recv": net.packets_recv,
        }
    
    @staticmethod
    def battery() -> Optional[Dict[str, Any]]:
        import psutil
        battery = psutil.sensors_battery()
        if battery:
            return {
                "percent": battery.percent,
                "charging": battery.is_plugged_in,
                "time_left": battery.secsleft
            }
        return None
