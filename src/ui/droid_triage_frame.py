import os
import re
import sys
import customtkinter as ctk
from tkinter import filedialog, messagebox, ttk
import tkinter as tk
import threading
import time
import traceback
from PIL import Image, ImageTk
import pandas as pd
import subprocess
import platform
import datetime
import queue

# Add the project root directory to Python's path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.Droid_triage.Android_Triage import AndroidTriageHandler
from src.utils.pdf_report_gen import AndroidTriagePDFGenerator

class DroidTriageFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        
        # Initialize the triage handler
        self.triage_handler = AndroidTriageHandler()
        self.device_connected = False
        self.running = True
        self.selected_profile = "None Selected"
        
        # Create GUI update queue for thread-safe updates
        self.gui_update_queue = queue.Queue()
        
        # Create the UI
        self.create_widgets()
        
        # Start thread-safe device monitoring
        self.triage_handler.start_device_monitoring(self.queue_status_update)
        
        # Start the GUI update cycles
        self.schedule_device_check()
        self.schedule_gui_updates()

    def schedule_gui_updates(self):
        """Process GUI update queue every 100ms"""
        if self.running:
            try:
                # Check if widget still exists before processing
                if not self.winfo_exists():
                    self.running = False
                    return
                    
                # Process all pending GUI updates
                while not self.gui_update_queue.empty():
                    try:
                        update_func = self.gui_update_queue.get_nowait()
                        if self.winfo_exists():  # Check if widget still exists
                            update_func()
                    except queue.Empty:
                        break
                    except Exception as e:
                        print(f"Error processing GUI update: {e}")
                
                # Schedule the next check only if we're still running and exist
                if self.running and self.winfo_exists():
                    self.after(100, self.schedule_gui_updates)
                
            except Exception as e:
                print(f"Error in GUI update cycle: {e}")
                # Continue checking only if we're still running and exist
                if self.running and self.winfo_exists():
                    self.after(1000, self.schedule_gui_updates)

    def queue_gui_update(self, update_func):
        """Queue a GUI update function to be executed in the main thread"""
        try:
            self.gui_update_queue.put(update_func)
        except Exception as e:
            print(f"Error queueing GUI update: {e}")

    def queue_status_update(self, message):
        """Queue a status update to be processed by the main GUI thread"""
        # This is called from the background thread, so we queue the update
        self.queue_gui_update(lambda: self.update_device_status(message))

    def update_device_status(self, message):
        """Update device status in the GUI - thread-safe version"""
        try:
            # Always log the message first
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {message}")
            
            # Update UI elements safely
            if hasattr(self, 'device_status_label'):
                self.device_status_label.configure(text=message)
                
                # Update connection state and colors
                if "No device" in message or "disconnected" in message.lower():
                    self.device_connected = False
                    self.device_status_label.configure(text_color="red")
                    
                    # Disable triage options
                    if hasattr(self, 'start_button'):
                        self.start_button.configure(state="disabled")
                        
                    self.log_message("Device disconnected - triage options disabled")
                        
                else:
                    # Device is connected
                    self.device_connected = True
                    self.device_status_label.configure(text_color="green")
                    
                    # Enable triage options
                    if hasattr(self, 'start_button'):
                        self.start_button.configure(state="normal")
                        
                    self.log_message("Device connection established - triage options enabled")
                        
        except Exception as e:
            print(f"Error updating device status: {e}")
            
    def schedule_device_check(self):
        """Schedule periodic device queue checking in the main GUI thread"""
        if self.running:
            try:
                # Check if widget still exists before processing
                if not self.winfo_exists():
                    self.running = False
                    return
                    
                # Check the device queue
                self.triage_handler.check_device_queue()
                
                # Schedule the next check only if we're still running and exist
                if self.running and self.winfo_exists():
                    self.after(1000, self.schedule_device_check)  # Check every 1 second
                
            except Exception as e:
                print(f"Error in device check cycle: {e}")
                # Continue checking only if we're still running and exist
                if self.running and self.winfo_exists():
                    self.after(5000, self.schedule_device_check)
   
    def stop_device_check(self):
        """Stop device monitoring - called from droid_app.py cleanup"""
        try:
            self.running = False
            if hasattr(self, 'triage_handler'):
                self.triage_handler.stop_device_monitoring()
            print("Device monitoring stopped")
        except Exception as e:
            print(f"Error stopping device monitoring: {e}")
            
    def refresh_device_status(self):
        """Manually refresh device status - called when app becomes visible"""
        try:
            if hasattr(self, 'triage_handler'):
                # Force a queue check
                self.triage_handler.check_device_queue()
        except Exception as e:
            print(f"Error refreshing device status: {e}")

    def destroy(self):
        """Clean up when closing the frame"""
        try:
            self.stop_device_check()
        except:
            pass
        super().destroy()

    
    def create_widgets(self):
        """Create all widgets for the Android Triage Frame"""
        # Configure the main frame's grid
        self.grid_columnconfigure(0, weight=0, minsize=250)  # Left column (fixed width)
        self.grid_columnconfigure(1, weight=1)  # Right column (expandable)
        self.grid_rowconfigure(1, weight=1)  # Make results area expandable
        
        # Row 0: Case information (spans both columns)
        # self.setup_case_info()
        
        # Row 1, Col 0: Command panel (triage options)
        self.setup_command_panel()
        
        # Row 1, Col 1: Results area with tabs
        self.setup_results_area()
        
        # Initialize the triage handler
        if not hasattr(self, 'triage_handler'):
            self.triage_handler = AndroidTriageHandler()

    # def setup_case_info(self):
    #     """Setup compact case information and device status section"""
    #     # Create a more compact frame with less padding
    #     case_frame = ctk.CTkFrame(self)
    #     case_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 0))
        
    #     # Use grid for more precise control
    #     case_frame.grid_columnconfigure(0, weight=0)  # Device status label
    #     case_frame.grid_columnconfigure(1, weight=1)  # Device status value
        
    #     # Device status only - case info removed since it's handled by main app header
    #     # device_label = ctk.CTkLabel(case_frame, text="Device Status:")
    #     # device_label.grid(row=0, column=0, padx=(10, 5), pady=(10, 10), sticky="w")
        
    #     # Device status display
    #     self.device_status_display = ctk.CTkLabel(case_frame, text="No device connected", 
    #                                         fg_color=("gray90", "gray20"), 
    #                                         corner_radius=6)
    #     self.device_status_display.grid(row=0, column=1, padx=5, pady=(10, 10), sticky="ew")
        
    #     return case_frame

    def run_triage(self):
        """Run triage with selected options"""
        try:
            # Get case info FROM MAIN APP instead of local entries
            main_app = self.winfo_toplevel()
            
            case_number = ""
            output_dir = ""
            
            if hasattr(main_app, 'get_case_number'):
                case_number = main_app.get_case_number()
            if hasattr(main_app, 'get_output_directory'):
                output_dir = main_app.get_output_directory()
            
            if not case_number:
                messagebox.showerror("Error", "Please enter a case number in the header")
                return
                
            if not output_dir or not os.path.isdir(output_dir):
                messagebox.showerror("Error", "Please select a valid output directory in the header")
                return
            
            # Verify device connection
            if not self.triage_handler.is_device_connected():
                messagebox.showerror("Error", "No device connected. Please connect a device and try again.")
                return
                
            # Build triage options (rest of method stays the same)
            triage_options = {
                "apps": True,
                "device_details": True,
                "filenames": False,
                "thumbnails": False,
                "hashes": False
            }
            
            # Start triage in background thread
            threading.Thread(
                target=self._triage_thread,
                args=(case_number, output_dir, triage_options),
                daemon=True
            ).start()
            
        except Exception as e:
            self.log_message(f"Error starting triage: {e}")
            import traceback
            self.log_message(traceback.format_exc())

    def refresh_case_info_display(self):
        """Refresh the case info display with current values from main app"""
        try:
            main_app = self.winfo_toplevel()
            
            # Update case number display
            if hasattr(main_app, 'get_case_number') and hasattr(self, 'case_display'):
                case_number = main_app.get_case_number()
                self.case_display.configure(text=case_number or "Not set")
            
            # Update output directory display
            if hasattr(main_app, 'get_output_directory') and hasattr(self, 'output_display'):
                output_dir = main_app.get_output_directory()
                # Truncate long paths for display
                if output_dir and len(output_dir) > 50:
                    display_dir = "..." + output_dir[-47:]
                else:
                    display_dir = output_dir or "Not set"
                self.output_display.configure(text=display_dir)
                
        except Exception as e:
            print(f"Error refreshing case info display: {e}")

    def setup_command_panel(self):
        """Set up the left command panel with grouped controls"""
        command_panel = ctk.CTkFrame(self)
        command_panel.grid(row=1, column=0, sticky="ns", padx=10, pady=10)
        
        # Device Connection Section
        self.create_device_section(command_panel)
        
        # Visual separator
        separator1 = ttk.Separator(command_panel, orient="horizontal")
        separator1.pack(fill="x", padx=10, pady=10)
        
        # Triage Options Section
        self.create_triage_options_section(command_panel)
        
        # Visual separator
        separator2 = ttk.Separator(command_panel, orient="horizontal")
        separator2.pack(fill="x", padx=10, pady=10)
        
        # Export & Reporting Section
        # self.create_export_section(command_panel)
        
        return command_panel
    

    # def refresh_device_status(self):
    #     """Manually refresh the device status display"""
    #     try:
    #         if hasattr(self, '_pending_status_message'):
    #             # Update the UI with the last known status
    #             if hasattr(self, 'device_status_label'):
    #                 self.device_status_label.configure(text=self._pending_status_message)
                    
    #         # Also check if device is still connected
    #         if hasattr(self, 'triage_handler'):
    #             is_connected = self.triage_handler.is_device_connected()
    #             if is_connected:
    #                 device_info = self.triage_handler.get_device_basic_info()
    #                 if device_info:
    #                     # status_msg = f"Device Connected/n {device_info.get('manufacturer', 'Unknown')} {device_info.get('model', 'Unknown')} (Android {device_info.get('android_version', 'Unknown')})"
    #                     status_msg = f"{device_info.get('model', 'Unknown')} (Android {device_info.get('android_version', 'Unknown')})"

    #                     self.update_device_status(status_msg)
    #             else:
    #                 self.update_device_status("No device connected")
                    
    #     except Exception as e:
    #         print(f"Error refreshing device status: {e}")

    
    def setup_results_area(self):
        """Set up the results area with tabs for different data views"""
        # Create the main tab view container
        self.results_tabs = ctk.CTkTabview(self)
        self.results_tabs.grid(row=1, column=1, sticky="nsew", padx=10, pady=10)
        
        # Add tabs for different content types
        self.status_tab = self.results_tabs.add("Status")
        self.details_tab = self.results_tabs.add("Device Info")
        self.apps_tab = self.results_tabs.add("Apps")
        self.files_tab = self.results_tabs.add("Files")
        self.thumbnails_tab = self.results_tabs.add("Images")
        
        # Add new content artifact tabs
        self.sms_tab = self.results_tabs.add("SMS")
        self.mms_tab = self.results_tabs.add("MMS") 
        self.contacts_tab = self.results_tabs.add("Contacts")
        self.call_logs_tab = self.results_tabs.add("Call Logs")
        self.notifications_tab = self.results_tabs.add("Notifications")
        
        # Set up each tab with appropriate content
        self.setup_status_tab()
        self.setup_details_tab()
        self.setup_apps_tab()
        self.setup_files_tab()
        self.setup_thumbnails_tab()
        
        # Set up new content artifact tabs
        self.setup_sms_tab()
        self.setup_mms_tab()
        self.setup_contacts_tab()
        self.setup_call_logs_tab()
        self.setup_notifications_tab()
        
        # Default to status tab
        self.results_tabs.set("Status")
        
        return self.results_tabs

    def apply_visual_enhancements(self):
        """Apply visual enhancements to improve usability"""
        # Add section headers with visual distinction
        for header in self.findChildren(ctk.CTkLabel):
            if header.cget("font")[1] > 12:  # If it's a header
                header.configure(fg_color="#3E4149", corner_radius=6)
                header.pack(fill="x", padx=5, pady=(10, 5), ipady=5)
        
        # Highlight the start button for better visibility
        if hasattr(self, 'start_button'):
            self.start_button.configure(
                fg_color="#28A745",  # Green color
                hover_color="#218838",  # Darker green on hover
                font=("Arial", 13, "bold")
            )
        
        # Add subtle borders to main panels
        for frame in [self.command_panel, self.results_tabs]:
            frame.configure(border_width=1, border_color="#1A1B1E")

    def create_device_section(self, parent):
        """Create device connection section"""
        # Create a frame for device information
        device_frame = ctk.CTkFrame(parent, fg_color="transparent")
        device_frame.pack(fill="x", padx=5, pady=5)
        
        # Header
        header = ctk.CTkLabel(
            device_frame,
            text="Device Connection",
            font=("Arial", 14, "bold"),
            anchor="w"
        )
        header.pack(fill="x", padx=5, pady=5)
        
        # Status display
        status_frame = ctk.CTkFrame(device_frame, fg_color="transparent")
        status_frame.pack(fill="x", padx=10, pady=5)
        
        status_label = ctk.CTkLabel(status_frame, text="Status:")
        status_label.pack(side="left", padx=5)
        
        self.device_status_label = ctk.CTkLabel(
            status_frame, 
            text="❌ No Device Connected",
            text_color="red"
        )
        self.device_status_label.pack(side="left", padx=5)
        
        # Device refresh button
        refresh_button = ctk.CTkButton(
            device_frame,
            text="Refresh Connection",
            command=self.refresh_device_connection
        )
        refresh_button.pack(padx=10, pady=5, fill="x")
        
        return device_frame
    

    def refresh_device_connection(self):
        """Manually refresh the device connection status"""
        try:
            self.log_message("Refreshing device connection...")
            
            # Check if device is connected using the triage handler
            if hasattr(self, 'triage_handler'):
                is_connected = self.triage_handler.is_device_connected()
                
                if is_connected:
                    # Get device info
                    device_info = self.triage_handler.get_device_basic_info()
                    if device_info:
                        status_msg = f"350 Device Connected: {device_info.get('manufacturer', 'Unknown')} {device_info.get('model', 'Unknown')} (Android {device_info.get('android_version', 'Unknown')})"
                        self.log_message(f"Connected to {device_info.get('model', 'Unknown')} (Android {device_info.get('android_version', 'Unknown')})")
                    else:
                        status_msg = "✓ Android device connected"
                        
                    # Update the UI directly
                    self.update_device_status(status_msg)
                    
                    # Enable triage options if they exist
                    if hasattr(self, 'enable_triage_options'):
                        self.enable_triage_options()
                        
                    # Fetch apps if method exists
                    if hasattr(self, '_fetch_apps_thread'):
                        threading.Thread(target=self._fetch_apps_thread, daemon=True).start()
                    elif hasattr(self, 'fetch_installed_apps'):
                        # Use alternative method if available
                        threading.Thread(target=self.fetch_installed_apps, daemon=True).start()
                        
                else:
                    # No device connected
                    status_msg = "❌ No Device Connected"
                    self.update_device_status(status_msg)
                    self.log_message("No device connected. Please connect a device and try again.")
                    
                    # Disable triage options
                    if hasattr(self, 'disable_triage_options'):
                        self.disable_triage_options()
            
        except Exception as e:
            self.log_message(f"Error refreshing device connection: {e}")
            import traceback
            self.log_message(traceback.format_exc())

    def setup_results_area(self):
        """Set up the results area with tabs for different data views"""
        # Create the main tab view container
        self.results_tabs = ctk.CTkTabview(self)
        self.results_tabs.grid(row=1, column=1, sticky="nsew", padx=10, pady=10)
        
        # Add tabs for different content types
        self.status_tab = self.results_tabs.add("Status")
        self.details_tab = self.results_tabs.add("Device Info")
        self.apps_tab = self.results_tabs.add("Apps")
        self.files_tab = self.results_tabs.add("Files")
        self.thumbnails_tab = self.results_tabs.add("Images")
        
        # Add new content artifact tabs
        self.sms_tab = self.results_tabs.add("SMS")
        self.mms_tab = self.results_tabs.add("MMS") 
        self.contacts_tab = self.results_tabs.add("Contacts")
        self.call_logs_tab = self.results_tabs.add("Call Logs")
        self.notifications_tab = self.results_tabs.add("Notifications")
        
        # Set up each tab with appropriate content
        self.setup_status_tab()
        self.setup_details_tab()
        self.setup_apps_tab()
        self.setup_files_tab()
        self.setup_thumbnails_tab()
        
        # Set up new content artifact tabs
        self.setup_sms_tab()
        self.setup_mms_tab()
        self.setup_contacts_tab()
        self.setup_call_logs_tab()
        self.setup_notifications_tab()
        
        # Default to status tab
        self.results_tabs.set("Status")
        
        return self.results_tabs

    def apply_visual_enhancements(self):
        """Apply visual enhancements to improve usability"""
        # Add section headers with visual distinction
        for header in self.findChildren(ctk.CTkLabel):
            if header.cget("font")[1] > 12:  # If it's a header
                header.configure(fg_color="#3E4149", corner_radius=6)
                header.pack(fill="x", padx=5, pady=(10, 5), ipady=5)
        
        # Highlight the start button for better visibility
        if hasattr(self, 'start_button'):
            self.start_button.configure(
                fg_color="#28A745",  # Green color
                hover_color="#218838",  # Darker green on hover
                font=("Arial", 13, "bold")
            )
        
        # Add subtle borders to main panels
        for frame in [self.command_panel, self.results_tabs]:
            frame.configure(border_width=1, border_color="#1A1B1E")

    def create_device_section(self, parent):
        """Create device connection section"""
        # Create a frame for device information
        device_frame = ctk.CTkFrame(parent, fg_color="transparent")
        device_frame.pack(fill="x", padx=5, pady=5)
        
        # Header
        header = ctk.CTkLabel(
            device_frame,
            text="Device Connection",
            font=("Arial", 14, "bold"),
            anchor="w"
        )
        header.pack(fill="x", padx=5, pady=5)
        
        # Status display
        status_frame = ctk.CTkFrame(device_frame, fg_color="transparent")
        status_frame.pack(fill="x", padx=10, pady=5)
        
        status_label = ctk.CTkLabel(status_frame, text="Status:")
        status_label.pack(side="left", padx=5)
        
        self.device_status_label = ctk.CTkLabel(
            status_frame, 
            text="❌ No Device Connected",
            text_color="red"
        )
        self.device_status_label.pack(side="left", padx=5)
        
        # Device refresh button
        refresh_button = ctk.CTkButton(
            device_frame,
            text="Refresh Connection",
            command=self.refresh_device_connection
        )
        refresh_button.pack(padx=10, pady=5, fill="x")
        
        return device_frame
    
    def create_triage_options_section(self, parent):
        """Create triage options section with workflow guidance"""
        # Options frame
        options_frame = ctk.CTkFrame(parent, fg_color="transparent")
        options_frame.pack(fill="x", padx=5, pady=5)
        
        # Header
        header = ctk.CTkLabel(
            options_frame,
            text="Triage Operations",
            font=("Arial", 14, "bold"),
            anchor="w"
        )
        header.pack(fill="x", padx=5, pady=5)
        
        
        # Help text
        help_text = "Triage capabilities will differ due to OS versions,\n security settings, and other variables.\n\n Visit the report folder for detailed results."
        help_label = ctk.CTkLabel(
            options_frame,
            text=help_text,
            font=("Arial", 10),
            text_color="gray"
        )
        help_label.pack(anchor="w", padx=5, pady=(5, 10))
        
        # Start button
        self.start_button = ctk.CTkButton(
            options_frame,
            text="Start Triage",
            command=self.run_triage,
            height=36
        )
        self.start_button.pack(padx=5, pady=10, fill="x")
        
        
        
        self.start_button.configure(state="disabled")
        
        return options_frame
    
    def setup_status_tab(self):
        """Set up the status tab with log display"""
        status_frame = ctk.CTkFrame(self.status_tab)
        status_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Header
        header = ctk.CTkLabel(
            status_frame,
            text="Triage Status & Progress",
            font=("Arial", 16, "bold")
        )
        header.pack(pady=(0, 10))
        
        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(status_frame)
        self.progress_bar.pack(fill="x", padx=10, pady=5)
        self.progress_bar.set(0)
        
        # Log text area
        self.log_text = ctk.CTkTextbox(
            status_frame,
            wrap="word",
            font=("Arial", 12)
        )
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Set initial content
        self.log_text.insert("1.0", "Triage status and progress will appear here...\nTo begin, enable developer options, enable USB debugging, attach device, and trust this computer when prompted.\n\n")
        self.log_text.configure(state="disabled")

    def setup_details_tab(self):
        """Set up the device details tab with information display"""
        # Main container
        details_frame = ctk.CTkFrame(self.details_tab)
        details_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Header
        header = ctk.CTkLabel(
            details_frame,
            text="Device Information & Analysis",
            font=("Arial", 16, "bold")
        )
        header.pack(pady=(0, 10))
        
        # Details text area with scrollbar
        text_frame = ctk.CTkFrame(details_frame, fg_color="transparent")
        text_frame.pack(fill="both", expand=True)
        
        # Create a text widget for device details
        self.details_text = ctk.CTkTextbox(
            text_frame,
            wrap="word",
            font=("Arial", 12),
            height=500
        )
        self.details_text.pack(side="left", fill="both", expand=True)
        
        # Add scrollbar for details text
        details_scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.details_text.yview)
        details_scrollbar.pack(side="right", fill="y")
        self.details_text.configure(yscrollcommand=details_scrollbar.set)
        
        # Set initial content
        self.details_text.insert("1.0", "Device details will appear here after connecting a device...\n\n")
        self.details_text.configure(state="disabled")
        
    def update_device_details(self, device_details):
        """Update the device details tab with enhanced organization and readability"""
        try:
            if not device_details:
                self.log_message("No device details provided")
                return
                    
            self.log_message(f"Device details keys: {list(device_details.keys())}")
                
            # Clear current content and ensure widget is in normal state
            if hasattr(self, 'details_text'):
                # Try a completely different approach for Android 11
                self.details_text.configure(state="normal")
                self.details_text.delete("1.0", "end")
                    
                # Build flat string with no fancy formatting or special characters
                details_output = "DEVICE INFORMATION & FORENSIC ANALYSIS REPORT\n\n"
                    
                # 1. DEVICE IDENTIFIERS - Explicitly add each piece separately
                details_output += "1. DEVICE IDENTIFIERS\n"
                details_output += "--------------------------\n"
                
            
                    
                if "Serial" in device_details:
                    serial_line = f"Serial: {device_details['Serial']}\n"
                    details_output += serial_line
                    # self.log_message(f"Added identifier: Serial")
                    
                details_output += "\n"
                    
                # 2. DEVICE SPECIFICATIONS - Add each spec line by line
                details_output += "2. DEVICE SPECIFICATIONS\n"
                details_output += "--------------------------\n"
                
                spec_keys = [
                    "Device Name", "Model", "Manufacturer", "Brand", "Android Version", 
                    "API Level", "Build ID", "Build Date", "Bootloader", "Security Patch", 
                    "Hardware", "Chipset", "ABI"
                ]
                    
                for key in spec_keys:
                    if key in device_details and device_details[key]:
                        # Add each spec as a separate string concatenation
                        spec_line = f"{key}: {device_details[key]}\n"
                        details_output += spec_line
                        # self.log_message(f"Added specification: {key}")
                    
                details_output += "\n"
                    
                # 3. SECURITY - Add section separately
                details_output += "3. SECURITY & ENCRYPTION\n"
                details_output += "--------------------------\n"
                
                if "Encryption Status" in device_details:
                    enc_line = f"Encryption Status: {device_details['Encryption Status']}\n"
                    details_output += enc_line
                    # self.log_message("Added encryption status")
                    
                details_output += "\n"
                    
                # 4. USERS - Add each user separately
                details_output += "4. USER ACCOUNTS\n"
                details_output += "--------------------------\n"
                
                if "Users" in device_details and device_details["Users"]:
                    users = device_details["Users"]
                    self.log_message(f"Processing {len(users)} users")
                    
                    if isinstance(users, list):
                        for user in users:
                            if isinstance(user, dict):
                                user_id = user.get('id', 'Unknown')
                                user_name = user.get('name', 'Unknown')
                                user_type = user.get('type', 'Unknown')
                                user_state = user.get('state', 'Unknown')
                                
                                # Add each user line by line
                                details_output += f"User {user_id}\n"
                                details_output += f"  Name: {user_name}\n"
                                details_output += f"  Type: {user_type}\n"
                                details_output += f"  Status: {user_state}\n\n"
                                
                                self.log_message(f"Added user: {user_id} - {user_name}")
                
                # Use a completely different approach for inserting text
                # self.log_message(f"Inserting text with length: {len(details_output)}")
                
                # First clear the widget again
                self.details_text.delete("1.0", "end")
                
                # Insert the content using a character-by-character approach (Android 11 workaround)
                for i in range(0, len(details_output), 1000):
                    chunk = details_output[i:i+1000]
                    self.details_text.insert("end", chunk)
                    # Force UI update after each chunk
                    self.details_text.update()
                
                # Force update
                self.details_text.see("1.0")  # Scroll to top
                self.details_text.update()
                self.update_idletasks()
                
                # Finally lock the widget
                self.details_text.configure(state="disabled")
                                
        except Exception as e:
            self.log_message(f"Error updating device details: {e}")
            import traceback
            self.log_message(traceback.format_exc())
        
    def _format_analysis_section_clean(self, section_content):
        """Format analysis sections with clean, readable structure"""
        try:
            if not section_content:
                return ""
                
            lines = section_content.split('\n')
            formatted_lines = []
            
            for line in lines:
                original_line = line
                line = line.strip()
                
                if not line:
                    formatted_lines.append("")
                    continue
                
                # Main section headers (all caps with separators)
                if line.isupper() and any(char in line for char in ['-', '=']):
                    formatted_lines.append(f"   {line}")
                # Subsection headers (ends with colon)
                elif line.endswith(':') and not line.startswith(' '):
                    formatted_lines.append(f"   {line}")
                # Data items with colons (key: value pairs)
                elif ':' in line and not original_line.startswith('  '):
                    try:
                        key, value = line.split(':', 1)
                        formatted_lines.append(f"      {key.strip():.<30}: {value.strip()}")
                    except ValueError:
                        formatted_lines.append(f"      {line}")
                # List items (already indented or bulleted)
                elif original_line.startswith('  ') or line.startswith('-') or line.startswith('•'):
                    clean_line = line.lstrip('- •').strip()
                    formatted_lines.append(f"      • {clean_line}")
                # Numbers or other data
                elif line and line[0].isdigit() and '.' in line[:3]:
                    formatted_lines.append(f"      {line}")
                # Regular text
                else:
                    formatted_lines.append(f"   {line}")
            
            return '\n'.join(formatted_lines)
            
        except Exception as e:
            self.log_message(f"Error formatting analysis section: {e}")
            return section_content  # Return original if formatting fails

    def _format_investigative_section_clean(self, section_content):
        """Format investigative indicators with clean, professional structure"""
        try:
            if not section_content:
                return ""
                
            lines = section_content.split('\n')
            formatted_lines = []
            current_category = None
            
            for line in lines:
                original_line = line
                line = line.strip()
                
                if not line:
                    formatted_lines.append("")
                    continue
                
                # Main section header
                if line.isupper() and any(char in line for char in ['-', '=']):
                    formatted_lines.append(f"   {line}")
                # Category indicators (contains numbers found/messages/etc)
                elif any(keyword in line.lower() for keyword in ['found:', 'messages:', 'numbers:', 'calls:']):
                    formatted_lines.append(f"   {line}")
                    current_category = line.lower()
                # Detail items (usually indented in original)
                elif original_line.startswith('  ') and line.startswith('-'):
                    detail = line[1:].strip()  # Remove the dash
                    
                    # Format based on content type
                    if ":" in detail and current_category and "codes" in current_category:
                        formatted_lines.append(f"      • {detail}")
                    elif detail.startswith('+') and current_category and "numbers" in current_category:
                        formatted_lines.append(f"      • {detail}")
                    elif current_category and "banking" in current_category:
                        formatted_lines.append(f"      • {detail}")
                    else:
                        formatted_lines.append(f"      • {detail}")
                # Sub-headers or other content
                else:
                    formatted_lines.append(f"   {line}")
            
            return '\n'.join(formatted_lines)
            
        except Exception as e:
            self.log_message(f"Error formatting investigative section: {e}")
            return section_content

    def _export_device_report(self):
        """Export the device details report to a text file"""
        try:
            if not hasattr(self, 'details_text'):
                messagebox.showwarning("No Data", "No device details to export")
                return
            
            # Get the content from the textbox
            content = self.details_text.get("1.0", "end-1c")
            
            if not content.strip() or "Ready to begin analysis" in content:
                messagebox.showwarning("No Data", "No device analysis data to export")
                return
            
            # Open file dialog
            filename = filedialog.asksaveasfilename(
                title="Save Device Analysis Report",
                defaultextension=".txt",
                filetypes=[
                    ("Text files", "*.txt"),
                    ("All files", "*.*")
                ],
                initialname=f"Device_Analysis_Report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )
            
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                messagebox.showinfo("Export Successful", f"Device analysis report exported to:\n{filename}")
                self.log_message(f"Device analysis report exported to: {filename}")
                
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export device analysis report:\n{e}")
            self.log_message(f"Error exporting device analysis report: {e}")
  

    def _insert_formatted_analysis(self, analysis_content):
        """Insert formatted analysis content with error handling"""
        try:
            if not analysis_content:
                return
                
            lines = analysis_content.split('\n')
            
            for line in lines:
                try:
                    original_line = line
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Main section headers (all caps with separators)
                    if line.isupper() and any(char in line for char in ['-', '=']):
                        self.details_text.insert("end", f"{line}\n", ("header2", "indent1"))
                    
                    # Subsection headers (ends with colon)
                    elif line.endswith(':') and not original_line.startswith(' '):
                        self.details_text.insert("end", f"{line}\n", ("header3", "indent1"))
                    
                    # Key-value pairs
                    elif ':' in line and not original_line.startswith('  '):
                        try:
                            key, value = line.split(':', 1)
                            self.details_text.insert("end", f"{key.strip()}: ", ("key", "indent2"))
                            self.details_text.insert("end", f"{value.strip()}\n", ("value", "indent2"))
                        except ValueError:
                            self.details_text.insert("end", f"{line}\n", ("value", "indent2"))
                    
                    # List items
                    elif original_line.startswith('  ') or line.startswith('-') or line.startswith('•'):
                        clean_line = line.lstrip('- •').strip()
                        self.details_text.insert("end", f"• {clean_line}\n", ("value", "indent2"))
                    
                    # Numbers or structured data
                    elif line and line[0].isdigit() and '.' in line[:3]:
                        self.details_text.insert("end", f"{line}\n", ("value", "indent2"))
                    
                    # Regular text
                    else:
                        self.details_text.insert("end", f"{line}\n", ("value", "indent1"))
                        
                except Exception as e:
                    self.log_message(f"Error formatting line '{line}': {e}")
                    # Insert the line as plain text if formatting fails
                    try:
                        self.details_text.insert("end", f"{line}\n", "value")
                    except:
                        pass
                    
        except Exception as e:
            self.log_message(f"Error in _insert_formatted_analysis: {e}")

    def _insert_formatted_indicators(self, indicators_content):
        """Insert formatted investigative indicators with error handling"""
        try:
            if not indicators_content:
                return
                
            lines = indicators_content.split('\n')
            
            for line in lines:
                try:
                    original_line = line
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Main section headers
                    if line.isupper() and any(char in line for char in ['-', '=']):
                        self.details_text.insert("end", f"{line}\n", ("header2", "indent1"))
                    
                    # Important indicators with highlighting
                    elif any(keyword in line.lower() for keyword in ['verification codes', 'banking messages', 'dual sim']):
                        if "banking" in line.lower():
                            self.details_text.insert("end", f"{line}\n", ("warning", "indent1"))
                        elif "verification" in line.lower():
                            self.details_text.insert("end", f"{line}\n", ("success", "indent1"))
                        elif "dual sim" in line.lower():
                            self.details_text.insert("end", f"{line}\n", ("important", "indent1"))
                        else:
                            self.details_text.insert("end", f"{line}\n", ("header3", "indent1"))
                    
                    # Detail items
                    elif original_line.startswith('  ') and line.startswith('-'):
                        detail = line[1:].strip()
                        
                        # Highlight specific types of data
                        if any(keyword in detail.lower() for keyword in ['discord', 'verification', 'code']):
                            self.details_text.insert("end", f"• {detail}\n", ("success", "indent2"))
                        elif any(keyword in detail.lower() for keyword in ['bank', 'visa', 'mastercard', 'payment']):
                            self.details_text.insert("end", f"• {detail}\n", ("warning", "indent2"))
                        elif detail.startswith('+'):  # International numbers
                            self.details_text.insert("end", f"• {detail}\n", ("code", "indent2"))
                        else:
                            self.details_text.insert("end", f"• {detail}\n", ("value", "indent2"))
                    
                    # Category headers or other content
                    elif line.endswith(':'):
                        self.details_text.insert("end", f"{line}\n", ("header3", "indent1"))
                    
                    # Regular content
                    else:
                        self.details_text.insert("end", f"{line}\n", ("value", "indent1"))
                        
                except Exception as e:
                    self.log_message(f"Error formatting indicator line '{line}': {e}")
                    # Insert as plain text if formatting fails
                    try:
                        self.details_text.insert("end", f"{line}\n", "value")
                    except:
                        pass
                    
        except Exception as e:
            self.log_message(f"Error in _insert_formatted_indicators: {e}")
        
    def setup_files_tab(self):
        """Set up the files tab with enhanced file listing and search"""
        # Main container
        files_frame = ctk.CTkFrame(self.files_tab)
        files_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Header section
        header_frame = ctk.CTkFrame(files_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 10))
        
        header = ctk.CTkLabel(
            header_frame,
            text="File Collection & External Media Results",
            font=("Arial", 16, "bold")
        )
        header.pack(side="left")
        
        # File count label
        self.files_count_label = ctk.CTkLabel(
            header_frame,
            text="",
            font=("Arial", 12),
            text_color="gray"
        )
        self.files_count_label.pack(side="right")
        
        # Search and filter section
        search_frame = ctk.CTkFrame(files_frame, fg_color="transparent")
        search_frame.pack(fill="x", pady=(0, 10))
        
        # Search bar
        search_label = ctk.CTkLabel(search_frame, text="Search:")
        search_label.pack(side="left", padx=(0, 5))
        
        self.files_search_var = tk.StringVar()
        self.files_search_entry = ctk.CTkEntry(
            search_frame,
            textvariable=self.files_search_var,
            placeholder_text="Search by filename, path, or extension...",
            width=300
        )
        self.files_search_entry.pack(side="left", padx=(0, 10))
        self.files_search_var.trace_add("write", self._on_files_search_changed)
        
        # Filter dropdown
        filter_label = ctk.CTkLabel(search_frame, text="Filter:")
        filter_label.pack(side="left", padx=(10, 5))
        
        self.files_filter_var = ctk.StringVar(value="All Files")
        self.files_filter_dropdown = ctk.CTkComboBox(
            search_frame,
            variable=self.files_filter_var,
            values=["All Files", "Videos", "Images", "Downloads", "My Downloads"],
            command=self._on_files_filter_changed,
            width=150
        )
        self.files_filter_dropdown.pack(side="left", padx=(0, 10))
        
        # Clear search button
        clear_button = ctk.CTkButton(
            search_frame,
            text="Clear",
            command=self._clear_files_search,
            width=80,
            height=28
        )
        clear_button.pack(side="left")
        
        # Export button
        export_button = ctk.CTkButton(
            search_frame,
            text="Export List",
            command=self._export_files_list,
            width=100,
            height=28
        )
        export_button.pack(side="right")
        
        # Files tree with improved layout
        tree_frame = ctk.CTkFrame(files_frame, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True)
        
        # Create files tree with enhanced columns
        columns = ("Type", "Name", "Path", "Size", "Modified", "Extension")
        self.files_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=20)
        
        # Configure column headings
        self.files_tree.heading("Type", text="Type")
        self.files_tree.heading("Name", text="File Name")
        self.files_tree.heading("Path", text="Path")
        self.files_tree.heading("Size", text="Size")
        self.files_tree.heading("Modified", text="Modified")
        self.files_tree.heading("Extension", text="Ext")
        
        # Set column widths
        self.files_tree.column("Type", width=100)
        self.files_tree.column("Name", width=250)
        self.files_tree.column("Path", width=350)
        self.files_tree.column("Size", width=80)
        self.files_tree.column("Modified", width=120)
        self.files_tree.column("Extension", width=60)
        
        # Add scrollbars
        files_v_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.files_tree.yview)
        files_h_scrollbar = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.files_tree.xview)
        self.files_tree.configure(yscrollcommand=files_v_scrollbar.set, xscrollcommand=files_h_scrollbar.set)
        
        # Pack widgets
        self.files_tree.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=(0, 5))
        files_v_scrollbar.grid(row=0, column=1, sticky="ns", pady=(0, 5))
        files_h_scrollbar.grid(row=1, column=0, sticky="ew", padx=(0, 5))
        
        # Configure grid weights
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # Double-click event for file details
        self.files_tree.bind("<Double-1>", self._on_file_double_click)
        
        # Right-click context menu
        self.files_tree.bind("<Button-2>", self._show_file_context_menu)  # macOS right-click
        self.files_tree.bind("<Button-3>", self._show_file_context_menu)  # Windows/Linux right-click
        
        # Store all files data for searching/filtering
        self.all_files_data = []
        self.displayed_files_data = []
        
        # Add initial message
        self.files_tree.insert("", "end", values=("", "File collection and external media results will appear here after triage", "", "", "", ""))
    
    def _on_files_search_changed(self, *args):
        """Handle search text changes"""
        self._filter_and_display_files()
    
    def _on_files_filter_changed(self, *args):
        """Handle filter dropdown changes"""
        self._filter_and_display_files()
    
    def _clear_files_search(self):
        """Clear search and filters"""
        self.files_search_var.set("")
        self.files_filter_var.set("All Files")
        self._filter_and_display_files()
    
    def _filter_and_display_files(self):
        """Filter and display files based on search and filter criteria"""
        try:
            if not hasattr(self, 'all_files_data') or not self.all_files_data:
                return
            
            search_text = self.files_search_var.get().lower()
            filter_type = self.files_filter_var.get()
            
            # Filter files
            filtered_files = []
            for file_data in self.all_files_data:
                # Apply type filter
                if filter_type != "All Files" and file_data.get('file_type', '') != filter_type:
                    continue
                
                # Apply search filter
                if search_text:
                    name = file_data.get('display_name', '').lower()
                    path = file_data.get('data_path', '').lower()
                    ext = file_data.get('extension', '').lower()
                    
                    if not (search_text in name or search_text in path or search_text in ext):
                        continue
                
                filtered_files.append(file_data)
            
            # Update display
            self._display_filtered_files(filtered_files)
            
        except Exception as e:
            self.log_message(f"Error filtering files: {e}")
    
    def _display_filtered_files(self, files_data):
        """Display filtered files in the tree"""
        try:
            # Clear current display
            self.files_tree.delete(*self.files_tree.get_children())
            
            if not files_data:
                self.files_tree.insert("", "end", values=("", "No files match the current filter", "", "", "", ""))
                self.files_count_label.configure(text="0 files")
                return
            
            # Group files by type for better organization
            files_by_type = {}
            for file_data in files_data:
                file_type = file_data.get('file_type', 'Unknown')
                if file_type not in files_by_type:
                    files_by_type[file_type] = []
                files_by_type[file_type].append(file_data)
            
            total_displayed = 0
            
            # Display files grouped by type
            for file_type in sorted(files_by_type.keys()):
                type_files = files_by_type[file_type]
                
                # Add type header if showing all types
                if self.files_filter_var.get() == "All Files" and len(files_by_type) > 1:
                    type_emoji = self._get_type_emoji(file_type)
                    self.files_tree.insert("", "end", values=(
                        f"{type_emoji} {file_type.upper()}",
                        f"({len(type_files)} files)",
                        "", "", "", ""
                    ), tags=("header",))
                
                # Add individual files
                for file_data in type_files:
                    self.files_tree.insert("", "end", values=(
                        file_data.get('file_type', ''),
                        file_data.get('display_name', ''),
                        file_data.get('data_path', ''),
                        file_data.get('size_str', ''),
                        file_data.get('date_str', ''),
                        file_data.get('extension', '')
                    ), tags=("file",))
                    total_displayed += 1
            
            # Configure tags for better visual appearance
            self.files_tree.tag_configure("header", background="#E3E3E3", font=("Arial", 10, "bold"))
            self.files_tree.tag_configure("file", background="white")
            
            # Update count display
            total_files = len(self.all_files_data)
            if total_displayed == total_files:
                self.files_count_label.configure(text=f"{total_files:,} files")
            else:
                self.files_count_label.configure(text=f"{total_displayed:,} of {total_files:,} files")
            
        except Exception as e:
            self.log_message(f"Error displaying filtered files: {e}")
    
    def _get_type_emoji(self, file_type):
        """Get emoji for file type"""
        emoji_map = {
            "Videos": "📹",
            "Images": "📷", 
            "Downloads": "📥",
            "My Downloads": "📁"
        }
        return emoji_map.get(file_type, "📄")
    
    def _on_file_double_click(self, event):
        """Handle double-click on file to show details"""
        try:
            selection = self.files_tree.selection()
            if not selection:
                return
            
            item = self.files_tree.item(selection[0])
            values = item['values']
            
            if len(values) >= 6 and values[0]:  # Valid file entry
                file_name = values[1]
                file_path = values[2]
                file_size = values[3]
                file_modified = values[4]
                file_ext = values[5]
                
                # Show file details dialog
                self._show_file_details_dialog(file_name, file_path, file_size, file_modified, file_ext)
                
        except Exception as e:
            self.log_message(f"Error showing file details: {e}")
    
    def _show_file_details_dialog(self, name, path, size, modified, extension):
        """Show detailed file information dialog"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("File Details")
        dialog.geometry("600x400")
        dialog.transient(self)
        
        # Main frame
        main_frame = ctk.CTkFrame(dialog)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title
        title_label = ctk.CTkLabel(main_frame, text="File Information", font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))
        
        # File details
        details_text = ctk.CTkTextbox(main_frame, height=250)
        details_text.pack(fill="both", expand=True, pady=(0, 20))
        
        details_content = f"""File Name: {name}
