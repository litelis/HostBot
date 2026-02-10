"""
Brain orchestrator for HostBot.
Central AI coordinator that manages multiple specialized AI models and makes decisions.
Acts as the "brain" that uses vision, reasoning, and specialized models to achieve goals.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Callable

from loguru import logger

from .ollama_client import get_ollama_client, OllamaClient
from vision.vision_orchestrator import get_vision_orchestrator, VisionOrchestrator


class TaskPriority(Enum):
    """Priority levels for tasks."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskStatus(Enum):
    """Status of a task."""
    PENDING = "pending"
    ANALYZING = "analyzing"
    PLANNING = "planning"
    EXECUTING = "executing"
    WAITING_VISION = "waiting_vision"
    WAITING_CONFIRMATION = "waiting_confirmation"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SubTask:
    """A subtask delegated to a specialized AI."""
    id: str
    type: str  # "vision", "code", "audio", "ocr", "reasoning"
    description: str
    parameters: Dict[str, Any]
    result: Optional[Any] = None
    status: str = "pending"
    assigned_model: Optional[str] = None


@dataclass
class BrainTask:
    """A task being processed by the brain."""
    id: str
    goal: str
    priority: TaskPriority
    status: TaskStatus
    created_at: datetime
    context: Dict[str, Any] = field(default_factory=dict)
    subtasks: List[SubTask] = field(default_factory=list)
    plan: Optional[List[Dict]] = None
    current_step: int = 0
    results: List[Dict] = field(default_factory=list)
    error: Optional[str] = None


