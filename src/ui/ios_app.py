import os
import tkinter as tk
from tkinter import filedialog, messagebox
import tkinter.ttk as ttk  # For Treeview widgets
import customtkinter as ctk
import threading
import logging
import webbrowser
# Delay import of device backup to avoid auto-detection issues
# from src.backup.device_backup import initiate_backup
from src.parser.backup_parser import parse_backup, parse_ios_backup  # Import the class
from PIL import Image, ImageTk
from PIL.ExifTags import TAGS
import re
import subprocess
import platform
from tzlocal import get_localzone
from concurrent.futures import ThreadPoolExecutor
import datetime
import pytz
import pillow_heif

# Define GPS tags mapping
GPSTAGS = {
    0: "GPSVersionID",
    1: "GPSLatitudeRef",
    2: "GPSLatitude",
    3: "GPSLongitudeRef",
    4: "GPSLongitude",
    5: "GPSAltitudeRef",
    6: "GPSAltitude",
    7: "GPSTimeStamp",
    8: "GPSSatellites",
    9: "GPSStatus",
    10: "GPSMeasureMode",
    11: "GPSDOP",
    12: "GPSSpeedRef",
    13: "GPSSpeed",
    14: "GPSTrackRef",
    15: "GPSTrack",
    16: "GPSImgDirectionRef",
    17: "GPSImgDirection",
    18: "GPSMapDatum",
    19: "GPSDestLatitudeRef",
    20: "GPSDestLatitude",
    21: "GPSDestLongitudeRef",
    22: "GPSDestLongitude",
    23: "GPSDestBearingRef",
    24: "GPSDestBearing",
    25: "GPSDestDistanceRef",
    26: "GPSDestDistance",
    27: "GPSProcessingMethod",
    28: "GPSAreaInformation",
    29: "GPSDateStamp",
    30: "GPSDifferential"
}

