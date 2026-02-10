#!/usr/bin/env python3
"""
Prueba intensiva completa del sistema HostBot.
Verifica todos los módulos, configuraciones, y funcionalidades.
"""

import asyncio
import sys
import os
import traceback
from datetime import datetime
from pathlib import Path

# Colores para terminal
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}  {text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.END}\n")

def print_section(text):
    print(f"\n{Colors.BOLD}{Colors.MAGENTA}▶ {text}{Colors.END}")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.END}")

# Resultados globales
test_results = {
    "passed": 0,
    "failed": 0,
    "warnings": 0,
    "total": 0
}

def record_result(success, warning=False):
    test_results["total"] += 1
    if success:
        test_results["passed"] += 1
    elif warning:
        test_results["warnings"] += 1
    else:
        test_results["failed"] += 1

# ==================== PRUEBAS ====================

async def test_config():
    """Prueba el módulo de configuración."""
    print_section("CONFIGURACIÓN")
    
    try:
        from config.settings import settings, Settings
        
        # Verificar que settings carga
        print_info(f"Agent name: {settings.agent_name}")
        print_info(f"Safety mode: {settings.safety_mode}")
        print_info(f"Log level: {settings.log_level}")
        print_info(f"Log dir: {settings.log_dir}")
        
        # Verificar tipos de datos
        assert isinstance(settings.agent_name, str)
        assert settings.safety_mode in ["strict", "moderate", "minimal"]
        
        print_success("Configuración carga correctamente")
        record_result(True)
        return True
    except Exception as e:
        print_error(f"Error en configuración: {e}")
        traceback.print_exc()
        record_result(False)
        return False

async def test_safety_layer():
    """Prueba la capa de seguridad."""
    print_section("CAPA DE SEGURIDAD")
    
    all_ok = True
    
    # Audit Logger
    try:
        from safety.audit_logger import get_audit_logger, ActionType, ActionStatus
        
        audit = get_audit_logger()
        op_id = audit.start_operation(
            action_type=ActionType.SYSTEM_COMMAND,
            description="Test operation",
            user_id="test"
        )
        audit.complete_operation(op_id, {"test": "data"})
        
        summary = audit.get_session_summary()
        print_info(f"Operaciones auditadas: {summary['total_operations']}")
        
        print_success("Audit Logger funciona")
        record_result(True)
    except Exception as e:
        print_error(f"Audit Logger falló: {e}")
        record_result(False)
        all_ok = False
    
    # Confirmation Manager
    try:
        from safety.confirmation_manager import get_confirmation_manager, ConfirmationLevel
        
        cm = get_confirmation_manager()
        pending = cm.get_pending_confirmations()
        print_info(f"Confirmaciones pendientes: {len(pending)}")
        
        # Probar formato de mensaje
        from dataclasses import dataclass
        from datetime import datetime
        
        @dataclass
        class MockRequest:
            id = "test-123"
            timestamp = datetime.now()
            level = ConfirmationLevel.STANDARD
            action_description = "Test action"
            details = {"test": "value"}
            timeout_seconds = 60
            user_id = "test"
            status = "pending"
        
        mock_req = MockRequest()
        msg = cm.format_confirmation_message(mock_req)
        assert "test-123" in msg
        
        print_success("Confirmation Manager funciona")
        record_result(True)
    except Exception as e:
        print_error(f"Confirmation Manager falló: {e}")
        traceback.print_exc()
        record_result(False)
        all_ok = False
    
    # Emergency Stop
    try:
        from safety.emergency_stop import get_emergency_stop, EmergencyLevel
        
        es = get_emergency_stop()
        status = es.get_status()
        print_info(f"Estado emergencia: {status}")
        
        # No probamos trigger para no detener el sistema
        print_success("Emergency Stop funciona")
        record_result(True)
    except Exception as e:
        print_error(f"Emergency Stop falló: {e}")
        record_result(False)
        all_ok = False
    
    # Permission Guard
    try:
        from safety.permission_guard import get_permission_guard, OperationCategory
        
        pg = get_permission_guard()
        
        # Probar permisos
        perm = pg.check_permission(OperationCategory.SYSTEM_COMMAND, "echo test")
        print_info(f"Permiso system command: {perm.value}")
        
        # Probar patrón peligroso
        perm_dangerous = pg.check_permission(OperationCategory.SYSTEM_COMMAND, "rm -rf /")
        print_info(f"Permiso comando peligroso: {perm_dangerous.value}")
        
        print_success("Permission Guard funciona")
        record_result(True)
    except Exception as e:
        print_error(f"Permission Guard falló: {e}")
        record_result(False)
        all_ok = False
    
    return all_ok

