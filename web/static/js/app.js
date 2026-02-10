/**
 * HostBot Web Interface - Main Application
 */

// Global state
const state = {
    agentStatus: null,
    visionEnabled: false,
    autoMode: false,
    commandHistory: [],
    currentTasks: [],
    logs: []
};

// DOM Elements
const elements = {
    commandInput: document.getElementById('commandInput'),
    useVision: document.getElementById('useVision'),
    autoMode: document.getElementById('autoMode'),
    prioritySelect: document.getElementById('prioritySelect'),
    outputConsole: document.getElementById('outputConsole'),
    visionImage: document.getElementById('visionImage'),
    visionContainer: document.getElementById('visionContainer'),
    visionAnalysis: document.getElementById('visionAnalysis'),
    statusGrid: document.getElementById('statusGrid'),
    tasksList: document.getElementById('tasksList'),
    agentStatus: document.getElementById('agentStatus'),
    toastContainer: document.getElementById('toastContainer')
};

// Initialize application
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

async function initializeApp() {
    // Setup event listeners
    setupEventListeners();
    
    // Setup WebSocket listeners
    setupWebSocketListeners();
    
    // Initial status check
    await updateStatus();
    
    // Start periodic updates
    setInterval(updateStatus, 5000);
    setInterval(refreshTasks, 10000);
    
    // Check if setup is needed
    await checkSetupRequired();
    
    log('HostBot Web Interface iniciado', 'system');
    log('Conectando al agente...', 'info');
}

function setupEventListeners() {
    // Command input
    if (elements.commandInput) {
        elements.commandInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                executeCommand();
            }
        });
    }
    
    // Vision toggle
    if (elements.useVision) {
        elements.useVision.addEventListener('change', (e) => {
            state.visionEnabled = e.target.checked;
            log(`Visión ${state.visionEnabled ? 'activada' : 'desactivada'}`, 'info');
        });
    }
    
    // Auto mode toggle
    if (elements.autoMode) {
        elements.autoMode.addEventListener('change', (e) => {
            state.autoMode = e.target.checked;
            log(`Modo autónomo ${state.autoMode ? 'activado' : 'desactivado'}`, 'info');
        });
    }
}

function setupWebSocketListeners() {
    // Connection events
    wsClient.on('connected', () => {
        log('WebSocket conectado', 'success');
        updateConnectionStatus(true);
    });
    
    wsClient.on('disconnected', () => {
        log('WebSocket desconectado', 'warning');
        updateConnectionStatus(false);
    });
    
    // Status updates
    wsClient.on('status_update', (status) => {
        updateStatusDisplay(status);
    });
    
    // Screenshot updates
    wsClient.on('screenshot_update', (data) => {
        if (data.image) {
            displayScreenshot(data.image, data.analysis);
        }
    });
    
    // Command completion
    wsClient.on('command_complete', (result) => {
        handleCommandResult(result);
    });
}

// Command execution
async function executeCommand() {
    const command = elements.commandInput?.value.trim();
    if (!command) return;
    
    // Add to history
    state.commandHistory.push(command);
    if (state.commandHistory.length > 50) {
        state.commandHistory.shift();
    }
    
    // Clear input
    elements.commandInput.value = '';
    
    // Log command
    log(`> ${command}`, 'system');
    
    // Get options
    const useVision = elements.useVision?.checked || false;
    const priority = elements.prioritySelect?.value || 'medium';
    
    try {
        // Show loading
        showToast('Ejecutando comando...', 'info');
        
        // Execute via API
        const result = await api.executeCommand(command, useVision, priority);
        
        handleCommandResult(result);
        
    } catch (error) {
        log(`Error: ${error.message}`, 'error');
        showToast('Error al ejecutar comando', 'error');
    }
}

function handleCommandResult(result) {
    if (result.success) {
        if (result.result?.requires_approval) {
            log('Comando requiere aprobación', 'warning');
            showToast('Revisa el plan y aprueba para continuar', 'warning');
        } else if (result.result?.requires_clarification) {
            log('Se necesita clarificación:', 'warning');
            result.result.questions?.forEach(q => log(`  ? ${q}`, 'warning'));
        } else {
            log('Comando ejecutado exitosamente', 'success');
            
            // Display result
            if (result.result?.summary) {
                log(result.result.summary, 'info');
            }
        }
    } else {
        log(`Error: ${result.error || 'Unknown error'}`, 'error');
        showToast('Error en la ejecución', 'error');
    }
    
    // Refresh status
    updateStatus();
}

// Vision functions
async function refreshVision() {
    try {
        showToast('Capturando pantalla...', 'info');
        
        const result = await api.captureScreen();
        
        if (result.success) {
            displayScreenshot(result.screenshot, result.analysis);
            log('Pantalla capturada y analizada', 'success');
        } else {
            log(`Error de visión: ${result.error}`, 'error');
        }
    } catch (error) {
        log(`Error: ${error.message}`, 'error');
    }
}

function displayScreenshot(imageData, analysis) {
    if (elements.visionImage) {
        elements.visionImage.src = `data:image/png;base64,${imageData}`;
        elements.visionImage.style.display = 'block';
    }
    
    // Hide placeholder
    const placeholder = elements.visionContainer?.querySelector('.vision-placeholder');
    if (placeholder) {
        placeholder.style.display = 'none';
    }
    
    // Show analysis
    if (elements.visionAnalysis && analysis) {
        elements.visionAnalysis.innerHTML = `
            <strong>Análisis:</strong> ${analysis.description || 'No disponible'}<br>
            ${analysis.elements ? `Elementos detectados: ${analysis.elements.length}` : ''}
        `;
    }
}

function toggleVision() {
    elements.useVision.checked = !elements.useVision.checked;
    state.visionEnabled = elements.useVision.checked;
    showToast(`Visión ${state.visionEnabled ? 'activada' : 'desactivada'}`, 'info');
}

// Status updates
async function updateStatus() {
    try {
        const result = await api.getStatus();
        
        if (result.success) {
            updateStatusDisplay(result.status);
        } else {
            updateConnectionStatus(false);
        }
    } catch (error) {
        console.error('Status update error:', error);
        updateConnectionStatus(false);
    }
}

function updateStatusDisplay(status) {
    state.agentStatus = status;
    
    // Update status indicator
    if (elements.agentStatus) {
        const isOnline = status.healthy && !status.emergency_stop;
        elements.agentStatus.className = `status-indicator ${isOnline ? 'online' : 'error'}`;
        elements.agentStatus.querySelector('.status-text').textContent = 
            isOnline ? 'En línea' : (status.emergency_stop ? 'EMERGENCY STOP' : 'Desconectado');
    }
    
    // Update status grid
    if (elements.statusGrid) {
        elements.statusGrid.innerHTML = `
            <div class="status-card">
                <div class="status-icon">${status.vision_available ? '👁️' : '👁️‍🗨️'}</div>
                <div class="status-label">Visión</div>
                <div class="status-value">${status.vision_available ? 'ON' : 'OFF'}</div>
            </div>
            <div class="status-card">
                <div class="status-icon">🧠</div>
                <div class="status-label">Brain</div>
                <div class="status-value">${status.brain_available ? 'ON' : 'OFF'}</div>
            </div>
            <div class="status-card">
                <div class="status-icon">⚡</div>
                <div class="status-label">Estado</div>
                <div class="status-value">${status.state?.toUpperCase() || 'IDLE'}</div>
            </div>
            <div class="status-card">
                <div class="status-icon">📋</div>
                <div class="status-label">Tareas</div>
                <div class="status-value">${status.brain_active_tasks || 0}</div>
            </div>
            <div class="status-card">
                <div class="status-icon">🔒</div>
                <div class="status-label">Seguridad</div>
                <div class="status-value">${status.safety_mode?.toUpperCase() || 'STRICT'}</div>
            </div>
            <div class="status-card">
                <div class="status-icon">🚨</div>
                <div class="status-label">Emergency</div>
                <div class="status-value" style="color: ${status.emergency_stop ? 'var(--accent-red)' : 'var(--accent-green)'}">
                    ${status.emergency_stop ? 'STOP' : 'OK'}
                </div>
            </div>
        `;
    }
}

function updateConnectionStatus(connected) {
    if (elements.agentStatus) {
        elements.agentStatus.className = `status-indicator ${connected ? 'online' : 'error'}`;
        elements.agentStatus.querySelector('.status-text').textContent = 
            connected ? 'En línea' : 'Desconectado';
    }
}

// Tasks
async function refreshTasks() {
    try {
        const result = await api.getTasks();
        
        if (result.success) {
            updateTasksList(result.tasks);
        }
    } catch (error) {
        console.error('Tasks refresh error:', error);
    }
}

