from customtkinter import CTkFrame, CTkButton, CTkLabel, CTkEntry, CTkProgressBar
import logging
import os

class BackupFrame(CTkFrame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.create_widgets()

    def create_widgets(self):
        self.label = CTkLabel(self, text="iOS Backup Manager")
        self.label.pack(pady=10)

        info_label = CTkLabel(self, text="📱 Creates encrypted iOS device backup\nCase number and output directory are set in the main app header")
        info_label.pack(pady=10)

        self.backup_button = CTkButton(self, text="Start iOS Backup", command=self.start_backup, height=40)
        self.backup_button.pack(pady=20)

        self.progress_bar = CTkProgressBar(self)
        self.progress_bar.pack(pady=10, padx=20, fill="x")

        self.status_label = CTkLabel(self, text="Ready to start backup")
        self.status_label.pack(pady=5)

    def start_backup(self):
        """Start iOS device backup using centralized case management"""
        # Get case number and output directory from main app
        main_app = self.winfo_toplevel()
        
        case_number = ""
        output_dir = ""
        
        if hasattr(main_app, 'get_case_number'):
            case_number = main_app.get_case_number()
        if hasattr(main_app, 'get_output_directory'):
            output_dir = main_app.get_output_directory()
        
        if not case_number:
            self.status_label.configure(text="❌ Please enter a case number in the header")
            return
            
        if not output_dir:
            self.status_label.configure(text="❌ Please select an output directory in the header")
            return
        
        # Create case-specific backup folder
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        case_backup_folder = os.path.join(output_dir, f"iOS_Backup_{case_number}_{timestamp}")
        
        try:
            os.makedirs(case_backup_folder, exist_ok=True)
        except Exception as e:
            self.status_label.configure(text=f"❌ Could not create backup folder: {e}")
            return
            
        # Clear previous status and reset progress
        self.status_label.configure(text=f"📱 Starting backup for case {case_number}...")
        self.progress_bar.set(0)
        
        # Disable backup button during backup
        self.backup_button.configure(state="disabled", text="Backup in Progress...")
            
        def backup_thread():
            try:
                from src.backup.device_backup import initiate_backup
                import threading
                
                # Track last progress to avoid spam
                last_progress = -1
                last_status = ""
                
                # Create thread-safe callback functions
                def status_callback(message):
                    nonlocal last_status
                    # Only update if status actually changed
                    if message != last_status:
                        last_status = message
                        # Schedule GUI update on main thread
                        self.after(0, lambda msg=message: self._update_status(msg))
                
                def progress_callback(progress_value):
                    nonlocal last_progress
                    # Only update progress if it changed by at least 5% or reached 100%
                    progress_percent = int(progress_value * 100)
                    if progress_percent >= 100 or progress_percent - last_progress >= 5:
                        last_progress = progress_percent
                        # Schedule GUI update on main thread  
                        self.after(0, lambda val=progress_value: self.progress_bar.set(val))
                
                # Call the backup function using pymobiledevice3
                success = initiate_backup(
                    path=case_backup_folder,
                    status_callback=status_callback,
                    progress_callback=progress_callback
                )
                
                # Schedule final completion update
                if success:
                    self.after(0, lambda: self._backup_complete(case_backup_folder))
                else:
                    self.after(0, lambda: self._backup_failed())
                
            except Exception as e:
                import traceback
                error_msg = f"Backup failed: {str(e)}"
                self.after(0, lambda: self._backup_error(error_msg))
        
        # Start backup in background thread
        import threading
        threading.Thread(target=backup_thread, daemon=True).start()

    def _update_status(self, message):
        """Update status with improved formatting"""
        # Clean up repetitive messages and make them more user-friendly
        if "Backup progress:" in message:
            # Skip the detailed backup progress messages since we have a progress bar
            return
        elif "Progress:" in message and "%" in message:
            # Skip the duplicate progress messages
            return
        elif "Device connected" in message:
            self.status_label.configure(text="✅ iOS device connected")
        elif "Getting device information" in message:
            self.status_label.configure(text="📱 Reading device information...")
        elif "Setting backup password" in message:
            self.status_label.configure(text="🔐 Configuring backup encryption...")
        elif "backup password was previously set" in message:
            self.status_label.configure(text="🔐 Using existing backup password")
        elif "Starting iOS backup" in message:
            self.status_label.configure(text="💾 Creating device backup...")
        elif "completed successfully" in message:
            self.status_label.configure(text="✅ Backup phase completed")
        elif "Collecting iOS logs" in message:
            self.status_label.configure(text="📋 Collecting system logs...")
        elif "Creating backup archive" in message:
            self.status_label.configure(text="📦 Creating backup archive...")
        elif "Creating backup hash" in message:
            self.status_label.configure(text="🔍 Generating backup verification hash...")
        elif "Creating log archive" in message:
            self.status_label.configure(text="📦 Creating log archive...")
        elif "Creating device report" in message:
            self.status_label.configure(text="📄 Generating device report...")
        elif "Backup process completed" in message:
            self.status_label.configure(text="🎉 All backup tasks completed")
        else:
            # For other messages, display as-is but limit length
            display_msg = message[:80] + "..." if len(message) > 80 else message
            self.status_label.configure(text=display_msg)

    def _backup_complete(self, backup_folder):
        """Handle successful backup completion"""
        self.status_label.configure(text=f"✅ Backup completed! Saved to: {os.path.basename(backup_folder)}")
        self.backup_button.configure(state="normal", text="Start iOS Backup")
        self.progress_bar.set(1.0)
        
    def _backup_failed(self):
        """Handle backup failure"""
        self.status_label.configure(text="❌ Backup failed!")
        self.backup_button.configure(state="normal", text="Start iOS Backup")
        
    def _backup_error(self, error_msg):
        """Handle backup error"""
        self.status_label.configure(text=f"❌ Error: {error_msg}")
        self.backup_button.configure(state="normal", text="Start iOS Backup")