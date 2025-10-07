// Main JavaScript for Arsenic Mobile Triage Tool

console.log('=== MAIN.JS LOADING ===');
console.log('JavaScript is working!');

// Global state
let currentPlatform = 'android';
let currentTab = {};
let deviceStatus = {
    android: false,
    ios: false
};

// Analysis mode flags
let isAnalysisMode = false;
let parsedDeviceInfo = null;

// Flask API utility
const apiClient = {
    baseURL: 'http://127.0.0.1:3131',
    
    async request(method, endpoint, params = {}) {
        try {
            let url = `${this.baseURL}${endpoint}`;
            let options = {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                }
            };
            
            if (method === 'GET' && Object.keys(params).length > 0) {
                // For GET requests, add parameters as query string
                const queryString = new URLSearchParams(params).toString();
                url += `?${queryString}`;
                console.log('DEBUG: Final GET URL with params:', url);
                console.log('DEBUG: Params object:', params);
                console.log('DEBUG: Query string:', queryString);
            } else if (method !== 'GET') {
                // For other methods, send as JSON body
                options.body = JSON.stringify(params);
            }
            
            console.log(`Making ${method} request to: ${url}`);
            
            const response = await fetch(url, options);
            
            if (!response.ok) {
                const errorText = await response.text();
                console.error(`API Error ${response.status}:`, errorText);
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }
            
            const data = await response.json();
            return data;
            
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    }
};

// Make API client available globally for other modules
window.flaskAPI = apiClient;

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    console.log('Arsenic Mobile Triage Tool initialized');
    
    // Ensure loading overlay is hidden on startup
    hideLoading();
    
    try {
        // Clean up any existing polling intervals
        cleanupPollingIntervals();
        
        // Set up event listeners
        setupEventListeners();
        
        // Start device monitoring
        startDeviceMonitoring();
        
        // Initialize current tab tracking
        currentTab = {
            android: 'triage',
            ios: 'parser'
        };

        // Initialize table controls
        initializeTableControls();
        
        // Initialize screenshot controls
        updateScreenshotControls();
        
        console.log('Application ready');
    } catch (error) {
        console.error('Error during initialization:', error);
        hideLoading();
        showNotification('Application initialization failed: ' + error.message, 'error');
    }
});

// Cleanup function to clear any existing polling intervals
function cleanupPollingIntervals() {
    // Clear analysis progress polling if it exists
    if (typeof analysisProgressInterval !== 'undefined' && analysisProgressInterval) {
        console.log('Clearing existing analysis progress interval');
        clearInterval(analysisProgressInterval);
        analysisProgressInterval = null;
    }
    
    // Reset analysis directory
    if (typeof currentAnalysisDir !== 'undefined') {
        currentAnalysisDir = null;
    }
}

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
    try {
        console.log(`Switching to platform: ${platform}`);
        
        // Update active platform button
        document.querySelectorAll('.platform-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        
        const platformBtn = document.querySelector(`[data-platform="${platform}"]`);
        if (platformBtn) {
            platformBtn.classList.add('active');
        }
        
        // Show/hide platform content
        document.querySelectorAll('.platform-content').forEach(content => {
            content.classList.remove('active');
        });
        
        const platformContent = document.getElementById(`${platform}-content`);
        if (platformContent) {
            // CRITICAL FIX: Ensure iOS content is properly nested in content-area
            if (platform === 'ios') {
                const contentArea = document.querySelector('.content-area');
                if (contentArea && platformContent.parentElement !== contentArea) {
                    contentArea.appendChild(platformContent);
                }
            }
            
            platformContent.classList.add('active');
        } else {
            console.error(`Could not find platform content: ${platform}-content`);
        }
        
        currentPlatform = platform;
        
        // Trigger immediate device check for the selected platform
        if (platform === 'android') {
            checkAndroidDeviceStatus();
        } else if (platform === 'ios') {
            checkiOSDeviceStatus();
        }
    } catch (error) {
        console.error('Error switching platform:', error);
        showNotification('Error switching platform: ' + error.message, 'error');
    }
}

// Tab switching within platforms
// Tab switching functionality
function switchTab(platform, tabName) {
    try {
        // Hide all tab panes for this platform
        const tabPanes = document.querySelectorAll(`#${platform}-content .tab-pane`);
        tabPanes.forEach(pane => {
            pane.classList.remove('active');
        });

        // Remove active class from all tab buttons for this platform
        const tabButtons = document.querySelectorAll(`#${platform}-content .tab-btn`);
        tabButtons.forEach(btn => {
            btn.classList.remove('active');
        });

        // Show the selected tab pane
        const selectedPane = document.getElementById(`${platform}-${tabName}`);
        if (selectedPane) {
            selectedPane.classList.add('active');
        }

        // Add active class to the clicked button
        const selectedButton = document.querySelector(`[data-tab="${platform}-${tabName}"]`);
        if (selectedButton) {
            selectedButton.classList.add('active');
        }

        // Update current tab tracking
        currentTab[platform] = tabName;

        // Load device info when switching to iOS backup tab
        if (platform === 'ios' && tabName === 'backup') {
            console.log('Switching to iOS backup tab, loading device info...');
            
            // Clear analysis mode when switching to backup tab
            clearAnalysisMode();
            
            setTimeout(async () => {
                await checkiOSDeviceStatus();
                // If device is connected, load the detailed info
                if (deviceStatus.ios) {
                    console.log('Device connected, loading detailed info...');
                    await refreshiOSInfo();
                }
            }, 500);
        }
    } catch (error) {
        console.error('Error switching tabs:', error);
    }
}

// Directory selection
async function selectOutputDirectory() {
    try {
        const result = await electronAPI.openDirectory();
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
        const result = await electronAPI.openFile({
            title: 'Select Backup File',
            filters: [
                { name: 'All Files', extensions: ['*'] },
                { name: 'Backup Files', extensions: ['backup', 'ab', 'tar', 'zip'] }
            ]
        });
        
        if (result && !result.canceled && result.filePaths.length > 0) {
            const selectedPath = result.filePaths[0];
            
            // Determine which backup file input to update based on currently active tab
            const iosParserTab = document.getElementById('ios-parser');
            const androidParserTab = document.getElementById('android-parser');
            
            if (iosParserTab && iosParserTab.classList.contains('active')) {
                // Update iOS parser tab
                document.getElementById('ios-backup-file').value = selectedPath;
                const button = document.getElementById('ios-start-parsing');
                if (button) button.disabled = false;
                updateParserStatus('Backup file selected: ' + selectedPath.split('/').pop(), 'ios');
            } else if (androidParserTab && androidParserTab.classList.contains('active')) {
                // Update Android parser tab
                document.getElementById('backup-file').value = selectedPath;
                const button = document.getElementById('start-parsing');
                if (button) button.disabled = false;
                updateParserStatus('Backup file selected: ' + selectedPath.split('/').pop(), 'android');
            } else {
                // Fallback - try to find any backup file input
                const backupFileInput = document.getElementById('backup-file') || document.getElementById('ios-backup-file');
                if (backupFileInput) {
                    backupFileInput.value = selectedPath;
                }
            }
        }
    } catch (error) {
        console.error('Error selecting backup file:', error);
        showNotification('Failed to select backup file', 'error');
    }
}

// Select iOS backup folder for parsing
async function selectIOSBackupFolder() {
    try {
        const result = await electronAPI.openDirectory({
            title: 'Select iOS Backup Folder'
        });
        
        if (result && !result.canceled && result.filePaths.length > 0) {
            const selectedPath = result.filePaths[0];
            document.getElementById('ios-backup-folder').value = selectedPath;
            
            // Check encryption status
            updateIOSParserStatus('Checking backup encryption status...');
            await checkIOSBackupEncryption(selectedPath);
        }
    } catch (error) {
        console.error('Error selecting iOS backup folder:', error);
        showNotification('Failed to select backup folder', 'error');
        updateIOSParserStatus('Error selecting backup folder');
    }
}

// Check iOS backup encryption status
async function checkIOSBackupEncryption(backupPath) {
    try {
        // Clear any previous analysis mode and device info
        clearAnalysisMode();
        
        console.log('DEBUG: Checking encryption for backup path:', backupPath);
        
        const response = await fetch('http://localhost:3131/api/ios/backup/check-encryption', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                backup_path: backupPath
            })
        });
        
        console.log('DEBUG: API response status:', response.status);
        const data = await response.json();
        console.log('DEBUG: API response data:', data);
        
        if (data.success) {
            const encryptionStatus = data.encryption_status;
            const deviceInfo = data.device_info;
            
            console.log('DEBUG: Encryption status:', encryptionStatus);
            console.log('DEBUG: Device info:', deviceInfo);
            
            // Update device info display when backup folder is selected
            if (deviceInfo && Object.keys(deviceInfo).length > 0) {
                console.log('Found device info in backup folder:', deviceInfo);
                
                // Set analysis mode and display device info in separate backup panel
                isAnalysisMode = true;
                parsedDeviceInfo = deviceInfo;
                updateBackupDeviceInfo(deviceInfo);
            }
            
            // Update status with device info
            let statusText = `Valid backup folder selected`;
            if (deviceInfo['Device Name']) {
                statusText += ` (${deviceInfo['Device Name']}`;
                if (deviceInfo['Product Version']) {
                    statusText += `, iOS ${deviceInfo['Product Version']}`;
                }
                statusText += `)`;
            }
            
            // Show/hide password field based on encryption
            const passwordGroup = document.getElementById('ios-password-group');
            const parseButton = document.getElementById('start-ios-parsing');
            
            console.log('DEBUG: Password group element:', passwordGroup);
            console.log('DEBUG: Is encrypted?', encryptionStatus.is_encrypted);
            
            if (encryptionStatus.is_encrypted) {
                console.log('DEBUG: Showing password field');
                passwordGroup.style.display = 'block';
                statusText += ` - 🔒 Backup is encrypted and requires a password`;
                parseButton.disabled = false; // Enable button, password will be validated during parsing
            } else {
                console.log('DEBUG: Hiding password field');
                passwordGroup.style.display = 'none';
                statusText += ` - 🔓 Backup is not encrypted`;
                parseButton.disabled = false;
            }
            
            updateIOSParserStatus(statusText);
            
        } else {
            // Clear device info on error
            clearAnalysisMode();
            const compactPanel = document.getElementById('ios-device-info-compact');
            if (compactPanel) {
                compactPanel.style.display = 'none';
            }
            
            updateIOSParserStatus(`Error: ${data.error}`);
            document.getElementById('ios-password-group').style.display = 'none';
            document.getElementById('start-ios-parsing').disabled = true;
        }
        
    } catch (error) {
        console.error('Error checking backup encryption:', error);
        
        // Clear device info on error
        clearAnalysisMode();
        const compactPanel = document.getElementById('ios-device-info-compact');
        if (compactPanel) {
            compactPanel.style.display = 'none';
        }
        
        updateIOSParserStatus('Error checking backup encryption status');
        document.getElementById('ios-password-group').style.display = 'none';
        document.getElementById('start-ios-parsing').disabled = true;
    }
}

// Toggle iOS taxonomy parsing options
function toggleIOSTaxonomyOptions() {
    const enableTaxonomy = document.getElementById('ios-enable-taxonomy').checked;
    const taxonomyOptions = document.getElementById('ios-taxonomy-options');
    
    if (enableTaxonomy) {
        taxonomyOptions.style.display = 'block';
    } else {
        taxonomyOptions.style.display = 'none';
        // Clear selection when disabled
        document.getElementById('ios-taxonomy-type').value = '';
    }
}

// Start iOS backup parsing from main tab
async function startIOSBackupParsing() {
    if (!validateCaseInfo()) {
        showNotification('Please enter case number and output directory', 'error');
        return;
    }
    
    const backupFolder = document.getElementById('ios-backup-folder').value.trim();
    const password = document.getElementById('ios-backup-password').value.trim();
    
    if (!backupFolder) {
        showNotification('Please select a backup folder', 'error');
        return;
    }
    
    try {
        showLoading('Parsing iOS backup...');
        updateIOSParserProgress(0, 'Initializing iOS backup parser...');
        
        // Get taxonomy parsing options
        const enableTaxonomy = document.getElementById('ios-enable-taxonomy').checked;
        const taxonomyType = document.getElementById('ios-taxonomy-type').value;
        
        const options = {
            backup_path: backupFolder,
            password: password,
            case_number: document.getElementById('case-number').value,
            output_directory: document.getElementById('output-directory').value,
            enable_taxonomy: enableTaxonomy,
            taxonomy_type: taxonomyType || null
        };
        
        const response = await apiClient.request('POST', '/api/ios/backup/parse', options);
        
        if (response.success) {
            showIOSParseResults({ status: 'Parsing started successfully' });
            monitorIOSParserOperation(response.operation_id);
            showNotification('iOS backup parsing started', 'success');
        } else {
            throw new Error(response.error || 'Failed to start parsing');
        }
    } catch (error) {
        console.error('Error starting iOS backup parsing:', error);
        showNotification('Failed to start iOS backup parsing: ' + error.message, 'error');
        hideLoading();
    }
}

// Update iOS parser status
function updateIOSParserStatus(message) {
    const statusElement = document.getElementById('ios-parser-status-log');
    if (statusElement) {
        const timestamp = new Date().toLocaleTimeString();
        statusElement.textContent = `[${timestamp}] ${message}`;
    }
}

// Update iOS parser progress
function updateIOSParserProgress(percentage, message) {
    const progressFill = document.getElementById('ios-parser-progress-fill');
    const progressText = document.getElementById('ios-parser-progress-text');
    
    if (progressFill) {
        progressFill.style.width = `${percentage}%`;
    }
    
    if (progressText) {
        progressText.textContent = message || `${percentage}%`;
    }
    
    updateIOSParserStatus(message || `Progress: ${percentage}%`);
}

// Monitor iOS parser operation
function monitorIOSParserOperation(operationId) {
    const interval = setInterval(async () => {
        try {
            const response = await apiClient.request('GET', '/api/operations/status');
            
            if (response.operations && response.operations.length > 0) {
                // Find the specific operation by ID
                const operation = response.operations.find(op => op.operation_id === operationId);
                
                if (operation) {
                    if (operation.completed) {
                        clearInterval(interval);
                        if (operation.success) {
                            updateIOSParserProgress(100, 'Parsing completed successfully');
                            console.log('Operation results structure:', operation.results);
                            // Extract structured data correctly - it's nested in operation.results.structured_data
                            const structuredData = operation.results?.structured_data || operation.results || operation.structured_data;
                            console.log('Extracted structured data:', structuredData);
                            showIOSParseResults(structuredData);
                            showNotification('iOS backup parsing completed', 'success');
                        } else {
                            const errorMsg = operation.error || 'Unknown error occurred';
                            updateIOSParserProgress(0, `Error: ${errorMsg}`);
                            showNotification('iOS backup parsing failed: ' + errorMsg, 'error');
                        }
                        hideLoading();
                    } else if (operation.updates && operation.updates.length > 0) {
                        const latestUpdate = operation.updates[operation.updates.length - 1];
                        if (latestUpdate.progress !== undefined) {
                            updateIOSParserProgress(latestUpdate.progress, latestUpdate.message || 'Parsing in progress...');
                        }
                    }
                }
            }
        } catch (error) {
            console.error('Error monitoring iOS parser operation:', error);
            clearInterval(interval);
            hideLoading();
        }
    }, 1000);
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
    
    // Also update screenshot controls when case info changes
    updateScreenshotControls();
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
        const response = await apiClient.request('GET', '/api/devices/android/detect');
        
        const statusElement = document.getElementById('android-device-status');
        const deviceInfoPanel = document.getElementById('android-device-info');
        const setupInstructions = document.getElementById('android-setup-instructions');
        const triageButton = document.getElementById('start-android-triage');
        const backupButton = document.getElementById('start-android-backup');
        
        if (response.connected) {
            deviceStatus.android = true;
            updateAndroidStatus('🟢 Android: Connected', 'connected');
            
            // Update new UI elements
            if (statusElement) {
                statusElement.textContent = 'Device Connected';
                statusElement.className = 'status-indicator online';
            }
            
            // Show device info and hide setup instructions
            if (deviceInfoPanel && response.device_info) {
                deviceInfoPanel.classList.remove('hidden');
                
                // Update device details with enhanced information
                const deviceInfo = response.device_info;
                updateElementText('device-model', deviceInfo.model || 'Unknown');
                updateElementText('device-manufacturer', deviceInfo.manufacturer || 'Unknown');
                updateElementText('device-android-version', deviceInfo.android_version || 'Unknown');
                updateElementText('device-serial', deviceInfo.serial || 'Unknown');
                updateElementText('device-sdk-version', deviceInfo.sdk_version || 'Unknown');
                updateElementText('device-build-id', deviceInfo.build_id || 'Unknown');
                updateElementText('device-security-patch', deviceInfo.security_patch || 'Unknown');
                updateElementText('device-encryption-status', deviceInfo.encryption_status || 'Unknown');
                updateElementText('device-hardware', deviceInfo.hardware || 'Unknown');
                updateElementText('device-imei', deviceInfo.imei || 'Unknown');
                updateElementText('device-brand', deviceInfo.brand || 'Unknown');
                updateElementText('device-chipset', deviceInfo.chipset || 'Unknown');
            }
            
            if (setupInstructions) {
                setupInstructions.classList.add('hidden');
            }
            
            // Enable triage and backup buttons
            if (triageButton) triageButton.disabled = !validateCaseInfo();
            if (backupButton) backupButton.disabled = !validateCaseInfo();
            
        } else {
            deviceStatus.android = false;
            updateAndroidStatus('🔴 Android: No device', 'disconnected');
            
            // Update new UI elements
            if (statusElement) {
                statusElement.textContent = 'No Device Connected';
                statusElement.className = 'status-indicator offline';
            }
            
            // Hide device info and show setup instructions
            if (deviceInfoPanel) {
                deviceInfoPanel.classList.add('hidden');
            }
            
            if (setupInstructions) {
                setupInstructions.classList.remove('hidden');
            }
            
            // Disable triage and backup buttons
            if (triageButton) triageButton.disabled = true;
            if (backupButton) backupButton.disabled = true;
        }
        
    } catch (error) {
        console.error('Android device check failed:', error);
        deviceStatus.android = false;
        updateAndroidStatus('🔴 Android: Connection error', 'error');
        
        // Update UI elements to show error state
        const statusElement = document.getElementById('android-device-status');
        if (statusElement) {
            statusElement.textContent = 'Connection Error';
            statusElement.className = 'status-indicator offline';
        }
        
        // Don't throw the error - just log it and continue
    }
}