class BrainOrchestrator:
    """
    Central brain that orchestrates multiple AI models.
    
    Responsibilities:
    1. Receive high-level goals from users
    2. Decide which specialized AI to use (vision, code, audio, etc.)
    3. Coordinate between AIs
    4. Make final decisions on actions
    5. Learn from results
    """
    
    def __init__(self):
        """Initialize brain orchestrator."""
        # AI clients
        self.ollama = get_ollama_client()
        self.vision = get_vision_orchestrator()
        
        # Task management
        self.active_tasks: Dict[str, BrainTask] = {}
        self.completed_tasks: List[BrainTask] = []
        self.max_completed_history = 50
        
        # Specialized model configuration
        self.models = {
            "vision": "llava",  # For image analysis
            "code": "codellama",  # For code generation
            "general": "llama3.2",  # For general reasoning
            "fast": "llama3.2",  # For quick responses
        }
        
        # Decision callbacks
        self.on_decision: Optional[Callable] = None
        self.on_task_complete: Optional[Callable] = None
        
        logger.info("BrainOrchestrator initialized")
        logger.info(f"Available models: {self.models}")
    
    async def process_goal(
        self,
        goal: str,
        priority: TaskPriority = TaskPriority.MEDIUM,
        context: Optional[Dict] = None
    ) -> BrainTask:
        """
        Process a high-level goal.
        
        This is the main entry point for the brain.
        
        Args:
            goal: High-level goal description
            priority: Task priority
            context: Additional context
            
        Returns:
            BrainTask object tracking the task
        """
        import uuid
        
        task_id = str(uuid.uuid4())[:8]
        
        task = BrainTask(
            id=task_id,
            goal=goal,
            priority=priority,
            status=TaskStatus.PENDING,
            created_at=datetime.now(),
            context=context or {}
        )
        
        self.active_tasks[task_id] = task
        logger.info(f"[Task {task_id}] New goal: {goal}")
        
        # Start processing
        asyncio.create_task(self._process_task(task))
        
        return task
    
    async def _process_task(self, task: BrainTask) -> None:
        """
        Main processing loop for a task.
        
        The brain follows this loop:
        1. Analyze what needs to be done
        2. Check current state (using vision if needed)
        3. Decide on approach
        4. Delegate to specialized AIs
        5. Execute actions
        6. Verify results
        7. Repeat until goal achieved
        """
        try:
            task.status = TaskStatus.ANALYZING
            logger.info(f"[Task {task.id}] Analyzing goal...")
            
            # Step 1: Initial analysis - understand the goal
            analysis = await self._analyze_goal(task)
            
            # Step 2: Determine if we need vision
            needs_vision = analysis.get("requires_vision", False)
            
            if needs_vision:
                task.status = TaskStatus.WAITING_VISION
                vision_result = await self._use_vision(task, analysis)
                
                if not vision_result["success"]:
                    task.status = TaskStatus.FAILED
                    task.error = f"Vision failed: {vision_result.get('error')}"
                    await self._complete_task(task)
                    return
                
                # Update context with vision data
                task.context["vision"] = vision_result
            
            # Step 3: Create execution plan
            task.status = TaskStatus.PLANNING
            plan = await self._create_plan(task, analysis)
            task.plan = plan
            
            logger.info(f"[Task {task.id}] Plan created with {len(plan)} steps")
            
            # Step 4: Execute plan
            task.status = TaskStatus.EXECUTING
            
            for step_idx, step in enumerate(plan):
                task.current_step = step_idx
                
                logger.info(f"[Task {task.id}] Executing step {step_idx + 1}/{len(plan)}: {step.get('description', 'Unknown')}")
                
                # Execute the step
                step_result = await self._execute_step(task, step)
                task.results.append(step_result)
                
                if not step_result["success"]:
                    # Check if we should retry or abort
                    if step.get("critical", False):
                        task.status = TaskStatus.FAILED
                        task.error = f"Critical step {step_idx + 1} failed: {step_result.get('error')}"
                        await self._complete_task(task)
                        return
                
                # Brief pause between steps
                await asyncio.sleep(0.5)
            
            # Task completed successfully
            task.status = TaskStatus.COMPLETED
            logger.info(f"[Task {task.id}] Completed successfully")
            await self._complete_task(task)
            
        except Exception as e:
            logger.error(f"[Task {task.id}] Processing error: {e}")
            task.status = TaskStatus.FAILED
            task.error = str(e)
            await self._complete_task(task)
    
    async def _analyze_goal(self, task: BrainTask) -> Dict[str, Any]:
        """
        Analyze the goal to understand what needs to be done.
        
        Args:
            task: The task to analyze
            
        Returns:
            Analysis results
        """
        prompt = f"""Analyze this goal and determine the best approach:

Goal: {task.goal}

Context: {task.context}

Answer these questions:
1. What is the main objective?
2. What tools/capabilities are needed? (system, desktop, browser, vision, etc.)
3. Does this require seeing the screen? (vision)
4. What are the potential risks?
5. What should be the first step?

Return as JSON:
{{
    "objective": "string",
    "capabilities_needed": ["list"],
    "requires_vision": true/false,
    "risk_level": "low/medium/high",
    "first_step": "string",
    "estimated_steps": number
}}"""
        
        try:
            response = await self.ollama.generate(
                prompt=prompt,
                model=self.models["general"],
                temperature=0.3,
                format="json"
            )
            
            result = response.get("response", "{}")
            
            # Try to parse as JSON
            import json
            try:
                return json.loads(result)
            except:
                # Fallback to text analysis
                return {
                    "objective": task.goal,
                    "capabilities_needed": ["system"],
                    "requires_vision": "screen" in task.goal.lower() or "click" in task.goal.lower(),
                    "risk_level": "medium",
                    "first_step": "Analyze the task",
                    "estimated_steps": 3,
                    "raw_analysis": result
                }
                
        except Exception as e:
            logger.error(f"Goal analysis failed: {e}")
            return {
                "objective": task.goal,
                "capabilities_needed": ["system"],
                "requires_vision": False,
                "risk_level": "medium",
                "first_step": "Start execution",
                "estimated_steps": 3,
                "error": str(e)
            }
    
    async def _use_vision(self, task: BrainTask, analysis: Dict) -> Dict[str, Any]:
        """
        Use vision AI to see and understand the screen.
        
        Args:
            task: Current task
            analysis: Goal analysis
            
        Returns:
            Vision analysis results
        """
        logger.info(f"[Task {task.id}] Using vision to analyze screen...")
        
        # Capture and analyze screen
        vision_result = await self.vision.see_and_analyze(
            task=task.goal,
            save_screenshot=False
        )
        
        if vision_result["success"]:
            # Get additional insights
            suggestion = await self.vision.suggest_next_action(
                goal=task.goal,
                current_step=analysis.get("first_step", "Start")
            )
            
            vision_result["suggestion"] = suggestion
        
        return vision_result
    
    async def _create_plan(
        self,
        task: BrainTask,
        analysis: Dict
    ) -> List[Dict]:
        """
        Create an execution plan based on analysis.
        
        Args:
            task: Current task
            analysis: Goal analysis
            
        Returns:
            List of plan steps
        """
        # Include vision context if available
        vision_context = ""
        if "vision" in task.context:
            vision = task.context["vision"]
            if vision.get("success"):
                analysis_data = vision["analysis"]["analysis"]
                vision_context = f"\nCurrent screen state: {analysis_data}\n"
        
        prompt = f"""Create a detailed execution plan for this goal:

Goal: {task.goal}
{vision_context}

Capabilities available:
- system: Execute system commands
- desktop: Control mouse and keyboard
- browser: Automate web browser
- application: Install/manage software
- vision: See and analyze screen

Create a step-by-step plan. Each step should specify:
- description: what to do
- tool: which capability to use
- command: specific command/action
- confirmation_level: none/standard/critical
- critical: true/false (if true, failure stops the task)

Return as JSON array of steps."""
        
        try:
            response = await self.ollama.generate(
                prompt=prompt,
                model=self.models["code"],
                temperature=0.3,
                format="json"
            )
            
            result = response.get("response", "[]")
            
            import json
            try:
                plan = json.loads(result)
                if isinstance(plan, list):
                    return plan
                elif isinstance(plan, dict) and "steps" in plan:
                    return plan["steps"]
                else:
                    return [plan]
            except:
                # Fallback plan
                return [
                    {
                        "description": f"Execute: {task.goal}",
                        "tool": "system",
                        "command": task.goal,
                        "confirmation_level": "standard",
                        "critical": False
                    }
                ]
                
        except Exception as e:
            logger.error(f"Plan creation failed: {e}")
            return [
                {
                    "description": f"Execute: {task.goal}",
                    "tool": "system",
                    "command": task.goal,
                    "confirmation_level": "standard",
                    "critical": False
                }
            ]
    
    async def _execute_step(
        self,
        task: BrainTask,
        step: Dict
    ) -> Dict[str, Any]:
        """
        Execute a single plan step.
        
        Args:
            task: Current task
            step: Step to execute
            
        Returns:
            Execution results
        """
        tool = step.get("tool", "system")
        command = step.get("command", "")
        description = step.get("description", "Unknown step")
        
        logger.info(f"[Task {task.id}] Tool: {tool}, Command: {command[:50]}...")
        
        # This will be integrated with the main agent's execution layer
        # For now, return the action to be executed
        return {
            "success": True,
            "step": step,
            "tool": tool,
            "command": command,
            "status": "ready_to_execute",
            "description": description
        }
    
    async def _complete_task(self, task: BrainTask) -> None:
        """
        Complete a task and clean up.
        
        Args:
            task: Task to complete
        """
        # Move to completed history
        if task.id in self.active_tasks:
            del self.active_tasks[task.id]
        
        self.completed_tasks.append(task)
        
        # Trim history
        if len(self.completed_tasks) > self.max_completed_history:
            self.completed_tasks = self.completed_tasks[-self.max_completed_history:]
        
        # Notify callback
        if self.on_task_complete:
            try:
                await self.on_task_complete(task)
            except Exception as e:
                logger.error(f"Task completion callback error: {e}")
        
        logger.info(f"[Task {task.id}] Final status: {task.status.value}")
    
    async def get_task_status(self, task_id: str) -> Optional[BrainTask]:
        """Get status of a task."""
        return self.active_tasks.get(task_id) or \
               next((t for t in self.completed_tasks if t.id == task_id), None)
    
    def get_active_tasks(self) -> List[BrainTask]:
        """Get list of active tasks."""
        return list(self.active_tasks.values())
    
    def get_recent_tasks(self, limit: int = 10) -> List[BrainTask]:
        """Get recent completed tasks."""
        return self.completed_tasks[-limit:]
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel an active task."""
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            task.status = TaskStatus.CANCELLED
            await self._complete_task(task)
            return True
        return False
    
    def get_brain_status(self) -> Dict[str, Any]:
        """Get overall brain status."""
        return {
            "active_tasks": len(self.active_tasks),
            "completed_tasks": len(self.completed_tasks),
            "models_configured": self.models,
            "healthy": True
        }


# Global brain orchestrator instance
_brain_orchestrator: Optional[BrainOrchestrator] = None


def get_brain_orchestrator() -> BrainOrchestrator:
    """Get or create global brain orchestrator instance."""
    global _brain_orchestrator
    if _brain_orchestrator is None:
        _brain_orchestrator = BrainOrchestrator()
    return _brain_orchestrator
