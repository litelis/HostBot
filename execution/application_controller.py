"""Application controller for software installation and management."""

import asyncio
import platform
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from execution.system_controller import get_system_controller
from safety.audit_logger import get_audit_logger, ActionType
from safety.emergency_stop import get_emergency_stop


class ApplicationController:
    """Controller for software installation and management."""
    
    def __init__(self):
        self.audit = get_audit_logger()
        self.emergency = get_emergency_stop()
        self.system = get_system_controller()
        self.os_type = platform.system().lower()
        
        # Package managers by OS
        self.package_managers = {
            "windows": ["winget", "choco", "scoop"],
            "linux": ["apt", "yum", "dnf", "pacman", "snap", "flatpak"],
            "darwin": ["brew", "port"]
        }
        
        logger.info(f"Application controller initialized ({platform.system()})")
    
    def _check_emergency(self) -> bool:
        """Check if emergency stop is active."""
        if self.emergency.check_stop():
            logger.warning("Application action blocked - emergency stop active")
            return True
        return False
    
    async def detect_package_manager(self) -> Optional[str]:
        """Detect available package manager."""
        available = []
        
        for pm in self.package_managers.get(self.os_type, []):
            result = await self.system.execute_command(f"which {pm}" if self.os_type != "windows" else f"where {pm}")
            if result["success"]:
                available.append(pm)
        
        # Prefer certain package managers
        preferred = {
            "windows": ["winget", "choco", "scoop"],
            "linux": ["apt", "dnf", "yum", "pacman", "snap", "flatpak"],
            "darwin": ["brew", "port"]
        }
        
        for pm in preferred.get(self.os_type, []):
            if pm in available:
                return pm
        
        return available[0] if available else None
    
    async def install_software(
        self,
        package_name: str,
        package_manager: Optional[str] = None,
        version: Optional[str] = None,
        silent: bool = True
    ) -> Dict[str, Any]:
        """
        Install software using package manager.
        
        Args:
            package_name: Name of package to install
            package_manager: Specific package manager to use
            version: Specific version to install
            silent: Whether to run silently
            
        Returns:
            Installation result
        """
        if self._check_emergency():
            return {"success": False, "error": "Emergency stop active"}
        
        op_id = self.audit.start_operation(
            action_type=ActionType.SOFTWARE_INSTALL,
            description=f"Install {package_name}",
            parameters={
                "package": package_name,
                "version": version,
                "package_manager": package_manager
            }
        )
        
        try:
            # Auto-detect package manager if not specified
            if not package_manager:
                package_manager = await self.detect_package_manager()
                if not package_manager:
                    raise RuntimeError("No package manager detected")
            
            # Build install command based on package manager
            cmd = self._build_install_command(package_manager, package_name, version, silent)
            
            logger.info(f"Installing {package_name} using {package_manager}")
            result = await self.system.execute_command(cmd, timeout=300)
            
            if result["success"]:
                self.audit.complete_operation(op_id, {
                    "package": package_name,
                    "package_manager": package_manager
                })
                logger.info(f"Successfully installed {package_name}")
            else:
                self.audit.fail_operation(op_id, result.get("stderr", "Installation failed"))
                logger.error(f"Failed to install {package_name}: {result.get('stderr', 'Unknown error')}")
            
            return {
                "success": result["success"],
                "package": package_name,
                "package_manager": package_manager,
                "version": version,
                "output": result.get("stdout", ""),
                "error": result.get("stderr", "") if not result["success"] else None
            }
            
        except Exception as e:
            error_msg = str(e)
            self.audit.fail_operation(op_id, error_msg)
            logger.error(f"Installation error: {error_msg}")
            
            return {
                "success": False,
                "package": package_name,
                "error": error_msg
            }
    
    async def uninstall_software(
        self,
        package_name: str,
        package_manager: Optional[str] = None,
        silent: bool = True
    ) -> Dict[str, Any]:
        """
        Uninstall software using package manager.
        
        Args:
            package_name: Name of package to uninstall
            package_manager: Specific package manager to use
            silent: Whether to run silently
            
        Returns:
            Uninstallation result
        """
        if self._check_emergency():
            return {"success": False, "error": "Emergency stop active"}
        
        op_id = self.audit.start_operation(
            action_type=ActionType.SOFTWARE_INSTALL,
            description=f"Uninstall {package_name}",
            parameters={"package": package_name, "package_manager": package_manager}
        )
        
        try:
            # Auto-detect package manager if not specified
            if not package_manager:
                package_manager = await self.detect_package_manager()
                if not package_manager:
                    raise RuntimeError("No package manager detected")
            
            # Build uninstall command
            cmd = self._build_uninstall_command(package_manager, package_name, silent)
            
            logger.info(f"Uninstalling {package_name} using {package_manager}")
            result = await self.system.execute_command(cmd, timeout=120)
            
            if result["success"]:
                self.audit.complete_operation(op_id, {
                    "package": package_name,
                    "package_manager": package_manager
                })
                logger.info(f"Successfully uninstalled {package_name}")
            else:
                self.audit.fail_operation(op_id, result.get("stderr", "Uninstallation failed"))
                logger.error(f"Failed to uninstall {package_name}")
            
            return {
                "success": result["success"],
                "package": package_name,
                "package_manager": package_manager,
                "output": result.get("stdout", ""),
                "error": result.get("stderr", "") if not result["success"] else None
            }
            
        except Exception as e:
            error_msg = str(e)
            self.audit.fail_operation(op_id, error_msg)
            logger.error(f"Uninstallation error: {error_msg}")
            
            return {
                "success": False,
                "package": package_name,
                "error": error_msg
            }
    
    async def search_software(
        self,
        query: str,
        package_manager: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search for available software packages.
        
        Args:
            query: Search query
            package_manager: Specific package manager to use
            
        Returns:
            Search results
        """
        try:
            # Auto-detect package manager if not specified
            if not package_manager:
                package_manager = await self.detect_package_manager()
                if not package_manager:
                    raise RuntimeError("No package manager detected")
            
            # Build search command
            cmd = self._build_search_command(package_manager, query)
            
            result = await self.system.execute_command(cmd, timeout=60)
            
            # Parse results based on package manager
            packages = self._parse_search_results(package_manager, result.get("stdout", ""))
            
            return {
                "success": result["success"],
                "query": query,
                "package_manager": package_manager,
                "packages": packages,
                "count": len(packages)
            }
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            return {
                "success": False,
                "query": query,
                "error": str(e),
                "packages": []
            }
    
    async def list_installed_software(self) -> Dict[str, Any]:
        """
        List installed software packages.
        
        Returns:
            List of installed packages
        """
        try:
            package_manager = await self.detect_package_manager()
            if not package_manager:
                # Fallback to system-specific methods
                if self.os_type == "windows":
                    return await self._list_windows_software()
                else:
                    return {"success": False, "error": "No package manager available"}
            
            cmd = self._build_list_command(package_manager)
            result = await self.system.execute_command(cmd, timeout=60)
            
            packages = self._parse_list_results(package_manager, result.get("stdout", ""))
            
            return {
                "success": result["success"],
                "package_manager": package_manager,
                "packages": packages,
                "count": len(packages)
            }
            
        except Exception as e:
            logger.error(f"List software error: {e}")
            return {
                "success": False,
                "error": str(e),
                "packages": []
            }
    
    async def update_software(
        self,
        package_name: Optional[str] = None,
        package_manager: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update software packages.
        
        Args:
            package_name: Specific package to update (None for all)
            package_manager: Specific package manager to use
            
        Returns:
            Update result
        """
        if self._check_emergency():
            return {"success": False, "error": "Emergency stop active"}
        
        op_id = self.audit.start_operation(
            action_type=ActionType.SOFTWARE_INSTALL,
            description=f"Update {package_name or 'all packages'}",
            parameters={"package": package_name}
        )
        
        try:
            if not package_manager:
                package_manager = await self.detect_package_manager()
                if not package_manager:
                    raise RuntimeError("No package manager detected")
            
            cmd = self._build_update_command(package_manager, package_name)
            
            result = await self.system.execute_command(cmd, timeout=300)
            
            if result["success"]:
                self.audit.complete_operation(op_id, {"package": package_name})
                logger.info(f"Update completed for {package_name or 'all packages'}")
            else:
                self.audit.fail_operation(op_id, result.get("stderr", "Update failed"))
            
            return {
                "success": result["success"],
                "package": package_name,
                "package_manager": package_manager,
                "output": result.get("stdout", ""),
                "error": result.get("stderr", "") if not result["success"] else None
            }
            
        except Exception as e:
            error_msg = str(e)
            self.audit.fail_operation(op_id, error_msg)
            logger.error(f"Update error: {error_msg}")
            
            return {
                "success": False,
                "package": package_name,
                "error": error_msg
            }
    
    def _build_install_command(
        self,
        package_manager: str,
        package: str,
        version: Optional[str],
        silent: bool
    ) -> str:
        """Build install command for package manager."""
        commands = {
            "winget": f"winget install {package} {'--silent' if silent else ''} {'-v ' + version if version else ''} --accept-package-agreements --accept-source-agreements",
            "choco": f"choco install {package} {'-y' if silent else ''} {'--version=' + version if version else ''}",
            "scoop": f"scoop install {package}{'@' + version if version else ''}",
            "apt": f"sudo apt install {package}{'=' + version if version else ''} -y",
            "yum": f"sudo yum install {package}{'-' + version if version else ''} -y",
            "dnf": f"sudo dnf install {package}{'-' + version if version else ''} -y",
            "pacman": f"sudo pacman -S {package}{'=' + version if version else ''} --noconfirm",
            "snap": f"sudo snap install {package}{' --channel=' + version if version else ''}",
            "flatpak": f"flatpak install {package}{'//'+version if version else ''} -y",
            "brew": f"brew install {package}{'@' + version if version else ''}",
            "port": f"sudo port install {package}{' @' + version if version else ''}"
        }
        return commands.get(package_manager, f"{package_manager} install {package}")
    
    def _build_uninstall_command(
        self,
        package_manager: str,
        package: str,
        silent: bool
    ) -> str:
        """Build uninstall command for package manager."""
        commands = {
            "winget": f"winget uninstall {package} {'--silent' if silent else ''}",
            "choco": f"choco uninstall {package} {'-y' if silent else ''}",
            "scoop": f"scoop uninstall {package}",
            "apt": f"sudo apt remove {package} -y",
            "yum": f"sudo yum remove {package} -y",
            "dnf": f"sudo dnf remove {package} -y",
            "pacman": f"sudo pacman -R {package} --noconfirm",
            "snap": f"sudo snap remove {package}",
            "flatpak": f"flatpak uninstall {package} -y",
            "brew": f"brew uninstall {package}",
            "port": f"sudo port uninstall {package}"
        }
        return commands.get(package_manager, f"{package_manager} uninstall {package}")
    
    def _build_search_command(self, package_manager: str, query: str) -> str:
        """Build search command for package manager."""
        commands = {
            "winget": f"winget search {query}",
            "choco": f"choco search {query}",
            "scoop": f"scoop search {query}",
            "apt": f"apt search {query}",
            "yum": f"yum search {query}",
            "dnf": f"dnf search {query}",
            "pacman": f"pacman -Ss {query}",
            "snap": f"snap find {query}",
            "flatpak": f"flatpak search {query}",
            "brew": f"brew search {query}",
            "port": f"port search {query}"
        }
        return commands.get(package_manager, f"{package_manager} search {query}")
    
    def _build_list_command(self, package_manager: str) -> str:
        """Build list command for package manager."""
        commands = {
            "winget": "winget list",
            "choco": "choco list --local-only",
            "scoop": "scoop list",
            "apt": "apt list --installed",
            "yum": "yum list installed",
            "dnf": "dnf list installed",
            "pacman": "pacman -Q",
            "snap": "snap list",
            "flatpak": "flatpak list",
            "brew": "brew list",
            "port": "port installed"
        }
        return commands.get(package_manager, f"{package_manager} list")
    
    def _build_update_command(self, package_manager: str, package: Optional[str]) -> str:
        """Build update command for package manager."""
        if package:
            commands = {
                "winget": f"winget upgrade {package}",
                "choco": f"choco upgrade {package} -y",
                "scoop": f"scoop update {package}",
                "apt": f"sudo apt install --only-upgrade {package} -y",
                "yum": f"sudo yum update {package} -y",
                "dnf": f"sudo dnf update {package} -y",
                "pacman": f"sudo pacman -S {package} --noconfirm",
                "snap": f"sudo snap refresh {package}",
                "flatpak": f"flatpak update {package} -y",
                "brew": f"brew upgrade {package}",
                "port": f"sudo port upgrade {package}"
            }
        else:
            # Update all
            commands = {
                "winget": "winget upgrade --all",
                "choco": "choco upgrade all -y",
                "scoop": "scoop update",
                "apt": "sudo apt update && sudo apt upgrade -y",
                "yum": "sudo yum update -y",
                "dnf": "sudo dnf update -y",
                "pacman": "sudo pacman -Syu --noconfirm",
                "snap": "sudo snap refresh",
                "flatpak": "flatpak update -y",
                "brew": "brew update && brew upgrade",
                "port": "sudo port selfupdate && sudo port upgrade outdated"
            }
        
        return commands.get(package_manager, f"{package_manager} update")
    
    def _parse_search_results(self, package_manager: str, output: str) -> List[Dict[str, str]]:
        """Parse search results from package manager output."""
        packages = []
        lines = output.strip().split('\\n')
        
        for line in lines:
            # Simple parsing - can be enhanced for specific formats
            if line and not line.startswith(' ') and not line.startswith('-'):
                parts = line.split()
                if len(parts) >= 2:
                    packages.append({
                        "name": parts[0],
                        "version": parts[1] if len(parts) > 1 else "unknown",
                        "description": " ".join(parts[2:]) if len(parts) > 2 else ""
                    })
        
        return packages
    
    def _parse_list_results(self, package_manager: str, output: str) -> List[Dict[str, str]]:
        """Parse list results from package manager output."""
        return self._parse_search_results(package_manager, output)
    
    async def _list_windows_software(self) -> Dict[str, Any]:
        """List installed software on Windows using PowerShell."""
        try:
            # Use PowerShell to get installed software from registry
            ps_command = """
            Get-ItemProperty HKLM:\\\\Software\\\\Wow6432Node\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Uninstall\\\\* |
            Select-Object DisplayName, DisplayVersion, Publisher |
            Where-Object { $_.DisplayName -ne $null } |\n            Sort-Object DisplayName |\n            Format-Table -AutoSize
            """
            
            result = await self.system.execute_command(
                f"powershell -Command \"{ps_command}\"",
                timeout=30
            )
            
            # Parse the output
            packages = []
            lines = result.get("stdout", "").strip().split('\\n')
            for line in lines[2:]:  # Skip header lines
                if line.strip():
                    parts = line.split(None, 2)
                    if len(parts) >= 1:
                        packages.append({
                            "name": parts[0],
                            "version": parts[1] if len(parts) > 1 else "unknown",
                            "publisher": parts[2] if len(parts) > 2 else "unknown"
                        })
            
            return {
                "success": result["success"],
                "packages": packages,
                "count": len(packages),
                "source": "registry"
            }
            
        except Exception as e:
            logger.error(f"Windows software list error: {e}")
            return {
                "success": False,
                "error": str(e),
                "packages": []
            }


# Global application controller instance
_application_controller: Optional[ApplicationController] = None


def get_application_controller() -> ApplicationController:
    """Get or create global application controller instance."""
    global _application_controller
    if _application_controller is None:
        _application_controller = ApplicationController()
    return _application_controller