async def test_cognitive_layer():
    """Prueba la capa cognitiva."""
    print_section("CAPA COGNITIVA")
    
    all_ok = True
    
    # Ollama Client
    try:
        from cognitive.ollama_client import get_ollama_client
        
        client = get_ollama_client()
        print_info(f"Ollama host: {client.host}")
        print_info(f"Ollama model: {client.model}")
        
        # Intentar conexión (puede fallar si Ollama no está corriendo)
        try:
            connected = await client.check_connection()
            if connected:
                print_success("Conexión a Ollama exitosa")
                
                # Probar list_models
                models = await client.list_models()
                print_info(f"Modelos disponibles: {len(models)}")
                if models:
                    print_info(f"  Primer modelo: {models[0]}")
            else:
                print_warning("Ollama no responde (puede no estar instalado)")
                record_result(True, warning=True)
        except Exception as conn_err:
            print_warning(f"No se pudo conectar a Ollama: {conn_err}")
            record_result(True, warning=True)
        
        print_success("Ollama Client inicializa correctamente")
        if 'connected' in locals() and connected:
            record_result(True)
    except Exception as e:
        print_error(f"Ollama Client falló: {e}")
        traceback.print_exc()
        record_result(False)
        all_ok = False
    
    # Planner
    try:
        from cognitive.planner import get_planner
        
        planner = get_planner()
        print_info(f"Planner inicializado: {planner is not None}")
        
        print_success("Planner funciona")
        record_result(True)
    except Exception as e:
        print_error(f"Planner falló: {e}")
        record_result(False)
        all_ok = False
    
    # Brain Orchestrator
    try:
        from cognitive.brain_orchestrator import get_brain_orchestrator
        
        brain = get_brain_orchestrator()
        print_info(f"Brain Orchestrator inicializado: {brain is not None}")
        
        print_success("Brain Orchestrator funciona")
        record_result(True)
    except Exception as e:
        print_error(f"Brain Orchestrator falló: {e}")
        record_result(False)
        all_ok = False
    
    return all_ok

async def test_execution_layer():
    """Prueba la capa de ejecución."""
    print_section("CAPA DE EJECUCIÓN")
    
    all_ok = True
    
    # System Controller
    try:
        from execution.system_controller import get_system_controller
        
        sc = get_system_controller()
        
        # Probar info del sistema (comando seguro)
        info = await sc.get_system_info()
        print_info(f"Plataforma: {info.get('platform', 'unknown')}")
        print_info(f"CPU cores: {info.get('cpu_count', 'unknown')}")
        
        print_success("System Controller funciona")
        record_result(True)
    except Exception as e:
        print_error(f"System Controller falló: {e}")
        traceback.print_exc()
        record_result(False)
        all_ok = False
    
    # Desktop Controller
    try:
        from execution.desktop_controller import get_desktop_controller
        
        dc = get_desktop_controller()
        print_info(f"Desktop Controller inicializado: {dc is not None}")
        
        # No movemos el mouse para no interferir
        print_success("Desktop Controller inicializa")
        record_result(True)
    except Exception as e:
        print_error(f"Desktop Controller falló: {e}")
        record_result(False)
        all_ok = False
    
    # Browser Controller
    try:
        from execution.browser_controller import get_browser_controller
        
        bc = get_browser_controller()
        print_info(f"Browser Controller inicializado: {bc is not None}")
        
        print_success("Browser Controller inicializa")
        record_result(True)
    except Exception as e:
        print_error(f"Browser Controller falló: {e}")
        record_result(False)
        all_ok = False
    
    # Application Controller
    try:
        from execution.application_controller import get_application_controller
        
        ac = get_application_controller()
        print_info(f"Application Controller inicializado: {ac is not None}")
        
        print_success("Application Controller inicializa")
        record_result(True)
    except Exception as e:
        print_error(f"Application Controller falló: {e}")
        record_result(False)
        all_ok = False
    
    return all_ok

