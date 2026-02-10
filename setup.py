#!/usr/bin/env python3
"""
Script de instalación y configuración de HostBot.
Verifica e instala todas las dependencias necesarias.
"""

import os
import sys
import subprocess
import platform
import json
import urllib.request
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


def run_command(cmd: list, capture: bool = True) -> tuple:
    """Ejecuta comando y retorna resultado."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            check=False
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)


def check_python_version() -> bool:
    """Verifica versión de Python."""
    print_status("Verificando Python...", "step")
    
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print_status(f"Python {version.major}.{version.minor}.{version.micro} ✓", "ok")
        return True
    else:
        print_status(f"Python {version.major}.{version.minor} - Se requiere 3.8+", "error")
        return False


def check_ollama() -> dict:
    """Verifica instalación y estado de Ollama."""
    print_status("Verificando Ollama...", "step")
    
    result = {
        "installed": False,
        "running": False,
        "models": [],
        "error": None
    }
    
    # Verificar si ollama está en PATH
    success, _, _ = run_command(["ollama", "--version"])
    if not success:
        result["error"] = "Ollama no encontrado en PATH"
        print_status("Ollama no está instalado", "error")
        return result
    
    result["installed"] = True
    print_status("Ollama instalado ✓", "ok")
    
    # Verificar si está ejecutándose
    try:
        req = urllib.request.Request(
            "http://localhost:11434/api/tags",
            method="GET"
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                result["running"] = True
                data = json.loads(response.read().decode())
                result["models"] = [m["name"] for m in data.get("models", [])]
                print_status("Ollama ejecutándose ✓", "ok")
                if result["models"]:
                    print_status(f"Modelos disponibles: {', '.join(result['models'])}", "info")
                else:
                    print_status("No hay modelos descargados", "warn")
            else:
                result["error"] = f"Ollama respondió con status {response.status}"
                print_status("Ollama no responde correctamente", "warn")
    except Exception as e:
        result["error"] = str(e)
        print_status("Ollama no está ejecutándose", "warn")
        print_status("Inicia Ollama antes de continuar", "info")
    
    return result


def install_ollama_model(model_name: str) -> bool:
    """Instala un modelo de Ollama."""
    print_status(f"Instalando modelo {model_name}...", "step")
    
    success, stdout, stderr = run_command(
        ["ollama", "pull", model_name],
        capture=False
    )
    
    if success:
        print_status(f"Modelo {model_name} instalado ✓", "ok")
        return True
    else:
        print_status(f"Error instalando modelo: {stderr}", "error")
        return False


def check_pip_dependencies() -> bool:
    """Verifica dependencias de Python."""
    print_status("Verificando dependencias de Python...", "step")
    
    required = [
        "discord.py",
        "ollama",
        "pyautogui",
        "playwright",
        "psutil",
        "pydantic",
        "loguru",
        "python-dotenv"
    ]
    
    missing = []
    for package in required:
        try:
            __import__(package.replace("-", "_").replace(".", "_").lower())
        except ImportError:
            missing.append(package)
    
    if missing:
        print_status(f"Faltan dependencias: {', '.join(missing)}", "warn")
        return False
    else:
        print_status("Todas las dependencias instaladas ✓", "ok")
        return True


def install_pip_dependencies(use_venv: bool = False) -> bool:
    """Instala dependencias de Python."""
    print_status("Instalando dependencias...", "step")
    
    if use_venv:
        # Crear y usar virtual environment
        venv_path = Path(".venv")
        if not venv_path.exists():
            print_status("Creando entorno virtual...", "info")
            success, _, stderr = run_command([sys.executable, "-m", "venv", ".venv"])
            if not success:
                print_status(f"Error creando venv: {stderr}", "error")
                return False
        
        # Determinar ruta de pip en el venv
        if platform.system() == "Windows":
            pip_path = venv_path / "Scripts" / "pip.exe"
            python_path = venv_path / "Scripts" / "python.exe"
        else:
            pip_path = venv_path / "bin" / "pip"
            python_path = venv_path / "bin" / "python"
        
        print_status("Instalando en entorno virtual...", "info")
        success, _, stderr = run_command(
            [str(pip_path), "install", "-r", "requirements.txt"],
            capture=False
        )
    else:
        print_status("Instalando en Python global...", "info")
        success, _, stderr = run_command(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            capture=False
        )
    
    if success:
        print_status("Dependencias instaladas ✓", "ok")
        if use_venv:
            print_status(f"Para usar el entorno virtual: {python_path}", "info")
        return True
    else:
        print_status(f"Error instalando dependencias: {stderr}", "error")
        return False


def ask_install_location() -> bool:
    """Pregunta dónde instalar dependencias."""
    print()
    print(f"{Colors.CYAN}¿Dónde deseas instalar las dependencias?{Colors.END}")
    print("  1. Entorno virtual (.venv) - Recomendado")
    print("  2. Python global (sistema)")
    
    while True:
        choice = input(f"\n{Colors.YELLOW}Selecciona (1/2): {Colors.END}").strip()
        if choice == "1":
            return True
        elif choice == "2":
            return False
        else:
            print("Opción inválida. Usa 1 o 2.")


def configure_env_file() -> dict:
    """Configura interactivamente el archivo .env."""
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    # Crear desde ejemplo si no existe
    if not env_file.exists() and env_example.exists():
        env_file.write_text(env_example.read_text())
        print_status("Archivo .env creado desde .env.example", "ok")
    
    if not env_file.exists():
        print_status("No se pudo crear .env", "error")
        return {"exists": False, "configured": False, "discord_token": False, "admin_id": False}
    
    print()
    print(f"{Colors.CYAN}Configuración de variables de entorno:{Colors.END}")
    print(f"{Colors.YELLOW}Presiona Enter para mantener el valor actual{Colors.END}")
    print()
    
    # Leer configuración actual
    content = env_file.read_text()
    lines = content.splitlines()
    new_lines = []
    
    current_values = {}
    for line in lines:
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            current_values[key] = value
    
    # Configurar DISCORD_TOKEN
    current_token = current_values.get("DISCORD_TOKEN", "")
    is_placeholder = "your_discord_bot_token" in current_token or not current_token
    
    if is_placeholder:
        print(f"{Colors.BOLD}DISCORD_TOKEN:{Colors.END}")
        print("  Obtén tu token en: https://discord.com/developers/applications")
        print("  Crea una aplicación → Bot → Copy Token")
    else:
        masked = current_token[:10] + "..." if len(current_token) > 10 else current_token
        print(f"{Colors.BOLD}DISCORD_TOKEN:{Colors.END} (actual: {masked})")
    
    new_token = input(f"  Token: ").strip()
    if new_token:
        current_values["DISCORD_TOKEN"] = new_token
    
    # Configurar DISCORD_ADMIN_USER_ID
    current_admin = current_values.get("DISCORD_ADMIN_USER_ID", "")
    is_placeholder = "your_admin_user_id" in current_admin or not current_admin
    
    if is_placeholder:
        print(f"\n{Colors.BOLD}DISCORD_ADMIN_USER_ID:{Colors.END}")
        print("  Tu ID de Discord: Activa modo desarrollador → Click derecho en tu nombre → Copy ID")
    else:
        print(f"\n{Colors.BOLD}DISCORD_ADMIN_USER_ID:{Colors.END} (actual: {current_admin})")
    
    new_admin = input(f"  Admin ID: ").strip()
    if new_admin:
        current_values["DISCORD_ADMIN_USER_ID"] = new_admin
    
    # Configurar OLLAMA_MODEL
    current_model = current_values.get("OLLAMA_MODEL", "llama3.2")
    print(f"\n{Colors.BOLD}OLLAMA_MODEL:{Colors.END} (actual: {current_model})")
    print("  Opciones: llama3.2, codellama, mistral, llava")
    new_model = input(f"  Modelo [Enter para {current_model}]: ").strip()
    if new_model:
        current_values["OLLAMA_MODEL"] = new_model
    
    # Guardar archivo
    new_content = []
    for line in lines:
        if "=" in line and not line.startswith("#"):
            key = line.split("=", 1)[0]
            if key in current_values:
                new_content.append(f"{key}={current_values[key]}")
            else:
                new_content.append(line)
        else:
            new_content.append(line)
    
    env_file.write_text("\n".join(new_content) + "\n")
    print_status("Configuración guardada ✓", "ok")
    
    # Verificar resultado
    content = env_file.read_text()
    discord_ok = "your_discord_bot_token" not in content and "DISCORD_TOKEN=" in content and len(current_values.get("DISCORD_TOKEN", "")) > 10
    admin_ok = "your_admin_user_id" not in content and "DISCORD_ADMIN_USER_ID=" in content and current_values.get("DISCORD_ADMIN_USER_ID", "").isdigit()
    
    return {
        "exists": True,
        "configured": discord_ok and admin_ok,
        "discord_token": discord_ok,
        "admin_id": admin_ok
    }


def check_env_file() -> dict:
    """Verifica archivo de configuración."""
    print_status("Verificando configuración...", "step")
    
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    result = {
        "exists": env_file.exists(),
        "configured": False,
        "discord_token": False,
        "admin_id": False
    }
    
    if not env_file.exists():
        if env_example.exists():
            print_status("Creando .env desde .env.example...", "info")
            env_file.write_text(env_example.read_text())
            print_status("Archivo .env creado", "ok")
            result["exists"] = True
        else:
            print_status("No se encontró .env.example", "error")
            return result
    
    # Leer configuración actual
    content = env_file.read_text()
    result["discord_token"] = "your_discord_bot_token_here" not in content and "DISCORD_TOKEN=" in content
    result["admin_id"] = "your_admin_user_id_here" not in content and "DISCORD_ADMIN_USER_ID=" in content
    result["configured"] = result["discord_token"] and result["admin_id"]
    
    if result["configured"]:
        print_status("Configuración completa ✓", "ok")
        # Preguntar si quiere reconfigurar
        reconfig = input(f"\n{Colors.YELLOW}¿Deseas reconfigurar las variables? (s/n): {Colors.END}").lower().strip()
        if reconfig == 's':
            return configure_env_file()
    else:
        print_status("Configuración incompleta", "warn")
        if not result["discord_token"]:
            print_status("  - Falta DISCORD_TOKEN", "info")
        if not result["admin_id"]:
            print_status("  - Falta DISCORD_ADMIN_USER_ID", "info")
        
        # Ofrecer configuración interactiva
        config_now = input(f"\n{Colors.YELLOW}¿Configurar ahora? (s/n): {Colors.END}").lower().strip()
        if config_now == 's':
            return configure_env_file()
    
    return result


def check_playwright() -> bool:
    """Verifica instalación de Playwright."""
    print_status("Verificando Playwright...", "step")
    
    try:
        import playwright
        print_status("Playwright instalado ✓", "ok")
        return True
    except ImportError:
        print_status("Playwright no instalado", "warn")
        return False


def install_playwright_browsers() -> bool:
    """Instala navegadores de Playwright."""
    print_status("Instalando navegadores de Playwright...", "step")
    
    success, stdout, stderr = run_command(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture=False
    )
    
    if success:
        print_status("Navegadores instalados ✓", "ok")
        return True
    else:
        print_status(f"Error instalando navegadores: {stderr}", "error")
        return False


def print_next_steps(ollama_ok: bool, env_ok: bool, models: list):
    """Imprime instrucciones siguientes."""
    print_header("PRÓXIMOS PASOS")
    
    if not ollama_ok:
        print(f"{Colors.YELLOW}1. Instalar Ollama:{Colors.END}")
        print("   Windows: https://ollama.com/download/windows")
        print("   Linux/macOS: curl -fsSL https://ollama.com/install.sh | sh")
        print()
        print(f"{Colors.YELLOW}2. Iniciar Ollama:{Colors.END}")
        print("   ollama serve")
        print()
    
    if not models:
        print(f"{Colors.YELLOW}3. Descargar un modelo:{Colors.END}")
        print("   ollama pull llama3.2")
        print("   # Alternativas: codellama, mistral, llava")
        print()
    
    if not env_ok:
        print(f"{Colors.YELLOW}4. Configurar .env:{Colors.END}")
        print("   Edita el archivo .env con:")
        print("   - DISCORD_TOKEN (desde https://discord.com/developers/applications)")
        print("   - DISCORD_ADMIN_USER_ID (tu ID de Discord)")
        print("   - OLLAMA_MODEL (ej: llama3.2)")
        print()
    
    print(f"{Colors.GREEN}5. Iniciar HostBot:{Colors.END}")
    print("   python main.py")
    print()


def main():
    """Función principal de setup."""
    print_header("HOSTBOT - SCRIPT DE INSTALACIÓN")
    
    # Verificar Python
    if not check_python_version():
        print_status("Instala Python 3.8 o superior", "error")
        sys.exit(1)
    
    # Verificar Ollama
    ollama_status = check_ollama()
    
    # Verificar dependencias
    deps_ok = check_pip_dependencies()
    if not deps_ok:
        install = input(f"\n{Colors.YELLOW}¿Instalar dependencias de Python? (s/n): {Colors.END}").lower().strip()
        if install == 's':
            use_venv = ask_install_location()
            deps_ok = install_pip_dependencies(use_venv=use_venv)
    
    # Verificar Playwright
    playwright_ok = check_playwright()
    if deps_ok and not playwright_ok:
        install = input(f"\n{Colors.YELLOW}¿Instalar Playwright? (s/n): {Colors.END}").lower().strip()
        if install == 's':
            playwright_ok = install_playwright_browsers()
    
    # Verificar .env
    env_status = check_env_file()
    
    # Si no hay modelos, ofrecer instalar
    if ollama_status["running"] and not ollama_status["models"]:
        print_status("No tienes modelos de Ollama instalados", "warn")
        print("Modelos recomendados:")
        print("  1. llama3.2 - Equilibrado (recomendado)")
        print("  2. codellama - Para tareas técnicas")
        print("  3. mistral - Para tareas generales")
        
        choice = input(f"\n{Colors.CYAN}¿Qué modelo deseas instalar? (1/2/3/n): {Colors.END}").strip()
        
        models_map = {"1": "llama3.2", "2": "codellama", "3": "mistral"}
        if choice in models_map:
            if install_ollama_model(models_map[choice]):
                ollama_status["models"].append(models_map[choice])
    
    # Resumen
    print_header("RESUMEN DE INSTALACIÓN")
    
    checks = [
        ("Python 3.8+", True),
        ("Ollama instalado", ollama_status["installed"]),
        ("Ollama ejecutándose", ollama_status["running"]),
        ("Modelos disponibles", len(ollama_status["models"]) > 0),
        ("Dependencias Python", deps_ok),
        ("Playwright", playwright_ok),
        ("Configuración .env", env_status["exists"]),
        ("Discord configurado", env_status["discord_token"]),
        ("Admin ID configurado", env_status["admin_id"])
    ]
    
    for name, status in checks:
        icon = f"{Colors.GREEN}✓{Colors.END}" if status else f"{Colors.RED}✗{Colors.END}"
        print(f"  {icon} {name}")
    
    # Próximos pasos
    all_ok = all([c[1] for c in checks])
    
    if all_ok:
        print_header("✨ INSTALACIÓN COMPLETA")
        print(f"{Colors.GREEN}Todo está configurado. Inicia HostBot con:{Colors.END}")
        print(f"{Colors.BOLD}  python main.py{Colors.END}")
    else:
        print_next_steps(
            ollama_status["running"],
            env_status["configured"],
            ollama_status["models"]
        )
    
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
