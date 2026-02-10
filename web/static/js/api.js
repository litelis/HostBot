/**
 * HostBot Web API Client
 * Handles all HTTP API communication
 */

const API_BASE = '';

const api = {
    /**
     * Get agent status
     */
    async getStatus() {
        const response = await fetch(`${API_BASE}/api/status`);
        return await response.json();
    },

    /**
     * Get configuration status
     */
    async getConfigStatus() {
        const response = await fetch(`${API_BASE}/api/config/status`);
        return await response.json();
    },

    /**
     * Update configuration
     */
    async updateConfig(config) {
        const response = await fetch(`${API_BASE}/api/config`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        });
        return await response.json();
    },

    /**
     * Execute a command
     */
    async executeCommand(command, useVision = false, priority = 'medium') {
        const response = await fetch(`${API_BASE}/api/command`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                command,
                use_vision: useVision,
                priority
            })
        });
        return await response.json();
    },

    /**
     * Capture screen
     */
    async captureScreen() {
        const response = await fetch(`${API_BASE}/api/vision`);
        return await response.json();
    },

    /**
     * Analyze screen
     */
    async analyzeScreen() {
        const response = await fetch(`${API_BASE}/api/vision/analyze`, {
            method: 'POST'
        });
        return await response.json();
    },

    /**
     * Get tasks
     */
    async getTasks() {
        const response = await fetch(`${API_BASE}/api/tasks`);
        return await response.json();
    },

    /**
     * Trigger emergency stop
     */
    async emergencyStop() {
        const response = await fetch(`${API_BASE}/api/emergency-stop`, {
            method: 'POST'
        });
        return await response.json();
    },

    /**
     * Reset emergency stop
     */
    async emergencyReset() {
        const response = await fetch(`${API_BASE}/api/emergency-reset`, {
            method: 'POST'
        });
        return await response.json();
    }
};

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
}
