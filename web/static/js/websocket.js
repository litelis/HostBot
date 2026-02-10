/**
 * HostBot WebSocket Client
 * Handles real-time communication with the server
 */

class WebSocketClient {
    constructor() {
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.listeners = new Map();
        this.isConnected = false;
    }

    /**
     * Connect to WebSocket server
     */
    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        try {
            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.emit('connected', {});
                this.send({ action: 'ping' });
            };

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleMessage(data);
                } catch (error) {
                    console.error('WebSocket message parse error:', error);
                }
            };

            this.ws.onclose = () => {
                console.log('WebSocket disconnected');
                this.isConnected = false;
                this.emit('disconnected', {});
                this.attemptReconnect();
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.emit('error', error);
            };

        } catch (error) {
            console.error('WebSocket connection error:', error);
            this.attemptReconnect();
        }
    }

    /**
     * Attempt to reconnect
     */
    attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnection attempts reached');
            this.emit('reconnect_failed', {});
            return;
        }

        this.reconnectAttempts++;
        const delay = this.reconnectDelay * this.reconnectAttempts;

        console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);

        setTimeout(() => {
            this.connect();
        }, delay);
    }

    /**
     * Handle incoming messages
     */
    handleMessage(data) {
        const { type, ...payload } = data;
        this.emit(type, payload);

        // Handle specific message types
        switch (type) {
            case 'pong':
                // Connection is alive
                break;
            case 'status':
                this.emit('status_update', payload.data);
                break;
            case 'screenshot':
                this.emit('screenshot_update', payload.data);
                break;
            case 'command_result':
                this.emit('command_complete', payload.data);
                break;
            case 'log':
                this.emit('log_entry', payload.data);
                break;
        }
    }

    /**
     * Send message to server
     */
    send(data) {
        if (this.isConnected && this.ws) {
            this.ws.send(JSON.stringify(data));
        } else {
            console.warn('WebSocket not connected, cannot send message');
        }
    }

    /**
     * Subscribe to events
     */
    on(event, callback) {
        if (!this.listeners.has(event)) {
            this.listeners.set(event, new Set());
        }
        this.listeners.get(event).add(callback);

        // Return unsubscribe function
        return () => {
            this.listeners.get(event)?.delete(callback);
        };
    }

    /**
     * Emit event to listeners
     */
    emit(event, data) {
        const callbacks = this.listeners.get(event);
        if (callbacks) {
            callbacks.forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error(`Error in event listener for ${event}:`, error);
                }
            });
        }
    }

    /**
     * Disconnect WebSocket
     */
    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        this.isConnected = false;
    }

    /**
     * Request status update
     */
    requestStatus() {
        this.send({ action: 'get_status' });
    }

    /**
     * Request screen capture
     */
    requestScreenshot() {
        this.send({ action: 'capture_screen' });
    }

    /**
     * Execute command via WebSocket
     */
    executeCommand(command, useVision = false) {
        this.send({
            action: 'execute_command',
            command,
            use_vision: useVision
        });
    }
}

// Create global instance
const wsClient = new WebSocketClient();

// Auto-connect when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    wsClient.connect();
});

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { WebSocketClient, wsClient };
}
