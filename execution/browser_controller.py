"""Browser controller for web automation using Playwright."""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from loguru import logger
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from safety.audit_logger import get_audit_logger, ActionType
from safety.emergency_stop import get_emergency_stop


@dataclass
class BrowserSession:
    """Browser session information."""
    session_id: str
    browser_type: str
    browser: Browser
    context: BrowserContext
    page: Page
    current_url: Optional[str] = None


class BrowserController:
    """Controller for browser automation."""
    
    def __init__(self):
        self.audit = get_audit_logger()
        self.emergency = get_emergency_stop()
        self.sessions: Dict[str, BrowserSession] = {}
        self.playwright = None
        
        logger.info("Browser controller initialized")
    
    async def _ensure_playwright(self):
        """Ensure playwright is initialized."""
        if self.playwright is None:
            self.playwright = await async_playwright().start()
    
    def _check_emergency(self) -> bool:
        """Check if emergency stop is active."""
        if self.emergency.check_stop():
            logger.warning("Browser action blocked - emergency stop active")
            return True
        return False
    
    async def start_session(
        self,
        browser_type: str = "chromium",
        headless: bool = False,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Start a new browser session.
        
        Args:
            browser_type: Browser to use (chromium, firefox, webkit)
            headless: Whether to run headless
            session_id: Optional custom session ID
            
        Returns:
            Session information
        """
        if self._check_emergency():
            return {"success": False, "error": "Emergency stop active"}
        
        await self._ensure_playwright()
        
        session_id = session_id or f"browser_{len(self.sessions)}"
        
        op_id = self.audit.start_operation(
            action_type=ActionType.BROWSER_ACTION,
            description=f"Start {browser_type} browser session",
            parameters={"browser_type": browser_type, "headless": headless}
        )
        
        try:
            # Launch browser
            browser_launcher = getattr(self.playwright, browser_type)
            browser = await browser_launcher.launch(headless=headless)
            
            # Create context and page
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080}
            )
            page = await context.new_page()
            
            # Store session
            session = BrowserSession(
                session_id=session_id,
                browser_type=browser_type,
                browser=browser,
                context=context,
                page=page
            )
            self.sessions[session_id] = session
            
            result = {
                "success": True,
                "session_id": session_id,
                "browser_type": browser_type,
                "headless": headless
            }
            
            self.audit.complete_operation(op_id, result)
            logger.info(f"Browser session started: {session_id}")
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            self.audit.fail_operation(op_id, error_msg)
            logger.error(f"Browser start error: {error_msg}")
            
            return {
                "success": False,
                "error": error_msg
            }
    
    async def navigate(
        self,
        url: str,
        session_id: str = "browser_0",
        wait_until: str = "networkidle"
    ) -> Dict[str, Any]:
        """
        Navigate to a URL.
        
        Args:
            url: URL to navigate to
            session_id: Browser session ID
            wait_until: When to consider navigation complete
            
        Returns:
            Navigation result
        """
        if self._check_emergency():
            return {"success": False, "error": "Emergency stop active"}
        
        if session_id not in self.sessions:
            return {"success": False, "error": f"Session not found: {session_id}"}
        
        session = self.sessions[session_id]
        
        op_id = self.audit.start_operation(
            action_type=ActionType.BROWSER_ACTION,
            description=f"Navigate to {url}",
            parameters={"url": url, "session_id": session_id}
        )
        
        try:
            await session.page.goto(url, wait_until=wait_until)
            session.current_url = session.page.url
            
            result = {
                "success": True,
                "url": session.page.url,
                "title": await session.page.title(),
                "session_id": session_id
            }
            
            self.audit.complete_operation(op_id, result)
            logger.info(f"Navigated to {url}")
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            self.audit.fail_operation(op_id, error_msg)
            logger.error(f"Navigation error: {error_msg}")
            
            return {
                "success": False,
                "error": error_msg,
                "url": url
            }
    
    async def click(
        self,
        selector: str,
        session_id: str = "browser_0",
        timeout: int = 5000
    ) -> Dict[str, Any]:
        """
        Click an element.
        
        Args:
            selector: CSS or XPath selector
            session_id: Browser session ID
            timeout: Timeout in milliseconds
            
        Returns:
            Click result
        """
        if self._check_emergency():
            return {"success": False, "error": "Emergency stop active"}
        
        if session_id not in self.sessions:
            return {"success": False, "error": f"Session not found: {session_id}"}
        
        session = self.sessions[session_id]
        
        op_id = self.audit.start_operation(
            action_type=ActionType.BROWSER_ACTION,
            description=f"Click element: {selector}",
            parameters={"selector": selector, "session_id": session_id}
        )
        
        try:
            await session.page.click(selector, timeout=timeout)
            
            result = {
                "success": True,
                "selector": selector,
                "session_id": session_id
            }
            
            self.audit.complete_operation(op_id, result)
            logger.info(f"Clicked element: {selector}")
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            self.audit.fail_operation(op_id, error_msg)
            logger.error(f"Click error: {error_msg}")
            
            return {
                "success": False,
                "error": error_msg,
                "selector": selector
            }
    
    async def type_text(
        self,
        selector: str,
        text: str,
        session_id: str = "browser_0",
        clear_first: bool = True,
        timeout: int = 5000
    ) -> Dict[str, Any]:
        """
        Type text into an input field.
        
        Args:
            selector: CSS or XPath selector
            text: Text to type
            session_id: Browser session ID
            clear_first: Whether to clear field first
            timeout: Timeout in milliseconds
            
        Returns:
            Type result
        """
        if self._check_emergency():
            return {"success": False, "error": "Emergency stop active"}
        
        if session_id not in self.sessions:
            return {"success": False, "error": f"Session not found: {session_id}"}
        
        session = self.sessions[session_id]
        
        op_id = self.audit.start_operation(
            action_type=ActionType.BROWSER_ACTION,
            description=f"Type text into {selector}",
            parameters={"selector": selector, "text_length": len(text), "session_id": session_id}
        )
        
        try:
            if clear_first:
                await session.page.fill(selector, "", timeout=timeout)
            
            await session.page.type(selector, text, timeout=timeout)
            
            result = {
                "success": True,
                "selector": selector,
                "text_length": len(text),
                "session_id": session_id
            }
            
            self.audit.complete_operation(op_id, result)
            logger.info(f"Typed text into {selector}")
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            self.audit.fail_operation(op_id, error_msg)
            logger.error(f"Type error: {error_msg}")
            
            return {
                "success": False,
                "error": error_msg,
                "selector": selector
            }
    
    async def get_text(
        self,
        selector: str,
        session_id: str = "browser_0",
        timeout: int = 5000
    ) -> Dict[str, Any]:
        """
        Get text content of an element.
        
        Args:
            selector: CSS or XPath selector
            session_id: Browser session ID
            timeout: Timeout in milliseconds
            
        Returns:
            Text content
        """
        if self._check_emergency():
            return {"success": False, "error": "Emergency stop active"}
        
        if session_id not in self.sessions:
            return {"success": False, "error": f"Session not found: {session_id}"}
        
        session = self.sessions[session_id]
        
        try:
            element = await session.page.wait_for_selector(selector, timeout=timeout)
            if element:
                text = await element.text_content()
                return {
                    "success": True,
                    "selector": selector,
                    "text": text,
                    "session_id": session_id
                }
            else:
                return {
                    "success": False,
                    "error": "Element not found",
                    "selector": selector
                }
                
        except Exception as e:
            logger.error(f"Get text error: {e}")
            return {
                "success": False,
                "error": str(e),
                "selector": selector
            }
    
    async def get_element_count(
        self,
        selector: str,
        session_id: str = "browser_0"
    ) -> Dict[str, Any]:
        """
        Count elements matching selector.
        
        Args:
            selector: CSS or XPath selector
            session_id: Browser session ID
            
        Returns:
            Element count
        """
        if session_id not in self.sessions:
            return {"success": False, "error": f"Session not found: {session_id}"}
        
        session = self.sessions[session_id]
        
        try:
            count = await session.page.locator(selector).count()
            return {
                "success": True,
                "selector": selector,
                "count": count,
                "session_id": session_id
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "selector": selector
            }
    
    async def wait_for_selector(
        self,
        selector: str,
        session_id: str = "browser_0",
        timeout: int = 5000,
        state: str = "visible"
    ) -> Dict[str, Any]:
        """
        Wait for an element to appear.
        
        Args:
            selector: CSS or XPath selector
            session_id: Browser session ID
            timeout: Timeout in milliseconds
            state: State to wait for (visible, hidden, attached, detached)
            
        Returns:
            Wait result
        """
        if session_id not in self.sessions:
            return {"success": False, "error": f"Session not found: {session_id}"}
        
        session = self.sessions[session_id]
        
        try:
            await session.page.wait_for_selector(selector, timeout=timeout, state=state)
            return {
                "success": True,
                "selector": selector,
                "state": state,
                "session_id": session_id
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "selector": selector
            }
    
    async def take_screenshot(
        self,
        session_id: str = "browser_0",
        selector: Optional[str] = None,
        full_page: bool = False,
        output_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Take a screenshot.
        
        Args:
            session_id: Browser session ID
            selector: Optional element to screenshot
            full_page: Whether to capture full page
            output_path: Path to save screenshot
            
        Returns:
            Screenshot result
        """
        if self._check_emergency():
            return {"success": False, "error": "Emergency stop active"}
        
        if session_id not in self.sessions:
            return {"success": False, "error": f"Session not found: {session_id}"}
        
        session = self.sessions[session_id]
        
        op_id = self.audit.start_operation(
            action_type=ActionType.BROWSER_ACTION,
            description="Take browser screenshot",
            parameters={"session_id": session_id, "full_page": full_page}
        )
        
        try:
            if output_path:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
            
            if selector:
                element = await session.page.query_selector(selector)
                if element:
                    screenshot_bytes = await element.screenshot(path=output_path)
                else:
                    raise ValueError(f"Element not found: {selector}")
            else:
                screenshot_bytes = await session.page.screenshot(
                    path=output_path,
                    full_page=full_page
                )
            
            result = {
                "success": True,
                "full_page": full_page,
                "selector": selector,
                "saved_path": str(output_path) if output_path else None,
                "session_id": session_id
            }
            
            self.audit.complete_operation(op_id, result)
            logger.info(f"Screenshot taken ({'full page' if full_page else 'viewport'})")
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            self.audit.fail_operation(op_id, error_msg)
            logger.error(f"Screenshot error: {error_msg}")
            
            return {
                "success": False,
                "error": error_msg
            }
    
    async def execute_javascript(
        self,
        script: str,
        session_id: str = "browser_0"
    ) -> Dict[str, Any]:
        """
        Execute JavaScript in the browser.
        
        Args:
            script: JavaScript code to execute
            session_id: Browser session ID
            
        Returns:
            Execution result
        """
        if self._check_emergency():
            return {"success": False, "error": "Emergency stop active"}
        
        if session_id not in self.sessions:
            return {"success": False, "error": f"Session not found: {session_id}"}
        
        session = self.sessions[session_id]
        
        op_id = self.audit.start_operation(
            action_type=ActionType.BROWSER_ACTION,
            description="Execute JavaScript",
            parameters={"script_length": len(script), "session_id": session_id}
        )
        
        try:
            result = await session.page.evaluate(script)
            
            result_data = {
                "success": True,
                "result": result,
                "session_id": session_id
            }
            
            self.audit.complete_operation(op_id, {"result_type": type(result).__name__})
            logger.info("JavaScript executed")
            
            return result_data
            
        except Exception as e:
            error_msg = str(e)
            self.audit.fail_operation(op_id, error_msg)
            logger.error(f"JavaScript error: {error_msg}")
            
            return {
                "success": False,
                "error": error_msg
            }
    
    async def close_session(self, session_id: str = "browser_0") -> Dict[str, Any]:
        """
        Close a browser session.
        
        Args:
            session_id: Session ID to close
            
        Returns:
            Close result
        """
        if session_id not in self.sessions:
            return {"success": False, "error": f"Session not found: {session_id}"}
        
        session = self.sessions[session_id]
        
        try:
            await session.context.close()
            await session.browser.close()
            del self.sessions[session_id]
            
            logger.info(f"Browser session closed: {session_id}")
            return {
                "success": True,
                "session_id": session_id
            }
            
        except Exception as e:
            logger.error(f"Close session error: {e}")
            return {
                "success": False,
                "error": str(e),
                "session_id": session_id
            }
    
    async def close_all_sessions(self) -> Dict[str, Any]:
        """Close all browser sessions."""
        results = []
        for session_id in list(self.sessions.keys()):
            result = await self.close_session(session_id)
            results.append(result)
        
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
        
        return {
            "success": all(r["success"] for r in results),
            "sessions_closed": len(results),
            "results": results
        }
    
    def get_session_info(self, session_id: str = "browser_0") -> Dict[str, Any]:
        """Get information about a session."""
        if session_id not in self.sessions:
            return {"success": False, "error": f"Session not found: {session_id}"}
        
        session = self.sessions[session_id]
        return {
            "success": True,
            "session_id": session_id,
            "browser_type": session.browser_type,
            "current_url": session.current_url
        }


# Global browser controller instance
_browser_controller: Optional[BrowserController] = None


def get_browser_controller() -> BrowserController:
    """Get or create global browser controller instance."""
    global _browser_controller
    if _browser_controller is None:
        _browser_controller = BrowserController()
    return _browser_controller
