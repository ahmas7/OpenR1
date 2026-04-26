"""
R1 v1 - Agent Loop
The core control cycle: observe -> think -> act -> verify -> remember
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

from ..model import Message, ModelResponse, get_model_manager
from ..tools import get_tool_registry, ToolResult
from ..memory import get_memory_store, MemoryRetrieval
from .state import AgentState, AgentStatus
from .planner import Planner
from ..config.settings import settings
from ..tools.base import ToolResult

logger = logging.getLogger("R1")


class ExecutionReport:
    def __init__(self):
        self.iteration_count: int = 0
        self.plan_steps: List[Dict] = []
        self.tool_calls: List[Dict] = []
        self.final_status: str = ""
        self.final_summary: str = ""
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "iteration_count": self.iteration_count,
            "plan_steps": self.plan_steps,
            "tool_calls": self.tool_calls,
            "final_status": self.final_status,
            "final_summary": self.final_summary,
            "duration_seconds": (self.end_time - self.start_time).total_seconds() if self.end_time else None
        }


class AgentLoop:
    def __init__(self, state: AgentState):
        self.state = state
        self.model = get_model_manager()
        self.tools = get_tool_registry()
        self.memory = get_memory_store()
        self.retrieval = MemoryRetrieval(self.memory)
        self.planner = Planner()
        self._running = False
        self.report = ExecutionReport()
        self._skills_runtime = None
        self._self_improver = None

    def _get_self_improver(self):
        if self._self_improver is None:
            try:
                from ..self_improver import get_self_improver
                self._self_improver = get_self_improver()
            except Exception as e:
                logger.warning(f"Self-improver not available: {e}")
        return self._self_improver
    
    def _get_skills_runtime(self):
        """Lazy load skills runtime"""
        if self._skills_runtime is None:
            try:
                from ..skills import get_skills_runtime
                self._skills_runtime = get_skills_runtime()
            except Exception as e:
                logger.warning(f"Skills runtime not available: {e}")
        return self._skills_runtime

    async def start(self, goal: str):
        self._running = True
        self.state.update(
            goal=goal,
            status=AgentStatus.THINKING,
            plan=self.planner.create_plan(goal),
            iteration=0
        )
        
        logger.info(f"Agent started with goal: {goal}")
        
        await self._run_loop()
        
        self.report.end_time = datetime.now()

    async def stop(self):
        self._running = False
        self.state.update(status=AgentStatus.STOPPED)
        logger.info(f"Agent stopped for session: {self.state.session_id}")

    async def _run_loop(self):
        # Initialize plan with at least one step
        self.state.plan = self.planner._simple_plan(self.state.goal)
        self.report.plan_steps = self.state.plan.get("steps", [])

        # Start of goal learning
        improver = self._get_self_improver()
        
        while self._running and self.state.iteration < settings.max_iterations:
            self.state.iteration += 1
            self.report.iteration_count = self.state.iteration
            
            logger.info(f"Iteration {self.state.iteration}/{settings.max_iterations}")
            
            try:
                await self._step()
            except Exception as e:
                logger.error(f"Step error: {e}")
                self.state.update(
                    status=AgentStatus.ERROR,
                    error=str(e),
                    last_action="error",
                    last_result=str(e)
                )
                self.report.final_status = "failed"
                self.report.final_summary = f"Error: {str(e)}"
                break
            
            # Check for terminal signals
            if self.state.status in (AgentStatus.DONE, AgentStatus.ERROR):
                logger.info(f"Agent stopped with status: {self.state.status}")

                # Learn from the outcome
                if improver:
                    outcome = "success" if self.state.status == AgentStatus.DONE else "failure"
                    improver.learn_from_interaction(
                        user_input=self.state.goal,
                        ai_response=str(self.state.last_result),
                        outcome=outcome,
                        tools_used=[c["tool"] for c in self.report.tool_calls]
                    )
                    # Update trust level based on success
                    improver.update_trust("agent_loop", self.state.status == AgentStatus.DONE)

                break
            
            # Check if max iterations reached
            if self.state.iteration >= settings.max_iterations:
                logger.warning(f"Max iterations reached: {settings.max_iterations}")
                self.state.update(
                    status=AgentStatus.ERROR,
                    error="Max iterations reached"
                )
                self.report.final_status = "failed"
                self.report.final_summary = "Max iterations reached"
                break

    async def _step(self):
        await self._think()
        
        # Check for terminal signals after thinking
        if self._check_terminal_signal():
            return
        
        if self.state.status == AgentStatus.DONE:
            return
        
        # Execute tool if needed
        if self.state.last_action and self.state.last_action != "respond":
            await self._act()
            
            # Verify after action
            verified = await self._verify()
            
            if verified:
                logger.info("Verification passed - task complete")
                self.state.update(status=AgentStatus.DONE)
                self.report.final_status = "completed"
                self.report.final_summary = str(self.state.last_result)[:200]
                return
            
            # Check for repeated tool calls (prevent infinite loops)
            if self._detect_infinite_loop():
                logger.warning("Infinite loop detected - stopping")
                self.state.update(
                    status=AgentStatus.ERROR,
                    error="Infinite loop detected"
                )
                self.report.final_status = "failed"
                self.report.final_summary = "Infinite loop - same tool called repeatedly"
                return

    def _check_terminal_signal(self) -> bool:
        """Check if model emitted a terminal signal"""
        response = self.state.last_result
        if not isinstance(response, str):
            return False
        
        response_upper = response.upper().strip()
        
        # Check for DONE signal
        if response_upper.startswith("DONE:"):
            summary = response[5:].strip()
            self.state.update(status=AgentStatus.DONE)
            self.report.final_status = "completed"
            self.report.final_summary = summary or "Task completed"
            return True
        
        # Check for FAIL signal
        if response_upper.startswith("FAIL:"):
            reason = response[5:].strip()
            self.state.update(
                status=AgentStatus.ERROR,
                error=reason
            )
            self.report.final_status = "failed"
            self.report.final_summary = f"Failed: {reason}"
            return True
        
        # Check for BLOCKED signal
        if response_upper.startswith("BLOCKED:"):
            reason = response[8:].strip()
            self.planner.mark_blocked(self.state.plan, reason)
            self.state.update(status=AgentStatus.DONE)
            self.report.final_status = "blocked"
            self.report.final_summary = f"Blocked: {reason}"
            return True
        
        return False

    def _detect_infinite_loop(self) -> bool:
        """Detect if same tool is being called repeatedly"""
        tool_history = self.memory.get_tool_history(self.state.session_id, limit=10)
        
        if len(tool_history) < 3:
            return False
        
        # Check last 5 tool calls
        recent_calls = tool_history[-5:]
        tool_names = [call["tool_name"] for call in recent_calls]
        
        # If same tool called 3+ times in a row
        if len(set(tool_names)) == 1 and len(tool_names) >= 3:
            return True
        
        return False

    async def _think(self):
        self.state.update(status=AgentStatus.THINKING)

        tool_schemas = self.tools.get_schemas()

        # Get skills and add them as available tools
        skills_info = ""
        skills_runtime = self._get_skills_runtime()
        if skills_runtime:
            try:
                await skills_runtime.initialize()
                skill_tools = skills_runtime.get_skill_tools()
                if skill_tools:
                    skills_info = "\n\nAvailable skills:"
                    for skill in skill_tools:
                        skills_info += f"\n- {skill['name']}: {skill['description']}"
                        if skill.get('triggers'):
                            skills_info += f" (triggers: {', '.join(skill['triggers'])})"
            except Exception as e:
                logger.warning(f"Could not load skills: {e}")

        # Get current step info
        current_step = self.planner.get_next_step(self.state.plan)
        step_info = f"Current step: {current_step.get('title', 'Unknown')}" if current_step else "No steps"

        # Get recent tool results
        recent_results = self._get_recent_tool_results()

        # Get semantic memory context
        semantic_context = ""
        try:
            semantic_context = await self.retrieval.semantic_search(self.state.goal, top_k=3)
        except Exception as e:
            logger.debug(f"Semantic search failed: {e}")

        system_prompt = f"""You are R1, an autonomous agent that can use tools and skills.

