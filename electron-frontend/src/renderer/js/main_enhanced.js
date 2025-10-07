// Main JavaScript for Arsenic Mobile Triage Tool

// Global state
let currentPlatform = 'android';
let currentTab = {};
let deviceStatus = {
    android: false,
    ios: false
};

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    console.log('Arsenic Mobile Triage Tool initialized');
    
    // Set up event listeners
    setupEventListeners();
    
    // Start device monitoring
    startDeviceMonitoring();
    
    // Initialize current tab tracking
    currentTab = {
        android: 'triage',
        ios: 'backup',
        parser: 'main'
    };
    
    console.log('Application ready');
});

function setupEventListeners() {
    // Directory browser
    const browseBtn = document.getElementById('browse-directory');
    if (browseBtn) {
        browseBtn.addEventListener('click', selectOutputDirectory);
    }
    
    // Case number validation
    const caseInput = document.getElementById('case-number');
    if (caseInput) {
        caseInput.addEventListener('input', validateCaseInfo);
    }
    
    // Output directory validation
    const outputInput = document.getElementById('output-directory');
    if (outputInput) {
        outputInput.addEventListener('input', validateCaseInfo);
    }
}

// Platform switching
function switchPlatform(platform) {
    console.log(`Switching to platform: ${platform}`);
    
    // Update active platform button
    document.querySelectorAll('.platform-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-platform="${platform}"]`).classList.add('active');
    
    // Show/hide platform content
    document.querySelectorAll('.platform-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(`${platform}-content`).classList.add('active');
    
    currentPlatform = platform;
    
    // Trigger immediate device check for the selected platform
    if (platform === 'android') {
        checkAndroidDeviceStatus();
    } else if (platform === 'ios') {
        checkiOSDeviceStatus();
    }
}

// Tab switching within platforms
function switchTab(platform, tab) {
    console.log(`Switching to tab: ${platform}-${tab}`);
    
    // Update active tab button
    const tabContainer = document.querySelector(`#${platform}-content .tab-buttons`);
    if (tabContainer) {
        tabContainer.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        tabContainer.querySelector(`[data-tab="${platform}-${tab}"]`).classList.add('active');
    }
    
    // Show/hide tab content
    const contentContainer = document.querySelector(`#${platform}-content .tab-content`);
    if (contentContainer) {
        contentContainer.querySelectorAll('.tab-pane').forEach(pane => {
            pane.classList.remove('active');
        });
        const targetPane = contentContainer.querySelector(`#${platform}-${tab}`);
        if (targetPane) {
            targetPane.classList.add('active');
        }
    }
    
    currentTab[platform] = tab;
}

// Directory selection
async function selectOutputDirectory() {
    try {
        const result = await electronAPI.selectDirectory();
        if (result && !result.canceled && result.filePaths.length > 0) {
            const selectedPath = result.filePaths[0];
            document.getElementById('output-directory').value = selectedPath;
            validateCaseInfo();
        }
    } catch (error) {
        console.error('Error selecting directory:', error);
        showNotification('Failed to select directory', 'error');
    }
}

// File selection for parser
async function selectBackupFile() {
    try {
        const result = await electronAPI.selectFile({
            title: 'Select Backup File',
            filters: [
                { name: 'All Files', extensions: ['*'] },
                { name: 'Backup Files', extensions: ['backup', 'ab', 'tar', 'zip'] }
            ]
        });
        
        if (result && !result.canceled && result.filePaths.length > 0) {
            const selectedPath = result.filePaths[0];
            document.getElementById('backup-file').value = selectedPath;
            document.getElementById('start-parsing').disabled = false;
            updateParserStatus('Backup file selected: ' + selectedPath.split('/').pop());
        }
    } catch (error) {
        console.error('Error selecting backup file:', error);
        showNotification('Failed to select backup file', 'error');
    }
}

// Validate case information
function validateCaseInfo() {
    const caseNumber = document.getElementById('case-number').value.trim();
    const outputDir = document.getElementById('output-directory').value.trim();
    
    const isValid = caseNumber && outputDir;
    
    // Enable/disable operation buttons based on validation
    updateOperationButtons(isValid);
    
    return isValid;
}

function updateOperationButtons(isValid) {
    const buttons = [
        'start-android-triage',
        'start-ios-backup'
    ];
    
    buttons.forEach(buttonId => {
        const button = document.getElementById(buttonId);
        if (button) {
            button.disabled = !isValid || !deviceStatus[currentPlatform];
        }
    });
}

// Device monitoring
function startDeviceMonitoring() {
    // Check device status every 3 seconds
    setInterval(() => {
        checkAndroidDeviceStatus();
        checkiOSDeviceStatus();
    }, 3000);
    
    // Initial check
    setTimeout(() => {
        checkAndroidDeviceStatus();
        checkiOSDeviceStatus();
    }, 1000);
}

async function checkAndroidDeviceStatus() {
    try {
        const response = await flaskAPI.request('GET', '/api/devices/android/detect');
        
        if (response.connected) {
            deviceStatus.android = true;
            updateAndroidStatus('🟢 Android: Connected', 'connected');
            updateAndroidDeviceInfo(response.device_info || 'Android device connected');
            document.getElementById('start-android-triage').disabled = !validateCaseInfo();
        } else {
            deviceStatus.android = false;
            updateAndroidStatus('🔴 Android: No device', 'disconnected');
            updateAndroidDeviceInfo('No Android device connected. Please connect a device via USB and enable USB debugging.');
            document.getElementById('start-android-triage').disabled = true;
        }
    } catch (error) {
        console.error('Error checking Android device:', error);
        deviceStatus.android = false;
        updateAndroidStatus('🟡 Android: Check failed', 'warning');
    }
}

async function checkiOSDeviceStatus() {
    try {
        const response = await flaskAPI.request('GET', '/api/devices/ios/detect');
        
        if (response.connected) {
            deviceStatus.ios = true;
            updateiOSStatus('🟢 iOS: Connected', 'connected');
            updateiOSDeviceInfo(response.device_info || 'iOS device connected');
            document.getElementById('start-ios-backup').disabled = !validateCaseInfo();
        } else {
            deviceStatus.ios = false;
            updateiOSStatus('🔴 iOS: No device', 'disconnected');
            updateiOSDeviceInfo('No iOS device connected. Please connect an iOS device via USB and trust this computer.');
            document.getElementById('start-ios-backup').disabled = true;
        }
    } catch (error) {
        console.error('Error checking iOS device:', error);
        deviceStatus.ios = false;
        updateiOSStatus('🟡 iOS: Check failed', 'warning');
    }
}

// Android operations
function updateAndroidStatus(text, status) {
    const indicator = document.getElementById('android-status');
    if (indicator) {
        indicator.textContent = text;
        indicator.className = `status-indicator ${status}`;
    }
}

function updateAndroidDeviceInfo(info) {
    const infoElement = document.getElementById('android-device-info');
    if (infoElement) {
        infoElement.textContent = info;
    }
}

async function refreshAndroidConnection() {
    updateAndroidStatus('🔵 Android: Checking...', 'warning');
    await checkAndroidDeviceStatus();
}

async function startAndroidTriage() {
    if (!validateCaseInfo()) {
        showNotification('Please enter case number and output directory', 'error');
        return;
    }
    
    if (!deviceStatus.android) {
        showNotification('No Android device connected', 'error');
        return;
    }
    
    const options = {
        apps: document.getElementById('triage-apps').checked,
        device_details: document.getElementById('triage-device-details').checked,
        sms: document.getElementById('triage-sms').checked,
        contacts: document.getElementById('triage-contacts').checked,
        call_logs: document.getElementById('triage-call-logs').checked,
        files: document.getElementById('triage-files').checked,
        thumbnails: document.getElementById('triage-thumbnails').checked,
        case_number: document.getElementById('case-number').value,
        output_directory: document.getElementById('output-directory').value
    };
    
    try {
        showLoading('Starting Android triage...');
        updateAndroidProgress(0, 'Initializing triage...');
        
        const response = await flaskAPI.request('POST', '/api/operations/android/triage', options);
        
        if (response.success) {
            updateAndroidProgress(10, 'Triage started successfully');
            pollTriageProgress('android');
        } else {
            throw new Error(response.error || 'Failed to start triage');
        }
    } catch (error) {
        console.error('Error starting Android triage:', error);
        showNotification('Failed to start Android triage: ' + error.message, 'error');
        updateAndroidProgress(0, 'Triage failed to start');
    } finally {
        hideLoading();
    }
}

function updateAndroidProgress(percent, message) {
    const progressFill = document.getElementById('android-progress-fill');
    const progressText = document.getElementById('android-progress-text');
    const statusLog = document.getElementById('android-status-log');
    
    if (progressFill) {
        progressFill.style.width = percent + '%';
    }
    
    if (progressText) {
        progressText.textContent = `${percent}% - ${message}`;
    }
    
    if (statusLog) {
        const timestamp = new Date().toLocaleTimeString();
        statusLog.textContent += `\n[${timestamp}] ${message}`;
        statusLog.scrollTop = statusLog.scrollHeight;
    }
}

// iOS operations
function updateiOSStatus(text, status) {
    const indicator = document.getElementById('ios-status');
    if (indicator) {
        indicator.textContent = text;
        indicator.className = `status-indicator ${status}`;
    }
}

function updateiOSDeviceInfo(info) {
    const infoElement = document.getElementById('ios-device-info');
    if (infoElement) {
        infoElement.textContent = info;
    }
}

async function refreshiOSConnection() {
    updateiOSStatus('🔵 iOS: Checking...', 'warning');
    await checkiOSDeviceStatus();
}

async function refreshiOSInfo() {
    try {
        const response = await flaskAPI.request('GET', '/api/devices/ios/info');
        
        const detailedInfo = document.getElementById('ios-detailed-info');
        const appsInfo = document.getElementById('ios-apps-info');
        
        if (response.device_info) {
            detailedInfo.textContent = JSON.stringify(response.device_info, null, 2);
        }
        
        if (response.apps) {
            appsInfo.textContent = response.apps.map(app => `${app.name} (${app.bundle_id})`).join('\n');
        }
    } catch (error) {
        console.error('Error getting iOS info:', error);
        showNotification('Failed to get iOS device info', 'error');
    }
}

async function startiOSBackup() {
    if (!validateCaseInfo()) {
        showNotification('Please enter case number and output directory', 'error');
        return;
    }
    
    if (!deviceStatus.ios) {
        showNotification('No iOS device connected', 'error');
        return;
    }
    
    const options = {
        case_number: document.getElementById('case-number').value,
        output_directory: document.getElementById('output-directory').value
    };
    
    try {
        showLoading('Starting iOS backup...');
        updateiOSProgress(0, 'Initializing backup...');
        
        const response = await flaskAPI.request('POST', '/api/operations/ios/backup', options);
        
        if (response.success) {
            updateiOSProgress(10, 'Backup started successfully');
            pollTriageProgress('ios');
        } else {
            throw new Error(response.error || 'Failed to start backup');
        }
    } catch (error) {
        console.error('Error starting iOS backup:', error);
        showNotification('Failed to start iOS backup: ' + error.message, 'error');
        updateiOSProgress(0, 'Backup failed to start');
    } finally {
        hideLoading();
    }
}

function updateiOSProgress(percent, message) {
    const progressFill = document.getElementById('ios-progress-fill');
    const progressText = document.getElementById('ios-progress-text');
    const statusLog = document.getElementById('ios-status-log');
    
    if (progressFill) {
        progressFill.style.width = percent + '%';
    }
    
    if (progressText) {
        progressText.textContent = `${percent}% - ${message}`;
    }
    
    if (statusLog) {
        const timestamp = new Date().toLocaleTimeString();
        statusLog.textContent += `\n[${timestamp}] ${message}`;
        statusLog.scrollTop = statusLog.scrollHeight;
    }
}

// Parser operations
async function startParsing() {
    const backupFile = document.getElementById('backup-file').value;
    const parserType = document.getElementById('parser-type').value;
    
    if (!backupFile) {
        showNotification('Please select a backup file', 'error');
        return;
    }
    
    try {
        showLoading('Parsing backup file...');
        updateParserProgress(0, 'Starting parser...');
        
        const response = await flaskAPI.request('POST', '/api/operations/parse', {
            backup_file: backupFile,
            parser_type: parserType
        });
        
        if (response.success) {
            updateParserProgress(50, 'Parsing in progress...');
            pollParseProgress();
        } else {
            throw new Error(response.error || 'Failed to start parsing');
        }
    } catch (error) {
        console.error('Error starting parsing:', error);
        showNotification('Failed to start parsing: ' + error.message, 'error');
        updateParserProgress(0, 'Parsing failed to start');
    } finally {
        hideLoading();
    }
}

function updateParserProgress(percent, message) {
    const progressFill = document.getElementById('parser-progress-fill');
    const progressText = document.getElementById('parser-progress-text');
    const statusLog = document.getElementById('parser-status-log');
    
    if (progressFill) {
        progressFill.style.width = percent + '%';
    }
    
    if (progressText) {
        progressText.textContent = `${percent}% - ${message}`;
    }
    
    if (statusLog) {
        const timestamp = new Date().toLocaleTimeString();
        statusLog.textContent += `\n[${timestamp}] ${message}`;
        statusLog.scrollTop = statusLog.scrollHeight;
    }
}

function updateParserStatus(message) {
    const statusLog = document.getElementById('parser-status-log');
    if (statusLog) {
        const timestamp = new Date().toLocaleTimeString();
        statusLog.textContent += `\n[${timestamp}] ${message}`;
        statusLog.scrollTop = statusLog.scrollHeight;
    }
}

// Progress polling
async function pollTriageProgress(platform) {
    const pollInterval = setInterval(async () => {
        try {
            const response = await flaskAPI.request('GET', '/api/operations/status');
            
            if (response.operations && response.operations.length > 0) {
                const operation = response.operations[0]; // Get latest operation
                
                if (platform === 'android') {
                    updateAndroidProgress(operation.progress || 0, operation.status || 'Processing...');
                } else if (platform === 'ios') {
                    updateiOSProgress(operation.progress || 0, operation.status || 'Processing...');
                }
                
                if (operation.completed) {
                    clearInterval(pollInterval);
                    if (operation.success) {
                        showNotification(`${platform.toUpperCase()} operation completed successfully!`, 'success');
                    } else {
                        showNotification(`${platform.toUpperCase()} operation failed: ${operation.error}`, 'error');
                    }
                }
            }
        } catch (error) {
            console.error('Error polling progress:', error);
            clearInterval(pollInterval);
        }
    }, 2000);
}

async function pollParseProgress() {
    const pollInterval = setInterval(async () => {
        try {
            const response = await flaskAPI.request('GET', '/api/operations/status');
            
            if (response.operations && response.operations.length > 0) {
                const operation = response.operations[0];
                
                updateParserProgress(operation.progress || 0, operation.status || 'Parsing...');
                
                if (operation.completed) {
                    clearInterval(pollInterval);
                    if (operation.success && operation.results) {
                        document.getElementById('parser-results-display').textContent = operation.results;
                        document.getElementById('export-results-btn').disabled = false;
                        showNotification('Parsing completed successfully!', 'success');
                        switchTab('parser', 'results');
                    } else {
                        showNotification(`Parsing failed: ${operation.error}`, 'error');
                    }
                }
            }
        } catch (error) {
            console.error('Error polling parse progress:', error);
            clearInterval(pollInterval);
        }
    }, 2000);
}

// Android results display
function showAndroidResults(type) {
    // Update active button
    const resultsTab = document.getElementById('android-results');
    resultsTab.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    event.target.classList.add('active');
    
    // Show appropriate results
    const resultsContent = document.getElementById('android-results-content');
    resultsContent.textContent = `Showing ${type} results...\n\nThis would display the ${type} data from the completed triage operation.`;
}

// Export functionality
async function exportResults() {
    try {
        const results = document.getElementById('parser-results-display').textContent;
        
        const result = await electronAPI.saveFile({
            title: 'Export Parsing Results',
            defaultPath: 'parsing_results.txt',
            filters: [
                { name: 'Text Files', extensions: ['txt'] },
                { name: 'All Files', extensions: ['*'] }
            ]
        });
        
        if (result && !result.canceled) {
            await electronAPI.writeFile(result.filePath, results);
            showNotification('Results exported successfully!', 'success');
        }
    } catch (error) {
        console.error('Error exporting results:', error);
        showNotification('Failed to export results', 'error');
    }
}

// UI utilities
function showLoading(message = 'Processing...') {
    const overlay = document.getElementById('loading-overlay');
    const text = overlay.querySelector('p');
    if (text) text.textContent = message;
    overlay.classList.remove('hidden');
}

function hideLoading() {
    const overlay = document.getElementById('loading-overlay');
    overlay.classList.add('hidden');
}

function showNotification(message, type = 'info') {
    console.log(`${type.toUpperCase()}: ${message}`);
    
    // You could implement a toast notification system here
    // For now, we'll use the browser's alert for important messages
    if (type === 'error') {
        alert('Error: ' + message);
    } else if (type === 'success') {
        console.log('✓ ' + message);
    }
}

// Error handling
window.addEventListener('error', function(event) {
    console.error('Unhandled error:', event.error);
    showNotification('An unexpected error occurred', 'error');
});

// Expose functions globally for onclick handlers
window.switchPlatform = switchPlatform;
window.switchTab = switchTab;
window.selectOutputDirectory = selectOutputDirectory;
window.selectBackupFile = selectBackupFile;
window.refreshAndroidConnection = refreshAndroidConnection;
window.refreshiOSConnection = refreshiOSConnection;
window.refreshiOSInfo = refreshiOSInfo;
window.startAndroidTriage = startAndroidTriage;
window.startiOSBackup = startiOSBackup;
window.startParsing = startParsing;
window.showAndroidResults = showAndroidResults;
window.exportResults = exportResults;