Full Path: {path}
Size: {size}
Modified: {modified}
Extension: {extension}
        
File Path (for manual access):
{path}

Note: This information is the result of a file system query. Verify file still exists on system if relevant."""
        
        details_text.insert("1.0", details_content)
        details_text.configure(state="disabled")
        
        # Close button
        close_button = ctk.CTkButton(main_frame, text="Close", command=dialog.destroy)
        close_button.pack()
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
    
    def _show_file_context_menu(self, event):
        """Show context menu for file operations"""
        try:
            # Select the item under cursor
            item = self.files_tree.identify_row(event.y)
            if item:
                self.files_tree.selection_set(item)
                
                # Create context menu
                context_menu = tk.Menu(self, tearoff=0)
                context_menu.add_command(label="Show Details", command=lambda: self._on_file_double_click(event))
                context_menu.add_separator()
                context_menu.add_command(label="Copy Path", command=self._copy_file_path)
                context_menu.add_command(label="Copy Name", command=self._copy_file_name)
                
                # Show menu
                context_menu.tk_popup(event.x_root, event.y_root)
                
        except Exception as e:
            self.log_message(f"Error showing context menu: {e}")
    
    def _copy_file_path(self):
        """Copy selected file path to clipboard"""
        try:
            selection = self.files_tree.selection()
            if selection:
                item = self.files_tree.item(selection[0])
                path = item['values'][2] if len(item['values']) > 2 else ""
                if path:
                    self.clipboard_clear()
                    self.clipboard_append(path)
                    self.log_message(f"Copied file path to clipboard: {path}")
        except Exception as e:
            self.log_message(f"Error copying file path: {e}")
    
    def _copy_file_name(self):
        """Copy selected file name to clipboard"""
        try:
            selection = self.files_tree.selection()
            if selection:
                item = self.files_tree.item(selection[0])
                name = item['values'][1] if len(item['values']) > 1 else ""
                if name:
                    self.clipboard_clear()
                    self.clipboard_append(name)
                    self.log_message(f"Copied file name to clipboard: {name}")
        except Exception as e:
            self.log_message(f"Error copying file name: {e}")
    
    def _export_files_list(self):
        """Export current file list to CSV"""
        try:
            if not hasattr(self, 'displayed_files_data') or not self.all_files_data:
                messagebox.showwarning("No Data", "No files to export")
                return
            
            # Get save location
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title="Export Files List"
            )
            
            if filename:
                import csv
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    
                    # Write header
                    writer.writerow(["Type", "Name", "Path", "Size", "Modified", "Extension"])
                    
                    # Write data based on current filter
                    search_text = self.files_search_var.get().lower()
                    filter_type = self.files_filter_var.get()
                    
                    exported_count = 0
                    for file_data in self.all_files_data:
                        # Apply same filters as display
                        if filter_type != "All Files" and file_data.get('file_type', '') != filter_type:
                            continue
                        
                        if search_text:
                            name = file_data.get('display_name', '').lower()
                            path = file_data.get('data_path', '').lower()
                            ext = file_data.get('extension', '').lower()
                            
                            if not (search_text in name or search_text in path or search_text in ext):
                                continue
                        
                        writer.writerow([
                            file_data.get('file_type', ''),
                            file_data.get('display_name', ''),
                            file_data.get('data_path', ''),
                            file_data.get('size_str', ''),
                            file_data.get('date_str', ''),
                            file_data.get('extension', '')
                        ])
                        exported_count += 1
                
                messagebox.showinfo("Export Complete", f"Exported {exported_count} files to {filename}")
                self.log_message(f"Exported {exported_count} files to {filename}")
                
        except Exception as e:
            messagebox.showerror("Export Error", f"Error exporting files: {e}")
            self.log_message(f"Error exporting files: {e}")
    
    def setup_thumbnails_tab(self):
        """Set up the thumbnails tab for image previews"""
        thumbnails_frame = ctk.CTkFrame(self.thumbnails_tab)
        thumbnails_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Header
        header = ctk.CTkLabel(
            thumbnails_frame,
            text="Screen Captures",
            font=("Arial", 16, "bold")
        )
        header.pack(pady=(0, 10))
        
        # Placeholder for thumbnails display
        placeholder_label = ctk.CTkLabel(
            thumbnails_frame,
            text="Under development. Check back soon...",
            font=("Arial", 12)
        )
        placeholder_label.pack(expand=True)

    def setup_apps_tab(self):
        """Set up the apps tab with search functionality and table display"""
        apps_frame = ctk.CTkFrame(self.apps_tab)
        apps_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Search bar at the top
        search_frame = ctk.CTkFrame(apps_frame)
        search_frame.pack(fill="x", padx=10, pady=5)
        
        search_label = ctk.CTkLabel(search_frame, text="Search Apps:")
        search_label.pack(side="left", padx=5)
        
        # Initialize the search variable
        self.app_search_var = ctk.StringVar()
        
        # Create search entry
        search_entry = ctk.CTkEntry(search_frame, width=200, textvariable=self.app_search_var)
        search_entry.pack(side="left", fill="x", expand=True, padx=5)
        
        # Add search button for explicit searching
        search_button = ctk.CTkButton(
            search_frame, 
            text="Search",
            width=80,
            command=lambda: self.filter_apps()
        )
        search_button.pack(side="right", padx=5)
        
        # Connect the trace for real-time search
        self.app_search_var.trace_add("write", self.filter_apps)
        
        # User information frame
        user_info_frame = ctk.CTkFrame(apps_frame)
        user_info_frame.pack(fill="x", padx=10, pady=5)
        
        # User information labels
        user_info_label = ctk.CTkLabel(user_info_frame, text="Current User:", font=ctk.CTkFont(weight="bold"))
        user_info_label.pack(side="left", padx=10)
        
        self.current_user_number_label = ctk.CTkLabel(user_info_frame, text="User Number: Not Available")
        self.current_user_number_label.pack(side="left", padx=10)
        
        self.current_user_name_label = ctk.CTkLabel(user_info_frame, text="User Name: Not Available")
        self.current_user_name_label.pack(side="left", padx=10)
        
        # Info frame for count display
        info_frame = ctk.CTkFrame(apps_frame)
        info_frame.pack(fill="x", padx=10, pady=5)
        
        self.apps_count_label = ctk.CTkLabel(info_frame, text="Apps will appear here after triage")
        self.apps_count_label.pack(side="left", padx=10)
        
        # Create apps table using Treeview
        table_frame = ctk.CTkFrame(apps_frame)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Define columns for the apps table
        columns = ("User ID", "App Name", "Package Name", "Version", "Install Time", "Update Time")
        
        self.apps_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)
        
        # Configure color tags for user highlighting
        self.apps_tree.tag_configure("user0", background="#F5F5F5", foreground="#333333")      # Light gray for primary user
        self.apps_tree.tag_configure("user10", background="#E8F4FD", foreground="#1565C0")    # Light blue for work profile
        self.apps_tree.tag_configure("user150", background="#FFCDD2", foreground="#B71C1C")   # Red highlight for user 150 (Secure Folder)
        self.apps_tree.tag_configure("other", background="#FFFFFF", foreground="#666666")     # White for other users
        
        # Configure column headings and widths
        self.apps_tree.heading("User ID", text="User ID")
        self.apps_tree.heading("App Name", text="App Name")
        self.apps_tree.heading("Package Name", text="Package Name")
        self.apps_tree.heading("Version", text="Version")
        self.apps_tree.heading("Install Time", text="Install Time")
        self.apps_tree.heading("Update Time", text="Update Time")
        
        # Set column widths
        self.apps_tree.column("User ID", width=80, minwidth=60)
        self.apps_tree.column("App Name", width=200, minwidth=150)
        self.apps_tree.column("Package Name", width=250, minwidth=200)
        self.apps_tree.column("Version", width=100, minwidth=80)
        self.apps_tree.column("Install Time", width=150, minwidth=120)
        self.apps_tree.column("Update Time", width=150, minwidth=120)
        
        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.apps_tree.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.apps_tree.xview)
        self.apps_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack the table and scrollbars
        self.apps_tree.pack(side="left", fill="both", expand=True)
        v_scrollbar.pack(side="right", fill="y")
        h_scrollbar.pack(side="bottom", fill="x")

    def setup_sms_tab(self):
        """Set up the SMS tab with search functionality and table display"""
        sms_frame = ctk.CTkFrame(self.sms_tab)
        sms_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Search bar at the top
        search_frame = ctk.CTkFrame(sms_frame)
        search_frame.pack(fill="x", padx=10, pady=5)
        
        search_label = ctk.CTkLabel(search_frame, text="Search SMS:")
        search_label.pack(side="left", padx=5)
        
        # Initialize search variable
        self.sms_search_var = ctk.StringVar()
        
        # Create search entry
        search_entry = ctk.CTkEntry(search_frame, width=200, textvariable=self.sms_search_var)
        search_entry.pack(side="left", fill="x", expand=True, padx=5)
        
        # Add search button
        search_button = ctk.CTkButton(
            search_frame, 
            text="Search",
            width=80,
            command=lambda: self.filter_sms()
        )
        search_button.pack(side="right", padx=5)
        
        # Connect the trace for real-time search
        self.sms_search_var.trace_add("write", self.filter_sms)
        
        # Info frame for count display
        info_frame = ctk.CTkFrame(sms_frame)
        info_frame.pack(fill="x", padx=10, pady=5)
        
        self.sms_count_label = ctk.CTkLabel(info_frame, text="SMS messages will appear here after triage")
        self.sms_count_label.pack(side="left", padx=10)
        
        # Create SMS table using Treeview
        table_frame = ctk.CTkFrame(sms_frame)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Define columns for the SMS table
        columns = ("Date", "Type", "Address", "Message", "Thread ID")
        
        self.sms_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)
        
        # Configure color tags for SMS message types
        self.sms_tree.tag_configure("received", background="#E8F5E8", foreground="#2E7D32")  # Light green for received
        self.sms_tree.tag_configure("sent", background="#E3F2FD", foreground="#1565C0")      # Light blue for sent
        self.sms_tree.tag_configure("draft", background="#FFF3E0", foreground="#F57C00")    # Light orange for draft
        self.sms_tree.tag_configure("failed", background="#FFEBEE", foreground="#C62828")   # Light red for failed
        self.sms_tree.tag_configure("user150", background="#FFCDD2", foreground="#B71C1C")  # Red highlight for user 150
        
        # Configure column headings and widths
        self.sms_tree.heading("Date", text="Date/Time")
        self.sms_tree.heading("Type", text="Type")
        self.sms_tree.heading("Address", text="Phone Number")
        self.sms_tree.heading("Message", text="Message")
        self.sms_tree.heading("Thread ID", text="Thread ID")
        
        # Set column widths
        self.sms_tree.column("Date", width=150, minwidth=120)
        self.sms_tree.column("Type", width=80, minwidth=60)
        self.sms_tree.column("Address", width=120, minwidth=100)
        self.sms_tree.column("Message", width=300, minwidth=200)
        self.sms_tree.column("Thread ID", width=80, minwidth=60)
        
        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.sms_tree.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.sms_tree.xview)
        self.sms_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack the table and scrollbars
        self.sms_tree.pack(side="left", fill="both", expand=True)
        v_scrollbar.pack(side="right", fill="y")
        h_scrollbar.pack(side="bottom", fill="x")

    def setup_mms_tab(self):
        """Set up the MMS tab with search functionality and table display"""
        mms_frame = ctk.CTkFrame(self.mms_tab)
        mms_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Search bar at the top
        search_frame = ctk.CTkFrame(mms_frame)
        search_frame.pack(fill="x", padx=10, pady=5)
        
        search_label = ctk.CTkLabel(search_frame, text="Search MMS:")
        search_label.pack(side="left", padx=5)
        
        # Initialize search variable
        self.mms_search_var = ctk.StringVar()
        
        # Create search entry
        search_entry = ctk.CTkEntry(search_frame, width=200, textvariable=self.mms_search_var)
        search_entry.pack(side="left", fill="x", expand=True, padx=5)
        
        # Add search button
        search_button = ctk.CTkButton(
            search_frame, 
            text="Search",
            width=80,
            command=lambda: self.filter_mms()
        )
        search_button.pack(side="right", padx=5)
        
        # Connect the trace for real-time search
        self.mms_search_var.trace_add("write", self.filter_mms)
        
        # Info frame for count display
        info_frame = ctk.CTkFrame(mms_frame)
        info_frame.pack(fill="x", padx=10, pady=5)
        
        self.mms_count_label = ctk.CTkLabel(info_frame, text="MMS messages will appear here after triage")
        self.mms_count_label.pack(side="left", padx=10)
        
        # Create MMS table using Treeview
        table_frame = ctk.CTkFrame(mms_frame)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Define columns for the MMS table
        columns = ("Date", "Type", "Subject", "Size", "Thread ID", "Message Box")
        
        self.mms_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)
        
        # Configure color tags for MMS message types (same as SMS)
        self.mms_tree.tag_configure("received", background="#E8F5E8", foreground="#2E7D32")  # Light green for received
        self.mms_tree.tag_configure("sent", background="#E3F2FD", foreground="#1565C0")      # Light blue for sent
        self.mms_tree.tag_configure("draft", background="#FFF3E0", foreground="#F57C00")    # Light orange for draft
        self.mms_tree.tag_configure("failed", background="#FFEBEE", foreground="#C62828")   # Light red for failed
        self.mms_tree.tag_configure("user150", background="#FFCDD2", foreground="#B71C1C")  # Red highlight for user 150
        
        # Configure column headings and widths
        self.mms_tree.heading("Date", text="Date/Time")
        self.mms_tree.heading("Type", text="Type")
        self.mms_tree.heading("Subject", text="Subject")
        self.mms_tree.heading("Size", text="Size")
        self.mms_tree.heading("Thread ID", text="Thread ID")
        self.mms_tree.heading("Message Box", text="Message Box")
        
        # Set column widths
        self.mms_tree.column("Date", width=150, minwidth=120)
        self.mms_tree.column("Type", width=80, minwidth=60)
        self.mms_tree.column("Subject", width=200, minwidth=150)
        self.mms_tree.column("Size", width=80, minwidth=60)
        self.mms_tree.column("Thread ID", width=80, minwidth=60)
        self.mms_tree.column("Message Box", width=100, minwidth=80)
        
        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.mms_tree.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.mms_tree.xview)
        self.mms_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack the table and scrollbars
        self.mms_tree.pack(side="left", fill="both", expand=True)
        v_scrollbar.pack(side="right", fill="y")
        h_scrollbar.pack(side="bottom", fill="x")

    def setup_contacts_tab(self):
        """Set up the contacts tab with search functionality and table display"""
        contacts_frame = ctk.CTkFrame(self.contacts_tab)
        contacts_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Search bar at the top
        search_frame = ctk.CTkFrame(contacts_frame)
        search_frame.pack(fill="x", padx=10, pady=5)
        
        search_label = ctk.CTkLabel(search_frame, text="Search Contacts:")
        search_label.pack(side="left", padx=5)
        
        # Initialize search variable
        self.contacts_search_var = ctk.StringVar()
        
        # Create search entry
        search_entry = ctk.CTkEntry(search_frame, width=200, textvariable=self.contacts_search_var)
        search_entry.pack(side="left", fill="x", expand=True, padx=5)
        
        # Add search button
        search_button = ctk.CTkButton(
            search_frame, 
            text="Search",
            width=80,
            command=lambda: self.filter_contacts()
        )
        search_button.pack(side="right", padx=5)
        
        # Connect the trace for real-time search
        self.contacts_search_var.trace_add("write", self.filter_contacts)
        
        # Info frame for count display
        info_frame = ctk.CTkFrame(contacts_frame)
        info_frame.pack(fill="x", padx=10, pady=5)
        
        self.contacts_count_label = ctk.CTkLabel(info_frame, text="Contacts will appear here after triage")
        self.contacts_count_label.pack(side="left", padx=10)
        
        # Create contacts table using Treeview
        table_frame = ctk.CTkFrame(contacts_frame)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Define columns for the contacts table
        columns = ("Name", "Phone", "Email", "Organization", "Contact ID", "Data Items")
        
        self.contacts_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)
        
        # Configure color tags for user 150 highlighting
        self.contacts_tree.tag_configure("user150", background="#FFCDD2", foreground="#B71C1C")  # Red highlight for user 150
        
        # Configure column headings and widths
        self.contacts_tree.heading("Name", text="Display Name")
        self.contacts_tree.heading("Phone", text="Phone Number")
        self.contacts_tree.heading("Email", text="Email Address")
        self.contacts_tree.heading("Organization", text="Organization")
        self.contacts_tree.heading("Contact ID", text="Contact ID")
        self.contacts_tree.heading("Data Items", text="Data Items")
        
        # Set column widths
        self.contacts_tree.column("Name", width=180, minwidth=150)
        self.contacts_tree.column("Phone", width=120, minwidth=100)
        self.contacts_tree.column("Email", width=150, minwidth=120)
        self.contacts_tree.column("Organization", width=120, minwidth=100)
        self.contacts_tree.column("Contact ID", width=80, minwidth=60)
        self.contacts_tree.column("Data Items", width=120, minwidth=100)
        
        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.contacts_tree.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.contacts_tree.xview)
        self.contacts_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack the table and scrollbars
        self.contacts_tree.pack(side="left", fill="both", expand=True)
        v_scrollbar.pack(side="right", fill="y")
        h_scrollbar.pack(side="bottom", fill="x")

    def setup_call_logs_tab(self):
        """Set up the call logs tab with search functionality and table display"""
        call_logs_frame = ctk.CTkFrame(self.call_logs_tab)
        call_logs_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Search bar at the top
        search_frame = ctk.CTkFrame(call_logs_frame)
        search_frame.pack(fill="x", padx=10, pady=5)
        
        search_label = ctk.CTkLabel(search_frame, text="Search Call Logs:")
        search_label.pack(side="left", padx=5)
        
        # Initialize search variable
        self.call_logs_search_var = ctk.StringVar()
        
        # Create search entry
        search_entry = ctk.CTkEntry(search_frame, width=200, textvariable=self.call_logs_search_var)
        search_entry.pack(side="left", fill="x", expand=True, padx=5)
        
        # Add search button
        search_button = ctk.CTkButton(
            search_frame, 
            text="Search",
            width=80,
            command=lambda: self.filter_call_logs()
        )
        search_button.pack(side="right", padx=5)
        
        # Connect the trace for real-time search
        self.call_logs_search_var.trace_add("write", self.filter_call_logs)
        
        # Info frame for count display
        info_frame = ctk.CTkFrame(call_logs_frame)
        info_frame.pack(fill="x", padx=10, pady=5)
        
        self.call_logs_count_label = ctk.CTkLabel(info_frame, text="Call logs will appear here after triage")
        self.call_logs_count_label.pack(side="left", padx=10)
        
        # Create call logs table using Treeview
        table_frame = ctk.CTkFrame(call_logs_frame)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Define columns for the call logs table
        columns = ("Date", "Type", "Number", "Name", "Duration", "Location")
        
        self.call_logs_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)
        
        # Configure color tags for call log types
        self.call_logs_tree.tag_configure("incoming", background="#E8F5E8", foreground="#2E7D32")    # Light green for incoming
        self.call_logs_tree.tag_configure("outgoing", background="#E3F2FD", foreground="#1565C0")    # Light blue for outgoing
        self.call_logs_tree.tag_configure("missed", background="#FFEBEE", foreground="#C62828")      # Light red for missed
        self.call_logs_tree.tag_configure("voicemail", background="#F3E5F5", foreground="#7B1FA2")  # Light purple for voicemail
        self.call_logs_tree.tag_configure("rejected", background="#FFF3E0", foreground="#F57C00")   # Light orange for rejected
        self.call_logs_tree.tag_configure("blocked", background="#ECEFF1", foreground="#546E7A")    # Light gray for blocked
        self.call_logs_tree.tag_configure("user150", background="#FFCDD2", foreground="#B71C1C")    # Red highlight for user 150
        
        # Configure column headings and widths
        self.call_logs_tree.heading("Date", text="Date/Time")
        self.call_logs_tree.heading("Type", text="Call Type")
        self.call_logs_tree.heading("Number", text="Phone Number")
        self.call_logs_tree.heading("Name", text="Contact Name")
        self.call_logs_tree.heading("Duration", text="Duration")
        self.call_logs_tree.heading("Location", text="Location")
        
        # Set column widths
        self.call_logs_tree.column("Date", width=150, minwidth=120)
        self.call_logs_tree.column("Type", width=100, minwidth=80)
        self.call_logs_tree.column("Number", width=120, minwidth=100)
        self.call_logs_tree.column("Name", width=150, minwidth=120)
        self.call_logs_tree.column("Duration", width=80, minwidth=60)
        self.call_logs_tree.column("Location", width=150, minwidth=120)
        
        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.call_logs_tree.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.call_logs_tree.xview)
        self.call_logs_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack the table and scrollbars
        self.call_logs_tree.pack(side="left", fill="both", expand=True)
        v_scrollbar.pack(side="right", fill="y")
        h_scrollbar.pack(side="bottom", fill="x")

    def setup_notifications_tab(self):
        """Set up the notifications tab with search functionality and table display"""
        notifications_frame = ctk.CTkFrame(self.notifications_tab)
        notifications_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Search bar at the top
        search_frame = ctk.CTkFrame(notifications_frame)
        search_frame.pack(fill="x", padx=10, pady=5)
        
        search_label = ctk.CTkLabel(search_frame, text="Search Notifications:")
        search_label.pack(side="left", padx=5)
        
        # Initialize search variable
        self.notifications_search_var = ctk.StringVar()
        
        # Create search entry
        search_entry = ctk.CTkEntry(search_frame, width=200, textvariable=self.notifications_search_var)
        search_entry.pack(side="left", fill="x", expand=True, padx=5)
        
        # Add search button
        search_button = ctk.CTkButton(
            search_frame, 
            text="Search",
            width=80,
            command=lambda: self.filter_notifications()
        )
        search_button.pack(side="right", padx=5)
        
        # Connect the trace for real-time search
        self.notifications_search_var.trace_add("write", self.filter_notifications)
        
        # Info frame for count display
        info_frame = ctk.CTkFrame(notifications_frame)
        info_frame.pack(fill="x", padx=10, pady=5)
        
        self.notifications_count_label = ctk.CTkLabel(info_frame, text="Notifications will appear here after triage")
        self.notifications_count_label.pack(side="left", padx=10)
        
        # Create notifications table using Treeview for better performance
        table_frame = ctk.CTkFrame(notifications_frame)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Define columns for the notifications table
        columns = ("Time", "App", "Title", "Text", "Channel", "Importance")
        
        self.notifications_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)
        
        # Configure color tags for notification importance levels
        self.notifications_tree.tag_configure("high", background="#FFE8E8", foreground="#B22222")       # Light red for high importance
        self.notifications_tree.tag_configure("default", background="#E8F0FF", foreground="#1E4A8C")   # Light blue for default
        self.notifications_tree.tag_configure("low", background="#F5F5F5", foreground="#696969")       # Light gray for low importance
        self.notifications_tree.tag_configure("min", background="#FFFEF0", foreground="#8B7D6B")       # Very light yellow for minimal
        self.notifications_tree.tag_configure("user150", background="#FFCDD2", foreground="#B71C1C")   # Red highlight for user 150
        
        # Configure column headings and widths
        self.notifications_tree.heading("Time", text="Time")
        self.notifications_tree.heading("App", text="App/Package")
        self.notifications_tree.heading("Title", text="Title")
        self.notifications_tree.heading("Text", text="Text")
        self.notifications_tree.heading("Channel", text="Channel")
        self.notifications_tree.heading("Importance", text="Importance")
        
        # Set column widths
        self.notifications_tree.column("Time", width=150, minwidth=120)
        self.notifications_tree.column("App", width=180, minwidth=150)
        self.notifications_tree.column("Title", width=200, minwidth=150)
        self.notifications_tree.column("Text", width=250, minwidth=200)
        self.notifications_tree.column("Channel", width=120, minwidth=100)
        self.notifications_tree.column("Importance", width=100, minwidth=80)
        
        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.notifications_tree.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.notifications_tree.xview)
        self.notifications_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack the table and scrollbars
        self.notifications_tree.pack(side="left", fill="both", expand=True)
        v_scrollbar.pack(side="right", fill="y")
        h_scrollbar.pack(side="bottom", fill="x")
        
        # Add double-click event to show notification details
        self.notifications_tree.bind("<Double-1>", self.show_notification_details)

    def filter_apps(self, *args):
        """Filter apps and display in table format with user 150 highlighting"""
        try:
            # Get search text
            search_text = self.app_search_var.get().lower() if hasattr(self, 'app_search_var') else ""
            
            # If we have no apps data, nothing to filter
            if not hasattr(self, 'apps_data') or not self.apps_data:
                self.log_message("No app data available to filter")
                return
                
            # Clear current table display
            if hasattr(self, 'apps_tree'):
                for item in self.apps_tree.get_children():
                    self.apps_tree.delete(item)
            
            # Filter apps
            filtered_apps = []
            for app in self.apps_data:
                # Check if it matches search term
                app_name = app.get("name", "").lower()
                package = app.get("package", "").lower()
                user_id = app.get("user_id", "")
                
                if not search_text or search_text in app_name or search_text in package or search_text in str(user_id):
                    filtered_apps.append(app)
            
            # Sort apps by user ID, then by app name
            filtered_apps.sort(key=lambda x: (x.get("user_id", "0"), x.get("name", "").lower() or x.get("package", "").lower()))
            
            # Populate the table
            for app in filtered_apps:
                user_id = app.get("user_id", "0")
                app_name = app.get("name", "") or app.get("package", "Unknown")
                package_name = app.get("package", "")
                version = app.get("version", "")
                install_time = app.get("install_time", "")
                update_time = app.get("update_time", "")
                
                # Determine color tag based on user ID
                if user_id == "150":
                    color_tag = "user150"  # Red highlight for user 150
                elif user_id == "0":
                    color_tag = "user0"    # Light gray for primary user
                elif user_id == "10":
                    color_tag = "user10"   # Light blue for work profile
                else:
                    color_tag = "other"    # Default for other users
                
                # Insert row into table with appropriate color tag
                self.apps_tree.insert("", "end", values=(
                    user_id,
                    app_name,
                    package_name,
                    version,
                    install_time,
                    update_time
                ), tags=(color_tag,))
            
            # Update count label
            total_filtered = len(filtered_apps)
            self.apps_count_label.configure(text=f"Showing {total_filtered} apps")
            
            # If no matches, add a message row
            if total_filtered == 0:
                self.apps_tree.insert("", "end", values=(
                    "No apps match your search criteria",
                    "", "", "", "", ""
                ))
            
        except Exception as e:
            self.log_message(f"Error filtering apps: {e}")
            import traceback
            self.log_message(traceback.format_exc())

    def filter_sms(self, *args):
        """Filter SMS messages based on search text and display in table format"""
        try:
            # Get search text
            search_text = self.sms_search_var.get().lower() if hasattr(self, 'sms_search_var') else ""
            
            # If we have no SMS data, nothing to filter
            if not hasattr(self, 'sms_data') or not self.sms_data:
                self.log_message("No SMS data available to filter")
                return
                
            # Clear current table display
            if hasattr(self, 'sms_tree'):
                for item in self.sms_tree.get_children():
                    self.sms_tree.delete(item)
            
            # Filter messages first (lightweight operation)
            filtered_messages = []
            for message in self.sms_data:
                # Check if message matches search term
                body = message.get("body", "").lower()
                address = message.get("address", "").lower()
                
                if not search_text or search_text in body or search_text in address:
                    filtered_messages.append(message)
            
            # Display all filtered messages (table view can handle large datasets efficiently)
            display_messages = filtered_messages
            
            # Populate the table
            for message in display_messages:
                # Format date
                date_raw = message.get("date", "")
                try:
                    # Convert timestamp to readable date
                    if date_raw and date_raw.isdigit():
                        timestamp = int(date_raw)
                        # SMS timestamps are typically in milliseconds
                        # Check if this looks like milliseconds (13+ digits) vs seconds (10 digits)
                        if len(str(timestamp)) >= 13:  # Milliseconds
                            try:
                                date_readable = datetime.datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
                            except (ValueError, OSError):
                                # If milliseconds fails, try treating as seconds
                                date_readable = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                        else:  # Seconds
                            try:
                                date_readable = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                            except (ValueError, OSError):
                                # If seconds fails, try treating as milliseconds
                                date_readable = datetime.datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        date_readable = date_raw
                except Exception:
                    date_readable = date_raw
                
                # Determine message type
                msg_type = "Received" if message.get("type") == "1" else "Sent"
                
                # Get address (phone number)
                address = message.get("address", "Unknown")
                
                # Get message body (truncate if very long for table display)
                body = message.get("body", "")
                if len(body) > 100:
                    body = body[:100] + "..."
                
                # Get thread ID
                thread_id = message.get("thread_id", "")
                
                # Determine color tag based on message type
                message_type = message.get("type", "")
                if message_type == "1":  # Received
                    color_tag = "received"
                elif message_type == "2":  # Sent
                    color_tag = "sent"
                elif message_type == "3":  # Draft
                    color_tag = "draft"
                elif message_type == "5":  # Failed
                    color_tag = "failed"
                else:
                    color_tag = ""  # Default, no color
                
                # Insert row into table with color tag
                self.sms_tree.insert("", "end", values=(
                    date_readable,
                    msg_type,
                    address,
                    body,
                    thread_id
                ), tags=(color_tag,))
            
            # Update count label
            total_filtered = len(filtered_messages)
            self.sms_count_label.configure(text=f"Showing {total_filtered} SMS messages")
            
            # If no matches, add a message row
            if total_filtered == 0:
                self.sms_tree.insert("", "end", values=(
                    "No SMS messages match your search criteria",
                    "", "", "", ""
                ))
            
        except Exception as e:
            self.log_message(f"Error filtering SMS: {e}")
            import traceback
            self.log_message(traceback.format_exc())

    def filter_mms(self, *args):
        """Filter MMS messages based on search text and display in table format"""
        try:
            # Get search text
            search_text = self.mms_search_var.get().lower() if hasattr(self, 'mms_search_var') else ""
            
            # If we have no MMS data, nothing to filter
            if not hasattr(self, 'mms_data') or not self.mms_data:
                self.log_message("No MMS data available to filter")
                return
                
            # Clear current table display
            if hasattr(self, 'mms_tree'):
                for item in self.mms_tree.get_children():
                    self.mms_tree.delete(item)
            
            # Filter messages first (lightweight operation)
            filtered_messages = []
            for message in self.mms_data:
                # Check if message matches search term
                subject = message.get("sub", "").lower()
                address = message.get("ct_l", "").lower()
                
                if not search_text or search_text in subject or search_text in address:
                    filtered_messages.append(message)
            
            # Display all filtered messages (table view can handle large datasets efficiently)
            display_messages = filtered_messages
            
            # Populate the table
            for message in display_messages:
                # Format date
                date_raw = message.get("date", "")
                try:
                    # Convert timestamp to readable date
                    if date_raw and date_raw.isdigit():
                        timestamp = int(date_raw)
                        # MMS timestamps are typically in seconds
                        # Check if this looks like milliseconds (13+ digits) vs seconds (10 digits)
                        if len(str(timestamp)) >= 13:  # Milliseconds
                            try:
                                date_readable = datetime.datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
                            except (ValueError, OSError):
                                # If milliseconds fails, try treating as seconds (maybe it's a very large seconds timestamp)
                                date_readable = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                        else:  # Seconds
                            try:
                                date_readable = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                            except (ValueError, OSError):
                                # If seconds fails, try treating as milliseconds
                                date_readable = datetime.datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        date_readable = date_raw
                except Exception:
                    date_readable = date_raw
                
                # Determine message type
                msg_type = "Received" if message.get("m_type") == "132" else "Sent"
                
                # Get subject
                subject = message.get("sub", "No Subject")
                if len(subject) > 50:
                    subject = subject[:50] + "..."
                
                # Get size
                size = message.get("m_size", "Unknown")
                
                # Get thread ID
                thread_id = message.get("thread_id", "")
                
                # Get message box type
                msg_box = message.get("msg_box", "")
                
                # Determine color tag based on message type
                m_type = message.get("m_type", "")
                msg_box_type = message.get("msg_box", "")
                if m_type == "132" or msg_box_type == "1":  # Received/Inbox
                    color_tag = "received"
                elif m_type == "128" or msg_box_type == "2":  # Sent/Outbox
                    color_tag = "sent"
                elif msg_box_type == "3":  # Draft
                    color_tag = "draft"
                elif msg_box_type == "4":  # Failed
                    color_tag = "failed"
                else:
                    color_tag = ""  # Default, no color
                
                # Insert row into table with color tag
                self.mms_tree.insert("", "end", values=(
                    date_readable,
                    msg_type,
                    subject,
                    size,
                    thread_id,
                    msg_box
                ), tags=(color_tag,))
            
            # Update count label
            total_filtered = len(filtered_messages)
            self.mms_count_label.configure(text=f"Showing {total_filtered} MMS messages")
            
            # If no matches, add a message row
            if total_filtered == 0:
                self.mms_tree.insert("", "end", values=(
                    "No MMS messages match your search criteria",
                    "", "", "", "", ""
                ))
            
        except Exception as e:
            self.log_message(f"Error filtering MMS: {e}")
            import traceback
            self.log_message(traceback.format_exc())

    def filter_contacts(self, *args):
        """Filter contacts based on search text and display in table format"""
        try:
            # Get search text
            search_text = self.contacts_search_var.get().lower() if hasattr(self, 'contacts_search_var') else ""
            
            # If we have no contacts data, nothing to filter
            if not hasattr(self, 'contacts_data') or not self.contacts_data:
                self.log_message("No contacts data available to filter")
                return
                
            # Clear current table display
            if hasattr(self, 'contacts_tree'):
                for item in self.contacts_tree.get_children():
                    self.contacts_tree.delete(item)
            
            # Filter contacts first
            filtered_contacts = []
            for contact in self.contacts_data:
                # Check if contact matches search term (new CSV structure)
                name = contact.get("display_name", "").lower()
                phones = contact.get("phone_numbers", "").lower()
                emails = contact.get("emails", "").lower()
                organization = contact.get("organization", "").lower()
                
                if not search_text or search_text in name or search_text in phones or search_text in emails or search_text in organization:
                    filtered_contacts.append(contact)
            
            # Populate the table directly (no additional grouping needed)
            for contact in filtered_contacts:
                name = contact.get("display_name", "")
                phones = contact.get("phone_numbers", "")
                emails = contact.get("emails", "")
                organization = contact.get("organization", "")
                contact_id = contact.get("contact_id", "")
                data_items = contact.get("data_count", "")
                
                # Insert row into table
                self.contacts_tree.insert("", "end", values=(
                    name,
                    phones,
                    emails,
                    organization,
                    contact_id,
                    data_items
                ))
            
            # Update count label
            total_filtered = len(filtered_contacts)
            self.contacts_count_label.configure(text=f"Showing {total_filtered} contacts")
            
            # If no matches, add a message row
            if total_filtered == 0:
                self.contacts_tree.insert("", "end", values=(
                    "No contacts match your search criteria",
                    "", "", "", "", ""
                ))
            
        except Exception as e:
            self.log_message(f"Error filtering contacts: {e}")
            import traceback
            self.log_message(traceback.format_exc())

    def filter_call_logs(self, *args):
        """Filter call logs based on search text and display in table format"""
        try:
            # Get search text
            search_text = self.call_logs_search_var.get().lower() if hasattr(self, 'call_logs_search_var') else ""
            
            # If we have no call logs data, nothing to filter
            if not hasattr(self, 'call_logs_data') or not self.call_logs_data:
                self.log_message("No call logs data available to filter")
               
                return
                
            # Clear current table display
            if hasattr(self, 'call_logs_tree'):
                for item in self.call_logs_tree.get_children():
                    self.call_logs_tree.delete(item)
            
            # Filter call logs first
            filtered_logs = []
            for log in self.call_logs_data:
                # Check if log matches search term
                number = log.get("number", "").lower()
                name = log.get("name", "").lower()
                
                if not search_text or search_text in number or search_text in name:
                    filtered_logs.append(log)
            
            # Populate the table
            for log in filtered_logs:
                # Format date
                date_raw = log.get("date", "")
                try:
                    if date_raw and date_raw.isdigit():
                        timestamp = int(date_raw)
                        # Call log timestamps are typically in milliseconds
                        # Check if this looks like milliseconds (13+ digits) vs seconds (10 digits)
                        if len(str(timestamp)) >= 13:  # Milliseconds
                            try:
                                date_readable = datetime.datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
                            except (ValueError, OSError):
                                # If milliseconds fails, try treating as seconds
                                date_readable = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                        else:  # Seconds
                            try:
                                date_readable = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                            except (ValueError, OSError):
                                # If seconds fails, try treating as milliseconds
                                date_readable = datetime.datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        date_readable = date_raw
                except Exception:
                    date_readable = date_raw
                
                # Determine call type - handle both numeric and string types
                call_type = log.get("type", "")
                type_name = "Unknown"
                color_tag = ""
                
                # Handle numeric type codes
                if call_type == "1" or call_type == 1:
                    type_name = "Incoming"
                    color_tag = "incoming"
                elif call_type == "2" or call_type == 2:
                    type_name = "Outgoing"
                    color_tag = "outgoing"
                elif call_type == "3" or call_type == 3:
                    type_name = "Missed"
                    color_tag = "missed"
                elif call_type == "4" or call_type == 4:
                    type_name = "Voicemail"
                    color_tag = "voicemail"
                elif call_type == "5" or call_type == 5:
                    type_name = "Rejected"
                    color_tag = "rejected"
                elif call_type == "6" or call_type == 6:
                    type_name = "Blocked"
                    color_tag = "blocked"
                # Handle string type names (for test data or converted data)
                elif isinstance(call_type, str):
                    call_type_lower = call_type.lower()
                    if call_type_lower in ["incoming", "inbound"]:
                        type_name = "Incoming"
                        color_tag = "incoming"
                    elif call_type_lower in ["outgoing", "outbound"]:
                        type_name = "Outgoing"
                        color_tag = "outgoing"
                    elif call_type_lower in ["missed", "missed call"]:
                        type_name = "Missed"
                        color_tag = "missed"
                    elif call_type_lower in ["voicemail", "voice mail"]:
                        type_name = "Voicemail"
                        color_tag = "voicemail"
                    elif call_type_lower in ["rejected", "decline", "declined"]:
                        type_name = "Rejected"
                        color_tag = "rejected"
                    elif call_type_lower in ["blocked", "spam"]:
                        type_name = "Blocked"
                        color_tag = "blocked"
                    else:
                        type_name = call_type  # Use the original string if it doesn't match known types
                
                # Format duration
                duration_sec = log.get("duration", "0")
                try:
                    duration_int = int(duration_sec)
                    if duration_int >= 3600:
                        duration_str = f"{duration_int // 3600}:{(duration_int % 3600) // 60:02d}:{duration_int % 60:02d}"
                    else:
                        duration_str = f"{duration_int // 60}:{duration_int % 60:02d}"
                except:
                    duration_str = duration_sec
                
                # Get other fields
                number = log.get("number", "Unknown")
                name = log.get("name", "")
                location = log.get("geocoded_location", "")
                
                # Insert row into table with color tag
                self.call_logs_tree.insert("", "end", values=(
                    date_readable,
                    type_name,
                    number,
                    name,
                    duration_str,
                    location
                ), tags=(color_tag,))
            
            # Update count label
            total_filtered = len(filtered_logs)
            self.call_logs_count_label.configure(text=f"Showing {total_filtered} call log entries")
            
            # If no matches, add a message row
            if total_filtered == 0:
                self.call_logs_tree.insert("", "end", values=(
                    "No call logs match your search criteria",
                    "", "", "", "", ""
                ))
            
        except Exception as e:
            self.log_message(f"Error filtering call logs: {e}")
            import traceback
            self.log_message(traceback.format_exc())
    def filter_notifications(self, *args):
        """Filter notifications based on search text and display in table format"""
        try:
            # Get search text
            search_text = self.notifications_search_var.get().lower() if hasattr(self, 'notifications_search_var') else ""
            
            # If we have no notifications data, nothing to filter
            if not hasattr(self, 'notifications_data') or not self.notifications_data:
                self.log_message("No notifications data available to filter")
                return
                
            # Clear current table display
            if hasattr(self, 'notifications_tree'):
                for item in self.notifications_tree.get_children():
                    self.notifications_tree.delete(item)
            
            # Filter notifications first
            filtered_notifications = []
            for notification in self.notifications_data:
                # Work with your actual CSV structure
                package = notification.get("package", "").lower()
                ticker_text = notification.get("ticker_text", "").lower()
                extras = notification.get("extras", "").lower()
                
                # Check if notification matches search term
                if not search_text or search_text in package or search_text in ticker_text or search_text in extras:
                    filtered_notifications.append(notification)
            
            # Display filtered notifications
            for notification in filtered_notifications:
                # Format time from 'when' field - handle multiple formats
                when_raw = notification.get("when", "")
                try:
                    if when_raw:
                        # Handle format like "1750519527144/1750519527144" - use first timestamp
                        if "/" in when_raw:
                            timestamp_str = when_raw.split("/")[0].strip()
                        else:
                            timestamp_str = when_raw.strip()
                        
                        if timestamp_str.isdigit():
                            timestamp = int(timestamp_str)
                            # Handle milliseconds timestamp (13+ digits) vs seconds (10 digits)
                            if len(str(timestamp)) >= 13:
                                time_readable = datetime.datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
                            else:
                                time_readable = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                        else:
                            time_readable = when_raw
                    else:
                        time_readable = "Unknown"
                except Exception as e:
                    self.log_message(f"Error parsing timestamp '{when_raw}': {e}")
                    time_readable = when_raw if when_raw else "Unknown"
                
                # Get package name
                app_name = notification.get("package", "Unknown")
                
                # Extract title from extras using a more flexible approach
                title = ""
                extras = notification.get("extras", "")
                
                # Look for android.title in extras
                if "android.title=String (" in extras:
                    try:
                        start = extras.find("android.title=String (") + len("android.title=String (")
                        end = extras.find(")", start)
                        if end > start:
                            title = extras[start:end]
                    except:
                        pass
                
                # If no title found, use ticker_text
                if not title:
                    ticker_text = notification.get("ticker_text", "")
                    if ticker_text and ticker_text != "null":
                        title = ticker_text
                
                # Extract text from extras
                text = ""
                if "android.text=" in extras:
                    try:
                        # Look for both String and SpannableString patterns
                        if "android.text=String (" in extras:
                            start = extras.find("android.text=String (") + len("android.text=String (")
                            end = extras.find(")", start)
                            if end > start:
                                text = extras[start:end]
                        elif "android.text=SpannableString (" in extras:
                            start = extras.find("android.text=SpannableString (") + len("android.text=SpannableString (")
                            end = extras.find(")", start)
                            if end > start:
                                text = extras[start:end]
                    except:
                        pass
                
                # Use title as text if no text found
                if not text:
                    text = title
                
                # Extract channel (optional since not in your data)
                channel = ""
                
                # Extract importance (optional since not in your data)  
                importance = ""
                
                # Truncate long text for table display
                display_title = title
                if len(display_title) > 50:
                    display_title = display_title[:50] + "..."
                
                display_text = text
                if len(display_text) > 80:
                    display_text = display_text[:80] + "..."
                
                # Use app name for display (truncate if too long)
                display_app_name = app_name
                if len(display_app_name) > 25:
                    display_app_name = display_app_name[:25] + "..."
                
                # Insert row into table
                self.notifications_tree.insert("", "end", values=(
                    time_readable,
                    display_app_name,
                    display_title,
                    display_text,
                    channel,
                    importance
                ))
            
            # Update count label
            total_filtered = len(filtered_notifications)
            self.notifications_count_label.configure(text=f"Showing {total_filtered} notification entries")
            
            # If no matches, add a message row
            if total_filtered == 0:
                self.notifications_tree.insert("", "end", values=(
                    "No notifications match your search criteria",
                    "", "", "", "", ""
                ))
            
        except Exception as e:
            self.log_message(f"Error filtering notifications: {e}")
            import traceback
            self.log_message(traceback.format_exc())

    def load_sms_data(self, csv_file_path):
        """Load SMS data from CSV file with progress indication"""
        try:
            self.sms_data = []
            
            if not os.path.exists(csv_file_path):
                self.log_message(f"SMS CSV file not found: {csv_file_path}")
                return
            
            # Show loading message
            # self.log_message("Loading SMS data...")
            import csv
            with open(csv_file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.sms_data.append(row)
                        
            # Update the initial display with a delay to prevent UI blocking
            self.queue_gui_update(self.filter_sms)
            
        except Exception as e:
            self.log_message(f"Error loading SMS data: {e}")
            import traceback
            self.log_message(traceback.format_exc())

    def load_mms_data(self, csv_file_path):
        """Load MMS data from CSV file with progress indication"""
        try:
            self.mms_data = []
            
            if not os.path.exists(csv_file_path):
                self.log_message(f"MMS CSV file not found: {csv_file_path}")
                return
            
            # Show loading message
            self.log_message("Loading MMS data...")
            import csv
            with open(csv_file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.mms_data.append(row)
                        
            # Update the initial display with a delay to prevent UI blocking
            self.queue_gui_update(self.filter_mms)
            
        except Exception as e:
            self.log_message(f"Error loading MMS data: {e}")
            import traceback
            self.log_message(traceback.format_exc())

    def load_contacts_data(self, csv_file_path):
        """Load contacts data from CSV file with progress indication"""
        try:
            self.contacts_data = []
            
            if not os.path.exists(csv_file_path):
                self.log_message(f"Contacts CSV file not found: {csv_file_path}")
                return
            
            # Show loading message
            self.log_message("Loading contacts data...")
            import csv
            with open(csv_file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.contacts_data.append(row)
            
            
            # Update the initial display immediately
            self.filter_contacts()
            
        except Exception as e:
            self.log_message(f"Error loading contacts data: {e}")
            import traceback
            self.log_message(traceback.format_exc())

    def load_call_logs_data(self, csv_file_path):
        """Load call logs data from CSV file with progress indication"""
        try:
            self.call_logs_data = []
            
            if not os.path.exists(csv_file_path):
                self.log_message(f"Call logs CSV file not found: {csv_file_path}")
                return
            
            # Show loading message
            self.log_message("Loading call logs data...")
            import csv
            with open(csv_file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.call_logs_data.append(row)
            
            
            # Update the initial display with a delay to prevent UI blocking
            self.queue_gui_update(self.filter_call_logs)
            
        except Exception as e:
            self.log_message(f"Error loading call logs data: {e}")
            import traceback
            self.log_message(traceback.format_exc())

    def load_notifications_data(self, csv_file_path):
        """Load notifications data from CSV file with progress indication"""
        try:
            self.notifications_data = []
            
            if not os.path.exists(csv_file_path):
                self.log_message(f"Notifications CSV file not found: {csv_file_path}")
                return
            
            # Show loading message
            self.log_message("Loading notifications data...")
            import csv
            with open(csv_file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.notifications_data.append(row)
            
            
            # Update the initial display with a delay to prevent UI blocking
            self.queue_gui_update(self.filter_notifications)
            
        except Exception as e:
            self.log_message(f"Error loading notifications data: {e}")
            import traceback
            self.log_message(traceback.format_exc())

    def load_external_files_data(self, external_files):
        """Load external files data and display in enhanced Files tab"""
        try:
            # Initialize storage for all files data
            self.all_files_data = []
            
            # Clear existing files tree
            if hasattr(self, 'files_tree'):
                self.files_tree.delete(*self.files_tree.get_children())
                
                # Process each type of external files
                file_types = [
                    ("videos_data", "Videos", "external_videos.csv"),
                    ("images_data", "Images", "external_images.csv"),
                    ("downloads_data", "Downloads", "downloads.csv"),
                    ("my_downloads_data", "My Downloads", "my_downloads.csv")
                ]
                
                total_files_loaded = 0
                
                for data_key, file_type, csv_filename in file_types:
                    if external_files.get(data_key):
                        file_info = external_files[data_key]
                        record_count = file_info.get('record_count', 0)
                        csv_path = file_info.get('csv_file', '')
                        
                        if record_count > 0 and csv_path and os.path.exists(csv_path):
                            # Load all files from CSV (not just a sample)
                            files_loaded = self._load_all_external_files_from_csv(csv_path, file_type)
                            total_files_loaded += files_loaded
                            self.log_message(f"Loaded {files_loaded} {file_type.lower()} files")
                
                if total_files_loaded > 0:
                    # Update filter dropdown with available types
                    available_types = ["All Files"]
                    type_counts = {}
                    
                    for file_data in self.all_files_data:
                        file_type = file_data.get('file_type', '')
                        if file_type not in available_types:
                            available_types.append(file_type)
                        type_counts[file_type] = type_counts.get(file_type, 0) + 1
                    
                    # Update filter dropdown values
                    if hasattr(self, 'files_filter_dropdown'):
                        self.files_filter_dropdown.configure(values=available_types)
                    
                    # Display all files initially
                    self._filter_and_display_files()
                    
                    # Log summary by type
                    summary_parts = []
                    for file_type, count in type_counts.items():
                        summary_parts.append(f"{file_type}: {count:,}")
                    
                    self.log_message(f"Files tab updated with {total_files_loaded:,} total files ({', '.join(summary_parts)})")
                else:
                    # No files found
                    self.files_tree.insert("", "end", values=("", "No external files found or accessible", "", "", "", ""))
                    if hasattr(self, 'files_count_label'):
                        self.files_count_label.configure(text="0 files")
                    
        except Exception as e:
            self.log_message(f"Error loading external files data: {e}")
            import traceback
            self.log_message(traceback.format_exc())

    def _load_all_external_files_from_csv(self, csv_path, file_type):
        """Load all external files from CSV for enhanced display"""
        try:
            import csv
            files_loaded = 0
            
            with open(csv_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                for row in reader:
                    # Extract relevant fields for display
                    display_name = row.get('_display_name', '')
                    data_path = row.get('_data', '')
                    size = row.get('_size', '0')
                    date_added = row.get('date_added', '')
                    
                    # Determine file extension
                    extension = ""
                    if display_name:
                        parts = display_name.split('.')
                        if len(parts) > 1:
                            extension = parts[-1].lower()
                    
                    # Format size for display
                    try:
                        size_bytes = int(size) if size.isdigit() else 0
                        if size_bytes > 1024*1024*1024:
                            size_str = f"{size_bytes/(1024*1024*1024):.1f} GB"
                        elif size_bytes > 1024*1024:
                            size_str = f"{size_bytes/(1024*1024):.1f} MB"
                        elif size_bytes > 1024:
                            size_str = f"{size_bytes/1024:.1f} KB"
                        else:
                            size_str = f"{size_bytes} bytes"
                    except:
                        size_str = size if size else "Unknown"
                    
                    # Format date for display
                    try:
                        if date_added and date_added.isdigit():
                            import datetime
                            timestamp = int(date_added)
                            # Handle both seconds and milliseconds timestamps
                            if timestamp > 10000000000:  # Likely milliseconds
                                timestamp = timestamp / 1000
                            date_str = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M')
                        else:
                            date_str = date_added if date_added else "Unknown"
                    except:
                        date_str = date_added if date_added else "Unknown"
                    
                    # Create file data record
                    file_data = {
                        'file_type': file_type,
                        'display_name': display_name if display_name else f"File_{files_loaded + 1}",
                        'data_path': data_path,
                        'size_str': size_str,
                        'date_str': date_str,
                        'extension': extension,
                        'size_bytes': int(size) if size.isdigit() else 0
                    }
                    
                    self.all_files_data.append(file_data)
                    files_loaded += 1
                    
            return files_loaded
                    
        except Exception as e:
            self.log_message(f"Error loading files from {csv_path}: {e}")
            return 0


    def show_notification_details(self, event):
        """Show detailed notification information in a popup"""
        try:
            # Get the selected item
            selection = self.notifications_tree.selection()
            if not selection:
                return
            
            # Get the item data
            item = self.notifications_tree.item(selection[0])
            if not item or not item['values']:
                return
            
            # Find the corresponding notification data
            values = item['values']
            if len(values) < 6:
                return
                
            time_readable = values[0]
            package = values[1]
            
            # Find the full notification data
            matching_notification = None
            if hasattr(self, 'notifications_data'):
                for notification in self.notifications_data:
                    notif_time = notification.get("when_readable", notification.get("creation_time_readable", ""))
                    notif_package = notification.get("package", "")
                    
                    if time_readable == notif_time and package.startswith(notif_package[:25]):
                        matching_notification = notification
                        break
            
            if not matching_notification:
                messagebox.showinfo("Details", "No detailed information available for this notification.")
                return
            
            # Create detail window
            detail_window = ctk.CTkToplevel(self)
            detail_window.title("Notification Details")
            detail_window.geometry("600x500")
            detail_window.transient(self)
            detail_window.grab_set()
            
            # Create scrollable text widget
            detail_text = ctk.CTkTextbox(
                detail_window,
                wrap="word",
                font=("Arial", 12)
            )
            detail_text.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Format the notification details
            details = "NOTIFICATION DETAILS\n"
            details += "=" * 50 + "\n\n"
            
            for key, value in matching_notification.items():
                if value and str(value).strip():  # Only show non-empty values
                    formatted_key = key.replace('_', ' ').title()
                    details += f"{formatted_key}: {value}\n"
            
            detail_text.insert("1.0", details)
            detail_text.configure(state="disabled")
            
            # Add close button
            close_button = ctk.CTkButton(
                detail_window,
                text="Close",
                command=detail_window.destroy
            )
            close_button.pack(pady=10)
            
        except Exception as e:
            self.log_message(f"Error showing notification details: {e}")
            import traceback
            self.log_message(traceback.format_exc())

    # def run_triage(self):
    #     """Run triage with selected options"""
    #     try:
    #         # Get case info
    #         case_number = self.case_entry.get().strip()
    #         output_dir = self.output_dir_var.get()
            
    #         if not case_number:
    #             messagebox.showerror("Error", "Please enter a case number")
    #             return
                
    #         if not output_dir or not os.path.isdir(output_dir):
    #             messagebox.showerror("Error", "Please select a valid output directory")
    #             return
            
    #         # Verify device connection
    #         if not self.triage_handler.is_device_connected():
    #             messagebox.showerror("Error", "No device connected. Please connect a device and try again.")
    #             return
                
    #         # Get optional settings
    #         collect_files = False
    #         collect_thumbnails = False
    #         calculate_hashes = False
                
    #         # Build triage profile
    #         triage_options = {
    #             # Mandatory options
    #             "apps": True,
    #             "device_details": True,
                
    #             # Optional operations
    #             "filenames": collect_files,
    #             "thumbnails": collect_thumbnails,
    #             "hashes": calculate_hashes
    #         }
            
            
    #         # Start triage in background thread
    #         threading.Thread(
    #             target=self._triage_thread,
    #             args=(case_number, output_dir, triage_options),
    #             daemon=True
    #         ).start()
            
    #     except Exception as e:
    #         self.log_message(f"Error starting triage: {e}")
    #         import traceback
    #         self.log_message(traceback.format_exc())

    def _triage_thread(self, case_number, output_dir, options):
        """Run triage in background thread"""
        try:
            start_time = time.time()

            self.log_message(f"Starting triage for case: {case_number}")
            self.update_progress(0.1)
            
            # Create timestamp for the operation
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Create case folder
            case_folder = os.path.join(output_dir, f"Android_Triage_{case_number}_{timestamp}")
            os.makedirs(case_folder, exist_ok=True)
            
            # Dictionary to store all results
            results = {}
            
            # ALWAYS COLLECT DEVICE DETAILS (mandatory)
            self.log_message("Collecting device details...")
            device_details = self.triage_handler.get_all_device_details()
            results["device_details"] = device_details
            
            # Update progress
            self.update_progress(0.2)
            
            # ALWAYS COLLECT APP DATA (mandatory)
            self.log_message("Collecting app data...")
            apps = self.triage_handler.get_installed_apps()
            results["apps"] = apps
            
            # Update progress
            self.update_progress(0.3)
            
            # MANDATORY: Extract content artifacts (SMS, MMS, Contacts, Call Logs)
            self.log_message("Extracting content artifacts (SMS, MMS, Contacts, Call Logs)...")
            try:
                artifacts_results = self.triage_handler.extract_content_artifacts(case_folder, self.log_message)
                results["artifacts"] = artifacts_results
                
                # Log artifact extraction results
                artifact_summary = []
                if artifacts_results.get("sms_data"):
                    artifact_summary.append(f"SMS: {artifacts_results['sms_data']['record_count']} records")
                if artifacts_results.get("mms_data"):
                    artifact_summary.append(f"MMS: {artifacts_results['mms_data']['record_count']} records")
                if artifacts_results.get("contacts_data"):
                    artifact_summary.append(f"Contacts: {artifacts_results['contacts_data']['record_count']} records")
                if artifacts_results.get("call_logs_data"):
                    artifact_summary.append(f"Call Logs: {artifacts_results['call_logs_data']['record_count']} records")
                
                if artifact_summary:
                    self.log_message(f"Content artifacts extracted: {', '.join(artifact_summary)}")
                else:
                    self.log_message("No content artifacts found or accessible")
                    
            except Exception as e:
                self.log_message(f"Error extracting content artifacts: {str(e)}")
                results["artifacts"] = {"error": str(e)}
            
            # Update progress
            self.update_progress(0.5)
            
            # MANDATORY: Extract notification data
            self.log_message("Extracting notification data...")
            try:
                notifications_results = self.triage_handler.collect_notifications(case_folder, self.log_message)
                results["notifications"] = notifications_results
                
                if notifications_results.get("notifications_data"):
                    record_count = notifications_results["notifications_data"]["record_count"]
                    self.log_message(f"Notification data extracted: {record_count} records")
                else:
                    self.log_message("No notification data found or accessible")
                    
            except Exception as e:
                self.log_message(f"Error extracting notification data: {str(e)}")
                results["notifications"] = {"error": str(e)}
            
            # Update progress
            self.update_progress(0.6)
            
            # MANDATORY: Extract external files (videos, images, downloads)
            self.log_message("Extracting external files (videos, images, downloads)...")
            try:
                external_files_results = self.triage_handler.extract_external_files(case_folder, self.log_message)
                results["external_files"] = external_files_results
                
                # Log external files extraction results
                external_summary = []
                if external_files_results.get("videos_data"):
                    external_summary.append(f"Videos: {external_files_results['videos_data']['record_count']} files")
                if external_files_results.get("images_data"):
                    external_summary.append(f"Images: {external_files_results['images_data']['record_count']} files")
                if external_files_results.get("downloads_data"):
                    external_summary.append(f"Downloads: {external_files_results['downloads_data']['record_count']} files")
                if external_files_results.get("my_downloads_data"):
                    external_summary.append(f"My Downloads: {external_files_results['my_downloads_data']['record_count']} files")
                
                if external_summary:
                    self.log_message(f"External files extracted: {', '.join(external_summary)}")
                else:
                    self.log_message("No external files found or accessible")
                    
            except Exception as e:
                self.log_message(f"Error extracting external files: {str(e)}")
                results["external_files"] = {"error": str(e)}
            
            # Update progress
            self.update_progress(0.65)
            
            # OPTIONAL: Collect file names
            if options.get("filenames", False):
                self.log_message("Collecting file names...")
                file_results = self.triage_handler.collect_file_names(
                    output_dir=output_dir,
                    case_number=case_number,
                    extensions=[".jpg", ".png", ".mp4", ".pdf", ".docx", ".xlsx", ".txt"],
                    status_callback=self.log_message
                )
                results["file_collection"] = file_results
                
            # Update progress
            self.update_progress(0.7)
            
            # OPTIONAL: Collect thumbnails
            if options.get("thumbnails", False):
                self.log_message("Collecting thumbnails...")
                thumbnail_results = self.triage_handler.collect_thumbnails(
                    output_dir=output_dir,
                    case_number=case_number,
                    status_callback=self.log_message
                )
                results["thumbnails"] = thumbnail_results
                
            # Update progress
            self.update_progress(0.8)
            
            # OPTIONAL: Calculate hashes
            if options.get("hashes", False):
                self.log_message("Calculating file hashes...")
                hash_results = self.triage_handler.calculate_hashes(
                    output_dir=output_dir,
                    case_number=case_number,
                    status_callback=self.log_message
                )
                results["hashes"] = hash_results
                
            # Update progress
            self.update_progress(0.9)
            
            # Generate final report
            self.log_message("Generating triage report...")
            report_path = self._generate_report(case_folder, results, case_number)
            results["report_path"] = report_path
            
            end_time = time.time()
            total_seconds = int(end_time - start_time)

            if total_seconds >= 60:
                minutes = total_seconds // 60
                seconds = total_seconds % 60
                time_display = f"{minutes} minute(s) and {seconds} second(s)"
            else:
                time_display = f"{total_seconds} second(s)"

            # Update progress
            self.update_progress(1.0)
            
            # Update UI with results
            self.queue_gui_update(lambda: self.update_results(results))
            
            # Complete
            self.log_message(f"Triage completed successfully for case: {case_number}")
            time.sleep(0.5)  # time to update UI
            self.log_message(f"Completed in: {time_display}")
            
        except Exception as e:
            self.log_message(f"Error during triage: {e}")
            import traceback
            self.log_message(traceback.format_exc())
        finally:
            # Re-enable UI
            self.queue_gui_update(lambda: self.enable_triage_options())
            self.update_progress(0)
    
 
    def clear_app_data(self):
        """Clear cached app data when device disconnects"""
        try:
            if hasattr(self, 'apps_data'):
                delattr(self, 'apps_data')
            
            # Clear apps display
            if hasattr(self, 'apps_listbox'):
                self.apps_listbox.configure(state="normal")
                self.apps_listbox.delete("1.0", "end")
                self.apps_listbox.insert("1.0", "App information will appear here after running triage...")
                self.apps_listbox.configure(state="disabled")
                
        except Exception as e:
            print(f"Error clearing app data: {e}")

    def update_device_info(self, info_text):
        """Update the device info text box"""
        if hasattr(self, 'details_text'):
            self.details_text.configure(state="normal")
            self.details_text.delete("1.0", "end")
            self.details_text.insert("1.0", info_text)
            self.details_text.configure(state="disabled")

    def enable_triage_options(self):
        """Enable all triage option buttons when device is connected"""
        try:
            # Enable all the triage buttons
            if hasattr(self, 'quick_triage_button'):
                self.quick_triage_button.configure(state="normal")
            if hasattr(self, 'full_triage_button'):
                self.full_triage_button.configure(state="normal")
            if hasattr(self, 'custom_triage_button'):
                self.custom_triage_button.configure(state="normal")
            if hasattr(self, 'live_analysis_button'):
                self.live_analysis_button.configure(state="normal")
                
            # Update any other UI elements that should be enabled
            # self.log_message("Triage options enabled")
            
        except Exception as e:
            print(f"Error enabling triage options: {e}")

    def disable_triage_options(self):
        """Disable all triage option buttons when device is disconnected"""
        try:
            # Disable all the triage buttons
            if hasattr(self, 'quick_triage_button'):
                self.quick_triage_button.configure(state="disabled")
            if hasattr(self, 'full_triage_button'):
                self.full_triage_button.configure(state="disabled")
            if hasattr(self, 'custom_triage_button'):
                self.custom_triage_button.configure(state="disabled")
            if hasattr(self, 'live_analysis_button'):
                self.live_analysis_button.configure(state="disabled")
                
            # Update any other UI elements that should be disabled
            self.log_message("Triage options disabled")
            
        except Exception as e:
            print(f"Error disabling triage options: {e}")

    def log_message(self, message):
        """Add a message to the status log"""
        try:
            # Get timestamp
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            
            # Format log entry
            log_entry = f"[{timestamp}] {message}\n"
            
            # Queue the GUI update instead of direct access
            def update_log():
                try:
                    if hasattr(self, 'log_text'):
                        self.log_text.configure(state="normal")
                        self.log_text.insert("end", log_entry)
                        self.log_text.see("end")  # Scroll to end
                        self.log_text.configure(state="disabled")
                except Exception as e:
                    print(f"Error updating log text: {e}")
            
            self.queue_gui_update(update_log)
                
            # Print to console as fallback
            print(log_entry.strip())
            
        except Exception as e:
            print(f"Error logging message: {e}")
            print(message)

    def update_progress(self, value):
        """Update the progress bar with the given value (0.0 to 1.0)"""
        try:
            if hasattr(self, 'progress_bar') and self.progress_bar:
                # Queue the GUI update instead of direct access
                def update_bar():
                    try:
                        self.progress_bar.set(value)
                    except Exception as e:
                        print(f"Error updating progress bar: {e}")
                
                self.queue_gui_update(update_bar)
        except Exception as e:
            print(f"Error updating progress: {e}")

    def _generate_report(self, case_folder, results, case_number):
        """Generate a comprehensive triage report with forensic analysis"""
        try:
            # Generate text report (keep for compatibility)
            report_path = os.path.join(case_folder, "triage_report.txt")
            
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write("ANDROID TRIAGE REPORT\n")
                f.write("=" * 50 + "\n\n")
                
                # Use case_number parameter from main app
                f.write(f"Case Number: {case_number}\n")
                f.write(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Case Folder: {case_folder}\n")
                
                # Add execution time if available
                if "execution_time" in results:
                    f.write(f"Execution Time: {results['execution_time']}\n")
                
                f.write("\n")
                
                # Device details with identifiers
                if "device_details" in results:
                    f.write("DEVICE INFORMATION & IDENTIFIERS:\n")
                    f.write("-" * 40 + "\n")
                    for key, value in results["device_details"].items():
                        if key != "Users":  # Handle users separately
                            f.write(f"{key}: {value}\n")
                    f.write("\n")
                    
                    # Add users to device details
                    if "Users" in results["device_details"]:
                        f.write("Device Users:\n")
                        users = results["device_details"]["Users"]
                        if isinstance(users, list):
                            for user in users:
                                if isinstance(user, dict):
                                    user_id = user.get('id', 'Unknown')
                                    user_name = user.get('name', 'Unknown')
                                    user_type = user.get('type', 'Unknown')
                                    f.write(f"  - User {user_id}: {user_name} ({user_type})\n")
                        f.write("\n")
                
                # Apps summary
                if "apps" in results:
                    f.write(f"APPLICATIONS: {len(results['apps'])} installed\n")
                    f.write("-" * 30 + "\n")
                    
                    # Group apps by user for summary
                    apps_by_user = {}
                    for app in results["apps"]:
                        user_id = app.get("user_id", "0")
                        if user_id not in apps_by_user:
                            apps_by_user[user_id] = []
                        apps_by_user[user_id].append(app)
                    
                    for user_id in sorted(apps_by_user.keys()):
                        user_type = "Primary"
                        if user_id == "10":
                            user_type = "Work Profile"
                        elif user_id == "150":
                            user_type = "Secure Folder"
                        f.write(f"User {user_id} ({user_type}): {len(apps_by_user[user_id])} apps\n")
                    f.write("\n")
                
                # Content artifacts with forensic analysis
                if "artifacts" in results:
                    artifacts = results["artifacts"]
                    if "artifacts" in results and "analysis_files" in results["artifacts"]:
                        f.write("FORENSIC ANALYSIS FILES (Reports folder):\n")  # Updated description
                        f.write("-" * 40 + "\n")  # Adjusted separator length
                        analysis_files = results["artifacts"]["analysis_files"]
                        
                        if analysis_files.get('sms_data'):
                            f.write("SMS Analysis: Reports/sms_forensic_analysis.txt\n")  # Added folder path
                        if analysis_files.get('mms_data'):
                            f.write("MMS Analysis: Reports/mms_forensic_analysis.txt\n")  # Added folder path
                        if analysis_files.get('contacts_data'):
                            f.write("Contacts Analysis: Reports/contacts_forensic_analysis.txt\n")  # Added folder path
                        if analysis_files.get('call_logs_data'):
                            f.write("Call Logs Analysis: Reports/call_logs_forensic_analysis.txt\n")  # Added folder path
                        f.write("\n")
                    elif artifacts.get('error'):
                        f.write("CONTENT ARTIFACTS & FORENSIC ANALYSIS:\n")
                        f.write("-" * 45 + "\n")
                        f.write(f"Error extracting artifacts: {artifacts['error']}\n\n")
                
                # Notifications summary
                if "notifications" in results and results["notifications"]:
                    notifications = results["notifications"]
                    if notifications.get('notifications_data'):
                        f.write(f"NOTIFICATIONS: {notifications['notifications_data']['record_count']} entries\n")
                        f.write("-" * 30 + "\n")
                        f.write(f"Notifications data saved to: Artifacts/Notifications/ folder\n\n")
                    else:
                        f.write("NOTIFICATIONS: No notification data found\n")
                        f.write("-" * 30 + "\n\n")
                # External files summary
                if "external_files" in results and results["external_files"]:
                    external_files = results["external_files"]
                    if external_files and not external_files.get('error'):
                        f.write("EXTERNAL FILES:\n")
                        f.write("-" * 30 + "\n")
                        
                        total_external = 0
                        if external_files.get('videos_data'):
                            count = external_files['videos_data']['record_count']
                            f.write(f"Videos: {count} files\n")
                            total_external += count
                        
                        if external_files.get('images_data'):
                            count = external_files['images_data']['record_count']
                            f.write(f"Images: {count} files\n")
                            total_external += count
                        
                        if external_files.get('downloads_data'):
                            count = external_files['downloads_data']['record_count']
                            f.write(f"Downloads: {count} files\n")
                            total_external += count
                        
                        if external_files.get('my_downloads_data'):
                            count = external_files['my_downloads_data']['record_count']
                            f.write(f"My Downloads: {count} files\n")
                            total_external += count
                        
                        f.write(f"Total External Files: {total_external}\n")
                        f.write(f"External files data saved to: Artifacts/External_Files/ folder\n\n")  # Updated path
                    elif external_files.get('error'):
                        f.write("EXTERNAL FILES:\n")
                        f.write("-" * 30 + "\n")
                        f.write(f"Error extracting external files: {external_files['error']}\n\n")
 
                # Analysis files summary
                if "artifacts" in results and "analysis_files" in results["artifacts"]:
                    f.write("FORENSIC ANALYSIS FILES:\n")
                    f.write("-" * 30 + "\n")
                    analysis_files = results["artifacts"]["analysis_files"]
                    
                    if analysis_files.get('sms_data'):
                        f.write("SMS Analysis: sms_forensic_analysis.txt\n")
                    if analysis_files.get('mms_data'):
                        f.write("MMS Analysis: mms_forensic_analysis.txt\n")
                    if analysis_files.get('contacts_data'):
                        f.write("Contacts Analysis: contacts_forensic_analysis.txt\n")
                    if analysis_files.get('call_logs_data'):
                        f.write("Call Logs Analysis: call_logs_forensic_analysis.txt\n")
                    f.write("\n")
                
                # Optional operations summary
                optional_ops = ["file_collection", "thumbnails", "hashes"]
                for op in optional_ops:
                    if op in results and results[op]:
                        op_name = op.replace('_', ' ').title()
                        f.write(f"{op_name}: Completed\n")
                
                f.write(f"\nReport generated successfully at: {report_path}\n")
            
            # Generate PDF report
            try:
                pdf_generator = AndroidTriagePDFGenerator()
                
                # Extract case number from case folder name
                case_number = os.path.basename(case_folder).split('_')[2] if '_' in os.path.basename(case_folder) else "Unknown"
                
                pdf_path = pdf_generator.generate_report(case_folder, results, case_number)
                
                
            except Exception as pdf_error:
                print(f"PDF generation error: {pdf_error}")
                import traceback
                traceback.print_exc()
            
            results["report_path"] = report_path
            return report_path
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return None
        
    def update_results(self, results):
        """Update UI with triage results"""
        try:
            self.log_message("Updating results display...")
            
            # Update apps list
            if "apps" in results and results["apps"]:
                self.log_message(f"Processing {len(results['apps'])} apps")
                
                # Store the apps data for filtering
                self.apps_data = results["apps"]
                
                # Update user information display now that we have data
                self.update_user_info_display()
                
                # Run the initial filtering (displays all apps)
                self.filter_apps()
            
            # Update artifacts data (SMS, MMS, Contacts, Call Logs)
            if "artifacts" in results and results["artifacts"]:
                artifacts = results["artifacts"]
                self.log_message("Processing content artifacts...")
                
                # Update forensic summary from analysis files
                self.update_forensic_summary(artifacts)
                
                # Process SMS data
                if "sms_data" in artifacts and artifacts["sms_data"]:
                    sms_info = artifacts["sms_data"]
                    if "csv_file" in sms_info and os.path.exists(sms_info["csv_file"]):
                        self.load_sms_data(sms_info["csv_file"])
                        self.log_message(f"Loaded {sms_info.get('record_count', 0)} SMS messages")
                
                # Process MMS data  
                if "mms_data" in artifacts and artifacts["mms_data"]:
                    mms_info = artifacts["mms_data"]
                    if "csv_file" in mms_info and os.path.exists(mms_info["csv_file"]):
                        self.load_mms_data(mms_info["csv_file"])
                        self.log_message(f"Loaded {mms_info.get('record_count', 0)} MMS messages")
                
                # Process Contacts data
                if "contacts_data" in artifacts and artifacts["contacts_data"]:
                    contacts_info = artifacts["contacts_data"]
                    if "csv_file" in contacts_info and os.path.exists(contacts_info["csv_file"]):
                        self.load_contacts_data(contacts_info["csv_file"])
                        self.log_message(f"Loaded {contacts_info.get('record_count', 0)} contacts")
                
                # Process Call Logs data
                if "call_logs_data" in artifacts and artifacts["call_logs_data"]:
                    call_logs_info = artifacts["call_logs_data"]
                    if "csv_file" in call_logs_info and os.path.exists(call_logs_info["csv_file"]):
                        self.load_call_logs_data(call_logs_info["csv_file"])
                        self.log_message(f"Loaded {call_logs_info.get('record_count', 0)} call log entries")
            
            # Process notification data
            if "notifications" in results and results["notifications"]:
                notifications = results["notifications"]
                if notifications.get('notifications_data'):
                    notifications_info = notifications["notifications_data"]
                    if "csv_file" in notifications_info and os.path.exists(notifications_info["csv_file"]):
                        self.load_notifications_data(notifications_info["csv_file"])
                        self.log_message(f"Loaded {notifications_info.get('record_count', 0)} notification entries")
        
            # Process external files data
            if "external_files" in results and results["external_files"]:
                external_files = results["external_files"]
                self.log_message("Processing external files data...")
                
                # Load external files data into the Files tab
                self.load_external_files_data(external_files)
                
                # Log summary of external files
                external_summary = []
                if external_files.get("videos_data"):
                    external_summary.append(f"Videos: {external_files['videos_data']['record_count']} files")
                if external_files.get("images_data"):
                    external_summary.append(f"Images: {external_files['images_data']['record_count']} files")
                if external_files.get("downloads_data"):
                    external_summary.append(f"Downloads: {external_files['downloads_data']['record_count']} files")
                if external_files.get("my_downloads_data"):
                    external_summary.append(f"My Downloads: {external_files['my_downloads_data']['record_count']} files")
                
                if external_summary:
                    self.log_message(f"External files loaded: {', '.join(external_summary)}")
                else:
                    self.log_message("No external files found or accessible")
            
            # Update device details if available
            if "device_details" in results:
                self.update_device_details(results["device_details"])
            
        except Exception as e:
            self.log_message(f"Error updating results: {e}")
            import traceback
            self.log_message(traceback.format_exc())

    def update_forensic_summary(self, artifacts_results):
        """Update forensic summary from analysis results"""
        try:
            if not artifacts_results or "analysis_files" not in artifacts_results:
                return
                
            summary_lines = []
            
            # Parse key insights from each analysis file
            for analysis_type, analysis_file in artifacts_results["analysis_files"].items():
                if os.path.exists(analysis_file):
                    try:
                        with open(analysis_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                            
                        if "SMS" in analysis_type.upper():
                            # Extract and store the FULL SIM card analysis section
                            sim_section = self._extract_full_sim_analysis(content)
                            if sim_section:
                                self.full_sim_analysis = sim_section  # Store complete analysis
                            
                            # Extract executive summary for brief overview
                            exec_summary = self._extract_executive_summary(content)
                            if exec_summary:
                                self.executive_summary = exec_summary
                            
                            # Extract investigative indicators
                            investigative_section = self._extract_investigative_indicators(content)
                            if investigative_section:
                                self.investigative_indicators = investigative_section
                            
                            # Brief summary lines for the summary section
                            if "Total Messages:" in content:
                                total_match = re.search(r'Total Messages: (\d+)', content)
                                if total_match:
                                    summary_lines.append(f"SMS Messages: {total_match.group(1)} total")
                            
                            if "Unique Contacts:" in content:
                                contacts_match = re.search(r'Unique Contacts: (\d+)', content)
                                if contacts_match:
                                    summary_lines.append(f"SMS Contacts: {contacts_match.group(1)} unique")
                            
                            if "Verification Codes Found:" in content:
                                codes_match = re.search(r'Verification Codes Found: (\d+)', content)
                                if codes_match:
                                    summary_lines.append(f"Verification Codes: {codes_match.group(1)} found")
                            
                            if "DUAL SIM DEVICE DETECTED" in content:
                                summary_lines.append("⚠️ DUAL SIM DEVICE DETECTED")
                        
                        elif "MMS" in analysis_type.upper():
                            # Extract full MMS analysis
                            mms_analysis = self._extract_full_section(content, "MMS FORENSIC ANALYSIS", "END OF REPORT")
                            if mms_analysis:
                                self.full_mms_analysis = mms_analysis
                            
                            if "Total MMS Messages:" in content:
                                mms_match = re.search(r'Total MMS Messages: (\d+)', content)
                                if mms_match:
                                    summary_lines.append(f"MMS Messages: {mms_match.group(1)} total")
                        
                        elif "CONTACTS" in analysis_type.upper():
                            # Extract full contacts analysis
                            contacts_analysis = self._extract_full_section(content, "CONTACTS FORENSIC ANALYSIS", "")
                            if contacts_analysis:
                                self.full_contacts_analysis = contacts_analysis
                            
                            if "Total Phone Numbers:" in content:
                                phones_match = re.search(r'Total Phone Numbers: (\d+)', content)
                                if phones_match:
                                    summary_lines.append(f"Phone Numbers: {phones_match.group(1)} stored")
                        
                        elif "CALL" in analysis_type.upper():
                            # Extract full call logs analysis
                            call_analysis = self._extract_full_section(content, "CALL LOGS FORENSIC ANALYSIS", "")
                            if call_analysis:
                                self.full_call_analysis = call_analysis
                            
                            if "Total Call Records:" in content:
                                calls_match = re.search(r'Total Call Records: (\d+)', content)
                                if calls_match:
                                    summary_lines.append(f"Call Records: {calls_match.group(1)} total")
                    
                    except Exception as e:
                        self.log_message(f"Error parsing analysis file {analysis_file}: {e}")
            
            # Store the brief summary for display
            if summary_lines:
                self.forensic_summary = "\n".join(summary_lines) + "\n"
                self.log_message(f"Forensic summary updated with {len(summary_lines)} insights")
            
        except Exception as e:
            self.log_message(f"Error updating forensic summary: {e}")

    def _extract_full_sim_analysis(self, content):
        """Extract the complete SIM card analysis section from SMS analysis"""
        try:
            # Look for the SIM CARD ANALYSIS section
            start_marker = "SIM CARD ANALYSIS"
            start_pos = content.find(start_marker)
            if start_pos == -1:
                return None
            
            # Find the end of the SIM section (next major section)
            next_sections = ["MESSAGING APPLICATIONS", "TOP CONTACTS", "INVESTIGATIVE INDICATORS"]
            end_pos = len(content)  # Default to end of content
            
            for section in next_sections:
                section_pos = content.find(section, start_pos)
                if section_pos != -1:
                    end_pos = section_pos
                    break
            
            # Extract the section
            sim_section = content[start_pos:end_pos].strip()
            return sim_section
            
        except Exception as e:
            print(f"Error extracting SIM analysis: {e}")
            return None

    def _extract_executive_summary(self, content):
        """Extract the executive summary section"""
        try:
            start_marker = "EXECUTIVE SUMMARY"
            start_pos = content.find(start_marker)
            if start_pos == -1:
                return None
            
            # Find the end (next major section or double newline)
            end_markers = ["\n\nSIM CARD ANALYSIS", "\n\nMESSAGING APPLICATIONS", "\n\n"]
            end_pos = len(content)
            
            for marker in end_markers:
                marker_pos = content.find(marker, start_pos + len(start_marker))
                if marker_pos != -1:
                    end_pos = marker_pos
                    break
            
            summary_section = content[start_pos:end_pos].strip()
            return summary_section
            
        except Exception as e:
            print(f"Error extracting executive summary: {e}")
            return None

    def _extract_investigative_indicators(self, content):
        """Extract the investigative indicators section"""
        try:
            start_marker = "INVESTIGATIVE INDICATORS"
            start_pos = content.find(start_marker)
            if start_pos == -1:
                return None
            
            # Find the end (next major section or end of report)
            end_markers = ["=" * 60, "END OF REPORT"]
            end_pos = len(content)
            
            for marker in end_markers:
                marker_pos = content.find(marker, start_pos + len(start_marker))
                if marker_pos != -1:
                    end_pos = marker_pos
                    break
            
            indicators_section = content[start_pos:end_pos].strip()
            return indicators_section
            
        except Exception as e:
            print(f"Error extracting investigative indicators: {e}")
            return None

    def _extract_full_section(self, content, start_marker, end_marker):
        """Extract a complete section from analysis content"""
        try:
            start_pos = content.find(start_marker)
            if start_pos == -1:
                return None
            
            if end_marker:
                end_pos = content.find(end_marker, start_pos + len(start_marker))
                if end_pos == -1:
                    end_pos = len(content)
            else:
                end_pos = len(content)
            
            section = content[start_pos:end_pos].strip()
            return section
            
        except Exception as e:
            print(f"Error extracting section: {e}")
            return None

    
        """Format call analysis with call-specific icons"""
        try:
            lines = section_content.split('\n')
            formatted_lines = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    formatted_lines.append("")
                    continue
                    
                # Add call-specific formatting
                if "incoming calls:" in line.lower():
                    formatted_lines.append(f"   {line}")
                elif "outgoing calls:" in line.lower():
                    formatted_lines.append(f"   {line}")
                elif "missed calls:" in line.lower():
                    formatted_lines.append(f"   {line}")
                elif "total call time:" in line.lower():
                    formatted_lines.append(f"   {line}")
                elif "top 5 most contacted" in line.lower():
                    formatted_lines.append(f"   {line}")
                elif line.startswith(('1.', '2.', '3.', '4.', '5.')):
                    # Top contact entries
                    formatted_lines.append(f"     {line}")
                elif line.startswith('   '):
                    # Sub-details for contacts
                    if "talk time:" in line.lower():
                        formatted_lines.append(f"       {line.strip()}")
                    elif "last call:" in line.lower():
                        formatted_lines.append(f"       {line.strip()}")
                    else:
                        formatted_lines.append(f"       {line.strip()}")
                else:
                    formatted_lines.append(self._format_analysis_section(line))
            
            return '\n'.join(formatted_lines)
            
        except Exception as e:
            return section_content
        
    def update_user_info_display(self):
        """Update the user information display in the apps tab"""
        try:
            if not hasattr(self, 'triage_handler') or not self.triage_handler:
                return
                
            # Get current user information from the device
            device_info = self.triage_handler.get_device_basic_info()
            if device_info:
                # Try to get current user information
                current_user = device_info.get('current_user', 'Unknown')
                current_user_name = device_info.get('current_user_name', 'Unknown')
                
                # Update the labels if they exist
                if hasattr(self, 'current_user_number_label'):
                    self.current_user_number_label.configure(text=f"User Number: {current_user}")
                
                if hasattr(self, 'current_user_name_label'):
                    self.current_user_name_label.configure(text=f"User Name: {current_user_name}")
                    
                self.log_message(f"Updated user info - Number: {current_user}, Name: {current_user_name}")
            else:
                # If no device info available, try to get user info from ADB directly
                try:
                    # Get current user from ADB
                    import subprocess
                    result = subprocess.run(['adb', 'shell', 'am', 'get-current-user'], 
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        current_user = result.stdout.strip()
                        if hasattr(self, 'current_user_number_label'):
                            self.current_user_number_label.configure(text=f"User Number: {current_user}")
                        
                        # Try to get user name
                        name_result = subprocess.run(['adb', 'shell', 'pm', 'list', 'users'], 
                                                   capture_output=True, text=True, timeout=5)
                        if name_result.returncode == 0:
                            # Parse user list to find the current user's name
                            for line in name_result.stdout.split('\n'):
                                if f'id={current_user}' in line:
                                    # Extract name from line like "UserInfo{0:Owner:c13} running"
                                    import re
                                    match = re.search(r'id=\d+:(.*?):', line)
                                    if match:
                                        user_name = match.group(1)
                                        if hasattr(self, 'current_user_name_label'):
                                            self.current_user_name_label.configure(text=f"User Name: {user_name}")
                                        break
                except Exception as e:
                    self.log_message(f"Could not retrieve user info via ADB: {e}")
                    
        except Exception as e:
            self.log_message(f"Error updating user info display: {e}")