"""Planning system for generating and managing execution plans."""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from loguru import logger

from cognitive.ollama_client import get_ollama_client
from cognitive.prompt_templates import PromptTemplates
from config.settings import settings


class StepStatus(Enum):
    """Status of a plan step."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"


class PlanStatus(Enum):
    """Status of an execution plan."""
    DRAFT = "draft"
    PENDING_CONFIRMATION = "pending_confirmation"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PlanStep:
    """Single step in an execution plan."""
    step_number: int
    description: str
    tool: str
    command: str
    confirmation_level: str
    verification: str
    rollback: str
    dependencies: List[int] = field(default_factory=list)
    status: str = StepStatus.PENDING.value
    result: Optional[Any] = None
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    execution_time_ms: Optional[int] = None


@dataclass
class ExecutionPlan:
    """Complete execution plan."""
    plan_id: str
    description: str
    estimated_duration: str
    steps: List[PlanStep]
    risk_assessment: str
    rollback_plan: str
    status: str = PlanStatus.DRAFT.value
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    user_id: Optional[str] = None
    original_command: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class Planner:
    """Generates and manages execution plans."""
    
    def __init__(self):
        self.ollama = get_ollama_client()
        self.templates = PromptTemplates()
        self.active_plans: Dict[str, ExecutionPlan] = {}
        self.plan_history: List[ExecutionPlan] = []
        
        logger.info("Planner initialized")
    
    async def analyze_command(
        self,
        command: str,
        user_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze a user command for intent, ambiguities, and requirements.
        
        Returns:
            Analysis result with intent, ambiguities, and recommendations
        """
        import os
        import platform
        
        context = context or {}
        
        prompt = self.templates.format_command_analysis(
            command=command,
            cwd=os.getcwd(),
            os_info=f"{platform.system()} {platform.release()}",
            history=context.get("history", "No previous actions")
        )
        
        try:
            result = await self.ollama.structured_generate(
                prompt=prompt,
                system=self.templates.format_system_prompt(
                    agent_name=settings.agent_name,
                    safety_mode=settings.safety_mode,
                    user_id=user_id,
                    session_id=str(uuid.uuid4())[:8]
                ),
                temperature=0.3
            )
            
            logger.info(f"Command analysis complete for: {command[:50]}...")
            return result
            
        except Exception as e:
            logger.error(f"Command analysis failed: {e}")
            return {
                "intent": command,
                "ambiguities": ["Analysis failed, proceeding with caution"],
                "questions": [],
                "capabilities_required": ["system"],
                "risk_level": "medium",
                "confirmation_level": "standard",
                "can_proceed": True,
                "reasoning": f"Error during analysis: {str(e)}"
            }
    
    async def detect_ambiguities(self, command: str) -> Dict[str, Any]:
        """
        Detect ambiguities and missing information in a command.
        
        Returns:
            Ambiguity detection results
        """
        prompt = self.templates.format_ambiguity_detection(command=command)
        
        try:
            result = await self.ollama.structured_generate(
                prompt=prompt,
                temperature=0.3
            )
            
            logger.info(f"Ambiguity detection complete: {result.get('is_ambiguous', False)}")
            return result
            
        except Exception as e:
            logger.error(f"Ambiguity detection failed: {e}")
            return {
                "is_ambiguous": False,
                "ambiguities": [],
                "suggested_questions": [],
                "assumed_interpretation": command,
                "confidence": "low"
            }
    
    async def create_plan(
        self,
        task: str,
        user_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ExecutionPlan:
        """
        Create an execution plan for a task.
        
        Returns:
            ExecutionPlan with detailed steps
        """
        context_str = json.dumps(context, indent=2) if context else "No additional context"
        
        prompt = self.templates.format_planning(
            task=task,
            context=context_str
        )
        
        try:
            result = await self.ollama.structured_generate(
                prompt=prompt,
                system=self.templates.format_system_prompt(
                    agent_name=settings.agent_name,
                    safety_mode=settings.safety_mode,
                    user_id=user_id,
                    session_id=str(uuid.uuid4())[:8]
                ),
                temperature=0.4
            )
            
            # Parse steps from result
            steps_data = result.get("steps", [])
            steps = []
            for i, step_data in enumerate(steps_data, 1):
                step = PlanStep(
                    step_number=step_data.get("step_number", i),
                    description=step_data.get("description", f"Step {i}"),
                    tool=step_data.get("tool", "system"),
                    command=step_data.get("command", ""),
                    confirmation_level=step_data.get("confirmation_level", "standard"),
                    verification=step_data.get("verification", "Check output"),
                    rollback=step_data.get("rollback", "Manual recovery needed"),
                    dependencies=step_data.get("dependencies", [])
                )
                steps.append(step)
            
            plan = ExecutionPlan(
                plan_id=str(uuid.uuid4())[:8],
                description=result.get("description", task),
                estimated_duration=result.get("estimated_duration", "unknown"),
                steps=steps,
                risk_assessment=result.get("risk_assessment", "unknown"),
                rollback_plan=result.get("rollback_plan", "Manual recovery"),
                user_id=user_id,
                original_command=task
            )
            
            self.active_plans[plan.plan_id] = plan
            
            logger.info(f"Created plan {plan.plan_id} with {len(steps)} steps")
            return plan
            
        except Exception as e:
            logger.error(f"Plan creation failed: {e}")
            # Create a minimal fallback plan
            plan = ExecutionPlan(
                plan_id=str(uuid.uuid4())[:8],
                description=task,
                estimated_duration="unknown",
                steps=[PlanStep(
                    step_number=1,
                    description=f"Execute: {task}",
                    tool="system",
                    command=task,
                    confirmation_level="critical",
                    verification="Check if task completed",
                    rollback="Manual recovery"
                )],
                risk_assessment="unknown - plan generation failed",
                rollback_plan="Manual recovery required",
                user_id=user_id,
                original_command=task
            )
            self.active_plans[plan.plan_id] = plan
            return plan
    
    async def evaluate_step_execution(
        self,
        step: PlanStep,
        execution_result: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Evaluate the result of executing a plan step.
        
        Returns:
            Evaluation with next action recommendation
        """
        context_str = json.dumps(context, indent=2) if context else "No additional context"
        
        prompt = self.templates.format_step_execution(
            step_description=step.description,
            tool=step.tool,
            command=step.command,
            context=context_str
        )
        
        # Add execution result to prompt
        prompt += f"\n\nACTUAL EXECUTION RESULT:\n{json.dumps(execution_result, indent=2)}"
        
        try:
            result = await self.ollama.structured_generate(
                prompt=prompt,
                temperature=0.3
            )
            
            logger.info(f"Step evaluation complete: {result.get('success', False)}")
            return result
            
        except Exception as e:
            logger.error(f"Step evaluation failed: {e}")
            return {
                "success": execution_result.get("success", False),
                "executed_command": step.command,
                "output": execution_result.get("output", ""),
                "error": execution_result.get("error", str(e)),
                "verification_result": "unknown",
                "next_action": "continue" if execution_result.get("success") else "ask_user",
                "notes": f"Evaluation failed: {str(e)}"
            }
    
    async def evaluate_completion(
        self,
        plan: ExecutionPlan,
        execution_summary: str
    ) -> Dict[str, Any]:
        """
        Evaluate the completion of an entire plan.
        
        Returns:
            Self-evaluation results
        """
        prompt = self.templates.format_self_evaluation(
            task=plan.description,
            summary=execution_summary
        )
        
        try:
            result = await self.ollama.structured_generate(
                prompt=prompt,
                temperature=0.4
            )
            
            logger.info(f"Completion evaluation finished")
            return result
            
        except Exception as e:
            logger.error(f"Completion evaluation failed: {e}")
            return {
                "success": True,
                "completion_percentage": 100,
                "issues_encountered": [f"Evaluation error: {str(e)}"],
                "improvements_suggested": [],
                "follow_up_needed": False,
                "follow_up_actions": [],
                "user_should_know": ["Task completed but evaluation failed"]
            }
    
    async def analyze_error(
        self,
        error: str,
        step: PlanStep,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze an error and suggest recovery options.
        
        Returns:
            Error analysis with recovery recommendations
        """
        context_str = json.dumps(context, indent=2) if context else "No additional context"
        
        prompt = self.templates.format_error_recovery(
            error=error,
            step_description=step.description,
            context=context_str
        )
        
        try:
            result = await self.ollama.structured_generate(
                prompt=prompt,
                temperature=0.3
            )
            
            logger.info(f"Error analysis complete: {result.get('error_type', 'unknown')}")
            return result
            
        except Exception as e:
            logger.error(f"Error analysis failed: {e}")
            return {
                "error_type": "unknown",
                "is_recoverable": False,
                "cause_analysis": f"Analysis failed: {str(e)}",
                "recovery_options": [
                    {
                        "action": "ask_user",
                        "description": "Ask user for guidance",
                        "likelihood_of_success": "high"
                    }
                ],
                "recommended_action": "ask_user",
                "reasoning": "Error analysis failed, need user input"
            }
    
    def get_plan(self, plan_id: str) -> Optional[ExecutionPlan]:
        """Get a plan by ID."""
        return self.active_plans.get(plan_id)
    
    def update_plan_status(self, plan_id: str, status: PlanStatus) -> bool:
        """Update the status of a plan."""
        if plan_id not in self.active_plans:
            return False
        
        plan = self.active_plans[plan_id]
        plan.status = status.value
        
        if status == PlanStatus.IN_PROGRESS and not plan.started_at:
            plan.started_at = datetime.now().isoformat()
        elif status in [PlanStatus.COMPLETED, PlanStatus.FAILED, PlanStatus.CANCELLED]:
            plan.completed_at = datetime.now().isoformat()
            self.plan_history.append(plan)
        
        logger.info(f"Plan {plan_id} status updated to {status.value}")
        return True
    
    def update_step_status(
        self,
        plan_id: str,
        step_number: int,
        status: StepStatus,
        result: Optional[Any] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """Update the status of a plan step."""
        plan = self.active_plans.get(plan_id)
        if not plan:
            return False
        
        for step in plan.steps:
            if step.step_number == step_number:
                step.status = status.value
                
                if status == StepStatus.IN_PROGRESS and not step.started_at:
                    step.started_at = datetime.now().isoformat()
                elif status in [StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.SKIPPED]:
                    step.completed_at = datetime.now().isoformat()
                    if step.started_at:
                        start = datetime.fromisoformat(step.started_at)
                        end = datetime.fromisoformat(step.completed_at)
                        step.execution_time_ms = int((end - start).total_seconds() * 1000)
                
                if result is not None:
                    step.result = result
                if error_message:
                    step.error_message = error_message
                
                logger.info(f"Plan {plan_id} step {step_number} updated to {status.value}")
                return True
        
        return False
    
    def get_plan_summary(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Get a summary of a plan's current state."""
        plan = self.active_plans.get(plan_id)
        if not plan:
            return None
        
        completed = sum(1 for s in plan.steps if s.status == StepStatus.COMPLETED.value)
        failed = sum(1 for s in plan.steps if s.status == StepStatus.FAILED.value)
        in_progress = sum(1 for s in plan.steps if s.status == StepStatus.IN_PROGRESS.value)
        pending = sum(1 for s in plan.steps if s.status == StepStatus.PENDING.value)
        
        return {
            "plan_id": plan.plan_id,
            "description": plan.description,
            "status": plan.status,
            "total_steps": len(plan.steps),
            "completed": completed,
            "failed": failed,
            "in_progress": in_progress,
            "pending": pending,
            "progress_percentage": (completed / len(plan.steps) * 100) if plan.steps else 0
        }
    
    def format_plan_for_display(self, plan: ExecutionPlan) -> str:
        """Format a plan for user display."""
        lines = [
            f"📋 **Execution Plan: {plan.plan_id}**",
            f"",
            f"**Description:** {plan.description}",
            f"**Status:** {plan.status}",
            f"**Estimated Duration:** {plan.estimated_duration}",
            f"**Risk Assessment:** {plan.risk_assessment}",
            f"",
            f"**Steps:**",
        ]
        
        for step in plan.steps:
            emoji = {
                StepStatus.PENDING.value: "⏳",
                StepStatus.IN_PROGRESS.value: "🔄",
                StepStatus.COMPLETED.value: "✅",
                StepStatus.FAILED.value: "❌",
                StepStatus.SKIPPED.value: "⏭️"
            }.get(step.status, "❓")
            
            lines.append(f"{emoji} **Step {step.step_number}:** {step.description}")
            lines.append(f"   Tool: `{step.tool}` | Confirmation: `{step.confirmation_level}`")
            lines.append(f"   Status: {step.status}")
            lines.append("")
        
        return "\n".join(lines)


# Global planner instance
_planner: Optional[Planner] = None


def get_planner() -> Planner:
    """Get or create global planner instance."""
    global _planner
    if _planner is None:
        _planner = Planner()
    return _planner
