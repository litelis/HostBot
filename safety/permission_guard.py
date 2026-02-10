"""Permission and access control system."""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set

from loguru import logger

from config.settings import settings


class PermissionLevel(Enum):
    """Permission levels for operations."""
    DENY = "deny"           # Operation not allowed
    ALLOW = "allow"         # Operation allowed
    CONFIRM = "confirm"     # Require confirmation
    ADMIN = "admin"         # Require admin approval


class OperationCategory(Enum):
    """Categories of operations."""
    SYSTEM_COMMAND = "system_command"
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_DELETE = "file_delete"
    DESKTOP_MOUSE = "desktop_mouse"
    DESKTOP_KEYBOARD = "desktop_keyboard"
    BROWSER_NAVIGATE = "browser_navigate"
    BROWSER_INTERACT = "browser_interact"
    PROCESS_START = "process_start"
    PROCESS_KILL = "process_kill"
    SOFTWARE_INSTALL = "software_install"
    SOFTWARE_UNINSTALL = "software_uninstall"
    REGISTRY_MODIFY = "registry_modify"
    NETWORK_CONNECT = "network_connect"
    ENVIRONMENT_MODIFY = "environment_modify"


@dataclass
class PermissionRule:
    """A permission rule."""
    category: OperationCategory
    pattern: Optional[str]  # Regex pattern for matching
    level: PermissionLevel
    description: str


