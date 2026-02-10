"""Configuration settings for the Autonomous OS Control Agent."""

import os
from pathlib import Path
from typing import List, Optional

from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )
    
    # Discord Settings
    discord_token: str = Field(..., description="Discord bot token")
    discord_guild_id: Optional[int] = Field(None, description="Discord guild ID")
    discord_admin_user_id: int = Field(..., description="Admin user ID for emergency access")
    discord_command_prefix: str = Field("!", description="Command prefix")
    
    # Ollama Settings
    ollama_host: str = Field("http://localhost:11434", description="Ollama server URL")
    ollama_model: str = Field("llama3.2", description="Model to use")
    ollama_timeout: int = Field(120, description="Request timeout in seconds")
    ollama_max_tokens: int = Field(4096, description="Maximum tokens per response")
    
    # Agent Settings
    agent_name: str = Field("SystemAgent", description="Agent name")
    safety_mode: str = Field("strict", description="Safety mode: strict, moderate, or minimal")
    log_level: str = Field("INFO", description="Logging level")
    log_dir: Path = Field(Path("./logs"), description="Log directory")
    
    # Permission Settings
    allow_desktop_control: bool = Field(True, description="Allow mouse/keyboard control")
    allow_system_commands: bool = Field(True, description="Allow system command execution")
    allow_browser_automation: bool = Field(True, description="Allow browser automation")
    allow_software_installation: bool = Field(True, description="Allow software installation")
    
    # Confirmation Settings
    require_confirmation_critical: bool = Field(True, description="Require confirmation for critical actions")
    require_confirmation_desktop: bool = Field(True, description="Require confirmation for desktop actions")
    require_confirmation_system: bool = Field(True, description="Require confirmation for system commands")
    confirmation_timeout: int = Field(300, description="Confirmation timeout in seconds")
    
    # Security Settings
    emergency_stop_code: str = Field("STOP123", description="Emergency stop code")
    
    @validator("log_dir", pre=True)
    def create_log_dir(cls, v):
        """Ensure log directory exists."""
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @validator("safety_mode")
    def validate_safety_mode(cls, v):
        """Validate safety mode setting."""
        allowed = ["strict", "moderate", "minimal"]
        if v.lower() not in allowed:
            raise ValueError(f"Safety mode must be one of: {allowed}")
        return v.lower()
    
    @property
    def is_strict_mode(self) -> bool:
        """Check if running in strict safety mode."""
        return self.safety_mode == "strict"
    
    @property
    def is_moderate_mode(self) -> bool:
        """Check if running in moderate safety mode."""
        return self.safety_mode == "moderate"
    
    @property
    def is_minimal_mode(self) -> bool:
        """Check if running in minimal safety mode."""
        return self.safety_mode == "minimal"


# Global settings instance
settings = Settings()
