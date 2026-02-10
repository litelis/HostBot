#!/usr/bin/env python3
"""
Web interface for HostBot.
Modern web UI with real-time capabilities.
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from loguru import logger

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.agent import Agent
from config.settings import settings


# Pydantic models for API
class CommandRequest(BaseModel):
    command: str
    use_vision: bool = False
    priority: str = "medium"


class ConfigRequest(BaseModel):
    discord_token: Optional[str] = None
    discord_admin_user_id: Optional[str] = None
    ollama_model: Optional[str] = None
    ollama_host: Optional[str] = None
    safety_mode: Optional[str] = None
    allow_desktop_control: Optional[bool] = None
    allow_system_commands: Optional[bool] = None
    allow_browser_automation: Optional[bool] = None
    allow_software_installation: Optional[bool] = None


class ConfigStatus(BaseModel):
    configured: bool
    missing: List[str]
    current_values: Dict[str, Any]



# Create FastAPI app
app = FastAPI(
    title="HostBot Web Interface",
    description="Modern web UI for HostBot autonomous agent",
    version="2.0.0"
)

# Mount static files
static_path = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Templates
templates_path = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=templates_path)

# Global agent instance
agent: Optional[Agent] = None
connected_websockets: List[WebSocket] = []


async def get_agent() -> Agent:
    """Get or initialize agent."""
    global agent
    if agent is None:
        agent = Agent()
        await agent.initialize()
    return agent


@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    logger.info("Web interface starting up...")
    # Try to auto-initialize agent if configured
    try:
        if settings.discord_token and "your_discord" not in settings.discord_token:
            await get_agent()
            logger.info("Agent auto-initialized")
    except Exception as e:
        logger.warning(f"Auto-initialization failed: {e}")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main dashboard page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    """Configuration page."""
    return templates.TemplateResponse("config.html", {"request": request})


@app.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    """Initial setup wizard page."""
    return templates.TemplateResponse("setup_wizard.html", {"request": request})


# API Routes
@app.get("/api/status")
async def api_status():
    """Get agent status."""
    try:
        agent_instance = await get_agent()
        status = agent_instance.get_status()
        return JSONResponse(content={
            "success": True,
            "status": status,
            "web_ui": True,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return JSONResponse(content={
            "success": False,
            "error": str(e),
            "web_ui": True,
            "agent_ready": False
        })


@app.get("/api/config/status")
async def config_status():
    """Check configuration status."""
    env_file = Path(".env")
    
    missing = []
    current_values = {}
    
    # Check Discord token
    if not settings.discord_token or "your_discord" in settings.discord_token:
        missing.append("discord_token")
    else:
        current_values["discord_token"] = settings.discord_token[:10] + "..."
    
    # Check Admin ID
    if not settings.discord_admin_user_id or "your_admin" in str(settings.discord_admin_user_id):
        missing.append("discord_admin_user_id")
    else:
        current_values["discord_admin_user_id"] = settings.discord_admin_user_id
    
    # Check Ollama
    current_values["ollama_model"] = settings.ollama_model
    current_values["ollama_host"] = settings.ollama_host
    
    # Other settings
    current_values["safety_mode"] = settings.safety_mode
    current_values["allow_desktop_control"] = settings.allow_desktop_control
    current_values["allow_system_commands"] = settings.allow_system_commands
    current_values["allow_browser_automation"] = settings.allow_browser_automation
    current_values["allow_software_installation"] = settings.allow_software_installation
    
    return JSONResponse(content={
        "success": True,
        "configured": len(missing) == 0,
        "missing": missing,
        "current_values": current_values
    })


@app.post("/api/config")
async def update_config(config: ConfigRequest):
    """Update configuration."""
    try:
        env_file = Path(".env")
        
        # Read current content
        if env_file.exists():
            content = env_file.read_text()
            lines = content.splitlines()
        else:
            lines = []
        
        # Build new values
        new_values = {}
        if config.discord_token:
            new_values["DISCORD_TOKEN"] = config.discord_token
        if config.discord_admin_user_id:
            new_values["DISCORD_ADMIN_USER_ID"] = config.discord_admin_user_id
        if config.ollama_model:
            new_values["OLLAMA_MODEL"] = config.ollama_model
        if config.ollama_host:
            new_values["OLLAMA_HOST"] = config.ollama_host
        if config.safety_mode:
            new_values["SAFETY_MODE"] = config.safety_mode
        if config.allow_desktop_control is not None:
            new_values["ALLOW_DESKTOP_CONTROL"] = str(config.allow_desktop_control)
        if config.allow_system_commands is not None:
            new_values["ALLOW_SYSTEM_COMMANDS"] = str(config.allow_system_commands)
        if config.allow_browser_automation is not None:
            new_values["ALLOW_BROWSER_AUTOMATION"] = str(config.allow_browser_automation)
        if config.allow_software_installation is not None:
            new_values["ALLOW_SOFTWARE_INSTALLATION"] = str(config.allow_software_installation)
        
        # Update lines
        updated_lines = []
        updated_keys = set()
        
        for line in lines:
            if "=" in line and not line.startswith("#"):
                key = line.split("=", 1)[0]
                if key in new_values:
                    updated_lines.append(f"{key}={new_values[key]}")
                    updated_keys.add(key)
                else:
                    updated_lines.append(line)
            else:
                updated_lines.append(line)
        
        # Add new keys
        for key, value in new_values.items():
            if key not in updated_keys:
                updated_lines.append(f"{key}={value}")
        
        # Write back
        env_file.write_text("\n".join(updated_lines) + "\n")
        
        return JSONResponse(content={
            "success": True,
            "message": "Configuration updated. Restart required for some changes."
        })
        
    except Exception as e:
        return JSONResponse(content={
            "success": False,
            "error": str(e)
        })


@app.post("/api/command")
async def execute_command(request: CommandRequest):
    """Execute a command."""
    try:
        agent_instance = await get_agent()
        
        # Use brain for complex commands
        if request.use_vision:
            result = await agent_instance.think_and_act(
                goal=request.command,
                priority=request.priority,
                use_vision=True
            )
        else:
            # Use traditional processing
            result = await agent_instance.process_command(
                command=request.command,
                user_id="web_ui",
                context={"source": "web"}
            )
        
        return JSONResponse(content={
            "success": True,
            "result": result
        })
        
    except Exception as e:
        logger.error(f"Command execution error: {e}")
        return JSONResponse(content={
            "success": False,
            "error": str(e)
        })


@app.get("/api/vision")
async def capture_screen():
    """Capture screen for vision."""
    try:
        agent_instance = await get_agent()
        result = await agent_instance.see()
        
        if result["success"]:
            return JSONResponse(content={
                "success": True,
                "screenshot": result["screenshot"]["base64"],
                "width": result["screenshot"]["width"],
                "height": result["screenshot"]["height"],
                "analysis": result.get("analysis", {})
            })
        else:
            return JSONResponse(content={
                "success": False,
                "error": result.get("error", "Vision failed")
            })
            
    except Exception as e:
        return JSONResponse(content={
            "success": False,
            "error": str(e)
        })


@app.post("/api/vision/analyze")
async def analyze_screen():
    """Analyze current screen."""
    try:
        agent_instance = await get_agent()
        result = await agent_instance.suggest_action("Analyze the current screen")
        
        return JSONResponse(content={
            "success": result["success"],
            "suggestion": result.get("suggestion"),
            "action_type": result.get("action_type"),
            "reasoning": result.get("reasoning")
        })
        
    except Exception as e:
        return JSONResponse(content={
            "success": False,
            "error": str(e)
        })


@app.get("/api/tasks")
async def get_tasks():
    """Get active and recent tasks."""
    try:
        agent_instance = await get_agent()
        
        # Get brain tasks if available
        brain_tasks = []
        if agent_instance.brain:
            active = agent_instance.brain.get_active_tasks()
            recent = agent_instance.brain.get_recent_tasks(10)
            
            for task in active:
                brain_tasks.append({
                    "id": task.id,
                    "goal": task.goal,
                    "status": task.status.value,
                    "priority": task.priority.value,
                    "progress": task.current_step,
                    "total_steps": len(task.plan) if task.plan else 0,
                    "active": True
                })
            
            for task in recent:
                brain_tasks.append({
                    "id": task.id,
                    "goal": task.goal,
                    "status": task.status.value,
                    "priority": task.priority.value,
                    "active": False
                })
        
        return JSONResponse(content={
            "success": True,
            "tasks": brain_tasks
        })
        
    except Exception as e:
        return JSONResponse(content={
            "success": False,
            "error": str(e)
        })


@app.post("/api/emergency-stop")
async def emergency_stop():
    """Trigger emergency stop."""
    try:
        from safety.emergency_stop import get_emergency_stop, EmergencyLevel
        
        es = get_emergency_stop()
        success = await es.trigger(
            code=settings.emergency_stop_code,
            level=EmergencyLevel.HARD,
            triggered_by="web_ui",
            reason="Emergency stop triggered from web interface"
        )
        
        return JSONResponse(content={
            "success": success,
            "message": "Emergency stop triggered" if success else "Failed to trigger"
        })
        
    except Exception as e:
        return JSONResponse(content={
            "success": False,
            "error": str(e)
        })


@app.post("/api/emergency-reset")
async def emergency_reset():
    """Reset emergency stop."""
    try:
        from safety.emergency_stop import get_emergency_stop
        
        es = get_emergency_stop()
        success = await es.reset(
            code=settings.emergency_stop_code,
            reset_by="web_ui"
        )
        
        return JSONResponse(content={
            "success": success,
            "message": "Emergency stop reset" if success else "Failed to reset"
        })
        
    except Exception as e:
        return JSONResponse(content={
            "success": False,
            "error": str(e)
        })


# WebSocket for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time communication."""
    await websocket.accept()
    connected_websockets.append(websocket)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            action = message.get("action")
            
            if action == "ping":
                await websocket.send_json({"type": "pong"})
            
            elif action == "get_status":
                agent_instance = await get_agent()
                status = agent_instance.get_status()
                await websocket.send_json({
                    "type": "status",
                    "data": status
                })
            
            elif action == "capture_screen":
                agent_instance = await get_agent()
                result = await agent_instance.see()
                if result["success"]:
                    await websocket.send_json({
                        "type": "screenshot",
                        "data": {
                            "image": result["screenshot"]["base64"],
                            "analysis": result.get("analysis", {})
                        }
                    })
            
            elif action == "execute_command":
                command = message.get("command", "")
                use_vision = message.get("use_vision", False)
                
                agent_instance = await get_agent()
                
                if use_vision:
                    result = await agent_instance.think_and_act(
                        goal=command,
                        priority="medium",
                        use_vision=True
                    )
                else:
                    result = await agent_instance.process_command(
                        command=command,
                        user_id="web_ui",
                        context={"source": "websocket"}
                    )
                
                await websocket.send_json({
                    "type": "command_result",
                    "data": result
                })
    
    except WebSocketDisconnect:
        connected_websockets.remove(websocket)
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if websocket in connected_websockets:
            connected_websockets.remove(websocket)


async def broadcast_message(message: Dict):
    """Broadcast message to all connected websockets."""
    disconnected = []
    for ws in connected_websockets:
        try:
            await ws.send_json(message)
        except:
            disconnected.append(ws)
    
    # Remove disconnected
    for ws in disconnected:
        if ws in connected_websockets:
            connected_websockets.remove(ws)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
