# Copyright (c) 2025 North Loop Consulting, LLC - Charlie Rubisoff
# GPLv3 License - https://www.gnu.org/licenses/gpl-3.

import os
import sys
import customtkinter as ctk
from PIL import Image, ImageTk
import threading
import logging
import subprocess
import time
import tkinter as tk
import tkinter.ttk as ttk
from tkinter import messagebox, filedialog
import webbrowser
import platform
import concurrent.futures
import pytz
from concurrent.futures import ThreadPoolExecutor
import re

# Windows-specific subprocess flag to prevent console windows
if sys.platform == "win32":
    SUBPROCESS_FLAGS = subprocess.CREATE_NO_WINDOW
else:
    SUBPROCESS_FLAGS = 0

# todo
# fix the exif heic data in ios thumbnails



# Ensure the project root is in the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = current_dir
if project_root not in sys.path:
    sys.path.insert(0, current_dir)

# Configure CustomTkinter appearance
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class UnifiedArsenicApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Configure window
        self.title("Arsenic Triage Tool - North Loop Consulting © 2025")
        self.geometry("1200x800")
        self.minsize(1000, 700)
        
        # Configure logging
        logging.basicConfig(level=logging.INFO, 
                           format='%(asctime)s - %(levelname)s - %(message)s')
        
        # Initialize variables
        self._device_refresh_triggered = False
        
        # Create the UI
        self.create_header()
        self.create_main_tabs()
        
        # Auto-refresh device info after UI is ready
        self.after(1500, self.refresh_device_info)  # Reduced delay for iOS
        
        # Start monitoring Android devices for sidebar status - start sooner and more frequently
        self.after(500, self.monitor_android_status)  # Even earlier start for Android
        
    def update_device_status_sidebar(self):
        """Update device status indicators in sidebar"""
        def update_ios_status():
            # This will be called from the device refresh
            pass
            
        def update_android_status():
            # This will be called from Android device monitoring
            pass
            
    def monitor_android_status(self):
        """Monitor Android device status for sidebar"""
        def check_android():
            try:
                
                # Try local ADB from utils directory first (try both adb and adb.exe)
                local_adb = os.path.join(current_dir, "src", "utils", "adb")
                local_adb_exe = os.path.join(current_dir, "src", "utils", "adb.exe")
                
                # Use the local ADB path first, then fall back to system ADB
                adb_commands = []
                if platform.system() == "Windows":
                    if os.path.exists(local_adb_exe):
                        adb_commands.append(local_adb_exe)
                else:
                    if os.path.exists(local_adb):
                        adb_commands.append(local_adb)
                    if os.path.exists(local_adb_exe):
                        adb_commands.append(local_adb_exe)
                    
                # Then try system ADB
                adb_commands.append('adb')
                
                result = None
                adb_used = None
                
                for adb_command in adb_commands:
                    try:
                #         print(f"DEBUG: Monitor trying ADB command: {adb_command}")
                        result = subprocess.run([adb_command, 'devices'], 
                                              capture_output=True, text=True, timeout=5,
                                              creationflags=SUBPROCESS_FLAGS)
                        adb_used = adb_command
                        # print(f"DEBUG: Monitor ADB command '{adb_command}' worked!")
                        break
                    except FileNotFoundError:
                        print(f"DEBUG: Monitor ADB command '{adb_command}' not found")
                        continue
                    except Exception as e:
                        print(f"DEBUG: Monitor ADB command '{adb_command}' failed: {e}")
                        continue
                
                if result is None:
                #     print("DEBUG: Monitor - No working ADB command found")
                    self.after(0, lambda: self.android_status_indicator.configure(text="🟡 Android: ADB unavailable"))
                    return
                
                # print(f"DEBUG: Monitor ADB output from '{adb_used}':\n{result.stdout}")
                
                devices = []
                for line in result.stdout.split('\n'):
                    line = line.strip()
                    if line and 'device' in line and not line.startswith('List'):
                        # Make sure it's actually a device line, not just containing 'device'
                        parts = line.split('\t')
                        if len(parts) >= 2 and parts[1] == 'device':
                            devices.append(line)
                            # print(f"DEBUG: Monitor found Android device: {line}")
                
                if devices:
                    # print(f"DEBUG: Monitor found {len(devices)} Android devices, updating sidebar to green")
                    self.after(0, lambda: self.android_status_indicator.configure(text="🟢 Android: Connected"))
                else:
                    # print("DEBUG: Monitor found no Android devices, updating sidebar to red")
                    self.after(0, lambda: self.android_status_indicator.configure(text="🔴 Android: No device"))
                    
            except Exception as e:
                print(f"DEBUG: Monitor Android status check error: {e}")
                self.after(0, lambda: self.android_status_indicator.configure(text="🟡 Android: Check failed"))
        
        threading.Thread(target=check_android, daemon=True).start()
        
        # Schedule next check - reduced frequency to every 3 seconds for more responsive updates
        self.after(3000, self.monitor_android_status)
        
    def check_android_status_immediate(self):
        """Immediately check Android status when switching to Android platform"""
        print("DEBUG: Immediate Android status check triggered")
        
        def check_android():
            try:
                # Try both the local ADB and system ADB
                adb_commands = []
                
                # Add local ADB path if it exists (try both adb and adb.exe)
                local_adb = os.path.join(current_dir, "src", "utils", "adb")
                local_adb_exe = os.path.join(current_dir, "src", "utils", "adb.exe")
                
                if os.path.exists(local_adb):
                    adb_commands.append(local_adb)
                if os.path.exists(local_adb_exe):
                    adb_commands.append(local_adb_exe)
                    
                # Then try system ADB
                adb_commands.append('adb')
                
                result = None
                adb_used = None
                
                for adb_cmd in adb_commands:
                    try:
                        print(f"DEBUG: Immediate check trying ADB command: {adb_cmd}")
                        result = subprocess.run([adb_cmd, 'devices'], 
                                              capture_output=True, text=True, timeout=5,
                                              creationflags=SUBPROCESS_FLAGS)
                        adb_used = adb_cmd
                        print(f"DEBUG: Immediate check - ADB command '{adb_cmd}' worked!")
                        break
                    except FileNotFoundError:
                        print(f"DEBUG: Immediate check - ADB command '{adb_cmd}' not found")
                        continue
                    except Exception as e:
                        print(f"DEBUG: Immediate check - ADB command '{adb_cmd}' failed: {e}")
                        continue
                
                if result is None:
                    print("DEBUG: Immediate check - No working ADB command found")
                    self.after(0, lambda: self.android_status_indicator.configure(text="🟡 Android: ADB unavailable"))
                    return
                
                print(f"DEBUG: Immediate check ADB output from '{adb_used}':\n{result.stdout}")
                
                devices = []
                for line in result.stdout.split('\n'):
                    line = line.strip()
                    if line and 'device' in line and not line.startswith('List'):
                        # Make sure it's actually a device line, not just containing 'device'
                        parts = line.split('\t')
                        if len(parts) >= 2 and parts[1] == 'device':
                            devices.append(line)
                            print(f"DEBUG: Immediate check found Android device: {line}")
                
                if devices:
                    print(f"DEBUG: Immediate check found {len(devices)} Android devices, updating sidebar to green")
                    self.after(0, lambda: self.android_status_indicator.configure(text="🟢 Android: Connected"))
                else:
                    print("DEBUG: Immediate check found no Android devices, updating sidebar to red")
                    self.after(0, lambda: self.android_status_indicator.configure(text="🔴 Android: No device"))
                    
            except Exception as e:
                print(f"DEBUG: Immediate Android status check error: {e}")
                self.after(0, lambda: self.android_status_indicator.configure(text="🟡 Android: Check failed"))
        
        threading.Thread(target=check_android, daemon=True).start()

    def create_header(self):
        """Create application header with logo, title, and case management controls"""
        header_frame = ctk.CTkFrame(self)
        header_frame.pack(fill="x", padx=10, pady=(10, 5))
        
        # Load main app icon/logo
        self.main_logo = None
        try:
            icons_dir = os.path.join(current_dir, "src", "assets", "icons")
            logo_path = os.path.join(icons_dir, "app_icon.png")
            
            if os.path.exists(logo_path):
                self.main_logo_pil = Image.open(logo_path)
                self.main_logo = ctk.CTkImage(
                    light_image=self.main_logo_pil, 
                    dark_image=self.main_logo_pil, 
                    size=(60, 60)
                )
        except Exception as e:
            print(f"Failed to load main logo: {e}")
        
        # Create main horizontal layout
        main_header_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        main_header_frame.pack(fill="x", pady=10)
        
        # Left side - Logo and title section
        left_section = ctk.CTkFrame(main_header_frame, fg_color="transparent")
        left_section.pack(side="left", fill="y")
        
        # Logo (or emoji fallback)
        if self.main_logo:
            logo_label = ctk.CTkLabel(left_section, image=self.main_logo, text="")
        else:
            logo_label = ctk.CTkLabel(left_section, text="🔧", font=ctk.CTkFont(size=40))
        logo_label.pack(side="left", padx=10)
        
        # Title and info
        title_frame = ctk.CTkFrame(left_section, fg_color="transparent")
        title_frame.pack(side="left", fill="y", padx=10)
        
        main_title = ctk.CTkLabel(
            title_frame,
            text="ARSENIC Mobile Triage Tool",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=("gray10", "gray90")
        )
        main_title.pack(anchor="w")
        
        subtitle = ctk.CTkLabel(
            title_frame,
            text="North Loop Consulting - Version 2.0",
            font=ctk.CTkFont(size=14),
            text_color=("gray40", "gray60")
        )
        subtitle.pack(anchor="w", pady=(5, 0))
        
        # Right side - Case management section (using grid for better alignment)
        right_section = ctk.CTkFrame(main_header_frame, fg_color="transparent")
        right_section.pack(side="right", fill="y", padx=20)
        
        # Configure grid columns for consistent width
        right_section.columnconfigure(1, weight=1, minsize=250)
        
        # Case Number row
        case_label = ctk.CTkLabel(
            right_section,
            text="Case Number:",
            font=ctk.CTkFont(size=12, weight="bold"),
            width=120,
            anchor="w"
        )
        case_label.grid(row=0, column=0, sticky="w", padx=(0, 10), pady=(0, 5))
        
        self.case_number_entry = ctk.CTkEntry(
            right_section,
            width=250,
            placeholder_text="Enter case number..."
        )
        self.case_number_entry.grid(row=0, column=1, sticky="ew", pady=(0, 5))
        
        # Output Directory row
        output_label = ctk.CTkLabel(
            right_section,
            text="Output Directory:",
            font=ctk.CTkFont(size=12, weight="bold"),
            width=120,
            anchor="w"
        )
        output_label.grid(row=1, column=0, sticky="w", padx=(0, 10), pady=(0, 5))
        
        # Directory selection with entry and button in a subframe
        dir_frame = ctk.CTkFrame(right_section, fg_color="transparent")
        dir_frame.grid(row=1, column=1, sticky="ew", pady=(0, 5))
        dir_frame.columnconfigure(0, weight=1)
        
        self.output_directory_entry = ctk.CTkEntry(
            dir_frame,
            placeholder_text="Select output directory..."
        )
        self.output_directory_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        
        browse_button = ctk.CTkButton(
            dir_frame,
            text="Browse",
            width=70,
            command=self.browse_output_directory
        )
        browse_button.grid(row=0, column=1)

    def browse_output_directory(self):
        """Browse and select output directory for case files"""
        from tkinter import filedialog
        
        directory = filedialog.askdirectory(
            title="Select Output Directory for Case Files",
            initialdir=os.path.expanduser("~/Desktop")
        )
        
        if directory:
            self.output_directory_entry.delete(0, "end")
            self.output_directory_entry.insert(0, directory)
            
            # Optionally create a case-specific subdirectory if case number is provided
            case_number = self.case_number_entry.get().strip()
            if case_number:
                case_dir = os.path.join(directory, f"Case_{case_number}")
                try:
                    os.makedirs(case_dir, exist_ok=True)
                    self.output_directory_entry.delete(0, "end")
                    self.output_directory_entry.insert(0, case_dir)
                except Exception as e:
                    print(f"Could not create case directory: {e}")
            
            # REFRESH ANDROID TRIAGE DISPLAY
            self.refresh_android_triage_case_info()

    def refresh_android_triage_case_info(self):
        """Refresh case info display in Android triage frame"""
        try:
            if hasattr(self, 'android_triage_frame') and hasattr(self.android_triage_frame, 'refresh_case_info_display'):
                self.android_triage_frame.refresh_case_info_display()
        except Exception as e:
            print(f"Error refreshing Android triage case info: {e}")

    # Also add event bindings to refresh when case number changes
    def setup_header_event_bindings(self):
        """Set up event bindings for header inputs"""
        # Bind case number changes
        self.case_number_entry.bind('<KeyRelease>', lambda e: self.after(500, self.refresh_android_triage_case_info))
        self.case_number_entry.bind('<FocusOut>', lambda e: self.refresh_android_triage_case_info())
        
        # Call this method after creating the header
        # Add this line to the end of create_header()
        self.after(100, self.setup_header_event_bindings)
        
    def get_case_number(self):
        """Get the current case number"""
        return self.case_number_entry.get().strip()

    def get_output_directory(self):
        """Get the current output directory"""
        return self.output_directory_entry.get().strip()

    def set_case_number(self, case_number):
        """Set the case number"""
        self.case_number_entry.delete(0, "end")
        self.case_number_entry.insert(0, case_number)

    def set_output_directory(self, directory):
        """Set the output directory"""
        self.output_directory_entry.delete(0, "end")
        self.output_directory_entry.insert(0, directory)  

    def create_main_tabs(self):
        """Create main interface with side navigation instead of tabs"""
        # Main container
        main_container = ctk.CTkFrame(self)
        main_container.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        
        # Left sidebar for platform selection
        self.sidebar = ctk.CTkFrame(main_container, width=200, corner_radius=10)
        self.sidebar.pack(side="left", fill="y", padx=(0, 10), pady=0)
        self.sidebar.pack_propagate(False)  # Maintain fixed width
        
        # Right content area
        self.content_area = ctk.CTkFrame(main_container, corner_radius=10)
        self.content_area.pack(side="right", fill="both", expand=True, padx=0, pady=0)
        
        # Setup sidebar navigation
        self.setup_sidebar()
        
        # Initially show iOS content
        self.current_platform = "ios"
        self.setup_ios_content()
        
    def setup_sidebar(self):
        """Setup the sidebar navigation"""
        # Sidebar title
        sidebar_title = ctk.CTkLabel(
            self.sidebar, 
            text="Platform", 
            font=ctk.CTkFont(size=18, weight="bold")
        )
        sidebar_title.pack(pady=(20, 10))
        
        # iOS Button
        self.ios_nav_button = ctk.CTkButton(
            self.sidebar,
            text="iOS Device",
            text_color="black",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=50,
            width=160,
            command=self.show_ios_platform,
            fg_color=("gray75", "gray25"),  # Selected state
            hover_color=("gray70", "gray30")
        )
        self.ios_nav_button.pack(pady=(10, 5), padx=20)
        
        # Android Button
        self.android_nav_button = ctk.CTkButton(
            self.sidebar,
            text="Android Device", 
            text_color="black",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=50,
            width=160,
            command=self.show_android_platform,
            fg_color="transparent",  # Unselected state
            hover_color=("gray75", "gray25")
        )
        self.android_nav_button.pack(pady=5, padx=20)
        
        # Separator
        separator = ctk.CTkFrame(self.sidebar, height=2, fg_color=("gray80", "gray20"))
        separator.pack(fill="x", padx=20, pady=20)
        
        # Status section
        status_label = ctk.CTkLabel(
            self.sidebar, 
            text="Device Status", 
            font=ctk.CTkFont(size=14, weight="bold")
        )
        status_label.pack(pady=(10, 5))
        
        # iOS status
        self.ios_status_indicator = ctk.CTkLabel(
            self.sidebar, 
            text="🔵 iOS: Checking...", 
            font=ctk.CTkFont(size=11)
        )
        self.ios_status_indicator.pack(pady=2, padx=10)
        
        # Android status  
        self.android_status_indicator = ctk.CTkLabel(
            self.sidebar, 
            text="🔵 Android: Checking...", 
            font=ctk.CTkFont(size=11)
        )
        self.android_status_indicator.pack(pady=2, padx=10)
        
    def show_ios_platform(self):
        """Switch to iOS platform"""
        if self.current_platform != "ios":
            self.current_platform = "ios"
            self.update_nav_buttons()
            self.clear_content_area()
            self.setup_ios_content()
            
    def show_android_platform(self):
        """Switch to Android platform"""
        if self.current_platform != "android":
            self.current_platform = "android"
            self.update_nav_buttons()
            self.clear_content_area()
            self.setup_android_content()
            
            # Immediately check Android device status when switching to Android
            print("DEBUG: Switching to Android platform, triggering immediate device check")
            self.after(50, self.check_android_status_immediate)
            
    def update_nav_buttons(self):
        """Update navigation button states"""
        if self.current_platform == "ios":
            self.ios_nav_button.configure(fg_color=("gray75", "gray25"))
            self.android_nav_button.configure(fg_color="transparent")
        else:
            self.android_nav_button.configure(fg_color=("gray75", "gray25"))
            self.ios_nav_button.configure(fg_color="transparent")
            
    def clear_content_area(self):
        """Clear the content area"""
        for widget in self.content_area.winfo_children():
            widget.destroy()
            
    def setup_ios_content(self):
        """Setup iOS content in the main area"""
        # Platform header
        header = ctk.CTkFrame(self.content_area)
        header.pack(fill="x", padx=10, pady=(10, 5))
        
        platform_title = ctk.CTkLabel(
            header, 
            text="iOS Device Management", 
            font=ctk.CTkFont(size=20, weight="bold")
        )
        platform_title.pack(side="left", padx=15, pady=10)
        
        # Create sub-tabs for iOS functions
        self.ios_subtabs = ctk.CTkTabview(self.content_area)
        self.ios_subtabs.pack(fill="both", expand=True, padx=10, pady=5)
        
        # iOS sub-tabs
        self.ios_backup_tab = self.ios_subtabs.add("Device Backup")
        self.ios_parse_tab = self.ios_subtabs.add("Parse Backup")
        
        # Setup iOS backup tab
        self.setup_ios_backup()
        self.setup_ios_parse()
        
    def setup_android_content(self):
        """Setup Android content in the main area"""
        # Platform header
        header = ctk.CTkFrame(self.content_area)
        header.pack(fill="x", padx=10, pady=(10, 5))
        
        platform_title = ctk.CTkLabel(
            header, 
            text="Android Device Management", 
            font=ctk.CTkFont(size=20, weight="bold")
        )
        platform_title.pack(side="left", padx=15, pady=10)
        
        # Create sub-tabs for Android functions
        self.android_subtabs = ctk.CTkTabview(self.content_area)
        self.android_subtabs.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Android sub-tabs
        self.android_triage_tab = self.android_subtabs.add("Triage")
        self.android_backup_tab = self.android_subtabs.add("Backup")
        # self.android_analysis_tab = self.android_subtabs.add("Analysis")
        
        # Setup Android tabs
        self.setup_android_triage()
        self.setup_android_backup()
        # self.setup_android_analysis()
        
    def setup_ios_backup(self):
        """Setup iOS backup functionality"""
        # Main container with left and right panes
        backup_container = ctk.CTkFrame(self.ios_backup_tab)
        backup_container.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Left pane for device info and controls
        left_pane = ctk.CTkFrame(backup_container)
        left_pane.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        
        # Right pane for apps list
        right_pane = ctk.CTkFrame(backup_container, width=300)
        right_pane.pack(side="right", fill="both", expand=True, padx=5, pady=5)
        
        # Device info section in left pane
        device_frame = ctk.CTkFrame(left_pane)
        device_frame.pack(fill="x", padx=5, pady=5)
        
        device_label = ctk.CTkLabel(device_frame, 
                                   text="Device Information", 
                                   font=ctk.CTkFont(size=16, weight="bold"))
        device_label.pack(pady=5)
        
        self.ios_device_status = ctk.CTkLabel(device_frame, text="Checking for device...")
        self.ios_device_status.pack(pady=5)
        
        self.ios_device_info_text = ctk.CTkTextbox(device_frame, height=100, wrap="word")
        self.ios_device_info_text.pack(fill="x", padx=10, pady=5)
        self.ios_device_info_text.insert("0.0", "Connect an iOS device to view device information...")
        
        refresh_button = ctk.CTkButton(device_frame, 
                                      text="Refresh Device Info", 
                                      command=self.manual_refresh_device_info)
        refresh_button.pack(pady=10)
        
        # Backup options section
        options_frame = ctk.CTkFrame(left_pane)
        options_frame.pack(fill="x", padx=5, pady=5)
        
        options_label = ctk.CTkLabel(options_frame, 
                                    text="Backup Options", 
                                    font=ctk.CTkFont(size=16, weight="bold"))
        options_label.pack(pady=5)
        
        # Information about centralized case management
        info_label = ctk.CTkLabel(options_frame, 
                                 text="Creates encrypted iOS device backup and collects logs.\nWill attempt to set backup password of 1234.\nMonitor the iOS device for prompts.", 
                                 font=ctk.CTkFont(size=12),
                                 justify="center")
        info_label.pack(pady=10)
        
        # Backup button
        backup_button = ctk.CTkButton(options_frame, 
                                     text="Start iOS Backup", 
                                     font=ctk.CTkFont(size=14, weight="bold"),
                                     height=40,
                                     command=self.start_ios_backup)
        backup_button.pack(pady=15)
        
        # Progress section
        progress_frame = ctk.CTkFrame(left_pane)
        progress_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        progress_label = ctk.CTkLabel(progress_frame, 
                                     text="Backup Progress", 
                                     font=ctk.CTkFont(size=16, weight="bold"))
        progress_label.pack(pady=5)
        
        self.ios_progress_bar = ctk.CTkProgressBar(progress_frame)
        self.ios_progress_bar.pack(fill="x", padx=10, pady=5)
        self.ios_progress_bar.set(0)
        
        self.ios_status_text = ctk.CTkTextbox(progress_frame, height=150)
        self.ios_status_text.pack(fill="both", expand=True, padx=10, pady=5)
        self.ios_status_text.insert("0.0", "Ready to start backup...\n")
        
        # Apps list in right pane
        apps_frame = ctk.CTkFrame(right_pane)
        apps_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        apps_label = ctk.CTkLabel(apps_frame, 
                                 text="Installed Apps", 
                                 font=ctk.CTkFont(size=16, weight="bold"))
        apps_label.pack(pady=5)
        
        self.ios_apps_count = ctk.CTkLabel(apps_frame, text="0 apps")
        self.ios_apps_count.pack(pady=5)
        
        # Add search functionality
        search_frame = ctk.CTkFrame(apps_frame)
        search_frame.pack(fill="x", padx=10, pady=5)
        
        search_label = ctk.CTkLabel(search_frame, text="Search:")
        search_label.pack(side="left", padx=5)
        
        self.ios_apps_search_entry = ctk.CTkEntry(search_frame, placeholder_text="Type to search apps...")
        self.ios_apps_search_entry.pack(side="left", fill="x", expand=True, padx=5)
        self.ios_apps_search_entry.bind("<KeyRelease>", self.on_ios_apps_search)
        
        clear_search_button = ctk.CTkButton(search_frame, text="Clear", width=60, 
                                          command=self.clear_ios_apps_search)
        clear_search_button.pack(side="right", padx=5)
        
        # Add sorting options
        sort_frame = ctk.CTkFrame(apps_frame)
        sort_frame.pack(fill="x", padx=10, pady=5)
        
        sort_label = ctk.CTkLabel(sort_frame, text="Sort:")
        sort_label.pack(side="left", padx=5)
        
        self.ios_apps_sort_var = tk.StringVar(value="Alphabetical")
        self.ios_apps_sort_menu = ctk.CTkOptionMenu(sort_frame, 
                                                   values=["Alphabetical", "Reverse Alphabetical", "By Length"],
                                                   variable=self.ios_apps_sort_var,
                                                   command=self.on_ios_apps_sort_change)
        self.ios_apps_sort_menu.pack(side="left", padx=5)
        
        self.ios_apps_list = ctk.CTkTextbox(apps_frame, height=320)  # Reduced height to accommodate sort controls
        self.ios_apps_list.pack(fill="both", expand=True, padx=10, pady=5)
        self.ios_apps_list.insert("0.0", "No apps detected yet...")
        
        # Initialize apps data
        self.ios_apps_data = []
        
    def setup_ios_parse(self):
        """Setup iOS backup parsing functionality"""
        # Import required modules for parsing
        try:
            import tkinter as tk
            from src.parser.backup_parser import parse_backup, parse_ios_backup
            import datetime
            import pytz
            from tzlocal import get_localzone
        except ImportError as e:
            print(f"Could not import required modules for iOS parsing: {e}")
            self._setup_ios_parse_fallback()
            return
            
        try:
            # Create a frame for the backup selection
            self.parse_top_frame = ctk.CTkFrame(self.ios_parse_tab)
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
            
            # Password field (hidden initially but properly positioned)
            self.password_label = ctk.CTkLabel(self.parse_top_frame, text="Backup Password:")
            self.password_entry = ctk.CTkEntry(self.parse_top_frame, width=400, placeholder_text="Enter backup password if encrypted")
            
            # Output folder selection
            # self.output_folder_label = ctk.CTkLabel(self.parse_top_frame, text="Output Location:")
            # self.output_folder_label.grid(row=1, column=0, padx=5, pady=5, sticky="w")
            
            # self.output_folder_path = ctk.CTkEntry(self.parse_top_frame, width=400)
            # self.output_folder_path.grid(row=1, column=1, padx=5, pady=5, sticky="we")
            
            # self.browse_output_button = ctk.CTkButton(
            #     self.parse_top_frame, text="Browse", width=80, 
            #     command=self.browse_output_folder
            # )
            # self.browse_output_button.grid(row=1, column=2, padx=5, pady=5)
            
            # Controls frame with taxonomy and timezone options
            self.controls_frame = ctk.CTkFrame(self.parse_top_frame)
            self.controls_frame.grid(row=2, column=0, columnspan=3, padx=5, pady=5, sticky="we")
            
            # Taxonomy options
            self.taxonomy_frame = ctk.CTkFrame(self.controls_frame, fg_color="transparent")
            self.taxonomy_frame.pack(side="left", fill="x", expand=True, padx=5, pady=5)
            
            self.enable_taxonomy_var = tk.BooleanVar(value=False)
            self.enable_taxonomy_checkbox = ctk.CTkCheckBox(
                self.taxonomy_frame, 
                text="Filter photos by scene classification:", 
                variable=self.enable_taxonomy_var,
                command=self.toggle_taxonomy_dropdown
            )
            self.enable_taxonomy_checkbox.pack(side="left", padx=5, pady=5)
            
            self.taxonomy_label = ctk.CTkLabel(self.taxonomy_frame, text="Scene type:")
            self.taxonomy_label.pack(side="left", padx=(10, 5), pady=5)
            
            self.taxonomy_var = tk.StringVar()
            self.taxonomy_dropdown = ctk.CTkOptionMenu(
                self.taxonomy_frame,
                values=self.get_taxonomy_options(),
                variable=self.taxonomy_var,
                state="disabled"
            )
            self.taxonomy_dropdown.pack(side="left", padx=5, pady=5)
            
            # Timezone options
            timezone_frame = ctk.CTkFrame(self.controls_frame, fg_color="transparent")
            timezone_frame.pack(side="right", fill="x", padx=5, pady=5)
            
            timezone_label = ctk.CTkLabel(timezone_frame, text="Display times in:")
            timezone_label.pack(side="left", padx=5, pady=5)
            
            # Setup timezone options
            self._setup_timezone_options()
            
            self.timezone_var = tk.StringVar(value=self.timezone_options[0])
            self.timezone_dropdown = ctk.CTkOptionMenu(
                timezone_frame,
                values=self.timezone_options,
                variable=self.timezone_var,
                command=self.update_timezone_preference
            )
            self.timezone_dropdown.pack(side="left", padx=5, pady=5)
            
            # Parse button
            self.button_frame = ctk.CTkFrame(self.parse_top_frame, fg_color="transparent", height=50)
            self.button_frame.grid(row=3, column=0, columnspan=3, padx=5, pady=20, sticky="nswe")
            self.button_frame.grid_propagate(False)
            self.button_frame.columnconfigure(0, weight=1)
            
            self.parse_button = ctk.CTkButton(
                self.button_frame, text="Parse Backup", 
                font=ctk.CTkFont(size=14, weight="bold"),
                height=40, width=200,
                command=self.start_ios_parse
            )
            self.parse_button.grid(row=0, column=0, padx=5, pady=5)
            
            # Status
            self.parse_status_label = ctk.CTkLabel(self.parse_top_frame, text="Status:")
            self.parse_status_label.grid(row=4, column=0, padx=5, pady=5, sticky="w")
            
            self.parse_status_text = ctk.CTkLabel(self.parse_top_frame, text="Ready")
            self.parse_status_text.grid(row=4, column=1, columnspan=2, padx=5, pady=5, sticky="w")
            
            # Results frame with tabs
            self.parse_results_frame = ctk.CTkFrame(self.ios_parse_tab)
            self.parse_results_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            self.parse_results_tabview = ctk.CTkTabview(self.parse_results_frame)
            self.parse_results_tabview.pack(fill="both", expand=True)
            
            # Create result tabs
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
            
            # Setup content areas
            self.setup_ios_parse_tabs()
            
        except Exception as e:
            print(f"Error setting up iOS parse functionality: {e}")
            # Print traceback for debugging but don't let it crash the app
            import traceback
            traceback.print_exc()
            self._setup_ios_parse_fallback()
            
    def _setup_ios_parse_fallback(self):
        """Fallback iOS parse setup if full functionality fails"""
        parse_label = ctk.CTkLabel(self.ios_parse_tab, 
                                  text="iOS Backup Parser", 
                                  font=ctk.CTkFont(size=20, weight="bold"))
        parse_label.pack(pady=20)
        
        info_label = ctk.CTkLabel(self.ios_parse_tab, 
                                 text="Select an iOS backup folder to parse and analyze")
        info_label.pack(pady=10)
            
    def setup_android_triage(self):
        """Setup Android triage functionality using the original DroidTriageFrame"""
        try:
            # Import and use the existing DroidTriageFrame
            from src.ui.droid_triage_frame import DroidTriageFrame
            
            # Add the DroidTriageFrame to the triage tab
            self.android_triage_frame = DroidTriageFrame(self.android_triage_tab)
            self.android_triage_frame.pack(fill="both", expand=True)
            
            # Hook into the triage frame's device monitoring to update our sidebar
            self.setup_android_device_callback()
            
        except ImportError as e:
            print(f"Could not import DroidTriageFrame: {e}")
            # Fallback implementation
            self._setup_android_triage_fallback()
        except Exception as e:
            print(f"Error setting up Android triage: {e}")
            self._setup_android_triage_fallback()
            
    def setup_android_device_callback(self):
        """Setup callback to update sidebar when DroidTriageFrame detects device changes"""
        if hasattr(self, 'android_triage_frame'):
            try:
                # Get reference to the triage handler  
                triage_handler = self.android_triage_frame.triage_handler
                
                # Store the original status callback
                original_callback = getattr(triage_handler, 'status_callback', None)
                
                def enhanced_status_callback(message):
                    print(f"DEBUG: Android device status update: {message}")
                    
                    # Call original callback first
                    if original_callback:
                        original_callback(message)
                    
                    # Update our sidebar based on the message
                    if ("device connected" in message.lower() or 
                        "android" in message.lower() and "connected" not in message.lower() and message != "No device connected"):
                        print("DEBUG: Updating sidebar to green - device connected")
                        self.after(0, lambda: self.android_status_indicator.configure(text="🟢 Android: Connected"))
                    elif "no device" in message.lower() or "disconnected" in message.lower():
                        print("DEBUG: Updating sidebar to red - no device")
                        self.after(0, lambda: self.android_status_indicator.configure(text="🔴 Android: No device"))
                
                # Replace the status callback in the triage handler
                triage_handler.status_callback = enhanced_status_callback
                
                print("DEBUG: Android device callback setup complete")
                
            except Exception as e:
                print(f"Could not setup Android device callback: {e}")
                
        # Also trigger an immediate status check
        self.after(500, self.check_android_status_immediate)
            
    def _setup_android_triage_fallback(self):
        """Fallback Android triage setup if DroidTriageFrame fails"""
        # Device status section
        device_frame = ctk.CTkFrame(self.android_triage_tab)
        device_frame.pack(fill="x", padx=10, pady=10)
        
        device_label = ctk.CTkLabel(device_frame, 
                                   text="Android Device Status", 
                                   font=ctk.CTkFont(size=16, weight="bold"))
        device_label.pack(pady=5)
        
        self.android_device_status = ctk.CTkLabel(device_frame, text="Checking for Android device...")
        self.android_device_status.pack(pady=5)
        
        refresh_android_button = ctk.CTkButton(device_frame, 
                                              text="Refresh Android Device", 
                                              command=self.refresh_android_device)
        refresh_android_button.pack(pady=10)
        
        # Triage options section
        triage_frame = ctk.CTkFrame(self.android_triage_tab)
        triage_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        triage_label = ctk.CTkLabel(triage_frame, 
                                   text="Live Triage Options", 
                                   font=ctk.CTkFont(size=16, weight="bold"))
        triage_label.pack(pady=10)
        
        info_label = ctk.CTkLabel(triage_frame, 
                                 text="DroidTriageFrame could not be loaded.\nUsing fallback interface.")
        info_label.pack(pady=10)
        
      
    def manual_refresh_device_info(self):
        """Manually triggered device info refresh"""
        self._device_refresh_triggered = False  # Reset flag
        self.refresh_device_info()
            
    def setup_android_backup(self):
        """Setup Android backup functionality using the comprehensive DroidBackupFrame"""
        try:
            from src.ui.droid_backup_frame import DroidBackupFrame
            self.android_backup_frame = DroidBackupFrame(self.android_backup_tab)
            self.android_backup_frame.pack(fill="both", expand=True)
            
            # Connect backup tab to the shared device detection system
            self.setup_android_backup_device_sync()

        except ImportError as e:
            print(f"Could not import DroidBackupFrame: {e}")
            self._setup_android_backup_fallback()
        except Exception as e:
            print(f"Error setting up Android backup: {e}")
            self._setup_android_backup_fallback()

    def setup_android_backup_device_sync(self):
        """Sync Android backup tab with the shared device detection system"""
        try:
            if not hasattr(self, 'android_backup_frame'):
                return
                
            # Get the triage handler from the backup frame
            if hasattr(self.android_backup_frame, 'triage_handler'):
                backup_triage_handler = self.android_backup_frame.triage_handler
                
                # Store original callback
                original_backup_callback = getattr(backup_triage_handler, 'status_callback', None)
                
                # Create enhanced callback that updates both backup tab and sidebar
                def enhanced_backup_callback(message):
                    print(f"DEBUG: Android backup device status update: {message}")
                    
                    # Call original backup callback first
                    if original_backup_callback:
                        original_backup_callback(message)
                    
                    # Update sidebar indicator based on message
                    if ("device connected" in message.lower() or 
                        "android" in message.lower() and "connected" not in message.lower() and message != "No device connected"):
                        self.after(0, lambda: self.android_status_indicator.configure(text="🟢 Android: Connected"))
                    elif "no device" in message.lower() or "disconnected" in message.lower():
                        self.after(0, lambda: self.android_status_indicator.configure(text="🔴 Android: No device"))
                
                # Replace the backup handler's callback
                backup_triage_handler.status_callback = enhanced_backup_callback
                
                # Also sync with triage tab if it exists
                if hasattr(self, 'android_triage_frame') and hasattr(self.android_triage_frame, 'triage_handler'):
                    triage_handler = self.android_triage_frame.triage_handler
                    original_triage_callback = getattr(triage_handler, 'status_callback', None)
                    
                    def synchronized_callback(message):
                        print(f"DEBUG: Synchronized Android device status: {message}")
                        
                        # Update both callbacks
                        if original_triage_callback:
                            original_triage_callback(message)
                        enhanced_backup_callback(message)
                    
                    # Set synchronized callback on triage handler
                    triage_handler.status_callback = synchronized_callback
                    
                    # Trigger immediate device check to sync all tabs
                    self.after(100, self.check_android_status_immediate)
                    
        except Exception as e:
            print(f"Error setting up Android backup device sync: {e}")

    def _setup_android_backup_fallback(self):
        """Fallback Android backup setup if DroidBackupFrame fails"""
        import traceback
        # Print full traceback for debugging
        print("\n--- ANDROID BACKUP TAB ERROR TRACEBACK ---")
        traceback.print_exc()
        print("--- END TRACEBACK ---\n")
        # Create a placeholder frame
        placeholder_frame = ctk.CTkFrame(self.android_backup_tab)
        placeholder_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Placeholder message
        placeholder_label = ctk.CTkLabel(
            placeholder_frame,
            text="Android backup functionality could not be loaded.\n\nPlease check the installation.",
            font=ctk.CTkFont(size=18)
        )
        placeholder_label.pack(pady=50)
        
        # Add some basic UI elements as placeholders
        device_frame = ctk.CTkFrame(placeholder_frame)
        device_frame.pack(fill="x", padx=20, pady=20)
        
        device_label = ctk.CTkLabel(
            device_frame,
            text="Android Device Information",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        device_label.pack(pady=10)
        
        refresh_button = ctk.CTkButton(
            device_frame,
            text="Scan for Android Devices",
            state="disabled"  # Disabled for now
        )
        refresh_button.pack(pady=10)
        
    # def setup_android_analysis(self):
    #     """Setup Android analysis functionality (matching original droid_app.py)"""
    #     # Create a placeholder frame
    #     placeholder_frame = ctk.CTkFrame(self.android_analysis_tab)
    #     placeholder_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
    #     # Placeholder message
    #     placeholder_label = ctk.CTkLabel(
    #         placeholder_frame,
    #         text="Android backup parsing functionality is under development.\n\nCheck back soon!",
    #         font=ctk.CTkFont(size=18)
    #     )
    #     placeholder_label.pack(pady=50)
        
    #     # Basic file selection UI
    #     file_frame = ctk.CTkFrame(placeholder_frame)
    #     file_frame.pack(fill="x", padx=20, pady=20)
        
    #     file_label = ctk.CTkLabel(
    #         file_frame,
    #         text="Select Android Backup File:",
    #         font=ctk.CTkFont(size=14)
    #     )
    #     file_label.pack(pady=5, anchor="w")
        
    #     file_entry = ctk.CTkEntry(file_frame, width=400)
    #     file_entry.pack(side="left", padx=5, fill="x", expand=True)
        
    #     browse_button = ctk.CTkButton(
    #         file_frame,
    #         text="Browse",
    #         width=80,
    #         state="disabled"  # Disabled for now
    #     )
    #     browse_button.pack(side="right", padx=5)

    def refresh_android_device(self):
        """Check for connected Android device (cross-platform, fallback method)"""
        if hasattr(self, 'android_device_status'):
            self.android_device_status.configure(text="Checking for Android device...")

        def check_device():
            try:
                local_adb = os.path.join(current_dir, "src", "utils", "adb")
                local_adb_exe = os.path.join(current_dir, "src", "utils", "adb.exe")
                adb_commands = []
                if platform.system() == "Windows":
                    if os.path.exists(local_adb_exe):
                        adb_commands.append(local_adb_exe)
                else:
                    if os.path.exists(local_adb):
                        adb_commands.append(local_adb)
                    if os.path.exists(local_adb_exe):
                        adb_commands.append(local_adb_exe)
                adb_commands.append('adb')  # System ADB fallback

                result = None
                for adb_cmd in adb_commands:
                    try:
                        result = subprocess.run([adb_cmd, 'devices'],
                                            capture_output=True, text=True, timeout=10,
                                            creationflags=SUBPROCESS_FLAGS)
                        break
                    except FileNotFoundError:
                        continue
                    except Exception:
                        continue

                devices = []
                if result:
                    for line in result.stdout.split('\n'):
                        if line.strip() and 'device' in line and not line.startswith('List'):
                            devices.append(line.strip())

                status = "Android device connected" if devices else "No Android device connected"
                self.after(0, lambda: self.android_device_status.configure(text=status))

            except Exception as e:
                self.after(0, lambda: self.android_device_status.configure(text=f"Error: {e}"))

        threading.Thread(target=check_device, daemon=True).start()
            
    def destroy(self):
        """Clean up resources before closing"""
        try:
            # Stop Android device monitoring if it exists
            if hasattr(self, 'android_triage_frame') and hasattr(self.android_triage_frame, 'stop_device_check'):
                self.android_triage_frame.stop_device_check()
            
            # Clean up Android backup frame
            if hasattr(self, 'android_backup_frame'):
                self.android_backup_frame.destroy()
                
        except Exception as e:
            print(f"Error cleaning up Android frames: {e}")
            
        super().destroy()
        
    def refresh_device_info(self):
        """Get information about connected iOS device"""
        if self._device_refresh_triggered:
            return
        self._device_refresh_triggered = True
        
        print("DEBUG: refresh_device_info called")
        
        # Clear current info
        self.ios_device_info_text.delete("1.0", "end")
        self.ios_device_status.configure(text="Checking for connected devices...")
        self.ios_apps_list.delete("1.0", "end")
        self.ios_apps_count.configure(text="0 apps")
        self.ios_apps_data = []
        if hasattr(self, 'ios_apps_search_entry'):
            self.ios_apps_search_entry.delete(0, "end")
        
        def get_info():
            print("DEBUG: get_info thread started")
            try:
                # Delay import to avoid auto-detection issues
                from src.backup.device_backup import DeviceBackup
                backup = DeviceBackup()
                
                print("DEBUG: Created DeviceBackup instance")
                
                if backup.connect_device():
                    print("DEBUG: Device connected, getting info")
                    device_info = backup.get_device_info()
                    print(f"DEBUG: Got device info: {bool(device_info)}")
                    
                    # Update UI in main thread
                    self.after(0, lambda: self._update_device_info(device_info))
                else:
                    print("DEBUG: Device connection failed")
                    self.after(0, lambda: self._update_no_device())
                    
            except Exception as e:
                print(f"Error in device info thread: {e}")
                import traceback
                traceback.print_exc()
                self.after(0, lambda: self._update_error())
        
        # Run in thread to prevent UI freezing
        threading.Thread(target=get_info, daemon=True).start()
        
    def _update_device_info(self, device_info):
        """Update device info in the UI (called from main thread)"""
        print(f"DEBUG: _update_device_info called with device_info: {bool(device_info)}")
        
        if device_info:
            self.ios_device_status.configure(text="iOS Device Connected")
            
            # Update sidebar status
            self.ios_status_indicator.configure(text="🟢 iOS: Connected")
            
            # Format device info
            info_text = f"Device: {device_info.get('Device Model', 'Unknown')}\n"
            info_text += f"Name: {device_info.get('Device Name', 'Unknown')}\n"
            info_text += f"iOS Version: {device_info.get('iOS Version', 'Unknown')}\n"
            info_text += f"Serial Number: {device_info.get('Serial Number', 'Unknown')}\n"
            info_text += f"IMEI: {device_info.get('IMEI', 'Unknown')}\n"
            
            # Update device info text
            self.ios_device_info_text.delete("1.0", "end")
            self.ios_device_info_text.insert("1.0", info_text)
            
            print("DEBUG: Device info text updated successfully")
            
            # Update apps if available - check both 'Apps' and 'Installed Applications' keys
            apps = None
            if 'Apps' in device_info and device_info['Apps']:
                apps = device_info['Apps']
            elif 'Installed Applications' in device_info and device_info['Installed Applications']:
                apps = device_info['Installed Applications']
                
            if apps:
                self.ios_apps_count.configure(text=f"{len(apps)} apps")
                print(f"DEBUG: Found {len(apps)} iOS apps")
                
                # Store apps for search functionality
                self.ios_apps_data = apps
                self.update_ios_apps_display()
        else:
            self._update_no_device()
            
    def _update_no_device(self):
        """Update UI when no device is connected"""
        self.ios_device_status.configure(text="No iOS device connected")
        self.ios_status_indicator.configure(text="🔴 iOS: No device")
        self.ios_device_info_text.delete("1.0", "end")
        self.ios_device_info_text.insert("1.0", "Connect an iOS device to view device information...")
        
        # Clear apps data and display
        self.ios_apps_data = []
        self.ios_apps_count.configure(text="0 apps")
        self.ios_apps_list.delete("1.0", "end")
        self.ios_apps_list.insert("1.0", "No apps detected yet...")
        if hasattr(self, 'ios_apps_search_entry'):
            self.ios_apps_search_entry.delete(0, "end")
        
    def _update_error(self):
        """Update UI when there's an error"""
        self.ios_device_status.configure(text="Error checking for device")
        self.ios_status_indicator.configure(text="🟡 iOS: Error")
        self.ios_device_info_text.delete("1.0", "end")
        self.ios_device_info_text.insert("1.0", "Error occurred while checking for device...")
        
    def start_ios_backup(self):
        """Start iOS device backup using centralized case info"""
        # Get case number and output directory from header
        case_number = self.get_case_number()
        output_dir = self.get_output_directory()
        
        if not case_number:
            self.ios_status_text.insert("end", "Please enter a case number in the header before starting backup.\n")
            messagebox.showwarning("Case Number Required", "Please enter a case number in the header before starting backup.")
            return
            
        if not output_dir:
            self.ios_status_text.insert("end", "Please select an output directory in the header before starting backup.\n")
            messagebox.showwarning("Output Directory Required", "Please select an output directory in the header before starting backup.")
            return
        
        # Create case-specific backup folder
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        case_backup_folder = os.path.join(output_dir, f"iOS_Backup_{case_number}_{timestamp}")
        os.makedirs(case_backup_folder, exist_ok=True)
            
        # Clear previous status and reset progress
        self.ios_status_text.delete("1.0", "end")
        self.ios_progress_bar.set(0)
        self.ios_status_text.insert("end", f"Starting backup for case: {case_number}\n")
        self.ios_status_text.insert("end", f"Backup destination: {case_backup_folder}\n")
        
        # Disable backup button during backup
        backup_button = None
        for widget in self.ios_backup_tab.winfo_children():
            if isinstance(widget, ctk.CTkFrame):
                for child in widget.winfo_children():
                    if isinstance(child, ctk.CTkFrame):
                        for grandchild in child.winfo_children():
                            if isinstance(grandchild, ctk.CTkButton) and "Start iOS Backup" in str(grandchild.cget("text")):
                                backup_button = grandchild
                                backup_button.configure(state="disabled", text="Backup in Progress...")
                                break
        
        def backup_thread():
            try:
                from src.backup.device_backup import initiate_backup
                
                # Track last progress to avoid spam
                last_progress = -1
                
                # Create thread-safe callback functions
                def status_callback(message):
                    # Schedule GUI update on main thread
                    self.after(0, lambda msg=message: self._update_ios_backup_status(msg))
                
                def progress_callback(progress_value):
                    nonlocal last_progress
                    # Only update progress if it changed by at least 5% or reached 100%
                    progress_percent = int(progress_value * 100)
                    if progress_percent >= 100 or progress_percent - last_progress >= 5:
                        last_progress = progress_percent
                        # Schedule GUI update on main thread  
                        self.after(0, lambda val=progress_value: self._update_ios_backup_progress(val))
                
                # Call the backup function with callbacks
                success = initiate_backup(
                    path=case_backup_folder,  # Use case-specific folder
                    status_callback=status_callback,
                    progress_callback=progress_callback
                )
                
                # Schedule final completion update
                self.after(0, lambda: self._ios_backup_complete(success, backup_button))
                
            except Exception as e:
                import traceback
                error_msg = f"Backup failed with error: {str(e)}\n{traceback.format_exc()}"
                self.after(0, lambda: self._ios_backup_error(error_msg, backup_button))
        
        # Start backup in background thread
        threading.Thread(target=backup_thread, daemon=True).start()

    def _update_ios_backup_status(self, message):
        """Update backup status text with improved formatting (called from main thread)"""
        try:
            # Clean up repetitive messages and make them more user-friendly
            if "Backup progress:" in message:
                # Display backup progress messages with emoji
                progress_match = message.replace("Backup progress:", "").strip()
                display_msg = f"Backup progress: {progress_match}"
            elif "Device connected" in message:
                display_msg = "✅ iOS device connected"
            elif "Getting device information" in message:
                display_msg = "📱 Reading device information..."
            elif "Setting backup password" in message:
                display_msg = "🔐 Configuring backup encryption..."
            elif "backup password was previously set" in message:
                display_msg = "🔐 A backup password was previously set on this device. The existing password will be used for backup encryption. Note: You may need the original password to decrypt this backup."
            elif "Starting iOS backup" in message:
                display_msg = "Creating device backup..."
            elif "Collecting iOS logs" in message:
                display_msg = "📋 Collecting system logs..."
            elif "Creating backup archive" in message:
                display_msg = "📦 Creating backup archive..."
            elif "Creating backup hash" in message:
                display_msg = "🔍 Generating backup verification hash..."
            elif "Creating log archive" in message:
                display_msg = "📦 Creating log archive..."
            elif "Creating device report" in message:
                display_msg = "📄 Generating device report..."
            elif "Backup process completed" in message:
                display_msg = "All backup tasks completed."
            else:
                # For other messages, display as-is but limit length
                display_msg = message[:100] + "....." if len(message) > 100 else message
            
            self.ios_status_text.insert("end", f"{display_msg}\n")
            self.ios_status_text.see("end")  # Scroll to bottom
            self.ios_status_text.update()  # Force GUI update
        except Exception as e:
            print(f"Error updating iOS backup status: {e}")

    def _update_ios_backup_progress(self, progress_value):
        """Update backup progress bar (called from main thread)"""
        try:
            # Ensure progress value is between 0 and 1
            if progress_value > 1:
                progress_value = progress_value / 100.0
            
            self.ios_progress_bar.set(progress_value)
            
            # Only update the progress bar, don't add duplicate text messages
            # The backup service already reports progress through status messages
            self.ios_progress_bar.update()  # Force progress bar update
        except Exception as e:
            print(f"Error updating iOS backup progress: {e}")

    def _ios_backup_complete(self, success, backup_button):
        """Handle backup completion (called from main thread)"""
        try:
            if success:
                self.ios_status_text.insert("end", "✅ Backup completed successfully!\n")
                self.ios_progress_bar.set(1.0)
            else:
                self.ios_status_text.insert("end", "❌ Backup failed!\n")
            
            self.ios_status_text.see("end")
            self.ios_status_text.update()
            
            # Re-enable backup button
            if backup_button:
                backup_button.configure(state="normal", text="Start iOS Backup")
                
        except Exception as e:
            print(f"Error in backup completion: {e}")

    def _ios_backup_error(self, error_msg, backup_button):
        """Handle backup error (called from main thread)"""
        try:
            self.ios_status_text.insert("end", f"❌ {error_msg}\n")
            self.ios_status_text.see("end")
            self.ios_status_text.update()
            
            # Re-enable backup button
            if backup_button:
                backup_button.configure(state="normal", text="Start iOS Backup")
                
        except Exception as e:
            print(f"Error handling backup error: {e}")
            
    # iOS Parsing Support Methods
    def browse_backup_folder(self):
        """Browse for iOS backup folder"""
        from tkinter import filedialog
        folder_path = filedialog.askdirectory(title="Select iOS backup folder")
        if folder_path:
            self.backup_folder_path.delete(0, "end")
            self.backup_folder_path.insert(0, folder_path)
            
            # Check if backup is encrypted
            is_encrypted = self.is_backup_encrypted(folder_path)
            self.toggle_password_field(is_encrypted)
            
            if is_encrypted:
                self.update_parse_status("Encrypted backup detected. Please enter password.")
            else:
                self.update_parse_status("Unencrypted backup selected.")
                
    def browse_output_folder(self):
        """Browse for output folder"""
        from tkinter import filedialog
        folder_path = filedialog.askdirectory(title="Select output folder for results")
        if folder_path:
            self.output_folder_path.delete(0, "end")
            self.output_folder_path.insert(0, folder_path)
            
    def is_backup_encrypted(self, backup_path):
        """Check if iOS backup is encrypted"""
        try:
            # Check for Manifest.plist or Info.plist to determine encryption
            manifest_path = os.path.join(backup_path, "Manifest.plist")
            info_path = os.path.join(backup_path, "Info.plist")

            if not os.path.exists(manifest_path):
                #popup windows stating the folder is not a valid iOS backup
                messagebox.showerror("Invalid Backup", "The selected folder is not a valid iOS backup folder. It should contain: Manifest.plist and Info.plist.")
            
            if os.path.exists(manifest_path):
                # Try to read the manifest to check for encryption
                import plistlib
                with open(manifest_path, 'rb') as f:
                    manifest = plistlib.load(f)
                    return manifest.get('IsEncrypted', False)
            return False
        except:
            return False
            
    def toggle_password_field(self, show):
        """Show or hide password field based on encryption status"""
        if show:
            self.password_label.grid(row=2, column=0, padx=5, pady=5, sticky="w")
            self.password_entry.grid(row=2, column=1, columnspan=2, padx=5, pady=5, sticky="we")
            # Adjust subsequent elements
            self.controls_frame.grid(row=3, column=0, columnspan=3, padx=5, pady=5, sticky="we")
            self.button_frame.grid(row=4, column=0, columnspan=3, padx=5, pady=20, sticky="nswe")
            self.parse_status_label.grid(row=5, column=0, padx=5, pady=5, sticky="w")
            self.parse_status_text.grid(row=5, column=1, columnspan=2, padx=5, pady=5, sticky="w")
        else:
            self.password_label.grid_remove()
            self.password_entry.grid_remove()
            # Reset original positions
            self.controls_frame.grid(row=2, column=0, columnspan=3, padx=5, pady=5, sticky="we")
            self.button_frame.grid(row=3, column=0, columnspan=3, padx=5, pady=20, sticky="nswe")
            self.parse_status_label.grid(row=4, column=0, padx=5, pady=5, sticky="w")
            self.parse_status_text.grid(row=4, column=1, columnspan=2, padx=5, pady=5, sticky="w")
            
    def update_parse_status(self, message):
        """Update parse status message"""
        if hasattr(self, 'parse_status_text'):
            self.parse_status_text.configure(text=message)
            
    def get_taxonomy_options(self):
        """Get taxonomy classification options matching backup_parser.py taxonomy_Dict"""
        return [
            "currency", "document", "firearm", "keypad", "people", "phone", 
            "vehicle", "body_part", "computer", "weapon", "handwriting", 
            "screenshot", "laptop", "child", "teen", "underwear", "adult", 
            "building", "atm", "baby", "mask", "military_uniform", 
            "license_plate", "fire", "credit_card", "receipt", "outdoor_scene"
        ]
        
    def toggle_taxonomy_dropdown(self):
        """Enable/disable taxonomy dropdown based on checkbox"""
        if self.enable_taxonomy_var.get():
            self.taxonomy_dropdown.configure(state="normal")
        else:
            self.taxonomy_dropdown.configure(state="disabled")
            
    def _setup_timezone_options(self):
        """Setup timezone options for display"""
        try:
            import pytz
            from tzlocal import get_localzone
            import datetime
            
            system_tz = get_localzone()
            
            def get_utc_offset(timezone_str):
                if timezone_str == "UTC":
                    return "+00:00"
                try:
                    tz = pytz.timezone(timezone_str)
                    now = datetime.datetime.now(tz)
                    offset_str = now.strftime('%z')
                    return f"{offset_str[:3]}:{offset_str[3:]}"
                except:
                    return ""
            
            system_offset = get_utc_offset(str(system_tz))
            
            timezone_data = [
                (f"System Time ({system_tz})", system_offset),
                ("UTC", "+00:00"),
                ("America/Pacific", get_utc_offset("America/Los_Angeles")),
                ("America/Mountain", get_utc_offset("America/Denver")),
                ("America/Central", get_utc_offset("America/Chicago")),
                ("America/Eastern", get_utc_offset("America/New_York")),
                ("Europe/London", get_utc_offset("Europe/London")),
                ("Europe/Berlin", get_utc_offset("Europe/Berlin")),
                ("Asia/Tokyo", get_utc_offset("Asia/Tokyo")),
                ("Australia/Sydney", get_utc_offset("Australia/Sydney"))
            ]
            
            self.timezone_options = [f"{name} {offset}" for name, offset in timezone_data]
        except:
            self.timezone_options = ["System Time", "UTC"]
            
    def update_timezone_preference(self, value):
        """Update timezone preference"""
        self.timezone_preference = value
        
    def start_ios_parse(self):
        """Start iOS backup parsing using centralized case info"""
        backup_path = self.backup_folder_path.get()
        
        # Get case number and output directory from header
        case_number = self.get_case_number()
        output_dir = self.get_output_directory()
        
        if not backup_path:
            self.update_parse_status("Please select a backup folder")
            return
            
        if not case_number:
            self.update_parse_status("Please enter a case number in the header")
            messagebox.showwarning("Case Number Required", "Please enter a case number in the header before parsing.")
            return
            
        if not output_dir:
            self.update_parse_status("Please select an output directory in the header")
            messagebox.showwarning("Output Directory Required", "Please select an output directory in the header before parsing.")
            return
        
        # Create case-specific output folder
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        case_output_folder = os.path.join(output_dir, f"iOS_Parse_{case_number}_{timestamp}")
        os.makedirs(case_output_folder, exist_ok=True)
            
        password = self.password_entry.get() if hasattr(self, 'password_entry') else None
        
        # Get taxonomy target if enabled
        taxonomy_target = None
        if hasattr(self, 'enable_taxonomy_var') and self.enable_taxonomy_var.get():
            taxonomy_target = self.taxonomy_var.get()
            
        # Get timezone preference
        timezone_pref = None
        if hasattr(self, 'timezone_var'):
            timezone_pref = self.timezone_var.get()
        
        self.update_parse_status(f"Starting backup parsing for case: {case_number}")
        self.update_parse_status(f"Output will be saved to: {case_output_folder}")
        
        def parse_thread():
            try:
                from src.parser.backup_parser import parse_backup
                
                def progress_callback(message):
                    self.after(0, lambda: self.update_parse_status(message))
                
                # Parse the backup using the correct function signature
                result = parse_backup(
                    backup_path=backup_path,
                    password=password,
                    status_callback=progress_callback,
                    output_dir=case_output_folder,  # Use case-specific folder
                    taxonomy_target=taxonomy_target,
                    timezone=timezone_pref
                )
                
                if result:
                    self.after(0, lambda: self.update_parse_status(f"Parsing completed successfully for case: {case_number}"))
                    self.after(0, lambda: self.load_parse_results(result))
                    # Generate HTML report
                    self.after(0, lambda: self.generate_ios_html_report(result, case_output_folder, case_number))
                else:
                    self.after(0, lambda: self.update_parse_status("Parsing failed"))
                    
            except Exception as e:
                error_msg = f"Parsing error: {e}"
                print(f"Full parsing error: {e}")
                import traceback
                traceback.print_exc()
                self.after(0, lambda: self.update_parse_status(error_msg))
                
        threading.Thread(target=parse_thread, daemon=True).start()
    
    def generate_ios_html_report(self, results, output_dir, case_number):
        """Generate comprehensive HTML forensic report for iOS parsing results"""
        try:
            from datetime import datetime
            import csv
            import glob
            
            # Read actual CSV data from Reports folder
            reports_dir = os.path.join(output_dir, "Reports")
            ios_analysis = {}
            
            print(f"DEBUG: Reading CSV files from: {reports_dir}")
            print(f"DEBUG: Reports directory exists: {os.path.exists(reports_dir)}")
            
            if os.path.exists(reports_dir):
                print(f"DEBUG: Files in reports directory: {os.listdir(reports_dir)}")
            
            # Read Messages CSV
            messages_file = glob.glob(os.path.join(reports_dir, "Messages_*.csv"))
            print(f"DEBUG: Messages files found: {messages_file}")
            if messages_file:
                with open(messages_file[0], 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    # Find the line that starts with actual CSV headers (looks for "Message Date" or similar)
                    header_line_index = None
                    for i, line in enumerate(lines):
                        if 'Message Date' in line or 'Date' in line and ',' in line:
                            header_line_index = i
                            break
                    
                    if header_line_index is not None:
                        # Read from the header line onwards
                        csv_content = ''.join(lines[header_line_index:])
                        import io
                        csv_file = io.StringIO(csv_content)
                        reader = csv.DictReader(csv_file)
                        ios_analysis['sms_messages'] = list(reader)
                        print(f"DEBUG: Loaded {len(ios_analysis['sms_messages'])} SMS messages")
                        if ios_analysis['sms_messages']:
                            print(f"DEBUG: Sample SMS data keys: {list(ios_analysis['sms_messages'][0].keys())}")
                            print(f"DEBUG: Sample SMS data: {ios_analysis['sms_messages'][0]}")
                    else:
                        print("DEBUG: Could not find CSV header in Messages file")
                        ios_analysis['sms_messages'] = []
            
            # Read Call History CSV
            calls_file = glob.glob(os.path.join(reports_dir, "Call_History_*.csv"))
            print(f"DEBUG: Call history files found: {calls_file}")
            if calls_file:
                with open(calls_file[0], 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    # Find the line that starts with actual CSV headers
                    header_line_index = None
                    for i, line in enumerate(lines):
                        if 'Date' in line and 'Call' in line and ',' in line:
                            header_line_index = i
                            break
                        elif line.strip() and ',' in line and not line.startswith('CALL') and not line.startswith('DEVICE'):
                            header_line_index = i
                            break
                    
                    if header_line_index is not None:
                        csv_content = ''.join(lines[header_line_index:])
                        import io
                        csv_file = io.StringIO(csv_content)
                        reader = csv.DictReader(csv_file)
                        ios_analysis['call_history'] = list(reader)
                        print(f"DEBUG: Loaded {len(ios_analysis['call_history'])} call records")
                        if ios_analysis['call_history']:
                            print(f"DEBUG: Sample call data keys: {list(ios_analysis['call_history'][0].keys())}")
                            print(f"DEBUG: Sample call data: {ios_analysis['call_history'][0]}")
                    else:
                        print("DEBUG: Could not find CSV header in Call History file")
                        ios_analysis['call_history'] = []
            
            # Read Contacts CSV
            contacts_file = glob.glob(os.path.join(reports_dir, "Contacts_*.csv"))
            print(f"DEBUG: Contacts files found: {contacts_file}")
            if contacts_file:
                with open(contacts_file[0], 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    # Find the line that starts with actual CSV headers - contacts has: Last,First,Main,iPhone,Mobile,Home,Work,Email
                    header_line_index = None
                    for i, line in enumerate(lines):
                        if ('Last,First' in line or 'Name' in line or 'Contact' in line) and ',' in line and not line.startswith('CONTACT') and not line.startswith('DEVICE'):
                            header_line_index = i
                            break
                    
                    if header_line_index is not None:
                        csv_content = ''.join(lines[header_line_index:])
                        import io
                        csv_file = io.StringIO(csv_content)
                        reader = csv.DictReader(csv_file)
                        ios_analysis['contacts'] = list(reader)
                        print(f"DEBUG: Loaded {len(ios_analysis['contacts'])} contacts")
                        if ios_analysis['contacts']:
                            print(f"DEBUG: Sample contact data keys: {list(ios_analysis['contacts'][0].keys())}")
                            print(f"DEBUG: Sample contact data: {ios_analysis['contacts'][0]}")
                    else:
                        print("DEBUG: Could not find CSV header in Contacts file")
                        ios_analysis['contacts'] = []
            
            # Read Safari History CSV
            safari_file = glob.glob(os.path.join(reports_dir, "Safari_History_*.csv"))
            print(f"DEBUG: Safari files found: {safari_file}")
            if safari_file:
                with open(safari_file[0], 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    # Find the line that starts with actual CSV headers
                    header_line_index = None
                    for i, line in enumerate(lines):
                        if ('URL' in line or 'Title' in line or 'Visit' in line) and ',' in line and not line.startswith('SAFARI') and not line.startswith('DEVICE'):
                            header_line_index = i
                            break
                    
                    if header_line_index is not None:
                        csv_content = ''.join(lines[header_line_index:])
                        import io
                        csv_file = io.StringIO(csv_content)
                        reader = csv.DictReader(csv_file)
                        ios_analysis['safari_history'] = list(reader)
                        print(f"DEBUG: Loaded {len(ios_analysis['safari_history'])} Safari records")
                        if ios_analysis['safari_history']:
                            print(f"DEBUG: Sample Safari data keys: {list(ios_analysis['safari_history'][0].keys())}")
                            print(f"DEBUG: Sample Safari data: {ios_analysis['safari_history'][0]}")
                    else:
                        print("DEBUG: Could not find CSV header in Safari History file")
                        ios_analysis['safari_history'] = []
            
            # Read Notes CSV
            notes_file = glob.glob(os.path.join(reports_dir, "Notes_*.csv"))
            print(f"DEBUG: Notes files found: {notes_file}")
            if notes_file:
                with open(notes_file[0], 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    # Find the line that starts with actual CSV headers
                    header_line_index = None
                    for i, line in enumerate(lines):
                        if ('Note' in line or 'Title' in line or 'Content' in line) and ',' in line and not line.startswith('NOTES') and not line.startswith('DEVICE'):
                            header_line_index = i
                            break
                    
                    if header_line_index is not None:
                        csv_content = ''.join(lines[header_line_index:])
                        import io
                        csv_file = io.StringIO(csv_content)
                        reader = csv.DictReader(csv_file)
                        ios_analysis['notes'] = list(reader)
                        print(f"DEBUG: Loaded {len(ios_analysis['notes'])} notes")
                        if ios_analysis['notes']:
                            print(f"DEBUG: Sample note data keys: {list(ios_analysis['notes'][0].keys())}")
                            print(f"DEBUG: Sample note data: {ios_analysis['notes'][0]}")
                    else:
                        print("DEBUG: Could not find CSV header in Notes file")
                        ios_analysis['notes'] = []
            
            # Read Accounts CSV
            accounts_file = glob.glob(os.path.join(reports_dir, "Accounts_*.csv"))
            print(f"DEBUG: Accounts files found: {accounts_file}")
            if accounts_file:
                with open(accounts_file[0], 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    header_line_index = None
                    for i, line in enumerate(lines):
                        if ('Account' in line or 'Type' in line or 'Username' in line) and ',' in line and not line.startswith('ACCOUNT') and not line.startswith('DEVICE'):
                            header_line_index = i
                            break
                    
                    if header_line_index is not None:
                        csv_content = ''.join(lines[header_line_index:])
                        import io
                        csv_file = io.StringIO(csv_content)
                        reader = csv.DictReader(csv_file)
                        ios_analysis['accounts'] = list(reader)
                        print(f"DEBUG: Loaded {len(ios_analysis['accounts'])} accounts")
                        if ios_analysis['accounts']:
                            print(f"DEBUG: Sample account data keys: {list(ios_analysis['accounts'][0].keys())}")
                            print(f"DEBUG: Sample account data: {ios_analysis['accounts'][0]}")
                    else:
                        print("DEBUG: Could not find CSV header in Accounts file")
                        ios_analysis['accounts'] = []
            
            # Read App Permissions CSV
            app_permissions_file = glob.glob(os.path.join(reports_dir, "App_Permissions_*.csv"))
            print(f"DEBUG: App permissions files found: {app_permissions_file}")
            if app_permissions_file:
                with open(app_permissions_file[0], 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    header_line_index = None
                    for i, line in enumerate(lines):
                        if ('App' in line or 'Permission' in line or 'Service' in line) and ',' in line and not line.startswith('APP') and not line.startswith('DEVICE'):
                            header_line_index = i
                            break
                    
                    if header_line_index is not None:
                        csv_content = ''.join(lines[header_line_index:])
                        import io
                        csv_file = io.StringIO(csv_content)
                        reader = csv.DictReader(csv_file)
                        ios_analysis['app_permissions'] = list(reader)
                        print(f"DEBUG: Loaded {len(ios_analysis['app_permissions'])} app permissions")
                        if ios_analysis['app_permissions']:
                            print(f"DEBUG: Sample app permission data keys: {list(ios_analysis['app_permissions'][0].keys())}")
                            print(f"DEBUG: Sample app permission data: {ios_analysis['app_permissions'][0]}")
                    else:
                        print("DEBUG: Could not find CSV header in App Permissions file")
                        ios_analysis['app_permissions'] = []
            
            # Read Data Usage CSV
            data_usage_file = glob.glob(os.path.join(reports_dir, "Data_Usage_*.csv"))
            print(f"DEBUG: Data usage files found: {data_usage_file}")
            if data_usage_file:
                with open(data_usage_file[0], 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    header_line_index = None
                    for i, line in enumerate(lines):
                        if ('Date,Application Bundle' in line or ('Date' in line and 'Application' in line and 'WWAN' in line)) and ',' in line and not line.startswith('DATA') and not line.startswith('DEVICE'):
                            header_line_index = i
                            break
                    
                    if header_line_index is not None:
                        csv_content = ''.join(lines[header_line_index:])
                        import io
                        csv_file = io.StringIO(csv_content)
                        reader = csv.DictReader(csv_file)
                        ios_analysis['data_usage'] = list(reader)
                        print(f"DEBUG: Loaded {len(ios_analysis['data_usage'])} data usage records")
                        if ios_analysis['data_usage']:
                            print(f"DEBUG: Sample data usage keys: {list(ios_analysis['data_usage'][0].keys())}")
                            print(f"DEBUG: Sample data usage: {ios_analysis['data_usage'][0]}")
                    else:
                        print("DEBUG: Could not find CSV header in Data Usage file")
                        ios_analysis['data_usage'] = []
            
            # Read InteractionC CSV
            interaction_file = glob.glob(os.path.join(reports_dir, "InteractionC_*.csv"))
            print(f"DEBUG: InteractionC files found: {interaction_file}")
            if interaction_file:
                with open(interaction_file[0], 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    header_line_index = None
                    for i, line in enumerate(lines):
                        if ('Event Start,Event End' in line or ('Event Start' in line and 'Application' in line)) and ',' in line and not line.startswith('INTERACTION') and not line.startswith('DEVICE'):
                            header_line_index = i
                            break
                    
                    if header_line_index is not None:
                        csv_content = ''.join(lines[header_line_index:])
                        import io
                        csv_file = io.StringIO(csv_content)
                        reader = csv.DictReader(csv_file)
                        ios_analysis['interactions'] = list(reader)
                        print(f"DEBUG: Loaded {len(ios_analysis['interactions'])} interactions")
                        if ios_analysis['interactions']:
                            print(f"DEBUG: Sample interaction data keys: {list(ios_analysis['interactions'][0].keys())}")
                            print(f"DEBUG: Sample interaction data: {ios_analysis['interactions'][0]}")
                    else:
                        print("DEBUG: Could not find CSV header in InteractionC file")
                        ios_analysis['interactions'] = []
            
            # Count photos from Photos folders (Photos_keypad, Photos_screenshot, etc.)
            photo_files = []
            photos_base_dirs = glob.glob(os.path.join(output_dir, "Photos_*"))
            print(f"DEBUG: Photo directories found: {photos_base_dirs}")
            for photos_dir in photos_base_dirs:
                if os.path.exists(photos_dir):
                    photo_extensions = ['.jpg', '.jpeg', '.png', '.heic', '.mov', '.3gp']
                    for ext in photo_extensions:
                        photo_files.extend(glob.glob(os.path.join(photos_dir, f"*{ext}")) + 
                                         glob.glob(os.path.join(photos_dir, f"*{ext.upper()}")))
            ios_analysis['photo_analysis'] = [{'filename': os.path.basename(f)} for f in photo_files]
            print(f"DEBUG: Loaded {len(ios_analysis['photo_analysis'])} photo files")
            
            print(f"DEBUG: Final ios_analysis keys: {list(ios_analysis.keys())}")
            for key, value in ios_analysis.items():
                print(f"DEBUG: {key}: {len(value)} records")
            
            # Prepare report data
            report_data = {
                'case_number': case_number,
                'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'ios_analysis': ios_analysis,
                'device_info': results.get('device_info', {}) if results else {}
            }
            
            # Generate HTML report
            html_content = self.create_ios_html_report(report_data, output_dir)
            
            # Save HTML report
            report_path = os.path.join(output_dir, f"iOS_Forensic_Report_{case_number}.html")
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            self.update_parse_status(f"HTML forensic report generated: {report_path}")
            print(f"DEBUG: HTML report saved to: {report_path}")
            
        except Exception as e:
            print(f"Error generating iOS HTML report: {e}")
            import traceback
            traceback.print_exc()
            self.update_parse_status(f"Error generating HTML report: {e}")

    def create_ios_html_report(self, data, output_dir):
        """Create comprehensive HTML forensic report for iOS data"""
        import glob
        analysis = data.get('ios_analysis', {})
        device_info = data.get('device_info', {})
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>iOS Forensic Analysis Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                .header {{ background: #34495e; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
                .section {{ margin: 20px 0; padding: 20px; border: 1px solid #ddd; border-radius: 8px; }}
                .summary {{ background: #ecf0f1; }}
                .data {{ background: #ffffff; }}
                .critical {{ background: #3498db; color: white; padding: 10px; border-radius: 5px; margin: 10px 0; }}
                .warning {{ background: #f39c12; color: white; padding: 10px; border-radius: 5px; margin: 10px 0; }}
                .info {{ background: #27ae60; color: white; padding: 10px; border-radius: 5px; margin: 10px 0; }}
                table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
                th {{ background: #34495e; color: white; font-weight: bold; }}
                .highlight {{ background: #3498db; color: white; padding: 5px 10px; border-radius: 3px; }}
                .metric {{ background: #e74c3c; color: white; padding: 5px 10px; border-radius: 3px; margin: 0 5px; }}
                .file-link {{ background: #9b59b6; color: white; padding: 5px 10px; border-radius: 3px; text-decoration: none; margin: 5px; display: inline-block; }}
                .file-link:hover {{ background: #8e44ad; }}
                .progress-bar {{ background: #ecf0f1; border-radius: 10px; padding: 3px; margin: 5px 0; }}
                .progress-fill {{ background: #3498db; height: 20px; border-radius: 8px; text-align: center; color: white; line-height: 20px; }}
                .two-column {{ display: flex; gap: 20px; }}
                .column {{ flex: 1; }}
                .device-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px; margin: 15px 0; }}
                .device-item {{ background: #f8f9fa; padding: 15px; border-radius: 5px; border-left: 4px solid #3498db; }}
                .footer {{ background: #34495e; color: white; padding: 20px; border-radius: 8px; margin-top: 30px; }}
                .footer-section {{ margin: 15px 0; }}
                .footer-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; }}
                .contact-info {{ background: #2c3e50; padding: 15px; border-radius: 5px; }}
                .file-info {{ background: #2c3e50; padding: 15px; border-radius: 5px; }}
                .data-table {{ border: 1px solid #ddd; border-radius: 5px; padding: 15px; background: #f9f9f9; margin: 10px 0; }}
                .timeline-item {{ margin: 10px 0; padding: 10px; border-left: 3px solid #3498db; background: #f8f9fa; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>iOS Forensic Analysis Report</h1>
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <p>Case Number: <span class="highlight">{data.get('case_number', 'N/A')}</span></p>
                        <p>Analysis Date: <span class="highlight">{data.get('analysis_date', 'N/A')}</span></p>
                    </div>
                    <div>
                        <p>Generated by: <span class="highlight">Arsenic Triage Suite</span></p>
                        <p>Report Version: <span class="highlight">2.0</span></p>
                        <p>Platform: <span class="highlight">iOS Device Analysis</span></p>
                    </div>
                </div>
            </div>
            
            <div class="section summary">
                <h2>Executive Summary</h2>
                <p>This comprehensive forensic report analyzes iOS device backup data extracted through iTunes/Finder backup methodology. The analysis provides detailed insights into user communications, application usage, device configuration, and digital activity patterns.</p>
        """
        
        # Add key findings section
        html += """
                <div class="critical">
                    <h3>Key Findings Summary</h3>
        """
        
        # Calculate key metrics
        total_files_analyzed = 0
        total_databases = 0
        earliest_date = None
        latest_date = None
        
        # Count data types first
        sms_count = len(analysis.get('sms_messages', []))
        calls_count = len(analysis.get('call_history', []))
        contacts_count = len(analysis.get('contacts', []))
        photos_count = len(analysis.get('photo_analysis', []))
        safari_count = len(analysis.get('safari_history', []))
        notes_count = len(analysis.get('notes', []))
        accounts_count = len(analysis.get('accounts', []))
        app_permissions_count = len(analysis.get('app_permissions', []))
        data_usage_count = len(analysis.get('data_usage', []))
        interactions_count = len(analysis.get('interactions', []))
        
        # Count database files from Artifacts folder
        artifacts_dir = os.path.join(output_dir, "Artifacts")
        if os.path.exists(artifacts_dir):
            db_extensions = ['.sqlite', '.db', '.plist']
            for ext in db_extensions:
                db_files = glob.glob(os.path.join(artifacts_dir, f"*{ext}"))
                total_databases += len(db_files)
        
        # Estimate timeline from various data sources
        all_dates = []
        for data_type in ['sms_messages', 'call_history', 'safari_history']:
            for item in analysis.get(data_type, []):
                if 'Date' in item:
                    all_dates.append(item['Date'])
                elif 'date' in item:
                    all_dates.append(item['date'])
                elif 'timestamp' in item:
                    all_dates.append(item['timestamp'])
        
        if all_dates:
            # Filter out empty dates and sort
            valid_dates = [d for d in all_dates if d and str(d).strip()]
            if valid_dates:
                earliest_date = min(valid_dates)
                latest_date = max(valid_dates)
        
        # Generate findings
        html += f"<p><strong>Total SMS/MMS Messages:</strong> {sms_count:,} messages analyzed</p>"
        html += f"<p><strong>Call Log Entries:</strong> {calls_count:,} call records processed</p>"
        html += f"<p><strong>Contacts Database:</strong> {contacts_count:,} contact entries recovered</p>"
        html += f"<p><strong>Safari Web History:</strong> {safari_count:,} browsing records found</p>"
        html += f"<p><strong>Notes Application:</strong> {notes_count:,} note entries extracted</p>"
        if accounts_count > 0:
            html += f"<p><strong>Account Information:</strong> {accounts_count:,} user accounts analyzed</p>"
        if app_permissions_count > 0:
            html += f"<p><strong>App Permissions:</strong> {app_permissions_count:,} permission records found</p>"
        if data_usage_count > 0:
            html += f"<p><strong>Data Usage Records:</strong> {data_usage_count:,} network usage entries</p>"
        if interactions_count > 0:
            html += f"<p><strong>User Interactions:</strong> {interactions_count:,} interaction events recorded</p>"
        html += f"<p><strong>Database Files Extracted:</strong> {total_databases:,} SQLite and plist files analyzed</p>"
        if photos_count > 0:
            html += f"<p><strong>Media Files Recovered:</strong> {photos_count:,} photos and videos extracted</p>"
        
        if earliest_date and latest_date:
            html += f"<p><strong>Data Coverage Period:</strong> {earliest_date} to {latest_date}</p>"
        else:
            html += f"<p><strong>Data Coverage Period:</strong> Analysis completed - individual timestamps in detailed sections</p>"
        
        html += "</div>"
        
        # Device Information Section
        if device_info:
            html += f"""
                <h2>Device Information</h2>
                <div class="device-grid">
            """
            
            for key, value in device_info.items():
                html += f"""
                    <div class="device-item">
                        <strong>{key}:</strong><br>
                        {value}
                    </div>
                """
            
            html += "</div>"
        
        # SMS/Messages Analysis
        if sms_count > 0:
            html += f"""
                <h2>SMS/Messages Analysis</h2>
                <div class="info">
                    <h3>Message Statistics</h3>
                    <p>Total messages analyzed from iOS Messages database</p>
                </div>
                
                <table>
                    <tr><th>Metric</th><th>Value</th></tr>
                    <tr><td>Total Messages</td><td><span class="metric">{sms_count:,}</span></td></tr>
                </table>
                
                {self.add_ios_sms_table(analysis.get('sms_messages', []))}
            """
        
        # Call History Analysis
        if calls_count > 0:
            # Calculate total duration with proper time format handling
            total_duration = 0
            for call in analysis.get('call_history', []):
                duration_str = call.get('Duration', '0') or '0'
                try:
                    # Handle different duration formats
                    if ':' in str(duration_str):
                        # Handle HH:MM:SS or MM:SS format
                        time_parts = str(duration_str).split(':')
                        if len(time_parts) == 3:  # HH:MM:SS
                            hours, minutes, seconds = map(int, time_parts)
                            duration_seconds = hours * 3600 + minutes * 60 + seconds
                        elif len(time_parts) == 2:  # MM:SS
                            minutes, seconds = map(int, time_parts)
                            duration_seconds = minutes * 60 + seconds
                        else:
                            duration_seconds = 0
                    else:
                        # Handle plain number (seconds)
                        duration_seconds = int(float(str(duration_str)))
                except (ValueError, TypeError):
                    duration_seconds = 0
                
                total_duration += duration_seconds
            
            avg_duration = total_duration / calls_count if calls_count > 0 else 0
            
            html += f"""
                <h2>Call History Analysis</h2>
                <table>
                    <tr><th>Metric</th><th>Value</th></tr>
                    <tr><td>Total Calls</td><td><span class="metric">{calls_count:,}</span></td></tr>
                    <tr><td>Total Duration</td><td>{total_duration // 3600}h {(total_duration % 3600) // 60}m</td></tr>
                    <tr><td>Average Call Duration</td><td>{avg_duration // 60:.1f} minutes</td></tr>
                </table>
                
                {self.add_ios_calls_table(analysis.get('call_history', []))}
            """
        
        # Contacts Analysis
        if contacts_count > 0:
            html += f"""
                <h2>Contacts Analysis</h2>
                <table>
                    <tr><th>Metric</th><th>Value</th></tr>
                    <tr><td>Total Contacts</td><td><span class="metric">{contacts_count:,}</span></td></tr>
                </table>
                
                {self.add_ios_contacts_table(analysis.get('contacts', []))}
            """
        
        # Safari Web History
        if safari_count > 0:
            html += f"""
                <h2>Safari Web History</h2>
                <table>
                    <tr><th>Metric</th><th>Value</th></tr>
                    <tr><td>Total Web Visits</td><td><span class="metric">{safari_count:,}</span></td></tr>
                </table>
                
                {self.add_ios_safari_table(analysis.get('safari_history', []))}
            """
        
        # Photos Analysis
        if photos_count > 0:
            html += f"""
                <h2>Photo Analysis</h2>
                <table>
                    <tr><th>Metric</th><th>Value</th></tr>
                    <tr><td>Photos Analyzed</td><td><span class="metric">{photos_count:,}</span></td></tr>
                </table>
                
                {self.add_ios_photos_table(analysis.get('photo_analysis', []))}
            """
        
        # Notes Analysis
        if notes_count > 0:
            html += f"""
                <h2>Notes Application Data</h2>
                <table>
                    <tr><th>Metric</th><th>Value</th></tr>
                    <tr><td>Total Notes</td><td><span class="metric">{notes_count:,}</span></td></tr>
                </table>
                
                {self.add_ios_notes_table(analysis.get('notes', []))}
            """
        
        # Accounts Analysis
        if accounts_count > 0:
            html += f"""
                <h2>Account Information</h2>
                <table>
                    <tr><th>Metric</th><th>Value</th></tr>
                    <tr><td>Total Accounts</td><td><span class="metric">{accounts_count:,}</span></td></tr>
                </table>
                
                {self.add_ios_accounts_table(analysis.get('accounts', []))}
            """
        
        # App Permissions Analysis
        if app_permissions_count > 0:
            html += f"""
                <h2>Application Permissions</h2>
                <table>
                    <tr><th>Metric</th><th>Value</th></tr>
                    <tr><td>Permission Records</td><td><span class="metric">{app_permissions_count:,}</span></td></tr>
                </table>
                
                {self.add_ios_app_permissions_table(analysis.get('app_permissions', []))}
            """
        
        # Data Usage Analysis
        if data_usage_count > 0:
            html += f"""
                <h2>Network Data Usage</h2>
                <table>
                    <tr><th>Metric</th><th>Value</th></tr>
                    <tr><td>Usage Records</td><td><span class="metric">{data_usage_count:,}</span></td></tr>
                </table>
                
                {self.add_ios_data_usage_table(analysis.get('data_usage', []))}
            """
        
        # User Interactions Analysis
        if interactions_count > 0:
            html += f"""
                <h2>User Interaction Events</h2>
                <table>
                    <tr><th>Metric</th><th>Value</th></tr>
                    <tr><td>Interaction Events</td><td><span class="metric">{interactions_count:,}</span></td></tr>
                </table>
                
                {self.add_ios_interactions_table(analysis.get('interactions', []))}
            """
        
        # Analytics Section - Communication Patterns and Statistics
        html += self.add_ios_analytics_section(analysis)
        
        # Technical Details and Footer
        html += f"""
            </div>
            
            <div class="section data">
                <h2>Technical Methodology</h2>
                <h3>Data Extraction Methods</h3>
                <ul>
                    <li><strong>iOS Backup Analysis:</strong> iTunes/Finder backup file parsing using specialized forensic tools</li>
                    <li><strong>Database Recovery:</strong> SQLite database extraction and analysis from backup containers</li>
                    <li><strong>Plist Processing:</strong> Property list file parsing for configuration and metadata</li>
                    <li><strong>Binary Analysis:</strong> Specialized parsing of iOS-specific data formats</li>
                </ul>
                
                <h3>Data Sources Analyzed</h3>
                <ul>
                    <li><strong>SMS.db:</strong> Messages application database containing SMS/MMS communications</li>
                    <li><strong>AddressBook.sqlitedb:</strong> Contacts database with contact information</li>
                    <li><strong>Call History:</strong> CallHistory.storedata containing call logs</li>
                    <li><strong>Safari:</strong> History.db and other Safari-related databases</li>
                    <li><strong>Photos.sqlite:</strong> Photo library database with metadata</li>
                    <li><strong>Notes:</strong> NoteStore.sqlite containing notes application data</li>
                </ul>
            </div>
            
            <div class="footer">
                <h2>Report Summary & Resources</h2>
                <div class="footer-grid">
                    <div class="contact-info">
                        <h3>Analysis Information</h3>
                        <table style="border: none; margin: 0;">
                            <tr style="border: none;"><td style="border: none; padding: 5px;"><strong>Tool:</strong></td><td style="border: none; padding: 5px;">Arsenic Triage Suite v2.0</td></tr>
                            <tr style="border: none;"><td style="border: none; padding: 5px;"><strong>Generated:</strong></td><td style="border: none; padding: 5px;">{data.get('analysis_date', 'N/A')}</td></tr>
                            <tr style="border: none;"><td style="border: none; padding: 5px;"><strong>Case:</strong></td><td style="border: none; padding: 5px;">{data.get('case_number', 'N/A')}</td></tr>
                            <tr style="border: none;"><td style="border: none; padding: 5px;"><strong>Platform:</strong></td><td style="border: none; padding: 5px;">iOS Device Backup</td></tr>
                        </table>
                    </div>
                    
                    <div class="file-info">
                        <h3>Available Resources</h3>
                        <ul style="list-style-type: none; padding-left: 0;">
                            <li style="margin: 8px 0;"><strong>CSV Data Files:</strong> Structured data exports for analysis software</li>
                            <li style="margin: 8px 0;"><strong>Extracted Files:</strong> Recovered photos, documents, and media</li>
                            <li style="margin: 8px 0;"><strong>Database Files:</strong> Raw SQLite databases for advanced analysis</li>
                            <li style="margin: 8px 0;"><strong>Timeline Data:</strong> Chronological reconstruction of device activity</li>
                        </ul>
                    </div>
                </div>
                
                <div class="footer-section">
                    <h3>Analysis Recommendations</h3>
                    <div class="two-column">
                        <div class="column">
                            <h4>Further Investigation</h4>
                            <ul>
                                <li>Import CSV files into timeline analysis tools</li>
                                <li>Cross-reference communication patterns with case timeline</li>
                                <li>Examine photo EXIF data for location and time information</li>
                                <li>Analyze deleted data recovery opportunities</li>
                            </ul>
                        </div>
                        <div class="column">
                            <h4>Evidence Documentation</h4>
                            <ul>
                                <li>Document backup creation date and iOS version</li>
                                <li>Preserve original backup files as primary evidence</li>
                                <li>Note any encryption status and password requirements</li>
                                <li>Maintain detailed chain of custody documentation</li>
                            </ul>
                        </div>
                    </div>
                </div>
                
                <div class="footer-section" style="text-align: center; margin-top: 20px; padding-top: 20px; border-top: 1px solid #4a5568;">
                    <p><strong>End of iOS Forensic Analysis Report</strong></p>
                    <p style="font-size: 12px; color: #cbd5e0;">This report contains forensic analysis results from iOS backup data. Manual verification and correlation with other evidence sources is recommended.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def add_ios_sms_table(self, sms_data):
        """Add paginated SMS table for iOS data with JavaScript pagination"""
        if not sms_data:
            return "<p>No SMS data available.</p>"
        
        # Create JavaScript for pagination
        js_pagination = """
        <script>
            let smsCurrentPage = 1;
            const smsItemsPerPage = 15;
            let smsFilteredData = [...smsData];
            
            function showSmsPage(page) {
                const startIndex = (page - 1) * smsItemsPerPage;
                const endIndex = startIndex + smsItemsPerPage;
                const pageData = smsFilteredData.slice(startIndex, endIndex);
                
                const tbody = document.getElementById('smsTableBody');
                tbody.innerHTML = '';
                
                pageData.forEach(msg => {
                    const row = tbody.insertRow();
                    const date = msg['Message Date'] || msg.Date || msg.date || msg.Timestamp || 'Unknown';
                    const contact = msg.Contact || msg.contact || msg['Phone Number'] || msg.phone_number || msg.Sender || 'Unknown';
                    const fromMe = msg['From Me'] || msg.Direction || msg.direction || msg.Type || 'Unknown';
                    
                    // Determine direction based on From Me field
                    let direction = 'Unknown';
                    if (fromMe === 'Yes' || fromMe === '1' || fromMe === 'Sent') {
                        direction = 'Sent';
                    } else if (fromMe === 'No' || fromMe === '0' || fromMe === 'Received') {
                        direction = 'Received';
                    }
                    
                    // Get message text - prioritize Sent/Received columns from actual CSV
                    let text = '';
                    if (fromMe === 'Yes' || fromMe === '1') {
                        text = msg.Sent || msg.Text || msg.text || msg.Message || msg.message || msg.Content || '';
                    } else {
                        text = msg.Received || msg.Text || msg.text || msg.Message || msg.message || msg.Content || '';
                    }
                    
                    if (!text || text.trim() === '') {
                        text = 'No content';
                    }
                    
                    if (text.length > 100) text = text.substring(0, 100) + '...';
                    text = text.replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/&/g, '&amp;');
                    
                    row.innerHTML = `
                        <td>${date}</td>
                        <td>${contact}</td>
                        <td>${direction}</td>
                        <td style="max-width: 300px; word-wrap: break-word;">${text}</td>
                    `;
                });
                
                updateSmsPagination();
            }
            
            function updateSmsPagination() {
                const totalPages = Math.ceil(smsFilteredData.length / smsItemsPerPage);
                document.getElementById('smsPageInfo').textContent = 
                    `Page ${smsCurrentPage} of ${totalPages} (${smsFilteredData.length} records)`;
                
                document.getElementById('smsPrevBtn').disabled = smsCurrentPage === 1;
                document.getElementById('smsNextBtn').disabled = smsCurrentPage === totalPages;
            }
            
            function filterSmsTable() {
                const searchTerm = document.getElementById('smsSearch').value.toLowerCase();
                smsFilteredData = smsData.filter(msg => {
                    const searchableText = Object.values(msg).join(' ').toLowerCase();
                    return searchableText.includes(searchTerm);
                });
                smsCurrentPage = 1;
                showSmsPage(smsCurrentPage);
            }
            
            function sortSmsTable(column) {
                smsFilteredData.sort((a, b) => {
                    const aVal = a[column] || '';
                    const bVal = b[column] || '';
                    return aVal.localeCompare(bVal);
                });
                showSmsPage(smsCurrentPage);
            }
        </script>
        """
        
        # Convert data to JavaScript
        import json
        js_data = f"<script>const smsData = {json.dumps(sms_data)};</script>"
        
        html = f"""
        {js_data}
        <div class="data-table">
            <h4>SMS/Messages Data - Paginated View (15 records per page)</h4>
            <div style="margin: 10px 0;">
                <input type="text" id="smsSearch" placeholder="Search SMS messages..." 
                       onkeyup="filterSmsTable()" style="padding: 5px; width: 300px;">
                <button onclick="sortSmsTable('Date')" style="margin-left: 10px;">Sort by Date</button>
                <button onclick="sortSmsTable('Contact')">Sort by Contact</button>
            </div>
            <table style="font-size: 12px;">
                <thead>
                    <tr style="background: #34495e; color: white;">
                        <th>Date</th>
                        <th>Contact</th>
                        <th>Direction</th>
                        <th>Message Content</th>
                    </tr>
                </thead>
                <tbody id="smsTableBody">
                </tbody>
            </table>
            <div style="margin: 10px 0;">
                <button id="smsPrevBtn" onclick="smsCurrentPage--; showSmsPage(smsCurrentPage)">Previous</button>
                <span id="smsPageInfo" style="margin: 0 15px;"></span>
                <button id="smsNextBtn" onclick="smsCurrentPage++; showSmsPage(smsCurrentPage)">Next</button>
            </div>
        </div>
        {js_pagination}
        <script>showSmsPage(1);</script>
        """
        
        return html
    
    def add_ios_calls_table(self, calls_data):
        """Add paginated calls table for iOS data with JavaScript pagination"""
        if not calls_data:
            return "<p>No call data available.</p>"
        
        # Create JavaScript for pagination
        js_pagination = """
        <script>
            let callsCurrentPage = 1;
            const callsItemsPerPage = 15;
            let callsFilteredData = [...callsData];
            
            function showCallsPage(page) {
                const startIndex = (page - 1) * callsItemsPerPage;
                const endIndex = startIndex + callsItemsPerPage;
                const pageData = callsFilteredData.slice(startIndex, endIndex);
                
                const tbody = document.getElementById('callsTableBody');
                tbody.innerHTML = '';
                
                pageData.forEach(call => {
                    const row = tbody.insertRow();
                    const date = call.Date || call.date || call.Timestamp || 'Unknown';
                    const contact = call['Other Party'] || call.Contact || call.contact || call['Phone Number'] || call.phone_number || 'Unknown';
                    const callType = call['Call Direction'] || call.CallType || call['Call Type'] || call.call_type || call.Type || call.Direction || 'Unknown';
                    let duration = call.Duration || call.duration || call['Call Duration'] || '0';
                    
                    // Format duration
                    try {
                        let duration = call.Duration || call.duration || call['Call Duration'] || '0';
                        
                        // Handle different duration formats
                        if (typeof duration === 'string' && duration.includes(':')) {
                            // Handle HH:MM:SS or MM:SS format
                            const timeParts = duration.split(':');
                            if (timeParts.length === 3) {
                                // HH:MM:SS
                                const hours = parseInt(timeParts[0]);
                                const minutes = parseInt(timeParts[1]);
                                const seconds = parseInt(timeParts[2]);
                                const totalSeconds = hours * 3600 + minutes * 60 + seconds;
                                
                                if (totalSeconds > 3600) {
                                    duration = Math.floor(totalSeconds / 3600) + 'h ' + Math.floor((totalSeconds % 3600) / 60) + 'm';
                                } else if (totalSeconds > 60) {
                                    duration = Math.floor(totalSeconds / 60) + 'm ' + (totalSeconds % 60) + 's';
                                } else {
                                    duration = totalSeconds + 's';
                                }
                            } else if (timeParts.length === 2) {
                                // MM:SS
                                const minutes = parseInt(timeParts[0]);
                                const seconds = parseInt(timeParts[1]);
                                duration = minutes + 'm ' + seconds + 's';
                            }
                        } else {
                            // Handle plain number (seconds)
                            const durSec = parseInt(parseFloat(duration));
                            if (durSec > 60) {
                                duration = Math.floor(durSec / 60) + 'm ' + (durSec % 60) + 's';
                            } else {
                                duration = durSec + 's';
                            }
                        }
                    } catch (e) {
                        duration = duration;
                    }
                    
                    row.innerHTML = `
                        <td>${date}</td>
                        <td>${contact}</td>
                        <td>${callType}</td>
                        <td>${duration}</td>
                    `;
                });
                
                updateCallsPagination();
            }
            
            function updateCallsPagination() {
                const totalPages = Math.ceil(callsFilteredData.length / callsItemsPerPage);
                document.getElementById('callsPageInfo').textContent = 
                    `Page ${callsCurrentPage} of ${totalPages} (${callsFilteredData.length} records)`;
                
                document.getElementById('callsPrevBtn').disabled = callsCurrentPage === 1;
                document.getElementById('callsNextBtn').disabled = callsCurrentPage === totalPages;
            }
            
            function filterCallsTable() {
                const searchTerm = document.getElementById('callsSearch').value.toLowerCase();
                callsFilteredData = callsData.filter(call => {
                    const searchableText = Object.values(call).join(' ').toLowerCase();
                    return searchableText.includes(searchTerm);
                });
                callsCurrentPage = 1;
                showCallsPage(callsCurrentPage);
            }
            
            function sortCallsTable(column) {
                callsFilteredData.sort((a, b) => {
                    const aVal = a[column] || '';
                    const bVal = b[column] || '';
                    return aVal.localeCompare(bVal);
                });
                showCallsPage(callsCurrentPage);
            }
        </script>
        """
        
        # Convert data to JavaScript
        import json
        js_data = f"<script>const callsData = {json.dumps(calls_data)};</script>"
        
        html = f"""
        {js_data}
        <div class="data-table">
            <h4>Call History Data - Paginated View (15 records per page)</h4>
            <div style="margin: 10px 0;">
                <input type="text" id="callsSearch" placeholder="Search call history..." 
                       onkeyup="filterCallsTable()" style="padding: 5px; width: 300px;">
                <button onclick="sortCallsTable('Date')" style="margin-left: 10px;">Sort by Date</button>
                <button onclick="sortCallsTable('Contact')">Sort by Contact</button>
            </div>
            <table style="font-size: 12px;">
                <thead>
                    <tr style="background: #34495e; color: white;">
                        <th>Date</th>
                        <th>Contact</th>
                        <th>Call Type</th>
                        <th>Duration</th>
                    </tr>
                </thead>
                <tbody id="callsTableBody">
                </tbody>
            </table>
            <div style="margin: 10px 0;">
                <button id="callsPrevBtn" onclick="callsCurrentPage--; showCallsPage(callsCurrentPage)">Previous</button>
                <span id="callsPageInfo" style="margin: 0 15px;"></span>
                <button id="callsNextBtn" onclick="callsCurrentPage++; showCallsPage(callsCurrentPage)">Next</button>
            </div>
        </div>
        {js_pagination}
        <script>showCallsPage(1);</script>
        """
        
        return html
    
    def add_ios_contacts_table(self, contacts_data):
        """Add paginated contacts table for iOS data with JavaScript pagination"""
        if not contacts_data:
            return "<p>No contacts data available.</p>"
        
        # Create JavaScript for pagination
        js_pagination = """
        <script>
            let contactsCurrentPage = 1;
            const contactsItemsPerPage = 15;
            let contactsFilteredData = [...contactsData];
            
            function showContactsPage(page) {
                const startIndex = (page - 1) * contactsItemsPerPage;
                const endIndex = startIndex + contactsItemsPerPage;
                const pageData = contactsFilteredData.slice(startIndex, endIndex);
                
                const tbody = document.getElementById('contactsTableBody');
                tbody.innerHTML = '';
                
                pageData.forEach(contact => {
                    const row = tbody.insertRow();
                    // Build name from First and Last columns
                    const first = contact.First || contact.first || '';
                    const last = contact.Last || contact.last || '';
                    const name = (first + ' ' + last).trim() || contact.Name || contact.name || contact['Display Name'] || 'Unknown';
                    
                    // Get phone number from multiple possible columns
                    const phone = contact.Main || contact.iPhone || contact.Mobile || contact.Home || contact.Work || 
                                contact['Phone Number'] || contact.phone_number || contact.Phone || 'N/A';
                    const email = contact.Email || contact.email || contact['Email Address'] || 'N/A';
                    // Use combination of available fields for organization
                    const org = contact.Organization || contact.organization || contact.Company || 'N/A';
                    
                    row.innerHTML = `
                        <td>${name}</td>
                        <td>${phone}</td>
                        <td>${email}</td>
                        <td>${org}</td>
                    `;
                });
                
                updateContactsPagination();
            }
            
            function updateContactsPagination() {
                const totalPages = Math.ceil(contactsFilteredData.length / contactsItemsPerPage);
                document.getElementById('contactsPageInfo').textContent = 
                    `Page ${contactsCurrentPage} of ${totalPages} (${contactsFilteredData.length} records)`;
                
                document.getElementById('contactsPrevBtn').disabled = contactsCurrentPage === 1;
                document.getElementById('contactsNextBtn').disabled = contactsCurrentPage === totalPages;
            }
            
            function filterContactsTable() {
                const searchTerm = document.getElementById('contactsSearch').value.toLowerCase();
                contactsFilteredData = contactsData.filter(contact => {
                    const searchableText = Object.values(contact).join(' ').toLowerCase();
                    return searchableText.includes(searchTerm);
                });
                contactsCurrentPage = 1;
                showContactsPage(contactsCurrentPage);
            }
            
            function sortContactsTable(column) {
                contactsFilteredData.sort((a, b) => {
                    const aVal = a[column] || '';
                    const bVal = b[column] || '';
                    return aVal.localeCompare(bVal);
                });
                showContactsPage(contactsCurrentPage);
            }
        </script>
        """
        
        # Convert data to JavaScript
        import json
        js_data = f"<script>const contactsData = {json.dumps(contacts_data)};</script>"
        
        html = f"""
        {js_data}
        <div class="data-table">
            <h4>Contacts Data - Paginated View (15 records per page)</h4>
            <div style="margin: 10px 0;">
                <input type="text" id="contactsSearch" placeholder="Search contacts..." 
                       onkeyup="filterContactsTable()" style="padding: 5px; width: 300px;">
                <button onclick="sortContactsTable('Name')" style="margin-left: 10px;">Sort by Name</button>
                <button onclick="sortContactsTable('Phone Number')">Sort by Phone</button>
            </div>
            <table style="font-size: 12px;">
                <thead>
                    <tr style="background: #34495e; color: white;">
                        <th>Name</th>
                        <th>Phone Number</th>
                        <th>Email</th>
                        <th>Organization</th>
                    </tr>
                </thead>
                <tbody id="contactsTableBody">
                </tbody>
            </table>
            <div style="margin: 10px 0;">
                <button id="contactsPrevBtn" onclick="contactsCurrentPage--; showContactsPage(contactsCurrentPage)">Previous</button>
                <span id="contactsPageInfo" style="margin: 0 15px;"></span>
                <button id="contactsNextBtn" onclick="contactsCurrentPage++; showContactsPage(contactsCurrentPage)">Next</button>
            </div>
        </div>
        {js_pagination}
        <script>showContactsPage(1);</script>
        """
        
        return html
    
    def add_ios_safari_table(self, safari_data):
        """Add paginated Safari history table for iOS data with JavaScript pagination"""
        if not safari_data:
            return "<p>No Safari data available.</p>"
        
        # Create JavaScript for pagination
        js_pagination = """
        <script>
            let safariCurrentPage = 1;
            const safariItemsPerPage = 15;
            let safariFilteredData = [...safariData];
            
            function showSafariPage(page) {
                const startIndex = (page - 1) * safariItemsPerPage;
                const endIndex = startIndex + safariItemsPerPage;
                const pageData = safariFilteredData.slice(startIndex, endIndex);
                
                const tbody = document.getElementById('safariTableBody');
                tbody.innerHTML = '';
                
                pageData.forEach(entry => {
                    const row = tbody.insertRow();
                    const date = entry.Date || entry.date || entry.Timestamp || entry['Last Visited'] || 'Unknown';
                    let url = entry.URL || entry.url || entry.Address || 'Unknown';
                    let title = entry.Title || entry.title || entry['Page Title'] || 'No title';
                    const visits = entry['Visit Count'] || entry.visit_count || entry.Visits || '1';
                    
                    // Truncate long URLs and titles
                    if (url.length > 50) url = url.substring(0, 50) + '...';
                    if (title.length > 40) title = title.substring(0, 40) + '...';
                    
                    row.innerHTML = `
                        <td>${date}</td>
                        <td style="max-width: 300px; word-wrap: break-word;">${url}</td>
                        <td style="max-width: 250px; word-wrap: break-word;">${title}</td>
                        <td>${visits}</td>
                    `;
                });
                
                updateSafariPagination();
            }
            
            function updateSafariPagination() {
                const totalPages = Math.ceil(safariFilteredData.length / safariItemsPerPage);
                document.getElementById('safariPageInfo').textContent = 
                    `Page ${safariCurrentPage} of ${totalPages} (${safariFilteredData.length} records)`;
                
                document.getElementById('safariPrevBtn').disabled = safariCurrentPage === 1;
                document.getElementById('safariNextBtn').disabled = safariCurrentPage === totalPages;
            }
            
            function filterSafariTable() {
                const searchTerm = document.getElementById('safariSearch').value.toLowerCase();
                safariFilteredData = safariData.filter(entry => {
                    const searchableText = Object.values(entry).join(' ').toLowerCase();
                    return searchableText.includes(searchTerm);
                });
                safariCurrentPage = 1;
                showSafariPage(safariCurrentPage);
            }
            
            function sortSafariTable(column) {
                safariFilteredData.sort((a, b) => {
                    const aVal = a[column] || '';
                    const bVal = b[column] || '';
                    return aVal.localeCompare(bVal);
                });
                showSafariPage(safariCurrentPage);
            }
        </script>
        """
        
        # Convert data to JavaScript
        import json
        js_data = f"<script>const safariData = {json.dumps(safari_data)};</script>"
        
        html = f"""
        {js_data}
        <div class="data-table">
            <h4>Safari History Data - Paginated View (15 records per page)</h4>
            <div style="margin: 10px 0;">
                <input type="text" id="safariSearch" placeholder="Search Safari history..." 
                       onkeyup="filterSafariTable()" style="padding: 5px; width: 300px;">
                <button onclick="sortSafariTable('Date')" style="margin-left: 10px;">Sort by Date</button>
                <button onclick="sortSafariTable('URL')">Sort by URL</button>
            </div>
            <table style="font-size: 12px;">
                <thead>
                    <tr style="background: #34495e; color: white;">
                        <th>Date</th>
                        <th>URL</th>
                        <th>Title</th>
                        <th>Visit Count</th>
                    </tr>
                </thead>
                <tbody id="safariTableBody">
                </tbody>
            </table>
            <div style="margin: 10px 0;">
                <button id="safariPrevBtn" onclick="safariCurrentPage--; showSafariPage(safariCurrentPage)">Previous</button>
                <span id="safariPageInfo" style="margin: 0 15px;"></span>
                <button id="safariNextBtn" onclick="safariCurrentPage++; showSafariPage(safariCurrentPage)">Next</button>
            </div>
        </div>
        {js_pagination}
        <script>showSafariPage(1);</script>
        """
        
        return html
    
    def add_ios_photos_table(self, photos_data):
        """Add paginated photos table for iOS data with JavaScript pagination"""
        if not photos_data:
            return "<p>No photos data available.</p>"
        
        # Create JavaScript for pagination
        js_pagination = """
        <script>
            let photosCurrentPage = 1;
            const photosItemsPerPage = 15;
            let photosFilteredData = [...photosData];
            
            function showPhotosPage(page) {
                const startIndex = (page - 1) * photosItemsPerPage;
                const endIndex = startIndex + photosItemsPerPage;
                const pageData = photosFilteredData.slice(startIndex, endIndex);
                
                const tbody = document.getElementById('photosTableBody');
                tbody.innerHTML = '';
                
                pageData.forEach(photo => {
                    const row = tbody.insertRow();
                    const filename = photo.filename || photo.Filename || 'Unknown';
                    
                    // Determine file type from extension
                    let fileType = 'Unknown';
                    if (filename.includes('.')) {
                        fileType = filename.split('.').pop().toUpperCase();
                    }
                    
                    row.innerHTML = `
                        <td>${filename}</td>
                        <td>${fileType}</td>
                        <td>Extracted</td>
                    `;
                });
                
                updatePhotosPagination();
            }
            
            function updatePhotosPagination() {
                const totalPages = Math.ceil(photosFilteredData.length / photosItemsPerPage);
                document.getElementById('photosPageInfo').textContent = 
                    `Page ${photosCurrentPage} of ${totalPages} (${photosFilteredData.length} records)`;
                
                document.getElementById('photosPrevBtn').disabled = photosCurrentPage === 1;
                document.getElementById('photosNextBtn').disabled = photosCurrentPage === totalPages;
            }
            
            function filterPhotosTable() {
                const searchTerm = document.getElementById('photosSearch').value.toLowerCase();
                photosFilteredData = photosData.filter(photo => {
                    const searchableText = Object.values(photo).join(' ').toLowerCase();
                    return searchableText.includes(searchTerm);
                });
                photosCurrentPage = 1;
                showPhotosPage(photosCurrentPage);
            }
            
            function sortPhotosTable(column) {
                photosFilteredData.sort((a, b) => {
                    const aVal = a[column] || '';
                    const bVal = b[column] || '';
                    return aVal.localeCompare(bVal);
                });
                showPhotosPage(photosCurrentPage);
            }
        </script>
        """
        
        # Convert data to JavaScript
        import json
        js_data = f"<script>const photosData = {json.dumps(photos_data)};</script>"
        
        html = f"""
        {js_data}
        <div class="data-table">
            <h4>Photo Analysis Data - Paginated View (15 records per page)</h4>
            <div style="margin: 10px 0;">
                <input type="text" id="photosSearch" placeholder="Search photos..." 
                       onkeyup="filterPhotosTable()" style="padding: 5px; width: 300px;">
                <button onclick="sortPhotosTable('filename')" style="margin-left: 10px;">Sort by Filename</button>
            </div>
            <table style="font-size: 12px;">
                <thead>
                    <tr style="background: #34495e; color: white;">
                        <th>Filename</th>
                        <th>File Type</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody id="photosTableBody">
                </tbody>
            </table>
            <div style="margin: 10px 0;">
                <button id="photosPrevBtn" onclick="photosCurrentPage--; showPhotosPage(photosCurrentPage)">Previous</button>
                <span id="photosPageInfo" style="margin: 0 15px;"></span>
                <button id="photosNextBtn" onclick="photosCurrentPage++; showPhotosPage(photosCurrentPage)">Next</button>
            </div>
        </div>
        {js_pagination}
        <script>showPhotosPage(1);</script>
        """
        
        return html
    
    def add_ios_notes_table(self, notes_data):
        """Add paginated notes table for iOS data with JavaScript pagination"""
        if not notes_data:
            return "<p>No notes data available.</p>"
        
        # Create JavaScript for pagination
        js_pagination = """
        <script>
            let notesCurrentPage = 1;
            const notesItemsPerPage = 15;
            let notesFilteredData = [...notesData];
            
            function showNotesPage(page) {
                const startIndex = (page - 1) * notesItemsPerPage;
                const endIndex = startIndex + notesItemsPerPage;
                const pageData = notesFilteredData.slice(startIndex, endIndex);
                
                const tbody = document.getElementById('notesTableBody');
                tbody.innerHTML = '';
                
                pageData.forEach(note => {
                    const row = tbody.insertRow();
                    const date = note['Creation Date'] || note['Modification Date'] || note.Date || note.date || 'Unknown';
                    const title = note.Title || note.title || note['Note Title'] || 'Untitled';
                    let content = note.Data || note.Content || note.content || note.Text || note['Note Content'] || note.Body || 'No content';
                    const account = note.Account || note.account || note.Folder || 'Unknown';
                    
                    // Truncate content for preview
                    if (content.length > 80) content = content.substring(0, 80) + '...';
                    
                    // Escape HTML
                    content = content.replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/&/g, '&amp;');
                    
                    row.innerHTML = `
                        <td>${date}</td>
                        <td>${title}</td>
                        <td style="max-width: 300px; word-wrap: break-word;">${content}</td>
                        <td>${account}</td>
                    `;
                });
                
                updateNotesPagination();
            }
            
            function updateNotesPagination() {
                const totalPages = Math.ceil(notesFilteredData.length / notesItemsPerPage);
                document.getElementById('notesPageInfo').textContent = 
                    `Page ${notesCurrentPage} of ${totalPages} (${notesFilteredData.length} records)`;
                
                document.getElementById('notesPrevBtn').disabled = notesCurrentPage === 1;
                document.getElementById('notesNextBtn').disabled = notesCurrentPage === totalPages;
            }
            
            function filterNotesTable() {
                const searchTerm = document.getElementById('notesSearch').value.toLowerCase();
                notesFilteredData = notesData.filter(note => {
                    const searchableText = Object.values(note).join(' ').toLowerCase();
                    return searchableText.includes(searchTerm);
                });
                notesCurrentPage = 1;
                showNotesPage(notesCurrentPage);
            }
            
            function sortNotesTable(column) {
                notesFilteredData.sort((a, b) => {
                    const aVal = a[column] || '';
                    const bVal = b[column] || '';
                    return aVal.localeCompare(bVal);
                });
                showNotesPage(notesCurrentPage);
            }
        </script>
        """
        
        # Convert data to JavaScript
        import json
        js_data = f"<script>const notesData = {json.dumps(notes_data)};</script>"
        
        html = f"""
        {js_data}
        <div class="data-table">
            <h4>Notes Application Data - Paginated View (15 records per page)</h4>
            <div style="margin: 10px 0;">
                <input type="text" id="notesSearch" placeholder="Search notes..." 
                       onkeyup="filterNotesTable()" style="padding: 5px; width: 300px;">
                <button onclick="sortNotesTable('Title')" style="margin-left: 10px;">Sort by Title</button>
                <button onclick="sortNotesTable('Creation Date')">Sort by Date</button>
            </div>
            <table style="font-size: 12px;">
                <thead>
                    <tr style="background: #34495e; color: white;">
                        <th>Date</th>
                        <th>Title</th>
                        <th>Content Preview</th>
                        <th>Account</th>
                    </tr>
                </thead>
                <tbody id="notesTableBody">
                </tbody>
            </table>
            <div style="margin: 10px 0;">
                <button id="notesPrevBtn" onclick="notesCurrentPage--; showNotesPage(notesCurrentPage)">Previous</button>
                <span id="notesPageInfo" style="margin: 0 15px;"></span>
                <button id="notesNextBtn" onclick="notesCurrentPage++; showNotesPage(notesCurrentPage)">Next</button>
            </div>
        </div>
        {js_pagination}
        <script>showNotesPage(1);</script>
        """
        
        return html
    
    def add_ios_accounts_table(self, accounts_data):
        """Add paginated accounts table for iOS data with JavaScript pagination"""
        if not accounts_data:
            return "<p>No accounts data available.</p>"
        
        # Create JavaScript for pagination
        js_pagination = """
        <script>
            let accountsCurrentPage = 1;
            const accountsItemsPerPage = 15;
            let accountsFilteredData = [...accountsData];
            
            function showAccountsPage(page) {
                const startIndex = (page - 1) * accountsItemsPerPage;
                const endIndex = startIndex + accountsItemsPerPage;
                const pageData = accountsFilteredData.slice(startIndex, endIndex);
                
                const tbody = document.getElementById('accountsTableBody');
                tbody.innerHTML = '';
                
                pageData.forEach(account => {
                    const row = tbody.insertRow();
                    // Using actual CSV columns: Account Date, Username, Description
                    const accountDate = account['Account Date'] || account.Date || account.date || 'Unknown';
                    const username = account.Username || account.username || account.User || account['Account Name'] || 'N/A';
                    const description = account.Description || account.description || account['Account Description'] || 'N/A';
                    const status = account.Status || account.status || account.Enabled || 'Active';
                    
                    row.innerHTML = `
                        <td>${accountDate}</td>
                        <td>${username}</td>
                        <td>${description}</td>
                        <td>${status}</td>
                    `;
                });
                
                updateAccountsPagination();
            }
            
            function updateAccountsPagination() {
                const totalPages = Math.ceil(accountsFilteredData.length / accountsItemsPerPage);
                document.getElementById('accountsPageInfo').textContent = 
                    `Page ${accountsCurrentPage} of ${totalPages} (${accountsFilteredData.length} records)`;
                
                document.getElementById('accountsPrevBtn').disabled = accountsCurrentPage === 1;
                document.getElementById('accountsNextBtn').disabled = accountsCurrentPage === totalPages;
            }
            
            function filterAccountsTable() {
                const searchTerm = document.getElementById('accountsSearch').value.toLowerCase();
                accountsFilteredData = accountsData.filter(account => {
                    const searchableText = Object.values(account).join(' ').toLowerCase();
                    return searchableText.includes(searchTerm);
                });
                accountsCurrentPage = 1;
                showAccountsPage(accountsCurrentPage);
            }
            
            function sortAccountsTable(column) {
                accountsFilteredData.sort((a, b) => {
                    const aVal = a[column] || '';
                    const bVal = b[column] || '';
                    return aVal.localeCompare(bVal);
                });
                showAccountsPage(accountsCurrentPage);
            }
        </script>
        """
        
        # Convert data to JavaScript
        import json
        js_data = f"<script>const accountsData = {json.dumps(accounts_data)};</script>"
        
        html = f"""
        {js_data}
        <div class="data-table">
            <h4>Account Information - Paginated View (15 records per page)</h4>
            <div style="margin: 10px 0;">
                <input type="text" id="accountsSearch" placeholder="Search accounts..." 
                       onkeyup="filterAccountsTable()" style="padding: 5px; width: 300px;">
                <button onclick="sortAccountsTable('Username')" style="margin-left: 10px;">Sort by Username</button>
                <button onclick="sortAccountsTable('Account Date')">Sort by Date</button>
            </div>
            <table style="font-size: 12px;">
                <thead>
                    <tr style="background: #34495e; color: white;">
                        <th>Account Date</th>
                        <th>Username</th>
                        <th>Description</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody id="accountsTableBody">
                </tbody>
            </table>
            <div style="margin: 10px 0;">
                <button id="accountsPrevBtn" onclick="accountsCurrentPage--; showAccountsPage(accountsCurrentPage)">Previous</button>
                <span id="accountsPageInfo" style="margin: 0 15px;"></span>
                <button id="accountsNextBtn" onclick="accountsCurrentPage++; showAccountsPage(accountsCurrentPage)">Next</button>
            </div>
        </div>
        {js_pagination}
        <script>showAccountsPage(1);</script>
        """
        
        return html
    
    def add_ios_app_permissions_table(self, permissions_data):
        """Add paginated app permissions table for iOS data with JavaScript pagination"""
        if not permissions_data:
            return "<p>No app permissions data available.</p>"
        
        # Create JavaScript for pagination
        js_pagination = """
        <script>
            let permissionsCurrentPage = 1;
            const permissionsItemsPerPage = 15;
            let permissionsFilteredData = [...permissionsData];
            
            function showPermissionsPage(page) {
                const startIndex = (page - 1) * permissionsItemsPerPage;
                const endIndex = startIndex + permissionsItemsPerPage;
                const pageData = permissionsFilteredData.slice(startIndex, endIndex);
                
                const tbody = document.getElementById('permissionsTableBody');
                tbody.innerHTML = '';
                
                pageData.forEach(permission => {
                    const row = tbody.insertRow();
                    // Using actual CSV columns: Device Permission, Application Bundle, Permission Status
                    const appBundle = permission['Application Bundle'] || permission.Application || permission.app_name || permission.App || permission['Bundle ID'] || 'Unknown';
                    const permissionType = permission['Device Permission'] || permission['Permission Type'] || permission.permission_type || permission.Service || permission.Permission || 'Unknown';
                    const status = permission['Permission Status'] || permission.Status || permission.status || permission.Allowed || permission.Granted || 'Unknown';
                    const lastModified = permission['Last Modified'] || permission.last_modified || permission.Date || 'Unknown';
                    
                    row.innerHTML = `
                        <td style="max-width: 200px; word-wrap: break-word;">${appBundle}</td>
                        <td>${permissionType}</td>
                        <td>${status}</td>
                        <td>${lastModified}</td>
                    `;
                });
                
                updatePermissionsPagination();
            }
            
            function updatePermissionsPagination() {
                const totalPages = Math.ceil(permissionsFilteredData.length / permissionsItemsPerPage);
                document.getElementById('permissionsPageInfo').textContent = 
                    `Page ${permissionsCurrentPage} of ${totalPages} (${permissionsFilteredData.length} records)`;
                
                document.getElementById('permissionsPrevBtn').disabled = permissionsCurrentPage === 1;
                document.getElementById('permissionsNextBtn').disabled = permissionsCurrentPage === totalPages;
            }
            
            function filterPermissionsTable() {
                const searchTerm = document.getElementById('permissionsSearch').value.toLowerCase();
                permissionsFilteredData = permissionsData.filter(permission => {
                    const searchableText = Object.values(permission).join(' ').toLowerCase();
                    return searchableText.includes(searchTerm);
                });
                permissionsCurrentPage = 1;
                showPermissionsPage(permissionsCurrentPage);
            }
            
            function sortPermissionsTable(column) {
                permissionsFilteredData.sort((a, b) => {
                    const aVal = a[column] || '';
                    const bVal = b[column] || '';
                    return aVal.localeCompare(bVal);
                });
                showPermissionsPage(permissionsCurrentPage);
            }
        </script>
        """
        
        # Convert data to JavaScript
        import json
        js_data = f"<script>const permissionsData = {json.dumps(permissions_data)};</script>"
        
        html = f"""
        {js_data}
        <div class="data-table">
            <h4>Application Permissions - Paginated View (15 records per page)</h4>
            <div style="margin: 10px 0;">
                <input type="text" id="permissionsSearch" placeholder="Search permissions..." 
                       onkeyup="filterPermissionsTable()" style="padding: 5px; width: 300px;">
                <button onclick="sortPermissionsTable('Application Bundle')" style="margin-left: 10px;">Sort by App</button>
                <button onclick="sortPermissionsTable('Device Permission')">Sort by Permission</button>
            </div>
            <table style="font-size: 12px;">
                <thead>
                    <tr style="background: #34495e; color: white;">
                        <th>Application</th>
                        <th>Permission Type</th>
                        <th>Status</th>
                        <th>Last Modified</th>
                    </tr>
                </thead>
                <tbody id="permissionsTableBody">
                </tbody>
            </table>
            <div style="margin: 10px 0;">
                <button id="permissionsPrevBtn" onclick="permissionsCurrentPage--; showPermissionsPage(permissionsCurrentPage)">Previous</button>
                <span id="permissionsPageInfo" style="margin: 0 15px;"></span>
                <button id="permissionsNextBtn" onclick="permissionsCurrentPage++; showPermissionsPage(permissionsCurrentPage)">Next</button>
            </div>
        </div>
        {js_pagination}
        <script>showPermissionsPage(1);</script>
        """
        
        return html
    
    def add_ios_data_usage_table(self, usage_data):
        """Add paginated data usage table for iOS data with JavaScript pagination"""
        if not usage_data:
            return "<p>No data usage information available.</p>"
        
        # Create JavaScript for pagination
        js_pagination = """
        <script>
            let usageCurrentPage = 1;
            const usageItemsPerPage = 15;
            let usageFilteredData = [...usageData];
            
            function showUsagePage(page) {
                const startIndex = (page - 1) * usageItemsPerPage;
                const endIndex = startIndex + usageItemsPerPage;
                const pageData = usageFilteredData.slice(startIndex, endIndex);
                
                const tbody = document.getElementById('usageTableBody');
                tbody.innerHTML = '';
                
                pageData.forEach(usage => {
                    const row = tbody.insertRow();
                    // Using actual CSV columns: Date, Application Bundle, WWAN In (KB), WWAN Out (KB)
                    const date = usage.Date || usage.date || usage.Timestamp || 'Unknown';
                    const appBundle = usage['Application Bundle'] || usage.Application || usage.app_name || usage['Bundle ID'] || usage.Process || 'Unknown';
                    const bytesSent = usage['WWAN Out (KB)'] || usage['Bytes Sent'] || usage.bytes_sent || usage.Upload || usage.Sent || '0';
                    const bytesReceived = usage['WWAN In (KB)'] || usage['Bytes Received'] || usage.bytes_received || usage.Download || usage.Received || '0';
                    
                    // Format bytes for readability (values are in KB from CSV)
                    function formatBytes(kbVal) {
                        try {
                            const kb = parseFloat(kbVal);
                            if (kb > 1024) {
                                return (kb/1024).toFixed(1) + ' MB';
                            } else if (kb > 0) {
                                return kb.toFixed(1) + ' KB';
                            } else {
                                return '0 B';
                            }
                        } catch {
                            return kbVal;
                        }
                    }
                    
                    row.innerHTML = `
                        <td>${date}</td>
                        <td style="max-width: 200px; word-wrap: break-word;">${appBundle}</td>
                        <td>${formatBytes(bytesSent)}</td>
                        <td>${formatBytes(bytesReceived)}</td>
                    `;
                });
                
                updateUsagePagination();
            }
            
            function updateUsagePagination() {
                const totalPages = Math.ceil(usageFilteredData.length / usageItemsPerPage);
                document.getElementById('usagePageInfo').textContent = 
                    `Page ${usageCurrentPage} of ${totalPages} (${usageFilteredData.length} records)`;
                
                document.getElementById('usagePrevBtn').disabled = usageCurrentPage === 1;
                document.getElementById('usageNextBtn').disabled = usageCurrentPage === totalPages;
            }
            
            function filterUsageTable() {
                const searchTerm = document.getElementById('usageSearch').value.toLowerCase();
                usageFilteredData = usageData.filter(usage => {
                    const searchableText = Object.values(usage).join(' ').toLowerCase();
                    return searchableText.includes(searchTerm);
                });
                usageCurrentPage = 1;
                showUsagePage(usageCurrentPage);
            }
            
            function sortUsageTable(column) {
                usageFilteredData.sort((a, b) => {
                    const aVal = a[column] || '';
                    const bVal = b[column] || '';
                    return aVal.localeCompare(bVal);
                });
                showUsagePage(usageCurrentPage);
            }
        </script>
        """
        
        # Convert data to JavaScript
        import json
        js_data = f"<script>const usageData = {json.dumps(usage_data)};</script>"
        
        html = f"""
        {js_data}
        <div class="data-table">
            <h4>Network Data Usage - Paginated View (15 records per page)</h4>
            <div style="margin: 10px 0;">
                <input type="text" id="usageSearch" placeholder="Search data usage..." 
                       onkeyup="filterUsageTable()" style="padding: 5px; width: 300px;">
                <button onclick="sortUsageTable('Date')" style="margin-left: 10px;">Sort by Date</button>
                <button onclick="sortUsageTable('Application Bundle')">Sort by App</button>
            </div>
            <table style="font-size: 12px;">
                <thead>
                    <tr style="background: #34495e; color: white;">
                        <th>Date</th>
                        <th>Application</th>
                        <th>Bytes Sent</th>
                        <th>Bytes Received</th>
                    </tr>
                </thead>
                <tbody id="usageTableBody">
                </tbody>
            </table>
            <div style="margin: 10px 0;">
                <button id="usagePrevBtn" onclick="usageCurrentPage--; showUsagePage(usageCurrentPage)">Previous</button>
                <span id="usagePageInfo" style="margin: 0 15px;"></span>
                <button id="usageNextBtn" onclick="usageCurrentPage++; showUsagePage(usageCurrentPage)">Next</button>
            </div>
        </div>
        {js_pagination}
        <script>showUsagePage(1);</script>
        """
        
        return html
    
    def add_ios_analytics_section(self, analysis):
        """Add comprehensive analytics section with communication patterns and statistics"""
        html = """
        <div class="section data">
            <h2>📊 Communication Analytics & Patterns</h2>
            <p>Advanced analysis of communication patterns, contact relationships, and usage statistics derived from iOS device data.</p>
        """
        
        # Most Messaged Contacts Analysis
        sms_data = analysis.get('sms_messages', [])
        if sms_data:
            html += self.analyze_most_messaged_contacts(sms_data)
        
        # Most Called Contacts Analysis  
        calls_data = analysis.get('call_history', [])
        if calls_data:
            html += self.analyze_most_called_contacts(calls_data)
        
        # Longest Call Durations Analysis
        if calls_data:
            html += self.analyze_longest_calls(calls_data)
        
        # Email Domain Analysis
        contacts_data = analysis.get('contacts', [])
        if contacts_data:
            html += self.analyze_email_domains(contacts_data)
        
        # Communication Timeline Analysis
        if sms_data or calls_data:
            html += self.analyze_communication_timeline(sms_data, calls_data)
        
        html += "</div>"
        return html
    
    def analyze_most_messaged_contacts(self, sms_data):
        """Analyze most frequently messaged contacts"""
        contact_message_count = {}
        contact_sent_count = {}
        contact_received_count = {}
        
        for msg in sms_data:
            contact = msg.get('Contact', 'Unknown')
            if contact == 'Unknown' or not contact:
                continue
                
            # Count total messages
            if contact not in contact_message_count:
                contact_message_count[contact] = 0
                contact_sent_count[contact] = 0
                contact_received_count[contact] = 0
            
            contact_message_count[contact] += 1
            
            # Count sent vs received
            from_me = msg.get('From Me', 'No')
            if from_me in ['Yes', '1', 'Sent']:
                contact_sent_count[contact] += 1
            else:
                contact_received_count[contact] += 1
        
        # Get top 10 most messaged contacts
        top_contacts = sorted(contact_message_count.items(), key=lambda x: x[1], reverse=True)[:10]
        
        html = """
        <div class="data-table">
            <h3>🗨️ Most Messaged Contacts</h3>
            <p>Top 10 contacts by total message volume (sent + received)</p>
            <table style="font-size: 12px;">
                <thead>
                    <tr style="background: #34495e; color: white;">
                        <th>Rank</th>
                        <th>Contact</th>
                        <th>Total Messages</th>
                        <th>Sent</th>
                        <th>Received</th>
                        <th>Ratio (Sent:Received)</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for i, (contact, total) in enumerate(top_contacts, 1):
            sent = contact_sent_count[contact]
            received = contact_received_count[contact]
            ratio = f"{sent}:{received}" if received > 0 else f"{sent}:0"
            
            html += f"""
                    <tr>
                        <td><span class="metric">#{i}</span></td>
                        <td>{contact}</td>
                        <td><strong>{total:,}</strong></td>
                        <td>{sent:,}</td>
                        <td>{received:,}</td>
                        <td>{ratio}</td>
                    </tr>
            """
        
        html += """
                </tbody>
            </table>
        </div>
        """
        
        return html
    
    def analyze_most_called_contacts(self, calls_data):
        """Analyze most frequently called contacts"""
        contact_call_count = {}
        contact_incoming_count = {}
        contact_outgoing_count = {}
        contact_total_duration = {}
        
        for call in calls_data:
            contact = call.get('Other Party', 'Unknown')
            if contact == 'Unknown' or not contact:
                continue
                
            # Count total calls
            if contact not in contact_call_count:
                contact_call_count[contact] = 0
                contact_incoming_count[contact] = 0
                contact_outgoing_count[contact] = 0
                contact_total_duration[contact] = 0
            
            contact_call_count[contact] += 1
            
            # Count incoming vs outgoing
            direction = call.get('Call Direction', 'Unknown')
            if 'Outgoing' in direction:
                contact_outgoing_count[contact] += 1
            elif 'Incoming' in direction:
                contact_incoming_count[contact] += 1
            
            # Calculate duration in seconds
            duration_str = call.get('Duration', '0')
            try:
                if ':' in duration_str:
                    time_parts = duration_str.split(':')
                    if len(time_parts) == 3:  # HH:MM:SS
                        hours, minutes, seconds = map(int, time_parts)
                        total_seconds = hours * 3600 + minutes * 60 + seconds
                    elif len(time_parts) == 2:  # MM:SS
                        minutes, seconds = map(int, time_parts)
                        total_seconds = minutes * 60 + seconds
                    else:
                        total_seconds = 0
                else:
                    total_seconds = int(float(duration_str))
                contact_total_duration[contact] += total_seconds
            except:
                pass
        
        # Get top 10 most called contacts
        top_contacts = sorted(contact_call_count.items(), key=lambda x: x[1], reverse=True)[:10]
        
        html = """
        <div class="data-table">
            <h3>📞 Most Called Contacts</h3>
            <p>Top 10 contacts by total call frequency (incoming + outgoing)</p>
            <table style="font-size: 12px;">
                <thead>
                    <tr style="background: #34495e; color: white;">
                        <th>Rank</th>
                        <th>Contact</th>
                        <th>Total Calls</th>
                        <th>Outgoing</th>
                        <th>Incoming</th>
                        <th>Total Duration</th>
                        <th>Avg Duration</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for i, (contact, total) in enumerate(top_contacts, 1):
            outgoing = contact_outgoing_count[contact]
            incoming = contact_incoming_count[contact]
            total_dur = contact_total_duration[contact]
            avg_dur = total_dur // total if total > 0 else 0
            
            # Format durations
            total_dur_str = self.format_duration(total_dur)
            avg_dur_str = self.format_duration(avg_dur)
            
            html += f"""
                    <tr>
                        <td><span class="metric">#{i}</span></td>
                        <td>{contact}</td>
                        <td><strong>{total:,}</strong></td>
                        <td>{outgoing:,}</td>
                        <td>{incoming:,}</td>
                        <td>{total_dur_str}</td>
                        <td>{avg_dur_str}</td>
                    </tr>
            """
        
        html += """
                </tbody>
            </table>
        </div>
        """
        
        return html
    
    def analyze_longest_calls(self, calls_data):
        """Analyze longest call durations"""
        call_durations = []
        
        for call in calls_data:
            contact = call.get('Other Party', 'Unknown')
            date = call.get('Date', 'Unknown')
            direction = call.get('Call Direction', 'Unknown')
            duration_str = call.get('Duration', '0')
            
            # Calculate duration in seconds
            try:
                if ':' in duration_str:
                    time_parts = duration_str.split(':')
                    if len(time_parts) == 3:  # HH:MM:SS
                        hours, minutes, seconds = map(int, time_parts)
                        total_seconds = hours * 3600 + minutes * 60 + seconds
                    elif len(time_parts) == 2:  # MM:SS
                        minutes, seconds = map(int, time_parts)
                        total_seconds = minutes * 60 + seconds
                    else:
                        total_seconds = 0
                else:
                    total_seconds = int(float(duration_str))
                
                if total_seconds > 0:  # Only include calls with actual duration
                    call_durations.append({
                        'contact': contact,
                        'date': date,
                        'direction': direction,
                        'duration_seconds': total_seconds,
                        'duration_formatted': self.format_duration(total_seconds)
                    })
            except:
                continue
        
        # Sort by duration and get top 10
        longest_calls = sorted(call_durations, key=lambda x: x['duration_seconds'], reverse=True)[:10]
        
        html = """
        <div class="data-table">
            <h3>⏱️ Longest Call Durations</h3>
            <p>Top 10 longest individual calls by duration</p>
            <table style="font-size: 12px;">
                <thead>
                    <tr style="background: #34495e; color: white;">
                        <th>Rank</th>
                        <th>Contact</th>
                        <th>Date</th>
                        <th>Direction</th>
                        <th>Duration</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for i, call in enumerate(longest_calls, 1):
            html += f"""
                    <tr>
                        <td><span class="metric">#{i}</span></td>
                        <td>{call['contact']}</td>
                        <td>{call['date']}</td>
                        <td>{call['direction']}</td>
                        <td><strong>{call['duration_formatted']}</strong></td>
                    </tr>
            """
        
        html += """
                </tbody>
            </table>
        </div>
        """
        
        return html
    
    def analyze_email_domains(self, contacts_data):
        """Analyze most common email domains in contacts"""
        domain_count = {}
        
        for contact in contacts_data:
            email = contact.get('Email', '') or contact.get('email', '') or contact.get('Email Address', '')
            if email and '@' in email:
                try:
                    domain = email.split('@')[1].lower()
                    if domain not in domain_count:
                        domain_count[domain] = 0
                    domain_count[domain] += 1
                except:
                    continue
        
        # Get top 10 domains
        top_domains = sorted(domain_count.items(), key=lambda x: x[1], reverse=True)[:10]
        
        html = """
        <div class="data-table">
            <h3>📧 Email Domain Analysis</h3>
            <p>Most common email domains in contact database</p>
            <table style="font-size: 12px;">
                <thead>
                    <tr style="background: #34495e; color: white;">
                        <th>Rank</th>
                        <th>Domain</th>
                        <th>Contact Count</th>
                        <th>Percentage</th>
                        <th>Domain Type</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        total_contacts_with_email = sum(domain_count.values())
        
        for i, (domain, count) in enumerate(top_domains, 1):
            percentage = (count / total_contacts_with_email * 100) if total_contacts_with_email > 0 else 0
            domain_type = self.categorize_email_domain(domain)
            
            html += f"""
                    <tr>
                        <td><span class="metric">#{i}</span></td>
                        <td>{domain}</td>
                        <td><strong>{count:,}</strong></td>
                        <td>{percentage:.1f}%</td>
                        <td>{domain_type}</td>
                    </tr>
            """
        
        html += """
                </tbody>
            </table>
        </div>
        """
        
        return html
    
    def analyze_communication_timeline(self, sms_data, calls_data):
        """Analyze communication patterns over time"""
        hourly_activity = {}
        daily_activity = {}
        
        # Initialize hourly buckets
        for hour in range(24):
            hourly_activity[hour] = {'sms': 0, 'calls': 0}
        
        # Initialize daily buckets
        for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
            daily_activity[day] = {'sms': 0, 'calls': 0}
        
        # Process SMS data
        for msg in sms_data:
            try:
                date_str = msg.get('Message Date', '') or msg.get('Date', '')
                if date_str:
                    # Parse datetime
                    import datetime
                    dt = datetime.datetime.strptime(date_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
                    hour = dt.hour
                    day = dt.strftime('%A')
                    
                    hourly_activity[hour]['sms'] += 1
                    daily_activity[day]['sms'] += 1
            except:
                continue
        
        # Process call data
        for call in calls_data:
            try:
                date_str = call.get('Date', '')
                if date_str:
                    # Parse datetime
                    import datetime
                    dt = datetime.datetime.strptime(date_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
                    hour = dt.hour
                    day = dt.strftime('%A')
                    
                    hourly_activity[hour]['calls'] += 1
                    daily_activity[day]['calls'] += 1
            except:
                continue
        
        # Find peak activity times
        peak_sms_hour = max(hourly_activity.keys(), key=lambda h: hourly_activity[h]['sms'])
        peak_call_hour = max(hourly_activity.keys(), key=lambda h: hourly_activity[h]['calls'])
        peak_sms_day = max(daily_activity.keys(), key=lambda d: daily_activity[d]['sms'])
        peak_call_day = max(daily_activity.keys(), key=lambda d: daily_activity[d]['calls'])
        
        html = f"""
        <div class="data-table">
            <h3>📈 Communication Timeline Analysis</h3>
            <p>Temporal patterns in communication behavior</p>
            
            <div class="two-column">
                <div class="column">
                    <h4>Peak Activity Times</h4>
                    <table style="font-size: 12px;">
                        <tr><th>Metric</th><th>Peak Time</th><th>Activity Count</th></tr>
                        <tr>
                            <td>Most SMS Activity</td>
                            <td><strong>{peak_sms_hour:02d}:00 - {peak_sms_hour+1:02d}:00</strong></td>
                            <td>{hourly_activity[peak_sms_hour]['sms']:,} messages</td>
                        </tr>
                        <tr>
                            <td>Most Call Activity</td>
                            <td><strong>{peak_call_hour:02d}:00 - {peak_call_hour+1:02d}:00</strong></td>
                            <td>{hourly_activity[peak_call_hour]['calls']:,} calls</td>
                        </tr>
                        <tr>
                            <td>Most SMS Day</td>
                            <td><strong>{peak_sms_day}</strong></td>
                            <td>{daily_activity[peak_sms_day]['sms']:,} messages</td>
                        </tr>
                        <tr>
                            <td>Most Call Day</td>
                            <td><strong>{peak_call_day}</strong></td>
                            <td>{daily_activity[peak_call_day]['calls']:,} calls</td>
                        </tr>
                    </table>
                </div>
                
                <div class="column">
                    <h4>Activity Distribution</h4>
                    <table style="font-size: 12px;">
                        <tr><th>Time Period</th><th>SMS Count</th><th>Call Count</th></tr>
                        <tr>
                            <td>Morning (6AM-12PM)</td>
                            <td>{sum(hourly_activity[h]['sms'] for h in range(6, 12)):,}</td>
                            <td>{sum(hourly_activity[h]['calls'] for h in range(6, 12)):,}</td>
                        </tr>
                        <tr>
                            <td>Afternoon (12PM-6PM)</td>
                            <td>{sum(hourly_activity[h]['sms'] for h in range(12, 18)):,}</td>
                            <td>{sum(hourly_activity[h]['calls'] for h in range(12, 18)):,}</td>
                        </tr>
                        <tr>
                            <td>Evening (6PM-12AM)</td>
                            <td>{sum(hourly_activity[h]['sms'] for h in range(18, 24)):,}</td>
                            <td>{sum(hourly_activity[h]['calls'] for h in range(18, 24)):,}</td>
                        </tr>
                        <tr>
                            <td>Night (12AM-6AM)</td>
                            <td>{sum(hourly_activity[h]['sms'] for h in range(0, 6)):,}</td>
                            <td>{sum(hourly_activity[h]['calls'] for h in range(0, 6)):,}</td>
                        </tr>
                    </table>
                </div>
            </div>
        </div>
        """
        
        return html
    
    def format_duration(self, seconds):
        """Format duration in seconds to human readable format"""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            remaining_seconds = seconds % 60
            return f"{minutes}m {remaining_seconds}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m"
    
    def categorize_email_domain(self, domain):
        """Categorize email domain type"""
        if domain in ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com', 'icloud.com', 'me.com', 'mac.com']:
            return 'Personal'
        elif domain.endswith('.edu'):
            return 'Educational'
        elif domain.endswith('.gov'):
            return 'Government'
        elif domain.endswith('.mil'):
            return 'Military'
        elif domain.endswith('.org'):
            return 'Organization'
        else:
            return 'Business/Other'
    
    def add_ios_interactions_table(self, interactions_data):
        """Add paginated user interactions table for iOS data with JavaScript pagination"""
        if not interactions_data:
            return "<p>No user interaction data available.</p>"
        
        # Create JavaScript for pagination
        js_pagination = """
        <script>
            let interactionsCurrentPage = 1;
            const interactionsItemsPerPage = 15;
            let interactionsFilteredData = [...interactionsData];
            
            function showInteractionsPage(page) {
                const startIndex = (page - 1) * interactionsItemsPerPage;
                const endIndex = startIndex + interactionsItemsPerPage;
                const pageData = interactionsFilteredData.slice(startIndex, endIndex);
                
                const tbody = document.getElementById('interactionsTableBody');
                tbody.innerHTML = '';
                
                pageData.forEach(interaction => {
                    const row = tbody.insertRow();
                    // Using actual CSV columns: Event Start, Event End, Application, Direction, Sender, Sender ID, Recipient, Recipient ID, Domain
                    const date = interaction['Event Start'] || interaction.Date || interaction.date || interaction.Timestamp || interaction['Start Date'] || 'Unknown';
                    const contact = interaction.Sender || interaction.Recipient || interaction.Contact || interaction.contact || interaction['Bundle ID'] || interaction.Identifier || 'Unknown';
                    const interactionType = interaction.Direction || interaction.Application || interaction['Interaction Type'] || interaction.interaction_type || interaction.Mechanism || interaction.Type || 'Unknown';
                    
                    // Calculate duration from Event Start and Event End or use provided duration
                    let duration = '0s';
                    try {
                        const start = interaction['Event Start'] || '';
                        const end = interaction['Event End'] || '';
                        if (start && end && start !== end) {
                            duration = 'Event';
                        } else {
                            duration = interaction.Duration || interaction.duration || interaction['Total Duration'] || '0s';
                        }
                    } catch {
                        duration = '0s';
                    }
                    
                    // Format duration
                    if (duration !== 'Event' && duration !== '0s') {
                        try {
                            const durSec = parseInt(parseFloat(duration));
                            if (durSec > 60) {
                                duration = Math.floor(durSec / 60) + 'm ' + (durSec % 60) + 's';
                            } else {
                                duration = durSec + 's';
                            }
                        } catch {
                            // Keep original duration value
                        }
                    }
                    
                    row.innerHTML = `
                        <td>${date}</td>
                        <td style="max-width: 200px; word-wrap: break-word;">${contact}</td>
                        <td>${interactionType}</td>
                        <td>${duration}</td>
                    `;
                });
                
                updateInteractionsPagination();
            }
            
            function updateInteractionsPagination() {
                const totalPages = Math.ceil(interactionsFilteredData.length / interactionsItemsPerPage);
                document.getElementById('interactionsPageInfo').textContent = 
                    `Page ${interactionsCurrentPage} of ${totalPages} (${interactionsFilteredData.length} records)`;
                
                document.getElementById('interactionsPrevBtn').disabled = interactionsCurrentPage === 1;
                document.getElementById('interactionsNextBtn').disabled = interactionsCurrentPage === totalPages;
            }
            
            function filterInteractionsTable() {
                const searchTerm = document.getElementById('interactionsSearch').value.toLowerCase();
                interactionsFilteredData = interactionsData.filter(interaction => {
                    const searchableText = Object.values(interaction).join(' ').toLowerCase();
                    return searchableText.includes(searchTerm);
                });
                interactionsCurrentPage = 1;
                showInteractionsPage(interactionsCurrentPage);
            }
            
            function sortInteractionsTable(column) {
                interactionsFilteredData.sort((a, b) => {
                    const aVal = a[column] || '';
                    const bVal = b[column] || '';
                    return aVal.localeCompare(bVal);
                });
                showInteractionsPage(interactionsCurrentPage);
            }
        </script>
        """
        
        # Convert data to JavaScript
        import json
        js_data = f"<script>const interactionsData = {json.dumps(interactions_data)};</script>"
        
        html = f"""
        {js_data}
        <div class="data-table">
            <h4>User Interaction Events - Paginated View (15 records per page)</h4>
            <div style="margin: 10px 0;">
                <input type="text" id="interactionsSearch" placeholder="Search interactions..." 
                       onkeyup="filterInteractionsTable()" style="padding: 5px; width: 300px;">
                <button onclick="sortInteractionsTable('Event Start')" style="margin-left: 10px;">Sort by Date</button>
                <button onclick="sortInteractionsTable('Sender')">Sort by Contact</button>
            </div>
            <table style="font-size: 12px;">
                <thead>
                    <tr style="background: #34495e; color: white;">
                        <th>Date</th>
                        <th>Contact/App</th>
                        <th>Interaction Type</th>
                        <th>Duration</th>
                    </tr>
                </thead>
                <tbody id="interactionsTableBody">
                </tbody>
            </table>
            <div style="margin: 10px 0;">
                <button id="interactionsPrevBtn" onclick="interactionsCurrentPage--; showInteractionsPage(interactionsCurrentPage)">Previous</button>
                <span id="interactionsPageInfo" style="margin: 0 15px;"></span>
                <button id="interactionsNextBtn" onclick="interactionsCurrentPage++; showInteractionsPage(interactionsCurrentPage)">Next</button>
            </div>
        </div>
        {js_pagination}
        <script>showInteractionsPage(1);</script>
        """
        
        return html
        
    def setup_ios_parse_tabs(self):
        """Setup content areas for iOS parse result tabs"""
        # Setup each tab with proper table structures
        self.setup_device_info_tab()
        self.setup_sms_table()
        self.setup_calls_table()
        self.setup_interactions_table()
        self.setup_safari_table()
        self.setup_contacts_table()
        self.setup_data_usage_table()
        self.setup_accounts_table()
        self.setup_permissions_table()
        self.setup_notes_table()
        self.setup_photos_table()
            
    def load_parse_results(self, results):
        """Load parsing results into the result tabs using proper table display"""
        if not results:
            self.update_parse_status("No results to display")
            return
            
        self.update_parse_status("Loading results into tabs...")
        
        try:
            # Store the parsed data for filtering/searching
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
            
            # Load device info
            self.load_device_info(results.get('device_info', {}))
            
            # Store photo path for thumbnails if available
            self.photos_path = results.get('extracted_photos_path', None)
            
            # Populate all tables with empty search (shows all data)
            self.filter_sms_results("")
            self.filter_call_results("")
            self.filter_contacts_results("")
            self.filter_data_usage_results("")
            self.filter_accounts_results("")
            self.filter_permissions_results("")
            self.filter_notes_results("")
            self.filter_photos_results("")
            self.filter_interactions_results("")
            self.filter_safari_results("")
            
            # Display thumbnails if photos were extracted
            if self.photos_path and os.path.exists(self.photos_path):
                self.display_photos(self.photos_path)
                # Switch to thumbnails tab if photos were found
                if hasattr(self, 'photos_notebook'):
                    self.photos_notebook.select(1)  # Select thumbnails tab
            
            # Show summary
            total_items = sum([
                len(self.sms_data),
                len(self.calls_data),
                len(self.contacts_data),
                len(self.data_usage_data),
                len(self.accounts_data),
                len(self.permissions_data),
                len(self.notes_data),
                len(self.photos_data),
                len(self.interactions_data),
                len(self.safari_data)
            ])
            
            self.update_parse_status(f"Results loaded successfully! {total_items} total items processed.")
            
        except Exception as e:
            print(f"Error loading results: {e}")
            import traceback
            traceback.print_exc()
            self.update_parse_status(f"Error displaying results: {e}")
            
    def load_device_info(self, device_info):
        """Load device information into the device info tab"""
        # Enable the text widget for editing
        self.device_result.configure(state="normal")
        
        # Clear previous content
        self.device_result.delete("1.0", "end")
        
        if device_info:
            device_text = "DEVICE INFORMATION\n\n"
            for key, value in device_info.items():
                device_text += f"{key}: {value}\n"
            self.device_result.insert("0.0", device_text)
        else:
            self.device_result.insert("0.0", "No device information available in the backup.")
        
        # Disable the text widget to make it read-only
        self.device_result.configure(state="disabled")
        
    def setup_device_info_tab(self):
        """Setup device information display"""
        # Create a read-only text widget for device information
        self.device_result = ctk.CTkTextbox(self.tab_device, wrap="word")
        self.device_result.pack(fill="both", expand=True, padx=10, pady=10)
        self.device_result.insert("0.0", "Device information will be displayed here after parsing...")
    
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

    def setup_safari_table(self):
        """Setup Safari history table"""
        
        # Search controls
        search_frame = ctk.CTkFrame(self.tab_safari)
        search_frame.pack(fill="x", padx=10, pady=5)
        
        search_label = ctk.CTkLabel(search_frame, text="Search:")
        search_label.pack(side="left", padx=5, pady=5)
        
        self.safari_search_entry = ctk.CTkEntry(search_frame, width=250)
        self.safari_search_entry.pack(side="left", padx=5, pady=5, fill="x", expand=True)
        
        search_button = ctk.CTkButton(
            search_frame, text="Search", 
            command=lambda: self.filter_safari_results(self.safari_search_entry.get())
        )
        search_button.pack(side="left", padx=5, pady=5)
        
        clear_button = ctk.CTkButton(
            search_frame, text="Clear", 
            command=lambda: [self.safari_search_entry.delete(0, "end"), self.filter_safari_results("")]
        )
        clear_button.pack(side="left", padx=5, pady=5)
        
        # Table
        table_frame = ctk.CTkFrame(self.tab_safari)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.safari_tree = ttk.Treeview(table_frame)
        self.safari_tree["columns"] = ("date", "title", "url", "loaded", "visit_count")
        
        # Format columns
        self.safari_tree.column("#0", width=0, stretch=False)
        self.safari_tree.column("date", anchor="w", width=150)
        self.safari_tree.column("title", anchor="w", width=200)
        self.safari_tree.column("url", anchor="w", width=300)
        self.safari_tree.column("loaded", anchor="w", width=80)
        self.safari_tree.column("visit_count", anchor="e", width=100)
        
        # Headings
        self.safari_tree.heading("date", text="Date Visited", anchor="w")
        self.safari_tree.heading("title", text="Page Title", anchor="w")
        self.safari_tree.heading("url", text="URL", anchor="w")
        self.safari_tree.heading("loaded", text="Page Loaded", anchor="w")
        self.safari_tree.heading("visit_count", text="Visit Count", anchor="e")
        
        # Scrollbars
        y_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.safari_tree.yview)
        x_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.safari_tree.xview)
        self.safari_tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
        
        y_scrollbar.pack(side="right", fill="y")
        x_scrollbar.pack(side="bottom", fill="x")
        self.safari_tree.pack(fill="both", expand=True)
        
        # Bind double-click to open URL
        self.safari_tree.bind("<Double-1>", self.open_safari_url)
        
    def setup_contacts_table(self):
        """Setup contacts table"""
        
        # Search controls
        search_frame = ctk.CTkFrame(self.tab_contacts)
        search_frame.pack(fill="x", padx=10, pady=5)
        
        search_label = ctk.CTkLabel(search_frame, text="Search:")
        search_label.pack(side="left", padx=5, pady=5)
        
        self.contacts_search_entry = ctk.CTkEntry(search_frame, width=250)
        self.contacts_search_entry.pack(side="left", padx=5, pady=5, fill="x", expand=True)
        
        search_button = ctk.CTkButton(
            search_frame, text="Search", 
            command=lambda: self.filter_contacts_results(self.contacts_search_entry.get())
        )
        search_button.pack(side="left", padx=5, pady=5)
        
        clear_button = ctk.CTkButton(
            search_frame, text="Clear", 
            command=lambda: [self.contacts_search_entry.delete(0, "end"), self.filter_contacts_results("")]
        )
        clear_button.pack(side="left", padx=5, pady=5)
        
        # Table
        table_frame = ctk.CTkFrame(self.tab_contacts)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.contacts_tree = ttk.Treeview(table_frame)
        self.contacts_tree["columns"] = ("first_name", "last_name", "main_number", "mobile_number", "email")
        
        # Format columns
        self.contacts_tree.column("#0", width=0, stretch=False)
        self.contacts_tree.column("first_name", anchor="w", width=100)
        self.contacts_tree.column("last_name", anchor="w", width=100)
        self.contacts_tree.column("main_number", anchor="w", width=120)
        self.contacts_tree.column("mobile_number", anchor="w", width=120)
        self.contacts_tree.column("email", anchor="w", width=200)
        
        # Headings
        self.contacts_tree.heading("first_name", text="First Name", anchor="w")
        self.contacts_tree.heading("last_name", text="Last Name", anchor="w")
        self.contacts_tree.heading("main_number", text="Main Number", anchor="w")
        self.contacts_tree.heading("mobile_number", text="Mobile", anchor="w")
        self.contacts_tree.heading("email", text="Email", anchor="w")
        
        # Scrollbars
        y_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.contacts_tree.yview)
        x_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.contacts_tree.xview)
        self.contacts_tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
        
        y_scrollbar.pack(side="right", fill="y")
        x_scrollbar.pack(side="bottom", fill="x")
        self.contacts_tree.pack(fill="both", expand=True)
        
    def setup_data_usage_table(self):
        """Setup data usage table"""
        
        # Search controls
        search_frame = ctk.CTkFrame(self.tab_data_usage)
        search_frame.pack(fill="x", padx=10, pady=5)
        
        search_label = ctk.CTkLabel(search_frame, text="Search:")
        search_label.pack(side="left", padx=5, pady=5)
        
        self.data_usage_search_entry = ctk.CTkEntry(search_frame, width=250)
        self.data_usage_search_entry.pack(side="left", padx=5, pady=5, fill="x", expand=True)
        
        search_button = ctk.CTkButton(
            search_frame, text="Search", 
            command=lambda: self.filter_data_usage_results(self.data_usage_search_entry.get())
        )
        search_button.pack(side="left", padx=5, pady=5)
        
        clear_button = ctk.CTkButton(
            search_frame, text="Clear", 
            command=lambda: [self.data_usage_search_entry.delete(0, "end"), self.filter_data_usage_results("")]
        )
        clear_button.pack(side="left", padx=5, pady=5)
        
        # Table
        table_frame = ctk.CTkFrame(self.tab_data_usage)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.data_usage_tree = ttk.Treeview(table_frame)
        self.data_usage_tree["columns"] = ("date", "app_name", "cell_in", "cell_out")
        
        # Format columns
        self.data_usage_tree.column("#0", width=0, stretch=False)
        self.data_usage_tree.column("date", anchor="w", width=150)
        self.data_usage_tree.column("app_name", anchor="w", width=200)
        self.data_usage_tree.column("cell_in", anchor="e", width=100)
        self.data_usage_tree.column("cell_out", anchor="e", width=100)
        
        # Headings
        self.data_usage_tree.heading("date", text="Date", anchor="w")
        self.data_usage_tree.heading("app_name", text="Application", anchor="w")
        self.data_usage_tree.heading("cell_in", text="Cell In (KB)", anchor="e")
        self.data_usage_tree.heading("cell_out", text="Cell Out (KB)", anchor="e")
        
        # Scrollbars
        y_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.data_usage_tree.yview)
        x_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.data_usage_tree.xview)
        self.data_usage_tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
        
        y_scrollbar.pack(side="right", fill="y")
        x_scrollbar.pack(side="bottom", fill="x")
        self.data_usage_tree.pack(fill="both", expand=True)
        
    def setup_accounts_table(self):
        """Setup accounts table"""
        
        # Search controls
        search_frame = ctk.CTkFrame(self.tab_accounts)
        search_frame.pack(fill="x", padx=10, pady=5)
        
        search_label = ctk.CTkLabel(search_frame, text="Search:")
        search_label.pack(side="left", padx=5, pady=5)
        
        self.accounts_search_entry = ctk.CTkEntry(search_frame, width=250)
        self.accounts_search_entry.pack(side="left", padx=5, pady=5, fill="x", expand=True)
        
        search_button = ctk.CTkButton(
            search_frame, text="Search", 
            command=lambda: self.filter_accounts_results(self.accounts_search_entry.get())
        )
        search_button.pack(side="left", padx=5, pady=5)
        
        clear_button = ctk.CTkButton(
            search_frame, text="Clear", 
            command=lambda: [self.accounts_search_entry.delete(0, "end"), self.filter_accounts_results("")]
        )
        clear_button.pack(side="left", padx=5, pady=5)
        
        # Table
        table_frame = ctk.CTkFrame(self.tab_accounts)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.accounts_tree = ttk.Treeview(table_frame)
        self.accounts_tree["columns"] = ("date", "username", "description", "account_type", "service")
        
        # Format columns
        self.accounts_tree.column("#0", width=0, stretch=False)
        self.accounts_tree.column("date", anchor="w", width=150)
        self.accounts_tree.column("username", anchor="w", width=200)
        self.accounts_tree.column("description", anchor="w", width=200)
        self.accounts_tree.column("account_type", anchor="w", width=100)
        self.accounts_tree.column("service", anchor="w", width=150)
        
        # Headings
        self.accounts_tree.heading("date", text="Date", anchor="w")
        self.accounts_tree.heading("username", text="Username", anchor="w")
        self.accounts_tree.heading("description", text="Description", anchor="w")
        self.accounts_tree.heading("account_type", text="Account Type", anchor="w")
        self.accounts_tree.heading("service", text="Service", anchor="w")
        
        # Scrollbars
        y_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.accounts_tree.yview)
        x_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.accounts_tree.xview)
        self.accounts_tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
        
        y_scrollbar.pack(side="right", fill="y")
        x_scrollbar.pack(side="bottom", fill="x")
        self.accounts_tree.pack(fill="both", expand=True)
        
    def setup_permissions_table(self):
        """Setup permissions table"""
        
        # Search controls
        search_frame = ctk.CTkFrame(self.tab_permissions)
        search_frame.pack(fill="x", padx=10, pady=5)
        
        search_label = ctk.CTkLabel(search_frame, text="Search:")
        search_label.pack(side="left", padx=5, pady=5)
        
        self.permissions_search_entry = ctk.CTkEntry(search_frame, width=250)
        self.permissions_search_entry.pack(side="left", padx=5, pady=5, fill="x", expand=True)
        
        search_button = ctk.CTkButton(
            search_frame, text="Search", 
            command=lambda: self.filter_permissions_results(self.permissions_search_entry.get())
        )
        search_button.pack(side="left", padx=5, pady=5)
        
        clear_button = ctk.CTkButton(
            search_frame, text="Clear", 
            command=lambda: [self.permissions_search_entry.delete(0, "end"), self.filter_permissions_results("")]
        )
        clear_button.pack(side="left", padx=5, pady=5)
        
        # Table
        table_frame = ctk.CTkFrame(self.tab_permissions)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.permissions_tree = ttk.Treeview(table_frame)
        self.permissions_tree["columns"] = ("permission", "app_bundle", "status")
        
        # Format columns
        self.permissions_tree.column("#0", width=0, stretch=False)
        self.permissions_tree.column("permission", anchor="w", width=200)
        self.permissions_tree.column("app_bundle", anchor="w", width=250)
        self.permissions_tree.column("status", anchor="w", width=100)
        
        # Headings
        self.permissions_tree.heading("permission", text="Permission", anchor="w")
        self.permissions_tree.heading("app_bundle", text="Application", anchor="w")
        self.permissions_tree.heading("status", text="Status", anchor="w")
        
        # Scrollbars
        y_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.permissions_tree.yview)
        x_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.permissions_tree.xview)
        self.permissions_tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
        
        y_scrollbar.pack(side="right", fill="y")
        x_scrollbar.pack(side="bottom", fill="x")
        self.permissions_tree.pack(fill="both", expand=True)
        
        # Configure tags for status coloring
        self.permissions_tree.tag_configure('granted', background='#e6ffe6')
        self.permissions_tree.tag_configure('denied', background='#ffe6e6')
        self.permissions_tree.tag_configure('unknown', background='#ffffe6')
    
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
        
        # Create a master frame for both table and detail view
        master_frame = ctk.CTkFrame(self.tab_notes)
        master_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Create frame for the notes list (top half)
        table_frame = ctk.CTkFrame(master_frame)
        table_frame.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Create Treeview for notes list
        self.notes_tree = ttk.Treeview(table_frame)
        self.notes_tree["columns"] = ("date", "title", "folder", "snippet")
        
        # Format columns
        self.notes_tree.column("#0", width=0, stretch=tk.NO)  # Hide the first column
        self.notes_tree.column("date", anchor=tk.W, width=150)
        self.notes_tree.column("title", anchor=tk.W, width=200)
        self.notes_tree.column("folder", anchor=tk.W, width=150)
        self.notes_tree.column("snippet", anchor=tk.W, width=300)
        
        # Create headings
        self.notes_tree.heading("#0", text="", anchor=tk.W)
        self.notes_tree.heading("date", text="Date", anchor=tk.W)
        self.notes_tree.heading("title", text="Title", anchor=tk.W)
        self.notes_tree.heading("folder", text="Folder", anchor=tk.W)
        self.notes_tree.heading("snippet", text="Preview", anchor=tk.W)
        
        # Add scrollbars for the table
        y_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.notes_tree.yview)
        x_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.notes_tree.xview)
        self.notes_tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
        
        # Pack table components
        y_scrollbar.pack(side="right", fill="y")
        x_scrollbar.pack(side="bottom", fill="x")
        self.notes_tree.pack(fill="both", expand=True)
        
        # Create a separator
        separator = ttk.Separator(master_frame, orient='horizontal')
        separator.pack(fill='x', pady=5)
        
        # Create a label for the note content display
        content_label = ctk.CTkLabel(master_frame, text="Selected Note Content:", anchor="w")
        content_label.pack(fill="x", padx=5, pady=(5,0))
        
        # Create frame for note content display (bottom half)
        content_frame = ctk.CTkFrame(master_frame)
        content_frame.pack(fill="both", expand=False, padx=0, pady=5, ipady=100)  # Give it some height
        
        # Create Text widget for displaying the full note content with word wrap
        self.notes_display = ctk.CTkTextbox(content_frame, wrap="word", height=150)
        self.notes_display.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Bind selection event to update note display
        self.notes_tree.bind("<<TreeviewSelect>>", self.update_notes_display)
        
    def setup_photos_table(self):
        """Set up the photos results display with tabbed interface"""
        # Create a tabview for photos with two tabs
        self.photos_tabview = ctk.CTkTabview(self.tab_photos)
        self.photos_tabview.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Tab 1: Photo List (table view)
        self.photo_list_tab = self.photos_tabview.add("Photo List")
        
        # Search frame for photo list
        photos_search_frame = ctk.CTkFrame(self.photo_list_tab)
        photos_search_frame.pack(fill="x", padx=5, pady=5)
        
        photos_search_label = ctk.CTkLabel(photos_search_frame, text="Search Photos:")
        photos_search_label.pack(side="left", padx=5)
        
        self.photos_search_var = tk.StringVar()
        self.photos_search_var.trace("w", lambda *args: self.filter_photos_results(self.photos_search_var.get()))
        
        photos_search_entry = ctk.CTkEntry(photos_search_frame, textvariable=self.photos_search_var)
        photos_search_entry.pack(side="left", padx=5, fill="x", expand=True)
        
        # Photos count
        self.photos_count = ctk.CTkLabel(photos_search_frame, text="0 photos")
        self.photos_count.pack(side="right", padx=5)
        
        # Photos table
        photos_columns = ("Filename", "Path", "Date Taken", "Scene Classification", "Confidence")
        self.photos_tree = ttk.Treeview(self.photo_list_tab, columns=photos_columns, show="tree headings")
        
        # Configure columns
        self.photos_tree.column("#0", width=50, minwidth=50)
        self.photos_tree.heading("#0", text="ID")
        
        for col in photos_columns:
            self.photos_tree.column(col, width=150, minwidth=100)
            self.photos_tree.heading(col, text=col)
        
        # Scrollbars for photos table
        photos_tree_scroll_y = ttk.Scrollbar(self.photo_list_tab, orient="vertical", command=self.photos_tree.yview)
        photos_tree_scroll_x = ttk.Scrollbar(self.photo_list_tab, orient="horizontal", command=self.photos_tree.xview)
        self.photos_tree.configure(yscrollcommand=photos_tree_scroll_y.set, xscrollcommand=photos_tree_scroll_x.set)
        
        # Pack the treeview and scrollbars using pack for better control
        tree_frame = ctk.CTkFrame(self.photo_list_tab)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        photos_tree_scroll_y.pack(side="right", fill="y")
        photos_tree_scroll_x.pack(side="bottom", fill="x")
        self.photos_tree.pack(fill="both", expand=True)
        
        # Tab 2: Photo Thumbnails (gallery view)
        self.photo_thumbnails_tab = self.photos_tabview.add("Thumbnails")
        
        # Initialize executor for background thumbnail loading
        import concurrent.futures
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
    
    # Filter methods for all data types

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
    
    def update_sms_message_display(self, event):
        """Update SMS message display when selection changes"""
        try:
            selection = self.sms_tree.selection()
            if selection:
                item = self.sms_tree.item(selection[0])
                values = item['values']
                if len(values) > 4:
                    message = values[4]  # Message is in the 5th column
                    self.sms_message_display.delete("1.0", "end")
                    self.sms_message_display.insert("1.0", message)
                else:
                    self.sms_message_display.delete("1.0", "end")
                    self.sms_message_display.insert("1.0", "No message content available")
            else:
                self.sms_message_display.delete("1.0", "end")
                self.sms_message_display.insert("1.0", "Select a message to view content")
        except Exception as e:
            print(f"Error updating SMS message display: {e}")
            self.sms_message_display.delete("1.0", "end")
            self.sms_message_display.insert("1.0", "Error displaying message")

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
    
    def filter_contacts_results(self, search_term):
        """Filter contacts results based on search term"""
        # Clear the tree
        for item in self.contacts_tree.get_children():
            self.contacts_tree.delete(item)
        
        # If we have contacts data
        if hasattr(self, 'contacts_data') and self.contacts_data:
            search_term = search_term.lower()
            
            # Debug: Print first contact to see field names
            if len(self.contacts_data) > 0:
                print(f"Sample contact keys: {list(self.contacts_data[0].keys())}")
            
            # Add filtered items
            for i, contact in enumerate(self.contacts_data):
                # Get values with multiple possible field names
                first_name = (contact.get('First Name') or 
                            contact.get('first_name') or 
                            contact.get('FirstName') or 
                            contact.get('given_name') or '')
                
                last_name = (contact.get('Last Name') or 
                            contact.get('last_name') or 
                            contact.get('LastName') or 
                            contact.get('family_name') or '')
                
                # Try multiple possible field names for phone numbers
                main_number = (contact.get('Main Number') or 
                            contact.get('main_number') or 
                            contact.get('Phone Number') or 
                            contact.get('phone_number') or 
                            contact.get('phone') or 
                            contact.get('Primary Phone') or '')
                
                mobile_number = (contact.get('Mobile Number') or 
                            contact.get('mobile_number') or 
                            contact.get('Mobile') or 
                            contact.get('mobile') or 
                            contact.get('Cell Phone') or 
                            contact.get('cell_phone') or '')
                
                # Try multiple possible field names for email
                email = (contact.get('Email') or 
                        contact.get('email') or 
                        contact.get('Email Address') or 
                        contact.get('email_address') or 
                        contact.get('Primary Email') or '')
                
                # Check if search term matches in any field
                if (search_term in str(first_name).lower() or
                    search_term in str(last_name).lower() or
                    search_term in str(main_number).lower() or
                    search_term in str(mobile_number).lower() or
                    search_term in str(email).lower()):
                    
                    values = (
                        first_name,
                        last_name,
                        main_number,
                        mobile_number,
                        email
                    )
                    
                    self.contacts_tree.insert("", "end", text=i, values=values)
            
            # Debug: Print how many contacts were added
            contact_count = len(self.contacts_tree.get_children())
            print(f"Added {contact_count} contacts to tree out of {len(self.contacts_data)} total")
        else:
            print("No contacts_data found or contacts_data is empty")   
    def filter_data_usage_results(self, search_term):
        """Filter data usage results based on search term"""
        # Clear the tree
        for item in self.data_usage_tree.get_children():
            self.data_usage_tree.delete(item)
        
        # If we have data usage data
        if hasattr(self, 'data_usage_data') and self.data_usage_data:
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
                
                # Check if search term exists in any field
                if (search_term in str(date_value).lower() or
                    search_term in str(usage.get('Application Bundle', '')).lower()):
                    
                    # Convert date for display
                    date_display = self.convert_timestamp(date_value) if date_value else "Unknown Date"
                    
                    self.data_usage_tree.insert(
                        "", "end", text=i,
                        values=(
                            date_display,
                            usage.get('Application Bundle', ''),
                            usage.get('WWAN In (KB)', '0'),
                            usage.get('WWAN Out (KB)', '0')
                        )
                    )
    
    def filter_accounts_results(self, search_term):
        """Filter accounts results based on search term"""
        # Clear the tree
        for item in self.accounts_tree.get_children():
            self.accounts_tree.delete(item)
        
        # If we have accounts data
        if hasattr(self, 'accounts_data') and self.accounts_data:
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
                            date_display,
                            account.get('Username', ''),
                            account.get('Description', ''),
                            account.get('Account Type', ''),
                            account.get('Service', '')
                        )
                    )
    
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
                    
                    # Add color highlighting based on permission status
                    if 'granted' in status.lower():
                        self.permissions_tree.item(item_id, tags=('granted',))
                    elif 'denied' in status.lower():
                        self.permissions_tree.item(item_id, tags=('denied',))
                    else:
                        self.permissions_tree.item(item_id, tags=('unknown',))
    
    def filter_notes_results(self, search_term):
        """Filter notes results based on search term"""
        print(f"DEBUG: filter_notes_results called with search_term: '{search_term}'")
        
        # Clear the tree
        for item in self.notes_tree.get_children():
            self.notes_tree.delete(item)
        
        # Check if we have notes data
        if not hasattr(self, 'notes_data'):
            print("DEBUG: No notes_data attribute found")
            return
            
        if not self.notes_data:
            print("DEBUG: notes_data is empty")
            return
            
        print(f"DEBUG: Processing {len(self.notes_data)} notes")
        
        search_term = search_term.lower()
        
        # Add filtered items
        for i, note in enumerate(self.notes_data):
            print(f"DEBUG: Processing note {i}: {note}")
            
            # Handle the actual field names from the parser
            title = (note.get('Title') or 
                    note.get('title') or 
                    'Untitled')
            
            folder = "N/A"  # Default folder if not found
            
            # The content field is called 'Data' from the parser
            note_content = (note.get('Data') or 
                        note.get('data') or 
                        note.get('ZCONTENT') or  # Fallback to old field name
                        '')
            
            # Date fields from the parser
            date_value = (note.get('Creation Date') or 
                        note.get('Modification Date') or 
                        note.get('creation_date') or 
                        note.get('modification_date') or 
                        '')
            
            print(f"DEBUG: Note {i} - title: '{title}', folder: '{folder}', content length: {len(str(note_content))}, date: '{date_value}'")
            
            # Check if search term matches in any field
            if (not search_term or 
                search_term in str(title).lower() or
                search_term in str(folder).lower() or
                search_term in str(note_content).lower()):
                
                # Convert date for display
                date_display = self.convert_timestamp(date_value) if date_value else "Unknown Date"
                
                # Create snippet from note content
                snippet = str(note_content)[:100] + "..." if len(str(note_content)) > 100 else str(note_content)
                
                values = (
                    date_display,
                    title,
                    folder,
                    snippet
                )
                
                print(f"DEBUG: Adding note {i} to tree with values: {values}")
                self.notes_tree.insert("", "end", text=i, values=values)
        
        # Check how many items were added
        tree_children = self.notes_tree.get_children()
        print(f"DEBUG: Added {len(tree_children)} notes to the tree")


    def filter_safari_results(self, search_term):
        """Filter Safari history results based on search term"""
        # Clear the tree
        for item in self.safari_tree.get_children():
            self.safari_tree.delete(item)
        
        # If we have Safari history data
        if hasattr(self, 'safari_data') and self.safari_data:
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
        """Open Safari URL in browser when double-clicked"""
        try:
            import webbrowser
            
            selection = self.safari_tree.selection()
            if selection:
                item = self.safari_tree.item(selection[0])
                values = item['values']
                if len(values) > 2:
                    url = values[2]  # URL is in the 3rd column
                    if url and url.startswith(('http://', 'https://')):
                        webbrowser.open(url)
        except Exception as e:
            print(f"Error opening URL: {e}")
    
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
    
    def filter_photos_results(self, search_term):
        """Filter photos results"""
        # Clear the tree
        for item in self.photos_tree.get_children():
            self.photos_tree.delete(item)
        
        if hasattr(self, 'photos_data') and self.photos_data:
            search_term = search_term.lower()
            filtered_count = 0
            
            for i, photo in enumerate(self.photos_data):
                # Check if search term matches in any field
                if (not search_term or 
                    search_term in str(photo.get('Filename', '')).lower() or
                    search_term in str(photo.get('Path', '')).lower() or
                    search_term in str(photo.get('Scene Classification', '')).lower()):
                    
                    date_taken_display = self.convert_timestamp(photo.get('Date Taken', ''))
                    
                    values = (
                        photo.get('Filename', ''),
                        photo.get('Path', ''),
                        date_taken_display,
                        photo.get('Scene Classification', ''),
                        photo.get('Confidence', '')
                    )
                    
                    self.photos_tree.insert("", "end", text=str(i), values=values)
                    filtered_count += 1
            
            # Update photos count
            if hasattr(self, 'photos_count'):
                self.photos_count.configure(text=f"{filtered_count} photos")
        else:
            # Update photos count to 0
            if hasattr(self, 'photos_count'):
                self.photos_count.configure(text="0 photos")

    def update_notes_display(self, event):
        """Update the notes display with the selected note content"""
        print("DEBUG: update_notes_display called")
        
        if not hasattr(self, 'notes_tree') or not hasattr(self, 'notes_display'):
            print("DEBUG: Missing notes_tree or notes_display")
            return
            
        selected_items = self.notes_tree.selection()
        if selected_items:
            item = selected_items[0]
            item_id = self.notes_tree.item(item, "text")
            
            print(f"DEBUG: Selected note item_id: {item_id}")
            
            # Get the note content
            if hasattr(self, 'notes_data') and self.notes_data and int(item_id) < len(self.notes_data):
                note = self.notes_data[int(item_id)]
                
                print(f"DEBUG: Displaying note: {note}")
                
                # Clear the text box
                self.notes_display.delete("1.0", "end")
                
                # Get note details with correct field names
                title = (note.get('Title') or note.get('title') or 'Untitled')
                
                # Try correct date fields
                creation_date = (note.get('Creation Date') or note.get('creation_date') or '')
                modification_date = (note.get('Modification Date') or note.get('modification_date') or '')
                
                # Try correct content field
                content = (note.get('Data') or note.get('data') or note.get('ZCONTENT') or '')
                
                # Format the note with proper headers and spacing
                display_text = f"TITLE: {title}\n"
                
                if creation_date:
                    display_text += f"CREATED: {self.convert_timestamp(creation_date)}\n"
                if modification_date and modification_date != creation_date:
                    display_text += f"MODIFIED: {self.convert_timestamp(modification_date)}\n"
                    
                display_text += "\n" + "="*50 + "\n"
                display_text += "CONTENT:\n"
                display_text += "="*50 + "\n\n"
                
                if content:
                    # Clean up content and format nicely
                    content = str(content).strip()
                    if content:
                        display_text += content
                    else:
                        display_text += "[Empty note]"
                else:
                    display_text += "[No content available]"
                
                self.notes_display.insert("1.0", display_text)
                print("DEBUG: Note display updated successfully")
            else:
                # Clear display if no valid note selected
                self.notes_display.delete("1.0", "end")
                self.notes_display.insert("1.0", "Select a note to view its content...")
                print("DEBUG: Cleared display - no valid note selected")
        else:
            # Clear display if no selection
            self.notes_display.delete("1.0", "end")
            self.notes_display.insert("1.0", "Select a note to view its content...")
            print("DEBUG: Cleared display - no selection")

    # iOS App Management Methods
    def update_ios_apps_display(self):
        """Update the iOS apps list display with filtering and sorting"""
        if not hasattr(self, 'ios_apps_data') or not self.ios_apps_data:
            return
            
        # Get current search term
        search_term = ""
        if hasattr(self, 'ios_apps_search_entry'):
            search_term = self.ios_apps_search_entry.get().lower()
            
        # Get current sort option
        sort_option = "Alphabetical"
        if hasattr(self, 'ios_apps_sort_var'):
            sort_option = self.ios_apps_sort_var.get()
            
        # Filter apps based on search term
        filtered_apps = []
        for app in self.ios_apps_data:
            if search_term == "" or search_term in app.lower():
                filtered_apps.append(app)
                
        # Sort apps based on selected option
        if sort_option == "Alphabetical":
            filtered_apps.sort()
        elif sort_option == "Reverse Alphabetical":
            filtered_apps.sort(reverse=True)
        elif sort_option == "By Length":
            filtered_apps.sort(key=len)
            
        # Update the display
        self.ios_apps_list.delete("1.0", "end")
        if filtered_apps:
            for app in filtered_apps:
                self.ios_apps_list.insert("end", f"{app}\n")
        else:
            self.ios_apps_list.insert("1.0", "No matching apps found...")
            
        # Update count
        self.ios_apps_count.configure(text=f"{len(filtered_apps)} apps")
        
    def on_ios_apps_search(self, event=None):
        """Handle iOS apps search entry changes"""
        self.update_ios_apps_display()
        
    def clear_ios_apps_search(self):
        """Clear the iOS apps search entry"""
        if hasattr(self, 'ios_apps_search_entry'):
            self.ios_apps_search_entry.delete(0, "end")
            self.update_ios_apps_display()
            
    def on_ios_apps_sort_change(self, value):
        """Handle iOS apps sort option changes"""
        self.update_ios_apps_display()
        
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
            self.after(200, load_visible_thumbnails)  # Increased delay for better initialization
            
            # For small collections, also trigger a more aggressive initial load
            if len(photo_files) <= 50:
                self.after(500, lambda: load_visible_thumbnails())  # Second trigger for small collections
        
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
            
            # Apply scroll using the CustomTkinter scrollable frame's method
            try:
                # Get the current scroll position
                current_top, current_bottom = scroll_frame._parent_canvas.yview()
                
                # Calculate new position (this is safer for CustomTkinter)
                scroll_fraction = scroll_amount / 1000.0  # Convert to fraction
                new_top = max(0, min(1, current_top + scroll_fraction))
                scroll_frame._parent_canvas.yview_moveto(new_top)
            except:
                # Fallback to standard scrolling if the above fails
                try:
                    scroll_frame._parent_canvas.yview_scroll(scroll_amount, "units")
                except:
                    pass
            
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
                buffer_rows = 3  # Increase buffer to load more thumbnails ahead of viewport
                
                # Calculate row range
                start_row = max(0, int(view_start * total_height / row_height) - buffer_rows)
                end_row = min(len(photo_files) // current_columns + 1, 
                            int(view_end * total_height / row_height) + buffer_rows)
                
                # Calculate visible thumbnail indices
                visible_start = start_row * current_columns
                visible_end = min(len(photo_files), end_row * current_columns)
                
                # Debug information
                print(f"DEBUG: Loading thumbnails {visible_start}-{visible_end} of {len(photo_files)} total")
                print(f"DEBUG: Viewport: {view_start:.3f}-{view_end:.3f}, Rows: {start_row}-{end_row}")
                
                # Queue loading only for thumbnails that aren't already loaded or loading
                batch_size = 10  # Increase batch size for better loading performance
                batch_count = 0
                
                for idx in range(visible_start, visible_end):
                    if idx not in self.loaded_thumbnails and idx < len(photo_files):
                        filename = photo_files[idx]
                        self.loaded_thumbnails[idx] = "loading"
                        
                        # Reduce delay between batches for faster loading
                        batch_delay = (batch_count // batch_size) * 50  # Reduced from 100ms to 50ms
                        self.after(batch_delay, lambda i=idx, f=filename: 
                                self.executor.submit(load_thumbnail, i, f))
                        batch_count += 1
                        
                # If we loaded thumbnails, update status
                if batch_count > 0:
                    status_label.configure(text=f"Loading {batch_count} thumbnails...")
                    print(f"DEBUG: Queued {batch_count} thumbnails for loading")
                    
            except Exception as e:
                print(f"Error in load_visible_thumbnails: {e}")
                import traceback
                traceback.print_exc()
        
        # Simple direct binding for better performance
        def bind_scroll_events():
            """Apply scroll bindings based on platform"""
            system = platform.system()
            
            if system in ['Darwin', 'Windows']:
                # Use regular bind for CustomTkinter compatibility
                scroll_frame.bind("<MouseWheel>", _on_mousewheel)
                gallery_frame.bind("<MouseWheel>", _on_mousewheel)
                self.photo_thumbnails_tab.bind("<MouseWheel>", _on_mousewheel)
            elif system == 'Linux':
                scroll_frame.bind("<Button-4>", _on_mousewheel)
                scroll_frame.bind("<Button-5>", _on_mousewheel)
                gallery_frame.bind("<Button-4>", _on_mousewheel)
                gallery_frame.bind("<Button-5>", _on_mousewheel)
                self.photo_thumbnails_tab.bind("<Button-4>", _on_mousewheel)
                self.photo_thumbnails_tab.bind("<Button-5>", _on_mousewheel)
        
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
        
        # Function to load all thumbnails (useful for smaller collections)
        def load_all_thumbnails():
            """Force load all thumbnails - useful for collections under 100 images"""
            if len(photo_files) <= 100:  # Only for manageable collections
                print(f"Loading all {len(photo_files)} thumbnails...")
                status_label.configure(text=f"Loading all {len(photo_files)} thumbnails...")
                
                for idx, filename in enumerate(photo_files):
                    if idx not in self.loaded_thumbnails:
                        self.loaded_thumbnails[idx] = "loading"
                        # Stagger loading to prevent overwhelming the UI
                        delay = (idx // 5) * 25  # Load 5 thumbnails every 25ms
                        self.after(delay, lambda i=idx, f=filename: 
                                self.executor.submit(load_thumbnail, i, f))
        
        # Add "Load All" button for convenience
        if len(photo_files) <= 100:
            load_all_btn = ctk.CTkButton(
                status_frame,
                text=f"Load All {len(photo_files)} Thumbnails",
                command=load_all_thumbnails,
                width=200
            )
            load_all_btn.pack(side="right", padx=10)
        
        # Handle resize with debouncing
        def on_resize(event=None):
            """Handle window resize events with debouncing"""
            if hasattr(self, '_resize_timer') and self._resize_timer:
                self.after_cancel(self._resize_timer)
            self._resize_timer = self.after(300, create_thumbnail_grid)
        
        # Bind resize events
        scroll_frame.bind("<Configure>", on_resize)
        self.photo_thumbnails_tab.bind("<Configure>", on_resize)


    def create_heic_thumbnail(self, heic_path, size=(150, 150)):
        """Generate thumbnail from HEIC file"""
        try:
            # Import PIL Image at the top level
            from PIL import Image
            
            # Try to use pillow-heif if available
            try:
                from pillow_heif import register_heif_opener
                register_heif_opener()
                img = Image.open(heic_path)
                img.thumbnail(size)
                return img
            except ImportError:
                pass
            
            # Fallback to pyheif
            import pyheif
            
            # Read HEIC file
            heif_file = pyheif.read(heic_path)
            
            # Convert to PIL Image
            img = Image.frombytes(
                heif_file.mode,
                heif_file.size,
                heif_file.data,
                "raw",
                heif_file.mode,
                heif_file.stride,
            )
            img.thumbnail(size)
            return img
            
        except ImportError:
            # Fallback if no HEIC libraries are available
            return self.create_generic_thumbnail("HEIC", size)
        except Exception as e:
            # Fallback for any other errors
            print(f"Error opening HEIC file: {e}")
            return self.create_generic_thumbnail("HEIC", size)

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
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        position = ((size[0] - text_width) // 2, (size[1] - text_height) // 2)
        
        # Draw text in white
        draw.text(position, text, fill=(255, 255, 255), font=font)
        
        return img
    
    def open_heic_image(self, heic_path):
        """Open HEIC image file and convert to PIL Image"""
        try:
            # Import PIL Image at the top level
            from PIL import Image
            
            # First try pillow-heif if available
            try:
                from pillow_heif import register_heif_opener
                register_heif_opener()
                return Image.open(heic_path)
            except ImportError:
                pass
            
            # Fallback to pyheif
            import pyheif
            
            # Read HEIC file
            heif_file = pyheif.read(heic_path)
            
            # Convert to PIL Image
            image = Image.frombytes(
                heif_file.mode,
                heif_file.size,
                heif_file.data,
                "raw",
                heif_file.mode,
                heif_file.stride,
            )
            
            return image
            
        except ImportError:
            # If no HEIC libraries are available, create placeholder
            return self.create_generic_thumbnail("HEIC File\n(No HEIC support)", (400, 300))
        except Exception as e:
            print(f"Error opening HEIC file: {e}")
            return self.create_generic_thumbnail("HEIC Error", (400, 300))
    
    def show_media_file(self, path):
        """Handle opening of image or video files"""
        import subprocess
        import platform
        
        file_ext = os.path.splitext(path.lower())[1]
        
        if file_ext in ['.mp4', '.mov', '.m4v', '.3gp']:
            # For videos, use system default player    
            try:
                if platform.system() == 'Darwin':  # macOS
                    subprocess.run(['open', path], creationflags=SUBPROCESS_FLAGS)
                elif platform.system() == 'Windows':
                    os.startfile(path)
                else:  # Linux
                    subprocess.run(['xdg-open', path], creationflags=SUBPROCESS_FLAGS)
            except Exception as e:
                messagebox.showerror("Error", f"Could not open video file: {str(e)}")
        else:
            # For images, use the image viewer
            self.show_full_image(path)
    
     

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
            if image_path.lower().endswith(('.heic', '.heif')):
                # Handle HEIC files specially
                img = self.open_heic_image(image_path)
            else:
                # Handle standard image formats
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
                    
                    # Check for GPS coordinates in the enhanced HEIC EXIF data
                    lat_value = None
                    lon_value = None
                    
                    # Look for the decimal GPS coordinates from our enhanced extraction
                    if 'GPS Latitude Decimal' in exif_data and 'GPS Longitude Decimal' in exif_data:
                        try:
                            lat_value = float(exif_data['GPS Latitude Decimal'])
                            lon_value = float(exif_data['GPS Longitude Decimal'])
                            print(f"Found GPS coordinates in HEIC: {lat_value}, {lon_value}")
                            has_gps_coords = True
                        except (ValueError, TypeError) as e:
                            print(f"Error parsing GPS decimal coordinates: {e}")
                            lat_value = None
                            lon_value = None
                    
                    # If we have GPS coordinates, create the map buttons
                    if lat_value is not None and lon_value is not None:
                        # Pack the map buttons frame
                        map_buttons_frame.pack(fill="x", padx=10, pady=(0, 10))
                        
                        # Add a label for the map section
                        map_label = ctk.CTkLabel(
                            map_buttons_frame, 
                            text="📍 View Location on Maps",
                            font=("Arial", 12, "bold")
                        )
                        map_label.pack(pady=(5, 5))
                        
                        # Create URLs
                        google_maps_url = f"https://maps.google.com/?q={lat_value:.6f},{lon_value:.6f}"
                        apple_maps_url = f"https://maps.apple.com/?ll={lat_value:.6f},{lon_value:.6f}&z=15"
                        
                        # Google Maps button with icon
                        google_maps_btn = ctk.CTkButton(
                            map_buttons_frame, 
                            text="Open in Google Maps",
                            command=lambda url=google_maps_url: webbrowser.open_new_tab(url),
                            fg_color="#4285f4",  # Google blue
                            hover_color="#3367d6"
                        )
                        google_maps_btn.pack(pady=(2, 2), fill="x")
                        
                        # Apple Maps button with icon
                        apple_maps_btn = ctk.CTkButton(
                            map_buttons_frame, 
                            text="Open in Apple Maps",
                            command=lambda url=apple_maps_url: webbrowser.open_new_tab(url),
                            fg_color="#007aff",  # Apple blue
                            hover_color="#0056b3"
                        )
                        apple_maps_btn.pack(pady=(2, 2), fill="x")
                        
                        # Coordinates display button (non-clickable info)
                        coords_display = ctk.CTkLabel(
                            map_buttons_frame, 
                            text=f"📍 {lat_value:.6f}°, {lon_value:.6f}°",
                            font=("Arial", 10),
                            text_color="gray"
                        )
                        coords_display.pack(pady=(2, 5))
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
                            # Pack the map buttons frame
                            map_buttons_frame.pack(fill="x", padx=10, pady=(0, 10))
                            
                            # Add a label for the map section
                            map_label = ctk.CTkLabel(
                                map_buttons_frame, 
                                text="📍 View Location on Maps",
                                font=("Arial", 12, "bold")
                            )
                            map_label.pack(pady=(5, 5))
                            
                            # Create URLs
                            google_maps_url = f"https://maps.google.com/?q={lat_value:.6f},{lon_value:.6f}"
                            apple_maps_url = f"https://maps.apple.com/?ll={lat_value:.6f},{lon_value:.6f}&z=15"
                            
                            # Google Maps button with icon
                            google_maps_btn = ctk.CTkButton(
                                map_buttons_frame, 
                                text="🌍 Open in Google Maps",
                                command=lambda url=google_maps_url: webbrowser.open_new_tab(url),
                                fg_color="#4285f4",  # Google blue
                                hover_color="#3367d6"
                            )
                            google_maps_btn.pack(pady=(2, 2), fill="x")
                            
                            # Apple Maps button with icon
                            apple_maps_btn = ctk.CTkButton(
                                map_buttons_frame, 
                                text="🍎 Open in Apple Maps",
                                command=lambda url=apple_maps_url: webbrowser.open_new_tab(url),
                                fg_color="#007aff",  # Apple blue
                                hover_color="#0056b3"
                            )
                            apple_maps_btn.pack(pady=(2, 2), fill="x")
                            
                            # Coordinates display
                            coords_display = ctk.CTkLabel(
                                map_buttons_frame, 
                                text=f"📍 {lat_value:.6f}°, {lon_value:.6f}°",
                                font=("Arial", 10),
                                text_color="gray"
                            )
                            coords_display.pack(pady=(2, 5))
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
     
    
    
    def extract_image_exif(self, image_path):
        """Extract EXIF data from image"""
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS
            
            exif_data = {}
            img = Image.open(image_path)
            
            if hasattr(img, '_getexif'):
                exif_info = img._getexif()
                if exif_info:
                    for tag, value in exif_info.items():
                        decoded = TAGS.get(tag, tag)
                        exif_data[decoded] = value
            
            return exif_data
        except Exception as e:
            return {"Error": f"Failed to extract EXIF: {str(e)}"}
    
    def format_exif_for_display(self, exif_data):
        """Format EXIF data for display"""
        if not exif_data:
            return "No EXIF data available."
        
        formatted = ""
        for key, value in exif_data.items():
            # Handle special cases for better readability
            if isinstance(value, bytes):
                try:
                    value = value.decode('utf-8', errors='ignore')
                except:
                    value = str(value)
            elif hasattr(value, 'numerator') and hasattr(value, 'denominator'):
                # Handle rational numbers
                if value.denominator != 0:
                    value = f"{value.numerator}/{value.denominator}"
                else:
                    value = str(value.numerator)
            
            formatted += f"{key}: {value}\n"
        
        return formatted

    def convert_gps_coordinate(self, coord_list):
        """Convert GPS coordinates from degrees/minutes/seconds to decimal degrees"""
        try:
            if isinstance(coord_list, (list, tuple)) and len(coord_list) >= 3:
                # Standard GPS format: [degrees, minutes, seconds]
                degrees = float(coord_list[0])
                minutes = float(coord_list[1]) 
                seconds = float(coord_list[2])
                return degrees + (minutes / 60.0) + (seconds / 3600.0)
            elif isinstance(coord_list, (list, tuple)) and len(coord_list) == 1:
                # Single value (like altitude)
                return float(coord_list[0])
            elif hasattr(coord_list, 'numerator') and hasattr(coord_list, 'denominator'):
                # Handle PIL rational number
                if coord_list.denominator != 0:
                    return float(coord_list.numerator) / float(coord_list.denominator)
                else:
                    return float(coord_list.numerator)
            else:
                # Try direct conversion
                return float(coord_list)
        except (ValueError, TypeError, IndexError) as e:
            print(f"Error converting GPS coordinates: {e}, value: {coord_list}")
            return 0.0

    def convert_to_degrees(self, value):
        """Convert GPS coordinates from degrees/minutes/seconds to decimal degrees"""
        try:
            if isinstance(value, (list, tuple)) and len(value) >= 3:
                # Handle list or tuple input like [degrees, minutes, seconds]
                degrees = float(value[0])
                minutes = float(value[1])
                seconds = float(value[2])
                return degrees + (minutes / 60.0) + (seconds / 3600.0)
            elif isinstance(value, str):
                # Handle string input - try to parse as list first
                if value.startswith('[') and value.endswith(']'):
                    # Remove brackets and split
                    value = value[1:-1]
                    parts = [float(x.strip()) for x in value.split(',')]
                    if len(parts) >= 3:
                        return parts[0] + (parts[1] / 60.0) + (parts[2] / 3600.0)
                # If not list format, try to convert directly
                return float(value)
            elif hasattr(value, '__len__') and len(value) >= 3:
                # Handle other iterable types
                return float(value[0]) + (float(value[1]) / 60.0) + (float(value[2]) / 3600.0)
            else:
                # Handle single value
                return float(value)
        except (ValueError, TypeError, IndexError) as e:
            print(f"Error converting GPS coordinates: {e}, value: {value}")
            return 0.0

    def extract_heic_exif(self, image_path):
        """Extract comprehensive EXIF data from HEIC files including GPS location"""
        try:
            # Import PIL Image at the top level
            from PIL import Image
            from PIL.ExifTags import TAGS, GPSTAGS
            import os
            from datetime import datetime
            
            # First try pillow-heif if available
            try:
                from pillow_heif import register_heif_opener
                register_heif_opener()
                
                # Use PIL to open HEIC with pillow-heif support
                img = Image.open(image_path)
                
                # Get basic file info
                file_size = os.path.getsize(image_path)
                file_modified = datetime.fromtimestamp(os.path.getmtime(image_path)).strftime('%Y-%m-%d %H:%M:%S')
                
                exif_data = {
                    'File Type': 'HEIC',
                    'File Name': os.path.basename(image_path),
                    'File Size': f"{file_size:,} bytes ({file_size / (1024*1024):.2f} MB)",
                    'File Modified': file_modified,
                    'Image Width': img.width,
                    'Image Height': img.height,
                    'Color Mode': img.mode,
                    'Image Resolution': f"{img.width} x {img.height}",
                }
                
                # Extract comprehensive EXIF data
                exif_dict = img.getexif()
                if exif_dict:
                    print(f"DEBUG: Found EXIF data with {len(exif_dict)} entries")
                    
                    # Process each EXIF tag
                    for tag_id, value in exif_dict.items():
                        tag_name = TAGS.get(tag_id, f"Tag_{tag_id}")
                        
                        # Special handling for different data types
                        if isinstance(value, bytes):
                            try:
                                # Try to decode as UTF-8
                                value = value.decode('utf-8').strip('\x00')
                            except:
                                # If that fails, represent as hex
                                value = value.hex()[:100] + ('...' if len(value) > 50 else '')
                        elif isinstance(value, tuple) and len(value) == 2:
                            # Handle rational numbers (fractions)
                            if value[1] != 0:
                                value = f"{value[0]}/{value[1]} ({value[0]/value[1]:.3f})"
                            else:
                                value = f"{value[0]}/0"
                        
                        # Add meaningful tag names and format values
                        if tag_name in ['DateTime', 'DateTimeOriginal', 'DateTimeDigitized']:
                            try:
                                # Format datetime values
                                if isinstance(value, str) and ':' in value:
                                    dt = datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
                                    exif_data[f"{tag_name}"] = dt.strftime('%Y-%m-%d %H:%M:%S')
                                else:
                                    exif_data[tag_name] = str(value)
                            except:
                                exif_data[tag_name] = str(value)
                        elif tag_name == 'Orientation':
                            orientation_map = {
                                1: "Normal", 2: "Mirrored horizontal", 3: "Rotated 180°",
                                4: "Mirrored vertical", 5: "Mirrored horizontal, rotated 270°",
                                6: "Rotated 90°", 7: "Mirrored horizontal, rotated 90°", 8: "Rotated 270°"
                            }
                            exif_data[tag_name] = f"{value} ({orientation_map.get(value, 'Unknown')})"
                        elif tag_name in ['XResolution', 'YResolution']:
                            exif_data[tag_name] = f"{value} DPI"
                        elif tag_name == 'Flash':
                            # Decode flash settings
                            flash_map = {0: "No Flash", 1: "Flash Fired", 5: "Flash Fired, Return not detected", 
                                       7: "Flash Fired, Return detected", 9: "Flash Fired, Compulsory", 
                                       13: "Flash Fired, Compulsory, Return not detected", 
                                       15: "Flash Fired, Compulsory, Return detected", 16: "No Flash, Compulsory",
                                       24: "No Flash, Auto", 25: "Flash Fired, Auto", 29: "Flash Fired, Auto, Return not detected",
                                       31: "Flash Fired, Auto, Return detected", 32: "No flash function", 
                                       65: "Flash Fired, Red-eye reduction", 69: "Flash Fired, Red-eye reduction, Return not detected",
                                       71: "Flash Fired, Red-eye reduction, Return detected", 73: "Flash Fired, Compulsory, Red-eye reduction",
                                       77: "Flash Fired, Compulsory, Red-eye reduction, Return not detected",
                                       79: "Flash Fired, Compulsory, Red-eye reduction, Return detected",
                                       89: "Flash Fired, Auto, Red-eye reduction", 93: "Flash Fired, Auto, Red-eye reduction, Return not detected",
                                       95: "Flash Fired, Auto, Red-eye reduction, Return detected"}
                            exif_data[tag_name] = f"{value} ({flash_map.get(value, 'Unknown')})"
                        elif tag_name in ['FocalLength', 'FocalLengthIn35mmFilm']:
                            if isinstance(value, str) and '/' in value:
                                try:
                                    num, den = map(float, value.split('/'))
                                    exif_data[tag_name] = f"{num/den:.1f}mm"
                                except:
                                    exif_data[tag_name] = str(value)
                            else:
                                exif_data[tag_name] = f"{value}mm"
                        elif tag_name in ['ExposureTime', 'ShutterSpeedValue']:
                            if isinstance(value, str) and '/' in value:
                                exif_data[tag_name] = f"{value} sec"
                            else:
                                exif_data[tag_name] = f"{value} sec"
                        elif tag_name in ['FNumber', 'ApertureValue']:
                            if isinstance(value, str) and '/' in value:
                                try:
                                    num, den = map(float, value.split('/'))
                                    exif_data[tag_name] = f"f/{num/den:.1f}"
                                except:
                                    exif_data[tag_name] = str(value)
                            else:
                                exif_data[tag_name] = f"f/{value}"
                        elif tag_name == 'ISOSpeedRatings':
                            exif_data['ISO'] = f"ISO {value}"
                        else:
                            exif_data[tag_name] = str(value)
                    
                    # Extract GPS data if present
                    gps_data = exif_dict.get_ifd(0x8825)  # GPS IFD
                    if gps_data:
                        print(f"DEBUG: Found GPS data with {len(gps_data)} entries")
                        gps_info = {}
                        
                        for gps_tag_id, gps_value in gps_data.items():
                            gps_tag_name = GPSTAGS.get(gps_tag_id, f"GPS_Tag_{gps_tag_id}")
                            gps_info[gps_tag_name] = gps_value
                        
                        # Parse GPS coordinates
                        if 'GPSLatitude' in gps_info and 'GPSLatitudeRef' in gps_info:
                            lat_degrees = self.convert_gps_coordinate(gps_info['GPSLatitude'])
                            if gps_info['GPSLatitudeRef'] == 'S':
                                lat_degrees = -lat_degrees
                            exif_data['GPS Latitude'] = f"{lat_degrees:.6f}° {gps_info['GPSLatitudeRef']}"
                            exif_data['GPS Latitude Decimal'] = lat_degrees
                        
                        if 'GPSLongitude' in gps_info and 'GPSLongitudeRef' in gps_info:
                            lon_degrees = self.convert_gps_coordinate(gps_info['GPSLongitude'])
                            if gps_info['GPSLongitudeRef'] == 'W':
                                lon_degrees = -lon_degrees
                            exif_data['GPS Longitude'] = f"{lon_degrees:.6f}° {gps_info['GPSLongitudeRef']}"
                            exif_data['GPS Longitude Decimal'] = lon_degrees
                        
                        # Create Google Maps link if we have coordinates
                        if 'GPS Latitude Decimal' in exif_data and 'GPS Longitude Decimal' in exif_data:
                            lat = exif_data['GPS Latitude Decimal']
                            lon = exif_data['GPS Longitude Decimal']
                            exif_data['Google Maps Link'] = f"https://maps.google.com/?q={lat},{lon}"
                        
                        # GPS altitude
                        if 'GPSAltitude' in gps_info:
                            altitude = self.convert_gps_coordinate([gps_info['GPSAltitude']])
                            altitude_ref = gps_info.get('GPSAltitudeRef', 0)
                            if altitude_ref == 1:
                                altitude = -altitude
                            exif_data['GPS Altitude'] = f"{altitude:.1f}m {'below' if altitude < 0 else 'above'} sea level"
                        
                        # GPS timestamp
                        if 'GPSTimeStamp' in gps_info and 'GPSDateStamp' in gps_info:
                            try:
                                gps_time = gps_info['GPSTimeStamp']
                                gps_date = gps_info['GPSDateStamp']
                                if isinstance(gps_time, (list, tuple)) and len(gps_time) == 3:
                                    hours = int(gps_time[0])
                                    minutes = int(gps_time[1])
                                    seconds = int(gps_time[2])
                                    exif_data['GPS Timestamp'] = f"{gps_date} {hours:02d}:{minutes:02d}:{seconds:02d} UTC"
                            except:
                                pass
                        
                        # GPS speed and direction
                        if 'GPSSpeed' in gps_info:
                            speed = float(gps_info['GPSSpeed'])
                            speed_ref = gps_info.get('GPSSpeedRef', 'K')  # K=km/h, M=mph, N=knots
                            unit_map = {'K': 'km/h', 'M': 'mph', 'N': 'knots'}
                            exif_data['GPS Speed'] = f"{speed:.1f} {unit_map.get(speed_ref, speed_ref)}"
                        
                        if 'GPSImgDirection' in gps_info:
                            direction = float(gps_info['GPSImgDirection'])
                            direction_ref = gps_info.get('GPSImgDirectionRef', 'T')  # T=True North, M=Magnetic North
                            compass_directions = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
                            compass_idx = int((direction + 11.25) / 22.5) % 16
                            exif_data['GPS Direction'] = f"{direction:.1f}° ({compass_directions[compass_idx]}, {direction_ref})"
                else:
                    print("DEBUG: No EXIF data found in HEIC file")
                
                return exif_data
                
            except ImportError:
                print("DEBUG: pillow-heif not available, trying pyheif")
                pass
            
            # Fallback to pyheif with enhanced metadata extraction
            import pyheif
            
            # Read HEIC file
            heif_file = pyheif.read(image_path)
            
            # Get basic file info
            file_size = os.path.getsize(image_path)
            file_modified = datetime.fromtimestamp(os.path.getmtime(image_path)).strftime('%Y-%m-%d %H:%M:%S')
            
            exif_data = {
                'File Type': 'HEIC',
                'File Name': os.path.basename(image_path),
                'File Size': f"{file_size:,} bytes ({file_size / (1024*1024):.2f} MB)",
                'File Modified': file_modified,
                'Image Width': heif_file.size[0],
                'Image Height': heif_file.size[1],
                'Color Mode': heif_file.mode,
                'Image Resolution': f"{heif_file.size[0]} x {heif_file.size[1]}",
            }
            
            # Extract metadata from HEIC using pyheif
            if heif_file.metadata:
                print(f"DEBUG: Found {len(heif_file.metadata)} metadata blocks in HEIC")
                
                for metadata in heif_file.metadata:
                    if metadata['type'] == 'Exif':
                        try:
                            # Use exifread library for better EXIF parsing if available
                            try:
                                import exifread
                                from io import BytesIO
                                
                                # Create a BytesIO object from the EXIF data
                                exif_stream = BytesIO(metadata['data'])
                                
                                # Parse EXIF data
                                tags = exifread.process_file(exif_stream, details=True)
                                
                                for tag_name, tag_value in tags.items():
                                    if tag_name.startswith('GPS'):
                                        # Handle GPS tags specially
                                        exif_data[tag_name.replace('GPS GPS', 'GPS')] = str(tag_value)
                                    elif tag_name not in ['JPEGThumbnail', 'TIFFThumbnail', 'Filename', 'EXIF MakerNote']:
                                        # Skip binary thumbnail data and other non-useful fields
                                        value_str = str(tag_value)
                                        if len(value_str) < 200:  # Avoid very long values
                                            exif_data[tag_name.replace('EXIF ', '').replace('Image ', '')] = value_str
                                
                                print(f"DEBUG: Extracted {len([k for k in exif_data.keys() if 'GPS' in k])} GPS-related fields")
                                
                            except ImportError:
                                print("DEBUG: exifread not available, using basic parsing")
                                # Basic EXIF parsing without exifread
                                exif_data['EXIF Data Found'] = f"Yes ({len(metadata['data'])} bytes)"
                                
                        except Exception as parse_error:
                            print(f"Error parsing HEIC EXIF data: {parse_error}")
                            exif_data['EXIF Parse Error'] = str(parse_error)
            else:
                print("DEBUG: No metadata found in HEIC file")
                        
            return exif_data
            
        except ImportError as ie:
            print(f"DEBUG: Import error in extract_heic_exif: {ie}")
            return {
                'Error': 'HEIC libraries not available. Install with: pip install pillow-heif pyheif exifread',
                'File Type': 'HEIC',
                'File Size': f"{os.path.getsize(image_path)} bytes" if os.path.exists(image_path) else 'Unknown'
            }
        except Exception as e:
            print(f"DEBUG: Error in extract_heic_exif: {e}")
            import traceback
            traceback.print_exc()
            return {
                'Error': f"Failed to extract HEIC EXIF: {str(e)}",
                'File Type': 'HEIC',
                'File Size': f"{os.path.getsize(image_path)} bytes" if os.path.exists(image_path) else 'Unknown'
            }

if __name__ == "__main__":
    app = UnifiedArsenicApp()
    app.mainloop()