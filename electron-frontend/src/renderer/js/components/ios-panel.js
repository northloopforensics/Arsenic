// iOS Panel Component - Handles iOS device operations

class IOSPanel {
    constructor() {
        this.currentOperation = null;
        this.operationInterval = null;
        this.apps = [];
        this.filteredApps = [];
        this.currentProgress = 0;  // Track current progress to prevent resets
        
        this.initializeEventListeners();
    }

    initializeEventListeners() {
        // iOS Backup operations
        const startBackupBtn = document.getElementById('start-ios-backup');
        if (startBackupBtn) {
            startBackupBtn.addEventListener('click', () => {
                this.startIOSBackup();
            });
        }

        // iOS Parse operations
        const browseBackupBtn = document.getElementById('browse-backup-folder');
        const startParseBtn = document.getElementById('start-ios-parse');
        const enableTaxonomyCheckbox = document.getElementById('enable-taxonomy');
        
        if (browseBackupBtn) {
            browseBackupBtn.addEventListener('click', () => {
                this.browseBackupFolder();
            });
        }
        
        if (startParseBtn) {
            startParseBtn.addEventListener('click', () => {
                this.startIOSParse();
            });
        }
        
        if (enableTaxonomyCheckbox) {
            enableTaxonomyCheckbox.addEventListener('change', (e) => {
                const taxonomySelect = document.getElementById('taxonomy-type');
                if (taxonomySelect) {
                    taxonomySelect.disabled = !e.target.checked;
                }
            });
        }

        // Apps search and sort
        const appsSearch = document.getElementById('ios-apps-search');
        const appsSort = document.getElementById('ios-apps-sort');
        const clearSearchBtn = document.getElementById('clear-ios-search');
        
        if (appsSearch) {
            appsSearch.addEventListener('input', (e) => {
                this.filterApps(e.target.value);
            });
        }
        
        if (appsSort) {
            appsSort.addEventListener('change', (e) => {
                this.sortApps(e.target.value);
            });
        }
        
        if (clearSearchBtn) {
            clearSearchBtn.addEventListener('click', () => {
                if (appsSearch) {
                    appsSearch.value = '';
                    this.filterApps('');
                }
            });
        }
    }

    async startIOSBackup() {
        try {
            if (!window.arsenicApp.caseInfo.output_directory) {
                showNotification('Please set an output directory first', 'warning');
                return;
            }

            const startBtn = document.getElementById('start-ios-backup');
            if (startBtn) {
                startBtn.disabled = true;
                startBtn.textContent = 'Starting Backup...';
            }

            // Reset progress tracking for new backup
            this.currentProgress = 0;
            this.updateBackupProgress(0, 'Initializing iOS backup...');
            this.updateBackupStatus('Starting iOS device backup...\n');

            const result = await api.startIOSBackup();
            
            if (result.success) {
                this.currentOperation = result.operation_id;
                showNotification('iOS backup started successfully', 'success');
                this.monitorIOSBackup();
            } else {
                throw new Error(result.error || 'Failed to start backup');
            }

        } catch (error) {
            console.error('Error starting iOS backup:', error);
            showNotification('Failed to start iOS backup: ' + error.message, 'error');
            this.resetBackupUI();
        }
    }

    monitorIOSBackup() {
        if (!this.currentOperation) return;

        this.operationInterval = setInterval(async () => {
            try {
                const status = await api.getIOSBackupStatus(this.currentOperation);
                
                if (status.success && status.updates) {
                    for (const update of status.updates) {
                        this.handleBackupUpdate(update);
                    }
                }
                
            } catch (error) {
                console.error('Error monitoring iOS backup:', error);
                this.stopMonitoring();
            }
        }, 1000);
    }

    handleBackupUpdate(update) {
        switch (update.type) {
            case 'status':
                this.updateBackupStatus(update.message + '\n');
                break;
                
            case 'progress':
                // Only update progress if we have a valid progress value
                if (update.progress !== null && update.progress !== undefined) {
                    this.updateBackupProgress(update.progress, update.message || '');
                }
                break;
                
            case 'complete':
                this.updateBackupProgress(100, 'Backup completed successfully');
                this.updateBackupStatus('iOS backup completed successfully!\n');
                showNotification('iOS backup completed', 'success');
                this.stopMonitoring();
                this.resetBackupUI();
                break;
                
            case 'error':
                this.updateBackupStatus(`Error: ${update.error}\n`);
                showNotification('iOS backup failed: ' + update.error, 'error');
                this.stopMonitoring();
                this.resetBackupUI();
                break;
        }
    }

    updateBackupProgress(percent, text = '') {
        // Only update if the new progress is higher than current (prevent resets)
        if (percent >= this.currentProgress) {
            this.currentProgress = percent;
            
            const progressFill = document.querySelector('#ios-progress-bar .progress-fill');
            const progressText = document.getElementById('ios-progress-text');
            
            if (progressFill) {
                progressFill.style.width = `${Math.min(100, Math.max(0, percent))}%`;
            }
            
            if (progressText && text) {
                progressText.textContent = text;
            }
        }
    }

