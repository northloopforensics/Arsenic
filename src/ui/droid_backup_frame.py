import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import customtkinter as ctk
import threading
import logging
from datetime import datetime
import subprocess
import json
import math  # For file size formatting
import io
from contextlib import redirect_stdout
import platform

# Windows-specific subprocess flag to prevent console windows
if sys.platform == "win32":
    SUBPROCESS_FLAGS = subprocess.CREATE_NO_WINDOW
else:
    SUBPROCESS_FLAGS = 0

# Add project root to path to import the collector
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.Droid_backup.android_backup_collector import ArsenicTriageCollector
from src.parser.AB_parser import BackupExtractor, ForensicDataParser
from src.utils.backup_analyzer import AndroidBackupAnalyzer

class ConsoleCapture:
    """Captures print output and redirects to GUI console"""
    def __init__(self, append_func):
        self.append_func = append_func
        self.terminal = sys.stdout
        
    def write(self, message):
        # Write to terminal (for debugging)
        if self.terminal:
            self.terminal.write(message)
        # Send to GUI console if it's not just a newline and append_func is valid
        if message.strip() and self.append_func:
            try:
                self.append_func(message.strip())
            except Exception as e:
                # Fallback to terminal if GUI append fails
                if self.terminal:
                    self.terminal.write(f"[GUI Error: {e}] {message}")
    
    def flush(self):
        if self.terminal:
            self.terminal.flush()

