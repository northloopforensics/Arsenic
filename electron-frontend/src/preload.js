const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electronAPI', {
    // Dialog methods
    openDirectory: () => ipcRenderer.invoke('dialog:openDirectory'),
    openFile: (options) => ipcRenderer.invoke('dialog:openFile', options),
    
    // Shell methods
    openExternal: (url) => ipcRenderer.invoke('shell:openExternal', url),
    openPath: (path) => ipcRenderer.invoke('shell:openPath', path),
    
    // App methods
    getVersion: () => ipcRenderer.invoke('app:getVersion'),
    getPlatform: () => ipcRenderer.invoke('app:getPlatform'),
    
    // CSV file operations - these now use IPC to the main process
    scanForCSVReports: (caseDirectory) => ipcRenderer.invoke('csv:scanReports', caseDirectory),
    readCSVFile: (caseDirectory, dataType) => ipcRenderer.invoke('csv:readFile', caseDirectory, dataType),
    
    // Android CSV operations
    scanForAndroidCSVReports: (caseDirectory) => ipcRenderer.invoke('android-csv:scanReports', caseDirectory),
    readAndroidCSVFile: (caseDirectory, dataType) => ipcRenderer.invoke('android-csv:readFile', caseDirectory, dataType),
    
    // File system operations
    getFileStats: (filePath) => ipcRenderer.invoke('fs:getFileStats', filePath),
    
    // ADB operations
    createADBBackup: (options) => ipcRenderer.invoke('adb:createBackup', options),
    getADBDevices: () => ipcRenderer.invoke('adb:getDevices'),
    
    // ADB progress events
    onADBBackupProgress: (callback) => ipcRenderer.on('adb-backup-progress', callback),
    removeADBBackupListener: (callback) => ipcRenderer.removeListener('adb-backup-progress', callback)
});

// Expose a simple API for making HTTP requests to Flask backend
contextBridge.exposeInMainWorld('flaskAPI', {
    baseURL: 'http://127.0.0.1:3131',
    
    // Generic request method
    request: async (method, endpoint, data = null) => {
        const url = `http://127.0.0.1:3131${endpoint}`;
        
        const options = {
            method: method,
            headers: {
                'Content-Type': 'application/json',
            }
        };
        
        if (data && (method === 'POST' || method === 'PUT')) {
            options.body = JSON.stringify(data);
        }
        
        try {
            const response = await fetch(url, options);
            const result = await response.json();
            
            if (!response.ok) {
                throw new Error(result.error || `HTTP ${response.status}`);
            }
            
            return result;
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    },
    
    // Convenience methods
    get: (endpoint) => {
        return contextBridge.exposeInMainWorld('flaskAPI').request('GET', endpoint);
    },
    
    post: (endpoint, data) => {
        return contextBridge.exposeInMainWorld('flaskAPI').request('POST', endpoint, data);
    }
});

// Also expose individual API methods for easier use
contextBridge.exposeInMainWorld('api', {
    // System
    getSystemStatus: () => flaskAPI.request('GET', '/api/system/status'),
    
    // Case management
    getCaseInfo: () => flaskAPI.request('GET', '/api/case/info'),
    updateCaseInfo: (data) => flaskAPI.request('POST', '/api/case/update', data),
    
    // Device status
    getIOSStatus: () => flaskAPI.request('GET', '/api/devices/ios/status'),
    getAndroidStatus: () => flaskAPI.request('GET', '/api/devices/android/status'),
    getIOSInfo: () => flaskAPI.request('GET', '/api/devices/ios/info'),
    getAndroidInfo: () => flaskAPI.request('GET', '/api/devices/android/info'),
    
    // iOS operations
    getIOSApps: () => flaskAPI.request('GET', '/api/ios/apps'),
    startIOSBackup: () => flaskAPI.request('POST', '/api/ios/backup/start'),
    getIOSBackupStatus: (operationId) => flaskAPI.request('GET', `/api/ios/backup/status/${operationId}`),
    parseIOSBackup: (data) => flaskAPI.request('POST', '/api/ios/backup/parse', data),
    
    // Android operations
    startAndroidTriage: (data) => flaskAPI.request('POST', '/api/android/triage/start', data),
    getAndroidTriageStatus: (operationId) => flaskAPI.request('GET', `/api/android/triage/status/${operationId}`),
    
    // Logs
    getLogs: () => flaskAPI.request('GET', '/api/logs')
});
