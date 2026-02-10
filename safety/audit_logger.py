"""Audit logging system for complete action tracking and accountability."""

import json
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict

from loguru import logger

from config.settings import settings


class ActionType(Enum):
    """Types of actions that can be logged."""
    SYSTEM_COMMAND = "system_command"
    DESKTOP_CONTROL = "desktop_control"
    BROWSER_ACTION = "browser_action"
    FILE_OPERATION = "file_operation"
    PROCESS_MANAGEMENT = "process_management"
    SOFTWARE_INSTALL = "software_install"
    CONFIGURATION_CHANGE = "configuration_change"
    AI_PLANNING = "ai_planning"
    AI_REASONING = "ai_reasoning"
    USER_CONFIRMATION = "user_confirmation"
    EMERGENCY_STOP = "emergency_stop"
    ERROR = "error"


class ActionStatus(Enum):
    """Status of logged actions."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


@dataclass
class AuditEntry:
    """Single audit log entry."""
    id: str
    timestamp: str
    action_type: str
    status: str
    description: str
    user_id: Optional[str]
    command: Optional[str]
    parameters: Dict[str, Any]
    result: Optional[Any]
    error_message: Optional[str]
    duration_ms: Optional[int]
    session_id: str
    parent_id: Optional[str]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class AuditLogger:
    """Comprehensive audit logging system."""
    
    def __init__(self):
        self.session_id = str(uuid.uuid4())
        self.log_file = settings.log_dir / f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
        self.entries: List[AuditEntry] = []
        self._current_operations: Dict[str, AuditEntry] = {}
        
        # Setup file logger
        logger.add(
            settings.log_dir / "audit.log",
            rotation="10 MB",
            retention="30 days",
            level=settings.log_level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
        )
        
        logger.info(f"Audit logger initialized. Session: {self.session_id}")
        logger.info(f"Audit log file: {self.log_file}")
    
    def start_operation(
        self,
        action_type: ActionType,
        description: str,
        user_id: Optional[str] = None,
        command: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        parent_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Start logging a new operation."""
        operation_id = str(uuid.uuid4())
        
        entry = AuditEntry(
            id=operation_id,
            timestamp=datetime.now().isoformat(),
            action_type=action_type.value,
            status=ActionStatus.IN_PROGRESS.value,
            description=description,
            user_id=user_id,
            command=command,
            parameters=parameters or {},
            result=None,
            error_message=None,
            duration_ms=None,
            session_id=self.session_id,
            parent_id=parent_id,
            metadata=metadata or {}
        )
        
        self._current_operations[operation_id] = entry
        self._write_entry(entry)
        
        logger.info(f"Started operation {operation_id}: {description}")
        
        return operation_id
    
    def complete_operation(
        self,
        operation_id: str,
        result: Any = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Mark an operation as completed."""
        if operation_id not in self._current_operations:
            logger.warning(f"Operation {operation_id} not found for completion")
            return
        
        entry = self._current_operations[operation_id]
        entry.status = ActionStatus.COMPLETED.value
        entry.result = result
        
        if metadata:
            entry.metadata.update(metadata)
        
        # Calculate duration
        start_time = datetime.fromisoformat(entry.timestamp)
        duration = (datetime.now() - start_time).total_seconds() * 1000
        entry.duration_ms = int(duration)
        
        self._write_entry(entry)
        del self._current_operations[operation_id]
        
        logger.info(f"Completed operation {operation_id} in {duration:.0f}ms")
    
    def fail_operation(
        self,
        operation_id: str,
        error_message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Mark an operation as failed."""
        if operation_id not in self._current_operations:
            logger.warning(f"Operation {operation_id} not found for failure logging")
            return
        
        entry = self._current_operations[operation_id]
        entry.status = ActionStatus.FAILED.value
        entry.error_message = error_message
        
        if metadata:
            entry.metadata.update(metadata)
        
        # Calculate duration
        start_time = datetime.fromisoformat(entry.timestamp)
        duration = (datetime.now() - start_time).total_seconds() * 1000
        entry.duration_ms = int(duration)
        
        self._write_entry(entry)
        del self._current_operations[operation_id]
        
        logger.error(f"Failed operation {operation_id}: {error_message}")
    
    def cancel_operation(
        self,
        operation_id: str,
        reason: str
    ) -> None:
        """Mark an operation as cancelled."""
        if operation_id not in self._current_operations:
            return
        
        entry = self._current_operations[operation_id]
        entry.status = ActionStatus.CANCELLED.value
        entry.error_message = reason
        
        self._write_entry(entry)
        del self._current_operations[operation_id]
        
        logger.warning(f"Cancelled operation {operation_id}: {reason}")
    
    def log_event(
        self,
        action_type: ActionType,
        description: str,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Log a single event without tracking duration."""
        entry_id = str(uuid.uuid4())
        
        entry = AuditEntry(
            id=entry_id,
            timestamp=datetime.now().isoformat(),
            action_type=action_type.value,
            status=ActionStatus.COMPLETED.value,
            description=description,
            user_id=user_id,
            command=None,
            parameters={},
            result=None,
            error_message=None,
            duration_ms=0,
            session_id=self.session_id,
            parent_id=None,
            metadata=metadata or {}
        )
        
        self._write_entry(entry)
        logger.info(f"Event logged: {description}")
        
        return entry_id
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Get summary of current session."""
        total_operations = len(self.entries)
        completed = sum(1 for e in self.entries if e.status == ActionStatus.COMPLETED.value)
        failed = sum(1 for e in self.entries if e.status == ActionStatus.FAILED.value)
        in_progress = len(self._current_operations)
        
        return {
            "session_id": self.session_id,
            "total_operations": total_operations,
            "completed": completed,
            "failed": failed,
            "in_progress": in_progress,
            "log_file": str(self.log_file)
        }
    
    def get_recent_entries(self, count: int = 10) -> List[AuditEntry]:
        """Get recent audit entries."""
        return self.entries[-count:] if self.entries else []
    
    def _write_entry(self, entry: AuditEntry) -> None:
        """Write entry to log file."""
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict(), default=str) + "\n")
            self.entries.append(entry)
        except Exception as e:
            logger.error(f"Failed to write audit entry: {e}")
    
    def export_session(self, output_path: Optional[Path] = None) -> Path:
        """Export entire session to JSON file."""
        if output_path is None:
            output_path = settings.log_dir / f"session_export_{self.session_id}.json"
        
        data = {
            "session_id": self.session_id,
            "export_time": datetime.now().isoformat(),
            "summary": self.get_session_summary(),
            "entries": [e.to_dict() for e in self.entries]
        }
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        
        logger.info(f"Session exported to {output_path}")
        return output_path


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get or create global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