# Configure CustomTkinter appearance
ctk.set_appearance_mode("System")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.timezone_preference = f"System Time ({get_localzone()})"
        # Configure window
        self.title("Arsenic Triage Tool - North Loop Consulting © 2025")
        self.geometry("1000x750")  # More compact window size
        self.minsize(900, 600)
        
        # Configure logging
        logging.basicConfig(level=logging.INFO, 
                           format='%(asctime)s - %(levelname)s - %(message)s')
        
        # Create the UI
        self.create_widgets()
        
        # Flag to track if device refresh has been triggered
        self._device_refresh_triggered = False
    
    def create_widgets(self):
        # Create header frame first
        header_frame = ctk.CTkFrame(self)
        header_frame.pack(fill="x", padx=10, pady=(5, 0))
        
        # For now, skip the icon to avoid PIL image conflicts
        # Create logo label with text only
        logo_label = ctk.CTkLabel(header_frame, text="🔧", font=ctk.CTkFont(size=32))
        logo_label.pack(side="left", padx=10, pady=5)
        
        # Add title with larger, bold font
        title_font = ctk.CTkFont(size=20, weight="bold")
        title_label = ctk.CTkLabel(header_frame, 
                                  text="Arsenic v1.0 - Triage Tool", 
                                  font=title_font)
        title_label.pack(side="left", padx=10, pady=5)
        
        # Add back button to right side
        self.back_button = ctk.CTkButton(
            header_frame,
            text="← Back to Main",
            font=ctk.CTkFont(size=14),
            width=120,
            command=self.go_back_to_main
        )
        self.back_button.pack(side="right", padx=10, pady=5)
        
        # Create tabview
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        
        # Create tabs
        self.tab_backup = self.tabview.add("Backup")
        self.tab_parse = self.tabview.add("Parse Backup")
        
        # Setup each tab
        self.setup_backup_tab()
        self.setup_parse_tab()

        # Setup treeview sorting after all tabs are created
        # self.setup_treeview_sorting()  # Commented out for now to avoid missing widget errors
        
    def setup_backup_tab(self):
        # Create main container frame
        main_container = ctk.CTkFrame(self.tab_backup)
        main_container.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Create top frame for Device Info and Apps side by side with specific height
        self.top_frame = ctk.CTkFrame(main_container, height=300)
        self.top_frame.pack(fill="x", padx=5, pady=5)
        self.top_frame.pack_propagate(False)  # Maintain the specified height
        
        # Configure grid weights for equal distribution
        self.top_frame.grid_columnconfigure(0, weight=1)
        self.top_frame.grid_columnconfigure(1, weight=1)
        self.top_frame.grid_rowconfigure(0, weight=1)
        
        # Left pane for device info only - using grid
        self.device_pane = ctk.CTkFrame(self.top_frame)
        self.device_pane.grid(row=0, column=0, sticky="nsew", padx=(5, 2.5), pady=5)
        
        # Right pane for apps list only - using grid
        self.apps_pane = ctk.CTkFrame(self.top_frame)
        self.apps_pane.grid(row=0, column=1, sticky="nsew", padx=(2.5, 5), pady=5)
        
        # Create bottom frame for backup options and progress
        self.bottom_frame = ctk.CTkFrame(main_container)
        self.bottom_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Device info frame in device pane
        self.device_frame = ctk.CTkFrame(self.device_pane)
        self.device_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.device_label = ctk.CTkLabel(self.device_frame, 
                                        text="Device Information", 
                                        font=ctk.CTkFont(size=16, weight="bold"))
        self.device_label.pack(pady=5)
        
        self.device_status = ctk.CTkLabel(self.device_frame, text="Checking for device...")
        self.device_status.pack(pady=5)
        
        self.device_info_text = ctk.CTkTextbox(self.device_frame, height=150, wrap="word")
        self.device_info_text.pack(fill="both", expand=True, padx=10, pady=5)
        self.device_info_text.insert("0.0", "Connect an iOS device to view device information...")
        
        self.refresh_button = ctk.CTkButton(self.device_frame, 
                                           text="Refresh Device Info", 
                                           command=self.refresh_device_info)
        self.refresh_button.pack(pady=10)
        
        # Apps list frame in apps pane
        self.apps_frame = ctk.CTkFrame(self.apps_pane)
        self.apps_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.apps_label = ctk.CTkLabel(self.apps_frame, 
                                      text="Installed Applications", 
                                      font=ctk.CTkFont(size=16, weight="bold"))
        self.apps_label.pack(pady=5)
        
        # Search box for apps
        self.search_frame = ctk.CTkFrame(self.apps_frame)
        self.search_frame.pack(fill="x", padx=5, pady=5)
        
        self.search_label = ctk.CTkLabel(self.search_frame, text="Search:")
        self.search_label.pack(side="left", padx=5)
        
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.filter_apps_list)
        
        self.search_entry = ctk.CTkEntry(self.search_frame, textvariable=self.search_var)
        self.search_entry.pack(side="left", padx=5, fill="x", expand=True)
        
        # Apps count
        self.apps_count = ctk.CTkLabel(self.apps_frame, text="0 apps")
        self.apps_count.pack(pady=(5, 0))
        
        # Apps list with scrollbar
        self.apps_list_frame = ctk.CTkFrame(self.apps_frame)
        self.apps_list_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.apps_list = ctk.CTkTextbox(self.apps_list_frame)
        self.apps_list.pack(fill="both", expand=True, side="left")
        self.apps_list.insert("0.0", "No apps loaded. Connect device and click refresh to view installed applications.")
        
        # Store apps for filtering
        self.current_apps = []
        
        # Backup options frame in bottom frame
        self.options_frame = ctk.CTkFrame(self.bottom_frame)
        self.options_frame.pack(fill="x", padx=10, pady=5)
        
        self.options_label = ctk.CTkLabel(self.options_frame, 
                                         text="Backup Options", 
                                         font=ctk.CTkFont(size=16, weight="bold"))
        self.options_label.pack(pady=5)
        
        # Backup folder selection
        self.folder_frame = ctk.CTkFrame(self.options_frame)
        self.folder_frame.pack(fill="x", padx=10, pady=5)
        
        self.folder_label = ctk.CTkLabel(self.folder_frame, text="Backup Location:")
        self.folder_label.pack(side="left", padx=5)
        
        self.folder_path = ctk.CTkEntry(self.folder_frame, width=300)
        self.folder_path.pack(side="left", padx=5, fill="x", expand=True)
        
        self.browse_button = ctk.CTkButton(self.folder_frame, 
                                          text="Browse", 
                                          width=80,
                                          command=self.browse_folder)
        self.browse_button.pack(side="left", padx=5)
        
        # Backup logs option
        self.logs_var = tk.BooleanVar(value=True)
        self.logs_checkbox = ctk.CTkCheckBox(self.options_frame, 
                                            text="Include device logs", 
                                            variable=self.logs_var)
        self.logs_checkbox.pack(pady=5, anchor="w", padx=15)
        
        # Backup button
        self.backup_button = ctk.CTkButton(self.options_frame, 
                                          text="Start Backup", 
                                          font=ctk.CTkFont(size=14, weight="bold"),
                                          height=40,
                                          command=self.start_backup)
        self.backup_button.pack(pady=10)
        
        # Progress frame in bottom frame
        self.progress_frame = ctk.CTkFrame(self.bottom_frame)
        self.progress_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.progress_label = ctk.CTkLabel(self.progress_frame, 
                                          text="Status", 
                                          font=ctk.CTkFont(size=16, weight="bold"))
        self.progress_label.pack(pady=5)
        
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame)
        self.progress_bar.pack(fill="x", padx=10, pady=5)
        self.progress_bar.set(0)
        
        self.status_text = ctk.CTkTextbox(self.progress_frame, height=100, wrap="word")
        self.status_text.pack(fill="both", expand=True, padx=10, pady=5)
        self.status_text.insert("0.0", "Ready to start backup process...")
        
    def setup_parse_tab(self):
        """Set up the parse backup tab"""
        # Create a frame for the backup selection
        self.parse_top_frame = ctk.CTkFrame(self.tab_parse)
        self.parse_top_frame.pack(fill="x", padx=10, pady=5)
        
        # Configure grid to ensure proper spacing
        self.parse_top_frame.columnconfigure(1, weight=1)
        
        # Backup folder selection
        self.backup_folder_label = ctk.CTkLabel(self.parse_top_frame, text="Backup Location:")
        self.backup_folder_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        
        self.backup_folder_path = ctk.CTkEntry(self.parse_top_frame, width=400)
        self.backup_folder_path.grid(row=0, column=1, padx=5, pady=5, sticky="we")
        
        self.browse_backup_button = ctk.CTkButton(
            self.parse_top_frame, text="Browse", width=80, command=self.browse_backup_folder
        )
        self.browse_backup_button.grid(row=0, column=2, padx=5, pady=5)
        
        # Password field (hidden initially)
        self.password_label = ctk.CTkLabel(self.parse_top_frame, text="Backup Password:")
        self.password_entry = ctk.CTkEntry(self.parse_top_frame, width=400)
        
        # Output folder selection
        self.output_folder_label = ctk.CTkLabel(self.parse_top_frame, text="Output Location:")
        self.output_folder_label.grid(row=1, column=0, padx=5, pady=5, sticky="w")
        
        self.output_folder_path = ctk.CTkEntry(self.parse_top_frame, width=400)
        self.output_folder_path.grid(row=1, column=1, padx=5, pady=5, sticky="we")
        
        self.browse_output_button = ctk.CTkButton(
            self.parse_top_frame, text="Browse", width=80, 
            command=lambda: self.browse_output_folder()
        )
        self.browse_output_button.grid(row=1, column=2, padx=5, pady=5)
        
       
        self.controls_frame = ctk.CTkFrame(self.parse_top_frame)
        self.controls_frame.grid(row=2, column=0, columnspan=3, padx=5, pady=5, sticky="we")

        # Create left subframe for taxonomy options
        self.taxonomy_frame = ctk.CTkFrame(self.controls_frame, fg_color="transparent")
        self.taxonomy_frame.pack(side="left", fill="x", expand=True, padx=5, pady=5)

        # Create checkbox to enable/disable taxonomy search
        self.enable_taxonomy_var = tk.BooleanVar(value=False)
        self.enable_taxonomy_checkbox = ctk.CTkCheckBox(
            self.taxonomy_frame, 
            text="Filter photos by scene classification:", 
            variable=self.enable_taxonomy_var,
            command=self.toggle_taxonomy_dropdown
        )
        self.enable_taxonomy_checkbox.pack(side="left", padx=5, pady=5)

        # Create label for dropdown
        self.taxonomy_label = ctk.CTkLabel(self.taxonomy_frame, text="Scene type:")
        self.taxonomy_label.pack(side="left", padx=(10, 5), pady=5)

        # Create dropdown with taxonomy options
        self.taxonomy_var = tk.StringVar()
        self.taxonomy_dropdown = ctk.CTkOptionMenu(
            self.taxonomy_frame,
            values=self.get_taxonomy_options(),
            variable=self.taxonomy_var,
            state="disabled"  # Initially disabled
        )
        self.taxonomy_dropdown.pack(side="left", padx=5, pady=5)

        # Create right subframe for timezone options
        timezone_frame = ctk.CTkFrame(self.controls_frame, fg_color="transparent")
        timezone_frame.pack(side="right", fill="x", padx=5, pady=5)

        timezone_label = ctk.CTkLabel(timezone_frame, text="Display times in:")
        timezone_label.pack(side="left", padx=5, pady=5)

        # Default options - system timezone and UTC
        import pytz
        from tzlocal import get_localzone

        # Get system timezone
        system_tz = get_localzone()
        def get_utc_offset(timezone_str):
            if timezone_str == "UTC":
                return "+00:00"
            
            try:
                tz = pytz.timezone(timezone_str)
                now = datetime.datetime.now(tz)
                offset_str = now.strftime('%z')  # Format like '+0200' or '-0500'
                # Format more nicely as '+02:00' or '-05:00'
                return f"{offset_str[:3]}:{offset_str[3:]}"
            except:
                return ""

        system_offset = get_utc_offset(str(system_tz))
        # Create timezone options list and store as class attribute
        self.timezone_options = [
            (f"System Time ({system_tz})", system_offset),
            ("UTC", "+00:00"),
            ("America/Hawaii", get_utc_offset("Pacific/Honolulu")),       # -10:00
            ("America/Alaska", get_utc_offset("America/Anchorage")),      # -09:00
            ("America/Pacific", get_utc_offset("America/Los_Angeles")),   # -08:00 or -07:00
            ("America/Mountain", get_utc_offset("America/Denver")),       # -07:00 or -06:00
            ("America/Central", get_utc_offset("America/Chicago")),       # -06:00 or -05:00
            ("America/Eastern", get_utc_offset("America/New_York")),      # -05:00 or -04:00
            ("America/Bogota", get_utc_offset("America/Bogota")),         # -05:00
            ("America/Toronto", get_utc_offset("America/Toronto")),       # -05:00 or -04:00
            ("America/Lima", get_utc_offset("America/Lima")),             # -05:00
            ("America/Santiago", get_utc_offset("America/Santiago")),     # -04:00 or -03:00
            ("America/Sao_Paulo", get_utc_offset("America/Sao_Paulo")),   # -03:00
            ("America/Buenos_Aires", get_utc_offset("America/Argentina/Buenos_Aires")), # -03:00
            ("Europe/Reykjavik", get_utc_offset("Atlantic/Reykjavik")),   # +00:00
            ("Europe/London", get_utc_offset("Europe/London")),           # +00:00 or +01:00
            ("Europe/Berlin", get_utc_offset("Europe/Berlin")),           # +01:00 or +02:00
            ("Europe/Paris", get_utc_offset("Europe/Paris")),             # +01:00 or +02:00
            ("Europe/Madrid", get_utc_offset("Europe/Madrid")),           # +01:00 or +02:00
            ("Europe/Rome", get_utc_offset("Europe/Rome")),               # +01:00 or +02:00
            ("Europe/Amsterdam", get_utc_offset("Europe/Amsterdam")),     # +01:00 or +02:00
            ("Europe/Zurich", get_utc_offset("Europe/Zurich")),           # +01:00 or +02:00
            ("Europe/Kyiv", get_utc_offset("Europe/Kiev")),               # +02:00 or +03:00
            ("Africa/Lagos", get_utc_offset("Africa/Lagos")),             # +01:00
            ("Africa/Cairo", get_utc_offset("Africa/Cairo")),             # +02:00
            ("Africa/Johannesburg", get_utc_offset("Africa/Johannesburg")), # +02:00
            ("Africa/Nairobi", get_utc_offset("Africa/Nairobi")),         # +03:00
            ("Europe/Moscow", get_utc_offset("Europe/Moscow")),           # +03:00
            ("Asia/Dubai", get_utc_offset("Asia/Dubai")),                 # +04:00
            ("Asia/Kolkata", get_utc_offset("Asia/Kolkata")),             # +05:30
            ("Asia/Bangkok", get_utc_offset("Asia/Bangkok")),             # +07:00
            ("Asia/Singapore", get_utc_offset("Asia/Singapore")),         # +08:00
            ("Asia/Hong_Kong", get_utc_offset("Asia/Hong_Kong")),         # +08:00
            ("Asia/Shanghai", get_utc_offset("Asia/Shanghai")),           # +08:00
            ("Asia/Seoul", get_utc_offset("Asia/Seoul")),                 # +09:00
            ("Asia/Tokyo", get_utc_offset("Asia/Tokyo")),                 # +09:00
            ("Australia/Perth", get_utc_offset("Australia/Perth")),       # +08:00
            ("Australia/Sydney", get_utc_offset("Australia/Sydney")),     # +10:00 or +11:00
            ("Australia/Melbourne", get_utc_offset("Australia/Melbourne")), # +10:00 or +11:00
            ("Pacific/Auckland", get_utc_offset("Pacific/Auckland"))    # +12:00 or +13:00
        ]
        self.timezone_options = [f"{name} {offset}" for name, offset in self.timezone_options]

        self.timezone_var = tk.StringVar(value=self.timezone_options[0])  # Default to system time
        self.timezone_dropdown = ctk.CTkOptionMenu(
            timezone_frame,
            values=self.timezone_options,
            variable=self.timezone_var,
            command=self.update_timezone_preference
        )
        self.timezone_dropdown.pack(side="left", padx=5, pady=5)

        # Button frame with fixed height to prevent overlapping
        self.button_frame = ctk.CTkFrame(self.parse_top_frame, fg_color="transparent", height=50)
        self.button_frame.grid(row=3, column=0, columnspan=3, padx=5, pady=20, sticky="nswe")
        self.button_frame.grid_propagate(False)  # Prevent frame from shrinking to button size
        self.button_frame.columnconfigure(0, weight=1)  # Center the button
        
        self.parse_button = ctk.CTkButton(
            self.button_frame, text="Parse Backup", 
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40, width=200,
            command=self.start_parse
        )
        self.parse_button.grid(row=0, column=0, padx=5, pady=5)
        
        # Status message
        self.parse_status_label = ctk.CTkLabel(self.parse_top_frame, text="Status:")
        self.parse_status_label.grid(row=4, column=0, padx=5, pady=5, sticky="w")
        
        self.parse_status_text = ctk.CTkLabel(self.parse_top_frame, text="Ready")
        self.parse_status_text.grid(row=4, column=1, columnspan=2, padx=5, pady=5, sticky="w")
        
        # Results frame
        self.parse_results_frame = ctk.CTkFrame(self.tab_parse)
        self.parse_results_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Create the results tabview FIRST - this is the critical fix
        self.parse_results_tabview = ctk.CTkTabview(self.parse_results_frame)
        self.parse_results_tabview.pack(fill="both", expand=True)
        
        # Now create the tabs
        self.tab_device = self.parse_results_tabview.add("Device Info")
        self.tab_sms = self.parse_results_tabview.add("SMS Messages")
        self.tab_calls = self.parse_results_tabview.add("Call History")
        self.tab_interactions = self.parse_results_tabview.add("Interactions")  
        self.tab_safari = self.parse_results_tabview.add("Safari History")  
        self.tab_contacts = self.parse_results_tabview.add("Contacts")
        self.tab_data_usage = self.parse_results_tabview.add("Data Usage")
        self.tab_accounts = self.parse_results_tabview.add("Accounts")
        self.tab_permissions = self.parse_results_tabview.add("App Permissions")
        self.tab_notes = self.parse_results_tabview.add("Notes")
        self.tab_photos = self.parse_results_tabview.add("Photos")  
        
        # Set up individual content areas - call these AFTER creating tabs
        self.setup_device_info()
        self.setup_sms_table()
        self.setup_calls_table()
        self.setup_contacts_table()
        self.setup_data_usage_table()
        self.setup_accounts_table()
        self.setup_permissions_table()
        self.setup_photos_table()
        self.setup_notes_table()
        self.setup_interactions_table()
        self.setup_safari_table()
        
        
    def browse_folder(self):
        """Open folder browser dialog"""
        folder_path = filedialog.askdirectory()
        if folder_path:
            self.folder_path.delete(0, "end")
            self.folder_path.insert(0, folder_path)
            
    def browse_backup_folder(self):
        """Open folder browser dialog for backup selection"""
        folder_path = filedialog.askdirectory()
        if folder_path:
            self.backup_folder_path.delete(0, "end")
            self.backup_folder_path.insert(0, folder_path)
            
            # Check if backup is encrypted and show/hide password field accordingly
            is_encrypted = self.is_backup_encrypted(folder_path)
            self.toggle_password_field(is_encrypted)
            
            if is_encrypted:
                self.update_parse_status("Encrypted backup detected. Please enter password.")
            else:
                self.update_parse_status("Unencrypted backup selected.")
            
    def update_status(self, message):
        """Update status text in the backup tab"""
        self.status_text.insert("end", f"{message}\n")
        self.status_text.see("end")
        
    def update_progress(self, value):
        """Update progress bar"""
        self.progress_bar.set(value / 100)
        
    def refresh_device_info(self):
        """Get information about connected device"""
        print("DEBUG: refresh_device_info called")
        # Don't start if we're not properly initialized
        try:
            if not self.winfo_exists():
                print("DEBUG: Window doesn't exist, returning")
                return
        except:
            print("DEBUG: Exception checking window existence, returning")
            return
            
        self.device_info_text.delete("1.0", "end")
        self.device_status.configure(text="Checking for connected devices...")
        self.apps_list.delete("1.0", "end")
        self.apps_count.configure(text="0 apps")
        self.current_apps = []
        
        print("DEBUG: Starting device info thread")
        
        def get_info():
            print("DEBUG: get_info thread started")
            try:
                from src.backup.device_backup import DeviceBackup
                backup = DeviceBackup()
                
                print("DEBUG: Created DeviceBackup instance")
                
                if backup.connect_device():
                    print("DEBUG: Device connected, getting info")
                    device_info = backup.get_device_info()
                    print(f"DEBUG: Got device info: {bool(device_info)}")
                    
                    # Update UI in main thread - but only if window still exists
                    try:
                        if hasattr(self, 'winfo_exists'):
                            print("DEBUG: Scheduling GUI update")
                            self.after(0, lambda: self._safe_update_device_info(device_info))
                    except Exception as e:
                        print(f"DEBUG: Exception scheduling GUI update: {e}")
                else:
                    print("DEBUG: Device connection failed")
                    try:
                        if hasattr(self, 'winfo_exists'):
                            self.after(0, lambda: self._safe_update_no_device())
                    except:
                        pass  # Window was destroyed
            except Exception as e:
                print(f"Error in device info thread: {e}")
                import traceback
                traceback.print_exc()
                try:
                    if hasattr(self, 'winfo_exists'):
                        self.after(0, lambda: self._safe_update_error())
                except:
                    pass  # Window was destroyed
        
        # Run in thread to prevent UI freezing
        threading.Thread(target=get_info, daemon=True).start()
        
    def _safe_update_device_info(self, device_info):
        """Safely update device info in UI"""
        try:
            print(f"DEBUG: _safe_update_device_info called with device_info: {bool(device_info)}")
            if self.winfo_exists():
                print("DEBUG: Window exists, calling _update_device_info")
                self._update_device_info(device_info)
            else:
                print("DEBUG: Window does not exist")
        except Exception as e:
            print(f"DEBUG: Exception in _safe_update_device_info: {e}")
            
    def _safe_update_no_device(self):
        """Safely update no device status"""
        try:
            if self.winfo_exists():
                self.device_status.configure(text="No device connected")
        except:
            pass  # Window was destroyed
            
    def _safe_update_error(self):
        """Safely update error status"""
        try:
            if self.winfo_exists():
                self.device_status.configure(text="Error checking device")
        except:
            pass  # Window was destroyed
        
    def _update_device_info(self, device_info):
        """Update device info in the UI"""
        print(f"DEBUG: _update_device_info called with device_info: {bool(device_info)}")
        if device_info:
            print(f"DEBUG: Device info keys: {list(device_info.keys()) if isinstance(device_info, dict) else 'Not a dict'}")
            self.device_status.configure(text="Device connected")
            
            # Format device info (basic info only)
            info_text = f"Device: {device_info.get('Device Model', 'Unknown')}\n"
            info_text += f"Name: {device_info.get('Device Name', 'Unknown')}\n"
            info_text += f"iOS Version: {device_info.get('iOS Version', 'Unknown')}\n"
            info_text += f"Serial Number: {device_info.get('Serial Number', 'Unknown')}\n"
            info_text += f"IMEI: {device_info.get('IMEI', 'Unknown')}\n"
            
            print(f"DEBUG: Formatted info text: {info_text}")
            
            # Clear existing text and insert new info
            self.device_info_text.delete("1.0", "end")
            self.device_info_text.insert("1.0", info_text)
            
            print("DEBUG: Device info text updated")
            
            # Update apps list separately
            apps = device_info.get('Installed Applications', [])
            self.current_apps = apps
            if apps:
                # Update apps count
                self.apps_count.configure(text=f"{len(apps)} applications")
                print(f"DEBUG: Found {len(apps)} applications")
                
                # Display apps in the list
                self.update_apps_list(apps)
            else:
                print("DEBUG: No applications found in device_info")
                self.apps_list.insert("1.0", "No applications found")
                self.apps_count.configure(text="0 applications")
        else:
            print("DEBUG: No device info provided")
            self.device_status.configure(text="Failed to get device information")
            
    def update_apps_list(self, apps):
        """Update the apps list with the given apps"""
        self.apps_list.delete("1.0", "end")
        for app in sorted(apps):
            self.apps_list.insert("end", f"• {app}\n")
            
    def filter_apps_list(self, *args):
        """Filter the apps list based on search text"""
        search_text = self.search_var.get().lower()
        if not self.current_apps:
            return
            
        if search_text:
            filtered_apps = [app for app in self.current_apps if search_text in app.lower()]
            self.update_apps_list(filtered_apps)
            self.apps_count.configure(text=f"{len(filtered_apps)} of {len(self.current_apps)} applications")
        else:
            self.update_apps_list(self.current_apps)
            self.apps_count.configure(text=f"{len(self.current_apps)} applications")

    def update_timezone_preference(self, selected_timezone):
        """Update the application's timezone preference"""
        self.timezone_preference = selected_timezone
        
        # If we have any displayed data, refresh it with the new timezone
        if hasattr(self, 'parse_results') and self.parse_results:
            self.refresh_displayed_timestamps()

    def refresh_displayed_timestamps(self):
        """Refresh all displayed data with the current timezone"""
        # Re-filter all data with new timezone settings
        if hasattr(self, 'sms_data') and self.sms_data:
            self.filter_sms_results(self.sms_search_entry.get())
        
        if hasattr(self, 'calls_data') and self.calls_data:
            self.filter_call_results(self.calls_search_entry.get())
        
        if hasattr(self, 'safari_data') and self.safari_data:
            self.filter_safari_results(self.safari_search_entry.get())
        
        if hasattr(self, 'contacts_data') and self.contacts_data:
            self.filter_contacts_results(self.contacts_search_entry.get())
        
        if hasattr(self, 'data_usage_data') and self.data_usage_data:   
            self.filter_data_usage_results(self.data_usage_search_entry.get())
            
        if hasattr(self, 'accounts_data') and self.accounts_data:
            self.filter_accounts_results(self.accounts_search_entry.get())
            
        if hasattr(self, 'permissions_data') and self.permissions_data:
            self.filter_permissions_results(self.permissions_search_entry.get())
            
        if hasattr(self, 'notes_data') and self.notes_data:
            self.filter_notes_results(self.notes_search_entry.get())
            
        if hasattr(self, 'photos_data') and self.photos_data:
            self.filter_photos_results(self.photos_search_entry.get())
            
        if hasattr(self, 'interactions_data') and self.interactions_data:
            self.filter_interactions_results(self.interactions_search_entry.get())
        
        self.update_parse_status(f"Updated displayed times to {self.timezone_preference}")

    def convert_timestamp(self, timestamp_str):
        """Convert a timestamp string from UTC to the selected timezone"""
        import datetime
        import pytz
        from tzlocal import get_localzone
        
        if not timestamp_str:
            return timestamp_str
        
        # Make sure we have the timezone preference
        if not hasattr(self, 'timezone_preference') or not self.timezone_preference:
            from tzlocal import get_localzone
            self.timezone_preference = f"System Time ({get_localzone()})"
            print(f"Initialized timezone preference to {self.timezone_preference}")
        
        try:
            # Debug
            # print(f"Converting: '{timestamp_str}' to {self.timezone_preference}")
            
            # Handle different timestamp formats
            dt_utc = None
            formats_to_try = [
                "%Y-%m-%d %H:%M:%S UTC",  # Format with UTC suffix
                "%Y-%m-%d %H:%M:%S",      # Format without timezone
            ]
            
            for fmt in formats_to_try:
                try:
                    if "UTC" in fmt:
                        dt_utc = datetime.datetime.strptime(timestamp_str.strip(), fmt)
                        dt_utc = dt_utc.replace(tzinfo=pytz.UTC)
                        break
                    else:
                        # For formats without explicit timezone
                        dt_utc = datetime.datetime.strptime(timestamp_str.strip(), fmt)
                        dt_utc = dt_utc.replace(tzinfo=pytz.UTC)
                        break
                except ValueError:
                    continue
            
            if not dt_utc:
                print(f"Failed to parse timestamp: {timestamp_str}")
                return timestamp_str
            
            # Convert to selected timezone with consistent format
            timezone_format = "%Y-%m-%d %H:%M:%S (%Z)"
            
            if self.timezone_preference.startswith("System Time"):
                local_tz = get_localzone()
                dt_local = dt_utc.astimezone(local_tz)
                return dt_local.strftime(timezone_format)
            elif self.timezone_preference == "UTC":
                return dt_utc.strftime(timezone_format)  # Always show (UTC)
            else:
                target_tz = pytz.timezone(self.timezone_preference)
                dt_target = dt_utc.astimezone(target_tz)
                return dt_target.strftime(timezone_format)
        except Exception as e:
            print(f"Error converting timestamp '{timestamp_str}': {e}")
            return timestamp_str

    
        
        # Run backup in a thread
    def start_backup(self):
        """Start iOS device backup"""
        folder_path = self.folder_path.get()  # Changed from self.ios_folder_path
        if not folder_path:
            self.status_text.insert("end", "Please select a backup destination folder.\n")  # Changed from self.ios_status_text
            return
            
        # Clear previous status and reset progress
        self.status_text.delete("1.0", "end")  # Changed from self.ios_status_text
        self.progress_bar.set(0)  # Changed from self.ios_progress_bar
        self.status_text.insert("end", f"Starting backup to: {folder_path}\n")  # Changed from self.ios_status_text
        
        # Disable backup button during backup
        self.backup_button.configure(state="disabled", text="Backup in Progress...")
            
        def backup_thread():
            try:
                from src.backup.device_backup import initiate_backup
                
                # Create thread-safe callback functions
                def status_callback(message):
                    # Schedule GUI update on main thread
                    self.after(0, lambda msg=message: self._update_ios_backup_status(msg))
                
                def progress_callback(progress_value):
                    # Schedule GUI update on main thread  
                    self.after(0, lambda val=progress_value: self._update_ios_backup_progress(val))
                
                # Call the backup function with callbacks
                success = initiate_backup(
                    path=folder_path,
                    status_callback=status_callback,
                    progress_callback=progress_callback
                )
                
                # Schedule final completion update
                self.after(0, lambda: self._ios_backup_complete(success, self.backup_button))
                
            except Exception as e:
                import traceback
                error_msg = f"Backup failed with error: {str(e)}\n{traceback.format_exc()}"
                self.after(0, lambda: self._ios_backup_error(error_msg, self.backup_button))
        
        # Start backup in background thread
        threading.Thread(target=backup_thread, daemon=True).start()

    def _update_ios_backup_status(self, message):
        """Update backup status text (called from main thread)"""
        try:
            self.status_text.insert("end", f"{message}\n")  # Changed from self.ios_status_text
            self.status_text.see("end")  # Scroll to bottom
        except Exception as e:
            print(f"Error updating iOS backup status: {e}")

    def _update_ios_backup_progress(self, progress_value):
        """Update backup progress bar (called from main thread)"""
        try:
            # Ensure progress value is between 0 and 1
            if progress_value > 1:
                progress_value = progress_value / 100.0
            
            self.progress_bar.set(progress_value)  # Changed from self.ios_progress_bar
            
            # Also update status text with percentage
            percentage = int(progress_value * 100)
            self.status_text.insert("end", f"Progress: {percentage}%\n")  # Changed from self.ios_status_text
            self.status_text.see("end")
        except Exception as e:
            print(f"Error updating iOS backup progress: {e}")

    def _ios_backup_complete(self, success, backup_button):
        """Handle backup completion (called from main thread)"""
        try:
            if success:
                self.status_text.insert("end", "✅ Backup completed successfully!\n")  # Changed from self.ios_status_text
                self.progress_bar.set(1.0)  # Changed from self.ios_progress_bar
            else:
                self.status_text.insert("end", "❌ Backup failed!\n")  # Changed from self.ios_status_text
            
            self.status_text.see("end")  # Changed from self.ios_status_text
            
            # Re-enable backup button
            if backup_button:
                backup_button.configure(state="normal", text="Start Backup")  # Changed text
                
        except Exception as e:
            print(f"Error in backup completion: {e}")

    def _ios_backup_error(self, error_msg, backup_button):
        """Handle backup error (called from main thread)"""
        try:
            self.status_text.insert("end", f"❌ {error_msg}\n")  # Changed from self.ios_status_text
            self.status_text.see("end")  # Changed from self.ios_status_text
            
            # Re-enable backup button
            if backup_button:
                backup_button.configure(state="normal", text="Start Backup")  # Changed text
                
        except Exception as e:
            print(f"Error handling backup error: {e}")

    def start_parse(self):
        """Start parsing an iOS backup"""
        backup_path = self.backup_folder_path.get()
        if not backup_path or not os.path.exists(backup_path):
            messagebox.showerror("Error", "Please select a valid backup folder")
            return
        
        password = self.password_entry.get()
        
        # Get output directory if specified
        output_dir = self.output_folder_path.get() if hasattr(self, 'output_folder_path') else None
        
        # Get taxonomy search settings
        taxonomy_target = None
        if hasattr(self, 'enable_taxonomy_var') and self.enable_taxonomy_var.get():
            taxonomy_target = self.taxonomy_var.get()
            print("TAXONOMY TARGET = " + taxonomy_target)
        
        timezone_preference = self.timezone_var.get() if hasattr(self, 'timezone_var') else None


        # Update status
        self.update_parse_status("Starting parsing process...")
        
        # Run parsing in a separate thread to avoid freezing UI
        def run_parsing():
            try:
                from src.parser.backup_parser import parse_backup
                results = parse_backup(
                    backup_path=backup_path, 
                    password=password, 
                    status_callback=self.update_parse_status, 
                    output_dir=output_dir,
                    taxonomy_target=taxonomy_target,
                    timezone=self.timezone_preference
                )
                
                # Update UI with results on the main thread
                self.after(100, lambda: self.display_parse_results(results))
            except Exception as e:
                import traceback
                error_message = f"Error parsing backup: {e}\n\n"
                error_details = traceback.format_exc()
                full_error = error_message + error_details
                
                # Log the full error
                print(f"PARSING ERROR: {full_error}")
                
                # Display a shorter message in the UI
                self.after(100, lambda m=error_message: self.update_parse_status(m))
        
        import threading
        threading.Thread(target=run_parsing).start()

    def display_parse_results(self, results):
        """Display parsed results in the GUI tables"""
        # Enable the text widget for editing
        self.device_result.configure(state="normal")
        
        # Clear previous content
        self.device_result.delete("1.0", tk.END)
        
        # Get device info
        device_info = results.get('device_info', {})
        
        if device_info:
            device_text = "Device Information:\n\n"
            for key, value in device_info.items():
                device_text += f"{key}: {value}\n"
            
            self.device_result.insert(tk.END, device_text)
        else:
            self.device_result.insert(tk.END, "No device information available in the backup.")
        
        # Disable the text widget again to make it read-only
        self.device_result.configure(state="disabled")
        
        # Store the data for filtering
        self.sms_data = results.get('sms_messages', [])
        self.calls_data = results.get('call_history', [])
        self.contacts_data = results.get('contacts', [])
        self.data_usage_data = results.get('data_usage', [])
        self.accounts_data = results.get('accounts', [])
        self.permissions_data = results.get('permissions', [])
        self.notes_data = results.get('notes', [])  
        self.photos_data = results.get('photo_analysis', [])
        self.interactions_data = results.get('interactions', [])
        self.safari_data = results.get('safari_history', [])

        # Debug print for contacts
        print(f"DEBUG: Contacts data length: {len(self.contacts_data)}")
        if len(self.contacts_data) > 0:
            print(f"DEBUG: First contact: {self.contacts_data[0]}")
            print(f"DEBUG: Contact data keys: {self.contacts_data[0].keys() if self.contacts_data else 'No contacts'}")

        # Populate SMS table
        self.filter_sms_results("")
        
        # Populate Call History table (implement similar methods for other data types)
        self.filter_call_results("")
        
        # Populate other tables...
        self.filter_contacts_results("")
        self.filter_data_usage_results("")
        self.filter_accounts_results("")
        self.filter_permissions_results("")
        self.filter_notes_results("")  # Add this line
        self.filter_photos_results("")
        self.filter_interactions_results("")
        self.filter_safari_results("") 
        
        # Show success message
        self.update_parse_status("Parsing complete! Results displayed in tabs.")
        
        # Handle photos display
        if hasattr(self, 'photos_data') or 'extracted_photos_path' in results:
            # Store extracted photos path for gallery functionality
            if 'extracted_photos_path' in results:
                self.extracted_photos_path = results['extracted_photos_path']
                
                # Enable the open folder button
                if hasattr(self, 'open_folder_button'):
                    self.open_folder_button.configure(state="normal")
            
            # Initialize gallery state if not already set
            if not hasattr(self, 'current_photo_view'):
                self.current_photo_view = "gallery"
                self.current_photos_page = 0
            
            # Initialize filtered photos
            self.filtered_photos = self.photos_data.copy() if hasattr(self, 'photos_data') and self.photos_data else []
            
            # Refresh the photos display with new data
            self.refresh_photos_display()

    def update_parse_status(self, message):
        """Update the status text in the parse tab"""
        self.parse_status_text.configure(text=message)
        # Force update of the UI
        self.update_idletasks()

    def browse_output_folder(self):
        """Open file dialog to select output folder"""
        folder_path = filedialog.askdirectory()
        if folder_path:
            self.output_folder_path.delete(0, tk.END)
            self.output_folder_path.insert(0, folder_path)

    def setup_sms_table(self):
        # Create frame for search controls
        search_frame = ctk.CTkFrame(self.tab_sms)
        search_frame.pack(fill="x", padx=10, pady=5)
        
        # Add search label and entry
        search_label = ctk.CTkLabel(search_frame, text="Search:")
        search_label.pack(side="left", padx=5, pady=5)
        
        self.sms_search_entry = ctk.CTkEntry(search_frame, width=250)
        self.sms_search_entry.pack(side="left", padx=5, pady=5, fill="x", expand=True)
        
        # Add search button
        search_button = ctk.CTkButton(
            search_frame, text="Search", 
            command=lambda: self.filter_sms_results(self.sms_search_entry.get())
        )
        search_button.pack(side="left", padx=5, pady=5)
        
        # Add clear button
        clear_button = ctk.CTkButton(
            search_frame, text="Clear", 
            command=lambda: [self.sms_search_entry.delete(0, tk.END), self.filter_sms_results("")]
        )
        clear_button.pack(side="left", padx=5, pady=5)
        
        # Create a master frame to hold both the table and message display
        master_frame = ctk.CTkFrame(self.tab_sms)
        master_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Create frame for table (now in the top portion)
        table_frame = ctk.CTkFrame(master_frame)
        table_frame.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Create Treeview for SMS
        self.sms_tree = ttk.Treeview(table_frame)
        
        # Define columns
        self.sms_tree["columns"] = ("date", "direction", "contact", "service", "message", "attachment")
        
        # Format columns
        self.sms_tree.column("#0", width=0, stretch=tk.NO)  # Hide the first column
        self.sms_tree.column("date", anchor=tk.W, width=150)
        self.sms_tree.column("direction", anchor=tk.W, width=80)
        self.sms_tree.column("contact", anchor=tk.W, width=120)
        self.sms_tree.column("service", anchor=tk.W, width=80)
        self.sms_tree.column("message", anchor=tk.W, width=300)
        self.sms_tree.column("attachment", anchor=tk.W, width=120)
        
        # Create headings
        self.sms_tree.heading("#0", text="", anchor=tk.W)
        self.sms_tree.heading("date", text="Date", anchor=tk.W)
        self.sms_tree.heading("direction", text="Direction", anchor=tk.W)
        self.sms_tree.heading("contact", text="Contact", anchor=tk.W)
        self.sms_tree.heading("service", text="Service", anchor=tk.W)
        self.sms_tree.heading("message", text="Message", anchor=tk.W)
        self.sms_tree.heading("attachment", text="Attachment", anchor=tk.W)
        
        # Add scrollbars for the table
        y_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.sms_tree.yview)
        x_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.sms_tree.xview)
        self.sms_tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
        
        # Pack table components
        y_scrollbar.pack(side="right", fill="y")
        x_scrollbar.pack(side="bottom", fill="x")
        self.sms_tree.pack(fill="both", expand=True)
        
        # Create a separator
        separator = ttk.Separator(master_frame, orient='horizontal')
        separator.pack(fill='x', pady=5)
        
        # Create a label for the message display
        msg_label = ctk.CTkLabel(master_frame, text="Selected Message Content:", anchor="w")
        msg_label.pack(fill="x", padx=5, pady=(5,0))
        
        # Create frame for message display
        message_frame = ctk.CTkFrame(master_frame)
        message_frame.pack(fill="both", expand=False, padx=0, pady=5, ipady=70)  # Give it some height with ipady
        
        # Create Text widget for displaying the full message with word wrap
        self.sms_message_display = ctk.CTkTextbox(message_frame, wrap="word", height=80)
        self.sms_message_display.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Bind selection event to update message display
        self.sms_tree.bind("<<TreeviewSelect>>", self.update_sms_message_display)

    def filter_sms_results(self, search_term):
        """Filter SMS results based on search term"""
        # Clear the tree
        for item in self.sms_tree.get_children():
            self.sms_tree.delete(item)
        
        # Configure tags for coloring
        self.sms_tree.tag_configure('incoming', background='#e6f2ff')  # Light blue for incoming
        self.sms_tree.tag_configure('outgoing', background='#f0f0f0')  # Light gray for outgoing
        
        # If we have SMS data
        if hasattr(self, 'sms_data') and self.sms_data:
            # Debug first few messages
            print(f"Total SMS records: {len(self.sms_data)}")
            for i, msg in enumerate(self.sms_data[:3]):  # Print first 3 for debugging
                # print(f"Debug SMS {i} keys: {msg.keys()}")
                # print(f"Debug SMS {i} values: {msg}")
                print("SMS is being filtered")
                
            search_term = search_term.lower()
            
            # Add filtered items
            for i, msg in enumerate(self.sms_data):
                # Get attachment data with better detection
                attachment = ""
    
                # First check if we have an attachment count > 0
                if 'Attachment Count' in msg and msg['Attachment Count'] and int(float(str(msg['Attachment Count']).replace(',', ''))) > 0:
                    attachment_count = int(float(str(msg['Attachment Count']).replace(',', '')))
    
                    # If we have names, show them
                    if 'Attachment Names' in msg and msg['Attachment Names']:
                        attachment = f"{attachment_count} file(s): {msg['Attachment Names']}"
                    # Otherwise just show the count
                    else:
                        attachment = f"{attachment_count} attachment(s)"
                # Fall back to other attachment fields
                elif 'Attachment Names' in msg and msg['Attachment Names']:
                    attachment = msg['Attachment Names']
                elif 'Attachment Files' in msg and msg['Attachment Files']:
                    attachment = msg['Attachment Files']
                elif 'attachment' in msg and msg['attachment']:
                    attachment = msg['attachment']
                
                # Fix service display
                service = msg.get('service', '')
                if not service or service == 'None':
                    if 'direction' in msg and msg['direction'] == 'Sent':
                        service = 'iMessage'  # Default for sent messages
                    elif 'Message Service' in msg:
                        service = msg['Message Service']
                
                # Check if search term exists in any field
                if (search_term in str(msg.get('date', '')).lower() or
                    search_term in str(msg.get('direction', '')).lower() or
                    search_term in str(msg.get('phone_number', '')).lower() or
                    search_term in str(service).lower() or
                    search_term in str(msg.get('message', '')).lower() or
                    search_term in str(attachment).lower()):
                    
                    # Get message content with combined text
                    message = msg.get('message', '')
                    if not message:
                        # Try other possible field names
                        if 'Sent' in msg and msg['Sent']:
                            message = msg['Sent']
                        elif 'Received' in msg and msg['Received']:
                            message = msg['Received']
                    date_display = self.convert_timestamp(msg.get('date', ''))
        
                    values = (
                        date_display,  # Now timezone-adjusted
                        msg.get('direction', ''),
                        msg.get('phone_number', ''),
                        service,  # Use the fixed service
                        message,
                        attachment  # Use the found attachment value
                    )
                    
                    item_id = self.sms_tree.insert("", "end", text=i, values=values)
                    
                    # Apply color based on direction
                    direction = msg.get('direction', '').lower()
                    if 'received' in direction:
                        self.sms_tree.item(item_id, tags=('incoming',))
                    elif 'sent' in direction:
                        self.sms_tree.item(item_id, tags=('outgoing',))

    def setup_calls_table(self):
        """Set up the call history table with search functionality"""
        # Create frame for search controls
        search_frame = ctk.CTkFrame(self.tab_calls)
        search_frame.pack(fill="x", padx=10, pady=5)
        
        # Add search label and entry
        search_label = ctk.CTkLabel(search_frame, text="Search:")
        search_label.pack(side="left", padx=5, pady=5)
        
        self.calls_search_entry = ctk.CTkEntry(search_frame, width=250)
        self.calls_search_entry.pack(side="left", padx=5, pady=5, fill="x", expand=True)
        
        # Add search button
        search_button = ctk.CTkButton(
            search_frame, text="Search", 
            command=lambda: self.filter_call_results(self.calls_search_entry.get())
        )
        search_button.pack(side="left", padx=5, pady=5)
        
        # Add clear button
        clear_button = ctk.CTkButton(
            search_frame, text="Clear", 
            command=lambda: [self.calls_search_entry.delete(0, tk.END), self.filter_call_results("")]
        )
        clear_button.pack(side="left", padx=5, pady=5)
        
        # Create frame for table
        table_frame = ctk.CTkFrame(self.tab_calls)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Create Treeview for call history
        self.calls_tree = ttk.Treeview(table_frame)
        
        # Define columns
        self.calls_tree["columns"] = ("date", "duration", "phone_number", "direction", "answered", "call_type")
        
        # Format columns
        self.calls_tree.column("#0", width=0, stretch=tk.NO)  # Hide the first column
        self.calls_tree.column("date", anchor=tk.W, width=150)
        self.calls_tree.column("duration", anchor=tk.W, width=80)
        self.calls_tree.column("phone_number", anchor=tk.W, width=150)
        self.calls_tree.column("direction", anchor=tk.W, width=100)
        self.calls_tree.column("answered", anchor=tk.W, width=80)
        self.calls_tree.column("call_type", anchor=tk.W, width=100)
        
        # Create headings
        self.calls_tree.heading("#0", text="", anchor=tk.W)
        self.calls_tree.heading("date", text="Date", anchor=tk.W)
        self.calls_tree.heading("duration", text="Duration", anchor=tk.W)
        self.calls_tree.heading("phone_number", text="Phone Number", anchor=tk.W)
        self.calls_tree.heading("direction", text="Direction", anchor=tk.W)
        self.calls_tree.heading("answered", text="Answered", anchor=tk.W)
        self.calls_tree.heading("call_type", text="Call Type", anchor=tk.W)
        
        # Configure tags for coloring
        self.calls_tree.tag_configure('incoming', background='#e6f2ff')  # Light blue for incoming
        self.calls_tree.tag_configure('outgoing', background='#f0f0f0')  # Light gray for outgoing
        
        # Add scrollbars
        y_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.calls_tree.yview)
        x_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.calls_tree.xview)
        self.calls_tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
        
        # Pack everything
        y_scrollbar.pack(side="right", fill="y")
        x_scrollbar.pack(side="bottom", fill="x")
        self.calls_tree.pack(fill="both", expand=True)

    def filter_call_results(self, search_term):
        """Filter call history results based on search term"""
        # Clear the tree
        for item in self.calls_tree.get_children():
            self.calls_tree.delete(item)
        
        # Configure tags for coloring
        self.calls_tree.tag_configure('incoming', background='#e6f2ff')  # Light blue for incoming
        self.calls_tree.tag_configure('outgoing', background='#f0f0f0')  # Light gray for outgoing
        
        # If we have call history data
        if hasattr(self, 'calls_data') and self.calls_data:
            search_term = search_term.lower()
            
            # Add filtered items
            for i, call in enumerate(self.calls_data):
                # Check if search term exists in any field
                if (search_term in str(call.get('date', '')).lower() or
                    search_term in str(call.get('duration', '')).lower() or
                    search_term in str(call.get('phone_number', '')).lower() or
                    search_term in str(call.get('direction', '')).lower() or
                    search_term in str(call.get('answered', '')).lower() or
                    search_term in str(call.get('call_type', '')).lower()):
                    
                    # Convert timestamp for display
                    date_display = self.convert_timestamp(call.get('date', ''))
                    
                    values = (
                        date_display,  # Now with timezone conversion
                        call.get('duration', ''),
                        call.get('phone_number', ''),
                        call.get('direction', ''),
                        call.get('answered', ''),
                        call.get('call_type', '')
                    )
                    
                    item_id = self.calls_tree.insert("", "end", text=i, values=values)
                    
                    # Apply color based on direction
                    direction = call.get('direction', '').lower()
                    if 'incoming' in direction:
                        self.calls_tree.item(item_id, tags=('incoming',))
                    elif 'outgoing' in direction:
                        self.calls_tree.item(item_id, tags=('outgoing',))

    def setup_safari_table(self):
        """Set up the Safari history table with search functionality"""
        # Create frame for search controls
        search_frame = ctk.CTkFrame(self.tab_safari)
        search_frame.pack(fill="x", padx=10, pady=5)
        
        # Add search label and entry
        search_label = ctk.CTkLabel(search_frame, text="Search:")
        search_label.pack(side="left", padx=5, pady=5)
        
        self.safari_search_entry = ctk.CTkEntry(search_frame, width=250)
        self.safari_search_entry.pack(side="left", padx=5, pady=5, fill="x", expand=True)
        
        # Add search button
        search_button = ctk.CTkButton(
            search_frame, text="Search", 
            command=lambda: self.filter_safari_results(self.safari_search_entry.get())
        )
        search_button.pack(side="left", padx=5, pady=5)
        
        # Add clear button
        clear_button = ctk.CTkButton(
            search_frame, text="Clear", 
            command=lambda: [self.safari_search_entry.delete(0, tk.END), self.filter_safari_results("")]
        )
        clear_button.pack(side="left", padx=5, pady=5)
        
        # Create frame for table
        table_frame = ctk.CTkFrame(self.tab_safari)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Create Treeview for Safari history
        self.safari_tree = ttk.Treeview(table_frame)
        
        # Define columns based on the expected data structure
        self.safari_tree["columns"] = ("date", "title", "url", "loaded", "visit_count")
        
        # Format columns
        self.safari_tree.column("#0", width=0, stretch=tk.NO)  # Hide the first column
        self.safari_tree.column("date", anchor=tk.W, width=150)
        self.safari_tree.column("title", anchor=tk.W, width=200)
        self.safari_tree.column("url", anchor=tk.W, width=300)
        self.safari_tree.column("loaded", anchor=tk.W, width=80)
        self.safari_tree.column("visit_count", anchor=tk.E, width=100)
        
        # Create headings
        self.safari_tree.heading("#0", text="", anchor=tk.W)
        self.safari_tree.heading("date", text="Date Visited", anchor=tk.W)
        self.safari_tree.heading("title", text="Page Title", anchor=tk.W)
        self.safari_tree.heading("url", text="URL", anchor=tk.W)
        self.safari_tree.heading("loaded", text="Page Loaded", anchor=tk.W)
        self.safari_tree.heading("visit_count", text="Visit Count", anchor=tk.E)
        
        # Add scrollbars
        y_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.safari_tree.yview)
        x_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.safari_tree.xview)
        self.safari_tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
        
        # Pack everything
        y_scrollbar.pack(side="right", fill="y")
        x_scrollbar.pack(side="bottom", fill="x")
        self.safari_tree.pack(fill="both", expand=True)
        
        # Bind double-click event to open URL
        self.safari_tree.bind("<Double-1>", self.open_safari_url)

    def filter_safari_results(self, search_term):
        """Filter Safari history results based on search term"""
        # Clear the tree
        for item in self.safari_tree.get_children():
            self.safari_tree.delete(item)
        
        # If we have Safari history data
        if hasattr(self, 'safari_data') and self.safari_data:
            # Debug the first few records to see what date fields are available
            if len(self.safari_data) > 0:
                print(f"Safari data sample keys: {list(self.safari_data[0].keys())}")
                for key in self.safari_data[0].keys():
                    if 'date' in key.lower() or 'time' in key.lower():
                        print(f"Potential date field: {key} = {self.safari_data[0][key]}")
            
            search_term = search_term.lower()
            
            # Add filtered items
            for i, history_item in enumerate(self.safari_data):
                # Check for various possible date keys 
                date_value = None
                for date_key in ['Date', 'date', 'Visit Date', 'visit_date', 'DateVisited', 'date_visited', 'Last Visited', 'last_visited', 'visit_time']:
                    if date_key in history_item:
                        date_value = history_item[date_key]
                        break
                
                # If date not found with known keys, try to find any key containing 'date'
                if not date_value:
                    for key in history_item.keys():
                        if 'date' in key.lower() or 'time' in key.lower():
                            date_value = history_item[key]
                            break
                
                # For debugging the raw date value
                if i < 3:  # Only print first 3 records to avoid console spam
                    print(f"Safari record {i} date value: '{date_value}'")
                
                # Check if search term exists in any field
                if (search_term in str(date_value).lower() or
                    search_term in str(history_item.get('Page Title', '')).lower() or
                    search_term in str(history_item.get('URL', '')).lower() or
                    search_term in str(history_item.get('Page Loaded', '')).lower() or
                    search_term in str(history_item.get('Total Visit Count', '')).lower()):
                    
                    # Convert date for display
                    date_display = self.convert_timestamp(date_value) if date_value else "Unknown Date"
                    
                    self.safari_tree.insert(
                        "", "end", text=i,
                        values=(
                            date_display,
                            history_item.get('Page Title', ''),
                            history_item.get('URL', ''),
                            history_item.get('Page Loaded', ''),
                            history_item.get('Total Visit Count', '')
                        )
                    )

    def open_safari_url(self, event):
        """Open the selected URL in the default web browser when double-clicked"""
        try:
            import webbrowser
            selected_items = self.safari_tree.selection()
            if selected_items:
                item = selected_items[0]
                url = self.safari_tree.item(item, "values")[2]  # URL is in the third column
                if url and url.startswith(("http://", "https://")):
                    webbrowser.open_new_tab(url)
        except Exception as e:
            self.update_parse_status(f"Error opening URL: {str(e)}")

    def setup_contacts_table(self):
        """Set up the contacts table with search functionality"""
        # Create frame for search controls
        search_frame = ctk.CTkFrame(self.tab_contacts)
        search_frame.pack(fill="x", padx=10, pady=5)
        
        # Add search label and entry
        search_label = ctk.CTkLabel(search_frame, text="Search:")
        search_label.pack(side="left", padx=5, pady=5)
        
        self.contacts_search_entry = ctk.CTkEntry(search_frame, width=250)
        self.contacts_search_entry.pack(side="left", padx=5, pady=5, fill="x", expand=True)
        
        # Add search button
        search_button = ctk.CTkButton(
            search_frame, text="Search", 
            command=lambda: self.filter_contacts_results(self.contacts_search_entry.get())
        )
        search_button.pack(side="left", padx=5, pady=5)
        
        # Add clear button
        clear_button = ctk.CTkButton(
            search_frame, text="Clear", 
            command=lambda: [self.contacts_search_entry.delete(0, tk.END), self.filter_contacts_results("")]
        )
        clear_button.pack(side="left", padx=5, pady=5)
        
        # Create frame for table
        table_frame = ctk.CTkFrame(self.tab_contacts)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Create Treeview for contacts
        self.contacts_tree = ttk.Treeview(table_frame)
        
        # Define columns
        self.contacts_tree["columns"] = ("first_name", "last_name", "main_number", "mobile_number", "home_number", "work_number", "email")
        
        # Format columns
        self.contacts_tree.column("#0", width=0, stretch=tk.NO)  # Hide the first column
        self.contacts_tree.column("first_name", anchor=tk.W, width=100)
        self.contacts_tree.column("last_name", anchor=tk.W, width=100)
        self.contacts_tree.column("main_number", anchor=tk.W, width=120)
        self.contacts_tree.column("mobile_number", anchor=tk.W, width=120)
        self.contacts_tree.column("home_number", anchor=tk.W, width=120)
        self.contacts_tree.column("work_number", anchor=tk.W, width=120)
        self.contacts_tree.column("email", anchor=tk.W, width=200)
        
        # Create headings
        self.contacts_tree.heading("#0", text="", anchor=tk.W)
        self.contacts_tree.heading("first_name", text="First Name", anchor=tk.W)
        self.contacts_tree.heading("last_name", text="Last Name", anchor=tk.W)
        self.contacts_tree.heading("main_number", text="Main Number", anchor=tk.W)
        self.contacts_tree.heading("mobile_number", text="Mobile", anchor=tk.W)
        self.contacts_tree.heading("home_number", text="Home", anchor=tk.W)
        self.contacts_tree.heading("work_number", text="Work", anchor=tk.W)
        self.contacts_tree.heading("email", text="Email", anchor=tk.W)
        
        # Add scrollbars
        y_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.contacts_tree.yview)
        x_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.contacts_tree.xview)
        self.contacts_tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
        
        # Pack everything
        y_scrollbar.pack(side="right", fill="y")
        x_scrollbar.pack(side="bottom", fill="x")
        self.contacts_tree.pack(fill="both", expand=True)

    def filter_contacts_results(self, search_term):
        """Filter contacts results based on search term"""
        # Clear the tree
        for item in self.contacts_tree.get_children():
            self.contacts_tree.delete(item)
        
        # If we have contacts data
        if hasattr(self, 'contacts_data') and self.contacts_data:
            search_term = search_term.lower()
            
            # Add filtered items
            for i, contact in enumerate(self.contacts_data):
                # Check if search term exists in any field
                if (search_term in str(contact.get('first_name', '')).lower() or
                    search_term in str(contact.get('last_name', '')).lower() or
                    search_term in str(contact.get('main_number', '')).lower() or
                    search_term in str(contact.get('mobile_number', '')).lower() or
                    search_term in str(contact.get('home_number', '')).lower() or
                    search_term in str(contact.get('work_number', '')).lower() or
                    search_term in str(contact.get('email', '')).lower()):
                    
                    self.contacts_tree.insert(
                        "", "end", text=i,
                        values=(
                            contact.get('first_name', ''),
                            contact.get('last_name', ''),
                            contact.get('main_number', ''),
                            contact.get('mobile_number', ''),
                            contact.get('home_number', ''),
                            contact.get('work_number', ''),
                            contact.get('email', '')
                        )
                    )

    def setup_data_usage_table(self):
        """Set up the data usage table with search functionality"""
        # Create frame for search controls
        search_frame = ctk.CTkFrame(self.tab_data_usage)
        search_frame.pack(fill="x", padx=10, pady=5)
        
        # Add search label and entry
        search_label = ctk.CTkLabel(search_frame, text="Search:")
        search_label.pack(side="left", padx=5, pady=5)
        
        self.data_usage_search_entry = ctk.CTkEntry(search_frame, width=250)
        self.data_usage_search_entry.pack(side="left", padx=5, pady=5, fill="x", expand=True)
        
        # Add search button
        search_button = ctk.CTkButton(
            search_frame, text="Search", 
            command=lambda: self.filter_data_usage_results(self.data_usage_search_entry.get())
        )
        search_button.pack(side="left", padx=5, pady=5)
        
        # Add clear button
        clear_button = ctk.CTkButton(
            search_frame, text="Clear", 
            command=lambda: [self.data_usage_search_entry.delete(0, tk.END), self.filter_data_usage_results("")]
        )
        clear_button.pack(side="left", padx=5, pady=5)
        
        # Create frame for table
        table_frame = ctk.CTkFrame(self.tab_data_usage)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Create Treeview for data usage
        self.data_usage_tree = ttk.Treeview(table_frame)
        
        # Define columns based on the expected data structure
        self.data_usage_tree["columns"] = ("date", "app_name", "cell_in", "cell_out")
        
        # Format columns
        self.data_usage_tree.column("#0", width=0, stretch=tk.NO)  # Hide the first column
        self.data_usage_tree.column("date", anchor=tk.W, width=150)
        self.data_usage_tree.column("app_name", anchor=tk.W, width=200)
        self.data_usage_tree.column("cell_in", anchor=tk.E, width=100)
        self.data_usage_tree.column("cell_out", anchor=tk.E, width=100)
        
        # Create headings
        self.data_usage_tree.heading("#0", text="", anchor=tk.W)
        self.data_usage_tree.heading("date", text="Date", anchor=tk.W)
        self.data_usage_tree.heading("app_name", text="Application", anchor=tk.W)
        self.data_usage_tree.heading("cell_in", text="Cell In (KB)", anchor=tk.E)
        self.data_usage_tree.heading("cell_out", text="Cell Out (KB)", anchor=tk.E)
        
        # Add scrollbars
        y_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.data_usage_tree.yview)
        x_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.data_usage_tree.xview)
        self.data_usage_tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
        
        # Pack everything
        y_scrollbar.pack(side="right", fill="y")
        x_scrollbar.pack(side="bottom", fill="x")
        self.data_usage_tree.pack(fill="both", expand=True)

    def filter_data_usage_results(self, search_term):
        """Filter data usage results based on search term"""
        # Clear the tree
        for item in self.data_usage_tree.get_children():
            self.data_usage_tree.delete(item)
        
        # If we have data usage data
        if hasattr(self, 'data_usage_data') and self.data_usage_data:
            # Debug - print keys for first item to see available fields
            if self.data_usage_data and len(self.data_usage_data) > 0:
                print(f"Data usage keys: {list(self.data_usage_data[0].keys())}")
                
            search_term = search_term.lower()
            
            # Add filtered items
            for i, usage in enumerate(self.data_usage_data):
                # Find date field - check multiple possible field names
                date_value = None
                for field in ['Date (UTC)', 'Date', 'Time', 'Timestamp', 'date', 'timestamp', 'time']:
                    if field in usage and usage[field]:
                        date_value = usage[field]
                        break
                
                # If not found yet, try any field containing 'date' or 'time'
                if not date_value:
                    for key in usage.keys():
                        if ('date' in key.lower() or 'time' in key.lower()) and usage[key]:
                            date_value = usage[key]
                            break
                
                # Debug first few records
                if i < 3:
                    print(f"Data usage record {i}: Date value: {date_value}")
                
                # Check if search term exists in any field
                if (search_term in str(date_value).lower() or
                    search_term in str(usage.get('Application Bundle', '')).lower()):
                    
                    # Convert date for display
                    date_display = self.convert_timestamp(date_value) if date_value else "Unknown Date"
                    
                    self.data_usage_tree.insert(
                        "", "end", text=i,
                        values=(
                            date_display,  # Now timezone-adjusted or "Unknown Date"
                            usage.get('Application Bundle', ''),
                            usage.get('WWAN In (KB)', '0'),
                            usage.get('WWAN Out (KB)', '0')
                        )
                    )

    def setup_accounts_table(self):
        """Set up the accounts table with search functionality"""
        # Create frame for search controls
        search_frame = ctk.CTkFrame(self.tab_accounts)
        search_frame.pack(fill="x", padx=10, pady=5)
        
        # Add search label and entry
        search_label = ctk.CTkLabel(search_frame, text="Search:")
        search_label.pack(side="left", padx=5, pady=5)
        
        self.accounts_search_entry = ctk.CTkEntry(search_frame, width=250)
        self.accounts_search_entry.pack(side="left", padx=5, pady=5, fill="x", expand=True)
        
        # Add search button
        search_button = ctk.CTkButton(
            search_frame, text="Search", 
            command=lambda: self.filter_accounts_results(self.accounts_search_entry.get())
        )
        search_button.pack(side="left", padx=5, pady=5)
        
        # Add clear button
        clear_button = ctk.CTkButton(
            search_frame, text="Clear", 
            command=lambda: [self.accounts_search_entry.delete(0, tk.END), self.filter_accounts_results("")]
        )
        clear_button.pack(side="left", padx=5, pady=5)
        
        # Create frame for table
        table_frame = ctk.CTkFrame(self.tab_accounts)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Create Treeview for accounts
        self.accounts_tree = ttk.Treeview(table_frame)
        
        # Define columns based on the expected data structure
        self.accounts_tree["columns"] = ("date", "username", "description", "account_type", "service")
        
        # Format columns
        self.accounts_tree.column("#0", width=0, stretch=tk.NO)  # Hide the first column
        self.accounts_tree.column("date", anchor=tk.W, width=150)
        self.accounts_tree.column("username", anchor=tk.W, width=200)
        self.accounts_tree.column("description", anchor=tk.W, width=200)
        self.accounts_tree.column("account_type", anchor=tk.W, width=100)
        self.accounts_tree.column("service", anchor=tk.W, width=150)
        
        # Create headings
        self.accounts_tree.heading("#0", text="", anchor=tk.W)
        self.accounts_tree.heading("date", text="Date", anchor=tk.W)
        self.accounts_tree.heading("username", text="Username", anchor=tk.W)
        self.accounts_tree.heading("description", text="Description", anchor=tk.W)
        self.accounts_tree.heading("account_type", text="Account Type", anchor=tk.W)
        self.accounts_tree.heading("service", text="Service", anchor=tk.W)
        
        # Add scrollbars
        y_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.accounts_tree.yview)
        x_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.accounts_tree.xview)
        self.accounts_tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
        
        # Pack everything
        y_scrollbar.pack(side="right", fill="y")
        x_scrollbar.pack(side="bottom", fill="x")
        self.accounts_tree.pack(fill="both", expand=True)

    def filter_accounts_results(self, search_term):
        """Filter accounts results based on search term"""
        # Clear the tree
        for item in self.accounts_tree.get_children():
            self.accounts_tree.delete(item)
        
        # If we have accounts data
        if hasattr(self, 'accounts_data') and self.accounts_data:
            # Debug - print keys for first item to see available fields
            if self.accounts_data and len(self.accounts_data) > 0:
                print(f"Accounts keys: {list(self.accounts_data[0].keys())}")
                
            search_term = search_term.lower()
                       
                       
                       
                       
            # Add filtered items
            for i, account in enumerate(self.accounts_data):
                # Find date field - check multiple possible field names
                date_value = None
                for field in ['Account Date (UTC)', 'Account Date', 'Date', 'Time', 'Created', 'Modified',
                             'creation_date', 'created_at', 'modified_at', 'timestamp']:
                    if field in account and account[field]:
                        date_value = account[field]
                        break
                
                # If not found yet, try any field containing 'date' or 'time'
                if not date_value:
                    for key in account.keys():
                        if ('date' in key.lower() or 'time' in key.lower()) and account[key]:
                            date_value = account[key]
                            break
                
                # Debug first few records
                if i < 3:
                    print(f"Accounts record {i}: Date value: {date_value}")
                
                # Check if search term exists in any field
                if (search_term in str(date_value).lower() or
                    search_term in str(account.get('Username', '')).lower() or
                    search_term in str(account.get('Description', '')).lower() or
                    search_term in str(account.get('Account Type', '')).lower() or
                    search_term in str(account.get('Service', '')).lower()):
                    
                    # Convert date for display
                    date_display = self.convert_timestamp(date_value) if date_value else "Unknown Date"
                    
                    self.accounts_tree.insert(
                        "", "end", text=i,
                        values=(
                            date_display,  # Now timezone-adjusted or "Unknown Date"
                            account.get('Username', ''),
                            account.get('Description', ''),
                            account.get('Account Type', ''),
                            account.get('Service', '')
                        )
                    )

    def setup_permissions_table(self):
        """Set up the app permissions table"""
        try:
            # Create frame for permissions content
            permissions_frame = ctk.CTkFrame(self.tab_permissions)
            permissions_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Create a text widget for now
            self.permissions_display = ctk.CTkTextbox(permissions_frame)
            self.permissions_display.pack(fill="both", expand=True, padx=10, pady=10)
            
            self.permissions_display.insert("0.0", "App permissions will appear here after parsing...")
            
        except Exception as e:
            print(f"Error setting up permissions table: {e}")

    def setup_photos_table(self):
        """Set up the photos tab with gallery view, search, and pagination"""
        try:
            # Initialize gallery state variables
            self.current_photo_view = "gallery"
            self.photos_page_size = 20
            self.current_photos_page = 0
            self.filtered_photos = []
            
            # Create main frame for photos content
            photos_frame = ctk.CTkFrame(self.tab_photos)
            photos_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Create header frame with title and search
            header_frame = ctk.CTkFrame(photos_frame)
            header_frame.pack(fill="x", pady=(0, 10))
            
            # Title
            title_label = ctk.CTkLabel(
                header_frame,
                text="Photo Gallery",
                font=ctk.CTkFont(size=18, weight="bold")
            )
            title_label.pack(side="left", padx=10, pady=10)
            
            # Search frame
            search_frame = ctk.CTkFrame(header_frame)
            search_frame.pack(side="right", padx=10, pady=10)
            
            search_label = ctk.CTkLabel(search_frame, text="Search by filename:")
            search_label.pack(side="left", padx=5)
            
            self.photos_search_entry = ctk.CTkEntry(search_frame, width=250, placeholder_text="Enter filename...")
            self.photos_search_entry.pack(side="left", padx=5)
            self.photos_search_entry.bind("<KeyRelease>", self.on_photos_search)
            
            search_clear_button = ctk.CTkButton(
                search_frame,
                text="Clear",
                width=60,
                command=self.clear_photos_search
            )
            search_clear_button.pack(side="left", padx=5)
            
            # Controls frame with view options and info
            controls_frame = ctk.CTkFrame(photos_frame)
            controls_frame.pack(fill="x", pady=(0, 10))
            
            # Left side - View controls
            left_controls = ctk.CTkFrame(controls_frame)
            left_controls.pack(side="left", padx=10, pady=5)
            
            view_label = ctk.CTkLabel(left_controls, text="View:")
            view_label.pack(side="left", padx=5)
            
            self.list_view_button = ctk.CTkButton(
                left_controls,
                text="List",
                width=80,
                command=self.switch_to_list_view
            )
            self.list_view_button.pack(side="left", padx=2)
            
            self.gallery_view_button = ctk.CTkButton(
                left_controls,
                text="Gallery",
                width=80,
                command=self.switch_to_gallery_view,
                fg_color=("gray70", "gray30")  # Active state
            )
            self.gallery_view_button.pack(side="left", padx=2)
            
            # Center - Photo count and pagination info
            center_controls = ctk.CTkFrame(controls_frame)
            center_controls.pack(side="left", expand=True, padx=10, pady=5)
            
            self.photos_count_label = ctk.CTkLabel(
                center_controls,
                text="No photos loaded",
                font=ctk.CTkFont(size=12)
            )
            self.photos_count_label.pack(pady=5)
            
            # Right side - Folder and page size controls
            right_controls = ctk.CTkFrame(controls_frame)
            right_controls.pack(side="right", padx=10, pady=5)
            
            page_size_label = ctk.CTkLabel(right_controls, text="Per page:")
            page_size_label.pack(side="left", padx=5)
            
            self.page_size_var = ctk.StringVar(value="20")
            page_size_menu = ctk.CTkOptionMenu(
                right_controls,
                values=["10", "20", "50", "100"],
                variable=self.page_size_var,
                width=80,
                command=self.change_page_size
            )
            page_size_menu.pack(side="left", padx=2)
            
            self.open_folder_button = ctk.CTkButton(
                right_controls,
                text="Open Folder",
                width=100,
                command=self.open_photos_folder,
                state="disabled"
            )
            self.open_folder_button.pack(side="left", padx=5)
            
            # Pagination controls frame
            pagination_frame = ctk.CTkFrame(photos_frame)
            pagination_frame.pack(fill="x", pady=(0, 10))
            
            self.prev_page_button = ctk.CTkButton(
                pagination_frame,
                text="← Previous",
                width=100,
                command=self.prev_photos_page,
                state="disabled"
            )
            self.prev_page_button.pack(side="left", padx=10, pady=5)
            
            self.page_info_label = ctk.CTkLabel(
                pagination_frame,
                text="Page 0 of 0",
                font=ctk.CTkFont(size=12)
            )
            self.page_info_label.pack(side="left", expand=True, pady=5)
            
            self.next_page_button = ctk.CTkButton(
                pagination_frame,
                text="Next →",
                width=100,
                command=self.next_photos_page,
                state="disabled"
            )
            self.next_page_button.pack(side="right", padx=10, pady=5)
            
            # Create scrollable content container
            self.photos_content_frame = ctk.CTkScrollableFrame(photos_frame)
            self.photos_content_frame.pack(fill="both", expand=True)
            
            # Initialize with placeholder
            self.show_photos_placeholder()
            
        except Exception as e:
            print(f"Error setting up photos table: {e}")

    def show_photos_placeholder(self):
        """Show placeholder when no photos are loaded"""
        # Clear existing content
        for widget in self.photos_content_frame.winfo_children():
            widget.destroy()
            
        placeholder_label = ctk.CTkLabel(
            self.photos_content_frame,
            text="📸 Photo gallery will appear here after parsing...\n\nThis will show thumbnails of all photos found in the iOS backup\nwith search and pagination capabilities.",
            font=ctk.CTkFont(size=14),
            justify="center"
        )
        placeholder_label.pack(expand=True, pady=50)
        
    def clear_photos_search(self):
        """Clear the search field and reset results"""
        self.photos_search_entry.delete(0, tk.END)
        self.current_photos_page = 0
        self.filter_and_display_photos()

    def on_photos_search(self, event):
        """Handle photo search input"""
        self.current_photos_page = 0  # Reset to first page on new search
        self.filter_and_display_photos()

    def change_page_size(self, value):
        """Change the number of photos per page"""
        self.photos_page_size = int(value)
        self.current_photos_page = 0  # Reset to first page
        self.filter_and_display_photos()

    def prev_photos_page(self):
        """Go to previous page"""
        if self.current_photos_page > 0:
            self.current_photos_page -= 1
            self.filter_and_display_photos()

    def next_photos_page(self):
        """Go to next page"""
        total_pages = self.get_total_pages()
        if self.current_photos_page < total_pages - 1:
            self.current_photos_page += 1
            self.filter_and_display_photos()

    def get_total_pages(self):
        """Calculate total number of pages"""
        if not self.filtered_photos:
            return 0
        return (len(self.filtered_photos) + self.photos_page_size - 1) // self.photos_page_size

    def update_pagination_controls(self):
        """Update pagination buttons and labels"""
        total_pages = self.get_total_pages()
        current_page = self.current_photos_page + 1  # Display as 1-based
        
        # Update page info
        if total_pages > 0:
            start_item = self.current_photos_page * self.photos_page_size + 1
            end_item = min((self.current_photos_page + 1) * self.photos_page_size, len(self.filtered_photos))
            self.page_info_label.configure(
                text=f"Page {current_page} of {total_pages} (showing {start_item}-{end_item} of {len(self.filtered_photos)})"
            )
        else:
            self.page_info_label.configure(text="No photos to display")
        
        # Update button states
        self.prev_page_button.configure(state="normal" if self.current_photos_page > 0 else "disabled")
        self.next_page_button.configure(state="normal" if self.current_photos_page < total_pages - 1 else "disabled")
        
        # Update count label
        total_photos = len(self.photos_data) if hasattr(self, 'photos_data') else 0
        filtered_count = len(self.filtered_photos)
        if filtered_count == total_photos:
            self.photos_count_label.configure(text=f"📸 {total_photos} photos total")
        else:
            self.photos_count_label.configure(text=f"📸 {filtered_count} of {total_photos} photos (filtered)")

    def filter_and_display_photos(self):
        """Filter photos based on search term and display current page"""
        try:
            if not hasattr(self, 'photos_data') or not self.photos_data:
                self.show_photos_placeholder()
                return
            
            # Get search term
            search_term = self.photos_search_entry.get().lower().strip() if hasattr(self, 'photos_search_entry') else ""
            
            # Filter photos by filename
            if search_term:
                self.filtered_photos = [
                    photo for photo in self.photos_data
                    if search_term in photo.get('filename', '').lower()
                ]
            else:
                self.filtered_photos = self.photos_data.copy()
            
            # Update pagination controls
            self.update_pagination_controls()
            
            # Display based on current view mode
            if self.current_photo_view == "gallery":
                self.display_photos_gallery()
            else:
                self.display_photos_list()
                
        except Exception as e:
            print(f"Error filtering and displaying photos: {e}")

    def display_photos_gallery(self):
        """Display photos in gallery view with thumbnails"""
        try:
            # Clear existing content
            for widget in self.photos_content_frame.winfo_children():
                widget.destroy()
            
            if not self.filtered_photos:
                no_results_label = ctk.CTkLabel(
                    self.photos_content_frame,
                    text="No photos match your search criteria",
                    font=ctk.CTkFont(size=14)
                )
                no_results_label.pack(expand=True, pady=50)
                return
            
            # Calculate page bounds
            start_idx = self.current_photos_page * self.photos_page_size
            end_idx = min(start_idx + self.photos_page_size, len(self.filtered_photos))
            page_photos = self.filtered_photos[start_idx:end_idx]
            
            # Create grid for thumbnails
            grid_frame = ctk.CTkFrame(self.photos_content_frame)
            grid_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Calculate grid dimensions (aim for roughly square grid)
            photos_per_row = 5
            rows_needed = (len(page_photos) + photos_per_row - 1) // photos_per_row
            
            for i, photo in enumerate(page_photos):
                row = i // photos_per_row
                col = i % photos_per_row
                
                # Create photo card
                photo_card = ctk.CTkFrame(grid_frame)
                photo_card.grid(row=row, col=col, padx=5, pady=5, sticky="nsew")
                
                # Configure grid weights for responsive layout
                grid_frame.grid_columnconfigure(col, weight=1)
                grid_frame.grid_rowconfigure(row, weight=1)
                
                # Try to load and display thumbnail
                thumbnail_path = self.get_photo_thumbnail_path(photo)
                if thumbnail_path and os.path.exists(thumbnail_path):
                    try:
                        thumbnail = self.create_thumbnail(thumbnail_path, (120, 120))
                        if thumbnail:
                            thumbnail_button = ctk.CTkButton(
                                photo_card,
                                image=thumbnail,
                                text="",
                                width=120,
                                height=120,
                                command=lambda p=thumbnail_path: self.show_photo_modal(p)
                            )
                            thumbnail_button.pack(pady=2)
                    except Exception as e:
                        print(f"Error loading thumbnail for {thumbnail_path}: {e}")
                        # Show placeholder if thumbnail fails
                        placeholder_button = ctk.CTkButton(
                            photo_card,
                            text="📷",
                            width=120,
                            height=120,
                            font=ctk.CTkFont(size=40)
                        )
                        placeholder_button.pack(pady=2)
                else:
                    # Show placeholder if no thumbnail
                    placeholder_button = ctk.CTkButton(
                        photo_card,
                        text="📷",
                        width=120,
                        height=120,
                        font=ctk.CTkFont(size=40)
                    )
                    placeholder_button.pack(pady=2)
                
                # Photo filename
                filename = photo.get('filename', 'Unknown')
                if len(filename) > 15:
                    display_name = filename[:12] + "..."
                else:
                    display_name = filename
                    
                name_label = ctk.CTkLabel(
                    photo_card,
                    text=display_name,
                    font=ctk.CTkFont(size=10),
                    wraplength=120
                )
                name_label.pack(pady=(0, 2))
                
                # Photo metadata (optional, compact)
                if photo.get('date_taken'):
                    date_label = ctk.CTkLabel(
                        photo_card,
                        text=photo['date_taken'][:10] if len(photo['date_taken']) > 10 else photo['date_taken'],
                        font=ctk.CTkFont(size=8),
                        text_color=("gray60", "gray40")
                    )
                    date_label.pack()
                    
        except Exception as e:
            print(f"Error displaying photos gallery: {e}")
            error_label = ctk.CTkLabel(
                self.photos_content_frame,
                text=f"Error displaying gallery: {str(e)}",
                font=ctk.CTkFont(size=12)
            )
            error_label.pack(expand=True, pady=50)

    def display_photos_list(self):
        """Display photos in list view"""
        try:
            # Clear existing content
            for widget in self.photos_content_frame.winfo_children():
                widget.destroy()
            
            if not self.filtered_photos:
                no_results_label = ctk.CTkLabel(
                    self.photos_content_frame,
                    text="No photos match your search criteria",
                    font=ctk.CTkFont(size=14)
                )
                no_results_label.pack(expand=True, pady=50)
                return
            
            # Calculate page bounds
            start_idx = self.current_photos_page * self.photos_page_size
            end_idx = min(start_idx + self.photos_page_size, len(self.filtered_photos))
            page_photos = self.filtered_photos[start_idx:end_idx]
            
            # Create scrollable text display
            text_frame = ctk.CTkFrame(self.photos_content_frame)
            text_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            text_display = ctk.CTkTextbox(text_frame)
            text_display.pack(fill="both", expand=True)
            
            # Build content
            content = f"Showing {len(page_photos)} photos (page {self.current_photos_page + 1})\n\n"
            
            for i, photo in enumerate(page_photos, start=start_idx + 1):
                content += f"{i}. {photo.get('filename', 'Unknown')}\n"
                content += f"   Date: {photo.get('date_taken', 'Unknown')}\n"
                content += f"   Size: {photo.get('file_size', 'Unknown')}\n"
                if photo.get('location'):
                    content += f"   Location: {photo['location']}\n"
                if photo.get('device_model'):
                    content += f"   Device: {photo['device_model']}\n"
                if photo.get('gps_coordinates'):
                    content += f"   GPS: {photo['gps_coordinates']}\n"
                content += "\n"
            
            text_display.insert("0.0", content)
            
        except Exception as e:
            print(f"Error displaying photos list: {e}")

    def get_photo_thumbnail_path(self, photo):
        """Get the path to the photo file for thumbnail generation"""
        try:
            # Try to construct path from extracted photos folder
            if hasattr(self, 'extracted_photos_path') and self.extracted_photos_path:
                filename = photo.get('filename', '')
                if filename:
                    full_path = os.path.join(self.extracted_photos_path, filename)
                    if os.path.exists(full_path):
                        return full_path
            
            # Fallback to any path info in the photo data
            if photo.get('file_path') and os.path.exists(photo['file_path']):
                return photo['file_path']
                
            return None
        except Exception as e:
            print(f"Error getting photo path: {e}")
            return None

    def on_photos_search(self, event):
        """Handle photo search"""
        if hasattr(self, 'photos_data') and self.photos_data:
            self.filter_photos_results(self.photos_search_entry.get())

    def switch_to_list_view(self):
        """Switch to list view for photos"""
        self.current_photo_view = "list"
        # Update button appearance
        self.list_view_button.configure(fg_color=("gray70", "gray30"))  # Active
        self.gallery_view_button.configure(fg_color=("gray75", "gray25"))  # Inactive
        self.filter_and_display_photos()

    def switch_to_gallery_view(self):
        """Switch to gallery view for photos"""
        self.current_photo_view = "gallery"
        # Update button appearance
        self.gallery_view_button.configure(fg_color=("gray70", "gray30"))  # Active
        self.list_view_button.configure(fg_color=("gray75", "gray25"))  # Inactive
        self.filter_and_display_photos()

    def refresh_photos_display(self):
        """Refresh the photos display based on current view mode and load data"""
        if hasattr(self, 'photos_data') and self.photos_data:
            # Initialize filtered data if not already done
            if not hasattr(self, 'filtered_photos'):
                self.filtered_photos = self.photos_data.copy()
            
            self.filter_and_display_photos()
            
            # Enable folder button if we have photos path
            if hasattr(self, 'extracted_photos_path') and self.extracted_photos_path:
                self.open_folder_button.configure(state="normal")
        else:
            self.show_photos_placeholder()

    def show_photos_list(self):
        """Legacy method - now redirects to new implementation"""
        self.current_photo_view = "list"
        self.filter_and_display_photos()

    def show_photos_gallery(self):
        """Legacy method - now redirects to new implementation"""
        self.current_photo_view = "gallery" 
        self.filter_and_display_photos()

    def open_photos_folder(self):
        """Open the photos folder in system file manager"""
        if hasattr(self, 'extracted_photos_path') and self.extracted_photos_path:
            try:
                if platform.system() == "Darwin":  # macOS
                    subprocess.run(["open", self.extracted_photos_path])
                elif platform.system() == "Windows":
                    subprocess.run(["explorer", self.extracted_photos_path])
                elif platform.system() == "Linux":
                    subprocess.run(["xdg-open", self.extracted_photos_path])
            except Exception as e:
                print(f"Error opening photos folder: {e}")
                messagebox.showerror("Error", f"Could not open photos folder: {e}")

    def setup_notes_table(self):
        """Set up the notes table"""
        try:
            # Create frame for notes content
            notes_frame = ctk.CTkFrame(self.tab_notes)
            notes_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Create a text widget for now
            self.notes_display = ctk.CTkTextbox(notes_frame)
            self.notes_display.pack(fill="both", expand=True, padx=10, pady=10)
            
            self.notes_display.insert("0.0", "Notes will appear here after parsing...")
            
        except Exception as e:
            print(f"Error setting up notes table: {e}")

    def setup_interactions_table(self):
        """Set up the interactions table"""
        try:
            # Create frame for interactions content
            interactions_frame = ctk.CTkFrame(self.tab_interactions)
            interactions_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Create a text widget for now
            self.interactions_display = ctk.CTkTextbox(interactions_frame)
            self.interactions_display.pack(fill="both", expand=True, padx=10, pady=10)
            
            self.interactions_display.insert("0.0", "Interaction data will appear here after parsing...")
            
        except Exception as e:
            print(f"Error setting up interactions table: {e}")

    def setup_device_info(self):
        """Set up the device info tab with device information display"""
        try:
            # Create a frame for device info
            device_info_frame = ctk.CTkFrame(self.tab_device)
            device_info_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Add a text widget to display device information
            self.device_info_text = ctk.CTkTextbox(device_info_frame)
            self.device_info_text.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Initial text
            self.device_info_text.insert("0.0", "Device information will appear here after parsing a backup...")
            
        except Exception as e:
            print(f"Error setting up device info tab: {e}")

    def is_backup_encrypted(self, backup_path):
        """Check if an iOS backup is encrypted by looking for encrypted files"""
        try:
            import os
            
            if not os.path.isdir(backup_path):
                return False
                
            # Look for Manifest.plist and check for encryption indicators
            manifest_path = os.path.join(backup_path, "Manifest.plist")
            if os.path.exists(manifest_path):
                try:
                    import plistlib
                    with open(manifest_path, 'rb') as f:
                        manifest = plistlib.load(f)
                    
                    # Check if backup is encrypted
                    return manifest.get('IsEncrypted', False)
                    
                except Exception as e:
                    print(f"Error reading manifest: {e}")
                    return False
            
            # If no manifest, assume not encrypted
            return False
            
        except Exception as e:
            print(f"Error checking backup encryption: {e}")
            return False

    def setup_treeview_sorting(self):
        """Set up sorting functionality for all treeview tables"""
        # Add this to the end of your __init__ method
        
        # Define sort state variables
        self.sms_sort_column = None
        self.sms_sort_reverse = False
        
        self.calls_sort_column = None
        self.calls_sort_reverse = False
        
        self.contacts_sort_column = None
        self.contacts_sort_reverse = False
        
        self.data_usage_sort_column = None
        self.data_usage_sort_reverse = False
        
        self.accounts_sort_column = None
        self.accounts_sort_reverse = False
        
        self.permissions_sort_column = None
        self.permissions_sort_reverse = False
        
        self.photos_sort_column = None
        self.photos_sort_reverse = False

        self.safari_sort_column = None  
        self.safari_sort_reverse = False
        
        # Bind click events to column headers
        for tree, name in [
            (self.sms_tree, "sms"),
            (self.calls_tree, "calls"),
            (self.contacts_tree, "contacts"),
            (self.data_usage_tree, "data_usage"),
            (self.accounts_tree, "accounts"),
            (self.permissions_tree, "permissions"),
            (self.photos_tree, "photos"),
            (self.interactions_tree, "interactions"),
            (self.safari_tree, "safari")
        ]:
            for col in tree["columns"]:
                tree.heading(col, command=lambda _col=col, _name=name: self.treeview_sort_column(_name, _col))

    def treeview_sort_column(self, tree_name, col):
        """Sort treeview contents when a column header is clicked"""
        # Get the appropriate tree and data variables
        tree_map = {
            "sms": (self.sms_tree, "sms_data"),
            "calls": (self.calls_tree, "calls_data"),
            "interactions": (self.interactions_tree, "interactions_data"),
            "contacts": (self.contacts_tree, "contacts_data"),
            "data_usage": (self.data_usage_tree, "data_usage_data"),
            "accounts": (self.accounts_tree, "accounts_data"),
            "permissions": (self.permissions_tree, "permissions_data"),
            "photos": (self.photos_tree, "photos_data"),
            "safari": (self.safari_tree, "safari_data")
        }
        
        tree, data_attr = tree_map[tree_name]
        data = getattr(self, data_attr, [])
        
        # Handle sort state
        sort_col_var = f"{tree_name}_sort_column"
        sort_reverse_var = f"{tree_name}_sort_reverse"
        
        current_col = getattr(self, sort_col_var, None)
        current_reverse = getattr(self, sort_reverse_var, False)
        
        # Toggle sort direction if clicking same column
        if current_col == col:
            setattr(self, sort_reverse_var, not current_reverse)
        else:
            setattr(self, sort_col_var, col)
            setattr(self, sort_reverse_var, False)
        
        reverse = getattr(self, sort_reverse_var)
        
        # Update sort indicator in header
        for c in tree["columns"]:
            tree.heading(c, text=tree.heading(c, "text").replace(" ↑", "").replace(" ↓", ""))
        
        arrow = " ↑" if not reverse else " ↓"
        tree.heading(col, text=tree.heading(col, "text") + arrow)
        
        # Create mapping for column IDs to actual data field names
        column_mappings = {
            "sms": {
                "date": "Date",
                "contact": "Contact",
                "service": "Message Service"
            },
            "calls": {
                "date": "Date",
                "phone_number": "Phone Number"
            },
            "data_usage": {
                "date": "Date",
                "app_name": "Application Bundle",
                "cell_in": "Cell In (KB)", 
                "cell_out": "Cell Out (KB)"
            },
            "accounts": {
                "date": "Date",
                "username": "Username",
                "description": "Description",
            },
            "permissions": {
                "permission": "Device Permission",
                "app_bundle": "Application Bundle",
                "status": "Permission Status"
            },
            "interactions": {
                "date": "Date",
                "service": "Service",
                "contact": "Contact Display Name",
                "app": "Application ID",
                "direction": "Direction",
                "count": "Interaction Count",
                "last_contact": "Last Contacted (UTC)",
                "content_type": "Content Type"
            }
        }
        
        # Get the field name to sort by
        field_name = col
        if tree_name in column_mappings and col in column_mappings[tree_name]:
            field_name = column_mappings[tree_name][col]
        
        # Get search term
        search_term = ""
        search_entry_attr = f"{tree_name}_search_entry"
        if hasattr(self, search_entry_attr):
            search_entry = getattr(self, search_entry_attr)
            search_term = search_entry.get()
        
        # Status update
        self.parse_status_text.configure(text=f"Sorting {tree_name} by {field_name}...")
        
        # Create thread local variables
        thread_data = data.copy() if data else []
        thread_field = field_name
        thread_reverse = reverse
        
        def do_sort():
            try:
                # Simple string-based sorting for ALL columns
                sorted_list = sorted(
                    thread_data,
                    key=lambda x: str(x.get(thread_field, '')).lower(),
                    reverse=thread_reverse
                )
                
                # Update UI on main thread
                self.after(10, lambda: self._update_sorted_data(tree_name, sorted_list, search_term))
                
            except Exception as e:
                print(f"Sorting error: {e}")
                self.after(10, lambda: self.parse_status_text.configure(text="Error during sorting"))
        
        # Start thread
        import threading
        thread = threading.Thread(target=do_sort)
        thread.daemon = True
        thread.start()

    def _update_sorted_data(self, tree_name, sorted_data, search_term):
        """Update the data and refresh the display"""
        # Update the data attribute
        setattr(self, f"{tree_name}_data", sorted_data)
        
        # Call the appropriate filter function
        filter_funcs = {
            "sms": self.filter_sms_results,
            "calls": self.filter_call_results,
            "contacts": self.filter_contacts_results,
            "data_usage": self.filter_data_usage_results,
            "accounts": self.filter_accounts_results,
            "permissions": self.filter_permissions_results,
            "photos": self.filter_photos_results
        }
        
        if tree_name in filter_funcs:
            filter_funcs[tree_name](search_term)
        
        self.parse_status_text.configure(text="Sorting complete")

    def update_sms_message_display(self, event):
        """Update the message display with the selected message content"""
        selected_items = self.sms_tree.selection()
        if selected_items:
            item = selected_items[0]
            item_id = self.sms_tree.item(item, "text")  # Get the index
            
            # Get the message content
            if hasattr(self, 'sms_data') and self.sms_data and int(item_id) < len(self.sms_data):
                msg = self.sms_data[int(item_id)]
                
                # Clear the text box
                self.sms_message_display.delete("1.0", tk.END)
                
                # Add message details
                direction = msg.get('direction', '')
                contact = msg.get('phone_number', '')
                date = msg.get('date', '')
                service = msg.get('service', '')
                message = msg.get('Sent', '') or msg.get('Received', '') or msg.get('message', '')
                attachment = msg.get('attachment', '')
                
                # Format the message
                content = f"From/To: {contact}\nDate: {date}\nService: {service}\n"
                content += f"Direction: {direction}\n\n"
                content += f"Message:\n{message}\n"
                
                if attachment:
                    content += f"\nAttachment: {attachment}"
                    
                self.sms_message_display.insert(tk.END, content)

    def trigger_device_refresh(self):
        """Trigger device refresh - called after window is shown and mainloop is active"""
        if not self._device_refresh_triggered:
            self._device_refresh_triggered = True
            print("DEBUG: trigger_device_refresh called, scheduling refresh")
            # Use after_idle to ensure the mainloop is running, then wait a bit more
            self.after_idle(lambda: self.after(1000, self.refresh_device_info))

    def go_back_to_main(self):
        """Handle back button press"""
        self.on_closing()
        
    def on_closing(self):
        """Handle window closing event"""
        try:
            # Hide this window
            self.withdraw()
            
            # Call the return callback if it exists
            if hasattr(self, 'return_to_main_callback') and self.return_to_main_callback:
                self.return_to_main_callback()
            else:
                # If no callback, just destroy the window
                self.destroy()
                
        except Exception as e:
            print(f"Error during window closing: {e}")
            # Force close if there's an error
            try:
                self.destroy()
            except:
                pass

    def toggle_taxonomy_dropdown(self):
        """Toggle the visibility/state of the taxonomy dropdown"""
        try:
            if hasattr(self, 'enable_taxonomy_var') and hasattr(self, 'taxonomy_dropdown'):
                if self.enable_taxonomy_var.get():
                    # Enable taxonomy filtering
                    self.taxonomy_dropdown.configure(state="normal")
                    if hasattr(self, 'taxonomy_label'):
                        self.taxonomy_label.configure(text_color=("gray10", "gray90"))
                else:
                    # Disable taxonomy filtering
                    self.taxonomy_dropdown.configure(state="disabled")
                    if hasattr(self, 'taxonomy_label'):
                        self.taxonomy_label.configure(text_color=("gray60", "gray40"))
        except Exception as e:
            print(f"Error toggling taxonomy dropdown: {e}")

    def get_taxonomy_options(self):
        """Get list of taxonomy classification options"""
        return [
            "All Photos",
            "People",
            "Outdoor Scene", 
            "Vehicle",
            "Building",
            "Document",
            "Screenshot",
            "Baby",
            "Child",
            "Teen",
            "Adult",
            "Credit Card",
            "Currency",
            "License Plate",
            "Weapon",
            "Firearm"
        ]

    def filter_photos_results(self, search_term=""):
        """Legacy compatibility method - redirects to new gallery system"""
        try:
            if not hasattr(self, 'photos_data') or not self.photos_data:
                return
            
            # If we have the new search entry, update it
            if hasattr(self, 'photos_search_entry') and search_term:
                self.photos_search_entry.delete(0, tk.END)
                self.photos_search_entry.insert(0, search_term)
            
            # Use the new filtering system
            self.filter_and_display_photos()
                
        except Exception as e:
            print(f"Error in legacy filter_photos_results: {e}")

    def display_photos(self, photos_path):
        """Display photos in a gallery view with thumbnails"""
        try:
            if not os.path.exists(photos_path):
                print(f"Photos path does not exist: {photos_path}")
                return
            
            # Create gallery window
            self.gallery_window = ctk.CTkToplevel(self)
            self.gallery_window.title("Photo Gallery")
            self.gallery_window.geometry("1200x800")
            
            # Create main container with scrollable frame
            main_container = ctk.CTkFrame(self.gallery_window)
            main_container.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Header
            header_frame = ctk.CTkFrame(main_container)
            header_frame.pack(fill="x", pady=(0, 10))
            
            title_label = ctk.CTkLabel(
                header_frame, 
                text="Photo Gallery", 
                font=ctk.CTkFont(size=16, weight="bold")
            )
            title_label.pack(side="left", padx=10, pady=10)
            
            close_button = ctk.CTkButton(
                header_frame,
                text="Close",
                command=self.gallery_window.destroy
            )
            close_button.pack(side="right", padx=10, pady=10)
            
            # Create scrollable frame for thumbnails
            self.gallery_scroll = ctk.CTkScrollableFrame(main_container)
            self.gallery_scroll.pack(fill="both", expand=True)
            
            # Load and display photos
            self.load_photo_thumbnails(photos_path)
            
        except Exception as e:
            print(f"Error displaying photos: {e}")
            messagebox.showerror("Error", f"Failed to display photos: {e}")

    def load_photo_thumbnails(self, photos_path):
        """Load and display photo thumbnails in a grid"""
        try:
            supported_formats = ('.jpg', '.jpeg', '.png', '.heic', '.heif', '.tiff', '.tif')
            photos = []
            
            # Find all photo files
            if os.path.isdir(photos_path):
                for root, dirs, files in os.walk(photos_path):
                    for file in files:
                        if file.lower().endswith(supported_formats):
                            photos.append(os.path.join(root, file))
            
            if not photos:
                no_photos_label = ctk.CTkLabel(
                    self.gallery_scroll,
                    text="No photos found in the specified directory",
                    font=ctk.CTkFont(size=14)
                )
                no_photos_label.pack(pady=20)
                return
            
            # Create thumbnail grid
            columns = 4
            current_row_frame = None
            
            for i, photo_path in enumerate(photos):
                if i % columns == 0:
                    current_row_frame = ctk.CTkFrame(self.gallery_scroll)
                    current_row_frame.pack(fill="x", pady=5)
                
                try:
                    # Create thumbnail container
                    thumb_container = ctk.CTkFrame(current_row_frame)
                    thumb_container.pack(side="left", padx=5, pady=5)
                    
                    # Load and resize image
                    thumbnail = self.create_thumbnail(photo_path)
                    
                    if thumbnail:
                        # Create thumbnail button that opens modal
                        thumb_button = ctk.CTkButton(
                            thumb_container,
                            image=thumbnail,
                            text="",
                            width=150,
                            height=150,
                            command=lambda path=photo_path: self.show_photo_modal(path)
                        )
                        thumb_button.pack(pady=5)
                        
                        # Add filename label
                        filename = os.path.basename(photo_path)
                        if len(filename) > 20:
                            filename = filename[:17] + "..."
                        
                        name_label = ctk.CTkLabel(
                            thumb_container,
                            text=filename,
                            font=ctk.CTkFont(size=10)
                        )
                        name_label.pack(pady=(0, 5))
                
                except Exception as e:
                    print(f"Error creating thumbnail for {photo_path}: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error loading photo thumbnails: {e}")

    def create_thumbnail(self, image_path, size=(150, 150)):
        """Create a thumbnail image for display"""
        try:
            # Register HEIF opener if available
            pillow_heif.register_heif_opener()
            
            # Open and resize image
            with Image.open(image_path) as img:
                # Convert RGBA to RGB if needed
                if img.mode == 'RGBA':
                    img = img.convert('RGB')
                
                # Create thumbnail maintaining aspect ratio
                img.thumbnail(size, Image.Resampling.LANCZOS)
                
                # Create a square background and paste the thumbnail
                background = Image.new('RGB', size, (240, 240, 240))
                
                # Calculate position to center the image
                x = (size[0] - img.width) // 2
                y = (size[1] - img.height) // 2
                background.paste(img, (x, y))
                
                # Convert to PhotoImage for tkinter
                return ImageTk.PhotoImage(background)
                
        except Exception as e:
            print(f"Error creating thumbnail for {image_path}: {e}")
            return None

    def show_photo_modal(self, image_path):
        """Show photo in a modal with EXIF and location data"""
        try:
            # Create modal window
            modal = ctk.CTkToplevel(self.gallery_window)
            modal.title(f"Photo: {os.path.basename(image_path)}")
            modal.geometry("900x700")
            modal.transient(self.gallery_window)
            modal.grab_set()
            
            # Create main container
            main_frame = ctk.CTkFrame(modal)
            main_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Header with filename and close button
            header_frame = ctk.CTkFrame(main_frame)
            header_frame.pack(fill="x", pady=(0, 10))
            
            filename_label = ctk.CTkLabel(
                header_frame,
                text=os.path.basename(image_path),
                font=ctk.CTkFont(size=14, weight="bold")
            )
            filename_label.pack(side="left", padx=10, pady=10)
            
            close_button = ctk.CTkButton(
                header_frame,
                text="Close",
                command=modal.destroy
            )
            close_button.pack(side="right", padx=10, pady=10)
            
            # Create horizontal layout for image and metadata
            content_frame = ctk.CTkFrame(main_frame)
            content_frame.pack(fill="both", expand=True)
            
            # Left side - Image display
            image_frame = ctk.CTkFrame(content_frame)
            image_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
            
            # Right side - Metadata
            metadata_frame = ctk.CTkFrame(content_frame)
            metadata_frame.pack(side="right", fill="y", padx=(5, 0))
            metadata_frame.configure(width=300)
            
            # Load and display the full image (resized to fit)
            self.display_full_image(image_path, image_frame)
            
            # Display EXIF and location data
            self.display_photo_metadata(image_path, metadata_frame)
            
        except Exception as e:
            print(f"Error showing photo modal: {e}")
            messagebox.showerror("Error", f"Failed to display photo: {e}")

    def display_full_image(self, image_path, container):
        """Display the full image in the modal"""
        try:
            pillow_heif.register_heif_opener()
            
            with Image.open(image_path) as img:
                # Convert RGBA to RGB if needed
                if img.mode == 'RGBA':
                    img = img.convert('RGB')
                
                # Calculate display size (max 500x500)
                display_size = (500, 500)
                img.thumbnail(display_size, Image.Resampling.LANCZOS)
                
                photo = ImageTk.PhotoImage(img)
                
                # Create label to display image
                image_label = ctk.CTkLabel(container, image=photo, text="")
                image_label.pack(expand=True, pady=20)
                
                # Keep a reference to prevent garbage collection
                image_label.image = photo
                
        except Exception as e:
            print(f"Error displaying full image: {e}")
            error_label = ctk.CTkLabel(
                container,
                text=f"Error loading image:\n{str(e)}",
                font=ctk.CTkFont(size=12)
            )
            error_label.pack(expand=True, pady=20)

    def display_photo_metadata(self, image_path, container):
        """Display EXIF data and location information"""
        try:
            # Create scrollable text area for metadata
            metadata_scroll = ctk.CTkScrollableFrame(container)
            metadata_scroll.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Title
            title_label = ctk.CTkLabel(
                metadata_scroll,
                text="Photo Metadata",
                font=ctk.CTkFont(size=14, weight="bold")
            )
            title_label.pack(anchor="w", pady=(0, 10))
            
            # Extract EXIF data
            exif_data = self.extract_exif_data(image_path)
            
            # Check if GPS data is available and create Google Maps button
            google_maps_url = None
            if exif_data and "Google Maps" in exif_data:
                google_maps_url = exif_data["Google Maps"]
                
                # Create Google Maps button
                maps_button = ctk.CTkButton(
                    metadata_scroll,
                    text="📍 Open in Google Maps",
                    command=lambda: self.open_google_maps(google_maps_url),
                    fg_color="#4285f4",
                    hover_color="#3367d6",
                    font=ctk.CTkFont(size=12, weight="bold")
                )
                maps_button.pack(anchor="w", pady=(0, 10))
            
            # Display basic file info
            file_info = self.get_file_info(image_path)
            
            info_text = ctk.CTkTextbox(metadata_scroll, height=400)
            info_text.pack(fill="both", expand=True)
            
            # Build metadata text
            metadata_text = "FILE INFORMATION:\n"
            metadata_text += f"Filename: {os.path.basename(image_path)}\n"
            metadata_text += f"File Size: {file_info.get('size', 'Unknown')}\n"
            metadata_text += f"Modified: {file_info.get('modified', 'Unknown')}\n\n"
            
            if exif_data:
                metadata_text += "EXIF DATA:\n"
                for key, value in exif_data.items():
                    # Don't display the raw Google Maps URL in text since we have a button
                    if key != "Google Maps":
                        metadata_text += f"{key}: {value}\n"
                
                # Add GPS coordinates section if available
                if any(key.startswith("GPS") or key in ["Latitude", "Longitude", "Coordinates"] for key in exif_data.keys()):
                    metadata_text += "\nLOCATION DATA:\n"
                    for key, value in exif_data.items():
                        if key in ["Coordinates", "Latitude", "Longitude", "Altitude", "GPS Date", "GPS Time"]:
                            metadata_text += f"{key}: {value}\n"
            else:
                metadata_text += "No EXIF data found\n"
            
            info_text.insert("0.0", metadata_text)
            info_text.configure(state="disabled")  # Make read-only
            
        except Exception as e:
            print(f"Error displaying metadata: {e}")
            error_label = ctk.CTkLabel(
                container,
                text=f"Error loading metadata:\n{str(e)}",
                font=ctk.CTkFont(size=12)
            )
            error_label.pack(expand=True, pady=20)

    def open_google_maps(self, maps_url):
        """Open Google Maps URL in default browser"""
        try:
            import webbrowser
            webbrowser.open(maps_url)
            print(f"Opening Google Maps: {maps_url}")
        except Exception as e:
            print(f"Error opening Google Maps: {e}")
            messagebox.showerror("Error", f"Could not open Google Maps: {e}")

    def extract_exif_data(self, image_path):
        """Extract EXIF data from image including GPS coordinates"""
        try:
            pillow_heif.register_heif_opener()
            
            with Image.open(image_path) as img:
                exif_data = {}
                
                # Get basic EXIF data
                exif = img._getexif()
                if exif:
                    for tag_id, value in exif.items():
                        tag = TAGS.get(tag_id, tag_id)
                        
                        # Handle GPS data specially
                        if tag == "GPSInfo":
                            gps_data = self.extract_gps_data(value)
                            if gps_data:
                                exif_data.update(gps_data)
                        else:
                            # Format common tags
                            if tag in ["DateTime", "DateTimeOriginal", "DateTimeDigitized"]:
                                exif_data[tag] = str(value)
                            elif tag in ["Make", "Model", "Software"]:
                                exif_data[tag] = str(value)
                            elif tag in ["ExposureTime", "FNumber", "ISO"]:
                                exif_data[tag] = str(value)
                            elif isinstance(value, (int, float, str)):
                                exif_data[tag] = str(value)
                
                return exif_data
                
        except Exception as e:
            print(f"Error extracting EXIF data: {e}")
            return {}

    def extract_gps_data(self, gps_info):
        """Extract GPS coordinates from EXIF GPS data"""
        try:
            gps_data = {}
            
            if not gps_info:
                return gps_data
            
            # Convert GPS info to readable format
            for key, value in gps_info.items():
                tag = GPSTAGS.get(key, key)
                
                if tag == "GPSLatitude":
                    lat = self.convert_gps_coordinate(value)
                    if lat:
                        gps_data["Latitude"] = lat
                elif tag == "GPSLongitude":
                    lon = self.convert_gps_coordinate(value)
                    if lon:
                        gps_data["Longitude"] = lon
                elif tag == "GPSLatitudeRef":
                    gps_data["Latitude Reference"] = value
                elif tag == "GPSLongitudeRef":
                    gps_data["Longitude Reference"] = value
                elif tag == "GPSAltitude":
                    gps_data["Altitude"] = f"{float(value)} meters"
                elif tag == "GPSTimeStamp":
                    if len(value) >= 3:
                        gps_data["GPS Time"] = f"{int(value[0])}:{int(value[1])}:{int(value[2])}"
                elif tag == "GPSDateStamp":
                    gps_data["GPS Date"] = str(value)
                else:
                    gps_data[tag] = str(value)
            
            # Create coordinate string if we have lat/lon
            if "Latitude" in gps_data and "Longitude" in gps_data:
                lat_ref = gps_data.get("Latitude Reference", "N")
                lon_ref = gps_data.get("Longitude Reference", "E")
                
                lat_val = gps_data["Latitude"]
                lon_val = gps_data["Longitude"]
                
                if lat_ref == "S":
                    lat_val = -lat_val
                if lon_ref == "W":
                    lon_val = -lon_val
                
                gps_data["Coordinates"] = f"{lat_val}, {lon_val}"
                gps_data["Google Maps"] = f"https://maps.google.com/?q={lat_val},{lon_val}"
            
            return gps_data
            
        except Exception as e:
            print(f"Error extracting GPS data: {e}")
            return {}

    def convert_gps_coordinate(self, coord):
        """Convert GPS coordinate from DMS to decimal degrees"""
        try:
            if not coord or len(coord) != 3:
                return None
            
            degrees = float(coord[0])
            minutes = float(coord[1]) 
            seconds = float(coord[2])
            
            decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
            return round(decimal, 6)
            
        except Exception as e:
            print(f"Error converting GPS coordinate: {e}")
            return None

    def get_file_info(self, file_path):
        """Get basic file information"""
        try:
            stat = os.stat(file_path)
            return {
                "size": f"{stat.st_size / 1024:.1f} KB",
                "modified": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            }
        except Exception as e:
            print(f"Error getting file info: {e}")
            return {"size": "Unknown", "modified": "Unknown"}
