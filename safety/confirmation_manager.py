"""Interactive confirmation system for critical actions."""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Coroutine
import uuid

from loguru import logger

from config.settings import settings


class ConfirmationLevel(Enum):
    """Levels of confirmation required."""
    NONE = "none"           # No confirmation needed
    INFO = "info"           # Inform only, no wait
    STANDARD = "standard"   # Wait for yes/no
    CRITICAL = "critical"   # Require explicit confirmation with code
    EMERGENCY = "emergency" # Require admin approval


@dataclass
class ConfirmationRequest:
    """A confirmation request from the agent."""
    id: str
    timestamp: datetime
    level: ConfirmationLevel
    action_description: str
    details: Dict[str, Any]
    timeout_seconds: int
    user_id: Optional[str]
    callback: Optional[Callable[[bool], Coroutine]]
    status: str  # "pending", "approved", "denied", "expired"
    response: Optional[bool] = None
    response_time: Optional[datetime] = None
    response_message: Optional[str] = None


class ConfirmationManager:
    """Manages interactive confirmations with users."""
    
    def __init__(self):
        self.pending_confirmations: Dict[str, ConfirmationRequest] = {}
        self.confirmation_history: List[ConfirmationRequest] = []
        self._event_handlers: List[Callable[[ConfirmationRequest], Coroutine]] = []
        self._lock = asyncio.Lock()
        
        logger.info("Confirmation manager initialized")
    
    def register_event_handler(self, handler: Callable[[ConfirmationRequest], Coroutine]) -> None:
        """Register a handler for confirmation events (e.g., Discord notifier)."""
        self._event_handlers.append(handler)
        logger.debug(f"Registered confirmation event handler: {handler.__name__}")
    
    async def request_confirmation(
        self,
        action_description: str,
        level: ConfirmationLevel = ConfirmationLevel.STANDARD,
        details: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        callback: Optional[Callable[[bool], Coroutine]] = None
    ) -> Optional[bool]:
        """
        Request confirmation from user.
        
        Returns:
            True if approved, False if denied, None if timeout/cancelled
        """
        if level == ConfirmationLevel.NONE:
            return True
        
        if level == ConfirmationLevel.INFO:
            # Just inform, don't wait
            await self._notify_handlers(
                ConfirmationRequest(
                    id=str(uuid.uuid4()),
                    timestamp=datetime.now(),
                    level=level,
                    action_description=action_description,
                    details=details or {},
                    timeout_seconds=0,
                    user_id=user_id,
                    callback=None,
                    status="info"
                )
            )
            return True
        
        # Determine timeout
        if timeout_seconds is None:
            timeout_seconds = settings.confirmation_timeout
        
        # Check if confirmation is required based on settings
        if not self._is_confirmation_required(level, action_description):
            logger.info(f"Auto-approved {level.value} action: {action_description}")
            return True
        
        # Create confirmation request
        request_id = str(uuid.uuid4())
        request = ConfirmationRequest(
            id=request_id,
            timestamp=datetime.now(),
            level=level,
            action_description=action_description,
            details=details or {},
            timeout_seconds=timeout_seconds,
            user_id=user_id,
            callback=callback,
            status="pending"
        )
        
        async with self._lock:
            self.pending_confirmations[request_id] = request
        
        # Notify handlers (e.g., send Discord message)
        await self._notify_handlers(request)
        
        logger.info(f"Confirmation requested [{request_id}]: {action_description}")
        
        # Wait for response with timeout
        try:
            result = await asyncio.wait_for(
                self._wait_for_response(request_id),
                timeout=timeout_seconds
            )
            return result
        except asyncio.TimeoutError:
            async with self._lock:
                if request_id in self.pending_confirmations:
                    request = self.pending_confirmations[request_id]
                    request.status = "expired"
                    self.confirmation_history.append(request)
                    del self.pending_confirmations[request_id]
            
            logger.warning(f"Confirmation [{request_id}] expired after {timeout_seconds}s")
            return None
    
    async def respond_to_confirmation(
        self,
        request_id: str,
        approved: bool,
        user_id: str,
        message: Optional[str] = None
    ) -> bool:
        """
        Process a user's response to a confirmation request.
        
        Returns:
            True if response was processed, False if request not found
        """
        async with self._lock:
            if request_id not in self.pending_confirmations:
                logger.warning(f"Confirmation response for unknown request: {request_id}")
                return False
            
            request = self.pending_confirmations[request_id]
            
            # Verify user authorization for critical/emergency levels
            if request.level in [ConfirmationLevel.CRITICAL, ConfirmationLevel.EMERGENCY]:
                if user_id != str(settings.discord_admin_user_id):
                    logger.warning(f"Unauthorized confirmation attempt by {user_id}")
                    return False
            
            request.status = "approved" if approved else "denied"
            request.response = approved
            request.response_time = datetime.now()
            request.response_message = message
            
            # Move to history
            self.confirmation_history.append(request)
            del self.pending_confirmations[request_id]
        
        logger.info(f"Confirmation [{request_id}] {request.status} by {user_id}")
        
        # Execute callback if provided
        if request.callback:
            try:
                await request.callback(approved)
            except Exception as e:
                logger.error(f"Confirmation callback error: {e}")
        
        return True
    
    def get_pending_confirmations(self) -> List[ConfirmationRequest]:
        """Get list of pending confirmation requests."""
        return list(self.pending_confirmations.values())
    
    def get_confirmation_history(
        self,
        limit: int = 50,
        user_id: Optional[str] = None
    ) -> List[ConfirmationRequest]:
        """Get confirmation history."""
        history = self.confirmation_history
        
        if user_id:
            history = [c for c in history if c.user_id == user_id]
        
        return history[-limit:]
    
    def cancel_pending(self, request_id: Optional[str] = None) -> int:
        """
        Cancel pending confirmations.
        
        Args:
            request_id: Specific request to cancel, or None to cancel all
            
        Returns:
            Number of confirmations cancelled
        """
        cancelled = 0
        
        if request_id:
            if request_id in self.pending_confirmations:
                request = self.pending_confirmations[request_id]
                request.status = "cancelled"
                self.confirmation_history.append(request)
                del self.pending_confirmations[request_id]
                cancelled = 1
                logger.info(f"Cancelled confirmation [{request_id}]")
        else:
            # Cancel all pending
            for request in list(self.pending_confirmations.values()):
                request.status = "cancelled"
                self.confirmation_history.append(request)
            
            cancelled = len(self.pending_confirmations)
            self.pending_confirmations.clear()
            logger.info(f"Cancelled all {cancelled} pending confirmations")
        
        return cancelled
    
    def _is_confirmation_required(self, level: ConfirmationLevel, description: str) -> bool:
        """Check if confirmation is required based on settings."""
        if settings.is_minimal_mode:
            return level in [ConfirmationLevel.EMERGENCY]
        
        if settings.is_moderate_mode:
            return level in [ConfirmationLevel.CRITICAL, ConfirmationLevel.EMERGENCY]
        
        # Strict mode
        if level == ConfirmationLevel.CRITICAL:
            return settings.require_confirmation_critical
        elif "desktop" in description.lower() or "mouse" in description.lower() or "keyboard" in description.lower():
            return settings.require_confirmation_desktop
        elif "system" in description.lower() or "command" in description.lower():
            return settings.require_confirmation_system
        
        return True
    
    async def _notify_handlers(self, request: ConfirmationRequest) -> None:
        """Notify all registered event handlers."""
        for handler in self._event_handlers:
            try:
                await handler(request)
            except Exception as e:
                logger.error(f"Confirmation handler error: {e}")
    
    async def _wait_for_response(self, request_id: str) -> bool:
        """Wait for a response to a confirmation request."""
        while True:
            async with self._lock:
                if request_id not in self.pending_confirmations:
                    # Request has been processed
                    for req in self.confirmation_history:
                        if req.id == request_id and req.response is not None:
                            return req.response
            
            await asyncio.sleep(0.5)  # Poll every 500ms
    
    def format_confirmation_message(self, request: ConfirmationRequest) -> str:
        """Format a confirmation request for display."""
        emoji = {
            ConfirmationLevel.STANDARD: "⚠️",
            ConfirmationLevel.CRITICAL: "🛑",
            ConfirmationLevel.EMERGENCY: "🚨"
        }.get(request.level, "❓")
        
        lines = [
            f"{emoji} **Confirmation Required**",
            f"",
            f"**Action:** {request.action_description}",
            f"**Level:** {request.level.value.upper()}",
            f"**Request ID:** `{request.id}`",
            f"**Timeout:** {request.timeout_seconds} seconds",
            f"",
        ]
        
        if request.details:
            lines.append("**Details:**")
            for key, value in request.details.items():
                lines.append(f"  • {key}: {value}")
            lines.append("")
        
        lines.append("**Respond with:**")
        lines.append(f"  `!confirm {request.id}` - to approve")
        lines.append(f"  `!deny {request.id}` - to deny")
        
        if request.level == ConfirmationLevel.CRITICAL:
            lines.append("")
            lines.append("⚠️ This is a CRITICAL action requiring explicit approval.")
        
        return "\n".join(lines)


# Global confirmation manager instance
_confirmation_manager: Optional[ConfirmationManager] = None


def get_confirmation_manager() -> ConfirmationManager:
    """Get or create global confirmation manager instance."""
    global _confirmation_manager
    if _confirmation_manager is None:
        _confirmation_manager = ConfirmationManager()
    return _confirmation_manager
