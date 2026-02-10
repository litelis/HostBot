"""Command handler for processing natural language commands."""

import asyncio
import re
from typing import Any, Dict, List, Optional

from loguru import logger

from cognitive.planner import get_planner, ExecutionPlan
from core.agent import Agent


class CommandHandler:
    """Handles natural language commands and orchestrates execution."""
    
    def __init__(self, agent: Agent):
        self.agent = agent
        self.planner = get_planner()
        
        logger.info("Command handler initialized")
    
    async def process_command(
        self,
        command: str,
        user_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a natural language command.
        
        Args:
            command: Natural language command
            user_id: ID of the user issuing the command
            context: Optional context information
            
        Returns:
            Processing result with plan and status
        """
        logger.info(f"Processing command from {user_id}: {command[:100]}...")
        
        try:
            # Step 1: Analyze command for intent and ambiguities
            analysis = await self.planner.analyze_command(command, user_id, context)
            
            # Step 2: Check for ambiguities
            if analysis.get("ambiguities") and len(analysis["ambiguities"]) > 0:
                # Need clarification
                return {
                    "success": False,
                    "requires_clarification": True,
                    "ambiguities": analysis["ambiguities"],
                    "questions": analysis.get("questions", []),
                    "assumed_interpretation": analysis.get("assumed_interpretation"),
                    "analysis": analysis
                }
            
            # Step 3: Check if we can proceed
            if not analysis.get("can_proceed", True):
                return {
                    "success": False,
                    "error": "Command analysis indicates cannot proceed",
                    "reasoning": analysis.get("reasoning", "Unknown reason"),
                    "analysis": analysis
                }
            
            # Step 4: Create execution plan
            plan = await self.planner.create_plan(
                task=analysis.get("intent", command),
                user_id=user_id,
                context=context
            )
            
            # Step 5: Return plan for approval
            return {
                "success": True,
                "requires_approval": True,
                "plan": plan,
                "analysis": analysis,
                "risk_level": analysis.get("risk_level", "unknown"),
                "confirmation_level": analysis.get("confirmation_level", "standard")
            }
            
        except Exception as e:
            logger.error(f"Command processing error: {e}")
            return {
                "success": False,
                "error": str(e),
                "command": command
            }
    
    async def execute_plan(
        self,
        plan_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Execute an approved plan.
        
        Args:
            plan_id: ID of the plan to execute
            user_id: ID of the user who approved
            
        Returns:
            Execution results
        """
        plan = self.planner.get_plan(plan_id)
        if not plan:
            return {
                "success": False,
                "error": f"Plan not found: {plan_id}"
            }
        
        logger.info(f"Executing plan {plan_id} for user {user_id}")
        
        # Update plan status
        self.planner.update_plan_status(plan_id, self.planner.PlanStatus.IN_PROGRESS)
        
        results = []
        failed_steps = []
        
        try:
            for step in plan.steps:
                # Check emergency stop
                if self.agent.emergency_stop.check_stop():
                    logger.warning(f"Plan {plan_id} halted due to emergency stop")
                    self.planner.update_plan_status(plan_id, self.planner.PlanStatus.CANCELLED)
                    return {
                        "success": False,
                        "error": "Emergency stop triggered",
                        "completed_steps": len(results),
                        "failed_steps": failed_steps
                    }
                
                # Execute step
                step_result = await self._execute_step(step, user_id)
                results.append(step_result)
                
                if not step_result["success"]:
                    failed_steps.append(step.step_number)
                    
                    # Check if we should continue or abort
                    if step_result.get("critical", False):
                        self.planner.update_plan_status(plan_id, self.planner.PlanStatus.FAILED)
                        return {
                            "success": False,
                            "error": f"Critical step {step.step_number} failed",
                            "step_result": step_result,
                            "completed_steps": len(results),
                            "failed_steps": failed_steps
                        }
                
                # Small delay between steps
                await asyncio.sleep(0.5)
            
            # Plan completed
            self.planner.update_plan_status(plan_id, self.planner.PlanStatus.COMPLETED)
            
            # Self-evaluation
            summary = self._generate_execution_summary(plan, results)
            evaluation = await self.planner.evaluate_completion(plan, summary)
            
            return {
                "success": True,
                "plan_id": plan_id,
                "completed_steps": len(results),
                "failed_steps": failed_steps,
                "results": results,
                "evaluation": evaluation
            }
            
        except Exception as e:
            logger.error(f"Plan execution error: {e}")
            self.planner.update_plan_status(plan_id, self.planner.PlanStatus.FAILED)
            return {
                "success": False,
                "error": str(e),
                "completed_steps": len(results),
                "failed_steps": failed_steps
            }
    
    async def _execute_step(
        self,
        step: Any,
        user_id: str
    ) -> Dict[str, Any]:
        """Execute a single plan step."""
        logger.info(f"Executing step {step.step_number}: {step.description}")
        
        # Update step status
        self.planner.update_step_status(
            step.plan_id if hasattr(step, 'plan_id') else 'unknown',
            step.step_number,
            self.planner.StepStatus.IN_PROGRESS
        )
        
        try:
            # Route to appropriate controller based on tool
            if step.tool == "system":
                result = await self.agent.system_controller.execute_command(step.command)
            elif step.tool == "desktop":
                result = await self._execute_desktop_action(step.command)
            elif step.tool == "browser":
                result = await self._execute_browser_action(step.command)
            elif step.tool == "application":
                result = await self._execute_application_action(step.command)
            else:
                result = {
                    "success": False,
                    "error": f"Unknown tool: {step.tool}"
                }
            
            # Evaluate result
            evaluation = await self.planner.evaluate_step_execution(
                step=step,
                execution_result=result
            )
            
            # Update step status based on result
            if result["success"]:
                self.planner.update_step_status(
                    step.plan_id if hasattr(step, 'plan_id') else 'unknown',
                    step.step_number,
                    self.planner.StepStatus.COMPLETED,
                    result=result
                )
            else:
                self.planner.update_step_status(
                    step.plan_id if hasattr(step, 'plan_id') else 'unknown',
                    step.step_number,
                    self.planner.StepStatus.FAILED,
                    result=result,
                    error_message=result.get("error", "Unknown error")
                )
            
            return {
                "step_number": step.step_number,
                "success": result["success"],
                "result": result,
                "evaluation": evaluation
            }
            
        except Exception as e:
            logger.error(f"Step execution error: {e}")
            self.planner.update_step_status(
                step.plan_id if hasattr(step, 'plan_id') else 'unknown',
                step.step_number,
                self.planner.StepStatus.FAILED,
                error_message=str(e)
            )
            return {
                "step_number": step.step_number,
                "success": False,
                "error": str(e),
                "critical": True
            }
    
    async def _execute_desktop_action(self, command: str) -> Dict[str, Any]:
        """Execute a desktop automation action."""
        # Parse command and route to appropriate method
        command = command.lower().strip()
        
        if command.startswith("move mouse") or command.startswith("move to"):
            # Extract coordinates
            match = re.search(r'(\d+)[,\s]+(\d+)', command)
            if match:
                x, y = int(match.group(1)), int(match.group(2))
                return await self.agent.desktop_controller.move_mouse(x, y)
        
        elif command.startswith("click"):
            # Check for coordinates
            match = re.search(r'(\d+)[,\s]+(\d+)', command)
            if match:
                x, y = int(match.group(1)), int(match.group(2))
                return await self.agent.desktop_controller.click(x, y)
            else:
                return await self.agent.desktop_controller.click()
        
        elif command.startswith("type"):
            text = command[4:].strip().strip('"\'')
            return await self.agent.desktop_controller.type_text(text)
        
        elif command.startswith("press"):
            key = command[5:].strip()
            return await self.agent.desktop_controller.press_key(key)
        
        elif command.startswith("screenshot"):
            return await self.agent.desktop_controller.take_screenshot()
        
        else:
            return {
                "success": False,
                "error": f"Unknown desktop command: {command}"
            }
    
    async def _execute_browser_action(self, command: str) -> Dict[str, Any]:
        """Execute a browser automation action."""
        command = command.lower().strip()
        
        if command.startswith("navigate") or command.startswith("goto"):
            url = command.split()[-1]
            if not url.startswith("http"):
                url = "https://" + url
            return await self.agent.browser_controller.navigate(url)
        
        elif command.startswith("click"):
            selector = command[5:].strip()
            return await self.agent.browser_controller.click(selector)
        
        elif command.startswith("type"):
            parts = command[4:].strip().split(" ", 1)
            if len(parts) == 2:
                selector, text = parts
                return await self.agent.browser_controller.type_text(selector, text)
            else:
                return {"success": False, "error": "Invalid type command format"}
        
        else:
            return {
                "success": False,
                "error": f"Unknown browser command: {command}"
            }
    
    async def _execute_application_action(self, command: str) -> Dict[str, Any]:
        """Execute an application management action."""
        command = command.lower().strip()
        
        if command.startswith("install"):
            package = command[7:].strip()
            return await self.agent.application_controller.install_software(package)
        
        elif command.startswith("uninstall") or command.startswith("remove"):
            package = command[9:].strip() if command.startswith("uninstall") else command[6:].strip()
            return await self.agent.application_controller.uninstall_software(package)
        
        elif command.startswith("update"):
            package = command[6:].strip()
            return await self.agent.application_controller.update_software(package if package else None)
        
        else:
            return {
                "success": False,
                "error": f"Unknown application command: {command}"
            }
    
    def _generate_execution_summary(self, plan: ExecutionPlan, results: List[Dict]) -> str:
        """Generate a summary of plan execution."""
        successful = sum(1 for r in results if r["success"])
        total = len(results)
        
        lines = [
            f"Plan: {plan.description}",
            f"Steps: {successful}/{total} successful",
            ""
        ]
        
        for result in results:
            status = "✅" if result["success"] else "❌"
            lines.append(f"{status} Step {result['step_number']}: {result.get('result', {}).get('stdout', result.get('error', 'No details'))[:100]}")
        
        return "\n".join(lines)
    
    def parse_command_intent(self, command: str) -> Dict[str, Any]:
        """Parse a command to determine intent."""
        command_lower = command.lower()
        
        # System commands
        if any(kw in command_lower for kw in ["run", "execute", "command", "cmd", "powershell", "bash"]):
            return {"intent": "system", "confidence": "high"}
        
        # Desktop commands
        if any(kw in command_lower for kw in ["click", "type", "mouse", "keyboard", "screenshot", "screen"]):
            return {"intent": "desktop", "confidence": "high"}
        
        # Browser commands
        if any(kw in command_lower for kw in ["browse", "navigate", "website", "url", "web", "click.*link", "fill.*form"]):
            return {"intent": "browser", "confidence": "high"}
        
        # Application commands
        if any(kw in command_lower for kw in ["install", "uninstall", "software", "program", "app", "package"]):
            return {"intent": "application", "confidence": "high"}
        
        # Information commands
        if any(kw in command_lower for kw in ["show", "list", "get", "check", "status", "info"]):
            return {"intent": "information", "confidence": "medium"}
        
        return {"intent": "general", "confidence": "low"}
