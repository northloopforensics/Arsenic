/**
 * Photo Gallery Component for iOS Photo Reports
 * Displays extracted photos as a thumbnail gallery instead of CSV table
 */

class PhotoGallery {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.photos = [];
        this.filteredPhotos = []; // For search results
        this.currentPage = 1;
        this.photosPerPage = 20;
        this.totalPages = 1;
        this.searchTerm = '';
        
        if (!this.container) {
            console.error(`Photo gallery container '${containerId}' not found`);
            return;
        }
        
        this.initializeGallery();
    }
    
    initializeGallery() {
        this.container.innerHTML = `
            <div class="photo-gallery-container">
                <div class="gallery-header">
                    <h4>Taxonomy Results</h4>
                    <div class="gallery-search">
                        <div class="search-container">
                            <input type="text" id="gallery-search" placeholder="Search photos by filename or metadata..." autocomplete="off">
                            <button id="search-clear" class="search-clear-btn" title="Clear search">✕</button>
                        </div>
                        <div class="search-info">
                            <span id="search-results-info"></span>
                        </div>
                    </div>
                    <div class="gallery-controls">
                        <div class="gallery-info">
                            <span id="gallery-photo-count">0 photos</span>
                        </div>
                        <div class="gallery-view-options">
                            <label>
                                <input type="range" id="thumbnail-size" min="120" max="300" value="180" step="30">
                                <span>Thumbnail Size</span>
                            </label>
                        </div>
                    </div>
                </div>
                
                <div class="gallery-grid" id="photo-grid">
                    <!-- Photos will be loaded here -->
                </div>
                
                <div class="gallery-pagination">
                    <button id="gallery-prev" class="btn btn-sm">← Previous</button>
                    <span id="gallery-page-info">Page 1 of 1</span>
                    <button id="gallery-next" class="btn btn-sm">Next →</button>
                </div>
                
                <div id="gallery-loading" class="loading-spinner" style="display: none;">
                    <div class="spinner"></div>
                    <p>Loading photos...</p>
                </div>
            </div>
        `;
        
        this.setupEventListeners();
        this.addGalleryStyles();
    }
    
    setupEventListeners() {
        console.log('=== SETTING UP SEARCH EVENT LISTENERS ===');
        
        // Search functionality
        const searchInput = this.container.querySelector('#gallery-search');
        const searchClear = this.container.querySelector('#search-clear');
        
        console.log('Search input element found:', !!searchInput);
        console.log('Search clear button found:', !!searchClear);
        
        if (searchInput) {
            console.log('✅ Adding search input event listeners');
            // Real-time search as user types (with debouncing)
            let searchTimeout;
            searchInput.addEventListener('input', (e) => {
                console.log('🔍 Search input event triggered:', e.target.value);
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    console.log('🔍 Performing search after debounce:', e.target.value);
                    this.performSearch(e.target.value);
                }, 300); // 300ms debounce
            });
            
            // Handle Enter key
            searchInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    console.log('🔍 Enter key pressed, performing immediate search');
                    clearTimeout(searchTimeout);
                    this.performSearch(e.target.value);
                }
            });
        } else {
            console.error('❌ Search input element not found!');
        }
        
        if (searchClear) {
            console.log('✅ Adding search clear button event listener');
            searchClear.addEventListener('click', () => {
                console.log('🔍 Clear search button clicked');
                this.clearSearch();
            });
        } else {
            console.error('❌ Search clear button not found!');
        }
        
        // Thumbnail size slider
        const sizeSlider = this.container.querySelector('#thumbnail-size');
        if (sizeSlider) {
            sizeSlider.addEventListener('input', (e) => {
                this.updateThumbnailSize(e.target.value);
            });
        }
        
        // Pagination
        const prevBtn = this.container.querySelector('#gallery-prev');
        const nextBtn = this.container.querySelector('#gallery-next');
        
        if (prevBtn) {
            prevBtn.addEventListener('click', () => {
                if (this.currentPage > 1) {
                    this.currentPage--;
                    this.renderPhotos();
                }
            });
        }
        
        if (nextBtn) {
            nextBtn.addEventListener('click', () => {
                if (this.currentPage < this.totalPages) {
                    this.currentPage++;
                    this.renderPhotos();
                }
            });
        }
    }
    
    addGalleryStyles() {
        // Add CSS styles for the photo gallery
        if (!document.getElementById('photo-gallery-styles')) {
            const style = document.createElement('style');
            style.id = 'photo-gallery-styles';
            style.textContent = `
                .photo-gallery-container {
                    padding: 20px;
                    background: #f8f9fa;
                    border-radius: 8px;
                    min-height: 500px;
                    font-family: Arial, sans-serif;
                }
                
                .gallery-header {
                    display: flex;
                    flex-direction: column;
                    gap: 15px;
                    margin-bottom: 20px;
                    padding-bottom: 15px;
                    border-bottom: 2px solid #dee2e6;
                }
                
                .gallery-header h4 {
                    margin: 0;
                    color: #333;
                    font-size: 20px;
                }
                
                .gallery-search {
                    display: flex;
                    flex-direction: column;
                    gap: 8px;
                }
                
                .search-container {
                    position: relative;
                    max-width: 500px;
                }
                
                #gallery-search {
                    width: 100%;
                    padding: 10px 40px 10px 15px;
                    border: 2px solid #ddd;
                    border-radius: 25px;
                    font-size: 14px;
                    outline: none;
                    transition: border-color 0.3s;
                    box-sizing: border-box;
                }
                
                #gallery-search:focus {
                    border-color: #007bff;
                    box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.1);
                }
                
                .search-clear-btn {
                    position: absolute;
                    right: 12px;
                    top: 50%;
                    transform: translateY(-50%);
                    background: none;
                    border: none;
                    font-size: 16px;
                    color: #999;
                    cursor: pointer;
                    padding: 0;
                    width: 20px;
                    height: 20px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    border-radius: 50%;
                    transition: background-color 0.2s;
                }
                
                .search-clear-btn:hover {
                    background-color: #f0f0f0;
                    color: #666;
                }
                
                .search-info {
                    font-size: 12px;
                    color: #666;
                    min-height: 16px;
                }
                
                .search-info.has-results {
                    color: #007bff;
                    font-weight: 500;
                }
                
                .gallery-controls {
                    display: flex;
                    align-items: center;
                    gap: 20px;
                    align-self: flex-end;
                }
                
                .gallery-info {
                    font-weight: bold;
                    color: #666;
                }
                
                .gallery-view-options label {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    font-size: 14px;
                }
                
                .gallery-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
                    gap: 15px;
                    margin-bottom: 30px;
                    min-height: 300px;
                    padding: 10px;
                }
                
                .photo-item {
                    background: white;
                    border-radius: 8px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                    transition: transform 0.2s, box-shadow 0.2s;
                    cursor: pointer;
                    display: flex;
                    flex-direction: column;
                    height: fit-content;
                    overflow: hidden;
                    position: relative;
                }
                
                .photo-item:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 4px 16px rgba(0,0,0,0.15);
                }
                
                .photo-thumbnail {
                    width: 100%;
                    height: 150px;
                    object-fit: cover;
                    background: #f0f0f0;
                    display: block;
                    flex-shrink: 0;
                }
                
                .video-thumbnail {
                    position: relative;
                }
                
                .video-thumbnail::after {
                    content: '▶';
                    position: absolute;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%);
                    background: rgba(0,0,0,0.7);
                    color: white;
                    border-radius: 50%;
                    width: 40px;
                    height: 40px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 16px;
                    pointer-events: none;
                }
                
                .photo-info {
                    padding: 8px 10px;
                    background: white;
                    display: flex;
                    flex-direction: column;
                    gap: 2px;
                    min-height: 55px;
                    position: relative;
                }
                
                .photo-filename {
                    font-size: 12px;
                    font-weight: 600;
                    color: #333;
                    word-break: break-all;
                    line-height: 1.2;
                    text-align: center;
                    max-height: 2.4em;
                    overflow: hidden;
                    display: -webkit-box;
                    -webkit-line-clamp: 2;
                    -webkit-box-orient: vertical;
                }
                
                .photo-metadata {
                    font-size: 10px;
                    color: #666;
                    text-align: center;
                    line-height: 1.2;
                }
                
                .photo-confidence {
                    font-size: 10px;
                    color: #007bff;
                    font-weight: 600;
                    text-align: center;
                }
                
                .photo-date {
                    font-size: 9px;
                    color: #999;
                    text-align: center;
                }
                
                .gallery-pagination {
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    gap: 15px;
                    margin-top: 20px;
                }
                
                .gallery-pagination button:disabled {
                    opacity: 0.5;
                    cursor: not-allowed;
                }
                
                .no-photos-message {
                    text-align: center;
                    padding: 60px 20px;
                    color: #666;
                    font-size: 18px;
                }
                
                .no-photos-message i {
                    font-size: 48px;
                    margin-bottom: 15px;
                    display: block;
                    opacity: 0.5;
                }
                
                .photo-error {
                    background: #f8f9fa;
                    border: 1px solid #dee2e6;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    height: 150px;
                    color: #6c757d;
                    font-size: 11px;
                    font-weight: 500;
                }
                
                .photo-error span {
                    display: none;
                }
                
                .heic-thumbnail {
                    background: #f0f0f0;
                    border: 1px solid #dee2e6;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 11px;
                    color: #666;
                    font-weight: 500;
                }
                
                .loading-spinner {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    padding: 40px;
                }
                
                .spinner {
                    border: 4px solid #f3f3f3;
                    border-top: 4px solid #007bff;
                    border-radius: 50%;
                    width: 40px;
                    height: 40px;
                    animation: spin 1s linear infinite;
                    margin-bottom: 10px;
                }
                
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
            `;
            document.head.appendChild(style);
        }
    }
    
    performSearch(searchTerm) {
        console.log('=== PERFORM SEARCH CALLED ===');
        console.log('Search term:', searchTerm);
        console.log('Total photos available:', this.photos.length);
        
        this.searchTerm = searchTerm.trim().toLowerCase();
        
        if (this.searchTerm === '') {
            // If search is empty, show all photos
            this.filteredPhotos = [...this.photos];
            console.log('Search cleared, showing all photos:', this.filteredPhotos.length);
        } else {
            console.log('Starting to filter photos...');
            console.log('Sample photo before filtering:', this.photos[0]);
            console.log('Sample photo keys:', Object.keys(this.photos[0]));
            console.log('All photo data for debugging:', this.photos[0]);
            
            // Search through photos based on filename and metadata
            this.filteredPhotos = this.photos.filter((photo, index) => {
                console.log(`Checking photo ${index + 1}/${this.photos.length}`);
                const matches = this.matchesSearchTerm(photo, this.searchTerm);
                if (matches) {
                    console.log('✅ Found match:', photo);
                }
                return matches;
            });
            console.log('Filtered photos found:', this.filteredPhotos.length);
        }
        
        // Reset to first page and update pagination
        this.currentPage = 1;
        this.totalPages = Math.ceil(this.filteredPhotos.length / this.photosPerPage);
        
        console.log('Updated pagination - current page:', this.currentPage, 'total pages:', this.totalPages);
        
        // Update UI
        this.updateSearchInfo();
        this.updatePhotoCount();
        this.renderPhotos();
        
        console.log('=== SEARCH COMPLETE ===');
    }
    
    matchesSearchTerm(photo, searchTerm) {
        // Debug: Show what fields are available for the first photo
        if (!this.searchDebugShown) {
            console.log('=== SEARCH DEBUG - Photo Data Structure ===');
            const keys = Object.keys(photo);
            console.log('Available photo fields:', keys);
            console.log('Photo data sample:');
            keys.forEach(key => {
                console.log(`  ${key}: ${photo[key]}`);
            });
            console.log('Searching for term:', searchTerm);
            this.searchDebugShown = true;
        }
        
        // Search in all available fields
        for (const [key, value] of Object.entries(photo)) {
            if (value && value.toString().toLowerCase().includes(searchTerm)) {
                console.log(`✅ Match found in ${key}:`, value);
                return true;
            }
        }
        
        return false;
    }
    
    clearSearch() {
        const searchInput = this.container.querySelector('#gallery-search');
        if (searchInput) {
            searchInput.value = '';
        }
        this.performSearch('');
    }
    
    updateSearchInfo() {
        const searchInfo = this.container.querySelector('#search-results-info');
        if (!searchInfo) return;
        
        if (this.searchTerm === '') {
            searchInfo.textContent = '';
            searchInfo.className = 'search-info';
        } else {
            const totalResults = this.filteredPhotos.length;
            const totalPhotos = this.photos.length;
            searchInfo.textContent = `Found ${totalResults} of ${totalPhotos} photos matching "${this.searchTerm}"`;
            searchInfo.className = 'search-info has-results';
        }
    }
    
    async loadPhotos(caseDirectory, dataType) {
        console.log('PhotoGallery.loadPhotos called with:', { caseDirectory, dataType });
        this.showLoading(true);
        
        try {
            // Load the CSV data
            console.log('Loading CSV data for photo gallery...');
            const csvData = await window.electronAPI.readCSVFile(caseDirectory, dataType);
            console.log('CSV data loaded:', csvData);
            
            if (csvData && csvData.data) {
                this.photos = csvData.data;
                this.filteredPhotos = [...this.photos]; // Initialize filtered photos with all photos
                console.log(`Found ${this.photos.length} photos in CSV data`);
                console.log('Sample photo data:', this.photos[0]);
                
                this.totalPages = Math.ceil(this.filteredPhotos.length / this.photosPerPage);
                this.currentPage = 1;
                
                this.updatePhotoCount();
                this.renderPhotos();
            } else {
                console.warn('No CSV data found');
                this.showNoPhotos();
            }
        } catch (error) {
            console.error('Error loading photos:', error);
            this.showError('Failed to load photos: ' + error.message);
        } finally {
            this.showLoading(false);
        }
    }
    
    renderPhotos() {
        const grid = this.container.querySelector('#photo-grid');
        if (!grid) return;
        
        // Use filtered photos for rendering
        const photosToRender = this.filteredPhotos || this.photos;
        
        // Calculate photos for current page
        const startIdx = (this.currentPage - 1) * this.photosPerPage;
        const endIdx = startIdx + this.photosPerPage;
        const pagePhotos = photosToRender.slice(startIdx, endIdx);
        
        if (pagePhotos.length === 0) {
            if (this.searchTerm && this.filteredPhotos.length === 0) {
                this.showNoSearchResults();
            } else {
                this.showNoPhotos();
            }
            return;
        }
        
        // Render photo items
        grid.innerHTML = pagePhotos.map(photo => this.createPhotoItem(photo)).join('');
        
        // Update pagination
        this.updatePagination();
        
        // Setup click handlers for photos
        this.setupPhotoClickHandlers();
        
        // Load HEIC thumbnails
        this.loadHeicThumbnails();
    }
    
    createPhotoItem(photo) {
        const filename = photo.Filename || 'Unknown';
        const extractedPath = photo.Extracted_File_Path || '';
        const confidence = photo.Confidence || '';
        const dateCreated = photo['Date Created'] || '';
        
        // Determine file type
        const extension = filename.toLowerCase().split('.').pop();
        const isVideo = ['mov', 'mp4', 'avi', 'm4v'].includes(extension);
        const isHeic = ['heic', 'heif'].includes(extension);
        
        let thumbnailHtml = '';
        if (extractedPath && extractedPath.trim() !== '') {
            const filePath = `file://${extractedPath.replace(/\\/g, '/')}`;
            
            if (isVideo) {
                thumbnailHtml = `
                    <video class="photo-thumbnail video-thumbnail" 
                           data-path="${filePath}" 
                           data-filename="${filename}"
                           muted>
                        <source src="${filePath}">
                    </video>
                `;
            } else if (isHeic) {
                // For HEIC files, use a placeholder that will be replaced with thumbnail
                thumbnailHtml = `
                    <div class="photo-thumbnail heic-thumbnail" 
                         data-path="${extractedPath}" 
                         data-filename="${filename}"
                         style="background: #f0f0f0; display: flex; align-items: center; justify-content: center; color: #666; font-size: 12px;">
                        Loading HEIC...
                    </div>
                `;
            } else {
                thumbnailHtml = `
                    <img class="photo-thumbnail" 
                         src="${filePath}" 
                         alt="${filename}"
                         data-path="${filePath}"
                         data-filename="${filename}">
                `;
            }
        } else {
            // No extracted file - show placeholder without icons
            thumbnailHtml = `
                <div class="photo-error">
                    <div>File not extracted</div>
                </div>
            `;
        }
        
        // Format date for better display
        const formattedDate = dateCreated ? new Date(dateCreated).toLocaleDateString() : '';
        
        return `
            <div class="photo-item" data-filename="${filename}" data-path="${extractedPath}">
                ${thumbnailHtml}
                <div class="photo-info">
                    <div class="photo-filename" title="${filename}">${filename}</div>
                    ${confidence ? `<div class="photo-confidence">Confidence: ${confidence}%</div>` : ''}
                    ${formattedDate ? `<div class="photo-date">${formattedDate}</div>` : ''}
                </div>
            </div>
        `;
    }
    
    setupPhotoClickHandlers() {
        const photoItems = this.container.querySelectorAll('.photo-item');
        photoItems.forEach(item => {
            item.addEventListener('click', () => {
                const path = item.dataset.path;
                const filename = item.dataset.filename;
                
                if (path && path.trim() !== '') {
                    this.showFullMedia(path, filename);
                }
            });
        });
        
        // Setup image error handling
        const images = this.container.querySelectorAll('.photo-thumbnail');
        images.forEach(img => {
            if (img.tagName === 'IMG') {
                img.addEventListener('error', () => {
                    // Replace with error placeholder while preserving the photo-info
                    const photoItem = img.closest('.photo-item');
                    const photoInfo = photoItem.querySelector('.photo-info');
                    const photoInfoHtml = photoInfo ? photoInfo.outerHTML : '';
                    
                    photoItem.innerHTML = `
                        <div class="photo-error">
                            <div>Image not found</div>
                        </div>
                        ${photoInfoHtml}
                    `;
                });
            }
        });
        
        // Setup video thumbnail generation
        const videos = this.container.querySelectorAll('.video-thumbnail');
        videos.forEach(video => {
            video.addEventListener('loadedmetadata', () => {
                video.currentTime = 1; // Seek to 1 second for thumbnail
            });
        });
    }
    
    async loadHeicThumbnails() {
        const heicThumbnails = this.container.querySelectorAll('.heic-thumbnail');
        
        for (const thumbnail of heicThumbnails) {
            const imagePath = thumbnail.dataset.path;
            const filename = thumbnail.dataset.filename;
            
            if (!imagePath) continue;
            
            try {
                // Call the Flask API to generate thumbnail
                const response = await fetch('http://127.0.0.1:3131/api/image/thumbnail', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ image_path: imagePath })
                });
                
                if (response.ok) {
                    // Convert response to blob and create object URL
                    const blob = await response.blob();
                    const thumbnailUrl = URL.createObjectURL(blob);
                    
                    // Replace the placeholder with an actual image
                    const img = document.createElement('img');
                    img.className = 'photo-thumbnail';
                    img.src = thumbnailUrl;
                    img.alt = filename;
                    img.setAttribute('data-path', imagePath);
                    img.setAttribute('data-filename', filename);
                    img.style.cssText = 'width: 100%; height: 150px; object-fit: cover; background: #f0f0f0; display: block; flex-shrink: 0;';
                    
                    // Replace the placeholder
                    thumbnail.parentNode.replaceChild(img, thumbnail);
                    
                    // Clean up object URL after image loads
                    img.onload = () => {
                        // Keep the URL for potential future use, but we could revoke it
                        // URL.revokeObjectURL(thumbnailUrl);
                    };
                } else {
                    // Show error state
                    thumbnail.innerHTML = 'HEIC preview unavailable';
                    thumbnail.style.fontSize = '10px';
                    thumbnail.style.color = '#999';
                }
            } catch (error) {
                console.error('Error loading HEIC thumbnail:', error);
                thumbnail.innerHTML = 'HEIC preview unavailable';
                thumbnail.style.fontSize = '10px';
                thumbnail.style.color = '#999';
            }
        }
    }
    
    async loadHeicModalImage(imagePath, imgElement) {
        try {
            console.log('Loading HEIC image for modal via API:', imagePath);
            
            const response = await fetch('http://127.0.0.1:3131/api/image/thumbnail', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ image_path: imagePath })
            });
            
            if (response.ok) {
                const blob = await response.blob();
                const imageUrl = URL.createObjectURL(blob);
                imgElement.src = imageUrl;
                console.log('Successfully loaded HEIC image for modal');
                
                // Clean up object URL when image loads or modal is closed
                imgElement.onload = () => {
                    // URL.revokeObjectURL(imageUrl); // Don't revoke immediately, keep for modal display
                };
            } else {
                console.error('Failed to load HEIC image:', response.status, response.statusText);
                imgElement.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48dGV4dCB4PSI1MCUiIHk9IjUwJSIgZG9taW5hbnQtYmFzZWxpbmU9Im1pZGRsZSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZmlsbD0iI2YwMCI+RXJyb3IgbG9hZGluZyBIRUlDPC90ZXh0Pjwvc3ZnPg==';
            }
        } catch (error) {
            console.error('Error loading HEIC image for modal:', error);
            imgElement.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48dGV4dCB4PSI1MCUiIHk9IjUwJSIgZG9taW5hbnQtYmFzZWxpbmU9Im1pZGRsZSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZmlsbD0iI2YwMCI+RXJyb3IgbG9hZGluZyBIRUlDPC90ZXh0Pjwvc3ZnPg==';
        }
    }
    
    showFullMedia(mediaPath, filename) {
        const extension = filename.toLowerCase().split('.').pop();
        const isVideo = ['mov', 'mp4', 'avi', 'm4v'].includes(extension);
        const isHeic = ['heic', 'heif'].includes(extension);
        const filePath = `file://${mediaPath.replace(/\\/g, '/')}`;
        
        // Create modal
        const modal = document.createElement('div');
        modal.className = 'photo-modal';
        modal.style.cssText = `
            position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
            background: rgba(0,0,0,0.9); display: flex; align-items: center; 
            justify-content: center; z-index: 10000; overflow-y: auto;
        `;
        
        // Create modal content container
        const modalContent = document.createElement('div');
        modalContent.style.cssText = `
            display: flex; max-width: 95%; max-height: 95%; 
            background: rgba(20,20,20,0.95); border-radius: 12px;
            overflow: hidden; position: relative;
        `;
        
        // Create image/video container
        const mediaContainer = document.createElement('div');
        mediaContainer.style.cssText = `
            flex: 1; display: flex; align-items: center; justify-content: center;
            min-width: 60%; position: relative;
        `;
        
        let mediaElement;
        if (isVideo) {
            mediaElement = document.createElement('video');
            mediaElement.controls = true;
            mediaElement.autoplay = true;
            mediaElement.style.cssText = 'max-width: 100%; max-height: 100%; object-fit: contain;';
            mediaElement.src = filePath;
        } else {
            mediaElement = document.createElement('img');
            mediaElement.style.cssText = 'max-width: 100%; max-height: 100%; object-fit: contain;';
            mediaElement.alt = filename;
            
            // For HEIC files, load via thumbnail API instead of direct file path
            if (isHeic) {
                console.log('Loading HEIC image via thumbnail API for modal:', mediaPath);
                // Show loading indicator
                mediaElement.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48dGV4dCB4PSI1MCUiIHk9IjUwJSIgZG9taW5hbnQtYmFzZWxpbmU9Im1pZGRsZSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZmlsbD0iI2NjYyI+TG9hZGluZyBIRUlDLi4uPC90ZXh0Pjwvc3ZnPg==';
                
                // Load HEIC image via API
                this.loadHeicModalImage(mediaPath, mediaElement);
            } else {
                // For regular images, use file path
                mediaElement.src = filePath;
            }
        }
        
        mediaContainer.appendChild(mediaElement);
        
        // Create metadata sidebar
        const metadataContainer = document.createElement('div');
        metadataContainer.style.cssText = `
            width: 350px; background: rgba(30,30,30,0.95); 
            padding: 20px; overflow-y: auto; color: white;
            border-left: 1px solid rgba(255,255,255,0.1);
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        `;
        
        // Add filename header
        const filenameHeader = document.createElement('h3');
        filenameHeader.style.cssText = `
            margin: 0 0 20px 0; color: #fff; font-size: 16px; 
            word-break: break-all; border-bottom: 2px solid #007bff; 
            padding-bottom: 10px;
        `;
        filenameHeader.textContent = filename;
        metadataContainer.appendChild(filenameHeader);
        
        // Add loading indicator for EXIF data
        const exifLoading = document.createElement('div');
        exifLoading.style.cssText = `
            display: flex; align-items: center; justify-content: center;
            padding: 20px; color: #ccc;
        `;
        exifLoading.innerHTML = `
            <div style="width: 20px; height: 20px; border: 2px solid #333; border-top: 2px solid #007bff; 
                        border-radius: 50%; animation: spin 1s linear infinite; margin-right: 10px;"></div>
            Loading metadata...
        `;
        metadataContainer.appendChild(exifLoading);
        
        // Create close button
        const closeButton = document.createElement('button');
        closeButton.innerHTML = '✕';
        closeButton.style.cssText = `
            position: absolute; top: 15px; right: 15px; z-index: 10001;
            background: rgba(0,0,0,0.8); color: white; border: none;
            border-radius: 50%; width: 40px; height: 40px; cursor: pointer;
            font-size: 18px; display: flex; align-items: center; justify-content: center;
            transition: background 0.2s;
        `;
        
        closeButton.addEventListener('click', () => {
            if (isVideo) mediaElement.pause();
            document.body.removeChild(modal);
        });
        
        // Assemble modal
        modalContent.appendChild(mediaContainer);
        modalContent.appendChild(metadataContainer);
        modal.appendChild(modalContent);
        modal.appendChild(closeButton);
        
        // Close on background click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                if (isVideo) mediaElement.pause();
                document.body.removeChild(modal);
            }
        });
        
        document.body.appendChild(modal);
        
        // Load EXIF data for images
        if (!isVideo) {
            this.loadExifData(mediaPath, metadataContainer, exifLoading);
        } else {
            // For videos, just show basic file info
            this.showBasicFileInfo(mediaPath, metadataContainer, exifLoading);
        }
    }
    
    async loadExifData(imagePath, container, loadingElement) {
        try {
            // Call the Flask API to extract EXIF data
            const response = await fetch('http://127.0.0.1:3131/api/image/exif', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ image_path: imagePath })
            });
            
            const result = await response.json();
            
            // Remove loading indicator
            if (loadingElement && container.contains(loadingElement)) {
                container.removeChild(loadingElement);
            }
            
            if (result.success && result.exif_data) {
                this.displayExifData(result.exif_data, container);
            } else {
                this.showExifError(result.error || 'Failed to extract metadata', container);
            }
            
        } catch (error) {
            console.error('Error loading EXIF data:', error);
            if (loadingElement && container.contains(loadingElement)) {
                container.removeChild(loadingElement);
            }
            this.showExifError('Network error loading metadata', container);
        }
    }
    
    async showBasicFileInfo(filePath, container, loadingElement) {
        try {
            const stats = await window.electronAPI.getFileStats(filePath);
            
            // Remove loading indicator
            if (loadingElement && container.contains(loadingElement)) {
                container.removeChild(loadingElement);
            }
            
            const fileInfo = {
                'File Type': 'Video',
                'File Size': this.formatFileSize(stats.size),
                'Modified': new Date(stats.mtime).toLocaleString()
            };
            
            this.displayExifData(fileInfo, container);
            
        } catch (error) {
            console.error('Error getting file info:', error);
            if (loadingElement && container.contains(loadingElement)) {
                container.removeChild(loadingElement);
            }
            this.showExifError('Failed to load file information', container);
        }
    }
    
    displayExifData(exifData, container) {
        // Essential file information
        const fileFields = [
            'File Type', 'File Size', 'Image Width', 'Image Height',
            'DateTime', 'DateTimeOriginal'
        ];
        
        // GPS information - always show if available
        const gpsFields = [
            'GPS Latitude', 'GPS Longitude', 'GPS Altitude', 'GPS Timestamp'
        ];
        
        // Key camera settings including lens model
        const cameraFields = [
            'Make', 'Model', 'LensModel', 'Lens Model', 'LensSpecification',
            'FocalLength', 'FNumber', 'ExposureTime', 'ISO'
        ];
        
        // Create sections - always show GPS section if any GPS data exists
        const sections = [
            { title: 'File Information', fields: fileFields, data: exifData },
            { title: 'GPS Location', fields: gpsFields, data: exifData },
            { title: 'Camera & Lens', fields: cameraFields, data: exifData }
        ];
        
        sections.forEach(section => {
            const sectionFields = section.fields.filter(field => 
                section.data.hasOwnProperty(field) && section.data[field] !== null && section.data[field] !== ''
            );
            
            if (sectionFields.length > 0) {
                // Section header
                const sectionHeader = document.createElement('h4');
                sectionHeader.style.cssText = `
                    margin: 20px 0 10px 0; color: #007bff; font-size: 14px; 
                    text-transform: uppercase; letter-spacing: 1px;
                    border-bottom: 1px solid rgba(0,123,255,0.3); padding-bottom: 5px;
                `;
                sectionHeader.textContent = section.title;
                container.appendChild(sectionHeader);
                
                // Section content
                sectionFields.forEach(field => {
                    const value = section.data[field];
                    const metadataItem = document.createElement('div');
                    metadataItem.style.cssText = `
                        margin-bottom: 12px; padding: 8px; border-radius: 4px;
                        background: rgba(255,255,255,0.05);
                    `;
                    
                    const label = document.createElement('div');
                    label.style.cssText = `
                        font-weight: 600; font-size: 12px; color: #ccc; 
                        margin-bottom: 4px; text-transform: uppercase;
                        letter-spacing: 0.5px;
                    `;
                    // Better field name formatting
                    let displayName = field.replace(/([A-Z])/g, ' $1').trim();
                    if (field.includes('GPS') || field.includes('Latitude') || field.includes('Longitude')) {
                        displayName = displayName.replace(/GPS/g, '').replace(/Latitude/g, 'Latitude').replace(/Longitude/g, 'Longitude').trim();
                    }
                    label.textContent = displayName;
                    
                    const valueDiv = document.createElement('div');
                    valueDiv.style.cssText = `
                        font-size: 14px; color: #fff; word-break: break-all;
                        line-height: 1.4;
                    `;
                    
                    // Special handling for map links
                    if (field.includes('Maps Link')) {
                        const link = document.createElement('a');
                        link.href = value;
                        link.target = '_blank';
                        link.style.cssText = `
                            color: #007bff; text-decoration: none; 
                            border: 1px solid #007bff; padding: 6px 12px;
                            border-radius: 4px; display: inline-block;
                            transition: all 0.2s;
                        `;
                        link.textContent = field.includes('Google') ? '📍 Open in Google Maps' : '📍 Open in Apple Maps';
                        link.addEventListener('mouseenter', () => {
                            link.style.background = '#007bff';
                            link.style.color = 'white';
                        });
                        link.addEventListener('mouseleave', () => {
                            link.style.background = 'transparent';
                            link.style.color = '#007bff';
                        });
                        valueDiv.appendChild(link);
                    } else {
                        valueDiv.textContent = value;
                        
                        // Color code GPS coordinates
                        if (field.includes('GPS')) {
                            valueDiv.style.color = '#4CAF50';
                        }
                    }
                    
                    metadataItem.appendChild(label);
                    metadataItem.appendChild(valueDiv);
                    container.appendChild(metadataItem);
                });
            }
        });
        
        // Add toggle for advanced metadata
        this.addAdvancedMetadataToggle(exifData, container);
        
        // Add GPS map button if GPS coordinates are available
        this.addGpsMapButton(exifData, container);
        
        // Show error if present
        if (exifData.Error) {
            this.showExifError(exifData.Error, container);
        }
    }
    
    addAdvancedMetadataToggle(exifData, container) {
        // Get all the fields we haven't shown yet
        const shownFields = [
            'File Type', 'File Size', 'Image Width', 'Image Height',
            'DateTime', 'DateTimeOriginal', 'GPS Latitude', 'GPS Longitude', 'GPS Altitude', 'GPS Timestamp',
            'GPS Latitude Decimal', 'GPS Longitude Decimal', // Exclude decimal GPS fields from advanced view
            'Make', 'Model', 'LensModel', 'Lens Model', 'LensSpecification',
            'FocalLength', 'FNumber', 'ExposureTime', 'ISO', 'Error',
            'Google Maps Link', 'Apple Maps Link' // Exclude auto-generated map links
        ];
        
        const remainingFields = Object.keys(exifData).filter(key => 
            !shownFields.includes(key) && 
            exifData[key] !== null && 
            exifData[key] !== '' &&
            !key.includes('Decimal') && // Exclude all decimal fields
            !key.includes('Maps Link') // Exclude auto-generated map links
        );
        
        if (remainingFields.length > 0) {
            const toggleContainer = document.createElement('div');
            toggleContainer.style.cssText = `
                margin: 20px 0; padding: 10px; 
                background: rgba(128, 128, 128, 0.1);
                border: 1px solid rgba(128, 128, 128, 0.3);
                border-radius: 6px;
                text-align: center;
            `;
            
            const toggleButton = document.createElement('button');
            toggleButton.style.cssText = `
                background: #6c757d; color: white; border: none;
                padding: 8px 16px; border-radius: 4px; font-size: 12px;
                cursor: pointer; transition: all 0.2s;
            `;
            toggleButton.textContent = `Show Additional Metadata (${remainingFields.length} more fields)`;
            
            const advancedContainer = document.createElement('div');
            advancedContainer.style.display = 'none';
            advancedContainer.style.marginTop = '15px';
            
            // Add remaining fields to advanced container
            remainingFields.forEach(field => {
                const value = exifData[field];
                const metadataItem = document.createElement('div');
                metadataItem.style.cssText = `
                    margin-bottom: 8px; padding: 6px; border-radius: 4px;
                    background: rgba(255,255,255,0.03);
                `;
                
                const label = document.createElement('div');
                label.style.cssText = `
                    font-weight: 600; font-size: 11px; color: #aaa; 
                    margin-bottom: 2px;
                `;
                label.textContent = field.replace(/([A-Z])/g, ' $1').trim();
                
                const valueDiv = document.createElement('div');
                valueDiv.style.cssText = `
                    font-size: 12px; color: #ddd; word-break: break-all;
                    line-height: 1.3;
                `;
                valueDiv.textContent = value;
                
                metadataItem.appendChild(label);
                metadataItem.appendChild(valueDiv);
                advancedContainer.appendChild(metadataItem);
            });
            
            let isExpanded = false;
            toggleButton.addEventListener('click', () => {
                isExpanded = !isExpanded;
                advancedContainer.style.display = isExpanded ? 'block' : 'none';
                toggleButton.textContent = isExpanded ? 
                    'Hide Additional Metadata' : 
                    `Show Additional Metadata (${remainingFields.length} more fields)`;
                toggleButton.style.background = isExpanded ? '#dc3545' : '#6c757d';
            });
            
            toggleContainer.appendChild(toggleButton);
            toggleContainer.appendChild(advancedContainer);
            container.appendChild(toggleContainer);
        }
    }
    
    showExifError(errorMessage, container) {
        const errorDiv = document.createElement('div');
        errorDiv.style.cssText = `
            padding: 15px; background: rgba(220,53,69,0.1); 
            border: 1px solid rgba(220,53,69,0.3); border-radius: 6px;
            color: #dc3545; margin-top: 10px;
        `;
        errorDiv.innerHTML = `
            <strong>⚠️ Metadata Error:</strong><br>
            ${errorMessage}
        `;
        container.appendChild(errorDiv);
    }
    
    addGpsMapButton(exifData, container) {
        // Debug: log all EXIF data to see what GPS fields are available
        console.log('=== GPS BUTTON DEBUG START ===');
        console.log('Full EXIF Data received:', exifData);
        console.log('EXIF Data keys:', Object.keys(exifData));
        
        let latitude = null;
        let longitude = null;
        
        // First try the processed decimal values
        latitude = exifData['GPS Latitude Decimal'] || exifData['GPSLatitudeDecimal'];
        longitude = exifData['GPS Longitude Decimal'] || exifData['GPSLongitudeDecimal'];
        console.log('Tried decimal coordinates:', { latitude, longitude });
        
        // If no processed values, check for raw GPS Info data with various possible names
        if (!latitude || !longitude) {
            const possibleGpsKeys = ['G P S Info', 'GPS Info', 'GPSInfo', 'GPS', 'gps'];
            let gpsInfo = null;
            
            for (const key of possibleGpsKeys) {
                if (exifData[key]) {
                    gpsInfo = exifData[key];
                    console.log(`Found GPS data under key "${key}":`, gpsInfo);
                    break;
                }
            }
            
            if (gpsInfo) {
                console.log('Attempting to parse raw GPS data...');
                const coords = this.parseRawGPSData(gpsInfo);
                if (coords) {
                    latitude = coords.latitude;
                    longitude = coords.longitude;
                    console.log('Successfully parsed coordinates:', coords);
                } else {
                    console.log('Failed to parse raw GPS data');
                }
            } else {
                console.log('No GPS Info found in any expected keys');
                console.log('Available keys containing "GPS" or "gps":', 
                    Object.keys(exifData).filter(key => 
                        key.toLowerCase().includes('gps') || key.toLowerCase().includes('g p s')
                    )
                );
            }
        }
        
        console.log('Final GPS coordinates:', { latitude, longitude });
        
        if (latitude && longitude && latitude !== 0 && longitude !== 0) {
            console.log('✅ Creating GPS map button...');
            // Create GPS map button container
            const mapButtonContainer = document.createElement('div');
            mapButtonContainer.style.cssText = `
                margin: 20px 0; padding: 15px; 
                background: rgba(0, 123, 255, 0.1);
                border: 1px solid rgba(0, 123, 255, 0.3);
                border-radius: 8px;
                text-align: center;
            `;
            
            // Add header
            const header = document.createElement('div');
            header.style.cssText = `
                color: #007bff; font-weight: 600; 
                margin-bottom: 10px; font-size: 14px;
                text-transform: uppercase; letter-spacing: 1px;
            `;
            header.textContent = '📍 GPS Location Available';
            mapButtonContainer.appendChild(header);
            
            // Create the map button
            const mapButton = document.createElement('button');
            mapButton.style.cssText = `
                background: #007bff; color: white; border: none;
                padding: 12px 24px; border-radius: 6px; font-size: 14px;
                font-weight: 600; cursor: pointer; transition: all 0.2s;
                display: inline-flex; align-items: center; gap: 8px;
            `;
            mapButton.innerHTML = 'Open in Google Maps';
            
            // Add hover effects
            mapButton.addEventListener('mouseenter', () => {
                mapButton.style.background = '#0056b3';
                mapButton.style.transform = 'translateY(-1px)';
            });
            mapButton.addEventListener('mouseleave', () => {
                mapButton.style.background = '#007bff';
                mapButton.style.transform = 'translateY(0)';
            });
            
            // Add click handler to open Google Maps
            mapButton.addEventListener('click', () => {
                this.openGoogleMaps(latitude, longitude);
            });
            
            mapButtonContainer.appendChild(mapButton);
            container.appendChild(mapButtonContainer);
            console.log('✅ GPS map button added to container');
        } else {
            console.log('❌ No valid GPS coordinates found. Latitude:', latitude, 'Longitude:', longitude);
        }
        console.log('=== GPS BUTTON DEBUG END ===');
    }
    
    parseRawGPSData(gpsInfo) {
        try {
            console.log('=== PARSING RAW GPS DATA ===');
            console.log('GPS Info type:', typeof gpsInfo);
            console.log('GPS Info structure:', gpsInfo);
            
            // Handle case where gpsInfo might be a string representation of a Python object
            let gpsData = gpsInfo;
            if (typeof gpsInfo === 'string') {
                try {
                    // Try JSON.parse first
                    gpsData = JSON.parse(gpsInfo);
                    console.log('Parsed GPS data from JSON:', gpsData);
                } catch (e) {
                    console.log('Could not parse GPS info as JSON, trying Python object parser...');
                    gpsData = this.parsePythonObjectString(gpsInfo);
                    if (gpsData) {
                        console.log('Successfully parsed Python object:', gpsData);
                    } else {
                        console.log('Failed to parse Python object');
                        return null;
                    }
                }
            }
            
            // GPS Info format: {1: 'N', 2: (30.0, 18.0, 28.95), 3: 'W', 4: (89.0, 22.0, 29.42), ...}
            // Key 1: GPS Latitude Reference (N/S)
            // Key 2: GPS Latitude (degrees, minutes, seconds)
            // Key 3: GPS Longitude Reference (E/W)  
            // Key 4: GPS Longitude (degrees, minutes, seconds)
            
            const latRef = gpsData[1] || gpsData['1'];
            const latDMS = gpsData[2] || gpsData['2'];
            const lonRef = gpsData[3] || gpsData['3'];
            const lonDMS = gpsData[4] || gpsData['4'];
            
            console.log('Extracted GPS components:');
            console.log('  Latitude Reference (key 1):', latRef);
            console.log('  Latitude DMS (key 2):', latDMS);
            console.log('  Longitude Reference (key 3):', lonRef);
            console.log('  Longitude DMS (key 4):', lonDMS);
            
            if (!latDMS || !lonDMS) {
                console.log('❌ Missing GPS coordinate data');
                return null;
            }
            
            // Convert DMS to decimal degrees
            let latitude = this.convertDMSToDecimal(latDMS);
            let longitude = this.convertDMSToDecimal(lonDMS);
            
            console.log('Before hemisphere correction:', { latitude, longitude });
            
            // Apply hemisphere corrections
            if (latRef === 'S') latitude = -latitude;
            if (lonRef === 'W') longitude = -longitude;
            
            console.log('After hemisphere correction:', { latitude, longitude, latRef, lonRef });
            
            if (isNaN(latitude) || isNaN(longitude)) {
                console.log('❌ Invalid coordinates after conversion');
                return null;
            }
            
            console.log('✅ Successfully parsed GPS coordinates');
            return { latitude, longitude };
        } catch (error) {
            console.error('❌ Error parsing raw GPS data:', error);
            return null;
        }
    }
    
    parsePythonObjectString(pythonStr) {
        try {
            console.log('Parsing Python object string:', pythonStr);
            
            // Convert Python object syntax to JavaScript object
            // {1: 'N', 2: (30.0, 18.0, 28.95), 3: 'W', 4: (89.0, 22.0, 29.42), ...}
            
            const gpsData = {};
            
            // Extract key-value pairs using regex
            // Pattern: number: 'string' or number: (number, number, number) or number: number
            const patterns = [
                // Pattern for string values: 1: 'N'
                /(\d+):\s*'([^']+)'/g,
                // Pattern for tuple values: 2: (30.0, 18.0, 28.95)
                /(\d+):\s*\(([^)]+)\)/g,
                // Pattern for simple numeric values: 6: 2.0
                /(\d+):\s*([0-9.-]+)(?=,|\s*})/g,
                // Pattern for byte values: 5: b'\x00'
                /(\d+):\s*b'[^']*'/g
            ];
            
            // Extract string values
            let match;
            while ((match = patterns[0].exec(pythonStr)) !== null) {
                const key = parseInt(match[1]);
                const value = match[2];
                gpsData[key] = value;
                console.log(`Found string: ${key} -> "${value}"`);
            }
            
            // Reset regex
            patterns[1].lastIndex = 0;
            
            // Extract tuple values 
            while ((match = patterns[1].exec(pythonStr)) !== null) {
                const key = parseInt(match[1]);
                const tupleContent = match[2];
                const numbers = tupleContent.split(',').map(s => parseFloat(s.trim()));
                gpsData[key] = numbers;
                console.log(`Found tuple: ${key} -> [${numbers.join(', ')}]`);
            }
            
            // Reset regex
            patterns[2].lastIndex = 0;
            
            // Extract simple numeric values (but skip those already captured in tuples)
            while ((match = patterns[2].exec(pythonStr)) !== null) {
                const key = parseInt(match[1]);
                if (!gpsData[key]) { // Only if not already set by tuple parsing
                    const value = parseFloat(match[2]);
                    gpsData[key] = value;
                    console.log(`Found number: ${key} -> ${value}`);
                }
            }
            
            console.log('Parsed GPS data object:', gpsData);
            return gpsData;
            
        } catch (error) {
            console.error('Error parsing Python object string:', error);
            return null;
        }
    }
    
    convertDMSToDecimal(dms) {
        console.log('Converting DMS to decimal:', dms, 'Type:', typeof dms);
        
        // Convert degrees, minutes, seconds tuple to decimal degrees
        // dms format: (degrees, minutes, seconds) or [degrees, minutes, seconds]
        if (!dms) {
            console.log('❌ No DMS data provided');
            return 0;
        }
        
        // Handle direct number
        if (typeof dms === 'number') {
            console.log('DMS is already a number:', dms);
            return dms;
        }
        
        // Handle string that might be a number
        if (typeof dms === 'string') {
            const num = parseFloat(dms);
            if (!isNaN(num)) {
                console.log('DMS converted from string to number:', num);
                return num;
            }
        }
        
        // Handle tuple/array format
        if (Array.isArray(dms) || (typeof dms === 'object' && dms.length)) {
            const degrees = parseFloat(dms[0] || 0);
            const minutes = parseFloat(dms[1] || 0);
            const seconds = parseFloat(dms[2] || 0);
            
            console.log('DMS components:', { degrees, minutes, seconds });
            
            const decimal = degrees + (minutes / 60.0) + (seconds / 3600.0);
            console.log('Calculated decimal:', decimal);
            return decimal;
        }
        
        // Handle object with numeric keys
        if (typeof dms === 'object') {
            const degrees = parseFloat(dms[0] || dms['0'] || 0);
            const minutes = parseFloat(dms[1] || dms['1'] || 0);
            const seconds = parseFloat(dms[2] || dms['2'] || 0);
            
            console.log('DMS object components:', { degrees, minutes, seconds });
            
            const decimal = degrees + (minutes / 60.0) + (seconds / 3600.0);
            console.log('Calculated decimal from object:', decimal);
            return decimal;
        }
        
        console.log('❌ Unhandled DMS format:', dms);
        return 0;
    }
    
    openGoogleMaps(latitude, longitude) {
        // Create Google Maps URL with coordinates
        const mapsUrl = `https://www.google.com/maps?q=${latitude},${longitude}&z=15`;
        
        try {
            // Open in external browser
            if (window.electronAPI && window.electronAPI.openExternal) {
                // Electron environment - open in external browser
                window.electronAPI.openExternal(mapsUrl);
                console.log('Opening GPS location in Google Maps:', mapsUrl);
            } else {
                // Web environment - open in new tab
                window.open(mapsUrl, '_blank');
                console.log('Opening GPS location in new tab:', mapsUrl);
            }
        } catch (error) {
            console.error('Error opening Google Maps:', error);
            // Fallback to opening in new tab
            window.open(mapsUrl, '_blank');
        }
    }
    
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    updateThumbnailSize(size) {
        const grid = this.container.querySelector('#photo-grid');
        if (grid) {
            grid.style.gridTemplateColumns = `repeat(auto-fill, minmax(${size}px, 1fr))`;
            
            const thumbnails = grid.querySelectorAll('.photo-thumbnail');
            thumbnails.forEach(thumb => {
                thumb.style.height = size + 'px';
            });
        }
    }
    
    updatePhotoCount() {
        const countElement = this.container.querySelector('#gallery-photo-count');
        if (countElement) {
            const totalCount = this.photos.length;
            const displayedCount = this.filteredPhotos ? this.filteredPhotos.length : totalCount;
            
            if (this.searchTerm && displayedCount !== totalCount) {
                countElement.textContent = `${displayedCount} of ${totalCount} photos`;
            } else {
                countElement.textContent = `${totalCount} photo${totalCount !== 1 ? 's' : ''}`;
            }
        }
    }
    
    updatePagination() {
        const pageInfo = this.container.querySelector('#gallery-page-info');
        const prevBtn = this.container.querySelector('#gallery-prev');
        const nextBtn = this.container.querySelector('#gallery-next');
        
        if (pageInfo) {
            pageInfo.textContent = `Page ${this.currentPage} of ${this.totalPages}`;
        }
        
        if (prevBtn) prevBtn.disabled = this.currentPage <= 1;
        if (nextBtn) nextBtn.disabled = this.currentPage >= this.totalPages;
    }
    
    showLoading(show) {
        const loading = this.container.querySelector('#gallery-loading');
        const grid = this.container.querySelector('#photo-grid');
        
        if (loading) loading.style.display = show ? 'flex' : 'none';
        if (grid) grid.style.opacity = show ? '0.5' : '1';
    }
    
    showNoPhotos() {
        const grid = this.container.querySelector('#photo-grid');
        if (grid) {
            grid.innerHTML = `
                <div class="no-photos-message" style="grid-column: 1 / -1;">
                    <i>📷</i>
                    <div>No photos found</div>
                    <p style="font-size: 14px; margin-top: 10px;">
                        This might mean no photos matched the taxonomy criteria or 
                        the photos weren't successfully extracted from the backup.
                    </p>
                </div>
            `;
        }
    }
    
    showNoSearchResults() {
        const grid = this.container.querySelector('#photo-grid');
        if (grid) {
            grid.innerHTML = `
                <div class="no-photos-message" style="grid-column: 1 / -1;">
                    <i>🔍</i>
                    <div>No photos match your search</div>
                    <p style="font-size: 14px; margin-top: 10px;">
                        Try adjusting your search terms or <button onclick="this.closest('.photo-gallery-container').querySelector('#gallery-search').value=''; this.closest('.photo-gallery-container').querySelector('#gallery-search').dispatchEvent(new Event('input'));" style="background: none; border: none; color: #007bff; text-decoration: underline; cursor: pointer; font-size: inherit;">clear the search</button> to see all photos.
                    </p>
                </div>
            `;
        }
    }
    
    showError(message) {
        const grid = this.container.querySelector('#photo-grid');
        if (grid) {
            grid.innerHTML = `
                <div class="no-photos-message" style="grid-column: 1 / -1;">
                    <i>⚠️</i>
                    <div>Error loading photos</div>
                    <p style="font-size: 14px; margin-top: 10px;">${message}</p>
                </div>
            `;
        }
    }
}

// Export for use in other modules
window.PhotoGallery = PhotoGallery;
