"""
Flask Backend for Arsenic Mobile Triage Tool
Copyright (c) 2025 North Loop Consulting, LLC - Charlie Rubisoff
GPLv3 License
"""

from flask import Flask, jsonify, request, send_file
import os
import sys
import threading
import logging
import traceback
import queue
import json
import time
import csv
from datetime import datetime
import subprocess
import platform

# Try to import flask-cors, but fall back to manual CORS if not available
try:
    from flask_cors import CORS
    CORS_AVAILABLE = True
except ImportError:
    CORS_AVAILABLE = False
    print("flask-cors not available, using manual CORS headers")

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = current_dir
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import existing modules
try:
    from src.backup.device_backup import DeviceBackup
    DEVICE_BACKUP_AVAILABLE = True
except ImportError as e:
    print(f"Warning: iOS backup functionality disabled due to import error: {e}")
    DeviceBackup = None
    DEVICE_BACKUP_AVAILABLE = False

from src.Droid_triage.Android_Triage import AndroidTriageHandler
from src.Droid_backup.android_backup_collector import ArsenicTriageCollector
from src.parser.backup_parser import parse_backup
from src.parser.AB_parser import BackupExtractor, ForensicDataParser

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_adb_command():
    """Get the correct ADB command path for the current environment."""
    debug_log_path = os.path.join(os.getcwd(), "flask_debug.log")
    adb_command = "adb"  # Default for development
    
    # Always try to use the wrapper script first if available
    possible_wrapper_paths = [
        # Compiled app bundle paths
        os.path.join(os.getcwd(), 'src', 'utils', 'adb_wrapper.sh'),
        # Development paths  
        os.path.join(os.path.dirname(__file__), 'src', 'utils', 'adb_wrapper.sh'),
        # PyInstaller bundle path
        os.path.join(getattr(sys, '_MEIPASS', os.getcwd()), 'src', 'utils', 'adb_wrapper.sh')
    ]
    
    possible_adb_paths = [
        # Compiled app bundle paths
        os.path.join(os.getcwd(), 'src', 'utils', 'adb'),
        # Development paths
        os.path.join(os.path.dirname(__file__), 'src', 'utils', 'adb'),
        # PyInstaller bundle path
        os.path.join(getattr(sys, '_MEIPASS', os.getcwd()), 'src', 'utils', 'adb')
    ]
    
    with open(debug_log_path, "a") as f:
        f.write(f"Current working directory: {os.getcwd()}\n")
        f.write(f"Script directory: {os.path.dirname(__file__)}\n")
        f.write(f"MEIPASS: {getattr(sys, '_MEIPASS', 'Not set')}\n")
    
    # Try direct ADB binary FIRST (wrapper doesn't work with symlinks due to SCRIPT_DIR resolution)
    for adb_path in possible_adb_paths:
        with open(debug_log_path, "a") as f:
            f.write(f"Checking ADB: {adb_path} - exists: {os.path.exists(adb_path)}\n")
        if os.path.exists(adb_path):
            adb_command = adb_path
            with open(debug_log_path, "a") as f:
                f.write(f"Using direct ADB: {adb_command}\n")
            return adb_command
    
    # Fall back to system ADB
    with open(debug_log_path, "a") as f:
        f.write("Using system ADB command\n")
    
    return adb_command

# Windows-specific subprocess flag
if sys.platform == "win32":
    SUBPROCESS_FLAGS = subprocess.CREATE_NO_WINDOW
else:
    SUBPROCESS_FLAGS = 0

app = Flask(__name__)

# Global dictionary to track processing operations
processing_results = {}

# Enable CORS for Electron communication
if CORS_AVAILABLE:
    CORS(app)
else:
    # Manual CORS handling
    @app.after_request
    def after_request(response):
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
        return response

def monitor_data_collection(collector, status_callback, progress_callback, timeout_minutes=10):
    """
    Monitor device storage for JSON files to detect when data collection begins.
    Returns the number of files found when ≥2 files are detected, or False if timeout.
    """
    print(f"DEBUG: Starting data collection monitoring for {timeout_minutes} minutes...")
    
    start_time = time.time()
    timeout_seconds = timeout_minutes * 60
    check_interval = 15  # Check every 15 seconds
    last_status_time = time.time()
    last_json_count = 0
    
    # Progress tracking
    initial_progress = 40  # Starting progress
    final_progress = 70    # Progress when data is found
    
    while time.time() - start_time < timeout_seconds:
        try:
            # Calculate elapsed time and progress
            elapsed_time = time.time() - start_time
            progress_percent = initial_progress + ((elapsed_time / timeout_seconds) * (final_progress - initial_progress))
            progress_callback(int(progress_percent))
            
            # Update status every minute or when data count changes
            if time.time() - last_status_time > 45:  # Status every 45 seconds
                minutes_elapsed = int(elapsed_time / 60)
                minutes_remaining = timeout_minutes - minutes_elapsed
                status_callback(f"⏳ Monitoring device storage... {minutes_elapsed}m elapsed")
                last_status_time = time.time()
            
            # Check both possible device directories for JSON files
            current_json_count = 0
            found_in_dir = None
            
            for device_dir in [collector.device_output_dir_modern, collector.device_output_dir_legacy]:
                try:
                    # List all files in the directory
                    list_result = collector._run_subprocess([collector.adb_command, 'shell', 'ls', '-la', device_dir], timeout=15)
                    
                    if list_result.returncode == 0 and list_result.stdout.strip():
                        files = list_result.stdout.strip().split('\n')
                        json_files = []
                        
                        for f in files:
                            f_clean = f.strip()
                            # Look specifically for JSON data files (not system/summary files)
                            if (f_clean and 
                                not f_clean.startswith('total') and 
                                not f_clean.startswith('d') and
                                f_clean.endswith('.json') and
                                'collection_complete.json' not in f_clean and 
                                'collection_summary.txt' not in f_clean):
                                json_files.append(f_clean)
                        
                        print(f"DEBUG: Found {len(json_files)} JSON files in {device_dir}: {json_files}")
                        
                        if len(json_files) > current_json_count:
                            current_json_count = len(json_files)
                            found_in_dir = device_dir
                            
                except Exception as e:
                    print(f"DEBUG: Error checking {device_dir}: {e}")
                    continue
            
            # Report progress if JSON count changed
            if current_json_count != last_json_count:
                if current_json_count == 0:
                    status_callback("📱 Waiting for investigation to begin...")
                elif current_json_count == 1:
                    status_callback("🔍 Data collection detected - first file created!")
                elif current_json_count >= 2:
                    # Data collection threshold met!
                    collector.device_output_dir = found_in_dir  # Set the correct directory
                    status_callback(f"✅ Investigation complete - {current_json_count} data files collected!")
                    print(f"DEBUG: Data collection complete! {current_json_count} files found")
                    return current_json_count
                
                last_json_count = current_json_count
            
            # Wait before next check
            time.sleep(check_interval)
            
        except Exception as e:
            print(f"ERROR in monitor_data_collection: {e}")
            continue
    
    print("DEBUG: Data collection monitoring timeout reached")
    return False

class TriageManager:
    """Manages ongoing triage operations and device connections"""
    
    def __init__(self):
        self.case_number = ""
        self.output_directory = ""
        self.ios_backup_handler = None
        self.android_triage_handler = AndroidTriageHandler()
        self.android_backup_collector = None
        self.operations = {}  # Track ongoing operations
        self.status_queues = {}  # Status update queues for operations
        
    def get_case_info(self):
        return {
            "case_number": self.case_number,
            "output_directory": self.output_directory
        }
    
    def update_case_info(self, case_number=None, output_directory=None):
        if case_number is not None:
            self.case_number = case_number
        if output_directory is not None:
            self.output_directory = output_directory
    
    def check_ios_device_status(self):
        """Check iOS device connection status"""
        try:
            from pymobiledevice3.usbmux import list_devices
            devices = list_devices()
            if devices:
                return {
                    "connected": True,
                    "count": len(devices),
                    "message": f"🟢 iOS: {len(devices)} device(s) connected"
                }
            else:
                return {
                    "connected": False,
                    "count": 0,
                    "message": "🔴 iOS: No device connected"
                }
        except Exception as e:
            logger.error(f"Error checking iOS device status: {e}")
            return {
                "connected": False,
                "count": 0,
                "message": "🟡 iOS: Check failed",
                "error": str(e)
            }
    
    def check_android_device_status(self):
        """Check Android device connection status"""
        try:
            # Get ADB command
            adb_commands = self._get_adb_commands()
            
            for adb_cmd in adb_commands:
                try:
                    result = subprocess.run([adb_cmd, 'devices'], 
                                          capture_output=True, text=True, timeout=5,
                                          creationflags=SUBPROCESS_FLAGS)
                    
                    if result.returncode == 0:
                        devices = []
                        for line in result.stdout.split('\n'):
                            line = line.strip()
                            if line and 'device' in line and not line.startswith('List'):
                                parts = line.split('\t')
                                if len(parts) >= 2 and parts[1] == 'device':
                                    devices.append(parts[0])  # Store serial number
                        
                        if devices:
                            # Get detailed device info for the first device
                            device_info = self._get_android_device_details(adb_cmd, devices[0])
                            
                            return {
                                "connected": True,
                                "count": len(devices),
                                "message": f"🟢 Android: {len(devices)} device(s) connected",
                                "adb_command": adb_cmd,
                                "device_info": device_info
                            }
                        else:
                            return {
                                "connected": False,
                                "count": 0,
                                "message": "🔴 Android: No device connected",
                                "adb_command": adb_cmd
                            }
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    continue
            
            return {
                "connected": False,
                "count": 0,
                "message": "🟡 Android: ADB unavailable",
                "error": "No working ADB command found"
            }
            
        except Exception as e:
            logger.error(f"Error checking Android device status: {e}")
            return {
                "connected": False,
                "count": 0,
                "message": "🟡 Android: Check failed",
                "error": str(e)
            }
    
    def _get_android_device_details(self, adb_cmd, serial):
        """Get detailed information about an Android device"""
        try:
            # Use the comprehensive device details from the triage handler
            if hasattr(self.android_triage_handler, 'get_all_device_details'):
                comprehensive_details = self.android_triage_handler.get_all_device_details()
                
                # Format for basic device status display (keep existing fields plus key additions)
                device_info = {
                    "serial": serial,
                    "model": comprehensive_details.get("Model", "Unknown"),
                    "manufacturer": comprehensive_details.get("Manufacturer", "Unknown"),
                    "android_version": comprehensive_details.get("Android Version", "Unknown"),
                    "product_name": comprehensive_details.get("Device Name", "Unknown"),
                    "sdk_version": comprehensive_details.get("API Level", "Unknown"),
                    "build_id": comprehensive_details.get("Build ID", "Unknown"),
                    "security_patch": comprehensive_details.get("Security Patch", "Unknown"),
                    "encryption_status": comprehensive_details.get("Encryption Status", "Unknown"),
                    "hardware": comprehensive_details.get("Hardware", "Unknown"),
                    "imei": comprehensive_details.get("IMEI", "Unknown"),
                    "brand": comprehensive_details.get("Brand", "Unknown"),
                    "chipset": comprehensive_details.get("Chipset", "Unknown")
                }
                
                return device_info
            else:
                # Fallback to basic properties if comprehensive method not available
                device_info = {"serial": serial}
                
                # Get device properties
                properties = [
                    ("ro.product.model", "model"),
                    ("ro.product.manufacturer", "manufacturer"), 
                    ("ro.build.version.release", "android_version"),
                    ("ro.product.name", "product_name"),
                    ("ro.build.version.sdk", "sdk_version"),
                    ("ro.build.display.id", "build_id")
                ]
                
                for prop, key in properties:
                    try:
                        result = subprocess.run([adb_cmd, '-s', serial, 'shell', 'getprop', prop],
                                              capture_output=True, text=True, timeout=3,
                                              creationflags=SUBPROCESS_FLAGS)
                        if result.returncode == 0:
                            value = result.stdout.strip()
                            if value:
                                device_info[key] = value
                    except Exception:
                        device_info[key] = "Unknown"
                
                return device_info
                
        except Exception as e:
            logger.error(f"Error getting device details: {e}")
            return {"serial": serial, "error": str(e)}
            
        except Exception as e:
            logger.error(f"Error getting Android device details: {e}")
            return {"serial": serial, "error": str(e)}
    
    def _get_adb_commands(self):
        """Get list of potential ADB commands to try"""
        adb_commands = []
        
        # Try local ADB first
        local_adb = os.path.join(project_root, "src", "utils", "adb")
        local_adb_exe = os.path.join(project_root, "src", "utils", "adb.exe")
        
        if platform.system() == "Windows":
            if os.path.exists(local_adb_exe):
                adb_commands.append(local_adb_exe)
        else:
            if os.path.exists(local_adb):
                adb_commands.append(local_adb)
            if os.path.exists(local_adb_exe):
                adb_commands.append(local_adb_exe)
        
        # System ADB fallback
        adb_commands.append('adb')
        
        return adb_commands
    
    def get_ios_device_info(self):
        """Get detailed iOS device information"""
        try:
            from pymobiledevice3.lockdown import create_using_usbmux
            from pymobiledevice3.usbmux import list_devices
            
            devices = list_devices()
            if not devices:
                return {"error": "No iOS device connected"}
            
            device = devices[0]  # Use first device
            lockdown = create_using_usbmux(serial=device.serial)
            
            # Get device information
            device_info = {
                "DeviceName": lockdown.get_value(domain=None, key="DeviceName"),
                "ProductType": lockdown.get_value(domain=None, key="ProductType"),
                "ProductVersion": lockdown.get_value(domain=None, key="ProductVersion"),
                "BuildVersion": lockdown.get_value(domain=None, key="BuildVersion"),
                "SerialNumber": lockdown.get_value(domain=None, key="SerialNumber"),
                "UniqueDeviceID": lockdown.get_value(domain=None, key="UniqueDeviceID"),
                "WiFiAddress": lockdown.get_value(domain=None, key="WiFiAddress"),
                "BluetoothAddress": lockdown.get_value(domain=None, key="BluetoothAddress")
            }
            
            return device_info
            
        except Exception as e:
            logger.error(f"Error getting iOS device info: {e}")
            return {"error": str(e)}
    
    def get_android_device_info(self):
        """Get detailed Android device information"""
        try:
            if not self.android_triage_handler.is_device_connected():
                return {"error": "No Android device connected"}
            
            # Get comprehensive device details
            device_details = self.android_triage_handler.get_all_device_details()
            
            # Format the response for frontend consumption
            formatted_info = {}
            for key, value in device_details.items():
                if key == "Users" and isinstance(value, list):
                    # Format users list for display
                    user_info = []
                    for user in value:
                        if isinstance(user, dict):
                            user_str = f"ID: {user.get('id', 'Unknown')}, Name: {user.get('name', 'Unknown')}"
                            if user.get('running', False):
                                user_str += " (Running)"
                            user_info.append(user_str)
                    formatted_info[key] = "; ".join(user_info) if user_info else "Single User"
                else:
                    formatted_info[key] = str(value) if value is not None else "Unknown"
            
            return formatted_info
        except Exception as e:
            logger.error(f"Error getting Android device info: {e}")
            return {"error": str(e)}

