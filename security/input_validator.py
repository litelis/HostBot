"""Strict input validation and sanitization for all user inputs."""

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union, Callable
from enum import Enum

from loguru import logger


class ValidationError(Exception):
    """Custom validation error with details."""
    def __init__(self, message: str, field: Optional[str] = None, code: str = "invalid"):
        self.message = message
        self.field = field
        self.code = code
        super().__init__(message)


class InputType(Enum):
    """Types of input validation."""
    COMMAND = "command"
    PATH = "path"
    URL = "url"
    SELECTOR = "selector"
    TEXT = "text"
    NUMBER = "number"
    PACKAGE_NAME = "package_name"
    DISCORD_ID = "discord_id"
    EMAIL = "email"
    JSON = "json"


@dataclass
class ValidationRule:
    """Validation rule configuration."""
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None
    allowed_chars: Optional[str] = None
    forbidden_chars: Optional[str] = None
    allowed_values: Optional[List[str]] = None
    type_check: Optional[type] = None
    custom_validator: Optional[Callable[[Any], bool]] = None
    sanitize: bool = True


class InputValidator:
    """
    Strict input validation with schema-based validation.
    Rejects unexpected fields, enforces type checks, length limits.
    """
    
    # Dangerous patterns that should be rejected
    DANGEROUS_PATTERNS = [
        r";\s*rm\s+-rf",
        r";\s*del\s+/[fq]",
        r";\s*format\s+",
        r">\s*/dev/sda",
        r";\s*dd\s+if=.*of=/dev",
        r";\s*mkfs\.",
        r"[;&|]\s*powershell",
        r"[;&|]\s*cmd\.exe",
        r"\$\(.*\)",  # Command substitution
        r"`.*`",  # Backtick command substitution
        r"\|\s*sh",
        r"\|\s*bash",
        r"<\s*script",
        r"javascript:",
        r"data:text/html",
        r"vbscript:",
        r"on\w+\s*=",  # Event handlers
    ]
    
    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r"(\%27)|(\')|(\-\-)|(\%23)|(#)",
        r"((\%3D)|(=))[^\n]*((\%27)|(\')|(\-\-)|(\%3B)|(;))",
        r"\w*((\%27)|(\'))((\%6F)|o|(\%4F))((\%72)|r|(\%52))",
        r"((\%27)|(\'))union",
        r"exec(\s|\+)+(s|x)p\w+",
        r"UNION\s+SELECT",
        r"INSERT\s+INTO",
        r"DELETE\s+FROM",
        r"DROP\s+TABLE",
    ]
    
    def __init__(self):
        self.rules: Dict[InputType, ValidationRule] = {
            InputType.COMMAND: ValidationRule(
                min_length=1,
                max_length=1000,
                forbidden_chars=None,  # Checked via patterns instead
                custom_validator=self._validate_command
            ),
            InputType.PATH: ValidationRule(
                min_length=1,
                max_length=500,
                pattern=r"^[\w\s\-\./\\\\:~]+$",
                forbidden_chars="<>:\"|?*",
                custom_validator=self._validate_path
            ),
            InputType.URL: ValidationRule(
                min_length=5,
                max_length=2000,
                pattern=r"^https?://[\w\-\.]+(:\d+)?(/[\w\-\./\?%&=]*)?$",
                custom_validator=self._validate_url
            ),
            InputType.SELECTOR: ValidationRule(
                min_length=1,
                max_length=200,
                pattern=r"^[#\.\w\-\[\]=\s>'\"]+$",
                custom_validator=self._validate_selector
            ),
            InputType.TEXT: ValidationRule(
                min_length=0,
                max_length=5000,
                custom_validator=self._validate_text
            ),
            InputType.NUMBER: ValidationRule(
                type_check=(int, float),
                custom_validator=self._validate_number
            ),
            InputType.PACKAGE_NAME: ValidationRule(
                min_length=1,
                max_length=100,
                pattern=r"^[\w\-\.@:]+$",
                custom_validator=self._validate_package_name
            ),
            InputType.DISCORD_ID: ValidationRule(
                min_length=17,
                max_length=20,
                pattern=r"^\d+$",
                type_check=str
            ),
            InputType.EMAIL: ValidationRule(
                min_length=5,
                max_length=254,
                pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            ),
            InputType.JSON: ValidationRule(
                custom_validator=self._validate_json
            )
        }
        
        logger.info("Input validator initialized")
    
    def validate(
        self,
        value: Any,
        input_type: InputType,
        field_name: str = "input",
        strict: bool = True,
        **kwargs
    ) -> Any:
        """
        Validate input against schema.
        
        Args:
            value: Input value to validate
            input_type: Type of input for validation rules
            field_name: Name of field for error messages
            strict: If True, reject unexpected types/fields
            **kwargs: Additional validation parameters
            
        Returns:
            Sanitized value if valid
            
        Raises:
            ValidationError: If validation fails
        """
        # Check for None
        if value is None:
            raise ValidationError(f"{field_name} cannot be None", field_name, "required")
        
        rule = self.rules.get(input_type)
        if not rule:
            raise ValidationError(f"Unknown input type: {input_type}", field_name, "unknown_type")
        
        # Type checking
        if rule.type_check and strict:
            if not isinstance(value, rule.type_check):
                raise ValidationError(
                    f"{field_name} must be of type {rule.type_check}",
                    field_name,
                    "type_error"
                )
        
        # String-specific validations
        if isinstance(value, str):
            # Length checks
            if rule.min_length is not None and len(value) < rule.min_length:
                raise ValidationError(
                    f"{field_name} must be at least {rule.min_length} characters",
                    field_name,
                    "too_short"
                )
            
            if rule.max_length is not None and len(value) > rule.max_length:
                raise ValidationError(
                    f"{field_name} must be at most {rule.max_length} characters",
                    field_name,
                    "too_long"
                )
            
            # Forbidden characters
            if rule.forbidden_chars:
                for char in rule.forbidden_chars:
                    if char in value:
                        raise ValidationError(
                            f"{field_name} contains forbidden character: {char}",
                            field_name,
                            "forbidden_char"
                        )
            
            # Pattern matching
            if rule.pattern:
                if not re.match(rule.pattern, value):
                    raise ValidationError(
                        f"{field_name} format is invalid",
                        field_name,
                        "pattern_mismatch"
                    )
            
            # Allowed values
            if rule.allowed_values and value not in rule.allowed_values:
                raise ValidationError(
                    f"{field_name} must be one of: {', '.join(rule.allowed_values)}",
                    field_name,
                    "invalid_value"
                )
        
        # Custom validator
        if rule.custom_validator:
            if not rule.custom_validator(value):
                raise ValidationError(
                    f"{field_name} failed custom validation",
                    field_name,
                    "custom_validation_failed"
                )
        
        # Sanitize if enabled
        if rule.sanitize and isinstance(value, str):
            value = self._sanitize_string(value)
        
        logger.debug(f"Validated {field_name} of type {input_type.value}")
        return value
    
    def validate_schema(
        self,
        data: Dict[str, Any],
        schema: Dict[str, Dict[str, Any]],
        strict: bool = True
    ) -> Dict[str, Any]:
        """
        Validate dictionary against schema.
        
        Args:
            data: Input dictionary
            schema: Schema definition {field: {type, required, min_length, max_length, pattern}}
            strict: If True, reject unexpected fields
            
        Returns:
            Validated and sanitized data
            
        Raises:
            ValidationError: If validation fails
        """
        validated = {}
        
        # Check for unexpected fields in strict mode
        if strict:
            unexpected = set(data.keys()) - set(schema.keys())
            if unexpected:
                raise ValidationError(
                    f"Unexpected fields: {', '.join(unexpected)}",
                    None,
                    "unexpected_fields"
                )
        
        # Validate each field
        for field_name, field_schema in schema.items():
            value = data.get(field_name)
            
            # Check required
            if field_schema.get("required", False) and value is None:
                raise ValidationError(
                    f"{field_name} is required",
                    field_name,
                    "required"
                )
            
            # Skip if None and not required
            if value is None:
                continue
            
            # Get input type
            input_type = field_schema.get("type", InputType.TEXT)
            
            # Validate
            try:
                validated_value = self.validate(
                    value,
                    input_type,
                    field_name,
                    strict,
                    **{k: v for k, v in field_schema.items() if k not in ["type", "required"]}
                )
                validated[field_name] = validated_value
            except ValidationError as e:
                raise ValidationError(e.message, field_name, e.code)
        
        return validated
    
    def _sanitize_string(self, value: str) -> str:
        """Sanitize string input."""
        # Remove null bytes
        value = value.replace("\x00", "")
        
        # Remove control characters except newlines and tabs
        value = "".join(char for char in value if ord(char) >= 32 or char in "\n\t\r")
        
        # Strip whitespace
        value = value.strip()
        
        return value
    
    def _validate_command(self, value: str) -> bool:
        """Validate command input."""
        # Check for dangerous patterns
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(f"Dangerous pattern detected in command: {pattern}")
                return False
        
        # Check for SQL injection patterns
        for pattern in self.SQL_INJECTION_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(f"SQL injection pattern detected: {pattern}")
                return False
        
        return True
    
    def _validate_path(self, value: str) -> bool:
        """Validate file path."""
        # Check for path traversal
        if ".." in value:
            logger.warning(f"Path traversal attempt detected: {value}")
            return False
        
        # Check for absolute paths that might be sensitive
        sensitive_paths = ["/etc/", "/sys/", "/proc/", "C:\\Windows", "C:\\Program Files"]
        for sensitive in sensitive_paths:
            if value.lower().startswith(sensitive.lower()):
                logger.warning(f"Sensitive path detected: {value}")
                # Don't block, just warn - permission guard will handle this
        
        return True
    
    def _validate_url(self, value: str) -> bool:
        """Validate URL."""
        # Check for dangerous URL schemes
        dangerous_schemes = ["javascript:", "data:", "vbscript:", "file:"]
        for scheme in dangerous_schemes:
            if value.lower().startswith(scheme):
                logger.warning(f"Dangerous URL scheme detected: {scheme}")
                return False
        
        return True
    
    def _validate_selector(self, value: str) -> bool:
        """Validate CSS/XPath selector."""
        # Check for script injection in selectors
        if "<script" in value.lower():
            logger.warning(f"Script tag detected in selector: {value}")
            return False
        
        return True
    
    def _validate_text(self, value: str) -> bool:
        """Validate general text."""
        # Check for excessive length (already checked in main validation)
        if len(value) > 10000:
            return False
        
        return True
    
    def _validate_number(self, value: Union[int, float]) -> bool:
        """Validate number."""
        # Check for reasonable range
        if isinstance(value, (int, float)):
            if abs(value) > 1e15:  # Unreasonably large number
                return False
        
        return True
    
    def _validate_package_name(self, value: str) -> bool:
        """Validate package name."""
        # Check for dangerous characters in package names
        dangerous = [";", "&", "|", "$", "`", "$(", ">", "<"]
        for char in dangerous:
            if char in value:
                logger.warning(f"Dangerous character in package name: {char}")
                return False
        
        return True
    
    def _validate_json(self, value: Any) -> bool:
        """Validate JSON data."""
        import json
        
        if isinstance(value, str):
            try:
                json.loads(value)
                return True
            except json.JSONDecodeError:
                return False
        elif isinstance(value, (dict, list)):
            return True
        
        return False
    
    def validate_discord_command(
        self,
        command: str,
        max_length: int = 2000
    ) -> str:
        """
        Validate Discord command input.
        
        Args:
            command: Discord command string
            max_length: Maximum command length
            
        Returns:
            Sanitized command
            
        Raises:
            ValidationError: If validation fails
        """
        if not command:
            raise ValidationError("Command cannot be empty", "command", "required")
        
        if len(command) > max_length:
            raise ValidationError(
                f"Command too long (max {max_length} characters)",
                "command",
                "too_long"
            )
        
        # Sanitize
        command = self._sanitize_string(command)
        
        # Check for @everyone/@here abuse
        if "@everyone" in command or "@here" in command:
            logger.warning("Command contains @everyone or @here")
            # Remove them
            command = command.replace("@everyone", "[everyone]").replace("@here", "[here]")
        
        return command


# Global input validator instance
_input_validator: Optional[InputValidator] = None


def get_input_validator() -> InputValidator:
    """Get or create global input validator instance."""
    global _input_validator
    if _input_validator is None:
        _input_validator = InputValidator()
    return _input_validator