class DroidBackupFrame(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.collector = None
        self.device_connected = False
        self.monitoring_thread = None
        self.stop_monitoring = False
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.timeout_var = tk.StringVar(value="10")
        self.create_widgets()
        # Removed extra status/progress textbox creation
        self.check_device_status()

    def get_adb_command(self):
        """Get the correct ADB command for the current platform"""
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        
        local_adb = os.path.join(project_root, "src", "utils", "adb")
        local_adb_exe = os.path.join(project_root, "src", "utils", "adb.exe")
        
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
        
        # Test each command and return the first working one
        for adb_cmd in adb_commands:
            try:
                result = subprocess.run([adb_cmd, 'version'], 
                                    capture_output=True, text=True, timeout=5, 
                                    creationflags=SUBPROCESS_FLAGS)
                if result.returncode == 0:
                    print(f"DEBUG: Found working ADB: {adb_cmd}")
                    return adb_cmd
            except (FileNotFoundError, subprocess.TimeoutExpired):
                print(f"DEBUG: ADB command failed: {adb_cmd}")
                continue
        
        print("DEBUG: No working ADB command found")
        return 'adb'  # Fallback to system ADB

    def create_collector(self, output_dir=None):
        """Create a properly configured ArsenicTriageCollector with the correct ADB command"""
        working_adb = self.get_adb_command()
        if output_dir:
            return ArsenicTriageCollector(output_dir=output_dir, adb_command=working_adb)
        else:
            return ArsenicTriageCollector(adb_command=working_adb)

    def create_widgets(self):
        # Device status frame at the top
        status_frame = ctk.CTkFrame(self)
        status_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        
        status_title = ctk.CTkLabel(status_frame, text="Device Status:", font=ctk.CTkFont(size=14, weight="bold"))
        status_title.pack(side="left", padx=10, pady=5)
        
        self.status_indicator = ctk.CTkLabel(status_frame, text="🟡", font=ctk.CTkFont(size=16))
        self.status_indicator.pack(side="left", padx=5)
        
        self.status_label = ctk.CTkLabel(status_frame, text="Checking...", font=ctk.CTkFont(size=12))
        self.status_label.pack(side="left", padx=5)
        
        # Manual refresh button
        refresh_button = ctk.CTkButton(status_frame, text="🔄 Refresh", command=self.manual_refresh_device, width=80)
        refresh_button.pack(side="right", padx=10, pady=5)
        
        # Main content frame with tabs
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)

        # Create tabview for different collection methods
        self.tabview = ctk.CTkTabview(self.main_frame)
        self.tabview.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # Create tabs
        self.tab_content = self.tabview.add("Content Providers")
        self.tab_backup_app = self.tabview.add("Backup & App Collection")

        # --- Content Providers Tab ---
        # Info label
        info_label = ctk.CTkLabel(
            self.tab_content,
            text="📱 Content Provider Data Collection\nCollect specific data types using Android content providers (requires device permissions)",
            font=ctk.CTkFont(size=14),
            justify="left"
        )
        info_label.pack(padx=10, pady=10)

        # Quick collection buttons
        quick_frame = ctk.CTkFrame(self.tab_content)
        quick_frame.pack(fill="x", padx=10, pady=5)

        self.collect_all_button = ctk.CTkButton(
            quick_frame,
            text="Select All Categories",
            command=self.collect_all_content_data,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="green",
            hover_color="#006400"
        )
        self.collect_all_button.pack(side="left", padx=5, pady=5)

        self.test_providers_button = ctk.CTkButton(
            quick_frame,
            text="🔍 Test Content Providers",
            command=self.test_content_providers,
            font=ctk.CTkFont(size=12)
        )
        self.test_providers_button.pack(side="left", padx=5, pady=5)

        # Individual data type selection
        selection_frame = ctk.CTkFrame(self.tab_content)
        selection_frame.pack(fill="both", expand=True, padx=10, pady=5)

        selection_label = ctk.CTkLabel(
            selection_frame,
            text="Select Individual Data Types:",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        selection_label.pack(anchor="w", padx=10, pady=(10, 5))

        # Scrollable frame for data type checkboxes
        self.data_scroll_frame = ctk.CTkScrollableFrame(selection_frame)
        self.data_scroll_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Create checkboxes for data types
        self.data_type_vars = {}
        data_types = [
            ("📞 Contacts", "contacts"),
            ("💬 SMS/MMS Messages", "sms_mms"),
            ("📞 Call Logs", "call_logs"),
            ("📅 Calendar Events", "calendar"),
            ("🌐 Browser Data", "browser"),
            ("🎵 Media Files", "media"),
            ("📱 Applications", "applications"),
            ("⚙️ System Settings", "system"),
            ("⬇️ Downloads", "downloads"),
            ("📝 Dictionary", "dictionary"),
            ("📶 WiFi Networks", "wifi")
        ]
        for display_name, key in data_types:
            var = ctk.BooleanVar()
            checkbox = ctk.CTkCheckBox(
                self.data_scroll_frame,
                text=display_name,
                variable=var,
                font=ctk.CTkFont(size=12)
            )
            checkbox.pack(anchor="w", padx=10, pady=2)
            self.data_type_vars[key] = var

        # Collect selected button
        collect_selected_button = ctk.CTkButton(
            selection_frame,
            text="📋 Collect Selected Data",
            command=self.collect_selected_content_data,
            font=ctk.CTkFont(size=12)
        )
        collect_selected_button.pack(padx=10, pady=5)

        # Status/progress textbox for Content Providers tab
        self.content_status_textbox = ctk.CTkTextbox(self.tab_content, height=60, font=ctk.CTkFont(size=12))
        self.content_status_textbox.pack(fill="x", padx=10, pady=(0, 10))
        self.content_status_textbox.configure(state="disabled")

        # --- Backup & App Collection Tab ---
        # Info label
        backup_info_label = ctk.CTkLabel(
            self.tab_backup_app,
            text="ADB Backup & App Collection\nCreate device backups and/or use the forensic app for advanced collection (requires user approval on device)\nNote: Case number and output directory are set in the main app header",
            font=ctk.CTkFont(size=14),
            justify="left"
        )
        backup_info_label.pack(padx=10, pady=10)

        # Timeout input
        timeout_frame = ctk.CTkFrame(self.tab_backup_app)
        timeout_frame.pack(fill="x", padx=10, pady=(0, 10))
        timeout_label = ctk.CTkLabel(timeout_frame, text="Timeout (minutes):", font=ctk.CTkFont(size=14))
        timeout_label.pack(side="left", padx=5)
        timeout_entry = ctk.CTkEntry(timeout_frame, textvariable=self.timeout_var, width=80)
        timeout_entry.pack(side="left", padx=5)

        # ADB Backup options
        backup_section_label = ctk.CTkLabel(
            self.tab_backup_app,
            text="ADB Backup Options:",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        backup_section_label.pack(anchor="w", padx=10, pady=(10, 5))

        self.include_apks_var = ctk.BooleanVar(value=True)
        apks_checkbox = ctk.CTkCheckBox(
            self.tab_backup_app,
            text="📱 Include APK files (app installers)",
            variable=self.include_apks_var,
            font=ctk.CTkFont(size=12)
        )
        apks_checkbox.pack(anchor="w", padx=20, pady=2)

        self.include_system_var = ctk.BooleanVar(value=False)
        system_checkbox = ctk.CTkCheckBox(
            self.tab_backup_app,
            text="⚙️ Include system apps (larger backup)",
            variable=self.include_system_var,
            font=ctk.CTkFont(size=12)
        )
        system_checkbox.pack(anchor="w", padx=20, pady=2)

        self.include_shared_var = ctk.BooleanVar(value=True)
        shared_checkbox = ctk.CTkCheckBox(
            self.tab_backup_app,
            text="📁 Include shared storage (SD card data)",
            variable=self.include_shared_var,
            font=ctk.CTkFont(size=12)
        )
        shared_checkbox.pack(anchor="w", padx=20, pady=2)

        self.install_app_var = ctk.BooleanVar(value=True)
        install_app_checkbox = ctk.CTkCheckBox(
            self.tab_backup_app,
            text="📲 Use app-based collection (arsenic_triage.apk)",
            variable=self.install_app_var,
            font=ctk.CTkFont(size=12)
        )
        install_app_checkbox.pack(anchor="w", padx=20, pady=2)

        warning_label = ctk.CTkLabel(
            self.tab_backup_app,
            text="⚠️ User must approve backup on device. Process may take 10-30 minutes.",
            font=ctk.CTkFont(size=11),
            text_color="orange"
        )
        warning_label.pack(anchor="w", padx=10, pady=(10, 5))

        self.create_backup_button = ctk.CTkButton(
            self.tab_backup_app,
            text="Create Backup",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40,
            command=self.run_combined_backup_and_collection
        )
        self.create_backup_button.pack(padx=10, pady=(10, 15))

        # Status/progress textbox for Backup & App Collection tab (only one, at the top)
        self.backup_status_textbox = ctk.CTkTextbox(self.tab_backup_app, height=120, font=ctk.CTkFont(size=12), wrap="word")
        self.backup_status_textbox.pack(fill="x", padx=10, pady=(0, 10))
        self.backup_status_textbox.configure(state="disabled")

    # Removed create_status_textbox and status_textbox

    # Removed append_backup_status and status_textbox references

        # Create tabview for different collection methods
        self.tabview = ctk.CTkTabview(self.main_frame)
        self.tabview.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # Create tabs
        self.tab_content = self.tabview.add("Content Providers")
        self.tab_backup_app = self.tabview.add("Backup & App Collection")
        self.tab_analysis = self.tabview.add("Data Analysis & Reports")

        self.setup_content_tab()
        self.setup_backup_app_tab()
        self.setup_analysis_tab()


    def append_content_status(self, msg):
        """Safely append status message to content console"""
        try:
            if hasattr(self, 'content_status_textbox') and self.content_status_textbox:
                self.content_status_textbox.configure(state="normal")
                self.content_status_textbox.insert("end", f"{datetime.now().strftime('%H:%M:%S')}  {msg}\n")
                self.content_status_textbox.see("end")
                self.content_status_textbox.configure(state="disabled")
            else:
                # Fallback to print if textbox not available
                print(f"[CONTENT STATUS] {msg}")
        except Exception as e:
            print(f"[CONTENT STATUS ERROR] {e}: {msg}")

    def append_backup_status(self, msg):
        """Safely append status message to backup console"""
        try:
            if hasattr(self, 'backup_status_textbox') and self.backup_status_textbox:
                self.backup_status_textbox.configure(state="normal")
                self.backup_status_textbox.insert("end", f"{datetime.now().strftime('%H:%M:%S')}  {msg}\n")
                self.backup_status_textbox.see("end")
                self.backup_status_textbox.configure(state="disabled")
            else:
                # Fallback to print if textbox not available
                print(f"[BACKUP STATUS] {msg}")
        except Exception as e:
            print(f"[BACKUP STATUS ERROR] {e}: {msg}")
    
        # self.timeout_var initialization moved to __init__
    def setup_content_tab(self):
        # Status/progress textbox for Content Providers tab
        self.content_status_textbox = ctk.CTkTextbox(self.tab_content, height=60, width=600, font=ctk.CTkFont(size=12))
        self.content_status_textbox.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.content_status_textbox.configure(state="disabled")
        """Setup the content provider data collection tab"""
        # Configure grid
        self.tab_content.grid_columnconfigure(0, weight=1)
        self.tab_content.grid_rowconfigure(1, weight=1)
        
        # Info frame
        info_frame = ctk.CTkFrame(self.tab_content)
        info_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        
        info_label = ctk.CTkLabel(
            info_frame,
            text="📱 Content Provider Data Collection\n\nCollect specific data types using Android content providers (requires device permissions)",
            font=ctk.CTkFont(size=14),
            justify="left"
        )
        info_label.pack(padx=10, pady=10)
        
        # Data collection options
        options_frame = ctk.CTkFrame(self.tab_content)
        options_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        options_frame.grid_columnconfigure(0, weight=1)
        options_frame.grid_rowconfigure(1, weight=1)
        
        # Quick collection buttons
        quick_frame = ctk.CTkFrame(options_frame)
        quick_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        
        quick_label = ctk.CTkLabel(
            quick_frame,
            text="Quick Collection:",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        quick_label.pack(anchor="w", padx=10, pady=(10, 5))
        
        # Button frame
        button_frame = ctk.CTkFrame(quick_frame)
        button_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        self.collect_all_button = ctk.CTkButton(
            button_frame,
            text="📋 Collect All Data",
            command=self.collect_all_content_data,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="green",
            hover_color="#006400"
        )
        self.collect_all_button.pack(side="left", padx=5, pady=5)
        
        self.test_providers_button = ctk.CTkButton(
            button_frame,
            text="🔍 Test Providers",
            command=self.test_content_providers,
            font=ctk.CTkFont(size=12)
        )
        self.test_providers_button.pack(side="left", padx=5, pady=5)
        
        # Individual data type selection
        selection_frame = ctk.CTkFrame(options_frame)
        selection_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        selection_frame.grid_columnconfigure(0, weight=1)
        selection_frame.grid_rowconfigure(1, weight=1)
        
        selection_label = ctk.CTkLabel(
            selection_frame,
            text="Select Individual Data Types:",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        selection_label.grid(row=0, column=0, sticky="w", padx=10, pady=(10, 5))
        
        # Scrollable frame for data type checkboxes
        self.data_scroll_frame = ctk.CTkScrollableFrame(selection_frame)
        self.data_scroll_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        
        # Create checkboxes for data types
        self.data_type_vars = {}
        data_types = [
            ("📞 Contacts", "contacts"),
            ("💬 SMS/MMS Messages", "sms_mms"),
            ("📞 Call Logs", "call_logs"),
            ("📅 Calendar Events", "calendar"),
            ("🌐 Browser Data", "browser"),
            ("🎵 Media Files", "media"),
            ("📱 Applications", "applications"),
            ("⚙️ System Settings", "system"),
            ("⬇️ Downloads", "downloads"),
            ("📝 Dictionary", "dictionary"),
            ("📶 WiFi Networks", "wifi")
        ]
        
        for display_name, key in data_types:
            var = ctk.BooleanVar()
            checkbox = ctk.CTkCheckBox(
                self.data_scroll_frame,
                text=display_name,
                variable=var,
                font=ctk.CTkFont(size=12)
            )
            checkbox.pack(anchor="w", padx=10, pady=2)
            self.data_type_vars[key] = var
        
        # Collect selected button
        collect_selected_button = ctk.CTkButton(
            selection_frame,
            text="📋 Collect Selected Data",
            command=self.collect_selected_content_data,
            font=ctk.CTkFont(size=12)
        )
        collect_selected_button.grid(row=2, column=0, padx=10, pady=5)
    
    def setup_backup_app_tab(self):
        """Setup the combined ADB backup and App Collection tab"""
        # Configure grid
        self.tab_backup_app.grid_columnconfigure(0, weight=1)
        self.tab_backup_app.grid_rowconfigure(1, weight=1)

        # Info frame
        info_frame = ctk.CTkFrame(self.tab_backup_app)
        info_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)

        info_label = ctk.CTkLabel(
            info_frame,
            text="📦 ADB Backup & App Collection\n\nCreate device backups and/or use the forensic app for advanced collection (requires user approval on device)",
            font=ctk.CTkFont(size=14),
            justify="left"
        )
        info_label.pack(padx=10, pady=10)

        # Main options frame
        options_frame = ctk.CTkFrame(self.tab_backup_app)
        options_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        options_frame.grid_columnconfigure(0, weight=1)

        # Console Output at the top for real-time feedback
        # console_label = ctk.CTkLabel(
        #     options_frame,
        #     text="📋 Console Output:",
        #     font=ctk.CTkFont(size=14, weight="bold")
        # )
        # console_label.pack(anchor="w", padx=10, pady=(10, 5))
        
        self.backup_status_textbox = ctk.CTkTextbox(
            options_frame, 
            height=150, 
            font=ctk.CTkFont(size=11), 
            wrap="word"
        )
        self.backup_status_textbox.pack(fill="x", padx=10, pady=(0, 15))
        self.backup_status_textbox.configure(state="disabled")

        # --- Timeout Input ---
        timeout_frame = ctk.CTkFrame(options_frame)
        timeout_frame.pack(fill="x", padx=10, pady=(5, 10))
        timeout_label = ctk.CTkLabel(timeout_frame, text="Timeout (minutes):", font=ctk.CTkFont(size=14))
        timeout_label.pack(side="left", padx=5)
        timeout_entry = ctk.CTkEntry(timeout_frame, textvariable=self.timeout_var, width=80)
        timeout_entry.pack(side="left", padx=5)

        # --- ADB Backup Section ---
        backup_section_label = ctk.CTkLabel(
            options_frame,
            text="ADB Backup Options:",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        backup_section_label.pack(anchor="w", padx=10, pady=(10, 5))

        self.include_apks_var = ctk.BooleanVar(value=True)
        apks_checkbox = ctk.CTkCheckBox(
            options_frame,
            text="📱 Include APK files (app installers)",
            variable=self.include_apks_var,
            font=ctk.CTkFont(size=12)
        )
        apks_checkbox.pack(anchor="w", padx=20, pady=2)

        self.include_system_var = ctk.BooleanVar(value=False)
        system_checkbox = ctk.CTkCheckBox(
            options_frame,
            text="⚙️ Include system apps (larger backup)",
            variable=self.include_system_var,
            font=ctk.CTkFont(size=12)
        )
        system_checkbox.pack(anchor="w", padx=20, pady=2)

        self.include_shared_var = ctk.BooleanVar(value=True)
        shared_checkbox = ctk.CTkCheckBox(
            options_frame,
            text="📁 Include shared storage (SD card data)",
            variable=self.include_shared_var,
            font=ctk.CTkFont(size=12)
        )
        shared_checkbox.pack(anchor="w", padx=20, pady=2)

        # App-based collection option
        self.install_app_var = ctk.BooleanVar(value=True)
        install_app_checkbox = ctk.CTkCheckBox(
            options_frame,
            text="📲 Use app-based collection (arsenic_triage.apk)",
            variable=self.install_app_var,
            font=ctk.CTkFont(size=12)
        )
        install_app_checkbox.pack(anchor="w", padx=20, pady=2)

        warning_label = ctk.CTkLabel(
            options_frame,
            text="⚠️ User must approve backup on device. Process may take 10-30 minutes.",
            font=ctk.CTkFont(size=11),
            text_color="orange"
        )
        warning_label.pack(anchor="w", padx=10, pady=(10, 5))

        self.create_backup_button = ctk.CTkButton(
            options_frame,
            text="Create Backup",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40,
            command=self.run_combined_backup_and_collection
        )
        self.create_backup_button.pack(padx=10, pady=(10, 15))

    def run_combined_backup_and_collection(self):
        # Get case number and output directory from main app header
        main_app = self.winfo_toplevel()
        
        case_number = ""
        output_dir = ""
        
        if hasattr(main_app, 'get_case_number'):
            case_number = main_app.get_case_number()
        if hasattr(main_app, 'get_output_directory'):
            output_dir = main_app.get_output_directory()
        
        if not case_number:
            self.append_backup_status("⚠️ Case number required in header.")
            messagebox.showwarning("Case Number Required", "Please enter a case number in the header before running backup.")
            return
            
        if not output_dir:
            self.append_backup_status("⚠️ Output directory required in header.")
            messagebox.showwarning("Output Directory Required", "Please select an output directory in the header before running backup.")
            return
            
        if not self.device_connected:
            self.append_backup_status("❌ No Android device connected!")
            messagebox.showerror("Error", "No Android device connected!")
            return
        
        # Disable button and show starting status
        self.create_backup_button.configure(state="disabled")
        
        include_apks = self.include_apks_var.get()
        include_system = self.include_system_var.get()
        include_shared = self.include_shared_var.get()
        install_app = self.install_app_var.get()
        timeout_minutes = int(self.timeout_var.get()) if self.timeout_var.get().isdigit() else 10

        self.append_backup_status(f"⏳ Starting ADB Backup + App Collection for case: {case_number}...")

        def thread_safe_append(msg):
            """Thread-safe method to append messages to console"""
            try:
                if self and hasattr(self, 'after') and callable(self.after):
                    self.after(0, lambda m=msg: self.append_backup_status(m))
                else:
                    print(f"[THREAD-SAFE APPEND] {msg}")
            except Exception as e:
                print(f"[THREAD-SAFE APPEND ERROR] {e}: {msg}")

        def run_tasks():
            adb_success = False
            app_success = False
            console_capture = None
            
            try:
                # Setup stdout capture to redirect print statements to GUI
                console_capture = ConsoleCapture(thread_safe_append)
                
                if not self.collector:
                    self.collector = self.create_collector()
                
                # Create case-specific output directory using case number
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                case_folder = os.path.join(output_dir, f"Android_Backup_{case_number}_{timestamp}")
                os.makedirs(case_folder, exist_ok=True)
                
                self.collector.output_dir = case_folder
                thread_safe_append(f"📁 Created case folder: {case_folder}")

                # Run app-based collection FIRST if requested
                if install_app:
                    try:
                        self.after(0, lambda: self.create_backup_button.configure(text="📲 App Collection..."))
                        thread_safe_append("🔧 Starting App-Based Collection...")
                        
                        # Redirect stdout to capture print statements from collector
                        with redirect_stdout(console_capture):
                            app_success = self.collector.collect_with_app(install_app=True, timeout_minutes=timeout_minutes)
                    except Exception as app_error:
                        thread_safe_append(f"❌ App Collection error: {str(app_error)}")
                        app_success = False
                else:
                    app_success = True
                
                # Then run ADB backup
                try:
                    self.after(0, lambda: self.create_backup_button.configure(text="Running ADB Backup..."))
                    thread_safe_append("📦 Starting ADB Backup...")
                    
                    # Redirect stdout to capture print statements from collector
                    with redirect_stdout(console_capture):
                        adb_success = self.collector.create_adb_backup(include_apks, include_system, include_shared)
                except Exception as backup_error:
                    thread_safe_append(f"❌ ADB Backup error: {str(backup_error)}")
                    adb_success = False

                # Show final result
                if adb_success and app_success:
                    result_msg = "✅ Both ADB backup and App Collection completed successfully!"
                    self.after(0, lambda: self.create_backup_button.configure(text="✅ Completed"))
                elif adb_success:
                    result_msg = "⚠️ ADB backup succeeded, but App Collection failed."
                    self.after(0, lambda: self.create_backup_button.configure(text="⚠️ Partial Success"))
                elif app_success:
                    result_msg = "⚠️ App Collection succeeded, but ADB backup failed."
                    self.after(0, lambda: self.create_backup_button.configure(text="⚠️ Partial Success"))
                else:
                    result_msg = "❌ Both ADB backup and App Collection failed."
                    self.after(0, lambda: self.create_backup_button.configure(text="❌ Failed"))
                
                thread_safe_append(result_msg)
                
            except Exception as e:
                error_msg = f"❌ Error during backup: {str(e)}"
                thread_safe_append(error_msg)
                print(f"DEBUG: Full backup error: {e}")  # Additional debug info
                self.after(0, lambda: self.create_backup_button.configure(text="❌ Error"))
            finally:
                # Re-enable button after 3 seconds
                self.after(3000, lambda: [
                    self.create_backup_button.configure(text="Create Backup"),
                    self.create_backup_button.configure(state="normal")
                ])

        # Start backup in background thread
        threading.Thread(target=run_tasks, daemon=True).start()
    # (Removed duplicate method definition)


    # ...existing code...
    
    def manual_refresh_device(self):
        """Manually refresh device status with detailed feedback"""
        self.status_label.configure(text="Checking...")
        self.status_indicator.configure(text="🟡")
        
        # Force recreation of collector
        self.collector = None
        
        def detailed_check():
            try:
                # Test ADB directly first with correct platform command
                print("=== MANUAL DEVICE CHECK DEBUG ===")
                import subprocess
                
                # Get the correct ADB command for this platform
                adb_cmd = self.get_adb_command()
                print(f"Using ADB command: {adb_cmd}")
                
                result = subprocess.run([adb_cmd, 'devices'], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
                
                print(f"ADB command return code: {result.returncode}")
                print(f"ADB stdout: {result.stdout}")
                print(f"ADB stderr: {result.stderr}")
                
                # Parse devices
                devices = []
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    for line in lines[1:]:  # Skip "List of devices attached"
                        if line.strip() and '\tdevice' in line:
                            devices.append(line.strip())
                            print(f"Found device: {line.strip()}")
                
                print(f"Total devices found: {len(devices)}")
                
                if devices:
                    self.after(0, lambda: self.append_content_status(f"✅ Found {len(devices)} Android device(s)"))
                    # Now test with collector - but create it with a temporary output directory
                    if not self.collector:
                        # Create collector with a temp directory to avoid None path error
                        import tempfile
                        temp_dir = tempfile.mkdtemp()
                        working_adb = self.get_adb_command()
                        self.collector = self.create_collector(output_dir=temp_dir)
                    
                    collector_result = self.collector.check_device()
                    print(f"Collector check_device result: {collector_result}")
                    
                    self.after(0, lambda: self.update_device_status(collector_result))
                else:
                    print("No devices found - updating status to disconnected")
                    self.after(0, lambda: self.append_content_status("❌ No Android devices found"))
                    self.after(0, lambda: self.update_device_status(False))
                
                print("=== END DEVICE CHECK DEBUG ===")
                
            except FileNotFoundError:
                print("ADB not found!")
                self.after(0, lambda: self.append_content_status("❌ ADB not found - install Android SDK"))
                self.after(0, lambda: self.update_device_status(False))
            except Exception as e:
                print(f"Device check error: {e}")
                self.after(0, lambda: self.append_content_status(f"❌ Device check error: {e}"))
                self.after(0, lambda: self.update_device_status(False))
        
        threading.Thread(target=detailed_check, daemon=True).start()

    def check_device_status(self):
        """Check if an Android device is connected"""
        def check():
            try:
                if not self.collector:
                    # Create collector with a temp directory to avoid None path error
                    import tempfile
                    temp_dir = tempfile.mkdtemp()
                    working_adb = self.get_adb_command()
                    self.collector = self.create_collector(output_dir=temp_dir)
                
                connected = self.collector.check_device()
                
                # Update UI in main thread
                self.after(0, self.update_device_status, connected)
            except Exception as e:
                print(f"Error in check_device_status: {e}")
                self.after(0, self.update_device_status, False)
        
        # Run check in background thread
        threading.Thread(target=check, daemon=True).start()
    
    def update_device_status(self, connected):
        """Update the device status display"""
        self.device_connected = connected
        
        if connected:
            self.status_indicator.configure(text="🟢")
            self.status_label.configure(text="Android device connected")
            
            # Enable all buttons
            if hasattr(self, 'collect_all_button'):
                self.collect_all_button.configure(state="normal")
            if hasattr(self, 'test_providers_button'):
                self.test_providers_button.configure(state="normal")
            if hasattr(self, 'create_backup_button'):
                self.create_backup_button.configure(state="normal")
                
            # Log successful connection
            self.append_content_status("✅ Android device connected and ready")
        else:
            self.status_indicator.configure(text="🔴")
            self.status_label.configure(text="No device connected")
            
            # Disable buttons that require device
            if hasattr(self, 'collect_all_button'):
                self.collect_all_button.configure(state="disabled")
            if hasattr(self, 'test_providers_button'):
                self.test_providers_button.configure(state="disabled")
            if hasattr(self, 'create_backup_button'):
                self.create_backup_button.configure(state="disabled")
                
            # Log connection failure
            self.append_content_status("❌ No Android device detected")
    
    def collect_all_content_data(self):
        """Collect all available content provider data"""
        if not self.device_connected:
            messagebox.showerror("Error", "No Android device connected!")
            return
        
        # Get case number and output directory from main app header
        main_app = self.winfo_toplevel()
        
        case_number = ""
        output_dir = ""
        
        if hasattr(main_app, 'get_case_number'):
            case_number = main_app.get_case_number()
        if hasattr(main_app, 'get_output_directory'):
            output_dir = main_app.get_output_directory()
        
        if not case_number:
            self.append_content_status("⚠️ Case number required in header.")
            messagebox.showwarning("Case Number Required", "Please enter a case number in the header before collecting data.")
            return
            
        if not output_dir:
            self.append_content_status("⚠️ Output directory required in header.")
            messagebox.showwarning("Output Directory Required", "Please select an output directory in the header before collecting data.")
            return
        
        def collect():
            try:
                self.after(0, lambda: self.collect_all_button.configure(text="⏳ Collecting...", state="disabled"))
                
                if not self.collector:
                    self.collector = self.create_collector()
                
                # Create case-specific output directory
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                case_folder = os.path.join(output_dir, f"Android_Content_{case_number}_{timestamp}")
                os.makedirs(case_folder, exist_ok=True)
                
                self.collector.output_dir = case_folder
                self.append_content_status(f"Created case folder: {case_folder}")
                
                self.collector.collect_all_data()
                
                success_msg = f"Data collection completed for case: {case_number}!\nData saved to: {case_folder}"
                self.after(0, lambda: self._show_success_message("Success", success_msg))
                
            except Exception as e:
                error_msg = f"Collection failed: {str(e)}"
                self.after(0, lambda: self._show_error_message("Error", error_msg))
            finally:
                self.after(0, lambda: self.collect_all_button.configure(text="📋 Collect All Data", state="normal"))
        
        threading.Thread(target=collect, daemon=True).start()
    
    def _show_success_message(self, title, message):
        """Safely display success message"""
        try:
            messagebox.showinfo(title, message)
        except Exception as e:
            print(f"Error displaying success message: {e}")
            print(f"{title}: {message}")
    
    def _show_error_message(self, title, message):
        """Safely display error message"""
        try:
            messagebox.showerror(title, message)
        except Exception as e:
            print(f"Error displaying error message: {e}")
            print(f"{title}: {message}")
    
    def collect_selected_content_data(self):
        """Collect data for selected content types"""
        if not self.device_connected:
            self.append_content_status("❌ No Android device connected!")
            messagebox.showerror("Error", "No Android device connected!")
            return

        # Get case number and output directory from main app header
        main_app = self.winfo_toplevel()
        
        case_number = ""
        output_dir = ""
        
        if hasattr(main_app, 'get_case_number'):
            case_number = main_app.get_case_number()
        if hasattr(main_app, 'get_output_directory'):
            output_dir = main_app.get_output_directory()
        
        if not case_number:
            self.append_content_status("⚠️ Case number required in header.")
            messagebox.showwarning("Case Number Required", "Please enter a case number in the header before collecting data.")
            return
            
        if not output_dir:
            self.append_content_status("⚠️ Output directory required in header.")
            messagebox.showwarning("Output Directory Required", "Please select an output directory in the header before collecting data.")
            return

        # Get selected data types
        selected_types = [key for key, var in self.data_type_vars.items() if var.get()]

        if not selected_types:
            self.append_content_status("⚠️ No data types selected.")
            messagebox.showwarning("Warning", "No data types selected!")
            return

        self.append_content_status(f"⏳ Collecting for case {case_number}: {', '.join(selected_types)}")

        def collect():
            try:
                if not self.collector:
                    self.collector = self.create_collector()

                # Create case-specific output directory
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                case_folder = os.path.join(output_dir, f"Android_Selected_{case_number}_{timestamp}")
                os.makedirs(case_folder, exist_ok=True)
                
                self.collector.output_dir = case_folder
                self.append_content_status(f"Created case folder: {case_folder}")

                # Import the content URI commands
                from src.Droid_backup.android_backup_collector import CONTENT_URI_COMMANDS

                collected_data = {}
                total_commands = sum(len(CONTENT_URI_COMMANDS[category]['commands']) 
                                   for category in selected_types 
                                   if category in CONTENT_URI_COMMANDS)
                current_command = 0

                for category in selected_types:
                    if category in CONTENT_URI_COMMANDS:
                        category_data = []

                        for cmd in CONTENT_URI_COMMANDS[category]['commands']:
                            current_command += 1

                            projection = cmd.get('projection')
                            success, data = self.collector.query_content_provider(cmd['uri'], projection)

                            if success and data.strip():
                                parsed_data = self.collector._parse_content_output(data)
                                category_data.append({
                                    'name': cmd['name'],
                                    'uri': cmd['uri'],
                                    'description': cmd['description'],
                                    'data': parsed_data,
                                    'record_count': len(parsed_data) if isinstance(parsed_data, list) else 1
                                })

                        if category_data:
                            collected_data[category] = category_data

                # Save collected data
                self.collector._save_collected_data(collected_data)

                success_msg = f"✅ Selected data collection completed! Data saved to: {self.collector.output_dir}"
                self.append_content_status(success_msg)
                self.after(0, lambda: self._show_success_message("Success", success_msg))

            except Exception as e:
                error_msg = f"❌ Collection failed: {str(e)}"
                self.append_content_status(error_msg)
                self.after(0, lambda: self._show_error_message("Error", error_msg))

        threading.Thread(target=collect, daemon=True).start()
    
    def test_content_providers(self):
        """Test access to common content providers"""
        if not self.device_connected:
            self.append_content_status("❌ No Android device connected!")
            return
        
        # Clear previous results and show starting message
        self.content_status_textbox.configure(state="normal")
        self.content_status_textbox.delete("1.0", "end")
        self.content_status_textbox.configure(state="disabled")
        
        self.append_content_status("🔍 Testing content provider access...")
        self.append_content_status("This may take a few moments...")
        
        # Disable the test button during testing
        self.test_providers_button.configure(state="disabled", text="Testing...")
        
        def test():
            try:
                if not self.collector:
                    # Create collector with a temp directory to avoid None path error
                    import tempfile
                    temp_dir = tempfile.mkdtemp()
                    self.collector = self.create_collector(output_dir=temp_dir)
                
                # Test common URIs with user-friendly names
                test_uris = [
                    ("content://sms", "SMS Messages"),
                    ("content://contacts/people", "Contacts"),
                    ("content://call_log/calls", "Call Logs"),
                    ("content://settings/system", "System Settings"),
                    ("content://media/external/images/media", "External Images"),
                    ("content://media/external/video/media", "External Videos"),
                    ("content://downloads/public_downloads", "Downloads"),
                    ("content://calendar/events", "Calendar Events"),
                    ("content://browser/bookmarks", "Browser Bookmarks")
                ]
                
                self.after(0, lambda: self.append_content_status(f"📋 Testing {len(test_uris)} content providers..."))
                
                accessible_count = 0
                not_accessible_count = 0
                
                for i, (uri, name) in enumerate(test_uris, 1):
                    self.after(0, lambda u=uri, n=name, idx=i: self.append_content_status(f"[{idx}/{len(test_uris)}] Testing {n}..."))
                    
                    success, data = self.collector.query_content_provider(uri)
                    
                    if success and data.strip():
                        # Count records if possible
                        lines = data.strip().split('\n')
                        record_count = len([line for line in lines if line.strip() and not line.startswith('Row:')])
                        
                        if record_count > 0:
                            status_msg = f"✅ {name}: {record_count} records found"
                            accessible_count += 1
                        else:
                            status_msg = f"⚠️ {name}: Accessible but no data"
                            not_accessible_count += 1
                    else:
                        status_msg = f"❌ {name}: Not accessible"
                        not_accessible_count += 1
                    
                    self.after(0, lambda msg=status_msg: self.append_content_status(msg))
                
                # Show summary
                total_tested = len(test_uris)
                self.after(0, lambda: self.append_content_status(""))
                self.after(0, lambda: self.append_content_status("📊 SUMMARY:"))
                self.after(0, lambda: self.append_content_status(f"   ✅ Accessible: {accessible_count}/{total_tested}"))
                self.after(0, lambda: self.append_content_status(f"   ❌ Not accessible: {not_accessible_count}/{total_tested}"))
                
                if accessible_count > 0:
                    self.after(0, lambda: self.append_content_status(""))
                    self.after(0, lambda: self.append_content_status("💡 You can now use 'Select All Categories' to collect data"))
                    self.after(0, lambda: self.append_content_status("   from the accessible content providers."))
                else:
                    self.after(0, lambda: self.append_content_status(""))
                    self.after(0, lambda: self.append_content_status("⚠️ No content providers are accessible."))
                    self.after(0, lambda: self.append_content_status("   This may be due to device permissions or Android version."))
                
            except Exception as e:
                error_msg = f"❌ Testing failed: {str(e)}"
                self.after(0, lambda: self.append_content_status(error_msg))
            finally:
                # Re-enable the test button
                self.after(0, lambda: self.test_providers_button.configure(state="normal", text="🔍 Test Providers"))
        
        threading.Thread(target=test, daemon=True).start()
    
    def create_adb_backup(self):
        """Create an ADB backup"""
        if not self.device_connected:
            messagebox.showerror("Error", "No Android device connected!")
            return
        
        include_apks = self.include_apks_var.get()
        include_system = self.include_system_var.get()
        include_shared = self.include_shared_var.get()
        
        def backup():
            try:
                self.after(0, lambda: self.create_backup_button.configure(text="⏳ Creating backup...", state="disabled"))
                
                if not self.collector:
                    self.collector = self.create_collector()
                
                success = self.collector.create_adb_backup(include_apks, include_system, include_shared)
                
                if success:
                    success_msg = f"ADB backup created successfully!\\nBackup saved to: {self.collector.output_dir}"
                    self.after(0, lambda: self._show_success_message("Success", success_msg))
                else:
                    self.after(0, lambda: self._show_error_message("Error", "Backup creation failed!"))
                
            except Exception as e:
                error_msg = f"Backup failed: {str(e)}"
                self.after(0, lambda: self._show_error_message("Error", error_msg))
            finally:
                self.after(0, lambda: self.create_backup_button.configure(text="📦 Create ADB Backup", state="normal"))
        
        threading.Thread(target=backup, daemon=True).start()
    
    def browse_backup_file(self):
        """Browse for an existing backup file and analyze it for encryption"""
        file_path = filedialog.askopenfilename(
            title="Select Android Backup File",
            filetypes=[("Android Backup", "*.ab"), ("All Files", "*.*")]
        )
        
        if file_path:
            self.backup_file_entry.delete(0, tk.END)
            self.backup_file_entry.insert(0, file_path)
            
            # Analyze the backup file for encryption
            self.analyze_selected_backup()
    
    def analyze_selected_backup(self):
        """Analyze the selected backup file to detect encryption"""
        backup_path = self.backup_file_entry.get().strip()
        
        if not backup_path or not os.path.exists(backup_path):
            return
        
        try:
            analyzer = AndroidBackupAnalyzer()
            analysis_result = analyzer.analyze_backup_file(backup_path)
            
            # Show analysis information to user
            analyzer.show_encryption_info(analysis_result, parent=self)
            
            # Store analysis result for later use during extraction
            self.backup_analysis = analysis_result
            
        except Exception as e:
            print(f"Error analyzing backup: {e}")
            messagebox.showwarning(
                "Analysis Warning", 
                f"Could not fully analyze backup file:\n{str(e)}\n\nExtraction will still be attempted.",
                parent=self
            )
    
    def extract_backup_file(self):
        """Extract a selected backup file with automatic encryption detection and password handling"""
        backup_path = self.backup_file_entry.get().strip()
        
        if not backup_path:
            messagebox.showerror("Error", "Please select a backup file!")
            return
        
        if not os.path.exists(backup_path):
            messagebox.showerror("Error", "Backup file not found!")
            return
        
        def extract():
            try:
                if not self.collector:
                    self.collector = self.create_collector()
                
                # Analyze backup for encryption if not already done
                password = None
                if not hasattr(self, 'backup_analysis'):
                    analyzer = AndroidBackupAnalyzer()
                    self.backup_analysis = analyzer.analyze_backup_file(backup_path)
                
                # If backup is encrypted, prompt for password
                if hasattr(self, 'backup_analysis') and self.backup_analysis.get('is_encrypted', False):
                    self.after(0, lambda: self._prompt_for_password_and_extract(backup_path))
                else:
                    # Extract unencrypted backup
                    success = self.collector.extract_adb_backup(backup_path, password=None)
                    self._handle_extraction_result(success)
                
            except Exception as e:
                error_msg = f"Extraction failed: {str(e)}"
                self.after(0, lambda: self._show_error_message("Error", error_msg))
        
        threading.Thread(target=extract, daemon=True).start()
    
    def _prompt_for_password_and_extract(self, backup_path):
        """Prompt for password and extract encrypted backup (runs on main thread)"""
        try:
            analyzer = AndroidBackupAnalyzer()
            password = analyzer.prompt_for_password(parent=self)
            
            if password is None:
                messagebox.showinfo("Extraction Cancelled", "Backup extraction was cancelled.")
                return
            
            # Extract with password in background thread
            def extract_with_password():
                try:
                    success = self.collector.extract_adb_backup(backup_path, password=password)
                    self.after(0, lambda: self._handle_extraction_result(success))
                except Exception as e:
                    error_msg = f"Password-protected extraction failed: {str(e)}"
                    self.after(0, lambda: self._show_error_message("Error", error_msg))
            
            threading.Thread(target=extract_with_password, daemon=True).start()
            
        except Exception as e:
            error_msg = f"Password prompt failed: {str(e)}"
            self._show_error_message("Error", error_msg)
    
    def _handle_extraction_result(self, success):
        """Handle the result of backup extraction"""
        if success:
            success_msg = f"Backup extracted successfully!\nExtracted to: {self.collector.output_dir}"
            self._show_success_message("Success", success_msg)
        else:
            self._show_error_message("Error", "Backup extraction failed!")
    
    def _show_success_message(self, title, message):
        """Show success message on main thread"""
        messagebox.showinfo(title, message, parent=self)
    
    def _show_error_message(self, title, message):
        """Show error message on main thread"""
        messagebox.showerror(title, message, parent=self)
    
    def start_app_collection(self):
        """Start the forensic app collection process"""
        if not self.device_connected:
            messagebox.showerror("Error", "No Android device connected!")
            return
        
        install_app = self.install_app_var.get()
        timeout_minutes = int(self.timeout_var.get()) if self.timeout_var.get().isdigit() else 10
        
        def collect():
            try:
                pass
                
                if not self.collector:
                    self.collector = self.create_collector()
                
                success = self.collector.collect_with_app(install_app, timeout_minutes)
                
                if success:
                    success_msg = f"App collection completed successfully!\\nData saved to: {self.collector.output_dir}/apk_data_directory"
                    self.after(0, lambda: self._show_success_message("Success", success_msg))
                else:
                    self.after(0, lambda: self._show_error_message("Error", "App collection failed!"))
                
            except Exception as e:
                error_msg = f"App collection failed: {str(e)}"
                self.after(0, lambda: self._show_error_message("Error", error_msg))
            finally:
                pass
        
        threading.Thread(target=collect, daemon=True).start()
    
    def discover_providers(self):
        """Discover available content providers"""
        if not self.device_connected:
            messagebox.showerror("Error", "No Android device connected!")
            return
        
        def discover():
            try:
                if not self.collector:
                    self.collector = self.create_collector()
                
                # Get raw providers
                success, providers = self.collector._discover_content_providers_raw()
                
                if success:
                    # Generate report
                    report = self.collector._generate_provider_report(providers)
                    
                    # Update UI in main thread
                    self.after(0, lambda: self.update_discovery_results(report))
                else:
                    self.after(0, lambda: self._show_error_message("Error", "Provider discovery failed!"))
                
            except Exception as e:
                error_msg = f"Discovery failed: {str(e)}"
                self.after(0, lambda: self._show_error_message("Error", error_msg))
        
        threading.Thread(target=discover, daemon=True).start()
    
    def test_custom_uri(self):
        """Test a custom content URI"""
        uri = self.uri_entry.get().strip()
        
        if not uri:
            messagebox.showerror("Error", "Please enter a content URI!")
            return
        
        if not self.device_connected:
            messagebox.showerror("Error", "No Android device connected!")
            return
        
        def test():
            try:
                if not self.collector:
                    self.collector = self.create_collector()
                
                success, data = self.collector.query_content_provider(uri)
                
                if success:
                    if data.strip():
                        # Show first few lines
                        lines = data.split('\n')[:10]
                        sample_data = '\n'.join(lines)
                        total_lines = len(data.split('\n'))
                        
                        result = f"✅ URI accessible!\\n\\nSample data ({total_lines} total lines):\\n{sample_data}"
                        if total_lines > 10:
                            result += f"\\n... ({total_lines - 10} more lines)"
                    else:
                        result = "⚠️ URI accessible but returned no data"
                else:
                    result = f"❌ URI not accessible: {data}"
                
                self.after(0, lambda: self.update_discovery_results(f"Test Results for {uri}:\\n\\n{result}"))
                
            except Exception as e:
                error_msg = f"URI test failed: {str(e)}"
                self.after(0, lambda: self._show_error_message("Error", error_msg))
        
        threading.Thread(target=test, daemon=True).start()
    
    def update_discovery_results(self, text):
        """Update the discovery results text display"""
        self.discovery_text.delete("1.0", tk.END)
        self.discovery_text.insert("1.0", text)
    
    def destroy(self):
        """Clean up when frame is destroyed"""
        self.stop_monitoring = True
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=1.0)
        super().destroy()
    
    def _format_file_size_safe(self, size_bytes):
        """Safely format file size with fallback"""
        try:
            if hasattr(self.collector, '_format_file_size'):
                return self.collector._format_file_size(size_bytes)
            else:
                # Fallback implementation
                if size_bytes == 0:
                    return "0 B"
                
                size_names = ["B", "KB", "MB", "GB", "TB"]
                i = int(math.floor(math.log(size_bytes, 1024)))
                p = math.pow(1024, i)
                s = round(size_bytes / p, 2)
                return f"{s} {size_names[i]}"
        except Exception:
            return f"{size_bytes} bytes"

    def setup_analysis_tab(self):
        """Setup the Android data analysis and reporting tab"""
        # Configure grid
        self.tab_analysis.grid_columnconfigure(0, weight=1)
        self.tab_analysis.grid_rowconfigure(1, weight=1)
        
        # Title and info
        title_frame = ctk.CTkFrame(self.tab_analysis)
        title_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        
        title_label = ctk.CTkLabel(
            title_frame,
            text="Android Data Analysis & Forensic Reports",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        title_label.pack(pady=10)
        
        info_label = ctk.CTkLabel(
            title_frame,
            text="Analyze Android backup files (.ab) and APK-collected data to generate comprehensive forensic reports",
            font=ctk.CTkFont(size=12)
        )
        info_label.pack(pady=(0, 10))
        
        # Main content frame
        content_frame = ctk.CTkFrame(self.tab_analysis)
        content_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_rowconfigure(2, weight=1)
        
        # File selection frame
        file_frame = ctk.CTkFrame(content_frame)
        file_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        file_frame.grid_columnconfigure(1, weight=1)
        
        # Android backup file selection
        ab_label = ctk.CTkLabel(file_frame, text="Android Backup (.ab):", font=ctk.CTkFont(size=12, weight="bold"))
        ab_label.grid(row=0, column=0, sticky="w", padx=5, pady=5)
        
        self.ab_file_var = tk.StringVar()
        self.ab_file_entry = ctk.CTkEntry(file_frame, textvariable=self.ab_file_var, placeholder_text="Select Android backup file...")
        self.ab_file_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        
        ab_browse_btn = ctk.CTkButton(file_frame, text="Browse", command=self.browse_ab_file, width=80)
        ab_browse_btn.grid(row=0, column=2, padx=5, pady=5)
        
        # Backup password field
        password_label = ctk.CTkLabel(file_frame, text="Backup Password:", font=ctk.CTkFont(size=12, weight="bold"))
        password_label.grid(row=1, column=0, sticky="w", padx=5, pady=5)
        
        self.backup_password_var = tk.StringVar()
        self.backup_password_entry = ctk.CTkEntry(file_frame, textvariable=self.backup_password_var, 
                                                 placeholder_text="Enter password (leave blank if no password)", show="*")
        self.backup_password_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=5)
        
        # Info button for password help
        password_info_btn = ctk.CTkButton(file_frame, text="?", command=self.show_password_info, width=30)
        password_info_btn.grid(row=1, column=2, padx=5, pady=5)
        
        # APK data directory selection
        apk_label = ctk.CTkLabel(file_frame, text="APK Data Directory:", font=ctk.CTkFont(size=12, weight="bold"))
        apk_label.grid(row=2, column=0, sticky="w", padx=5, pady=5)
        
        self.apk_dir_var = tk.StringVar()
        self.apk_dir_entry = ctk.CTkEntry(file_frame, textvariable=self.apk_dir_var, placeholder_text="Select APK collected data directory...")
        self.apk_dir_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=5)
        
        apk_browse_btn = ctk.CTkButton(file_frame, text="Browse", command=self.browse_apk_dir, width=80)
        apk_browse_btn.grid(row=2, column=2, padx=5, pady=5)
        
        # Output directory selection
        output_label = ctk.CTkLabel(file_frame, text="Output Directory:", font=ctk.CTkFont(size=12, weight="bold"))
        output_label.grid(row=3, column=0, sticky="w", padx=5, pady=5)
        
        self.analysis_output_var = tk.StringVar()
        self.analysis_output_entry = ctk.CTkEntry(file_frame, textvariable=self.analysis_output_var, placeholder_text="Select output directory for analysis results...")
        self.analysis_output_entry.grid(row=3, column=1, sticky="ew", padx=5, pady=5)
        
        output_browse_btn = ctk.CTkButton(file_frame, text="Browse", command=self.browse_analysis_output, width=80)
        output_browse_btn.grid(row=3, column=2, padx=5, pady=5)
        
        # Options frame
        options_frame = ctk.CTkFrame(content_frame)
        options_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        
        options_label = ctk.CTkLabel(options_frame, text="Analysis Options:", font=ctk.CTkFont(size=14, weight="bold"))
        options_label.pack(anchor="w", padx=10, pady=(10, 5))
        
        # Analysis options checkboxes
        self.extract_ab_var = tk.BooleanVar(value=True)
        ab_checkbox = ctk.CTkCheckBox(
            options_frame,
            text="📦 Extract Android Backup (.ab) file",
            variable=self.extract_ab_var,
            font=ctk.CTkFont(size=12)
        )
        ab_checkbox.pack(anchor="w", padx=20, pady=2)
        
        self.parse_apk_var = tk.BooleanVar(value=True)
        apk_checkbox = ctk.CTkCheckBox(
            options_frame,
            text="📱 Parse APK collected data",
            variable=self.parse_apk_var,
            font=ctk.CTkFont(size=12)
        )
        apk_checkbox.pack(anchor="w", padx=20, pady=2)
        
        self.generate_report_var = tk.BooleanVar(value=True)
        report_checkbox = ctk.CTkCheckBox(
            options_frame,
            text="📊 Generate comprehensive forensic report",
            variable=self.generate_report_var,
            font=ctk.CTkFont(size=12)
        )
        report_checkbox.pack(anchor="w", padx=20, pady=2)
        
        self.create_timeline_var = tk.BooleanVar(value=True)
        timeline_checkbox = ctk.CTkCheckBox(
            options_frame,
            text="⏰ Create forensic timeline",
            variable=self.create_timeline_var,
            font=ctk.CTkFont(size=12)
        )
        timeline_checkbox.pack(anchor="w", padx=20, pady=2)
        
        # Analysis button
        self.analyze_button = ctk.CTkButton(
            options_frame,
            text="🔬 Start Analysis",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40,
            command=self.run_android_analysis
        )
        self.analyze_button.pack(padx=10, pady=15)
        
        # Console output for analysis
        console_frame = ctk.CTkFrame(content_frame)
        console_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        console_frame.grid_columnconfigure(0, weight=1)
        console_frame.grid_rowconfigure(1, weight=1)
        
        console_label = ctk.CTkLabel(
            console_frame,
            text="Analysis Console:",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        console_label.grid(row=0, column=0, sticky="w", padx=10, pady=(10, 5))
        
        self.analysis_console = ctk.CTkTextbox(
            console_frame,
            font=ctk.CTkFont(size=11),
            wrap="word"
        )
        self.analysis_console.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.analysis_console.configure(state="disabled")

    def browse_ab_file(self):
        """Browse for Android backup file and analyze encryption"""
        filename = filedialog.askopenfilename(
            title="Select Android Backup File",
            filetypes=[("Android Backup", "*.ab"), ("All Files", "*.*")]
        )
        if filename:
            self.ab_file_var.set(filename)
            
            # Analyze the backup file for encryption
            self.analyze_ab_file_encryption(filename)
    
    def analyze_ab_file_encryption(self, backup_file_path):
        """Analyze selected .ab file for encryption and provide user feedback"""
        try:
            analyzer = AndroidBackupAnalyzer()
            analysis_result = analyzer.analyze_backup_file(backup_file_path)
            
            if analysis_result['is_valid']:
                if analysis_result['is_encrypted']:
                    # Show encryption detected message
                    messagebox.showinfo(
                        "Encrypted Backup Detected", 
                        f"Backup Information:\n"
                        f"• Version: {analysis_result['version']}\n"
                        f"• Compression: {analysis_result['compression']}\n"
                        f"• Status: Encrypted (password required)\n\n"
                        f"Please enter the backup password in the field below before running analysis.",
                        parent=self
                    )
                    # Clear any existing password and focus on password field
                    self.backup_password_var.set("")
                    self.backup_password_entry.focus()
                else:
                    # Show unencrypted backup info
                    messagebox.showinfo(
                        "Backup Analysis Complete",
                        f"Backup Information:\n"
                        f"• Version: {analysis_result['version']}\n" 
                        f"• Compression: {analysis_result['compression']}\n"
                        f"• Status: Unencrypted (no password required)\n\n"
                        f"Ready for analysis.",
                        parent=self
                    )
                    # Clear password field for unencrypted backups
                    self.backup_password_var.set("")
            else:
                # Show error for invalid backup
                messagebox.showerror(
                    "Invalid Backup File",
                    f"The selected file is not a valid Android backup:\n{analysis_result.get('error', 'Unknown error')}",
                    parent=self
                )
                
        except Exception as e:
            print(f"Error analyzing backup: {e}")
            messagebox.showwarning(
                "Analysis Warning", 
                f"Could not fully analyze backup file:\n{str(e)}\n\nAnalysis will still be attempted.",
                parent=self
            )

    def browse_apk_dir(self):
        """Browse for APK data directory"""
        dirname = filedialog.askdirectory(
            title="Select APK Data Directory"
        )
        if dirname:
            self.apk_dir_var.set(dirname)

    def browse_analysis_output(self):
        """Browse for analysis output directory"""
        dirname = filedialog.askdirectory(
            title="Select Output Directory for Analysis"
        )
        if dirname:
            self.analysis_output_var.set(dirname)

    def append_analysis_status(self, msg):
        """Append message to analysis console"""
        self.analysis_console.configure(state="normal")
        self.analysis_console.insert("end", f"{datetime.now().strftime('%H:%M:%S')}  {msg}\n")
        self.analysis_console.see("end")
        self.analysis_console.configure(state="disabled")

    def run_android_analysis(self):
        """Run comprehensive Android data analysis"""
        # Validate inputs
        ab_file = self.ab_file_var.get()
        apk_dir = self.apk_dir_var.get()
        output_dir = self.analysis_output_var.get()
        
        # Check if at least one valid input is provided
        valid_ab_file = ab_file and os.path.exists(ab_file)
        valid_apk_dir = apk_dir and os.path.exists(apk_dir)
        
        if not (valid_ab_file or valid_apk_dir):
            messagebox.showerror("No Valid Input", "Please provide at least one valid input: Android backup (.ab) file or APK data directory.")
            return
        
        # Auto-enable processing options based on available valid inputs if none are selected
        if not (self.extract_ab_var.get() or self.parse_apk_var.get()):
            if valid_ab_file:
                self.extract_ab_var.set(True)
                self.append_analysis_status("Auto-enabled AB extraction based on provided AB file")
            if valid_apk_dir:
                self.parse_apk_var.set(True)
                self.append_analysis_status("Auto-enabled APK parsing based on provided APK directory")
        
        # Validate specific requirements only if the corresponding option is selected
        if self.extract_ab_var.get() and not valid_ab_file:
            messagebox.showerror("File Not Found", "Please select a valid Android backup (.ab) file for extraction.")
            return
        
        # Validate APK directory if parsing is enabled
        if self.parse_apk_var.get() and not valid_apk_dir:
            messagebox.showerror("Directory Not Found", "Please select a valid APK data directory for parsing.")
            return
        
        # Validate output directory
        if not output_dir:
            messagebox.showwarning("Output Directory Required", "Please select an output directory.")
            return
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Disable button during analysis
        self.analyze_button.configure(state="disabled")
        self.append_analysis_status("🔬 Starting Android forensic analysis...")
        
        def analysis_thread():
            try:
                # Get case number from main app
                main_app = self.winfo_toplevel()
                case_number = ""
                if hasattr(main_app, 'get_case_number'):
                    case_number = main_app.get_case_number()
                
                # Get backup password from UI
                backup_password = self.backup_password_var.get().strip() or None
                
                # Create timestamped analysis directory
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                analysis_dir = os.path.join(output_dir, f"Android_Analysis_{case_number}_{timestamp}")
                os.makedirs(analysis_dir, exist_ok=True)
                
                self.after(0, lambda: self.append_analysis_status(f"📁 Created analysis directory: {analysis_dir}"))
                
                # Extract Android backup if selected
                ab_extracted_dir = None
                if self.extract_ab_var.get() and ab_file:
                    if backup_password:
                        self.after(0, lambda: self.append_analysis_status("� Extracting password-protected Android backup file..."))
                    else:
                        self.after(0, lambda: self.append_analysis_status("�📦 Extracting Android backup file..."))
                    ab_extracted_dir = os.path.join(analysis_dir, "ab_extracted")
                    
                    # Find abe.jar using improved path resolution
                    from src.Droid_backup.android_backup_collector import ArsenicTriageCollector
                    temp_collector = ArsenicTriageCollector()
                    abe_jar = temp_collector.get_abe_jar_path()
                    
                    if abe_jar is None:
                        self.after(0, lambda: self.append_analysis_status("❌ abe.jar not found in any expected location"))
                        return
                    
                    # Extract backup with password support
                    extractor = BackupExtractor(ab_file, abe_jar, ab_extracted_dir, password=backup_password)
                    if extractor.extract():
                        self.after(0, lambda: self.append_analysis_status("✅ Android backup extracted successfully"))
                        self.after(0, lambda: self.append_analysis_status(f"📂 Backup contents saved to: {ab_extracted_dir}"))
                    else:
                        if backup_password:
                            self.after(0, lambda: self.append_analysis_status("❌ Failed to extract Android backup - please verify password"))
                        else:
                            self.after(0, lambda: self.append_analysis_status("❌ Failed to extract Android backup - backup may be password-protected"))
                        ab_extracted_dir = None
                
                # Parse APK data if selected
                parsed_apk_dir = None
                if self.parse_apk_var.get() and apk_dir:
                    self.after(0, lambda: self.append_analysis_status("📱 Parsing APK collected data..."))
                    parsed_apk_dir = os.path.join(analysis_dir, "apk_parsed")
                    
                    try:
                        parser = ForensicDataParser(apk_dir, parsed_apk_dir)
                        parser.parse_all()
                        self.after(0, lambda: self.append_analysis_status("✅ APK data parsed successfully"))
                        self.after(0, lambda: self.append_analysis_status(f"📊 Parsed data saved to: {parsed_apk_dir}"))
                    except Exception as e:
                        self.after(0, lambda: self.append_analysis_status(f"❌ Failed to parse APK data: {str(e)}"))
                        parsed_apk_dir = None
                
                # Generate comprehensive forensic report
                if self.generate_report_var.get():
                    self.after(0, lambda: self.append_analysis_status("📊 Generating comprehensive forensic report..."))
                    report_path = self.generate_forensic_report(analysis_dir, case_number, ab_extracted_dir, parsed_apk_dir)
                    if report_path:
                        self.after(0, lambda: self.append_analysis_status(f"📄 Forensic report generated: {report_path}"))
                
                # Create forensic timeline
                if self.create_timeline_var.get():
                    self.after(0, lambda: self.append_analysis_status("⏰ Creating forensic timeline..."))
                    timeline_path = self.create_forensic_timeline(analysis_dir, ab_extracted_dir, parsed_apk_dir)
                    if timeline_path:
                        self.after(0, lambda: self.append_analysis_status(f"📅 Timeline created: {timeline_path}"))
                
                self.after(0, lambda: self.append_analysis_status("🎉 Android forensic analysis completed successfully!"))
                self.after(0, lambda: self.append_analysis_status(f"📁 All results saved to: {analysis_dir}"))
                
            except Exception as e:
                self.after(0, lambda: self.append_analysis_status(f"❌ Analysis error: {str(e)}"))
            finally:
                self.after(0, lambda: self.analyze_button.configure(state="normal"))
        
        # Start analysis in background thread
        threading.Thread(target=analysis_thread, daemon=True).start()

    def generate_forensic_report(self, analysis_dir, case_number, ab_dir, apk_dir):
        """Generate a comprehensive forensic report"""
        try:
            report_path = os.path.join(analysis_dir, "Forensic_Report.html")
            
            # Collect all available data
            report_data = {
                'case_number': case_number,
                'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'ab_dir': ab_dir,
                'apk_dir': apk_dir,
                'summary': {}
            }
            
            # Analyze APK data if available
            if apk_dir and os.path.exists(apk_dir):
                report_data['apk_analysis'] = self.analyze_apk_data(apk_dir)
            
            # Analyze AB extracted data if available
            if ab_dir and os.path.exists(ab_dir):
                report_data['ab_analysis'] = self.analyze_ab_data(ab_dir)
            
            # Generate HTML report
            html_content = self.create_html_report(report_data, apk_dir, ab_dir)
            
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            return report_path
            
        except Exception as e:
            self.append_analysis_status(f"❌ Error generating report: {str(e)}")
            return None

    def analyze_apk_data(self, apk_dir):
        """Analyze parsed APK data and return comprehensive summary"""
        analysis = {}
        
        try:
            import csv
            from collections import Counter
            
            # Analyze SMS data with detailed breakdown
            sms_file = os.path.join(apk_dir, "sms_messages.csv")
            if os.path.exists(sms_file):
                sms_analysis = {
                    'total_count': 0,
                    'incoming': 0,
                    'outgoing': 0,
                    'top_contacts': [],
                    'date_range': {'earliest': None, 'latest': None},
                    'monthly_distribution': Counter(),
                    'thread_count': 0
                }
                
                contact_counter = Counter()
                thread_ids = set()
                dates = []
                
                with open(sms_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        sms_analysis['total_count'] += 1
                        
                        # Count by type
                        sms_type = row.get('sms_type_label', '').lower()
                        if 'incoming' in sms_type:
                            sms_analysis['incoming'] += 1
                        elif 'outgoing' in sms_type:
                            sms_analysis['outgoing'] += 1
                        
                        # Track contacts
                        address = row.get('address', 'Unknown')
                        if address != 'Unknown':
                            contact_counter[address] += 1
                        
                        # Track threads
                        thread_id = row.get('thread_id')
                        if thread_id:
                            thread_ids.add(thread_id)
                        
                        # Track dates
                        date_str = row.get('date', '')
                        if date_str:
                            try:
                                # Parse the timestamp and extract year-month
                                import datetime
                                # Handle different date formats
                                if '/' in date_str:
                                    dt = datetime.datetime.strptime(date_str.split()[0], '%Y/%m/%d')
                                else:
                                    # Handle timestamp format
                                    timestamp = int(date_str) if date_str.isdigit() else int(date_str) // 1000
                                    dt = datetime.datetime.fromtimestamp(timestamp)
                                
                                dates.append(dt)
                                month_key = dt.strftime('%Y-%m')
                                sms_analysis['monthly_distribution'][month_key] += 1
                            except:
                                pass
                
                # Process collected data
                sms_analysis['top_contacts'] = contact_counter.most_common(10)
                sms_analysis['thread_count'] = len(thread_ids)
                
                if dates:
                    dates.sort()
                    sms_analysis['date_range']['earliest'] = dates[0].strftime('%Y-%m-%d')
                    sms_analysis['date_range']['latest'] = dates[-1].strftime('%Y-%m-%d')
                
                analysis['sms'] = sms_analysis
            
            # Analyze call logs with detailed breakdown
            calls_file = os.path.join(apk_dir, "call_logs.csv")
            if os.path.exists(calls_file):
                calls_analysis = {
                    'total_count': 0,
                    'incoming': 0,
                    'outgoing': 0,
                    'missed': 0,
                    'rejected': 0,
                    'total_duration': 0,
                    'avg_duration': 0,
                    'top_contacts': [],
                    'date_range': {'earliest': None, 'latest': None},
                    'longest_call': {'duration': 0, 'contact': '', 'date': ''},
                    'call_frequency': Counter()
                }
                
                contact_counter = Counter()
                durations = []
                dates = []
                longest_call = {'duration': 0, 'contact': '', 'date': ''}
                
                with open(calls_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        calls_analysis['total_count'] += 1
                        
                        # Count by type
                        call_type = row.get('call_type_label', '').lower()
                        if 'incoming' in call_type:
                            calls_analysis['incoming'] += 1
                        elif 'outgoing' in call_type:
                            calls_analysis['outgoing'] += 1
                        elif 'missed' in call_type:
                            calls_analysis['missed'] += 1
                        elif 'rejected' in call_type:
                            calls_analysis['rejected'] += 1
                        
                        # Track duration
                        duration = row.get('duration', '0')
                        try:
                            duration_int = int(duration)
                            durations.append(duration_int)
                            calls_analysis['total_duration'] += duration_int
                            
                            # Track longest call
                            if duration_int > longest_call['duration']:
                                longest_call['duration'] = duration_int
                                longest_call['contact'] = row.get('number', 'Unknown')
                                longest_call['date'] = row.get('date', '')
                        except:
                            pass
                        
                        # Track contacts
                        number = row.get('number', 'Unknown')
                        if number != 'Unknown':
                            contact_counter[number] += 1
                        
                        # Track dates for frequency analysis
                        date_str = row.get('date', '')
                        if date_str:
                            try:
                                if '/' in date_str:
                                    dt = datetime.datetime.strptime(date_str.split()[0], '%Y/%m/%d')
                                else:
                                    timestamp = int(date_str) if date_str.isdigit() else int(date_str) // 1000
                                    dt = datetime.datetime.fromtimestamp(timestamp)
                                
                                dates.append(dt)
                                day_key = dt.strftime('%A')  # Day of week
                                calls_analysis['call_frequency'][day_key] += 1
                            except:
                                pass
                
                # Process collected data
                calls_analysis['top_contacts'] = contact_counter.most_common(10)
                calls_analysis['longest_call'] = longest_call
                
                if durations:
                    calls_analysis['avg_duration'] = sum(durations) / len(durations)
                
                if dates:
                    dates.sort()
                    calls_analysis['date_range']['earliest'] = dates[0].strftime('%Y-%m-%d')
                    calls_analysis['date_range']['latest'] = dates[-1].strftime('%Y-%m-%d')
                
                analysis['calls'] = calls_analysis
            
            # Analyze contacts
            contacts_file = os.path.join(apk_dir, "contacts.csv")
            if os.path.exists(contacts_file):
                contacts_analysis = {
                    'total_count': 0,
                    'with_phone': 0,
                    'sources': Counter()
                }
                
                with open(contacts_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        contacts_analysis['total_count'] += 1
                        
                        if row.get('has_phone_number', '').lower() in ['true', '1']:
                            contacts_analysis['with_phone'] += 1
                        
                        source = row.get('source', 'Unknown')
                        contacts_analysis['sources'][source] += 1
                
                analysis['contacts'] = contacts_analysis
            
            # Analyze calendar events
            calendar_file = os.path.join(apk_dir, "calendar_events.csv")
            if os.path.exists(calendar_file):
                calendar_analysis = {
                    'total_count': 0,
                    'upcoming': 0,
                    'past': 0,
                    'calendars': Counter(),
                    'locations': []
                }
                
                current_date = datetime.datetime.now()
                
                with open(calendar_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        calendar_analysis['total_count'] += 1
                        
                        # Track calendar sources
                        calendar_id = row.get('calendar_id', 'Unknown')
                        calendar_analysis['calendars'][calendar_id] += 1
                        
                        # Track locations
                        location = row.get('location', '').strip()
                        if location and location not in calendar_analysis['locations']:
                            calendar_analysis['locations'].append(location)
                        
                        # Determine if past or upcoming (simplified)
                        start_date = row.get('start_date', '')
                        if start_date:
                            try:
                                if '/' in start_date:
                                    event_date = datetime.datetime.strptime(start_date.split()[0], '%Y/%m/%d')
                                    if event_date > current_date:
                                        calendar_analysis['upcoming'] += 1
                                    else:
                                        calendar_analysis['past'] += 1
                            except:
                                pass
                
                # Limit locations list
                calendar_analysis['locations'] = calendar_analysis['locations'][:20]
                analysis['calendar'] = calendar_analysis
                
        except Exception as e:
            analysis['error'] = str(e)
        
        return analysis

    def analyze_ab_data(self, ab_dir):
        """Analyze extracted AB data and return summary"""
        analysis = {}
        
        try:
            # Count files and directories
            total_files = 0
            total_dirs = 0
            app_dirs = []
            
            for root, dirs, files in os.walk(ab_dir):
                total_dirs += len(dirs)
                total_files += len(files)
                
                # Look for app directories
                if 'apps' in root:
                    for d in dirs:
                        if d.startswith('com.') or d.startswith('org.'):
                            app_dirs.append(d)
            
            analysis['total_files'] = total_files
            analysis['total_directories'] = total_dirs
            analysis['app_directories'] = len(set(app_dirs))
            analysis['sample_apps'] = list(set(app_dirs))[:10]  # First 10 unique apps
            
        except Exception as e:
            analysis['error'] = str(e)
        
        return analysis

    def add_sample_sms_data(self, apk_dir):
        """Add paginated, searchable SMS messages table to the HTML report"""
        if not apk_dir:
            return ""
            
        sms_file = os.path.join(apk_dir, "sms_messages.csv")
        if not os.path.exists(sms_file):
            return ""
        
        html = """
        <h4>SMS Messages Data</h4>
        <div id="sms-container" style="border: 1px solid #ddd; border-radius: 5px; padding: 15px; background: #f9f9f9;">
            <!-- Search and pagination controls -->
            <div style="margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <input type="text" id="sms-search" placeholder="Search messages..." 
                           style="padding: 8px; border: 1px solid #ccc; border-radius: 3px; width: 300px;">
                    <button onclick="searchSMS()" style="padding: 8px 15px; margin-left: 5px; background: #3498db; color: white; border: none; border-radius: 3px; cursor: pointer;">Search</button>
                    <button onclick="clearSMSSearch()" style="padding: 8px 15px; margin-left: 5px; background: #95a5a6; color: white; border: none; border-radius: 3px; cursor: pointer;">Clear</button>
                </div>
                <div id="sms-pagination-info" style="font-weight: bold;"></div>
            </div>
            
            <!-- Data table -->
            <div style="overflow-x: auto;">
                <table id="sms-table" style="width: 100%; border-collapse: collapse; font-size: 12px;">
                    <thead style="background: #34495e; color: white;">
                        <tr>
                            <th style="padding: 8px; border: 1px solid #ddd; cursor: pointer;" onclick="sortSMS('type')">Type</th>
                            <th style="padding: 8px; border: 1px solid #ddd; cursor: pointer;" onclick="sortSMS('address')">Contact</th>
                            <th style="padding: 8px; border: 1px solid #ddd; cursor: pointer;" onclick="sortSMS('date')">Date</th>
                            <th style="padding: 8px; border: 1px solid #ddd; max-width: 300px;">Message</th>
                        </tr>
                    </thead>
                    <tbody id="sms-tbody">
                        <!-- Data will be populated by JavaScript -->
                    </tbody>
                </table>
            </div>
            
            <!-- Pagination controls -->
            <div id="sms-pagination" style="margin-top: 15px; text-align: center;">
                <!-- Pagination buttons will be populated by JavaScript -->
            </div>
        </div>
        
        <script>
        // SMS data and pagination variables
        let smsData = [];
        let filteredSmsData = [];
        let currentSmsPage = 1;
        const smsRecordsPerPage = 15;
        let smsSortColumn = 'date';
        let smsSortDirection = 'desc';
        
        // Load SMS data
        function loadSMSData() {
            // Data will be populated by Python
            smsData = ["""
        
        try:
            import csv
            messages = []
            
            with open(sms_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    messages.append(row)
            
            # Convert messages to JavaScript array format
            for i, msg in enumerate(messages):
                date = msg.get('date', 'Unknown')
                address = msg.get('address', 'Unknown')
                body = msg.get('body', 'No content')
                msg_type = msg.get('sms_type_label', 'Unknown')
                
                # Escape JavaScript strings
                address = address.replace("'", "\\'").replace('"', '\\"').replace('\n', '\\n')
                body = body.replace("'", "\\'").replace('"', '\\"').replace('\n', '\\n')
                msg_type = msg_type.replace("'", "\\'").replace('"', '\\"')
                
                # Truncate long messages for display
                display_body = body[:100] + "..." if len(body) > 100 else body
                
                html += f"""
                {{'type': '{msg_type}', 'address': '{address}', 'date': '{date}', 'body': '{display_body}', 'fullBody': '{body}'}},"""
            
            # Remove trailing comma if there are messages
            if messages:
                html = html.rstrip(',')
                
        except Exception as e:
            html += f"// Error loading SMS data: {str(e)}"
        
        html += """
            ];
            filteredSmsData = [...smsData];
            sortSMS(smsSortColumn);
            displaySMSPage(1);
        }
        
        // Search SMS messages
        function searchSMS() {
            const searchTerm = document.getElementById('sms-search').value.toLowerCase();
            if (searchTerm === '') {
                filteredSmsData = [...smsData];
            } else {
                filteredSmsData = smsData.filter(msg => 
                    msg.type.toLowerCase().includes(searchTerm) ||
                    msg.address.toLowerCase().includes(searchTerm) ||
                    msg.body.toLowerCase().includes(searchTerm) ||
                    msg.date.toLowerCase().includes(searchTerm)
                );
            }
            currentSmsPage = 1;
            displaySMSPage(1);
        }
        
        // Clear SMS search
        function clearSMSSearch() {
            document.getElementById('sms-search').value = '';
            filteredSmsData = [...smsData];
            currentSmsPage = 1;
            displaySMSPage(1);
        }
        
        // Sort SMS data
        function sortSMS(column) {
            if (smsSortColumn === column) {
                smsSortDirection = smsSortDirection === 'asc' ? 'desc' : 'asc';
            } else {
                smsSortColumn = column;
                smsSortDirection = 'asc';
            }
            
            filteredSmsData.sort((a, b) => {
                let aVal = a[column];
                let bVal = b[column];
                
                if (column === 'date') {
                    aVal = new Date(aVal);
                    bVal = new Date(bVal);
                }
                
                if (aVal < bVal) return smsSortDirection === 'asc' ? -1 : 1;
                if (aVal > bVal) return smsSortDirection === 'asc' ? 1 : -1;
                return 0;
            });
            
            displaySMSPage(currentSmsPage);
        }
        
        // Display SMS page
        function displaySMSPage(page) {
            currentSmsPage = page;
            const startIndex = (page - 1) * smsRecordsPerPage;
            const endIndex = startIndex + smsRecordsPerPage;
            const pageData = filteredSmsData.slice(startIndex, endIndex);
            
            const tbody = document.getElementById('sms-tbody');
            tbody.innerHTML = '';
            
            pageData.forEach(msg => {
                const row = tbody.insertRow();
                const typeColor = msg.type.toLowerCase().includes('incoming') ? '#e6f3ff' : '#fff2e6';
                row.style.backgroundColor = typeColor;
                
                row.insertCell(0).innerHTML = msg.type;
                row.insertCell(1).innerHTML = msg.address;
                row.insertCell(2).innerHTML = msg.date;
                const bodyCell = row.insertCell(3);
                bodyCell.innerHTML = msg.body;
                bodyCell.style.maxWidth = '300px';
                bodyCell.style.wordWrap = 'break-word';
                bodyCell.title = msg.fullBody; // Show full message on hover
            });
            
            updateSMSPagination();
        }
        
        // Update SMS pagination
        function updateSMSPagination() {
            const totalPages = Math.ceil(filteredSmsData.length / smsRecordsPerPage);
            const startRecord = (currentSmsPage - 1) * smsRecordsPerPage + 1;
            const endRecord = Math.min(currentSmsPage * smsRecordsPerPage, filteredSmsData.length);
            
            document.getElementById('sms-pagination-info').innerHTML = 
                `Showing ${startRecord}-${endRecord} of ${filteredSmsData.length} messages (Page ${currentSmsPage} of ${totalPages})`;
            
            let paginationHTML = '';
            
            // Previous button
            if (currentSmsPage > 1) {
                paginationHTML += `<button onclick="displaySMSPage(${currentSmsPage - 1})" style="padding: 5px 10px; margin: 2px; background: #3498db; color: white; border: none; border-radius: 3px; cursor: pointer;">Previous</button>`;
            }
            
            // Page numbers
            for (let i = Math.max(1, currentSmsPage - 2); i <= Math.min(totalPages, currentSmsPage + 2); i++) {
                const isActive = i === currentSmsPage;
                const bgColor = isActive ? '#2c3e50' : '#3498db';
                paginationHTML += `<button onclick="displaySMSPage(${i})" style="padding: 5px 10px; margin: 2px; background: ${bgColor}; color: white; border: none; border-radius: 3px; cursor: pointer;">${i}</button>`;
            }
            
            // Next button
            if (currentSmsPage < totalPages) {
                paginationHTML += `<button onclick="displaySMSPage(${currentSmsPage + 1})" style="padding: 5px 10px; margin: 2px; background: #3498db; color: white; border: none; border-radius: 3px; cursor: pointer;">Next</button>`;
            }
            
            document.getElementById('sms-pagination').innerHTML = paginationHTML;
        }
        
        // Initialize SMS data when page loads
        loadSMSData();
        </script>
        """
        
        return html

    def add_sample_call_data(self, apk_dir):
        """Add paginated, searchable call logs table to the HTML report"""
        if not apk_dir:
            return ""
            
        calls_file = os.path.join(apk_dir, "call_logs.csv")
        if not os.path.exists(calls_file):
            return ""
        
        html = """
        <h4>Call Logs Data</h4>
        <div id="calls-container" style="border: 1px solid #ddd; border-radius: 5px; padding: 15px; background: #f9f9f9;">
            <!-- Search and pagination controls -->
            <div style="margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <input type="text" id="calls-search" placeholder="Search calls..." 
                           style="padding: 8px; border: 1px solid #ccc; border-radius: 3px; width: 300px;">
                    <button onclick="searchCalls()" style="padding: 8px 15px; margin-left: 5px; background: #3498db; color: white; border: none; border-radius: 3px; cursor: pointer;">Search</button>
                    <button onclick="clearCallsSearch()" style="padding: 8px 15px; margin-left: 5px; background: #95a5a6; color: white; border: none; border-radius: 3px; cursor: pointer;">Clear</button>
                </div>
                <div id="calls-pagination-info" style="font-weight: bold;"></div>
            </div>
            
            <!-- Data table -->
            <div style="overflow-x: auto;">
                <table id="calls-table" style="width: 100%; border-collapse: collapse; font-size: 12px;">
                    <thead style="background: #34495e; color: white;">
                        <tr>
                            <th style="padding: 8px; border: 1px solid #ddd; cursor: pointer;" onclick="sortCalls('type')">Type</th>
                            <th style="padding: 8px; border: 1px solid #ddd; cursor: pointer;" onclick="sortCalls('number')">Number</th>
                            <th style="padding: 8px; border: 1px solid #ddd; cursor: pointer;" onclick="sortCalls('date')">Date</th>
                            <th style="padding: 8px; border: 1px solid #ddd; cursor: pointer;" onclick="sortCalls('duration')">Duration</th>
                        </tr>
                    </thead>
                    <tbody id="calls-tbody">
                        <!-- Data will be populated by JavaScript -->
                    </tbody>
                </table>
            </div>
            
            <!-- Pagination controls -->
            <div id="calls-pagination" style="margin-top: 15px; text-align: center;">
                <!-- Pagination buttons will be populated by JavaScript -->
            </div>
        </div>
        
        <script>
        // Calls data and pagination variables
        let callsData = [];
        let filteredCallsData = [];
        let currentCallsPage = 1;
        const callsRecordsPerPage = 15;
        let callsSortColumn = 'date';
        let callsSortDirection = 'desc';
        
        // Load calls data
        function loadCallsData() {
            // Data will be populated by Python
            callsData = ["""
        
        try:
            import csv
            calls = []
            
            with open(calls_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    calls.append(row)
            
            # Convert calls to JavaScript array format
            for i, call in enumerate(calls):
                date = call.get('date', 'Unknown')
                number = call.get('number', 'Unknown')
                call_type = call.get('call_type_label', 'Unknown')
                duration = call.get('duration', '0')
                
                # Format duration
                try:
                    duration_sec = int(duration)
                    if duration_sec > 60:
                        minutes = duration_sec // 60
                        seconds = duration_sec % 60
                        duration_str = f"{minutes}m {seconds}s"
                    else:
                        duration_str = f"{duration_sec}s"
                except:
                    duration_str = duration
                
                # Escape JavaScript strings
                number = number.replace("'", "\\'").replace('"', '\\"')
                call_type = call_type.replace("'", "\\'").replace('"', '\\"')
                
                html += f"""
                {{'type': '{call_type}', 'number': '{number}', 'date': '{date}', 'duration': '{duration_str}', 'durationSeconds': {duration}}},"""
            
            # Remove trailing comma if there are calls
            if calls:
                html = html.rstrip(',')
                
        except Exception as e:
            html += f"// Error loading calls data: {str(e)}"
        
        html += """
            ];
            filteredCallsData = [...callsData];
            sortCalls(callsSortColumn);
            displayCallsPage(1);
        }
        
        // Search calls
        function searchCalls() {
            const searchTerm = document.getElementById('calls-search').value.toLowerCase();
            if (searchTerm === '') {
                filteredCallsData = [...callsData];
            } else {
                filteredCallsData = callsData.filter(call => 
                    call.type.toLowerCase().includes(searchTerm) ||
                    call.number.toLowerCase().includes(searchTerm) ||
                    call.date.toLowerCase().includes(searchTerm) ||
                    call.duration.toLowerCase().includes(searchTerm)
                );
            }
            currentCallsPage = 1;
            displayCallsPage(1);
        }
        
        // Clear calls search
        function clearCallsSearch() {
            document.getElementById('calls-search').value = '';
            filteredCallsData = [...callsData];
            currentCallsPage = 1;
            displayCallsPage(1);
        }
        
        // Sort calls data
        function sortCalls(column) {
            if (callsSortColumn === column) {
                callsSortDirection = callsSortDirection === 'asc' ? 'desc' : 'asc';
            } else {
                callsSortColumn = column;
                callsSortDirection = 'asc';
            }
            
            filteredCallsData.sort((a, b) => {
                let aVal = a[column];
                let bVal = b[column];
                
                if (column === 'date') {
                    aVal = new Date(aVal);
                    bVal = new Date(bVal);
                } else if (column === 'duration') {
                    aVal = a.durationSeconds || 0;
                    bVal = b.durationSeconds || 0;
                }
                
                if (aVal < bVal) return callsSortDirection === 'asc' ? -1 : 1;
                if (aVal > bVal) return callsSortDirection === 'asc' ? 1 : -1;
                return 0;
            });
            
            displayCallsPage(currentCallsPage);
        }
        
        // Display calls page
        function displayCallsPage(page) {
            currentCallsPage = page;
            const startIndex = (page - 1) * callsRecordsPerPage;
            const endIndex = startIndex + callsRecordsPerPage;
            const pageData = filteredCallsData.slice(startIndex, endIndex);
            
            const tbody = document.getElementById('calls-tbody');
            tbody.innerHTML = '';
            
            pageData.forEach(call => {
                const row = tbody.insertRow();
                
                // Color code by call type
                let bgColor = '#ffffff';
                if (call.type.toLowerCase().includes('incoming')) {
                    bgColor = '#e6f3ff';
                } else if (call.type.toLowerCase().includes('outgoing')) {
                    bgColor = '#f0f8e6';
                } else if (call.type.toLowerCase().includes('missed')) {
                    bgColor = '#ffe6e6';
                }
                row.style.backgroundColor = bgColor;
                
                row.insertCell(0).innerHTML = call.type;
                row.insertCell(1).innerHTML = call.number;
                row.insertCell(2).innerHTML = call.date;
                row.insertCell(3).innerHTML = call.duration;
            });
            
            updateCallsPagination();
        }
        
        // Update calls pagination
        function updateCallsPagination() {
            const totalPages = Math.ceil(filteredCallsData.length / callsRecordsPerPage);
            const startRecord = (currentCallsPage - 1) * callsRecordsPerPage + 1;
            const endRecord = Math.min(currentCallsPage * callsRecordsPerPage, filteredCallsData.length);
            
            document.getElementById('calls-pagination-info').innerHTML = 
                `Showing ${startRecord}-${endRecord} of ${filteredCallsData.length} calls (Page ${currentCallsPage} of ${totalPages})`;
            
            let paginationHTML = '';
            
            // Previous button
            if (currentCallsPage > 1) {
                paginationHTML += `<button onclick="displayCallsPage(${currentCallsPage - 1})" style="padding: 5px 10px; margin: 2px; background: #3498db; color: white; border: none; border-radius: 3px; cursor: pointer;">Previous</button>`;
            }
            
            // Page numbers
            for (let i = Math.max(1, currentCallsPage - 2); i <= Math.min(totalPages, currentCallsPage + 2); i++) {
                const isActive = i === currentCallsPage;
                const bgColor = isActive ? '#2c3e50' : '#3498db';
                paginationHTML += `<button onclick="displayCallsPage(${i})" style="padding: 5px 10px; margin: 2px; background: ${bgColor}; color: white; border: none; border-radius: 3px; cursor: pointer;">${i}</button>`;
            }
            
            // Next button
            if (currentCallsPage < totalPages) {
                paginationHTML += `<button onclick="displayCallsPage(${currentCallsPage + 1})" style="padding: 5px 10px; margin: 2px; background: #3498db; color: white; border: none; border-radius: 3px; cursor: pointer;">Next</button>`;
            }
            
            document.getElementById('calls-pagination').innerHTML = paginationHTML;
        }
        
        // Initialize calls data when page loads
        loadCallsData();
        </script>
        """
        
        return html

    def add_sample_contacts_data(self, apk_dir):
        """Add paginated, searchable contacts table to the HTML report"""
        if not apk_dir:
            return ""
            
        contacts_file = os.path.join(apk_dir, "contacts.csv")
        if not os.path.exists(contacts_file):
            return ""
        
        html = """
        <h4>Contacts Data</h4>
        <div id="contacts-container" style="border: 1px solid #ddd; border-radius: 5px; padding: 15px; background: #f9f9f9;">
            <!-- Search and pagination controls -->
            <div style="margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <input type="text" id="contacts-search" placeholder="Search contacts..." 
                           style="padding: 8px; border: 1px solid #ccc; border-radius: 3px; width: 300px;">
                    <button onclick="searchContacts()" style="padding: 8px 15px; margin-left: 5px; background: #3498db; color: white; border: none; border-radius: 3px; cursor: pointer;">Search</button>
                    <button onclick="clearContactsSearch()" style="padding: 8px 15px; margin-left: 5px; background: #95a5a6; color: white; border: none; border-radius: 3px; cursor: pointer;">Clear</button>
                </div>
                <div id="contacts-pagination-info" style="font-weight: bold;"></div>
            </div>
            
            <!-- Data table -->
            <div style="overflow-x: auto;">
                <table id="contacts-table" style="width: 100%; border-collapse: collapse; font-size: 12px;">
                    <thead style="background: #34495e; color: white;">
                        <tr>
                            <th style="padding: 8px; border: 1px solid #ddd; cursor: pointer;" onclick="sortContacts('name')">Name</th>
                            <th style="padding: 8px; border: 1px solid #ddd; cursor: pointer;" onclick="sortContacts('phone')">Phone Number</th>
                            <th style="padding: 8px; border: 1px solid #ddd; cursor: pointer;" onclick="sortContacts('email')">Email</th>
                            <th style="padding: 8px; border: 1px solid #ddd; cursor: pointer;" onclick="sortContacts('source')">Source</th>
                        </tr>
                    </thead>
                    <tbody id="contacts-tbody">
                        <!-- Data will be populated by JavaScript -->
                    </tbody>
                </table>
            </div>
            
            <!-- Pagination controls -->
            <div id="contacts-pagination" style="margin-top: 15px; text-align: center;">
                <!-- Pagination buttons will be populated by JavaScript -->
            </div>
        </div>
        
        <script>
        // Contacts data and pagination variables
        let contactsData = [];
        let filteredContactsData = [];
        let currentContactsPage = 1;
        const contactsRecordsPerPage = 15;
        let contactsSortColumn = 'name';
        let contactsSortDirection = 'asc';
        
        // Load contacts data
        function loadContactsData() {
            // Data will be populated by Python
            contactsData = ["""
        
        try:
            import csv
            contacts = []
            
            with open(contacts_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    contacts.append(row)
            
            # Convert contacts to JavaScript array format
            for i, contact in enumerate(contacts):
                name = contact.get('display_name', 'Unknown')
                phone = contact.get('phone_number', 'N/A')
                email = contact.get('email', 'N/A')
                source = contact.get('source', 'Unknown')
                
                # Escape JavaScript strings
                name = name.replace("'", "\\'").replace('"', '\\"').replace('\n', ' ')
                phone = phone.replace("'", "\\'").replace('"', '\\"')
                email = email.replace("'", "\\'").replace('"', '\\"')
                source = source.replace("'", "\\'").replace('"', '\\"')
                
                # Truncate long entries
                if len(name) > 40:
                    name = name[:40] + "..."
                if len(email) > 40:
                    email = email[:40] + "..."
                
                html += f"""
                {{'name': '{name}', 'phone': '{phone}', 'email': '{email}', 'source': '{source}'}},"""
            
            # Remove trailing comma if there are contacts
            if contacts:
                html = html.rstrip(',')
                
        except Exception as e:
            html += f"// Error loading contacts data: {str(e)}"
        
        html += """
            ];
            filteredContactsData = [...contactsData];
            sortContacts(contactsSortColumn);
            displayContactsPage(1);
        }
        
        // Search contacts
        function searchContacts() {
            const searchTerm = document.getElementById('contacts-search').value.toLowerCase();
            if (searchTerm === '') {
                filteredContactsData = [...contactsData];
            } else {
                filteredContactsData = contactsData.filter(contact => 
                    contact.name.toLowerCase().includes(searchTerm) ||
                    contact.phone.toLowerCase().includes(searchTerm) ||
                    contact.email.toLowerCase().includes(searchTerm) ||
                    contact.source.toLowerCase().includes(searchTerm)
                );
            }
            currentContactsPage = 1;
            displayContactsPage(1);
        }
        
        // Clear contacts search
        function clearContactsSearch() {
            document.getElementById('contacts-search').value = '';
            filteredContactsData = [...contactsData];
            currentContactsPage = 1;
            displayContactsPage(1);
        }
        
        // Sort contacts data
        function sortContacts(column) {
            if (contactsSortColumn === column) {
                contactsSortDirection = contactsSortDirection === 'asc' ? 'desc' : 'asc';
            } else {
                contactsSortColumn = column;
                contactsSortDirection = 'asc';
            }
            
            filteredContactsData.sort((a, b) => {
                let aVal = a[column].toLowerCase();
                let bVal = b[column].toLowerCase();
                
                if (aVal < bVal) return contactsSortDirection === 'asc' ? -1 : 1;
                if (aVal > bVal) return contactsSortDirection === 'asc' ? 1 : -1;
                return 0;
            });
            
            displayContactsPage(currentContactsPage);
        }
        
        // Display contacts page
        function displayContactsPage(page) {
            currentContactsPage = page;
            const startIndex = (page - 1) * contactsRecordsPerPage;
            const endIndex = startIndex + contactsRecordsPerPage;
            const pageData = filteredContactsData.slice(startIndex, endIndex);
            
            const tbody = document.getElementById('contacts-tbody');
            tbody.innerHTML = '';
            
            pageData.forEach(contact => {
                const row = tbody.insertRow();
                row.style.backgroundColor = '#ffffff';
                
                row.insertCell(0).innerHTML = contact.name;
                row.insertCell(1).innerHTML = contact.phone;
                row.insertCell(2).innerHTML = contact.email;
                row.insertCell(3).innerHTML = contact.source;
            });
            
            updateContactsPagination();
        }
        
        // Update contacts pagination
        function updateContactsPagination() {
            const totalPages = Math.ceil(filteredContactsData.length / contactsRecordsPerPage);
            const startRecord = (currentContactsPage - 1) * contactsRecordsPerPage + 1;
            const endRecord = Math.min(currentContactsPage * contactsRecordsPerPage, filteredContactsData.length);
            
            document.getElementById('contacts-pagination-info').innerHTML = 
                `Showing ${startRecord}-${endRecord} of ${filteredContactsData.length} contacts (Page ${currentContactsPage} of ${totalPages})`;
            
            let paginationHTML = '';
            
            // Previous button
            if (currentContactsPage > 1) {
                paginationHTML += `<button onclick="displayContactsPage(${currentContactsPage - 1})" style="padding: 5px 10px; margin: 2px; background: #3498db; color: white; border: none; border-radius: 3px; cursor: pointer;">Previous</button>`;
            }
            
            // Page numbers
            for (let i = Math.max(1, currentContactsPage - 2); i <= Math.min(totalPages, currentContactsPage + 2); i++) {
                const isActive = i === currentContactsPage;
                const bgColor = isActive ? '#2c3e50' : '#3498db';
                paginationHTML += `<button onclick="displayContactsPage(${i})" style="padding: 5px 10px; margin: 2px; background: ${bgColor}; color: white; border: none; border-radius: 3px; cursor: pointer;">${i}</button>`;
            }
            
            // Next button
            if (currentContactsPage < totalPages) {
                paginationHTML += `<button onclick="displayContactsPage(${currentContactsPage + 1})" style="padding: 5px 10px; margin: 2px; background: #3498db; color: white; border: none; border-radius: 3px; cursor: pointer;">Next</button>`;
            }
            
            document.getElementById('contacts-pagination').innerHTML = paginationHTML;
        }
        
        // Initialize contacts data when page loads
        loadContactsData();
        </script>
        """
        
        return html

    def create_html_report(self, data, apk_dir=None, ab_dir=None):
        """Create comprehensive HTML forensic report"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Android Forensic Analysis Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                .header {{ background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
                .section {{ margin: 20px 0; padding: 20px; border: 1px solid #ddd; border-radius: 8px; }}
                .summary {{ background: #ecf0f1; }}
                .data {{ background: #ffffff; }}
                .critical {{ background: #e74c3c; color: white; padding: 10px; border-radius: 5px; margin: 10px 0; }}
                .warning {{ background: #f39c12; color: white; padding: 10px; border-radius: 5px; margin: 10px 0; }}
                .info {{ background: #3498db; color: white; padding: 10px; border-radius: 5px; margin: 10px 0; }}
                table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
                th {{ background: #34495e; color: white; font-weight: bold; }}
                .highlight {{ background: #3498db; color: white; padding: 5px 10px; border-radius: 3px; }}
                .metric {{ background: #27ae60; color: white; padding: 5px 10px; border-radius: 3px; margin: 0 5px; }}
                .file-link {{ background: #9b59b6; color: white; padding: 5px 10px; border-radius: 3px; text-decoration: none; margin: 5px; display: inline-block; }}
                .file-link:hover {{ background: #8e44ad; }}
                .chart-container {{ margin: 20px 0; }}
                .progress-bar {{ background: #ecf0f1; border-radius: 10px; padding: 3px; margin: 5px 0; }}
                .progress-fill {{ background: #3498db; height: 20px; border-radius: 8px; text-align: center; color: white; line-height: 20px; }}
                .two-column {{ display: flex; gap: 20px; }}
                .column {{ flex: 1; }}
                ul.contact-list {{ max-height: 200px; overflow-y: auto; }}
                .app-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; margin: 15px 0; }}
                .app-item {{ background: #f8f9fa; padding: 10px; border-radius: 5px; border-left: 4px solid #3498db; }}
                .footer {{ background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-top: 30px; }}
                .footer-section {{ margin: 15px 0; }}
                .footer-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; }}
                .contact-info {{ background: #34495e; padding: 15px; border-radius: 5px; }}
                .file-info {{ background: #34495e; padding: 15px; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Android Forensic Analysis Report</h1>
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <p>Case Number: <span class="highlight">{data.get('case_number', 'N/A')}</span></p>
                        <p>Analysis Date: <span class="highlight">{data.get('analysis_date', 'N/A')}</span></p>
                    </div>
                    <div>
                        <p>Generated by: <span class="highlight">Arsenic Triage Suite</span></p>
                        <p>Report Version: <span class="highlight">2.0</span></p>
                    </div>
                </div>
            </div>
            
            <div class="section summary">
                <h2>Executive Summary</h2>
                <p>This comprehensive forensic report analyzes Android device data extracted through multiple collection methods including ADB backup extraction and APK-based data collection. The analysis provides detailed insights into user communications, application usage, and device activity patterns.</p>
        """
        
        # Add critical findings section
        html += """
                <div class="critical">
                    <h3>Key Findings Summary</h3>
        """
        
        # Calculate comprehensive findings
        total_media_files = 0
        total_database_files = 0
        earliest_date = None
        latest_date = None
        
        # Count media and database files from backup analysis
        if 'ab_analysis' in data and ab_dir:
            try:
                for root, dirs, files in os.walk(ab_dir):
                    for file in files:
                        file_lower = file.lower()
                        # Count media files
                        if any(ext in file_lower for ext in ['.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mov', '.3gp', '.mp3', '.wav', '.m4a']):
                            total_media_files += 1
                        # Count database files
                        elif any(ext in file_lower for ext in ['.db', '.sqlite', '.sqlite3', '.db-journal']):
                            total_database_files += 1
            except Exception as e:
                pass
        
        # Calculate time period from APK data
        if 'apk_analysis' in data:
            apk = data['apk_analysis']
            
            # Get date range from SMS data
            if 'sms' in apk and 'date_range' in apk['sms']:
                sms_earliest = apk['sms']['date_range']['earliest']
                sms_latest = apk['sms']['date_range']['latest']
                if earliest_date is None or (sms_earliest and sms_earliest < earliest_date):
                    earliest_date = sms_earliest
                if latest_date is None or (sms_latest and sms_latest > latest_date):
                    latest_date = sms_latest
            
            # Get date range from call data if available
            if 'calls' in apk and 'date_range' in apk['calls']:
                calls_earliest = apk['calls']['date_range']['earliest']
                calls_latest = apk['calls']['date_range']['latest']
                if earliest_date is None or (calls_earliest and calls_earliest < earliest_date):
                    earliest_date = calls_earliest
                if latest_date is None or (calls_latest and calls_latest > latest_date):
                    latest_date = calls_latest
        
        # Generate findings summary
        html += f"<p><strong>Media Files Recovered:</strong> {total_media_files:,} files (photos, videos, audio)</p>"
        html += f"<p><strong>Database Files in Backup:</strong> {total_database_files:,} database files containing application data</p>"
        
        if earliest_date and latest_date:
            html += f"<p><strong>Data Coverage Period:</strong> {earliest_date} to {latest_date}</p>"
        else:
            html += f"<p><strong>Data Coverage Period:</strong> Analysis in progress - timeline to be determined</p>"
        
        # Add communication summary if available
        if 'apk_analysis' in data:
            apk = data['apk_analysis']
            if 'sms' in apk:
                sms_data = apk['sms']
                html += f"<p><strong>SMS/MMS Messages:</strong> {sms_data['total_count']:,} messages from {len(sms_data['top_contacts'])} unique contacts</p>"
            
            if 'calls' in apk:
                calls_data = apk['calls']
                total_hours = calls_data['total_duration'] / 3600
                html += f"<p><strong>Call Records:</strong> {calls_data['total_count']:,} calls with {total_hours:.1f} hours total duration ({calls_data['missed']} missed)</p>"
        
        html += "</div>"
        
        # APK Data Analysis Section
        if 'apk_analysis' in data:
            apk = data['apk_analysis']
            html += """
                <h2>Communication Analysis (APK Data)</h2>
                <div class="info">
                    <h3>Available Data Files</h3>
                    <p>Click the links below to access the detailed CSV data files:</p>
                    <a href="apk_parsed/sms_messages.csv" class="file-link">SMS Messages</a>
                    <a href="apk_parsed/call_logs.csv" class="file-link">Call Logs</a>
                    <a href="apk_parsed/contacts.csv" class="file-link">Contacts</a>
                    <a href="apk_parsed/calendar_events.csv" class="file-link">Calendar Events</a>
                    <a href="apk_parsed/system_settings.csv" class="file-link">System Settings</a>
                </div>
            """
            
            # SMS/MMS Analysis
            if 'sms' in apk:
                sms_data = apk['sms']
                html += f"""
                <div class="two-column">
                    <div class="column">
                        <h3>SMS/MMS Message Analysis</h3>
                        <table>
                            <tr><th>Metric</th><th>Value</th></tr>
                            <tr><td>Total Messages</td><td><span class="metric">{sms_data['total_count']}</span></td></tr>
                            <tr><td>Incoming Messages</td><td>{sms_data['incoming']}</td></tr>
                            <tr><td>Outgoing Messages</td><td>{sms_data['outgoing']}</td></tr>
                            <tr><td>Conversation Threads</td><td>{sms_data['thread_count']}</td></tr>
                            <tr><td>Date Range</td><td>{sms_data['date_range']['earliest']} to {sms_data['date_range']['latest']}</td></tr>
                        </table>
                        
                        <h4>Message Distribution</h4>
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: {(sms_data['incoming'] / sms_data['total_count'] * 100) if sms_data['total_count'] > 0 else 0:.1f}%">
                                Incoming: {(sms_data['incoming'] / sms_data['total_count'] * 100) if sms_data['total_count'] > 0 else 0:.1f}%
                            </div>
                        </div>
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: {(sms_data['outgoing'] / sms_data['total_count'] * 100) if sms_data['total_count'] > 0 else 0:.1f}%; background: #e74c3c;">
                                Outgoing: {(sms_data['outgoing'] / sms_data['total_count'] * 100) if sms_data['total_count'] > 0 else 0:.1f}%
                            </div>
                        </div>
                    </div>
                    
                    <div class="column">
                        <h4>Top 10 SMS Contacts</h4>
                        <ul class="contact-list">
                """
                
                for contact, count in sms_data['top_contacts']:
                    percentage = (count / sms_data['total_count'] * 100) if sms_data['total_count'] > 0 else 0
                    html += f"<li><strong>{contact}</strong>: {count} messages ({percentage:.1f}%)</li>"
                
                html += "</ul></div></div>"
                
                # Monthly distribution
                if sms_data['monthly_distribution']:
                    html += "<h4>Monthly Message Activity</h4><table>"
                    html += "<tr><th>Month</th><th>Messages</th><th>Percentage</th></tr>"
                    for month, count in sorted(sms_data['monthly_distribution'].items()):
                        percentage = (count / sms_data['total_count'] * 100) if sms_data['total_count'] > 0 else 0
                        html += f"<tr><td>{month}</td><td>{count}</td><td>{percentage:.1f}%</td></tr>"
                    html += "</table>"
                
                # Add sample SMS messages if available
                html += self.add_sample_sms_data(apk_dir)
            
            # Call Log Analysis
            if 'calls' in apk:
                calls_data = apk['calls']
                total_hours = calls_data['total_duration'] / 3600
                avg_minutes = calls_data['avg_duration'] / 60
                
                html += f"""
                <div class="two-column">
                    <div class="column">
                        <h3>Call Log Analysis</h3>
                        <table>
                            <tr><th>Metric</th><th>Value</th></tr>
                            <tr><td>Total Calls</td><td><span class="metric">{calls_data['total_count']}</span></td></tr>
                            <tr><td>Incoming Calls</td><td>{calls_data['incoming']}</td></tr>
                            <tr><td>Outgoing Calls</td><td>{calls_data['outgoing']}</td></tr>
                            <tr><td>Missed Calls</td><td><span style="color: #e74c3c; font-weight: bold;">{calls_data['missed']}</span></td></tr>
                            <tr><td>Rejected Calls</td><td>{calls_data['rejected']}</td></tr>
                            <tr><td>Total Talk Time</td><td>{total_hours:.2f} hours</td></tr>
                            <tr><td>Average Call Duration</td><td>{avg_minutes:.1f} minutes</td></tr>
                        </table>
                    </div>
                    
                    <div class="column">
                        <h4>Top 10 Call Contacts</h4>
                        <ul class="contact-list">
                """
                
                for contact, count in calls_data['top_contacts']:
                    percentage = (count / calls_data['total_count'] * 100) if calls_data['total_count'] > 0 else 0
                    html += f"<li><strong>{contact}</strong>: {count} calls ({percentage:.1f}%)</li>"
                
                html += "</ul>"
                
                # Longest call info
                if calls_data['longest_call']['duration'] > 0:
                    longest_minutes = calls_data['longest_call']['duration'] / 60
                    html += f"""
                        <div class="warning">
                            <h4>Longest Call</h4>
                            <p><strong>Contact:</strong> {calls_data['longest_call']['contact']}</p>
                            <p><strong>Duration:</strong> {longest_minutes:.1f} minutes</p>
                            <p><strong>Date:</strong> {calls_data['longest_call']['date']}</p>
                        </div>
                    """
                
                html += "</div></div>"
                
                # Call frequency by day of week
                if calls_data['call_frequency']:
                    html += "<h4>Call Activity by Day of Week</h4><table>"
                    html += "<tr><th>Day</th><th>Calls</th><th>Percentage</th></tr>"
                    for day, count in calls_data['call_frequency'].most_common():
                        percentage = (count / calls_data['total_count'] * 100) if calls_data['total_count'] > 0 else 0
                        html += f"<tr><td>{day}</td><td>{count}</td><td>{percentage:.1f}%</td></tr>"
                    html += "</table>"
                
                # Add sample call data
                html += self.add_sample_call_data(apk_dir)
            
            # Contacts Analysis
            if 'contacts' in apk:
                contacts_data = apk['contacts']
                html += f"""
                <h3>Contacts Analysis</h3>
                <table>
                    <tr><th>Metric</th><th>Value</th></tr>
                    <tr><td>Total Contacts</td><td><span class="metric">{contacts_data['total_count']}</span></td></tr>
                    <tr><td>Contacts with Phone Numbers</td><td>{contacts_data['with_phone']}</td></tr>
                    <tr><td>Contacts without Phone Numbers</td><td>{contacts_data['total_count'] - contacts_data['with_phone']}</td></tr>
                </table>
                
                <h4>Contact Sources</h4>
                <table>
                    <tr><th>Source</th><th>Count</th><th>Percentage</th></tr>
                """
                
                for source, count in contacts_data['sources'].most_common():
                    percentage = (count / contacts_data['total_count'] * 100) if contacts_data['total_count'] > 0 else 0
                    html += f"<tr><td>{source}</td><td>{count}</td><td>{percentage:.1f}%</td></tr>"
                
                html += "</table>"
                
                # Add sample contacts data
                html += self.add_sample_contacts_data(apk_dir)
            
            # Calendar Analysis
            if 'calendar' in apk:
                calendar_data = apk['calendar']
                html += f"""
                <h3>Calendar Events Analysis</h3>
                <table>
                    <tr><th>Metric</th><th>Value</th></tr>
                    <tr><td>Total Events</td><td><span class="metric">{calendar_data['total_count']}</span></td></tr>
                    <tr><td>Past Events</td><td>{calendar_data['past']}</td></tr>
                    <tr><td>Upcoming Events</td><td>{calendar_data['upcoming']}</td></tr>
                    <tr><td>Unique Locations</td><td>{len(calendar_data['locations'])}</td></tr>
                </table>
                
                <h4>Event Locations (Sample)</h4>
                <ul style="max-height: 150px; overflow-y: auto;">
                """
                
                for location in calendar_data['locations'][:15]:
                    html += f"<li>{location}</li>"
                
                html += "</ul>"
        
        # Android Backup Analysis Section
        if 'ab_analysis' in data:
            ab = data['ab_analysis']
            html += f"""
                <h2>Android Backup Analysis</h2>
                <div class="info">
                    <h3>Backup Data Structure</h3>
                    <p>Android backup extracted and analyzed. Raw files available in: <strong>ab_extracted/</strong></p>
                </div>
                
                <table>
                    <tr><th>Metric</th><th>Value</th></tr>
                    <tr><td>Total Files Extracted</td><td><span class="metric">{ab.get('total_files', 'N/A')}</span></td></tr>
                    <tr><td>Total Directories</td><td>{ab.get('total_directories', 'N/A')}</td></tr>
                    <tr><td>Application Directories</td><td>{ab.get('app_directories', 'N/A')}</td></tr>
                </table>
                
                <h3>Applications Found in Backup</h3>
                <div class="app-grid">
            """
            
            for app in ab.get('sample_apps', []):
                # Extract app name from package
                app_name = app.split('.')[-1].title() if '.' in app else app
                html += f"""
                    <div class="app-item">
                        <strong>{app_name}</strong><br>
                        <small>{app}</small>
                    </div>
                """
            
            html += "</div>"
        
        # Technical details section
        html += f"""
            </div>
            
            <div class="section data">
                <h2>Technical Methodology</h2>
                <h3>Data Collection Methods</h3>
                <ul>
                    <li><strong>APK-Based Collection:</strong> Custom Android application deployed to collect data via content providers</li>
                    <li><strong>ADB Backup Extraction:</strong> Android Debug Bridge backup (.ab) files extracted using abe.jar</li>
                    <li><strong>Forensic Parsing:</strong> Automated parsing and analysis of collected data structures</li>
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
                            <tr style="border: none;"><td style="border: none; padding: 5px;"><strong>Sources:</strong></td><td style="border: none; padding: 5px;">APK Collection, ADB Backup</td></tr>
                        </table>
                    </div>
                    
                    <div class="file-info">
                        <h3>Available Resources</h3>
                        <ul style="list-style-type: none; padding-left: 0;">
                            <li style="margin: 8px 0;"><strong>CSV Data Files:</strong> Raw extracted data in spreadsheet format</li>
                            <li style="margin: 8px 0;"><strong>Timeline Data:</strong> Chronological event reconstruction</li>
                            <li style="margin: 8px 0;"><strong>Backup Files:</strong> Complete Android backup extraction</li>
                            <li style="margin: 8px 0;"><strong>Analysis Logs:</strong> Detailed processing documentation</li>
                        </ul>
                    </div>
                </div>
                
                <div class="footer-section">
                    <h3>Next Steps</h3>
                    <div class="two-column">
                        <div class="column">
                            <h4>Further Analysis</h4>
                            <ul>
                                <li>Import CSV files into analysis software (Excel, R, Python)</li>
                                <li>Cross-reference timeline data with external evidence</li>
                                <li>Examine application-specific data in backup directories</li>
                                <li>Correlate communication patterns with case timeline</li>
                            </ul>
                        </div>
                        <div class="column">
                            <h4>Documentation</h4>
                            <ul>
                                <li>Maintain chain of custody for all extracted files</li>
                                <li>Document analysis methodology in case notes</li>
                                <li>Preserve original backup files as evidence</li>
                                <li>Note any limitations or extraction errors</li>
                            </ul>
                        </div>
                    </div>
                </div>
                
                <div class="footer-section" style="text-align: center; margin-top: 20px; padding-top: 20px; border-top: 1px solid #4a5568;">
                    <p><strong>End of Android Forensic Analysis Report</strong></p>
                    <p style="font-size: 12px; color: #cbd5e0;">This report contains forensic analysis results generated by automated tools. Manual verification of findings is recommended for critical evidence.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html

    def create_forensic_timeline(self, analysis_dir, ab_dir, apk_dir):
        """Create a forensic timeline from available data"""
        try:
            timeline_path = os.path.join(analysis_dir, "Forensic_Timeline.csv")
            timeline_events = []
            
            # Parse APK data for timeline events
            if apk_dir and os.path.exists(apk_dir):
                # SMS timeline
                sms_file = os.path.join(apk_dir, "sms_messages.csv")
                if os.path.exists(sms_file):
                    import csv
                    with open(sms_file, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            if row.get('date'):
                                timeline_events.append({
                                    'timestamp': row['date'],
                                    'event_type': 'SMS',
                                    'description': f"SMS {row.get('sms_type_label', 'Unknown')} - {row.get('address', 'Unknown')}",
                                    'details': row.get('body', '')[:100] + '...' if len(row.get('body', '')) > 100 else row.get('body', ''),
                                    'source': 'APK Collection'
                                })
                
                # Call timeline
                calls_file = os.path.join(apk_dir, "call_logs.csv")
                if os.path.exists(calls_file):
                    with open(calls_file, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            if row.get('date'):
                                timeline_events.append({
                                    'timestamp': row['date'],
                                    'event_type': 'Call',
                                    'description': f"Call {row.get('call_type_label', 'Unknown')} - {row.get('number', 'Unknown')}",
                                    'details': f"Duration: {row.get('duration', 'Unknown')} seconds",
                                    'source': 'APK Collection'
                                })
            
            # Sort timeline by timestamp
            timeline_events.sort(key=lambda x: x['timestamp'])
            
            # Write timeline CSV
            if timeline_events:
                fieldnames = ['timestamp', 'event_type', 'description', 'details', 'source']
                with open(timeline_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(timeline_events)
                
                return timeline_path
            
        except Exception as e:
            self.append_analysis_status(f"❌ Error creating timeline: {str(e)}")
        
        return None

    def show_password_info(self):
        """Show information about Android backup passwords"""
        import tkinter.messagebox as messagebox
        
        info_text = """Android Backup Password Information:

🔐 What is it?
Android backup passwords are used to encrypt ADB backups for security.

🔑 Common Passwords:
• "1234" - Default password set by some forensic tools
• Empty - Many backups are unencrypted 
• Custom - User-set passwords during backup

💡 Usage Tips:
• Leave blank if backup is unencrypted
• Try "1234" if backup was created with forensic tools
• Contact device owner for custom passwords
• Error messages will indicate if password is wrong

⚠️ Security Note:
Passwords protect sensitive data in backups. Always handle with appropriate security measures."""
        
        messagebox.showinfo("Android Backup Password Help", info_text)
