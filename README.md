# 🤖 HostBot - Agente Autónomo de Control Total

**HostBot** es un agente autónomo de propósito general capaz de controlar completamente un ordenador Windows mediante comandos en lenguaje natural, ya sea a través de Discord o una interfaz web moderna.

## ✨ Características Principales

### 🧠 Inteligencia Artificial
- **Ollama Local**: Usa modelos de IA locales (Llama, Mistral, etc.)
- **Brain Orchestrator**: Coordinador central de IA que gestiona múltiples modelos
- **Planificación Inteligente**: Genera planes paso a paso para tareas complejas
- **Razonamiento Encadenado**: Capacidad de auto-evaluación y corrección

### 👁️ Visión por Computadora
- **Captura de Pantalla**: Análisis visual del escritorio en tiempo real
- **Detección de Elementos**: Encuentra botones, campos de texto, etc.
- **OCR Inteligente**: Lee texto visible en pantalla
- **Modo "Ver y Actuar"**: Toma decisiones basadas en lo que ve

### 🎮 Control Total del Sistema
- **Escritorio**: Control completo de ratón y teclado
- **Sistema**: Ejecución de comandos, gestión de archivos y procesos
- **Navegador**: Automatización web con Playwright
- **Software**: Instalación y configuración de aplicaciones

### 🛡️ Seguridad Avanzada
- **Confirmaciones Interactivas**: Pregunta antes de acciones críticas
- **Modos de Seguridad**: Strict / Moderate / Minimal
- **Parada de Emergencia**: Botón de STOP inmediato
- **Auditoría Completa**: Registro de todas las acciones

### 🌐 Interfaz Web Moderna
- **Dashboard en Tiempo Real**: WebSocket para actualizaciones instantáneas
- **Setup Wizard**: Configuración guiada paso a paso
- **Vista Previa de Pantalla**: Captura y análisis visual
- **Tema Oscuro Tech**: Diseño moderno con efectos neón

## 🚀 Instalación Rápida

### 1. Clonar el Repositorio
```bash
git clone https://github.com/litelis/HostBot.git
cd HostBot
```

### 2. Ejecutar Setup
```bash
python setup.py
```

El setup interactivo te guiará para:
- Instalar dependencias (con o sin virtual environment)
- Configurar Discord Bot
- Configurar Ollama
- Seleccionar permisos del sistema

### 3. Iniciar Servicios

**Interfaz Web:**
```bash
cd web
python main.py
```
Accede a: http://localhost:8080

**Bot de Discord:**
```bash
python main.py
```

## 📋 Configuración