async def test_vision_layer():
    """Prueba la capa de visión."""
    print_section("CAPA DE VISIÓN")
    
    all_ok = True
    
    try:
        from vision.vision_orchestrator import get_vision_orchestrator
        from vision.screen_capture import get_screen_capture
        from vision.visual_analyzer import get_visual_analyzer
        
        # Screen Capture
        sc = get_screen_capture()
        print_info(f"Screen Capture inicializado: {sc is not None}")
        
        # Visual Analyzer
        va = get_visual_analyzer()
        print_info(f"Visual Analyzer inicializado: {va is not None}")
        
        # Vision Orchestrator
        vo = get_vision_orchestrator()
        print_info(f"Vision Orchestrator inicializado: {vo is not None}")
        
        print_success("Capa de visión inicializa correctamente")
        record_result(True)
    except Exception as e:
        print_error(f"Capa de visión falló: {e}")
        traceback.print_exc()
        record_result(False)
        all_ok = False
    
    return all_ok

async def test_core_agent():
    """Prueba el agente core."""
    print_section("AGENTE CORE")
    
    try:
        from core.agent import Agent
        
        agent = Agent()
        print_info(f"Agente creado: {agent is not None}")
        print_info(f"Estado inicial: {agent.state}")
        print_info(f"Vision enabled: {agent.vision_enabled}")
        
        # No inicializamos completamente para no requerir Ollama
        print_success("Agente Core se instancia correctamente")
        record_result(True)
        return True
    except Exception as e:
        print_error(f"Agente Core falló: {e}")
        traceback.print_exc()
        record_result(False)
        return False

async def test_security_layer():
    """Prueba la capa de seguridad adicional."""
    print_section("CAPA DE SEGURIDAD ADICIONAL")
    
    all_ok = True
    
    # Input Validator
    try:
        from security.input_validator import get_input_validator
        
        iv = get_input_validator()
        print_info(f"Input Validator inicializado: {iv is not None}")
        
        print_success("Input Validator funciona")
        record_result(True)
    except Exception as e:
        print_error(f"Input Validator falló: {e}")
        record_result(False)
        all_ok = False
    
    # Rate Limiter
    try:
        from security.rate_limiter import get_rate_limiter
        
        rl = get_rate_limiter()
        print_info(f"Rate Limiter inicializado: {rl is not None}")
        
        print_success("Rate Limiter funciona")
        record_result(True)
    except Exception as e:
        print_error(f"Rate Limiter falló: {e}")
        record_result(False)
        all_ok = False
    
    # Secure Config
    try:
        from security.secure_config import get_secure_config
        
        sc = get_secure_config()
        print_info(f"Secure Config inicializado: {sc is not None}")
        
        print_success("Secure Config funciona")
        record_result(True)
    except Exception as e:
        print_error(f"Secure Config falló: {e}")
        record_result(False)
        all_ok = False
    
    return all_ok

async def test_bot_layer():
    """Prueba la capa de Discord bot."""
    print_section("CAPA DE DISCORD BOT")
    
    all_ok = True
    
    try:
        from bot.discord_client import get_discord_client
        
        # No inicializamos el bot real para no requerir token
        print_info("Discord Client module importado correctamente")
        
        print_success("Discord Bot layer importa correctamente")
        record_result(True)
    except Exception as e:
        print_error(f"Discord Bot falló: {e}")
        traceback.print_exc()
        record_result(False)
        all_ok = False
    
    return all_ok

async def test_web_layer():
    """Prueba la capa web."""
    print_section("CAPA WEB")
    
    try:
        from web.main import app
        
        print_info(f"FastAPI app creada: {app is not None}")
        
        # Verificar rutas
        routes = [route.path for route in app.routes]
        print_info(f"Rutas disponibles: {len(routes)}")
        
        print_success("Web layer inicializa correctamente")
        record_result(True)
        return True
    except Exception as e:
        print_error(f"Web layer falló: {e}")
        traceback.print_exc()
        record_result(False)
        return False

