const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const path = require('path');
const fs = require('fs').promises;
const { spawn } = require('child_process');

// Helper function to get clean report names
function getCleanReportName(reportType) {
    const nameMap = {
        'SMS_Messages': 'SMS Messages',
        'Messages': 'Messages', 
        'Call_History': 'Call History',
        'Contacts': 'Contacts',
        'Safari_History': 'Safari History',
        'Notes': 'Notes',
        'Accounts': 'Accounts',
        'App_Permissions': 'App Permissions',
        'Data_Usage': 'Data Usage',
        'InteractionC': 'Interactions'
    };
    
    // Remove any remaining timestamp patterns and clean up
    const cleanType = reportType.replace(/_\d{14}$/, '').replace(/_\d+$/, '');
    return nameMap[cleanType] || cleanType.replace(/_/g, ' ');
}

class ArsenicApp {
    constructor() {
        this.mainWindow = null;
        this.flaskProcess = null;
        this.isDev = process.argv.includes('--dev');
    }

    async createWindow() {
        // Create the browser window
        this.mainWindow = new BrowserWindow({
            width: 1600,
            height: 1200,
            minWidth: 1200,
            minHeight: 900,
            webPreferences: {
                nodeIntegration: false,
                contextIsolation: true,
                enableRemoteModule: false,
                preload: path.join(__dirname, 'preload.js')
            },
            icon: this.getIconPath(),
            title: 'Arsenic Mobile Triage Tool - North Loop Consulting'
        });

        // Load the app
        await this.mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));

        // Open DevTools in development
        if (this.isDev) {
            this.mainWindow.webContents.openDevTools();
        }

        // Handle window closed
        this.mainWindow.on('closed', () => {
            this.mainWindow = null;
        });

        return this.mainWindow;
    }

    getIconPath() {
        const iconDir = path.join(__dirname, 'assets');
        
        // Try to find an appropriate icon
        if (process.platform === 'win32') {
            return path.join(iconDir, 'icon.ico');
        } else if (process.platform === 'darwin') {
            return path.join(iconDir, 'icon.icns');
        } else {
            return path.join(iconDir, 'icon.png');
        }
    }

    async startFlaskServer() {
        return new Promise((resolve, reject) => {
            try {
                // Determine if we're running in a packaged app or development
                const isPackaged = app.isPackaged;
                let backendExecutablePath;
                let workingDirectory;
                
                if (isPackaged) {
                    // In packaged app, look for the bundled fast backend (onedir version)
                    backendExecutablePath = path.join(process.resourcesPath, 'backend-fast', 'arsenic-backend-fast');
                    // Set working directory to the fast backend folder
                    workingDirectory = path.join(process.resourcesPath, 'backend-fast');
                } else {
                    // In development, use the Python script
                    const flaskAppPath = path.join(__dirname, '..', '..', 'flask_app.py');
                    const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
                    backendExecutablePath = pythonCmd;
                    workingDirectory = path.join(__dirname, '..', '..');
                }
                
                console.log('Starting Flask server...');
                console.log('Is packaged:', isPackaged);
                console.log('Backend path:', backendExecutablePath);
                console.log('Working directory:', workingDirectory);
                console.log('Backend exists:', require('fs').existsSync(backendExecutablePath));
                
                // Spawn Flask process
                try {
                    // Set environment to prevent Python bytecode caching
                    const env = {
                        ...process.env,
                        PYTHONDONTWRITEBYTECODE: '1',  // Prevent .pyc file creation and usage
                        PYTHONUNBUFFERED: '1'           // Force unbuffered output
                    };
                    
                    if (isPackaged) {
                        console.log('Spawning packaged backend...');
                        this.flaskProcess = spawn(backendExecutablePath, [], {
                            cwd: workingDirectory,
                            stdio: ['pipe', 'pipe', 'pipe'],
                            env: env
                        });
                    } else {
                        console.log('Spawning development backend...');
                        const flaskAppPath = path.join(__dirname, '..', '..', 'flask_app.py');
                        this.flaskProcess = spawn(backendExecutablePath, [flaskAppPath], {
                            cwd: workingDirectory,
                            stdio: ['pipe', 'pipe', 'pipe'],
                            env: env
                        });
                    }
                    console.log('Flask process spawned with PID:', this.flaskProcess.pid);
                } catch (spawnError) {
                    console.error('Error spawning Flask process:', spawnError);
                    reject(spawnError);
                    return;
                }

                // Handle Flask output
                this.flaskProcess.stdout.on('data', (data) => {
                    const output = data.toString();
                    console.log('Flask stdout:', output);
                    
                    // Check if Flask is ready
                    if (output.includes('Running on') || output.includes('* Serving Flask app')) {
                        console.log('Flask server is ready!');
                        resolve();
                    }
                });

                this.flaskProcess.stderr.on('data', (data) => {
                    const output = data.toString();
                    console.error('Flask stderr:', output);
                    
                    // Also check stderr for Flask ready messages
                    if (output.includes('Running on') || output.includes('* Serving Flask app')) {
                        console.log('Flask server is ready! (from stderr)');
                        resolve();
                    }
                });

                this.flaskProcess.on('error', (error) => {
                    console.error('Flask process error:', error);
                    reject(error);
                });

                this.flaskProcess.on('close', (code, signal) => {
                    console.log(`Flask process closed with code: ${code}, signal: ${signal}`);
                    if (code !== 0 && code !== null) {
                        console.error(`Flask process exited unexpectedly with code ${code}`);
                        reject(new Error(`Flask process exited with code ${code}`));
                    }
                });

                this.flaskProcess.on('exit', (code, signal) => {
                    console.log(`Flask process exited with code: ${code}, signal: ${signal}`);
                });

                // Give Flask a moment to start, then check if it's responding
                const checkFlaskReady = async (maxAttempts = 15, attemptDelay = 1000) => {
                    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
                        try {
                            console.log(`Checking Flask readiness (attempt ${attempt}/${maxAttempts})...`);
                            const response = await fetch('http://127.0.0.1:3131/api/devices/android/status');
                            if (response.ok) {
                                console.log('Flask server is ready and responding!');
                                resolve();
                                return;
                            }
                        } catch (error) {
                            // Flask not ready yet, continue checking
                        }
                        
                        // Check if process is still alive
                        if (!this.flaskProcess || this.flaskProcess.killed) {
                            console.error('Flask process died during startup');
                            reject(new Error('Flask process died during startup'));
                            return;
                        }
                        
                        await new Promise(resolve => setTimeout(resolve, attemptDelay));
                    }
                    
                    // If we get here, Flask didn't respond in time
                    console.error('Flask server failed to respond after 15 seconds');
                    reject(new Error('Flask server failed to respond after 15 seconds'));
                };

                // Start checking after a brief delay
                setTimeout(() => checkFlaskReady(), 2000);

            } catch (error) {
                console.error('Error starting Flask server:', error);
                reject(error);
            }
        });
    }

    stopFlaskServer() {
        if (this.flaskProcess) {
            console.log('Stopping Flask server...');
            this.flaskProcess.kill();
            this.flaskProcess = null;
        }
    }

    // Helper method to parse CSV lines correctly (handles quoted fields with commas)
    parseCSVLine(line) {
        const result = [];
        let current = '';
        let inQuotes = false;
        
        for (let i = 0; i < line.length; i++) {
            const char = line[i];
            
            if (char === '"') {
                if (inQuotes && line[i + 1] === '"') {
                    // Escaped quote
                    current += '"';
                    i++; // Skip next quote
                } else {
                    // Toggle quote state
                    inQuotes = !inQuotes;
                }
            } else if (char === ',' && !inQuotes) {
                // Field separator outside quotes
                result.push(current.trim());
                current = '';
            } else {
                current += char;
            }
        }
        
        // Add the last field
        result.push(current.trim());
        
        return result;
    }

    setupIpcHandlers() {
        // Handle file dialogs
        ipcMain.handle('dialog:openDirectory', async () => {
            const result = await dialog.showOpenDialog(this.mainWindow, {
                properties: ['openDirectory']
            });
            return result;
        });

        ipcMain.handle('dialog:openFile', async (event, options = {}) => {
            const result = await dialog.showOpenDialog(this.mainWindow, {
                properties: ['openFile'],
                filters: options.filters || []
            });
            return result;
        });

        // Handle external links
        ipcMain.handle('shell:openExternal', async (event, url) => {
            await shell.openExternal(url);
        });

        // Handle opening file paths in system file manager
        ipcMain.handle('shell:openPath', async (event, path) => {
            await shell.openPath(path);
        });

        // Handle app info
        ipcMain.handle('app:getVersion', () => {
            return app.getVersion();
        });

        ipcMain.handle('app:getPlatform', () => {
            return process.platform;
        });

        // Handle CSV file operations
        ipcMain.handle('csv:scanReports', async (event, caseDirectory) => {
            try {
                const allCsvFiles = [];
                const seenFiles = new Set();

                // Recursive function to find all CSV files
                async function findCsvFiles(directory) {
                    try {
                        const files = await fs.readdir(directory, { withFileTypes: true });
                        for (const file of files) {
                            const fullPath = path.join(directory, file.name);
                            if (file.isDirectory()) {
                                // Recursively search in subdirectories
                                await findCsvFiles(fullPath);
                            } else if (file.name.endsWith('.csv') && !seenFiles.has(file.name)) {
                                // Found a CSV file
                                seenFiles.add(file.name);

                                const baseName = path.basename(file.name, '.csv');
                                const cleanName = baseName.replace(/_\d{8,14}$/, '').replace(/_\d{6,8}$/, '');
                                const displayName = getCleanReportName(cleanName);

                                allCsvFiles.push({
                                    name: displayName,
                                    type: cleanName,
                                    filename: file.name,
                                    path: fullPath
                                });
                            }
                        }
                    } catch (error) {
                        // Ignore errors from directories that can't be read (e.g., permissions)
                        console.warn(`Could not read directory: ${directory}`, error);
                    }
                }

                // Start scanning from the root of the case directory
                await findCsvFiles(caseDirectory);

                console.log('Found CSV reports:', allCsvFiles);
                return allCsvFiles;

            } catch (error) {
                console.error('Error scanning for CSV reports:', error);
                return []; // Return empty array on error
            }
        });

        // CSV reading handler function
        const csvReadHandler = async (event, caseDirectory, dataType) => {
            try {
                const reportsPath = path.join(caseDirectory, 'Reports');
                const files = await fs.readdir(reportsPath);
                
                // Find CSV file matching the data type
                const csvFile = files.find(file => 
                    file.endsWith('.csv') && 
                    file.toLowerCase().includes(dataType.toLowerCase())
                );
                
                if (!csvFile) {
                    throw new Error(`No CSV file found for data type: ${dataType}`);
                }
                
                const filePath = path.join(reportsPath, csvFile);
                const csvContent = await fs.readFile(filePath, 'utf8');
                
                // Parse CSV content - skip header section and find actual CSV data
                const lines = csvContent.split('\n');
                
                // Find the line that contains the CSV headers
                let headerLineIndex = -1;
                for (let i = 0; i < lines.length; i++) {
                    const line = lines[i].trim();
                    
                    // Skip empty lines
                    if (!line) continue;
                    
                    // Skip obvious device metadata lines
                    if (line.startsWith('DEVICE') || line.startsWith('Device Info') || 
                        line.startsWith('Model') || line.startsWith('OS') || 
                        line.startsWith('Serial') || line.startsWith('UDID') ||
                        line.includes('REPORT') || line.includes('Analysis Date') ||
                        line.match(/^\w+\s*:\s*/)) { // Skip lines like "Model: iPhone"
                        continue;
                    }
                    
                    // Look for CSV headers - should contain delimiter and look like headers
                    if (line.includes('\t') || line.includes(',')) {
                        const delimiter = line.includes('\t') ? '\t' : ',';
                        const parts = line.split(delimiter).map(p => p.replace(/"/g, '').trim()).filter(p => p);
                        
                        // Must have at least 2 columns
                        if (parts.length >= 2) {
                            // For App Permissions, look for the specific expected headers
                            if (dataType.toLowerCase().includes('app_permissions') || dataType.toLowerCase().includes('permission')) {
                                const hasPermissionHeaders = parts.some(part => 
                                    part.toLowerCase().includes('device permission') ||
                                    part.toLowerCase().includes('application bundle') ||
                                    part.toLowerCase().includes('permission status')
                                );
                                if (hasPermissionHeaders) {
                                    headerLineIndex = i;
                                    break;
                                }
                            } else {
                                // For other data types, use the more general logic
                                const hasExpectedHeaders = parts.some(part => 
                                    part.toLowerCase().includes('date') ||
                                    part.toLowerCase().includes('time') ||
                                    part.toLowerCase().includes('name') ||
                                    part.toLowerCase().includes('type') ||
                                    part.toLowerCase().includes('status') ||
                                    part.toLowerCase().includes('title') ||
                                    part.toLowerCase().includes('application') ||
                                    part.toLowerCase().includes('duration') ||
                                    part.toLowerCase().includes('message') ||
                                    part.toLowerCase().includes('contact') ||
                                    // Add contacts-specific headers - exact matches and variations
                                    part.toLowerCase() === 'first' ||
                                    part.toLowerCase() === 'last' ||
                                    part.toLowerCase().includes('first') ||
                                    part.toLowerCase().includes('last') ||
                                    part.toLowerCase().includes('phone') ||
                                    part.toLowerCase().includes('email') ||
                                    part.toLowerCase().includes('organization') ||
                                    part.toLowerCase().includes('mobile') ||
                                    part.toLowerCase().includes('home') ||
                                    part.toLowerCase().includes('work') ||
                                    part.toLowerCase().includes('iphone') ||
                                    part.toLowerCase().includes('main')
                                );
                                
                                // Avoid lines that look like actual data rather than headers
                                const looksLikeData = parts.some(part => 
                                    part.toLowerCase().includes('ios') ||
                                    part.toLowerCase().includes('denied') ||
                                    part.toLowerCase().includes('allowed') ||
                                    part.toLowerCase().includes('com.apple') ||
                                    part.match(/^\d+$/) || // Pure numbers
                                    part.match(/^\d{4}-\d{2}-\d{2}/) || // Dates
                                    part.match(/kTCC/) // TCC service names
                                );
                                
                                // Special case for contacts: if we have contact-like headers, don't treat as data
                                const isContactsHeader = parts.some(part => 
                                    part.toLowerCase() === 'first' ||
                                    part.toLowerCase() === 'last' ||
                                    part.toLowerCase() === 'email'
                                );
                                
                                if (hasExpectedHeaders && (!looksLikeData || isContactsHeader)) {
                                    headerLineIndex = i;
                                    break;
                                }
                            }
                        }
                    }
                }
                
                if (headerLineIndex === -1) {
                    console.log('No CSV header found in file');
                    return { columns: [], data: [] };
                }
                
                // Parse header (use tabs as primary delimiter, fallback to commas)
                const headerLine = lines[headerLineIndex].trim();
                const delimiter = headerLine.includes('\t') ? '\t' : ',';
                const headers = headerLine.split(delimiter).map(h => h.replace(/"/g, '').trim()).filter(h => h);
                
                // Parse data rows
                const data = [];
                for (let i = headerLineIndex + 1; i < lines.length; i++) {
                    const line = lines[i].trim();
                    if (!line) continue; // Skip empty lines
                    
                    const values = line.split(delimiter).map(v => v.replace(/"/g, '').trim());
                    if (values.length >= headers.length) {
                        const row = {};
                        headers.forEach((header, index) => {
                            row[header] = values[index] || '';
                        });
                        data.push(row);
                    }
                }
                
                console.log(`CSV parsing results for ${csvFile}:`);
                console.log(`- Found header at line ${headerLineIndex}: ${headers.join(', ')}`);
                console.log(`- Parsed ${data.length} data rows`);
                console.log(`- Using delimiter: ${delimiter}`);
                
                return { columns: headers, data: data };
            } catch (error) {
                console.error('Error reading CSV file:', error);
                throw error;
            }
        };

        // Register handlers for both general and iOS-specific CSV reading
        ipcMain.handle('csv:readFile', csvReadHandler);
        ipcMain.handle('ios-csv:readFile', csvReadHandler);

        // Android CSV handlers
        ipcMain.handle('android-csv:scanReports', async (event, caseDirectory) => {
            try {
                console.log('Scanning for Android CSV reports in:', caseDirectory);
                
                // Android CSV files are in organized subdirectories
                const csvFiles = [];
                const csvPaths = [
                    { path: 'Data/Messages/sms_messages.csv', type: 'SMS Messages' },
                    { path: 'Data/Messages/mms_messages.csv', type: 'MMS Messages' },
                    { path: 'Data/Contacts/contacts_data.csv', type: 'Contacts' },
                    { path: 'Artifacts/Notifications/notifications.csv', type: 'Notifications' },
                    { path: 'Artifacts/External_Files/external_videos.csv', type: 'Videos' },
                    { path: 'Artifacts/External_Files/external_images.csv', type: 'Images' }
                ];
                
                for (const csvInfo of csvPaths) {
                    const fullPath = path.join(caseDirectory, csvInfo.path);
                    try {
                        const stats = await fs.stat(fullPath);
                        if (stats.isFile()) {
                            csvFiles.push({
                                type: csvInfo.type,
                                file: csvInfo.path,
                                name: csvInfo.type
                            });
                        }
                    } catch (error) {
                        // File doesn't exist, skip
                        console.log(`Android CSV file not found: ${fullPath}`);
                    }
                }
                
                console.log('Found Android CSV files:', csvFiles);
                return csvFiles;
            } catch (error) {
                console.error('Error scanning for Android CSV reports:', error);
                return [];
            }
        });

        ipcMain.handle('android-csv:readFile', async (event, caseDirectory, dataType) => {
            try {
                console.log(`=== CSV READER DEBUG ===`);
                console.log(`Reading Android CSV for data type: ${dataType}`);
                console.log(`Case directory: ${caseDirectory}`);
                
                // Map data types to file paths
                const fileMap = {
                    'SMS Messages': 'Data/Messages/sms_messages.csv',
                    'MMS Messages': 'Data/Messages/mms_messages.csv',
                    'Contacts': 'Data/Contacts/contacts_data.csv',
                    'Call Logs': 'Data/CallLogs/call_logs.csv',
                    'Notifications': 'Artifacts/Notifications/notifications.csv',
                    'Videos': 'Artifacts/External_Files/external_videos.csv',
                    'Images': 'Artifacts/External_Files/external_images.csv',
                    'Location': 'Data/Location/location_data.csv'
                };
                
                const csvPath = fileMap[dataType];
                if (!csvPath) {
                    throw new Error(`Unknown Android data type: ${dataType}`);
                }
                
                const filePath = path.join(caseDirectory, csvPath);
                console.log(`Full file path: ${filePath}`);
                
                // Check if file exists
                try {
                    await fs.access(filePath);
                    console.log(`✓ File exists: ${filePath}`);
                } catch (error) {
                    console.log(`✗ Android CSV file not found: ${filePath}`);
                    console.log(`Access error: ${error.message}`);
                    return { columns: [], data: [] };
                }
                
                const csvContent = await fs.readFile(filePath, 'utf8');
                const lines = csvContent.split('\n');
                
                if (lines.length < 1) {
                    return { columns: [], data: [] };
                }
                
                // Parse header line (Android CSVs have headers as first line)
                const headerLine = lines[0].trim();
                if (!headerLine) {
                    return { columns: [], data: [] };
                }
                
                // Parse CSV headers properly (handle quoted fields)
                const headers = this.parseCSVLine(headerLine);
                console.log(`Android CSV headers found: ${headers.join(', ')}`);
                
                // Parse data rows
                const data = [];
                for (let i = 1; i < lines.length; i++) {
                    const line = lines[i].trim();
                    if (!line) continue; // Skip empty lines
                    
                    // Parse CSV line properly (handle quoted fields with commas)
                    const values = this.parseCSVLine(line);
                    
                    // Only process rows that have some data
                    if (values.length > 0 && values.some(val => val.trim() !== '')) {
                        const row = {};
                        headers.forEach((header, index) => {
                            row[header] = values[index] || '';
                        });
                        data.push(row);
                    }
                }
                
                console.log(`Android CSV parsing results for ${csvPath}:`);
                console.log(`- Headers: ${headers.join(', ')}`);
                console.log(`- Parsed ${data.length} data rows`);
                console.log(`- First row sample:`, data[0]);
                
                return { columns: headers, data: data };
            } catch (error) {
                console.error('Error reading Android CSV file:', error);
                throw error;
            }
        });

        // File system operations
        ipcMain.handle('fs:getFileStats', async (event, filePath) => {
            try {
                const stats = await fs.stat(filePath);
                return {
                    size: stats.size,
                    mtime: stats.mtime,
                    ctime: stats.ctime,
                    isFile: stats.isFile(),
                    isDirectory: stats.isDirectory()
                };
            } catch (error) {
                console.error('Error getting file stats:', error);
                throw error;
            }
        });

        // ADB backup operations
        ipcMain.handle('adb:createBackup', async (event, options) => {
            return await this.createADBBackup(options);
        });

        ipcMain.handle('adb:getDevices', async (event) => {
            return await this.getADBDevices();
        });
    }

    async getADBPath() {
        // Get the correct ADB path for the current environment
        const isDev = this.isDev;
        
        if (isDev) {
            // Development environment - use project ADB
            return path.join(__dirname, '..', '..', 'src', 'utils', 'adb');
        } else {
            // Compiled app - use bundled ADB
            const resourcesPath = process.resourcesPath;
            return path.join(resourcesPath, 'backend-fast', 'src', 'utils', 'adb');
        }
    }

    async getADBDevices() {
        try {
            const adbPath = await this.getADBPath();
            
            return new Promise((resolve, reject) => {
                const adbProcess = spawn(adbPath, ['devices']);
                let output = '';
                let error = '';

                adbProcess.stdout.on('data', (data) => {
                    output += data.toString();
                });

                adbProcess.stderr.on('data', (data) => {
                    error += data.toString();
                });

                adbProcess.on('close', (code) => {
                    if (code === 0) {
                        // Parse devices output
                        const lines = output.split('\n');
                        const devices = [];
                        
                        for (let line of lines) {
                            line = line.trim();
                            if (line && line !== 'List of devices attached' && !line.startsWith('*')) {
                                const parts = line.split('\t');
                                if (parts.length >= 2) {
                                    devices.push({
                                        id: parts[0],
                                        status: parts[1]
                                    });
                                }
                            }
                        }
                        
                        resolve({ success: true, devices: devices });
                    } else {
                        reject(new Error(`ADB devices command failed: ${error}`));
                    }
                });

                adbProcess.on('error', (err) => {
                    reject(new Error(`Failed to execute ADB: ${err.message}`));
                });
            });
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    async createADBBackup(options) {
        try {
            const { outputDir, caseNumber, deviceId, includeApks = true, includeSystem = false, includeShared = true } = options;
            
            console.log('Starting ADB backup with options:', options);
            
            // Get ADB path
            const adbPath = await this.getADBPath();
            
            // Create timestamp
            const timestamp = new Date().toISOString().replace(/[:.]/g, '-').split('T')[0] + '_' + 
                             new Date().toISOString().replace(/[:.]/g, '-').split('T')[1].split('.')[0];
            
            // Create backup directory
            const backupDir = path.join(outputDir, `Android_Backup_${caseNumber}_${timestamp}`);
            await fs.mkdir(backupDir, { recursive: true });
            
            // Create backup filename
            const backupFile = path.join(backupDir, `android_backup_${timestamp}.ab`);
            
            // Build ADB command
            const adbArgs = ['backup'];
            
            if (deviceId) {
                adbArgs.unshift('-s', deviceId);
            }
            
            // Add backup options
            if (includeApks) adbArgs.push('-apk');
            if (includeSystem) adbArgs.push('-system');
            if (includeShared) adbArgs.push('-shared');
            
            // Add output file
            adbArgs.push('-f', backupFile);
            
            // Add all user apps
            adbArgs.push('-all');
            
            console.log('Executing ADB command:', adbPath, adbArgs);
            
            return new Promise((resolve, reject) => {
                const adbProcess = spawn(adbPath, adbArgs);
                let output = '';
                let error = '';

                // Send progress updates to renderer
                this.mainWindow.webContents.send('adb-backup-progress', {
                    type: 'status',
                    message: '📦 Starting ADB backup process...'
                });

                this.mainWindow.webContents.send('adb-backup-progress', {
                    type: 'status',
                    message: '⚠️ Please unlock your device and approve the backup operation'
                });

                adbProcess.stdout.on('data', (data) => {
                    output += data.toString();
                    console.log('ADB stdout:', data.toString());
                });

                adbProcess.stderr.on('data', (data) => {
                    error += data.toString();
                    console.log('ADB stderr:', data.toString());
                });

                // Monitor backup file creation and size
                let monitorInterval;
                const startMonitoring = () => {
                    monitorInterval = setInterval(async () => {
                        try {
                            const stats = await fs.stat(backupFile);
                            const sizeMB = (stats.size / (1024 * 1024)).toFixed(2);
                            
                            this.mainWindow.webContents.send('adb-backup-progress', {
                                type: 'progress',
                                message: `📊 Backup in progress... Size: ${sizeMB} MB`
                            });
                        } catch (err) {
                            // File doesn't exist yet, which is normal initially
                        }
                    }, 2000);
                };

                // Start monitoring after a brief delay
                setTimeout(startMonitoring, 3000);

                adbProcess.on('close', async (code) => {
                    if (monitorInterval) {
                        clearInterval(monitorInterval);
                    }

                    console.log(`ADB backup process completed with code: ${code}`);
                    
                    if (code === 0) {
                        // Check if backup file was created
                        try {
                            const stats = await fs.stat(backupFile);
                            const sizeMB = (stats.size / (1024 * 1024)).toFixed(2);
                            
                            this.mainWindow.webContents.send('adb-backup-progress', {
                                type: 'complete',
                                message: `✅ ADB backup completed successfully! Size: ${sizeMB} MB`
                            });
                            
                            resolve({
                                success: true,
                                backupFile: backupFile,
                                backupDir: backupDir,
                                size: stats.size,
                                sizeMB: sizeMB
                            });
                        } catch (err) {
                            this.mainWindow.webContents.send('adb-backup-progress', {
                                type: 'error',
                                message: '❌ Backup file not found - backup may have been cancelled'
                            });
                            
                            reject(new Error('Backup file not created - backup may have been cancelled by user'));
                        }
                    } else {
                        this.mainWindow.webContents.send('adb-backup-progress', {
                            type: 'error',
                            message: `❌ ADB backup failed with exit code: ${code}`
                        });
                        
                        reject(new Error(`ADB backup process failed with exit code ${code}: ${error}`));
                    }
                });

                adbProcess.on('error', (err) => {
                    if (monitorInterval) {
                        clearInterval(monitorInterval);
                    }
                    
                    this.mainWindow.webContents.send('adb-backup-progress', {
                        type: 'error',
                        message: `❌ Failed to execute ADB: ${err.message}`
                    });
                    
                    reject(new Error(`Failed to execute ADB backup: ${err.message}`));
                });
            });
        } catch (error) {
            console.error('ADB backup error:', error);
            return { success: false, error: error.message };
        }
    }

    async initialize() {
        try {
            // Wait for Electron to be ready
            await app.whenReady();
            
            console.log('Electron ready, starting Flask server...');
            
            // Start the Flask server
            await this.startFlaskServer();
            
            console.log('Creating window...');
            
            // Set up IPC handlers
            this.setupIpcHandlers();
            
            // Create the main window
            await this.createWindow();
            
            console.log('Application initialized successfully');
            
        } catch (error) {
            console.error('Error initializing application:', error);
            
            // Show error dialog
            if (this.mainWindow) {
                dialog.showErrorBox(
                    'Startup Error',
                    `Failed to start the application: ${error.message}`
                );
            }
            
            app.quit();
        }
    }

    setupAppEventHandlers() {
        // Quit when all windows are closed
        app.on('window-all-closed', () => {
            this.stopFlaskServer();
            
            // On macOS, keep app running when no windows are open
            if (process.platform !== 'darwin') {
                app.quit();
            }
        });

        app.on('activate', async () => {
            // Re-create window on macOS when dock icon is clicked
            if (BrowserWindow.getAllWindows().length === 0) {
                await this.createWindow();
            }
        });

        app.on('before-quit', () => {
            this.stopFlaskServer();
        });

        // Security: prevent new window creation
        app.on('web-contents-created', (event, contents) => {
            contents.on('new-window', (event, navigationUrl) => {
                event.preventDefault();
                shell.openExternal(navigationUrl);
            });
        });
    }
}

// Create and initialize the app
const arsenicApp = new ArsenicApp();

// Set up app event handlers
arsenicApp.setupAppEventHandlers();

// Initialize the application
arsenicApp.initialize().catch(console.error);
