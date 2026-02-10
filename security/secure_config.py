"""Secure configuration handling for API keys and sensitive data."""

import os
import secrets
import hashlib
from typing import Optional, Dict, Any
from pathlib import Path

from loguru import logger

from config.settings import settings



class SecureConfig:
    """
    Secure configuration management for API keys and sensitive data.
    Ensures no hardcoded keys, uses environment variables, supports key rotation.
    """
    
    # Required environment variables
    REQUIRED_VARS = [
        "DISCORD_TOKEN",
        "DISCORD_ADMIN_USER_ID"
    ]
    
    # Sensitive variables that should never be logged
    SENSITIVE_VARS = [
        "DISCORD_TOKEN",
        "EMERGENCY_STOP_CODE",
        "OLLAMA_API_KEY"  # If Ollama requires auth in future
    ]
    
    def __init__(self):
        self._config_cache: Dict[str, Any] = {}
        self._key_hashes: Dict[str, str] = {}
        self._rotation_dates: Dict[str, float] = {}
        
        # Validate on initialization
        self._validate_environment()
        
        logger.info("Secure config initialized")
    
    def _validate_environment(self):
        """Validate that all required environment variables are set."""
        missing = []
        
        # Use pydantic-settings which properly parses .env files
        if not settings.discord_token:
            missing.append("DISCORD_TOKEN")
        if not settings.discord_admin_user_id:
            missing.append("DISCORD_ADMIN_USER_ID")
        
        if missing:
            raise RuntimeError(
                f"Missing required environment variables: {', '.join(missing)}\n"
                f"Please set these in your .env file or environment."
            )
        
        # Check for default/weak emergency stop code
        emergency_code = settings.emergency_stop_code
        if emergency_code in ["STOP123", "123456", "password", "admin"]:
            logger.warning("WARNING: Using default emergency stop code. Please change it in .env!")
        
        logger.info("Environment validation passed")

    
    def get(self, key: str, default: Any = None, sensitive: bool = False) -> Any:
        """
        Get configuration value securely.
        
        Args:
            key: Environment variable name
            default: Default value if not set
            sensitive: Whether this is sensitive data
            
        Returns:
            Configuration value
        """
        value = os.getenv(key, default)
        
        if sensitive and value:
            # Store hash for rotation detection
            self._key_hashes[key] = self._hash_value(value)
        
        return value
    
    def get_discord_token(self) -> str:
        """Get Discord token securely."""
        token = settings.discord_token
        if not token:
            raise RuntimeError("DISCORD_TOKEN not set")
        
        # Validate token format (should be base64-like)
        if len(token) < 50:
            logger.warning("Discord token seems unusually short - verify it's correct")
        
        # Store hash for rotation detection
        self._key_hashes["DISCORD_TOKEN"] = self._hash_value(token)
        
        return token

    
    def get_emergency_code(self) -> str:
        """Get emergency stop code securely."""
        code = settings.emergency_stop_code
        if not code:
            return "STOP123"  # Fallback (will warn in logs)
        
        # Validate code strength
        if len(code) < 6:
            logger.warning("Emergency stop code should be at least 6 characters")
        
        # Store hash for rotation detection
        self._key_hashes["EMERGENCY_STOP_CODE"] = self._hash_value(code)
        
        return code

    
    def check_key_rotation(self, key: str) -> bool:
        """
        Check if a key needs rotation.
        
        Returns:
            True if key has changed (needs rotation handling)
        """
        current_value = os.getenv(key)
        if not current_value:
            return False
        
        current_hash = self._hash_value(current_value)
        stored_hash = self._key_hashes.get(key)
        
        if stored_hash and stored_hash != current_hash:
            logger.info(f"Key rotation detected for {key}")
            self._key_hashes[key] = current_hash
            return True
        
        return False
    
    def mask_sensitive_value(self, value: str, visible_chars: int = 4) -> str:
        """
        Mask a sensitive value for logging.
        
        Args:
            value: Value to mask
            visible_chars: Number of characters to show at start/end
            
        Returns:
            Masked value (e.g., "abcd****wxyz")
        """
        if not value or len(value) <= visible_chars * 2:
            return "*" * len(value) if value else ""
        
        return f"{value[:visible_chars]}{'*' * (len(value) - visible_chars * 2)}{value[-visible_chars:]}"
    
    def mask_sensitive_in_string(self, text: str) -> str:
        """
        Mask all sensitive values in a string.
        
        Args:
            text: Text that might contain sensitive values
            
        Returns:
            Text with sensitive values masked
        """
        for var in self.SENSITIVE_VARS:
            value = os.getenv(var)
            if value and value in text:
                masked = self.mask_sensitive_value(value)
                text = text.replace(value, masked)
        
        return text
    
    def validate_no_hardcoded_keys(self, file_path: str) -> bool:
        """
        Scan a file for hardcoded API keys.
        
        Args:
            file_path: Path to file to check
            
        Returns:
            True if no keys found, False otherwise
        """
        suspicious_patterns = [
            r'api[_-]?key\s*[=:]\s*["\'][^"\']{20,}["\']',
            r'token\s*[=:]\s*["\'][^"\']{50,}["\']',
            r'secret\s*[=:]\s*["\'][^"\']{20,}["\']',
            r'password\s*[=:]\s*["\'][^"\']{8,}["\']',
            r'[a-zA-Z0-9_-]{50,}\.[a-zA-Z0-9_-]{50,}\.[a-zA-Z0-9_-]{50,}',  # JWT-like
        ]
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            import re
            for pattern in suspicious_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    logger.error(f"Potential hardcoded key found in {file_path}: {matches[0][:20]}...")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error scanning {file_path}: {e}")
            return False
    
    def scan_project_for_keys(self, project_path: str) -> Dict[str, bool]:
        """
        Scan entire project for hardcoded keys.
        
        Args:
            project_path: Root path of project
            
        Returns:
            Dictionary of file paths and their scan results
        """
        project_path = Path(project_path)
        results = {}
        
        # Files to scan
        extensions = ['.py', '.js', '.ts', '.json', '.yaml', '.yml', '.env.example']
        
        for ext in extensions:
            for file_path in project_path.rglob(f"*{ext}"):
                # Skip certain directories
                if any(part in str(file_path) for part in ['.git', '__pycache__', 'node_modules', 'venv', '.env']):
                    continue
                
                # Skip the example env file
                if file_path.name == '.env':
                    continue
                
                results[str(file_path)] = self.validate_no_hardcoded_keys(str(file_path))
        
        # Report results
        clean_files = sum(1 for v in results.values() if v)
        total_files = len(results)
        
        logger.info(f"Security scan complete: {clean_files}/{total_files} files clean")
        
        suspicious = [f for f, clean in results.items() if not clean]
        if suspicious:
            logger.warning(f"Suspicious files found: {suspicious}")
        
        return results
    
    def _hash_value(self, value: str) -> str:
        """Create hash of a value for comparison."""
        return hashlib.sha256(value.encode()).hexdigest()[:16]
    
    def get_secure_headers(self) -> Dict[str, str]:
        """
        Get secure HTTP headers for any API endpoints.
        
        Returns:
            Dictionary of security headers
        """
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'",
            "Referrer-Policy": "strict-origin-when-cross-origin"
        }


# Global secure config instance
_secure_config: Optional[SecureConfig] = None


def get_secure_config() -> SecureConfig:
    """Get or create global secure config instance."""
    global _secure_config
    if _secure_config is None:
        _secure_config = SecureConfig()
    return _secure_config
