"""Discord client for the autonomous agent."""

import asyncio
from typing import Any, Dict, Optional

import discord
from discord.ext import commands
from loguru import logger

from config.settings import settings
from core.agent import Agent
from safety.confirmation_manager import ConfirmationManager, ConfirmationRequest, ConfirmationLevel
from safety.emergency_stop import get_emergency_stop
from security.rate_limiter import get_rate_limiter, RateLimiter
from security.input_validator import get_input_validator, InputValidator, InputType, ValidationError
from security.secure_config import get_secure_config



class DiscordClient(commands.Bot):
    """Discord bot client for the autonomous agent."""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True
        
        super().__init__(
            command_prefix=settings.discord_command_prefix,
            intents=intents,
            help_command=None
        )
        
        self.agent: Optional[Agent] = None
        self.confirmation_manager: Optional[ConfirmationManager] = None
        self.rate_limiter: Optional[RateLimiter] = None
        self.input_validator: Optional[InputValidator] = None
        
        logger.info("Discord client initialized")

    
    async def setup_hook(self):
        """Setup hook called before the bot starts."""
        # Initialize security components
        self.rate_limiter = get_rate_limiter()
        await self.rate_limiter.start()
        
        self.input_validator = get_input_validator()
        
        # Validate no hardcoded keys
        secure_config = get_secure_config()
        secure_config.scan_project_for_keys(".")
        
        # Initialize agent
        self.agent = Agent()
        await self.agent.initialize()
        
        # Register confirmation handler
        if self.agent.confirmation_manager:
            self.agent.confirmation_manager.register_event_handler(
                self._handle_confirmation_request
            )
        
        logger.info("Discord client setup complete")

    
    async def on_ready(self):
        """Called when the bot is ready."""
        logger.info(f"Discord bot logged in as {self.user} (ID: {self.user.id})")
        
        # Set status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="for commands | !help"
            )
        )
        
        # Send startup message to admin if possible
        try:
            admin_user = await self.fetch_user(settings.discord_admin_user_id)
            if admin_user:
                await admin_user.send(
                    f"🟢 **Agent Online**\\n"
                    f"Name: {settings.agent_name}\\n"
                    f"Safety Mode: {settings.safety_mode}\\n"
                    f"Use `!help` for available commands"
                )
        except Exception as e:
            logger.warning(f"Could not send startup message to admin: {e}")
    
    async def on_message(self, message: discord.Message):
        """Handle incoming messages."""
        # Ignore own messages
        if message.author == self.user:
            return
        
        # Rate limiting check
        if self.rate_limiter and not self.rate_limiter.is_admin_exempt(
            str(message.author.id), 
            [str(settings.discord_admin_user_id)]
        ):
            allowed, retry_after, reason = await self.rate_limiter.check_user_limit(
                str(message.author.id),
                action_type="standard"
            )
            
            if not allowed:
                await message.channel.send(
                    self.rate_limiter.format_rate_limit_message(retry_after, reason)
                )
                return
        
        # Validate command input
        if self.input_validator and message.content.startswith(settings.discord_command_prefix):
            try:
                sanitized = self.input_validator.validate_discord_command(message.content)
                # Replace message content with sanitized version
                message.content = sanitized
            except ValidationError as e:
                await message.channel.send(f"❌ **Invalid input**: {e.message}")
                return
        
        # Process commands
        await self.process_commands(message)

    
    async def _handle_confirmation_request(self, request: ConfirmationRequest) -> None:
        """Handle confirmation requests by sending Discord message."""
        try:
            # Get admin user
            admin_user = await self.fetch_user(settings.discord_admin_user_id)
            if not admin_user:
                logger.error("Admin user not found for confirmation")
                return
            
            # Format message
            message = self._format_confirmation_message(request)
            
            # Send DM to admin
            await admin_user.send(message)
            
            logger.info(f"Confirmation request sent to admin: {request.id}")
            
        except Exception as e:
            logger.error(f"Failed to send confirmation request: {e}")
    
    def _format_confirmation_message(self, request: ConfirmationRequest) -> str:
        """Format a confirmation request for Discord."""
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
    
    # Commands
    @commands.command(name="help")
    async def help_command(self, ctx: commands.Context):
        """Show help message."""
        help_text = """
**🤖 Autonomous OS Control Agent - Commands**

**Basic Commands:**
`!status` - Check agent status
`!execute <command>` - Execute a system command
`!ask <question>` - Ask the AI a question

**Control Commands:**
`!stop <code>` - Emergency stop (requires code)
`!reset <code>` - Reset emergency stop
`!confirm <id>` - Confirm a pending action
`!deny <id>` - Deny a pending action

**Information Commands:**
`!system` - Show system information
`!processes` - List running processes
`!plans` - Show active execution plans
`!history` - Show recent activity

**Desktop Commands:**
`!screenshot` - Take a screenshot
`!mouse <x> <y>` - Move mouse to position
`!click [x] [y]` - Click at position (or current)
`!type <text>` - Type text

**Browser Commands:**
`!browse <url>` - Open browser and navigate
`!browser_click <selector>` - Click element
`!browser_type <selector> <text>` - Type in element

**Software Commands:**
`!install <package>` - Install software
`!uninstall <package>` - Uninstall software
`!search <query>` - Search for software

**Safety Commands:**
`!safety` - Show safety status
`!mode <strict|moderate|minimal>` - Change safety mode

Use `!help <command>` for detailed help on a specific command.
        """
        await ctx.send(help_text)
    
    @commands.command(name="status")
    async def status_command(self, ctx: commands.Context):
        """Check agent status."""
        if not self.agent:
            await ctx.send("❌ Agent not initialized")
            return
        
        status = self.agent.get_status()
        
        embed = discord.Embed(
            title=f"🤖 {settings.agent_name} Status",
            color=discord.Color.green() if status["healthy"] else discord.Color.red()
        )
        
        embed.add_field(name="State", value=status["state"], inline=True)
        embed.add_field(name="Safety Mode", value=status["safety_mode"], inline=True)
        embed.add_field(name="Emergency Stop", value="🚨 Active" if status["emergency_stop"] else "✅ Clear", inline=True)
        
        embed.add_field(name="Active Plans", value=str(status["active_plans"]), inline=True)
        embed.add_field(name="Pending Confirmations", value=str(status["pending_confirmations"]), inline=True)
        embed.add_field(name="Session Operations", value=str(status["session_operations"]), inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="execute")
    async def execute_command(self, ctx: commands.Context, *, command: str):
        """Execute a system command."""
        if not self.agent:
            await ctx.send("❌ Agent not initialized")
            return
        
        # Check if user is authorized
        if ctx.author.id != settings.discord_admin_user_id:
            await ctx.send("⛔ You are not authorized to execute commands")
            return
        
        # Rate limit check for critical action
        allowed, retry_after, reason = await self.rate_limiter.check_user_limit(
            str(ctx.author.id),
            action_type="critical"
        )
        if not allowed:
            await ctx.send(self.rate_limiter.format_rate_limit_message(retry_after, reason))
            return
        
        # Validate command input
        try:
            command = self.input_validator.validate(command, InputType.COMMAND, "command")
        except ValidationError as e:
            await ctx.send(f"❌ **Invalid command**: {e.message}")
            return
        
        await ctx.send(f"🔄 Executing: `{command[:100]}`")

        
        try:
            result = await self.agent.execute_system_command(
                command,
                user_id=str(ctx.author.id)
            )
            
            if result["success"]:
                output = result.get("stdout", "")[:1500]  # Discord limit
                if output:
                    await ctx.send(f"✅ **Success**\\n```\\n{output}\\n```")
                else:
                    await ctx.send("✅ **Success** (no output)")
            else:
                error = result.get("stderr", result.get("error", "Unknown error"))[:1500]
                await ctx.send(f"❌ **Failed**\\n```\\n{error}\\n```")
                
        except Exception as e:
            await ctx.send(f"❌ **Error**: {str(e)}")
    
    @commands.command(name="ask")
    async def ask_command(self, ctx: commands.Context, *, question: str):
        """Ask the AI a question."""
        if not self.agent:
            await ctx.send("❌ Agent not initialized")
            return
        
        await ctx.send("🤔 Thinking...")
        
        try:
            response = await self.agent.ask_ai(question)
            await ctx.send(f"🤖 **AI Response**:\\n{response[:1900]}")
        except Exception as e:
            await ctx.send(f"❌ **Error**: {str(e)}")
    
    @commands.command(name="stop")
    async def stop_command(self, ctx: commands.Context, code: str):
        """Emergency stop."""
        # Validate code input
        try:
            code = self.input_validator.validate(code, InputType.TEXT, "code", max_length=50)
        except ValidationError as e:
            await ctx.send(f"❌ **Invalid code**: {e.message}")
            return
        
        # Rate limit check for emergency action
        allowed, retry_after, reason = await self.rate_limiter.check_user_limit(
            str(ctx.author.id),
            action_type="critical"
        )
        if not allowed:
            await ctx.send(self.rate_limiter.format_rate_limit_message(retry_after, reason))
            return
        
        emergency = get_emergency_stop()
        
        success = await emergency.trigger(
            code=code,
            triggered_by=str(ctx.author.id),
            reason=f"Emergency stop triggered by {ctx.author.name}"
        )
        
        if success:
            await ctx.send("🚨 **EMERGENCY STOP TRIGGERED**\\nAll operations halted.")
        else:
            await ctx.send("❌ Invalid code or already stopped")

    
    @commands.command(name="reset")
    async def reset_command(self, ctx: commands.Context, code: str):
        """Reset emergency stop."""
        # Validate code input
        try:
            code = self.input_validator.validate(code, InputType.TEXT, "code", max_length=50)
        except ValidationError as e:
            await ctx.send(f"❌ **Invalid code**: {e.message}")
            return
        
        emergency = get_emergency_stop()
        
        success = await emergency.reset(code, str(ctx.author.id))
        
        if success:
            await ctx.send("🟢 **Emergency stop reset**\\nOperations can resume.")
        else:
            await ctx.send("❌ Invalid code or not stopped")

    
    @commands.command(name="confirm")
    async def confirm_command(self, ctx: commands.Context, request_id: str):
        """Confirm a pending action."""
        if not self.agent or not self.agent.confirmation_manager:
            await ctx.send("❌ Agent not initialized")
            return
        
        # Validate request_id
        try:
            request_id = self.input_validator.validate(request_id, InputType.TEXT, "request_id", max_length=100)
        except ValidationError as e:
            await ctx.send(f"❌ **Invalid request ID**: {e.message}")
            return
        
        success = await self.agent.confirmation_manager.respond_to_confirmation(
            request_id=request_id,
            approved=True,
            user_id=str(ctx.author.id),
            message=f"Approved by {ctx.author.name}"
        )
        
        if success:
            await ctx.send(f"✅ Confirmation `{request_id}` approved")
        else:
            await ctx.send(f"❌ Confirmation `{request_id}` not found or unauthorized")

    
    @commands.command(name="deny")
    async def deny_command(self, ctx: commands.Context, request_id: str):
        """Deny a pending action."""
        if not self.agent or not self.agent.confirmation_manager:
            await ctx.send("❌ Agent not initialized")
            return
        
        # Validate request_id
        try:
            request_id = self.input_validator.validate(request_id, InputType.TEXT, "request_id", max_length=100)
        except ValidationError as e:
            await ctx.send(f"❌ **Invalid request ID**: {e.message}")
            return
        
        success = await self.agent.confirmation_manager.respond_to_confirmation(
            request_id=request_id,
            approved=False,
            user_id=str(ctx.author.id),
            message=f"Denied by {ctx.author.name}"
        )
        
        if success:
            await ctx.send(f"❌ Confirmation `{request_id}` denied")
        else:
            await ctx.send(f"❌ Confirmation `{request_id}` not found or unauthorized")

    
    @commands.command(name="system")
    async def system_command(self, ctx: commands.Context):
        """Show system information."""
        if not self.agent:
            await ctx.send("❌ Agent not initialized")
            return
        
        try:
            info = await self.agent.get_system_info()
            
            if info["success"]:
                embed = discord.Embed(
                    title="💻 System Information",
                    color=discord.Color.blue()
                )
                
                sys_info = info["info"]
                embed.add_field(name="Platform", value=sys_info.get("platform", "Unknown"), inline=False)
                embed.add_field(name="Processor", value=sys_info.get("processor", "Unknown"), inline=True)
                embed.add_field(name="CPU Cores", value=str(sys_info.get("cpu_count", "Unknown")), inline=True)
                
                memory = sys_info.get("memory", {})
                embed.add_field(
                    name="Memory",
                    value=f"{memory.get('percent', 0)}% used",
                    inline=True
                )
                
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"❌ Failed to get system info: {info.get('error', 'Unknown error')}")
                
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}")
    
    @commands.command(name="screenshot")
    async def screenshot_command(self, ctx: commands.Context):
        """Take a screenshot."""
        if not self.agent:
            await ctx.send("❌ Agent not initialized")
            return
        
        # Check authorization
        if ctx.author.id != settings.discord_admin_user_id:
            await ctx.send("⛔ Not authorized")
            return
        
        await ctx.send("📸 Taking screenshot...")
        
        try:
            result = await self.agent.take_screenshot()
            
            if result["success"]:
                await ctx.send(f"✅ Screenshot taken: {result['size']}")
            else:
                await ctx.send(f"❌ Failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}")
    
    @commands.command(name="safety")
    async def safety_command(self, ctx: commands.Context):
        """Show safety status."""
        from safety.permission_guard import get_permission_guard
        
        guard = get_permission_guard()
        status = guard.get_status()
        
        embed = discord.Embed(
            title="🛡️ Safety Status",
            color=discord.Color.orange()
        )
        
        embed.add_field(name="Safety Mode", value=settings.safety_mode, inline=True)
        embed.add_field(name="Permission Rules", value=str(status["total_rules"]), inline=True)
        embed.add_field(name="Admin Users", value=str(status["admin_users"]), inline=True)
        
        embed.add_field(
            name="Desktop Control",
            value="✅ Enabled" if status["desktop_control"] else "❌ Disabled",
            inline=True
        )
        embed.add_field(
            name="System Commands",
            value="✅ Enabled" if status["system_commands"] else "❌ Disabled",
            inline=True
        )
        embed.add_field(
            name="Browser Automation",
            value="✅ Enabled" if status["browser_automation"] else "❌ Disabled",
            inline=True
        )
        
        await ctx.send(embed=embed)


# Global Discord client instance
_discord_client: Optional[DiscordClient] = None


def get_discord_client() -> DiscordClient:
    """Get or create global Discord client instance."""
    global _discord_client
    if _discord_client is None:
        _discord_client = DiscordClient()
    return _discord_client
