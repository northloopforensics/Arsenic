// Device Status Component - Handles real-time device status monitoring

class DeviceStatus {
    constructor() {
        this.statusInterval = null;
        this.lastIOSStatus = null;
        this.lastAndroidStatus = null;
        
        this.initialize();
    }

    initialize() {
        // Start monitoring immediately
        this.startMonitoring();
        
        // Update status every 3 seconds
        this.statusInterval = setInterval(() => {
            this.updateStatus();
        }, 3000);
    }

    async updateStatus() {
        try {
            // Update iOS status
            await this.updateIOSStatus();
            
            // Update Android status
            await this.updateAndroidStatus();
            
        } catch (error) {
            console.error('Error updating device status:', error);
        }
    }

    async updateIOSStatus() {
        try {
            const status = await api.getIOSStatus();
            
            if (JSON.stringify(status) !== JSON.stringify(this.lastIOSStatus)) {
                this.lastIOSStatus = status;
                this.updateIOSIndicator(status);
            }
            
        } catch (error) {
            console.error('Error updating iOS status:', error);
            this.updateIOSIndicator({
                connected: false,
                message: '🟡 iOS: Check failed'
            });
        }
    }

    async updateAndroidStatus() {
        try {
            const status = await api.getAndroidStatus();
            
            if (JSON.stringify(status) !== JSON.stringify(this.lastAndroidStatus)) {
                this.lastAndroidStatus = status;
                this.updateAndroidIndicator(status);
            }
            
        } catch (error) {
            console.error('Error updating Android status:', error);
            this.updateAndroidIndicator({
                connected: false,
                message: '🟡 Android: Check failed'
            });
        }
    }

    updateIOSIndicator(status) {
        const indicator = document.getElementById('ios-status');
        if (indicator) {
            indicator.textContent = status.message || '🔵 iOS: Checking...';
            
            // Update indicator class based on connection status
            indicator.className = 'status-indicator';
            if (status.connected) {
                indicator.classList.add('connected');
            } else if (status.message && status.message.includes('🟡')) {
                indicator.classList.add('warning');
            } else {
                indicator.classList.add('disconnected');
            }
        }
        
        // Also update the device info section if we're on iOS platform
        if (window.arsenicApp && window.arsenicApp.currentPlatform === 'ios') {
            this.updateIOSDeviceSection(status);
        }
    }

    updateAndroidIndicator(status) {
        const indicator = document.getElementById('android-status');
        if (indicator) {
            indicator.textContent = status.message || '🔵 Android: Checking...';
            
            // Update indicator class based on connection status
            indicator.className = 'status-indicator';
            if (status.connected) {
                indicator.classList.add('connected');
            } else if (status.message && status.message.includes('🟡')) {
                indicator.classList.add('warning');
            } else {
                indicator.classList.add('disconnected');
            }
        }
        
        // Also update the device info section if we're on Android platform
        if (window.arsenicApp && window.arsenicApp.currentPlatform === 'android') {
            this.updateAndroidDeviceSection(status);
        }
    }

    updateIOSDeviceSection(status) {
        // If iOS device is connected, automatically refresh device info
        if (status.connected && window.arsenicApp) {
            // Throttle automatic refreshes
            if (!this.iosRefreshThrottle) {
                this.iosRefreshThrottle = true;
                setTimeout(() => {
                    this.iosRefreshThrottle = false;
                }, 10000); // Only auto-refresh every 10 seconds
                
                window.arsenicApp.refreshIOSDeviceInfo();
            }
        }
    }

    updateAndroidDeviceSection(status) {
        // If Android device is connected, automatically refresh device info
        if (status.connected && window.arsenicApp) {
            // Throttle automatic refreshes
            if (!this.androidRefreshThrottle) {
                this.androidRefreshThrottle = true;
                setTimeout(() => {
                    this.androidRefreshThrottle = false;
                }, 10000); // Only auto-refresh every 10 seconds
                
                window.arsenicApp.refreshAndroidDeviceInfo();
            }
        }
    }

    async startMonitoring() {
        // Initial status check
        await this.updateStatus();
    }

    stopMonitoring() {
        if (this.statusInterval) {
            clearInterval(this.statusInterval);
            this.statusInterval = null;
        }
    }

    // Manual refresh methods (called by UI buttons)
    async manualRefreshIOS() {
        try {
            const indicator = document.getElementById('ios-status');
            if (indicator) {
                indicator.textContent = '🔵 iOS: Refreshing...';
            }
            
            await this.updateIOSStatus();
            
            if (window.arsenicApp) {
                await window.arsenicApp.refreshIOSDeviceInfo();
            }
            
        } catch (error) {
            console.error('Error manually refreshing iOS:', error);
            showNotification('Failed to refresh iOS device status', 'error');
        }
    }

    async manualRefreshAndroid() {
        try {
            const indicator = document.getElementById('android-status');
            if (indicator) {
                indicator.textContent = '🔵 Android: Refreshing...';
            }
            
            await this.updateAndroidStatus();
            
            if (window.arsenicApp) {
                await window.arsenicApp.refreshAndroidDeviceInfo();
            }
            
        } catch (error) {
            console.error('Error manually refreshing Android:', error);
            showNotification('Failed to refresh Android device status', 'error');
        }
    }

    destroy() {
        this.stopMonitoring();
        console.log('Device status monitoring stopped');
    }
}

// Initialize device status monitoring when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.deviceStatus = new DeviceStatus();
});

// Handle cleanup
window.addEventListener('beforeunload', () => {
    if (window.deviceStatus) {
        window.deviceStatus.destroy();
    }
});
