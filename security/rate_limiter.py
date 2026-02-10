"""Rate limiting for Discord commands and API endpoints."""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from loguru import logger


@dataclass
class RateLimitEntry:
    """Rate limit tracking entry."""
    requests: List[float] = field(default_factory=list)
    blocked_until: Optional[float] = None
    
    def clean_old_requests(self, window_seconds: float):
        """Remove requests outside the time window."""
        now = time.time()
        cutoff = now - window_seconds
        self.requests = [t for t in self.requests if t > cutoff]


class RateLimiter:
    """
    Rate limiter with IP and user-based limits.
    Provides graceful 429 handling with retry-after headers.
    """
    
    def __init__(self):
        # User-based limits (Discord user ID)
        self.user_limits: Dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)
        
        # IP-based limits (for any future HTTP endpoints)
        self.ip_limits: Dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)
        
        # Default limits
        self.default_user_limits = {
            "commands_per_minute": 10,
            "commands_per_hour": 100,
            "critical_actions_per_hour": 5
        }
        
        self.default_ip_limits = {
            "requests_per_minute": 30,
            "requests_per_hour": 300
        }
        
        # Time windows in seconds
        self.windows = {
            "minute": 60,
            "hour": 3600
        }
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        # Cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        
        logger.info("Rate limiter initialized")
    
    async def start(self):
        """Start the cleanup task."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Rate limiter cleanup task started")
    
    async def stop(self):
        """Stop the cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("Rate limiter stopped")
    
    async def check_user_limit(
        self,
        user_id: str,
        action_type: str = "standard"
    ) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        Check if user has exceeded rate limits.
        
        Args:
            user_id: Discord user ID
            action_type: Type of action (standard, critical)
            
        Returns:
            Tuple of (allowed, retry_after_seconds, reason)
        """
        async with self._lock:
            entry = self.user_limits[user_id]
            now = time.time()
            
            # Check if currently blocked
            if entry.blocked_until and now < entry.blocked_until:
                retry_after = int(entry.blocked_until - now)
                return False, retry_after, "User is temporarily blocked"
            
            # Clean old requests
            entry.clean_old_requests(self.windows["hour"])
            
            # Determine limits based on action type
            if action_type == "critical":
                limit_minute = 2
                limit_hour = self.default_user_limits["critical_actions_per_hour"]
            else:
                limit_minute = self.default_user_limits["commands_per_minute"]
                limit_hour = self.default_user_limits["commands_per_hour"]
            
            # Check minute window
            minute_ago = now - self.windows["minute"]
            requests_last_minute = sum(1 for t in entry.requests if t > minute_ago)
            
            if requests_last_minute >= limit_minute:
                # Block for 1 minute
                entry.blocked_until = now + 60
                return False, 60, f"Rate limit exceeded: {limit_minute} commands per minute"
            
            # Check hour window
            if len(entry.requests) >= limit_hour:
                # Block for 1 hour
                entry.blocked_until = now + self.windows["hour"]
                return False, self.windows["hour"], f"Rate limit exceeded: {limit_hour} commands per hour"
            
            # Record request
            entry.requests.append(now)
            
            return True, None, None
    
    async def check_ip_limit(
        self,
        ip_address: str,
        endpoint: str = "default"
    ) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        Check if IP has exceeded rate limits.
        
        Args:
            ip_address: Client IP address
            endpoint: API endpoint being accessed
            
        Returns:
            Tuple of (allowed, retry_after_seconds, reason)
        """
        async with self._lock:
            entry = self.ip_limits[ip_address]
            now = time.time()
            
            # Check if currently blocked
            if entry.blocked_until and now < entry.blocked_until:
                retry_after = int(entry.blocked_until - now)
                return False, retry_after, "IP is temporarily blocked"
            
            # Clean old requests
            entry.clean_old_requests(self.windows["hour"])
            
            # Get limits
            limit_minute = self.default_ip_limits["requests_per_minute"]
            limit_hour = self.default_ip_limits["requests_per_hour"]
            
            # Check minute window
            minute_ago = now - self.windows["minute"]
            requests_last_minute = sum(1 for t in entry.requests if t > minute_ago)
            
            if requests_last_minute >= limit_minute:
                entry.blocked_until = now + 60
                return False, 60, f"IP rate limit exceeded: {limit_minute} requests per minute"
            
            # Check hour window
            if len(entry.requests) >= limit_hour:
                entry.blocked_until = now + self.windows["hour"]
                return False, self.windows["hour"], f"IP rate limit exceeded: {limit_hour} requests per hour"
            
            # Record request
            entry.requests.append(now)
            
            return True, None, None
    
    def get_user_stats(self, user_id: str) -> Dict[str, any]:
        """Get rate limit statistics for a user."""
        entry = self.user_limits[user_id]
        now = time.time()
        
        entry.clean_old_requests(self.windows["hour"])
        
        minute_ago = now - self.windows["minute"]
        requests_last_minute = sum(1 for t in entry.requests if t > minute_ago)
        
        return {
            "user_id": user_id,
            "requests_last_minute": requests_last_minute,
            "requests_last_hour": len(entry.requests),
            "limit_minute": self.default_user_limits["commands_per_minute"],
            "limit_hour": self.default_user_limits["commands_per_hour"],
            "blocked": entry.blocked_until is not None and now < entry.blocked_until,
            "blocked_until": entry.blocked_until
        }
    
    def format_rate_limit_message(
        self,
        retry_after: int,
        reason: str
    ) -> str:
        """Format a user-friendly rate limit message."""
        minutes = retry_after // 60
        seconds = retry_after % 60
        
        if minutes > 0:
            time_str = f"{minutes}m {seconds}s"
        else:
            time_str = f"{seconds}s"
        
        return (
            f"⏳ **Rate Limit Exceeded**\\n"
            f"{reason}\\n\\n"
            f"Please try again in **{time_str}**."
        )
    
    async def _cleanup_loop(self):
        """Periodic cleanup of old entries."""
        while True:
            try:
                await asyncio.sleep(300)  # Clean every 5 minutes
                
                async with self._lock:
                    now = time.time()
                    
                    # Clean user limits
                    for user_id in list(self.user_limits.keys()):
                        entry = self.user_limits[user_id]
                        entry.clean_old_requests(self.windows["hour"])
                        
                        # Remove if empty and not blocked
                        if not entry.requests and (not entry.blocked_until or now > entry.blocked_until):
                            del self.user_limits[user_id]
                    
                    # Clean IP limits
                    for ip in list(self.ip_limits.keys()):
                        entry = self.ip_limits[ip]
                        entry.clean_old_requests(self.windows["hour"])
                        
                        if not entry.requests and (not entry.blocked_until or now > entry.blocked_until):
                            del self.ip_limits[ip]
                    
                    logger.debug("Rate limiter cleanup completed")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Rate limiter cleanup error: {e}")
    
    def is_admin_exempt(self, user_id: str, admin_ids: List[str]) -> bool:
        """Check if user is admin and exempt from rate limits."""
        return user_id in admin_ids


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter
