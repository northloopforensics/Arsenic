// Utility helper functions for the Arsenic Mobile Triage Tool

// Format file sizes in human readable format
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Format timestamps in a readable format
function formatTimestamp(timestamp) {
    if (!timestamp) return 'Unknown';
    
    try {
        const date = new Date(timestamp);
        return date.toLocaleString();
    } catch (error) {
        return 'Invalid Date';
    }
}

// Format duration in human readable format
function formatDuration(seconds) {
    if (seconds < 60) {
        return `${Math.round(seconds)}s`;
    } else if (seconds < 3600) {
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = Math.round(seconds % 60);
        return `${minutes}m ${remainingSeconds}s`;
    } else {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        return `${hours}h ${minutes}m`;
    }
}

// Debounce function for input events
function debounce(func, wait, immediate) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            timeout = null;
            if (!immediate) func(...args);
        };
        const callNow = immediate && !timeout;
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
        if (callNow) func(...args);
    };
}

// Throttle function for frequent events
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Parse error messages from API responses
function parseErrorMessage(error) {
    if (typeof error === 'string') {
        return error;
    }
    
    if (error && error.message) {
        return error.message;
    }
    
    if (error && error.error) {
        return error.error;
    }
    
    return 'An unknown error occurred';
}

// Validate case number format
function validateCaseNumber(caseNumber) {
    if (!caseNumber || caseNumber.trim() === '') {
        return { valid: false, message: 'Case number cannot be empty' };
    }
    
    // Basic validation - alphanumeric and some special characters
    const regex = /^[a-zA-Z0-9_-]+$/;
    if (!regex.test(caseNumber.trim())) {
        return { 
            valid: false, 
            message: 'Case number can only contain letters, numbers, hyphens, and underscores' 
        };
    }
    
    return { valid: true };
}

// Validate file paths
function validatePath(path) {
    if (!path || path.trim() === '') {
        return { valid: false, message: 'Path cannot be empty' };
    }
    
    // Basic path validation
    const invalidChars = /[<>:"|?*]/;
    if (invalidChars.test(path)) {
        return { 
            valid: false, 
            message: 'Path contains invalid characters' 
        };
    }
    
    return { valid: true };
}

// Copy text to clipboard
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        return true;
    } catch (error) {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.opacity = '0';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        try {
            const successful = document.execCommand('copy');
            document.body.removeChild(textArea);
            return successful;
        } catch (fallbackError) {
            document.body.removeChild(textArea);
            return false;
        }
    }
}

// Download text as file
function downloadAsFile(content, filename, contentType = 'text/plain') {
    const blob = new Blob([content], { type: contentType });
    const url = URL.createObjectURL(blob);
    
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    URL.revokeObjectURL(url);
}

// Format device information for display
function formatDeviceInfo(deviceInfo) {
    if (!deviceInfo || typeof deviceInfo !== 'object') {
        return 'No device information available';
    }
    
    const entries = Object.entries(deviceInfo)
        .filter(([key, value]) => value != null && value !== '' && key !== 'error')
        .map(([key, value]) => {
            // Format the key name
            const formattedKey = key.replace(/([A-Z])/g, ' $1')
                                   .replace(/^./, str => str.toUpperCase())
                                   .trim();
            return `${formattedKey}: ${value}`;
        });
    
    return entries.length > 0 ? entries.join('\n') : 'No device information available';
}

// Generate unique IDs
function generateId() {
    return Date.now().toString(36) + Math.random().toString(36).substr(2);
}

// Check if a value is empty
function isEmpty(value) {
    return value == null || 
           (typeof value === 'string' && value.trim() === '') ||
           (Array.isArray(value) && value.length === 0) ||
           (typeof value === 'object' && Object.keys(value).length === 0);
}

// Deep clone objects
function deepClone(obj) {
    if (obj === null || typeof obj !== 'object') {
        return obj;
    }
    
    if (obj instanceof Date) {
        return new Date(obj.getTime());
    }
    
    if (Array.isArray(obj)) {
        return obj.map(item => deepClone(item));
    }
    
    const cloned = {};
    for (const key in obj) {
        if (obj.hasOwnProperty(key)) {
            cloned[key] = deepClone(obj[key]);
        }
    }
    
    return cloned;
}

// Capitalize first letter of string
function capitalize(str) {
    if (!str || typeof str !== 'string') return str;
    return str.charAt(0).toUpperCase() + str.slice(1);
}

// Convert camelCase to Title Case
function camelToTitle(str) {
    if (!str || typeof str !== 'string') return str;
    return str.replace(/([A-Z])/g, ' $1')
              .replace(/^./, str => str.toUpperCase())
              .trim();
}

// Loading state management
class LoadingManager {
    constructor() {
        this.loadingCount = 0;
        this.overlay = null;
    }
    
    show(message = 'Loading...') {
        this.loadingCount++;
        
        if (!this.overlay) {
            this.overlay = document.getElementById('loading-overlay');
        }
        
        if (this.overlay) {
            const loadingText = this.overlay.querySelector('#loading-text');
            if (loadingText) {
                loadingText.textContent = message;
            }
            this.overlay.style.display = 'flex';
        }
    }
    
    hide() {
        this.loadingCount = Math.max(0, this.loadingCount - 1);
        
        if (this.loadingCount === 0 && this.overlay) {
            this.overlay.style.display = 'none';
        }
    }
    
    isVisible() {
        return this.loadingCount > 0;
    }
}

// Global loading manager instance
const loadingManager = new LoadingManager();

// Export functions for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        formatFileSize,
        formatTimestamp,
        formatDuration,
        debounce,
        throttle,
        escapeHtml,
        parseErrorMessage,
        validateCaseNumber,
        validatePath,
        copyToClipboard,
        downloadAsFile,
        formatDeviceInfo,
        generateId,
        isEmpty,
        deepClone,
        capitalize,
        camelToTitle,
        LoadingManager,
        loadingManager
    };
}
