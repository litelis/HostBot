"""Desktop controller for mouse and keyboard automation."""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import pyautogui
from loguru import logger
from PIL import Image

from safety.audit_logger import get_audit_logger, ActionType
from safety.emergency_stop import get_emergency_stop


@dataclass
class Point:
    """2D point coordinates."""
    x: int
    y: int


@dataclass
class Region:
    """Screen region."""
    x: int
    y: int
    width: int
    height: int


class DesktopController:
    """Controller for desktop automation (mouse and keyboard)."""
    
    def __init__(self):
        self.audit = get_audit_logger()
        self.emergency = get_emergency_stop()
        
        # Configure pyautogui
        pyautogui.FAILSAFE = True  # Move mouse to corner to abort
        pyautogui.PAUSE = 0.1  # Brief pause between actions
        
        # Get screen size
        self.screen_size = pyautogui.size()
        
        logger.info(f"Desktop controller initialized (screen: {self.screen_size})")
    
    def _check_emergency(self) -> bool:
        """Check if emergency stop is active."""
        if self.emergency.check_stop():
            logger.warning("Desktop action blocked - emergency stop active")
            return True
        return False
    
    async def move_mouse(
        self,
        x: int,
        y: int,
        duration: float = 0.5
    ) -> Dict[str, Any]:
        """
        Move mouse to coordinates.
        
        Args:
            x: X coordinate
            y: Y coordinate
            duration: Movement duration in seconds
            
        Returns:
            Success status and coordinates
        """
        if self._check_emergency():
            return {"success": False, "error": "Emergency stop active", "x": x, "y": y}
        
        op_id = self.audit.start_operation(
            action_type=ActionType.DESKTOP_CONTROL,
            description=f"Move mouse to ({x}, {y})",
            parameters={"x": x, "y": y, "duration": duration}
        )
        
        try:
            # Validate coordinates
            if x < 0 or x > self.screen_size.width or y < 0 or y > self.screen_size.height:
                raise ValueError(f"Coordinates ({x}, {y}) out of screen bounds ({self.screen_size})")
            
            # Move mouse
            pyautogui.moveTo(x, y, duration=duration)
            
            result = {
                "success": True,
                "x": x,
                "y": y,
                "duration": duration
            }
            
            self.audit.complete_operation(op_id, result)
            logger.info(f"Mouse moved to ({x}, {y})")
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            self.audit.fail_operation(op_id, error_msg)
            logger.error(f"Mouse move error: {error_msg}")
            
            return {
                "success": False,
                "error": error_msg,
                "x": x,
                "y": y
            }
    
    async def click(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
        button: str = "left",
        clicks: int = 1
    ) -> Dict[str, Any]:
        """
        Click mouse button.
        
        Args:
            x: X coordinate (None for current position)
            y: Y coordinate (None for current position)
            button: Button to click (left, right, middle)
            clicks: Number of clicks
            
        Returns:
            Success status
        """
        if self._check_emergency():
            return {"success": False, "error": "Emergency stop active"}
        
        current_pos = pyautogui.position()
        target_x = x if x is not None else current_pos.x
        target_y = y if y is not None else current_pos.y
        
        op_id = self.audit.start_operation(
            action_type=ActionType.DESKTOP_CONTROL,
            description=f"Click {button} button at ({target_x}, {target_y})",
            parameters={"x": target_x, "y": target_y, "button": button, "clicks": clicks}
        )
        
        try:
            # Move to position if specified
            if x is not None and y is not None:
                pyautogui.moveTo(x, y)
            
            # Perform click
            pyautogui.click(button=button, clicks=clicks)
            
            result = {
                "success": True,
                "x": target_x,
                "y": target_y,
                "button": button,
                "clicks": clicks
            }
            
            self.audit.complete_operation(op_id, result)
            logger.info(f"Clicked {button} at ({target_x}, {target_y})")
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            self.audit.fail_operation(op_id, error_msg)
            logger.error(f"Click error: {error_msg}")
            
            return {
                "success": False,
                "error": error_msg
            }
    
    async def scroll(
        self,
        amount: int,
        x: Optional[int] = None,
        y: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Scroll mouse wheel.
        
        Args:
            amount: Scroll amount (positive up, negative down)
            x: X coordinate (None for current position)
            y: Y coordinate (None for current position)
            
        Returns:
            Success status
        """
        if self._check_emergency():
            return {"success": False, "error": "Emergency stop active"}
        
        current_pos = pyautogui.position()
        target_x = x if x is not None else current_pos.x
        target_y = y if y is not None else current_pos.y
        
        op_id = self.audit.start_operation(
            action_type=ActionType.DESKTOP_CONTROL,
            description=f"Scroll {amount} at ({target_x}, {target_y})",
            parameters={"amount": amount, "x": target_x, "y": target_y}
        )
        
        try:
            # Move to position if specified
            if x is not None and y is not None:
                pyautogui.moveTo(x, y)
            
            # Scroll
            pyautogui.scroll(amount)
            
            result = {
                "success": True,
                "amount": amount,
                "x": target_x,
                "y": target_y
            }
            
            self.audit.complete_operation(op_id, result)
            logger.info(f"Scrolled {amount} at ({target_x}, {target_y})")
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            self.audit.fail_operation(op_id, error_msg)
            logger.error(f"Scroll error: {error_msg}")
            
            return {
                "success": False,
                "error": error_msg
            }
    
    async def type_text(
        self,
        text: str,
        interval: float = 0.01
    ) -> Dict[str, Any]:
        """
        Type text with keyboard.
        
        Args:
            text: Text to type
            interval: Delay between keystrokes
            
        Returns:
            Success status
        """
        if self._check_emergency():
            return {"success": False, "error": "Emergency stop active"}
        
        op_id = self.audit.start_operation(
            action_type=ActionType.DESKTOP_CONTROL,
            description=f"Type text: {text[:50]}...",
            parameters={"text_length": len(text), "interval": interval}
        )
        
        try:
            pyautogui.typewrite(text, interval=interval)
            
            result = {
                "success": True,
                "text_length": len(text),
                "interval": interval
            }
            
            self.audit.complete_operation(op_id, result)
            logger.info(f"Typed {len(text)} characters")
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            self.audit.fail_operation(op_id, error_msg)
            logger.error(f"Type error: {error_msg}")
            
            return {
                "success": False,
                "error": error_msg
            }
    
    async def press_key(
        self,
        key: str,
        presses: int = 1
    ) -> Dict[str, Any]:
        """
        Press a key or key combination.
        
        Args:
            key: Key to press (e.g., 'enter', 'ctrl+c', 'alt+tab')
            presses: Number of times to press
            
        Returns:
            Success status
        """
        if self._check_emergency():
            return {"success": False, "error": "Emergency stop active"}
        
        op_id = self.audit.start_operation(
            action_type=ActionType.DESKTOP_CONTROL,
            description=f"Press key: {key}",
            parameters={"key": key, "presses": presses}
        )
        
        try:
            # Handle key combinations
            if '+' in key:
                keys = key.split('+')
                pyautogui.hotkey(*keys)
            else:
                pyautogui.press(key, presses=presses)
            
            result = {
                "success": True,
                "key": key,
                "presses": presses
            }
            
            self.audit.complete_operation(op_id, result)
            logger.info(f"Pressed key: {key}")
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            self.audit.fail_operation(op_id, error_msg)
            logger.error(f"Key press error: {error_msg}")
            
            return {
                "success": False,
                "error": error_msg
            }
    
    async def take_screenshot(
        self,
        region: Optional[Region] = None,
        output_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Take a screenshot.
        
        Args:
            region: Optional region to capture (None for full screen)
            output_path: Optional path to save screenshot
            
        Returns:
            Success status and screenshot info
        """
        if self._check_emergency():
            return {"success": False, "error": "Emergency stop active"}
        
        op_id = self.audit.start_operation(
            action_type=ActionType.DESKTOP_CONTROL,
            description="Take screenshot",
            parameters={"region": str(region) if region else "full"}
        )
        
        try:
            # Take screenshot
            if region:
                screenshot = pyautogui.screenshot(
                    region=(region.x, region.y, region.width, region.height)
                )
            else:
                screenshot = pyautogui.screenshot()
            
            # Save if path provided
            saved_path = None
            if output_path:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                screenshot.save(output_path)
                saved_path = str(output_path)
            
            result = {
                "success": True,
                "size": screenshot.size,
                "mode": screenshot.mode,
                "saved_path": saved_path,
                "region": {
                    "x": region.x if region else 0,
                    "y": region.y if region else 0,
                    "width": region.width if region else self.screen_size.width,
                    "height": region.height if region else self.screen_size.height
                } if region else None
            }
            
            self.audit.complete_operation(op_id, result)
            logger.info(f"Screenshot taken ({screenshot.size})")
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            self.audit.fail_operation(op_id, error_msg)
            logger.error(f"Screenshot error: {error_msg}")
            
            return {
                "success": False,
                "error": error_msg
            }
    
    async def locate_on_screen(
        self,
        image_path: Union[str, Path],
        confidence: float = 0.9,
        region: Optional[Region] = None
    ) -> Dict[str, Any]:
        """
        Locate an image on screen.
        
        Args:
            image_path: Path to image to find
            confidence: Matching confidence (0-1)
            region: Optional region to search within
            
        Returns:
            Success status and location if found
        """
        if self._check_emergency():
            return {"success": False, "error": "Emergency stop active"}
        
        op_id = self.audit.start_operation(
            action_type=ActionType.DESKTOP_CONTROL,
            description=f"Locate image on screen: {image_path}",
            parameters={"image": str(image_path), "confidence": confidence}
        )
        
        try:
            image_path = Path(image_path)
            if not image_path.exists():
                raise FileNotFoundError(f"Image not found: {image_path}")
            
            # Search region
            region_tuple = None
            if region:
                region_tuple = (region.x, region.y, region.width, region.height)
            
            # Locate image
            location = pyautogui.locateOnScreen(
                str(image_path),
                confidence=confidence,
                region=region_tuple
            )
            
            if location:
                center = pyautogui.center(location)
                result = {
                    "success": True,
                    "found": True,
                    "location": {
                        "left": location.left,
                        "top": location.top,
                        "width": location.width,
                        "height": location.height
                    },
                    "center": {
                        "x": center.x,
                        "y": center.y
                    }
                }
            else:
                result = {
                    "success": True,
                    "found": False,
                    "location": None,
                    "center": None
                }
            
            self.audit.complete_operation(op_id, result)
            logger.info(f"Image location: {result['found']}")
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            self.audit.fail_operation(op_id, error_msg)
            logger.error(f"Locate error: {error_msg}")
            
            return {
                "success": False,
                "error": error_msg,
                "found": False
            }
    
    async def drag(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration: float = 0.5,
        button: str = "left"
    ) -> Dict[str, Any]:
        """
        Drag mouse from one point to another.
        
        Args:
            start_x: Starting X coordinate
            start_y: Starting Y coordinate
            end_x: Ending X coordinate
            end_y: Ending Y coordinate
            duration: Drag duration
            button: Mouse button to use
            
        Returns:
            Success status
        """
        if self._check_emergency():
            return {"success": False, "error": "Emergency stop active"}
        
        op_id = self.audit.start_operation(
            action_type=ActionType.DESKTOP_CONTROL,
            description=f"Drag from ({start_x}, {start_y}) to ({end_x}, {end_y})",
            parameters={
                "start": (start_x, start_y),
                "end": (end_x, end_y),
                "duration": duration,
                "button": button
            }
        )
        
        try:
            # Move to start position
            pyautogui.moveTo(start_x, start_y)
            
            # Perform drag
            pyautogui.dragTo(end_x, end_y, duration=duration, button=button)
            
            result = {
                "success": True,
                "start": (start_x, start_y),
                "end": (end_x, end_y),
                "duration": duration
            }
            
            self.audit.complete_operation(op_id, result)
            logger.info(f"Dragged from ({start_x}, {start_y}) to ({end_x}, {end_y})")
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            self.audit.fail_operation(op_id, error_msg)
            logger.error(f"Drag error: {error_msg}")
            
            return {
                "success": False,
                "error": error_msg
            }
    
    def get_mouse_position(self) -> Dict[str, Any]:
        """Get current mouse position."""
        x, y = pyautogui.position()
        return {
            "success": True,
            "x": x,
            "y": y
        }
    
    def get_screen_size(self) -> Dict[str, Any]:
        """Get screen dimensions."""
        return {
            "success": True,
            "width": self.screen_size.width,
            "height": self.screen_size.height
        }


# Global desktop controller instance
_desktop_controller: Optional[DesktopController] = None


def get_desktop_controller() -> DesktopController:
    """Get or create global desktop controller instance."""
    global _desktop_controller
    if _desktop_controller is None:
        _desktop_controller = DesktopController()
    return _desktop_controller