# Initialize the manager
triage_manager = TriageManager()

# API Routes

@app.route('/api/system/status')
def system_status():
    """Get overall system status"""
    return jsonify({
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "case_info": triage_manager.get_case_info()
    })

@app.route('/api/case/info')
def get_case_info():
    """Get current case information"""
    return jsonify(triage_manager.get_case_info())

@app.route('/api/case/update', methods=['POST'])
def update_case_info():
    """Update case information"""
    try:
        data = request.get_json()
        triage_manager.update_case_info(
            case_number=data.get('case_number'),
            output_directory=data.get('output_directory')
        )
        return jsonify({"success": True, "case_info": triage_manager.get_case_info()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/devices/ios/status')
def ios_device_status():
    """Check iOS device connection status"""
    return jsonify(triage_manager.check_ios_device_status())

@app.route('/api/devices/android/status')
def android_device_status():
    """Check Android device connection status"""
    return jsonify(triage_manager.check_android_device_status())

@app.route('/api/devices/ios/info')
def ios_device_info():
    """Get iOS device information"""
    return jsonify(triage_manager.get_ios_device_info())

@app.route('/api/devices/android/info')
def android_device_info():
    """Get Android device information"""
    return jsonify(triage_manager.get_android_device_info())

@app.route('/api/ios/apps')
def get_ios_apps():
    """Get list of installed iOS apps"""
    try:
        from pymobiledevice3.lockdown import create_using_usbmux
        from pymobiledevice3.usbmux import list_devices
        from pymobiledevice3.services import installation_proxy
        
        devices = list_devices()
        if not devices:
            return jsonify({"error": "No iOS device connected"})
        
        device = devices[0]
        lockdown = create_using_usbmux(serial=device.serial)
        
        with installation_proxy.InstallationProxyService(lockdown=lockdown) as installation_proxy_service:
            apps = installation_proxy_service.get_apps()
            
        app_list = []
        for bundle_id, app_info in apps.items():
            if 'CFBundleDisplayName' in app_info:
                app_list.append({
                    "bundle_id": bundle_id,
                    "name": app_info.get('CFBundleDisplayName', bundle_id),
                    "version": app_info.get('CFBundleShortVersionString', 'Unknown'),
                    "is_system": app_info.get('ApplicationType') == 'System'
                })
        
        return jsonify({
            "success": True,
            "apps": app_list,
            "count": len(app_list)
        })
        
    except Exception as e:
        logger.error(f"Error getting iOS apps: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/devices/ios/detect')
def ios_device_detect():
    """Detect iOS device connection"""
    return jsonify(triage_manager.check_ios_device_status())

@app.route('/api/devices/android/detect')
def android_device_detect():
    """Detect Android device connection"""
    return jsonify(triage_manager.check_android_device_status())

@app.route('/api/capture_screenshot', methods=['POST'])
def capture_screenshot():
    """Capture screenshot from Android device using ADB"""
    try:
        data = request.get_json() or {}
        output_dir = data.get('output_dir', '')
        case_number = data.get('case_number', '')
        filename = data.get('filename', f'screenshot_{int(time.time())}.png')
        
        if not output_dir:
            return jsonify({
                'success': False,
                'error': 'Output directory not specified'
            }), 400
            
        if not case_number:
            return jsonify({
                'success': False,
                'error': 'Case number not specified'
            }), 400
        
        # Find or create Android triage case folder
        case_folder = None
        
        # Look for existing Android_Triage folder for this case
        import glob
        pattern = os.path.join(output_dir, f"Android_Triage_{case_number}_*")
        existing_folders = glob.glob(pattern)
        
        if existing_folders:
            # Use the most recent existing folder
            case_folder = max(existing_folders, key=os.path.getmtime)
            logger.info(f"Using existing case folder: {case_folder}")
        else:
            # Create new case folder with current timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            case_folder = os.path.join(output_dir, f"Android_Triage_{case_number}_{timestamp}")
            try:
                os.makedirs(case_folder, exist_ok=True)
                logger.info(f"Created new case folder: {case_folder}")
            except Exception as e:
                logger.error(f"Failed to create case folder: {e}")
                return jsonify({
                    'success': False,
                    'error': f'Failed to create case folder: {str(e)}'
                }), 500
        
        # Create Screenshots subfolder within the case folder
        screenshots_dir = os.path.join(case_folder, 'Screenshots')
        try:
            os.makedirs(screenshots_dir, exist_ok=True)
            logger.info(f"Screenshots directory created/verified: {screenshots_dir}")
        except Exception as e:
            logger.error(f"Failed to create screenshots directory: {e}")
            return jsonify({
                'success': False,
                'error': f'Failed to create screenshots directory: {str(e)}'
            }), 500
        
        # Full path for screenshot
        screenshot_path = os.path.join(screenshots_dir, filename)
        
        # Check if Android device is connected
        android_status = triage_manager.check_android_device_status()
        if not android_status.get('connected', False):
            return jsonify({
                'success': False,
                'error': 'No Android device connected'
            }), 400
        
        # Get ADB path from triage manager
        adb_path = None
        if hasattr(triage_manager, 'android_handler') and triage_manager.android_handler:
            adb_path = getattr(triage_manager.android_handler, 'adb_path', None)
        
        # Fallback ADB path detection
        if not adb_path:
            utils_dir = os.path.join(project_root, 'src', 'utils')
            potential_adb = os.path.join(utils_dir, 'adb.exe' if platform.system() == 'Windows' else 'adb')
            if os.path.exists(potential_adb):
                adb_path = potential_adb
            else:
                # Try system ADB
                adb_path = 'adb'
        
        logger.info(f"Using ADB path: {adb_path}")
        
        # Capture screenshot using ADB
        try:
            # Use ADB to capture screenshot to device
            device_screenshot_path = '/sdcard/screenshot_temp.png'
            
            # Capture screenshot on device
            result = subprocess.run([
                adb_path, 'exec-out', 'screencap', '-p'
            ], capture_output=True, timeout=30)
            
            if result.returncode != 0:
                logger.error(f"ADB screencap failed: {result.stderr.decode()}")
                return jsonify({
                    'success': False,
                    'error': 'Failed to capture screenshot on device'
                }), 500
            
            # Save the screenshot data directly to file
            with open(screenshot_path, 'wb') as f:
                f.write(result.stdout)
            
            # Verify screenshot was created and has content
            if not os.path.exists(screenshot_path) or os.path.getsize(screenshot_path) == 0:
                return jsonify({
                    'success': False,
                    'error': 'Screenshot file was not created or is empty'
                }), 500
            
            logger.info(f"Screenshot captured successfully: {screenshot_path}")
            
            return jsonify({
                'success': True,
                'screenshot_path': screenshot_path,
                'filename': filename,
                'message': 'Screenshot captured successfully'
            })
            
        except subprocess.TimeoutExpired:
            logger.error("ADB screenshot command timed out")
            return jsonify({
                'success': False,
                'error': 'Screenshot capture timed out'
            }), 500
            
        except Exception as e:
            logger.error(f"Error during screenshot capture: {e}")
            logger.error(traceback.format_exc())
            return jsonify({
                'success': False,
                'error': f'Screenshot capture failed: {str(e)}'
            }), 500
    
    except Exception as e:
        logger.error(f"Screenshot endpoint error: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }), 500

def load_csv_data_from_artifacts(case_folder):
    """Load CSV data from artifacts folder and return structured data for UI"""
    import csv
    
    logger.info(f"DEBUG: load_csv_data_from_artifacts called with case_folder: {case_folder}")
    
    if not case_folder or not os.path.exists(case_folder):
        logger.info(f"DEBUG: Case folder doesn't exist: {case_folder}")
        return {}
    
    artifacts_folder = os.path.join(case_folder, "Artifacts")
    logger.info(f"DEBUG: Artifacts folder: {artifacts_folder}, exists: {os.path.exists(artifacts_folder)}")
    
    csv_data = {}
    
    # Define CSV files to load with their organized locations
    csv_files = {
        'sms_data': {
            'file': os.path.join('Data', 'Messages', 'sms_messages.csv'),
            'key': 'sms_data'
        },
        'mms_data': {
            'file': os.path.join('Data', 'Messages', 'mms_messages.csv'), 
            'key': 'mms_data'
        },
        'contacts_data': {
            'file': os.path.join('Data', 'Contacts', 'contacts_data.csv'),
            'key': 'contacts_data'
        },
        'call_logs_data': {
            'file': os.path.join('Data', 'CallLogs', 'call_logs.csv'),
            'key': 'call_logs_data'
        }
    }
    
    # Load main CSV files from organized structure
    for data_type, info in csv_files.items():
        csv_path = os.path.join(case_folder, info['file'])  # Use case_folder instead of artifacts_folder
        logger.info(f"DEBUG: Checking {data_type} at path: {csv_path}, exists: {os.path.exists(csv_path)}")
        if os.path.exists(csv_path):
            try:
                with open(csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                    csv_data[info['key']] = {
                        'records': rows,
                        'record_count': len(rows),
                        'csv_file': csv_path
                    }
                    logger.info(f"DEBUG: Successfully loaded {data_type}: {len(rows)} records")
            except Exception as e:
                logger.error(f"Error loading {csv_path}: {e}")
        else:
            logger.info(f"DEBUG: CSV file not found for {data_type}: {csv_path}")
        
    # Load notifications CSV
    notifications_folder = os.path.join(artifacts_folder, "Notifications")
    notifications_csv = os.path.join(notifications_folder, "notifications.csv")
    logger.info(f"DEBUG: Checking notifications at: {notifications_csv}, exists: {os.path.exists(notifications_csv)}")
    if os.path.exists(notifications_csv):
        try:
            with open(notifications_csv, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                csv_data['notifications_data'] = {
                    'records': rows,
                    'record_count': len(rows),
                    'csv_file': notifications_csv
                }
                logger.info(f"DEBUG: Successfully loaded notifications: {len(rows)} records")
        except Exception as e:
            logger.error(f"Error loading notifications CSV: {e}")    # Load external files CSV data
    external_files_folder = os.path.join(artifacts_folder, "External_Files")
    external_csv_files = {
        'videos_data': 'external_videos.csv',
        'images_data': 'external_images.csv',
        'downloads_data': 'downloads.csv'
    }
    
    for data_type, filename in external_csv_files.items():
        csv_path = os.path.join(external_files_folder, filename)
        if os.path.exists(csv_path):
            try:
                with open(csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                    if data_type not in csv_data:
                        csv_data[data_type] = {}
                    csv_data[data_type] = {
                        'records': rows,
                        'record_count': len(rows),
                        'csv_file': csv_path
                    }
            except Exception as e:
                logger.error(f"Error loading {csv_path}: {e}")
    
    return csv_data

@app.route('/api/operations/android/triage', methods=['POST'])
def start_android_triage():
    """Start Android device triage"""
    try:
        print("DEBUG: start_android_triage called")
        
        data = request.get_json()
        print(f"DEBUG: Request data: {data}")
        
        # Check if there's already an active triage operation
        active_operations = [op_id for op_id, op_type in triage_manager.operations.items() 
                           if op_type == "android_triage"]
        if active_operations:
            print(f"DEBUG: Found active triage operations: {active_operations}")
            return jsonify({"success": False, "error": "Android triage is already running"}), 409
        
        # Update case info
        if 'case_number' in data:
            triage_manager.case_number = data['case_number']
        if 'output_directory' in data:
            triage_manager.output_directory = data['output_directory']
        
        if not triage_manager.case_number or not triage_manager.output_directory:
            return jsonify({"success": False, "error": "Case number and output directory required"}), 400
        
        # Start triage in background thread
        operation_id = f"android_triage_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"DEBUG: Starting operation {operation_id}")
        
        def triage_thread():
            try:
                # Set up status queue for this operation
                status_queue = queue.Queue()
                triage_manager.status_queues[operation_id] = status_queue
                
                def status_callback(message):
                    logger.info(f"Android Triage: {message}")
                    status_queue.put({"type": "status", "message": message, "progress": None})
                
                def progress_callback(progress):
                    # Don't send generic "Processing..." messages, just progress updates
                    status_queue.put({"type": "progress", "message": "", "progress": int(progress * 100)})
                
                # Import and initialize the Android triage handler
                from src.Droid_triage.Android_Triage import AndroidTriageHandler
                
                status_callback("Initializing Android triage handler...")
                android_handler = AndroidTriageHandler()
                
                # Check if device is connected first
                if not android_handler.is_device_connected():
                    raise Exception("No Android device connected. Please connect a device with USB debugging enabled.")
                
                status_callback("Device connection verified. Starting Android triage...")
                
                # Run the actual triage process using the existing method
                triage_results = android_handler.run_triage(
                    case_number=triage_manager.case_number,
                    output_dir=triage_manager.output_directory,
                    get_hashes=False,
                    get_thumbnails=data.get('thumbnails', True),
                    make_backup=data.get('backup', False),
                    pull_storage=data.get('files', True),
                    status_callback=status_callback,
                    progress_callback=progress_callback
                )
                
                # Process the results for display
                if triage_results:
                    status_callback("Triage completed successfully!")
                    
                    # Debug: Log the structure of triage_results
                    logger.info(f"Triage results structure: {list(triage_results.keys()) if triage_results else 'None'}")
                    if triage_results and 'artifacts' in triage_results:
                        logger.info(f"Artifacts structure: {list(triage_results['artifacts'].keys())}")
                        for key, value in triage_results['artifacts'].items():
                            if isinstance(value, dict) and 'record_count' in value:
                                logger.info(f"  {key}: {value['record_count']} records")
                    
                    # Load CSV data from artifacts folder
                    status_callback("Loading CSV data...")
                    csv_data = load_csv_data_from_artifacts(triage_results.get('case_folder'))
                    logger.info(f"DEBUG: CSV data loaded: {list(csv_data.keys())}")
                    
                    # Merge CSV data into triage_results
                    if csv_data:
                        if 'artifacts' not in triage_results:
                            triage_results['artifacts'] = {}
                        triage_results['artifacts'].update(csv_data)
                        
                        # Also put the actual records at the top level for easy access (like apps)
                        for data_type, data_info in csv_data.items():
                            if isinstance(data_info, dict) and 'records' in data_info:
                                triage_results[data_type] = data_info['records']
                                logger.info(f"DEBUG: Added {data_type} with {len(data_info['records'])} records to top level")
                        
                        status_callback(f"Loaded CSV data: {', '.join(csv_data.keys())}")
                    else:
                        logger.info("DEBUG: No CSV data was loaded")
                    
                    # Create a results summary for the status tab
                    summary_lines = [
                        "=== ANDROID TRIAGE COMPLETED ===",
                        f"Case Number: {triage_results.get('case_number', 'Unknown')}",
                        f"Timestamp: {triage_results.get('timestamp', 'Unknown')}",
                        f"Output Directory: {triage_results.get('case_folder', 'Unknown')}",
                        "",
                        "=== DEVICE INFORMATION ===",
                    ]
                    
                    # Add device details
                    if triage_results.get('device_details'):
                        for key, value in triage_results['device_details'].items():
                            summary_lines.append(f"{key}: {value}")
                    
                    summary_lines.append("")
                    
                    # Add app information
                    if triage_results.get('apps'):
                        summary_lines.append(f"=== INSTALLED APPLICATIONS ({len(triage_results['apps'])}) ===")
                        for app in triage_results['apps'][:10]:  # Show first 10 apps
                            summary_lines.append(f"- {app}")
                        if len(triage_results['apps']) > 10:
                            summary_lines.append(f"... and {len(triage_results['apps']) - 10} more apps")
                        summary_lines.append("")
                    
                    # Add artifacts information
                    if triage_results.get('artifacts'):
                        summary_lines.append("=== CONTENT ARTIFACTS ===")
                        artifacts = triage_results['artifacts']
                        
                        if artifacts.get('sms_data'):
                            summary_lines.append(f"SMS Messages: {artifacts['sms_data'].get('record_count', 0)} records")
                        if artifacts.get('mms_data'):
                            summary_lines.append(f"MMS Messages: {artifacts['mms_data'].get('record_count', 0)} records")
                        if artifacts.get('contacts_data'):
                            summary_lines.append(f"Contacts: {artifacts['contacts_data'].get('record_count', 0)} records")
                        if artifacts.get('call_logs_data'):
                            summary_lines.append(f"Call Logs: {artifacts['call_logs_data'].get('record_count', 0)} records")
                        summary_lines.append("")
                    
                    # Add file information
                    if triage_results.get('files'):
                        summary_lines.append(f"=== FILES FOUND ({len(triage_results['files'])}) ===")
                        file_types = {}
                        for file_info in triage_results['files']:
                            file_type = file_info.get('type', 'unknown')
                            file_types[file_type] = file_types.get(file_type, 0) + 1
                        
                        for file_type, count in file_types.items():
                            summary_lines.append(f"{file_type.title()}: {count} files")
                        summary_lines.append("")
                    
                    # Add external files information
                    if triage_results.get('external_files'):
                        summary_lines.append("=== EXTERNAL FILES ===")
                        ext_files = triage_results['external_files']
                        
                        if ext_files.get('videos_data'):
                            summary_lines.append(f"Videos: {ext_files['videos_data'].get('record_count', 0)} records")
                        if ext_files.get('images_data'):
                            summary_lines.append(f"Images: {ext_files['images_data'].get('record_count', 0)} records")
                        if ext_files.get('downloads_data'):
                            summary_lines.append(f"Downloads: {ext_files['downloads_data'].get('record_count', 0)} records")
                        summary_lines.append("")
                    
                    if triage_results.get('backup_path'):
                        summary_lines.append(f"=== BACKUP CREATED ===")
                        summary_lines.append(f"Backup file: {triage_results['backup_path']}")
                        summary_lines.append("")
                    
                    summary_lines.append("=== TRIAGE COMPLETE ===")
                    summary_lines.append("All detailed results have been saved to the output directory.")
                    summary_lines.append("Check the case folder for individual data files and reports.")
                    
                    summary_text = "\n".join(summary_lines)
                else:
                    summary_text = "Triage completed but no results were returned. Check the output directory for any generated files."
                    triage_results = None
                
                status_callback("Triage process completed successfully!")
                
                status_queue.put({
                    "type": "complete", 
                    "success": True,
                    "message": "Android triage completed successfully",
                    "progress": 100,
                    "results": triage_results,  # Frontend expects structured data in 'results'
                    "structured_data": triage_results,  # Keep for backward compatibility
                    "summary": summary_text  # Move summary text to separate field
                })
                
            except Exception as e:
                error_msg = f"Android triage error: {str(e)}"
                logger.error(error_msg)
                import traceback
                traceback.print_exc()
                status_queue.put({
                    "type": "complete",
                    "success": False,
                    "error": error_msg,
                    "progress": 0
                })
        
        threading.Thread(target=triage_thread, daemon=True).start()
        triage_manager.operations[operation_id] = "android_triage"
        
        return jsonify({
            "success": True,
            "operation_id": operation_id,
            "message": "Android triage started"
        })
        
    except Exception as e:
        logger.error(f"Error starting Android triage: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/android/triage/latest-results')
def get_latest_android_triage_results():
    """Get the latest and most complete Android triage results"""
    try:
        if not triage_manager.output_directory:
            print("DEBUG: No output directory configured in triage_manager")
        else:
            print(f"DEBUG: triage_manager.output_directory = '{triage_manager.output_directory}'")
        
        # Import the results loader
        from src.utils.triage_results_loader import find_latest_android_triage_results, load_triage_data_from_folder
        
        # Find the latest complete triage folder
        latest_folder = find_latest_android_triage_results(triage_manager.output_directory)
        
        if not latest_folder:
            print("DEBUG: No Android triage folder found")
            return jsonify({"success": False, "error": "No Android triage results found"}), 404
        
        print(f"DEBUG: Found latest Android triage folder: {latest_folder}")
        
        # Load structured data from the folder
        triage_data = load_triage_data_from_folder(latest_folder)
        
        if not triage_data:
            print("DEBUG: Failed to load triage data from folder")
            return jsonify({"success": False, "error": "Failed to load triage data"}), 500
        
        print(f"DEBUG: Successfully loaded triage data with {len(triage_data.get('artifacts', {}))} artifact types")
        for artifact_type, artifact_data in triage_data.get('artifacts', {}).items():
            record_count = artifact_data.get('record_count', 0)
            print(f"DEBUG: {artifact_type}: {record_count} records")
        
        # Load CSV data from artifacts folder and merge it
        csv_data = load_csv_data_from_artifacts(latest_folder)
        logger.info(f"DEBUG: CSV data loaded for latest results: {list(csv_data.keys())}")
        
        # Merge CSV data into triage_data
        if csv_data:
            if 'artifacts' not in triage_data:
                triage_data['artifacts'] = {}
            triage_data['artifacts'].update(csv_data)
            
            # Also put the actual records at the top level for easy access (like apps)
            for data_type, data_info in csv_data.items():
                if isinstance(data_info, dict) and 'records' in data_info:
                    triage_data[data_type] = data_info['records']
                    logger.info(f"DEBUG: Added {data_type} with {len(data_info['records'])} records to top level for latest results")
        else:
            logger.info("DEBUG: No CSV data was loaded for latest results")
        
        # Add case directory for CSV file access
        triage_data['case_directory'] = latest_folder
        
        # Create a results summary for the status tab
        summary_lines = [
            "=== ANDROID TRIAGE RESULTS ===",
            f"Case Folder: {os.path.basename(latest_folder)}",
            f"Loaded at: {triage_data.get('timestamp', 'Unknown')}",
            "",
            "=== DEVICE INFORMATION ===",
        ]
        
        # Add device details
        if triage_data.get('device_details'):
            for key, value in triage_data['device_details'].items():
                summary_lines.append(f"{key}: {value}")
        
        summary_lines.append("")
        
        # Add artifacts information
        if triage_data.get('artifacts'):
            summary_lines.append("=== CONTENT ARTIFACTS ===")
            artifacts = triage_data['artifacts']
            
            if artifacts.get('sms_data'):
                summary_lines.append(f"SMS Messages: {artifacts['sms_data']['record_count']} records")
            if artifacts.get('mms_data'):
                summary_lines.append(f"MMS Messages: {artifacts['mms_data']['record_count']} records")
            if artifacts.get('contacts_data'):
                summary_lines.append(f"Contacts: {artifacts['contacts_data']['record_count']} records")
            summary_lines.append("")
        
        # Add app information
        if triage_data.get('apps'):
            summary_lines.append(f"=== INSTALLED APPLICATIONS ({len(triage_data['apps'])}) ===")
            for app in triage_data['apps'][:10]:  # Show first 10 apps
                summary_lines.append(f"- {app}")
            if len(triage_data['apps']) > 10:
                summary_lines.append(f"... and {len(triage_data['apps']) - 10} more apps")
            summary_lines.append("")
        
        summary_lines.append("=== DATA LOADED ===")
        summary_lines.append("All detailed results are available in the tabbed interface.")
        summary_lines.append("Navigate through the tabs to view different data types.")
        
        summary_text = "\n".join(summary_lines)
        
        return jsonify({
            "success": True,
            "results": summary_text,
            "structured_data": triage_data,
            "case_folder": latest_folder
        })
        
    except Exception as e:
        logger.error(f"Error getting latest Android triage results: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/operations/ios/backup', methods=['POST'])
def start_ios_backup():
    """Start iOS device backup"""
    try:
        data = request.get_json()
        
        # Update case info
        if 'case_number' in data:
            triage_manager.case_number = data['case_number']
        if 'output_directory' in data:
            triage_manager.output_directory = data['output_directory']
        
        if not triage_manager.case_number or not triage_manager.output_directory:
            return jsonify({"success": False, "error": "Case number and output directory required"}), 400
        
        # Start backup in background thread
        operation_id = f"ios_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        def backup_thread():
            try:
                # Set up status queue for this operation
                status_queue = queue.Queue()
                triage_manager.status_queues[operation_id] = status_queue
                
                def status_callback(message):
                    # Filter out verbose or redundant messages more precisely
                    filtered_patterns = [
                        "backing up", "please wait", "working", "busy", 
                        "updating", "parsing", "preparing", "analyzing", 
                        "examining", "scanning", "processing results",
                        "operation in progress"
                    ]
                    
                    # Convert message to lowercase for checking
                    msg_lower = message.lower()
                    
                    # Skip messages that are just generic "processing..." without context
                    if msg_lower.strip() == "processing...":
                        return
                    
                    # Skip messages that match our filtered patterns exactly
                    if any(pattern in msg_lower for pattern in filtered_patterns):
                        return
                    
                    # Only send important status updates
                    status_queue.put({"type": "status", "message": message, "progress": None})
                
                def progress_callback(progress):
                    # Convert to percentage (0-100) for consistency with other operations
                    progress_percent = int(progress * 100) if progress <= 1.0 else int(progress)
                    print(f"DEBUG: iOS backup progress: {progress} -> {progress_percent}%")
                    status_queue.put({"type": "progress", "message": None, "progress": progress_percent})
                
                # Create the actual backup using DeviceBackup class
                status_callback("Initializing iOS backup...")
                
                # Check if iOS backup functionality is available
                if not DEVICE_BACKUP_AVAILABLE:
                    status_callback("❌ iOS backup functionality not available in compiled version")
                    return {"success": False, "error": "iOS backup functionality disabled"}
                
                # Create DeviceBackup instance
                backup_device = DeviceBackup()
                backup_device.set_callbacks(status_callback, progress_callback)
                
                # Create output directory with case number
                case_output_dir = os.path.join(triage_manager.output_directory, f"Case_{triage_manager.case_number}")
                if not os.path.exists(case_output_dir):
                    os.makedirs(case_output_dir)
                
                # Connect to device
                status_callback("Connecting to iOS device...")
                if not backup_device.connect_device():
                    raise Exception("Failed to connect to iOS device. Please ensure device is connected and trusted.")
                
                # Get device information
                status_callback("Getting device information...")
                backup_device.get_device_info()
                
                # Create backup (this handles password setting, backup creation, log collection, etc.)
                status_callback("Creating device backup...")
                success = backup_device.create_backup(case_output_dir, backup_logs=True)
                
                if success:
                    status_queue.put({
                        "type": "complete", 
                        "success": True,
                        "message": "iOS backup completed successfully",
                        "progress": 100,
                        "backup_info": {
                            "backup_folder": backup_device.backupFolder,
                            "backup_archive": backup_device.backupArchive,
                            "log_archive": backup_device.logArchive,
                            "backup_md5": backup_device.backupMD5,
                            "log_md5": backup_device.logMD5,
                            "device_info": backup_device.device_info
                        }
                    })
                else:
                    raise Exception("Backup process failed")
                
            except Exception as e:
                logger.error(f"iOS backup error: {e}")
                import traceback
                traceback.print_exc()
                status_queue.put({
                    "type": "complete",
                    "success": False,
                    "error": str(e),
                    "progress": 0
                })
        
        threading.Thread(target=backup_thread, daemon=True).start()
        triage_manager.operations[operation_id] = "ios_backup"
        
        return jsonify({
            "success": True,
            "operation_id": operation_id,
            "message": "iOS backup started"
        })
        
    except Exception as e:
        logger.error(f"Error starting iOS backup: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/operations/android/backup', methods=['POST'])
def start_android_backup():
    """Start Android device backup"""
    try:
        data = request.get_json()
        
        # Update case info
        if 'case_number' in data:
            triage_manager.case_number = data['case_number']
        if 'output_directory' in data:
            triage_manager.output_directory = data['output_directory']
        
        if not triage_manager.case_number or not triage_manager.output_directory:
            return jsonify({"success": False, "error": "Case number and output directory required"}), 400
        
        # Start backup in background thread
        operation_id = f"android_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Store backup parameters for later use in APK removal decision
        backup_params = {
            'case_number': triage_manager.case_number,
            'output_directory': triage_manager.output_directory,
            'use_forensic_apk': data.get('use_forensic_apk', True),
            'include_apks': data.get('backup_apps', True),
            'include_system': data.get('backup_system', False),
            'include_shared': data.get('backup_shared', True),
            'backup_all': data.get('backup_all', False),
            'timeout_minutes': data.get('timeout_minutes', 10),
            'case_folder': None,  # Will be set once folder is created
            # Store original UI checkbox states to know user intent
            'original_backup_apps': data.get('backup_apps', False),
            'original_backup_system': data.get('backup_system', False), 
            'original_backup_shared': data.get('backup_shared', False),
            'original_backup_all': data.get('backup_all', False)
        }
        
        # Store parameters for this operation
        if not hasattr(triage_manager, 'backup_params'):
            triage_manager.backup_params = {}
        triage_manager.backup_params[operation_id] = backup_params
        
        def backup_thread():
            try:
                # Set up status queue for this operation
                status_queue = queue.Queue()
                triage_manager.status_queues[operation_id] = status_queue
                
                def status_callback(message):
                    status_queue.put({"type": "status", "message": message, "progress": None})
                    print(f"🔄 Backup status: {message}")
                
                def progress_callback(percentage):
                    progress_message = f"Progress: {percentage}%"
                    status_queue.put({"type": "progress", "message": progress_message, "progress": percentage})
                    print(f"📊 Backup progress: {percentage}%")
                    
                # Add detailed status updates
                status_callback("🔍 Checking device connection...")
                status_callback("📱 Validating Android device compatibility...")
                
                # Check if forensic APK should be used
                use_apk = data.get('use_forensic_apk', True)
                if use_apk:
                    status_callback("🔬 Forensic APK mode enabled - starting enhanced data collection")
                    status_callback("📲 Installing forensic APK as first priority...")
                else:
                    status_callback("⚙️ Standard ADB backup mode selected")
                    
                status_callback("🚀 Beginning Android backup process...")
                
                # Initialize Android backup collector with correct ADB path
                collector = ArsenicTriageCollector(adb_command=get_adb_command())
                
                # Create case-specific output directory
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                case_folder = os.path.join(triage_manager.output_directory, f"Android_Backup_{triage_manager.case_number}_{timestamp}")
                os.makedirs(case_folder, exist_ok=True)
                collector.output_dir = case_folder
                
                # Store the case folder path for use in APK removal decision
                triage_manager.backup_params[operation_id]['case_folder'] = case_folder
                
                progress_callback(10)  # Initial setup complete
                
                # Get backup options from request
                use_apk = data.get('use_forensic_apk', True)
                include_apks = data.get('backup_apps', True)  # Map from frontend parameter
                include_system = data.get('backup_system', False)  # Map from frontend parameter  
                include_shared = data.get('backup_shared', True)  # Map from frontend parameter
                timeout_minutes = data.get('timeout_minutes', 10)
                
                app_success = False
                adb_success = False
                
                # Check if any backup was requested
                has_adb_backup = include_apks or include_system or include_shared or data.get('backup_all', False)
                
                if not use_apk and not has_adb_backup:
                    status_callback("❌ No backup options selected")
                    status_queue.put({
                        "type": "complete",
                        "success": False,
                        "error": "No backup options were selected",
                        "progress": 0
                    })
                    return
                
                # Run app-based collection first if requested
                if use_apk:
                    try:
                        status_callback("📲 Installing and launching forensic APK...")
                        progress_callback(20)
                        
                        print(f"DEBUG: About to call collect_with_app with output_dir: {collector.output_dir}")
                        print(f"DEBUG: Collector ADB command: {collector.adb_command}")
                        
                        status_callback("⏳ Waiting for you to press 'Export Data' in the APK...")
                        
                        # Install and launch APK, then monitor for data collection
                        print("DEBUG: Starting APK workflow with data monitoring...")
                        
                        # Install the APK
                        try:
                            print("DEBUG: About to call install_forensic_app...")
                            print(f"DEBUG: Current working directory: {os.getcwd()}")
                            print(f"DEBUG: Collector type: {type(collector)}")
                            print(f"DEBUG: Collector ADB command: {collector.adb_command}")
                            
                            # Add file logging for compiled app debugging
                            debug_log_path = os.path.join(os.getcwd(), "flask_debug.log")
                            with open(debug_log_path, "a") as debug_file:
                                debug_file.write(f"\n=== APK Installation Debug {datetime.now()} ===\n")
                                debug_file.write(f"Working directory: {os.getcwd()}\n")
                                debug_file.write(f"Collector type: {type(collector)}\n")
                                debug_file.write(f"ADB command: {collector.adb_command}\n")
                                debug_file.write("About to call install_forensic_app...\n")
                            
                            install_success = collector.install_forensic_app()
                            print(f"DEBUG: install_forensic_app returned: {install_success}")
                            
                            # Log the result
                            with open(debug_log_path, "a") as debug_file:
                                debug_file.write(f"install_forensic_app returned: {install_success}\n")
                                debug_file.write(f"Result type: {type(install_success)}\n")
                                debug_file.write(f"Result == True: {install_success == True}\n")
                                debug_file.write(f"Result is True: {install_success is True}\n")
                                debug_file.write(f"bool(Result): {bool(install_success)}\n")
                                
                        except Exception as e:
                            print(f"ERROR in install_forensic_app: {e}")
                            print(f"ERROR type: {type(e)}")
                            import traceback
                            print(f"ERROR traceback: {traceback.format_exc()}")
                            
                            # Log the error
                            debug_log_path = os.path.join(os.getcwd(), "flask_debug.log")
                            with open(debug_log_path, "a") as debug_file:
                                debug_file.write(f"ERROR: {e}\n")
                                debug_file.write(f"ERROR type: {type(e)}\n")
                                debug_file.write(f"ERROR traceback: {traceback.format_exc()}\n")
                                
                            install_success = False
                            
                        if not install_success:
                            status_callback("❌ Failed to install forensic APK")
                            data_successfully_collected = False
                        else:
                            status_callback("✅ APK installed successfully")
                            progress_callback(20)
                            
                            # Launch the APK
                            try:
                                launch_success = collector.launch_forensic_app()
                                print(f"DEBUG: launch_forensic_app returned: {launch_success}")
                            except Exception as e:
                                print(f"ERROR in launch_forensic_app: {e}")
                                launch_success = False
                                
                            if not launch_success:
                                status_callback("❌ Failed to launch forensic APK")
                                collector._get_app_debug_info()
                                collector._provide_troubleshooting_guidance()
                                data_successfully_collected = False
                            else:
                                # APK launched successfully - start monitoring workflow
                                status_callback("📱 APK launched - ready for investigation")
                                progress_callback(30)
                                
                                # Store collector instance for later pull operation
                                triage_manager.active_collectors = getattr(triage_manager, 'active_collectors', {})
                                triage_manager.active_collectors[operation_id] = collector
                                
                                # Guide user through the process
                                status_callback("🔘 APK is open and ready!")
                                status_callback("📱 Complete these steps on your device:")
                                status_callback("   1️⃣ Grant permissions (SMS, Contacts, Call Logs, etc.)")
                                status_callback("   2️⃣ Click 'Start Investigation' to begin data collection")
                                status_callback("⏳ Tool will automatically detect when data collection starts...")
                                progress_callback(40)
                                
                                # Start monitoring for JSON files (≥2 files indicates active collection)
                                monitoring_success = monitor_data_collection(collector, status_callback, progress_callback, timeout_minutes=10)
                                
                                if monitoring_success:
                                    # Data files detected - show pull prompt
                                    data_file_count = monitoring_success  # Returns the count of files found
                                    status_callback("✅ Investigation complete - data ready for extraction!")
                                    status_callback(f"� Detected {data_file_count} data files on device")
                                    progress_callback(70)
                                    
                                    # Mark operation as ready for pull
                                    status_queue.put({
                                        "type": "ready_for_pull", 
                                        "message": f"Investigation complete - {data_file_count} data files ready for extraction",
                                        "operation_id": operation_id,
                                        "data_file_count": data_file_count
                                    })
                                    
                                    # Don't continue with automatic processing
                                    data_successfully_collected = False  # Will be set by manual pull
                                else:
                                    status_callback("⚠️ Investigation timeout - no data files detected")
                                    status_callback("� Please ensure you clicked 'Start Investigation' on the device")
                                    status_callback("📱 You may need to grant additional permissions")
                                    data_successfully_collected = False
                            
                            # Check if data was pulled manually and transferred to local directory
                            apk_data_dir = f"{collector.output_dir}/apk_data_directory"
                            if not data_successfully_collected and os.path.exists(apk_data_dir):
                                # Check for meaningful data files locally
                                local_files = []
                                for f in os.listdir(apk_data_dir):
                                    if os.path.isfile(os.path.join(apk_data_dir, f)):
                                        if f not in ['collection_complete.json', 'collection_summary.txt']:
                                            local_files.append(f)
                                
                                if local_files:
                                    status_callback(f"📁 Found {len(local_files)} data files in local directory")
                                    data_successfully_collected = True
                            
                            # Final assessment based on data transfer results
                            if data_successfully_collected:
                                # Send APK removal prompt to frontend
                                status_queue.put({
                                    "type": "apk_removal_prompt",
                                    "message": "APK data collection complete. Would you like to remove the APK from the device?",
                                    "progress": 50
                                })
                                
                                # Wait for user decision on APK removal - DON'T continue here
                                status_callback("⏳ Waiting for APK removal decision...")
                                # The backup thread ends here - continuation happens in the APK removal endpoint
                                return
                            else:
                                # Check if we have collection markers but no data files
                                if os.path.exists(apk_data_dir) and any(f in os.listdir(apk_data_dir) 
                                                                       for f in ['collection_complete.json', 'collection_summary.txt']):
                                    status_callback("⚠️ Data collection completed but no meaningful data was found")
                                    status_callback("📋 Device may have no accessible data to extract")
                                else:
                                    status_callback("⚠️ Data transfer to output folder failed")
                                    status_callback("📋 Data may still be available on device for manual retrieval")
                                
                                # NEVER automatically remove APK - user should have control
                                status_callback("� Investigation complete - APK remains on device")
                                status_callback("💡 You can manually remove the APK from device settings if desired")
                                
                                progress_callback(100)
                                status_queue.put({
                                    "type": "complete",
                                    "success": False,
                                    "error": "Backup completed but no data was collected from device",
                                    "backup_path": collector.output_dir,
                                    "progress": 100
                                })
                                return
                            
                    except Exception as app_error:
                        error_msg = f"❌ APK collection error: {str(app_error)}"
                        print(f"DEBUG: Exception in collect_with_app: {app_error}")
                        print(f"DEBUG: Exception type: {type(app_error)}")
                        import traceback
                        print(f"DEBUG: Traceback: {traceback.format_exc()}")
                        status_callback(error_msg)
                        progress_callback(30)
                        status_queue.put({
                            "type": "complete",
                            "success": False,
                            "error": f"APK collection failed: {str(app_error)}",
                            "progress": 30
                        })
                        return
                else:
                    # Skip APK collection - go directly to ADB backup
                    status_callback("⚙️ Skipping APK collection - proceeding to ADB backup")
                    progress_callback(30)
                
                # Only run ADB backup if APK collection was skipped (use_apk=False)
                if not use_apk:
                    try:
                        status_callback("📦 Creating ADB backup...")
                        progress_callback(40)
                        
                        adb_success = collector.create_adb_backup(
                            include_apks=include_apks,
                            include_system=include_system,
                            include_shared=include_shared
                        )
                        
                        if adb_success:
                            status_callback("✅ ADB backup completed successfully")
                            progress_callback(100)
                            status_queue.put({
                                "type": "complete",
                                "success": True,
                                "backup_path": case_folder,
                                "message": "Android backup completed successfully",
                                "progress": 100
                            })
                        else:
                            status_callback("⚠️ ADB backup failed")
                            status_queue.put({
                                "type": "complete",
                                "success": False,
                                "error": "ADB backup failed",
                                "progress": 40
                            })
                            
                    except Exception as backup_error:
                        status_callback(f"❌ ADB backup error: {str(backup_error)}")
                        status_queue.put({
                            "type": "complete",
                            "success": False,
                            "error": f"ADB backup error: {str(backup_error)}",
                            "progress": 40
                        })
                    
            except Exception as e:
                error_msg = f"Android backup failed: {str(e)}"
                logger.error(error_msg)
                status_queue.put({"type": "error", "message": error_msg, "progress": 0})
                status_queue.put({
                    "type": "complete",
                    "success": False,
                    "error": error_msg,
                    "progress": 0
                })
        
        # Start the backup thread
        backup_thread_obj = threading.Thread(target=backup_thread)
        backup_thread_obj.daemon = True
        backup_thread_obj.start()
        
        # Store operation info
        triage_manager.operations[operation_id] = "android_backup"
        
        return jsonify({
            "success": True,
            "operation_id": operation_id,
            "message": "Android backup started"
        })
        
    except Exception as e:
        logger.error(f"Error starting Android backup: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/operations/android/pull', methods=['POST'])
def pull_android_data():
    """Pull data from Android device after APK collection"""
    try:
        data = request.get_json()
        operation_id = data.get('operation_id')
        
        if not operation_id:
            return jsonify({"success": False, "error": "Operation ID required"}), 400
        
        # Get the collector instance
        active_collectors = getattr(triage_manager, 'active_collectors', {})
        collector = active_collectors.get(operation_id)
        
        if not collector:
            return jsonify({"success": False, "error": "No active collector found for this operation"}), 404
        
        # Create a new status queue for pull updates
        pull_operation_id = f"pull_{operation_id}"
        status_queue = queue.Queue()
        triage_manager.status_queues[pull_operation_id] = status_queue
        
        def pull_thread():
            try:
                def status_callback(message):
                    status_queue.put({"type": "status", "message": message, "progress": None})
                    print(f"🔄 Pull status: {message}")
                
                status_callback("🔄 Starting data pull operation...")
                
                # Execute the pull
                pull_success = collector.pull_app_data()
                
                if pull_success:
                    status_callback("✅ Data successfully pulled from device!")
                    
                    # Verify pulled data
                    apk_data_dir = f"{collector.output_dir}/apk_data_directory"
                    if os.path.exists(apk_data_dir):
                        data_files = []
                        for f in os.listdir(apk_data_dir):
                            if os.path.isfile(os.path.join(apk_data_dir, f)):
                                if f not in ['collection_complete.json', 'collection_summary.txt']:
                                    data_files.append(f)
                        
                        if data_files:
                            status_callback(f"📁 Successfully transferred {len(data_files)} data files to output folder")
                            status_callback(f"💾 Data saved to: {apk_data_dir}")
                            
                            # Now we can show APK removal prompt
                            status_queue.put({
                                "type": "apk_removal_prompt",
                                "message": "Data pull complete. Would you like to remove the APK from the device?",
                                "progress": 100,
                                "original_operation_id": operation_id  # Include the original backup operation ID
                            })
                        else:
                            status_callback("⚠️ Pull completed but no meaningful data files found")
                    else:
                        status_callback("⚠️ Pull completed but output directory not found")
                else:
                    status_callback("❌ Data pull failed - see console for details")
                
                status_queue.put({"type": "complete", "message": "Pull operation finished"})
                
            except Exception as e:
                print(f"Error in pull thread: {e}")
                status_queue.put({
                    "type": "error", 
                    "message": f"Pull operation failed: {str(e)}"
                })
        
        # Start pull in background
        thread = threading.Thread(target=pull_thread, daemon=True)
        thread.start()
        
        return jsonify({
            "success": True,
            "pull_operation_id": pull_operation_id,
            "message": "Data pull started"
        })
        
    except Exception as e:
        logger.error(f"Error starting data pull: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/operations/android/apk-removal-decision', methods=['POST'])
def handle_apk_removal_decision():
    """Handle user decision about APK removal and continue with ADB backup"""
    try:
        data = request.get_json()
        operation_id = data.get('operation_id')
        remove_apk = data.get('remove_apk', False)
        
        print(f"DEBUG: APK removal decision - operation_id: {operation_id}, remove_apk: {remove_apk}")
        print(f"DEBUG: Available status_queues: {list(triage_manager.status_queues.keys())}")
        print(f"DEBUG: Available active_collectors: {list(getattr(triage_manager, 'active_collectors', {}).keys())}")
        print(f"DEBUG: Available backup_params: {list(getattr(triage_manager, 'backup_params', {}).keys())}")
        
        # Check if this is a pull operation ID, and if so, extract the original operation ID
        original_operation_id = operation_id
        if operation_id and operation_id.startswith('pull_'):
            original_operation_id = operation_id[5:]  # Remove 'pull_' prefix
            print(f"DEBUG: Extracted original operation ID: {original_operation_id}")
        else:
            print(f"DEBUG: Using operation ID as-is (no pull prefix): {original_operation_id}")
        
        # Check for valid operation ID in either pull operations or backup operations
        valid_operation = False
        status_queue = None
        
        if operation_id and operation_id in triage_manager.status_queues:
            # Direct match (pull operation)
            status_queue = triage_manager.status_queues[operation_id]
            valid_operation = True
            print(f"DEBUG: Found direct operation match: {operation_id}")
        elif original_operation_id and original_operation_id in triage_manager.status_queues:
            # Original backup operation
            status_queue = triage_manager.status_queues[original_operation_id]
            valid_operation = True
            print(f"DEBUG: Found original operation match: {original_operation_id}")
        else:
            print(f"DEBUG: No valid operation found for IDs: {operation_id}, {original_operation_id}")
        
        if not valid_operation:
            print(f"DEBUG: No valid operation found for IDs: {operation_id}, {original_operation_id}")
            
            # Try to find any matching operation with partial match
            all_keys = list(triage_manager.status_queues.keys())
            print(f"DEBUG: Searching in available keys: {all_keys}")
            
            # Look for any operation that contains our ID
            found_key = None
            for key in all_keys:
                if original_operation_id in key or key in original_operation_id:
                    found_key = key
                    print(f"DEBUG: Found partial match: {key} for {original_operation_id}")
                    break
            
            if found_key:
                status_queue = triage_manager.status_queues[found_key]
                valid_operation = True
                print(f"DEBUG: Using partial match operation: {found_key}")
            else:
                # Last resort: create a temporary status queue for this operation
                print(f"DEBUG: Creating temporary status queue for operation: {original_operation_id}")
                status_queue = queue.Queue()
                triage_manager.status_queues[original_operation_id] = status_queue
                valid_operation = True
        
        if not valid_operation:
            print(f"DEBUG: Invalid operation ID. Available operations: {list(triage_manager.status_queues.keys())}")
            return jsonify({"success": False, "error": "Invalid operation ID"}), 400
        
        # Clear the APK removal prompt from persistent updates
        if hasattr(triage_manager, 'persistent_updates'):
            for op_id in [operation_id, original_operation_id]:
                if op_id in triage_manager.persistent_updates:
                    # Remove APK removal prompt from persistent updates since user has made a decision
                    triage_manager.persistent_updates[op_id] = [
                        update for update in triage_manager.persistent_updates[op_id] 
                        if update.get("type") != "apk_removal_prompt"
                    ]
        
        def status_callback(message):
            status_queue.put({"type": "status", "message": message, "progress": None})
        
        def progress_callback(percentage):
            status_queue.put({"type": "progress", "message": f"Progress: {percentage}%", "progress": percentage})
        
        # Handle APK removal in background thread
        def continue_backup():
            try:
                # Get stored backup parameters using original operation ID
                backup_params = getattr(triage_manager, 'backup_params', {}).get(original_operation_id, {})
                
                # Get the stored collector instance from the original backup operation
                collector = None
                if hasattr(triage_manager, 'active_collectors') and original_operation_id in triage_manager.active_collectors:
                    collector = triage_manager.active_collectors[original_operation_id]
                    print(f"DEBUG: Retrieved stored collector for operation {original_operation_id}")
                else:
                    # Fallback: create new collector
                    collector = ArsenicTriageCollector(adb_command=get_adb_command())
                    print(f"DEBUG: Created fallback collector for operation {original_operation_id}")
                
                case_number = backup_params.get('case_number', 'Unknown')
                output_dir = backup_params.get('output_directory', '/tmp')
                
                # Use the stored case folder path from the original backup thread
                case_folder = backup_params.get('case_folder')
                if not case_folder or not os.path.exists(case_folder):
                    # Fallback: look for existing folder or create new one
                    if output_dir and case_number:
                        # Look for existing Android_Backup folders for this case
                        backup_folders = []
                        if os.path.exists(output_dir):
                            for item in os.listdir(output_dir):
                                if item.startswith(f"Android_Backup_{case_number}_"):
                                    backup_folders.append(item)
                        
                        if backup_folders:
                            # Use the most recent folder (sort by name which includes timestamp)
                            backup_folders.sort(reverse=True)
                            case_folder = os.path.join(output_dir, backup_folders[0])
                        else:
                            # Create new folder with current timestamp if none found
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                            case_folder = os.path.join(output_dir, f"Android_Backup_{case_number}_{timestamp}")
                            os.makedirs(case_folder, exist_ok=True)
                    else:
                        # Fallback
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        case_folder = os.path.join('/tmp', f"Android_Backup_{case_number}_{timestamp}")
                        os.makedirs(case_folder, exist_ok=True)
                
                collector.output_dir = case_folder
                
                if remove_apk:
                    status_callback("🗑️ Removing forensic APK from device...")
                    try:
                        result = collector._run_subprocess([collector.adb_command, 'uninstall', collector.app_package], timeout=30)
                        if result.returncode == 0:
                            status_callback("✅ Forensic APK removed from device")
                        else:
                            status_callback("⚠️ Could not remove APK (may not be installed)")
                    except Exception as e:
                        status_callback(f"⚠️ APK removal failed: {str(e)}")
                else:
                    status_callback("📱 Forensic APK left on device as requested")
                
                progress_callback(60)
                
                # Check if ADB backup was requested by looking at original checkbox states
                # If user unchecked all ADB options and only left APK collection, skip ADB backup
                adb_options_selected = (
                    backup_params.get('original_backup_apps', False) or 
                    backup_params.get('original_backup_system', False) or 
                    backup_params.get('original_backup_shared', False) or
                    backup_params.get('original_backup_all', False)
                )
                
                print(f"DEBUG: ADB backup needed: {adb_options_selected}")
                print(f"DEBUG: Original checkbox states - apps: {backup_params.get('original_backup_apps')}, system: {backup_params.get('original_backup_system')}, shared: {backup_params.get('original_backup_shared')}, all: {backup_params.get('original_backup_all')}")
                
                if adb_options_selected:
                    # Continue with ADB backup using stored parameters
                    status_callback("📦 Starting ADB backup process...")
                    progress_callback(70)
                    
                    adb_success = collector.create_adb_backup(
                        include_apks=backup_params.get('include_apks', True),
                        include_system=backup_params.get('include_system', False),
                        include_shared=backup_params.get('include_shared', True)
                    )
                    
                    if adb_success:
                        status_callback("✅ ADB backup completed successfully")
                        status_callback("🎉 Complete Android backup process finished!")
                        progress_callback(100)
                        status_queue.put({
                            "type": "complete",
                            "success": True,
                            "backup_path": case_folder,
                            "message": "Complete Android backup process (APK + ADB) finished successfully",
                            "progress": 100
                        })
                    else:
                        status_callback("⚠️ ADB backup failed")
                        status_queue.put({
                            "type": "complete", 
                            "success": False,
                            "error": "ADB backup failed after APK collection",
                            "progress": 70
                        })
                else:
                    # Only APK collection was requested, so we're done
                    status_callback("🎉 APK investigation process completed!")
                    progress_callback(100)
                    status_queue.put({
                        "type": "complete",
                        "success": True,
                        "backup_path": case_folder,
                        "message": "APK investigation completed successfully",
                        "progress": 100
                    })
                
                # Clean up stored parameters
                if operation_id in triage_manager.backup_params:
                    del triage_manager.backup_params[operation_id]
                    
            except Exception as e:
                error_msg = f"Error continuing backup: {str(e)}"
                status_callback(error_msg)
                status_queue.put({
                    "type": "complete",
                    "success": False,
                    "error": error_msg,
                    "progress": 60
                })
        
        # Start continuation in background
        threading.Thread(target=continue_backup, daemon=True).start()
        
        # Ensure operation type is preserved for the original operation
        if original_operation_id not in triage_manager.operations:
            triage_manager.operations[original_operation_id] = "android_backup"
            print(f"DEBUG: Restored operation type for {original_operation_id}")
        
        return jsonify({"success": True, "message": "APK removal decision processed"})
        
    except Exception as e:
        logger.error(f"Error handling APK removal decision: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/debug/operations', methods=['GET'])
def debug_operations():
    """Debug endpoint to show current operations"""
    try:
        return jsonify({
            "status_queues": list(triage_manager.status_queues.keys()),
            "active_collectors": list(getattr(triage_manager, 'active_collectors', {}).keys()),
            "backup_params": list(getattr(triage_manager, 'backup_params', {}).keys()),
            "persistent_updates": list(getattr(triage_manager, 'persistent_updates', {}).keys()),
            "operations_dict": dict(triage_manager.operations)  # Show actual operation types
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/operations/parse', methods=['POST'])
def start_parsing():
    """Start backup parsing"""
    try:
        data = request.get_json()
        backup_file = data.get('backup_file')
        parser_type = data.get('parser_type', 'auto')
        
        if not backup_file:
            return jsonify({"success": False, "error": "Backup file required"}), 400
        
        if not os.path.exists(backup_file):
            return jsonify({"success": False, "error": "Backup file not found"}), 400
        
        # Start parsing in background thread
        operation_id = f"parse_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        def parse_thread():
            try:
                # Set up status queue for this operation
                status_queue = queue.Queue()
                triage_manager.status_queues[operation_id] = status_queue
                
                def status_callback(message):
                    status_queue.put({"type": "status", "message": message, "progress": None})
                
                def progress_callback(progress):
                    # Don't send generic "Parsing..." messages, just progress updates
                    status_queue.put({"type": "progress", "message": "", "progress": progress})
                
                # Mock parsing process for now
                status_callback("Starting backup parsing...")
                progress_callback(10)
                
                time.sleep(1)
                status_callback("Analyzing backup structure...")
                progress_callback(30)
                
                time.sleep(1)
                status_callback("Extracting data...")
                progress_callback(60)
                
                time.sleep(2)
                status_callback("Finalizing results...")
                progress_callback(80)
                
                time.sleep(1)
                status_callback("Parsing completed successfully!")
                progress_callback(100)
                
                # Mock results
                results = f"Parsing Results for: {os.path.basename(backup_file)}\n"
                results += f"Parser Type: {parser_type}\n"
                results += f"File Size: {os.path.getsize(backup_file)} bytes\n"
                results += f"Parsed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                results += "This is a mock parsing result. In the real implementation,\n"
                results += "this would contain the actual parsed backup data."
                
                status_queue.put({
                    "type": "complete", 
                    "success": True,
                    "message": "Parsing completed successfully",
                    "progress": 100,
                    "results": results
                })
                
            except Exception as e:
                logger.error(f"Parsing error: {e}")
                status_queue.put({
                    "type": "complete",
                    "success": False,
                    "error": str(e),
                    "progress": 0
                })
        
        threading.Thread(target=parse_thread, daemon=True).start()
        triage_manager.operations[operation_id] = "parse"
        
        return jsonify({
            "success": True,
            "operation_id": operation_id,
            "message": "Parsing started"
        })
        
    except Exception as e:
        logger.error(f"Error starting parsing: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/operations/status')
def operations_status():
    """Get status of all operations"""
    try:
        print("DEBUG: operations_status called")
        print(f"DEBUG: Current operations: {list(triage_manager.operations.keys())}")
        print(f"DEBUG: Current status queues: {list(triage_manager.status_queues.keys())}")
        
        all_operations = []
        completed_operations = []
        
        # Process all status queues
        for operation_id, queue_obj in list(triage_manager.status_queues.items()):
            operation_status = {
                "operation_id": operation_id,
                "type": triage_manager.operations.get(operation_id, "unknown"),
                "updates": []
            }
            
            # For backup operations, we need to maintain state between calls
            # Store updates that need to persist (like APK removal prompts) 
            if not hasattr(triage_manager, 'persistent_updates'):
                triage_manager.persistent_updates = {}
            if operation_id not in triage_manager.persistent_updates:
                triage_manager.persistent_updates[operation_id] = []
            
            # Get all pending updates from queue
            new_updates = []
            while not queue_obj.empty():
                try:
                    update = queue_obj.get_nowait()
                    new_updates.append(update)
                    print(f"DEBUG: Processing update: {update}")
                    
                    # If this is a completion update, mark it
                    if update.get("type") == "complete":
                        operation_status["completed"] = True
                        operation_status["success"] = update.get("success", False)
                        operation_status["error"] = update.get("error")
                        
                        # Debug the result data - check both "result" and "results"
                        result_data = update.get("results") or update.get("result")
                        print(f"DEBUG: Result data type: {type(result_data)}")
                        print(f"DEBUG: Result data keys: {result_data.keys() if isinstance(result_data, dict) else 'Not a dict'}")
                        if isinstance(result_data, dict):
                            for key, value in result_data.items():
                                print(f"DEBUG: {key}: {type(value)} with length {len(value) if hasattr(value, '__len__') else 'N/A'}")
                        
                        operation_status["results"] = result_data  # Map to "results" for frontend
                        operation_status["structured_data"] = update.get("structured_data")
                        operation_status["progress"] = update.get("progress", 0)
                        operation_status["status"] = update.get("message", "Completed")
                        
                        # Mark for cleanup after sending to frontend
                        completed_operations.append(operation_id)
                except queue.Empty:
                    break
            
            # Add new updates to persistent storage
            triage_manager.persistent_updates[operation_id].extend(new_updates)
            
            # For APK removal prompts, keep them until acted upon
            current_updates = triage_manager.persistent_updates[operation_id].copy()
            
            # Check if there's an active APK removal prompt
            has_apk_prompt = any(update.get("type") == "apk_removal_prompt" for update in current_updates)
            
            # Send all accumulated updates to frontend
            operation_status["updates"] = current_updates
            
            # Set current status from latest update
            if current_updates:
                latest = current_updates[-1]
                operation_status["progress"] = latest.get("progress", 0)
                operation_status["status"] = latest.get("message", "Operation in progress")
                print(f"DEBUG: Operation {operation_id} status: {operation_status['status']}")
                print(f"DEBUG: Has APK prompt: {has_apk_prompt}")
            
            all_operations.append(operation_status)
        
        print(f"DEBUG: Returning {len(all_operations)} operations")
        
        # Clean up completed operations after sending response
        for op_id in completed_operations:
            print(f"DEBUG: Cleaning up completed operation {op_id}")
            if op_id in triage_manager.operations:
                del triage_manager.operations[op_id]
            if op_id in triage_manager.status_queues:
                del triage_manager.status_queues[op_id]
        
        return jsonify({
            "success": True,
            "operations": all_operations
        })
        
    except Exception as e:
        logger.error(f"Error getting operations status: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
    try:
        data = request.get_json()
        profile = data.get('profile', 'basic')
        
        if not triage_manager.output_directory:
            return jsonify({"success": False, "error": "Output directory not set"}), 400
        
        operation_id = f"android_triage_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        def triage_thread():
            try:
                status_queue = queue.Queue()
                triage_manager.status_queues[operation_id] = status_queue
                
                def status_callback(message):
                    status_queue.put({"type": "status", "message": message})
                
                # Set up status callback
                triage_manager.android_triage_handler.status_callback = status_callback
                
                # Perform triage
                result = triage_manager.android_triage_handler.perform_triage(
                    output_dir=triage_manager.output_directory,
                    case_number=triage_manager.case_number,
                    profile=profile
                )
                
                status_queue.put({
                    "type": "complete", 
                    "success": True,
                    "result": result,
                    "message": "Android triage completed successfully"
                })
                
            except Exception as e:
                logger.error(f"Android triage error: {e}")
                status_queue.put({
                    "type": "complete",
                    "success": False,
                    "error": str(e)
                })
        
        threading.Thread(target=triage_thread, daemon=True).start()
        triage_manager.operations[operation_id] = "android_triage"
        
        return jsonify({
            "success": True,
            "operation_id": operation_id,
            "message": "Android triage started"
        })
        
    except Exception as e:
        logger.error(f"Error starting Android triage: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/android/triage/status/<operation_id>')
def get_android_triage_status(operation_id):
    """Get Android triage status"""
    try:
        if operation_id not in triage_manager.status_queues:
            return jsonify({"error": "Operation not found"}), 404
        
        status_queue = triage_manager.status_queues[operation_id]
        updates = []
        
        while not status_queue.empty():
            try:
                update = status_queue.get_nowait()
                updates.append(update)
            except queue.Empty:
                break
        
        return jsonify({
            "success": True,
            "updates": updates
        })
        
    except Exception as e:
        logger.error(f"Error getting triage status: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/ios/backup/check-encryption', methods=['POST'])
def check_ios_backup_encryption():
    """Check if an iOS backup is encrypted"""
    try:
        data = request.get_json()
        backup_path = data.get('backup_path')
        
        if not backup_path or not os.path.exists(backup_path):
            return jsonify({"success": False, "error": "Invalid backup path"}), 400
        
        # Check for required plist files
        info_plist_path = os.path.join(backup_path, 'Info.plist')
        manifest_plist_path = os.path.join(backup_path, 'Manifest.plist')
        
        if not os.path.exists(info_plist_path):
            return jsonify({"success": False, "error": "Info.plist not found - invalid backup folder"}), 400
        
        if not os.path.exists(manifest_plist_path):
            return jsonify({"success": False, "error": "Manifest.plist not found - invalid backup folder"}), 400
        
        # Import plistlib
        import plistlib
        
        # Check encryption status
        encryption_status = {
            'is_encrypted': False,
            'requires_password': False,
            'valid_backup': True
        }
        
        try:
            with open(manifest_plist_path, 'rb') as plist_file:
                manifest_data = plistlib.load(plist_file)
                encryption_status['is_encrypted'] = manifest_data.get('IsEncrypted', False)
                encryption_status['requires_password'] = encryption_status['is_encrypted']
        except Exception as e:
            return jsonify({"success": False, "error": f"Error reading Manifest.plist: {str(e)}"}), 400
        
        # Get device info for confirmation
        device_info = {}
        try:
            with open(info_plist_path, 'rb') as plist_file:
                plist_data = plistlib.load(plist_file)
                
                # Log all available plist keys for debugging
                print("Available plist keys:", list(plist_data.keys()))
                
                device_info = {
                    'Device Name': plist_data.get('Device Name', ''),
                    'Display Name': plist_data.get('Display Name', ''),
                    'Product Version': plist_data.get('Product Version', ''),
                    'Product Type': plist_data.get('Product Type', ''),
                    'Serial Number': plist_data.get('Serial Number', ''),
                    'IMEI': plist_data.get('IMEI', ''),
                    'ICCID': plist_data.get('ICCID', ''),
                    'UniqueDeviceID': plist_data.get('UniqueDeviceID', ''),
                    'UDID': plist_data.get('UDID', ''),
                    'Phone Number': plist_data.get('Phone Number', ''),
                    'Target Identifier': plist_data.get('Target Identifier', ''),
                    'Target Type': plist_data.get('Target Type', ''),
                    'Unique Identifier': plist_data.get('Unique Identifier', ''),
                    'Build Version': plist_data.get('Build Version', ''),
                    'Last Backup Date': str(plist_data.get('Last Backup Date', '')) if plist_data.get('Last Backup Date') else ''
                }
                
                # Log device info values for debugging
                print("Device info extracted:")
                for key, value in device_info.items():
                    if value:  # Only log non-empty values
                        print(f"  {key}: {value}")
                
        except Exception as e:
            print(f"Error parsing Info.plist: {e}")
            pass
        
        return jsonify({
            "success": True,
            "encryption_status": encryption_status,
            "device_info": device_info
        })
        
    except Exception as e:
        logger.error(f"Error checking backup encryption: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/android/backup/check-encryption', methods=['POST'])
def check_android_backup_encryption():
    """Check if an Android backup is encrypted and get basic info"""
    try:
        data = request.get_json()
        backup_path = data.get('backup_path')
        
        if not backup_path or not os.path.exists(backup_path):
            return jsonify({"success": False, "error": "Invalid backup path"}), 400
        
        # Import the backup analyzer
        from src.utils.backup_analyzer import AndroidBackupAnalyzer
        
        analyzer = AndroidBackupAnalyzer()
        analysis_result = analyzer.analyze_backup_file(backup_path)
        
        if analysis_result.get('error'):
            return jsonify({
                "success": False, 
                "error": analysis_result['error']
            }), 400
        
        return jsonify({
            "success": True,
            "is_valid": analysis_result['is_valid'],
            "is_encrypted": analysis_result['is_encrypted'],
            "version": analysis_result['version'],
            "compression": analysis_result['compression'],
            "file_size": os.path.getsize(backup_path)
        })
        
    except Exception as e:
        logger.error(f"Error checking Android backup encryption: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/ios/backup/parse', methods=['POST'])
def parse_ios_backup():
    """Parse an iOS backup folder"""
    try:
        data = request.get_json()
        backup_path = data.get('backup_path')
        password = data.get('password', '')
        enable_taxonomy = data.get('enable_taxonomy', False)
        taxonomy_type = data.get('taxonomy_type')
        
        # Update case info from request
        if 'case_number' in data:
            triage_manager.case_number = data['case_number']
        if 'output_directory' in data:
            triage_manager.output_directory = data['output_directory']
        
        if not backup_path or not os.path.exists(backup_path):
            return jsonify({"success": False, "error": "Invalid backup path"}), 400
            
        if not triage_manager.case_number or not triage_manager.output_directory:
            return jsonify({"success": False, "error": "Case number and output directory are required"}), 400
        
        operation_id = f"ios_parse_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        def parse_thread():
            try:
                status_queue = queue.Queue()
                triage_manager.status_queues[operation_id] = status_queue
                
                def status_callback(message):
                    status_queue.put({"type": "status", "message": message})
                
                status_callback("Starting iOS backup parsing...")
                
                # Create case-specific output directory
                case_output_dir = os.path.join(triage_manager.output_directory, f"Case_{triage_manager.case_number}")
                if not os.path.exists(case_output_dir):
                    os.makedirs(case_output_dir, exist_ok=True)
                    status_callback(f"Created output directory: {case_output_dir}")
                
                # Parse the backup with taxonomy options
                taxonomy_target = None
                if enable_taxonomy and taxonomy_type:
                    try:
                        taxonomy_id = int(taxonomy_type)
                        # Import the taxonomy dictionary to get the description
                        from src.parser.backup_parser import taxonomy_Dict
                        taxonomy_description = taxonomy_Dict.get(taxonomy_id, f"unknown_{taxonomy_id}")
                        taxonomy_target = taxonomy_id  # Pass the numeric ID for filtering
                        status_callback(f"Taxonomy analysis enabled - searching for: {taxonomy_description} (ID: {taxonomy_id})")
                    except ValueError:
                        status_callback("Warning: Invalid taxonomy type, proceeding without taxonomy analysis")
                
                result = parse_backup(
                    backup_path=backup_path,
                    password=password,
                    status_callback=status_callback,
                    output_dir=case_output_dir,
                    taxonomy_target=taxonomy_target
                )
                
                status_queue.put({
                    "type": "complete", 
                    "success": True,
                    "result": result,
                    "message": "iOS backup parsing completed successfully"
                })
                
            except Exception as e:
                logger.error(f"iOS parse error: {e}")
                status_queue.put({
                    "type": "complete",
                    "success": False,
                    "error": str(e)
                })
        
        threading.Thread(target=parse_thread, daemon=True).start()
        triage_manager.operations[operation_id] = "ios_parse"
        
        return jsonify({
            "success": True,
            "operation_id": operation_id,
            "message": "iOS backup parsing started"
        })
        
    except Exception as e:
        logger.error(f"Error starting iOS backup parse: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/logs')
def get_logs():
    """Get application logs"""
    # This is a simplified version - in production you'd want proper log file handling
    return jsonify({
        "logs": [
            {"timestamp": datetime.now().isoformat(), "level": "INFO", "message": "Application running"}
        ]
    })

def read_ios_csv_with_header(file_path):
    """
    Read iOS CSV files that have a header section with device info before the actual CSV data.
    These files typically have:
    - Report title
    - Device information section
    - Empty line
    - CSV headers and data
    """
    import pandas as pd
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Find where the actual CSV data starts
    csv_start_line = 0
    for i, line in enumerate(lines):
        # Look for a line that looks like CSV headers (contains commas and typical CSV column names)
        if ',' in line and any(keyword in line.lower() for keyword in ['date', 'time', 'name', 'contact', 'message', 'id']):
            csv_start_line = i
            break
    
    if csv_start_line == 0:
        # If no clear header found, try to find first line with multiple commas
        for i, line in enumerate(lines):
            if line.count(',') >= 3:  # Assume CSV data has at least 4 columns
                csv_start_line = i
                break
    
    # Read the CSV data starting from the detected line
    from io import StringIO
    csv_content = ''.join(lines[csv_start_line:])
    
    # Handle potential encoding issues and empty lines
    csv_content = csv_content.strip()
    if not csv_content:
        # Return empty DataFrame with proper structure
        return pd.DataFrame()
    
    try:
        df = pd.read_csv(StringIO(csv_content))
        return df
    except Exception as e:
        # If parsing fails, try with different parameters
        try:
            # Try with error handling for bad lines
            df = pd.read_csv(StringIO(csv_content), on_bad_lines='skip')
            return df
        except Exception as e2:
            # Last resort: return basic structure
            logger.warning(f"Could not parse CSV file {file_path}: {e2}")
            return pd.DataFrame()

@app.route('/api/ios/reports/csv-data', methods=['GET'])
def get_ios_csv_data():
    """
    Get CSV data for iOS reports with pagination, sorting, and search
    """
    try:
        import pandas as pd
        import glob
        
        # Get query parameters
        data_type = request.args.get('type', 'sms')  # sms, contacts, call_history, etc.
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 100))
        search = request.args.get('search', '')
        sort_column = request.args.get('sort_column', '')
        sort_direction = request.args.get('sort_direction', 'asc')
        case_directory = request.args.get('case_directory', '')
        
        if not case_directory:
            return jsonify({"success": False, "error": "Case directory not provided"}), 400
            
        # Map data types to CSV file patterns (matching actual iOS parsing output)
        csv_patterns = {
            'sms': 'Messages.csv',  # Updated to static filename
            'contacts': 'Contacts.csv', 
            'call_history': 'Call_History.csv',
            'safari_history': 'Safari_History.csv',
            'notes': 'Notes.csv',
            'accounts': 'Accounts.csv',
            'data_usage': 'Data_Usage.csv',
            'permissions': 'App_Permissions.csv',
            'interactions': 'InteractionC.csv'  # Updated to static filename
        }
        
        if data_type not in csv_patterns:
            return jsonify({"success": False, "error": f"Invalid data type: {data_type}"}), 400
            
        # Find the CSV file for this data type
        reports_dir = os.path.join(case_directory, 'Reports')
        if not os.path.exists(reports_dir):
            return jsonify({"success": False, "error": "Reports directory not found"}), 404
            
        csv_file_path = os.path.join(reports_dir, csv_patterns[data_type])
        
        if not os.path.exists(csv_file_path):
            return jsonify({
                "success": True, 
                "data": [], 
                "total_records": 0,
                "page": page,
                "per_page": per_page,
                "total_pages": 0
            })
            
        # Use the found file
        latest_csv = csv_file_path
        
        # Read CSV file (skip header section for iOS reports)
        try:
            df = read_ios_csv_with_header(latest_csv)
        except Exception as e:
            return jsonify({"success": False, "error": f"Error reading CSV file: {str(e)}"}), 500
            
        # Apply search filter if provided
        if search:
            # Search across all string columns
            string_columns = df.select_dtypes(include=['object']).columns
            search_mask = df[string_columns].astype(str).apply(
                lambda x: x.str.contains(search, case=False, na=False)
            ).any(axis=1)
            df = df[search_mask]
            
        # Apply sorting if provided
        if sort_column and sort_column in df.columns:
            ascending = sort_direction.lower() == 'asc'
            df = df.sort_values(by=sort_column, ascending=ascending)
            
        # Calculate pagination
        total_records = len(df)
        total_pages = (total_records + per_page - 1) // per_page
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        
        # Get page data
        page_data = df.iloc[start_idx:end_idx]
        
        # Convert to dict and handle NaN values
        records = page_data.fillna('').to_dict('records')
        
        # Get column info for frontend table setup
        columns = [{'name': col, 'type': str(df[col].dtype)} for col in df.columns]
        
        return jsonify({
            "success": True,
            "data": records,
            "columns": columns,
            "total_records": total_records,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "file_path": latest_csv
        })
        
    except Exception as e:
        logger.error(f"Error getting CSV data: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/ios/reports/available', methods=['GET'])
def get_available_ios_reports():
    """
    Get list of available CSV reports for a case
    """
    try:
        import glob
        
        case_directory = request.args.get('case_directory', '')
        if not case_directory:
            return jsonify({"success": False, "error": "Case directory not provided"}), 400
            
        reports_dir = os.path.join(case_directory, 'Reports')
        if not os.path.exists(reports_dir):
            return jsonify({"success": True, "reports": []})
            
        # Map CSV files to display names (matching actual iOS parsing output)
        report_types = {
            'Messages.csv': {'type': 'sms', 'name': 'SMS Messages', 'icon': '💬'},
            'Contacts.csv': {'type': 'contacts', 'name': 'Contacts', 'icon': '👥'},
            'Call_History.csv': {'type': 'call_history', 'name': 'Call History', 'icon': '📞'},
            'Safari_History.csv': {'type': 'safari_history', 'name': 'Safari History', 'icon': '🌐'},
            'Notes.csv': {'type': 'notes', 'name': 'Notes', 'icon': '📝'},
            'Accounts.csv': {'type': 'accounts', 'name': 'Accounts', 'icon': '👤'},
            'Data_Usage.csv': {'type': 'data_usage', 'name': 'Data Usage', 'icon': '📊'},
            'App_Permissions.csv': {'type': 'permissions', 'name': 'App Permissions', 'icon': '🔒'},
            'InteractionC.csv': {'type': 'interactions', 'name': 'User Interactions', 'icon': '👆'}
        }
        
        available_reports = []
        
        for filename, info in report_types.items():
            csv_file = os.path.join(reports_dir, filename)
            if os.path.exists(csv_file):
                file_size = os.path.getsize(csv_file)
                file_time = datetime.fromtimestamp(os.path.getctime(csv_file))
                
                # Get record count by reading the CSV properly (handling iOS format)
                try:
                    df = read_ios_csv_with_header(csv_file)
                    record_count = len(df)
                except:
                    record_count = 0
                    
                available_reports.append({
                    'type': info['type'],
                    'name': info['name'],
                    'icon': info['icon'],
                    'file_path': csv_file,
                    'file_size': file_size,
                    'created_time': file_time.isoformat(),
                    'record_count': record_count
                })
                
        return jsonify({"success": True, "reports": available_reports})
        
    except Exception as e:
        logger.error(f"Error getting available reports: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/image/exif', methods=['POST'])
def get_image_exif():
    """Extract EXIF data from an image file"""
    try:
        data = request.get_json()
        if not data or 'image_path' not in data:
            return jsonify({"success": False, "error": "image_path required"}), 400
        
        image_path = data['image_path']
        
        # Ensure file exists
        if not os.path.exists(image_path):
            return jsonify({"success": False, "error": "Image file not found"}), 404
            
        # Import the EXIF extraction functions
        import sys
        sys.path.append(os.path.join(project_root, 'src', 'parser'))
        from backup_parser import extract_image_exif, extract_heic_exif
        
        # Determine file type and extract EXIF accordingly
        file_extension = image_path.lower().split('.')[-1]
        
        if file_extension in ['heic', 'heif']:
            exif_data = extract_heic_exif(image_path)
        else:
            exif_data = extract_image_exif(image_path)
        
        # Ensure all values are JSON serializable
        def make_serializable(obj):
            if isinstance(obj, bytes):
                try:
                    return obj.decode('utf-8')
                except:
                    return str(obj)
            elif hasattr(obj, 'numerator') and hasattr(obj, 'denominator'):
                if obj.denominator != 0:
                    return float(obj.numerator) / float(obj.denominator)
                else:
                    return float(obj.numerator)
            elif isinstance(obj, dict):
                return {k: make_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [make_serializable(item) for item in obj]
            else:
                return str(obj) if not isinstance(obj, (str, int, float, bool, type(None))) else obj
        
        serializable_exif = make_serializable(exif_data)
        
        return jsonify({
            "success": True, 
            "exif_data": serializable_exif,
            "file_path": image_path,
            "file_type": file_extension.upper()
        })
        
    except Exception as e:
        logger.error(f"Error extracting EXIF data: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/image/thumbnail', methods=['POST'])
def generate_thumbnail():
    """Generate a thumbnail for HEIC images"""
    try:
        data = request.get_json()
        if not data or 'image_path' not in data:
            return jsonify({"success": False, "error": "image_path required"}), 400
        
        image_path = data['image_path']
        
        # Ensure file exists
        if not os.path.exists(image_path):
            return jsonify({"success": False, "error": "Image file not found"}), 404
            
        # Get file extension
        file_extension = image_path.lower().split('.')[-1]
        
        # Create thumbnails directory if it doesn't exist
        thumbnails_dir = os.path.join(project_root, 'thumbnails')
        os.makedirs(thumbnails_dir, exist_ok=True)
        
        # Generate thumbnail filename
        import hashlib
        file_hash = hashlib.md5(image_path.encode()).hexdigest()
        thumbnail_path = os.path.join(thumbnails_dir, f"{file_hash}.jpg")
        
        # Check if thumbnail already exists
        if os.path.exists(thumbnail_path):
            return send_file(thumbnail_path, mimetype='image/jpeg')
        
        # Generate thumbnail for HEIC files
        if file_extension in ['heic', 'heif']:
            try:
                # Try pillow-heif first
                from pillow_heif import register_heif_opener
                from PIL import Image
                
                register_heif_opener()
                
                # Open HEIC file and create thumbnail
                img = Image.open(image_path)
                
                # Create thumbnail (max 300x300 while maintaining aspect ratio)
                img.thumbnail((300, 300), Image.Resampling.LANCZOS)
                
                # Convert to RGB if necessary and save as JPEG
                if img.mode in ('RGBA', 'LA', 'P'):
                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    rgb_img.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                    img = rgb_img
                elif img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')
                
                img.save(thumbnail_path, 'JPEG', quality=85, optimize=True)
                
                return send_file(thumbnail_path, mimetype='image/jpeg')
                
            except ImportError:
                # Fallback to pyheif
                try:
                    import pyheif
                    from PIL import Image
                    
                    heif_file = pyheif.read(image_path)
                    image = Image.frombytes(
                        heif_file.mode,
                        heif_file.size,
                        heif_file.data,
                        "raw",
                        heif_file.mode,
                        heif_file.stride,
                    )
                    
                    # Create thumbnail
                    image.thumbnail((300, 300), Image.Resampling.LANCZOS)
                    
                    # Convert to RGB and save as JPEG
                    if image.mode in ('RGBA', 'LA', 'P'):
                        rgb_img = Image.new('RGB', image.size, (255, 255, 255))
                        if image.mode == 'P':
                            image = image.convert('RGBA')
                        rgb_img.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
                        image = rgb_img
                    elif image.mode not in ('RGB', 'L'):
                        image = image.convert('RGB')
                    
                    image.save(thumbnail_path, 'JPEG', quality=85, optimize=True)
                    
                    return send_file(thumbnail_path, mimetype='image/jpeg')
                    
                except ImportError:
                    return jsonify({"success": False, "error": "HEIC libraries not available"}), 500
        else:
            # For non-HEIC images, create thumbnail using PIL
            try:
                from PIL import Image
                
                img = Image.open(image_path)
                img.thumbnail((300, 300), Image.Resampling.LANCZOS)
                
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'LA', 'P'):
                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    rgb_img.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                    img = rgb_img
                elif img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')
                
                img.save(thumbnail_path, 'JPEG', quality=85, optimize=True)
                
                return send_file(thumbnail_path, mimetype='image/jpeg')
                
            except Exception as img_error:
                logger.error(f"Error creating thumbnail for {image_path}: {img_error}")
                return jsonify({"success": False, "error": f"Failed to create thumbnail: {str(img_error)}"}), 500
        
    except Exception as e:
        logger.error(f"Error generating thumbnail: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


# Processing endpoints for backup analysis
@app.route('/api/process_backup', methods=['POST'])
def process_backup():
    """Process Android backup files and APK data to generate reports"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
            
        ab_file = data.get('ab_file', '')
        apk_dir = data.get('apk_dir', '')
        output_dir = data.get('output_dir', '')
        case_number = data.get('case_number', '')
        backup_password = data.get('backup_password', None)  # New password parameter
        
        # Processing options
        extract_ab = data.get('extract_ab', False)
        parse_apk = data.get('parse_apk', False)
        generate_report = data.get('generate_report', False)
        create_timeline = data.get('create_timeline', False)
        
        # Validate inputs
        if not output_dir:
            return jsonify({"success": False, "error": "Output directory is required"}), 400
            
        # Check if at least one valid input is provided
        valid_ab_file = ab_file and os.path.exists(ab_file)
        valid_apk_dir = apk_dir and os.path.exists(apk_dir)
        
        if not (valid_ab_file or valid_apk_dir):
            return jsonify({"success": False, "error": "At least one valid input is required: Android backup (.ab) file or APK data directory"}), 400
            
        # Only validate specific requirements if the corresponding option is selected
        if extract_ab and not valid_ab_file:
            return jsonify({"success": False, "error": "Valid Android backup (.ab) file is required for extraction"}), 400
            
        if parse_apk and not valid_apk_dir:
            return jsonify({"success": False, "error": "Valid APK data directory is required for parsing"}), 400
            
        # Auto-enable processing options based on available valid inputs
        if not extract_ab and not parse_apk:
            if valid_ab_file:
                extract_ab = True
                logger.info("Auto-enabled AB extraction based on provided AB file")
            if valid_apk_dir:
                parse_apk = True
                logger.info("Auto-enabled APK parsing based on provided APK directory")
        
        # Create timestamped analysis directory
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        analysis_dir = os.path.join(output_dir, f"Android_Analysis_{case_number}_{timestamp}")
        os.makedirs(analysis_dir, exist_ok=True)
        
        logger.info(f"Starting Android backup analysis in {analysis_dir}")
        if backup_password:
            logger.info("Using password-protected backup extraction")
        
        # Process in background thread to avoid blocking
        def process_thread():
            try:
                results = {}
                ab_extracted_dir = None
                parsed_apk_dir = None
                
                # Initialize progress tracking
                processing_results[analysis_dir] = {
                    'status': 'processing',
                    'progress': 5,
                    'message': 'Initializing Android backup processing...',
                    'analysis_dir': analysis_dir,
                    'timestamp': timestamp
                }
                
                # Extract Android backup if requested
                if extract_ab and ab_file:
                    processing_results[analysis_dir].update({
                        'progress': 15,
                        'message': 'Extracting Android backup file...'
                    })
                    logger.info("Extracting Android backup file...")
                    ab_extracted_dir = os.path.join(analysis_dir, "ab_extracted")
                    
                    # Find abe.jar using improved path resolution
                    from src.Droid_backup.android_backup_collector import ArsenicTriageCollector
                    temp_collector = ArsenicTriageCollector(adb_command=get_adb_command())
                    abe_jar = temp_collector.get_abe_jar_path()
                    
                    if abe_jar is None:
                        results['ab_extraction'] = {'success': False, 'error': 'abe.jar not found in any expected location'}
                        processing_results[analysis_dir].update({
                            'progress': 20,
                            'message': 'Error: abe.jar not found'
                        })
                    else:
                        processing_results[analysis_dir].update({
                            'progress': 25,
                            'message': 'Extracting backup with ABE...'
                        })
                        extractor = BackupExtractor(ab_file, abe_jar, ab_extracted_dir, password=backup_password)
                        if extractor.extract():
                            results['ab_extraction'] = {'success': True, 'path': ab_extracted_dir}
                            logger.info(f"Android backup extracted to {ab_extracted_dir}")
                            processing_results[analysis_dir].update({
                                'progress': 40,
                                'message': 'Android backup extracted successfully'
                            })
                        else:
                            # Use detailed error message from extractor if available
                            error_msg = extractor.error_message or 'Failed to extract Android backup'
                            results['ab_extraction'] = {'success': False, 'error': error_msg}
                            processing_results[analysis_dir].update({
                                'progress': 25,
                                'message': f'❌ {error_msg}'
                            })
                            logger.error(f"Android backup extraction failed: {error_msg}")
                
                # Parse APK data if requested
                if parse_apk and apk_dir:
                    processing_results[analysis_dir].update({
                        'progress': 50,
                        'message': 'Parsing APK collected data...'
                    })
                    logger.info("Parsing APK collected data...")
                    parsed_apk_dir = os.path.join(analysis_dir, "apk_parsed")
                    
                    try:
                        parser = ForensicDataParser(apk_dir, parsed_apk_dir)
                        processing_results[analysis_dir].update({
                            'progress': 60,
                            'message': 'Analyzing forensic artifacts...'
                        })
                        parser.parse_all()
                        results['apk_parsing'] = {'success': True, 'path': parsed_apk_dir}
                        logger.info(f"APK data parsed to {parsed_apk_dir}")
                        processing_results[analysis_dir].update({
                            'progress': 70,
                            'message': 'APK data parsing completed'
                        })
                    except Exception as e:
                        results['apk_parsing'] = {'success': False, 'error': str(e)}
                        processing_results[analysis_dir].update({
                            'progress': 60,
                            'message': f'APK parsing failed: {str(e)}'
                        })
                
                # Generate forensic report if requested
                if generate_report:
                    processing_results[analysis_dir].update({
                        'progress': 75,
                        'message': 'Generating comprehensive forensic report...'
                    })
                    logger.info("Generating comprehensive forensic report...")
                    try:
                        from src.ui.droid_backup_frame import DroidBackupFrame
                        
                        # Create a temporary frame instance to use report generation methods
                        temp_frame = type('TempFrame', (), {})()
                        temp_frame.append_analysis_status = lambda msg: logger.info(msg)
                        temp_frame.analyze_apk_data = DroidBackupFrame.analyze_apk_data.__get__(temp_frame)
                        temp_frame.analyze_ab_data = DroidBackupFrame.analyze_ab_data.__get__(temp_frame)
                        temp_frame.create_html_report = DroidBackupFrame.create_html_report.__get__(temp_frame)
                        temp_frame.add_sample_sms_data = DroidBackupFrame.add_sample_sms_data.__get__(temp_frame)
                        temp_frame.add_sample_call_data = DroidBackupFrame.add_sample_call_data.__get__(temp_frame)
                        temp_frame.add_sample_contacts_data = DroidBackupFrame.add_sample_contacts_data.__get__(temp_frame)
                        
                        # Collect report data
                        report_data = {
                            'case_number': case_number,
                            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'ab_dir': ab_extracted_dir,
                            'apk_dir': parsed_apk_dir,
                            'summary': {}
                        }
                        
                        # Analyze APK data if available
                        if parsed_apk_dir and os.path.exists(parsed_apk_dir):
                            report_data['apk_analysis'] = temp_frame.analyze_apk_data(parsed_apk_dir)
                        
                        # Analyze AB extracted data if available
                        if ab_extracted_dir and os.path.exists(ab_extracted_dir):
                            report_data['ab_analysis'] = temp_frame.analyze_ab_data(ab_extracted_dir)
                        
                        # Generate HTML report
                        processing_results[analysis_dir].update({
                            'progress': 85,
                            'message': 'Generating HTML report...'
                        })
                        html_content = temp_frame.create_html_report(report_data, parsed_apk_dir, ab_extracted_dir)
                        
                        report_path = os.path.join(analysis_dir, "Forensic_Report.html")
                        with open(report_path, 'w', encoding='utf-8') as f:
                            f.write(html_content)
                        
                        results['report_generation'] = {'success': True, 'path': report_path}
                        logger.info(f"Forensic report generated: {report_path}")
                        processing_results[analysis_dir].update({
                            'progress': 90,
                            'message': 'Forensic report generated successfully'
                        })
                        
                    except Exception as e:
                        results['report_generation'] = {'success': False, 'error': str(e)}
                        logger.error(f"Error generating report: {str(e)}")
                        processing_results[analysis_dir].update({
                            'progress': 85,
                            'message': f'Report generation failed: {str(e)}'
                        })
                
                # Create forensic timeline if requested
                if create_timeline:
                    processing_results[analysis_dir].update({
                        'progress': 92,
                        'message': 'Creating forensic timeline...'
                    })
                    logger.info("Creating forensic timeline...")
                    try:
                        timeline_events = []
                        
                        # Parse APK data for timeline events
                        if parsed_apk_dir and os.path.exists(parsed_apk_dir):
                            # SMS timeline
                            sms_file = os.path.join(parsed_apk_dir, "sms_messages.csv")
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
                            calls_file = os.path.join(parsed_apk_dir, "call_logs.csv")
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
                        
                        # Sort timeline by timestamp and save
                        if timeline_events:
                            timeline_events.sort(key=lambda x: x['timestamp'])
                            timeline_path = os.path.join(analysis_dir, "Forensic_Timeline.csv")
                            
                            fieldnames = ['timestamp', 'event_type', 'description', 'details', 'source']
                            with open(timeline_path, 'w', newline='', encoding='utf-8') as f:
                                writer = csv.DictWriter(f, fieldnames=fieldnames)
                                writer.writeheader()
                                writer.writerows(timeline_events)
                            
                            results['timeline_creation'] = {'success': True, 'path': timeline_path, 'events': len(timeline_events)}
                            logger.info(f"Forensic timeline created: {timeline_path} ({len(timeline_events)} events)")
                            processing_results[analysis_dir].update({
                                'progress': 98,
                                'message': f'Timeline created with {len(timeline_events)} events'
                            })
                        else:
                            results['timeline_creation'] = {'success': False, 'error': 'No timeline events found'}
                            processing_results[analysis_dir].update({
                                'progress': 95,
                                'message': 'No timeline events found'
                            })
                            
                    except Exception as e:
                        results['timeline_creation'] = {'success': False, 'error': str(e)}
                        logger.error(f"Error creating timeline: {str(e)}")
                        processing_results[analysis_dir].update({
                            'progress': 92,
                            'message': f'Timeline creation failed: {str(e)}'
                        })
                
                # Final completion update
                processing_results[analysis_dir].update({
                    'progress': 100,
                    'message': 'Android backup analysis completed successfully!'
                })
                
                # Store results for later retrieval
                processing_results[analysis_dir] = {
                    'status': 'completed',
                    'progress': 100,
                    'message': 'Analysis completed successfully!',
                    'results': results,
                    'analysis_dir': analysis_dir,
                    'timestamp': timestamp
                }
                logger.info(f"Android backup analysis completed: {analysis_dir}")
                
            except Exception as e:
                error_msg = f"Error in processing thread: {str(e)}"
                logger.error(error_msg)
                processing_results[analysis_dir] = {
                    'status': 'error',
                    'progress': 0,
                    'message': f'Processing failed: {error_msg}',
                    'error': error_msg,
                    'analysis_dir': analysis_dir,
                    'timestamp': timestamp
                }
        
        # Start processing thread
        thread = threading.Thread(target=process_thread, daemon=True)
        thread.start()
        
        # Store initial status
        processing_results[analysis_dir] = {
            'status': 'processing',
            'analysis_dir': analysis_dir,
            'timestamp': timestamp
        }
        
        return jsonify({
            "success": True, 
            "analysis_dir": analysis_dir,
            "status": "processing",
            "message": "Android backup processing started"
        })
        
    except Exception as e:
        logger.error(f"Error in process_backup endpoint: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/processing_status/<path:analysis_dir>')
def get_processing_status(analysis_dir):
    """Get the status of a processing operation"""
    try:
        if analysis_dir in processing_results:
            return jsonify(processing_results[analysis_dir])
        else:
            return jsonify({"status": "not_found", "error": "Analysis directory not found"}), 404
    except Exception as e:
        logger.error(f"Error getting processing status: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    print("Starting Arsenic Mobile Triage Flask Backend...")
    print(f"Project root: {project_root}")
    
    # Run Flask app
    app.run(
        host='127.0.0.1',
        port=3131,
        debug=False,  # Set to False for production
        threaded=True
    )
