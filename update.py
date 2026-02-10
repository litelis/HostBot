#!/usr/bin/env python3
"""
Script de actualización para HostBot.
Verifica y aplica actualizaciones desde el repositorio Git.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path


class Colors:
    """Colores para terminal."""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_status(message: str, status: str = "info"):
    """Imprime mensaje con formato."""
    icons = {
        "ok": f"{Colors.GREEN}✅{Colors.END}",
        "warn": f"{Colors.YELLOW}⚠️{Colors.END}",
        "error": f"{Colors.RED}❌{Colors.END}",
        "info": f"{Colors.BLUE}ℹ️{Colors.END}",
        "step": f"{Colors.CYAN}➡️{Colors.END}"
    }
    print(f"{icons.get(status, 'ℹ️')} {message}")


def print_header(message: str):
    """Imprime encabezado."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}  {message}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}\n")


def run_command(cmd: list, capture: bool = True, cwd: Path = None) -> tuple:
    """Ejecuta comando y retorna resultado."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            check=False,
            cwd=cwd or Path.cwd()
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)


def check_git_installed() -> bool:
    """Verifica si Git está instalado."""
    success, _, _ = run_command(["git", "--version"])
    return success


def get_current_commit() -> str:
    """Obtiene el hash del commit actual."""
    success, stdout, _ = run_command(["git", "rev-parse", "HEAD"])
    return stdout.strip() if success else "unknown"


def get_remote_url() -> str:
    """Obtiene la URL del remoto."""
    success, stdout, _ = run_command(["git", "remote", "get-url", "origin"])
    return stdout.strip() if success else ""


def check_for_updates() -> dict:
    """Verifica si hay actualizaciones disponibles."""
    result = {
        "has_updates": False,
        "current_commit": "",
        "latest_commit": "",
        "commits_behind": 0,
        "commits_ahead": 0,
        "error": None
    }
    
    # Verificar si es un repositorio git
    if not Path(".git").exists():
        result["error"] = "No es un repositorio Git. Clona el repo primero."
        return result
    
    # Obtener commit actual
    result["current_commit"] = get_current_commit()
    
    # Fetch de cambios remotos
    print_status("Buscando actualizaciones...", "step")
    success, _, stderr = run_command(["git", "fetch", "origin"])
    if not success:
        result["error"] = f"Error al buscar actualizaciones: {stderr}"
        return result
    
    # Verificar commits detrás/ahead
    success, stdout, _ = run_command(
        ["git", "rev-list", "--left-right", "--count", "HEAD...origin/main"]
    )
    if success:
        ahead, behind = stdout.strip().split()
        result["commits_ahead"] = int(ahead)
        result["commits_behind"] = int(behind)
        result["has_updates"] = int(behind) > 0
        
        if result["has_updates"]:
            # Obtener info del último commit
            success, stdout, _ = run_command(
                ["git", "log", "origin/main", "-1", "--oneline"]
            )
            if success:
                result["latest_commit"] = stdout.strip()
    
    return result


def show_update_info(update_info: dict):
    """Muestra información de actualizaciones."""
    print_header("ESTADO DE ACTUALIZACIONES")
    
    print(f"Commit actual: {update_info['current_commit'][:8]}")
    print(f"Repositorio: {get_remote_url()}")
    print()
    
    if update_info["error"]:
        print_status(update_info["error"], "error")
        return
    
    if update_info["commits_behind"] == 0:
        print_status("Estás en la última versión ✓", "ok")
    else:
        print_status(f"Hay {update_info['commits_behind']} actualizaciones disponibles", "warn")
        print()
        print(f"{Colors.YELLOW}Últimos cambios:{Colors.END}")
        
        # Mostrar lista de commits
        success, stdout, _ = run_command(
            ["git", "log", "HEAD..origin/main", "--oneline", "--no-decorate"]
        )
        if success:
            for line in stdout.strip().split("\n"):
                if line:
                    print(f"  • {line}")
        print()
        print(f"{Colors.CYAN}Para actualizar ejecuta:{Colors.END}")
        print(f"  python update.py --apply")
    
    if update_info["commits_ahead"] > 0:
        print()
        print_status(f"Tienes {update_info['commits_ahead']} commits locales no publicados", "info")


def apply_updates() -> bool:
    """Aplica las actualizaciones."""
    print_header("APLICANDO ACTUALIZACIONES")
    
    # Verificar estado del repo
    success, stdout, _ = run_command(["git", "status", "--porcelain"])
    if stdout.strip():
        print_status("Tienes cambios locales sin guardar", "warn")
        print("Cambios pendientes:")
        print(stdout)
        
        choice = input(f"\n{Colors.YELLOW}¿Deseas guardar los cambios locales primero? (s/n): {Colors.END}").strip().lower()
        if choice == 's':
            print_status("Guardando cambios locales...", "step")
            run_command(["git", "stash"])
        else:
            print_status("Actualización cancelada", "error")
            return False
    
    # Hacer pull
    print_status("Descargando actualizaciones...", "step")
    success, stdout, stderr = run_command(["git", "pull", "origin", "main"])
    
    if success:
        print_status("Actualización completada ✓", "ok")
        print()
        print(f"{Colors.GREEN}Cambios aplicados:{Colors.END}")
        print(stdout)
        return True
    else:
        print_status(f"Error al actualizar: {stderr}", "error")
        return False


def setup_remote(repo_url: str = "https://github.com/litelis/HostBot.git"):
    """Configura el remoto si no existe."""
    print_status("Configurando repositorio remoto...", "step")
    
    # Verificar si ya tiene remoto
    current_remote = get_remote_url()
    if current_remote:
        print_status(f"Remoto ya configurado: {current_remote}", "info")
        return True
    
    # Agregar remoto
    success, _, stderr = run_command(["git", "remote", "add", "origin", repo_url])
    if success:
        print_status(f"Remoto agregado: {repo_url}", "ok")
        return True
    else:
        print_status(f"Error agregando remoto: {stderr}", "error")
        return False


def main():
    """Función principal."""
    parser = argparse.ArgumentParser(description="Actualizador de HostBot")
    parser.add_argument(
        "--apply", 
        action="store_true",
        help="Aplicar actualizaciones disponibles"
    )
    parser.add_argument(
        "--setup",
        action="store_true", 
        help="Configurar repositorio remoto"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Mostrar estado del repositorio"
    )
    
    args = parser.parse_args()
    
    print_header("HOSTBOT - ACTUALIZADOR")
    
    # Verificar Git
    if not check_git_installed():
        print_status("Git no está instalado. Instálalo primero.", "error")
        sys.exit(1)
    
    # Configurar remoto si se solicita
    if args.setup:
        setup_remote()
        return
    
    # Mostrar estado si se solicita
    if args.status:
        update_info = check_for_updates()
        show_update_info(update_info)
        return
    
    # Aplicar actualizaciones
    if args.apply:
        update_info = check_for_updates()
        if not update_info["has_updates"]:
            print_status("No hay actualizaciones disponibles", "info")
            return
        
        success = apply_updates()
        if success:
            print()
            print_status("Reinicia HostBot para aplicar los cambios", "info")
            print(f"{Colors.CYAN}  python main.py{Colors.END}")
        sys.exit(0 if success else 1)
    
    # Por defecto: solo verificar
    update_info = check_for_updates()
    show_update_info(update_info)


if __name__ == "__main__":
    main()
