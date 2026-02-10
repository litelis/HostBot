#!/usr/bin/env python3
"""
Autonomous OS Control Agent - Main Entry Point

This is the main entry point for the autonomous agent system.
It initializes all components and starts the Discord bot.
"""

import asyncio
import signal
import sys
from pathlib import Path

from loguru import logger

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.settings import settings
from bot.discord_client import get_discord_client
from security.rate_limiter import get_rate_limiter


def setup_logging():
    """Configure logging with security masking."""
    # Remove default handler
    logger.remove()
    
    # Add console handler
    logger.add(
        sys.stdout,
        level=settings.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    
    # Add file handler
    log_file = settings.log_dir / "agent.log"
    logger.add(
        log_file,
        rotation="10 MB",
        retention="30 days",
        level=settings.log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
    )
    
    logger.info(f"Logging configured. Log file: {log_file}")


def handle_signal(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)


async def shutdown(client, rate_limiter):
    """Graceful shutdown."""
    logger.info("Shutting down gracefully...")
    
    # Stop rate limiter cleanup task
    if rate_limiter:
        await rate_limiter.stop()
    
    # Close Discord client
    if client:
        await client.close()
    
    logger.info("Shutdown complete")


async def main():
    """Main entry point."""
    # Setup logging
    setup_logging()
    
    logger.info("=" * 60)
    logger.info(f"Starting {settings.agent_name}")
    logger.info(f"Safety Mode: {settings.safety_mode}")
    logger.info(f"Log Level: {settings.log_level}")
    logger.info("=" * 60)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    client = None
    rate_limiter = None
    
    try:
        # Get rate limiter
        rate_limiter = get_rate_limiter()
        await rate_limiter.start()
        
        # Get Discord client
        client = get_discord_client()
        
        # Start the bot
        logger.info("Starting Discord bot...")
        await client.start(settings.discord_token)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
    finally:
        await shutdown(client, rate_limiter)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        sys.exit(1)
