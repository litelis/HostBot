"""
Visual analyzer for HostBot.
Uses AI vision models to understand screen content and provide actionable insights.
"""

import json
from typing import Dict, List, Optional, Any

from loguru import logger

from cognitive.ollama_client import get_ollama_client


class VisualAnalyzer:
    """
    Analyzes screenshots using AI vision models.
    Can detect UI elements, text, and provide context for decision making.
    """
    
    def __init__(self):
        """Initialize visual analyzer."""
        self.ollama = get_ollama_client()
        self.analysis_history = []
        
        logger.info("VisualAnalyzer initialized")
    
    async def analyze_screen(
        self,
        screenshot_base64: str,
        query: str = "What do you see on this screen? Describe the main elements.",
        context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Analyze a screenshot using AI vision capabilities.
        
        Args:
            screenshot_base64: Base64 encoded screenshot
            query: Specific question about the screen
            context: Additional context (current task, previous actions, etc.)
            
        Returns:
            Analysis results with detected elements and recommendations
        """
        try:
            # Build comprehensive prompt for vision analysis
            system_prompt = """You are a computer vision assistant analyzing a screenshot.
Describe what you see in detail, including:
1. The main application or window visible
2. UI elements (buttons, text fields, menus, etc.)
3. Text content that is readable
4. Current state (loading, error, ready, etc.)
5. Any popups, notifications, or dialogs

Provide your analysis in a structured format that can be used for automation."""

            # Add context if provided
            context_str = ""
            if context:
                context_str = f"\n\nContext:\n- Current task: {context.get('task', 'Unknown')}\n"
                context_str += f"- Previous action: {context.get('previous_action', 'None')}\n"
                context_str += f"- Goal: {context.get('goal', 'Complete the task')}\n"
            
            full_prompt = f"{system_prompt}\n\n{query}{context_str}"
            
            # Call Ollama with vision capabilities
            # Note: This requires a vision-capable model like llava
            response = await self.ollama.generate(
                prompt=full_prompt,
                images=[screenshot_base64],  # Send image to model
                temperature=0.3,  # Lower temperature for more consistent analysis
                format="json"  # Request structured output if supported
            )
            
            analysis_text = response.get("response", "")
            
            # Parse the response
            analysis = self._parse_analysis(analysis_text)
            
            # Store in history
            self.analysis_history.append({
                "query": query,
                "analysis": analysis,
                "raw_response": analysis_text
            })
            
            # Keep history manageable
            if len(self.analysis_history) > 50:
                self.analysis_history = self.analysis_history[-50:]
            
            return {
                "success": True,
                "analysis": analysis,
                "raw_text": analysis_text,
                "timestamp": logger.time()
            }
            
        except Exception as e:
            logger.error(f"Visual analysis failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "analysis": None
            }
    
    async def find_element(
        self,
        screenshot_base64: str,
        element_description: str
    ) -> Dict[str, Any]:
        """
        Find a specific UI element on the screen.
        
        Args:
            screenshot_base64: Base64 encoded screenshot
            element_description: Description of element to find (e.g., "Submit button", "Username field")
            
        Returns:
            Coordinates and details of the element if found
        """
        query = f"""Find the element described as: "{element_description}"

Return a JSON object with:
- found: boolean
- element_type: string (button, input, link, text, image, etc.)
- location: object with x, y coordinates (center of element)
- size: object with width, height
- confidence: number 0-1
- alternative_text: string (any text labels on the element)

Be precise with coordinates. If not found, set found to false."""
        
        result = await self.analyze_screen(screenshot_base64, query)
        
        if result["success"]:
            # Try to extract coordinates from analysis
            analysis = result["analysis"]
            if isinstance(analysis, dict) and analysis.get("found"):
                return {
                    "success": True,
                    "found": True,
                    "coordinates": analysis.get("location", {}),
                    "size": analysis.get("size", {}),
                    "confidence": analysis.get("confidence", 0.5),
                    "element_type": analysis.get("element_type", "unknown")
                }
        
        return {
            "success": result["success"],
            "found": False,
            "error": result.get("error", "Element not found"),
            "coordinates": None
        }
    
    async def read_text(
        self,
        screenshot_base64: str,
        region: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Read text from the screen (OCR-like functionality via AI).
        
        Args:
            screenshot_base64: Base64 encoded screenshot
            region: Optional region to focus on {x, y, width, height}
            
        Returns:
            Extracted text with locations
        """
        query = "Read all visible text on this screen. Return as a list of text elements with their approximate locations."
        
        if region:
            query += f"\nFocus on region: x={region['x']}, y={region['y']}, w={region['width']}, h={region['height']}"
        
        result = await self.analyze_screen(screenshot_base64, query)
        
        if result["success"]:
            analysis = result["analysis"]
            text_elements = []
            
            # Extract text elements from analysis
            if isinstance(analysis, dict):
                texts = analysis.get("texts", analysis.get("text_elements", []))
                for text in texts:
                    text_elements.append({
                        "text": text.get("content", text) if isinstance(text, dict) else text,
                        "location": text.get("location", {}) if isinstance(text, dict) else {},
                        "confidence": text.get("confidence", 0.8) if isinstance(text, dict) else 0.8
                    })
            
            return {
                "success": True,
                "text_elements": text_elements,
                "full_text": " ".join([t["text"] for t in text_elements])
            }
        
        return {
            "success": False,
            "error": result.get("error", "Failed to read text")
        }
    
    async def detect_state(
        self,
        screenshot_base64: str
    ) -> Dict[str, Any]:
        """
        Detect the current state of the system (loading, error, ready, etc.).
        
        Args:
            screenshot_base64: Base64 encoded screenshot
            
        Returns:
            Detected state information
        """
        query = """Analyze the current state of the system. Is it:
- Loading/processing?
- Showing an error?
- Ready for input?
- Waiting for user action?
- In a specific application state?

Return state as: {state: string, confidence: number, details: string}"""
        
        result = await self.analyze_screen(screenshot_base64, query)
        
        if result["success"]:
            analysis = result["analysis"]
            if isinstance(analysis, dict):
                return {
                    "success": True,
                    "state": analysis.get("state", "unknown"),
                    "confidence": analysis.get("confidence", 0.5),
                    "details": analysis.get("details", "No details provided")
                }
        
        return {
            "success": False,
            "state": "unknown",
            "error": result.get("error", "State detection failed")
        }
    
    async def suggest_action(
        self,
        screenshot_base64: str,
        goal: str,
        current_step: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Suggest the next action based on current screen and goal.
        
        Args:
            screenshot_base64: Base64 encoded screenshot
            goal: The overall goal to achieve
            current_step: Current step in the process
            
        Returns:
            Suggested action with reasoning
        """
        query = f"""Given the goal: "{goal}"
{current_step and f'Current step: {current_step}' or ''}

What should be the next action? Suggest:
1. Action type (click, type, wait, scroll, etc.)
2. Target element (describe it)
3. Specific details (coordinates if possible, text to type, etc.)
4. Expected outcome

Return as structured data for automation."""
        
        result = await self.analyze_screen(screenshot_base64, query)
        
        if result["success"]:
            analysis = result["analysis"]
            return {
                "success": True,
                "suggestion": analysis,
                "action_type": analysis.get("action_type", "unknown") if isinstance(analysis, dict) else "unknown",
                "target": analysis.get("target", {}) if isinstance(analysis, dict) else {},
                "reasoning": analysis.get("reasoning", "No reasoning provided") if isinstance(analysis, dict) else "No reasoning"
            }
        
        return {
            "success": False,
            "error": result.get("error", "Failed to suggest action")
        }
    
    def _parse_analysis(self, text: str) -> Any:
        """
        Parse analysis text, attempting to extract JSON if present.
        
        Args:
            text: Raw analysis text from model
            
        Returns:
            Parsed analysis (dict if JSON found, else raw text)
        """
        # Try to find JSON in the response
        try:
            # Look for JSON block
            if "```json" in text:
                json_start = text.find("```json") + 7
                json_end = text.find("```", json_start)
                json_str = text[json_start:json_end].strip()
                return json.loads(json_str)
            elif "```" in text:
                json_start = text.find("```") + 3
                json_end = text.find("```", json_start)
                json_str = text[json_start:json_end].strip()
                return json.loads(json_str)
            else:
                # Try to parse entire response as JSON
                return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            # Return as structured text if JSON parsing fails
            return {
                "description": text,
                "parsed": False
            }
    
    def get_history(self, limit: int = 10) -> List[Dict]:
        """
        Get recent analysis history.
        
        Args:
            limit: Number of recent analyses to return
            
        Returns:
            List of recent analyses
        """
        return self.analysis_history[-limit:]


# Global visual analyzer instance
_visual_analyzer: Optional[VisualAnalyzer] = None


def get_visual_analyzer() -> VisualAnalyzer:
    """Get or create global visual analyzer instance."""
    global _visual_analyzer
    if _visual_analyzer is None:
        _visual_analyzer = VisualAnalyzer()
    return _visual_analyzer