Current goal: {self.state.goal}
{step_info}

{semantic_context}

Available tools:
{self._format_tools(tool_schemas)}{skills_info}

Recent tool results:
{recent_results}

Instructions:
1. If the goal is COMPLETE, respond with: DONE: <summary>
2. If the goal FAILED, respond with: FAIL: <reason>
3. If BLOCKED and cannot proceed, respond with: BLOCKED: <reason>
4. To use a tool, respond with:
TOOL: <tool_name>
<arg_key>: <arg_value>

Example:
TOOL: shell
command: dir

5. To use a skill, respond with:
SKILL: <skill_name>
context: <context_json>

Example:
SKILL: file_organizer
context: {{"directory": "/path/to/folder", "pattern": "*.txt"}}

Now respond to achieve this goal: {self.state.goal}"""

        messages = [
            Message(role="system", content=system_prompt)
        ]

        for msg in self.state.messages[-5:]:
            messages.append(Message(role=msg["role"], content=msg["content"]))

        try:
            response = await self.model.chat(messages)
            self.state.last_result = response.content

            # Check for terminal signal
            if self._check_terminal_signal():
                return

            self._parse_action(response.content)

        except Exception as e:
            logger.error(f"Think error: {e}")
            # Don't set last_action to "error" — that causes the loop to
            # try executing a non-existent tool called "error".
            # Instead, just mark the step as blocked and move on.
            self.state.update(status=AgentStatus.DONE, last_action="respond",
                              last_result=f"I encountered an error: {e}")

    def _get_recent_tool_results(self) -> str:
        """Get recent tool results for context"""
        tool_history = self.memory.get_tool_history(self.state.session_id, limit=5)
        if not tool_history:
            return "No recent tool calls"
        
        lines = []
        for call in reversed(tool_history):
            status = "OK" if call["success"] else "FAILED"
            result = call["result"][:100] if call["result"] else ""
            lines.append(f"- {call['tool_name']}: {status} - {result}")
        
        return "\n".join(lines)

    def _format_plan(self) -> str:
        plan = self.state.plan
        if not plan.get("steps"):
            return "No plan yet"
        
        lines = []
        for step in plan["steps"]:
            status = step.get("status", "pending")
            title = step.get("title", "Unknown")
            lines.append(f"- [{status}] {title}")
        return "\n".join(lines)

    def _format_tools(self, schemas: list) -> str:
        lines = []
        for schema in schemas:
            func = schema.get("function", {})
            lines.append(f"- {func.get('name')}: {func.get('description')}")
        return "\n".join(lines)

    def _parse_action(self, response: str):
        """Parse model response for tool or skill calls"""
        tool_names = [t.name for t in self.tools.list_tools()]
        response_lower = response.lower()
        
        # Check for skill invocation first
        skill_pattern = "skill:"
        if skill_pattern in response_lower:
            idx = response_lower.index(skill_pattern)
            skill_section = response[idx:]
            
            lines = skill_section.split("\n")
            if len(lines) > 0:
                first_line = lines[0]
                # Case-insensitive replace
                import re
                skill_name = re.sub(r'^skill:\s*', '', first_line, flags=re.IGNORECASE).strip()
                
                context = {}
                if len(lines) > 1:
                    context_text = "\n".join(lines[1:])
                    # Try to parse as JSON
                    try:
                        import json
                        if "context:" in context_text.lower():
                            context_str = context_text.lower().replace("context:", "").strip()
                            try:
                                context = json.loads(context_str)
                            except:
                                # Fall back to simple key-value parsing
                                for line in context_str.split("\n"):
                                    line = line.strip()
                                    if ":" in line:
                                        key, val = line.split(":", 1)
                                        context[key.strip()] = val.strip()
                        else:
                            context = json.loads(context_text)
                    except:
                        # Fall back to simple parsing
                        context = self._parse_simple_args(skill_name, context_text)
                
                self._advance_step(f"skill:{skill_name}")
                
                self.state.update(
                    status=AgentStatus.ACTING,
                    last_action=f"skill:{skill_name}",
                    last_result={"skill_name": skill_name, "context": context, "_is_skill": True}
                )
                return
        
        # Check for tool invocation
        tool_pattern = "tool:"
        if tool_pattern in response_lower:
            idx = response_lower.index(tool_pattern)
            tool_section = response[idx:]
            
            lines = tool_section.split("\n")
            if len(lines) > 0:
                first_line = lines[0].replace("tool:", "").strip()
                
                for tool_name in tool_names:
                    if tool_name in first_line.lower():
                        args = {}
                        if len(lines) > 1:
                            args_text = "\n".join(lines[1:])
                            args = self._parse_simple_args(tool_name, args_text)
                        
                        self._advance_step(tool_name)
                        
                        self.state.update(
                            status=AgentStatus.ACTING,
                            last_action=tool_name,
                            last_result=args
                        )
                        return
        
        # If no tool call, treat as response
        if len(response) > 500:
            response = response[:500] + "..."
        self.state.update(
            status=AgentStatus.DONE,
            last_action="respond",
            last_result=response
        )
        self.report.final_status = "completed"
        self.report.final_summary = response[:200]
    
    def _advance_step(self, tool_name: str):
        """Mark current step as in_progress"""
        next_step = self.planner.get_next_step(self.state.plan)
        if next_step:
            self.planner.update_step_status(
                self.state.plan,
                next_step["id"],
                "in_progress",
                f"Executing: {tool_name}"
            )
            self.report.plan_steps = self.state.plan.get("steps", [])

    def _parse_simple_args(self, tool_name: str, args_text: str) -> dict:
        args = {}
        for line in args_text.split("\n"):
            line = line.strip()
            if ":" in line:
                key, value = line.split(":", 1)
                args[key.strip()] = value.strip()
        return args

    async def _act(self):
        self.state.update(status=AgentStatus.ACTING)

        tool_name = self.state.last_action
        arguments = self.state.last_result if isinstance(self.state.last_result, dict) else {}

        # Validate tool name before attempting execution
        valid_tools = {t.name for t in self.tools.list_tools()}
        if tool_name not in valid_tools and not tool_name.startswith("skill:"):
            logger.warning(f"Invalid tool requested: {tool_name}")
            self.state.update(
                status=AgentStatus.ERROR,
                error=f"Unknown tool: {tool_name}",
                last_result=f"BLOCKED: Tool '{tool_name}' does not exist."
            )
            return

        logger.info(f"Executing: {tool_name}")
        
        # Check if this is a skill invocation
        if isinstance(arguments, dict) and arguments.get("_is_skill"):
            skill_name = arguments.get("skill_name", tool_name.replace("skill:", ""))
            context = arguments.get("context", {})
            
            logger.info(f"Invoking skill: {skill_name} with context: {context}")
            
            # Execute skill with failure isolation
            try:
                skills_runtime = self._get_skills_runtime()
                if skills_runtime:
                    await skills_runtime.initialize()
                    skill_result = skills_runtime.invoke_skill(skill_name, context)
                    
                    success = skill_result.get("success", False)
                    output = skill_result.get("result") if success else skill_result.get("error", "Unknown error")
                    
                    self.memory.add_tool_call(
                        self.state.session_id,
                        f"skill:{skill_name}",
                        context,
                        str(output)[:500],
                        success
                    )
                    
                    self.report.tool_calls.append({
                        "tool": f"skill:{skill_name}",
                        "args": context,
                        "success": success,
                        "result": str(output)[:200]
                    })
                    
                    self.state.last_result = output
                    return
            
            except Exception as e:
                logger.error(f"Skill invocation failed: {e}")
                error_msg = f"Skill error: {str(e)}"
                
                self.memory.add_tool_call(
                    self.state.session_id,
                    f"skill:{skill_name}",
                    context,
                    error_msg,
                    False
                )
                
                self.report.tool_calls.append({
                    "tool": f"skill:{skill_name}",
                    "args": context,
                    "success": False,
                    "result": error_msg
                })
                
                self.state.last_result = error_msg
                return
        
        # Regular tool execution
        logger.info(f"Executing tool: {tool_name} with args: {arguments}")
        
        # Check permissions via self-improver
        improver = self._get_self_improver()
        if improver:
            # Basic permission check
            if not improver.check_permission(tool_name):
                # If trust is low, we might need confirmation or block
                if improver.get_trust_level().value in ["stranger", "acquaintance"]:
                     logger.warning(f"Restricted tool '{tool_name}' access at trust level '{improver.get_trust_level().value}'")
                     # For now, let it pass but log it, or we could block it here

        result = await self.tools.execute(tool_name, arguments)

        if isinstance(result, ToolResult) and result.requires_confirmation:
            if settings.tool_auto_confirm:
                confirmed_args = dict(arguments)
                confirmed_args["_confirm"] = True
                result = await self.tools.execute(tool_name, confirmed_args)
            else:
                self.state.update(
                    status=AgentStatus.ERROR,
                    error="Tool requires confirmation",
                    last_result="BLOCKED: Tool requires confirmation."
                )
                return
        
        # Log to memory
        self.memory.add_tool_call(
            self.state.session_id,
            tool_name,
            arguments,
            str(result.output)[:500],
            result.success
        )

        # Update trust based on tool success
        if improver:
            improver.update_trust(f"tool:{tool_name}", result.success)
        
        # Add to report
        self.report.tool_calls.append({
            "tool": tool_name,
            "args": arguments,
            "success": result.success,
            "result": str(result.output)[:200]
        })
        
        self.state.last_result = result.output if result.success else result.error

    async def _verify(self) -> bool:
        """Verify if the task is complete after tool execution"""
        if not self.state.last_result:
            return False
        
        # Get current step
        next_step = self.planner.get_next_step(self.state.plan)
        
        if next_step:
            # Mark step as done
            self.planner.update_step_status(
                self.state.plan,
                next_step["id"],
                "done",
                str(self.state.last_result)[:200]
            )
            self.report.plan_steps = self.state.plan.get("steps", [])
        
        # Only auto-complete when the result is strong enough; otherwise let the
        # model reason over the completed step and emit DONE explicitly.
        if self.planner.is_plan_complete(self.state.plan) and self._should_auto_complete():
            return True
        
        # Check simple success conditions
        goal = self.state.goal.lower()
        
        # File creation success
        if "file" in goal and ("create" in goal or "write" in goal):
            if self._check_file_success():
                return True
        
        return False

    def _should_auto_complete(self) -> bool:
        goal = self.state.goal.lower()
        action = (self.state.last_action or "").lower()
        result = self.state.last_result

        if action == "filesystem":
            return self._check_file_success()

        if isinstance(result, str):
            upper = result.upper()
            if upper.startswith("DONE:"):
                return True

        # Shell/browser/code actions often need another reasoning pass before
        # we can say the goal is actually done.
        if action in {"shell", "browser", "code_exec"}:
            return False

        # For very small read/check goals, a successful non-empty result is enough.
        if any(word in goal for word in ["read", "check", "show", "list"]) and result:
            return True

        return False
    
    def _check_file_success(self) -> bool:
        """Check if file was created successfully"""
        # Get the arguments used
        args = self.state.last_result if isinstance(self.state.last_result, dict) else {}
        
        if "path" in args:
            file_path = Path(args["path"])
            if file_path.exists():
                return True
        
        # Check recent tool calls for file operations
        tool_history = self.memory.get_tool_history(self.state.session_id, limit=5)
        for call in reversed(tool_history):
            if call["tool_name"] == "filesystem":
                if call["success"] and "write" in str(call.get("arguments", "")).lower():
                    return True
        
        return False

    def get_status(self) -> Dict[str, Any]:
        return {
            "session_id": self.state.session_id,
            "status": self.state.status.value,
            "goal": self.state.goal,
            "plan": self.state.plan,
            "iteration": self.state.iteration,
            "last_action": self.state.last_action,
            "last_result": self.state.last_result,
            "error": self.state.error,
            "report": self.report.to_dict()
        }