class PermissionGuard:
    """Manages permissions and access control."""
    
    # Dangerous patterns that require extra scrutiny
    DANGEROUS_PATTERNS = [
        r"rm\s+-rf\s+/",
        r"format\s+[a-zA-Z]:",
        r"del\s+/f\s+/s\s+/q\s+\\",
        r"rd\s+/s\s+/q\s+\\",
        r">\\s*/dev/sda",
        r"dd\s+if=.*of=/dev/sda",
        r"mkfs\.",
        r"fdisk",
        r"reg\s+delete\s+.*\\Software\\Microsoft\\Windows\\CurrentVersion\\Run",
    ]
    
    # Sensitive paths that require confirmation
    SENSITIVE_PATHS = [
        r"^C:\\\\Windows",
        r"^C:\\\\Program Files",
        r"^C:\\\\ProgramData",
        r"^/etc/",
        r"^/usr/bin/",
        r"^/bin/",
        r"^/sbin/",
        r"^/sys/",
        r"^/proc/",
        r"\\.ssh",
        r"\\.gnupg",
        r"password",
        r"secret",
        r"token",
        r"key",
    ]
    
    def __init__(self):
        self.rules: List[PermissionRule] = []
        self._init_default_rules()
        self._admin_users: Set[str] = {str(settings.discord_admin_user_id)}
        
        logger.info("Permission guard initialized")
    
    def _init_default_rules(self) -> None:
        """Initialize default permission rules based on settings."""
        # System commands
        if settings.allow_system_commands:
            self.add_rule(OperationCategory.SYSTEM_COMMAND, None, PermissionLevel.CONFIRM, "System commands require confirmation")
        else:
            self.add_rule(OperationCategory.SYSTEM_COMMAND, None, PermissionLevel.DENY, "System commands disabled")
        
        # Desktop control
        if settings.allow_desktop_control:
            self.add_rule(OperationCategory.DESKTOP_MOUSE, None, PermissionLevel.CONFIRM, "Mouse control requires confirmation")
            self.add_rule(OperationCategory.DESKTOP_KEYBOARD, None, PermissionLevel.CONFIRM, "Keyboard control requires confirmation")
        else:
            self.add_rule(OperationCategory.DESKTOP_MOUSE, None, PermissionLevel.DENY, "Desktop control disabled")
            self.add_rule(OperationCategory.DESKTOP_KEYBOARD, None, PermissionLevel.DENY, "Desktop control disabled")
        
        # Browser automation
        if settings.allow_browser_automation:
            self.add_rule(OperationCategory.BROWSER_NAVIGATE, None, PermissionLevel.ALLOW, "Browser navigation allowed")
            self.add_rule(OperationCategory.BROWSER_INTERACT, None, PermissionLevel.CONFIRM, "Browser interaction requires confirmation")
        else:
            self.add_rule(OperationCategory.BROWSER_NAVIGATE, None, PermissionLevel.DENY, "Browser automation disabled")
            self.add_rule(OperationCategory.BROWSER_INTERACT, None, PermissionLevel.DENY, "Browser automation disabled")
        
        # Software installation
        if settings.allow_software_installation:
            self.add_rule(OperationCategory.SOFTWARE_INSTALL, None, PermissionLevel.CONFIRM, "Software installation requires confirmation")
            self.add_rule(OperationCategory.SOFTWARE_UNINSTALL, None, PermissionLevel.ADMIN, "Software uninstallation requires admin")
        else:
            self.add_rule(OperationCategory.SOFTWARE_INSTALL, None, PermissionLevel.DENY, "Software installation disabled")
            self.add_rule(OperationCategory.SOFTWARE_UNINSTALL, None, PermissionLevel.DENY, "Software installation disabled")
        
        # File operations
        self.add_rule(OperationCategory.FILE_READ, None, PermissionLevel.ALLOW, "File reading generally allowed")
        self.add_rule(OperationCategory.FILE_WRITE, None, PermissionLevel.CONFIRM, "File writing requires confirmation")
        self.add_rule(OperationCategory.FILE_DELETE, None, PermissionLevel.CONFIRM, "File deletion requires confirmation")
        
        # Process management
        self.add_rule(OperationCategory.PROCESS_START, None, PermissionLevel.CONFIRM, "Starting processes requires confirmation")
        self.add_rule(OperationCategory.PROCESS_KILL, None, PermissionLevel.CONFIRM, "Killing processes requires confirmation")
        
        # System modifications
        self.add_rule(OperationCategory.REGISTRY_MODIFY, None, PermissionLevel.ADMIN, "Registry modification requires admin")
        self.add_rule(OperationCategory.ENVIRONMENT_MODIFY, None, PermissionLevel.CONFIRM, "Environment modification requires confirmation")
        self.add_rule(OperationCategory.NETWORK_CONNECT, None, PermissionLevel.ALLOW, "Network connections generally allowed")
    
    def add_rule(
        self,
        category: OperationCategory,
        pattern: Optional[str],
        level: PermissionLevel,
        description: str
    ) -> None:
        """Add a permission rule."""
        rule = PermissionRule(
            category=category,
            pattern=pattern,
            level=level,
            description=description
        )
        self.rules.append(rule)
        logger.debug(f"Added permission rule: {category.value} -> {level.value}")
    
    def check_permission(
        self,
        category: OperationCategory,
        command: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> PermissionLevel:
        """
        Check permission for an operation.
        
        Returns:
            PermissionLevel indicating if operation is allowed
        """
        # Check for dangerous patterns first
        if command and self._is_dangerous(command):
            logger.warning(f"Dangerous pattern detected in command: {command}")
            return PermissionLevel.ADMIN
        
        # Check for sensitive paths
        if command and self._contains_sensitive_path(command):
            logger.warning(f"Sensitive path detected in command: {command}")
            return PermissionLevel.ADMIN
        
        # Find matching rules
        matching_rules = []
        for rule in self.rules:
            if rule.category == category:
                if rule.pattern is None:
                    matching_rules.append(rule)
                elif command and re.search(rule.pattern, command, re.IGNORECASE):
                    matching_rules.append(rule)
        
        if not matching_rules:
            # Default deny if no rules match
            logger.warning(f"No permission rules matched for {category.value}")
            return PermissionLevel.DENY
        
        # Return the most restrictive level
        level_priority = {
            PermissionLevel.DENY: 0,
            PermissionLevel.ADMIN: 1,
            PermissionLevel.CONFIRM: 2,
            PermissionLevel.ALLOW: 3
        }
        
        most_restrictive = min(matching_rules, key=lambda r: level_priority[r.level])
        
        # Check if user is admin
        if user_id and user_id in self._admin_users:
            if most_restrictive.level == PermissionLevel.ADMIN:
                logger.info(f"Admin user {user_id} approved for {category.value}")
                return PermissionLevel.ALLOW
        
        return most_restrictive.level
    
    def is_allowed(
        self,
        category: OperationCategory,
        command: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> bool:
        """Quick check if operation is allowed without confirmation."""
        level = self.check_permission(category, command, user_id)
        return level == PermissionLevel.ALLOW
    
    def requires_confirmation(
        self,
        category: OperationCategory,
        command: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> bool:
        """Check if operation requires confirmation."""
        level = self.check_permission(category, command, user_id)
        return level in [PermissionLevel.CONFIRM, PermissionLevel.ADMIN]
    
    def requires_admin(
        self,
        category: OperationCategory,
        command: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> bool:
        """Check if operation requires admin approval."""
        level = self.check_permission(category, command, user_id)
        return level == PermissionLevel.ADMIN
    
    def _is_dangerous(self, command: str) -> bool:
        """Check if command matches dangerous patterns."""
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return True
        return False
    
    def _contains_sensitive_path(self, command: str) -> bool:
        """Check if command contains sensitive paths."""
        for pattern in self.SENSITIVE_PATHS:
            if re.search(pattern, command, re.IGNORECASE):
                return True
        return False
    
    def add_admin_user(self, user_id: str) -> None:
        """Add a user to the admin list."""
        self._admin_users.add(user_id)
        logger.info(f"Added admin user: {user_id}")
    
    def remove_admin_user(self, user_id: str) -> None:
        """Remove a user from the admin list."""
        self._admin_users.discard(user_id)
        logger.info(f"Removed admin user: {user_id}")
    
    def get_rules(self) -> List[PermissionRule]:
        """Get all permission rules."""
        return self.rules.copy()
    
    def get_status(self) -> Dict[str, any]:
        """Get current permission status."""
        return {
            "total_rules": len(self.rules),
            "admin_users": len(self._admin_users),
            "desktop_control": settings.allow_desktop_control,
            "system_commands": settings.allow_system_commands,
            "browser_automation": settings.allow_browser_automation,
            "software_installation": settings.allow_software_installation,
        }


# Global permission guard instance
_permission_guard: Optional[PermissionGuard] = None


def get_permission_guard() -> PermissionGuard:
    """Get or create global permission guard instance."""
    global _permission_guard
    if _permission_guard is None:
        _permission_guard = PermissionGuard()
    return _permission_guard
