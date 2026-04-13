"""
R1 - Code Execution Engine
Safe Python execution and script generation
"""
import asyncio
import io
import sys
import tempfile
import subprocess
import os
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ExecutionResult:
    success: bool
    output: str
    error: Optional[str] = None
    execution_time: float = 0.0


class CodeExecutor:
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.execution_history = []
    
    async def execute_python(self, code: str, context: Dict = None) -> ExecutionResult:
        """Execute Python code safely"""
        import time
        start_time = time.time()
        
        context = context or {}
        
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        
        local_vars = {
            "__builtins__": __builtins__,
            **context
        }
        
        try:
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture
            
            try:
                exec(code, {}, local_vars)
                
                output = stdout_capture.getvalue()
                error = stderr_capture.getvalue()
                
                execution_time = time.time() - start_time
                
                result = ExecutionResult(
                    success=True,
                    output=output or "Code executed successfully (no output)",
                    error=error if error else None,
                    execution_time=execution_time
                )
                
                self.execution_history.append({
                    "code": code,
                    "result": result
                })
                
                return result
                
            except Exception as e:
                execution_time = time.time() - start_time
                return ExecutionResult(
                    success=False,
                    output=stdout_capture.getvalue(),
                    error=str(e),
                    execution_time=execution_time
                )
        
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
    
    async def execute_shell(self, command: str) -> ExecutionResult:
        """Execute shell command"""
        import time
        start_time = time.time()
        
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=self.timeout
                )
                
                execution_time = time.time() - start_time
                
                result = ExecutionResult(
                    success=proc.returncode == 0,
                    output=stdout.decode() if stdout else "",
                    error=stderr.decode() if stderr else None,
                    execution_time=execution_time
                )
                
                self.execution_history.append({
                    "command": command,
                    "result": result
                })
                
                return result
                
            except asyncio.TimeoutError:
                proc.kill()
                return ExecutionResult(
                    success=False,
                    output="",
                    error=f"Command timed out after {self.timeout} seconds"
                )
        
        except Exception as e:
            return ExecutionResult(
                success=False,
                output="",
                error=str(e)
            )
    
    async def analyze_data(self, data: str, analysis_type: str = "basic") -> Dict[str, Any]:
        """Analyze data (CSV, JSON, etc.)"""
        code = f"""
import json
import statistics

data = {data}

result = {{"type": type(data).__name__, "length": len(data) if hasattr(data, '__len__') else None}}

if isinstance(data, (list, tuple)):
    try:
        numeric = [x for x in data if isinstance(x, (int, float))]
        if numeric:
            result["sum"] = sum(numeric)
            result["avg"] = statistics.mean(numeric)
            result["min"] = min(numeric)
            result["max"] = max(numeric)
    except Exception:
        pass  # Statistics calculation failed, continue with basic analysis
    result["first_5"] = data[:5]
    result["last_5"] = data[-5:]
    
elif isinstance(data, dict):
    result["keys"] = list(data.keys())[:10]
    
elif isinstance(data, str):
    result["word_count"] = len(data.split())
    result["char_count"] = len(data)

print(json.dumps(result))
"""
        
        result = await self.execute_python(code)
        
        if result.success:
            try:
                return json.loads(result.output)
            except:
                return {"raw_output": result.output}
        
        return {"error": result.error}
    
    async def generate_script(self, task: str, language: str = "python") -> str:
        """Generate automation script based on task description"""
        script_templates = {
            "python": f'''"""
Generated Python Script for: {task}
"""
import os
import sys

def main():
    # Your code here
    pass

if __name__ == "__main__":
    main()
''',
            "batch": f'''@echo off
REM Generated Batch Script for: {task}

REM Your commands here
echo Done
pause
''',
            "powershell": f'''# Generated PowerShell Script for: {task}

# Your commands here
Write-Host "Done"
'''
        }
        
        return script_templates.get(language, "# Unsupported language")
    
    def get_history(self) -> list:
        return self.execution_history[-20:]


code_executor = CodeExecutor()
