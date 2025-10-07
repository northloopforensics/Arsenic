// Notification system for toast messages

class NotificationManager {
    constructor() {
        this.container = null;
        this.notifications = new Map();
        this.nextId = 1;
        
        this.initialize();
    }

    initialize() {
        // Create container if it doesn't exist
        this.container = document.getElementById('toast-container');
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.id = 'toast-container';
            this.container.className = 'toast-container';
            document.body.appendChild(this.container);
        }
    }

    show(message, type = 'info', duration = 5000) {
        const id = this.nextId++;
        const toast = this.createToast(id, message, type);
        
        this.container.appendChild(toast);
        this.notifications.set(id, toast);
        
        // Auto-remove after duration
        if (duration > 0) {
            setTimeout(() => {
                this.remove(id);
            }, duration);
        }
        
        return id;
    }

    createToast(id, message, type) {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.dataset.id = id;
        
        const icon = this.getIcon(type);
        
        toast.innerHTML = `
            <span class="toast-icon">${icon}</span>
            <span class="toast-message">${this.escapeHtml(message)}</span>
            <button class="toast-close" onclick="notificationManager.remove(${id})">&times;</button>
        `;
        
        return toast;
    }

    remove(id) {
        const toast = this.notifications.get(id);
        if (toast) {
            toast.classList.add('removing');
            
            // Remove from DOM after animation
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
                this.notifications.delete(id);
            }, 300);
        }
    }

    removeAll() {
        this.notifications.forEach((toast, id) => {
            this.remove(id);
        });
    }

    getIcon(type) {
        switch (type) {
            case 'success': return '✓';
            case 'error': return '✕';
            case 'warning': return '⚠';
            case 'info': 
            default: return 'ℹ';
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Global notification manager instance
const notificationManager = new NotificationManager();

// Global helper function
function showNotification(message, type = 'info', duration = 5000) {
    return notificationManager.show(message, type, duration);
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { NotificationManager, showNotification };
}
