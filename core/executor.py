"""
Execution engine for the Crypto Intelligence Agent.
Executes plans, manages tool calls, and handles results.
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

from core.planner import ExecutionPlan, ExecutionStep, StepType
from core.tool_registry import get_tool_registry
from core.conversation import get_conversation_manager, ConversationRole
from database.storage import get_db_manager
from database.models import ToolExecution
from providers.kilo_api import get_ai_provider, get_kilo_provider, ModelTask, ChatMessage


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


@dataclass
class StepResult:
    """Result of a step execution."""
    step_id: str
    status: ExecutionStatus
    output: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class ExecutionResult:
    """Result of a complete plan execution."""
    plan_id: str
    status: ExecutionStatus
    step_results: List[StepResult]
    final_output: Any = None
    total_time: float = 0.0
    error: Optional[str] = None


class ExecutionEngine:
    """Executes plans step by step."""
    
    def __init__(self):
        self.tool_registry = get_tool_registry()
        self.conversation = get_conversation_manager()
        self.kilo_provider = None  # created lazily via await get_kilo_provider()
        self._cancelled = False
        self._progress_callback: Optional[Callable] = None
    
    def set_progress_callback(self, callback: Callable[[str, str, Any], None]) -> None:
        """Set callback for progress updates: callback(step_id, status, output)"""
        self._progress_callback = callback
    
    def cancel(self) -> None:
        """Cancel current execution."""
        self._cancelled = True
    
    async def execute_plan(self, plan: ExecutionPlan) -> ExecutionResult:
        """Execute a complete plan."""
        self._cancelled = False
        step_results = []
        step_outputs = {}  # step_id -> output
        start_time = time.time()
        
        # Build dependency graph
        step_map = {step.step_id: step for step in plan.steps}
        
        # Execute steps in topological order
        completed = set()
        failed = set()
        
        while len(completed) + len(failed) < len(plan.steps):
            # Find ready steps
            ready_steps = []
            for step in plan.steps:
                if step.step_id in completed or step.step_id in failed:
                    continue
                
                # Check dependencies
                deps_met = all(dep in completed for dep in step.depends_on)
                if deps_met:
                    ready_steps.append(step)
            
            if not ready_steps:
                # Circular dependency or all remaining failed
                for step in plan.steps:
                    if step.step_id not in completed and step.step_id not in failed:
                        failed.add(step.step_id)
                        step_results.append(StepResult(
                            step_id=step.step_id,
                            status=ExecutionStatus.FAILED,
                            error="Dependency not met (possible circular dependency)"
                        ))
                break
            
            # Execute ready steps (can run in parallel if independent)
            # For simplicity, run sequentially
            for step in ready_steps:
                if self._cancelled:
                    step_results.append(StepResult(
                        step_id=step.step_id,
                        status=ExecutionStatus.CANCELLED,
                        error="Execution cancelled by user"
                    ))
                    failed.add(step.step_id)
                    continue
                
                result = await self._execute_step(step, step_outputs)
                step_results.append(result)
                step_outputs[step.step_id] = result.output
                
                if result.status == ExecutionStatus.COMPLETED:
                    completed.add(step.step_id)
                else:
                    failed.add(step.step_id)
                
                # Progress callback
                if self._progress_callback:
                    self._progress_callback(step.step_id, result.status.value, result.output)
        
        # Final synthesis step
        final_step = next((s for s in plan.steps if s.type == StepType.AI_ANALYSIS), None)
        final_output = None
        
        if final_step and not self._cancelled:
            synthesis_result = await self._execute_synthesis(final_step, step_outputs, plan.user_request)
            step_results.append(synthesis_result)
            final_output = synthesis_result.output
        
        total_time = time.time() - start_time
        
        # Determine overall status
        if self._cancelled:
            status = ExecutionStatus.CANCELLED
        elif failed:
            status = ExecutionStatus.FAILED
        else:
            status = ExecutionStatus.COMPLETED
        
        return ExecutionResult(
            plan_id=plan.plan_id,
            status=status,
            step_results=step_results,
            final_output=final_output,
            total_time=total_time,
            error=step_results[-1].error if step_results and step_results[-1].status == ExecutionStatus.FAILED else None
        )
    
    async def _execute_step(self, step: ExecutionStep, previous_outputs: Dict) -> StepResult:
        """Execute a single step."""
        started_at = datetime.utcnow()
        start_time = time.time()
        
        # Notify running
        if self._progress_callback:
            self._progress_callback(step.step_id, ExecutionStatus.RUNNING.value, None)
        
        try:
            if step.type == StepType.DATA_FETCH or step.type == StepType.CALCULATION or step.type == StepType.TOOL:
                # Resolve parameters from previous outputs
                params = self._resolve_params(step.parameters, previous_outputs)
                
                # Execute tool
                output = await self.tool_registry.execute(step.tool_name, **params)
                
                # Log tool execution
                await self._log_tool_execution(step, params, output, True, None, time.time() - start_time)
                
            elif step.type == StepType.SKILL:
                # Skill execution would go here
                output = {"skill": step.name, "status": "not_implemented"}
            
            else:
                output = {"status": "unknown_step_type"}
            
            execution_time = time.time() - start_time
            
            return StepResult(
                step_id=step.step_id,
                status=ExecutionStatus.COMPLETED,
                output=output,
                execution_time=execution_time,
                started_at=started_at,
                completed_at=datetime.utcnow()
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            # Log failed execution
            await self._log_tool_execution(step, step.parameters, None, False, str(e), execution_time)
            
            return StepResult(
                step_id=step.step_id,
                status=ExecutionStatus.FAILED,
                error=str(e),
                execution_time=execution_time,
                started_at=started_at,
                completed_at=datetime.utcnow()
            )
    
    async def _execute_synthesis(
        self,
        step: ExecutionStep,
        step_outputs: Dict,
        user_request: str
    ) -> StepResult:
        """Execute AI synthesis step."""
        started_at = datetime.utcnow()
        start_time = time.time()
        
        # Lazily create the AI provider (init is synchronous, so await here)
        if self.kilo_provider is None:
            self.kilo_provider = await get_ai_provider()
        
        try:
            # Prepare context for AI
            context = {
                "user_request": user_request,
                "step_outputs": step_outputs
            }
            
            # Build synthesis prompt
            prompt = self._build_synthesis_prompt(user_request, step_outputs)
            
            # Get AI response — answers are produced in Arabic when possible
            messages = [
                ChatMessage(role="system", content="You are a cryptocurrency research analyst. Synthesize the provided data into a clear, actionable response. Answer in Arabic (Modern Standard Arabic) when the user writes in Arabic, otherwise answer in the language the user used."),
                ChatMessage(role="user", content=prompt)
            ]
            
            response = await self.kilo_provider.chat_completion(
                messages=messages,
                task=ModelTask.RESEARCH,
                temperature=0.3,
                max_tokens=4000
            )
            
            final_text = response.choices[0]["message"]["content"] if response.choices else "No response generated"
            
            # Add assistant message to conversation
            await self.conversation.add_message(
                role=ConversationRole.ASSISTANT,
                content=final_text,
                model_used=response.model,
                tokens_used=response.usage.get("total_tokens", 0),
                cost_usd=response.cost_usd
            )
            
            execution_time = time.time() - start_time
            
            return StepResult(
                step_id=step.step_id,
                status=ExecutionStatus.COMPLETED,
                output=final_text,
                execution_time=execution_time,
                started_at=started_at,
                completed_at=datetime.utcnow()
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            return StepResult(
                step_id=step.step_id,
                status=ExecutionStatus.FAILED,
                error=f"Synthesis failed: {e}",
                execution_time=execution_time,
                started_at=started_at,
                completed_at=datetime.utcnow()
            )
    
    def _build_synthesis_prompt(self, user_request: str, step_outputs: Dict) -> str:
        """Build prompt for result synthesis."""
        prompt = f"User Request: {user_request}\n\n"
        prompt += "Available Data:\n"
        
        for step_id, output in step_outputs.items():
            if output is None:
                continue
            
            prompt += f"\n--- {step_id} ---\n"
            
            if isinstance(output, dict):
                if "data" in output:
                    data = output["data"]
                    if isinstance(data, list):
                        prompt += f"Found {len(data)} items\n"
                        if data:
                            prompt += f"Sample: {str(data[0])[:500]}\n"
                    elif isinstance(data, dict):
                        prompt += f"{str(data)[:1000]}\n"
                    else:
                        prompt += f"{str(data)[:1000]}\n"
                else:
                    prompt += f"{str(output)[:1000]}\n"
            elif isinstance(output, list):
                prompt += f"List with {len(output)} items\n"
                if output:
                    prompt += f"Sample: {str(output[0])[:500]}\n"
            else:
                prompt += f"{str(output)[:1000]}\n"
        
        prompt += "\n\nPlease provide a comprehensive analysis addressing the user's request. Include:\n"
        prompt += "1. Key findings from the data\n"
        prompt += "2. Technical assessment (if applicable)\n"
        prompt += "3. Risk factors\n"
        prompt += "4. Potential scenarios (bullish/neutral/bearish)\n"
        prompt += "5. Clear recommendation\n"
        prompt += "6. Important caveats\n"
        
        return prompt
    
    def _resolve_params(self, params: Dict, previous_outputs: Dict) -> Dict:
        """Resolve parameter references to previous step outputs."""
        resolved = {}
        
        for key, value in params.items():
            if isinstance(value, str) and value.startswith("$step:"):
                # Reference to previous step output
                ref = value[6:]  # Remove $step:
                if ref in previous_outputs:
                    resolved[key] = previous_outputs[ref]
                else:
                    resolved[key] = value  # Keep as-is if not found
            elif isinstance(value, dict):
                resolved[key] = self._resolve_params(value, previous_outputs)
            elif isinstance(value, list):
                resolved[key] = [
                    self._resolve_params({"item": v}, previous_outputs)["item"]
                    if isinstance(v, (dict, str)) else v
                    for v in value
                ]
            else:
                resolved[key] = value
        
        return resolved
    
    async def _log_tool_execution(
        self,
        step: ExecutionStep,
        params: Dict,
        output: Any,
        success: bool,
        error: Optional[str],
        execution_time: float
    ) -> None:
        """Log tool execution to database."""
        try:
            db = await get_db_manager()
            conv = get_conversation_manager()
            
            if conv._current_session:
                await db.log_tool_execution(
                    session_id=conv._current_session.id,
                    tool_name=step.tool_name or step.name,
                    skill_name=None,
                    input_params=params,
                    output_data=output if isinstance(output, dict) else {"result": str(output)},
                    success=success,
                    error_message=error,
                    execution_time_ms=int(execution_time * 1000)
                )
        except Exception:
            pass  # Don't fail execution due to logging


# Global executor instance
_executor: Optional[ExecutionEngine] = None


def get_executor() -> ExecutionEngine:
    """Get the global executor instance."""
    global _executor
    if _executor is None:
        _executor = ExecutionEngine()
    return _executor