async def test_files_structure():
    """Prueba la estructura de archivos."""
    print_section("ESTRUCTURA DE ARCHIVOS")
    
    required_files = [
        "main.py",
        "setup.py",
        "update.py",
        "requirements.txt",
        "README.md",
        "LICENSE",
        "config/settings.py",
        "core/agent.py",
        "safety/audit_logger.py",
        "cognitive/ollama_client.py",
        "execution/system_controller.py",
        "vision/vision_orchestrator.py",
        "web/main.py",
        "bot/discord_client.py",
    ]
    
    missing = []
    for file in required_files:
        if not Path(file).exists():
            missing.append(file)
            print_error(f"Falta archivo: {file}")
        else:
            print_success(f"Existe: {file}")
    
    if missing:
        record_result(False)
        return False
    
    print_success("Todos los archivos requeridos existen")
    record_result(True)
    return True

async def test_imports():
    """Prueba que todos los imports funcionan."""
    print_section("IMPORTS GLOBALES")
    
    modules = [
        "config",
        "core",
        "safety",
        "cognitive",
        "execution",
        "vision",
        "web",
        "bot",
        "security",
    ]
    
    all_ok = True
    for module in modules:
        try:
            __import__(module)
            print_success(f"Import: {module}")
            record_result(True)
        except Exception as e:
            print_error(f"Import falló {module}: {e}")
            record_result(False)
            all_ok = False
    
    return all_ok

async def test_logs_directory():
    """Prueba el directorio de logs."""
    print_section("DIRECTORIO DE LOGS")
    
    try:
        from config.settings import settings
        
        log_dir = settings.log_dir
        print_info(f"Log directory: {log_dir}")
        print_info(f"Exists: {log_dir.exists()}")
        print_info(f"Is directory: {log_dir.is_dir()}")
        
        # Intentar escribir
        test_file = log_dir / "test_write.tmp"
        test_file.write_text("test")
        test_file.unlink()
        
        print_success("Directorio de logs funciona correctamente")
        record_result(True)
        return True
    except Exception as e:
        print_error(f"Logs directory falló: {e}")
        record_result(False)
        return False

# ==================== MAIN ====================

async def run_all_tests():
    """Ejecuta todas las pruebas."""
    print_header("PRUEBA INTENSIVA - HOSTBOT SYSTEM")
    print_info(f"Fecha: {datetime.now().isoformat()}")
    print_info(f"Python: {sys.version}")
    print_info(f"Directorio: {os.getcwd()}")
    print()
    
    tests = [
        ("Estructura de Archivos", test_files_structure),
        ("Imports Globales", test_imports),
        ("Configuración", test_config),
        ("Directorio de Logs", test_logs_directory),
        ("Capa de Seguridad", test_safety_layer),
        ("Capa Cognitiva", test_cognitive_layer),
        ("Capa de Ejecución", test_execution_layer),
        ("Capa de Visión", test_vision_layer),
        ("Agente Core", test_core_agent),
        ("Seguridad Adicional", test_security_layer),
        ("Discord Bot", test_bot_layer),
        ("Capa Web", test_web_layer),
    ]
    
    for name, test_func in tests:
        try:
            await test_func()
        except Exception as e:
            print_error(f"TEST {name} CRASHED: {e}")
            traceback.print_exc()
            record_result(False)
    
    # Resumen final
    print_header("RESUMEN DE PRUEBAS")
    
    total = test_results["total"]
    passed = test_results["passed"]
    failed = test_results["failed"]
    warnings = test_results["warnings"]
    
    print(f"Total tests: {total}")
    print_success(f"Pasados: {passed}")
    print_warning(f"Advertencias: {warnings}")
    print_error(f"Fallidos: {failed}")
    print()
    
    if failed == 0:
        print_success("🎉 TODAS LAS PRUEBAS PASARON")
        return 0
    else:
        print_error(f"⚠️  {failed} PRUEBAS FALLARON")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
