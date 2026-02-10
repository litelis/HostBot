"""Core agent that orchestrates all components including vision and brain."""

import asyncio
from typing import Any, Dict, List, Optional

from loguru import logger

from cognitive.ollama_client import get_ollama_client
from cognitive.planner import get_planner, Planner, ExecutionPlan
from cognitive.brain_orchestrator import get_brain_orchestrator, BrainOrchestrator, TaskPriority
from vision.vision_orchestrator import get_vision_orchestrator, VisionOrchestrator
from execution.system_controller import get_system_controller, SystemController
from execution.desktop_controller import get_desktop_controller, DesktopController
from execution.browser_controller import get_browser_controller, BrowserController
from execution.application_controller import get_application_controller, ApplicationController
from safety.audit_logger import get_audit_logger, AuditLogger, ActionType
from safety.confirmation_manager import get_confirmation_manager, ConfirmationManager
from safety.emergency_stop import get_emergency_stop, EmergencyStop
from safety.permission_guard import get_permission_guard, PermissionGuard, OperationCategory
from config.settings import settings


class Agent:
    """
    Core autonomous agent that orchestrates all components.
    
    Enhanced with:
    - Vision capabilities (screen capture and analysis)
    - Brain orchestration (central AI coordinator)
    - Multi-model AI delegation
    """
    
    def __init__(self):
        # Safety layer
        self.audit: Optional[AuditLogger] = None
        self.confirmation_manager: Optional[ConfirmationManager] = None
        self.emergency_stop: Optional[EmergencyStop] = None
        self.permission_guard: Optional[PermissionGuard] = None
        
        # Cognitive layer
        self.ollama = None
        self.planner: Optional[Planner] = None
        self.brain: Optional[BrainOrchestrator] = None  # NEW: Central brain
        
        # Vision layer - NEW
        self.vision: Optional[VisionOrchestrator] = None
        
        # Execution layer
        self.system_controller: Optional[SystemController] = None
        self.desktop_controller: Optional[DesktopController] = None
        self.browser_controller: Optional[BrowserController] = None
        self.application_controller: Optional[ApplicationController] = None
        
        # State
        self.initialized = False
        self.state = "idle"  # idle, processing, executing, paused, error
        self.vision_enabled = True  # NEW: Toggle vision capabilities
        
        logger.info("Agent instance created (with vision and brain capabilities)")
    
    async def initialize(self) -> bool:
        """Initialize all agent components including vision and brain."""
        try:
            logger.info("Initializing agent components...")
            
            # Initialize safety layer first
            self.audit = get_audit_logger()
            self.confirmation_manager = get_confirmation_manager()
            self.emergency_stop = get_emergency_stop()
            self.permission_guard = get_permission_guard()
            
            # Register emergency stop handler
            self.emergency_stop.register_handler(self._on_emergency_stop)
            
            # Initialize cognitive layer
            self.ollama = get_ollama_client()
            self.planner = get_planner()
            self.brain = get_brain_orchestrator()  # NEW: Initialize brain
            
            # Initialize vision layer - NEW
            logger.info("Initializing vision capabilities...")
            self.vision = get_vision_orchestrator()
            
            # Initialize execution layer
            self.system_controller = get_system_controller()
            self.desktop_controller = get_desktop_controller()
            self.browser_controller = get_browser_controller()
            self.application_controller = get_application_controller()
            
            # Check Ollama connection
            ollama_ok = await self.ollama.check_connection()
            if not ollama_ok:
                logger.warning("Ollama connection failed - AI features may be limited")
            
            # Check vision model availability - NEW
            vision_models = await self.ollama.list_models()
            vision_available = any("llava" in m.lower() for m in vision_models)
            if not vision_available:
                logger.warning("No vision model (llava) found - vision features disabled")
                self.vision_enabled = False
            
            self.initialized = True
            self.state = "idle"
            
            logger.info("Agent initialization complete")
            logger.info(f"Vision enabled: {self.vision_enabled}")
            logger.info(f"Brain orchestrator: Active")
            
            # Log startup
            self.audit.log_event(
                action_type=ActionType.SYSTEM_COMMAND,
                description="Agent initialized with vision and brain capabilities",
                user_id="system"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Agent initialization failed: {e}")
            self.state = "error"
            return False
    
    async def _on_emergency_stop(self, level: Any, reason: str) -> None:
        """Handle emergency stop event."""
        logger.critical(f"Emergency stop handler called: {level.value} - {reason}")
        self.state = "paused"
        
        # Cancel all pending confirmations
        if self.confirmation_manager:
            cancelled = self.confirmation_manager.cancel_pending()
            logger.info(f"Cancelled {cancelled} pending confirmations")
        
        # Cancel active brain tasks - NEW
        if self.brain:
            for task in self.brain.get_active_tasks():
                await self.brain.cancel_task(task.id)
                logger.info(f"Cancelled brain task: {task.id}")
    
    # ==================== VISION METHODS (NEW) ====================
    
    async def see(self, task: Optional[str] = None) -> Dict[str, Any]:
        """
        Capture and analyze the screen.
        
        Args:
            task: Optional task context for better analysis
            
        Returns:
            Vision analysis results
        """
        if not self.vision or not self.vision_enabled:
            return {"success": False, "error": "Vision not available"}
        
        try:
            result = await self.vision.see_and_analyze(task=task)
            return result
        except Exception as e:
            logger.error(f"Vision error: {e}")
            return {"success": False, "error": str(e)}
    
    async def find_on_screen(self, element_description: str) -> Dict[str, Any]:
        """
        Find an element on the screen.
        
        Args:
            element_description: Description of element to find
            
        Returns:
            Element location if found
        """
        if not self.vision or not self.vision_enabled:
            return {"success": False, "error": "Vision not available"}
        
        return await self.vision.find_and_click(element_description)
    
    async def read_screen(self) -> Dict[str, Any]:
        """
        Read all text visible on screen.
        
        Returns:
            Extracted text elements
        """
        if not self.vision or not self.vision_enabled:
            return {"success": False, "error": "Vision not available"}
        
        return await self.vision.read_screen_text()
    
    async def suggest_action(self, goal: str) -> Dict[str, Any]:
        """
        Get AI suggestion for next action based on current screen.
        
        Args:
            goal: The goal to achieve
            
        Returns:
            Suggested action
        """
        if not self.vision or not self.vision_enabled:
            return {"success": False, "error": "Vision not available"}
        
        return await self.vision.suggest_next_action(goal=goal)
    
    # ==================== BRAIN METHODS (NEW) ====================
    
    async def think_and_act(
        self,
        goal: str,
        priority: str = "medium",
        use_vision: bool = True
    ) -> Dict[str, Any]:
        """
        Use the brain to analyze, plan, and execute a goal.
        
        This is the main autonomous loop:
        1. Brain analyzes the goal
        2. Uses vision if needed (and enabled)
        3. Creates execution plan
        4. Executes steps
        5. Verifies results
        
        Args:
            goal: High-level goal to achieve
            priority: Task priority (low/medium/high/critical)
            use_vision: Whether to use vision capabilities
            
        Returns:
            Task execution results
        """
        if not self.brain:
            return {"success": False, "error": "Brain not initialized"}
        
        # Map priority string to enum
        priority_map = {
            "low": TaskPriority.LOW,
            "medium": TaskPriority.MEDIUM,
            "high": TaskPriority.HIGH,
            "critical": TaskPriority.CRITICAL
        }
        task_priority = priority_map.get(priority.lower(), TaskPriority.MEDIUM)
        
        # Create context with vision preference
        context = {
            "use_vision": use_vision and self.vision_enabled,
            "vision_orchestrator": self.vision
        }
        
        # Submit goal to brain
        task = await self.brain.process_goal(
            goal=goal,
            priority=task_priority,
            context=context
        )
        
        # Wait for task to complete (with timeout)
        max_wait = 300  # 5 minutes max
        waited = 0
        
        while task.status.value not in ["completed", "failed", "cancelled"]:
            await asyncio.sleep(1)
            waited += 1
            
            if waited > max_wait:
                await self.brain.cancel_task(task.id)
                return {
                    "success": False,
                    "error": "Task timeout",
                    "task_id": task.id
                }
        
        # Execute the plan steps
        if task.plan and task.status.value == "completed":
            execution_result = await self._execute_brain_plan(task)
            return execution_result
        
        return {
            "success": task.status.value == "completed",
            "task_id": task.id,
            "status": task.status.value,
            "error": task.error,
            "plan": task.plan,
            "results": task.results
        }
    
    async def _execute_brain_plan(self, task: Any) -> Dict[str, Any]:
        """
        Execute the plan generated by the brain.
        
        Args:
            task: BrainTask with plan to execute
            
        Returns:
            Execution results
        """
        logger.info(f"[Brain] Executing plan for task {task.id}")
        
        execution_results = []
        
        for step in task.plan:
            # Check emergency stop
            if self.emergency_stop.check_stop():
                return {
                    "success": False,
                    "error": "Emergency stop triggered",
                    "completed_steps": len(execution_results)
                }
            
            # Execute the step using appropriate controller
            tool = step.get("tool", "system")
            command = step.get("command", "")
            description = step.get("description", "Unknown step")
            
            logger.info(f"[Brain] Executing: {description} (tool: {tool})")
            
            try:
                if tool == "system":
                    result = await self.system_controller.execute_command(command)
                elif tool == "desktop":
                    result = await self._execute_desktop_command(command)
                elif tool == "browser":
                    result = await self._execute_browser_command(command)
                elif tool == "application":
                    result = await self._execute_application_command(command)
                elif tool == "vision":
                    # Vision-based action
                    result = await self._execute_vision_command(command)
                else:
                    result = {
                        "success": False,
                        "error": f"Unknown tool: {tool}"
                    }
                
                execution_results.append({
                    "step": description,
                    "tool": tool,
                    "success": result.get("success", False),
                    "result": result
                })
                
                # Check if step failed and is critical
                if not result.get("success", False) and step.get("critical", False):
                    return {
                        "success": False,
                        "error": f"Critical step failed: {description}",
                        "completed_steps": len(execution_results),
                        "results": execution_results
                    }
                
                # Brief pause between steps
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Step execution error: {e}")
                execution_results.append({
                    "step": description,
                    "tool": tool,
                    "success": False,
                    "error": str(e)
                })
                
                if step.get("critical", False):
                    return {
                        "success": False,
                        "error": f"Critical step failed: {str(e)}",
                        "completed_steps": len(execution_results),
                        "results": execution_results
                    }
        
        return {
            "success": True,
            "task_id": task.id,
            "completed_steps": len(execution_results),
            "results": execution_results
        }
    
    async def _execute_vision_command(self, command: str) -> Dict[str, Any]:
        """
        Execute a vision-based command.
        
        Args:
            command: Vision command string
            
        Returns:
            Execution results
        """
        command = command.lower().strip()
        
        if "see" in command or "look" in command or "analyze" in command:
            # General screen analysis
            return await self.see()
        
        elif "find" in command:
            # Find element
            element = command.replace("find", "").strip()
            return await self.find_on_screen(element)
        
        elif "read" in command:
            # Read text
            return await self.read_screen()
        
        elif "suggest" in command or "what should" in command:
            # Get suggestion
            goal = command.replace("suggest", "").replace("what should i do", "").strip()
            return await self.suggest_action(goal)
        
        else:
            return {
                "success": False,
                "error": f"Unknown vision command: {command}"
            }
    
    # ==================== EXISTING METHODS (PRESERVED) ====================
    
    async def process_command(
        self,
        command: str,
        user_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a natural language command (legacy method).
        Now enhanced to use brain when appropriate.
        """
        if not self.initialized:
            return {"success": False, "error": "Agent not initialized"}
        
        if self.emergency_stop.check_stop():
            return {"success": False, "error": "Emergency stop is active"}
        
        # Check if this should use the brain (complex tasks)
        brain_keywords = ["automate", "do", "perform", "complete", "finish", "handle"]
        use_brain = any(kw in command.lower() for kw in brain_keywords)
        
        if use_brain and self.brain:
            logger.info("Using brain orchestrator for complex task")
            return await self.think_and_act(
                goal=command,
                priority="medium",
                use_vision=True
            )
        
        # Otherwise use traditional processing
        self.state = "processing"
        
        try:
            # Log command
            op_id = self.audit.start_operation(
                action_type=ActionType.AI_PLANNING,
                description=f"Process command: {command[:100]}",
                user_id=user_id,
                parameters={"command": command}
            )
            
            # Step 1: Analyze command
            analysis = await self.planner.analyze_command(command, user_id, context)
            
            # Step 2: Check for ambiguities
            if analysis.get("ambiguities") and len(analysis["ambiguities"]) > 0:
                self.audit.complete_operation(op_id, {"status": "needs_clarification"})
                self.state = "idle"
                return {
                    "success": False,
                    "requires_clarification": True,
                    "ambiguities": analysis["ambiguities"],
                    "questions": analysis.get("questions", []),
                    "message": "I need some clarification before proceeding."
                }
            
            # Step 3: Check permissions
            for capability in analysis.get("capabilities_required", []):
                category = self._map_capability_to_category(capability)
                if category:
                    permission = self.permission_guard.check_permission(
                        category=category,
                        user_id=user_id
                    )
                    
                    if permission.value == "deny":
                        self.audit.fail_operation(op_id, f"Permission denied for {capability}")
                        self.state = "idle"
                        return {
                            "success": False,
                            "error": f"Operation not permitted: {capability}"
                        }
            
            # Step 4: Create execution plan
            plan = await self.planner.create_plan(
                task=analysis.get("intent", command),
                user_id=user_id,
                context=context
            )
            
            self.audit.complete_operation(op_id, {"plan_id": plan.plan_id})
            
            # Step 5: Determine if approval is needed
            risk_level = analysis.get("risk_level", "medium")
            confirmation_level = analysis.get("confirmation_level", "standard")
            
            if risk_level in ["high", "critical"] or confirmation_level in ["critical", "emergency"]:
                self.state = "idle"
                return {
                    "success": True,
                    "requires_approval": True,
                    "plan": plan,
                    "risk_level": risk_level,
                    "message": f"This operation has {risk_level} risk and requires your approval."
                }
            
            # Auto-approve for low risk
            self.state = "idle"
            return {
                "success": True,
                "requires_approval": False,
                "plan": plan,
                "message": "Plan created and ready for execution."
            }
            
        except Exception as e:
            logger.error(f"Command processing error: {e}")
            self.state = "error"
            return {
                "success": False,
                "error": str(e)
            }
    
    async def execute_plan(
        self,
        plan_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Execute an approved plan (legacy method).
        """
        if not self.initialized:
            return {"success": False, "error": "Agent not initialized"}
        
        if self.emergency_stop.check_stop():
            return {"success": False, "error": "Emergency stop is active"}
        
        plan = self.planner.get_plan(plan_id)
        if not plan:
            return {"success": False, "error": f"Plan not found: {plan_id}"}
        
        self.state = "executing"
        
        # Log plan execution start
        exec_op_id = self.audit.start_operation(
            action_type=ActionType.AI_PLANNING,
            description=f"Execute plan: {plan.description}",
            user_id=user_id,
            parameters={"plan_id": plan_id, "steps": len(plan.steps)}
        )
        
        results = []
        failed_steps = []
        
        try:
            for step in plan.steps:
                # Check emergency stop
                if self.emergency_stop.check_stop():
                    self.planner.update_plan_status(plan_id, self.planner.PlanStatus.CANCELLED)
                    self.audit.fail_operation(exec_op_id, "Emergency stop triggered")
                    self.state = "paused"
                    return {
                        "success": False,
                        "error": "Emergency stop triggered",
                        "completed_steps": len(results),
                        "failed_steps": failed_steps
                    }
                
                # Check permissions for step
                category = self._map_tool_to_category(step.tool)
                if category:
                    permission = self.permission_guard.check_permission(
                        category=category,
                        command=step.command,
                        user_id=user_id
                    )
                    
                    if permission.value == "deny":
                        result = {
                            "step_number": step.step_number,
                            "success": False,
                            "error": f"Permission denied for {step.tool}"
                        }
                        results.append(result)
                        failed_steps.append(step.step_number)
                        continue
                
                # Request confirmation if needed
                if step.confirmation_level in ["standard", "critical"]:
                    confirmed = await self.confirmation_manager.request_confirmation(
                        action_description=f"Step {step.step_number}: {step.description}",
                        level=self._map_confirmation_level(step.confirmation_level),
                        details={"command": step.command, "tool": step.tool},
                        user_id=user_id
                    )
                    
                    if confirmed is None:
                        result = {
                            "step_number": step.step_number,
                            "success": False,
                            "error": "Confirmation timeout"
                        }
                        results.append(result)
                        failed_steps.append(step.step_number)
                        continue
                    elif confirmed is False:
                        result = {
                            "step_number": step.step_number,
                            "success": False,
                            "error": "Confirmation denied"
                        }
                        results.append(result)
                        failed_steps.append(step.step_number)
                        continue
                
                # Execute step
                step_result = await self._execute_step(step)
                results.append({
                    "step_number": step.step_number,
                    "success": step_result["success"],
                    "result": step_result
                })
                
                if not step_result["success"]:
                    failed_steps.append(step.step_number)
                    
                    # Check if we should continue or abort
                    if step_result.get("critical", False):
                        self.planner.update_plan_status(plan_id, self.planner.PlanStatus.FAILED)
                        self.audit.fail_operation(exec_op_id, f"Critical step {step.step_number} failed")
                        self.state = "idle"
                        return {
                            "success": False,
                            "error": f"Critical step {step.step_number} failed",
                            "completed_steps": len(results),
                            "failed_steps": failed_steps,
                            "results": results
                        }
                
                # Small delay between steps
                await asyncio.sleep(0.5)
            
            # Plan completed
            self.planner.update_plan_status(plan_id, self.planner.PlanStatus.COMPLETED)
            
            # Generate summary
            summary = self._generate_summary(plan, results)
            
            self.audit.complete_operation(exec_op_id, {
                "completed_steps": len(results),
                "failed_steps": len(failed_steps)
            })
            
            self.state = "idle"
            
            return {
                "success": len(failed_steps) == 0,
                "plan_id": plan_id,
                "completed_steps": len(results),
                "failed_steps": failed_steps,
                "summary": summary,
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Plan execution error: {e}")
            self.planner.update_plan_status(plan_id, self.planner.PlanStatus.FAILED)
            self.audit.fail_operation(exec_op_id, str(e))
            self.state = "error"
            return {
                "success": False,
                "error": str(e),
                "completed_steps": len(results),
                "failed_steps": failed_steps,
                "results": results
            }
    
    async def _execute_step(self, step: Any) -> Dict[str, Any]:
        """Execute a single plan step."""
        logger.info(f"Executing step {step.step_number}: {step.description}")
        
        try:
            if step.tool == "system":
                return await self.system_controller.execute_command(step.command)
            elif step.tool == "desktop":
                return await self._execute_desktop_command(step.command)
            elif step.tool == "browser":
                return await self._execute_browser_command(step.command)
            elif step.tool == "application":
                return await self._execute_application_command(step.command)
            else:
                return {
                    "success": False,
                    "error": f"Unknown tool: {step.tool}"
                }
        except Exception as e:
            logger.error(f"Step execution error: {e}")
            return {
                "success": False,
                "error": str(e),
                "critical": True
            }
    
    async def _execute_desktop_command(self, command: str) -> Dict[str, Any]:
        """Execute a desktop automation command."""
        import re
        
        command = command.lower().strip()
        
        if command.startswith("move mouse") or command.startswith("move to"):
            match = re.search(r'(\d+)[,\s]+(\d+)', command)
            if match:
                x, y = int(match.group(1)), int(match.group(2))
                return await self.desktop_controller.move_mouse(x, y)
        
        elif command.startswith("click"):
            match = re.search(r'(\d+)[,\s]+(\d+)', command)
            if match:
                x, y = int(match.group(1)), int(match.group(2))
                return await self.desktop_controller.click(x, y)
            else:
                return await self.desktop_controller.click()
        
        elif command.startswith("type"):
            text = command[4:].strip().strip('"\'')
            return await self.desktop_controller.type_text(text)
        
        elif command.startswith("press"):
            key = command[5:].strip()
            return await self.desktop_controller.press_key(key)
        
        elif command.startswith("screenshot"):
            return await self.desktop_controller.take_screenshot()
        
        else:
            return {
                "success": False,
                "error": f"Unknown desktop command: {command}"
            }
    
    async def _execute_browser_command(self, command: str) -> Dict[str, Any]:
        """Execute a browser automation command."""
        command = command.lower().strip()
        
        if command.startswith("navigate") or command.startswith("goto"):
            url = command.split()[-1]
            if not url.startswith("http"):
                url = "https://" + url
            return await self.browser_controller.navigate(url)
        
        elif command.startswith("click"):
            selector = command[5:].strip()
            return await self.browser_controller.click(selector)
        
        elif command.startswith("type"):
            parts = command[4:].strip().split(" ", 1)
            if len(parts) == 2:
                selector, text = parts
                return await self.browser_controller.type_text(selector, text)
            else:
                return {"success": False, "error": "Invalid type command format"}
        
        else:
            return {
                "success": False,
                "error": f"Unknown browser command: {command}"
            }
    
    async def _execute_application_command(self, command: str) -> Dict[str, Any]:
        """Execute an application management command."""
        command = command.lower().strip()
        
        if command.startswith("install"):
            package = command[7:].strip()
            return await self.application_controller.install_software(package)
        
        elif command.startswith("uninstall") or command.startswith("remove"):
            package = command[9:].strip() if command.startswith("uninstall") else command[6:].strip()
            return await self.application_controller.uninstall_software(package)
        
        elif command.startswith("update"):
            package = command[6:].strip()
            return await self.application_controller.update_software(package if package else None)
        
        else:
            return {
                "success": False,
                "error": f"Unknown application command: {command}"
            }
    
    async def ask_ai(self, question: str) -> str:
        """Ask the AI a question."""
        if not self.ollama:
            return "AI not initialized"
        
        try:
            response = await self.ollama.generate(
                prompt=question,
                temperature=0.7
            )
            return response.get("response", "No response")
        except Exception as e:
            logger.error(f"AI query error: {e}")
            return f"Error: {str(e)}"
    
    async def execute_system_command(
        self,
        command: str,
        user_id: str
    ) -> Dict[str, Any]:
        """Execute a direct system command."""
        if not self.system_controller:
            return {"success": False, "error": "System controller not initialized"}
        
        # Check permission
        permission = self.permission_guard.check_permission(
            category=OperationCategory.SYSTEM_COMMAND,
            command=command,
            user_id=user_id
        )
        
        if permission.value == "deny":
            return {"success": False, "error": "Permission denied"}
        
        # Request confirmation if needed
        if permission.value == "confirm":
            confirmed = await self.confirmation_manager.request_confirmation(
                action_description=f"Execute system command: {command[:50]}",
                level=self._map_confirmation_level("standard"),
                details={"command": command},
                user_id=user_id
            )
            
            if not confirmed:
                return {"success": False, "error": "Confirmation denied or timeout"}
        
        return await self.system_controller.execute_command(command)
    
    async def get_system_info(self) -> Dict[str, Any]:
        """Get system information."""
        if not self.system_controller:
            return {"success": False, "error": "System controller not initialized"}
        return await self.system_controller.get_system_info()
    
    async def take_screenshot(self) -> Dict[str, Any]:
        """Take a screenshot."""
        if not self.desktop_controller:
            return {"success": False, "error": "Desktop controller not initialized"}
        return await self.desktop_controller.take_screenshot()
    
    def get_status(self) -> Dict[str, Any]:
        """Get current agent status including vision and brain."""
        return {
            "initialized": self.initialized,
            "state": self.state,
            "healthy": self.initialized and self.state != "error",
            "safety_mode": settings.safety_mode,
            "emergency_stop": self.emergency_stop.check_stop() if self.emergency_stop else False,
            "active_plans": len(self.planner.active_plans) if self.planner else 0,
            "pending_confirmations": len(self.confirmation_manager.pending_confirmations) if self.confirmation_manager else 0,
            "session_operations": len(self.audit._current_operations) if self.audit else 0,
            # NEW: Vision and brain status
            "vision_enabled": self.vision_enabled,
            "vision_available": self.vision is not None,
            "brain_available": self.brain is not None,
            "brain_active_tasks": len(self.brain.active_tasks) if self.brain else 0
        }
    
    def _map_capability_to_category(self, capability: str) -> Optional[OperationCategory]:
        """Map capability string to operation category."""
        mapping = {
            "system": OperationCategory.SYSTEM_COMMAND,
            "desktop": OperationCategory.DESKTOP_CONTROL,
            "browser": OperationCategory.BROWSER_NAVIGATE,
            "application": OperationCategory.SOFTWARE_INSTALL,
            "vision": OperationCategory.DESKTOP_CONTROL
        }
        return mapping.get(capability)
    
    def _map_tool_to_category(self, tool: str) -> Optional[OperationCategory]:
        """Map tool string to operation category."""
        mapping = {
            "system": OperationCategory.SYSTEM_COMMAND,
            "desktop": OperationCategory.DESKTOP_CONTROL,
            "browser": OperationCategory.BROWSER_NAVIGATE,
            "application": OperationCategory.SOFTWARE_INSTALL,
            "vision": OperationCategory.DESKTOP_CONTROL
        }
        return mapping.get(tool)
    
    def _map_confirmation_level(self, level: str) -> Any:
        """Map string confirmation level to enum."""
        from safety.confirmation_manager import ConfirmationLevel
        mapping = {
            "none": ConfirmationLevel.NONE,
            "info": ConfirmationLevel.INFO,
            "standard": ConfirmationLevel.STANDARD,
            "critical": ConfirmationLevel.CRITICAL,
            "emergency": ConfirmationLevel.EMERGENCY
        }
        return mapping.get(level, ConfirmationLevel.STANDARD)
    
    def _generate_summary(self, plan: ExecutionPlan, results: List[Dict]) -> str:
        """Generate execution summary."""
        successful = sum(1 for r in results if r["success"])
        total = len(results)
        
        lines = [
            f"Plan: {plan.description}",
            f"Result: {successful}/{total} steps successful",
            ""
        ]
        
        for result in results:
            status = "✅" if result["success"] else "❌"
            step_result = result.get("result", {})
            detail = step_result.get("stdout", step_result.get("error", "No details"))[:100]
            lines.append(f"{status} Step {result['step_number']}: {detail}")
        
        return "\n".join(lines)