    updateBackupStatus(message) {
        const statusLog = document.getElementById('ios-status-log');
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

    resetBackupUI() {
        const startBtn = document.getElementById('start-ios-backup');
        if (startBtn) {
            startBtn.disabled = false;
            startBtn.textContent = 'Start iOS Backup';
        }
    }

    async browseBackupFolder() {
        try {
            const result = await electronAPI.openDirectory();
            
            if (!result.canceled && result.filePaths.length > 0) {
                const backupPath = result.filePaths[0];
                const pathInput = document.getElementById('backup-folder-path');
                
                if (pathInput) {
                    pathInput.value = backupPath;
                }
                
                showNotification('Backup folder selected', 'success');
            }
        } catch (error) {
            console.error('Error browsing backup folder:', error);
            showNotification('Failed to select backup folder', 'error');
        }
    }

    async startIOSParse() {
        try {
            const backupPath = document.getElementById('backup-folder-path')?.value;
            const password = document.getElementById('backup-password')?.value || '';
            
            if (!backupPath) {
                showNotification('Please select a backup folder first', 'warning');
                return;
            }

            const startBtn = document.getElementById('start-ios-parse');
            const statusElement = document.getElementById('parse-status');
            
            if (startBtn) {
                startBtn.disabled = true;
                startBtn.textContent = 'Parsing...';
            }
            
            if (statusElement) {
                statusElement.textContent = 'Starting backup parse...';
            }

            const result = await api.parseIOSBackup({
                backup_path: backupPath,
                password: password
            });
            
            if (result.success) {
                this.currentOperation = result.operation_id;
                showNotification('iOS backup parsing started', 'success');
                this.monitorIOSParse();
            } else {
                throw new Error(result.error || 'Failed to start parsing');
            }

        } catch (error) {
            console.error('Error starting iOS parse:', error);
            showNotification('Failed to start iOS parsing: ' + error.message, 'error');
            this.resetParseUI();
        }
    }

    monitorIOSParse() {
        if (!this.currentOperation) return;

        this.operationInterval = setInterval(async () => {
            try {
                const status = await api.getIOSBackupStatus(this.currentOperation);
                
                if (status.success && status.updates) {
                    for (const update of status.updates) {
                        this.handleParseUpdate(update);
                    }
                }
                
            } catch (error) {
                console.error('Error monitoring iOS parse:', error);
                this.stopMonitoring();
            }
        }, 1000);
    }

    handleParseUpdate(update) {
        const statusElement = document.getElementById('parse-status');
        
        switch (update.type) {
            case 'status':
                if (statusElement) {
                    statusElement.textContent = update.message;
                }
                break;
                
            case 'complete':
                if (statusElement) {
                    statusElement.textContent = 'Parse completed successfully';
                }
                this.showParseResults(update.result);
                showNotification('iOS backup parsing completed', 'success');
                this.stopMonitoring();
                this.resetParseUI();
                break;
                
            case 'error':
                if (statusElement) {
                    statusElement.textContent = `Error: ${update.error}`;
                }
                showNotification('iOS parsing failed: ' + update.error, 'error');
                this.stopMonitoring();
                this.resetParseUI();
                break;
        }
    }

    showParseResults(results) {
        console.log('showParseResults called with:', results);
        
        // Hide the old simple results panel if it exists
        const oldResultsPanel = document.getElementById('parse-results');
        if (oldResultsPanel) {
            oldResultsPanel.style.display = 'none';
        }
        
        // Use the new comprehensive iOS results display system
        if (typeof showIOSParseResults === 'function') {
            showIOSParseResults(results);
        } else {
            console.error('showIOSParseResults function not found');
            
            // Fallback to old display method
            const resultsPanel = document.getElementById('parse-results');
            if (resultsPanel) {
                resultsPanel.style.display = 'block';
                
                const resultsContent = document.getElementById('results-content');
                if (resultsContent) {
                    resultsContent.textContent = JSON.stringify(results, null, 2);
                }
            }
        }
    }

    resetParseUI() {
        const startBtn = document.getElementById('start-ios-parse');
        if (startBtn) {
            startBtn.disabled = false;
            startBtn.textContent = 'Parse Backup';
        }
    }

    updateAppsDisplay(apps) {
        this.apps = apps || [];
        this.filteredApps = [...this.apps];
        this.renderApps();
    }

    filterApps(searchTerm) {
        const term = searchTerm.toLowerCase();
        this.filteredApps = this.apps.filter(app => 
            app.name.toLowerCase().includes(term) ||
            app.bundle_id.toLowerCase().includes(term)
        );
        this.renderApps();
    }

    sortApps(sortType) {
        switch (sortType) {
            case 'name':
                this.filteredApps.sort((a, b) => a.name.localeCompare(b.name));
                break;
            case 'name-reverse':
                this.filteredApps.sort((a, b) => b.name.localeCompare(a.name));
                break;
            case 'type':
                this.filteredApps.sort((a, b) => {
                    if (a.is_system !== b.is_system) {
                        return a.is_system ? 1 : -1;
                    }
                    return a.name.localeCompare(b.name);
                });
                break;
        }
        this.renderApps();
    }

    renderApps() {
        const appsListElement = document.getElementById('ios-apps-list');
        const appsCountElement = document.getElementById('ios-apps-count');
        
        if (appsCountElement) {
            appsCountElement.textContent = `${this.filteredApps.length} apps`;
        }
        
        if (appsListElement) {
            if (this.filteredApps.length === 0) {
                appsListElement.innerHTML = '<div class="no-apps">No apps match the current filter</div>';
            } else {
                const appsHTML = this.filteredApps.map(app => `
                    <div class="app-item">
                        <div>
                            <div class="app-name">${this.escapeHtml(app.name)}</div>
                            <div class="app-bundle">${this.escapeHtml(app.bundle_id)}</div>
                        </div>
                        <div class="app-version">${this.escapeHtml(app.version)}</div>
                    </div>
                `).join('');
                
                appsListElement.innerHTML = appsHTML;
            }
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize iOS panel when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.iosPanel = new IOSPanel();
});