async function checkiOSDeviceStatus() {
    try {
        const response = await apiClient.request('GET', '/api/devices/ios/detect');
        
        if (response.connected) {
            deviceStatus.ios = true;
            updateiOSStatus('🟢 iOS: Connected', 'connected');
            
            // Only update device info if it hasn't been loaded with detailed information yet
            const deviceInfo = document.getElementById('ios-device-info');
            const currentInfo = deviceInfo ? deviceInfo.textContent : '';
            
            // Check if detailed info is already loaded (contains newlines indicating formatted info)
            if (!currentInfo || currentInfo.includes('Connect an iOS device') || !currentInfo.includes('\n')) {
                updateiOSDeviceInfo(response.device_info || 'iOS device connected');
            }
            
            // Don't overwrite apps list if it's already loaded with data
            const appsList = document.getElementById('ios-apps-list');
            const currentApps = appsList ? appsList.textContent : '';
            
            // Only update status if apps aren't loaded yet
            if (!window.currentIOSApps || window.currentIOSApps.length === 0) {
                const statusElement = document.getElementById('ios-device-status');
                if (statusElement && (!statusElement.textContent || statusElement.textContent.includes('No device'))) {
                    statusElement.textContent = 'Device connected - Click refresh to load device info and apps';
                }
            }
            
            const button = document.getElementById('start-ios-backup');
            if (button) button.disabled = !validateCaseInfo();
            
            // Don't automatically load device info here to prevent conflicts
            // Only load once when manually requested or when switching tabs
            
        } else {
            deviceStatus.ios = false;
            updateiOSStatus('🔴 iOS: No device', 'disconnected');
            updateiOSDeviceInfo('No iOS device connected. Please connect an iOS device via USB and trust this computer.');
            const button = document.getElementById('start-ios-backup');
            if (button) button.disabled = true;
            
            // Hide compact device info panel when no device is connected
            const statusElement = document.getElementById('ios-device-status');
            const compactDeviceInfo = document.getElementById('ios-device-info-compact');
            const appsList = document.getElementById('ios-apps-list');
            const appsCount = document.getElementById('ios-apps-count');
            
            if (statusElement) {
                statusElement.textContent = 'No device connected';
            }
            if (compactDeviceInfo) {
                compactDeviceInfo.style.display = 'none';
            }
            if (appsList) {
                appsList.textContent = 'No apps loaded. Connect device and click refresh to view installed applications.';
            }
            if (appsCount) {
                appsCount.textContent = '0 apps';
            }
            window.currentIOSApps = [];
        }
    } catch (error) {
        console.error('Error checking iOS device:', error);
        deviceStatus.ios = false;
        updateiOSStatus('🟡 iOS: Check failed', 'warning');
        // Don't show error alerts for routine device checks
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

// Helper functions for new Android UI elements
function updateElementText(elementId, text) {
    const element = document.getElementById(elementId);
    if (element) {
        element.textContent = text;
    }
}

function updateAndroidStatusLog(message) {
    const progressText = document.getElementById('android-progress-text');
    if (progressText) {
        progressText.textContent = message;
    }
}

function updateBackupStatus(message, progress = null, stage = null) {
    // Update the backup progress container
    const progressContainer = document.getElementById('backup-progress-container');
    const progressFill = document.getElementById('backup-progress-fill');
    const progressText = document.getElementById('backup-progress-text');
    const statusLog = document.getElementById('backup-status-log');
    
    // Show progress container
    if (progressContainer) {
        progressContainer.style.display = 'block';
    }
    
    // Update progress bar if percentage provided
    if (progress !== null && progressFill) {
        progressFill.style.width = `${Math.max(0, Math.min(100, progress))}%`;
    }
    
    // Update progress text
    if (progressText) {
        if (stage) {
            progressText.textContent = `${stage}: ${message}`;
        } else {
            progressText.textContent = message;
        }
    }
    
    // Update status log with timestamp
    if (statusLog) {
        const timestamp = new Date().toLocaleTimeString();
        const currentLog = statusLog.textContent || '';
        const newLogEntry = `[${timestamp}] ${message}`;
        
        // Keep last 10 status messages
        const logLines = currentLog.split('\n').filter(line => line.trim());
        logLines.push(newLogEntry);
        if (logLines.length > 10) {
            logLines.shift();
        }
        
        statusLog.textContent = logLines.join('\n');
        statusLog.scrollTop = statusLog.scrollHeight; // Auto-scroll to bottom
    }
    
    // Add visual feedback for different types of messages
    if (progressText) {
        progressText.className = 'progress-text';
        if (message.includes('completed') || message.includes('success')) {
            progressText.className += ' success';
        } else if (message.includes('failed') || message.includes('error')) {
            progressText.className += ' error';
        } else if (message.includes('installing') || message.includes('preparing')) {
            progressText.className += ' installing';
        }
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
    
    // Android triage - all data types enabled by default
    const options = {
        apps: true,
        device_details: true,
        sms: true,
        contacts: true,
        call_logs: true,
        files: true,
        thumbnails: true,
        case_number: document.getElementById('case-number').value,
        output_directory: document.getElementById('output-directory').value
    };
    
    try {
        showLoading('Starting Android triage...');
        updateAndroidProgress(0, 'Initializing Android triage...');
        
        const response = await apiClient.request('POST', '/api/operations/android/triage', options);
        
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
    
    if (progressFill) {
        progressFill.style.width = percent + '%';
    }
    
    if (progressText) {
        progressText.textContent = `${percent}% - ${message}`;
    }
}

async function startAndroidBackup() {
    console.log('=== startAndroidBackup() called ===');
    
    // Check if elements exist
    const caseNumberEl = document.getElementById('case-number');
    const outputDirEl = document.getElementById('output-directory');
    console.log('Case number element:', caseNumberEl);
    console.log('Output directory element:', outputDirEl);
    console.log('Case number value:', caseNumberEl?.value);
    console.log('Output directory value:', outputDirEl?.value);
    console.log('Device status:', deviceStatus);
    
    // Check button state
    const backupButton = document.getElementById('start-android-backup');
    console.log('Backup button disabled:', backupButton?.disabled);
    
    if (!validateCaseInfo()) {
        console.log('validateCaseInfo() failed');
        showNotification('Please enter case number and output directory', 'error');
        return;
    }
    
    if (!deviceStatus.android) {
        showNotification('No Android device connected', 'error');
        return;
    }
    
    const options = {
        case_number: document.getElementById('case-number').value,
        output_directory: document.getElementById('output-directory').value,
        backup_apps: document.getElementById('backup-apps').checked,
        backup_shared: document.getElementById('backup-shared').checked,
        backup_system: document.getElementById('backup-system').checked,
        backup_all: document.getElementById('backup-all').checked,
        use_forensic_apk: document.getElementById('use-forensic-apk').checked
    };
    
    try {
        showLoading('Starting Android backup...');
        updateBackupStatus('🚀 Initializing Android backup process...', 0, 'Initializing');
        
        // Disable backup button during process
        const backupButton = document.getElementById('start-android-backup');
        if (backupButton) {
            backupButton.disabled = true;
            backupButton.textContent = 'Backup in Progress...';
        }
        
        // Show backup options summary
        const enabledOptions = [];
        if (options.backup_apps) enabledOptions.push('📱 App Data');
        if (options.backup_shared) enabledOptions.push('💾 Shared Storage');
        if (options.backup_system) enabledOptions.push('⚙️ System Data');
        if (options.backup_all) enabledOptions.push('📦 All Packages');
        if (options.use_forensic_apk) enabledOptions.push('🔬 Forensic APK');
        
        updateBackupStatus(`📋 Backup options: ${enabledOptions.join(', ')}`, 5, 'Configuration');
        
        const response = await apiClient.request('POST', '/api/operations/android/backup', options);
        
        if (response.success) {
            updateBackupStatus('✅ Backup request submitted successfully', 10, 'Started');
            updateBackupStatus('🔄 Starting real-time progress monitoring...', 15, 'Monitoring');
            pollBackupProgress('android');
        } else {
            throw new Error(response.error || 'Failed to start backup');
        }
    } catch (error) {
        console.error('Error starting Android backup:', error);
        updateBackupStatus(`❌ Failed to start backup: ${error.message}`, 0, 'Error');
        showNotification('Failed to start Android backup: ' + error.message, 'error');
        
        // Re-enable backup button on error
        const backupButton = document.getElementById('start-android-backup');
        if (backupButton) {
            backupButton.disabled = false;
        }
    } finally {
        hideLoading();
    }
}

// Frontend-based ADB backup function
async function startFrontendADBBackup(options) {
    console.log('Starting frontend ADB backup with options:', options);
    
    try {
        // Show loading
        showLoading();
        
        // Update status
        updateBackupStatus('📦 Starting frontend ADB backup...', 5, 'Initializing');
        
        // Set up progress listener
        const progressHandler = (event, data) => {
            console.log('ADB backup progress:', data);
            
            if (data.type === 'status') {
                updateBackupStatus(data.message, null, 'In Progress');
            } else if (data.type === 'progress') {
                updateBackupStatus(data.message, null, 'In Progress');
            } else if (data.type === 'complete') {
                updateBackupStatus(data.message, 100, 'Complete');
                showNotification('ADB backup completed successfully!', 'success');
                window.electronAPI.removeADBBackupListener(progressHandler);
            } else if (data.type === 'error') {
                updateBackupStatus(data.message, 0, 'Error');
                showNotification('ADB backup failed: ' + data.message, 'error');
                window.electronAPI.removeADBBackupListener(progressHandler);
            }
        };
        
        // Listen for progress updates
        window.electronAPI.onADBBackupProgress(progressHandler);
        
        // Start the backup
        const result = await window.electronAPI.createADBBackup({
            outputDir: options.output_dir,
            caseNumber: options.case_number,
            deviceId: options.device_id,
            includeApks: options.backup_apps || false,
            includeSystem: options.backup_system || false,
            includeShared: options.backup_shared || false
        });
        
        console.log('Frontend ADB backup result:', result);
        
        if (result.success) {
            updateBackupStatus(`✅ ADB backup completed! File: ${result.backupFile}`, 100, 'Complete');
            showNotification(`ADB backup completed successfully! Size: ${result.sizeMB} MB`, 'success');
        } else {
            throw new Error(result.error || 'ADB backup failed');
        }
        
    } catch (error) {
        console.error('Frontend ADB backup error:', error);
        updateBackupStatus(`❌ ADB backup failed: ${error.message}`, 0, 'Error');
        showNotification('ADB backup failed: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

// Function to trigger frontend ADB backup when Flask backup fails
async function handleADBBackupFailure(originalOptions) {
    console.log('Handling ADB backup failure, trying frontend approach...');
    
    // Show a confirmation dialog
    const userWantsToTry = confirm(
        'ADB backup failed through the backend. Would you like to try the frontend ADB backup method?\n\n' +
        'This alternative method runs ADB directly from the frontend and may bypass the issue.'
    );
    
    if (userWantsToTry) {
        await startFrontendADBBackup(originalOptions);
    } else {
        console.log('User declined frontend ADB backup');
    }
}

async function showApkRemovalPrompt(operationId) {
    console.log('Showing APK removal prompt for operation:', operationId);
    
    // Create modal overlay
    const overlay = document.createElement('div');
    overlay.id = 'apk-removal-overlay';
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.7);
        backdrop-filter: blur(4px);
        z-index: 10000;
        display: flex;
        align-items: center;
        justify-content: center;
        animation: fadeIn 0.2s ease-out;
    `;
    
    // Create modal dialog
    const modal = document.createElement('div');
    modal.style.cssText = `
        background: var(--surface-color, #374151);
        border: 1px solid var(--border-color, #6b7280);
        padding: 2rem;
        border-radius: var(--radius-lg, 16px);
        box-shadow: var(--shadow-lg, 0 10px 15px -3px rgb(0 0 0 / 0.5));
        max-width: 520px;
        width: 90%;
        color: var(--text-primary, #f9fafb);
        position: relative;
        animation: slideIn 0.3s ease-out;
    `;
    
    modal.innerHTML = `
        <div style="margin-bottom: 1.5rem;">
            <div style="display: flex; align-items: center; margin-bottom: 1rem;">
                <div style="
                    background: var(--primary-color, #3b82f6);
                    width: 48px;
                    height: 48px;
                    border-radius: var(--radius-md, 10px);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 1.5rem;
                    margin-right: 1rem;
                ">🔬</div>
                <div>
                    <h3 style="
                        margin: 0;
                        color: var(--text-primary, #f9fafb);
                        font-size: 1.25rem;
                        font-weight: 600;
                    ">APK Data Collection Complete</h3>
                    <p style="
                        margin: 0.25rem 0 0 0;
                        color: var(--text-secondary, #d1d5db);
                        font-size: 0.875rem;
                    ">Forensic data extraction successful</p>
                </div>
            </div>
            <p style="
                margin: 0;
                line-height: 1.5;
                color: var(--text-secondary, #d1d5db);
                font-size: 0.875rem;
            ">
                The forensic APK has successfully collected data from the device. 
                Would you like to remove the APK from the device before proceeding with the ADB backup?
            </p>
        </div>
        
        <div style="
            display: flex;
            gap: 0.75rem;
            justify-content: flex-end;
            margin-top: 2rem;
        ">
            <button id="keep-apk-btn" class="btn btn-secondary large" style="
                display: inline-flex;
                align-items: center;
                justify-content: center;
                padding: 0.75rem 1.5rem;
                border: 1px solid var(--border-color, #6b7280);
                border-radius: var(--radius-md, 10px);
                font-size: 0.875rem;
                font-weight: 500;
                background: var(--surface-color, #374151);
                color: var(--text-secondary, #d1d5db);
                cursor: pointer;
                transition: all 0.2s ease;
                gap: 0.5rem;
            ">
                <span style="font-size: 1rem;">📱</span>
                Leave APK on Device
            </button>
            
            <button id="remove-apk-btn" class="btn btn-primary large" style="
                display: inline-flex;
                align-items: center;
                justify-content: center;
                padding: 0.75rem 1.5rem;
                border: 1px solid transparent;
                border-radius: var(--radius-md, 10px);
                font-size: 0.875rem;
                font-weight: 500;
                background: var(--primary-color, #3b82f6);
                color: white;
                cursor: pointer;
                transition: all 0.2s ease;
                gap: 0.5rem;
            ">
                <span style="font-size: 1rem;">🗑️</span>
                Remove Arsenic APK
            </button>
        </div>
        
        <div style="
            margin-top: 1rem;
            padding-top: 1rem;
            border-top: 1px solid var(--border-color, #6b7280);
            font-size: 0.75rem;
            color: var(--text-muted, #9ca3af);
            text-align: center;
        ">
            <p style="margin: 0;">
                <span style="color: var(--accent-blue, #60a5fa);">ℹ️</span>
                The ADB backup process will begin immediately after your selection
            </p>
        </div>
    `;
    
    // Add CSS animations
    const style = document.createElement('style');
    style.textContent = `
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        @keyframes slideIn {
            from { 
                opacity: 0;
                transform: translateY(-20px) scale(0.95);
            }
            to { 
                opacity: 1;
                transform: translateY(0) scale(1);
            }
        }
        
        #apk-removal-overlay button:hover:not(:disabled) {
            transform: translateY(-1px);
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
        }
        
        #remove-apk-btn:hover:not(:disabled) {
            background: var(--primary-hover, #2563eb) !important;
        }
        
        #keep-apk-btn:hover:not(:disabled) {
            background: var(--background-color, #1f2937) !important;
            border-color: var(--secondary-color, #6b7280) !important;
            color: var(--text-primary, #f9fafb) !important;
        }
    `;
    document.head.appendChild(style);
    
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
    
    // Handle button clicks
    document.getElementById('remove-apk-btn').onclick = async () => {
        document.body.removeChild(overlay);
        await handleApkRemovalDecision(operationId, true);
    };
    
    document.getElementById('keep-apk-btn').onclick = async () => {
        document.body.removeChild(overlay);
        await handleApkRemovalDecision(operationId, false);
    };
}

async function handleApkRemovalDecision(operationId, removeApk) {
    console.log(`APK removal decision: ${removeApk ? 'Remove' : 'Keep'} for operation ${operationId}`);
    console.log(`DEBUG: Sending operation_id to backend: ${operationId}`);
    
    try {
        // Update status to show decision processing
        updateBackupStatus(
            removeApk ? '🗑️ Removing APK and continuing with ADB backup...' : '📱 Keeping APK and continuing with ADB backup...', 
            55, 
            'Processing Decision'
        );
        
        // Send decision to backend
        console.log(`DEBUG: About to send POST request with operation_id: ${operationId}`);
        const response = await apiClient.request('POST', '/api/operations/android/apk-removal-decision', {
            operation_id: operationId,
            remove_apk: removeApk
        });
        
        console.log(`DEBUG: Backend response:`, response);
        
        if (response.success) {
            updateBackupStatus('✅ Decision processed, continuing with backup...', 60, 'Continuing');
            
            // Resume progress polling
            pollBackupProgress('android');
        } else {
            throw new Error(response.error || 'Failed to process APK removal decision');
        }
        
    } catch (error) {
        console.error('Error handling APK removal decision:', error);
        updateBackupStatus(`❌ Error processing decision: ${error.message}`, 50, 'Error');
        showNotification('Error processing APK removal decision: ' + error.message, 'error');
        
        // Re-enable backup button on error
        const backupButton = document.getElementById('start-android-backup');
        if (backupButton) {
            backupButton.disabled = false;
            backupButton.textContent = 'Start Android Backup';
        }
    }
}

async function showDataPullPrompt(operationId) {
    console.log('Showing data pull prompt for operation:', operationId);
    
    // Create modal overlay
    const overlay = document.createElement('div');
    overlay.id = 'data-pull-overlay';
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.7);
        backdrop-filter: blur(4px);
        z-index: 10000;
        display: flex;
        align-items: center;
        justify-content: center;
        animation: fadeIn 0.2s ease-out;
    `;
    
    // Create modal dialog
    const modal = document.createElement('div');
    modal.style.cssText = `
        background: var(--surface-color, #374151);
        border: 1px solid var(--border-color, #6b7280);
        padding: 2rem;
        border-radius: var(--radius-lg, 16px);
        box-shadow: var(--shadow-lg, 0 10px 15px -3px rgb(0 0 0 / 0.5));
        max-width: 520px;
        width: 90%;
        color: var(--text-primary, #f9fafb);
        position: relative;
        animation: slideIn 0.3s ease-out;
    `;
    
    modal.innerHTML = `
        <div style="margin-bottom: 1.5rem;">
            <div style="display: flex; align-items: center; margin-bottom: 1rem;">
                <div style="
                    background: var(--success-color, #10b981);
                    width: 48px;
                    height: 48px;
                    border-radius: var(--radius-md, 10px);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 1.5rem;
                    margin-right: 1rem;
                ">📱</div>
                <div>
                    <h3 style="
                        margin: 0;
                        color: var(--text-primary, #f9fafb);
                        font-size: 1.25rem;
                        font-weight: 600;
                    ">Data Collection Ready</h3>
                    <p style="
                        margin: 0.25rem 0 0 0;
                        color: var(--text-secondary, #d1d5db);
                        font-size: 0.875rem;
                    ">APK has collected data on the device</p>
                </div>
            </div>
            <p style="
                margin: 0;
                line-height: 1.5;
                color: var(--text-secondary, #d1d5db);
                font-size: 0.875rem;
            ">
                The forensic APK has successfully completed the investigation and collected data files on the device. 
                Click "Pull Data" to transfer the collected JSON files to your computer for analysis, 
                or "Skip" to leave the data on the device.
            </p>
        </div>
        
        <div style="
            display: flex;
            gap: 0.75rem;
            justify-content: flex-end;
            margin-top: 2rem;
        ">
            <button id="skip-pull-btn" class="btn btn-secondary large" style="
                display: inline-flex;
                align-items: center;
                justify-content: center;
                padding: 0.75rem 1.5rem;
                border: 1px solid var(--border-color, #6b7280);
                border-radius: var(--radius-md, 10px);
                font-size: 0.875rem;
                font-weight: 500;
                background: var(--surface-color, #374151);
                color: var(--text-secondary, #d1d5db);
                cursor: pointer;
                transition: all 0.2s ease;
                gap: 0.5rem;
            ">
                <span style="font-size: 1rem;">⏭️</span>
                Skip Pull
            </button>
            
            <button id="pull-data-btn" class="btn btn-primary large" style="
                display: inline-flex;
                align-items: center;
                justify-content: center;
                padding: 0.75rem 1.5rem;
                border: 1px solid var(--primary-color, #3b82f6);
                border-radius: var(--radius-md, 10px);
                font-size: 0.875rem;
                font-weight: 500;
                background: var(--primary-color, #3b82f6);
                color: white;
                cursor: pointer;
                transition: all 0.2s ease;
                gap: 0.5rem;
            ">
                <span style="font-size: 1rem;">📥</span>
                Pull Data
            </button>
        </div>
    `;
    
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
    
    // Add event listeners
    const skipButton = modal.querySelector('#skip-pull-btn');
    const pullButton = modal.querySelector('#pull-data-btn');
    
    skipButton.addEventListener('click', () => {
        document.body.removeChild(overlay);
        // Continue without pulling data - just show completion
        updateBackupStatus('✅ APK data collection completed (data left on device)', 100, 'Complete');
        showNotification('APK data collection completed - data remains on device', 'info');
        
        // Re-enable backup button
        const backupButton = document.getElementById('start-android-backup');
        if (backupButton) {
            backupButton.disabled = false;
            backupButton.textContent = 'Start Android Backup';
        }
    });
    
    pullButton.addEventListener('click', async () => {
        document.body.removeChild(overlay);
        await startDataPull(operationId);
    });
    
    // Add hover effects
    skipButton.addEventListener('mouseenter', () => {
        skipButton.style.borderColor = 'var(--border-hover, #9ca3af)';
        skipButton.style.background = 'var(--surface-hover, #4b5563)';
    });
    
    skipButton.addEventListener('mouseleave', () => {
        skipButton.style.borderColor = 'var(--border-color, #6b7280)';
        skipButton.style.background = 'var(--surface-color, #374151)';
    });
    
    pullButton.addEventListener('mouseenter', () => {
        pullButton.style.background = 'var(--primary-hover, #2563eb)';
    });
    
    pullButton.addEventListener('mouseleave', () => {
        pullButton.style.background = 'var(--primary-color, #3b82f6)';
    });
}

async function startDataPull(operationId) {
    console.log('Starting data pull for operation:', operationId);
    
    try {
        updateBackupStatus('📥 Starting data pull operation...', 50, 'Pulling Data');
        
        // Start pull operation
        const response = await apiClient.request('POST', '/api/operations/android/pull', {
            operation_id: operationId
        });
        
        if (response.success) {
            updateBackupStatus('🔄 Pulling data from device...', 60, 'Pulling Data');
            
            // Start polling the pull operation progress
            pollPullProgress(response.pull_operation_id);
        } else {
            throw new Error(response.error || 'Failed to start data pull');
        }
        
    } catch (error) {
        console.error('Error starting data pull:', error);
        updateBackupStatus(`❌ Failed to start data pull: ${error.message}`, 50, 'Error');
        showNotification('Failed to start data pull: ' + error.message, 'error');
        
        // Re-enable backup button on error
        const backupButton = document.getElementById('start-android-backup');
        if (backupButton) {
            backupButton.disabled = false;
            backupButton.textContent = 'Start Android Backup';
        }
    }
}

async function pollPullProgress(pullOperationId) {
    console.log('Starting pull progress polling for:', pullOperationId);
    
    const pollInterval = setInterval(async () => {
        try {
            const response = await apiClient.request('GET', '/api/operations/status');
            
            if (response.operations && response.operations.length > 0) {
                // Find our pull operation
                const pullOperation = response.operations.find(op => op.operation_id === pullOperationId);
                
                if (pullOperation && pullOperation.updates) {
                    const lastUpdate = pullOperation.updates[pullOperation.updates.length - 1];
                    
                    // Update status with pull progress
                    if (lastUpdate.message) {
                        updateBackupStatus(lastUpdate.message, lastUpdate.progress || 60, 'Pulling Data');
                    }
                    
                    // Check for APK removal prompt from pull operation
                    const apkRemovalPrompt = pullOperation.updates.find(update => update.type === 'apk_removal_prompt');
                    if (apkRemovalPrompt) {
                        console.log('*** APK REMOVAL PROMPT FROM PULL OPERATION ***');
                        clearInterval(pollInterval);
                        // Use the original operation ID from the prompt, not the pull operation ID
                        const originalOperationId = apkRemovalPrompt.original_operation_id || pullOperationId;
                        showApkRemovalPrompt(originalOperationId);
                        return;
                    }
                    
                    // Check for completion
                    if (lastUpdate.type === 'complete' || pullOperation.completed) {
                        clearInterval(pollInterval);
                        
                        if (lastUpdate.type === 'complete' || pullOperation.success) {
                            updateBackupStatus('✅ Data pull completed successfully!', 100, 'Complete');
                            showNotification('Data pull completed successfully!', 'success');
                        } else {
                            updateBackupStatus('❌ Data pull failed', 60, 'Error');
                            showNotification('Data pull failed - see console for details', 'error');
                        }
                        
                        // Re-enable backup button
                        setTimeout(() => {
                            const backupButton = document.getElementById('start-android-backup');
                            if (backupButton) {
                                backupButton.disabled = false;
                                backupButton.textContent = 'Start Android Backup';
                            }
                        }, 3000);
                    }
                }
            }
            
        } catch (error) {
            console.error('Error polling pull progress:', error);
            clearInterval(pollInterval);
            updateBackupStatus('❌ Error monitoring pull progress', 60, 'Error');
        }
    }, 1500);
    
    // Set timeout for pull operation
    setTimeout(() => {
        clearInterval(pollInterval);
        updateBackupStatus('⚠️ Pull operation timed out', 60, 'Timeout');
    }, 5 * 60 * 1000); // 5 minutes timeout
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
    // Don't overwrite parsed device info when in analysis mode
    if (isAnalysisMode && parsedDeviceInfo) {
        console.log('Analysis mode active, preserving parsed device info');
        return;
    }
    
    // This function is now deprecated - use updateCompactDeviceInfo instead
    console.log('updateiOSDeviceInfo called with:', info);
    
    // If info is a string, show it in the compact panel
    if (typeof info === 'string') {
        updateCompactDeviceInfo({ Status: info });
    } else if (typeof info === 'object') {
        updateCompactDeviceInfo(info);
    }
}

function updateCompactDeviceInfo(deviceInfo) {
    console.log('Updating compact device info with:', deviceInfo);
    
    const compactPanel = document.getElementById('ios-device-info-compact');
    if (!compactPanel) {
        console.warn('Compact device info panel not found');
        return;
    }
    
    // Show the panel
    compactPanel.style.display = 'block';
    
    // Update individual fields
    if (deviceInfo) {
        if (typeof deviceInfo === 'string') {
            // For string messages, just show in model field
            const modelElement = document.getElementById('ios-device-model');
            if (modelElement) modelElement.textContent = deviceInfo;
        } else {
            // Update specific fields
            const modelElement = document.getElementById('ios-device-model');
            const osElement = document.getElementById('ios-device-os');
            const serialElement = document.getElementById('ios-device-serial');
            const udidElement = document.getElementById('ios-device-udid');
            
            if (modelElement) modelElement.textContent = deviceInfo['Device Name'] || deviceInfo['Model'] || deviceInfo['ProductType'] || '-';
            if (osElement) osElement.textContent = deviceInfo['ProductVersion'] || deviceInfo['OS Version'] || '-';
            if (serialElement) serialElement.textContent = deviceInfo['SerialNumber'] || deviceInfo['Serial Number'] || '-';
            if (udidElement) udidElement.textContent = deviceInfo['UniqueDeviceID'] || deviceInfo['UDID'] || '-';
        }
    }
}

function getReadableDeviceModel(productType) {
    // Convert technical product type to readable model name
    const deviceModels = {
        // iPhone 15 series
        'iPhone15,4': 'iPhone 15',
        'iPhone15,5': 'iPhone 15 Plus', 
        'iPhone15,3': 'iPhone 15 Pro',
        'iPhone15,2': 'iPhone 15 Pro Max',
        
        // iPhone 14 series
        'iPhone14,7': 'iPhone 14',
        'iPhone14,8': 'iPhone 14 Plus',
        'iPhone14,2': 'iPhone 14 Pro',
        'iPhone14,3': 'iPhone 14 Pro Max',
        
        // iPhone 13 series
        'iPhone14,5': 'iPhone 13',
        'iPhone14,4': 'iPhone 13 mini',
        'iPhone14,2': 'iPhone 13 Pro',
        'iPhone14,3': 'iPhone 13 Pro Max',
        
        // iPhone 12 series
        'iPhone13,2': 'iPhone 12',
        'iPhone13,1': 'iPhone 12 mini',
        'iPhone13,3': 'iPhone 12 Pro',
        'iPhone13,4': 'iPhone 12 Pro Max',
        
        // iPhone 11 series
        'iPhone12,1': 'iPhone 11',
        'iPhone12,3': 'iPhone 11 Pro',
        'iPhone12,5': 'iPhone 11 Pro Max',
        
        // iPhone XS/XR series
        'iPhone11,2': 'iPhone XS',
        'iPhone11,4': 'iPhone XS Max',
        'iPhone11,6': 'iPhone XS Max',
        'iPhone11,8': 'iPhone XR',
        
        // iPhone X
        'iPhone10,3': 'iPhone X',
        'iPhone10,6': 'iPhone X',
        
        // iPhone 8 series
        'iPhone10,1': 'iPhone 8',
        'iPhone10,4': 'iPhone 8',
        'iPhone10,2': 'iPhone 8 Plus',
        'iPhone10,5': 'iPhone 8 Plus',
        
        // iPhone 7 series
        'iPhone9,1': 'iPhone 7',
        'iPhone9,3': 'iPhone 7',
        'iPhone9,2': 'iPhone 7 Plus',
        'iPhone9,4': 'iPhone 7 Plus',
        
        // iPad series (basic mapping)
        'iPad13,1': 'iPad Air (5th gen)',
        'iPad13,2': 'iPad Air (5th gen)',
        'iPad14,1': 'iPad mini (6th gen)',
        'iPad14,2': 'iPad mini (6th gen)',
    };
    
    return deviceModels[productType] || productType || 'Unknown Device';
}

function updateBackupDeviceInfo(deviceInfo) {
    console.log('Updating backup device info with:', deviceInfo);
    console.log('Available keys in deviceInfo:', Object.keys(deviceInfo));
    
    const backupPanel = document.getElementById('ios-backup-device-info');
    if (!backupPanel) {
        console.warn('Backup device info panel not found');
        return;
    }
    
    // Show the panel
    backupPanel.style.display = 'block';
    
    // Update individual fields
    if (deviceInfo) {
        if (typeof deviceInfo === 'string') {
            // For string messages, just show in model field
            const modelElement = document.getElementById('backup-device-model');
            if (modelElement) modelElement.textContent = deviceInfo;
        } else {
            // Update specific fields with correct plist key names
            const deviceNameElement = document.getElementById('backup-device-name');
            const modelElement = document.getElementById('backup-device-model');
            const osElement = document.getElementById('backup-device-os');
            const serialElement = document.getElementById('backup-device-serial');
            const imeiElement = document.getElementById('backup-device-imei');
            const iccidElement = document.getElementById('backup-device-iccid');
            const udidElement = document.getElementById('backup-device-udid');
            const phoneElement = document.getElementById('backup-device-phone');
            
            // Get readable model name from Product Type
            let modelName = deviceInfo['Model'] || deviceInfo['ProductType'] || '-';
            if (deviceInfo['Product Type']) {
                modelName = getReadableDeviceModel(deviceInfo['Product Type']);
            }
            
            // Update all fields
            const deviceName = deviceInfo['Device Name'] || deviceInfo['Display Name'] || '-';
            const osVersion = deviceInfo['Product Version'] || deviceInfo['ProductVersion'] || deviceInfo['OS Version'] || '-';
            const serialNumber = deviceInfo['Serial Number'] || deviceInfo['SerialNumber'] || '-';
            const imei = deviceInfo['IMEI'] || '-';
            const iccid = deviceInfo['ICCID'] || '-';
            const udid = deviceInfo['Unique Identifier'] || deviceInfo['Target Identifier'] || deviceInfo['UniqueDeviceID'] || deviceInfo['UDID'] || '-';
            const phoneNumber = deviceInfo['Phone Number'] || '-';
            
            console.log('Field values:');
            console.log('Device Name:', deviceName);
            console.log('Model:', modelName);
            console.log('OS Version:', osVersion);
            console.log('Serial Number:', serialNumber);
            console.log('IMEI:', imei);
            console.log('ICCID:', iccid);
            console.log('UDID:', udid);
            console.log('Phone Number:', phoneNumber);
            
            if (deviceNameElement) deviceNameElement.textContent = deviceName;
            if (modelElement) modelElement.textContent = modelName;
            if (osElement) osElement.textContent = osVersion;
            if (serialElement) serialElement.textContent = serialNumber;
            if (imeiElement) imeiElement.textContent = imei;
            if (iccidElement) iccidElement.textContent = iccid;
            if (udidElement) udidElement.textContent = udid;
            if (phoneElement) phoneElement.textContent = phoneNumber;
        }
    }
}

function hideBackupDeviceInfo() {
    const backupPanel = document.getElementById('ios-backup-device-info');
    if (backupPanel) {
        backupPanel.style.display = 'none';
    }
}

function clearAnalysisMode() {
    console.log('Clearing analysis mode');
    isAnalysisMode = false;
    parsedDeviceInfo = null;
    hideBackupDeviceInfo();
}

async function refreshiOSConnection() {
    console.log('Manual iOS connection refresh requested');
    updateiOSStatus('🔵 iOS: Checking...', 'warning');
    
    try {
        // First check if device is connected
        await checkiOSDeviceStatus();
        
        // If device is connected, load the detailed info
        if (deviceStatus.ios) {
            console.log('Device connected, loading detailed device info...');
            await refreshiOSInfo();
        }
        
        console.log('iOS connection refresh completed');
    } catch (error) {
        console.error('Error during iOS connection refresh:', error);
        updateiOSStatus('🔴 iOS: Connection error', 'disconnected');
        showNotification(`iOS connection check failed: ${error.message}`, 'error');
    }
}

async function refreshiOSInfo() {
    try {
        console.log('Attempting to get iOS device info...');
        
        // Update status to show we're loading (but don't clear existing info yet)
        const statusElement = document.getElementById('ios-device-status');
        if (statusElement) {
            statusElement.textContent = 'Loading device information...';
        }

        const response = await apiClient.request('GET', '/api/devices/ios/info');
        console.log('iOS info response:', response);
        
        if (response.error) {
            throw new Error(response.error);
        }
        
        if (response && Object.keys(response).length > 0) {
            // Update device status only after successful load
            if (statusElement) {
                statusElement.textContent = 'Device connected';
            }
            
            // Format device info using the actual keys from backend
            let formattedInfo = '';
            formattedInfo += `Device: ${response.ProductType || 'Unknown'}\n`;
            formattedInfo += `Name: ${response.DeviceName || 'Unknown'}\n`;
            formattedInfo += `iOS Version: ${response.ProductVersion || 'Unknown'}\n`;
            formattedInfo += `Build: ${response.BuildVersion || 'Unknown'}\n`;
            formattedInfo += `Serial Number: ${response.SerialNumber || 'Unknown'}\n`;
            formattedInfo += `UDID: ${response.UniqueDeviceID || 'Unknown'}`;
            
            const deviceInfo = document.getElementById('ios-device-info');
            if (deviceInfo) {
                deviceInfo.textContent = formattedInfo;
            }
            
            console.log('iOS device info updated successfully');
            showNotification('iOS device information retrieved successfully', 'success');
        } else {
            throw new Error('No device information received');
        }
        
        // Try to get apps info
        try {
            const appsResponse = await apiClient.request('GET', '/api/ios/apps');
            console.log('iOS apps response:', appsResponse);
            
            const appsList = document.getElementById('ios-apps-list');
            const appsCount = document.getElementById('ios-apps-count');
            
            if (appsResponse.success && appsResponse.apps && appsList) {
                // Filter to show only third-party (non-system) apps, then store for filtering
                const thirdPartyApps = appsResponse.apps
                    .filter(app => !app.is_system) // Only include non-system apps
                    .map(app => app.name || app.bundle_id)
                    .filter(name => name) // Remove any empty names
                    .sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));
                
                window.currentIOSApps = thirdPartyApps;
                
                // Display filtered third-party apps only
                updateIOSAppsList(window.currentIOSApps);
                
                // Update apps count to show third-party apps count
                if (appsCount) {
                    appsCount.textContent = `${window.currentIOSApps.length} third-party applications`;
                }
            }
        } catch (appsError) {
            console.warn('Could not retrieve iOS apps:', appsError);
            const appsList = document.getElementById('ios-apps-list');
            const appsCount = document.getElementById('ios-apps-count');
            
            if (appsList) {
                appsList.textContent = 'Apps list not available (this is normal for some iOS versions)';
            }
            
            if (appsCount) {
                appsCount.textContent = 'Apps data not available';
            }
            window.currentIOSApps = [];
        }
        
    } catch (error) {
        console.error('Error getting iOS info:', error);
        
        const statusElement = document.getElementById('ios-device-status');
        const deviceInfo = document.getElementById('ios-device-info');
        
        if (statusElement) {
            statusElement.textContent = 'Error getting device info';
        }
        if (deviceInfo) {
            deviceInfo.textContent = `Error: ${error.message}`;
        }
        
        showNotification(`Failed to get iOS device info: ${error.message}`, 'error');
    }
}

// Function to update the iOS apps list display (one app per line)
function updateIOSAppsList(apps) {
    const appsList = document.getElementById('ios-apps-list');
    if (!appsList) return;
    
    if (apps && apps.length > 0) {
        // Each app on its own line with bullet points and proper line breaks
        const appsText = apps.map(app => `• ${app}`).join('\n');
        appsList.textContent = appsText;
    } else {
        appsList.textContent = 'No applications found.';
    }
    
    // Debug: Ensure scrollability works by checking content height vs container height
    console.log('Apps list content height:', appsList.scrollHeight, 'Container height:', appsList.clientHeight);
    if (appsList.scrollHeight > appsList.clientHeight) {
        console.log('Content should be scrollable');
    } else {
        console.log('Content fits in container - no scroll needed');
    }
}

// Function to update the iOS apps count display
function updateIOSAppsCount(count) {
    const appsCount = document.getElementById('ios-apps-count');
    if (appsCount) {
        appsCount.textContent = `${count} app${count !== 1 ? 's' : ''}`;
    }
}

// Function to filter iOS apps based on search text
function filterIOSApps() {
    const searchInput = document.getElementById('ios-apps-search');
    const appsCount = document.getElementById('ios-apps-count');
    
    if (!searchInput || !window.currentIOSApps) return;
    
    const searchText = searchInput.value.toLowerCase().trim();
    
    if (searchText) {
        const filteredApps = window.currentIOSApps.filter(app => 
            app.toLowerCase().includes(searchText)
        );
        updateIOSAppsList(filteredApps);
        
        if (appsCount) {
            appsCount.textContent = `${filteredApps.length} of ${window.currentIOSApps.length} third-party applications`;
        }
    } else {
        updateIOSAppsList(window.currentIOSApps);
        
        if (appsCount) {
            appsCount.textContent = `${window.currentIOSApps.length} third-party applications`;
        }
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
        
        const response = await apiClient.request('POST', '/api/operations/ios/backup', options);
        
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

    // Only add to status log if it's a meaningful new message
    if (statusLog && message && message !== 'Processing...' && message !== 'Initializing...') {
        // Check if this message is different from the last one
        const currentLog = statusLog.textContent;
        const lastLineMatch = currentLog.match(/\[.*\] (.*)$/);
        const lastMessage = lastLineMatch ? lastLineMatch[1] : '';
        
        if (message !== lastMessage) {
            const timestamp = new Date().toLocaleTimeString();
            statusLog.textContent += `\n[${timestamp}] ${message}`;
            statusLog.scrollTop = statusLog.scrollHeight;
        }
    }
}

// Parser operations
async function startParsing() {
    // Determine which parser context we're in
    const iosParserTab = document.getElementById('ios-parser');
    const isIOSParser = iosParserTab && iosParserTab.classList.contains('active');
    
    let backupFile, parserType;
    
    if (isIOSParser) {
        backupFile = document.getElementById('ios-backup-file').value;
        parserType = document.getElementById('ios-parser-type').value;
    } else {
        backupFile = document.getElementById('backup-file').value;
        parserType = document.getElementById('parser-type').value;
    }
    
    if (!backupFile) {
        showNotification('Please select a backup file', 'error');
        return;
    }
    
    try {
        showLoading('Parsing backup file...');
        updateParserProgress(0, 'Starting parser...', isIOSParser ? 'ios' : 'android');
        
        const response = await apiClient.request('POST', '/api/operations/parse', {
            backup_file: backupFile,
            parser_type: parserType
        });
        
        if (response.success) {
            updateParserProgress(50, 'Parsing in progress...', isIOSParser ? 'ios' : 'android');
            pollParseProgress(isIOSParser ? 'ios' : 'android');
        } else {
            throw new Error(response.error || 'Failed to start parsing');
        }
    } catch (error) {
        console.error('Error starting parsing:', error);
        showNotification('Failed to start parsing: ' + error.message, 'error');
        updateParserProgress(0, 'Parsing failed to start', isIOSParser ? 'ios' : 'android');
    } finally {
        hideLoading();
    }
}

function updateParserProgress(percent, message, platform = 'android') {
    let progressFillId, progressTextId, statusLogId;
    
    if (platform === 'ios') {
        progressFillId = 'ios-parser-progress-fill';
        progressTextId = 'ios-parser-progress-text';
        statusLogId = 'ios-parser-status-log';
    } else {
        progressFillId = 'parser-progress-fill';
        progressTextId = 'parser-progress-text';
        statusLogId = 'parser-status-log';
    }
    
    const progressFill = document.getElementById(progressFillId);
    const progressText = document.getElementById(progressTextId);
    const statusLog = document.getElementById(statusLogId);
    
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

function updateParserStatus(message, platform = 'android') {
    let statusLogId = 'parser-status-log'; // Default to Android parser
    
    if (platform === 'ios') {
        statusLogId = 'ios-parser-status-log';
    }
    
    const statusLog = document.getElementById(statusLogId);
    if (statusLog) {
        const timestamp = new Date().toLocaleTimeString();
        statusLog.textContent += `\n[${timestamp}] ${message}`;
        statusLog.scrollTop = statusLog.scrollHeight;
    }
}

// Progress polling
let lastUpdateTimestamp = {};  // Track last update time per platform to avoid spam
let currentProgress = { android: 0, ios: 0 };  // Track current progress to prevent resets

async function pollTriageProgress(platform) {
    const pollInterval = setInterval(async () => {
        try {
            const response = await apiClient.request('GET', '/api/operations/status');
            
            if (response.operations && response.operations.length > 0) {
                const operation = response.operations[0]; // Get latest operation
                
                // Process all status updates for detailed feedback
                if (operation.updates && operation.updates.length > 0) {
                    const latestUpdate = operation.updates[operation.updates.length - 1];
                    const statusMessage = latestUpdate.message || 'Operation in progress';
                    
                    // Only use progress if it's valid and higher than current
                    let progress = currentProgress[platform];
                    if (latestUpdate.progress !== null && latestUpdate.progress !== undefined && latestUpdate.progress >= currentProgress[platform]) {
                        progress = latestUpdate.progress;
                        currentProgress[platform] = progress;
                    }
                    
                    // Only update if we have a meaningful message or new progress
                    if (latestUpdate.message || (latestUpdate.progress !== null && latestUpdate.progress !== undefined)) {
                        if (platform === 'android') {
                            updateAndroidProgress(progress, statusMessage);
                        } else if (platform === 'ios') {
                            updateiOSProgress(progress, statusMessage);
                        }
                    }
                } else {
                    // Only show fallback if we haven't shown anything recently
                    const now = Date.now();
                    const lastUpdate = lastUpdateTimestamp[platform] || 0;
                    
                    // Only show "Processing..." once every 10 seconds to avoid spam
                    if (now - lastUpdate > 10000) {
                        if (platform === 'android') {
                            updateAndroidProgress(currentProgress[platform], 'Initializing...');
                        } else if (platform === 'ios') {
                            updateiOSProgress(currentProgress[platform], 'Initializing...');
                        }
                        lastUpdateTimestamp[platform] = now;
                    }
                }
                
                if (operation.completed) {
                    clearInterval(pollInterval);
                    if (operation.success) {
                        showNotification(`${platform.toUpperCase()} triage completed successfully!`, 'success');
                        
                        console.log('Triage completed. Operation data:', operation);
                        console.log('Has structured_data:', !!operation.structured_data);
                        console.log('Has results:', !!operation.results);
                        console.log('DEBUG: Operation keys:', Object.keys(operation));
                        console.log('DEBUG: Results value:', operation.results);
                        console.log('DEBUG: Results type:', typeof operation.results);
                        
                        // Debug: Log detailed structured data
                        if (operation.structured_data) {
                            console.log('Structured data keys:', Object.keys(operation.structured_data));
                            console.log('Full structured data:', operation.structured_data);
                            if (operation.structured_data.artifacts) {
                                console.log('Artifacts keys:', Object.keys(operation.structured_data.artifacts));
                                for (const [key, value] of Object.entries(operation.structured_data.artifacts)) {
                                    if (value && typeof value === 'object' && value.record_count !== undefined) {
                                        console.log(`  ${key}: ${value.record_count} records`);
                                    }
                                }
                            }
                        }
                        
                        // Show results in the same tab for Android
                        if (platform === 'android') {
                            if (operation.structured_data) {
                                console.log('Using structured data from operation');
                                // Use structured data if available
                                showTriageResults('android', operation.results, operation.structured_data);
                            } else if (operation.results) {
                                console.log('Using results without structured data');
                                // Fallback to text results
                                showTriageResults('android', operation.results);
                            }
                        }
                        
                        // Update final status
                        if (platform === 'android') {
                            updateAndroidProgress(100, 'Triage completed successfully!');
                        }
                    } else {
                        showNotification(`${platform.toUpperCase()} triage failed: ${operation.error}`, 'error');
                        
                        // Update error status
                        if (platform === 'android') {
                            updateAndroidProgress(0, `Triage failed: ${operation.error}`);
                        }
                    }
                }
            }
        } catch (error) {
            console.error('Error polling progress:', error);
            clearInterval(pollInterval);
        }
    }, 1000); // Poll every second for better responsiveness
}

async function pollBackupProgress(platform) {
    console.log(`Starting backup progress polling for ${platform}`);
    
    let backupStage = 'Initializing';
    let lastProgress = 0;
    let lastStatus = '';
    
    const pollInterval = setInterval(async () => {
        try {
            const response = await apiClient.request('GET', '/api/operations/status');
            
            console.log('Backup progress response:', response);
            
            // Extract operations array from response
            const operations = response.operations || [];
            
            // DEBUG: Log all operations to see what we're getting
            console.log(`=== DEBUG: Received ${operations.length} operations ===`);
            operations.forEach((op, index) => {
                console.log(`Operation ${index}: ID=${op.operation_id}, type=${op.type}, progress=${op.progress}%`);
            });
            
            // Find backup operations for the current platform
            // Look for type match OR operation_id pattern match (in case type is 'unknown')
            const backupOperations = operations.filter(op => 
                op.type === `${platform}_backup` || 
                op.type === 'android_backup' ||
                (op.operation_id && op.operation_id.includes(`${platform}_backup`)) ||
                (op.operation_id && op.operation_id.includes('android_backup'))
            );
            
            console.log(`=== DEBUG: Found ${backupOperations.length} backup operations ===`);
            
            if (backupOperations.length > 0) {
                const latestOperation = backupOperations[backupOperations.length - 1];
                console.log('Latest backup operation:', latestOperation);
                
                const currentStatus = latestOperation.status || 'Processing backup...';
                const currentProgress = latestOperation.progress || lastProgress;
                
                // Determine backup stage based on status message
                if (currentStatus.includes('Installing') || currentStatus.includes('APK')) {
                    backupStage = 'APK Phase - Installing Forensic App';
                } else if (currentStatus.includes('Investigation complete') || currentStatus.includes('data files collected')) {
                    backupStage = 'APK Phase - Data Collection Complete';
                } else if (currentStatus.includes('ADB backup')) {
                    backupStage = 'ADB Phase - Creating System Backup';
                } else if (currentStatus.includes('device info') || currentStatus.includes('Getting device')) {
                    backupStage = 'Gathering Device Info';
                } else if (currentStatus.includes('SMS') || currentStatus.includes('messages')) {
                    backupStage = 'APK Phase - Extracting SMS Data';
                } else if (currentStatus.includes('contacts') || currentStatus.includes('Contacts')) {
                    backupStage = 'APK Phase - Extracting Contacts';
                } else if (currentStatus.includes('call') || currentStatus.includes('Call')) {
                    backupStage = 'APK Phase - Extracting Call Logs';
                } else if (currentStatus.includes('apps') || currentStatus.includes('Apps') || currentStatus.includes('third-party')) {
                    backupStage = 'Extracting App Data';
                } else if (currentStatus.includes('backup') && currentStatus.includes('Creating')) {
                    backupStage = 'ADB Phase - Creating Device Backup';
                } else if (currentStatus.includes('files') || currentStatus.includes('storage')) {
                    backupStage = 'Extracting Files';
                } else if (currentStatus.includes('Converted') || currentStatus.includes('CSV')) {
                    backupStage = 'Processing Data';
                } else if (currentStatus.includes('saved') || currentStatus.includes('completed')) {
                    backupStage = 'Finalizing';
                }
                
                // Only update if status has changed to avoid spam
                if (currentStatus !== lastStatus || currentProgress !== lastProgress) {
                    updateBackupStatus(currentStatus, currentProgress, backupStage);
                    lastStatus = currentStatus;
                    lastProgress = currentProgress;
                }
                
                // Handle completion
                if (latestOperation.updates && latestOperation.updates.length > 0) {
                    const lastUpdate = latestOperation.updates[latestOperation.updates.length - 1];
                    
                    // Debug: Log all updates to see what we're getting
                    console.log('=== DEBUG: All updates for operation ===');
                    latestOperation.updates.forEach((update, index) => {
                        console.log(`Update ${index}: type=${update.type}, message=${update.message}`);
                    });
                    
                    // Check ALL updates for ready_for_pull status, but only if APK removal hasn't started
                    const apkRemovalInProgress = latestOperation.updates.find(update => 
                        update.message && update.message.includes('Removing forensic APK')
                    );
                    
                    const readyForPull = latestOperation.updates.find(update => update.type === 'ready_for_pull');
                    if (readyForPull && !apkRemovalInProgress) {
                        console.log('*** FOUND READY FOR PULL STATUS! ***');
                        console.log('Ready for pull:', readyForPull);
                        clearInterval(pollInterval);
                        showDataPullPrompt(latestOperation.operation_id);
                        return;
                    } else if (readyForPull && apkRemovalInProgress) {
                        console.log('*** READY FOR PULL FOUND BUT APK REMOVAL IN PROGRESS - SKIPPING ***');
                    }
                    
                    // Check ALL updates for APK removal prompt, not just the last one
                    const apkRemovalPrompt = latestOperation.updates.find(update => update.type === 'apk_removal_prompt');
                    if (apkRemovalPrompt) {
                        console.log('*** FOUND APK REMOVAL PROMPT IN FRONTEND! ***');
                        console.log('APK prompt:', apkRemovalPrompt);
                        clearInterval(pollInterval);
                        // Use the original operation ID from the prompt, not the current operation ID
                        const originalOperationId = apkRemovalPrompt.original_operation_id || latestOperation.operation_id;
                        showApkRemovalPrompt(originalOperationId);
                        return;
                    }
                    
                    // Handle APK removal prompt (fallback check on last update)
                    if (lastUpdate.type === 'apk_removal_prompt') {
                        console.log('*** APK REMOVAL PROMPT DETECTED (last update) ***');
                        clearInterval(pollInterval);
                        // Use the original operation ID from the prompt, not the current operation ID
                        const originalOperationId = lastUpdate.original_operation_id || latestOperation.operation_id;
                        showApkRemovalPrompt(originalOperationId);
                        return;
                    }
                    
                    // Don't show completion for APK processing alone - wait for backend's 'complete' signal
                    // The backend will determine if ADB backup is needed and send 'complete' accordingly
                    
                    if (lastUpdate.type === 'complete') {
                        clearInterval(pollInterval);
                        
                        if (lastUpdate.success) {
                            updateBackupStatus('✅ Android backup completed successfully!', 100, 'Complete');
                            showNotification('Android backup completed successfully!', 'success');
                            console.log('SUCCESS: ANDROID backup completed successfully!');
                            
                            // Show completion summary
                            setTimeout(() => {
                                const backupPath = lastUpdate.backup_path || 'Unknown location';
                                updateBackupStatus(`💾 Backup saved to: ${backupPath}`, 100, 'Complete');
                            }, 1000);
                            
                            // Re-enable backup button after completion
                            setTimeout(() => {
                                const backupButton = document.getElementById('start-android-backup');
                                if (backupButton) {
                                    backupButton.disabled = false;
                                    backupButton.textContent = 'Start Android Backup';
                                }
                            }, 3000);
                            
                        } else {
                            // Check if this is specifically an ADB backup failure
                            const isADBFailure = lastUpdate.message && lastUpdate.message.includes('ADB backup failed');
                            
                            updateBackupStatus('❌ Android backup failed', 0, 'Failed');
                            showNotification(`Android backup failed: ${lastUpdate.message}`, 'error');
                            
                            // Re-enable backup button on failure
                            const backupButton = document.getElementById('start-android-backup');
                            if (backupButton) {
                                backupButton.disabled = false;
                                backupButton.textContent = 'Start Android Backup';
                            }
                            
                            // Offer frontend ADB backup if it's an ADB-specific failure
                            if (isADBFailure) {
                                console.log('Detected ADB backup failure, offering frontend alternative...');
                                setTimeout(() => {
                                    // Get the original backup options from global state if available
                                    const caseNumber = document.getElementById('case-number-android')?.value || 'unknown';
                                    const outputDir = document.getElementById('output-directory-android')?.value || '/tmp';
                                    const deviceId = null; // We'll detect this in the frontend function
                                    
                                    const backupOptions = {
                                        output_dir: outputDir,
                                        case_number: caseNumber,
                                        device_id: deviceId,
                                        backup_apps: true,  // Default values
                                        backup_shared: true,
                                        backup_system: false
                                    };
                                    
                                    handleADBBackupFailure(backupOptions);
                                }, 2000); // Small delay to let user see the failure message
                            }
                        }
                        return;
                    }
                }
                
                // Check for successful completion (legacy support)
                if (latestOperation.completed) {
                    clearInterval(pollInterval);
                    if (latestOperation.success) {
                        updateBackupStatus('✅ Android backup completed successfully!', 100, 'Complete');
                        showNotification(`${platform.toUpperCase()} backup completed successfully!`, 'success');
                    } else {
                        updateBackupStatus(`❌ Backup failed: ${latestOperation.error}`, 0, 'Failed');
                        showNotification(`${platform.toUpperCase()} backup failed: ${latestOperation.error}`, 'error');
                    }
                }
                
            } else {
                // No operations found, show waiting status
                updateBackupStatus('⏳ Waiting for backup to start...', 0, 'Initializing');
            }
            
        } catch (error) {
            console.error('Error polling backup progress:', error);
            clearInterval(pollInterval);
            updateBackupStatus('❌ Error monitoring backup progress', 0, 'Error');
            showNotification('Error monitoring backup progress', 'error');
        }
    }, 1500); // Poll every 1.5 seconds for more responsive feedback
    
    // Set a maximum polling time (30 minutes)
    setTimeout(() => {
        clearInterval(pollInterval);
        updateBackupStatus('⚠️ Backup monitoring timed out after 30 minutes', null, 'Timeout');
    }, 30 * 60 * 1000);
}

async function pollParseProgress(platform = 'android') {
    const pollInterval = setInterval(async () => {
        try {
            const response = await apiClient.request('GET', '/api/operations/status');
            
            if (response.operations && response.operations.length > 0) {
                const operation = response.operations[0];
                
                updateParserProgress(operation.progress || 0, operation.status || 'Parsing...', platform);
                
                if (operation.completed) {
                    clearInterval(pollInterval);
                    if (operation.success && operation.results) {
                        // For iOS, results are handled by showIOSParseResults
                        if (platform === 'ios') {
                            // iOS results handled by showIOSParseResults function
                        } else {
                            // Handle Android results
                            const resultsDisplay = document.getElementById('parser-results-display');
                            const exportBtn = document.getElementById('export-results-btn');
                            
                            if (resultsDisplay) {
                                resultsDisplay.textContent = operation.results;
                            }
                            if (exportBtn) {
                                exportBtn.disabled = false;
                            }
                        }
                        
                        showNotification('Parsing completed successfully!', 'success');
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

// Triage Results Functions

// Helper function to check if structured data contains file references instead of actual records
function checkIfDataNeedsLoading(structuredData) {
    // Check if any data fields have file references instead of records
    const dataFields = ['sms_data', 'contacts_data', 'notifications_data', 'mms_data'];
    
    for (const field of dataFields) {
        if (structuredData[field] && typeof structuredData[field] === 'object') {
            // If it has csv_file or raw_file properties, it means we have file references, not actual data
            if (structuredData[field].csv_file || structuredData[field].raw_file) {
                return true;
            }
        }
    }
    
    return false;
}

// Function to load actual triage data from the API
async function loadActualTriageData() {
    try {
        console.log('Loading actual triage data from API...');
        const response = await makeRequest('GET', '/api/android/triage/latest-results');
        
        if (response.success && response.structured_data) {
            console.log('Successfully loaded actual triage data');
            populateTriageDataTables(response.structured_data);
            showResultsTab('apps');
        } else {
            console.error('Failed to load actual triage data:', response);
            showNotification('Failed to load triage data', 'error');
        }
    } catch (error) {
        console.error('Error loading actual triage data:', error);
        showNotification('Error loading triage data', 'error');
    }
}

function showTriageResults(platform, results, structuredData = null) {
    console.log('showTriageResults called with:', { platform, resultsType: typeof results, hasStructuredData: !!structuredData });
    console.log('Structured data:', structuredData);
    
    if (platform === 'android') {
        const tabNav = document.getElementById('results-tab-nav');
        
        // Show the tab navigation
        if (tabNav) {
            tabNav.style.display = 'flex';
        }
        
        // If we have structured data, check if it contains actual records or just file references
        if (structuredData) {
            console.log('Using structured data for table population');
            
            // Check if we have file references instead of actual data
            const needsDataLoading = checkIfDataNeedsLoading(structuredData);
            
            if (needsDataLoading) {
                console.log('Structured data contains file references, loading actual data from API');
                loadActualTriageData();
            } else {
                populateTriageDataTables(structuredData);
                // Show the apps tab by default
                showResultsTab('apps');
            }
        } else {
            console.log('No structured data provided, trying to parse results');
            // Try to parse the results if it's JSON (from actual triage)
            let triageData = null;
            try {
                // Check if results contains JSON-like data or if we have triage data
                if (typeof results === 'object') {
                    triageData = results;
                } else if (results.includes('"case_number"') || results.includes('"device_details"')) {
                    // Attempt to extract JSON from the results string
                    const jsonMatch = results.match(/\{.*\}/s);
                    if (jsonMatch) {
                        triageData = JSON.parse(jsonMatch[0]);
                    }
                }
            } catch (e) {
                console.log('Results are not JSON, displaying as text');
            }
            
            // If we have structured triage data, populate the tables
            if (triageData) {
                console.log('Parsed triage data from results, populating tables');
                populateTriageDataTables(triageData);
                
                // Show the apps tab by default
                showResultsTab('apps');
            } else {
                console.log('No parseable triage data found');
            }
        }
        
        // Scroll to results section
        const resultsSection = document.getElementById('android-triage-results');
        if (resultsSection) {
            resultsSection.scrollIntoView({ behavior: 'smooth' });
        }
    }
}

function populateTriageDataTables(triageData) {
    console.log('populateTriageDataTables called with:', triageData);
    console.log('Triage data keys:', Object.keys(triageData || {}));

    // This function now acts as a dispatcher.
    // It will call the appropriate function to load data for each table.
    // The data loading can come from the main triageData object or by reading CSVs.

    // Populate Apps table
    if (triageData.apps && Array.isArray(triageData.apps)) {
        console.log('Populating apps table with', triageData.apps.length, 'apps');
        populateAppsTable(triageData.apps);
    } else {
        loadTableData('apps', []);
    }

    // Populate SMS table
    if (triageData.sms_data && Array.isArray(triageData.sms_data)) {
        console.log('Populating SMS table with', triageData.sms_data.length, 'records from triageData');
        populateSMSTable(triageData.sms_data);
    } else if (triageData.case_directory) {
        console.log('Case directory found, populating SMS table from CSV');
        populateSMSTableFromCSV(triageData.case_directory);
    } else {
        loadTableData('sms', []);
    }

    // Populate Contacts table
    if (triageData.contacts_data && Array.isArray(triageData.contacts_data)) {
        console.log('Populating contacts table with', triageData.contacts_data.length, 'records from triageData');
        populateContactsTable(triageData.contacts_data);
    } else if (triageData.case_directory) {
        console.log('Case directory found, populating Contacts table from CSV');
        populateContactsTableFromCSV(triageData.case_directory);
    } else {
        loadTableData('contacts', []);
    }

    // Populate Call Logs table
    if (triageData.call_logs_data && Array.isArray(triageData.call_logs_data)) {
        console.log('Populating call logs table with', triageData.call_logs_data.length, 'records from triageData');
        populateCallLogsTable(triageData.call_logs_data);
    } else if (triageData.case_directory) {
        console.log('Case directory found, populating Call Logs table from CSV');
        populateCallLogsTableFromCSV(triageData.case_directory);
    } else {
        loadTableData('call-logs', []);
    }
    
    // Populate Photos and Videos tables with data from structured data
    console.log('Loading photos and videos from structured data...');
    populatePhotosTable(triageData);
    populateVideosTable(triageData);

    // Populate Notifications table
    if (triageData.notifications_data && Array.isArray(triageData.notifications_data)) {
        console.log('Populating notifications table with', triageData.notifications_data.length, 'records from triageData');
        populateNotificationsTable(triageData.notifications_data);
    } else if (triageData.case_directory) {
        console.log('Case directory found, populating Notifications table from CSV');
        populateNotificationsTableFromCSV(triageData.case_directory);
    } else {
        loadTableData('notifications', []);
    }
}

function populateAppsTable(apps) {
    console.log('Populating apps table with data:', apps);
    
    if (!apps || !Array.isArray(apps)) {
        console.log('No apps data available');
        loadTableData('apps', []);
        return;
    }
    
    // Convert apps data to consistent format for table management
    const formattedApps = apps.map(app => ({
        package: app.package || app.Package || 'Unknown',
        name: app.name || app.Name || 'Unknown',
        version: app.version || app.Version || 'Unknown',
        user_id: app.user_id || app.UserID || app.userId || '0'
    }));
    
    loadTableData('apps', formattedApps);
}

function populateSMSTable(smsData) {
    console.log('Populating SMS table with data:', smsData);
    console.log('SMS data keys:', smsData ? Object.keys(smsData) : 'null/undefined');
    console.log('SMS data type:', typeof smsData);
    
    let records = [];
    
    // Check different possible data structures
    if (smsData && Array.isArray(smsData)) {
        records = smsData;
    } else if (smsData && smsData.records && Array.isArray(smsData.records)) {
        records = smsData.records;
    } else if (smsData && smsData.data && Array.isArray(smsData.data)) {
        records = smsData.data;
    }
    
    if (records.length === 0) {
        console.log('No SMS data available - no valid records found');
        loadTableData('sms', []);
        return;
    }
    
    console.log('Found', records.length, 'SMS records to process');
    
    // Debug: show the structure of the first SMS
    if (records.length > 0) {
        console.log('First SMS structure:', records[0]);
        console.log('First SMS keys:', Object.keys(records[0] || {}));
        console.log('Sample SMS fields:');
        const firstSMS = records[0];
        Object.keys(firstSMS).forEach(key => {
            console.log(`  ${key}:`, firstSMS[key]);
        });
    }
    
    // Convert SMS data to show all available columns from CSV
    const formattedSMS = records.map(sms => {
        // Create a new object with all the original fields
        const formattedRecord = {};
        
        // Copy all original fields
        Object.keys(sms).forEach(key => {
            let value = sms[key];
            
            // Convert Unix timestamps to human-readable dates
            value = formatUnixTimestamp(value, key);
            
            // Special formatting for message body - truncate if too long
            if (key === 'body' && value && typeof value === 'string' && value.length > 200) {
                value = value.substring(0, 200) + '...';
            }
            
            // Convert type codes to readable format if this is the type field
            if (key === 'type' && (value === '1' || value === '2')) {
                value = value === '1' ? 'Received' : 'Sent';
            }
            
            formattedRecord[key] = value || '';
        });
        
        return formattedRecord;
    });
    
    // Generate dynamic table headers
    if (formattedSMS.length > 0) {
        generateDynamicTableHeaders('sms', Object.keys(formattedSMS[0]));
    }
    
    loadTableData('sms', formattedSMS);
}

function populateContactsTable(contactsData) {
    console.log('Populating contacts table with data:', contactsData);
    console.log('Contacts data keys:', contactsData ? Object.keys(contactsData) : 'null/undefined');
    console.log('Contacts data type:', typeof contactsData);
    
    let records = [];
    
    // Check different possible data structures
    if (contactsData && Array.isArray(contactsData)) {
        records = contactsData;
    } else if (contactsData && contactsData.records && Array.isArray(contactsData.records)) {
        records = contactsData.records;
    } else if (contactsData && contactsData.data && Array.isArray(contactsData.data)) {
        records = contactsData.data;
    }
    
    if (records.length === 0) {
        console.log('No contacts data available - no valid records found');
        loadTableData('contacts', []);
        return;
    }
    
    console.log('Found', records.length, 'contact records to process');
    
    // Debug: show the structure of the first contact
    if (records.length > 0) {
        console.log('First contact structure:', records[0]);
        console.log('First contact keys:', Object.keys(records[0] || {}));
        console.log('Sample contact fields:');
        const firstContact = records[0];
        Object.keys(firstContact).forEach(key => {
            console.log(`  ${key}:`, firstContact[key]);
        });
    }
    
    // Convert contacts data to show all available columns from CSV
    const formattedContacts = records.map(contact => {
        // Create a new object with all the original fields
        const formattedRecord = {};
        
        // Copy all original fields
        Object.keys(contact).forEach(key => {
            let value = contact[key];
            
            // Convert Unix timestamps to human-readable dates
            value = formatUnixTimestamp(value, key);
            
            formattedRecord[key] = value || '';
        });
        
        return formattedRecord;
    });
    
    // Generate dynamic table headers
    if (formattedContacts.length > 0) {
        generateDynamicTableHeaders('contacts', Object.keys(formattedContacts[0]));
    }
    
    loadTableData('contacts', formattedContacts);
}

function populateCallLogsTable(callLogsData) {
    console.log('Populating call logs table with data:', callLogsData);
    console.log('Call logs data keys:', callLogsData ? Object.keys(callLogsData) : 'null/undefined');
    console.log('Call logs data type:', typeof callLogsData);
    
    let records = [];
    
    // Check different possible data structures
    if (callLogsData && Array.isArray(callLogsData)) {
        records = callLogsData;
    } else if (callLogsData && callLogsData.records && Array.isArray(callLogsData.records)) {
        records = callLogsData.records;
    } else if (callLogsData && callLogsData.data && Array.isArray(callLogsData.data)) {
        records = callLogsData.data;
    }
    
    if (records.length === 0) {
        console.log('No call logs data available - no valid records found');
        loadTableData('call-logs', []);
        return;
    }
    
    console.log('Found', records.length, 'call log records to process');
    
    // Convert call logs data to show all available columns from CSV
    const formattedCallLogs = records.map(call => {
        // Create a new object with all the original fields
        const formattedRecord = {};
        
        // Copy all original fields
        Object.keys(call).forEach(key => {
            let value = call[key];
            
            // Convert Unix timestamps to human-readable dates
            value = formatUnixTimestamp(value, key);
            
            // Convert call type codes to readable format if this is the type field
            if (key === 'type') {
                if (value === '1') value = 'Incoming';
                else if (value === '2') value = 'Outgoing';
                else if (value === '3') value = 'Missed';
            }
            
            // Format duration if this is the duration field
            if (key === 'duration' && value && !isNaN(value)) {
                const seconds = parseInt(value);
                const minutes = Math.floor(seconds / 60);
                const remainingSeconds = seconds % 60;
                value = `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
            }
            
            formattedRecord[key] = value || '';
        });
        
        return formattedRecord;
    });
    
    // Generate dynamic table headers
    if (formattedCallLogs.length > 0) {
        generateDynamicTableHeaders('call-logs', Object.keys(formattedCallLogs[0]));
    }
    
    loadTableData('call-logs', formattedCallLogs);
}

function populateFilesTable(files) {
    console.log('Populating files table with data:', files);
    
    if (!files || !Array.isArray(files)) {
        console.log('No files data available');
        loadTableData('files', []);
        return;
    }
    
    // Convert files data to show all available columns from CSV
    const formattedFiles = files.map(file => {
        // Create a new object with all the original fields
        const formattedRecord = {};
        
        // Copy all original fields
        Object.keys(file).forEach(key => {
            let value = file[key];
            
            // Convert Unix timestamps to human-readable dates
            value = formatUnixTimestamp(value, key);
            
            formattedRecord[key] = value || '';
        });
        
        return formattedRecord;
    });
    
    // Generate dynamic table headers
    if (formattedFiles.length > 0) {
        generateDynamicTableHeaders('files', Object.keys(formattedFiles[0]));
    }
    
    loadTableData('files', formattedFiles);
}

// Populate photos table with images data from structured data
function populatePhotosTable(triageData) {
    console.log('Populating photos table with data from structured data');
    console.log('Triage data keys:', Object.keys(triageData));
    
    let records = [];
    
    // Check for images_data in the structured data
    if (triageData.images_data && Array.isArray(triageData.images_data)) {
        records = triageData.images_data;
    } else if (triageData.images_data && triageData.images_data.records && Array.isArray(triageData.images_data.records)) {
        records = triageData.images_data.records;
    } else if (triageData.images_data && triageData.images_data.data && Array.isArray(triageData.images_data.data)) {
        records = triageData.images_data.data;
    }
    
    if (records.length === 0) {
        console.log('No photos data available - no valid records found');
        loadTableData('photos', []);
        return;
    }
    
    console.log('Found', records.length, 'photo records to process');
    
    // Debug: show the structure of the first photo
    if (records.length > 0) {
        console.log('First photo structure:', records[0]);
        console.log('First photo keys:', Object.keys(records[0] || {}));
        console.log('Sample photo fields:');
        const firstPhoto = records[0];
        Object.keys(firstPhoto).forEach(key => {
            console.log(`  ${key}:`, firstPhoto[key]);
        });
    }
    
    // Convert photos data to show all available columns
    const formattedPhotos = records.map(photo => {
        // Create a new object with all the original fields
        const formattedRecord = {};
        
        // Copy all original fields
        Object.keys(photo).forEach(key => {
            let value = photo[key];
            
            // Convert Unix timestamps to human-readable dates
            value = formatUnixTimestamp(value, key);
            
            formattedRecord[key] = value || '';
        });
        
        return formattedRecord;
    });
    
    // Generate dynamic table headers
    if (formattedPhotos.length > 0) {
        generateDynamicTableHeaders('photos', Object.keys(formattedPhotos[0]));
    }
    
    loadTableData('photos', formattedPhotos);
}

// Populate videos table with videos data from structured data
function populateVideosTable(triageData) {
    console.log('=== VIDEOS TABLE FUNCTION CALLED ===');
    console.log('Populating videos table with data from structured data');
    console.log('Triage data keys:', Object.keys(triageData));
    
    let records = [];
    
    // Check for videos_data in the structured data
    if (triageData.videos_data && Array.isArray(triageData.videos_data)) {
        records = triageData.videos_data;
    } else if (triageData.videos_data && triageData.videos_data.records && Array.isArray(triageData.videos_data.records)) {
        records = triageData.videos_data.records;
    } else if (triageData.videos_data && triageData.videos_data.data && Array.isArray(triageData.videos_data.data)) {
        records = triageData.videos_data.data;
    }
    
    if (records.length === 0) {
        console.log('No videos data available - no valid records found');
        loadTableData('videos', []);
        return;
    }
    
    console.log('Found', records.length, 'video records to process');
    
    // Debug: show the structure of the first video
    if (records.length > 0) {
        console.log('First video structure:', records[0]);
        console.log('First video keys:', Object.keys(records[0] || {}));
        console.log('Sample video fields:');
        const firstVideo = records[0];
        Object.keys(firstVideo).forEach(key => {
            console.log(`  ${key}:`, firstVideo[key]);
        });
    }
    
    // Convert videos data to show all available columns
    const formattedVideos = records.map(video => {
        // Create a new object with all the original fields
        const formattedRecord = {};
        
        // Copy all original fields
        Object.keys(video).forEach(key => {
            let value = video[key];
            
            // Convert Unix timestamps to human-readable dates
            value = formatUnixTimestamp(value, key);
            
            formattedRecord[key] = value || '';
        });
        
        return formattedRecord;
    });
    
    // Generate dynamic table headers
    if (formattedVideos.length > 0) {
        generateDynamicTableHeaders('videos', Object.keys(formattedVideos[0]));
    }
    
    loadTableData('videos', formattedVideos);
}

function populateNotificationsTable(notificationsData) {
    console.log('Populating notifications table with data:', notificationsData);
    console.log('Notifications data keys:', notificationsData ? Object.keys(notificationsData) : 'null/undefined');
    console.log('Notifications data type:', typeof notificationsData);
    
    let records = [];
    
    // Check different possible data structures
    if (notificationsData && Array.isArray(notificationsData)) {
        records = notificationsData;
    } else if (notificationsData && notificationsData.records && Array.isArray(notificationsData.records)) {
        records = notificationsData.records;
    } else if (notificationsData && notificationsData.data && Array.isArray(notificationsData.data)) {
        records = notificationsData.data;
    }
    
    if (records.length === 0) {
        console.log('No notifications data available - no valid records found');
        loadTableData('notifications', []);
        return;
    }
    
    console.log('Found', records.length, 'notification records to process');
    
    // Convert notifications data to show all available columns from CSV
    const formattedNotifications = records.map(notification => {
        // Create a new object with all the original fields
        const formattedRecord = {};
        
        // Copy all original fields
        Object.keys(notification).forEach(key => {
            let value = notification[key];
            
            // Convert Unix timestamps to human-readable dates
            value = formatUnixTimestamp(value, key);
            
            // Truncate long text fields
            if ((key.toLowerCase().includes('text') || key.toLowerCase().includes('content')) && 
                value && typeof value === 'string' && value.length > 200) {
                value = value.substring(0, 200) + '...';
            }
            
            formattedRecord[key] = value || '';
        });
        
        return formattedRecord;
    });
    
    // Generate dynamic table headers
    if (formattedNotifications.length > 0) {
        generateDynamicTableHeaders('notifications', Object.keys(formattedNotifications[0]));
    }
    
    loadTableData('notifications', formattedNotifications);
}

// CSV reading functions for direct file access
async function populateSMSTableFromCSV(caseDirectory) {
    try {
        console.log('Reading SMS CSV file from case directory:', caseDirectory);
        
        // Read SMS CSV file - use correct data type parameter
        const csvResult = await electronAPI.invoke('android-csv:readFile', caseDirectory, 'SMS Messages');
        
        if (!csvResult || !csvResult.data || csvResult.data.length === 0) {
            console.log('No SMS data found in CSV');
            return;
        }
        
        const smsData = csvResult.data;
        console.log('Found', smsData.length, 'SMS records in CSV');
        console.log('SMS CSV columns:', csvResult.columns);
        console.log('First SMS record structure:', smsData[0]);
        console.log('First SMS record keys:', Object.keys(smsData[0] || {}));
        
        // Format SMS data for display
        const formattedSMS = smsData.map(sms => {
            // Format date if available
            let dateStr = sms.date || sms.Date || 'Unknown';
            if (dateStr && dateStr !== 'Unknown' && !isNaN(dateStr)) {
                try {
                    const date = new Date(parseInt(dateStr));
                    dateStr = date.toLocaleString();
                } catch (e) {
                    // Keep original if parsing fails
                }
            }
            
            // Determine message type
            let messageType = 'Unknown';
            const type = sms.type || sms.Type;
            if (type === '1') messageType = 'Received';
            else if (type === '2') messageType = 'Sent';
            else if (type === '3') messageType = 'Draft';
            
            return {
                date: dateStr,
                contact: sms.address || sms.Address || 'Unknown',  // Use address field for contact info
                message: (sms.body || sms.Body || 'No message').substring(0, 200),  // Use body field for message content
                type: messageType
            };
        });
        
        loadTableData('sms', formattedSMS);
        console.log('SMS table populated with', formattedSMS.length, 'records');
        
    } catch (error) {
        console.error('Error reading SMS CSV:', error);
    }
}

async function populateContactsTableFromCSV(caseDirectory) {
    try {
        console.log('Reading Android Contacts CSV file from case directory:', caseDirectory);
        
        // Read Android Contacts CSV file - use correct Android CSV reader
        const csvResult = await electronAPI.invoke('android-csv:readFile', caseDirectory, 'Contacts');
        
        if (!csvResult || !csvResult.data || csvResult.data.length === 0) {
            console.log('No contacts data found in CSV');
            return;
        }
        
        const contactsData = csvResult.data;
        console.log('Found', contactsData.length, 'contact records in CSV');
        console.log('Contacts CSV columns:', csvResult.columns);
        console.log('First contact record structure:', contactsData[0]);
        console.log('First contact record keys:', Object.keys(contactsData[0] || {}));
        
        // Format contacts data for display - use Android column names from actual CSV structure
        // Android contacts CSV has: raw_contact_id,display_name,phone_numbers,emails,addresses,organizations,other_data
        const formattedContacts = contactsData.map(contact => {
            return {
                name: contact.display_name || 'Unknown',
                phone: contact.phone_numbers || 'Unknown',
                email: contact.emails || 'Unknown',
                organization: contact.organizations || 'Unknown'
            };
        });
        
        loadTableData('contacts', formattedContacts);
        console.log('Contacts table populated with', formattedContacts.length, 'records');
        
    } catch (error) {
        console.error('Error reading Android Contacts CSV:', error);
    }
}

async function populateNotificationsTableFromCSV(caseDirectory) {
    try {
        console.log('Reading Notifications CSV file from case directory:', caseDirectory);
        
        // Read Notifications CSV file - use correct data type parameter
        const csvResult = await electronAPI.invoke('android-csv:readFile', caseDirectory, 'Notifications');
        
        if (!csvResult || !csvResult.data || csvResult.data.length === 0) {
            console.log('No notifications data found in CSV');
            return;
        }
        
        const notificationsData = csvResult.data;
        console.log('Found', notificationsData.length, 'notification records in CSV');
        
        // Format notifications data for display
        const formattedNotifications = notificationsData.map(notification => {
            // Format timestamp if available
            let timestampStr = notification.when || notification.When || notification.timestamp || notification.Timestamp || 'Unknown';
            if (timestampStr && timestampStr !== 'Unknown' && !isNaN(timestampStr)) {
                try {
                    const date = new Date(parseInt(timestampStr));
                    timestampStr = date.toLocaleString();
                } catch (e) {
                    // Keep original if parsing fails
                }
            }
            
            // Extract title and text from extras field
            let title = 'No Title';
            let text = 'No Text';
            
            const extras = notification.extras || notification.Extras || '';
            if (extras) {
                const titleMatch = extras.match(/android\.title=String \(([^)]+)\)/);
                const textMatch = extras.match(/android\.text=String \(([^)]+)\)/);
                
                if (titleMatch) title = titleMatch[1];
                if (textMatch) text = textMatch[1];
            }
            
            // Use ticker_text as fallback for title
            if (title === 'No Title' && notification.ticker_text) {
                title = notification.ticker_text;
            }
            
            return {
                package: notification.package || notification.Package || 'Unknown',
                title: title,
                text: text.substring(0, 200),
                timestamp: timestampStr
            };
        });
        
        loadTableData('notifications', formattedNotifications);
        console.log('Notifications table populated with', formattedNotifications.length, 'records');
        
    } catch (error) {
        console.error('Error reading Notifications CSV:', error);
    }
}

async function populateCallLogsTableFromCSV(caseDirectory) {
    try {
        console.log('Reading Call Logs CSV file from case directory:', caseDirectory);
        
        const csvResult = await electronAPI.invoke('android-csv:readFile', caseDirectory, 'Call Logs');
        
        if (!csvResult || !csvResult.data || csvResult.data.length === 0) {
            console.log('No call logs data found in CSV');
            loadTableData('call-logs', []);
            return;
        }
        
        const callLogsData = csvResult.data;
        console.log('Found', callLogsData.length, 'call log records in CSV');
        
        const formattedCallLogs = callLogsData.map(call => {
            let dateStr = call.date || call.Date || 'Unknown';
            if (dateStr && dateStr !== 'Unknown' && !isNaN(dateStr)) {
                try {
                    const date = new Date(parseInt(dateStr));
                    dateStr = date.toLocaleString();
                } catch (e) { /* keep original */ }
            }
            
            let callType = 'Unknown';
            const type = call.type || call.Type;
            if (type === '1') callType = 'Incoming';
            else if (type === '2') callType = 'Outgoing';
            else if (type === '3') callType = 'Missed';
            
            let duration = call.duration || call.Duration || '0';
            if (!isNaN(duration)) {
                const seconds = parseInt(duration);
                const minutes = Math.floor(seconds / 60);
                const remainingSeconds = seconds % 60;
                duration = `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
            }
            
            return {
                date: dateStr,
                number: call.number || call.Number || 'Unknown',
                name: call.name || call.Name || 'Unknown',
                type: callType,
                duration: duration
            };
        });
        
        loadTableData('call-logs', formattedCallLogs);
        console.log('Call logs table populated with', formattedCallLogs.length, 'records');
        
    } catch (error) {
        console.error('Error reading Call Logs CSV:', error);
        loadTableData('call-logs', []);
    }
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

// Android CSV functionality
let androidCSVViewer = null;

async function loadAndroidCSVReports(caseDirectory) {
    console.log('DEBUG: loadAndroidCSVReports called with caseDirectory:', caseDirectory);
    
    if (!caseDirectory) {
        console.log('Android triage completed, but no case directory found for CSV reports.');
        return;
    }
    
    try {
        // Initialize Android CSV viewer if needed
        if (!androidCSVViewer) {
            androidCSVViewer = new CSVDataViewer('android-csv-data-viewer');
        }
        
        // Load available Android CSV reports
        const reports = await electronAPI.invoke('android-csv:scanReports', caseDirectory);
        
        if (!reports || reports.length === 0) {
            console.log(`Android triage completed, but no CSV reports were found in ${caseDirectory}.`);
            return;
        }
        
        // Show CSV data tab and hide other content
        const csvContainer = document.getElementById('android-results-csv-data');
        if (csvContainer) {
            csvContainer.style.display = 'block';
        }
        
        // Create tabs for Android CSV reports
        createAndroidCSVReportTabs(reports, caseDirectory);
        
        console.log(`Android triage completed. Found ${reports.length} CSV report types with data.`);
        
    } catch (error) {
        console.error('Error loading Android CSV reports:', error);
        console.log(`Android triage completed, but unable to load CSV reports: ${error.message}`);
    }
}

async function createAndroidCSVReportTabs(reports, caseDirectory) {
    const csvTabsContainer = document.getElementById('android-csv-report-tabs');
    if (!csvTabsContainer) return;
    
    // Clear existing CSV tabs
    csvTabsContainer.innerHTML = '';
    
    // Create tab for each available report
    for (const report of reports) {
        const button = document.createElement('button');
        button.className = 'results-tab-btn';
        
        // Get icon for this report type
        const icon = getDataTypeIcon(report.type);
        button.innerHTML = `${icon} ${report.name}`;
        
        button.addEventListener('click', async () => {
            // Update active tab
            csvTabsContainer.querySelectorAll('.results-tab-btn').forEach(btn => 
                btn.classList.remove('active'));
            button.classList.add('active');
            
            // Load data in CSV viewer
            if (androidCSVViewer) {
                try {
                    await androidCSVViewer.loadDataType(report.type, caseDirectory, 'android-csv:readFile');
                } catch (error) {
                    console.error('Error loading Android CSV data:', error);
                }
            }
        });
        
        csvTabsContainer.appendChild(button);
    }
    
    // Activate first tab by default
    if (reports.length > 0) {
        const firstTab = csvTabsContainer.querySelector('.results-tab-btn');
        if (firstTab) {
            firstTab.click();
        }
    }
}

// Helper function to get icons for different report types
function getDataTypeIcon(reportType) {
    const iconMap = {
        'triage': '📊',
        'sms': '💬',
        'call_logs': '📞',
        'contacts': '👥',
        'files': '📁',
        'notifications': '🔔',
        'device_details': 'ℹ️',
        'apps': '📱'
    };
    return iconMap[reportType] || '📄';
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
    if (overlay) {
        const text = overlay.querySelector('p');
        if (text) text.textContent = message;
        overlay.classList.remove('hidden');
    }
}

function hideLoading() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.classList.add('hidden');
    }
}

// Ensure loading is hidden when page loads
window.addEventListener('load', function() {
    console.log('Window loaded, ensuring loading overlay is hidden');
    hideLoading();
});

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

// Results tab management
function showResultsTab(tabName) {
    console.log('Switching to results tab:', tabName);
    
    // Hide all result tab panes
    const resultPanes = document.querySelectorAll('.results-pane');
    resultPanes.forEach(pane => {
        pane.classList.remove('active');
    });
    
    // Remove active class from all tab buttons
    const tabButtons = document.querySelectorAll('.results-tab-btn');
    tabButtons.forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show the selected tab pane (fix the ID pattern)
    const selectedPane = document.getElementById(`results-${tabName}`);
    if (selectedPane) {
        selectedPane.classList.add('active');
        console.log(`Successfully activated pane: results-${tabName}`);
    } else {
        console.error(`Could not find pane with ID: results-${tabName}`);
    }
    
    // Add active class to the clicked button
    const selectedButton = document.querySelector(`[onclick="showResultsTab('${tabName}')"]`);
    if (selectedButton) {
        selectedButton.classList.add('active');
        console.log(`Successfully activated button for: ${tabName}`);
    } else {
        console.error(`Could not find button for: ${tabName}`);
    }
    
    console.log(`Results tab switched to: ${tabName}`);
}

// Clear results function
function clearResults(platform) {
    console.log('Clearing results for platform:', platform);
    
    if (platform === 'android') {
        // Clear all table data
        const tableNames = ['apps', 'sms', 'contacts', 'call-logs', 'photos', 'videos', 'notifications'];
        tableNames.forEach(tableName => {
            loadTableData(tableName, []);
        });
        
        // Hide results section
        const resultsSection = document.getElementById('android-triage-results');
        if (resultsSection) {
            resultsSection.style.display = 'none';
        }
        
        // Reset progress
        updateAndroidProgress(0, 'Ready for new triage');
        
        showNotification('Android results cleared', 'success');
    }
}

// Test functions for CSV viewer (for debugging)
function testCSVViewer() {
    console.log('Testing CSV viewer...');
    showNotification('CSV viewer test function called', 'info');
}

function testRealCSVViewer() {
    console.log('Testing real CSV viewer...');
    showNotification('Real CSV viewer test function called', 'info');
}

// Debug function to test tab switching
function debugTabSwitching() {
    console.log('=== DEBUG TAB SWITCHING ===');
    
    // Check if result panes exist
    const panes = ['apps', 'sms', 'contacts', 'call-logs', 'files', 'notifications'];
    panes.forEach(pane => {
        const element = document.getElementById(`results-${pane}`);
        console.log(`Pane results-${pane}:`, element ? 'EXISTS' : 'NOT FOUND');
        if (element) {
            console.log(`  - Classes: ${element.className}`);
            console.log(`  - Display: ${window.getComputedStyle(element).display}`);
        }
    });
    
    // Check if buttons exist
    const buttons = document.querySelectorAll('.results-tab-btn');
    console.log(`Found ${buttons.length} tab buttons`);
    buttons.forEach((btn, index) => {
        console.log(`  Button ${index}: ${btn.textContent} - Classes: ${btn.className}`);
    });
    
    // Test switching to SMS tab
    console.log('Testing switch to SMS tab...');
    showResultsTab('sms');
}

// Debug platform layout
function debugPlatformLayout() {
    console.log('=== DEBUG PLATFORM LAYOUT ===');
    
    const platforms = ['android', 'ios'];
    platforms.forEach(platform => {
        const element = document.getElementById(`${platform}-content`);
        console.log(`Platform ${platform}:`, element ? 'EXISTS' : 'NOT FOUND');
        if (element) {
            const computedStyle = window.getComputedStyle(element);
            console.log(`  - Classes: ${element.className}`);
            console.log(`  - Display: ${computedStyle.display}`);
            console.log(`  - Position: ${computedStyle.position}`);
            console.log(`  - Width: ${computedStyle.width}`);
            console.log(`  - Height: ${computedStyle.height}`);
            console.log(`  - Max-width: ${computedStyle.maxWidth}`);
            console.log(`  - Max-height: ${computedStyle.maxHeight}`);
            console.log(`  - Overflow: ${computedStyle.overflow}`);
        }
    });
    
    // Check content area
    const contentArea = document.querySelector('.content-area');
    if (contentArea) {
        const computedStyle = window.getComputedStyle(contentArea);
        console.log('Content Area:');
        console.log(`  - Display: ${computedStyle.display}`);
        console.log(`  - Flex-direction: ${computedStyle.flexDirection}`);
        console.log(`  - Overflow: ${computedStyle.overflow}`);
        console.log(`  - Width: ${computedStyle.width}`);
        console.log(`  - Height: ${computedStyle.height}`);
    }
}

// ============================================================================
// TABLE MANAGEMENT SYSTEM - Pagination, Search, and Sorting
// ============================================================================

// Store for table data and state
const tableDataStore = {
    apps: { originalData: [], filteredData: [], currentPage: 1, pageSize: 50, sortColumn: null, sortDirection: 'asc' },
    sms: { originalData: [], filteredData: [], currentPage: 1, pageSize: 50, sortColumn: null, sortDirection: 'asc' },
    contacts: { originalData: [], filteredData: [], currentPage: 1, pageSize: 50, sortColumn: null, sortDirection: 'asc' },
    'call-logs': { originalData: [], filteredData: [], currentPage: 1, pageSize: 50, sortColumn: null, sortDirection: 'asc' },
    photos: { originalData: [], filteredData: [], currentPage: 1, pageSize: 50, sortColumn: null, sortDirection: 'asc' },
    videos: { originalData: [], filteredData: [], currentPage: 1, pageSize: 50, sortColumn: null, sortDirection: 'asc' },
    notifications: { originalData: [], filteredData: [], currentPage: 1, pageSize: 50, sortColumn: null, sortDirection: 'asc' }
};

document.addEventListener('DOMContentLoaded', function() {
    // Initialize UI components
    console.log('DOM fully loaded and parsed');
    
    // Initialize tab switching
    const platformButtons = document.querySelectorAll('.platform-btn');
    platformButtons.forEach(button => {
        button.addEventListener('click', () => {
            const platform = button.getAttribute('data-platform');
            switchPlatform(platform);
        });
    });
    
    // Initialize tab switching within platforms
    const tabButtons = document.querySelectorAll('.tab-btn');
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const tab = button.getAttribute('data-tab');
            // Extract just the tab name part (e.g., 'ios-backup' -> 'backup')
            const tabName = tab.includes('-') ? tab.split('-').slice(1).join('-') : tab;
            switchTab(currentPlatform, tabName);
        });
    });
    
    // Initialize case info validation
    const caseInputs = ['case-number', 'output-directory'];
    caseInputs.forEach(inputId => {
        const input = document.getElementById(inputId);
        if (input) {
            input.addEventListener('input', validateCaseInfo);
        }
    });
    
    // Initialize device monitoring
    startDeviceMonitoring();
    
    // Set initial state
    switchPlatform('android'); // Default to Android view
    validateCaseInfo();
    
    // Initialize table controls
    initializeTableControls();
    
    // Hide loading overlay
    hideLoading();
    
    console.log('Arsenic Mobile Triage Tool initialized');
});

// === ANDROID BACKUP PROCESSING FUNCTIONS ===

// Global processing state
let currentAnalysisDir = null;
let analysisProgressInterval = null;

// File selection functions for processing interface
async function selectAbFile() {
    try {
        const result = await electronAPI.openFile({
            title: 'Select Android Backup File',
            filters: [
                { name: 'Android Backup Files', extensions: ['ab'] },
                { name: 'All Files', extensions: ['*'] }
            ]
        });
        
        if (result && !result.canceled && result.filePaths.length > 0) {
            const selectedPath = result.filePaths[0];
            document.getElementById('ab-file-input').value = selectedPath;
            updateAnalysisButtonState();
            appendAnalysisConsole(`📦 Selected Android backup file: ${selectedPath.split('/').pop()}`);
            
            // Automatically analyze backup for encryption
            await analyzeBackupEncryption(selectedPath);
        }
    } catch (error) {
        console.error('Error selecting Android backup file:', error);
        showNotification('Failed to select Android backup file', 'error');
    }
}

// Function to analyze backup file for encryption
async function analyzeBackupEncryption(backupPath) {
    try {
        appendAnalysisConsole('🔍 Analyzing backup file for encryption...');
        
        const response = await apiClient.request('POST', '/api/android/backup/check-encryption', {
            backup_path: backupPath
        });
        
        if (response.success) {
            const filename = backupPath.split('/').pop();
            
            appendAnalysisConsole(`✅ Backup analysis complete for ${filename}`);
            appendAnalysisConsole(`   • Version: ${response.version}`);
            appendAnalysisConsole(`   • Compression: ${response.compression}`);
            appendAnalysisConsole(`   • File size: ${formatFileSize(response.file_size)}`);
            
            if (response.is_encrypted) {
                appendAnalysisConsole(`   • Status: 🔐 ENCRYPTED (password required)`);
                
                // Show professional modal for encrypted backup
                showEncryptedBackupModal({
                    filename: filename,
                    version: response.version,
                    compression: response.compression,
                    file_size: response.file_size,
                    backup_path: backupPath
                });
                
            } else {
                appendAnalysisConsole(`   • Status: 🔓 UNENCRYPTED (no password needed)`);
                appendAnalysisConsole('✅ This backup can be extracted without a password.');
                
                // Clear any stored password for unencrypted backups
                window.currentBackupPassword = null;
                
                showNotification('Unencrypted backup detected - ready for analysis', 'success');
            }
        } else {
            appendAnalysisConsole(`❌ Failed to analyze backup: ${response.error}`);
            showNotification(`Backup analysis failed: ${response.error}`, 'error');
        }
        
    } catch (error) {
        console.error('Error analyzing backup encryption:', error);
        appendAnalysisConsole(`❌ Error analyzing backup: ${error.message}`);
        showNotification('Failed to analyze backup encryption', 'error');
    }
}

// Helper function to format file sizes
function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

// === ENCRYPTED BACKUP MODAL FUNCTIONS ===

// Global variables for modal state
window.currentBackupInfo = null;
window.currentBackupPassword = null;

// Show encrypted backup modal
function showEncryptedBackupModal(backupInfo) {
    window.currentBackupInfo = backupInfo;
    
    // Populate modal with backup information
    document.getElementById('modal-backup-filename').textContent = backupInfo.filename;
    document.getElementById('modal-backup-version').textContent = backupInfo.version;
    document.getElementById('modal-backup-compression').textContent = backupInfo.compression;
    document.getElementById('modal-backup-size').textContent = formatFileSize(backupInfo.file_size);
    
    // Clear password field
    document.getElementById('modal-backup-password').value = '';
    
    // Show modal
    document.getElementById('encrypted-backup-modal').style.display = 'flex';
    
    // Focus password field
    setTimeout(() => {
        document.getElementById('modal-backup-password').focus();
    }, 100);
    
    // Add escape key listener
    document.addEventListener('keydown', handleModalKeydown);
}

// Close modal
function closePasswordModal() {
    document.getElementById('encrypted-backup-modal').style.display = 'none';
    document.removeEventListener('keydown', handleModalKeydown);
    window.currentBackupInfo = null;
}

// Handle keyboard events in modal
function handleModalKeydown(event) {
    if (event.key === 'Escape') {
        closePasswordModal();
    } else if (event.key === 'Enter') {
        confirmPasswordAndProceed();
    }
}

// Confirm password and proceed with analysis
function confirmPasswordAndProceed() {
    const password = document.getElementById('modal-backup-password').value.trim();
    
    if (!password) {
        // Show confirmation for empty password
        const confirmed = confirm(
            'No password entered.\n\n' +
            'Are you sure you want to proceed without a password?\n' +
            'This may cause extraction to fail if the backup is actually encrypted.'
        );
        
        if (!confirmed) {
            return;
        }
    }
    
    // Store password and close modal
    window.currentBackupPassword = password || null;
    closePasswordModal();
    
    // Show confirmation message
    if (password) {
        appendAnalysisConsole(`🔐 Password provided for encrypted backup`);
        showNotification('Password set - ready to proceed with analysis', 'success');
    } else {
        appendAnalysisConsole(`⚠️  Proceeding without password (may fail for encrypted backups)`);
        showNotification('Proceeding without password', 'warning');
    }
}

// Proceed without password (for advanced users)
function proceedWithoutPassword() {
    const confirmed = confirm(
        'Proceed without password?\n\n' +
        'This backup is encrypted and will likely fail extraction without the correct password.\n\n' +
        'Continue anyway?'
    );
    
    if (confirmed) {
        window.currentBackupPassword = null;
        closePasswordModal();
        appendAnalysisConsole(`⚠️  User chose to proceed without password for encrypted backup`);
        showNotification('Proceeding without password - extraction may fail', 'warning');
    }
}

async function selectApkDir() {
    try {
        const result = await electronAPI.openDirectory({
            title: 'Select APK Data Directory'
        });
        
        if (result && !result.canceled && result.filePaths.length > 0) {
            const selectedPath = result.filePaths[0];
            document.getElementById('apk-dir-input').value = selectedPath;
            updateAnalysisButtonState();
            appendAnalysisConsole(`📱 Selected APK data directory: ${selectedPath.split('/').pop()}`);
        }
    } catch (error) {
        console.error('Error selecting APK data directory:', error);
        showNotification('Failed to select APK data directory', 'error');
    }
}

async function selectAnalysisOutput() {
    try {
        const result = await electronAPI.openDirectory({
            title: 'Select Output Directory for Analysis'
        });
        
        if (result && !result.canceled && result.filePaths.length > 0) {
            const selectedPath = result.filePaths[0];
            document.getElementById('analysis-output-input').value = selectedPath;
            updateAnalysisButtonState();
            appendAnalysisConsole(`📁 Selected output directory: ${selectedPath.split('/').pop()}`);
        }
    } catch (error) {
        console.error('Error selecting analysis output directory:', error);
        showNotification('Failed to select output directory', 'error');
    }
}

function updateAnalysisButtonState() {
    const abFile = document.getElementById('ab-file-input').value;
    const apkDir = document.getElementById('apk-dir-input').value;
    const outputDir = document.getElementById('analysis-output-input').value;
    const extractAb = document.getElementById('extract-ab-option').checked;
    const parseApk = document.getElementById('parse-apk-option').checked;
    
    // Check if at least one operation is selected and required files are present
    const hasRequiredFiles = (extractAb && abFile) || (parseApk && apkDir);
    const hasOutputDir = outputDir.trim() !== '';
    const hasOperation = extractAb || parseApk;
    
    const startButton = document.getElementById('start-analysis');
    if (startButton) {
        startButton.disabled = !(hasRequiredFiles && hasOutputDir && hasOperation);
    }
}

function appendAnalysisConsole(message) {
    const console = document.getElementById('analysis-console');
    if (console) {
        const timestamp = new Date().toLocaleTimeString();
        console.textContent += `[${timestamp}] ${message}\n`;
        console.scrollTop = console.scrollHeight;
    }
}

function clearAnalysisConsole() {
    const console = document.getElementById('analysis-console');
    if (console) {
        console.textContent = '';
    }
}

async function startAndroidAnalysis() {
    try {
        // Get form values
        const abFile = document.getElementById('ab-file-input').value;
        const apkDir = document.getElementById('apk-dir-input').value;
        const outputDir = document.getElementById('analysis-output-input').value;
        const caseNumber = document.getElementById('case-number').value || 'Unknown';
        const backupPassword = window.currentBackupPassword || null;
        
        // Get processing options
        const extractAb = document.getElementById('extract-ab-option').checked;
        const parseApk = document.getElementById('parse-apk-option').checked;
        const generateReport = document.getElementById('generate-report-option').checked;
        const createTimeline = document.getElementById('create-timeline-option').checked;
        
        // Validate inputs
        if (!outputDir) {
            showNotification('Please select an output directory', 'error');
            return;
        }
        
        // Check if at least one valid input is provided
        const validAbFile = abFile && abFile.trim() !== '';
        const validApkDir = apkDir && apkDir.trim() !== '';
        
        if (!validAbFile && !validApkDir) {
            showNotification('Please provide at least one valid input: Android backup (.ab) file or APK data directory', 'error');
            return;
        }
        
        // Only validate specific requirements if the corresponding option is selected
        if (extractAb && !validAbFile) {
            showNotification('Please select an Android backup (.ab) file for extraction', 'error');
            return;
        }
        
        if (parseApk && !validApkDir) {
            showNotification('Please select an APK data directory for parsing', 'error');
            return;
        }
        
        // Auto-enable processing options based on available valid inputs if none are selected
        let autoEnabledExtraction = false;
        let autoEnabledParsing = false;
        
        if (!extractAb && !parseApk) {
            if (validAbFile) {
                document.getElementById('extract-ab-option').checked = true;
                autoEnabledExtraction = true;
                appendAnalysisConsole('Auto-enabled AB extraction based on provided AB file');
            }
            if (validApkDir) {
                document.getElementById('parse-apk-option').checked = true;
                autoEnabledParsing = true;
                appendAnalysisConsole('Auto-enabled APK parsing based on provided APK directory');
            }
        }
        
        // Re-read the checkbox values after potential auto-enabling
        const finalExtractAb = document.getElementById('extract-ab-option').checked;
        const finalParseApk = document.getElementById('parse-apk-option').checked;
        
        // Clear previous results and console
        clearAnalysisConsole();
        document.getElementById('analysis-results').style.display = 'none';
        
        // Show progress section and disable button
        const progressSection = document.getElementById('analysis-progress-section');
        const startButton = document.getElementById('start-analysis');
        
        if (progressSection) progressSection.style.display = 'block';
        if (startButton) {
            startButton.disabled = true;
            startButton.textContent = '🔬 Processing...';
        }
        
        appendAnalysisConsole('🚀 Starting Android backup analysis...');
        appendAnalysisConsole(`📋 Case Number: ${caseNumber}`);
        appendAnalysisConsole(`📁 Output Directory: ${outputDir}`);
        
        if (extractAb) appendAnalysisConsole(`📦 Will extract Android backup: ${abFile}`);
        if (parseApk) appendAnalysisConsole(`📱 Will parse APK data: ${apkDir}`);
        if (generateReport) appendAnalysisConsole(`📊 Will generate forensic report`);
        if (createTimeline) appendAnalysisConsole(`⏰ Will create forensic timeline`);
        
        // Start processing
        const processingData = {
            ab_file: abFile,
            apk_dir: apkDir,
            output_dir: outputDir,
            case_number: caseNumber,
            backup_password: backupPassword,
            extract_ab: finalExtractAb,
            parse_apk: finalParseApk,
            generate_report: generateReport,
            create_timeline: createTimeline
        };
        
        const response = await apiClient.request('POST', '/api/process_backup', processingData);
        
        if (response.success) {
            currentAnalysisDir = response.analysis_dir;
            appendAnalysisConsole(`✅ Processing started successfully`);
            appendAnalysisConsole(`📂 Analysis directory: ${currentAnalysisDir}`);
            
            // Start monitoring progress
            startProgressMonitoring();
        } else {
            throw new Error(response.error || 'Unknown error starting analysis');
        }
        
    } catch (error) {
        console.error('Error starting Android analysis:', error);
        appendAnalysisConsole(`❌ Error starting analysis: ${error.message}`);
        showNotification('Failed to start Android analysis: ' + error.message, 'error');
        
        // Re-enable button
        const startButton = document.getElementById('start-analysis');
        if (startButton) {
            startButton.disabled = false;
            startButton.textContent = '🔬 Start Analysis';
        }
        
        // Hide progress section
        const progressSection = document.getElementById('analysis-progress-section');
        if (progressSection) progressSection.style.display = 'none';
    }
}

function startProgressMonitoring() {
    if (analysisProgressInterval) {
        clearInterval(analysisProgressInterval);
    }
    
    let analysisStartTime = Date.now();
    
    // Update progress immediately
    updateProgressBar(5, 'Initializing analysis...');
    
    analysisProgressInterval = setInterval(async () => {
        try {
            if (currentAnalysisDir) {
                // Check processing status
                const encodedPath = encodeURIComponent(currentAnalysisDir);
                const statusResponse = await apiClient.request('GET', `/api/processing_status/${encodedPath}`);
                
                if (statusResponse.status === 'completed') {
                    // Processing completed
                    clearInterval(analysisProgressInterval);
                    analysisProgressInterval = null;
                    
                    const completionMsg = statusResponse.message || 'Analysis completed!';
                    updateProgressBar(100, completionMsg);
                    appendAnalysisConsole(`🎉 ${completionMsg}`);
                    
                    // Show results
                    displayAnalysisResults(statusResponse.results);
                    
                    // Re-enable button
                    const startButton = document.getElementById('start-analysis');
                    if (startButton) {
                        startButton.disabled = false;
                        startButton.textContent = '🔬 Start Analysis';
                    }
                    
                } else if (statusResponse.status === 'error') {
                    // Processing failed
                    clearInterval(analysisProgressInterval);
                    analysisProgressInterval = null;
                    
                    const errorMsg = statusResponse.error || statusResponse.message || 'Unknown error';
                    updateProgressBar(0, `Error: ${errorMsg}`);
                    appendAnalysisConsole(`❌ Analysis failed: ${errorMsg}`);
                    showNotification('Analysis failed: ' + errorMsg, 'error');
                    
                    // Re-enable button
                    const startButton = document.getElementById('start-analysis');
                    if (startButton) {
                        startButton.disabled = false;
                        startButton.textContent = '🔬 Start Analysis';
                    }
                    
                    // Hide progress section
                    const progressSection = document.getElementById('analysis-progress-section');
                    if (progressSection) progressSection.style.display = 'none';
                    
                } else if (statusResponse.status === 'processing') {
                    // Use actual progress data from backend
                    const progress = statusResponse.progress || 0;
                    const message = statusResponse.message || 'Processing...';
                    
                    updateProgressBar(progress, message);
                    
                } else {
                    // Unknown status - log it for debugging
                    console.log('Unknown analysis status:', statusResponse.status);
                }
            }
        } catch (error) {
            console.error('Error checking analysis progress:', error);
            
            // If it's a 404 (analysis directory not found), stop polling
            if (error.message && error.message.includes('404')) {
                console.log('Analysis directory not found, stopping progress polling');
                clearInterval(analysisProgressInterval);
                analysisProgressInterval = null;
                currentAnalysisDir = null;
                
                // Re-enable button
                const startButton = document.getElementById('start-analysis');
                if (startButton) {
                    startButton.disabled = false;
                    startButton.textContent = '🔬 Start Analysis';
                }
                
                // Hide progress section
                const progressSection = document.getElementById('analysis-progress-section');
                if (progressSection) progressSection.style.display = 'none';
            }
            // For other errors, continue checking - might be temporary network issue
        }
    }, 3000); // Check every 3 seconds
}

function updateProgressBar(percent, text) {
    const progressFill = document.getElementById('analysis-progress-fill');
    const progressText = document.getElementById('analysis-progress-text');
    const progressPercent = document.getElementById('analysis-progress-percent');
    
    if (progressFill) progressFill.style.width = `${percent}%`;
    if (progressText) progressText.textContent = text;
    if (progressPercent) progressPercent.textContent = `${Math.round(percent)}%`;
}

function displayAnalysisResults(results) {
    const resultsSection = document.getElementById('analysis-results');
    const resultsGrid = document.getElementById('analysis-results-grid');
    
    if (!resultsSection || !resultsGrid) return;
    
    // Clear previous results
    resultsGrid.innerHTML = '';
    
    // Create result cards
    if (results.ab_extraction) {
        const card = createResultCard('Android Backup Extraction', results.ab_extraction);
        resultsGrid.appendChild(card);
    }
    
    if (results.apk_parsing) {
        const card = createResultCard('APK Data Parsing', results.apk_parsing);
        resultsGrid.appendChild(card);
    }
    
    if (results.report_generation) {
        const card = createResultCard('Forensic Report Generation', results.report_generation);
        resultsGrid.appendChild(card);
    }
    
    if (results.timeline_creation) {
        const card = createResultCard('Forensic Timeline Creation', results.timeline_creation);
        resultsGrid.appendChild(card);
    }
    
    // Show results section
    resultsSection.style.display = 'block';
    
    // Hide progress section
    const progressSection = document.getElementById('analysis-progress-section');
    if (progressSection) progressSection.style.display = 'none';
}

function createResultCard(title, result) {
    const card = document.createElement('div');
    card.className = 'result-card';
    
    const isSuccess = result.success;
    const statusClass = isSuccess ? 'success' : 'error';
    const statusIcon = isSuccess ? '✅' : '❌';
    const statusText = isSuccess ? 'Success' : 'Failed';
    
    card.innerHTML = `
        <h5>${getResultIcon(title)} ${title}</h5>
        <div class="result-status ${statusClass}">
            ${statusIcon} ${statusText}
        </div>
        <div class="result-details">
            ${isSuccess ? 
                (result.path ? `📁 Saved to: ${result.path.split('/').pop()}` : 'Completed successfully') + 
                (result.events ? `<br>📊 ${result.events} timeline events created` : '') :
                `❌ Error: ${result.error || 'Unknown error'}`
            }
        </div>
    `;
    
    return card;
}

function getResultIcon(title) {
    const icons = {
        'Android Backup Extraction': '📦',
        'APK Data Parsing': '📱',
        'Forensic Report Generation': '📊',
        'Forensic Timeline Creation': '⏰'
    };
    return icons[title] || '📄';
}

function openResultsFolder() {
    if (currentAnalysisDir) {
        electronAPI.openPath(currentAnalysisDir);
        appendAnalysisConsole(`📁 Opened results folder: ${currentAnalysisDir}`);
    } else {
        showNotification('No results folder available', 'warning');
    }
}

function viewForensicReport() {
    if (currentAnalysisDir) {
        const reportPath = `${currentAnalysisDir}/Forensic_Report.html`;
        electronAPI.openPath(reportPath);
        appendAnalysisConsole(`📄 Opening forensic report: Forensic_Report.html`);
    } else {
        showNotification('No forensic report available', 'warning');
    }
}

// Add event listeners for processing options
document.addEventListener('DOMContentLoaded', function() {
    // Add listeners for processing option checkboxes
    const processingOptions = [
        'extract-ab-option',
        'parse-apk-option', 
        'generate-report-option',
        'create-timeline-option'
    ];
    
    processingOptions.forEach(id => {
        const checkbox = document.getElementById(id);
        if (checkbox) {
            checkbox.addEventListener('change', updateAnalysisButtonState);
        }
    });
});

// Expose functions globally for onclick handlers
window.switchPlatform = switchPlatform;
window.switchTab = switchTab;
window.selectOutputDirectory = selectOutputDirectory;
window.selectBackupFile = selectBackupFile;
window.refreshAndroidConnection = refreshAndroidConnection;
window.refreshiOSConnection = refreshiOSConnection;
window.refreshiOSInfo = refreshiOSInfo;
window.filterIOSApps = filterIOSApps;
window.startAndroidTriage = startAndroidTriage;
window.startAndroidBackup = startAndroidBackup;
window.startiOSBackup = startiOSBackup;
window.startParsing = startParsing;
window.showAndroidResults = showAndroidResults;
window.showResultsTab = showResultsTab;
window.exportResults = exportResults;
window.clearResults = clearResults;
window.testCSVViewer = testCSVViewer;
window.testRealCSVViewer = testRealCSVViewer;
window.selectIOSBackupFolder = selectIOSBackupFolder;
window.startIOSBackupParsing = startIOSBackupParsing;
window.toggleIOSTaxonomyOptions = toggleIOSTaxonomyOptions;
window.debugTabSwitching = debugTabSwitching;
window.debugPlatformLayout = debugPlatformLayout;

// Android Processing Functions
window.selectAbFile = selectAbFile;
window.selectApkDir = selectApkDir;
window.selectAnalysisOutput = selectAnalysisOutput;
window.startAndroidAnalysis = startAndroidAnalysis;
window.openResultsFolder = openResultsFolder;
window.viewForensicReport = viewForensicReport;

// Encrypted Backup Modal Functions
window.showEncryptedBackupModal = showEncryptedBackupModal;
window.closePasswordModal = closePasswordModal;
window.confirmPasswordAndProceed = confirmPasswordAndProceed;
window.proceedWithoutPassword = proceedWithoutPassword;

// Initialize table controls for all tables
function initializeTableControls() {
    const tableNames = ['apps', 'sms', 'contacts', 'call-logs', 'photos', 'videos', 'notifications'];
    
    tableNames.forEach(tableName => {
        // Search functionality
        const searchInput = document.getElementById(`${tableName}-search`);
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                handleTableSearch(tableName, e.target.value);
            });
        }
        
        // Page size selection
        const pageSizeSelect = document.getElementById(`${tableName}-page-size`);
        if (pageSizeSelect) {
            pageSizeSelect.addEventListener('change', (e) => {
                handlePageSizeChange(tableName, e.target.value);
            });
        }
        
        // Pagination buttons
        const prevBtn = document.getElementById(`${tableName}-prev-page`);
        const nextBtn = document.getElementById(`${tableName}-next-page`);
        if (prevBtn) {
            prevBtn.addEventListener('click', () => {
                handlePageChange(tableName, 'prev');
            });
        }
        if (nextBtn) {
            nextBtn.addEventListener('click', () => {
                handlePageChange(tableName, 'next');
            });
        }
        
        // Sortable headers
        const table = document.getElementById(`${tableName}-table`);
        if (table) {
            const sortableHeaders = table.querySelectorAll('th.sortable');
            sortableHeaders.forEach(header => {
                header.addEventListener('click', () => {
                    const column = header.getAttribute('data-column');
                    handleTableSort(tableName, column);
                });
            });
        }
    });
}

// Handle table search
function handleTableSearch(tableName, searchTerm) {
    const tableData = tableDataStore[tableName];
    
    if (searchTerm.trim() === '') {
        tableData.filteredData = [...tableData.originalData];
    } else {
        const term = searchTerm.toLowerCase();
        tableData.filteredData = tableData.originalData.filter(row => {
            return Object.values(row).some(value => 
                String(value).toLowerCase().includes(term)
            );
        });
    }
    
    tableData.currentPage = 1; // Reset to first page
    renderTable(tableName);
}

// Handle page size change
function handlePageSizeChange(tableName, newPageSize) {
    const tableData = tableDataStore[tableName];
    tableData.pageSize = newPageSize === 'all' ? tableData.filteredData.length : parseInt(newPageSize);
    tableData.currentPage = 1; // Reset to first page
    renderTable(tableName);
}

// Handle page navigation
function handlePageChange(tableName, direction) {
    const tableData = tableDataStore[tableName];
    const totalPages = Math.ceil(tableData.filteredData.length / tableData.pageSize);
    
    if (direction === 'prev' && tableData.currentPage > 1) {
        tableData.currentPage--;
    } else if (direction === 'next' && tableData.currentPage < totalPages) {
        tableData.currentPage++;
    }
    
    renderTable(tableName);
}

// Handle table sorting
function handleTableSort(tableName, column) {
    const tableData = tableDataStore[tableName];
    
    // Determine sort direction
    if (tableData.sortColumn === column) {
        tableData.sortDirection = tableData.sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
        tableData.sortColumn = column;
        tableData.sortDirection = 'asc';
    }
    
    // Sort the filtered data
    tableData.filteredData.sort((a, b) => {
        let aValue = a[column] || '';
        let bValue = b[column] || '';
        
        // Try to parse as numbers if possible
        const aNum = parseFloat(aValue);
        const bNum = parseFloat(bValue);
        if (!isNaN(aNum) && !isNaN(bNum)) {
            aValue = aNum;
            bValue = bNum;
        } else {
            aValue = String(aValue).toLowerCase();
            bValue = String(bValue).toLowerCase();
        }
        
        if (aValue < bValue) return tableData.sortDirection === 'asc' ? -1 : 1;
        if (aValue > bValue) return tableData.sortDirection === 'asc' ? 1 : -1;
        return 0;
    });
    
    // Update sort indicators
    updateSortIndicators(tableName);
    
    // Reset to first page and render
    tableData.currentPage = 1;
    renderTable(tableName);
}

// Update sort indicators in table headers
function updateSortIndicators(tableName) {
    const table = document.getElementById(`${tableName}-table`);
    if (!table) return;
    
    const headers = table.querySelectorAll('th.sortable');
    const tableData = tableDataStore[tableName];
    
    headers.forEach(header => {
        const column = header.getAttribute('data-column');
        header.classList.remove('sort-asc', 'sort-desc');
        
        if (column === tableData.sortColumn) {
            header.classList.add(tableData.sortDirection === 'asc' ? 'sort-asc' : 'sort-desc');
        }
    });
}

// Render table with current page data
function renderTable(tableName) {
    const tableData = tableDataStore[tableName];
    const tbody = document.getElementById(`${tableName}-tbody`);
    const statsDiv = document.getElementById(`${tableName}-stats`);
    
    if (!tbody || !statsDiv) return;
    
    // Calculate pagination
    const totalItems = tableData.filteredData.length;
    const totalPages = Math.ceil(totalItems / tableData.pageSize);
    const startIndex = (tableData.currentPage - 1) * tableData.pageSize;
    const endIndex = Math.min(startIndex + tableData.pageSize, totalItems);
    const pageData = tableData.filteredData.slice(startIndex, endIndex);
    
    // Clear existing content
    tbody.innerHTML = '';
    
    if (pageData.length === 0) {
        tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; padding: 20px;">No data available</td></tr>`;
    } else {
        // Render table rows
        pageData.forEach(row => {
            const tr = document.createElement('tr');
            
            // Get table headers to determine column order
            const table = document.getElementById(`${tableName}-table`);
            const headers = table.querySelectorAll('th[data-column]');
            
            headers.forEach(header => {
                const column = header.getAttribute('data-column');
                const td = document.createElement('td');
                td.textContent = row[column] || '';
                tr.appendChild(td);
            });
            
            tbody.appendChild(tr);
        });
    }
    
    // Update stats
    const searchTerm = document.getElementById(`${tableName}-search`)?.value || '';
    const filterText = searchTerm ? ` (filtered from ${tableData.originalData.length})` : '';
    statsDiv.textContent = `Showing ${startIndex + 1}-${endIndex} of ${totalItems} records${filterText}`;
    
    // Update pagination controls
    updatePaginationControls(tableName, totalPages);
}

// Update pagination controls
function updatePaginationControls(tableName, totalPages) {
    const tableData = tableDataStore[tableName];
    const prevBtn = document.getElementById(`${tableName}-prev-page`);
    const nextBtn = document.getElementById(`${tableName}-next-page`);
    const pageInfo = document.getElementById(`${tableName}-page-info`);
    
    if (prevBtn) {
        prevBtn.disabled = tableData.currentPage <= 1;
    }
    
    if (nextBtn) {
        nextBtn.disabled = tableData.currentPage >= totalPages;
    }
    
    if (pageInfo) {
        pageInfo.textContent = `Page ${tableData.currentPage} of ${totalPages}`;
    }
}

// Generate dynamic table headers based on CSV columns
function generateDynamicTableHeaders(tableName, columns) {
    const table = document.getElementById(`${tableName}-table`);
    if (!table) return;
    
    const thead = table.querySelector('thead tr');
    const tbody = table.querySelector('tbody');
    
    if (!thead || !tbody) return;
    
    // Clear existing headers
    thead.innerHTML = '';
    
    // Create new headers for each column
    columns.forEach(column => {
        const th = document.createElement('th');
        th.className = 'sortable';
        th.setAttribute('data-column', column);
        th.textContent = formatColumnName(column);
        thead.appendChild(th);
    });
    
    // Update the "no data" row colspan
    const noDataRow = tbody.querySelector('tr td[colspan]');
    if (noDataRow) {
        noDataRow.setAttribute('colspan', columns.length.toString());
    }
}

// Format column names for display (convert snake_case to Title Case)
function formatColumnName(columnName) {
    return columnName
        .replace(/_/g, ' ')
        .replace(/\b\w/g, l => l.toUpperCase());
}

// Convert Unix timestamp to human-readable date
function formatUnixTimestamp(value, fieldName) {
    if (!value || value === '' || value === 'NULL' || value === null) {
        return '';
    }
    
    // Check if this looks like a timestamp field
    const timestampFields = ['date', 'time', 'timestamp', 'created', 'modified', 'updated', 'sent', 'received'];
    const isTimestampField = timestampFields.some(field => 
        fieldName.toLowerCase().includes(field)
    );
    
    if (!isTimestampField) {
        return value;
    }
    
    try {
        let timestamp = parseInt(value);
        
        // Handle different timestamp formats
        if (timestamp < 0) {
            return value; // Negative timestamps, keep original
        }
        
        // If timestamp is in seconds (Unix epoch), convert to milliseconds
        // Unix timestamps are typically 10 digits for seconds, 13 digits for milliseconds
        if (timestamp.toString().length === 10) {
            timestamp = timestamp * 1000;
        }
        
        // If timestamp is too large (beyond year 2100), it might be microseconds
        if (timestamp > 4102444800000) { // Jan 1, 2100 in milliseconds
            timestamp = timestamp / 1000; // Convert microseconds to milliseconds
        }
        
        const date = new Date(timestamp);
        
        // Check if the date is valid
        if (isNaN(date.getTime())) {
            return value; // Invalid date, keep original
        }
        
        // Check if date is reasonable (not before 1970 or after 2100)
        if (date.getFullYear() < 1970 || date.getFullYear() > 2100) {
            return value; // Unreasonable date, keep original
        }
        
        return date.toLocaleString();
        
    } catch (e) {
        // If parsing fails, return original value
        return value;
    }
}

// Load data into table store
function loadTableData(tableName, data) {
    const tableData = tableDataStore[tableName];
    tableData.originalData = data || [];
    tableData.filteredData = [...tableData.originalData];
    tableData.currentPage = 1;
    
    // Clear search
    const searchInput = document.getElementById(`${tableName}-search`);
    if (searchInput) {
        searchInput.value = '';
    }
    
    // Reset sort
    tableData.sortColumn = null;
    tableData.sortDirection = 'asc';
    
    renderTable(tableName);
}

// Initialize table controls when document is ready
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(initializeTableControls, 100); // Small delay to ensure DOM is fully loaded
});

// iOS Parser Results Functions
function showIOSResultsTab(tabName) {
    console.log('showIOSResultsTab called with:', tabName);
    
    // Hide all iOS result panes
    const allPanes = document.querySelectorAll('#ios-parser-results .results-pane');
    allPanes.forEach(pane => {
        pane.classList.remove('active');
    });
    
    // Remove active class from all iOS result tab buttons (including CSV tabs)
    const allButtons = document.querySelectorAll('#ios-results-tab-nav .results-tab-btn');
    allButtons.forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Remove active class from CSV report tabs
    const csvButtons = document.querySelectorAll('#ios-csv-report-tabs .results-tab-btn');
    csvButtons.forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected pane (only CSV data pane is available now)
    const selectedPane = document.getElementById(`ios-results-${tabName}`);
    if (selectedPane) {
        selectedPane.classList.add('active');
    }
    
    // Add active class to clicked button
    const clickedButton = document.querySelector(`#ios-results-tab-nav .results-tab-btn[onclick="showIOSResultsTab('${tabName}')"]`);
    if (clickedButton) {
        clickedButton.classList.add('active');
    }
}

function showIOSParseResults(results) {
    console.log('showIOSParseResults called with:', results);
    console.log('Results type:', typeof results);
    console.log('Results keys (if object):', results && typeof results === 'object' ? Object.keys(results) : 'N/A');
    
    const tabNav = document.getElementById('ios-results-tab-nav');
    
    if (results) {
        // Check if this is just a status message (parsing started) vs actual results
        const isStatusMessage = results.status && Object.keys(results).length === 1;
        
        if (isStatusMessage) {
            console.log('DEBUG: Received status message, not attempting to load CSV reports yet');
            // Show the tab navigation but don't load CSV reports yet
            if (tabNav) {
                tabNav.style.display = 'flex';
            }
            return;
        }
        
        // Show the tab navigation
        if (tabNav) {
            tabNav.style.display = 'flex';
        }
        
        // Check if results contain case directory information
        let caseDirectory = '';
        if (typeof results === 'object' && results !== null) {
            // Try to extract case directory from results
            console.log('DEBUG: Full results object:', results);
            console.log('DEBUG: results.reports_path:', results.reports_path);
            
            caseDirectory = results.reports_path?.replace('/Reports', '') || '';
            console.log('DEBUG: Extracted case directory from reports_path:', caseDirectory);
            
            if (!caseDirectory) {
                // Try to get from current case info
                const caseNumber = document.getElementById('case-number')?.value;
                const outputDir = document.getElementById('output-directory')?.value;
                console.log('DEBUG: Fallback - case number:', caseNumber, 'output dir:', outputDir);
                if (caseNumber && outputDir) {
                    caseDirectory = `${outputDir}/Case_${caseNumber}`;
                }
            }
            console.log('DEBUG: Final case directory:', caseDirectory);
            
            // Debug: Check what's in the results object
            console.log('DEBUG: Checking for device info in results...');
            console.log('DEBUG: results.device_info:', results.device_info);
            console.log('DEBUG: All result keys:', Object.keys(results));
            console.log('DEBUG: Sample result values:', results);
            
            // Only update device info if we're not in analysis mode or don't have parsed device info
            if (!isAnalysisMode || !parsedDeviceInfo) {
                // Populate device info if available - check multiple possible keys
                let deviceInfo = null;
                if (results.device_info) {
                    deviceInfo = results.device_info;
                    console.log('DEBUG: Found device info under device_info key');
                } else if (results.deviceInfo) {
                    deviceInfo = results.deviceInfo;
                    console.log('DEBUG: Found device info under deviceInfo key');
                } else if (results['Device Info']) {
                    deviceInfo = results['Device Info'];
                    console.log('DEBUG: Found device info under Device Info key');
                } else {
                    // Look for device info in other keys
                    for (const [key, value] of Object.entries(results)) {
                        if (key.toLowerCase().includes('device') && typeof value === 'object' && value !== null) {
                            deviceInfo = value;
                            console.log(`DEBUG: Found device info under key: ${key}`);
                            break;
                        }
                    }
                }
                
                if (deviceInfo) {
                    console.log('DEBUG: Populating device info:', deviceInfo);
                    
                    // Set analysis mode and store parsed device info
                    isAnalysisMode = true;
                    parsedDeviceInfo = deviceInfo;
                    
                    populateIOSDeviceInfoTable(deviceInfo);
                } else {
                    console.log('DEBUG: No device info found in results');
                }
            } else {
                console.log('DEBUG: Analysis mode active - preserving existing complete device info from backup folder selection');
            }
            
            // Load and setup CSV reports
            loadIOSCSVReports(caseDirectory);
            
            // Show CSV data tab by default (first available tab)
            const csvDataPane = document.getElementById('ios-results-csv-data');
            if (csvDataPane) {
                csvDataPane.classList.add('active');
            }
        } else {
            console.log('Results are text-based, cannot process CSV reports');
            // Show CSV data pane anyway
            const csvDataPane = document.getElementById('ios-results-csv-data');
            if (csvDataPane) {
                csvDataPane.classList.add('active');
            }
        }
    } else {
        console.warn('showIOSParseResults: missing results data');
        console.log('results data:', results);
    }
}

function populateIOSParseDataTables(parseData) {
    console.log('populateIOSParseDataTables called with:', parseData);
    console.log('Parse data keys:', Object.keys(parseData || {}));
    
    // Populate Device Info table
    if (parseData.device_info) {
        console.log('Populating iOS device info table');
        populateIOSDeviceInfoTable(parseData.device_info);
    }
    
    // Populate SMS/Messages table
    if (parseData.sms_messages) {
        console.log('Populating iOS SMS table with', parseData.sms_messages.length, 'messages');
        loadIOSTableData('sms', parseData.sms_messages);
    }
    
    // Populate Call History table
    if (parseData.call_history) {
        console.log('Populating iOS call history table with', parseData.call_history.length, 'calls');
        loadIOSTableData('call-logs', parseData.call_history);
    }
    
    // Populate Contacts table
    if (parseData.contacts) {
        console.log('Populating iOS contacts table with', parseData.contacts.length, 'contacts');
        loadIOSTableData('contacts', parseData.contacts);
    }
    
    // Populate Notes table
    if (parseData.notes) {
        console.log('Populating iOS notes table with', parseData.notes.length, 'notes');
        loadIOSTableData('notes', parseData.notes);
    }
    
    // Populate Safari History table
    if (parseData.safari_history) {
        console.log('Populating iOS Safari history table with', parseData.safari_history.length, 'entries');
        loadIOSTableData('safari', parseData.safari_history);
    }
    
    // Populate Accounts table
    if (parseData.accounts) {
        console.log('Populating iOS accounts table with', parseData.accounts.length, 'accounts');
        loadIOSTableData('accounts', parseData.accounts);
    }
    
    // Populate App Permissions table
    if (parseData.permissions) {
        console.log('Populating iOS permissions table with', parseData.permissions.length, 'permissions');
        loadIOSTableData('permissions', parseData.permissions);
    }
    
    // Populate Data Usage table
    if (parseData.data_usage) {
        console.log('Populating iOS data usage table with', parseData.data_usage.length, 'entries');
        loadIOSTableData('data-usage', parseData.data_usage);
    }
    
    // Populate Interactions table
    if (parseData.interactions) {
        console.log('Populating iOS interactions table with', parseData.interactions.length, 'interactions');
        loadIOSTableData('interactions', parseData.interactions);
    }
    
    // Populate Photo Analysis table
    if (parseData.photo_analysis) {
        console.log('Populating iOS photo analysis table with', parseData.photo_analysis.length, 'photos');
        loadIOSTableData('photos', parseData.photo_analysis);
    }
}

// Global photo gallery instance
let iosPhotoGallery = null;

async function showPhotoGallery(dataType, caseDirectory, reportName) {
    console.log('=== PHOTO GALLERY DEBUG ===');
    console.log('Initializing photo gallery for:', reportName);
    console.log('DataType:', dataType);
    console.log('CaseDirectory:', caseDirectory);
    console.log('PhotoGallery class available:', typeof PhotoGallery);
    
    try {
        // Hide the CSV viewer and show photo gallery container
        const csvViewerContainer = document.getElementById('ios-csv-data-viewer');
        if (csvViewerContainer) {
            csvViewerContainer.style.display = 'none';
            console.log('Hidden CSV viewer container');
        }
        
        // Create or show photo gallery container
        let galleryContainer = document.getElementById('ios-photo-gallery-container');
        if (!galleryContainer) {
            // Create gallery container if it doesn't exist
            const csvPane = document.getElementById('ios-results-csv-data');
            if (csvPane) {
                // Ensure the CSV pane can expand
                csvPane.style.minHeight = '800px';
                csvPane.style.maxHeight = 'none';
                csvPane.style.height = 'auto';
                
                galleryContainer = document.createElement('div');
                galleryContainer.id = 'ios-photo-gallery-container';
                galleryContainer.style.minHeight = '800px';
                galleryContainer.style.maxHeight = 'none';
                galleryContainer.style.height = 'auto';
                csvPane.appendChild(galleryContainer);
                console.log('Created new photo gallery container with proper styling');
            } else {
                console.error('Could not find CSV pane to attach gallery');
            }
        }
        
        if (galleryContainer) {
            galleryContainer.style.display = 'block';
            // Ensure proper height for photo gallery
            galleryContainer.style.minHeight = '800px';
            galleryContainer.style.maxHeight = 'none';
            galleryContainer.style.height = 'auto';
            
            // Also ensure the parent results section can expand
            const resultsSection = document.getElementById('ios-parser-results');
            if (resultsSection) {
                resultsSection.style.minHeight = '800px';
                resultsSection.style.maxHeight = 'none';
                resultsSection.style.height = 'auto';
            }
            
            console.log('Gallery container is visible and styled');
            
            // Always create a fresh gallery instance for photo reports to avoid conflicts
            console.log('Creating new PhotoGallery instance...');
            iosPhotoGallery = new PhotoGallery('ios-photo-gallery-container');
            console.log('PhotoGallery instance created');
            
            // Load photos for this report
            console.log('Loading photos...');
            await iosPhotoGallery.loadPhotos(caseDirectory, dataType);
            
            console.log('Photo gallery loaded successfully');
        } else {
            console.error('Could not create photo gallery container');
        }
        
    } catch (error) {
        console.error('Error showing photo gallery:', error);
        // Fallback to CSV viewer
        if (iosCSVViewer) {
            const csvViewerContainer = document.getElementById('ios-csv-data-viewer');
            if (csvViewerContainer) {
                csvViewerContainer.style.display = 'block';
            }
            await iosCSVViewer.loadDataType(dataType, caseDirectory);
        }
    }
}

// Global CSV data viewer instance
let iosCSVViewer = null;

async function loadIOSCSVReports(caseDirectory) {
    console.log('DEBUG: loadIOSCSVReports called with caseDirectory:', caseDirectory);
    
    if (!caseDirectory) {
        console.warn('No case directory provided for loading CSV reports');
        console.log('iOS backup parsing completed, but no case directory found for CSV reports.');
        return;
    }
    
    try {
        console.log('DEBUG: Initializing CSV viewer...');
        
        // Initialize CSV viewer if not already created
        if (!iosCSVViewer) {
            iosCSVViewer = new CSVDataViewer('ios-csv-data-viewer');
            console.log('DEBUG: Created new CSV viewer instance');
        }
        
        // Load available reports
        console.log('DEBUG: Loading reports from:', caseDirectory);
        let reports;
        try {
            reports = await iosCSVViewer.loadReports(caseDirectory);
        } catch (reportsError) {
            console.warn('CSV reports not found, this may be normal if parsing is still in progress:', reportsError.message);
            // Don't throw error - this is expected when parsing is starting
            return;
        }
        console.log('DEBUG: Loaded reports:', reports);
        
        if (!reports || reports.length === 0) {
            console.warn('No CSV reports found');
            console.log(`iOS backup parsing completed, but no CSV reports were found in ${caseDirectory}.`);
            return;
        }
        
        // Show the results tab navigation
        const tabNav = document.getElementById('ios-results-tab-nav');
        if (tabNav) {
            tabNav.style.display = 'flex';
            console.log('Made tab navigation visible');
        }
        
        // Hide all result panes first
        document.querySelectorAll('.results-pane').forEach(pane => {
            pane.classList.remove('active');
        });
        
        // Show the CSV container
        const csvContainer = document.getElementById('ios-results-csv-data');
        if (csvContainer) {
            csvContainer.classList.add('active');
            console.log('Made CSV container active');
        }
        
        // Initialize CSV viewer
        const viewerContainer = document.getElementById('ios-csv-data-viewer');
        if (viewerContainer && typeof CSVDataViewer !== 'undefined') {
            console.log('Creating CSV viewer instance...');
            window.iosCSVViewer = new CSVDataViewer('ios-csv-data-viewer');
            
            // Load reports using the CSV viewer
            console.log('Loading reports via CSV viewer...');
            const reports = await window.iosCSVViewer.loadReports(caseDirectory);
            console.log('CSV viewer reports:', reports);
            
            if (reports && reports.length > 0) {
                // Create tabs for the reports
                createIOSCSVReportTabs(reports, caseDirectory);
                console.log('Created CSV report tabs');
                
                // Auto-load handled by clicking the first tab
                console.log('Creating tabs, first report will be auto-loaded by tab click');
                
                console.log('✅ CSV viewer test completed successfully!');
                
            } else {
                console.warn('No reports found via CSV viewer');
                alert('No CSV reports found in the CSV viewer');
            }
            
        } else {
            console.error('CSV viewer container not found or CSVDataViewer class not available');
            console.log('viewerContainer:', viewerContainer);
            console.log('CSVDataViewer type:', typeof CSVDataViewer);
            alert('CSV viewer not properly initialized');
        }
    } catch (error) {
        console.warn('Error in loadIOSCSVReports (may be normal during parsing):', error.message);
        // Don't show alert for expected errors during parsing startup
    }
}

// Create tabs for iOS CSV reports
async function createIOSCSVReportTabs(reports, caseDirectory) {
    console.log('Creating iOS CSV report tabs for reports:', reports);
    const csvTabsContainer = document.getElementById('ios-csv-report-tabs');
    if (!csvTabsContainer) {
        console.error('iOS CSV tabs container not found');
        return;
    }
    
    // Clear existing CSV tabs
    csvTabsContainer.innerHTML = '';
    
    // Create tab for each available report
    for (const report of reports) {
        const button = document.createElement('button');
        button.className = 'results-tab-btn';
        
        // Enhanced tab naming for Photo Reports with taxonomy
        let tabName = report.name;
        
        if (report.type && report.type.includes('Photo_Report')) {
            // Extract taxonomy category from report type or name
            let taxonomyCategory = null;
            
            // Debug logging to see what we're working with
            console.log(`Photo Report detected - report.type: "${report.type}", report.name: "${report.name}"`);
            
            // First, try to extract from the report.type (e.g., "Photo_Report_Firearms")
            const typeMatch = report.type.match(/Photo_Report_(.+)/);
            if (typeMatch) {
                taxonomyCategory = typeMatch[1];
                console.log(`Extracted category from type: "${taxonomyCategory}"`);
            }
            
            // If not found, try to extract from report.name (e.g., "Photo_Report_Firearms.csv")
            if (!taxonomyCategory && report.name) {
                // Try pattern: Photo_Report_CategoryName.csv
                const fileMatch = report.name.match(/Photo_Report_(.+?)\.csv/i);
                if (fileMatch) {
                    taxonomyCategory = fileMatch[1];
                    console.log(`Extracted category from file name: "${taxonomyCategory}"`);
                } else {
                    // Try pattern: Photo Report - Category
                    const dashMatch = report.name.match(/Photo.*Report.*-\s*(.+)/i);
                    if (dashMatch) {
                        taxonomyCategory = dashMatch[1].replace(/\.csv$/i, '');
                        console.log(`Extracted category from dash pattern: "${taxonomyCategory}"`);
                    }
                }
            }
            
            // Format the tab name with taxonomy category
            if (taxonomyCategory) {
                // Remove .csv extension if present
                taxonomyCategory = taxonomyCategory.replace(/\.csv$/i, '');
                
                // Capitalize first letter and clean up underscores
                const cleanCategory = taxonomyCategory.replace(/_/g, ' ')
                    .split(' ')
                    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
                    .join(' ');
                tabName = `Photo Report - ${cleanCategory}`;
                console.log(`Final tab name: "${tabName}"`);
            } else {
                tabName = 'Photo Report';
                console.log(`No category found, using generic: "${tabName}"`);
            }
        }
        
        // Don't show icons for ANY iOS tabs
        button.innerHTML = tabName;
        
        button.addEventListener('click', async () => {
            // Update active tab
            csvTabsContainer.querySelectorAll('.results-tab-btn').forEach(btn => 
                btn.classList.remove('active'));
            button.classList.add('active');
            
            // Check if this is a Photo Report - use gallery instead of CSV
            if (report.type && report.type.includes('Photo_Report')) {
                console.log('Photo Report detected - switching to gallery view for:', report.type);
                try {
                    await showPhotoGallery(report.type, caseDirectory, tabName);
                } catch (error) {
                    console.error('Error loading photo gallery:', error);
                }
            } else {
                // Hide photo gallery and show CSV viewer for non-photo reports
                const galleryContainer = document.getElementById('ios-photo-gallery-container');
                if (galleryContainer) {
                    galleryContainer.style.display = 'none';
                    console.log('Hidden photo gallery container for non-photo report');
                }
                
                const csvViewerContainer = document.getElementById('ios-csv-data-viewer');
                if (csvViewerContainer) {
                    csvViewerContainer.style.display = 'block';
                    console.log('Shown CSV viewer container');
                }
                
                // Load data in CSV viewer for non-photo reports
                if (iosCSVViewer) {
                    try {
                        console.log('Loading iOS CSV data for type:', report.type);
                        await iosCSVViewer.loadDataType(report.type, caseDirectory, 'ios-csv:readFile');
                    } catch (error) {
                        console.error('Error loading iOS CSV data:', error);
                    }
                } else {
                    console.error('iOS CSV viewer not available');
                }
            }
        });
        
        csvTabsContainer.appendChild(button);
    }
    
    // Activate first tab by default
    if (reports.length > 0) {
        const firstTab = csvTabsContainer.querySelector('.results-tab-btn');
        if (firstTab) {
            console.log('Activating first iOS CSV tab');
            firstTab.click();
        }
    }
}

// ============================================
// Screenshot Functionality
// ============================================

let screenshotCount = 0;
let currentScreenshotPath = '';

async function captureScreenshot() {
    console.log('=== Capturing Android Screenshot ===');
    
    const captureBtn = document.getElementById('capture-screenshot-btn');
    const spinner = captureBtn.querySelector('.loading-spinner');
    const btnText = captureBtn.querySelector('.btn-text');
    
    if (!deviceStatus.android) {
        showNotification('No Android device connected', 'error');
        return;
    }
    
    try {
        // Show loading state
        captureBtn.disabled = true;
        spinner.style.display = 'block';
        btnText.textContent = '📷 Capturing...';
        
        // Create timestamp for filename (unix timestamp)
        const unixTimestamp = Math.floor(Date.now() / 1000);
        
        // Get case number and output directory
        const caseNumber = document.getElementById('case-number').value.trim();
        const outputDir = document.getElementById('output-directory').value;
        const filename = `${caseNumber}_${unixTimestamp}.png`;
        
        if (!outputDir) {
            throw new Error('Please set an output directory first');
        }
        
        if (!caseNumber) {
            throw new Error('Please set a case number first');
        }

        // Call Flask API to capture screenshot
        const response = await apiClient.request('POST', '/api/capture_screenshot', {
            output_dir: outputDir,
            case_number: caseNumber,
            filename: filename
        });        if (response.success) {
            screenshotCount++;
            updateScreenshotCount();
            
            // Add thumbnail to gallery
            await addScreenshotThumbnail(response.screenshot_path, filename, unixTimestamp);
            
            showNotification('Screenshot captured successfully', 'success');
        } else {
            throw new Error(response.error || 'Failed to capture screenshot');
        }
        
    } catch (error) {
        console.error('Screenshot capture error:', error);
        showNotification(`Failed to capture screenshot: ${error.message}`, 'error');
    } finally {
        // Reset loading state
        captureBtn.disabled = false;
        spinner.style.display = 'none';
        btnText.textContent = '📷 Capture Screenshot';
    }
}

function updateScreenshotCount() {
    const countElement = document.getElementById('screenshot-count');
    if (countElement) {
        countElement.textContent = `${screenshotCount} screenshot${screenshotCount !== 1 ? 's' : ''} captured`;
    }
}

async function addScreenshotThumbnail(screenshotPath, filename, timestamp) {
    const gallery = document.getElementById('screenshot-gallery');
    const placeholder = gallery.querySelector('.gallery-placeholder');
    
    // Remove placeholder if it exists
    if (placeholder) {
        placeholder.remove();
    }
    
    // Create thumbnails container if it doesn't exist
    let thumbnailsContainer = gallery.querySelector('.screenshot-thumbnails');
    if (!thumbnailsContainer) {
        thumbnailsContainer = document.createElement('div');
        thumbnailsContainer.className = 'screenshot-thumbnails';
        gallery.appendChild(thumbnailsContainer);
    }
    
    // Create thumbnail element
    const thumbnail = document.createElement('div');
    thumbnail.className = 'screenshot-thumbnail';
    thumbnail.onclick = () => openScreenshotModal(screenshotPath, filename, timestamp);
    
    // Create image element
    const img = document.createElement('img');
    img.src = `file://${screenshotPath}`;
    img.alt = filename;
    img.onerror = () => {
        console.error('Failed to load screenshot:', screenshotPath);
        img.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTUwIiBoZWlnaHQ9IjEyMCIgdmlld0JveD0iMCAwIDE1MCAxMjAiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxyZWN0IHdpZHRoPSIxNTAiIGhlaWdodD0iMTIwIiBmaWxsPSIjZjVmNWY1Ii8+CjxwYXRoIGQ9Im03NSA0MCA1IDUgLTUgNSAtNSAtNSA1IC01eiIgZmlsbD0iIzk5OTk5OSIvPgo8dGV4dCB4PSI3NSIgeT0iNzAiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGZpbGw9IiM5OTk5OTkiIGZvbnQtZmFtaWx5PSJzYW5zLXNlcmlmIiBmb250LXNpemU9IjEyIj5JbWFnZSBOb3QgRm91bmQ8L3RleHQ+Cjwvc3ZnPgo=';
    };
    
    // Create info overlay
    const infoOverlay = document.createElement('div');
    infoOverlay.className = 'screenshot-info-overlay';
    
    const timestampDiv = document.createElement('div');
    timestampDiv.className = 'screenshot-timestamp';
    timestampDiv.textContent = formatTimestamp(timestamp);
    
    infoOverlay.appendChild(timestampDiv);
    
    thumbnail.appendChild(img);
    thumbnail.appendChild(infoOverlay);
    
    // Add to container (newest first)
    thumbnailsContainer.insertBefore(thumbnail, thumbnailsContainer.firstChild);
}

function formatTimestamp(unixTimestamp) {
    // Convert unix timestamp to readable format
    const date = new Date(unixTimestamp * 1000);
    return date.toLocaleString();
}

function openScreenshotModal(imagePath, filename, timestamp) {
    const modal = document.getElementById('screenshot-modal');
    const modalImg = document.getElementById('modal-screenshot');
    const filenameElement = document.getElementById('screenshot-filename');
    const timestampElement = document.getElementById('screenshot-timestamp');
    
    // Set current screenshot path for other actions
    currentScreenshotPath = imagePath;
    
    // Update modal content
    modalImg.src = `file://${imagePath}`;
    filenameElement.textContent = `Filename: ${filename}`;
    // Removed capture timestamp display
    
    // Show modal
    modal.classList.remove('hidden');
}

function closeScreenshotModal() {
    const modal = document.getElementById('screenshot-modal');
    modal.classList.add('hidden');
}

async function openScreenshotInFolder() {
    if (currentScreenshotPath && window.electronAPI) {
        try {
            await window.electronAPI.openPath(currentScreenshotPath);
        } catch (error) {
            console.error('Failed to open screenshot folder:', error);
            showNotification('Failed to open folder', 'error');
        }
    }
}

// Enable screenshot button when Android device is connected AND case info is valid
function updateScreenshotControls() {
    const captureBtn = document.getElementById('capture-screenshot-btn');
    if (captureBtn) {
        // Require: 1. Android device connected, 2. Case ID provided, 3. Output folder provided
        const caseNumber = document.getElementById('case-number')?.value?.trim() || '';
        const outputDir = document.getElementById('output-directory')?.value?.trim() || '';
        const hasValidCaseInfo = caseNumber && outputDir;
        const hasAndroidDevice = deviceStatus.android;
        
        console.log('Screenshot button check:', {
            hasValidCaseInfo,
            hasAndroidDevice,
            caseNumber: caseNumber || 'empty',
            outputDir: outputDir || 'empty'
        });
        
        captureBtn.disabled = !(hasValidCaseInfo && hasAndroidDevice);
        console.log('Screenshot button disabled:', captureBtn.disabled);
    }
}

// Add to device status update functions
const originalUpdateAndroidDeviceStatus = updateAndroidDeviceStatus;
if (typeof updateAndroidDeviceStatus === 'function') {
    updateAndroidDeviceStatus = function(status) {
        originalUpdateAndroidDeviceStatus(status);
        updateScreenshotControls();
    };
} else {
    function updateAndroidDeviceStatus(status) {
        updateScreenshotControls();
    }
}

// Close modal when clicking outside
document.addEventListener('click', (event) => {
    const modal = document.getElementById('screenshot-modal');
    if (event.target === modal) {
        closeScreenshotModal();
    }
});

// Close modal with Escape key
document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
        const modal = document.getElementById('screenshot-modal');
        if (modal && !modal.classList.contains('hidden')) {
            closeScreenshotModal();
        }
    }
});
