"""
Vision orchestrator for HostBot.
Coordinates screen capture with AI analysis and provides actionable insights to the main agent.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any

from loguru import logger

from .screen_capture import get_screen_capture, ScreenCapture
from .visual_analyzer import get_visual_analyzer, VisualAnalyzer


@dataclass
class VisionContext:
    """Context for vision-based decision making."""
    screenshot_data: Dict[str, Any]
    analysis: Dict[str, Any]
    timestamp: datetime
    task: Optional[str] = None
    previous_actions: List[str] = None


class VisionOrchestrator:
    """
    Orchestrates the vision pipeline: capture → analyze → decide → act.
    Acts as the "eyes" of the HostBot agent.
    """
    
    def __init__(self):
        """Initialize vision orchestrator."""
        self.screen_capture = get_screen_capture()
        self.visual_analyzer = get_visual_analyzer()
        
        # Configuration
        self.auto_save_screenshots = False
        self.analysis_cooldown = 2.0  # Seconds between analyses
        self.last_analysis_time = 0
        
        # State
        self.current_context: Optional[VisionContext] = None
        self.context_history: List[VisionContext] = []
        self.max_history = 20
        
        # Callbacks for integration with main agent
        self.on_analysis_complete: Optional[Callable] = None
        self.on_action_suggested: Optional[Callable] = None
        
        logger.info("VisionOrchestrator initialized")
    
    async def see_and_analyze(
        self,
        task: Optional[str] = None,
        region: Optional[Dict] = None,
        save_screenshot: bool = False
    ) -> Dict[str, Any]:
        """
        Main method: capture screen and analyze it.
        
        Args:
            task: Current task context for better analysis
            region: Optional specific region to capture
            save_screenshot: Whether to save screenshot to disk
            
        Returns:
            Complete analysis results
        """
        try:
            # Step 1: Capture screen
            logger.info("Capturing screen for analysis...")
            
            if region:
                capture_result = self.screen_capture.capture_region(
                    region["x"], region["y"],
                    region["width"], region["height"],
                    save=save_screenshot
                )
            else:
                capture_result = self.screen_capture.capture_full_screen(save=save_screenshot)
            
            if not capture_result["success"]:
                logger.error(f"Screen capture failed: {capture_result.get('error')}")
                return {
                    "success": False,
                    "error": capture_result.get("error", "Screen capture failed"),
                    "stage": "capture"
                }
            
            # Step 2: Analyze with AI
            logger.info("Analyzing screen content...")
            
            context = {
                "task": task or "General screen analysis",
                "previous_action": self._get_last_action(),
                "goal": task
            }
            
            analysis_result = await self.visual_analyzer.analyze_screen(
                screenshot_base64=capture_result["base64"],
                query=f"What do you see? I'm trying to: {task}" if task else "What do you see on this screen?",
                context=context
            )
            
            if not analysis_result["success"]:
                logger.error(f"Visual analysis failed: {analysis_result.get('error')}")
                return {
                    "success": False,
                    "error": analysis_result.get("error", "Analysis failed"),
                    "stage": "analysis",
                    "screenshot": capture_result
                }
            
            # Step 3: Create vision context
            vision_context = VisionContext(
                screenshot_data=capture_result,
                analysis=analysis_result,
                timestamp=datetime.now(),
                task=task,
                previous_actions=self._get_recent_actions(5)
            )
            
            self.current_context = vision_context
            self.context_history.append(vision_context)
            
            # Trim history
            if len(self.context_history) > self.max_history:
                self.context_history = self.context_history[-self.max_history:]
            
            # Step 4: Notify callbacks
            if self.on_analysis_complete:
                try:
                    await self.on_analysis_complete(vision_context)
                except Exception as e:
                    logger.error(f"Analysis callback error: {e}")
            
            logger.info("Vision analysis complete")
            
            return {
                "success": True,
                "context": vision_context,
                "screenshot": capture_result,
                "analysis": analysis_result,
                "summary": self._generate_summary(vision_context)
            }
            
        except Exception as e:
            logger.error(f"Vision orchestration failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "stage": "unknown"
            }
    
    async def find_and_click(
        self,
        element_description: str,
        task: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Find an element on screen and return its coordinates for clicking.
        
        Args:
            element_description: Description of element to find
            task: Current task context
            
        Returns:
            Click coordinates and success status
        """
        # First, see and analyze
        vision_result = await self.see_and_analyze(task=task)
        
        if not vision_result["success"]:
            return vision_result
        
        # Find the specific element
        screenshot_base64 = vision_result["screenshot"]["base64"]
        
        find_result = await self.visual_analyzer.find_element(
            screenshot_base64=screenshot_base64,
            element_description=element_description
        )
        
        if find_result["success"] and find_result["found"]:
            coords = find_result["coordinates"]
            return {
                "success": True,
                "found": True,
                "x": coords.get("x", 0),
                "y": coords.get("y", 0),
                "confidence": find_result["confidence"],
                "element_type": find_result["element_type"],
                "vision_context": vision_result
            }
        
        return {
            "success": False,
            "found": False,
            "error": f"Element not found: {element_description}",
            "vision_context": vision_result
        }
    
    async def read_screen_text(
        self,
        region: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Read all text visible on screen.
        
        Args:
            region: Optional region to focus on
            
        Returns:
            Extracted text elements
        """
        # Capture specific region or full screen
        if region:
            capture_result = self.screen_capture.capture_region(
                region["x"], region["y"],
                region["width"], region["height"]
            )
        else:
            capture_result = self.screen_capture.capture_full_screen()
        
        if not capture_result["success"]:
            return capture_result
        
        # Read text from screenshot
        text_result = await self.visual_analyzer.read_text(
            screenshot_base64=capture_result["base64"],
            region=region
        )
        
        return {
            "success": text_result["success"],
            "text_elements": text_result.get("text_elements", []),
            "full_text": text_result.get("full_text", ""),
            "screenshot": capture_result
        }
    
    async def suggest_next_action(
        self,
        goal: str,
        current_step: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get AI suggestion for next action based on current screen.
        
        Args:
            goal: Overall goal to achieve
            current_step: Description of current step
            
        Returns:
            Suggested action with details
        """
        # Capture and analyze current state
        vision_result = await self.see_and_analyze(task=goal)
        
        if not vision_result["success"]:
            return {
                "success": False,
                "error": vision_result.get("error", "Failed to analyze screen"),
                "suggestion": None
            }
        
        # Get action suggestion
        screenshot_base64 = vision_result["screenshot"]["base64"]
        
        suggestion_result = await self.visual_analyzer.suggest_action(
            screenshot_base64=screenshot_base64,
            goal=goal,
            current_step=current_step
        )
        
        # Notify callback
        if self.on_action_suggested and suggestion_result["success"]:
            try:
                await self.on_action_suggested(suggestion_result)
            except Exception as e:
                logger.error(f"Action suggestion callback error: {e}")
        
        return {
            "success": suggestion_result["success"],
            "suggestion": suggestion_result.get("suggestion"),
            "action_type": suggestion_result.get("action_type"),
            "target": suggestion_result.get("target"),
            "reasoning": suggestion_result.get("reasoning"),
            "vision_context": vision_result
        }
    
    async def wait_for_state(
        self,
        target_state: str,
        timeout: float = 30.0,
        check_interval: float = 2.0
    ) -> Dict[str, Any]:
        """
        Wait for screen to reach a specific state.
        
        Args:
            target_state: State to wait for (e.g., "loading complete", "ready")
            timeout: Maximum time to wait in seconds
            check_interval: Time between checks in seconds
            
        Returns:
            Result of state detection
        """
        start_time = asyncio.get_event_loop().time()
        
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            # Capture and check state
            vision_result = await self.see_and_analyze()
            
            if not vision_result["success"]:
                await asyncio.sleep(check_interval)
                continue
            
            # Check if target state is reached
            analysis = vision_result["analysis"]["analysis"]
            state_info = await self.visual_analyzer.detect_state(
                vision_result["screenshot"]["base64"]
            )
            
            if state_info["success"]:
                current_state = state_info["state"].lower()
                if target_state.lower() in current_state:
                    return {
                        "success": True,
                        "state_reached": True,
                        "state": current_state,
                        "waited": asyncio.get_event_loop().time() - start_time,
                        "vision_context": vision_result
                    }
            
            await asyncio.sleep(check_interval)
        
        return {
            "success": False,
            "state_reached": False,
            "error": f"Timeout waiting for state: {target_state}",
            "waited": timeout
        }
    
    def get_current_view(self) -> Optional[VisionContext]:
        """Get the current vision context."""
        return self.current_context
    
    def get_history(self, limit: int = 10) -> List[VisionContext]:
        """Get recent vision context history."""
        return self.context_history[-limit:]
    
    def _get_last_action(self) -> str:
        """Get the most recent action from history."""
        if self.context_history:
            last = self.context_history[-1]
            if last.previous_actions:
                return last.previous_actions[-1]
        return "None"
    
    def _get_recent_actions(self, count: int = 5) -> List[str]:
        """Get recent actions from history."""
        actions = []
        for ctx in reversed(self.context_history[-count:]):
            if ctx.previous_actions:
                actions.extend(ctx.previous_actions)
        return actions[-count:]
    
    def _generate_summary(self, context: VisionContext) -> str:
        """Generate human-readable summary of vision context."""
        analysis = context.analysis.get("analysis", {})
        
        if isinstance(analysis, dict):
            desc = analysis.get("description", "No description available")
        else:
            desc = str(analysis)
        
        lines = [
            f"Task: {context.task or 'None'}",
            f"Screen: {context.screenshot_data.get('width', 0)}x{context.screenshot_data.get('height', 0)}",
            f"Analysis: {desc[:200]}..." if len(desc) > 200 else f"Analysis: {desc}",
            f"Timestamp: {context.timestamp.strftime('%H:%M:%S')}"
        ]
        
        return "\n".join(lines)


# Global vision orchestrator instance
_vision_orchestrator: Optional[VisionOrchestrator] = None


def get_vision_orchestrator() -> VisionOrchestrator:
    """Get or create global vision orchestrator instance."""
    global _vision_orchestrator
    if _vision_orchestrator is None:
        _vision_orchestrator = VisionOrchestrator()
    return _vision_orchestrator
