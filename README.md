# HostBot

Agente autónomo de control de sistemas operativos controlado por Discord e IA local.

## ¿Qué es HostBot?

HostBot es un agente autónomo que permite controlar un ordenador completo a través de comandos de Discord. Utiliza Ollama (IA local) para interpretar instrucciones en lenguaje natural y ejecutar acciones en el sistema operativo.

## Características principales

- **Control total del sistema**: Comandos, archivos, procesos
- **Automatización de escritorio**: Ratón, teclado, capturas de pantalla
- **Navegación web**: Automatización de navegador con Playwright
- **Gestión de software**: Instalación y configuración de aplicaciones
- **IA local**: Procesamiento con Ollama, sin dependencias externas
- **Seguridad integrada**: Confirmaciones, auditoría completa, parada de emergencia

## ⚠️ Advertencia de seguridad

**Este sistema tiene control total sobre el ordenador. Úsalo con extrema precaución.**

- Ejecuta siempre en modo `strict` inicialmente
- Solo usuarios autorizados de Discord pueden ejecutar comandos
- El sistema de parada de emergencia está siempre activo
- Todas las acciones se registran para auditoría
- Las acciones críticas requieren confirmación explícita
- Rate limiting integrado para prevenir abuso
- Validación estricta de todas las entradas

## Requisitos

- Python 3.8+
- Windows 10/11 (principal), Linux/macOS (parcial)-
- Ollama ejecutándose localmente
- Token de bot de Discord

## Instalación completa

### Paso 1: Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/hostbot.git
cd hostbot
```

### Paso 2: Ejecutar el script de setup

El script `setup.py` verificará e instalará automáticamente todas las dependencias:

```bash
python setup.py
```

Este script comprobará:
- ✅ Versión de Python (3.8+)
- ✅ Ollama instalado y ejecutándose
- ✅ Modelos de Ollama disponibles
- ✅ Dependencias de Python
- ✅ Playwright y navegadores
- ✅ Variables de entorno configuradas

### Paso 3: Configurar variables de entorno

```bash
cp .env.example .env
# Edita .env con tu configuración
```

Variables obligatorias:
- `DISCORD_TOKEN`: Token de tu bot de Discord ([crear bot](https://discord.com/developers/applications))
- `DISCORD_ADMIN_USER_ID`: Tu ID de usuario de Discord
- `OLLAMA_MODEL`: Modelo a usar (recomendado: llama3.2, codellama, o mistral)

### Paso 4: Iniciar el agente

```bash
python main.py
```

## Configuración de Ollama

### Instalación de Ollama

**Windows:**
1. Descarga desde [ollama.com](https://ollama.com)
2. Ejecuta el instalador
3. Ollama se ejecutará automáticamente en segundo plano

**Linux/macOS:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Descargar modelos

Una vez instalado Ollama, descarga un modelo:

```bash
# Modelo recomendado (equilibrado)
ollama pull llama3.2

# Alternativas según uso:
ollama pull codellama    # Para técnicas/programación
ollama pull mistral      # Para tareas generales
ollama pull llava        # Para análisis de imágenes
```

Verifica que Ollama funciona:
```bash
ollama list
ollama run llama3.2
```

## Cómo funciona el código

### Arquitectura del sistema

HostBot está organizado en capas modulares:

```
┌─────────────────────────────────────┐
│         Capa de Control            │
│      (Discord - bot/)            │
│  - Recepción de comandos           │
│  - Gestión de autorizaciones       │
│  - Comunicación en tiempo real     │
└─────────────┬───────────────────────┘
              ▼
┌─────────────────────────────────────┐
│        Capa Cognitiva              │
│    (Ollama - cognitive/)           │
│  - Interpretación de lenguaje      │
│  - Generación de planes            │
│  - Razonamiento paso a paso        │
└─────────────┬───────────────────────┘
              ▼
┌─────────────────────────────────────┐
│       Capa de Ejecución            │
│     (Sistema - execution/)         │
│  - Control de escritorio           │
│  - Automatización de apps          │
│  - Navegador web                   │
│  - Comandos del sistema            │
└─────────────┬───────────────────────┘
              ▼
┌─────────────────────────────────────┐
│        Capa de Seguridad           │
│      (Protección - safety/)          │
│  - Sistema de confirmaciones       │
│  - Auditoría completa              │
│  - Parada de emergencia            │
│  - Control de permisos             │
└─────────────────────────────────────┘
```

### Flujo de ejecución

1. **Usuario envía orden** → Discord recibe el mensaje
2. **Análisis semántico** → Ollama interpreta la intención
3. **Detección de ambigüedades** → El agente pregunta si falta información
4. **Generación de plan** → Se crea un plan paso a paso
5. **Confirmación** → El usuario aprueba el plan
6. **Ejecución** → Se ejecutan las acciones una a una
7. **Verificación** → Cada paso se valida antes de continuar
8. **Informe** → Resultados enviados a Discord

### Componentes principales

| Módulo | Función |
|--------|---------|
| `bot/discord_client.py` | Cliente de Discord, manejo de comandos |
| `cognitive/ollama_client.py` | Conexión con Ollama API |
| `cognitive/planner.py` | Generación y gestión de planes |
| `execution/system_controller.py` | Comandos del sistema operativo |
| `execution/desktop_controller.py` | Control de ratón y teclado |
| `execution/browser_controller.py` | Automatización de navegador |
| `safety/confirmation_manager.py` | Sistema de confirmaciones |
| `safety/audit_logger.py` | Registro de todas las acciones |
| `safety/emergency_stop.py` | Parada de emergencia |
| `core/agent.py` | Orquestación central |

## Uso básico

Una vez iniciado, interactúa con el bot en Discord:

```
!agent instala Python 3.11 y configúralo en el PATH
```

El agente responderá con preguntas si necesita clarificación, luego ejecutará el plan paso a paso.

### Comandos de Discord

- `!agent <orden>` - Enviar orden al agente
- `!confirm <id>` - Confirmar acción pendiente
- `!deny <id>` - Denegar acción pendiente
- `!status` - Ver estado del agente
- `!stop <código>` - Parada de emergencia
- `!audit` - Ver registro de acciones


## Licencia

MIT - Ver [LICENSE](LICENSE) para más detalles.

---

**Uso bajo tu propia responsabilidad.** Diseñado para automatización autorizada y propósitos educativos.