### Discord Bot
1. Ve a [Discord Developer Portal](https://discord.com/developers/applications)
2. Crea una nueva aplicación
3. En la sección "Bot", genera un token
4. Activa estos intents:
   - MESSAGE CONTENT INTENT
   - SERVER MEMBERS INTENT
5. Copia el token al archivo `.env`

### Ollama
1. Descarga [Ollama](https://ollama.ai)
2. Instala un modelo:
```bash
ollama pull llama3.2
ollama pull llava  # Para visión (opcional)
```
3. Verifica que Ollama está corriendo:
```bash
ollama list
```

## 🎯 Uso

### Interfaz Web
1. Abre http://localhost:8080
2. Si es primera vez, el Setup Wizard te guiará
3. En el Dashboard, escribe comandos en lenguaje natural:
   - "Abre Chrome y busca Python tutorials"
   - "Toma una captura de pantalla y dime qué ves"
   - "Instala VS Code"
   - "Automatiza el login en GitHub"

### Discord
Envía comandos en el canal configurado:
```
!agent Abre el navegador y busca las últimas noticias de tecnología
!agent Toma una captura de pantalla
!agent Instala Node.js
```

## 🛠️ Arquitectura

```
HostBot/
├── bot/                    # Discord bot
├── cognitive/              # IA y planificación
│   ├── brain_orchestrator.py   # Coordinador central
│   ├── ollama_client.py
│   ├── planner.py
│   └── prompt_templates.py
├── vision/                 # Visión por computadora
│   ├── screen_capture.py
│   ├── visual_analyzer.py
│   └── vision_orchestrator.py
├── execution/              # Control del sistema
│   ├── system_controller.py
│   ├── desktop_controller.py
│   ├── browser_controller.py
│   └── application_controller.py
├── safety/                 # Seguridad y auditoría
│   ├── audit_logger.py
│   ├── confirmation_manager.py
│   ├── emergency_stop.py
│   └── permission_guard.py
├── web/                    # Interfaz web
│   ├── main.py            # FastAPI server
│   ├── templates/         # HTML templates
│   └── static/            # CSS, JS
└── core/
    └── agent.py           # Núcleo del agente
```

## 🔧 Comandos Disponibles

### Control de Escritorio
- Mover ratón a coordenadas
- Clics (izquierdo, derecho, doble)
- Escribir texto
- Presionar teclas especiales
- Capturas de pantalla

### Sistema
- Ejecutar comandos de terminal
- Gestión de archivos (crear, leer, modificar, eliminar)
- Gestión de procesos (listar, iniciar, detener)
- Información del sistema

### Navegador
- Navegar a URLs
- Interactuar con elementos (click, type)
- Extraer información
- Automatización de flujos

### Aplicaciones
- Instalar software (winget, chocolatey)
- Desinstalar software
- Actualizar software
- Configurar aplicaciones

## 🎨 Personalización

### Variables de Entorno (.env)
```env
# Discord
DISCORD_TOKEN=tu_token_aqui
DISCORD_ADMIN_USER_ID=tu_user_id
DISCORD_GUILD_ID=id_servidor_opcional

# Ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.2

# Seguridad
SAFETY_MODE=strict  # strict, moderate, minimal
EMERGENCY_STOP_CODE=STOP123

# Permisos
ALLOW_DESKTOP_CONTROL=true
ALLOW_SYSTEM_COMMANDS=true
ALLOW_BROWSER_AUTOMATION=true
ALLOW_SOFTWARE_INSTALLATION=false
```

## 🔄 Actualización

```bash
python update.py --status    # Verificar actualizaciones
python update.py --apply     # Aplicar actualización
```

## 🆘 Solución de Problemas

### Ollama no conecta
```bash
# Verificar que Ollama está corriendo
curl http://localhost:11434/api/tags

# Reiniciar Ollama
ollama serve
```

### Discord bot no responde
- Verificar que el token es correcto
- Asegurar que los intents están activados
- Comprobar que el bot tiene permisos en el servidor

### Visión no funciona
- Instalar modelo llava: `ollama pull llava`
- Verificar que Pillow está instalado: `pip install Pillow`
- En Windows, asegurar permisos de captura de pantalla

## ⚠️ Advertencia de Seguridad

**HostBot tiene control total del sistema.** Usar con precaución:

1. **Nunca** compartas tu archivo `.env`
2. Usa el modo **strict** en entornos de producción
3. Configura un **código de emergencia** seguro
4. Revisa siempre los planes antes de aprobar
5. Mantén el sistema actualizado

## 📄 Licencia

MIT License - Ver [LICENSE](LICENSE) para detalles.

## 🤝 Contribuir

1. Fork el repositorio
2. Crea una rama: `git checkout -b feature/nueva-funcionalidad`
3. Commit tus cambios: `git commit -am 'Añadir nueva funcionalidad'`
4. Push a la rama: `git push origin feature/nueva-funcionalidad`
5. Abre un Pull Request

## 📞 Soporte

- Issues: [GitHub Issues](https://github.com/litelis/HostBot/issues)
- Discord: Tu propio servidor con HostBot instalado 😉

---

**¡HostBot está listo para ayudarte!** 🚀
