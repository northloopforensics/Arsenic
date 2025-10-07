# Copyright (c) 2025 North Loop Consulting, LLC

import os
import datetime
import subprocess
import time
import tarfile
from subprocess import Popen, PIPE, run
import platform
import hashlib
from typing import BinaryIO, Callable
from io import BytesIO
import sys
import re
import traceback
import stat
import csv
import datetime
import re
import json

# Windows-specific subprocess flag to prevent console windows
if sys.platform == "win32":
    SUBPROCESS_FLAGS = subprocess.CREATE_NO_WINDOW
else:
    SUBPROCESS_FLAGS = 0
import threading
import queue

# Import Android backup collector for enhanced APK-based collection
try:
    from ..Droid_backup.android_backup_collector import AndroidBackupCollector
except ImportError:
    try:
        from src.Droid_backup.android_backup_collector import AndroidBackupCollector
    except ImportError:
        AndroidBackupCollector = None

# Define constants for platform-specific settings
if platform.system() == "Windows":
    CREATE_NO_WINDOW = 0x08000000
else:
    CREATE_NO_WINDOW = 0  # Not used on non-Windows platforms

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.utils.pdf_report_gen import AndroidTriagePDFGenerator


class AndroidTriageHandler:
    def __init__(self):
        """Initialize the Android triage handler"""
        self.adb_path = self._get_adb_path()
        self.device_info = {}
        self.stamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        self.dev_Model = ""
        self.dev_Manufacturer = ""
        self.dev_Name = ""
        self.dev_Serial = ""
        self.verbose = False  # Add this flag to control output verbosity
        
        self.device_check_queue = queue.Queue()
        self.device_connected = False
        self.check_in_progress = False

    def _create_case_folder_structure(self, case_folder):
        """Create organized directory structure for the case"""
        # Main case folder
        os.makedirs(case_folder, exist_ok=True)
        
        # Organized subdirectories
        subdirs = [
            "Data",              # SMS, MMS, Contacts, Call Logs
            "Data/Messages",     # SMS and MMS data
            "Data/Contacts",     # Contact information
            "Data/CallLogs",     # Call history
            "Data/Location",     # GPS and location data
            "Apps",              # Application data and lists
            "Reports",           # Analysis reports and summaries
            "Media",             # Screenshots, images, videos
            "Logs",              # System logs and debug info
            "Artifacts",         # Raw extracted artifacts
            "Backup"             # Device backup files
        ]
        
        for subdir in subdirs:
            os.makedirs(os.path.join(case_folder, subdir), exist_ok=True)
    
    def _save_device_details(self, case_folder, device_details):
        """Save device details in both JSON and text formats"""
        # Save as JSON for programmatic access
        device_json_path = os.path.join(case_folder, "device_info.json")
        with open(device_json_path, "w") as f:
            json.dump(device_details, f, indent=2)
        
        # Save as text for human readability
        device_txt_path = os.path.join(case_folder, "device_details.txt")
        with open(device_txt_path, "w") as f:
            f.write("ANDROID DEVICE INFORMATION\n")
            f.write("=" * 50 + "\n\n")
            for key, value in device_details.items():
                f.write(f"{key}: {value}\n")

    def _run_subprocess(self, command, **kwargs):
        """Helper method to run subprocess with proper encoding handling"""
        # Set default encoding parameters for Windows compatibility
        default_kwargs = {
            'stdout': subprocess.PIPE,
            'stderr': subprocess.PIPE,
            'text': True,
            'encoding': 'utf-8',
            'errors': 'replace',
            'creationflags': SUBPROCESS_FLAGS
        }
        # Update with any provided kwargs
        default_kwargs.update(kwargs)
        
        return subprocess.run(command, **default_kwargs)

    def _run_subprocess_popen(self, command, **kwargs):
        """Helper method to run subprocess.Popen with proper encoding handling"""
        # Set default encoding parameters for Windows compatibility
        default_kwargs = {
            'stdout': subprocess.PIPE,
            'stderr': subprocess.PIPE,
            'text': True,
            'encoding': 'utf-8',
            'errors': 'replace',
            'creationflags': SUBPROCESS_FLAGS
        }
        # Update with any provided kwargs
        default_kwargs.update(kwargs)
        
        return subprocess.Popen(command, **default_kwargs)

    def _schedule_queue_check(self):
        """Schedule regular queue checking - simplified version"""
        if not getattr(self, '_monitoring_active', False):
            return
            
        try:
            self._check_device_queue()
        except Exception as e:
            print(f"Error in queue check: {e}")
        
        # Schedule next check in 2 seconds using a simple timer
        if getattr(self, '_monitoring_active', False):
            # Use a more robust timer approach
            def delayed_check():
                if getattr(self, '_monitoring_active', False):
                    self._schedule_queue_check()
            
            timer = threading.Timer(2.0, delayed_check)
            timer.daemon = True
            timer.start()

    def start_device_monitoring(self, status_callback=None):
        """Start monitoring for device connections in a thread-safe way"""
        self.status_callback = status_callback
        
        # Don't start multiple monitoring threads
        if hasattr(self, '_monitoring_active') and self._monitoring_active:
            return
            
        self._monitoring_active = True
        self.device_connected = False  # Initialize connection state
        
        # Start the monitoring thread
        monitor_thread = threading.Thread(target=self._device_monitor_worker, daemon=True)
        monitor_thread.start()
        
        print("Device monitoring started")
    
    def _device_monitor_worker(self):
        """Worker thread that checks for device connections - simplified"""
        while getattr(self, '_monitoring_active', False):
            try:
                if not self.check_in_progress:
                    self.check_in_progress = True
                    
                    # Check for device
                    is_connected = self.is_device_connected()
                    
                    # Get device info if connected
                    device_info = None
                    if is_connected:
                        try:
                            device_info = self.get_device_basic_info()
                        except Exception as e:
                            print(f"Error getting device info: {e}")
                            device_info = None
                    
                    # Put result in queue for main thread to process
                    self.device_check_queue.put({
                        'connected': is_connected,
                        'device_info': device_info,
                        'timestamp': datetime.datetime.now()
                    })
                    
                    self.check_in_progress = False
                    
                # Wait before next check
                time.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                print(f"Error in device monitor: {e}")
                self.check_in_progress = False
                time.sleep(10)
                
    def check_device_queue(self):
        """Check the device queue and update status - called from GUI thread"""
        try:
            # Non-blocking check
            while not self.device_check_queue.empty():
                result = self.device_check_queue.get_nowait()
                
                if result['connected'] and not self.device_connected:
                    # Device just connected
                    self.device_connected = True
                    if self.status_callback:
                        if result['device_info']:
                            info = result['device_info']
                            status_msg = f"{info.get('model', 'Unknown')} (Android {info.get('android_version', 'Unknown')})"
                        else:
                            status_msg = "Android device connected"
                        self.status_callback(status_msg)
                        
                elif not result['connected'] and self.device_connected:
                    # Device disconnected
                    self.device_connected = False
                    if self.status_callback:
                        self.status_callback("No device connected")
                        
        except queue.Empty:
            pass
        except Exception as e:
            print(f"Error checking device queue: {e}")
            
        return self.device_connected

    def stop_device_monitoring(self):
        """Stop device monitoring"""
        self._monitoring_active = False
        self.device_connected = False

    def _get_adb_path(self):
        """Get the path to the ADB executable"""
        
        # Build the path to the utils directory - CORRECTED PATH
        project_root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.."))
        
        # Use src/utils instead of just utils
        utils_dir = os.path.join(project_root, "src", "utils")
        
        # Determine ADB filename based on platform
        adb_filename = "adb.exe" if platform.system() == "Windows" else "adb"
        adb_path = os.path.join(utils_dir, adb_filename)
        
        # Debug info
        print(f"Project root: {project_root}")
        print(f"Utils directory: {utils_dir}")
        print(f"Looking for ADB at: {adb_path}")
        
        # Check if the file exists
        if os.path.exists(adb_path):
            print(f"ADB file found at: {adb_path}")
            
            # Check permissions
            try:
                # On Unix systems, make sure it's executable
                if platform.system() != "Windows":
                    file_stats = os.stat(adb_path)
                    is_executable = bool(file_stats.st_mode & stat.S_IXUSR)
                    print(f"Is ADB executable? {is_executable}")
                    
                    if not is_executable:
                        print(f"Setting executable permission on {adb_path}")
                        os.chmod(adb_path, file_stats.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                
                return adb_path
            except Exception as e:
                print(f"Error checking/setting permissions: {e}")
        else:
            print(f"ERROR: ADB not found at: {adb_path}")
        
        # Return the expected path anyway
        return adb_path
    
    def is_device_connected(self):
        """Check if an Android device is connected"""
        try:
            # Run the ADB devices command
            result = self._run_subprocess(
                [self.adb_path, "devices"], 
                check=False
            )
            
            # Only print debug info if verbose mode is enabled
            if self.verbose:
                print(f"ADB devices stderr: {result.stderr}")
                print(f"ADB devices stdout: {result.stdout}")
            
            # Check if any device is connected (device ID followed by "device")
            lines = result.stdout.strip().split('\n')
            if len(lines) <= 1:  # Only header line present
                return False
                
            devices = []
            for line in lines[1:]:  # Skip the header line
                if line.strip() and "\tdevice" in line:
                    devices.append(line.split('\t')[0])
            
            if self.verbose:
                print(f"Connected devices: {devices}")
                
            return len(devices) > 0
            
        except Exception as e:
            if self.verbose:
                print(f"Error checking for devices: {e}")
            return False
    #################################################
    def get_device_basic_info(self):
        """Get basic device information for GUI display"""
        try:
            if not self.is_device_connected():
                return None
                
            device_info = {}
            
            # Get model
            model_cmd = self.run_adb_command("shell getprop ro.product.model")
            if model_cmd:
                device_info["model"] = model_cmd.strip()
                
            # Get Android version
            version_cmd = self.run_adb_command("shell getprop ro.build.version.release")
            if version_cmd:
                device_info["android_version"] = version_cmd.strip()
                
            # Get manufacturer
            mfg_cmd = self.run_adb_command("shell getprop ro.product.manufacturer")
            if mfg_cmd:
                device_info["manufacturer"] = mfg_cmd.strip()
                
            return device_info
        except Exception as e:
            print(f"Error getting basic device info: {e}")
            return None
    ####################################################
    def get_device_info(self):
        """Get detailed information about the connected device"""
        if not self.is_device_connected():
            return "No device connected. Please connect a device with USB debugging enabled."
        
        device_info = []
        try:
            # Get device model
            model_cmd = run(
                [self.adb_path, "shell", "getprop", "ro.product.model"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            self.dev_Model = model_cmd.stdout.strip()
            device_info.append(f"Model: {self.dev_Model}")
            
            # Get manufacturer
            mfg_cmd = run(
                [self.adb_path, "shell", "getprop", "ro.product.manufacturer"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            self.dev_Manufacturer = mfg_cmd.stdout.strip()
            device_info.append(f"Manufacturer: {self.dev_Manufacturer}")
            
            # Get device name
            name_cmd = run(
                [self.adb_path, "shell", "getprop", "ro.product.name"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            self.dev_Name = name_cmd.stdout.strip()
            device_info.append(f"Device Name: {self.dev_Name}")
            
            # Get serial number
            serial_cmd = run(
                [self.adb_path, "shell", "getprop", "ro.serialno"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            self.dev_Serial = serial_cmd.stdout.strip()
            device_info.append(f"Serial: {self.dev_Serial}")
            
            # Get Android version
            version_cmd = run(
                [self.adb_path, "shell", "getprop", "ro.build.version.release"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            self.build_version = version_cmd.stdout.strip()
            device_info.append(f"Android Version: {self.build_version}")
            
            # Get build date
            build_date_cmd = run(
                [self.adb_path, "shell", "getprop", "ro.build.date"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            self.Build_date = build_date_cmd.stdout.strip()
            device_info.append(f"Build Date: {self.Build_date}")
            
            # Get encryption status
            encrypt_cmd = run(
                [self.adb_path, "shell", "getprop", "ro.crypto.state"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            self.encrypt_status = encrypt_cmd.stdout.strip()
            device_info.append(f"Encryption: {self.encrypt_status}")
            
            return "\n".join(device_info)
        except Exception as e:
            print(f"Error getting device info: {e}")
            return f"Error retrieving device information: {str(e)}"
    
    def run_triage(self, case_number, output_dir, 
           get_hashes=False, get_thumbnails=True, 
           make_backup=True, pull_storage=True,
           use_forensic_apk=True,
           status_callback=None, progress_callback=None):
        """Run the Android triage process"""
        # Helper function for status updates
        def update_status(message):
            print(message)
            if status_callback:
                status_callback(message)
                
        # Helper function for progress updates
        def update_progress(value):
            if progress_callback:
                progress_callback(value)
    
        # Check if device is connected
        if not self.is_device_connected():
            update_status("No device connected. Please connect a device and try again.")
            return None
        
        # Execute forensic APK first if requested (enhanced data collection)
        if use_forensic_apk and AndroidBackupCollector:
            update_status("🔬 Forensic APK mode enabled - starting enhanced data collection...")
            update_progress(0.02)
            
            try:
                backup_collector = AndroidBackupCollector()
                update_status("📲 Installing forensic APK on device...")
                
                if backup_collector.install_forensic_app():
                    update_status("✅ Forensic APK installed successfully")
                    update_progress(0.05)
                    
                    update_status("🚀 Launching forensic data collection app...")
                    if backup_collector.launch_forensic_app():
                        update_status("✅ Forensic app launched - collecting data...")
                        update_progress(0.08)
                        
                        # Wait for app-based collection to complete
                        update_status("⏳ Waiting for forensic app to complete data collection...")
                        if backup_collector.wait_for_app_completion(timeout_minutes=15):
                            update_status("✅ Forensic app data collection completed")
                            update_progress(0.12)
                            
                            # Pull collected data from device
                            update_status("📥 Pulling forensic data from device...")
                            # The forensic app data will be pulled as part of regular triage
                        else:
                            update_status("⚠️ Forensic app collection timed out, continuing with standard triage")
                    else:
                        update_status("⚠️ Failed to launch forensic app, continuing with standard triage")
                else:
                    update_status("⚠️ Failed to install forensic APK, continuing with standard triage")
                    
            except Exception as e:
                update_status(f"⚠️ Forensic APK error: {str(e)}, continuing with standard triage")
        
        elif use_forensic_apk:
            update_status("⚠️ Forensic APK requested but AndroidBackupCollector not available")
            update_progress(0.02)
        
        try:
            # Create a single case folder with organized structure
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            case_folder = os.path.join(output_dir, f"Android_Triage_{case_number}_{timestamp}")
            
            # Create organized directory structure
            self._create_case_folder_structure(case_folder)
            update_status(f"Created organized case folder: {case_folder}")
            update_progress(0.15)
            
            # Create results dictionary
            results = {
                "case_number": case_number,
                "case_folder": case_folder,
                "timestamp": datetime.datetime.now().isoformat(),
            }
            
            # Get comprehensive device details
            update_status("Getting device information...")
            device_details = self.get_all_device_details()
            results["device_details"] = device_details
            
            # Save device details to structured location
            self._save_device_details(case_folder, device_details)
            update_progress(0.20)
            
            # Run package dumpsys analysis to find third-party apps by user
            update_status("Analyzing installed applications...")
            dumpsys_results = self.analyze_package_dumpsys(case_folder, case_number)
            
            # Add apps to results
            if dumpsys_results and "apps_by_user" in dumpsys_results:
                # Flatten the apps by user into a single list for the results
                all_apps = []
                for user_id, apps in dumpsys_results["apps_by_user"].items():
                    all_apps.extend(apps)
                    
                results["apps"] = all_apps
                results["dumpsys_file"] = dumpsys_results.get("dumpsys_file")
                results["app_summary_file"] = dumpsys_results.get("summary_file")
                
                update_status(f"Found {len(all_apps)} third-party apps across all users")
        
            update_progress(0.25)
            
            # Take screenshot if available
            try:
                update_status("Taking device screenshot...")
                screenshot_path = os.path.join(case_folder, "device_screenshot.png")
                self.run_adb_command("shell screencap -p /sdcard/screenshot.png")
                self.run_adb_command(f"pull /sdcard/screenshot.png {screenshot_path}")
                self.run_adb_command("shell rm /sdcard/screenshot.png")
                
                if os.path.exists(screenshot_path):
                    results["screenshot"] = screenshot_path
                    update_status(f"Screenshot saved to: {screenshot_path}")
            except Exception as e:
                update_status(f"Error taking screenshot: {e}")
        
            update_progress(0.20)
            
            # Get file listing
            update_status("Collecting file names...")
            try:
                # Get file listing using a more targeted approach
                files_cmd = self.run_adb_command("shell find /sdcard -type f | grep -v '.thumbnail'")
                
                file_list = []
                for line in files_cmd.splitlines():
                    file_path = line.strip()
                    if file_path:
                        # Determine file type
                        file_type = "unknown"
                        if file_path.lower().endswith((".jpg", ".jpeg", ".png", ".gif")):
                            file_type = "image"
                        elif file_path.lower().endswith((".mp4", ".3gp", ".mov", ".avi")):
                            file_type = "video"
                        elif file_path.lower().endswith((".mp3", ".aac", ".m4a", ".wav")):
                            file_type = "audio"
                        elif file_path.lower().endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt")):
                            file_type = "document"
                        
                        file_list.append({"path": file_path, "type": file_type})
                
                results["files"] = file_list
                
                # Save file list
                with open(os.path.join(case_folder, "file_listing.txt"), "w") as f:
                    for file_info in file_list:
                        f.write(f"{file_info['path']} ({file_info['type']})\n")
                
                update_status(f"Found {len(file_list)} files")
            except Exception as e:
                update_status(f"Error collecting file names: {e}")
            
            update_progress(0.35)
            
            # Extract content artifacts (SMS, MMS, Contacts)
            update_status("Extracting content artifacts (SMS, MMS, Contacts)...")
            try:
                artifacts_results = self.extract_content_artifacts(case_folder, update_status)
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
                    update_status(f"Content artifacts extracted: {', '.join(artifact_summary)}")
                else:
                    update_status("No content artifacts found or accessible")
                    
            except Exception as e:
                update_status(f"Error extracting content artifacts: {str(e)}")
                results["artifacts"] = {"error": str(e)}
            
            update_progress(0.50)
            
            # Extract notification data
            update_status("Extracting notification data...")
            try:
                notifications_results = self.collect_notifications(case_folder, update_status)
                results["notifications"] = notifications_results
                
                if notifications_results.get("notifications_data"):
                    update_status(f"Notifications extracted: {notifications_results['notifications_data']['record_count']} records")
                else:
                    update_status("No notification data found or accessible")
                    
            except Exception as e:
                update_status(f"Error extracting notifications: {str(e)}")
                results["notifications"] = {"error": str(e)}
            
            update_progress(0.60)
            
            # Extract external files data
            update_status("Extracting external files (Videos, Images, Downloads)...")
            try:
                external_files_results = self.extract_external_files(case_folder, update_status)
                results["external_files"] = external_files_results
                
                # Log external files extraction results
                external_summary = []
                if external_files_results.get("videos_data"):
                    external_summary.append(f"Videos: {external_files_results['videos_data']['record_count']} records")
                if external_files_results.get("images_data"):
                    external_summary.append(f"Images: {external_files_results['images_data']['record_count']} records")
                if external_files_results.get("downloads_data"):
                    external_summary.append(f"Downloads: {external_files_results['downloads_data']['record_count']} records")
                if external_files_results.get("my_downloads_data"):
                    external_summary.append(f"My Downloads: {external_files_results['my_downloads_data']['record_count']} records")
                
                if external_summary:
                    update_status(f"External files extracted: {', '.join(external_summary)}")
                else:
                    update_status("No external files found or accessible")
                    
            except Exception as e:
                update_status(f"Error extracting external files: {str(e)}")
                results["external_files"] = {"error": str(e)}
            
            update_progress(0.70)
            
            # Create backup if requested
            if make_backup:
                update_status("Creating device backup (this may take a while)...")
                backup_file = self.make_backup(case_folder, case_number, self.dev_Name, use_forensic_apk)
                
                if backup_file and os.path.exists(backup_file):
                    results["backup_path"] = backup_file
                    update_status(f"Backup saved to: {backup_file}")
                    
                    # Optionally unpack the backup
                    update_status("Unpacking backup file...")
                    unpack_dir = os.path.join(case_folder, "unpacked_backup")
                    os.makedirs(unpack_dir, exist_ok=True)
                    
                    if self.unpack_backup(backup_file, unpack_dir):
                        results["unpacked_backup"] = unpack_dir
                        update_status(f"Backup unpacked to: {unpack_dir}")
                    else:
                        update_status("Failed to unpack backup. It may be encrypted or corrupt.")
                else:
                    update_status("Backup failed or was cancelled.")
            
            update_progress(0.80)
            
           # Update the PDF generation section in run_triage method around line 434:

            # Generate PDF report only (no text report)
            update_status("Generating PDF report...")
            
            try:
                # Check if reportlab is available
                try:
                    from reportlab.lib.pagesizes import letter
                    update_status("Reportlab library found")
                except ImportError as e:
                    update_status(f"Error: reportlab library not found. Please install with: pip install reportlab")
                    update_status(f"Import error: {e}")
                    return None
                
                # Import the PDF generator
                try:
                    from src.utils.pdf_report_gen import AndroidTriagePDFGenerator
                    update_status("PDF generator imported successfully")
                except ImportError as e:
                    update_status(f"Error importing PDF generator: {e}")
                    return None
                
                # Create the PDF generator
                pdf_generator = AndroidTriagePDFGenerator()
                update_status("PDF generator created")
                
                # Debug: print what we're passing to the generator
                update_status(f"Generating PDF with case_number: {case_number}")
                update_status(f"Case folder: {case_folder}")
                update_status(f"Results keys: {list(results.keys())}")
                
                # Generate the PDF
                pdf_path = pdf_generator.generate_report(case_folder, results, case_number)
                
                if pdf_path and os.path.exists(pdf_path):
                    file_size = os.path.getsize(pdf_path)
                    update_status(f"PDF report generated successfully: {os.path.basename(pdf_path)} ({file_size:,} bytes)")
                    results["pdf_report_path"] = pdf_path
                    results["report_path"] = pdf_path  # Set this as the main report path
                    return results
                else:
                    update_status("Error: PDF report generation returned None or file doesn't exist")
                    if pdf_path:
                        update_status(f"Expected PDF path: {pdf_path}")
                        update_status(f"File exists: {os.path.exists(pdf_path) if pdf_path else 'No path returned'}")
                    return None
                
            except Exception as pdf_error:
                update_status(f"Error: PDF report generation failed: {pdf_error}")
                print(f"PDF generation error: {pdf_error}")
                import traceback
                error_details = traceback.format_exc()
                print(f"Full traceback: {error_details}")
                update_status(f"Error details: {str(pdf_error)}")
                return None
            


            update_status(f"Report generated: {pdf_path}")
            
            update_progress(1.0)
            update_status("Triage completed successfully!")
            
            return results
                
        except Exception as e:
            update_status(f"Error during triage: {str(e)}")
            import traceback
            traceback.print_exc()
            update_progress(0)
            return None
        
    def get_installed_apps(self):
        """Get list of installed applications by parsing dumpsys packages output"""
        if not self.is_device_connected():
            return []
        
        try:
            print("Fetching installed applications via dumpsys packages...")
            
            # Run dumpsys command to get package information
            dumpsys_cmd = self.run_adb_command("shell dumpsys package packages")
            
            if not dumpsys_cmd:
                print("Failed to get dumpsys package output")
                return []
            
            # Parse the dumpsys output to find third-party apps by user
            apps_by_user = self._parse_dumpsys_for_apps(dumpsys_cmd)
            
            # Flatten all apps from all users into a single list
            all_apps = []
            for user_id, apps in apps_by_user.items():
                all_apps.extend(apps)
            
            # Fill in missing names with common app names
            self.fill_common_app_names(all_apps)
            
            print(f"Found {len(all_apps)} installed applications across all users")
            return all_apps
            
        except Exception as e:
            print(f"Error getting installed apps: {e}")
            import traceback
            traceback.print_exc()
            return []
        
    def get_app_name_fallback(self, package_name):
        """Get app name using aapt if available"""
        try:
            # Get app name using a direct adb shell command to extract the label
            label_cmd = self._run_subprocess(
                [self.adb_path, "shell", "cmd", "package", "dump", package_name, "|", "grep", "primaryCpuAbi"],
                shell=True
            )
            return ""  # Return empty string if failed
        except:
            return ""  # Return empty string if failed

    def fill_common_app_names(self, apps):
        """Fill in friendly names for common apps"""
        common_names = {
            "com.skype.raider": "Skype",
            "com.united.mobile.android": "United Airlines",
            "com.shazam.android": "Shazam",
            "com.plexapp.android": "Plex",
            "fm.castbox.audiobook.radio.podcast": "Castbox",
            "com.whatsapp": "WhatsApp",
            "com.discord": "Discord",
            "com.sec.android.app.voicenote": "Samsung Voice Recorder",
            "com.samsung.android.email.provider": "Samsung Email",
            "com.singtel.hiaccount": "Singtel",
            "com.samsung.android.sidegesturepad": "Samsung Edge Panel",
            "com.stitcher.app": "Stitcher",
            "org.thoughtcrime.securesms": "Signal",
            "com.microsoft.office.outlook": "Outlook",
            "com.dropbox.android": "Dropbox",
            "com.samsung.app.slowmotion": "Samsung Slow Motion",
            "com.google.android.apps.docs": "Google Drive",
            "com.grabtaxi.passenger": "Grab",
            "com.pandora.android": "Pandora",
            "net.wigle.wigleandroid": "WiGLE WiFi",
            "com.hbo.hbonow": "HBO Max",
            "com.aimp.player": "AIMP",
            "com.nordvpn.android": "NordVPN",
            "com.google.android.videos": "Google Play Movies",
            "com.hushed.release": "Hushed",
            "flipboard.boxer.app": "Flipboard",
            "com.google.android.apps.photos": "Google Photos",
            "com.spotify.music": "Spotify",
            "com.ubercab": "Uber",
            "com.sec.android.app.sbrowser": "Samsung Internet",
            "com.microsoft.office.officehubrow": "Microsoft Office",
            "com.samsung.android.visionarapps": "AR Zone",
            "com.samsung.android.app.music": "Samsung Music",
            "com.musical.ly": "TikTok",
            "com.kakao.talk": "KakaoTalk",
            "com.facebook.orca": "Facebook Messenger",
            "com.instagram.android": "Instagram",
            "com.twitter.android": "Twitter",
            "com.snapchat.android": "Snapchat",
            "com.plentyoffish.android": "Plenty of Fish",
            "com.tinder": "Tinder",
            "com.linkedin.android": "LinkedIn",
            "com.skipthegames": "SkipTheGames",
            "com.okcupid.d": "OkCupid",
            "com.badoo.mobile": "Badoo",
            "com.tumblr": "Tumblr",
            "com.reddit.frontpage": "Reddit",
            "com.viber.voip": "Viber",
            "com.mega.privacy": "MEGA",
        }
        
        for app in apps:
            if not app["name"] and app["package"] in common_names:
                app["name"] = common_names[app["package"]]
                print(f"Using common name for {app['package']}: {app['name']}")

    def run_adb_command(self, command):
        """Run an ADB command and return the output"""
        try:
            # Ensure we have the ADB path
            if not self.adb_path:
                print("ERROR: ADB path not set")
                return ""
                
            # Build the full command
            full_cmd = [self.adb_path] + command.split()
            
            # Run the command
            process = self._run_subprocess(
                full_cmd,
                check=False
            )
            
            # Return the output, stripping whitespace
            return process.stdout.strip()
        except Exception as e:
            print(f"Error running ADB command: {e}")
            return ""

    def get_all_device_details(self):
        """Get all device details including users"""
        details = {}
        
        try:
            if not self.is_device_connected():
                print("No device connected")
                return details
                
            # Get basic device properties
            properties = [
                ("Device Name", "ro.product.device"),
                ("Model", "ro.product.model"),
                ("Manufacturer", "ro.product.manufacturer"),
                ("Brand", "ro.product.brand"),
                ("Android Version", "ro.build.version.release"),
                ("API Level", "ro.build.version.sdk"),
                ("Build ID", "ro.build.id"),
                ("Build Date", "ro.build.date"),
                ("Bootloader", "ro.bootloader"),
                ("Kernel Version", "ro.kernel.version"),
                ("Security Patch", "ro.build.version.security_patch"),
                ("Hardware", "ro.hardware"),
                ("Chipset", "ro.board.platform"),
                ("ABI", "ro.product.cpu.abi")
            ]
            
            for label, prop in properties:
                value = self.run_adb_command(f"shell getprop {prop}")
                if value and value.strip():
                    details[label] = value.strip()
        
            # Get device identifiers (IMEI, serial, etc.)
            try:
                device_ids = self.get_device_ids()
                details.update(device_ids)
            except Exception as e:
                print(f"Error getting device identifiers: {e}")
        
            # Get encryption status
            try:
                encryption_cmd = self.run_adb_command("shell getprop ro.crypto.state")
                if encryption_cmd and encryption_cmd.strip():
                    details["Encryption Status"] = encryption_cmd.strip()
            except Exception:
                pass
            
            # Add users to device details
            try:
                users = self.get_users()
                if users:
                    details["Users"] = users  # Store the full user objects for formatting later
            except Exception as e:
                print(f"Error getting users: {e}")
                
            return details
            
        except Exception as e:
            print(f"Error collecting comprehensive device details: {e}")
            import traceback
            traceback.print_exc()
            return details
    
    def get_storage_info(self):
        """Get storage information from the device"""
        try:
            if not self.is_device_connected():
                return {}
                
            storage_info = {}
            
            # Run df command to get filesystem info
            filesysteminfo = self.run_adb_command("shell df")
            if not filesysteminfo:
                return storage_info
                
            # Parse the output
            internal_store = None
            external_store = None
            
            for line in filesysteminfo.split('\n'):
                if "storage" in line:
                    if "emulated" in line:
                        internal_store = line.split()
                    else:
                        external_store = line.split()
            
            # Calculate storage sizes
            if internal_store:
                storage_info["internal_used"] = f"{round(int(internal_store[2])/1024/1024, 2)} GB"
                storage_info["internal_total"] = f"{round(int(internal_store[1])/1024/1024, 2)} GB"
                
            if external_store:
                storage_info["external_used"] = f"{round(int(external_store[2])/1024/1024, 2)} GB"
                storage_info["external_total"] = f"{round(int(external_store[1])/1024/1024, 2)} GB"
            else:
                storage_info["external_used"] = "0 GB"
                storage_info["external_total"] = "0 GB"
                
            return storage_info
            
        except Exception as e:
            print(f"Error getting storage info: {e}")
            return {}

    def get_users(self):
        """Get list of users on the device with improved detection"""
        try:
            if not self.is_device_connected():
                return []
                
            users = []
            users_output = self.run_adb_command("shell pm list users")
            
            # Log the output for debugging
            print(f"User listing output: {users_output}")
            
            # Always add user 0 (primary user) if not detected
            primary_user_found = False
            
            for line in users_output.split('\n'):
                if 'UserInfo' in line:
                    # Extract user ID, name and state
                    # Try different regex patterns to handle various output formats
                    match = re.search(r'UserInfo{(\d+):([^:}]+)', line)
                    if not match:
                        # Try alternative pattern
                        match = re.search(r'UserInfo{(\d+):', line)
                        user_id = match.group(1) if match else "Unknown"
                        user_name = "Unknown"
                    else:
                        user_id = match.group(1)
                        user_name = match.group(2)
                    
                    # Check if this is the primary user
                    if user_id == "0":
                        primary_user_found = True
                    
                    state = "Running" if "running" in line.lower() else "Not Running"
                    
                    user_type = "Unknown"
                    if user_id == "0":
                        user_type = "Primary User"
                    elif user_id == "10":
                        user_type = "Work Profile"
                    elif user_id == "150":
                        user_type = "Secure Folder"
                    elif int(user_id) > 0:
                        user_type = "Secondary User"
                    
                    users.append({
                        "id": user_id,
                        "name": user_name,
                        "type": user_type,
                        "state": state
                    })
            
            # If no primary user was found in the output, add it manually
            if not primary_user_found:
                print("Primary user (0) not found in output, adding manually")
                users.insert(0, {
                    "id": "0",
                    "name": "Owner",
                    "type": "Primary User",
                    "state": "Running"
                })
            
            # Sort users by ID
            users.sort(key=lambda x: int(x.get("id", "0")))
            
            print(f"Detected users: {[u.get('id') for u in users]}")
            return users
            
        except Exception as e:
            print(f"Error getting users: {e}")
            import traceback
            traceback.print_exc()
            
            # Return at least the primary user if there was an error
            return [{
                "id": "0",
                "name": "Owner",
                "type": "Primary User",
                "state": "Running"
            }]

    # def secure_folder_apps_fix(self):
    #     """Get apps installed in secure folder by analyzing dumpsys output"""
    #     try:
    #         print("Starting comprehensive Secure Folder app detection...")
            
    #         # Get all third-party packages first
    #         all_apps_cmd = self.run_adb_command("shell pm list packages -3")
    #         if not all_apps_cmd:
    #             print("Failed to get app list")
    #             return []
                
    #         all_packages = []
    #         for line in all_apps_cmd.split('\n'):
    #             if line.startswith("package:"):
    #                 package = line.replace("package:", "").strip()
    #                 if package:
    #                     all_packages.append(package)
        
    #         print(f"Checking {len(all_packages)} packages for Secure Folder presence...")
        
    #         # For debugging - dump all packages info
    #         dump_all_cmd = self.run_adb_command("shell dumpsys package packages | grep -A 2 'User 150:'")
    #         print(f"User 150 packages found in dump: {dump_all_cmd.count('User 150:')}")
        
    #         # Check each package for User 150 installation
    #         secure_folder_apps = []
    #         for i, package in enumerate(all_packages):
    #             # Show progress periodically
    #             if i % 10 == 0:
    #                 print(f"Checking package {i+1}/{len(all_packages)}: {package}")
                
    #             dumpsys_cmd = self.run_adb_command(f"shell dumpsys package {package}")
                
    #             # Find all User sections
    #             user_sections = re.findall(r'User (\d+):[^\n]+installed=(\w+)', dumpsys_cmd)
            
    #             # Check if User 150 exists with installed=true
    #             for user_id, installed in user_sections:
    #                 if user_id == "150" and installed == "true":
    #                     print(f"Found Secure Folder app: {package}")
                    
    #                     # This app is installed for user 150
    #                     app_info = {
    #                         "package": package,
    #                         "name": "",
    #                         "version": "",
    #                         "path": "",
    #                         "user_id": "150"
    #                     }
                    
    #                     # Get app name and version
    #                     name_match = re.search(r'labelRes=\d+ label=([^ ]+)', dumpsys_cmd)
    #                     if name_match:
    #                         app_info["name"] = name_match.group(1)
                        
    #                     version_match = re.search(r'versionName=([^\s]+)', dumpsys_cmd)
    #                     if version_match:
    #                         app_info["version"] = version_match.group(1)
                            
    #                     secure_folder_apps.append(app_info)
    #                     break
        
    #         print(f"Found {len(secure_folder_apps)} apps in Secure Folder")
    #         return secure_folder_apps
            
    #     except Exception as e:
    #         print(f"Error finding secure folder apps: {e}")
    #         import traceback
    #         traceback.print_exc()
    #         return []
    
    def analyze_package_dumpsys(self, case_folder, case_number):
        """
        Analyze package dumpsys to find third-party apps for each user
        
        Args:
            case_folder: Existing case folder path to save output
            case_number: Case identifier
        
        Returns:
            Dictionary of apps by user ID
        """
        try:
            # Define output file path in Apps subdirectory
            dumpsys_file = os.path.join(case_folder, "Apps", "package_dumpsys.txt")
            
            print(f"Running dumpsys package packages and saving to {dumpsys_file}")
            
            # Run the dumpsys command and save output directly
            dumpsys_cmd = self.run_adb_command("shell dumpsys package packages")
            
            # Save to file
            with open(dumpsys_file, "w", encoding="utf-8", errors="ignore") as f:
                f.write(dumpsys_cmd)
                
            print(f"Saved dumpsys output ({len(dumpsys_cmd)} bytes)")
            
            # Parse the file to find third-party apps by user using shared method
            apps_by_user = self._parse_dumpsys_for_apps(dumpsys_cmd)
            
            # Create a summary file in Apps directory
            summary_file = os.path.join(case_folder, "Apps", "app_summary.txt")
            with open(summary_file, "w", encoding="utf-8") as f:
                f.write("THIRD-PARTY APPLICATIONS BY USER\n")
                f.write("================================\n\n")
                
                for user_id in sorted(apps_by_user.keys()):
                    user_type = "Primary User"
                    if user_id == "10":
                        user_type = "Work Profile"
                    elif user_id == "150":
                        user_type = "Secure Folder"
                        
                    f.write(f"USER {user_id} ({user_type}) - {len(apps_by_user[user_id])} apps\n")
                    f.write("-" * 40 + "\n")
                    
                    for app in sorted(apps_by_user[user_id], key=lambda x: x["name"].lower()):
                        f.write(f"App: {app['name']}\n")
                        f.write(f"Package: {app['package']}\n")
                        if app['version']:
                            f.write(f"Version: {app['version']}\n")
                        if app['path']:
                            f.write(f"Path: {app['path']}\n")
                        f.write("\n")
                    
                    f.write("\n")
                    
            print(f"Saved app summary to {summary_file}")
            
            # Return the apps by user
            return {
                "apps_by_user": apps_by_user,
                "dumpsys_file": dumpsys_file,
                "summary_file": summary_file
            }
            
        except Exception as e:
            print(f"Error analyzing package dumpsys: {e}")
            import traceback
            traceback.print_exc()
            return {"apps_by_user": {}}
    
    def get_device_ids(self):
        """
        Get device identifiers (IMEI, MEID, serial numbers, etc.)
        
        Returns:
            Dictionary of device identifiers
        """
        device_ids = {}
        
        try:
            if not self.is_device_connected():
                print("No device connected")
                return device_ids
                
            # Get IMEI using telephony service
            try:
                imei_cmd = self.run_adb_command("shell service call iphonesubinfo 1 | grep -o '[0-9a-f]\\{8\\} ' | tail -n+3 | while read a; do echo -n \\\\u${a:4:4}\\\\u${a:0:4}; done")
                if imei_cmd and len(imei_cmd.strip()) > 5:
                    device_ids["IMEI"] = imei_cmd.strip()
            except Exception as e:
                print(f"Error getting IMEI: {e}")
            
            # Try alternative IMEI command
            if "IMEI" not in device_ids:
                try:
                    alt_imei = self.run_adb_command("shell dumpsys iphonesubinfo | grep -E 'Device ID|IMEI' | head -n 1")
                    if "=" in alt_imei:
                        device_ids["IMEI"] = alt_imei.split("=")[1].strip()
                except Exception as e:
                    print(f"Error getting IMEI via alternative method: {e}")
            
            # Get MEID
            try:
                meid_cmd = self.run_adb_command("shell dumpsys iphonesubinfo | grep -i meid")
                if "=" in meid_cmd:
                    device_ids["MEID"] = meid_cmd.split("=")[1].strip()
            except Exception:
                pass
            
            # Get serial number
            try:
                serial_cmd = self.run_adb_command("shell getprop ro.serialno")
                if serial_cmd and serial_cmd.strip():
                    device_ids["Serial"] = serial_cmd.strip()
            except Exception:
                pass
                
            # Get phone numbers
            try:
                phone_cmd = self.run_adb_command("shell dumpsys telephony.registry | grep -E 'mPhoneId|mPhoneNumber'")
                numbers = re.findall(r'mPhoneNumber=([\d+]+)', phone_cmd)
                if numbers:
                    device_ids["Phone Numbers"] = ", ".join(numbers)
            except Exception:
                pass
                
            # Get ICCID (SIM card ID)
            try:
                iccid_cmd = self.run_adb_command("shell dumpsys telephony.registry | grep -i iccid")
                iccids = re.findall(r'ICCID=(\d+)', iccid_cmd)
                if iccids:
                    device_ids["ICCID"] = ", ".join(iccids)
            except Exception:
                pass
                
            # Get IMSI (International Mobile Subscriber Identity)
            try:
                imsi_cmd = self.run_adb_command("shell dumpsys telephony.registry | grep -i imsi")
                imsis = re.findall(r'IMSI=(\d+)', imsi_cmd)
                if imsis:
                    device_ids["IMSI"] = ", ".join(imsis)
            except Exception:
                pass
                
            return device_ids
            
        except Exception as e:
            print(f"Error collecting device IDs: {e}")
            return device_ids

    def collect_file_names(self, case_folder, case_number, extensions=None, paths=None, max_depth=None, status_callback=None):
        """
        Collect file names from the Android device
    
        Args:
            case_folder: Existing case folder path to save output
            case_number: Case identifier
            extensions: List of file extensions to collect (e.g., ['.jpg', '.png'])
            paths: List of paths to search (default: ['/sdcard'])
            max_depth: Maximum directory depth to search (None for unlimited)
            status_callback: Function to call with status updates
        
        Returns:
            Dictionary with results info including paths to output files
        """
        try:
            # Helper function for status updates
            def update_status(message):
                print(message)
                if status_callback:
                    status_callback(message)
        
            # Use existing case folder and save to Media subdirectory
            media_dir = os.path.join(case_folder, "Media")
            os.makedirs(media_dir, exist_ok=True)
        
            # Default parameters
            if paths is None:
                paths = ["/sdcard"]
            
            if extensions is None:
                extensions = []  # Empty list means collect all files
            
            # Prepare results
            results = {
                "total_files": 0,
                "matching_files": 0,
                "output_files": [],
                "errors": []
            }
        
            # Create output file for all collected filenames in Media directory
            all_files_path = os.path.join(media_dir, "collected_filenames.txt")
            results["output_files"].append(all_files_path)
        
            # If extensions are provided, create separate files for each extension
            extension_files = {}
            if extensions:
                for ext in extensions:
                    ext_clean = ext.replace(".", "").lower()
                    ext_file_path = os.path.join(media_dir, f"files_{ext_clean}.txt")
                    extension_files[ext.lower()] = {
                        "path": ext_file_path,
                        "count": 0,
                        "file": None  # Will open file handlers later
                    }
                    results["output_files"].append(ext_file_path)
        
            # Open all output files
            with open(all_files_path, "w", encoding="utf-8") as all_files_output:
                # Open extension-specific files if needed
                for ext_info in extension_files.values():
                    ext_info["file"] = open(ext_info["path"], "w", encoding="utf-8")
                
                # Process each search path
                for path in paths:
                    update_status(f"Collecting filenames from {path}...")
                    
                    # Build the find command with appropriate options
                    find_cmd = f"shell find {path}"
                    
                    # Add depth constraint if specified
                    if max_depth is not None:
                        find_cmd += f" -maxdepth {max_depth}"
                    
                    # Add type filter for files only
                    find_cmd += " -type f"
                    
                    # Execute the command
                    find_output = self.run_adb_command(find_cmd)
                    
                    if not find_output:
                        update_status(f"No files found in {path} or error executing command")
                        results["errors"].append(f"No files found in {path}")
                        continue
                    
                    # Process the output
                    file_count = 0
                    matching_count = 0
                    
                    for line in find_output.splitlines():
                        file_path = line.strip()
                        if not file_path:
                            continue
                            
                        file_count += 1
                        
                        # Write to the all files output
                        all_files_output.write(f"{file_path}\n")
                        
                        # Check if this file matches any of our extensions
                        if extensions:
                            file_ext = os.path.splitext(file_path)[1].lower()
                            if file_ext in extension_files:
                                extension_files[file_ext]["count"] += 1
                                extension_files[file_ext]["file"].write(f"{file_path}\n")
                                matching_count += 1
                        else:
                            # If no extensions specified, all files match
                            matching_count += 1
                        
                        # Provide periodic updates for large collections
                        if file_count % 1000 == 0:
                            update_status(f"Processed {file_count} files so far...")
                    
                    update_status(f"Found {file_count} files in {path}, {matching_count} matching requested extensions")
                    results["total_files"] += file_count
                    results["matching_files"] += matching_count
                
                # Close extension-specific files
                for ext_info in extension_files.values():
                    if ext_info["file"]:
                        ext_info["file"].close()
        
            # Create a summary file
            summary_path = os.path.join(case_folder, "filenames_summary.txt")
            with open(summary_path, "w", encoding="utf-8") as summary_file:
                summary_file.write("FILE COLLECTION SUMMARY\n")
                summary_file.write("======================\n\n")
                summary_file.write(f"Case Number: {case_number}\n")
                summary_file.write(f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                summary_file.write(f"Total files collected: {results['total_files']}\n")
                summary_file.write(f"Files matching extensions: {results['matching_files']}\n\n")
                
                summary_file.write("Searched paths:\n")
                for path in paths:
                    summary_file.write(f"- {path}\n")
                summary_file.write("\n")
                
                if extensions:
                    summary_file.write("Files by extension:\n")
                    for ext, info in extension_files.items():
                        summary_file.write(f"- {ext}: {info['count']} files\n")
                    summary_file.write("\n")
                
                if results["errors"]:
                    summary_file.write("Errors encountered:\n")
                    for error in results["errors"]:
                        summary_file.write(f"- {error}\n")
        
            results["summary_file"] = summary_path
            update_status(f"File collection complete. Found {results['total_files']} total files.")
            return results
        
        except Exception as e:
            print(f"Error collecting filenames: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "total_files": 0, "matching_files": 0, "output_files": []}

    def log_message(self, message):
        """Log a message with timestamp"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")

    def get_device_basic_info(self):
        """Get basic device information for GUI display"""
        try:
            if not self.is_device_connected():
                return None
                
            device_info = {}
            
            # Get model
            model_cmd = self.run_adb_command("shell getprop ro.product.model")
            if model_cmd:
                device_info["model"] = model_cmd.strip()
                
            # Get Android version
            version_cmd = self.run_adb_command("shell getprop ro.build.version.release")
            if version_cmd:
                device_info["android_version"] = version_cmd.strip()
                
            # Get manufacturer
            mfg_cmd = self.run_adb_command("shell getprop ro.product.manufacturer")
            if mfg_cmd:
                device_info["manufacturer"] = mfg_cmd.strip()
                
            return device_info
        except Exception as e:
            print(f"Error getting basic device info: {e}")
            return None

    def make_backup(self, case_folder, case_number, device_name, use_forensic_apk=True):
        """Create an ADB backup of the device"""
        try:
            self.log_message("Starting device backup...")
            
            # If forensic APK was used, the data collection already happened at the start
            if use_forensic_apk and AndroidBackupCollector is not None:
                self.log_message("Finalizing forensic APK data collection...")
                
                try:
                    # Initialize backup collector to pull any remaining data
                    backup_collector = AndroidBackupCollector()
                    
                    # Pull any collected data that wasn't already retrieved
                    self.log_message("📥 Pulling final forensic data from device...")
                    if backup_collector.pull_collected_data(case_folder):
                        self.log_message("✅ Forensic APK data collection completed")
                        
                        # Create a summary backup file for compatibility
                        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                        backup_filename = f"forensic_backup_{case_number}_{device_name}_{timestamp}.tar"
                        backup_path = os.path.join(case_folder, backup_filename)
                        
                        # Create a compressed archive of the collected data
                        import tarfile
                        with tarfile.open(backup_path, 'w') as tar:
                            for root, dirs, files in os.walk(case_folder):
                                for file in files:
                                    if file != backup_filename:  # Don't include the backup file itself
                                        file_path = os.path.join(root, file)
                                        arcname = os.path.relpath(file_path, case_folder)
                                        tar.add(file_path, arcname=arcname)
                        
                        self.log_message(f"Forensic backup created: {backup_path}")
                        return backup_path
                    else:
                        self.log_message("⚠️ Failed to pull forensic data, falling back to standard ADB backup")
                        
                except Exception as e:
                    self.log_message(f"Forensic APK backup error: {str(e)}, falling back to standard ADB backup")
            
            # Standard ADB backup (fallback or when APK not used)
            self.log_message("Creating standard ADB backup...")
            
            # Create backup filename
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"backup_{case_number}_{device_name}_{timestamp}.ab"
            backup_path = os.path.join(case_folder, backup_filename)
            
            # Run ADB backup command
            backup_cmd = [
                self.adb_path, "backup", 
                "-apk", "-shared", "-nosystem", 
                "-f", backup_path
            ]
            
            self.log_message("Please confirm backup on device...")
            
            # Execute backup command
            process = self._run_subprocess(
                backup_cmd,
                timeout=1800  # 30 minute timeout
            )
            
            if process.returncode == 0 and os.path.exists(backup_path):
                self.log_message(f"Standard backup completed: {backup_path}")
                return backup_path
            else:
                self.log_message(f"Standard backup failed: {process.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            self.log_message("Backup timed out - may have been cancelled by user")
            return None
        except Exception as e:
            self.log_message(f"Error creating backup: {e}")
            return None

    def unpack_backup(self, backup_file, output_dir):
        """Attempt to unpack an ADB backup file"""
        try:
            self.log_message(f"Attempting to unpack backup: {backup_file}")
            
            # Check if backup file exists
            if not os.path.exists(backup_file):
                self.log_message("Backup file not found")
                return False
                
            # Try to extract using Android Backup Extractor or similar tool
            # For now, we'll just indicate that the file exists and is ready for manual extraction
            file_size = os.path.getsize(backup_file)
            self.log_message(f"Backup file size: {file_size:,} bytes")
            
            # Note: Actual unpacking would require additional tools like:
            # - Android Backup Extractor
            # - dd + zlib decompression
            # For now, we'll just report that the backup was created successfully
            
            self.log_message("Backup created successfully. Manual extraction may be required.")
            return True
            
        except Exception as e:
            self.log_message(f"Error unpacking backup: {e}")
            return False

    def collect_thumbnails(self, case_folder, case_number, status_callback=None):
        """Collect thumbnails from the device"""
        try:
            # Helper function for status updates
            def update_status(message):
                if status_callback:
                    status_callback(message)
                else:
                    self.log_message(message)
            
            update_status("Starting thumbnail collection...")
            
            # Use existing case folder and create thumbnails subdirectory in Media
            media_dir = os.path.join(case_folder, "Media")
            os.makedirs(media_dir, exist_ok=True)
            
            thumbnails_dir = os.path.join(media_dir, "thumbnails")
            os.makedirs(thumbnails_dir, exist_ok=True)
            
            # Find thumbnail directories on device
            thumbnail_paths = [
                "/sdcard/DCIM/.thumbnails",
                "/sdcard/.thumbnails", 
                "/storage/emulated/0/DCIM/.thumbnails",
                "/storage/emulated/0/.thumbnails"
            ]
            
            collected_count = 0
            
            for thumb_path in thumbnail_paths:
                update_status(f"Checking {thumb_path}...")
                
                # Check if directory exists
                check_cmd = f"shell ls {thumb_path} 2>/dev/null"
                result = self.run_adb_command(check_cmd)
                
                if result and "No such file" not in result:
                    # Pull thumbnails from this directory
                    pull_cmd = f"pull {thumb_path} {thumbnails_dir}/"
                    pull_result = self.run_adb_command(pull_cmd)
                    
                    if "file pulled" in pull_result.lower():
                        # Count files
                        try:
                            for root, dirs, files in os.walk(thumbnails_dir):
                                collected_count += len([f for f in files if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
                        except:
                            pass
            
            update_status(f"Thumbnail collection complete. Found {collected_count} thumbnails.")
            
            return {
                "thumbnails_dir": thumbnails_dir,
                "count": collected_count,
                "status": "completed"
            }
            
        except Exception as e:
            if status_callback:
                status_callback(f"Error collecting thumbnails: {e}")
            else:
                self.log_message(f"Error collecting thumbnails: {e}")
            return {"error": str(e), "count": 0}

    def calculate_hashes(self, case_folder, case_number, status_callback=None):
        """Calculate hashes for files on the device"""
        try:
            # Helper function for status updates
            def update_status(message):
                if status_callback:
                    status_callback(message)
                else:
                    self.log_message(message)
            
            update_status("Starting hash calculation...")
            
            # Use existing case folder and create artifacts subdirectory
            artifacts_dir = os.path.join(case_folder, "Artifacts")
            os.makedirs(artifacts_dir, exist_ok=True)
            
            # Hash calculation is very resource intensive on mobile devices
            # We'll limit this to important file types and directories
            target_dirs = ["/sdcard/DCIM", "/sdcard/Download", "/sdcard/Documents"]
            target_extensions = [".jpg", ".jpeg", ".png", ".mp4", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"]
            
            hash_results = []
            
            for target_dir in target_dirs:
                update_status(f"Calculating hashes for files in {target_dir}...")
                
                # Get file list
                find_cmd = f"shell find {target_dir} -type f 2>/dev/null"
                files_output = self.run_adb_command(find_cmd)
                
                if not files_output:
                    continue
                    
                files = [f.strip() for f in files_output.split('\n') if f.strip()]
                
                # Filter by extensions
                filtered_files = []
                for file_path in files:
                    if any(file_path.lower().endswith(ext) for ext in target_extensions):
                        filtered_files.append(file_path)
                
                # Calculate hashes (limit to first 50 files to avoid excessive processing)
                for i, file_path in enumerate(filtered_files[:50]):
                    update_status(f"Hashing {os.path.basename(file_path)} ({i+1}/{min(len(filtered_files), 50)})")
                    
                    # Use Android's md5sum if available
                    hash_cmd = f"shell md5sum '{file_path}' 2>/dev/null"
                    hash_result = self.run_adb_command(hash_cmd)
                    
                    if hash_result and len(hash_result.split()) >= 2:
                        hash_value = hash_result.split()[0]
                        hash_results.append({
                            "file_path": file_path,
                            "md5": hash_value,
                            "algorithm": "MD5"
                        })
            
            # Save hash results
            hash_file = os.path.join(case_folder, "file_hashes.txt")
            with open(hash_file, "w") as f:
                f.write("FILE HASH RESULTS\n")
                f.write("=================\n\n")
                f.write(f"Case Number: {case_number}\n")
                f.write(f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                for result in hash_results:
                    f.write(f"File: {result['file_path']}\n")
                    f.write(f"MD5:  {result['md5']}\n\n")
            
            update_status(f"Hash calculation complete. Processed {len(hash_results)} files.")
            
            return {
                "hash_file": hash_file,
                "count": len(hash_results),
                "results": hash_results,
                "status": "completed"
            }
            
        except Exception as e:
            if status_callback:
                status_callback(f"Error calculating hashes: {e}")
            else:
                self.log_message(f"Error calculating hashes: {e}")
            return {"error": str(e), "count": 0}

    def _parse_dumpsys_for_apps(self, dumpsys_output):
        """
        Parse dumpsys package output to extract third-party apps by user
        
        Args:
            dumpsys_output: Raw dumpsys package packages output
            
        Returns:
            Dictionary of apps by user ID
        """
        try:
            apps_by_user = {}
            
            # Parse the dumpsys output
            package_blocks = re.findall(r'Package \[([^\]]+)\](.*?)(?=Package \[|$)', dumpsys_output, re.DOTALL)
            
            for package, block in package_blocks:
                # Skip system packages (be less restrictive to catch more apps)
                if (package.startswith("android") or 
                    (package.startswith("com.android") and not package.startswith("com.android.vending")) or 
                    package.startswith("com.sec.android") or 
                    package.startswith("com.samsung.android") or
                    package.startswith("com.google.android.gms") or
                    package.startswith("com.google.android.gsf")):
                    continue
                    
                # Find user installations
                user_installations = re.findall(r'User (\d+):[^\n]+installed=(\w+)', block)
                
                for user_id, installed in user_installations:
                    if installed == "true":
                        # This app is installed for this user
                        if user_id not in apps_by_user:
                            apps_by_user[user_id] = []
                            
                        # Get app details
                        app_info = {
                            "package": package,
                            "name": "",
                            "version": "",
                            "path": "",
                            "user_id": user_id
                        }
                        
                        # Extract app name
                        name_match = re.search(r'labelRes=\d+ label=([^ ]+)', block)
                        if name_match:
                            app_info["name"] = name_match.group(1)
                        else:
                            # Use package name as fallback
                            app_info["name"] = package.split(".")[-1].capitalize()
                            
                        # Extract version
                        version_match = re.search(r'versionName=([^\s]+)', block)
                        if version_match:
                            app_info["version"] = version_match.group(1)
                            
                        # Extract path
                        path_match = re.search(r'codePath=([^\s]+)', block)
                        if path_match:
                            app_info["path"] = path_match.group(1)
                            
                        apps_by_user[user_id].append(app_info)
            
            # Log the results
            for user_id, apps in apps_by_user.items():
                user_type = "Primary User"
                if user_id == "10":
                    user_type = "Work Profile"
                elif user_id == "150":
                    user_type = "Secure Folder"
                print(f"Found {len(apps)} third-party apps for User {user_id} ({user_type})")
                
            return apps_by_user
            
        except Exception as e:
            print(f"Error parsing dumpsys for apps: {e}")
            traceback.print_exc()
            return {}

    def extract_content_artifacts(self, case_folder, update_status=None):
        """Extract SMS, MMS, contacts, and call logs data using ADB content queries"""
        if update_status is None:
            update_status = lambda x: print(x)

        # Create organized directories for different data types
        messages_folder = os.path.join(case_folder, "Data", "Messages")
        contacts_folder = os.path.join(case_folder, "Data", "Contacts") 
        call_logs_folder = os.path.join(case_folder, "Data", "CallLogs")
        reports_folder = os.path.join(case_folder, "Reports")
        
        # Ensure directories exist
        os.makedirs(messages_folder, exist_ok=True)
        os.makedirs(contacts_folder, exist_ok=True)
        os.makedirs(call_logs_folder, exist_ok=True)
        os.makedirs(reports_folder, exist_ok=True)
        
        update_status(f"Created organized data directories")
        print(f"DEBUG: Created directories - Messages: {messages_folder}, Contacts: {contacts_folder}, CallLogs: {call_logs_folder}")
        
        results = {
            "messages_folder": messages_folder,
            "contacts_folder": contacts_folder,
            "call_logs_folder": call_logs_folder,
            "reports_folder": reports_folder,
            "sms_data": None,
            "mms_data": None,
            "contacts_data": None,
            "call_logs_data": None,
            "analysis_files": {}
        }
        
        # Content queries to execute with appropriate target directories
        content_queries = [
            {
                "name": "SMS Messages",
                "uri": "content://sms/",
                "output_file": "sms_messages.txt",
                "csv_file": "sms_messages.csv",
                "key": "sms_data",
                "target_folder": messages_folder
            },
            {
                "name": "MMS Messages", 
                "uri": "content://mms/",
                "output_file": "mms_messages.txt",
                "csv_file": "mms_messages.csv",
                "key": "mms_data",
                "target_folder": messages_folder
            },
            {
                "name": "Contacts",
                "uri": "content://com.android.contacts/data",
                "output_file": "contacts_data.txt", 
                "csv_file": "contacts_data.csv",
                "key": "contacts_data",
                "target_folder": contacts_folder
            },
            {
                "name": "Call Logs",
                "uri": "content://call_log/calls",
                "output_file": "call_logs.txt",
                "csv_file": "call_logs.csv",
                "key": "call_logs_data",
                "target_folder": call_logs_folder
            }
        ]
        
        for query in content_queries:
            try:
                update_status(f"Extracting {query['name']}...")
                
                # Run the content query
                raw_output = self.run_adb_command(f"shell content query --uri {query['uri']}")
                
                if not raw_output or raw_output.strip() == "":
                    if query['key'] == 'call_logs_data':
                        update_status(f"No call logs found - device may have no call history or call logs may not be accessible")
                        update_status(f"This is normal for new devices or devices with privacy restrictions")
                    else:
                        update_status(f"No data found for {query['name']}")
                    continue
                
                # Save raw output to appropriate directory
                raw_file_path = os.path.join(query['target_folder'], query['output_file'])
                with open(raw_file_path, 'w', encoding='utf-8') as f:
                    f.write(raw_output)
                
                update_status(f"Raw {query['name']} data saved to: {query['output_file']}")
                print(f"DEBUG: Saved {query['name']} raw data to: {raw_file_path}")
                
                # Convert to CSV format - use specialized method for contacts
                csv_file_path = os.path.join(query['target_folder'], query['csv_file'])
                print(f"DEBUG: Processing {query['name']} to CSV: {csv_file_path}")
                
                if query['key'] == 'contacts_data':
                    # Use specialized contacts processing that groups by raw_contact_id
                    rows_processed = self._convert_contacts_to_csv(raw_output, csv_file_path)
                elif query['key'] == 'call_logs_data':
                    # Use specialized call logs processing
                    rows_processed = self._convert_call_logs_to_csv(raw_output, csv_file_path)
                else:
                    # Use standard processing for SMS and MMS
                    rows_processed = self._convert_content_query_to_csv(raw_output, csv_file_path)
                
                print(f"DEBUG: Processed {rows_processed} rows for {query['name']}")
                
                if rows_processed > 0:
                    results[query['key']] = {
                        "raw_file": raw_file_path,
                        "csv_file": csv_file_path,
                        "record_count": rows_processed
                    }
                    print(f"DEBUG: Added {query['key']} to results with {rows_processed} records")
                    
                    if query['key'] == 'contacts_data':
                        update_status(f"Processed {rows_processed} unique contacts (grouped by raw_contact_id)")
                    elif query['key'] == 'call_logs_data':
                        update_status(f"Processed {rows_processed} call log entries")
                    else:
                        update_status(f"Converted {rows_processed} {query['name']} records to CSV")
                    
                    # Generate forensic analysis for each data type
                    analysis_file = None
                    if query['key'] == 'sms_data':
                        analysis_file = self._generate_sms_analysis(raw_file_path, reports_folder, update_status)
                    elif query['key'] == 'mms_data':
                        analysis_file = self._generate_mms_analysis(raw_file_path, reports_folder, update_status)
                    elif query['key'] == 'contacts_data':
                        analysis_file = self._generate_contacts_analysis(raw_file_path, reports_folder, update_status)
                    elif query['key'] == 'call_logs_data':
                        analysis_file = self._generate_call_logs_analysis(raw_file_path, reports_folder, update_status)
                
                    if analysis_file:
                        results["analysis_files"][query['key']] = analysis_file
                else:
                    update_status(f"No valid records found in {query['name']} data")
            except Exception as e:
                update_status(f"Error extracting {query['name']}: {str(e)}")
                continue
        
        return results
    
    def extract_external_files(self, case_folder, update_status=None):
        """Extract external files data using ADB content queries for videos, images, and downloads"""
        if update_status is None:
            update_status = lambda x: print(x)
        
        # Create external files folder INSIDE artifacts folder
        artifacts_folder = os.path.join(case_folder, "Artifacts")
        external_files_folder = os.path.join(artifacts_folder, "External_Files")  # Changed path
        os.makedirs(external_files_folder, exist_ok=True)
        update_status(f"Created external files folder: {external_files_folder}")
        
        results = {
            "external_files_folder": external_files_folder,
            "videos_data": None,
            "images_data": None,
            "downloads_data": None,
            "my_downloads_data": None
        }
        
        # External files queries to execute
        external_queries = [
            {
                "name": "External Videos",
                "uri": "content://media/external/video/media",
                "output_file": "external_videos.txt",
                "csv_file": "external_videos.csv",
                "key": "videos_data"
            },
            {
                "name": "External Images",
                "uri": "content://media/external/images/media",
                "output_file": "external_images.txt",
                "csv_file": "external_images.csv",
                "key": "images_data"
            },
            {
                "name": "Downloads",
                "uri": "content://downloads/download",
                "output_file": "downloads.txt",
                "csv_file": "downloads.csv",
                "key": "downloads_data"
            },
            {
                "name": "My Downloads",
                "uri": "content://downloads/my_downloads",
                "output_file": "my_downloads.txt",
                "csv_file": "my_downloads.csv",
                "key": "my_downloads_data"
            }
        ]
        
        # Track if any content query was successful
        any_query_successful = False
        
        for query in external_queries:
            try:
                update_status(f"Extracting {query['name']}...")
                
                # Run the content query
                raw_output = self.run_adb_command(f"shell content query --uri {query['uri']}")
                
                if not raw_output or raw_output.strip() == "":
                    update_status(f"No data found for {query['name']}")
                    continue
                
                # Save raw output
                raw_file_path = os.path.join(external_files_folder, query['output_file'])
                with open(raw_file_path, 'w', encoding='utf-8') as f:
                    f.write(raw_output)
                
                update_status(f"Raw {query['name']} data saved to: {query['output_file']}")
                
                # Convert to CSV format using standard processing
                csv_file_path = os.path.join(external_files_folder, query['csv_file'])
                rows_processed = self._convert_content_query_to_csv(raw_output, csv_file_path)
                
                if rows_processed > 0:
                    results[query['key']] = {
                        "raw_file": raw_file_path,
                        "csv_file": csv_file_path,
                        "record_count": rows_processed
                    }
                    update_status(f"Converted {rows_processed} {query['name']} records to CSV")
                    any_query_successful = True
                else:
                    update_status(f"No valid records found in {query['name']} data")
                    
            except Exception as e:
                update_status(f"Error extracting {query['name']}: {str(e)}")
                continue
        
        # Fallback to ls -R if content queries didn't return any data
        if not any_query_successful:
            update_status("Content queries returned no data. Falling back to ls -R method...")
            try:
                # Run ls -R on the storage directory
                ls_output_path = os.path.join(external_files_folder, "ls_r_output.txt")
                ls_command = "shell ls -R /storage/emulated/0"
                ls_output = self.run_adb_command(ls_command)
                
                # Save raw output
                with open(ls_output_path, 'w', encoding='utf-8') as f:
                    f.write(ls_output)
                
                update_status("Recursive listing of files completed and saved")
                
                # Process ls -R output into a format compatible with frontend
                fallback_results = self._process_ls_r_output(ls_output, external_files_folder)
                
                # Add fallback results to main results
                results.update(fallback_results)
                
                update_status("Fallback file extraction completed successfully")
            except Exception as e:
                update_status(f"Error during fallback extraction: {str(e)}")
        
        return results

    def _process_ls_r_output(self, ls_output, external_files_folder):
        """Process the ls -R output to a structure mimicking content query results"""
        lines = ls_output.split('\n')
        current_path = ""
        file_list = []
        
        # Parse ls -R output
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Lines ending with : indicate directory paths
            if line.endswith(':'):
                # Strip the trailing colon and leading ./
                current_path = line[:-1].strip()
                if current_path.startswith('./'):
                    current_path = current_path[2:]
                continue
                
            # Skip directories that start with . (hidden dirs)
            if '.' in line and not line.startswith('.'):
                file_list.append({
                    'path': f"/storage/emulated/0/{current_path}/{line}" if current_path else f"/storage/emulated/0/{line}",
                    'name': line,
                    'size': "0",  # We don't have size info from ls -R
                    'modified': "Unknown",  # No timestamp info
                    '_data': f"/storage/emulated/0/{current_path}/{line}" if current_path else f"/storage/emulated/0/{line}"
                })
        
        # Categorize files based on extensions
        videos = []
        images = []
        downloads = []
        others = []
        
        video_extensions = ['.mp4', '.3gp', '.mov', '.avi', '.mkv']
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
        download_indicators = ['/Download/', '/Downloads/']
        
        for file_info in file_list:
            file_path = file_info['path'].lower()
            extension = os.path.splitext(file_path)[1].lower()
            
            # Categorize by extension and path
            if '/Download/' in file_path or '/Downloads/' in file_path:
                downloads.append(file_info)
            elif extension in video_extensions:
                videos.append(file_info)
            elif extension in image_extensions:
                images.append(file_info)
            else:
                others.append(file_info)
        
        # Create CSV files for each category
        results = {}
        categories = [
            {"name": "External Videos", "files": videos, "csv_file": "external_videos.csv", "key": "videos_data"},
            {"name": "External Images", "files": images, "csv_file": "external_images.csv", "key": "images_data"},
            {"name": "Downloads", "files": downloads, "csv_file": "downloads.csv", "key": "downloads_data"},
            {"name": "Other Files", "files": others, "csv_file": "other_files.csv", "key": "other_files_data"}
        ]
        
        for category in categories:
            if category["files"]:
                csv_path = os.path.join(external_files_folder, category["csv_file"])
                record_count = self._write_files_to_csv(category["files"], csv_path)
                
                if record_count > 0:
                    results[category["key"]] = {
                        "raw_file": os.path.join(external_files_folder, "ls_r_output.txt"),
                        "csv_file": csv_path,
                        "record_count": record_count
                    }
        
        return results
    
    def _write_files_to_csv(self, files, csv_path):
        """Write file information to a CSV file"""
        try:
            with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['_id', '_data', '_size', 'title', 'date_modified', '_display_name', 'mime_type', 'path']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for i, file_info in enumerate(files):
                    extension = os.path.splitext(file_info['name'])[1].lower()
                    mime_type = "video/mp4" if extension in ['.mp4', '.3gp'] else \
                                "image/jpeg" if extension in ['.jpg', '.jpeg'] else \
                                "image/png" if extension == '.png' else \
                                "application/octet-stream"
                    
                    writer.writerow({
                        '_id': str(i + 1),
                        '_data': file_info['path'],
                        '_size': file_info['size'],
                        'title': file_info['name'],
                        'date_modified': file_info['modified'],
                        '_display_name': file_info['name'],
                        'mime_type': mime_type,
                        'path': file_info['path']
                    })
                
                return len(files)
                
        except Exception as e:
            print(f"Error writing files to CSV: {str(e)}")
            return 0
    
    def collect_notifications(self, case_folder, update_status=None):
        """Extract notification data using dumpsys notification command"""
        if update_status is None:
            update_status = lambda x: print(x)
            
        # Create notifications folder INSIDE artifacts folder
        artifacts_folder = os.path.join(case_folder, "Artifacts")
        notifications_folder = os.path.join(artifacts_folder, "Notifications")  # Changed path
        os.makedirs(notifications_folder, exist_ok=True)
        update_status(f"Created notifications folder: {notifications_folder}")
        
        results = {
            "notifications_folder": notifications_folder,
            "notifications_data": None
        }
            
        try:
            update_status("Extracting notification data...")
            
            # Run dumpsys notification command
            raw_file_path = os.path.join(notifications_folder, "notifications_raw.txt")
            csv_file_path = os.path.join(notifications_folder, "notifications.csv")
            
            # Execute the dumpsys notification command
            notifications_output = self.run_adb_command("shell dumpsys notification --noredact")
            
            # Save raw output
            with open(raw_file_path, 'w', encoding='utf-8') as f:
                f.write(notifications_output)
            
            update_status(f"Raw notification data saved to: {raw_file_path}")
            
            # Parse notification data and convert to CSV
            rows_processed = self._parse_notifications_to_csv(notifications_output, csv_file_path)
            
            if rows_processed > 0:
                results["notifications_data"] = {
                    "raw_file": raw_file_path,
                    "csv_file": csv_file_path,
                    "record_count": rows_processed
                }
                update_status(f"Processed {rows_processed} notification records to CSV")
            else:
                update_status("No valid notification records found")
                
        except Exception as e:
            update_status(f"Error extracting notifications: {str(e)}")
            
        return results
    
    def _parse_notifications_to_csv(self, notifications_output, csv_file_path):
        """Parse dumpsys notification output and convert to CSV format"""
        lines = notifications_output.strip().split('\n')
        notifications = []
        current_notification = {}
        in_notification_record = False
        in_extras = False
        
        for line in lines:
            line = line.strip()
            
            # Start of a new notification record
            if line.startswith('NotificationRecord('):
                if current_notification:
                    notifications.append(current_notification)
                current_notification = {}
                in_notification_record = True
                in_extras = False
                
                
                # Extract basic info from the record line
                if 'pkg=' in line:
                    current_notification['package'] = line.split('pkg=')[1].split()[0] if 'pkg=' in line else ''
                if 'id=' in line:
                    current_notification['id'] = line.split('id=')[1].split()[0] if 'id=' in line else ''
                        
            elif in_notification_record:
                if line.startswith('user='):
                    current_notification['user'] = line.split('=')[1] if '=' in line else ''
                elif line.startswith('tag='):
                    current_notification['tag'] = line.split('=')[1] if '=' in line else ''
                elif line.startswith('when='):
                    current_notification['when'] = line.split('=')[1] if '=' in line else ''
                elif line.startswith('flags='):
                    current_notification['flags'] = line.split('=')[1] if '=' in line else ''
                elif line.startswith('contentIntent='):
                    current_notification['content_intent'] = line.split('=')[1] if '=' in line else ''
                elif line.startswith('tickerText='):
                    current_notification['ticker_text'] = line.split('=')[1] if '=' in line else ''
                elif 'extras={' in line:
                    in_extras = True
                    extras_content = line.split('extras={')[1] if 'extras={' in line else ''
                    current_notification['extras'] = extras_content
                elif in_extras and '}' in line:
                    in_extras = False
                    if 'extras' in current_notification:
                        current_notification['extras'] += ' ' + line
                elif in_extras:
                    if 'extras' in current_notification:
                        current_notification['extras'] += ' ' + line
                    
            elif line.startswith('mArchive=') or line.startswith('TimeoutPendingIntent:'):
                in_notification_record = False
        
        # Add the last notification if we were processing one
        if current_notification:
            notifications.append(current_notification)
        
        # Write to CSV
        try:
            with open(csv_file_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['id', 'package', 'user', 'tag', 'when', 'flags', 'content_intent', 'ticker_text', 'extras']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for notification in notifications:
                    # Ensure all fields exist
                    row = {}
                    for field in fieldnames:
                        row[field] = notification.get(field, '')
                    writer.writerow(row)
                
                return len(notifications)
                
        except Exception as e:
            print(f"Error writing notifications to CSV: {str(e)}")
            return 0
    
    def _convert_content_query_to_csv(self, raw_output, csv_file_path):
        """Convert ADB content query output to CSV format"""
        try:
            lines = raw_output.strip().split('\n')
            rows = []
            headers = set()
            
            # First pass to gather all possible headers
            for line in lines:
                if line.startswith('Row:'):
                    row_data = line.split(' ', 2)[2] if len(line.split(' ', 2)) > 2 else ''
                    parts = re.split(r', (?=\w+=)', row_data)
                    for part in parts:
                        if '=' in part:
                            key = part.split('=', 1)[0]
                            headers.add(key.strip())

            if not headers:
                return 0

            sorted_headers = sorted(list(headers))

            # Second pass to parse rows
            for line in lines:
                if line.startswith('Row:'):
                    row_data = line.split(' ', 2)[2] if len(line.split(' ', 2)) > 2 else ''
                    
                    row = {header: '' for header in sorted_headers}
                    parts = re.split(r', (?=\w+=)', row_data)
                    for part in parts:
                        if '=' in part:
                            key, value = part.split('=', 1)
                            key = key.strip()
                            if key in row:
                                row[key] = value.strip()
                    
                    if any(row.values()):
                        rows.append(row)
            
            # Write to CSV
            if rows:
                with open(csv_file_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=sorted_headers)
                    writer.writeheader()
                    writer.writerows(rows)
                
                return len(rows)
            else:
                return 0
                
        except Exception as e:
            print(f"Error converting content query to CSV: {str(e)}")
            return 0
    
    def _convert_contacts_to_csv(self, raw_output, csv_file_path):
        """Convert contacts data to CSV format with contact grouping"""
        try:
            lines = raw_output.strip().split('\n')
            contacts_dict = {}
            
            # Parse each line and group by raw_contact_id
            for line in lines:
                if line.startswith('Row:'):
                    # Extract the row data part after "Row: X "
                    row_data = line.split(' ', 2)[2] if len(line.split(' ', 2)) > 2 else ''
                    
                    # Parse key=value pairs
                    row = {}
                    parts = row_data.split(', ')
                    for part in parts:
                        if '=' in part:
                            key, value = part.split('=', 1)
                            row[key.strip()] = value.strip()
                    
                    if row and 'raw_contact_id' in row:
                        contact_id = row['raw_contact_id']
                        if contact_id not in contacts_dict:
                            contacts_dict[contact_id] = {
                                'raw_contact_id': contact_id,
                                'display_name': '',
                                'phone_numbers': [],
                                'emails': [],
                                'addresses': [],
                                'organizations': [],
                                'other_data': []
                            }
                        
                        # Categorize the data based on mimetype
                        mimetype = row.get('mimetype', '')
                        data1 = row.get('data1', '')
                        
                        if 'vnd.android.cursor.item/phone' in mimetype:
                            if data1:
                                contacts_dict[contact_id]['phone_numbers'].append(data1)
                        elif 'vnd.android.cursor.item/email' in mimetype:
                            if data1:
                                contacts_dict[contact_id]['emails'].append(data1)
                        elif 'vnd.android.cursor.item/name' in mimetype:
                            if data1:
                                contacts_dict[contact_id]['display_name'] = data1
                        elif 'vnd.android.cursor.item/postal-address' in mimetype:
                            if data1:
                                contacts_dict[contact_id]['addresses'].append(data1)
                        elif 'vnd.android.cursor.item/organization' in mimetype:
                            if data1:
                                contacts_dict[contact_id]['organizations'].append(data1)
                        else:
                            if data1:
                                contacts_dict[contact_id]['other_data'].append(f"{mimetype}: {data1}")
            
            # Write to CSV
            if contacts_dict:
                with open(csv_file_path, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = ['raw_contact_id', 'display_name', 'phone_numbers', 'emails', 'addresses', 'organizations', 'other_data']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    
                    for contact in contacts_dict.values():
                        # Join lists with semicolons
                        row = {
                            'raw_contact_id': contact['raw_contact_id'],
                            'display_name': contact['display_name'],
                            'phone_numbers': '; '.join(contact['phone_numbers']),
                            'emails': '; '.join(contact['emails']),
                            'addresses': '; '.join(contact['addresses']),
                            'organizations': '; '.join(contact['organizations']),
                            'other_data': '; '.join(contact['other_data'])
                        }
                        writer.writerow(row)
                
                return len(contacts_dict)
            else:
                return 0
                
        except Exception as e:
            print(f"Error converting contacts to CSV: {str(e)}")
            return 0
    
    def _convert_call_logs_to_csv(self, raw_output, csv_file_path):
        """Convert call logs data to CSV format with proper formatting"""
        try:
            lines = raw_output.strip().split('\n')
            call_logs = []
            
            # Parse each line
            for line in lines:
                if line.startswith('Row:'):
                    call_data = self._parse_call_log_row(line)
                    if call_data:
                        # Add readable date if timestamp exists
                        if call_data.get('date') and call_data['date'].isdigit():
                            try:
                                timestamp = int(call_data['date'])
                                readable_date = datetime.datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')
                                call_data['readable_date'] = readable_date
                            except:
                                call_data['readable_date'] = 'Unknown'
                        
                        call_logs.append(call_data)
            
            # Write to CSV
            if call_logs:
                # Get all unique keys from all call log entries
                all_keys = set()
                for call in call_logs:
                    all_keys.update(call.keys())
                
                # Sort keys for consistent output
                sorted_keys = sorted(all_keys)
                
                with open(csv_file_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=sorted_keys)
                    writer.writeheader()
                    
                    for call in call_logs:
                        # Ensure all fields exist
                        clean_row = {}
                        for key in sorted_keys:
                            clean_row[key] = call.get(key, '')
                        writer.writerow(clean_row)
                
                return len(call_logs)
            else:
                return 0
                
        except Exception as e:
            print(f"Error converting call logs to CSV: {str(e)}")
            import traceback
            traceback.print_exc()
            return 0  
    def _parse_mms_row(self, row_line):
        """Parse a single MMS row from dumpsys output"""
        try:
            row_data = row_line.split(' ', 2)[2] if len(row_line.split(' ', 2)) > 2 else ''
            mms = {}
            parts = row_data.split(', ')
            for part in parts:
                if '=' in part:
                    key, value = part.split('=', 1)
                    mms[key.strip()] = value.strip()
            return mms if mms else None
        except Exception as e:
            return None

    def _parse_contact_row(self, row_line):
        """Parse a single contact row from dumpsys output"""
        try:
            row_data = row_line.split(' ', 2)[2] if len(row_line.split(' ', 2)) > 2 else ''
            contact = {}
            parts = row_data.split(', ')
            for part in parts:
                if '=' in part:
                    key, value = part.split('=', 1)
                    contact[key.strip()] = value.strip()
            return contact if contact else None
        except Exception as e:
            return None

    def _parse_call_log_row(self, row_line):
        """Parse a single call log row from dumpsys output"""
        try:
            row_data = row_line.split(' ', 2)[2] if len(row_line.split(' ', 2)) > 2 else ''
            call = {}
            parts = row_data.split(', ')
            for part in parts:
                if '=' in part:
                    key, value = part.split('=', 1)
                    call[key.strip()] = value.strip()
            return call if call else None
        except Exception as e:
            return None
        
    def _generate_sms_analysis(self, sms_raw_file, reports_folder, update_status):
        """Generate comprehensive forensic analysis of SMS data"""
        try:
            analysis_file = os.path.join(reports_folder, "sms_forensic_analysis.txt")
            
            with open(sms_raw_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse SMS data
            sms_messages = []
            lines = content.strip().split('\n')
            
            for line in lines:
                if line.startswith('Row:'):
                    sms = self._parse_sms_row(line)
                    if sms:
                        sms_messages.append(sms)
            
            # IMSI Analysis
            imsis = set()
            imsi_details = {}
            for sms in sms_messages:
                if sms.get('sim_imsi') and sms['sim_imsi'] != 'NULL':
                    imsi = sms['sim_imsi']
                    imsis.add(imsi)
                    
                    # Get detailed IMSI information if not already analyzed
                    if imsi not in imsi_details:
                        imsi_details[imsi] = self._get_imsi_info(imsi)
                        
            # Top 10 Contacts Analysis
            contact_stats = {}
            for sms in sms_messages:
                address = sms.get('address', '')
                if address and address != 'NULL':
                    if address not in contact_stats:
                        contact_stats[address] = {
                            'total_messages': 0,
                            'incoming': 0,
                            'outgoing': 0,
                            'dates': []
                        }
                    
                    contact_stats[address]['total_messages'] += 1
                    
                    # Track message direction (1=incoming, 2=outgoing)
                    msg_type = sms.get('type', '')
                    if msg_type == '1':
                        contact_stats[address]['incoming'] += 1
                    elif msg_type == '2':
                        contact_stats[address]['outgoing'] += 1
                    
                    # Track dates for timespan analysis
                    date_val = sms.get('date', '')
                    if date_val and date_val.isdigit():
                        try:
                            timestamp = int(date_val)
                            readable_date = datetime.datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')
                            contact_stats[address]['dates'].append(timestamp)
                        except:
                            pass
            
            # Sort contacts by total messages
            top_contacts = sorted(contact_stats.items(), key=lambda x: x[1]['total_messages'], reverse=True)[:10]
            
            # Verification Code Analysis
            verification_messages = []
            verification_patterns = [
                r'verification code[:\s]*(\d{4,8})',
                r'verify[:\s]*(\d{4,8})',
                r'code[:\s]*(\d{4,8})',
                r'OTP[:\s]*(\d{4,8})',
                r'PIN[:\s]*(\d{4,8})',
                r'(\d{4,8})\s*is your.*code',
                r'your.*code.*is[:\s]*(\d{4,8})',
                r'confirm.*(\d{4,8})',
                r'authentication.*(\d{4,8})',
                r'security.*code[:\s]*(\d{4,8})'
            ]
            
            verification_providers = {}
            
            for sms in sms_messages:
                body = sms.get('body', '').lower()
                address = sms.get('address', '')
                
                if body:
                    # Check for verification patterns
                    for pattern in verification_patterns:
                        matches = re.findall(pattern, body, re.IGNORECASE)
                        if matches:
                            provider = address if address else 'Unknown'
                            if provider not in verification_providers:
                                verification_providers[provider] = []
                            
                            # Extract timestamp
                            date_val = sms.get('date', '')
                            readable_date = 'Unknown'
                            if date_val and date_val.isdigit():
                                try:
                                    timestamp = int(date_val)
                                    readable_date = datetime.datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')
                                except:
                                    pass
                            
                            verification_providers[provider].append({
                                'code': matches[0],
                                'body': sms.get('body', ''),
                                'date': readable_date,
                                'type': sms.get('type', '')
                            })
                            verification_messages.append(sms)
                            break
            
            # Banking and Financial Institution Analysis
            banking_keywords = [
                'bank', 'banking', 'account', 'balance', 'transaction', 'transfer', 'payment',
                'deposit', 'withdrawal', 'atm', 'card', 'credit', 'debit', 'loan', 'mortgage',
                'investment', 'paypal', 'venmo', 'zelle', 'cashapp', 'financial', 'finance',
                'billing', 'invoice', 'charge', 'purchase', 'refund', 'fraud', 'security alert'
            ]
            
            banking_providers = [
                'bank', 'wells fargo', 'chase', 'bofa', 'citi', 'capital one', 'amex',
                'discover', 'paypal', 'venmo', 'zelle', 'cash app', 'square', 'stripe',
                'mastercard', 'visa', 'american express', 'fnb', 'standard bank',
                'absa', 'nedbank', 'capitec', 'vodacom', 'mtn', 'cell c', 'telkom'
            ]
            
            banking_messages = []
            banking_stats = {}
            
            for sms in sms_messages:
                body = sms.get('body', '').lower()
                address = sms.get('address', '').lower()
                
                is_banking = False
                
                # Check if address contains banking provider
                for provider in banking_providers:
                    if provider in address:
                        is_banking = True
                        break
                
                # Check if body contains banking keywords
                if not is_banking:
                    for keyword in banking_keywords:
                        if keyword in body:
                            is_banking = True
                            break
                
                if is_banking:
                    banking_messages.append(sms)
                    provider = sms.get('address', 'Unknown')
                    
                    if provider not in banking_stats:
                        banking_stats[provider] = {
                            'count': 0,
                            'messages': []
                        }
                    
                    banking_stats[provider]['count'] += 1
                    
                    # Extract timestamp
                    date_val = sms.get('date', '')
                    readable_date = 'Unknown'
                    if date_val and date_val.isdigit():
                        try:
                            timestamp = int(date_val)
                            readable_date = datetime.datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')
                        except:
                            pass
                    
                    banking_stats[provider]['messages'].append({
                        'body': sms.get('body', ''),
                        'date': readable_date,
                        'type': sms.get('type', '')
                    })
            
            # Calculate overall statistics
            total_messages = len(sms_messages)
            incoming_messages = len([m for m in sms_messages if m.get('type') == '1'])
            outgoing_messages = len([m for m in sms_messages if m.get('type') == '2'])
            
            # Date range analysis
            all_dates = []
            for sms in sms_messages:
                date_val = sms.get('date', '')
                if date_val and date_val.isdigit():
                    try:
                        timestamp = int(date_val)
                        all_dates.append(timestamp)
                    except:
                        pass
            
            date_range = None
            if all_dates:
                earliest = min(all_dates)
                latest = max(all_dates)
                earliest_date = datetime.datetime.fromtimestamp(earliest/1000).strftime('%Y-%m-%d %H:%M:%S')
                latest_date = datetime.datetime.fromtimestamp(latest/1000).strftime('%Y-%m-%d %H:%M:%S')
                date_range = f"{earliest_date} to {latest_date}"
            
            # Generate comprehensive analysis report
            with open(analysis_file, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("SMS MESSAGES FORENSIC ANALYSIS\n")
                f.write("=" * 80 + "\n")
                f.write(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                # Executive Summary
                f.write("-" * 17 + "\n")
                f.write(f"Total SMS Messages: {total_messages:,}\n")
                f.write(f"Incoming Messages: {incoming_messages:,}\n")
                f.write(f"Outgoing Messages: {outgoing_messages:,}\n")
                f.write(f"Unique Contacts: {len(contact_stats):,}\n")
                f.write(f"Verification Codes Found: {len(verification_messages):,}\n")
                f.write(f"Banking/Financial Messages: {len(banking_messages):,}\n")
                f.write(f"IMSIs Detected: {len(imsis)}\n")
                
                if date_range:
                    f.write(f"Date Range: {date_range}\n")
                
                f.write("\n")
                
                # IMSI Analysis
                f.write("IMSI (INTERNATIONAL MOBILE SUBSCRIBER IDENTITY) ANALYSIS\n")
                f.write("-" * 56 + "\n")
                # Modify the IMSI reporting section in _generate_sms_analysis
                if imsis:
                    f.write(f"Number of IMSIs Found: {len(imsis)}\n")
                    for i, imsi in enumerate(sorted(imsis), 1):
                        details = imsi_details.get(imsi, {})
                        country = details.get('country', 'Unknown')
                        operator = details.get('operator', 'Unknown')
                        
                        # Highlight country and carrier in the IMSI header
                        carrier_info = f" - {operator}" if operator != 'Unknown' else ""
                        country_info = f" - {country}" if country != 'Unknown' else ""
                        
                        f.write(f"IMSI {i}: {imsi}{country_info}{carrier_info}\n")
                        f.write("  " + "-" * 60 + "\n")
                        
                        # Count messages per IMSI
                        imsi_count = len([m for m in sms_messages if m.get('sim_imsi') == imsi])
                        f.write(f"  Messages using this IMSI: {imsi_count:,}\n")
                        
                        # Output detailed IMSI information
                        f.write(f"  Mobile Country Code (MCC): {details.get('mcc', '')}\n")
                        f.write(f"  Mobile Network Code (MNC): {details.get('mnc', '')}\n")
                        
                        # Enhanced country information
                        if country != 'Unknown':
                            f.write(f"  Country: {country}")
                            if details.get('country_code'):
                                f.write(f" ({details.get('country_code')})")
                            f.write("\n")
                        
                        # Enhanced carrier information 
                        if operator != 'Unknown':
                            f.write(f"  Network Operator: {operator}\n")
                            
                        if details.get('brand') and details.get('brand') != operator:
                            f.write(f"  Brand: {details.get('brand')}\n")
                            
                        if details.get('status'):
                            f.write(f"  Status: {details.get('status')}\n")
                            
                        if details.get('bands'):
                            f.write(f"  Network Bands: {details.get('bands')}\n")
                        
                        # Add a blank line between IMSIs
                        f.write("\n")
                else:
                    f.write("No IMSI information found in SMS records.\n\n")
                
                # Top 10 Contacts Analysis
                f.write("TOP 10 MOST MESSAGED CONTACTS\n")
                f.write("-" * 31 + "\n")
                
                for i, (contact, stats) in enumerate(top_contacts, 1):
                    f.write(f"{i}. {contact}\n")
                    f.write(f"   Total Messages: {stats['total_messages']:,}\n")
                    f.write(f"   Incoming: {stats['incoming']:,}, Outgoing: {stats['outgoing']:,}\n")
                    
                    # Calculate timespan
                    if stats['dates']:
                        earliest = min(stats['dates'])
                        latest = max(stats['dates'])
                        
                        if earliest != latest:
                            earliest_str = datetime.datetime.fromtimestamp(earliest/1000).strftime('%Y-%m-%d %H:%M:%S')
                            latest_str = datetime.datetime.fromtimestamp(latest/1000).strftime('%Y-%m-%d %H:%M:%S')
                            
                            # Calculate timespan in days
                            timespan_seconds = (latest - earliest) / 1000
                            timespan_days = timespan_seconds / 86400
                            
                            f.write(f"   First Message: {earliest_str}\n")
                            f.write(f"   Last Message: {latest_str}\n")
                            f.write(f"   Communication Timespan: {timespan_days:.1f} days\n")
                        else:
                            single_date = datetime.datetime.fromtimestamp(earliest/1000).strftime('%Y-%m-%d %H:%M:%S')
                            f.write(f"   Single Message Date: {single_date}\n")
                    
                    f.write("\n")
                
                # Verification Code Analysis
                f.write("VERIFICATION CODE ANALYSIS\n")
                f.write("-" * 27 + "\n")
                f.write(f"Total Verification Messages Found: {len(verification_messages):,}\n")
                f.write(f"Providers Sending Verification Codes: {len(verification_providers)}\n\n")
                
                if verification_providers:
                    f.write("VERIFICATION PROVIDERS:\n")
                    for provider, codes in sorted(verification_providers.items(), key=lambda x: len(x[1]), reverse=True):
                        f.write(f"\n{provider}: {len(codes)} verification messages\n")
                        f.write("-" * (len(provider) + 30) + "\n")
                        
                        for code_info in codes[-5:]:  # Show last 5 codes
                            f.write(f"Code: {code_info['code']}\n")
                            f.write(f"Date: {code_info['date']}\n")
                            f.write(f"Message: {code_info['body'][:100]}{'...' if len(code_info['body']) > 100 else ''}\n")
                            f.write("\n")
                
                # Banking and Financial Institution Analysis
                f.write("BANKING & COMMERCIAL INSTITUTION ANALYSIS\n")
                f.write("-" * 40 + "\n")
                f.write(f"Total Banking/Commercial Messages: {len(banking_messages):,}\n")
                f.write(f"Commercial Institutions Detected: {len(banking_stats)}\n\n")
                
                if banking_stats:
                    f.write("COMMERCIAL INSTITUTIONS:\n")
                    for provider, stats in sorted(banking_stats.items(), key=lambda x: x[1]['count'], reverse=True):
                        f.write(f"\n{provider}: {stats['count']} messages\n")
                        f.write("-" * (len(provider) + 20) + "\n")
                        
                        # Show recent messages
                        for msg in stats['messages'][-3:]:  # Show last 3 messages
                            f.write(f"Date: {msg['date']}\n")
                            f.write(f"Message: {msg['body'][:150]}{'...' if len(msg['body']) > 150 else ''}\n")
                            f.write("\n")
                
                # Investigative Indicators
                f.write("INVESTIGATIVE INDICATORS\n")
                f.write("-" * 23 + "\n")
                
                # High-value indicators
                if len(verification_messages) > 50:
                    f.write("Extensive verification code activity ({} codes)\n".format(len(verification_messages)))
                
                if len(banking_messages) > 20:
                    f.write("Significant banking/commercial activity ({} messages)\n".format(len(banking_messages)))
                
                if len(imsis) > 1:
                    f.write("Multiple IMSIs detected ({})\n".format(len(imsis)))
                
                # Check for international numbers
                international_contacts = [contact for contact in contact_stats.keys() if contact.startswith('+') and not contact.startswith('+1')]
                if international_contacts:
                    f.write("International contacts detected ({})\n".format(len(international_contacts)))
                
                # Check for suspicious patterns
                if incoming_messages > outgoing_messages * 3:
                    f.write("MEDIUM: Disproportionate incoming messages\n")
                
                f.write("\n")
                f.write("=" * 80 + "\n")
               
            
            update_status(f"Comprehensive SMS forensic analysis saved to: {analysis_file}")
            return analysis_file
            
        except Exception as e:
            update_status(f"Error generating SMS analysis: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def _generate_contacts_analysis(self, contacts_raw_file, reports_folder, update_status):
        """Generate forensic analysis of contacts data"""
        try:
            analysis_file = os.path.join(reports_folder, "contacts_forensic_analysis.txt")
            
            with open(contacts_raw_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse contacts data
            contacts = []
            lines = content.strip().split('\n')
            
            for line in lines:
                if line.startswith('Row:'):
                    contact = self._parse_contact_row(line)
                    if contact:
                        contacts.append(contact)
            
            # Group contacts by raw_contact_id to avoid duplicates
            contacts_dict = {}
            for contact in contacts:
                contact_id = contact.get('raw_contact_id', 'unknown')
                if contact_id not in contacts_dict:
                    contacts_dict[contact_id] = {
                        'raw_contact_id': contact_id,
                        'display_name': '',
                        'phone_numbers': [],
                        'emails': [],
                        'organizations': [],
                        'other_data': []
                    }
                
                # Categorize the data based on mimetype
                mimetype = contact.get('mimetype', '')
                data1 = contact.get('data1', '')
                
                if 'vnd.android.cursor.item/phone' in mimetype and data1:
                    contacts_dict[contact_id]['phone_numbers'].append(data1)
                elif 'vnd.android.cursor.item/email' in mimetype and data1:
                    contacts_dict[contact_id]['emails'].append(data1)
                elif 'vnd.android.cursor.item/name' in mimetype and data1:
                    contacts_dict[contact_id]['display_name'] = data1
                elif 'vnd.android.cursor.item/organization' in mimetype and data1:
                    contacts_dict[contact_id]['organizations'].append(data1)
            
            # Analyze email domains
            email_domains = {}
            all_emails = []
            
            for contact in contacts_dict.values():
                for email in contact['emails']:
                    all_emails.append(email)
                    if '@' in email:
                        domain = email.split('@')[1].lower().strip()
                        if domain:
                            email_domains[domain] = email_domains.get(domain, 0) + 1
            
            # Get top 5 email domains
            top_email_domains = sorted(email_domains.items(), key=lambda x: x[1], reverse=True)[:5]
            
            # Analyze phone numbers and country codes
            phone_analysis = {
                'international_numbers': [],
                'country_codes': {},
                'us_numbers': [],
                'local_numbers': [],
                'total_numbers': 0
            }
            
            # Country code mapping
            country_codes = {
                '+1': 'United States/Canada',
                '+7': 'Russia/Kazakhstan',
                '+20': 'Egypt',
                '+27': 'South Africa',
                '+30': 'Greece',
                '+31': 'Netherlands',
                '+32': 'Belgium',
                '+33': 'France',
                '+34': 'Spain',
                '+36': 'Hungary',
                '+39': 'Italy',
                '+40': 'Romania',
                '+41': 'Switzerland',
                '+43': 'Austria',
                '+44': 'United Kingdom',
                '+45': 'Denmark',
                '+46': 'Sweden',
                '+47': 'Norway',
                '+48': 'Poland',
                '+49': 'Germany',
                '+51': 'Peru',
                '+52': 'Mexico',
                '+53': 'Cuba',
                '+54': 'Argentina',
                '+55': 'Brazil',
                '+56': 'Chile',
                '+57': 'Colombia',
                '+58': 'Venezuela',
                '+60': 'Malaysia',
                '+61': 'Australia',
                '+62': 'Indonesia',
                '+63': 'Philippines',
                '+64': 'New Zealand',
                '+65': 'Singapore',
                '+66': 'Thailand',
                '+81': 'Japan',
                '+82': 'South Korea',
                '+84': 'Vietnam',
                '+86': 'China',
                '+90': 'Turkey',
                '+91': 'India',
                '+92': 'Pakistan',
                '+93': 'Afghanistan',
                '+94': 'Sri Lanka',
                '+95': 'Myanmar',
                '+98': 'Iran',
                '+212': 'Morocco',
                '+213': 'Algeria',
                '+216': 'Tunisia',
                '+218': 'Libya',
                '+220': 'Gambia',
                '+221': 'Senegal',
                '+222': 'Mauritania',
                '+223': 'Mali',
                '+224': 'Guinea',
                '+225': 'Ivory Coast',
                '+226': 'Burkina Faso',
                '+227': 'Niger',
                '+228': 'Togo',
                '+229': 'Benin',
                '+230': 'Mauritius',
                '+231': 'Liberia',
                '+232': 'Sierra Leone',
                '+233': 'Ghana',
                '+234': 'Nigeria',
                '+235': 'Chad',
                '+236': 'Central African Republic',
                '+237': 'Cameroon',
                '+238': 'Cape Verde',
                '+239': 'São Tomé and Príncipe',
                '+240': 'Equatorial Guinea',
                '+241': 'Gabon',
                '+242': 'Republic of the Congo',
                '+243': 'Democratic Republic of the Congo',
                '+244': 'Angola',
                '+245': 'Guinea-Bissau',
                '+246': 'British Indian Ocean Territory',
                '+248': 'Seychelles',
                '+249': 'Sudan',
                '+250': 'Rwanda',
                '+251': 'Ethiopia',
                '+252': 'Somalia',
                '+253': 'Djibouti',
                '+254': 'Kenya',
                '+255': 'Tanzania',
                '+256': 'Uganda',
                '+257': 'Burundi',
                '+258': 'Mozambique',
                '+260': 'Zambia',
                '+261': 'Madagascar',
                '+262': 'Réunion/Mayotte',
                '+263': 'Zimbabwe',
                '+264': 'Namibia',
                '+265': 'Malawi',
                '+266': 'Lesotho',
                '+267': 'Botswana',
                '+268': 'Eswatini',
                '+269': 'Comoros',
                '+290': 'Saint Helena',
                '+291': 'Eritrea',
                '+297': 'Aruba',
                '+298': 'Faroe Islands',
                '+299': 'Greenland',
                '+350': 'Gibraltar',
                '+351': 'Portugal',
                '+352': 'Luxembourg',
                '+353': 'Ireland',
                '+354': 'Iceland',
                '+355': 'Albania',
                '+356': 'Malta',
                '+357': 'Cyprus',
                '+358': 'Finland',
                '+359': 'Bulgaria',
                '+370': 'Lithuania',
                '+371': 'Latvia',
                '+372': 'Estonia',
                '+373': 'Moldova',
                '+374': 'Armenia',
                '+375': 'Belarus',
                '+376': 'Andorra',
                '+377': 'Monaco',
                '+378': 'San Marino',
                '+380': 'Ukraine',
                '+381': 'Serbia',
                '+382': 'Montenegro',
                '+383': 'Kosovo',
                '+385': 'Croatia',
                '+386': 'Slovenia',
                '+387': 'Bosnia and Herzegovina',
                '+389': 'North Macedonia',
                '+420': 'Czech Republic',
                '+421': 'Slovakia',
                '+423': 'Liechtenstein',
                '+500': 'Falkland Islands',
                '+501': 'Belize',
                '+502': 'Guatemala',
                '+503': 'El Salvador',
                '+504': 'Honduras',
                '+505': 'Nicaragua',
                '+506': 'Costa Rica',
                '+507': 'Panama',
                '+508': 'Saint Pierre and Miquelon',
                '+509': 'Haiti',
                '+590': 'Guadeloupe',
                '+591': 'Bolivia',
                '+592': 'Guyana',
                '+593': 'Ecuador',
                '+594': 'French Guiana',
                '+595': 'Paraguay',
                '+596': 'Martinique',
                '+597': 'Suriname',
                '+598': 'Uruguay',
                '+599': 'Netherlands Antilles',
                '+670': 'East Timor',
                '+672': 'Antarctica/Norfolk Island',
                '+673': 'Brunei',
                '+674': 'Nauru',
                '+675': 'Papua New Guinea',
                '+676': 'Tonga',
                '+677': 'Solomon Islands',
                '+678': 'Vanuatu',
                '+679': 'Fiji',
                '+680': 'Palau',
                '+681': 'Wallis and Futuna',
                '+682': 'Cook Islands',
                '+683': 'Niue',
                '+684': 'American Samoa',
                '+685': 'Samoa',
                '+686': 'Kiribati',
                '+687': 'New Caledonia',
                '+688': 'Tuvalu',
                '+689': 'French Polynesia',
                '+690': 'Tokelau',
                '+691': 'Micronesia',
                '+692': 'Marshall Islands',
                '+850': 'North Korea',
                '+852': 'Hong Kong',
                '+853': 'Macau',
                '+855': 'Cambodia',
                '+856': 'Laos',
                '+880': 'Bangladesh',
                '+886': 'Taiwan',
                '+960': 'Maldives',
                '+961': 'Lebanon',
                '+962': 'Jordan',
                '+963': 'Syria',
                '+964': 'Iraq',
                '+965': 'Kuwait',
                '+966': 'Saudi Arabia',
                '+967': 'Yemen',
                '+968': 'Oman',
                '+970': 'Palestine',
                '+971': 'United Arab Emirates',
                '+972': 'Israel',
                '+973': 'Bahrain',
                '+974': 'Qatar',
                '+975': 'Bhutan',
                '+976': 'Mongolia',
                '+977': 'Nepal',
                '+992': 'Tajikistan',
                '+993': 'Turkmenistan',
                '+994': 'Azerbaijan',
                '+995': 'Georgia',
                '+996': 'Kyrgyzstan',
                '+998': 'Uzbekistan'
            }
            
            # Analyze all phone numbers
            for contact in contacts_dict.values():
                for phone in contact['phone_numbers']:
                    phone_analysis['total_numbers'] += 1
                    phone_clean = phone.strip()
                    
                    # Check if it's an international number
                    if phone_clean.startswith('+'):
                        phone_analysis['international_numbers'].append(phone_clean)
                        
                        # Extract country code
                        # Try different lengths for country codes (1-4 digits)
                        for length in [4, 3, 2, 1]:
                            potential_code = phone_clean[:length+1]  # +1, +12, +123, +1234
                            if potential_code in country_codes:
                                country = country_codes[potential_code]
                                if potential_code not in phone_analysis['country_codes']:
                                    phone_analysis['country_codes'][potential_code] = {
                                        'country': country,
                                        'count': 0,
                                        'numbers': []
                                    }
                                phone_analysis['country_codes'][potential_code]['count'] += 1
                                phone_analysis['country_codes'][potential_code]['numbers'].append(phone_clean)
                                break
                        else:
                            # Unknown country code
                            unknown_code = phone_clean[:4] if len(phone_clean) >= 4 else phone_clean
                            if 'unknown' not in phone_analysis['country_codes']:
                                phone_analysis['country_codes']['unknown'] = {
                                    'country': 'Unknown Country',
                                    'count': 0,
                                    'numbers': []
                                }
                            phone_analysis['country_codes']['unknown']['count'] += 1
                            phone_analysis['country_codes']['unknown']['numbers'].append(phone_clean)
                    
                    elif phone_clean.startswith('1') and len(phone_clean) == 11:
                        # US/Canada number without + prefix
                        phone_analysis['us_numbers'].append(phone_clean)
                    else:
                        # Local number
                        phone_analysis['local_numbers'].append(phone_clean)
            
            # Generate analysis report
            total_contacts = len(contacts_dict)
            contacts_with_phones = len([c for c in contacts_dict.values() if c['phone_numbers']])
            contacts_with_emails = len([c for c in contacts_dict.values() if c['emails']])
            contacts_with_organizations = len([c for c in contacts_dict.values() if c['organizations']])
            
            with open(analysis_file, 'w', encoding='utf-8') as f:
                f.write("=" * 70 + "\n")
                f.write("CONTACTS FORENSIC ANALYSIS\n")
                f.write("=" * 70 + "\n")
                f.write(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                # Executive Summary
                f.write("-" * 17 + "\n")
                f.write(f"Total Unique Contacts: {total_contacts:,}\n")
                f.write(f"Contacts with Phone Numbers: {contacts_with_phones:,}\n")
                f.write(f"Contacts with Email Addresses: {contacts_with_emails:,}\n")
                f.write(f"Contacts with Organizations: {contacts_with_organizations:,}\n")
                f.write(f"Total Phone Numbers: {phone_analysis['total_numbers']:,}\n")
                f.write(f"Total Email Addresses: {len(all_emails):,}\n")
                f.write(f"International Numbers: {len(phone_analysis['international_numbers']):,}\n")
                f.write(f"Countries Represented: {len([k for k in phone_analysis['country_codes'].keys() if k != 'unknown'])}\n")
                f.write("\n")
                
                # Top 5 Email Domains Analysis
                f.write("TOP 5 EMAIL DOMAINS\n")
                f.write("-" * 19 + "\n")
                if top_email_domains:
                    for i, (domain, count) in enumerate(top_email_domains, 1):
                        percentage = (count / len(all_emails)) * 100 if all_emails else 0
                        f.write(f"{i}. {domain}: {count:,} addresses ({percentage:.1f}%)\n")
                        
                        # Categorize domain types
                        domain_type = "Unknown"
                        if domain in ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com', 'icloud.com']:
                            domain_type = "Consumer Email Provider"
                        elif domain.endswith('.edu'):
                            domain_type = "Educational Institution"
                        elif domain.endswith('.gov'):
                            domain_type = "Government"
                        elif domain.endswith('.mil'):
                            domain_type = "Military"
                        elif domain.endswith('.org'):
                            domain_type = "Organization"
                        elif any(corp in domain for corp in ['microsoft', 'google', 'apple', 'amazon', 'facebook']):
                            domain_type = "Major Corporation"
                        elif any(corp in domain for corp in ['proton', 'tuta', 'canary', 'disroot', 'onionmail', 'ctemplar']):
                            domain_type = "Privacy-Focused Email Provider"
                        else:
                            domain_type = "Business/Corporate"
                        
                        f.write(f"   Type: {domain_type}\n")
                        f.write("\n")
                else:
                    f.write("No email addresses found in contacts.\n\n")
                
                # Phone Number Country Code Analysis
                f.write("PHONE NUMBER COUNTRY CODE ANALYSIS\n")
                f.write("-" * 35 + "\n")
                f.write(f"Total Phone Numbers Analyzed: {phone_analysis['total_numbers']:,}\n")
                f.write(f"International Numbers: {len(phone_analysis['international_numbers']):,}\n")
                f.write(f"US/Canada Numbers: {len(phone_analysis['us_numbers']):,}\n")
                f.write(f"Local Numbers: {len(phone_analysis['local_numbers']):,}\n")
                f.write("\n")
                
                if phone_analysis['country_codes']:
                    f.write("COUNTRIES REPRESENTED:\n")
                    # Sort by count (most common first)
                    sorted_countries = sorted(phone_analysis['country_codes'].items(), 
                                            key=lambda x: x[1]['count'], reverse=True)
                    
                    for code, info in sorted_countries:
                        if code != 'unknown':
                            percentage = (info['count'] / phone_analysis['total_numbers']) * 100
                            f.write(f"{code} - {info['country']}: {info['count']:,} numbers ({percentage:.1f}%)\n")
                            
                            # Show sample numbers (first 3)
                            sample_numbers = info['numbers'][:3]
                            if sample_numbers:
                                f.write(f"   Sample numbers: {', '.join(sample_numbers)}\n")
                            f.write("\n")
                    
                    # Handle unknown country codes separately
                    if 'unknown' in phone_analysis['country_codes']:
                        unknown_info = phone_analysis['country_codes']['unknown']
                        f.write(f"Unknown Country Codes: {unknown_info['count']:,} numbers\n")
                        sample_unknown = unknown_info['numbers'][:5]
                        if sample_unknown:
                            f.write(f"   Sample numbers: {', '.join(sample_unknown)}\n")
                        f.write("\n")
                else:
                    f.write("No international numbers with identifiable country codes found.\n\n")
                
                # Geographic Distribution Summary
                f.write("GEOGRAPHIC DISTRIBUTION ANALYSIS\n")
                f.write("-" * 32 + "\n")
                
                # Analyze by region
                regions = {
                    'North America': ['+1'],
                    'Europe': ['+30', '+31', '+32', '+33', '+34', '+36', '+39', '+40', '+41', '+43', '+44', '+45', '+46', '+47', '+48', '+49'],
                    'Asia': ['+60', '+61', '+62', '+63', '+64', '+65', '+66', '+81', '+82', '+84', '+86', '+90', '+91', '+92', '+93', '+94', '+95', '+98'],
                    'Africa': ['+20', '+27', '+212', '+213', '+216', '+218', '+220', '+221', '+222', '+223', '+224', '+225', '+226', '+227', '+228', '+229', '+230', '+231', '+232', '+233', '+234', '+235', '+236', '+237', '+238', '+239', '+240', '+241', '+242', '+243', '+244', '+245', '+248', '+249', '+250', '+251', '+252', '+253', '+254', '+255', '+256', '+257', '+258', '+260', '+261', '+262', '+263', '+264', '+265', '+266', '+267', '+268', '+269', '+290', '+291'],
                    'South America': ['+51', '+52', '+53', '+54', '+55', '+56', '+57', '+58', '+591', '+592', '+593', '+594', '+595', '+596', '+597', '+598'],
                    'Middle East': ['+961', '+962', '+963', '+964', '+965', '+966', '+967', '+968', '+970', '+971', '+972', '+973', '+974'],
                    'Oceania': ['+61', '+64', '+670', '+672', '+673', '+674', '+675', '+676', '+677', '+678', '+679', '+680', '+681', '+682', '+683', '+684', '+685', '+686', '+687', '+688', '+689', '+690', '+691', '+692']
                }
                
                region_counts = {}
                for region, codes in regions.items():
                    region_counts[region] = 0
                    for code in codes:
                        if code in phone_analysis['country_codes']:
                            region_counts[region] += phone_analysis['country_codes'][code]['count']
                
                # Only show regions with contacts
                active_regions = {k: v for k, v in region_counts.items() if v > 0}
                if active_regions:
                    f.write("Contacts by Geographic Region:\n")
                    for region, count in sorted(active_regions.items(), key=lambda x: x[1], reverse=True):
                        percentage = (count / phone_analysis['total_numbers']) * 100
                        f.write(f"  {region}: {count:,} contacts ({percentage:.1f}%)\n")
                    f.write("\n")
                
                # Investigative Indicators
                f.write("INVESTIGATIVE INDICATORS\n")
                f.write("-" * 23 + "\n")
                
                # High-value indicators
                international_percentage = (len(phone_analysis['international_numbers']) / phone_analysis['total_numbers'] * 100) if phone_analysis['total_numbers'] > 0 else 0
                
                if international_percentage > 30:
                    f.write("High percentage of international contacts ({:.1f}%)\n".format(international_percentage))
                
                if len(phone_analysis['country_codes']) > 5:
                    f.write("Contacts from {} different countries\n".format(len(phone_analysis['country_codes'])))
                
                f.write("\n")
                f.write("=" * 70 + "\n")
               
            
            update_status(f"Contacts analysis saved to: {analysis_file}")
            return analysis_file
            
        except Exception as e:
            update_status(f"Error generating contacts analysis: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
        
    def _parse_sms_row(self, row_line):
        """Parse a single SMS row from dumpsys output"""
        try:
            # Extract the row data part after "Row: X "
            parts = row_line.split(' ', 2)
            if len(parts) < 3:
                return None
                
            row_data = parts[2]
            sms = {}
            
            # Split by comma and parse key=value pairs
            items = []
            current_item = ""
            in_quotes = False
            
            for char in row_data:
                if char == '"':
                    in_quotes = not in_quotes
                elif char == ',' and not in_quotes:
                    items.append(current_item.strip())
                    current_item = ""
                    continue
                current_item += char
            
            # Add the last item
            if current_item.strip():
                items.append(current_item.strip())
            
            # Parse each key=value pair
            for item in items:
                if '=' in item:
                    key, value = item.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    
                    sms[key] = value
            
            return sms if sms else None
            
        except Exception as e:
            print(f"Error parsing SMS row: {e}")
            return None

    def _parse_contact_row(self, row_line):
        """Parse a single contact row from dumpsys output"""
        try:
            # Extract the row data part after "Row: X "
            parts = row_line.split(' ', 2)
            if len(parts) < 3:
                return None
                
            row_data = parts[2]
            contact = {}
            
            # Split by comma and parse key=value pairs
            items = []
            current_item = ""
            in_quotes = False
            
            for char in row_data:
                if char == '"':
                    in_quotes = not in_quotes
                elif char == ',' and not in_quotes:
                    items.append(current_item.strip())
                    current_item = ""
                    continue
                current_item += char
            
            # Add the last item
            if current_item.strip():
                items.append(current_item.strip())
            
            # Parse each key=value pair
            for item in items:
                if '=' in item:
                    key, value = item.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    
                    contact[key] = value
            
            return contact if contact else None
            
        except Exception as e:
            print(f"Error parsing contact row: {e}")
            return None

    def _parse_call_log_row(self, row_line):
        """Parse a single call log row from dumpsys output"""
        try:
            # Extract the row data part after "Row: X "
            parts = row_line.split(' ', 2)
            if len(parts) < 3:
                return None
                
            row_data = parts[2]
            call = {}
            
            # Split by comma and parse key=value pairs
            items = []
            current_item = ""
            in_quotes = False
            
            for char in row_data:
                if char == '"':
                    in_quotes = not in_quotes
                elif char == ',' and not in_quotes:
                    items.append(current_item.strip())
                    current_item = ""
                    continue
                current_item += char
            
            # Add the last item
            if current_item.strip():
                items.append(current_item.strip())
            
            # Parse each key=value pair
            for item in items:
                if '=' in item:
                    key, value = item.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    
                    call[key] = value
            
            return call if call else None
            
        except Exception as e:
            print(f"Error parsing call log row: {e}")
            return None
    

    def _generate_mms_analysis(self, mms_raw_file, reports_folder, update_status):
        """Generate forensic analysis of MMS data"""
        try:
            analysis_file = os.path.join(reports_folder, "mms_forensic_analysis.txt")
            
            with open(mms_raw_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse MMS data
            mms_messages = []
            lines = content.strip().split('\n')
            
            for line in lines:
                if line.startswith('Row:'):
                    mms = self._parse_sms_row(line)  # MMS uses similar structure to SMS
                    if mms:
                        mms_messages.append(mms)
            
            # Basic analysis
            total_messages = len(mms_messages)
            incoming_messages = len([m for m in mms_messages if m.get('type') == '1'])
            outgoing_messages = len([m for m in mms_messages if m.get('type') == '2'])
            
            # Contact analysis
            contact_stats = {}
            for mms in mms_messages:
                address = mms.get('address', '')
                if address and address != 'NULL':
                    contact_stats[address] = contact_stats.get(address, 0) + 1
            
            top_contacts = sorted(contact_stats.items(), key=lambda x: x[1], reverse=True)[:5]
            
            with open(analysis_file, 'w', encoding='utf-8') as f:
                f.write("=" * 60 + "\n")
                f.write("MMS MESSAGES FORENSIC ANALYSIS\n")
                f.write("=" * 60 + "\n")
                f.write(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                f.write("-" * 17 + "\n")
                f.write(f"Total MMS Messages: {total_messages:,}\n")
                f.write(f"Incoming Messages: {incoming_messages:,}\n")
                f.write(f"Outgoing Messages: {outgoing_messages:,}\n")
                f.write(f"Unique Contacts: {len(contact_stats):,}\n\n")
                
                if top_contacts:
                    f.write("TOP 5 MMS CONTACTS\n")
                    f.write("-" * 18 + "\n")
                    for i, (contact, count) in enumerate(top_contacts, 1):
                        f.write(f"{i}. {contact}: {count:,} messages\n")
                    f.write("\n")
                
                f.write("=" * 60 + "\n")
                
            
            update_status(f"MMS analysis saved to: {analysis_file}")
            return analysis_file
            
        except Exception as e:
            update_status(f"Error generating MMS analysis: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def _generate_call_logs_analysis(self, call_logs_raw_file, reports_folder, update_status):
        """Generate forensic analysis of call logs data"""
        try:
            analysis_file = os.path.join(reports_folder, "call_logs_forensic_analysis.txt")
            
            with open(call_logs_raw_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse call logs
            call_logs = []
            lines = content.strip().split('\n')
            
            for line in lines:
                if line.startswith('Row:'):
                    call = self._parse_call_log_row(line)
                    if call:
                        call_logs.append(call)
            
            # Analysis
            total_calls = len(call_logs)
            incoming_calls = len([c for c in call_logs if c.get('type') == '1'])
            outgoing_calls = len([c for c in call_logs if c.get('type') == '2'])
            missed_calls = len([c for c in call_logs if c.get('type') == '3'])
            
            # Contact analysis
            contact_stats = {}
            for call in call_logs:
                number = call.get('number', '')
                if number and number != 'NULL':
                    if number not in contact_stats:
                        contact_stats[number] = {'total': 0, 'incoming': 0, 'outgoing': 0, 'missed': 0, 'total_duration': 0}
                    contact_stats[number]['total'] += 1
                    
                    call_type = call.get('type', '')
                    if call_type == '1':
                        contact_stats[number]['incoming'] += 1
                    elif call_type == '2':
                        contact_stats[number]['outgoing'] += 1
                    elif call_type == '3':
                        contact_stats[number]['missed'] += 1
                    
                    # Track duration
                    duration = int(call.get('duration', 0)) if call.get('duration', '').isdigit() else 0
                    contact_stats[number]['total_duration'] += duration
            
            top_contacts = sorted(contact_stats.items(), key=lambda x: x[1]['total'], reverse=True)[:10]
            
            # Calculate durations
            durations = [int(c.get('duration', 0)) for c in call_logs if c.get('duration', '').isdigit()]
            total_duration = sum(durations)
            
            with open(analysis_file, 'w', encoding='utf-8') as f:
                f.write("=" * 70 + "\n")
                f.write("CALL LOGS FORENSIC ANALYSIS\n")
                f.write("=" * 70 + "\n")
                f.write(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                f.write("-" * 17 + "\n")
                f.write(f"Total Call Records: {total_calls:,}\n")
                f.write(f"Incoming Calls: {incoming_calls:,}\n")
                f.write(f"Outgoing Calls: {outgoing_calls:,}\n")
                f.write(f"Missed Calls: {missed_calls:,}\n")
                f.write(f"Unique Numbers: {len(contact_stats):,}\n")
                f.write(f"Total Call Duration: {total_duration} seconds ({total_duration//60} minutes)\n\n")
                
                if top_contacts:
                    f.write("TOP 10 MOST CALLED NUMBERS\n")
                    f.write("-" * 27 + "\n")
                    for i, (number, stats) in enumerate(top_contacts, 1):
                        f.write(f"{i}. {number}\n")
                        f.write(f"   Total Calls: {stats['total']:,}\n")
                        f.write(f"   Incoming: {stats['incoming']:,}, Outgoing: {stats['outgoing']:,}, Missed: {stats['missed']:,}\n")
                        
                        # Format duration
                        total_min = stats['total_duration'] // 60
                        total_sec = stats['total_duration'] % 60
                        f.write(f"   Total Talk Time: {total_min}m {total_sec}s\n\n")
                
                f.write("=" * 70 + "\n")
               
            
            update_status(f"Call logs analysis saved to: {analysis_file}")
            return analysis_file
            
        except Exception as e:
            update_status(f"Error generating call logs analysis: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
        
        
    def _load_mcc_lookup(self):
        """Load MCC/MNC lookup data from JSON file"""
        try:
            # Define the path to the MCC lookup file
            mcc_lookup_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                "utils", 
                "mcc_lookup.json"
            )
            
            print(f"Looking for MCC lookup file at: {mcc_lookup_path}")
            
            # Load the JSON data
            with open(mcc_lookup_path, 'r', encoding='utf-8') as f:
                mcc_data = json.load(f)
            
            print(f"Loaded MCC lookup data with {len(mcc_data)} entries")
            
            # Create lookup dictionaries for faster access
            mcc_country_map = {}  # MCC to country mapping
            mcc_mnc_network_map = {}  # MCC-MNC to network mapping
            
            for entry in mcc_data:
                # Skip entries without proper data
                if not entry.get('mcc'):
                    continue
                    
                mcc = entry.get('mcc')
                mnc = entry.get('mnc')
                
                # Map MCC to country - Updated field names to match JSON
                if mcc and entry.get('countryName'):
                    mcc_country_map[mcc] = {
                        'country_name': entry.get('countryName', 'Unknown'),
                        'country_code': entry.get('countryCode', '')
                    }
                
                # Map MCC-MNC to network - Updated field names to match JSON
                if mcc and mnc:
                    key = f"{mcc}-{mnc}"
                    mcc_mnc_network_map[key] = {
                        'operator': entry.get('operator', ''),
                        'brand': entry.get('brand', ''),
                        'status': entry.get('status', ''),
                        'bands': entry.get('bands', '')
                    }
            
            print(f"Processed {len(mcc_country_map)} country codes and {len(mcc_mnc_network_map)} network codes")
            return {
                'mcc_country_map': mcc_country_map,
                'mcc_mnc_network_map': mcc_mnc_network_map,
                'raw_data': mcc_data
            }
                
        except Exception as e:
            print(f"Error loading MCC lookup data: {e}")
            import traceback
            traceback.print_exc()
            # Return empty dictionaries as fallback
            return {
                'mcc_country_map': {},
                'mcc_mnc_network_map': {},
                'raw_data': []
            }
    
    def _get_imsi_info(self, imsi):
        """Get detailed information from an IMSI number"""
        if not imsi or len(imsi) < 5:
            return {
                'mcc': '',
                'mnc': '',
                'country': 'Unknown',
                'operator': 'Unknown'
            }
        
        # Extract MCC (first 3 digits)
        mcc = imsi[:3]
        
        # Extract MNC (typically next 2-3 digits)
        # Try 3-digit MNC first, then 2-digit if not found
        mnc_3 = imsi[3:6] if len(imsi) >= 6 else ''
        mnc_2 = imsi[3:5] if len(imsi) >= 5 else ''
        
        # Load MCC lookup data if not already loaded
        if not hasattr(self, '_mcc_lookup_data'):
            self._mcc_lookup_data = self._load_mcc_lookup()
        
        # Get country information based on MCC
        country_info = self._mcc_lookup_data['mcc_country_map'].get(mcc, {})
        country = country_info.get('country_name', 'Unknown')
        
        # Try to get operator information based on MCC-MNC
        # Try 3-digit MNC first, then 2-digit
        operator_info = {}
        used_mnc = None
        
        if mnc_3:
            key_3 = f"{mcc}-{mnc_3}"
            operator_info = self._mcc_lookup_data['mcc_mnc_network_map'].get(key_3, {})
            if operator_info:
                used_mnc = mnc_3
        
        if not operator_info and mnc_2:
            key_2 = f"{mcc}-{mnc_2}"
            operator_info = self._mcc_lookup_data['mcc_mnc_network_map'].get(key_2, {})
            if operator_info:
                used_mnc = mnc_2
        
        # If we couldn't find the specific carrier, still use the MNC value
        mnc = used_mnc if used_mnc else (mnc_2 if len(mnc_2) > 0 else '')
        
        return {
            'mcc': mcc,
            'mnc': mnc,
            'country': country,
            'country_code': country_info.get('country_code', ''),
            'operator': operator_info.get('operator', 'Unknown'),
            'brand': operator_info.get('brand', ''),
            'status': operator_info.get('status', ''),
            'bands': operator_info.get('bands', '')
        }           
       