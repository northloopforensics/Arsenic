// Main application logic for Arsenic Mobile Triage Tool

class ArsenicApp {
    constructor() {
        this.currentPlatform = 'ios';
        this.operations = new Map(); // Track ongoing operations
        this.deviceStatusInterval = null;
        this.caseInfo = { case_number: '', output_directory: '' };
        
        this.initializeApp();
    }

    async initializeApp() {
        try {
            console.log('Initializing Arsenic Mobile Triage Tool...');
            
            // Initialize UI components
            this.initializeEventListeners();
            this.initializeTabs();
            this.initializePlatformSwitching();
            this.initializeCaseManagement();
            
            // Load initial data
            await this.loadCaseInfo();
            await this.loadSystemStatus();
            
            // Start device monitoring
            this.startDeviceStatusMonitoring();
            
            console.log('Application initialized successfully');
            
            // Show success notification
            showNotification('Application loaded successfully', 'success');
            
        } catch (error) {
            console.error('Error initializing application:', error);
            showNotification('Failed to initialize application: ' + error.message, 'error');
        }
    }

    initializeEventListeners() {
        // Platform switching
        document.querySelectorAll('.platform-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const platform = e.target.dataset.platform;
                this.switchPlatform(platform);
            });
        });

        // Tab switching
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const tabId = e.target.dataset.tab;
                this.switchTab(tabId);
            });
        });

        // Case management
        const caseNumberInput = document.getElementById('case-number');
        const outputDirectoryInput = document.getElementById('output-directory');
        const browseDirectoryBtn = document.getElementById('browse-directory');

        if (caseNumberInput) {
            caseNumberInput.addEventListener('input', debounce(() => {
                this.updateCaseInfo();
            }, 500));
        }

        if (browseDirectoryBtn) {
            browseDirectoryBtn.addEventListener('click', () => {
                this.browseOutputDirectory();
            });
        }

        // Device refresh buttons
        const refreshIOSBtn = document.getElementById('refresh-ios-info');
        const refreshAndroidBtn = document.getElementById('refresh-android-info');

        if (refreshIOSBtn) {
            refreshIOSBtn.addEventListener('click', () => {
                this.refreshIOSDeviceInfo();
            });
        }

        if (refreshAndroidBtn) {
            refreshAndroidBtn.addEventListener('click', () => {
                this.refreshAndroidDeviceInfo();
            });
        }
    }

    initializeTabs() {
        // Set up tab functionality for both platforms
        this.switchTab('ios-backup'); // Default iOS tab
        this.switchTab('android-triage'); // Default Android tab
    }

    initializePlatformSwitching() {
        // Show iOS platform by default
        this.switchPlatform('ios');
    }

    async initializeCaseManagement() {
        try {
            // Load case info from backend
            const caseInfo = await api.getCaseInfo();
            this.caseInfo = caseInfo;
            
            // Update UI
            const caseNumberInput = document.getElementById('case-number');
            const outputDirectoryInput = document.getElementById('output-directory');
            
            if (caseNumberInput && caseInfo.case_number) {
                caseNumberInput.value = caseInfo.case_number;
            }
            
            if (outputDirectoryInput && caseInfo.output_directory) {
                outputDirectoryInput.value = caseInfo.output_directory;
            }
            
        } catch (error) {
            console.error('Error loading case info:', error);
        }
    }

    switchPlatform(platform) {
        if (this.currentPlatform === platform) return;
        
        this.currentPlatform = platform;
        
        // Update platform buttons
        document.querySelectorAll('.platform-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.platform === platform);
        });
        
        // Update content visibility
        document.querySelectorAll('.platform-content').forEach(content => {
            content.classList.toggle('active', content.id === `${platform}-content`);
        });
        
        // Refresh device info for the selected platform
        if (platform === 'ios') {
            this.refreshIOSDeviceInfo();
        } else if (platform === 'android') {
            this.refreshAndroidDeviceInfo();
        }
        
        console.log(`Switched to ${platform} platform`);
    }

    switchTab(tabId) {
        const platform = tabId.startsWith('ios') ? 'ios' : 'android';
        const container = document.querySelector(`#${platform}-content`);
        
        if (!container) return;
        
        // Update tab buttons
        container.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tabId);
        });
        
        // Update tab content
        container.querySelectorAll('.tab-pane').forEach(pane => {
            pane.classList.toggle('active', pane.id === tabId);
        });
        
        console.log(`Switched to ${tabId} tab`);
    }

    async loadCaseInfo() {
        try {
            const caseInfo = await api.getCaseInfo();
            this.caseInfo = caseInfo;
            console.log('Case info loaded:', caseInfo);
        } catch (error) {
            console.error('Error loading case info:', error);
        }
    }

    async loadSystemStatus() {
        try {
            const status = await api.getSystemStatus();
            console.log('System status:', status);
        } catch (error) {
            console.error('Error loading system status:', error);
        }
    }

    async updateCaseInfo() {
        try {
            const caseNumber = document.getElementById('case-number')?.value || '';
            const outputDirectory = document.getElementById('output-directory')?.value || '';
            
            const updatedInfo = await api.updateCaseInfo({
                case_number: caseNumber,
                output_directory: outputDirectory
            });
            
            this.caseInfo = updatedInfo.case_info;
            console.log('Case info updated:', this.caseInfo);
            
        } catch (error) {
            console.error('Error updating case info:', error);
            showNotification('Failed to update case information', 'error');
        }
    }

    async browseOutputDirectory() {
        try {
            const result = await electronAPI.openDirectory();
            
            if (!result.canceled && result.filePaths.length > 0) {
                const directory = result.filePaths[0];
                const outputDirectoryInput = document.getElementById('output-directory');
                
                if (outputDirectoryInput) {
                    outputDirectoryInput.value = directory;
                    await this.updateCaseInfo();
                    showNotification('Output directory updated', 'success');
                }
            }
        } catch (error) {
            console.error('Error browsing directory:', error);
            showNotification('Failed to select directory', 'error');
        }
    }

    startDeviceStatusMonitoring() {
        // Check device status every 3 seconds
        this.deviceStatusInterval = setInterval(() => {
            this.updateDeviceStatus();
        }, 3000);
        
        // Initial check
        this.updateDeviceStatus();
    }

    async updateDeviceStatus() {
        try {
            // Check iOS status
            const iosStatus = await api.getIOSStatus();
            this.updateIOSStatusIndicator(iosStatus);
            
            // Check Android status  
            const androidStatus = await api.getAndroidStatus();
            this.updateAndroidStatusIndicator(androidStatus);
            
        } catch (error) {
            console.error('Error updating device status:', error);
        }
    }

    updateIOSStatusIndicator(status) {
        const indicator = document.getElementById('ios-status');
        if (indicator) {
            indicator.textContent = status.message || '🔵 iOS: Checking...';
        }
    }

    updateAndroidStatusIndicator(status) {
        const indicator = document.getElementById('android-status');
        if (indicator) {
            indicator.textContent = status.message || '🔵 Android: Checking...';
        }
    }

    async refreshIOSDeviceInfo() {
        try {
            const deviceInfoElement = document.getElementById('ios-device-info');
            if (deviceInfoElement) {
                deviceInfoElement.textContent = 'Refreshing device information...';
            }
            
            const deviceInfo = await api.getIOSInfo();
            
            if (deviceInfo.error) {
                if (deviceInfoElement) {
                    deviceInfoElement.textContent = `Error: ${deviceInfo.error}`;
                }
            } else {
                if (deviceInfoElement) {
                    deviceInfoElement.textContent = this.formatDeviceInfo(deviceInfo);
                }
                
                // Also refresh apps list
                this.refreshIOSApps();
            }
            
        } catch (error) {
            console.error('Error refreshing iOS device info:', error);
            const deviceInfoElement = document.getElementById('ios-device-info');
            if (deviceInfoElement) {
                deviceInfoElement.textContent = `Error: ${error.message}`;
            }
        }
    }

    async refreshAndroidDeviceInfo() {
        try {
            const deviceInfoElement = document.getElementById('android-device-info');
            if (deviceInfoElement) {
                deviceInfoElement.textContent = 'Refreshing device information...';
            }
            
            const deviceInfo = await api.getAndroidInfo();
            
            if (deviceInfo.error) {
                if (deviceInfoElement) {
                    deviceInfoElement.textContent = `Error: ${deviceInfo.error}`;
                }
            } else {
                if (deviceInfoElement) {
                    deviceInfoElement.textContent = this.formatDeviceInfo(deviceInfo);
                }
            }
            
        } catch (error) {
            console.error('Error refreshing Android device info:', error);
            const deviceInfoElement = document.getElementById('android-device-info');
            if (deviceInfoElement) {
                deviceInfoElement.textContent = `Error: ${error.message}`;
            }
        }
    }

    async refreshIOSApps() {
        try {
            const appsListElement = document.getElementById('ios-apps-list');
            const appsCountElement = document.getElementById('ios-apps-count');
            
            if (appsListElement) {
                appsListElement.textContent = 'Loading apps...';
            }
            
            const appsData = await api.getIOSApps();
            
            if (appsData.success) {
                const apps = appsData.apps || [];
                
                if (appsCountElement) {
                    appsCountElement.textContent = `${apps.length} apps`;
                }
                
                if (appsListElement) {
                    if (apps.length === 0) {
                        appsListElement.textContent = 'No apps found';
                    } else {
                        const appsList = apps.map(app => 
                            `${app.name}\n  Bundle ID: ${app.bundle_id}\n  Version: ${app.version}\n  Type: ${app.is_system ? 'System' : 'User'}\n`
                        ).join('\n');
                        appsListElement.textContent = appsList;
                    }
                }
            } else {
                if (appsListElement) {
                    appsListElement.textContent = `Error: ${appsData.error}`;
                }
            }
            
        } catch (error) {
            console.error('Error refreshing iOS apps:', error);
            const appsListElement = document.getElementById('ios-apps-list');
            if (appsListElement) {
                appsListElement.textContent = `Error: ${error.message}`;
            }
        }
    }

    formatDeviceInfo(deviceInfo) {
        if (!deviceInfo || Object.keys(deviceInfo).length === 0) {
            return 'No device information available';
        }
        
        const formatted = Object.entries(deviceInfo)
            .filter(([key, value]) => value != null && value !== '')
            .map(([key, value]) => `${key}: ${value}`)
            .join('\n');
        
        return formatted || 'No device information available';
    }

    stopDeviceStatusMonitoring() {
        if (this.deviceStatusInterval) {
            clearInterval(this.deviceStatusInterval);
            this.deviceStatusInterval = null;
        }
    }

    destroy() {
        this.stopDeviceStatusMonitoring();
        console.log('Application destroyed');
    }
}

// Utility function for debouncing
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.arsenicApp = new ArsenicApp();
});

// Handle app cleanup
window.addEventListener('beforeunload', () => {
    if (window.arsenicApp) {
        window.arsenicApp.destroy();
    }
});
