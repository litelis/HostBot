"""
Screen capture module for HostBot.
Captures screenshots and prepares them for AI analysis.
Optimized for Windows with support for multiple monitors.
"""

import base64
import io
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import pyautogui
from PIL import Image, ImageDraw, ImageFont
from loguru import logger


class ScreenCapture:
    """
    Handles screen capture functionality for the agent.
    Supports full screen, region capture, and multi-monitor setups.
    """
    
    def __init__(self, save_dir: Optional[Path] = None):
        """
        Initialize screen capture.
        
        Args:
            save_dir: Directory to save screenshots (optional)
        """
        self.save_dir = save_dir or Path("./screenshots")
        self.save_dir.mkdir(parents=True, exist_ok=True)
        
        # Get screen dimensions
        self.screen_width, self.screen_height = pyautogui.size()
        
        logger.info(f"ScreenCapture initialized: {self.screen_width}x{self.screen_height}")
    
    def capture_full_screen(self, save: bool = False) -> Dict[str, any]:
        """
        Capture the entire screen.
        
        Args:
            save: Whether to save the screenshot to disk
            
        Returns:
            Dictionary with image data and metadata
        """
        try:
            # Capture screenshot using pyautogui
            screenshot = pyautogui.screenshot()
            
            timestamp = datetime.now().isoformat()
            filename = None
            
            if save:
                filename = self.save_dir / f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                screenshot.save(filename)
                logger.info(f"Screenshot saved: {filename}")
            
            # Convert to base64 for AI processing
            buffered = io.BytesIO()
            screenshot.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            return {
                "success": True,
                "image": screenshot,
                "base64": img_base64,
                "width": screenshot.width,
                "height": screenshot.height,
                "timestamp": timestamp,
                "filename": str(filename) if filename else None,
                "mode": "full_screen"
            }
            
        except Exception as e:
            logger.error(f"Screen capture failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def capture_region(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        save: bool = False
    ) -> Dict[str, any]:
        """
        Capture a specific region of the screen.
        
        Args:
            x: X coordinate of top-left corner
            y: Y coordinate of top-left corner
            width: Width of region
            height: Height of region
            save: Whether to save to disk
            
        Returns:
            Dictionary with image data and metadata
        """
        try:
            # Validate coordinates
            if x < 0 or y < 0 or width <= 0 or height <= 0:
                raise ValueError("Invalid region coordinates")
            
            # Capture region
            screenshot = pyautogui.screenshot(region=(x, y, width, height))
            
            timestamp = datetime.now().isoformat()
            filename = None
            
            if save:
                filename = self.save_dir / f"region_{x}_{y}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                screenshot.save(filename)
            
            # Convert to base64
            buffered = io.BytesIO()
            screenshot.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            return {
                "success": True,
                "image": screenshot,
                "base64": img_base64,
                "width": width,
                "height": height,
                "x": x,
                "y": y,
                "timestamp": timestamp,
                "filename": str(filename) if filename else None,
                "mode": "region"
            }
            
        except Exception as e:
            logger.error(f"Region capture failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def capture_around_mouse(
        self,
        radius: int = 200,
        save: bool = False
    ) -> Dict[str, any]:
        """
        Capture screen area around current mouse position.
        
        Args:
            radius: Radius in pixels around mouse
            save: Whether to save to disk
            
        Returns:
            Dictionary with image data and metadata
        """
        try:
            # Get mouse position
            mouse_x, mouse_y = pyautogui.position()
            
            # Calculate region
            x = max(0, mouse_x - radius)
            y = max(0, mouse_y - radius)
            width = min(radius * 2, self.screen_width - x)
            height = min(radius * 2, self.screen_height - y)
            
            return self.capture_region(x, y, width, height, save)
            
        except Exception as e:
            logger.error(f"Mouse region capture failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def capture_window(self, window_title: str, save: bool = False) -> Dict[str, any]:
        """
        Capture a specific window by title (Windows only).
        
        Args:
            window_title: Title of window to capture
            save: Whether to save to disk
            
        Returns:
            Dictionary with image data and metadata
        """
        try:
            # Windows-specific implementation using pygetwindow
            import pygetwindow as gw
            
            # Find window
            windows = gw.getWindowsWithTitle(window_title)
            if not windows:
                return {
                    "success": False,
                    "error": f"Window not found: {window_title}"
                }
            
            window = windows[0]
            
            # Bring to front and capture
            window.activate()
            import time
            time.sleep(0.5)  # Wait for window to be active
            
            # Capture the window region
            return self.capture_region(
                window.left,
                window.top,
                window.width,
                window.height,
                save
            )
            
        except ImportError:
            logger.error("pygetwindow not installed. Install with: pip install pygetwindow")
            return {
                "success": False,
                "error": "pygetwindow not installed"
            }
        except Exception as e:
            logger.error(f"Window capture failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def annotate_image(
        self,
        image: Image.Image,
        elements: List[Dict],
        mouse_pos: Optional[Tuple[int, int]] = None
    ) -> Image.Image:
        """
        Annotate image with detected elements and mouse position.
        
        Args:
            image: PIL Image to annotate
            elements: List of detected elements with coordinates
            mouse_pos: Current mouse position (x, y)
            
        Returns:
            Annotated PIL Image
        """
        draw = ImageDraw.Draw(image)
        
        # Draw detected elements
        for i, element in enumerate(elements):
            x, y = element.get("x", 0), element.get("y", 0)
            w, h = element.get("width", 50), element.get("height", 20)
            label = element.get("label", f"Element {i}")
            
            # Draw rectangle
            draw.rectangle([x, y, x + w, y + h], outline="red", width=2)
            
            # Draw label
            try:
                draw.text((x, y - 15), label, fill="red")
            except:
                # Font might not be available
                pass
        
        # Draw mouse position
        if mouse_pos:
            mx, my = mouse_pos
            draw.ellipse([mx-5, my-5, mx+5, my+5], fill="blue", outline="blue")
            draw.line([mx-10, my, mx+10, my], fill="blue", width=2)
            draw.line([mx, my-10, mx, my+10], fill="blue", width=2)
        
        return image
    
    def get_screen_info(self) -> Dict[str, any]:
        """
        Get information about the screen setup.
        
        Returns:
            Dictionary with screen information
        """
        return {
            "width": self.screen_width,
            "height": self.screen_height,
            "aspect_ratio": self.screen_width / self.screen_height,
            "save_directory": str(self.save_dir)
        }
    
    def list_saved_screenshots(self, limit: int = 10) -> List[Path]:
        """
        List recently saved screenshots.
        
        Args:
            limit: Maximum number of screenshots to return
            
        Returns:
            List of screenshot file paths
        """
        screenshots = sorted(
            self.save_dir.glob("*.png"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        return screenshots[:limit]


# Global screen capture instance
_screen_capture: Optional[ScreenCapture] = None


def get_screen_capture() -> ScreenCapture:
    """Get or create global screen capture instance."""
    global _screen_capture
    if _screen_capture is None:
        _screen_capture = ScreenCapture()
    return _screen_capture
