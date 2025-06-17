"""
Arsenic - A forensic analysis tool for iOS and Android devices
Copyright (C) 2025 North Loop Consulting, LLC 
Charlie Rubisoff

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox
import tkinter.ttk as ttk  # For Treeview widgets
import customtkinter as ctk
import threading
import logging
from src.backup.device_backup import initiate_backup
from src.parser.backup_parser import parse_backup, parse_ios_backup  # Import the class
from PIL import Image, ImageTk  
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
        self.geometry("1000x850")  # Increased window size
        self.minsize(900, 650)
        
        # Configure logging
        logging.basicConfig(level=logging.INFO, 
                           format='%(asctime)s - %(levelname)s - %(message)s')
        
        # Create the UI
        self.create_widgets()
    
    def create_widgets(self):
        # Load the app icon with the correct path
        try:
            from PIL import Image, ImageTk
            
             # Calculate path relative to the current file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(current_dir))  # Go up two levels from src/ui
            icon_path = os.path.join(project_root, "src", "assets", "icons", "app_icon.png")
            
         
            # Debug output
            print(f"Looking for icon at: {icon_path}")
         
            if os.path.exists(icon_path):
                print(f"Loading icon from: {icon_path}")
                
                # Load with PIL as required by CTkImage
                pil_img = Image.open(icon_path)
                # Inverse the image colors for dark mode
                pil_img = pil_img.convert("RGBA")
                 # Get data for manipulation
                data = pil_img.getdata()
                new_data = []
                
                # Invert each pixel while preserving alpha
                for item in data:
                    # Invert RGB but keep alpha channel
                    new_data.append((255 - item[0], 255 - item[1], 255 - item[2], item[3]))
                
                # Update image with inverted colors
                pil_img.putdata(new_data)

                
                # Create CTkImage with PIL Image objects
                self.app_icon = ctk.CTkImage(light_image=pil_img, 
                                             dark_image=pil_img,
                                             size=(64, 64))
                
                # Create header frame at top of window
                header_frame = ctk.CTkFrame(self)
                header_frame.pack(fill="x", padx=10, pady=(10, 0))
                
                # Add logo to left side
                logo_label = ctk.CTkLabel(header_frame, image=self.app_icon, text="")
                logo_label.pack(side="left", padx=10, pady=5)
                
                # Add title with larger, bold font
                title_font = ctk.CTkFont(size=20, weight="bold")
                title_label = ctk.CTkLabel(header_frame, 
                                          text="Arsenic v1.0 - Triage Tool", 
                                          font=title_font)
                title_label.pack(side="left", padx=10, pady=5)
                
                # Set window icon
                icon_img = ImageTk.PhotoImage(pil_img)
                self.iconphoto(True, icon_img)
            else:
                print(f"Icon not found at path: {icon_path}")
                raise FileNotFoundError(f"Icon not found at: {icon_path}")
                
        except Exception as e:
            print(f"Failed to load app icon: {e}")
        
        # Create tabview (whether icon loaded or not)
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Create tabs
        self.tab_backup = self.tabview.add("Backup")
        self.tab_parse = self.tabview.add("Parse Backup")
        
        # Setup each tab
        self.setup_backup_tab()
        self.setup_parse_tab()

        self.setup_treeview_sorting()
        
    def setup_backup_tab(self):
        # Create a left and right pane for the backup tab
        self.backup_panes = ctk.CTkFrame(self.tab_backup)
        self.backup_panes.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Left pane for device info and backup options
        self.left_pane = ctk.CTkFrame(self.backup_panes)
        self.left_pane.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        
        # Right pane for apps list - Create with width parameter
        self.right_pane = ctk.CTkFrame(self.backup_panes, width=300)
        # Pack without the width parameter
        self.right_pane.pack(side="right", fill="both", expand=True, padx=5, pady=5)
        
        # Device info frame in left pane
        self.device_frame = ctk.CTkFrame(self.left_pane)
        self.device_frame.pack(fill="x", padx=10, pady=10)
        
        self.device_label = ctk.CTkLabel(self.device_frame, 
                                        text="Device Information", 
                                        font=ctk.CTkFont(size=16, weight="bold"))
        self.device_label.pack(pady=5)
        
        self.device_status = ctk.CTkLabel(self.device_frame, text="No device connected")
        self.device_status.pack(pady=5)
        
        self.device_info_text = ctk.CTkTextbox(self.device_frame, height=100, wrap="word")
        self.device_info_text.pack(fill="x", padx=10, pady=5)
        
        self.refresh_button = ctk.CTkButton(self.device_frame, 
                                           text="Refresh Device Info", 
                                           command=self.refresh_device_info)
        self.refresh_button.pack(pady=10)
        
        # Backup options frame in left pane
        self.options_frame = ctk.CTkFrame(self.left_pane)
        self.options_frame.pack(fill="x", padx=10, pady=10)
        
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
        self.backup_button.pack(pady=15)
        
        # Progress frame in left pane
        self.progress_frame = ctk.CTkFrame(self.left_pane)
        self.progress_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.progress_label = ctk.CTkLabel(self.progress_frame, 
                                          text="Status", 
                                          font=ctk.CTkFont(size=16, weight="bold"))
        self.progress_label.pack(pady=5)
        
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame)
        self.progress_bar.pack(fill="x", padx=10, pady=5)
        self.progress_bar.set(0)
        
        self.status_text = ctk.CTkTextbox(self.progress_frame, height=120, wrap="word")
        self.status_text.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Apps list frame in right pane
        self.apps_frame = ctk.CTkFrame(self.right_pane)
        self.apps_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
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
        
        # Store apps for filtering
        self.current_apps = []
        
    def setup_parse_tab(self):
        """Set up the parse backup tab"""
        # Create a frame for the backup selection
        self.parse_top_frame = ctk.CTkFrame(self.tab_parse)
        self.parse_top_frame.pack(fill="x", padx=10, pady=10)
        
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
        self.device_info_text.delete("1.0", "end")
        self.device_status.configure(text="Checking for connected devices...")
        self.apps_list.delete("1.0", "end")
        self.apps_count.configure(text="0 apps")
        self.current_apps = []
        
        def get_info():
            from src.backup.device_backup import DeviceBackup
            backup = DeviceBackup()
            
            if backup.connect_device():
                device_info = backup.get_device_info()
                
                # Update UI in main thread
                self.after(0, lambda: self._update_device_info(device_info))
            else:
                self.after(0, lambda: self.device_status.configure(
                    text="No device connected"))
        
        # Run in thread to prevent UI freezing
        threading.Thread(target=get_info, daemon=True).start()
        
    def _update_device_info(self, device_info):
        """Update device info in the UI"""
        if device_info:
            self.device_status.configure(text="Device connected")
            
            # Format device info (basic info only)
            info_text = f"Device: {device_info.get('Device Model', 'Unknown')}\n"
            info_text += f"Name: {device_info.get('Device Name', 'Unknown')}\n"
            info_text += f"iOS Version: {device_info.get('iOS Version', 'Unknown')}\n"
            info_text += f"Serial Number: {device_info.get('Serial Number', 'Unknown')}\n"
            info_text += f"IMEI: {device_info.get('IMEI', 'Unknown')}\n"
            
            # Update device info text
            self.device_info_text.insert("1.0", info_text)
            
            # Update apps list separately
            apps = device_info.get('Installed Applications', [])
            self.current_apps = apps
            if apps:
                # Update apps count
                self.apps_count.configure(text=f"{len(apps)} applications")
                
                # Display apps in the list
                self.update_apps_list(apps)
            else:
                self.apps_list.insert("1.0", "No applications found")
                self.apps_count.configure(text="0 applications")
        else:
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

    def start_backup(self):
        """Start the backup process"""
        folder_path = self.folder_path.get()
        include_logs = self.logs_var.get()
        
        if not folder_path:
            self.update_status("Please select a backup location")
            return
            
        # Clear previous status
        self.status_text.delete("1.0", "end")
        self.progress_bar.set(0)
        self.update_status("Starting backup process...")
        self.backup_button.configure(state="disabled")
        
        # Run backup in a thread
        def run_backup():
            try:
                result = initiate_backup(
                    path=folder_path,
                    backup_logs=include_logs,
                    status_callback=lambda msg: self.after(0, lambda: self.update_status(msg)),
                    progress_callback=lambda val: self.after(0, lambda: self.update_progress(val))
                )
                
                self.after(0, lambda: self.update_status(
                    "Backup completed successfully!" if result else "Backup failed!"))
                self.after(0, lambda: self.backup_button.configure(state="normal"))
            except Exception as e:
                self.after(0, lambda: self.update_status(f"Error: {str(e)}"))
                self.after(0, lambda: self.backup_button.configure(state="normal"))
                
        threading.Thread(target=run_backup, daemon=True).start()
        
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
        
        # Display photo analysis
        if hasattr(self, 'photos_tree'):
            # Clear the tree
            self.photos_tree.delete(*self.photos_tree.get_children())
            
            # Display photo data
            self.filter_photos_results("")
            
            # Show extracted photos path and thumbnails if available
            if 'extracted_photos_path' in results:
                # Create path info in the analysis tab
                path_frame = ctk.CTkFrame(self.photo_analysis_tab)
                path_frame.pack(padx=10, pady=(5, 0), anchor="w", fill="x")
                
                path_label = ctk.CTkLabel(
                    path_frame, 
                    text=f"Extracted photos: {results['extracted_photos_path']}", 
                    fg_color="#4caf50",
                    text_color="white",
                    corner_radius=6
                )
                path_label.pack(side="left", padx=10, pady=5)
                
                # Add button to open folder
                open_folder_button = ctk.CTkButton(
                    path_frame, 
                    text="Open Photos Folder", 
                    command=lambda: os.system(f"open {results['extracted_photos_path']}")
                )
                open_folder_button.pack(side="left", padx=10, pady=5)
                
                # Display thumbnails and switch to thumbnails tab
                self.display_photos(results['extracted_photos_path'])
                self.photos_notebook.select(1)  # Switch to thumbnails tab

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
        """Set up the permissions table tab"""
        # Create a search frame at the top
        search_frame = ctk.CTkFrame(self.tab_permissions)
        search_frame.pack(fill="x", padx=10, pady=5)
        
        search_label = ctk.CTkLabel(search_frame, text="Search:")
        search_label.pack(side="left", padx=5, pady=5)
        
        self.permissions_search_entry = ctk.CTkEntry(search_frame, width=250)
        self.permissions_search_entry.pack(side="left", padx=5, pady=5)
        
        # Add search button
        search_button = ctk.CTkButton(
            search_frame, text="Search", 
            command=lambda: self.filter_permissions_results(self.permissions_search_entry.get())
        )
        search_button.pack(side="left", padx=5, pady=5)
        
        # Add clear button
        clear_button = ctk.CTkButton(
            search_frame, text="Clear", 
            command=lambda: [self.permissions_search_entry.delete(0, tk.END), self.filter_permissions_results("")]
        )
        clear_button.pack(side="left", padx=5, pady=5)
        
        # Create frame for table
        table_frame = ctk.CTkFrame(self.tab_permissions)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Create Treeview for permissions - CREATE THE WIDGET FIRST
        self.permissions_tree = ttk.Treeview(table_frame)
        
        # Define columns based on the expected data structure
        self.permissions_tree["columns"] = ("app_name", "permission", "access_granted", "type", "description")
        
        # NOW configure columns AFTER the widget is created
        self.permissions_tree.column("#0", width=0, stretch=tk.NO)  # Hide the first column
        self.permissions_tree.column("app_name", anchor=tk.W, width=150)
        self.permissions_tree.column("permission", anchor=tk.W, width=150)
        self.permissions_tree.column("access_granted", anchor=tk.W, width=100)
        self.permissions_tree.column("type", anchor=tk.W, width=100)
        self.permissions_tree.column("description", anchor=tk.W, width=200)
        
        # Create headings
        self.permissions_tree.heading("#0", text="", anchor=tk.W)
        self.permissions_tree.heading("app_name", text="App Name", anchor=tk.W)
        self.permissions_tree.heading("permission", text="Permission", anchor=tk.W)
        self.permissions_tree.heading("access_granted", text="Access Granted", anchor=tk.W)
        self.permissions_tree.heading("type", text="Type", anchor=tk.W)
        self.permissions_tree.heading("description", text="Description", anchor=tk.W)
        
        # Add scrollbars
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.permissions_tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.permissions_tree.xview)
        self.permissions_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # Pack the Treeview and scrollbars
        self.permissions_tree.pack(fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")

    def filter_permissions_results(self, search_term):
        """Filter app permissions results based on search term"""
        # Clear the tree
        for item in self.permissions_tree.get_children():
            self.permissions_tree.delete(item)
        
        # If we have permissions data
        if hasattr(self, 'permissions_data') and self.permissions_data:
            search_term = search_term.lower()
            
            # Add filtered items
            for i, permission in enumerate(self.permissions_data):
                # Check if search term exists in any field
                if (search_term in str(permission.get('Device Permission', '')).lower() or
                    search_term in str(permission.get('Application Bundle', '')).lower() or
                    search_term in str(permission.get('Permission Status', '')).lower()):
                    
                    # Apply special styling based on status
                    status = permission.get('Permission Status', '')
                    
                    values = (
                        permission.get('Device Permission', ''),
                        permission.get('Application Bundle', ''),
                        permission.get('Permission Status', '')
                    )
                    item_id = self.permissions_tree.insert("", "end", text=i, values=values)
                    
                    # Optional: Add color highlighting based on permission status
                    if 'granted' in status.lower():
                        self.permissions_tree.tag_configure('granted', background='#e6ffe6')
                        self.permissions_tree.item(item_id, tags=('granted',))
                    elif 'denied' in status.lower():
                        self.permissions_tree.tag_configure('denied', background='#ffe6e6')
                        self.permissions_tree.item(item_id, tags=('denied',))
                    else:
                        self.permissions_tree.tag_configure('unknown', background='#ffffe6')
                        self.permissions_tree.item(item_id, tags=('unknown',))

    def setup_photos_table(self):
        """Set up the photos analysis and thumbnail display"""
        # Create main container with notebook/tab control for photos
        self.photos_notebook = ttk.Notebook(self.tab_photos)
        self.photos_notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Create tabs for the analysis grid and thumbnails
        self.photo_analysis_tab = ttk.Frame(self.photos_notebook)
        self.photo_thumbnails_tab = ttk.Frame(self.photos_notebook)
        
        self.photos_notebook.add(self.photo_analysis_tab, text="Analysis")
        self.photos_notebook.add(self.photo_thumbnails_tab, text="Thumbnails")
        
        # Add existing search frame and table to analysis tab
        search_frame = ctk.CTkFrame(self.photo_analysis_tab)
        search_frame.pack(fill="x", padx=10, pady=5)
        
        # Add search label and entry
        search_label = ctk.CTkLabel(search_frame, text="Search:")
        search_label.pack(side="left", padx=5, pady=5)
        
        self.photos_search_entry = ctk.CTkEntry(search_frame, width=250)
        self.photos_search_entry.pack(side="left", padx=5, pady=5, fill="x", expand=True)
        
        # Add search button
        search_button = ctk.CTkButton(
            search_frame, text="Search", 
            command=lambda: self.filter_photos_results(self.photos_search_entry.get())
        )
        search_button.pack(side="left", padx=5, pady=5)
        
        # Add clear button
        clear_button = ctk.CTkButton(
            search_frame, text="Clear", 
            command=lambda: [self.photos_search_entry.delete(0, tk.END), self.filter_photos_results("")]
        )
        clear_button.pack(side="left", padx=5, pady=5)
        
        # Add this in setup_photos_table method, near other buttons
        # test_button = ctk.CTkButton(
        #     search_frame, 
        #     text="Test Thumbnails", 
        #     command=self.test_photo_display
        # )
        # test_button.pack(side="left", padx=5, pady=5)
        
        # Create frame for table
        table_frame = ctk.CTkFrame(self.photo_analysis_tab)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Create Treeview for photos
        self.photos_tree = ttk.Treeview(table_frame)
        
        # Define columns based on the expected data structure
        self.photos_tree["columns"] = ("filename", "path", "date_taken", "classification", "confidence")
        
        # Format columns
        self.photos_tree.column("#0", width=0, stretch=tk.NO)  # Hide the first column
        self.photos_tree.column("filename", anchor=tk.W, width=150)
        self.photos_tree.column("path", anchor=tk.W, width=250)
        self.photos_tree.column("date_taken", anchor=tk.W, width=150)
        self.photos_tree.column("classification", anchor=tk.W, width=150)
        self.photos_tree.column("confidence", anchor=tk.E, width=100)
        
        # Create headings
        self.photos_tree.heading("#0", text="", anchor=tk.W)
        self.photos_tree.heading("filename", text="Filename", anchor=tk.W)
        self.photos_tree.heading("path", text="Path", anchor=tk.W)
        self.photos_tree.heading("date_taken", text="Date Taken", anchor=tk.W)
        self.photos_tree.heading("classification", text="Classification", anchor=tk.W)
        self.photos_tree.heading("confidence", text="Confidence", anchor=tk.E)
        
        # Add scrollbars
        y_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.photos_tree.yview)
        x_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.photos_tree.xview)
        self.photos_tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
        
        # Pack everything
        y_scrollbar.pack(side="right", fill="y")
        x_scrollbar.pack(side="bottom", fill="x")
        self.photos_tree.pack(fill="both", expand=True)

    def filter_photos_results(self, search_term):
        """Filter photo analysis results based on search term"""
        # Clear the tree
        for item in self.photos_tree.get_children():
            self.photos_tree.delete(item)
        
        # If we have photos data
        if hasattr(self, 'photos_data') and self.photos_data:
            search_term = search_term.lower()
            
            # Add filtered items
            for i, photo in enumerate(self.photos_data):
                # Check if search term exists in any field
                if (search_term in str(photo.get('Filename', '')).lower() or
                    search_term in str(photo.get('Path', '')).lower() or
                    search_term in str(photo.get('Date Taken', '')).lower() or
                    search_term in str(photo.get('Scene Classification', '')).lower()):
                    
                    # Convert date for display
                    date_taken_display = self.convert_timestamp(photo.get('Date Taken', ''))
                    date_added_display = self.convert_timestamp(photo.get('Date Added', ''))
                    
                    self.photos_tree.insert(
                        "", "end", text=i,
                        values=(
                            photo.get('Filename', ''),
                            photo.get('Path', ''),
                            date_taken_display,  # Now timezone-adjusted
                            photo.get('Scene Classification', ''),
                            photo.get('Confidence', '')
                        )
                    )

    def toggle_taxonomy_dropdown(self):
        """Enable or disable the taxonomy dropdown based on checkbox state"""
        if self.enable_taxonomy_var.get():
            self.taxonomy_dropdown.configure(state="normal")
            self.taxonomy_label.configure(state="normal")
        else:
            self.taxonomy_dropdown.configure(state="disabled")
            self.taxonomy_label.configure(state="disabled")

    def get_taxonomy_options(self):
        # Extract all unique values from the taxonomy dictionary
        taxonomy_values = set(parse_ios_backup.taxonomy_Dict.values())
        # Sort them alphabetically for better user experience
        sorted_values = sorted(list(taxonomy_values))
        # Add an "All Photos" option at the top
        return [" "] + sorted_values

    def setup_notes_table(self):
        """Set up the notes table with search functionality"""
        # Create frame for search controls
        search_frame = ctk.CTkFrame(self.tab_notes)
        search_frame.pack(fill="x", padx=10, pady=5)
        
        # Add search label and entry
        search_label = ctk.CTkLabel(search_frame, text="Search:")
        search_label.pack(side="left", padx=5, pady=5)
        
        self.notes_search_entry = ctk.CTkEntry(search_frame, width=250)
        self.notes_search_entry.pack(side="left", padx=5, pady=5, fill="x", expand=True)
        
        # Add search button
        search_button = ctk.CTkButton(
            search_frame, text="Search", 
            command=lambda: self.filter_notes_results(self.notes_search_entry.get())
        )
        search_button.pack(side="left", padx=5, pady=5)
        
        # Add clear button
        clear_button = ctk.CTkButton(
            search_frame, text="Clear", 
            command=lambda: [self.notes_search_entry.delete(0, tk.END), self.filter_notes_results("")]
        )
        clear_button.pack(side="left", padx=5, pady=5)
        
        # Create frame for the notes content
        table_frame = ctk.CTkFrame(self.tab_notes)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Create Text widget for notes with word wrap
        self.notes_text = ctk.CTkTextbox(table_frame, wrap="word")
        
        # Configure tags for different styles - FIX: use absolute sizes instead of relative
        title_font = ctk.CTkFont(size=14, weight="bold")
        header_font = ctk.CTkFont(size=13, weight="bold")
        
        self.notes_text._textbox.tag_configure("title", font=title_font, foreground="#2a6099")
        self.notes_text._textbox.tag_configure("note_header", font=header_font, foreground="#333333")
        self.notes_text._textbox.tag_configure("note_odd", background="#f5f8fc", spacing1=10, spacing2=2, spacing3=10)
        self.notes_text._textbox.tag_configure("note_even", background="#ffffff", spacing1=10, spacing2=2, spacing3=10) 
        self.notes_text._textbox.tag_configure("separator", foreground="#cccccc")
        
        # Pack the text widget
        self.notes_text.pack(fill="both", expand=True)

    def filter_notes_results(self, search_term):
        """Filter notes results based on search term with enhanced styling"""
        # Clear the text widget
        self.notes_text.delete("1.0", tk.END)
        
        # Debug output
        self.update_parse_status(f"Searching notes for: '{search_term}'")
        
        # If we have notes data
        if hasattr(self, 'notes_data') and self.notes_data:
            self.update_parse_status(f"Found {len(self.notes_data)} notes to search")
            search_term = search_term.lower()
            
            # Display filtered notes with alternating backgrounds
            displayed_count = 0
            for i, note in enumerate(self.notes_data):
                if i == 0:
                    print(f"Note keys: {note.keys()}")
                
                # Try different possible keys for note content
                content = ""
                for possible_key in ['ZCONTENT', 'content', 'Content', 'text', 'Text', 'body', 'Body', 'note_content']:
                    if possible_key in note:
                        content = str(note.get(possible_key, ''))
                        break
                
                # If still no content found, try to use the entire note
                if not content and isinstance(note, dict):
                    content = str(note)
                
                # Apply search filter if specified
                if not search_term or search_term in content.lower():
                    # Determine style based on odd/even
                    note_tag = "note_odd" if displayed_count % 2 == 1 else "note_even"
                    
                    # Add note header with note number
                    self.notes_text.insert(tk.END, f"Note {displayed_count + 1}", "note_header")
                    
                    # Add creation date if available with timezone conversion
                    for date_key in ['ZCREATIONDATE', 'creation_date', 'date', 'timestamp']:
                        if date_key in note:
                            creation_date = note.get(date_key, '')
                            # Convert timestamp for timezone display
                            creation_date_display = self.convert_timestamp(creation_date)
                            self.notes_text.insert(tk.END, f" • {creation_date_display}", "note_header")
                            break
                    
                    self.notes_text.insert(tk.END, "\n\n", note_tag)
                    
                    # Insert the content with proper formatting
                    self.notes_text.insert(tk.END, content + "\n\n", note_tag)
                    
                    # Add a stylish separator
                    self.notes_text.insert(tk.END, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n", "separator")
                    
                    displayed_count += 1
            
            # Show summary
            if displayed_count > 0:
                self.update_parse_status(f"Found {displayed_count} notes matching '{search_term}'")
            else:
                self.notes_text.insert(tk.END, f"No notes found matching '{search_term}'", "note_header")
                self.update_parse_status("No matching notes found")
        else:
            self.notes_text.insert(tk.END, "No notes data available", "title")
            self.update_parse_status("No notes data available")

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

    def is_backup_encrypted(self, backup_path):
        """Check if the selected backup is encrypted"""
        # Look for the Manifest.plist file
        manifest_path = os.path.join(backup_path, "Manifest.plist")
        
        if not os.path.exists(manifest_path):
            return False
        
        try:
            # Try to parse the Manifest.plist to check for encryption
            import plistlib
            with open(manifest_path, 'rb') as f:
                manifest = plistlib.load(f)
            
            # If IsEncrypted key exists and is True, the backup is encrypted
            return manifest.get('IsEncrypted', False)
        except:
            # If we can't read the file properly, assume it's encrypted
            return True

    def toggle_password_field(self, show=False):
        """Show or hide the password field and adjust other elements accordingly"""
        # First, ensure any existing timezone frame is completely removed
        if hasattr(self, 'timezone_frame') and self.timezone_frame.winfo_exists():
            self.timezone_frame.destroy()
        
        if show:
            # Show password field at row 1
            self.password_label.grid(row=1, column=0, padx=5, pady=5, sticky="w")
            self.password_entry.grid(row=1, column=1, padx=5, pady=5, sticky="we")
            
            # Move output folder to row 2
            self.output_folder_label.grid(row=2, column=0, padx=5, pady=5, sticky="w")
            self.output_folder_path.grid(row=2, column=1, padx=5, pady=5, sticky="we")
            self.browse_output_button.grid(row=2, column=2, padx=5, pady=5)
            
            # Move controls frame to row 3
            if hasattr(self, 'controls_frame') and self.controls_frame.winfo_exists():
                self.controls_frame.grid(row=3, column=0, columnspan=3, padx=5, pady=5, sticky="we")
            
            # Move button frame to row 4
            self.button_frame.grid(row=4, column=0, columnspan=3, padx=5, pady=20, sticky="nswe")
            
            # Move status to row 5 
            self.parse_status_label.grid(row=5, column=0, padx=5, pady=5, sticky="w")
            self.parse_status_text.grid(row=5, column=1, columnspan=2, padx=5, pady=5, sticky="w")
        else:
            # Hide password field
            self.password_label.grid_forget()
            self.password_entry.grid_forget()
            self.password_entry.delete(0, tk.END)  # Clear any password
            
            # Move output folder up to row 1
            self.output_folder_label.grid(row=1, column=0, padx=5, pady=5, sticky="w")
            self.output_folder_path.grid(row=1, column=1, padx=5, pady=5, sticky="we")
            self.browse_output_button.grid(row=1, column=2, padx=5, pady=5)
            
            # Move controls frame up to row 2
            if hasattr(self, 'controls_frame') and self.controls_frame.winfo_exists():
                self.controls_frame.grid(row=2, column=0, columnspan=3, padx=5, pady=5, sticky="we")
            
            # Move button frame up to row 3
            self.button_frame.grid(row=3, column=0, columnspan=3, padx=5, pady=20, sticky="nswe")
            
            # Move status up to row 4
            self.parse_status_label.grid(row=4, column=0, padx=5, pady=5, sticky="w")
            self.parse_status_text.grid(row=4, column=1, columnspan=2, padx=5, pady=5, sticky="w")
        
        

    def setup_device_info(self):
        """Set up the device info display tab"""
        # Create a text widget to display device information
        self.device_result = ctk.CTkTextbox(self.tab_device, wrap="word")
        self.device_result.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Set initial text
        self.device_result.insert("1.0", "Device information will be displayed here after parsing a backup.")
        
        # Make it read-only
        self.device_result.configure(state="disabled")

    def setup_photo_view(self):
        """Set up the photo view area with proper scrolling"""
        # Frame to contain canvas and scrollbar
        self.photo_frame = ctk.CTkFrame(self.tab_view.tab("Photos"))
        self.photo_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Create canvas for scrollable content
        self.photo_canvas = ctk.CTkCanvas(
            self.photo_frame,
            bg=self._apply_appearance_mode(self.cget("fg_color"))
        )
        
        # Add vertical scrollbar
        self.photo_scrollbar = ctk.CTkScrollbar(
            self.photo_frame,
            command=self.photo_canvas.yview
        )
        
        # Configure canvas to use scrollbar
        self.photo_canvas.configure(
            yscrollcommand=self.photo_scrollbar.set,
            highlightthickness=0
        )
        
        # Place canvas and scrollbar
        self.photo_scrollbar.pack(side="right", fill="y")
        self.photo_canvas.pack(side="left", fill="both", expand=True)
        
        # Bind mousewheel scrolling
        self.photo_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
        # Bind resize event
        self.photo_canvas.bind("<Configure>", self.update_canvas_scrollregion)

    def _on_mousewheel(self, event):
        """Handle mousewheel scrolling on canvas"""
        # For Windows/MacOS
        self.photo_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def display_photos(self, photo_path):
        """Display photos and videos in a responsive grid that adapts to window size"""
        import time
        from PIL import Image
        from concurrent.futures import ThreadPoolExecutor
        import platform
        import os
        
        # Clear existing content
        for widget in self.photo_thumbnails_tab.winfo_children():
            widget.destroy()
        
        if not photo_path or not os.path.exists(photo_path):
            no_photos = ctk.CTkLabel(self.photo_thumbnails_tab, text="No media directory found")
            no_photos.pack(pady=20)
            return
            
        # Create status bar
        status_frame = ctk.CTkFrame(self.photo_thumbnails_tab)
        status_frame.pack(fill="x", padx=10, pady=5)
        status_label = ctk.CTkLabel(status_frame, text="Loading media files...")
        status_label.pack(pady=5)
        
        # Constants for thumbnail sizing
        THUMB_SIZE = 150
        THUMB_SPACING = 20
        
        # Get photo AND video files
        photo_files = [f for f in os.listdir(photo_path) 
                    if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.heic', 
                                        '.mp4', '.mov', '.m4v', '.3gp'))]
        
        if not photo_files:
            status_label.configure(text="No media files found in this backup")
            return
        
        status_label.configure(text=f"Found {len(photo_files)} media files")
            
        # Create scrollable frame for content
        scroll_frame = ctk.CTkScrollableFrame(self.photo_thumbnails_tab)
        scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Optimize scrolling performance
        scroll_frame._parent_canvas.configure(yscrollincrement=20)
        scroll_frame._parent_canvas.configure(highlightthickness=0)
        
        # Set scroll speed based on platform
        system = platform.system()
        scroll_speed = 2 if system == 'Darwin' else 3
        
        # Create frame for thumbnails
        gallery_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        gallery_frame.pack(fill="both", expand=True)
        
        # Variables to track grid state
        current_columns = 0
        
        # Function to calculate optimal number of columns
        def calculate_columns():
            """Calculate the optimal number of columns based on available width"""
            # Get current width of the scrollable frame
            width = scroll_frame.winfo_width()
            
            # Use parent width if scroll frame isn't initialized yet
            if width < 50:
                width = self.photo_thumbnails_tab.winfo_width()
            
            # Fallback if still no width available
            if width < 50:
                width = 800  # Default fallback width
            
            # Calculate columns based on available width
            available_width = width - 40  # Account for padding
            optimal_columns = max(1, available_width // (THUMB_SIZE + THUMB_SPACING))
            return optimal_columns
        
        # Track scroll state
        self.is_scrolling = False
        self.last_scroll_time = 0
        self.scroll_debounce_ms = 100
        
        # Function to create/update the thumbnail grid
        def create_thumbnail_grid():
            """Create or update the grid of thumbnails"""
            nonlocal current_columns
            
            # Calculate optimal number of columns
            optimal_columns = calculate_columns()
            
            # Only rebuild if the column count changed
            if optimal_columns == current_columns and current_columns > 0:
                return
            
            current_columns = optimal_columns
            status_label.configure(text=f"Arranging {len(photo_files)} photos ({current_columns} columns)")
            
            # Clear existing thumbnails and reset loaded state
            for widget in gallery_frame.winfo_children():
                widget.destroy()
            self.loaded_thumbnails = {}
            
            # Calculate total rows needed
            total_rows = (len(photo_files) + current_columns - 1) // current_columns
            
            # Rebuild the grid with empty placeholders first
            for i, file in enumerate(photo_files):
                # Calculate grid position
                row = i // current_columns
                col = i % current_columns
                
                # Create frame for this thumbnail
                thumb_frame = ctk.CTkFrame(gallery_frame)
                thumb_frame.grid(row=row, column=col, padx=THUMB_SPACING//2, pady=THUMB_SPACING//2, sticky="nsew")
                
                # Create placeholder for image
                placeholder = ctk.CTkLabel(thumb_frame, text="Loading...", width=THUMB_SIZE, height=THUMB_SIZE)
                placeholder.pack(padx=5, pady=5)
                
                # Add filename
                filename = os.path.basename(file)
                short_name = filename[:15] + "..." if len(filename) > 15 else filename
                name_label = ctk.CTkLabel(thumb_frame, text=short_name, font=("Arial", 10))
                name_label.pack(pady=(0, 5))
                
            # Add an empty spacer at the bottom to ensure proper scrolling boundaries
            bottom_spacer = ctk.CTkFrame(gallery_frame, height=10, fg_color="transparent")
            bottom_spacer.grid(row=total_rows, column=0, columnspan=current_columns, sticky="ew")
            
            # Configure grid rows and columns to ensure proper spacing
            for i in range(current_columns):
                gallery_frame.columnconfigure(i, weight=1, uniform="column")
            
            for i in range(total_rows + 1):  # +1 for the spacer
                gallery_frame.rowconfigure(i, weight=0)  # Don't let rows stretch
            
            # Force update of the underlying canvas scroll region
            gallery_frame.update_idletasks()
            scroll_frame._parent_canvas.update_idletasks()
            
            # Calculate optimal scrollable height
            total_height = (THUMB_SIZE + THUMB_SPACING) * total_rows + 50  # Add extra padding
            
            # Set canvas scrollregion to exact content size
            content_width = scroll_frame._parent_canvas.winfo_width()
            scroll_frame._parent_canvas.configure(scrollregion=(0, 0, content_width, total_height))
            
            # After grid is created, load only visible thumbnails
            self.after(100, load_visible_thumbnails)
        
        def _on_mousewheel(event):
            """Handle mouse wheel scrolling with platform-specific logic"""
            # Get system and set scrolling flag
            system = platform.system()
            self.is_scrolling = True
            
            # Reset debounce timer
            current_time = time.time() * 1000
            self.last_scroll_time = current_time
            
            # Calculate scroll amount based on platform
            if system == 'Darwin':  # macOS
                # macOS natural scrolling
                scroll_amount = int(event.delta * scroll_speed)
            elif system == 'Windows':
                # Windows needs delta divided by 120 and direction inverted
                scroll_amount = int(-1 * (event.delta / 120) * scroll_speed)
            else:  # Linux
                # Button4 = up, Button5 = down
                scroll_amount = -3 * scroll_speed if event.num == 4 else 3 * scroll_speed
            
            # Apply scroll
            scroll_frame._parent_canvas.yview_scroll(scroll_amount, "units")
            
            # Schedule end of scrolling after a short delay
            if hasattr(self, '_scroll_timer'):
                self.after_cancel(self._scroll_timer)
            self._scroll_timer = self.after(200, end_scrolling)
            
            return "break"  # Prevent event propagation
        
        def end_scrolling():
            """Mark scrolling as complete and load visible thumbnails"""
            self.is_scrolling = False
            # Load visible thumbnails after scrolling stops
            self.after(50, load_visible_thumbnails)
        
        # Track loaded thumbnails
        self.loaded_thumbnails = {}
        def create_fallback_thumbnail(self, image_path, size=(150, 150)):
            """Create a thumbnail using alternative methods when standard methods fail"""
            try:
                # Try with different Pillow options
                from PIL import Image, ImageFile
                # Allow loading truncated images
                ImageFile.LOAD_TRUNCATED_IMAGES = True
                
                img = Image.open(image_path)
                img.load()  # Force load the image data
                img.thumbnail(size, Image.NEAREST)  # Use NEAREST for faster resizing
                return img
            except Exception as e:
                print(f"Fallback thumbnail creation failed: {e}")
                return self.create_generic_thumbnail(os.path.splitext(os.path.basename(image_path))[1].upper(), size)
        
        def load_visible_thumbnails():
            """Load only the thumbnails that are visible in the current view"""
            if self.is_scrolling:
                return
                
            # Get scroll position
            try:
                view_start = scroll_frame._parent_canvas.yview()[0]
                view_end = scroll_frame._parent_canvas.yview()[1]
                
                # Calculate visible rows (with buffer for smoother scrolling)
                total_height = gallery_frame.winfo_height()
                if total_height <= 1:  # Not yet properly sized
                    self.after(100, load_visible_thumbnails)
                    return
                    
                row_height = THUMB_SIZE + THUMB_SPACING
                buffer_rows = 1  # Load one extra row above and below viewport
                
                # Calculate row range
                start_row = max(0, int(view_start * total_height / row_height) - buffer_rows)
                end_row = min(len(photo_files) // current_columns + 1, 
                            int(view_end * total_height / row_height) + buffer_rows)
                
                # Calculate visible thumbnail indices
                visible_start = start_row * current_columns
                visible_end = min(len(photo_files), end_row * current_columns)
                
                # Queue loading only for thumbnails that aren't already loaded or loading
                batch_size = 2  # Process thumbnails in small batches
                batch_count = 0
                
                for idx in range(visible_start, visible_end):
                    if idx not in self.loaded_thumbnails and idx < len(photo_files):
                        filename = photo_files[idx]
                        self.loaded_thumbnails[idx] = "loading"
                        
                        # Stagger loading to prevent UI freezes (more delay for later items)
                        batch_delay = (batch_count // batch_size) * 100
                        self.after(batch_delay, lambda i=idx, f=filename: 
                                self.executor.submit(load_thumbnail, i, f))
                        batch_count += 1
                        
                # If we loaded thumbnails, update status
                if batch_count > 0:
                    status_label.configure(text=f"Loading {batch_count} thumbnails...")
                    
            except Exception as e:
                print(f"Error in load_visible_thumbnails: {e}")
        
        # Simple direct binding for better performance
        def bind_scroll_events():
            """Apply scroll bindings based on platform"""
            system = platform.system()
            
            if system in ['Darwin', 'Windows']:
                # Use bind_all for complete capture
                self.photo_thumbnails_tab.bind_all("<MouseWheel>", _on_mousewheel)
            elif system == 'Linux':
                self.photo_thumbnails_tab.bind_all("<Button-4>", _on_mousewheel)
                self.photo_thumbnails_tab.bind_all("<Button-5>", _on_mousewheel)
        
        # Apply bindings
        bind_scroll_events()
        
        # Create thumbnail image references container
        if not hasattr(self, 'photo_references'):
            self.photo_references = []
        self.photo_references.clear()
        
        # Function to load a thumbnail in the background
        def load_thumbnail(index, filename):
            """Load a thumbnail in a background thread"""
            try:
                file_path = os.path.join(photo_path, filename)
                file_ext = os.path.splitext(filename.lower())[1]
                
                # Create thumbnail based on file type
                if file_ext == '.heic':
                    img = self.create_heic_thumbnail(file_path, (THUMB_SIZE, THUMB_SIZE))
                elif file_ext in ['.mp4', '.mov', '.m4v', '.3gp']:
                    # Add video thumbnail generation
                    img = self.create_video_thumbnail(file_path, (THUMB_SIZE, THUMB_SIZE))
                else:
                    img = Image.open(file_path)
                    img.thumbnail((THUMB_SIZE, THUMB_SIZE))
                
                # Update UI in main thread
                self.after(0, lambda: update_thumbnail(index, img, file_path))
                
            except Exception as e:
                print(f"Error loading thumbnail {filename}: {e}")
                self.after(0, lambda: update_thumbnail_error(index, str(e)))
        
        # Function to update a thumbnail in the UI
        def update_thumbnail(index, img, file_path):
            """Update the UI with a loaded thumbnail"""
            try:
                row = index // current_columns
                col = index % current_columns
                
                # Find the frame at this grid position
                frames = gallery_frame.grid_slaves(row=row, column=col)
                if not frames:
                    return
                
                thumb_frame = frames[0]
                
                # Clear placeholder
                for widget in thumb_frame.winfo_children():
                    widget.destroy()
                
                # Create CTkImage
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(THUMB_SIZE, THUMB_SIZE))
                self.photo_references.append(ctk_img)  # Store reference
                
                # Display thumbnail
                img_label = ctk.CTkLabel(thumb_frame, image=ctk_img, text="")
                img_label.pack(padx=5, pady=5)
                
                # Add video indicator if this is a video file
                file_ext = os.path.splitext(file_path.lower())[1]
                if file_ext in ['.mp4', '.mov', '.m4v', '.3gp']:
                    video_indicator = ctk.CTkLabel(
                        thumb_frame,
                        text="▶ VIDEO",
                        fg_color="#E74C3C",
                        text_color="white",
                        corner_radius=4,
                        font=("Arial", 10, "bold")
                    )
                    video_indicator.place(x=5, y=5)
                
                # Add filename
                filename = os.path.basename(file_path)
                short_name = filename[:15] + "..." if len(filename) > 15 else filename
                name_label = ctk.CTkLabel(thumb_frame, text=short_name, font=("Arial", 10))
                name_label.pack(pady=(0, 5))
                
                # Bind click event to show full image/video
                img_label.bind("<Button-1>", lambda e: self.show_media_file(file_path))
                name_label.bind("<Button-1>", lambda e: self.show_media_file(file_path))
                
                # Mark as loaded
                self.loaded_thumbnails[index] = "loaded"
                
                # Update status periodically
                loaded_count = sum(1 for status in self.loaded_thumbnails.values() if status == "loaded")
                if loaded_count % 10 == 0:
                    status_label.configure(text=f"Loaded {loaded_count}/{len(photo_files)} thumbnails")
                    
            except Exception as e:
                print(f"Error updating thumbnail UI: {e}")
        
        # Function to show error when thumbnail can't be loaded
        def update_thumbnail_error(index, error_msg):
            """Show error in place of thumbnail that failed to load"""
            try:
                row = index // current_columns
                col = index % current_columns
                
                # Find the frame at this grid position
                frames = gallery_frame.grid_slaves(row=row, column=col)
                if not frames:
                    return
                
                thumb_frame = frames[0]
                
                # Clear placeholder
                for widget in thumb_frame.winfo_children():
                    widget.destroy()
                
                # Show error icon/message
                error_label = ctk.CTkLabel(
                    thumb_frame, 
                    text="⚠️",
                    font=("Arial", 24),
                    text_color="#E74C3C"
                )
                error_label.pack(pady=(10, 0))
                
                error_text = ctk.CTkLabel(
                    thumb_frame,
                    text="Error loading image",
                    font=("Arial", 10),
                    text_color="#E74C3C"
                )
                error_text.pack(pady=5)
                
                # Add filename
                filename = os.path.basename(photo_files[index])
                short_name = filename[:15] + "..." if len(filename) > 15 else filename
                name_label = ctk.CTkLabel(thumb_frame, text=short_name, font=("Arial", 10))
                name_label.pack(pady=(0, 5))
                
                # Mark as error for tracking
                self.loaded_thumbnails[index] = "error"
                
            except Exception as e:
                print(f"Error displaying thumbnail error: {e}")
        
        # Create thread pool for thumbnail loading
        self.executor = ThreadPoolExecutor(max_workers=8)
        
        # Create initial thumbnail grid after a short delay
        self.after(100, create_thumbnail_grid)
        
        # Handle resize with debouncing
        def on_resize(event=None):
            """Handle window resize events with debouncing"""
            if hasattr(self, '_resize_timer') and self._resize_timer:
                self.after_cancel(self._resize_timer)
            self._resize_timer = self.after(300, create_thumbnail_grid)
        
        # Bind resize events
        scroll_frame.bind("<Configure>", on_resize)
        self.photo_thumbnails_tab.bind("<Configure>", on_resize)

    def extract_heic_exif(self, image_path):
        import exifread
        """Extract EXIF data from HEIC files"""
        try:
            with open(image_path, 'rb') as f:
                tags = exifread.process_file(f)
            return {tag: str(value) for tag, value in tags.items()}
        except Exception as e:
            print(f"Error extracting HEIC EXIF data: {e}")
            return None
                    
    def format_exif_for_display(self, exif_data):
        """Format EXIF data into a readable string"""
        if not exif_data:
            return "No EXIF data found"
        
        # Import for GPSTAGS
        from PIL.ExifTags import TAGS, GPSTAGS
        
        # Helper function for rational conversion
        def rational_to_float(rational):
            if isinstance(rational, tuple) and len(rational) == 2:
                return rational[0] / rational[1]
            return float(rational)
        
        # Start with basic formatted string
        formatted = ""
        
        # Track which tags have been processed
        processed_tags = set()
        
        # Create sections
        sections = {
            "BASIC INFO": [],
            "CAMERA INFO": [],
            "EXPOSURE INFO": [],
            "LOCATION DATA": [],
            "OTHER INFO": []
        }
        
        # Process GPS Info first if it exists
        if 'GPSInfo' in exif_data:
            gps_info = {}
            for tag, value in exif_data['GPSInfo'].items():
                # Convert numeric tags to their text names if possible
                tag_name = GPSTAGS.get(tag, tag) if isinstance(tag, int) else tag
                gps_info[tag_name] = value
            
            # Add to location data section
            sections["LOCATION DATA"].append("GPS Information:")
            
            # Format latitude and longitude in a consistent way
            if 'GPSLatitude' in gps_info and 'GPSLatitudeRef' in gps_info:
                lat = gps_info['GPSLatitude']
                lat_ref = gps_info['GPSLatitudeRef']
                
                if isinstance(lat, tuple) and len(lat) == 3:
                    degrees = rational_to_float(lat[0])
                    minutes = rational_to_float(lat[1])
                    seconds = rational_to_float(lat[2])
                    
                    lat_value = degrees + minutes/60 + seconds/3600
                    if lat_ref == 'S':
                        lat_value = -lat_value
                    
                    # Format consistently with HEIC display pattern
                    sections["LOCATION DATA"].append(
                        f"• Latitude: {int(degrees)}° {int(minutes)}' {seconds:.2f}\" {lat_ref}"
                    )
            
            # Longitude
            if 'GPSLongitude' in gps_info and 'GPSLongitudeRef' in gps_info:
                lon = gps_info['GPSLongitude']
                lon_ref = gps_info['GPSLongitudeRef']
                
                if isinstance(lon, tuple) and len(lon) == 3:
                    degrees = rational_to_float(lon[0])
                    minutes = rational_to_float(lon[1])
                    seconds = rational_to_float(lon[2])
                    
                    lon_value = degrees + minutes/60 + seconds/3600
                    if lon_ref == 'W':
                        lon_value = -lon_value
                    
                    # Format consistently with HEIC display pattern
                    sections["LOCATION DATA"].append(
                        f"• Longitude: {int(degrees)}° {int(minutes)}' {seconds:.2f}\" {lon_ref}"
                    )
            
            # Add other GPS info
            for tag, value in gps_info.items():
                if tag not in ['GPSLatitude', 'GPSLatitudeRef', 'GPSLongitude', 'GPSLongitudeRef']:
                    sections["LOCATION DATA"].append(f"• {tag}: {value}")
            
            # Mark GPSInfo as processed
            processed_tags.add('GPSInfo')
        
        # Process remaining EXIF tags
        for tag, value in exif_data.items():
            if tag in processed_tags:
                continue
                
            # Skip empty or None values
            if value is None or value == '':
                continue
                
            # Process based on tag name
            tag_name = tag
            if isinstance(tag, int):
                tag_name = TAGS.get(tag, tag)
            
            # Skip MakerNote data (often large binary data)
            tag_str = str(tag_name).lower()
            if 'maker' in tag_str and 'note' in tag_str:
                continue
            # Determine which section to put it in
            section = "OTHER INFO"
            tag_lower = str(tag_name).lower()
            
            if any(keyword in tag_lower for keyword in ['date', 'time', 'creation', 'modified']):
                section = "BASIC INFO"
            elif any(keyword in tag_lower for keyword in ['make', 'model', 'software', 'camera']):
                section = "CAMERA INFO"
            elif any(keyword in tag_lower for keyword in ['exposure', 'aperture', 'iso', 'focal', 'flash']):
                section = "EXPOSURE INFO"
            elif any(keyword in tag_lower for keyword in ['gps', 'location', 'altitude', 'longitude', 'latitude']):
                section = "LOCATION DATA"
            
            # Add to appropriate section
            sections[section].append(f"• {tag_name}: {value}")
        
        # Build the final formatted string by section
        for section, items in sections.items():
            if items:  # Only include sections with data
                formatted += f"\n{section}:\n"
                formatted += "\n".join(items) + "\n"
        
        return formatted.strip()
    
    def update_canvas_scrollregion(self, event=None):
        """Update the canvas scroll region to encompass all thumbnails"""
        # Force an update to ensure widgets have been laid out
        if hasattr(self, 'photo_canvas') and self.photo_canvas.winfo_exists():
            self.photo_canvas.update_idletasks()
            
            # Get the bounding box of all items in the canvas
            all_items = self.photo_canvas.find_all()
            if not all_items:
                return
            
            # Calculate the total area occupied by all items
            bbox = self.photo_canvas.bbox("all")
            if not bbox:
                return
            
            # Set the scroll region with a small padding
            self.photo_canvas.configure(scrollregion=(0, 0, bbox[2]+10, bbox[3]+10))
            
            # Force another update to ensure scroll region is applied
            self.photo_canvas.update_idletasks()

    def show_image_metadata(self, image_path):
        """Display image metadata in a new window"""
        # Extract EXIF data using our unified function
        exif_data = self.extract_image_exif(image_path)
        
        # Create a new window to display metadata
        metadata_window = ctk.CTkToplevel(self)
        metadata_window.title("Image Metadata")
        metadata_window.geometry("600x500")
        
        # Create a scrollable frame
        scroll_frame = ctk.CTkScrollableFrame(metadata_window, width=580, height=450)
        scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Display the metadata
        if exif_data:
            for key, value in exif_data.items():
                # Skip binary data or very long values
                if isinstance(value, bytes) or (isinstance(value, str) and len(value) > 100):
                    value = f"[Binary data or long text, length: {len(value)}]"
                
                row = ctk.CTkFrame(scroll_frame)
                row.pack(fill="x", padx=5, pady=2)
                
                key_label = ctk.CTkLabel(row, text=str(key), width=150, anchor="w")
                key_label.pack(side="left", padx=5)
                
                value_label = ctk.CTkLabel(row, text=str(value), anchor="w")
                value_label.pack(side="left", fill="x", expand=True, padx=5)
        else:
            no_data_label = ctk.CTkLabel(scroll_frame, text="No EXIF data found in this image")
            no_data_label.pack(pady=20)
    
    def convert_to_degrees(self, value):
        """Convert GPS coordinates from various formats to decimal degrees"""
        if value is None:
            return None
            
        # Handle the array format [degrees, minutes, seconds] or [degrees, minutes, seconds_numerator/seconds_denominator]
        if isinstance(value, list) and len(value) == 3:
            d = float(value[0])
            m = float(value[1])
            
            # Handle seconds which might be a fraction
            if isinstance(value[2], str) and '/' in value[2]:
                # Handle fraction format like "3657/100"
                num, denom = value[2].split('/')
                s = float(num) / float(denom)
            else:
                s = float(value[2])
                
            return d + (m / 60.0) + (s / 3600.0)
            
        # Handle string format
        elif isinstance(value, str):
            if '/' in value:
                # Handle a single rational value
                num, denom = value.split('/')
                return float(num) / float(denom)
            else:
                # Try to parse as a decimal or handle other formats
                try:
                    return float(value)
                except ValueError:
                    # Try to parse from string format like "34 deg 56' 12.34\" N"
                    parts = re.match(r'(\d+)\s*deg\s*(\d+)\'\s*(\d+\.\d+)"\s*([NSEW])', value)
                    if parts:
                        d = float(parts.group(1))
                        m = float(parts.group(2))
                        s = float(parts.group(3))
                        ref = parts.group(4)
                        
                        result = d + (m / 60.0) + (s / 3600.0)
                        if ref in ['S', 'W']:
                            result = -result
                        return result
                    return None
                    
        # Handle tuple format used by some EXIF libraries
        elif isinstance(value, tuple) and len(value) == 3:
            d = float(value[0][0]) / float(value[0][1])
            m = float(value[1][0]) / float(value[1][1])
            s = float(value[2][0]) / float(value[2][1])
            return d + (m / 60.0) + (s / 3600.0)
            
        return None


    def show_full_image(self, image_path):
        """Show a larger version of the image with exhaustive EXIF data"""
        try:
            # Import required libraries
            from PIL import Image, ImageTk
            from PIL.ExifTags import TAGS, GPSTAGS
            import json
            import webbrowser  # For opening URLs
            
            # Create popup window
            img_window = ctk.CTkToplevel(self)
            img_window.title("Image Viewer")
            img_window.geometry("1200x900")
            img_window.grab_set()  # Make window modal
            
            # Create split layout - main content and EXIF sidebar
            content_frame = ctk.CTkFrame(img_window)
            content_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Create a horizontal split with PanedWindow
            paned = tk.PanedWindow(content_frame, orient='horizontal')
            paned.pack(fill="both", expand=True)
            
            # Left side - Image display
            image_frame = ctk.CTkFrame(paned)
            
            # Right side - EXIF data
            exif_frame = ctk.CTkFrame(paned, width=350)
            
            # Add both frames to paned window
            paned.add(image_frame)
            paned.add(exif_frame)
            paned.paneconfigure(image_frame, minsize=600)
            paned.paneconfigure(exif_frame, minsize=250)
            
            # Load and process the image
            img = Image.open(image_path)
            
            # Calculate display size
            max_width, max_height = 700, 700
            ratio = min(max_width/max(img.width, 1), max_height/max(img.height, 1))
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img_resized = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # Convert to PhotoImage
            display_img = ImageTk.PhotoImage(img_resized)
            img_window.img_ref = display_img  # Keep reference
            
            # Create image display
            img_label = ctk.CTkLabel(image_frame, image=display_img, text="")
            img_label.pack(padx=10, pady=10)
            
            # Make image clickable to close window
            img_label.bind("<Button-1>", lambda event: img_window.destroy())
            img_label.configure(cursor="hand2")  # Change cursor to hand when hovering
            
            # Add "click to close" hint below image
            click_hint = ctk.CTkLabel(image_frame, text="Click image to close", 
                                     text_color="gray", font=("Arial", 10))
            click_hint.pack(pady=(0, 5))
            
            # Add basic file info below image
            filename = os.path.basename(image_path)
            filesize = f"{os.path.getsize(image_path) / 1024:.1f} KB"
            dimensions = f"{img.width} x {img.height} pixels"
            
            info_text = f"File: {filename}\nSize: {filesize}\nDimensions: {dimensions}"
            info_label = ctk.CTkLabel(image_frame, text=info_text)
            info_label.pack(pady=5)
            
            # EXIF Title
            exif_title = ctk.CTkLabel(exif_frame, 
                                    text="EXIF Metadata", 
                                    font=("Arial", 16, "bold"))
            exif_title.pack(pady=(15,10), padx=10, anchor="w")
            
            # Create scrollable text area for EXIF data
            exif_text = ctk.CTkTextbox(exif_frame, wrap="word")
            exif_text.pack(fill="both", expand=True, padx=10, pady=(0,10))
            
            # Map buttons frame - create this BEFORE extracting EXIF
            map_buttons_frame = ctk.CTkFrame(exif_frame)
            
            # Flag to track if we have GPS coordinates
            has_gps_coords = False
            lat_value = None
            lon_value = None
            
            # Extract and format EXIF data
            try:
                exif_data = {}
                exif_formatted = ""

                if image_path.lower().endswith((".heic", ".heif")):
                    print(f"Processing HEIC file: {image_path}")
                    heic_exif = self.extract_heic_exif(image_path)
                    
                    # For HEIC files, the extract_heic_exif already returns a properly formatted dictionary
                    exif_data = heic_exif
                    exif_formatted = self.format_exif_for_display(exif_data)
                    # print(f"HEIC EXIF formatted data: {exif_formatted}")
                    exif_text.insert("1.0", exif_formatted)
                    exif_text.configure(state="disabled")
                    
                    # Add GPS coordinate extraction and mapping buttons for HEIC files
                    lat_value = None
                    lon_value = None
                    if "LOCATION DATA" in exif_formatted and 'GPS GPSLatitude' in exif_data and 'GPS GPSLongitude' in exif_data:
                        # Parse the string representation of coordinates
                        try:
                            # Get the raw string values
                            lat_str = exif_data['GPS GPSLatitude']
                            lon_str = exif_data['GPS GPSLongitude']
                            
                            # Parse the array format from the string
                            import re
                            
                            # Remove brackets and split by comma
                            if isinstance(lat_str, str) and lat_str.startswith('[') and lat_str.endswith(']'):
                                lat_parts = lat_str[1:-1].split(',')
                                lon_parts = lon_str[1:-1].split(',')
                                
                                # Convert to proper values
                                lat_values = []
                                for part in lat_parts:
                                    lat_values.append(part.strip())
                                    
                                lon_values = []
                                for part in lon_parts:
                                    lon_values.append(part.strip())
                                
                                # Now pass the parsed values to convert_to_degrees
                                lat = self.convert_to_degrees(lat_values)
                                lon = self.convert_to_degrees(lon_values)
                                
                                # Handle refs
                                lat_ref = exif_data.get('GPS GPSLatitudeRef', 'N')
                                lon_ref = exif_data.get('GPS GPSLongitudeRef', 'E')
                                
                                if lat_ref == 'S':
                                    lat = -lat
                                if lon_ref == 'W':
                                    lon = -lon
                                    
                                lat_value = lat
                                lon_value = lon
                                print(f"Parsed GPS coordinates: {lat_value}, {lon_value}")
                                
                                # Now create and show the map buttons
                                if lat_value is not None and lon_value is not None:
                                    import webbrowser
                                    
                                    google_maps_url = f"https://maps.google.com/?q={lat_value:.6f},{lon_value:.6f}"
                                    apple_maps_url = f"https://maps.apple.com/?ll={lat_value:.6f},{lon_value:.6f}&z=15"
                                    
                                    # Pack the map buttons frame
                                    map_buttons_frame.pack(fill="x", padx=10, pady=(0, 10))
                                    
                                    # Google Maps button
                                    google_maps_btn = ctk.CTkButton(
                                        map_buttons_frame, 
                                        text="Open in Google Maps",
                                        command=lambda url=google_maps_url: webbrowser.open_new_tab(url)
                                    )
                                    google_maps_btn.pack(pady=(5, 2), fill="x")
                                    
                                    # Apple Maps button
                                    apple_maps_btn = ctk.CTkButton(
                                        map_buttons_frame, 
                                        text="Open in Apple Maps",
                                        command=lambda url=apple_maps_url: webbrowser.open_new_tab(url)
                                    )
                                    apple_maps_btn.pack(pady=(2, 5), fill="x")
                        except Exception as e:
                            print(f"Error parsing GPS coordinates: {e}")
                            lat_value = None
                            lon_value = None
                            pass
                # NonApple exif work        
                else:
                    exif_info = img._getexif()
                    if exif_info:
                        for tag, value in exif_info.items():
                            decoded = TAGS.get(tag, tag)
                            exif_data[decoded] = value
                
                    # GPS Information with more detailed extraction
                    if 'GPSInfo' in exif_data:
                        gps = exif_data['GPSInfo']
                        gps_info = {}
                        
                        # Process all GPS tags
                        for gps_tag in gps:
                            gps_decoded = GPSTAGS.get(gps_tag, gps_tag)
                            gps_info[gps_decoded] = gps[gps_tag]
                        
                        # Helper function for rational values
                        def rational_to_float(rational):
                            if hasattr(rational, 'numerator') and hasattr(rational, 'denominator'):
                                return rational.numerator / rational.denominator
                            elif isinstance(rational, tuple) and len(rational) == 2:
                                return rational[0] / rational[1]
                            return float(rational)
                        
                        # Extract coordinates with proper parsing
                        try:
                            exif_formatted += "GPS INFORMATION:\n"
                            
                            # Latitude
                            if 'GPSLatitude' in gps_info and 'GPSLatitudeRef' in gps_info:
                                lat = gps_info['GPSLatitude']
                                lat_ref = gps_info['GPSLatitudeRef']
                                
                                if isinstance(lat, tuple) and len(lat) == 3:
                                    degrees = rational_to_float(lat[0])
                                    minutes = rational_to_float(lat[1])
                                    seconds = rational_to_float(lat[2])
                                    
                                    lat_value = degrees + minutes/60 + seconds/3600
                                    if lat_ref == 'S':
                                        lat_value = -lat_value
                                        
                                    exif_formatted += f"• Latitude: {lat_value:.6f}° ({int(degrees)}° {int(minutes)}' {seconds:.2f}\" {lat_ref})\n"
                            
                            # Longitude
                            if 'GPSLongitude' in gps_info and 'GPSLongitudeRef' in gps_info:
                                lon = gps_info['GPSLongitude']
                                lon_ref = gps_info['GPSLongitudeRef']
                                
                                if isinstance(lon, tuple) and len(lon) == 3:
                                    degrees = rational_to_float(lon[0])
                                    minutes = rational_to_float(lon[1])
                                    seconds = rational_to_float(lon[2])
                                    
                                    lon_value = degrees + minutes/60 + seconds/3600
                                    if lon_ref == 'W':
                                        lon_value = -lon_value
                                        
                                    exif_formatted += f"• Longitude: {lon_value:.6f}° ({int(degrees)}° {int(minutes)}' {seconds:.2f}\" {lon_ref})\n"
                            
                            # Altitude - Add detailed altitude information
                            if 'GPSAltitude' in gps_info:
                                altitude = rational_to_float(gps_info['GPSAltitude'])
                                altitude_ref = gps_info.get('GPSAltitudeRef', 0)  # 0 means above sea level
                                if altitude_ref == 1:
                                    altitude = -altitude  # Below sea level
                                exif_formatted += f"• Altitude: {altitude:.1f} meters {' below' if altitude_ref == 1 else ' above'} sea level\n"
                            
                            # GPS Time
                            if all(key in gps_info for key in ['GPSTimeStamp', 'GPSDateStamp']):
                                time_stamp = gps_info['GPSTimeStamp']
                                if isinstance(time_stamp, tuple) and len(time_stamp) == 3:
                                    hour = rational_to_float(time_stamp[0])
                                    minute = rational_to_float(time_stamp[1])
                                    second = rational_to_float(time_stamp[2])
                                    date_stamp = gps_info['GPSDateStamp']
                                    exif_formatted += f"• GPS Timestamp: {date_stamp} {int(hour):02d}:{int(minute):02d}:{second:.1f}\n"
                            
                            # Direction
                            if 'GPSImgDirection' in gps_info:
                                direction = rational_to_float(gps_info['GPSImgDirection'])
                                ref = gps_info.get('GPSImgDirectionRef', 'T')
                                ref_text = 'True North' if ref == 'T' else 'Magnetic North'
                                exif_formatted += f"• Image Direction: {direction:.1f}° ({ref_text})\n"
                            
                            # Speed
                            if 'GPSSpeed' in gps_info:
                                speed = rational_to_float(gps_info['GPSSpeed'])
                                speed_ref = gps_info.get('GPSSpeedRef', 'K')
                                speed_unit = {'K': 'km/h', 'M': 'mph', 'N': 'knots'}.get(speed_ref, 'units')
                                exif_formatted += f"• Speed: {speed:.1f} {speed_unit}\n"
                            
                            # GPS Processing Method
                            if 'GPSProcessingMethod' in gps_info:
                                method = gps_info['GPSProcessingMethod']
                                if isinstance(method, bytes):
                                    try:
                                        method = method.decode('utf-8', errors='replace').strip('\x00')
                                    except:
                                        method = f"<binary data {len(method)} bytes>"
                                exif_formatted += f"• Processing Method: {method}\n"
                            
                            # Status
                            if 'GPSStatus' in gps_info:
                                status = gps_info['GPSStatus']
                                status_text = {'A': 'Active', 'V': 'Void'}.get(status, status)
                                exif_formatted += f"• GPS Status: {status_text}\n"
                            
                            # Differential
                            if 'GPSDifferential' in gps_info:
                                diff = gps_info['GPSDifferential']
                                diff_text = {0: 'No correction', 1: 'Differential correction'}.get(diff, diff)
                                exif_formatted += f"• GPS Differential: {diff_text}\n"
                            
                            # Set flag if we have both coordinates
                            has_gps_coords = (lat_value is not None and lon_value is not None)
                            
                            # Add a line break after GPS section
                            exif_formatted += "\n"
                            
                        except Exception as gps_error:
                            exif_formatted += f"GPS data present but parsing error: {str(gps_error)}\n\n"
                        
                        # Date/Time information
                        time_section = ""
                        for key in ['DateTime', 'DateTimeOriginal', 'DateTimeDigitized', 'CreateDate', 'ModifyDate']:
                            if key in exif_data:
                                time_section += f"{key}: {exif_data[key]}\n"
                        
                        if time_section:
                            exif_formatted += "TIMESTAMPS:\n" + time_section + "\n"
                        
                        # Camera information
                        camera_section = ""
                        for key in ['Make', 'Model', 'Software', 'LensMake', 'LensModel']:
                            if key in exif_data:
                                camera_section += f"• {key}: {exif_data[key]}\n"
                        
                        if camera_section:
                            exif_formatted += "CAMERA INFORMATION:\n" + camera_section + "\n"
                        
                        # Camera settings
                        settings_section = ""
                        settings_fields = [
                            'ExposureTime', 'FNumber', 'ISOSpeedRatings', 'FocalLength', 
                            'ExposureProgram', 'Flash', 'WhiteBalance', 'MeteringMode',
                            'ExposureBiasValue', 'DigitalZoomRatio', 'SceneCaptureType',
                            'Sharpness', 'Saturation', 'Contrast'
                        ]
                        
                        for key in settings_fields:
                            if key in exif_data:
                                value = exif_data[key]
                                if key == 'ExposureTime' and isinstance(value, tuple):
                                    value = f"{value[0]}/{value[1]} sec"
                                elif key == 'FNumber' and isinstance(value, tuple):
                                    value = f"f/{value[0]/value[1]}"
                                elif key == 'FocalLength' and isinstance(value, tuple):
                                    value = f"{value[0]/value[1]}mm"
                                    
                                settings_section += f"• {key}: {value}\n"
                        
                        if settings_section:
                            exif_formatted += "CAMERA SETTINGS:\n" + settings_section + "\n"
                        
                        # Insert the formatted text
                        exif_text.insert("1.0", exif_formatted)
                        exif_text.configure(state="disabled")
                        
                        # Add map buttons if we have GPS coordinates
                        if has_gps_coords:
                            google_maps_url = f"https://maps.google.com/?q={lat_value:.6f},{lon_value:.6f}"
                            apple_maps_url = f"https://maps.apple.com/?ll={lat_value:.6f},{lon_value:.6f}&z=15"
                            
                            # Pack the map buttons frame
                            map_buttons_frame.pack(fill="x", padx=10, pady=(0, 10))
                            
                            # Google Maps button
                            google_maps_btn = ctk.CTkButton(
                                map_buttons_frame, 
                                text="Open in Google Maps",
                                command=lambda url=google_maps_url: webbrowser.open_new_tab(url)
                            )
                            google_maps_btn.pack(pady=(5, 2), fill="x")
                            
                            # Apple Maps button
                            apple_maps_btn = ctk.CTkButton(
                                map_buttons_frame, 
                                text="Open in Apple Maps",
                                command=lambda url=apple_maps_url: webbrowser.open_new_tab(url)
                            )
                            apple_maps_btn.pack(pady=(2, 5), fill="x")
                    else:
                        exif_text.insert("1.0", "No EXIF data found in this image.")

                    
            except Exception as e:
                exif_text.insert("1.0", f"Error extracting EXIF data: {str(e)}")
            
            # Add close button at the bottom
            close_btn = ctk.CTkButton(
                content_frame, text="Close", width=100,
                command=img_window.destroy
            )
            close_btn.pack(pady=5)
            
        except Exception as e:
            messagebox.showerror("Image Viewer Error", f"Could not display image: {str(e)}")

    
    def test_photo_display(self):
        """Test photo display with a folder selector"""
        photo_dir = filedialog.askdirectory(title="Select folder with photos")
        if photo_dir:
            self.display_photos(photo_dir)
            # Force switch to thumbnails tab
            self.photos_notebook.select(1)  # Select the thumbnails tab

    def _open_url(self, event, text_widget):
        """Open the URL when a hyperlink is clicked"""
        import webbrowser
        
        # Get the index of the character under the mouse
        index = text_widget._textbox.index(f"@{event.x},{event.y}")
        
        # Get all tags for this position
        tags = text_widget._textbox.tag_names(index)
        
        # Find the URL mapping tag
        for tag in tags:
            if tag in text_widget.url_mappings:
                url = text_widget.url_mappings[tag]
                webbrowser.open_new_tab(url)
                break

    def setup_interactions_table(self):
        # Create a search frame so users can filter interactions
        search_frame = ctk.CTkFrame(self.tab_interactions)
        search_frame.pack(fill="x", padx=10, pady=5)

        search_label = ctk.CTkLabel(search_frame, text="Search:")
        search_label.pack(side="left", padx=5, pady=5)

        self.interactions_search_entry = ctk.CTkEntry(search_frame, width=250)
        self.interactions_search_entry.pack(side="left", padx=5, pady=5, fill="x", expand=True)

        # Add search/clear buttons
        search_button = ctk.CTkButton(
            search_frame, text="Search",
            command=lambda: self.filter_interactions_results(self.interactions_search_entry.get())
        )
        search_button.pack(side="left", padx=5)
        
        clear_button = ctk.CTkButton(
            search_frame, text="Clear",
            command=lambda: [self.interactions_search_entry.delete(0, "end"),
                            self.filter_interactions_results("")]
        )
        clear_button.pack(side="left", padx=5)

        # Create a frame for the table
        table_frame = ctk.CTkFrame(self.tab_interactions)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Create Treeview
        self.interactions_tree = ttk.Treeview(table_frame)
        
        # Configure tags for coloring
        self.interactions_tree.tag_configure('incoming', background='#e6f2ff')  # Light blue for incoming
        self.interactions_tree.tag_configure('outgoing', background='#f0f0f0')  # Light gray for outgoing
        
        # Define columns
        self.interactions_tree["columns"] = ("event_start", "event_end", "application", "direction", "sender", "sender_id", "recipient", "recipient_id", "domain")
        self.interactions_tree.column("#0", width=0, stretch=tk.NO)
        self.interactions_tree.column("event_start", anchor=tk.W, width=150)
        self.interactions_tree.column("event_end", anchor=tk.W, width=130)
        self.interactions_tree.column("application", anchor=tk.W, width=130)
        self.interactions_tree.column("direction", anchor=tk.W, width=130)
        self.interactions_tree.column("sender", anchor=tk.W, width=80)
        self.interactions_tree.column("sender_id", anchor=tk.W, width=80)
        self.interactions_tree.column("recipient", anchor=tk.W, width=150)
        self.interactions_tree.column("recipient_id", anchor=tk.W, width=130)
        self.interactions_tree.column("domain", anchor=tk.W, width=150)

        # Create headings
        self.interactions_tree.heading("#0", text="", anchor=tk.W)
        self.interactions_tree.heading("event_start", text="Event Start", anchor=tk.W)
        self.interactions_tree.heading("event_end", text="Event End", anchor=tk.W)
        self.interactions_tree.heading("application", text="Application", anchor=tk.W)
        self.interactions_tree.heading("direction", text="Direction", anchor=tk.W)
        self.interactions_tree.heading("sender", text="Sender", anchor=tk.W)
        self.interactions_tree.heading("sender_id", text="Sender ID", anchor=tk.W)
        self.interactions_tree.heading("recipient", text="Recipient", anchor=tk.W)
        self.interactions_tree.heading("recipient_id", text="Recipient ID", anchor=tk.W)
        self.interactions_tree.heading("domain", text="Domain", anchor=tk.W)

        # Add scrollbars
        y_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.interactions_tree.yview)
        x_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.interactions_tree.xview)
        self.interactions_tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)

        y_scrollbar.pack(side="right", fill="y")
        x_scrollbar.pack(side="bottom", fill="x")
        self.interactions_tree.pack(fill="both", expand=True)

    def filter_interactions_results(self, search_term):
        """Filter interactions based on search term."""
        # Clear the table
        for item in self.interactions_tree.get_children():
            self.interactions_tree.delete(item)
        
        if hasattr(self, 'interactions_data') and self.interactions_data:
            search_term = search_term.lower()
            
            for i, interaction in enumerate(self.interactions_data):
                # Handle dictionary or tuple
                if isinstance(interaction, dict):
                    row_str = " ".join(str(interaction.get(k, "")).lower() for k in interaction.keys())
                    
                    # Get date values
                    event_start = interaction.get('Event Start', '')
                    event_end = interaction.get('Event End', '')
                    
                    # Convert timestamps for display
                    event_start_display = self.convert_timestamp(event_start)
                    event_end_display = self.convert_timestamp(event_end)
                    
                    app_val = interaction.get('Application', '')
                    direction = interaction.get('Direction', '')
                    sender = interaction.get('Sender', '')
                    sender_id = interaction.get('Sender ID', '')
                    recipient = interaction.get('Recipient', '')
                    recipient_id = interaction.get('Recipient ID', '')
                    domain = interaction.get('Domain', '')
                else:
                    # Assume it's a tuple
                    str_values = [str(val).lower() for val in interaction]
                    row_str = " ".join(str_values)
                    
                    # Map tuple values to appropriate fields - adjust indices as needed
                    event_start = interaction[0] if len(interaction) > 0 else ''
                    event_end = interaction[1] if len(interaction) > 1 else ''
                    
                    # Convert timestamps for display
                    event_start_display = self.convert_timestamp(event_start)
                    event_end_display = self.convert_timestamp(event_end)
                    
                    app_val = interaction[2] if len(interaction) > 2 else ''
                    direction = interaction[3] if len(interaction) > 3 else ''
                    sender = interaction[4] if len(interaction) > 4 else ''
                    sender_id = interaction[5] if len(interaction) > 5 else ''
                    recipient = interaction[6] if len(interaction) > 6 else ''
                    recipient_id = interaction[7] if len(interaction) > 7 else ''
                    domain = interaction[8] if len(interaction) > 8 else ''
                
                if search_term in row_str:
                    item_id = self.interactions_tree.insert(
                        "", "end", text=i,
                        values=(
                            event_start_display,  # Now timezone-adjusted
                            event_end_display,    # Now timezone-adjusted
                            app_val, direction, sender, sender_id, recipient, recipient_id, domain
                        )
                    )
                    
                    # Apply color based on direction
                    direction_lower = str(direction).lower()
                    if 'incoming' in direction_lower:
                        self.interactions_tree.item(item_id, tags=('incoming',))
                    elif 'outgoing' in direction_lower:
                        self.interactions_tree.item(item_id, tags=('outgoing',))

    def create_video_thumbnail(self, video_path, size=(150, 150)):
        """Generate thumbnail from the first frame of a video"""
        try:
            # Try to use OpenCV if available
            import cv2
            cap = cv2.VideoCapture(video_path)
            ret, frame = cap.read()
            cap.release()
            
            if ret:
                # Convert BGR to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame_rgb)
                img.thumbnail(size)
                return img
            else:
                # Fallback if frame can't be read
                return self.create_generic_thumbnail("Video", size)
        except ImportError:
            # Fallback if OpenCV is not available
            return self.create_generic_thumbnail("Video", size)

    def create_heic_thumbnail(self, heic_path, size=(150, 150)):
        """Generate thumbnail from HEIC file"""
        try:
            # Try to use pillow-heif if available
            from pillow_heif import register_heif_opener
            register_heif_opener()
            
            # Now PIL should be able to open HEIC files
            img = Image.open(heic_path)
            img.thumbnail(size)
            return img
        except ImportError:
            # Fallback if pillow-heif is not available
            return self.create_generic_thumbnail("HEIC", size)
        except Exception as e:
            # Fallback for any other errors
            print(f"Error opening HEIC file: {e}")
            return self.create_generic_thumbnail("HEIC", size)

    def create_generic_thumbnail(self, text, size=(150, 150)):
        """Create a generic thumbnail with text when media can't be opened"""
        img = Image.new('RGB', size, color=(50, 50, 50))
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(img)
        try:
            # Try to use a font if available
            font = ImageFont.truetype("Arial", 16)
        except IOError:
            font = ImageFont.load_default()
        
        # Center the text
        text_width, text_height = draw.textbbox((0, 0), text, font=font)[2:4]
        position = ((size[0] - text_width) // 2, (size[1] - text_height) // 2)
        
        # Draw text in white
        draw.text(position, text, fill=(255, 255, 255), font=font)
        return img

    def show_media_file(self, path):
        """Handle opening of image or video files"""
        file_ext = os.path.splitext(path.lower())[1]
        
        if file_ext in ['.mp4', '.mov', '.m4v', '.3gp']:
            # For videos, use system default player    
            try:
                if platform.system() == 'Darwin':  # macOS
                    subprocess.run(['open', path])
                elif platform.system() == 'Windows':
                    os.startfile(path)
                else:  # Linux
                    subprocess.run(['xdg-open', path])
            except Exception as e:
                messagebox.showerror("Error", f"Could not open video file: {str(e)}")
        else:
            # For images, use the existing viewer
            self.show_full_image(path)

    def extract_image_exif(self, image_path):
        """Extract EXIF data from any image type including HEIC/HEIF"""
        exif_data = {}
        
        # Check if it's a HEIC/HEIF file
        if image_path.lower().endswith(('.heic', '.heif')):
            try:
                # Method 1: Use pyheif library
                import pyheif
                
                heif_file = pyheif.read(image_path)
                # Extract metadata
                for metadata in heif_file.metadata or []:
                    if metadata['type'] == 'Exif':
                        # Skip the TIFF header (first 8 bytes)
                        import io
                        from PIL import Image
                        from PIL.ExifTags import TAGS
                        
                        exif_stream = io.BytesIO(metadata['data'][8:])
                        exif_info = Image.Exif()
                        exif_info.load(exif_stream)
                        
                        # Convert to dictionary
                        for tag_id, value in exif_info.items():
                            tag = TAGS.get(tag_id, tag_id)
                            exif_data[tag] = value
                        
                        return exif_data
                        
            except (ImportError, Exception) as e:
                # Method 2: Use exiftool as fallback
                try:
                    import subprocess
                    result = subprocess.run(['exiftool', '-json', image_path], 
                                          capture_output=True, text=True)
                    
                    import json
                    exif_data = json.loads(result.stdout)[0]
                    return exif_data
                    
                except Exception as e2:
                    print(f"HEIC extraction fallback failed: {e2}")
                    return {"Error": f"Failed to extract EXIF data: {str(e)}, {str(e2)}"}
        else:
            # Regular image formats
            try:
                from PIL import Image
                from PIL.ExifTags import TAGS
                
                img = Image.open(image_path)
                if hasattr(img, '_getexif'):
                    exif_info = img._getexif()
                    if exif_info:
                        for tag, value in exif_info.items():
                            decoded = TAGS.get(tag, tag)
                            exif_data[decoded] = value
            except Exception as e:
                return {"Error": f"Failed to extract EXIF: {str(e)}"}
        
        return exif_data
