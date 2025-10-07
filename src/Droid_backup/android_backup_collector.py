#!/usr/bin/env python3
"""
Arsenic Triage - Android Forensic Data Collector

A comprehensive tool for collecting forensic data from Android devices using ADB
and content provider URIs. This tool provides a systematic approach to extracting
various types of data from Android devices for forensic analysis.

Author: Arsenic Triage Forensic Suite
Date: July 13, 2025
"""

import subprocess
import json
import csv
import os
import sys
import logging
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import argparse
from pathlib import Path

# Windows-specific subprocess flag to prevent console windows
if sys.platform == "win32":
    SUBPROCESS_FLAGS = subprocess.CREATE_NO_WINDOW
else:
    SUBPROCESS_FLAGS = 0

# # Configure logging for forensic audit trail
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(levelname)s - %(message)s',
#     handlers=[
#         logging.FileHandler(f'forensic_collection_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
#         logging.StreamHandler()
#     ]
# )

# Configure logging for console output only (no file creation)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class ArsenicTriageCollector:
    """Main class for Android forensic data collection using ADB content URIs."""
    
    def __init__(self, device_id: Optional[str] = None, output_dir: Optional[str] = None, adb_command: Optional[str] = None):
        """
        Initialize the Arsenic Triage collector.
        
        Args:
            device_id: Specific device ID to target, if multiple devices connected
            output_dir: Output directory for collected data (optional for device checking)
            adb_command: Custom ADB command path (for cross-platform compatibility)
        """
        self.device_id = device_id
        self.output_dir = output_dir
        self.adb_command = adb_command or 'adb'  # Default to 'adb' if not specified
        # App uses different output directories based on Android API level
        self.device_output_dir_legacy = "/storage/emulated/0/ArsenicTriage"
        self.device_output_dir_modern = "/storage/emulated/0/Android/data/com.arsenictriage.datacollector/files/ArsenicTriage"
        self.app_package = "com.arsenictriage.datacollector"
        self.app_activity = f"{self.app_package}/.MainActivity"
        
        # Only create output directory if one was provided
        if self.output_dir:
            self.ensure_output_directory()
    
    def _find_resource_file(self, filename: str, subdirs: List[str] = None) -> Optional[str]:
        """
        Find a resource file (APK, JAR, etc.) in different possible locations
        for development, bundled, and compiled environments.
        
        Args:
            filename: Name of the file to find (e.g., 'arsenic_triage.apk', 'abe.jar')
            subdirs: Subdirectories to search in (e.g., ['src', 'utils'])
        
        Returns:
            Full path to the file if found, None otherwise
        """
        if subdirs is None:
            subdirs = ['src', 'utils']
            
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Build possible paths for different environments
        possible_paths = [
            # For bundled app: same level as current directory  
            os.path.join(os.path.dirname(current_dir), *subdirs, filename),
            # For development: two levels up then subdirs
            os.path.join(os.path.dirname(os.path.dirname(current_dir)), *subdirs, filename),
            # For PyInstaller bundle: relative to current directory
            os.path.join(current_dir, "..", *subdirs, filename)
        ]
        
        for path in possible_paths:
            normalized_path = os.path.normpath(path)
            print(f"🔍 Checking {filename} path: {normalized_path}")
            if os.path.exists(normalized_path):
                print(f"✅ Found {filename} at: {normalized_path}")
                return normalized_path
        
        print(f"❌ {filename} not found in any of the expected locations:")
        for path in possible_paths:
            print(f"  - {os.path.normpath(path)}")
        return None
    
    def get_abe_jar_path(self) -> Optional[str]:
        """Get the path to abe.jar for Android backup extraction"""
        return self._find_resource_file('abe.jar')
    
    def _run_subprocess(self, command, **kwargs):
        """Helper method to run subprocess with proper encoding handling"""
        # Set default encoding parameters for Windows compatibility
        default_kwargs = {
            'capture_output': True,
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
        # Debug logging
        debug_file = "/tmp/adb_backup_debug.log"
        with open(debug_file, "a") as f:
            f.write(f"\n=== _run_subprocess_popen DEBUG START ===\n")
            f.write(f"Received command: {command}\n")
            f.write(f"Command type: {type(command)}\n")
            f.write(f"Is list: {isinstance(command, list)}\n")
        
        # CRITICAL: Ensure command is a list
        if not isinstance(command, list):
            with open(debug_file, "a") as f:
                f.write(f"ERROR: Command is not a list! Converting...\n")
            if isinstance(command, str):
                import shlex
                command = shlex.split(command)
                with open(debug_file, "a") as f:
                    f.write(f"Converted to list: {command}\n")
        
        # Handle commands with paths containing spaces
        if isinstance(command, list) and len(command) > 0:
            executable = command[0]
            
            with open(debug_file, "a") as f:
                f.write(f"Original executable: '{executable}'\n")
                f.write(f"Executable type: {type(executable)}\n")
                f.write(f"Executable exists: {os.path.exists(executable)}\n")
                f.write(f"Has spaces: {' ' in executable}\n")
            
            # ALWAYS use temp path if executable has spaces
            if ' ' in executable:
                with open(debug_file, "a") as f:
                    f.write(f"⚠️  DETECTED SPACE IN PATH - Creating temp executable\n")
                
                # Verify original exists first
                if not os.path.exists(executable):
                    error_msg = f"ERROR: Executable doesn't exist: '{executable}'"
                    with open(debug_file, "a") as f:
                        f.write(f"{error_msg}\n")
                    raise FileNotFoundError(error_msg)
                
                import tempfile
                import shutil
                temp_dir = tempfile.gettempdir()
                temp_adb_name = "adb_temp_" + str(os.getpid())
                temp_adb_path = os.path.join(temp_dir, temp_adb_name)
                
                with open(debug_file, "a") as f:
                    f.write(f"Temp path: {temp_adb_path}\n")
                
                # Remove any existing temp file
                if os.path.exists(temp_adb_path):
                    with open(debug_file, "a") as f:
                        f.write(f"Removing existing temp file...\n")
                    try:
                        os.remove(temp_adb_path)
                    except:
                        pass
                
                # Try symlink first, fallback to copy
                try:
                    with open(debug_file, "a") as f:
                        f.write(f"Attempting symlink: {temp_adb_path} -> {executable}\n")
                    os.symlink(executable, temp_adb_path)
                    with open(debug_file, "a") as f:
                        f.write(f"✅ Symlink created successfully\n")
                except (OSError, NotImplementedError) as e:
                    with open(debug_file, "a") as f:
                        f.write(f"Symlink failed ({e}), using copy instead...\n")
                    shutil.copy2(executable, temp_adb_path)
                    os.chmod(temp_adb_path, 0o755)
                    with open(debug_file, "a") as f:
                        f.write(f"✅ Copy created successfully\n")
                
                # Update command to use temp path
                command = list(command)  # Make a copy
                command[0] = temp_adb_path
                
                with open(debug_file, "a") as f:
                    f.write(f"✅ Updated command[0] to: {temp_adb_path}\n")
                    f.write(f"Temp file exists: {os.path.exists(temp_adb_path)}\n")
                    f.write(f"Temp file executable: {os.access(temp_adb_path, os.X_OK)}\n")
        
        with open(debug_file, "a") as f:
            f.write(f"Final command to execute: {command}\n")
            f.write(f"Final command[0]: '{command[0]}'\n")
            f.write(f"=== _run_subprocess_popen DEBUG END ===\n\n")
        
        # Set default encoding parameters for cross-platform compatibility
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
        
        with open(debug_file, "a") as f:
            f.write(f"About to call subprocess.Popen with command[0]='{command[0]}'\n")
        
        try:
            process = subprocess.Popen(command, **default_kwargs)
            with open(debug_file, "a") as f:
                f.write(f"✅ subprocess.Popen succeeded, PID={process.pid}\n")
            return process
        except Exception as e:
            with open(debug_file, "a") as f:
                f.write(f"❌ subprocess.Popen FAILED: {e}\n")
                import traceback
                f.write(f"Traceback: {traceback.format_exc()}\n")
            raise
        
    def ensure_output_directory(self):
        """Create output directory for collected data if specified."""
        if self.output_dir and not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            logger.info(f"Created output directory: {self.output_dir}")
    
    def execute_adb_command(self, command: str) -> Tuple[bool, str]:
        """
        Execute an ADB command and return result.
        
        Args:
            command: ADB command to execute
            
        Returns:
            Tuple of (success, output)
        """
        try:
            device_arg = f"-s {self.device_id}" if self.device_id else ""
            full_command = f"{self.adb_command} {device_arg} {command}"
            logger.info(f"Executing: {full_command}")
            
            result = self._run_subprocess(
                full_command.split(),
                timeout=30
            )
            
            if result.returncode == 0:
                logger.info("Command executed successfully")
                return True, result.stdout
            else:
                logger.error(f"Command failed: {result.stderr}")
                return False, result.stderr
                
        except subprocess.TimeoutExpired:
            logger.error("Command timed out")
            return False, "Command timed out"
        except Exception as e:
            logger.error(f"Exception executing command: {e}")
            return False, str(e)
    
    def query_content_provider(self, uri: str, projection: Optional[str] = None) -> Tuple[bool, str]:
        """
        Query an Android content provider using content URI.
        
        Args:
            uri: Content URI to query
            projection: Columns to select (optional)
            
        Returns:
            Tuple of (success, output)
        """
        projection_arg = f"--projection {projection}" if projection else ""
        command = f"shell content query --uri {uri} {projection_arg}"
        return self.execute_adb_command(command)
    
    def save_data(self, filename: str, data: str):
        """Save collected data to file."""
        if not self.output_dir:
            # If no output directory specified, just print the data
            print(f"Data for {filename}:")
            print(data)
            print("-" * 50)
            return
            
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(data)
        logger.info(f"Data saved to: {filepath}")
    
    # Remove the old duplicate method - now using _discover_content_providers_raw and _generate_provider_report
    
    def test_content_provider_access(self, authority: str) -> Tuple[bool, str, str]:
        """
        Test access to a specific content provider authority.
        
        Args:
            authority: Content provider authority to test
            
        Returns:
            Tuple of (accessible, sample_data, error_message)
        """
        uri = f"content://{authority}"
        success, data = self.query_content_provider(uri)
        
        if success and data.strip():
            # Limit sample data to first few lines for testing
            sample_lines = data.split('\n')[:3]
            sample_data = '\n'.join(sample_lines)
            return True, sample_data, ""
        elif success:
            return False, "", "Provider accessible but returned no data"
        else:
            return False, "", data
    
    # Remove the old duplicate method - now using _generate_provider_report
    
    def install_forensic_app(self, apk_path=None):
        """Install the forensic data collector app on the connected device"""
        
        # Force write debug info to file for Flask debugging
        import datetime
        debug_file = "/tmp/apk_debug.log"
        with open(debug_file, "a") as f:
            f.write(f"\n=== APK Installation Debug {datetime.datetime.now()} ===\n")
            f.write(f"Current working directory: {os.getcwd()}\n")
            f.write(f"Python executable: {sys.executable}\n")
            f.write(f"ADB command: {self.adb_command}\n")
        
        if apk_path is None:
            apk_path = self._find_resource_file('arsenic_triage.apk')
            if apk_path is None:
                with open(debug_file, "a") as f:
                    f.write("❌ APK path resolution failed\n")
                return False
            
        with open(debug_file, "a") as f:
            f.write(f"APK path: {apk_path}\n")
            f.write(f"APK exists: {os.path.exists(apk_path)}\n")
            
        if not os.path.exists(apk_path):
            print(f"❌ APK not found: {apk_path}")
            print("Please build the Android app first using Android Studio")
            with open(debug_file, "a") as f:
                f.write(f"❌ APK not found: {apk_path}\n")
            return False
            
        try:
            print(f"📱 Installing forensic app: {apk_path}")
            print(f"🔍 APK file size: {os.path.getsize(apk_path)} bytes")
            print(f"🔍 ADB command: {self.adb_command}")
            
            with open(debug_file, "a") as f:
                f.write(f"📱 Installing forensic app: {apk_path}\n")
                f.write(f"🔍 APK file size: {os.path.getsize(apk_path)} bytes\n")
                f.write(f"🔍 ADB command: {self.adb_command}\n")
            
            # First verify ADB connection
            devices_result = self._run_subprocess([self.adb_command, 'devices'], timeout=10)
            if devices_result.returncode != 0:
                print(f"❌ ADB devices check failed: {devices_result.stderr}")
                with open(debug_file, "a") as f:
                    f.write(f"❌ ADB devices check failed: {devices_result.stderr}\n")
                return False
            
            print(f"🔍 ADB devices output: {devices_result.stdout}")
            with open(debug_file, "a") as f:
                f.write(f"🔍 ADB devices output: {devices_result.stdout}\n")
            
            # Check if any devices are connected
            devices_lines = devices_result.stdout.strip().split('\n')[1:]  # Skip header
            connected_devices = [line for line in devices_lines if line.strip() and 'device' in line]
            
            # Enhanced device status checking
            print(f"🔍 Raw device lines: {devices_lines}")
            print(f"🔍 Connected devices: {connected_devices}")
            with open(debug_file, "a") as f:
                f.write(f"🔍 Raw device lines: {devices_lines}\n")
                f.write(f"🔍 Connected devices: {connected_devices}\n")
            
            if not connected_devices:
                print("❌ No Android devices connected")
                print("Please connect an Android device and enable USB debugging")
                with open(debug_file, "a") as f:
                    f.write("❌ No Android devices connected\n")
                return False
            
            # Check for unauthorized devices
            unauthorized_devices = [line for line in devices_lines if line.strip() and 'unauthorized' in line]
            if unauthorized_devices:
                print(f"⚠️ Found {len(unauthorized_devices)} unauthorized device(s)")
                print("Please authorize USB debugging on your device")
                with open(debug_file, "a") as f:
                    f.write(f"⚠️ Found {len(unauthorized_devices)} unauthorized device(s)\n")
                return False
            
            print(f"✅ Found {len(connected_devices)} connected device(s)")
            with open(debug_file, "a") as f:
                f.write(f"✅ Found {len(connected_devices)} connected device(s)\n")
            
            # Now attempt APK installation
            result = self._run_subprocess([self.adb_command, 'install', '-r', apk_path], timeout=60)
            
            print(f"🔍 ADB install return code: {result.returncode}")
            print(f"🔍 ADB install stdout: {result.stdout}")
            print(f"🔍 ADB install stderr: {result.stderr}")
            
            with open(debug_file, "a") as f:
                f.write(f"🔍 ADB install return code: {result.returncode}\n")
                f.write(f"🔍 ADB install stdout: {result.stdout}\n")
                f.write(f"🔍 ADB install stderr: {result.stderr}\n")
            
            if result.returncode == 0:
                print("✅ Forensic app installed successfully")
                with open(debug_file, "a") as f:
                    f.write("✅ Forensic app installed successfully\n")
                return True
            else:
                # Enhanced error analysis
                error_msg = result.stderr.lower() if result.stderr else ""
                output_msg = result.stdout.lower() if result.stdout else ""
                
                if "install_failed_already_exists" in error_msg or "install_failed_already_exists" in output_msg:
                    print("ℹ️ App already installed, attempting to reinstall...")
                    with open(debug_file, "a") as f:
                        f.write("ℹ️ App already installed, attempting to reinstall...\n")
                    
                    # Try uninstalling first, then reinstalling
                    uninstall_result = self._run_subprocess([self.adb_command, 'uninstall', 'com.arsenictriage.datacollector'], timeout=30)
                    if uninstall_result.returncode == 0:
                        print("✅ Previous installation removed")
                        # Retry installation
                        retry_result = self._run_subprocess([self.adb_command, 'install', '-r', apk_path], timeout=60)
                        if retry_result.returncode == 0:
                            print("✅ Forensic app installed successfully (after retry)")
                            with open(debug_file, "a") as f:
                                f.write("✅ Forensic app installed successfully (after retry)\n")
                            return True
                
                elif "install_failed_insufficient_storage" in error_msg or "install_failed_insufficient_storage" in output_msg:
                    print("❌ Installation failed: Insufficient storage on device")
                    with open(debug_file, "a") as f:
                        f.write("❌ Installation failed: Insufficient storage on device\n")
                
                elif "install_failed_user_restricted" in error_msg or "install_failed_user_restricted" in output_msg:
                    print("❌ Installation failed: Unknown sources not enabled")
                    print("Please enable 'Install unknown apps' in device settings")
                    with open(debug_file, "a") as f:
                        f.write("❌ Installation failed: Unknown sources not enabled\n")
                
                print(f"❌ App installation failed with return code {result.returncode}")
                print(f"❌ Error details: {result.stderr}")
                print(f"❌ Output details: {result.stdout}")
                with open(debug_file, "a") as f:
                    f.write(f"❌ App installation failed with return code {result.returncode}\n")
                    f.write(f"❌ Error details: {result.stderr}\n")
                    f.write(f"❌ Output details: {result.stdout}\n")
                return False
                
        except subprocess.TimeoutExpired:
            print("❌ App installation timed out")
            with open(debug_file, "a") as f:
                f.write("❌ App installation timed out\n")
            return False
        except Exception as e:
            print(f"❌ Error installing app: {e}")
            import traceback
            traceback.print_exc()
            with open(debug_file, "a") as f:
                f.write(f"❌ Error installing app: {e}\n")
                f.write(f"❌ Traceback: {traceback.format_exc()}\n")
            return False
    
    def launch_forensic_app(self):
        """Launch the forensic data collector app on the device"""
        try:
            print("🚀 Launching forensic data collector app...")
            print(f"🔍 App package: {self.app_package}")
            print(f"🔍 App activity: {self.app_activity}")
            
            # Clear logcat to get fresh logs
            print("🔍 Clearing logcat...")
            self._run_subprocess([self.adb_command, 'logcat', '-c'], timeout=5)
            
            # Launch the app
            print("🔍 Launching app with am start command...")
            result = self._run_subprocess([self.adb_command, 'shell', 'am', 'start', '-n', self.app_activity],
                                        timeout=30)
            
            print(f"🔍 Launch return code: {result.returncode}")
            print(f"🔍 Launch stdout: {result.stdout}")
            print(f"🔍 Launch stderr: {result.stderr}")
            
            if result.returncode != 0:
                print(f"❌ Failed to launch app: {result.stderr}")
                return False
            
            print("✅ App launch command sent successfully")
            
            # Wait and check for crashes multiple times
            for check_num in range(1, 4):  # Check 3 times over 6 seconds
                print(f"⏳ Stability check {check_num}/3 (waiting 2 seconds)...")
                time.sleep(2)
                
                # Check if process is running
                app_running = self._check_app_running()
                print(f"🔍 _check_app_running() returned: {app_running}")
                
                if app_running:
                    print(f"✅ Check {check_num}: App is running")
                    if check_num == 3:  # Passed all checks
                        print("🎉 App is stable and running!")
                        print("👤 Please grant permissions and start data collection on the device")
                        return True
                else:
                    print(f"❌ Check {check_num}: App not running")
                    # Get more details about what's running
                    print("🔍 Checking what processes are running...")
                    ps_result = self._run_subprocess([self.adb_command, 'shell', 'ps | grep', self.app_package], timeout=10)
                    print(f"🔍 Process check result: {ps_result.stdout}")
                    break
            
            # If we get here, app crashed or isn't running
            print("💡 Checking for crash details...")
            self._show_recent_crash_logs()
            return False
                
        except Exception as e:
            print(f"❌ Error launching app: {e}")
            return False
    
    def wait_for_app_completion(self, timeout_minutes=10):
        """Wait for the app to complete data collection"""
        print(f"⏳ Waiting for data collection to complete (timeout: {timeout_minutes} minutes)...")
        timeout_seconds = timeout_minutes * 60
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            try:
                # Check both possible locations for completion file
                # First check app-specific directory (Android API 23+)
                result_modern = self._run_subprocess([self.adb_command, 'shell', 'test', '-f', 
                                                    f'{self.device_output_dir_modern}/collection_complete.json'],
                                                   timeout=10)
                
                # Then check legacy directory (older Android versions)
                result_legacy = self._run_subprocess([self.adb_command, 'shell', 'test', '-f', 
                                                    f'{self.device_output_dir_legacy}/collection_complete.json'],
                                                   timeout=10)
                
                if result_modern.returncode == 0:
                    print("✅ Data collection completed on device (app-specific directory)")
                    self.device_output_dir = self.device_output_dir_modern
                    return True
                elif result_legacy.returncode == 0:
                    print("✅ Data collection completed on device (legacy directory)")
                    self.device_output_dir = self.device_output_dir_legacy
                    return True
                    
                # Show progress every 30 seconds
                elapsed = int(time.time() - start_time)
                if elapsed % 30 == 0 and elapsed > 0:
                    print(f"⏳ Still waiting... ({elapsed//60}m {elapsed%60}s elapsed)")
                    
                time.sleep(5)
                
            except subprocess.TimeoutExpired:
                continue
            except KeyboardInterrupt:
                print("\n⚠️ Waiting cancelled by user")
                return False
                
        print(f"⏰ Timeout reached ({timeout_minutes} minutes)")
        return False
    
    def pull_app_data(self):
        """Pull collected data from the device"""
        try:
            print("📥 Pulling collected data from device...")
            
            # Create local output directory
            os.makedirs(self.output_dir, exist_ok=True)
            
            # Determine which directory to pull from
            device_output_dir = getattr(self, 'device_output_dir', None)
            if not device_output_dir:
                # Check both locations if not already determined
                result_modern = self._run_subprocess([self.adb_command, 'shell', 'test', '-d', self.device_output_dir_modern],
                                                   timeout=10)
                result_legacy = self._run_subprocess([self.adb_command, 'shell', 'test', '-d', self.device_output_dir_legacy],
                                                   timeout=10)
                
                if result_modern.returncode == 0:
                    device_output_dir = self.device_output_dir_modern
                    print(f"📱 Using app-specific directory: {device_output_dir}")
                elif result_legacy.returncode == 0:
                    device_output_dir = self.device_output_dir_legacy
                    print(f"📱 Using legacy directory: {device_output_dir}")
                else:
                    print("❌ No data directory found on device")
                    return False
            
            # Pull the entire directory
            local_data_dir = f'{self.output_dir}/apk_data_directory'
            print(f"🔄 Executing ADB pull command:")
            print(f"   Source: {device_output_dir}")
            print(f"   Target: {local_data_dir}")
            print(f"   Command: {self.adb_command} pull {device_output_dir} {local_data_dir}")
            
            result = self._run_subprocess([self.adb_command, 'pull', device_output_dir, local_data_dir], timeout=120)
            
            print(f"🔍 Pull command result:")
            print(f"   Return code: {result.returncode}")
            print(f"   Stdout: {result.stdout}")
            print(f"   Stderr: {result.stderr}")
            
            if result.returncode == 0:
                print("✅ Data pulled successfully")
                self._process_pulled_data()
                return True
            else:
                print(f"❌ Failed to pull data: {result.stderr}")
                print("🔄 Attempting alternative pull method...")
                
                # Try pulling individual files if directory pull fails
                try:
                    # List files in the device directory
                    list_result = self._run_subprocess([self.adb_command, 'shell', 'ls', device_output_dir], timeout=30)
                    if list_result.returncode == 0 and list_result.stdout.strip():
                        files = list_result.stdout.strip().split('\n')
                        os.makedirs(local_data_dir, exist_ok=True)
                        
                        success_count = 0
                        for file in files:
                            if file.strip():
                                file_result = self._run_subprocess([
                                    self.adb_command, 'pull', 
                                    f'{device_output_dir}/{file}', 
                                    f'{local_data_dir}/{file}'
                                ], timeout=60)
                                if file_result.returncode == 0:
                                    success_count += 1
                                    print(f"✅ Pulled {file}")
                                else:
                                    print(f"⚠️ Failed to pull {file}")
                        
                        if success_count > 0:
                            print(f"✅ Successfully pulled {success_count} files using alternative method")
                            self._process_pulled_data()
                            return True
                    
                    print("❌ Alternative pull method also failed")
                    return False
                    
                except Exception as e:
                    print(f"❌ Error in alternative pull method: {e}")
                    return False
                
        except Exception as e:
            print(f"❌ Error pulling data: {e}")
            return False
    
    def _process_pulled_data(self):
        """Process and organize the pulled data"""
        app_data_dir = f"{self.output_dir}/apk_data_directory"
        if not os.path.exists(app_data_dir):
            return
            
        print("📊 Processing collected data...")
        
        # List collected files
        for root, dirs, files in os.walk(app_data_dir):
            for file in files:
                file_path = os.path.join(root, file)
                file_size = os.path.getsize(file_path)
                rel_path = os.path.relpath(file_path, app_data_dir)
                print(f"  📄 {rel_path} ({file_size} bytes)")
                
                # If it's a JSON file, validate and show summary
                if file.endswith('.json'):
                    try:
                        with open(file_path, 'r') as f:
                            data = json.load(f)
                            if isinstance(data, list):
                                print(f"     → {len(data)} records")
                            elif isinstance(data, dict) and 'data' in data:
                                print(f"     → {len(data['data'])} records")
                    except:
                        pass
    
    def collect_with_app(self, install_app=True, timeout_minutes=10):
        """
        Complete workflow: install app, collect data, and pull results
        Use this method when ADB content queries fail due to permissions
        """
        print("🔧 Using Android app method for data collection")
        print("This method bypasses ADB content provider limitations")
        print()
        
        # Check device connectivity
        if not self.check_device():
            return False
        
        # Install app if requested
        if install_app:
            if not self.install_forensic_app():
                return False
        
        # Launch app
        if not self.launch_forensic_app():
            self._get_app_debug_info()
            self._provide_troubleshooting_guidance()
            return False
        
        # Wait for user to complete collection
        if not self.wait_for_app_completion(timeout_minutes):
            print("⚠️ Consider checking the device manually and trying again")
            return False

        print("🎉 APK data collection completed on device!")
        print("📥 Attempting to pull data automatically...")
        
        # Pull collected data
        pull_success = self.pull_app_data()
        
        if pull_success:
            print("✅ Data successfully pulled from device!")
            print(f"📁 Data saved to: {self.output_dir}/apk_data_directory")
        else:
            print("⚠️ Automatic data pull failed (likely due to permissions)")
            print("📋 Data collection completed successfully on device, but manual pull may be needed")
            print(f"🔧 You can manually pull data using:")
            print(f"   adb pull \"{getattr(self, 'device_output_dir', self.device_output_dir_modern)}\" \"{self.output_dir}/apk_data_directory\"")
            
            # Still return True because the APK collection itself succeeded
            # The Flask backend should show success and proceed with APK removal prompt
        
        print()
        print("🎉 Android app data collection completed!")
        if pull_success:
            print(f"📁 Data saved to: {self.output_dir}/apk_data_directory")
        else:
            print("📋 Data is ready on device for manual retrieval")
        print()
        
        return True  # Return True even if pull failed, since collection succeeded
    
    def check_device(self) -> bool:
        """Check if an Android device is connected and accessible via ADB."""
        try:
            result = self._run_subprocess([self.adb_command, 'devices'], timeout=10)
            
            if result.returncode != 0:
                print("❌ ADB command failed. Please ensure ADB is installed and in PATH.")
                print(f"ADB error: {result.stderr}")
                return False
            
            lines = result.stdout.strip().split('\n')[1:]  # Skip header line
            
            # More specific device detection - look for '\tdevice' (authorized devices only)
            authorized_devices = []
            unauthorized_devices = []
            
            for line in lines:
                if line.strip():
                    if '\tdevice' in line:  # Authorized device
                        authorized_devices.append(line.strip())
                    elif '\tunauthorized' in line:  # Unauthorized device
                        unauthorized_devices.append(line.strip())
                    elif '\toffline' in line:  # Offline device
                        print(f"⚠️ Device offline: {line.strip()}")
            
            if unauthorized_devices:
                print("⚠️ Found unauthorized device(s). Please:")
                print("  1. Check your Android device screen")
                print("  2. Accept 'Allow USB debugging' prompt")
                print("  3. Try again")
                for device in unauthorized_devices:
                    print(f"     {device}")
                return False
            
            if not authorized_devices:
                print("❌ No authorized Android devices found.")
                print("Please:")
                print("  1. Connect Android device via USB")
                print("  2. Enable 'Developer Options' and 'USB Debugging'")
                print("  3. Accept debugging authorization on device")
                return False
            
            if len(authorized_devices) > 1:
                print(f"⚠️ Multiple devices found ({len(authorized_devices)})")
                for i, device in enumerate(authorized_devices):
                    print(f"  {i+1}. {device}")
                print("Using first device. Specify device ID if needed.")
            
            device_info = authorized_devices[0].split('\t')[0]
            print(f"✅ Device connected: {device_info}")
            return True
            
        except subprocess.TimeoutExpired:
            print("❌ ADB command timed out")
            return False
        except FileNotFoundError:
            print("❌ ADB not found. Please install Android Platform Tools.")
            return False
        except Exception as e:
            print(f"❌ Error checking device: {e}")
            return False

    def list_content_uris(self):
        """List all available content URIs in a formatted manner."""
        print_commands_list()

    def discover_content_providers(self):
        """Discover and display content providers on the connected device."""
        if not self.check_device():
            return
        
        # Get the raw list of providers
        success, providers = self._discover_content_providers_raw()
        
        if not success:
            print("❌ Failed to discover content providers")
            return
        
        # Generate and display report
        report = self._generate_provider_report(providers)
        print(report)
        
        # Save report to file
        report_file = os.path.join(self.output_dir, "provider_discovery_report.txt")
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n📄 Report saved to: {report_file}")

    def _discover_content_providers_raw(self) -> Tuple[bool, List[str]]:
        """
        Discover all available content providers on the device using dumpsys.
        
        Returns:
            Tuple of (success, list of provider authorities)
        """
        success, output = self.execute_adb_command("shell dumpsys package providers")
        
        if not success:
            return False, []
        
        providers = []
        lines = output.split('\n')
        
        for line in lines:
            line = line.strip()
            # Look for provider authority patterns like [com.provider.authority]:
            if line.startswith('[') and line.endswith(']:'):
                authority = line[1:-2]  # Remove [ and ]:
                if authority and '/' not in authority:  # Filter out specific provider instances
                    providers.append(authority)
        
        # Remove duplicates and sort
        providers = sorted(list(set(providers)))
        logger.info(f"Discovered {len(providers)} content provider authorities")
        
        return True, providers

    def _generate_provider_report(self, providers: List[str]) -> str:
        """
        Generate a comprehensive report of discovered content providers.
        
        Args:
            providers: List of provider authorities
        
        Returns:
            Formatted report string
        """
        report = f"""
CONTENT PROVIDER DISCOVERY REPORT
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Device: {self.device_id if self.device_id else 'Default'}
Total Providers Found: {len(providers)}

{"="*80}
DISCOVERED CONTENT PROVIDER AUTHORITIES
{"="*80}

"""
        
        # Categorize providers
        system_providers = []
        google_providers = []
        samsung_providers = []
        app_providers = []
        
        for provider in providers:
            if provider.startswith('com.android.') or provider.startswith('android'):
                system_providers.append(provider)
            elif provider.startswith('com.google.'):
                google_providers.append(provider)
            elif provider.startswith('com.samsung.') or provider.startswith('com.sec.'):
                samsung_providers.append(provider)
            else:
                app_providers.append(provider)
        
        # Add categorized providers to report
        if system_providers:
            report += f"\n📱 ANDROID SYSTEM PROVIDERS ({len(system_providers)}):\n"
            report += "-" * 50 + "\n"
            for provider in system_providers:
                report += f"  • {provider}\n"
        
        if google_providers:
            report += f"\n🔍 GOOGLE SERVICE PROVIDERS ({len(google_providers)}):\n"
            report += "-" * 50 + "\n"
            for provider in google_providers:
                report += f"  • {provider}\n"
        
        if samsung_providers:
            report += f"\n📲 SAMSUNG/SEC PROVIDERS ({len(samsung_providers)}):\n"
            report += "-" * 50 + "\n"
            for provider in samsung_providers:
                report += f"  • {provider}\n"
        
        if app_providers:
            report += f"\n📱 THIRD-PARTY APP PROVIDERS ({len(app_providers)}):\n"
            report += "-" * 50 + "\n"
            for provider in app_providers:
                report += f"  • {provider}\n"
        
        report += f"\n{'='*80}\n"
        report += "USAGE INSTRUCTIONS:\n"
        report += "To query a provider: adb shell content query --uri content://AUTHORITY\n"
        report += "Example: adb shell content query --uri content://settings/system\n"
        report += f"{'='*80}\n"
        
        return report

    def test_content_provider_access(self, uri: str):
        """Test access to a specific content URI and display results."""
        if not self.check_device():
            return
        
        print(f"🔍 Testing content URI: {uri}")
        print("-" * 50)
        
        success, data = self.query_content_provider(uri)
        
        if success:
            if data.strip():
                print("✅ URI accessible - Sample data:")
                # Show first few lines
                lines = data.split('\n')[:5]
                for line in lines:
                    if line.strip():
                        print(f"  {line}")
                total_lines = len(data.split('\n'))
                if total_lines > 5:
                    print(f"  ... ({total_lines} total lines)")
            else:
                print("⚠️ URI accessible but returned no data")
        else:
            print(f"❌ URI not accessible: {data}")

    def collect_all_data(self):
        """Collect all available data using ADB content provider queries."""
        if not self.check_device():
            return
        
        print("🔍 Starting comprehensive data collection via ADB...")
        print("This may take several minutes depending on data volume.")
        print()
        
        collected_data = {}
        total_commands = sum(len(info['commands']) for info in CONTENT_URI_COMMANDS.values())
        current_command = 0
        
        for category, info in CONTENT_URI_COMMANDS.items():
            print(f"📱 Collecting {category.replace('_', ' ')} data...")
            category_data = []
            
            for cmd in info['commands']:
                current_command += 1
                print(f"  [{current_command}/{total_commands}] {cmd['name']}...")
                
                projection = cmd.get('projection')
                success, data = self.query_content_provider(cmd['uri'], projection)
                
                if success and data.strip():
                    # Parse and store data
                    parsed_data = self._parse_content_output(data)
                    category_data.append({
                        'name': cmd['name'],
                        'uri': cmd['uri'],
                        'description': cmd['description'],
                        'data': parsed_data,
                        'record_count': len(parsed_data) if isinstance(parsed_data, list) else 1
                    })
                    print(f"    ✅ {len(parsed_data) if isinstance(parsed_data, list) else 1} records")
                else:
                    print(f"    ❌ Failed or no data")
            
            if category_data:
                collected_data[category] = category_data
        
        # Save collected data
        self._save_collected_data(collected_data)
        print()
        print("🎉 Data collection completed!")
        print(f"📁 Data saved to: {self.output_dir}")

    def _parse_content_output(self, output: str) -> List[Dict]:
        """Parse ADB content query output into structured data."""
        lines = output.strip().split('\n')
        parsed_data = []
        
        for line in lines:
            if line.startswith('Row:'):
                # Parse content provider row format
                row_data = {}
                parts = line.split(',')
                for part in parts[1:]:  # Skip 'Row: N'
                    if '=' in part:
                        key, value = part.split('=', 1)
                        row_data[key.strip()] = value.strip()
                if row_data:
                    parsed_data.append(row_data)
            elif line.strip() and not line.startswith('Row:'):
                # Handle other formats
                parsed_data.append({'raw_data': line.strip()})
        
        return parsed_data

    def _save_collected_data(self, collected_data: Dict):
        """Save collected data in multiple formats."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save as JSON
        json_file = os.path.join(self.output_dir, f"forensic_data_{timestamp}.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(collected_data, f, indent=2, ensure_ascii=False)
        
        # Create summary report
        summary = {
            'collection_timestamp': timestamp,
            'device_id': self.device_id,
            'categories_collected': len(collected_data),
            'total_records': sum(
                sum(item['record_count'] for item in category_data)
                for category_data in collected_data.values()
            ),
            'category_summary': {
                category: {
                    'commands_executed': len(category_data),
                    'total_records': sum(item['record_count'] for item in category_data)
                }
                for category, category_data in collected_data.items()
            }
        }
        
        summary_file = os.path.join(self.output_dir, f"collection_summary_{timestamp}.json")
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
        
        print(f"📄 Data saved: {json_file}")
        print(f"📊 Summary: {summary_file}")

    def _check_app_running(self) -> bool:
        """Check if the forensic app is currently running on the device."""
        try:
            # Method 1: Check running processes
            result = self._run_subprocess([self.adb_command, 'shell', 'ps', 'aux'], 
                                        timeout=10)
            
            if result.returncode == 0 and self.app_package in result.stdout:
                print(f"✅ Process found: {self.app_package}")
                return True
            
            # Method 2: Check via pidof
            result = self._run_subprocess([self.adb_command, 'shell', 'pidof', self.app_package],
                                        timeout=10)
            
            if result.returncode == 0 and result.stdout.strip():
                print(f"✅ PID found: {result.stdout.strip()}")
                return True
            
            # Method 3: Check recent activities
            result = self._run_subprocess([self.adb_command, 'shell', 'dumpsys', 'activity', 'recents'],
                                        timeout=10)
            
            if result.returncode == 0 and self.app_package in result.stdout:
                print(f"⚠️ App in recent activities but may not be active")
                # Check if it's actually running or just in history
                lines = result.stdout.split('\n')
                for line in lines:
                    if self.app_package in line and 'running' in line.lower():
                        return True
            
            print(f"❌ App {self.app_package} not found in running processes")
            return False
            
        except Exception as e:
            logger.error(f"Error checking app status: {e}")
            print(f"⚠️ Error checking app status: {e}")
            return False
    
    def _show_recent_crash_logs(self):
        """Show recent crash logs related to our app."""
        try:
            print("📋 Checking for recent crashes...")
            
            # Get recent logcat entries focusing on errors
            result = self._run_subprocess([self.adb_command, 'logcat', '-d', '-v', 'time', '*:E'], 
                                        timeout=10)
            
            if result.returncode == 0 and result.stdout:
                lines = result.stdout.split('\n')
                crash_lines = []
                
                # Look for our app or generic crash indicators
                for line in lines:
                    if (self.app_package in line or 
                        'FATAL EXCEPTION' in line or
                        'AndroidRuntime' in line or
                        'MainActivity' in line or
                        'Theme.AppCompat' in line):
                        crash_lines.append(line)
                
                if crash_lines:
                    print("💥 Found crash-related logs:")
                    for line in crash_lines[-10:]:  # Show last 10 relevant lines
                        print(f"   {line}")
                else:
                    print("ℹ️ No obvious crashes found in recent logs")
            
            # Also check if the app is simply not starting
            result = self._run_subprocess([self.adb_command, 'shell', 'am', 'start', '-W', '-n', self.app_activity],
                                        timeout=15)
            
            if result.returncode == 0:
                print("📊 App start attempt result:")
                print(f"   {result.stdout}")
            
        except Exception as e:
            print(f"⚠️ Error retrieving crash logs: {e}")
    
    def _monitor_app_launch_realtime(self) -> bool:
        """Monitor app launch in real-time to catch immediate crashes."""
        try:
            print("� Starting real-time crash monitoring...")
            
            # Start logcat monitoring in background
            import threading
            import queue
            
            crash_queue = queue.Queue()
            
            def logcat_monitor():
                try:
                    # Monitor logcat for crashes in real-time
                    process = self._run_subprocess_popen([self.adb_command, 'logcat', '-v', 'time', '*:E'], bufsize=1)
                    
                    start_time = time.time()
                    while time.time() - start_time < 10:  # Monitor for 10 seconds
                        line = process.stdout.readline()
                        if line:
                            if (self.app_package in line or 
                                'FATAL EXCEPTION' in line or
                                'AndroidRuntime' in line):
                                crash_queue.put(f"CRASH: {line.strip()}")
                        time.sleep(0.1)
                    
                    process.terminate()
                except Exception as e:
                    crash_queue.put(f"ERROR: {e}")
            
            # Start monitoring thread
            monitor_thread = threading.Thread(target=logcat_monitor)
            monitor_thread.daemon = True
            monitor_thread.start()
            
            # Launch the app
            result = self._run_subprocess([self.adb_command, 'shell', 'am', 'start', '-n', self.app_activity],
                                        timeout=30)
            
            if result.returncode != 0:
                print(f"❌ Failed to launch app: {result.stderr}")
                return False
            
            print("✅ App launch command sent, monitoring for crashes...")
            
            # Check for crashes in the queue
            time.sleep(2)  # Give app time to start
            
            crashes_detected = []
            try:
                while True:
                    crash_line = crash_queue.get_nowait()
                    crashes_detected.append(crash_line)
            except queue.Empty:
                pass
            
            if crashes_detected:
                print("💥 Real-time crash detected:")
                for crash in crashes_detected:
                    print(f"   {crash}")
                return False
            
            # Wait a bit more and check if process is running
            time.sleep(3)
            
            if self._check_app_running():
                print("✅ App appears to be running successfully")
                return True
            else:
                print("❌ App not found in running processes")
                return False
                
        except Exception as e:
            print(f"❌ Error in real-time monitoring: {e}")
            return False
    
    def _provide_troubleshooting_guidance(self):
        """Provide troubleshooting guidance when the app fails."""
        print("\n🔧 TROUBLESHOOTING GUIDANCE:")
        print("=" * 50)
        print("1. 📱 Check device compatibility:")
        print("   - Android 6.0+ required")
        print("   - USB debugging enabled")
        print("   - Developer options unlocked")
        print()
        print("2. 🔐 Permission issues:")
        print("   - App may need permissions granted manually")
        print("   - Some data requires system-level access")
        print("   - Try running on rooted device if available")
        print()
        print("3. 🏗️  Build issues:")
        print("   - Ensure latest APK was built successfully")
        print("   - Check Android SDK compatibility")
        print("   - Verify theme configuration")
        print()
        print("4. 🔄 Alternative methods:")
        print("   - Use ADB method: python3 android_forensic_collector.py --collect")
        print("   - Try older Android version if available")
        print("   - Check device-specific restrictions")
        print("=" * 50)

    def _get_app_debug_info(self):
        """Get detailed debug information about the app installation and state."""
        try:
            print("\n🔍 APP DEBUG INFORMATION:")
            print("=" * 40)
            
            # Check if app is installed
            result = self._run_subprocess([self.adb_command, 'shell', 'pm', 'list', 'packages', self.app_package],
                                        timeout=10)
            
            if result.returncode == 0 and result.stdout.strip():
                print(f"✅ App installed: {result.stdout.strip()}")
            else:
                print("❌ App not found in installed packages")
                return
            
            # Get app info
            result = self._run_subprocess([self.adb_command, 'shell', 'dumpsys', 'package', self.app_package],
                                        timeout=15)
            
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for line in lines[:20]:  # Show first 20 lines
                    if any(keyword in line.lower() for keyword in ['version', 'target', 'min', 'install', 'enabled']):
                        print(f"   {line.strip()}")
            
            # Check permissions
            result = self._run_subprocess([self.adb_command, 'shell', 'dumpsys', 'package', self.app_package, '|', 'grep', '-A20', 'declared permissions'],
                                        timeout=10)
            
            if result.returncode == 0 and result.stdout.strip():
                print("📋 App permissions:")
                lines = result.stdout.split('\n')[:10]  # Show first 10 permission lines
                for line in lines:
                    if line.strip():
                        print(f"   {line.strip()}")
            
            print("=" * 40)
            
        except Exception as e:
            print(f"⚠️ Error getting app debug info: {e}")
    
    def create_adb_backup(self, include_apks=True, include_system=False, include_shared=True):
        """
        Create a comprehensive ADB backup of the device.
        
        Args:
            include_apks: Include APK files in backup
            include_system: Include system apps (requires more storage)
            include_shared: Include shared storage/SD card data
            
        Returns:
            bool: Success status
        """
        # Add debug logging for ADB backup
        debug_file = "/tmp/adb_backup_debug.log"
        with open(debug_file, "a") as f:
            f.write(f"\n=== ADB Backup Debug {datetime.now()} ===\n")
            f.write(f"ADB command: {self.adb_command}\n")
            f.write(f"Output directory: {self.output_dir}\n")
            f.write(f"Include APKs: {include_apks}\n")
            f.write(f"Include System: {include_system}\n")
            f.write(f"Include Shared: {include_shared}\n")
        
        if not self.check_device():
            with open(debug_file, "a") as f:
                f.write(f"❌ Device check failed\n")
            return False
        
        print("📦 Creating comprehensive ADB backup...")
        print("This may take 10-30 minutes depending on device data volume.")
        print("⚠️  Please approve the backup on your device when prompted!")
        print()
        
        # Create backup filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"android_backup_{timestamp}.ab"
        backup_path = os.path.join(self.output_dir, backup_filename)
        
        # Build ADB backup command
        backup_options = []
        
        if include_apks:
            backup_options.append("-apk")
        else:
            backup_options.append("-noapk")
            
        if include_system:
            backup_options.append("-system")
        else:
            backup_options.append("-nosystem")
            
        if include_shared:
            backup_options.append("-shared")
        else:
            backup_options.append("-noshared")
        
        # Add all user apps
        backup_options.append("-all")
        
        print(f"💾 Backup will be saved to: {backup_path}")
        print(f"🔧 ADB command: {self.adb_command}")
        print(f"🔧 Backup options: {' '.join(backup_options)}")
        print()
        print("📱 PLEASE APPROVE THE BACKUP ON YOUR DEVICE!")
        print("   - Look for a backup confirmation dialog")
        print("   - You may need to set a backup password (optional)")
        print("   - Tap 'Back up my data' to proceed")
        print()
        
        try:
            # Log the exact command being executed FIRST
            debug_file = "/tmp/adb_backup_debug.log"
            with open(debug_file, "a") as f:
                f.write(f"=== ENTERING ADB BACKUP TRY BLOCK ===\n")
                f.write(f"ADB command: {self.adb_command}\n")
                f.write(f"Device ID: {self.device_id}\n")
                f.write(f"Backup path: {backup_path}\n")
                f.write(f"Backup options: {backup_options}\n")
            
            # Execute backup command with extended timeout (backup can take 10-30 minutes)
            print("⏳ Starting backup process (this may take 10-30 minutes)...")
            print("💡 You can monitor progress by checking the backup file size")
            
            # Use a longer timeout for backup operations and execute with live monitoring
            device_arg = f"-s {self.device_id}" if self.device_id else ""
            
            # Build command as proper list to handle paths with spaces
            full_command = [self.adb_command]
            if device_arg:
                full_command.extend(["-s", self.device_id])
            full_command.extend(["backup"] + backup_options + ["-f", backup_path])
            
            import subprocess
            import threading
            import time
            
            # Log the exact command being executed
            with open(debug_file, "a") as f:
                f.write(f"Full command as list: {full_command}\n")
                f.write(f"Command type: {type(full_command)}\n")
                f.write(f"Command length: {len(full_command)}\n")
                for i, part in enumerate(full_command):
                    f.write(f"  [{i}]: '{part}' (type: {type(part)})\n")
            
            # Start backup process
            process = self._run_subprocess_popen(full_command)
            
            # Monitor backup progress in separate thread
            def monitor_backup():
                while process.poll() is None:
                    time.sleep(30)  # Check every 30 seconds
                    if os.path.exists(backup_path):
                        current_size = os.path.getsize(backup_path)
                        if current_size > 0:
                            print(f"📊 Backup in progress... Current size: {self._format_file_size(current_size)}")
                    else:
                        print("⏳ Waiting for backup to start...")
            
            # Start monitoring thread
            monitor_thread = threading.Thread(target=monitor_backup, daemon=True)
            monitor_thread.start()
            
            # Wait for backup to complete (30 minute timeout)
            try:
                stdout, stderr = process.communicate(timeout=1800)  # 30 minutes
                success = process.returncode == 0
                output = stderr if stderr else stdout
            except subprocess.TimeoutExpired:
                process.kill()
                print("❌ Backup timed out after 30 minutes")
                return False
            
            if success:
                # Check if backup file was created and has reasonable size
                if os.path.exists(backup_path):
                    backup_size = os.path.getsize(backup_path)
                    if backup_size > 1024:  # At least 1KB
                        print(f"✅ ADB backup completed successfully!")
                        print(f"📊 Backup size: {self._format_file_size(backup_size)}")
                        print(f"📁 Backup saved to: {backup_path}")
                        
                        # Create backup metadata
                        self._create_backup_metadata(backup_path, include_apks, include_system, include_shared)
                        return True
                    else:
                        print(f"⚠️  Backup file created but appears to be empty ({backup_size} bytes)")
                        print("This usually means the backup was cancelled or failed")
                        return False
                else:
                    print("❌ Backup file was not created")
                    print("This usually means the backup was cancelled by the user")
                    return False
            else:
                print(f"❌ ADB backup command failed: {output}")
                debug_file = "/tmp/adb_backup_debug.log"
                with open(debug_file, "a") as f:
                    f.write(f"❌ ADB backup command failed\n")
                    f.write(f"Return code: {process.returncode}\n")
                    f.write(f"Stdout: {stdout}\n")
                    f.write(f"Stderr: {stderr}\n")
                    f.write(f"Output: {output}\n")
                return False
                
        except Exception as e:
            print(f"❌ Error during backup creation: {e}")
            debug_file = "/tmp/adb_backup_debug.log"
            with open(debug_file, "a") as f:
                f.write(f"❌ Exception during backup creation: {e}\n")
                import traceback
                f.write(f"Traceback: {traceback.format_exc()}\n")
            return False
    
    def _create_backup_metadata(self, backup_path, include_apks, include_system, include_shared):
        """Create metadata file for the ADB backup."""
        try:
            metadata = {
                'backup_timestamp': datetime.now().isoformat(),
                'backup_file': os.path.basename(backup_path),
                'backup_size_bytes': os.path.getsize(backup_path),
                'backup_size_formatted': self._format_file_size(os.path.getsize(backup_path)),
                'backup_options': {
                    'include_apks': include_apks,
                    'include_system': include_system,
                    'include_shared': include_shared,
                    'include_all_apps': True
                },
                'device_info': self._get_device_info_for_backup()
            }
            
            metadata_path = backup_path.replace('.ab', '_metadata.json')
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            print(f"📋 Backup metadata saved to: {metadata_path}")
            
        except Exception as e:
            print(f"⚠️  Warning: Could not create backup metadata: {e}")
    
    def _get_device_info_for_backup(self):
        """Get basic device information for backup metadata."""
        device_info = {}
        
        try:
            # Get device properties
            properties = [
                ('ro.product.model', 'model'),
                ('ro.product.manufacturer', 'manufacturer'),
                ('ro.build.version.release', 'android_version'),
                ('ro.build.version.sdk', 'api_level'),
                ('ro.serialno', 'serial_number'),
                ('ro.build.fingerprint', 'build_fingerprint')
            ]
            
            for prop, key in properties:
                success, value = self.execute_adb_command(f"shell getprop {prop}")
                if success and value.strip():
                    device_info[key] = value.strip()
            
        except Exception as e:
            print(f"⚠️  Warning: Could not gather device info: {e}")
            
        return device_info
    
    def _format_file_size(self, size_bytes):
        """Format file size in human-readable format."""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        import math
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_names[i]}"
    
    def extract_adb_backup(self, backup_file_path, extract_dir=None, password=None):
        """
        Extract an ADB backup file for analysis.
        
        Args:
            backup_file_path: Path to the .ab backup file
            extract_dir: Directory to extract to (optional)
            password: Backup password if the backup is encrypted (optional)
            
        Returns:
            bool: Success status
        """
        if not os.path.exists(backup_file_path):
            print(f"❌ Backup file not found: {backup_file_path}")
            return False
        
        if extract_dir is None:
            backup_name = os.path.splitext(os.path.basename(backup_file_path))[0]
            extract_dir = os.path.join(self.output_dir, f"{backup_name}_extracted")
        
        print(f"📂 Extracting ADB backup...")
        print(f"📁 Source: {backup_file_path}")
        print(f"📁 Destination: {extract_dir}")
        if password:
            print(f"🔐 Using password-protected extraction")
        
        try:
            # Create extraction directory
            os.makedirs(extract_dir, exist_ok=True)
            
            # Try to extract using abe.jar (preferred method with password support)
            extraction_success = False
            abe_jar = self.get_abe_jar_path()
            
            if abe_jar and os.path.exists(abe_jar):
                print(f"🔧 Using abe.jar for extraction: {abe_jar}")
                try:
                    from src.parser.AB_parser import BackupExtractor
                    extractor = BackupExtractor(backup_file_path, abe_jar, extract_dir, password=password)
                    if extractor.extract():
                        print("✅ Extraction completed using abe.jar")
                        extraction_success = True
                    else:
                        print("❌ abe.jar extraction failed")
                except Exception as e:
                    print(f"❌ Error using abe.jar: {e}")
            else:
                print("⚠️  abe.jar not found, trying alternative methods...")
            
            # Method 2: Try using Android Backup Extractor (if available) - fallback without password support
            if not extraction_success:
                try:
                    import subprocess
                    result = self._run_subprocess([
                        'java', '-jar', 'android-backup-extractor.jar',
                        backup_file_path, extract_dir
                    ], timeout=300)
                    
                    if result.returncode == 0:
                        print("✅ Extraction completed using Android Backup Extractor")
                        extraction_success = True
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    pass
            
            # Method 3: Check backup format and provide guidance
            if not extraction_success:
                try:
                    # Check if backup is compressed/encrypted
                    with open(backup_file_path, 'rb') as f:
                        header = f.read(24)
                        if header.startswith(b'ANDROID BACKUP'):
                            print("📋 Detected Android backup format")
                            if password:
                                print("⚠️  Extraction failed despite password - backup may use different encryption")
                                print(f"💡 Try manual extraction with different tools:")
                                print(f"   java -jar abe.jar unpack {backup_file_path} {extract_dir} {password}")
                            else:
                                print("⚠️  Manual extraction required - backup may be encrypted")
                                print(f"💡 Try using abe.jar with password support:")
                                print(f"   java -jar abe.jar unpack {backup_file_path} {extract_dir} <password>")
                            return True
                        
                except Exception as e:
                    print(f"⚠️  Could not analyze backup format: {e}")
            
            if not extraction_success:
                print("⚠️  Automatic extraction not available")
                print("📋 Backup file created successfully but extraction requires additional tools")
                print("💡 Recommended extraction tools:")
                print("   - abe.jar (with password support): java -jar abe.jar unpack <backup.ab> <output.tar> [password]")
                print("   - Android Backup Extractor: https://github.com/nelenkov/android-backup-extractor")
                print("   - ABE (Android Backup Extractor): https://github.com/nelenkov/android-backup-extractor")
                print("   - Manual extraction with dd/openssl for unencrypted backups")
                return True
            
            return extraction_success
            
        except Exception as e:
            print(f"❌ Error during backup extraction: {e}")
            return False
    
    def collect_with_backup(self, include_apks=True, include_system=False, include_shared=True):
        """
        Create a comprehensive ADB backup as part of forensic collection.
        
        Args:
            include_apks: Include APK files in backup
            include_system: Include system apps
            include_shared: Include shared storage data
            
        Returns:
            bool: Success status
        """
        print("🔧 Using ADB backup method for comprehensive data collection")
        print("This method creates a complete device backup including app data")
        print()
        
        # Check device connectivity
        if not self.check_device():
            return False
        
        # Create the backup
        success = self.create_adb_backup(include_apks, include_system, include_shared)
        
        if success:
            print()
            print("🎉 ADB backup collection completed successfully!")
            print(f"📁 Data saved to: {self.output_dir}")
            print()
            print("📋 Backup Analysis Options:")
            print("1. Use Android Backup Extractor for detailed analysis")
            print("2. Manual extraction for specific app data")
            print("3. Forensic tools that support .ab format")
            print()
        
        return success
# Content URI commands organized by data type
CONTENT_URI_COMMANDS = {
    "contacts": {
        "description": "Contact-related data from the contacts database",
        "commands": [
            {
                "name": "All Contacts",
                "uri": "content://contacts/people",
                "description": "Retrieve all contacts from the device"
            },
            {
                "name": "Contact Details",
                "uri": "content://com.android.contacts/contacts",
                "description": "Detailed contact information"
            },
            {
                "name": "Phone Numbers",
                "uri": "content://com.android.contacts/data/phones",
                "description": "All phone numbers stored in contacts"
            },
            {
                "name": "Email Addresses",
                "uri": "content://com.android.contacts/data/emails",
                "description": "All email addresses from contacts"
            },
            {
                "name": "Contact Raw Data",
                "uri": "content://com.android.contacts/raw_contacts",
                "description": "Raw contact data including sync information"
            },
            {
                "name": "Contact Display Names",
                "uri": "content://com.android.contacts/contacts",
                "projection": "display_name,lookup_key,photo_uri",
                "description": "Contact names and photo information"
            }
        ]
    },
    "sms_mms": {
        "description": "SMS and MMS message data",
        "commands": [
            {
                "name": "All SMS Messages",
                "uri": "content://sms",
                "description": "All SMS messages (sent, received, draft)"
            },
            {
                "name": "Inbox SMS",
                "uri": "content://sms/inbox",
                "description": "Received SMS messages"
            },
            {
                "name": "Sent SMS",
                "uri": "content://sms/sent",
                "description": "Sent SMS messages"
            },
            {
                "name": "Draft SMS",
                "uri": "content://sms/draft",
                "description": "Draft SMS messages"
            },
            {
                "name": "Failed SMS",
                "uri": "content://sms/failed",
                "description": "Failed SMS messages"
            },
            {
                "name": "Outbox SMS",
                "uri": "content://sms/outbox",
                "description": "SMS messages in outbox"
            },
            {
                "name": "All MMS Messages",
                "uri": "content://mms",
                "description": "All MMS messages"
            },
            {
                "name": "MMS Inbox",
                "uri": "content://mms/inbox",
                "description": "Received MMS messages"
            },
            {
                "name": "MMS Sent",
                "uri": "content://mms/sent",
                "description": "Sent MMS messages"
            },
            {
                "name": "MMS Parts",
                "uri": "content://mms/part",
                "description": "MMS message parts (attachments, text)"
            },
            {
                "name": "Conversation Threads",
                "uri": "content://mms-sms/conversations",
                "description": "SMS/MMS conversation threads"
            }
        ]
    },
    "call_logs": {
        "description": "Call history and call log information",
        "commands": [
            {
                "name": "Call Log",
                "uri": "content://call_log/calls",
                "description": "Complete call history including incoming, outgoing, missed calls"
            },
            {
                "name": "Call Log with Details",
                "uri": "content://call_log/calls",
                "projection": "number,date,duration,type,name",
                "description": "Call log with specific details"
            }
        ]
    },
    "calendar": {
        "description": "Calendar events and calendar data",
        "commands": [
            {
                "name": "Calendar Events",
                "uri": "content://com.android.calendar/events",
                "description": "All calendar events"
            },
            {
                "name": "Calendar Instances",
                "uri": "content://com.android.calendar/instances/when",
                "description": "Calendar event instances"
            },
            {
                "name": "Calendars",
                "uri": "content://com.android.calendar/calendars",
                "description": "Calendar accounts and settings"
            },
            {
                "name": "Event Attendees",
                "uri": "content://com.android.calendar/attendees",
                "description": "Event attendee information"
            },
            {
                "name": "Event Reminders",
                "uri": "content://com.android.calendar/reminders",
                "description": "Calendar event reminders"
            }
        ]
    },
    "browser": {
        "description": "Browser history, bookmarks, and browser data",
        "commands": [
            {
                "name": "Browser History",
                "uri": "content://browser/bookmarks",
                "description": "Browser history and bookmarks (legacy)"
            },
            {
                "name": "Chrome Bookmarks",
                "uri": "content://com.android.chrome.browser/bookmarks",
                "description": "Chrome browser bookmarks"
            },
            {
                "name": "Chrome History",
                "uri": "content://com.android.chrome.browser/history",
                "description": "Chrome browser history"
            }
        ]
    },
    "media": {
        "description": "Media files and media store information",
        "commands": [
            {
                "name": "External Images",
                "uri": "content://media/external/images/media",
                "description": "All images on external storage"
            },
            {
                "name": "External Videos",
                "uri": "content://media/external/video/media",
                "description": "All videos on external storage"
            },
            {
                "name": "External Audio",
                "uri": "content://media/external/audio/media",
                "description": "All audio files on external storage"
            },
            {
                "name": "Internal Images",
                "uri": "content://media/internal/images/media",
                "description": "Images on internal storage"
            },
            {
                "name": "Internal Videos",
                "uri": "content://media/internal/video/media",
                "description": "Videos on internal storage"
            },
            {
                "name": "Internal Audio",
                "uri": "content://media/internal/audio/media",
                "description": "Audio files on internal storage"
            },
            {
                "name": "Image Thumbnails",
                "uri": "content://media/external/images/thumbnails",
                "description": "Image thumbnails"
            },
            {
                "name": "Video Thumbnails",
                "uri": "content://media/external/video/thumbnails",
                "description": "Video thumbnails"
            }
        ]
    },
    "applications": {
        "description": "Application and package information",
        "commands": [
            {
                "name": "Installed Packages",
                "uri": "content://com.android.providers.applications/applications",
                "description": "Information about installed applications"
            }
        ]
    },
    "system": {
        "description": "System settings and configuration",
        "commands": [
            {
                "name": "System Settings",
                "uri": "content://settings/system",
                "description": "System-level settings"
            },
            {
                "name": "Secure Settings",
                "uri": "content://settings/secure",
                "description": "Secure system settings"
            },
            {
                "name": "Global Settings",
                "uri": "content://settings/global",
                "description": "Global system settings"
            }
        ]
    },
    "downloads": {
        "description": "Download manager information",
        "commands": [
            {
                "name": "Downloads",
                "uri": "content://downloads/my_downloads",
                "description": "Download manager entries"
            },
            {
                "name": "All Downloads",
                "uri": "content://downloads/all_downloads",
                "description": "All download entries including completed and failed"
            }
        ]
    },
    "dictionary": {
        "description": "User dictionary and autocomplete data",
        "commands": [
            {
                "name": "User Dictionary",
                "uri": "content://user_dictionary/words",
                "description": "Custom words added to user dictionary"
            }
        ]
    },
    "wifi": {
        "description": "WiFi configuration and connection data",
        "commands": [
            {
                "name": "WiFi Networks",
                "uri": "content://com.android.providers.settings/favorites?notify=true",
                "description": "WiFi network configurations (may require root)"
            }
        ]
    }
}


def print_commands_list():
    """Print a formatted list of all available ADB content URI commands."""
    print("\n" + "="*80)
    print("ANDROID FORENSIC DATA COLLECTION - ADB CONTENT URI COMMANDS")
    print("="*80)
    
    for category, info in CONTENT_URI_COMMANDS.items():
        print(f"\n{category.upper().replace('_', ' ')}")
        print("-" * 50)
        print(f"Description: {info['description']}")
        print()
        
        for i, cmd in enumerate(info['commands'], 1):
            print(f"{i}. {cmd['name']}")
            print(f"   URI: {cmd['uri']}")
            if 'projection' in cmd:
                print(f"   Projection: {cmd['projection']}")
            print(f"   Description: {cmd['description']}")
            print(f"   ADB Command: adb shell content query --uri {cmd['uri']}" + 
                  (f" --projection {cmd['projection']}" if 'projection' in cmd else ""))
            print()
    
    print("="*80)
    print("IMPORTANT NOTES:")
    print("- Root access may be required for some content providers")
    print("- Device must have USB debugging enabled")
    print("- Some URIs may not be accessible on newer Android versions")
    print("- Always ensure proper legal authorization before data collection")
    print("="*80)


def generate_command_script(output_file: str = "forensic_commands.sh"):
    """Generate a shell script with all ADB commands."""
    script_content = """#!/bin/bash
# Android Forensic Data Collection Script
# Generated on: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """
# 
# This script contains ADB commands for collecting forensic data from Android devices
# using content provider URIs.
#
# IMPORTANT: Ensure proper legal authorization before running these commands!

echo "Starting Android Forensic Data Collection..."
echo "Timestamp: $(date)"

# Check if device is connected
if ! adb devices | grep -q "device$"; then
    echo "Error: No Android device detected. Please connect device and enable USB debugging."
    exit 1
fi

# Create output directory
OUTPUT_DIR="forensic_data_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUTPUT_DIR"
echo "Output directory: $OUTPUT_DIR"

"""
    
    for category, info in CONTENT_URI_COMMANDS.items():
        script_content += f'\n# {category.upper().replace("_", " ")} DATA\n'
        script_content += f'echo "Collecting {category.replace("_", " ")} data..."\n'
        
        for cmd in info['commands']:
            safe_name = cmd['name'].replace(' ', '_').replace('/', '_').lower()
            projection_arg = f" --projection {cmd['projection']}" if 'projection' in cmd else ""
            
            script_content += f'\n# {cmd["name"]}\n'
            script_content += f'adb shell content query --uri {cmd["uri"]}{projection_arg} > "$OUTPUT_DIR/{category}_{safe_name}.txt" 2>&1\n'
    
    script_content += '\necho "Data collection completed. Check $OUTPUT_DIR for results."\n'
    
    with open(output_file, 'w') as f:
        f.write(script_content)
    
    os.chmod(output_file, 0o755)
    print(f"Generated executable script: {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Android Forensic Data Collector')
    parser.add_argument('--list', action='store_true', help='List available content URIs')
    parser.add_argument('--discover', action='store_true', help='Discover content providers on device')
    parser.add_argument('--test', metavar='URI', help='Test a specific content URI')
    parser.add_argument('--collect', action='store_true', help='Collect all available data via ADB')
    parser.add_argument('--collect-app', action='store_true', help='Collect data using Android app (bypasses ADB limitations)')
    parser.add_argument('--collect-backup', action='store_true', help='Create comprehensive ADB backup for forensic analysis')
    parser.add_argument('--backup-full', action='store_true', help='Create full backup including system apps (requires more time/storage)')
    parser.add_argument('--backup-no-apks', action='store_true', help='Create backup without APK files (faster, smaller)')
    parser.add_argument('--extract-backup', metavar='BACKUP_FILE', help='Extract an existing ADB backup file')
    parser.add_argument('--install-app', action='store_true', help='Install the forensic data collector app')
    parser.add_argument('--output', metavar='DIR', default='forensic_output', help='Output directory')
    parser.add_argument('--timeout', metavar='MINUTES', type=int, default=10, help='Timeout for app collection (default: 10 minutes)')
    
    args = parser.parse_args()
    
    collector = ArsenicTriageCollector()
    if args.output != 'forensic_output':  # Only override if user specified custom output
        collector.output_dir = args.output
    
    if args.list:
        collector.list_content_uris()
    elif args.discover:
        collector.discover_content_providers()
    elif args.test:
        collector.test_content_provider_access(args.test)
    elif args.collect:
        collector.collect_all_data()
    elif args.collect_app:
        collector.collect_with_app(install_app=not args.install_app, timeout_minutes=args.timeout)
    elif args.collect_backup:
        # Configure backup options based on flags
        include_apks = not args.backup_no_apks
        include_system = args.backup_full
        include_shared = True  # Always include shared storage for forensics
        collector.collect_with_backup(include_apks, include_system, include_shared)
    elif args.extract_backup:
        collector.extract_adb_backup(args.extract_backup)
    elif args.install_app:
        collector.install_forensic_app()
    else:
        print("Arsenic Triage - Android Forensic Data Collector")
        print("=================================================")
        print()
        print("This tool collects forensic data from Android devices using multiple methods:")
        print("1. ADB Content Provider Queries (--collect)")
        print("2. Native Android App (--collect-app) - Use when ADB queries fail")
        print("3. ADB Backup (--collect-backup) - Comprehensive device backup")
        print()
        print("Quick Start:")
        print("  1. Connect Android device with USB debugging enabled")
        print("  2. Run: python android_forensic_collector.py --collect")
        print("  3. For comprehensive backup: python android_forensic_collector.py --collect-backup")
        print("  4. If content queries fail, try: python android_forensic_collector.py --collect-app")
        print()
        print("Available commands:")
        print("  --list                  List all available content URIs")
        print("  --discover              Discover content providers on connected device")
        print("  --test URI              Test access to a specific content URI")
        print("  --collect               Collect data via ADB content queries")
        print("  --collect-app           Collect data using Android app (recommended for restricted devices)")
        print("  --collect-backup        Create comprehensive ADB backup for forensic analysis")
        print("  --backup-full           Include system apps in backup (larger file, more data)")
        print("  --backup-no-apks        Create backup without APK files (faster, smaller)")
        print("  --extract-backup FILE   Extract an existing ADB backup file")
        print("  --install-app           Install the forensic app only")
        print("  --output DIR            Specify output directory")
        print("  --timeout MINUTES       Timeout for app collection (default: 10)")
        print()
        print("Examples:")
        print("  python android_forensic_collector.py --collect")
        print("  python android_forensic_collector.py --collect-backup")
        print("  python android_forensic_collector.py --collect-backup --backup-full")
        print("  python android_forensic_collector.py --collect-app --timeout 15")
        print("  python android_forensic_collector.py --extract-backup backup_file.ab")
        print("  python android_forensic_collector.py --test 'content://call_log/calls'")
        print()
        print("Notes:")
        print("  - ADB backup requires user approval on device")
        print("  - Full backups with system apps can be several GB in size")
        print("  - Android app method requires manual permission granting on device")
        print("  - Always ensure proper legal authorization before data collection")


if __name__ == "__main__":
    main()