function updateTasksList(tasks) {
    state.currentTasks = tasks;
    
    if (!elements.tasksList) return;
    
    if (tasks.length === 0) {
        elements.tasksList.innerHTML = '<div class="task-empty">No hay tareas activas</div>';
        return;
    }
    
    elements.tasksList.innerHTML = tasks.map(task => `
        <div class="task-item ${task.status}">
            <div class="task-info">
                <div class="task-goal">${escapeHtml(task.goal.substring(0, 50))}${task.goal.length > 50 ? '...' : ''}</div>
                <div class="task-meta">
                    ID: ${task.id.substring(0, 8)} | 
                    Prioridad: ${task.priority} | 
                    ${task.active ? `Progreso: ${task.progress}/${task.total_steps}` : ''}
                </div>
            </div>
            <div class="task-status ${task.status}">${task.status}</div>
        </div>
    `).join('');
}

// Emergency functions
async function triggerEmergency() {
    if (!confirm('¿Estás seguro de activar la PARADA DE EMERGENCIA?')) {
        return;
    }
    
    try {
        const result = await api.emergencyStop();
        
        if (result.success) {
            showToast('🚨 EMERGENCY STOP ACTIVADO', 'error');
            log('EMERGENCY STOP activado por usuario web', 'error');
            updateStatus();
        } else {
            showToast('Error al activar emergency stop', 'error');
        }
    } catch (error) {
        showToast('Error de conexión', 'error');
    }
}

async function resetEmergency() {
    try {
        const result = await api.emergencyReset();
        
        if (result.success) {
            showToast('Emergency stop reseteado', 'success');
            log('Emergency stop reseteado', 'success');
            updateStatus();
        }
    } catch (error) {
        showToast('Error al resetear', 'error');
    }
}

// Quick actions
function quickAction(action) {
    switch (action) {
        case 'screenshot':
            refreshVision();
            break;
        case 'system_info':
            executeCommandDirect('Obtener información del sistema');
            break;
        case 'list_processes':
            executeCommandDirect('Listar procesos activos');
            break;
        default:
            log(`Acción rápida: ${action}`, 'info');
    }
}

async function executeCommandDirect(command) {
    elements.commandInput.value = command;
    await executeCommand();
}

// Console functions
function log(message, type = 'info') {
    const timestamp = new Date().toLocaleTimeString('es-ES', { hour12: false });
    
    const line = document.createElement('div');
    line.className = `console-line ${type} fade-in`;
    line.innerHTML = `
        <span class="timestamp">[${timestamp}]</span>
        <span class="message">${escapeHtml(message)}</span>
    `;
    
    elements.outputConsole?.appendChild(line);
    elements.outputConsole?.scrollTo(0, elements.outputConsole.scrollHeight);
    
    // Keep only last 100 lines
    const lines = elements.outputConsole?.querySelectorAll('.console-line');
    if (lines && lines.length > 100) {
        lines[0].remove();
    }
}

function clearOutput() {
    if (elements.outputConsole) {
        elements.outputConsole.innerHTML = '';
    }
}

function copyOutput() {
    const text = Array.from(elements.outputConsole?.querySelectorAll('.console-line') || [])
        .map(line => line.textContent)
        .join('\n');
    
    navigator.clipboard.writeText(text).then(() => {
        showToast('Output copiado al portapapeles', 'success');
    });
}

// Setup check
async function checkSetupRequired() {
    try {
        const result = await api.getConfigStatus();
        
        if (!result.success || !result.configured) {
            const missing = result.missing?.join(', ') || 'configuración';
            log(`Configuración incompleta. Falta: ${missing}`, 'warning');
            log('Ve a /setup para configurar HostBot', 'warning');
            
            // Show setup notification
            setTimeout(() => {
                showToast('⚠️ Configuración requerida. Ve al Setup Wizard', 'warning');
            }, 2000);
        }
    } catch (error) {
        console.error('Setup check error:', error);
    }
}

// Toast notifications
function showToast(message, type = 'info', duration = 3000) {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    
    elements.toastContainer?.appendChild(toast);
    
    // Animate in
    requestAnimationFrame(() => {
        toast.style.animation = 'slide-in 0.3s ease';
    });
    
    // Remove after duration
    setTimeout(() => {
        toast.style.animation = 'fade-out 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// Utility functions
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Export functions for global access
window.executeCommand = executeCommand;
window.refreshVision = refreshVision;
window.toggleVision = toggleVision;
window.triggerEmergency = triggerEmergency;
window.resetEmergency = resetEmergency;
window.quickAction = quickAction;
window.clearOutput = clearOutput;
window.copyOutput = copyOutput;
window.refreshTasks = refreshTasks;
window.showToast = showToast;
