// Android Panel Component - Handles Android device operations

class AndroidPanel {
    constructor() {
        this.currentOperation = null;
        this.operationInterval = null;
        
        this.initializeEventListeners();
    }

    initializeEventListeners() {
        // Android Triage operations
        const startTriageBtn = document.getElementById('start-android-triage');
        if (startTriageBtn) {
            startTriageBtn.addEventListener('click', () => {
                this.startAndroidTriage();
            });
        }

        // Android Backup operations
        const startBackupBtn = document.getElementById('start-android-backup');
        if (startBackupBtn) {
            startBackupBtn.addEventListener('click', () => {
                this.startAndroidBackup();
            });
        }
    }

    async startAndroidTriage() {
        try {
            if (!window.arsenicApp.caseInfo.output_directory) {
                showNotification('Please set an output directory first', 'warning');
                return;
            }

            const startBtn = document.getElementById('start-android-triage');
            const profileSelect = document.getElementById('triage-profile');
            
            if (startBtn) {
                startBtn.disabled = true;
                startBtn.textContent = 'Starting Triage...';
            }

            const profile = profileSelect ? profileSelect.value : 'basic';

            this.updateTriageProgress(0, 'Initializing Android triage...');
            this.updateTriageStatus('Starting Android device triage...\n');

            const result = await api.startAndroidTriage({
                profile: profile
            });
            
            if (result.success) {
                this.currentOperation = result.operation_id;
                showNotification('Android triage started successfully', 'success');
                this.monitorAndroidTriage();
            } else {
                throw new Error(result.error || 'Failed to start triage');
            }

        } catch (error) {
            console.error('Error starting Android triage:', error);
            showNotification('Failed to start Android triage: ' + error.message, 'error');
            this.resetTriageUI();
        }
    }

    monitorAndroidTriage() {
        if (!this.currentOperation) return;

        this.operationInterval = setInterval(async () => {
            try {
                const status = await api.getAndroidTriageStatus(this.currentOperation);
                
                if (status.success && status.updates) {
                    for (const update of status.updates) {
                        this.handleTriageUpdate(update);
                    }
                }
                
            } catch (error) {
                console.error('Error monitoring Android triage:', error);
                this.stopMonitoring();
            }
        }, 1000);
    }

    handleTriageUpdate(update) {
        switch (update.type) {
            case 'status':
                this.updateTriageStatus(update.message + '\n');
                break;
                
            case 'progress':
                this.updateTriageProgress(update.value * 100, update.message || '');
                break;
                
            case 'complete':
                this.updateTriageProgress(100, 'Triage completed successfully');
                this.updateTriageStatus('Android triage completed successfully!\n');
                showNotification('Android triage completed', 'success');
                this.stopMonitoring();
                this.resetTriageUI();
                break;
                
            case 'error':
                this.updateTriageStatus(`Error: ${update.error}\n`);
                showNotification('Android triage failed: ' + update.error, 'error');
                this.stopMonitoring();
                this.resetTriageUI();
                break;
        }
    }

    updateTriageProgress(percent, text = '') {
        const progressFill = document.querySelector('#android-progress-bar .progress-fill');
        const progressText = document.getElementById('android-progress-text');
        
        if (progressFill) {
            progressFill.style.width = `${Math.min(100, Math.max(0, percent))}%`;
        }
        
        if (progressText && text) {
            progressText.textContent = text;
        }
    }

    updateTriageStatus(message) {
        const statusLog = document.getElementById('android-status-log');
        if (statusLog) {
            statusLog.textContent += message;
            statusLog.scrollTop = statusLog.scrollHeight;
        }
    }

    stopMonitoring() {
        if (this.operationInterval) {
            clearInterval(this.operationInterval);
            this.operationInterval = null;
        }
        this.currentOperation = null;
    }

    resetTriageUI() {
        const startBtn = document.getElementById('start-android-triage');
        if (startBtn) {
            startBtn.disabled = false;
            startBtn.textContent = 'Start Android Triage';
        }
    }

    async startAndroidBackup() {
        try {
            if (!window.arsenicApp.caseInfo.output_directory) {
                showNotification('Please set an output directory first', 'warning');
                return;
            }

            showNotification('Android backup collection feature coming soon...', 'info');
            
            // TODO: Implement Android backup collection
            // This would integrate with the existing DroidBackupFrame functionality
            
        } catch (error) {
            console.error('Error starting Android backup:', error);
            showNotification('Failed to start Android backup: ' + error.message, 'error');
        }
    }

    updateBackupStatus(message) {
        const statusLog = document.getElementById('android-backup-status');
        if (statusLog) {
            statusLog.textContent += message + '\n';
            statusLog.scrollTop = statusLog.scrollHeight;
        }
    }
}

// Initialize Android panel when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.androidPanel = new AndroidPanel();
});
