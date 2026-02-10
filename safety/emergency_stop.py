"""Emergency stop system for immediate agent halt."""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Callable, Coroutine, List, Optional, Set

from loguru import logger

from config.settings import settings


class EmergencyLevel(Enum):
    """Levels of emergency stop."""
    SOFT = "soft"       # Stop current operation, keep agent running
    HARD = "hard"       # Stop all operations, pause agent
    FULL = "full"       # Complete shutdown of agent


@dataclass
class EmergencyEvent:
    """Record of an emergency stop event."""
    timestamp: datetime
    level: EmergencyLevel
    triggered_by: str
    reason: str
    code_used: str
    operations_stopped: int


class EmergencyStop:
    """Emergency stop system for immediate halt capability."""
    
    def __init__(self):
        self._stop_event = asyncio.Event()
        self._level: Optional[EmergencyLevel] = None
        self._triggered_by: Optional[str] = None
        self._reason: Optional[str] = None
        self._active_operations: Set[str] = set()
        self._lock = asyncio.Lock()
        self._handlers: List[Callable[[EmergencyLevel, str], Coroutine]] = []
        self._history: List[EmergencyEvent] = []
        self._is_armed = True
        
        logger.info("Emergency stop system initialized")
        logger.info(f"Emergency code: {settings.emergency_stop_code}")
    
    def arm(self) -> None:
        """Arm the emergency stop system."""
        self._is_armed = True
        logger.info("Emergency stop system ARMED")
    
    def disarm(self) -> None:
        """Disarm the emergency stop system."""
        self._is_armed = False
        logger.warning("Emergency stop system DISARMED")
    
    @property
    def is_armed(self) -> bool:
        """Check if emergency stop is armed."""
        return self._is_armed
    
    @property
    def is_triggered(self) -> bool:
        """Check if emergency stop has been triggered."""
        return self._stop_event.is_set()
    
    @property
    def current_level(self) -> Optional[EmergencyLevel]:
        """Get current emergency level if triggered."""
        return self._level
    
    def register_handler(self, handler: Callable[[EmergencyLevel, str], Coroutine]) -> None:
        """Register a handler to be called when emergency stop is triggered."""
        self._handlers.append(handler)
        logger.debug(f"Registered emergency handler: {handler.__name__}")
    
    async def trigger(
        self,
        code: str,
        level: EmergencyLevel = EmergencyLevel.HARD,
        triggered_by: str = "unknown",
        reason: str = "Emergency stop triggered"
    ) -> bool:
        """
        Trigger the emergency stop.
        
        Args:
            code: Emergency stop code for verification
            level: Level of emergency stop
            triggered_by: Identifier of who/what triggered the stop
            reason: Reason for the emergency stop
            
        Returns:
            True if successfully triggered, False if invalid code or not armed
        """
        if not self._is_armed:
            logger.warning(f"Emergency stop attempt by {triggered_by} but system is disarmed")
            return False
        
        if code != settings.emergency_stop_code:
            logger.warning(f"Invalid emergency stop code attempt by {triggered_by}")
            return False
        
        if self._stop_event.is_set():
            logger.warning(f"Emergency stop already triggered, ignoring new trigger by {triggered_by}")
            return False
        
        async with self._lock:
            self._level = level
            self._triggered_by = triggered_by
            self._reason = reason
            
            # Record the event
            event = EmergencyEvent(
                timestamp=datetime.now(),
                level=level,
                triggered_by=triggered_by,
                reason=reason,
                code_used=code,
                operations_stopped=len(self._active_operations)
            )
            self._history.append(event)
            
            # Set the stop event
            self._stop_event.set()
        
        logger.critical(f"🚨 EMERGENCY STOP TRIGGERED by {triggered_by}")
        logger.critical(f"Level: {level.value}, Reason: {reason}")
        logger.critical(f"Operations stopped: {event.operations_stopped}")
        
        # Notify all handlers
        for handler in self._handlers:
            try:
                await handler(level, reason)
            except Exception as e:
                logger.error(f"Emergency handler error: {e}")
        
        return True
    
    async def reset(self, code: str, reset_by: str) -> bool:
        """
        Reset the emergency stop system.
        
        Args:
            code: Emergency stop code for verification
            reset_by: Identifier of who is resetting
            
        Returns:
            True if successfully reset, False if invalid code
        """
        if code != settings.emergency_stop_code:
            logger.warning(f"Invalid emergency reset code attempt by {reset_by}")
            return False
        
        if not self._stop_event.is_set():
            logger.info(f"Emergency reset by {reset_by} but system was not triggered")
            return True
        
        async with self._lock:
            self._stop_event.clear()
            self._level = None
            self._triggered_by = None
            self._reason = None
        
        logger.critical(f"🟢 EMERGENCY STOP RESET by {reset_by}")
        
        return True
    
    def check_stop(self) -> bool:
        """
        Check if emergency stop has been triggered.
        
        Returns:
            True if stop is triggered (caller should halt)
        """
        return self._stop_event.is_set()
    
    async def wait_for_stop(self) -> EmergencyLevel:
        """
        Wait for emergency stop to be triggered.
        
        Returns:
            The emergency level when triggered
        """
        await self._stop_event.wait()
        return self._level or EmergencyLevel.HARD
    
    def register_operation(self, operation_id: str) -> bool:
        """
        Register an active operation.
        
        Returns:
            True if operation can proceed, False if emergency stop is active
        """
        if self._stop_event.is_set():
            return False
        
        self._active_operations.add(operation_id)
        return True
    
    def unregister_operation(self, operation_id: str) -> None:
        """Unregister a completed operation."""
        self._active_operations.discard(operation_id)
    
    def get_active_operations(self) -> Set[str]:
        """Get set of currently active operation IDs."""
        return self._active_operations.copy()
    
    def get_history(self, limit: int = 10) -> List[EmergencyEvent]:
        """Get history of emergency stop events."""
        return self._history[-limit:]
    
    def get_status(self) -> dict:
        """Get current emergency stop status."""
        return {
            "armed": self._is_armed,
            "triggered": self._stop_event.is_set(),
            "level": self._level.value if self._level else None,
            "triggered_by": self._triggered_by,
            "reason": self._reason,
            "active_operations": len(self._active_operations),
            "history_count": len(self._history)
        }
    
    def format_status_message(self) -> str:
        """Format current status for display."""
        status = self.get_status()
        
        if status["triggered"]:
            return (
                f"🚨 **EMERGENCY STOP ACTIVE**\\n"
                f"Level: {status['level']}\\n"
                f"Triggered by: {status['triggered_by']}\\n"
                f"Reason: {status['reason']}\\n"
                f"Active operations: {status['active_operations']}"
            )
        else:
            armed_status = "🟢 ARMED" if status['armed'] else "⚪ DISARMED"
            return (
                f"**Emergency Stop Status**\\n"
                f"Status: {armed_status}\\n"
                f"Active operations: {status['active_operations']}\\n"
                f"Past events: {status['history_count']}"
            )


# Global emergency stop instance
_emergency_stop: Optional[EmergencyStop] = None


def get_emergency_stop() -> EmergencyStop:
    """Get or create global emergency stop instance."""
    global _emergency_stop
    if _emergency_stop is None:
        _emergency_stop = EmergencyStop()
    return _emergency_stop
