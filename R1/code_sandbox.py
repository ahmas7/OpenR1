"""
ORION-R1 Code Sandbox
Safe Python code execution with timeouts, resource limits, and audit logging
"""
import asyncio
import io
import sys
import traceback
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from contextlib import redirect_stdout, redirect_stderr
import threading

DATA_DIR = Path.home() / ".r1" / "sandbox"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Dangerous operations to block
DANGEROUS_PATTERNS = [
    r'^\s*import\s+os\b',
    r'^\s*import\s+subprocess\b',
    r'^\s*import\s+shutil\b',
    r'^\s*from\s+os\b',
    r'^\s*from\s+subprocess\b',
    r'^\s*from\s+shutil\b',
    r'__import__\s*\(\s*["\']os["\']',
    r'__import__\s*\(\s*["\']subprocess["\']',
    r'__import__\s*\(\s*["\']shutil["\']',
    r'os\.system\s*\(',
    r'os\.popen\s*\(',
    r'subprocess\.',
    r'shutil\.rmtree',
    r'eval\s*\(',
    r'exec\s*\(',
    r'compile\s*\(',
    r'open\s*\([^)]*["\'][wra]',  # Write mode file access
    r'input\s*\(',
]

class SandboxResult:
    def __init__(self, success: bool, output: str = "", error: str = "",
                 result: Any = None, execution_time: float = 0):
        self.success = success
        self.output = output
        self.error = error
        self.result = result
        self.execution_time = execution_time

    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "result": self.result,
            "execution_time": round(self.execution_time, 3)
        }

class CodeSandbox:
    def __init__(self, timeout: float = 5.0, max_output_lines: int = 100):
        self.timeout = timeout
        self.max_output_lines = max_output_lines
        self.execution_log = DATA_DIR / "executions.json"
        self._load_log()

    def _load_log(self):
        if self.execution_log.exists():
            try:
                self.log = json.loads(self.execution_log.read_text())
            except:
                self.log = []
        else:
            self.log = []

    def _save_log(self):
        if len(self.log) > 500:
            self.log = self.log[-500:]
        self.execution_log.write_text(json.dumps(self.log, indent=2, default=str))

    def _check_safety(self, code: str) -> List[str]:
        """Check code for dangerous patterns"""
        violations = []
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE | re.MULTILINE):
                violations.append(f"Dangerous pattern detected: {pattern}")
        return violations

    def _sanitize_code(self, code: str) -> str:
        """Remove potentially dangerous imports"""
        lines = code.split('\n')
        safe_lines = []
        blocked_imports = ['os', 'subprocess', 'shutil', 'sys', 'ctypes', 'pickle']

        for line in lines:
            is_blocked = False
            for blocked in blocked_imports:
                if f'import {blocked}' in line or f'from {blocked}' in line:
                    is_blocked = True
                    break
            if not is_blocked:
                safe_lines.append(line)

        return '\n'.join(safe_lines)

    def execute(self, code: str, variables: Optional[Dict] = None) -> SandboxResult:
        """Execute Python code safely"""
        start_time = datetime.now()

        # Safety check
        violations = self._check_safety(code)
        if violations:
            return SandboxResult(
                success=False,
                error="Safety violation: " + "; ".join(violations)
            )

        # Sanitize
        safe_code = self._sanitize_code(code)

        # Setup execution environment
        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()

        # Safe globals - only allow safe builtins
        safe_globals = {
            '__builtins__': {
                'abs': abs, 'all': all, 'any': any, 'bin': bin, 'bool': bool,
                'chr': chr, 'complex': complex, 'dict': dict, 'enumerate': enumerate,
                'float': float, 'format': format, 'hex': hex, 'int': int,
                'len': len, 'list': list, 'map': map, 'max': max, 'min': min,
                'oct': oct, 'ord': ord, 'pow': pow, 'print': print, 'range': range,
                'reversed': reversed, 'round': round, 'set': set, 'slice': slice,
                'sorted': sorted, 'str': str, 'sum': sum, 'tuple': tuple,
                'type': type, 'zip': zip, 'True': True, 'False': False, 'None': None,
                'iter': iter, 'next': next, 'filter': filter,
            },
            'json': json,
            'datetime': datetime,
        }

        # Add user variables
        if variables:
            safe_globals.update(variables)

        local_vars = {}

        try:
            # Compile and execute with timeout
            compiled = compile(safe_code, '<sandbox>', 'exec')

            result_container = {'result': None, 'error': None}

            def run_code():
                try:
                    with redirect_stdout(stdout_buffer):
                        with redirect_stderr(stderr_buffer):
                            exec(compiled, safe_globals, local_vars)
                            result_container['result'] = local_vars.get('result')
                except Exception as e:
                    result_container['error'] = str(e)
                    traceback.print_exc(file=stderr_buffer)

            thread = threading.Thread(target=run_code)
            thread.start()
            thread.join(timeout=self.timeout)

            if thread.is_alive():
                return SandboxResult(
                    success=False,
                    error=f"Execution timeout (>{self.timeout}s)"
                )

            if result_container['error']:
                return SandboxResult(
                    success=False,
                    output=stdout_buffer.getvalue()[:10000],
                    error=result_container['error']
                )

            # Get output
            output = stdout_buffer.getvalue()
            lines = output.split('\n')
            if len(lines) > self.max_output_lines:
                output = '\n'.join(lines[:self.max_output_lines]) + '\n... (truncated)'

            exec_time = (datetime.now() - start_time).total_seconds()

            # Log execution
            self.log.append({
                "timestamp": datetime.now().isoformat(),
                "code_preview": code[:100],
                "success": True,
                "execution_time": exec_time
            })
            self._save_log()

            return SandboxResult(
                success=True,
                output=output,
                result=result_container['result'],
                execution_time=exec_time
            )

        except Exception as e:
            return SandboxResult(
                success=False,
                output=stdout_buffer.getvalue()[:10000],
                error=str(e) + "\n" + stderr_buffer.getvalue()[:5000]
            )

    async def execute_async(self, code: str, variables: Optional[Dict] = None) -> SandboxResult:
        """Async wrapper for execute"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.execute, code, variables
        )

    def get_execution_history(self, limit: int = 20) -> List[Dict]:
        return self.log[-limit:]

    def clear_history(self):
        self.log = []
        self._save_log()


# Singleton
_sandbox = None

def get_code_sandbox() -> CodeSandbox:
    global _sandbox
    if _sandbox is None:
        _sandbox = CodeSandbox()
    return _sandbox
