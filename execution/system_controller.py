"""System controller for OS commands, file operations, and process management."""

import asyncio
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import psutil
from loguru import logger

from safety.audit_logger import get_audit_logger, ActionType
from safety.emergency_stop import get_emergency_stop


class SystemController:
    """Controller for system-level operations."""
    
    def __init__(self):
        self.audit = get_audit_logger()
        self.emergency = get_emergency_stop()
        self.os_type = platform.system().lower()
        
        logger.info(f"System controller initialized ({platform.system()})")
    
    async def execute_command(
        self,
        command: Union[str, List[str]],
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: int = 60,
        shell: bool = True,
        capture_output: bool = True
    ) -> Dict[str, Any]:
        """
        Execute a system command.
        
        Args:
            command: Command string or list of arguments
            cwd: Working directory for command
            env: Environment variables
            timeout: Timeout in seconds
            shell: Whether to use shell execution
            capture_output: Whether to capture stdout/stderr
            
        Returns:
            Dictionary with returncode, stdout, stderr, and success status
        """
        # Check emergency stop
        if self.emergency.check_stop():
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": "Emergency stop is active",
                "command": command if isinstance(command, str) else " ".join(command)
            }
        
        cmd_str = command if isinstance(command, str) else " ".join(command)
        
        # Start audit
        op_id = self.audit.start_operation(
            action_type=ActionType.SYSTEM_COMMAND,
            description=f"Execute command: {cmd_str[:100]}",
            command=cmd_str
        )
        
        try:
            logger.info(f"Executing command: {cmd_str[:100]}...")
            
            # Prepare environment
            process_env = os.environ.copy()
            if env:
                process_env.update(env)
            
            # Execute command
            if shell and isinstance(command, list):
                command = " ".join(command)
            
            process = await asyncio.create_subprocess_shell(
                cmd_str if shell else command,
                stdout=asyncio.subprocess.PIPE if capture_output else None,
                stderr=asyncio.subprocess.PIPE if capture_output else None,
                cwd=cwd,
                env=process_env
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
                
                stdout_str = stdout.decode('utf-8', errors='replace') if stdout else ""
                stderr_str = stderr.decode('utf-8', errors='replace') if stderr else ""
                
                result = {
                    "success": process.returncode == 0,
                    "returncode": process.returncode,
                    "stdout": stdout_str,
                    "stderr": stderr_str,
                    "command": cmd_str
                }
                
                if process.returncode == 0:
                    self.audit.complete_operation(op_id, result)
                    logger.info(f"Command completed successfully (code {process.returncode})")
                else:
                    self.audit.fail_operation(op_id, f"Exit code {process.returncode}: {stderr_str[:200]}")
                    logger.warning(f"Command failed with code {process.returncode}")
                
                return result
                
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                
                error_msg = f"Command timed out after {timeout} seconds"
                self.audit.fail_operation(op_id, error_msg)
                logger.error(error_msg)
                
                return {
                    "success": False,
                    "returncode": -1,
                    "stdout": "",
                    "stderr": error_msg,
                    "command": cmd_str
                }
                
        except Exception as e:
            error_msg = str(e)
            self.audit.fail_operation(op_id, error_msg)
            logger.error(f"Command execution error: {error_msg}")
            
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": error_msg,
                "command": cmd_str
            }
    
    async def read_file(
        self,
        path: Union[str, Path],
        encoding: str = 'utf-8',
        limit_bytes: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Read contents of a file.
        
        Args:
            path: File path
            encoding: File encoding
            limit_bytes: Maximum bytes to read
            
        Returns:
            Dictionary with content, success status, and metadata
        """
        path = Path(path)
        
        op_id = self.audit.start_operation(
            action_type=ActionType.FILE_OPERATION,
            description=f"Read file: {path}",
            parameters={"path": str(path), "encoding": encoding}
        )
        
        try:
            if not path.exists():
                raise FileNotFoundError(f"File not found: {path}")
            
            if not path.is_file():
                raise ValueError(f"Path is not a file: {path}")
            
            # Check file size
            file_size = path.stat().st_size
            if limit_bytes and file_size > limit_bytes:
                raise ValueError(f"File too large ({file_size} bytes), limit is {limit_bytes}")
            
            # Read file
            content = path.read_text(encoding=encoding)
            
            result = {
                "success": True,
                "content": content,
                "path": str(path),
                "size": len(content),
                "encoding": encoding
            }
            
            self.audit.complete_operation(op_id, {"size": len(content)})
            logger.info(f"Read file: {path} ({len(content)} chars)")
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            self.audit.fail_operation(op_id, error_msg)
            logger.error(f"File read error: {error_msg}")
            
            return {
                "success": False,
                "content": "",
                "path": str(path),
                "error": error_msg
            }
    
    async def write_file(
        self,
        path: Union[str, Path],
        content: str,
        encoding: str = 'utf-8',
        append: bool = False
    ) -> Dict[str, Any]:
        """
        Write content to a file.
        
        Args:
            path: File path
            content: Content to write
            encoding: File encoding
            append: Whether to append instead of overwrite
            
        Returns:
            Dictionary with success status and metadata
        """
        path = Path(path)
        
        op_id = self.audit.start_operation(
            action_type=ActionType.FILE_OPERATION,
            description=f"{'Append to' if append else 'Write'} file: {path}",
            parameters={"path": str(path), "encoding": encoding, "append": append}
        )
        
        try:
            # Create parent directories if needed
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            mode = 'a' if append else 'w'
            path.write_text(content, encoding=encoding)
            
            result = {
                "success": True,
                "path": str(path),
                "bytes_written": len(content.encode(encoding)),
                "operation": "append" if append else "write"
            }
            
            self.audit.complete_operation(op_id, result)
            logger.info(f"Wrote file: {path} ({result['bytes_written']} bytes)")
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            self.audit.fail_operation(op_id, error_msg)
            logger.error(f"File write error: {error_msg}")
            
            return {
                "success": False,
                "path": str(path),
                "error": error_msg
            }
    
    async def delete_file(
        self,
        path: Union[str, Path],
        recursive: bool = False
    ) -> Dict[str, Any]:
        """
        Delete a file or directory.
        
        Args:
            path: Path to delete
            recursive: Whether to recursively delete directories
            
        Returns:
            Dictionary with success status
        """
        path = Path(path)
        
        op_id = self.audit.start_operation(
            action_type=ActionType.FILE_OPERATION,
            description=f"Delete: {path}",
            parameters={"path": str(path), "recursive": recursive}
        )
        
        try:
            if not path.exists():
                raise FileNotFoundError(f"Path not found: {path}")
            
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                if recursive:
                    shutil.rmtree(path)
                else:
                    path.rmdir()  # Will fail if not empty
            
            result = {
                "success": True,
                "path": str(path),
                "type": "directory" if path.is_dir() else "file"
            }
            
            self.audit.complete_operation(op_id, result)
            logger.info(f"Deleted: {path}")
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            self.audit.fail_operation(op_id, error_msg)
            logger.error(f"Delete error: {error_msg}")
            
            return {
                "success": False,
                "path": str(path),
                "error": error_msg
            }
    
    async def list_directory(
        self,
        path: Union[str, Path] = ".",
        pattern: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List contents of a directory.
        
        Args:
            path: Directory path
            pattern: Optional glob pattern to filter
            
        Returns:
            Dictionary with file list and metadata
        """
        path = Path(path)
        
        try:
            if not path.exists():
                raise FileNotFoundError(f"Directory not found: {path}")
            
            if not path.is_dir():
                raise ValueError(f"Path is not a directory: {path}")
            
            if pattern:
                items = list(path.glob(pattern))
            else:
                items = list(path.iterdir())
            
            files = []
            directories = []
            
            for item in items:
                stat = item.stat()
                entry = {
                    "name": item.name,
                    "path": str(item),
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "is_file": item.is_file(),
                    "is_dir": item.is_dir()
                }
                
                if item.is_file():
                    files.append(entry)
                else:
                    directories.append(entry)
            
            result = {
                "success": True,
                "path": str(path),
                "files": files,
                "directories": directories,
                "total_count": len(files) + len(directories)
            }
            
            logger.info(f"Listed directory: {path} ({result['total_count']} items)")
            return result
            
        except Exception as e:
            logger.error(f"Directory list error: {e}")
            return {
                "success": False,
                "path": str(path),
                "error": str(e),
                "files": [],
                "directories": []
            }
    
    async def get_processes(self) -> Dict[str, Any]:
        """
        Get list of running processes.
        
        Returns:
            Dictionary with process list
        """
        try:
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent', 'status']):
                try:
                    info = proc.info
                    info['created'] = proc.create_time()
                    processes.append(info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            return {
                "success": True,
                "processes": processes,
                "count": len(processes)
            }
            
        except Exception as e:
            logger.error(f"Process list error: {e}")
            return {
                "success": False,
                "error": str(e),
                "processes": []
            }
    
    async def kill_process(
        self,
        pid: int,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Kill a process by PID.
        
        Args:
            pid: Process ID
            force: Whether to force kill
            
        Returns:
            Dictionary with success status
        """
        op_id = self.audit.start_operation(
            action_type=ActionType.PROCESS_MANAGEMENT,
            description=f"Kill process {pid}",
            parameters={"pid": pid, "force": force}
        )
        
        try:
            process = psutil.Process(pid)
            name = process.name()
            
            if force:
                process.kill()
            else:
                process.terminate()
            
            # Wait for process to terminate
            gone, alive = psutil.wait_procs([process], timeout=3)
            
            if process in alive:
                # Force kill if still alive
                process.kill()
            
            result = {
                "success": True,
                "pid": pid,
                "name": name,
                "force": force
            }
            
            self.audit.complete_operation(op_id, result)
            logger.info(f"Killed process {pid} ({name})")
            
            return result
            
        except psutil.NoSuchProcess:
            error_msg = f"Process {pid} not found"
            self.audit.fail_operation(op_id, error_msg)
            return {"success": False, "error": error_msg}
        except Exception as e:
            error_msg = str(e)
            self.audit.fail_operation(op_id, error_msg)
            logger.error(f"Kill process error: {error_msg}")
            return {"success": False, "error": error_msg}
    
    async def get_system_info(self) -> Dict[str, Any]:
        """
        Get system information.
        
        Returns:
            Dictionary with system details
        """
        try:
            info = {
                "platform": platform.platform(),
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "hostname": platform.node(),
                "cpu_count": psutil.cpu_count(),
                "memory": {
                    "total": psutil.virtual_memory().total,
                    "available": psutil.virtual_memory().available,
                    "percent": psutil.virtual_memory().percent
                },
                "disk": {
                    "total": psutil.disk_usage('/').total,
                    "used": psutil.disk_usage('/').used,
                    "free": psutil.disk_usage('/').free,
                    "percent": psutil.disk_usage('/').percent
                },
                "boot_time": psutil.boot_time()
            }
            
            return {
                "success": True,
                "info": info
            }
            
        except Exception as e:
            logger.error(f"System info error: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# Global system controller instance
_system_controller: Optional[SystemController] = None


def get_system_controller() -> SystemController:
    """Get or create global system controller instance."""
    global _system_controller
    if _system_controller is None:
        _system_controller = SystemController()
    return _system_controller
