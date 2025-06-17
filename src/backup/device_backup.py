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

from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.usbmux import list_devices
from pymobiledevice3.services.mobilebackup2 import Mobilebackup2Service
from pymobiledevice3.services.os_trace import OsTraceService
from pymobiledevice3.services import installation_proxy
import zipfile
import hashlib
import os
import time
import logging
import json
import datetime
import threading

class DeviceBackup:
    def __init__(self):
        self.backupTarget = ""
        self.logTarget = ""
        self.backupFolder = ""
        self.logsFolder = ""
        self.backupArchive = ""
        self.logArchive = ""
        self.backupMD5 = ""
        self.logMD5 = ""
        self.now = datetime.datetime.now()
        self.device_info = {}
        self.status_callback = None
        self.progress_callback = None
        
    def set_callbacks(self, status_callback=None, progress_callback=None):
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        
    def update_status(self, message):
        if self.status_callback:
            self.status_callback(message)
        else:
            print(message)
            
    def update_progress(self, progress):
        if self.progress_callback:
            self.progress_callback(progress)
            
    def connect_device(self):
        """Attempt to connect to an iOS device"""
        try:
            self.update_status("Connecting to device...")
            self.lock_Handshake = create_using_usbmux()
            self.update_status("Device connected")
            return True
        except Exception as e:
            self.update_status(f"ERROR: No device found. Connect a device and try again.")
            logging.error(f"Device connection error: {e}")
            return False
            
    def get_device_info(self):
        """Get information about the connected device"""
        if not hasattr(self, 'lock_Handshake'):
            if not self.connect_device():
                return {}
                
        self.update_status("Getting device information...")
        all_iOS_IDs = self.lock_Handshake.all_values
        
        # Extract device information from iOS IDs
        device_data = {
            'Device Model': "",
            'Device Name': "",
            'iOS Version': "",
            'Serial Number': "",
            'Phone Number': "",
            'IMEI': "",
            'ICCID': "",
            'IMSI': "",
            'Carrier Bundle': "",
            'MEID': "",
            'Bluetooth MAC': "",
            'WiFi Mac': "",
            'Installed Applications': []
        }
        
        # Process device information
        for key in all_iOS_IDs:
            if "DeviceName" in key:
                device_data['Device Name'] = all_iOS_IDs[key]
            if "ProductVersion" in key:
                device_data['iOS Version'] = all_iOS_IDs[key]
            if "SerialNumber" in key and not "Baseband" in key and not "Wireless" in key:
                device_data['Serial Number'] = all_iOS_IDs[key]
            if "PhoneNumber" in key:
                device_data['Phone Number'] = all_iOS_IDs[key]
            if "InternationalMobileEquipmentIdentity" in key:
                device_data['IMEI'] = all_iOS_IDs[key]
            if "BluetoothAddress" in key:
                device_data['Bluetooth MAC'] = all_iOS_IDs[key]
            if "WiFiAddress" in key:
                device_data['WiFi Mac'] = all_iOS_IDs[key]
            if "ProductType" in key:
                device_data['Device Model'] = self.get_imodel(all_iOS_IDs[key])
                
        try:
            device_data['Installed Applications'] = self.get_applications()
        except Exception as e:
            logging.error(f"Error getting applications: {e}")
            
        self.device_info = device_data
        self.update_status("Device information retrieved")
        return device_data
        
    def get_imodel(self, product_number):
        """Convert product number to friendly device name"""
        # Import Models_Dictionary from the original script
        from src.utils.models_dict import Models_Dictionary
        
        if product_number in Models_Dictionary:
            return Models_Dictionary[product_number]
        return product_number
        
    def get_applications(self):
        """Get list of installed applications"""
        app_listing = []
        try:
            app_library = installation_proxy.InstallationProxyService(lockdown=self.lock_Handshake).get_apps()
            for i in app_library:
                if 'apple' not in i:  # remove apple apps
                    try:
                        app_name = app_library[i]['CFBundleDisplayName']
                        clean_app = app_name.strip("\u200e")
                        app_listing.append(clean_app)
                    except:
                        pass
            app_listing.sort()
        except Exception as e:
            logging.error(f"Error getting applications: {e}")
        return app_listing
        
    def create_backup(self, path, backup_logs=True):
        """Create a backup of the device"""
        if not hasattr(self, 'lock_Handshake'):
            if not self.connect_device():
                return False
                
        # Create backup directory
        self.backupTarget = "Backup_" + self.now.strftime("%Y%m%d%H%M%S")
        self.backupFolder = os.path.join(path, self.backupTarget)
        
        # Make directory if it doesn't exist
        if not os.path.exists(self.backupFolder):
            os.makedirs(self.backupFolder)
            
        # Change backup password
        try:
            self.update_status("Setting backup password...")
            self.change_backup_password()
        except Exception as e:
            self.update_status(f"Error changing backup password: {e}")
            
        # Create the backup
        try:
            self.update_status("Starting iOS backup...")
            self.ios_backup(self.backupFolder)
            self.update_status("iOS backup completed successfully")
        except Exception as e:
            self.update_status(f"Error backing up device: {e}")
            logging.error(f"Backup error: {e}")
            return False
            
        # Collect logs if requested
        if backup_logs:
            try:
                self.logTarget = "Logs_" + self.now.strftime("%Y%m%d%H%M%S")
                self.logsFolder = os.path.join(path, self.logTarget)
                self.update_status("Collecting iOS logs...")
                self.syslog_collect(save_log_to=os.path.join(self.logsFolder, "system_logs.logarchive"))
                self.update_status("iOS logs collected")
            except Exception as e:
                self.update_status(f"Error collecting logs: {e}")
                logging.error(f"Log collection error: {e}")
                
        # Create archives and calculate hashes
        if os.path.exists(self.backupFolder):
            try:
                self.update_status("Creating backup archive...")
                self.backupArchive = os.path.join(path, "BackupArchive.zip")
                self.zip_folder(self.backupFolder, self.backupArchive)
                self.update_status("Creating backup hash...")
                self.backupMD5 = self.calculate_md5(self.backupArchive)
                self.update_status(f"Backup MD5: {self.backupMD5}")
            except Exception as e:
                self.update_status(f"Error creating backup archive: {e}")
                logging.error(f"Archive error: {e}")
                
        if backup_logs and os.path.exists(self.logsFolder):
            try:
                self.update_status("Creating log archive...")
                self.logArchive = os.path.join(path, "LogArchive.zip")
                self.zip_folder(self.logsFolder, self.logArchive)
                self.update_status("Creating log hash...")
                self.logMD5 = self.calculate_md5(self.logArchive)
                self.update_status(f"Log MD5: {self.logMD5}")
            except Exception as e:
                self.update_status(f"Error creating log archive: {e}")
                
        # Create device report
        try:
            if not self.device_info:
                self.get_device_info()
            self.update_status("Creating device report...")
            self.create_text_report(path)
            self.update_status("Device report created")
        except Exception as e:
            self.update_status(f"Error creating device report: {e}")
            logging.error(f"Report error: {e}")
            
        self.update_status("Backup process completed")
        return True
        
    def change_backup_password(self, new_password="1234"):
        """Set the backup password to 1234"""
        backup_client = Mobilebackup2Service(self.lock_Handshake)
        try:
            backup_client.change_password(new=new_password)
        except Exception as e:
            error_str = str(e)
            
            # Check for the specific error code for invalid password
            if "ErrorCode': 207" in error_str and "Invalid password" in error_str:
                friendly_message = (
                    f"Attempted to change the backup password to '{new_password}', but a "
                    f"previously set backup password exists. Acquire the existing password. "
                    f"It is needed to decrypt the backup."
                )
                self.update_status(friendly_message)
                logging.warning(friendly_message)
            else:
                self.update_status(f"Error changing backup password: {e}")
                logging.error(f"Backup password error: {e}")
        
    def ios_backup(self, store_location):
        """Create an iOS backup"""
        backup_client = Mobilebackup2Service(self.lock_Handshake)
        time.sleep(2)
        
        def progress_callback(progress):
            self.update_status(f"Backup progress: {round(progress)}%")
            self.update_progress(progress)
            
        # Create an unencrypted backup
        backup_client.backup(
            full=True, 
            backup_directory=store_location,
            progress_callback=progress_callback
        )
        
    def syslog_collect(self, save_log_to, size_limit=None, age_limit=None, start_time=None):
        """Collect system logs from the device"""
        if not os.path.exists(os.path.dirname(save_log_to)):
            os.makedirs(os.path.dirname(save_log_to))
            
        OsTraceService(lockdown=self.lock_Handshake).collect(
            save_log_to, 
            size_limit=size_limit, 
            age_limit=age_limit, 
            start_time=start_time
        )
        
    def zip_folder(self, folder_path, zip_path):
        """Compress a folder to a zip file"""
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for foldername, subfolders, filenames in os.walk(folder_path):
                for filename in filenames:
                    file_path = os.path.join(foldername, filename)
                    arcname = os.path.relpath(file_path, folder_path)
                    zip_file.write(file_path, arcname)
                    
    def calculate_md5(self, file_path):
        """Calculate MD5 hash of a file"""
        md5_hash = hashlib.md5()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                md5_hash.update(byte_block)
        return md5_hash.hexdigest()
        
    def create_text_report(self, output_path):
        """Create a text report with device information"""
        report = "\nArsenic Collection Summary\n"
        report += "Version: 1.0\n\n"
        report += "Report Date: {}\n".format(self.now.strftime("%Y-%m-%d %H:%M:%S"))
        report += "Device Model: {}\n".format(self.device_info.get('Device Model', ''))
        report += "Device Name: {}\n".format(self.device_info.get('Device Name', ''))
        report += "iOS Version: {}\n".format(self.device_info.get('iOS Version', ''))
        report += "Serial Number: {}\n".format(self.device_info.get('Serial Number', ''))
        report += "Phone Number: {}\n".format(self.device_info.get('Phone Number', ''))
        report += "IMEI: {}\n".format(self.device_info.get('IMEI', ''))
        report += "ICCID: {}\n".format(self.device_info.get('ICCID', ''))
        report += "IMSI: {}\n".format(self.device_info.get('IMSI', ''))
        report += "Carrier Bundle: {}\n".format(self.device_info.get('Carrier Bundle', ''))
        report += "MEID: {}\n".format(self.device_info.get('MEID', ''))
        report += "Bluetooth MAC: {}\n".format(self.device_info.get('Bluetooth MAC', ''))
        report += "WiFi MAC: {}\n".format(self.device_info.get('WiFi Mac', ''))
        report += "\nInstalled Applications:\n"
        
        apps = self.device_info.get('Installed Applications', [])
        if apps:
            report += "\n".join(apps) + "\n"
            
        report += "\n\n\nWhen creating backups, Arsenic attempts to set the backup password to 1234. "
        report += "If a user has previously set a backup password, this will not be changed. "
        report += "If the backup password is not 1234, the user will need to provide the password to access the backup.\n\n"
        
        if self.backupMD5:
            report += f"Backup Archive MD5: {self.backupMD5}\n"
        if self.logMD5:
            report += f"Log Archive MD5: {self.logMD5}\n"
            
        # Write the report to a file
        with open(os.path.join(output_path, "Arsenic Device Report.txt"), "w") as f:
            f.write(report)
        return report

# This function was missing from the file, which caused the import error
def initiate_backup(path=None, backup_logs=True, status_callback=None, progress_callback=None):
    """Function to initiate the backup process"""
    backup = DeviceBackup()
    backup.set_callbacks(status_callback, progress_callback)
    
    if path is None:
        path = os.path.expanduser("~/Documents/ArsenicBackups")
        if not os.path.exists(path):
            os.makedirs(path)
            
    return backup.create_backup(path, backup_logs)