/**
 * CSV Data Viewer Module
 * Handles paginated, sortable, searchable tables from CSV data
 */

class CSVDataViewer {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.options = {
            perPage: options.perPage || 1000,
            searchDelay: options.searchDelay || 500,
            ...options
        };
        
        this.currentData = [];
        this.currentPage = 1;
        this.totalPages = 1;
        this.totalRecords = 0;
        this.sortColumn = '';
        this.sortDirection = 'asc';
        this.searchTerm = '';
        this.searchTimeout = null;
        this.columns = [];
        this.dataType = '';
        this.caseDirectory = '';
        
        this.init();
    }
    
    init() {
        if (!this.container) {
            console.error('CSV Data Viewer container not found');
            return;
        }
        
        this.createHTML();
        this.attachEventListeners();
    }
    
    createHTML() {
        this.container.innerHTML = `
            <div class="csv-data-viewer">
                <div class="csv-controls">
                    <div class="csv-search-box">
                        <input type="text" id="csv-search" placeholder="Search across all columns..." class="form-control">
                        <span class="search-icon">🔍</span>
                    </div>
                    <div class="csv-info">
                        <span id="csv-record-count">0 records</span>
                        <select id="csv-per-page" class="form-control">
                            <option value="50">50 per page</option>
                            <option value="100">100 per page</option>
                            <option value="250">250 per page</option>
                            <option value="500">500 per page</option>
                            <option value="1000" selected>1000 per page</option>
                            <option value="2500">2500 per page</option>
                            <option value="5000">5000 per page</option>
                            <option value="10000">10000 per page</option>
                            <option value="25000">25000 per page</option>
                            <option value="50000">50000 per page</option>
                            <option value="100000">Show All (100k+ records)</option>
                        </select>
                    </div>
                </div>
                
                <div class="csv-table-container">
                    <div id="csv-loading" class="csv-loading" style="display: none;">
                        <div class="spinner"></div>
                        <span>Loading data...</span>
                    </div>
                    
                    <table id="csv-data-table" class="csv-table">
                        <thead id="csv-table-head"></thead>
                        <tbody id="csv-table-body"></tbody>
                    </table>
                </div>
                
                <div class="csv-pagination">
                    <div class="pagination-info">
                        <span id="csv-page-info">Page 1 of 1</span>
                    </div>
                    <div class="pagination-controls">
                        <button id="csv-first-page" class="btn btn-sm">First</button>
                        <button id="csv-prev-page" class="btn btn-sm">Previous</button>
                        <span class="page-numbers" id="csv-page-numbers"></span>
                        <button id="csv-next-page" class="btn btn-sm">Next</button>
                        <button id="csv-last-page" class="btn btn-sm">Last</button>
                    </div>
                </div>
            </div>
        `;
    }
    
    attachEventListeners() {
        // Search functionality
        const searchInput = this.container.querySelector('#csv-search');
        searchInput.addEventListener('input', (e) => {
            clearTimeout(this.searchTimeout);
            this.searchTimeout = setTimeout(() => {
                this.searchTerm = e.target.value;
                this.currentPage = 1;
                this.loadData();
            }, this.options.searchDelay);
        });
        
        // Per page selector
        const perPageSelect = this.container.querySelector('#csv-per-page');
        perPageSelect.addEventListener('change', (e) => {
            this.options.perPage = parseInt(e.target.value);
            this.currentPage = 1;
            this.loadData();
        });
        
        // Pagination controls
        this.container.querySelector('#csv-first-page').addEventListener('click', () => {
            this.currentPage = 1;
            this.loadData();
        });
        
        this.container.querySelector('#csv-prev-page').addEventListener('click', () => {
            if (this.currentPage > 1) {
                this.currentPage--;
                this.loadData();
            }
        });
        
        this.container.querySelector('#csv-next-page').addEventListener('click', () => {
            if (this.currentPage < this.totalPages) {
                this.currentPage++;
                this.loadData();
            }
        });
        
        this.container.querySelector('#csv-last-page').addEventListener('click', () => {
            this.currentPage = this.totalPages;
            this.loadData();
        });
    }
    
    async loadReports(caseDirectory) {
        this.caseDirectory = caseDirectory;
        
        try {
            console.log('Loading reports directly from directory:', caseDirectory);
            
            // Use Electron's fs to scan for CSV files
            const reports = await window.electronAPI.scanForCSVReports(caseDirectory);
            
            if (reports && reports.length > 0) {
                this.reports = reports;
                console.log('Found reports:', reports);
                return reports;
            } else {
                throw new Error('No CSV reports found in directory');
            }
        } catch (error) {
            console.error('Error loading reports:', error);
            throw error;
        }
    }
    
    async loadDataType(dataType, caseDirectory, ipcMethod = 'csv:readFile') {
        this.dataType = dataType;
        this.caseDirectory = caseDirectory;
        this.ipcMethod = ipcMethod;
        this.currentPage = 1;
        this.searchTerm = '';
        this.sortColumn = '';
        this.sortDirection = 'asc';
        
        // Clear search box
        const searchInput = this.container.querySelector('#csv-search');
        if (searchInput) searchInput.value = '';
        
        await this.loadData();
    }
    
    async loadData() {
        if (!this.dataType || !this.caseDirectory) {
            console.warn('Data type or case directory not set');
            return;
        }
        
        this.showLoading(true);
        
        try {
            console.log('Loading CSV data directly for:', this.dataType, 'using IPC method:', this.ipcMethod);
            
            // Read CSV file using the appropriate IPC method
            let csvData;
            if (this.ipcMethod === 'android-csv:readFile') {
                // Use Android-specific CSV reading method
                csvData = await window.electronAPI.readAndroidCSVFile(this.caseDirectory, this.dataType);
            } else {
                // Default iOS method
                csvData = await window.electronAPI.readCSVFile(this.caseDirectory, this.dataType);
            }
            
            console.log('Received CSV data:', {
                columns: csvData?.columns,
                dataLength: csvData?.data?.length,
                firstRow: csvData?.data?.[0],
                dataType: this.dataType
            });
            
            // Add special debug logging for Contacts data
            if (this.dataType === 'Contacts') {
                console.log('CONTACTS DEBUG - Full CSV data:', csvData);
                console.log('CONTACTS DEBUG - Columns:', csvData?.columns);
                console.log('CONTACTS DEBUG - First 3 rows:', csvData?.data?.slice(0, 3));
            }
            
            if (csvData && csvData.data) {
                // Apply search and sorting locally
                let filteredData = csvData.data;
                
                // Apply search filter
                if (this.searchTerm) {
                    filteredData = filteredData.filter(row => 
                        Object.values(row).some(value => 
                            String(value).toLowerCase().includes(this.searchTerm.toLowerCase())
                        )
                    );
                }
                
                // Apply sorting
                if (this.sortColumn) {
                    filteredData.sort((a, b) => {
                        const aVal = String(a[this.sortColumn] || '');
                        const bVal = String(b[this.sortColumn] || '');
                        const comparison = aVal.localeCompare(bVal);
                        return this.sortDirection === 'asc' ? comparison : -comparison;
                    });
                }
                
                // Apply pagination
                this.totalRecords = filteredData.length;
                this.totalPages = Math.ceil(this.totalRecords / this.options.perPage);
                
                const startIndex = (this.currentPage - 1) * this.options.perPage;
                const endIndex = startIndex + this.options.perPage;
                
                this.currentData = filteredData.slice(startIndex, endIndex);
                this.columns = csvData.columns;
                
                this.renderTable();
                this.updatePagination();
                this.updateRecordCount();
            } else {
                throw new Error('No data found in CSV file');
            }
        } catch (error) {
            console.error('Error loading CSV data:', error);
            this.showError(error.message);
        } finally {
            this.showLoading(false);
        }
    }
    
    renderTable() {
        console.log('renderTable called for dataType:', this.dataType);
        console.log('Columns:', this.columns);
        console.log('Current data length:', this.currentData.length);
        
        const thead = this.container.querySelector('#csv-table-head');
        const tbody = this.container.querySelector('#csv-table-body');
        
        // Clear existing content
        thead.innerHTML = '';
        tbody.innerHTML = '';
        
        if (this.columns.length === 0 || this.currentData.length === 0) {
            console.log('No data to render - columns:', this.columns.length, 'data:', this.currentData.length);
            tbody.innerHTML = '<tr><td colspan="100%" class="text-center">No data available</td></tr>';
            return;
        }
        
        // Filter columns for Messages data type
        const hiddenMessagesColumns = [
            'ChatId', 'Chat ID', 
            'From Me', 
            'Is Sent', 
            'Is Delivered', 
            'Is Read',
            'Attachment Types',
            'Attachment Names', 
            'Attachment Count',
            'Is Group Chat',
            'Group Name'
        ];
        const isMessagesData = this.dataType && this.dataType.toLowerCase().includes('messages');
        const visibleColumns = isMessagesData ? 
            this.columns.filter(column => {
                const columnName = typeof column === 'string' ? column : column.name;
                return !hiddenMessagesColumns.includes(columnName);
            }) : this.columns;
        
        // Create header row
        const headerRow = document.createElement('tr');
        visibleColumns.forEach(column => {
            const th = document.createElement('th');
            const columnName = typeof column === 'string' ? column : column.name;
            th.textContent = columnName;
            th.className = 'sortable';
            th.dataset.column = columnName;
            
            // Add special styling for Sent and Received columns in Messages
            if (isMessagesData && (columnName === 'Sent' || columnName === 'Received')) {
                th.classList.add('messages-content-column');
            }
            
            // Add sort indicator
            if (this.sortColumn === columnName) {
                th.className += this.sortDirection === 'asc' ? ' sort-asc' : ' sort-desc';
            }
            
            // Add click handler for sorting
            th.addEventListener('click', () => {
                this.handleSort(columnName);
            });
            
            headerRow.appendChild(th);
        });
        thead.appendChild(headerRow);
        
        // Create data rows
        this.currentData.forEach(record => {
            const row = document.createElement('tr');
            visibleColumns.forEach(column => {
                const td = document.createElement('td');
                const columnName = typeof column === 'string' ? column : column.name;
                const value = record[columnName] || '';
                
                // Add special styling for Sent and Received columns in Messages
                if (isMessagesData && (columnName === 'Sent' || columnName === 'Received')) {
                    td.classList.add('messages-content-column');
                }
                
                // Special handling for Photo Reports - show thumbnails
                if (this.dataType && this.dataType.includes('Photo_Report') && columnName === 'Filename') {
                    this.renderPhotoThumbnail(td, value, record);
                }
                // Format certain types of data
                else if (columnName.toLowerCase().includes('date') || columnName.toLowerCase().includes('time')) {
                    td.textContent = this.formatDate(value);
                } else if (columnName.toLowerCase().includes('phone') || columnName.toLowerCase().includes('number')) {
                    td.textContent = this.formatPhoneNumber(value);
                } else {
                    td.textContent = this.truncateText(value, 500);
                }
                
                td.title = value; // Full text on hover
                row.appendChild(td);
            });
            tbody.appendChild(row);
        });
    }
    
    handleSort(columnName) {
        if (this.sortColumn === columnName) {
            // Toggle direction
            this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
        } else {
            // New column
            this.sortColumn = columnName;
            this.sortDirection = 'asc';
        }
        
        this.loadData();
    }
    
    updatePagination() {
        const pageInfo = this.container.querySelector('#csv-page-info');
        const pageNumbers = this.container.querySelector('#csv-page-numbers');
        const firstBtn = this.container.querySelector('#csv-first-page');
        const prevBtn = this.container.querySelector('#csv-prev-page');
        const nextBtn = this.container.querySelector('#csv-next-page');
        const lastBtn = this.container.querySelector('#csv-last-page');
        
        pageInfo.textContent = `Page ${this.currentPage} of ${this.totalPages}`;
        
        // Update button states
        firstBtn.disabled = this.currentPage <= 1;
        prevBtn.disabled = this.currentPage <= 1;
        nextBtn.disabled = this.currentPage >= this.totalPages;
        lastBtn.disabled = this.currentPage >= this.totalPages;
        
        // Generate page numbers
        this.generatePageNumbers(pageNumbers);
    }
    
    generatePageNumbers(container) {
        container.innerHTML = '';
        
        const maxVisible = 5;
        let start = Math.max(1, this.currentPage - Math.floor(maxVisible / 2));
        let end = Math.min(this.totalPages, start + maxVisible - 1);
        
        if (end - start + 1 < maxVisible) {
            start = Math.max(1, end - maxVisible + 1);
        }
        
        for (let i = start; i <= end; i++) {
            const pageBtn = document.createElement('button');
            pageBtn.textContent = i;
            pageBtn.className = i === this.currentPage ? 'btn btn-sm active' : 'btn btn-sm';
            pageBtn.addEventListener('click', () => {
                this.currentPage = i;
                this.loadData();
            });
            container.appendChild(pageBtn);
        }
    }
    
    updateRecordCount() {
        const recordCount = this.container.querySelector('#csv-record-count');
        const start = (this.currentPage - 1) * this.options.perPage + 1;
        const end = Math.min(this.currentPage * this.options.perPage, this.totalRecords);
        
        if (this.totalRecords === 0) {
            recordCount.textContent = 'No records found';
        } else {
            recordCount.textContent = `Showing ${start}-${end} of ${this.totalRecords.toLocaleString()} records`;
        }
    }
    
    showLoading(show) {
        const loading = this.container.querySelector('#csv-loading');
        const table = this.container.querySelector('#csv-data-table');
        
        if (show) {
            loading.style.display = 'flex';
            table.style.opacity = '0.5';
        } else {
            loading.style.display = 'none';
            table.style.opacity = '1';
        }
    }
    
    showError(message) {
        const tbody = this.container.querySelector('#csv-table-body');
        tbody.innerHTML = `<tr><td colspan="100%" class="text-center text-danger">Error: ${message}</td></tr>`;
    }
    
    // Utility functions
    renderPhotoThumbnail(td, filename, record) {
        if (!filename) {
            td.textContent = 'No filename';
            return;
        }
        
        // Create a container for the thumbnail and filename
        const container = document.createElement('div');
        container.className = 'photo-thumbnail-container';
        container.style.cssText = 'display: flex; align-items: center; gap: 10px;';
        
        // Try to find the extracted photo
        const photoPath = this.findExtractedPhoto(filename, record);
        
        if (photoPath) {
            // Determine if this is a video or image file
            const extension = filename.toLowerCase().split('.').pop();
            const isVideo = ['mov', 'mp4', 'avi', 'm4v'].includes(extension);
            
            if (isVideo) {
                // Create video thumbnail
                const video = document.createElement('video');
                video.src = photoPath;
                video.style.cssText = 'width: 60px; height: 60px; object-fit: cover; border-radius: 4px; cursor: pointer;';
                video.muted = true;
                video.addEventListener('loadedmetadata', () => {
                    video.currentTime = 1; // Seek to 1 second for thumbnail
                });
                
                // Add play icon overlay
                const playIcon = document.createElement('div');
                playIcon.innerHTML = '▶';
                playIcon.style.cssText = `
                    position: absolute; width: 20px; height: 20px; 
                    background: rgba(0,0,0,0.7); color: white; 
                    border-radius: 50%; display: flex; align-items: center; 
                    justify-content: center; font-size: 10px; margin-left: -50px; margin-top: 20px;
                `;
                
                video.addEventListener('click', () => {
                    this.showFullVideo(photoPath, filename);
                });
                
                container.appendChild(video);
                container.appendChild(playIcon);
            } else {
                // Create image thumbnail
                const img = document.createElement('img');
                img.src = photoPath;
                img.style.cssText = 'width: 60px; height: 60px; object-fit: cover; border-radius: 4px; cursor: pointer;';
                img.alt = filename;
                
                // Add click handler to view full image
                img.addEventListener('click', () => {
                    this.showFullImage(photoPath, filename);
                });
                
                // Handle image load errors
                img.addEventListener('error', () => {
                    img.style.display = 'none';
                    const errorText = document.createElement('span');
                    errorText.textContent = '📷 ' + filename;
                    errorText.style.cssText = 'color: #999; font-size: 12px;';
                    container.appendChild(errorText);
                });
                
                container.appendChild(img);
            }
        } else {
            // No extracted file found - show filename with icon
            const icon = document.createElement('span');
            const extension = filename.toLowerCase().split('.').pop();
            const isVideo = ['mov', 'mp4', 'avi', 'm4v'].includes(extension);
            icon.textContent = isVideo ? '🎥' : '📷';
            icon.style.cssText = 'font-size: 20px; opacity: 0.5;';
            container.appendChild(icon);
        }
        
        // Add filename text
        const filenameSpan = document.createElement('span');
        filenameSpan.textContent = filename;
        filenameSpan.style.cssText = 'font-size: 12px; color: #666; word-break: break-all;';
        container.appendChild(filenameSpan);
        
        td.appendChild(container);
    }
    
    findExtractedPhoto(filename, record) {
        // Check if the record has the extracted file path information
        if (record && record['Extracted_File_Path'] && record['Extracted_File_Path'].trim() !== '') {
            // Convert file system path to file:// URL for the browser
            const filePath = record['Extracted_File_Path'].replace(/\\/g, '/');
            return `file://${filePath}`;
        }
        
        // Fallback: try to construct path (this may not work reliably)
        if (!this.caseDirectory || !filename) return null;
        
        try {
            // Look for Photos_* folders in the case directory
            const photosFolderPattern = /Photos_.*_\d+/;
            // Note: In a real implementation, we'd need to scan the directory structure
            // For now, we'll return null to avoid broken image links
            return null;
        } catch (error) {
            console.warn('Error finding extracted photo:', error);
            return null;
        }
    }
    
    showFullImage(imagePath, filename) {
        // Create modal to show full-size image
        const modal = document.createElement('div');
        modal.className = 'photo-modal';
        modal.style.cssText = `
            position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
            background: rgba(0,0,0,0.8); display: flex; align-items: center; 
            justify-content: center; z-index: 10000; cursor: pointer;
        `;
        
        const img = document.createElement('img');
        img.src = imagePath;
        img.style.cssText = 'max-width: 90%; max-height: 90%; object-fit: contain;';
        img.alt = filename;
        
        const caption = document.createElement('div');
        caption.textContent = filename;
        caption.style.cssText = `
            position: absolute; bottom: 20px; left: 50%; transform: translateX(-50%);
            color: white; background: rgba(0,0,0,0.7); padding: 10px 20px;
            border-radius: 4px; font-size: 14px;
        `;
        
        modal.appendChild(img);
        modal.appendChild(caption);
        
        // Close modal on click
        modal.addEventListener('click', () => {
            document.body.removeChild(modal);
        });
        
        document.body.appendChild(modal);
    }
    
    showFullVideo(videoPath, filename) {
        // Create modal to show full-size video
        const modal = document.createElement('div');
        modal.className = 'video-modal';
        modal.style.cssText = `
            position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
            background: rgba(0,0,0,0.8); display: flex; align-items: center; 
            justify-content: center; z-index: 10000;
        `;
        
        const video = document.createElement('video');
        video.src = videoPath;
        video.style.cssText = 'max-width: 90%; max-height: 90%; object-fit: contain;';
        video.controls = true;
        video.autoplay = true;
        
        const caption = document.createElement('div');
        caption.textContent = filename;
        caption.style.cssText = `
            position: absolute; bottom: 20px; left: 50%; transform: translateX(-50%);
            color: white; background: rgba(0,0,0,0.7); padding: 10px 20px;
            border-radius: 4px; font-size: 14px;
        `;
        
        const closeButton = document.createElement('button');
        closeButton.textContent = '✕';
        closeButton.style.cssText = `
            position: absolute; top: 20px; right: 20px;
            background: rgba(0,0,0,0.7); color: white; border: none;
            border-radius: 50%; width: 40px; height: 40px; cursor: pointer;
            font-size: 18px; display: flex; align-items: center; justify-content: center;
        `;
        
        closeButton.addEventListener('click', () => {
            video.pause();
            document.body.removeChild(modal);
        });
        
        modal.appendChild(video);
        modal.appendChild(caption);
        modal.appendChild(closeButton);
        
        // Close modal on background click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                video.pause();
                document.body.removeChild(modal);
            }
        });
        
        document.body.appendChild(modal);
    }
    
    formatDate(dateStr) {
        if (!dateStr) return '';
        try {
            const date = new Date(dateStr);
            return date.toLocaleString();
        } catch {
            return dateStr;
        }
    }
    
    formatPhoneNumber(phone) {
        if (!phone) return '';
        // Simple phone number formatting
        const cleaned = phone.replace(/\D/g, '');
        if (cleaned.length === 10) {
            return `(${cleaned.slice(0, 3)}) ${cleaned.slice(3, 6)}-${cleaned.slice(6)}`;
        }
        return phone;
    }
    
    truncateText(text, maxLength) {
        if (!text) return '';
        if (text.length <= maxLength) return text;
        return text.slice(0, maxLength) + '...';
    }
}

// Export for use in other modules
window.CSVDataViewer = CSVDataViewer;
