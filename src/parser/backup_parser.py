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
import argparse
from pyiosbackup import Backup
from pyiosbackup.exceptions import MissingEntryError
import plistlib
import sqlite3
import os
import re
from datetime import datetime, timedelta
import pandas as pd
from hashlib import sha1
import time
from reportlab.lib import pagesizes
from reportlab.pdfbase.pdfdoc import PDFText
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Image, Paragraph, Frame, Spacer
from reportlab.platypus import KeepInFrame, HRFlowable
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.pagesizes import LETTER, landscape, portrait, legal
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER, TA_JUSTIFY
from reportlab.pdfgen import canvas 
from reportlab.platypus.flowables import KeepTogether
from src.utils.models_dict import Models_Dictionary

taxonomy_Dict = {
    450: 'currency',
    492: 'document',
    554: 'firearm',
    759: 'keypad',
    881: 'people',
    983: 'phone',
    1447: 'vehicle',
    1605: 'body_part',
    1622: 'computer',
    1632: 'weapon',
    1664: 'handwriting',
    1665: 'screenshot',
    1668: 'laptop',
    1736: 'child',
    1758: 'teen',
    1777: 'underwear',
    1600: 'adult',
    8: 'building',
    139: 'atm',
    147: 'baby',
    1754: 'mask',
    1659: 'military_uniform',
    800: 'license_plate',
    13: 'fire',
    432: 'credit_card',
    1086: 'receipt',
    2147483655: 'outdoor_scene',
}

def replace_taxonomy_id_w_descr(df):   # use string id rather than number
    df['Scene Classification'] = df['Scene Classification'].replace(taxonomy_Dict)

# Function to format a float as a percentage
def format_as_percentage(value):
    return f'{value * 100:.0f}'
    # return f'{value * 100:.0f}%' removed to just get integer
# Function to convert mac epoch to time
def mac_absolute_time_to_datetime(mac_time):
    mac_epoch = datetime(2001, 1, 1, 0, 0, 0)
    dt = mac_epoch + timedelta(seconds=mac_time)
    dt = dt.replace(microsecond=0)
    return str(dt) + " UTC"

def save_report_with_device_info(df, csv_path, device_info, report_title, timezone=None):
    """
    Save a DataFrame to CSV with device information as a header.
    
    Args:
        df (pandas.DataFrame): The DataFrame to save
        csv_path (str): Path where the CSV should be saved
        device_info (dict): Dictionary containing device information
        report_title (str): Title for the report
        timezone (str, optional): Timezone for converting timestamps
    
    Returns:
        str: Path to the saved file
    """
    # Create device info header
    device_header = f"{report_title}\n\nDEVICE INFORMATION\n"
    if device_info:
        for key, value in device_info.items():
            if value:  # Only include non-empty values
                device_header += f"{key}: {value}\n"
    device_header += "\n"
    
    # Convert timestamps in the DataFrame if timezone specified
    if timezone:
        for column in df.columns:
            if 'date' in column.lower() or 'time' in column.lower():
                df[column] = df[column].apply(
                    lambda x: convert_timezone(x, timezone) if x and 'UTC' in str(x) else x
                )
    
    # Write header to file
    with open(csv_path, 'w') as f:
        f.write(device_header)
    
    # Append DataFrame to file
    df.to_csv(csv_path, mode='a', index=False)
    
    return csv_path

def photo_taxonomy(photosqlitepath):        # query photo db to get scene descriptions
    sqlite_file = photosqlitepath
    if sqlite_file is None:
        print("The 'photos.sqlite' file was not found in the specified folder or its subfolders.")
        return
    try:
        conn = sqlite3.connect(sqlite_file)
        cur = conn.cursor()
    except sqlite3.Error as e:
        print(f"Error connecting to {sqlite_file}: {e}")
        return
   
    # Execute the SQL query
    query = """SELECT 

		   ZSCENECLASSIFICATION.ZSCENEIDENTIFIER as 'Scene Classification',
           ZSCENECLASSIFICATION.ZCONFIDENCE as 'Confidence',
           ZASSET.ZDIRECTORY as 'Path',
           ZASSET.ZFILENAME as 'Filename',
           ZASSET.ZDATECREATED as 'Date Created',
           ZASSET.ZADDEDDATE as 'Date Added'
    FROM ZASSET
    INNER JOIN ZADDITIONALASSETATTRIBUTES ON ZADDITIONALASSETATTRIBUTES.ZASSET = ZASSET.Z_PK
    INNER JOIN ZSCENECLASSIFICATION ON ZSCENECLASSIFICATION.ZASSETATTRIBUTES = ZADDITIONALASSETATTRIBUTES.Z_PK
    """

    df = pd.read_sql_query(query, conn)
 
    # Reference taxonomy dictionary and replace numtag for word
    replace_taxonomy_id_w_descr(df=df)
    # Convert confidence to a percentile
    df['Confidence'] = df["Confidence"].apply(format_as_percentage)
    # Convert epoch to date time
    df["Date Created"] = df["Date Created"].apply(mac_absolute_time_to_datetime)
    df["Date Added"] = df["Date Added"].apply(mac_absolute_time_to_datetime)
    # Export to csv file
   
    conn.close()
    return(df)

def parse_backup(backup_path, password, status_callback=None, output_dir=None, taxonomy_target=None, timezone=None):
    """
    Parse an iOS backup and return structured data
    
    Args:
        backup_path (str): Path to the iOS backup directory
        password (str): Password for the iOS backup
        status_callback (callable): Function to call with status updates
        output_dir (str): Optional path to store artifacts and reports
        taxonomy_target (str): Optional taxonomy category to search for in photos
        timezone (str): Optional timezone to convert timestamps to
        
    Returns:
        dict: Parsed data from the backup
    """
    extraction_summary = "" # Initialize extraction summary
    # Initialize this variable at the beginning regardless of taxonomy selection
    photo_output_destination = None
    filtered_df = None

    if status_callback:
        status_callback("Starting backup parsing...")
    
    # Create output folders - use specified directory or create default
    if output_dir:
        report_output_destination = output_dir
    else:
        report_output_destination = os.path.join(os.path.dirname(backup_path), "ArsenicReports", 
                                               datetime.now().strftime("%Y%m%d%H%M%S"))
    
    if not os.path.isdir(report_output_destination):
        os.makedirs(report_output_destination, exist_ok=True)
    
    file_output_destination = os.path.join(report_output_destination, 'Artifacts')
    if not os.path.isdir(file_output_destination):
        os.makedirs(file_output_destination, exist_ok=True)
    
    # Create reports directory
    reports_dir = os.path.join(report_output_destination, 'Reports')
    if not os.path.isdir(reports_dir):
        os.makedirs(reports_dir, exist_ok=True)
        
    if status_callback:
        status_callback(f"Saving artifacts to: {report_output_destination}")
        status_callback(f"Reports will be saved to: {reports_dir}")
    
    # Parse basic info
    info_plist_path = os.path.join(backup_path, 'Info.plist')
    device_info = {}
    if os.path.exists(info_plist_path):
        try:
            with open(info_plist_path, 'rb') as plist_file:
                plist_data = plistlib.load(plist_file)
                
                # Get product type and look up the friendly name
                product_type = plist_data.get('Product Type', '')
                try:
                    model_name = Models_Dictionary.get(product_type, f"Unknown Model ({product_type})")
                except KeyError:
                    model_name = product_type                      

                device_info = {
                    'Device Name': plist_data.get('Device Name', ''),
                    # 'Device Type': product_type,
                    'Device Model': model_name,  # Add the friendly model name
                    'Phone Number': plist_data.get('Phone Number', ''),
                    'IMEI': plist_data.get('IMEI', ''),
                    'Serial Number': plist_data.get('Serial Number', ''),
                    'iOS Version': plist_data.get('Product Version', '')
                }
                
                # Set global variables for report generation
                global phonetype, devicename, imei, phonenum, serialnum
                phonetype = device_info.get('Device Type', '')
                devicename = device_info.get('Device Name', '')
                imei = device_info.get('IMEI', '')
                phonenum = device_info.get('Phone Number', '')
                serialnum = device_info.get('Serial Number', '')
        except Exception as e:
            if status_callback:
                status_callback(f"Error parsing Info.plist: {e}")
    
    # Check encryption status
    encryption_status = {
        'is_encrypted': False,
        'requires_password': False,
        'has_password': False
    }
    
    manifest_plist_path = os.path.join(backup_path, 'Manifest.plist')
    if os.path.exists(manifest_plist_path):
        try:
            with open(manifest_plist_path, 'rb') as plist_file:
                manifest_data = plistlib.load(plist_file)
                encryption_status['is_encrypted'] = manifest_data.get('IsEncrypted', False)
                encryption_status['requires_password'] = encryption_status['is_encrypted']
                encryption_status['has_password'] = bool(password) if encryption_status['is_encrypted'] else True
        except Exception as e:
            if status_callback:
                status_callback(f"Error parsing Manifest.plist: {e}")
    
    if status_callback:
        status_callback(f"Device info retrieved: {device_info.get('Device Name', 'Unknown device')}")
    
    # Initialize results dictionary
    results = {
        'device_info': device_info,
        'encryption_status': encryption_status,
        'sms_messages': [],
        'call_history': [],
        'installed_apps': [],
        'contacts': [],
        'browser_history': [],
        'photo_analysis': [],
        'data_usage': [],
        'accounts': [],
        'permissions': [],
        'interactions': [],
    }
    
    # Extract files from backup
    if status_callback:
        status_callback("Extracting files from backup...")
    
    try:
        # List of file IDs to extract with comments for clarity, ACTUAL LIST RIGHT HERE
        list_of_fileIDs = [
            '12b144c0bd44f2b3dffd9186d3f9c05b917cee25',  # Photos.sqlite
            "0d609c54856a9bb2d56729df1d68f2958a88426b",   # DataUsage.sqlite
            "31bb7ba8914766d4ba40d6dfb6113c8b614be442",   # AddressBook.sqlitedb
            "943624fd13e27b800cc6d9ce1100c22356ee365c",   # Accounts3.sqlite
            "3d0d7e5fb2ce288813306e4d4636395e047a3d28",   # sms.db
            "64d0019cb3d46bfc8cce545a8ba54b93e7ea9347",   # TCC.db
            "5a4935c78a5255723f707230a451d79c540d2741",   # CallHistory.storedata
            "ed1f8fb5a948b40504c19580a458c384659a605e",   
            "51a4616e576dd33cd2abadfea874eb8ff246bf0e",    
            "ca3bc056d4da0bbf88b5fb3be254f3b7147e639c",
            "1f5a521220a3ad80ebfdc196978df8e7a2e49dee",   # interactionC.db 
            "e74113c185fd8297e140cfcf9c99436c5cc06b57",  # Safari Old History.db
            "1a0e7afc19d307da602ccdcece51af33afe92c53",  # Safari History.db
            "992df473bbb9e132f4b3b6e4d33f72171e97bc7a",   # voicemail.db
        ]
        
        backup = Backup.from_path(backup_path=backup_path, password=password)
        for ID in list_of_fileIDs:
            try:
                backup.extract_file_id(ID, path=file_output_destination)
                if status_callback:
                    status_callback(f"Extracted file {ID}")
            except Exception as e:
                if status_callback:
                    status_callback(f"Error extracting file {ID}: {e}")
    except Exception as e:
        if status_callback:
            status_callback(f"Error setting up backup extraction: {e}")
    
    # Process the extracted files
    if status_callback:
        status_callback("Processing extracted files...")
    
    recovered_files = []
    if os.path.exists(file_output_destination):
        recovered_files = os.listdir(file_output_destination)
        if status_callback:
            status_callback(f"Found {len(recovered_files)} files to process")
    
    # Single loop for processing all files
    for artifact in recovered_files:
        file_path = os.path.join(file_output_destination, artifact)
        
        if status_callback:
            status_callback(f"Processing file: {artifact}")
        
        # Process SMS messages - look for both file ID and common name
        if "3d0d7e5fb2ce288813306e4d4636395e047a3d28" in artifact or "sms.db" in artifact:
            if status_callback:
                status_callback("Processing SMS messages...")
            try:
                sms_data, sms_df = parse_ios_backup.sqlite_run_SMS(file_path)
                if len(sms_data) > 1:  # Skip header row
                    # Save to CSV
                    csv_path = os.path.join(reports_dir, f'Messages_{datetime.now().strftime("%Y%m%d%H%M%S")}.csv')
                    save_report_with_device_info(sms_df, csv_path, device_info, "SMS MESSAGES REPORT", timezone=timezone)

                    if status_callback:
                        status_callback(f"Saved SMS messages to {csv_path}")
                    
                    # Process for UI display
                    messages = []
                    for _, row in sms_df.iterrows():
                        message = {
                            'date': row.get('Message Date', ''),
                            'phone_number': row.get('Contact', ''),
                            'service': row.get('Message Service', ''),
                            'direction': 'Sent' if pd.notna(row.get('Sent')) else 'Received',
                            'message': row.get('Sent') if pd.notna(row.get('Sent')) else row.get('Received', ''),
                            # Include ALL attachment fields directly:
                            'Attachment Names': row.get('Attachment Names', ''),
                            'Attachment Files': row.get('Attachment Files', ''),
                            'Attachment Types': row.get('Attachment Types', ''),
                            'Attachment Count': row.get('Attachment Count', 0)
                        }
                        messages.append(message)
                    results['sms_messages'] = messages
                    if status_callback:
                        status_callback(f"Found {len(messages)} SMS messages")
            except Exception as e:
                if status_callback:
                    status_callback(f"Error processing SMS: {e}")
        
        # Process call history
        if "5a4935c78a5255723f707230a451d79c540d2741" in artifact or "CallHistory.storedata" in artifact:
            if status_callback:
                status_callback("Processing call history...")
            try:
                call_data = parse_ios_backup.sqlite_run_callhistory(file_path)
                if len(call_data) > 1:  # Skip header row
                    # Save to CSV
                    csv_path = os.path.join(reports_dir, f'Call_History_{datetime.now().strftime("%Y%m%d%H%M%S")}.csv')
                    call_df = pd.DataFrame(call_data[1:], columns=call_data[0])
                    save_report_with_device_info(call_df, csv_path, device_info, "CALL HISTORY REPORT", timezone=timezone)

                    
                    if status_callback:
                        status_callback(f"Saved call history to {csv_path}")
                    
                    # Process for UI display
                    calls = []
                    for row in call_data[1:]:  # Skip the header
                        call = {
                            'date': row[0] if len(row) > 0 else '',
                            'duration': row[1] if len(row) > 1 else '',
                            'phone_number': row[2] if len(row) > 2 else '',
                            'direction': row[3] if len(row) > 3 else '',
                            'answered': row[4] if len(row) > 4 else '',
                            'call_type': row[5] if len(row) > 5 else ''
                        }
                        calls.append(call)
                    results['call_history'] = calls
                    if status_callback:
                        status_callback(f"Found {len(calls)} call records")
            except Exception as e:
                if status_callback:
                    status_callback(f"Error processing call history: {e}")
        
        # Process contacts
        if "31bb7ba8914766d4ba40d6dfb6113c8b614be442" in artifact or "AddressBook.sqlitedb" in artifact:
            if status_callback:
                status_callback("Processing contacts...")
            try:
                contact_data = parse_ios_backup.sqlite_run_addressbook(file_path)
                if len(contact_data) > 1:  # Skip header row
                    # Save to CSV
                    csv_path = os.path.join(reports_dir, f'Contacts_{datetime.now().strftime("%Y%m%d%H%M%S")}.csv')
                    contact_df = pd.DataFrame(contact_data[1:], columns=contact_data[0])
                    save_report_with_device_info(contact_df, csv_path, device_info, "CONTACTS REPORT", timezone=timezone)
                    if status_callback:
                        status_callback(f"Saved contacts to {csv_path}")
                    
                    # Process for UI display
                    contacts = []
                    for row in contact_data[1:]:  # Skip the header
                        contact = {
                            'last_name': row[0] if len(row) > 0 else '',
                            'first_name': row[1] if len(row) > 1 else '',
                            'main_number': row[2] if len(row) > 2 else '',
                            'iphone_number': row[3] if len(row) > 3 else '',
                            'mobile_number': row[4] if len(row) > 4 else '',
                            'home_number': row[5] if len(row) > 5 else '',
                            'work_number': row[6] if len(row) > 6 else '',
                            'email': row[7] if len(row) > 7 else ''
                        }
                        contacts.append(contact)
                    results['contacts'] = contacts
                    if status_callback:
                        status_callback(f"Found {len(contacts)} contacts")
            except Exception as e:
                if status_callback:
                    status_callback(f"Error processing contacts: {e}")

        # Process data usage
        if "0d609c54856a9bb2d56729df1d68f2958a88426b" in artifact or "DataUsage.sqlite" in artifact:
            if status_callback:
                status_callback("Processing data usage...")
            try:
                data_usage = parse_ios_backup.sqlite_run_datausage(file_path)
                if len(data_usage) > 1:  # Skip header row
                    # Save to CSV
                    csv_path = os.path.join(reports_dir, f'Data_Usage_{datetime.now().strftime("%Y%m%d%H%M%S")}.csv')

                    data_usage_df = pd.DataFrame(data_usage[1:], columns=data_usage[0])
                    save_report_with_device_info(data_usage_df, csv_path, device_info, "DATA USAGE REPORT", timezone=timezone)

                    if status_callback:
                        status_callback(f"Saved data usage to {csv_path}")
                    
                    # Process for UI display
                    headers = data_usage[0]
                    usage_data = []
                    for row in data_usage[1:]:
                        usage_entry = {}
                        for i, header in enumerate(headers):
                            if i < len(row):
                                usage_entry[header] = row[i]
                            else:
                                usage_entry[header] = ''
                        usage_data.append(usage_entry)
                    results['data_usage'] = usage_data
                    if status_callback:
                        status_callback(f"Found {len(usage_data)} data usage records")
            except Exception as e:
                if status_callback:
                    status_callback(f"Error processing data usage: {e}")

        # Process accounts
        if "943624fd13e27b800cc6d9ce1100c22356ee365c" in artifact or "Accounts3.sqlite" in artifact:
            if status_callback:
                status_callback("Processing accounts...")
            try:
                accounts_data = parse_ios_backup.sqlite_run_accounts3(file_path)
                if len(accounts_data) > 1:  # Skip header row
                    # Save to CSV
                    csv_path = os.path.join(reports_dir, f'Accounts_{datetime.now().strftime("%Y%m%d%H%M%S")}.csv')
                    accounts_df = pd.DataFrame(accounts_data[1:], columns=accounts_data[0])
                    save_report_with_device_info(accounts_df, csv_path, device_info, "ACCOUNTS REPORT", timezone=timezone)

                    if status_callback:
                        status_callback(f"Saved accounts to {csv_path}")
                    
                    # Process for UI display
                    headers = accounts_data[0]
                    accounts = []
                    for row in accounts_data[1:]:
                        account = {}
                        for i, header in enumerate(headers):
                            if i < len(row):
                                account[header] = row[i]
                            else:
                                account[header] = ''
                        accounts.append(account)
                    results['accounts'] = accounts
                    if status_callback:
                        status_callback(f"Found {len(accounts)} accounts")
            except Exception as e:
                if status_callback:
                    status_callback(f"Error processing accounts: {e}")

        # Process Notes
        if "ed1f8fb5a948b40504c19580a458c384659a605e" in artifact or "notes.sqlite" in artifact:
            if status_callback:
                status_callback("Processing notes...")
            try:
                print("Processing notes...")
                notes_data = parse_ios_backup.sqlite_run_notes(file_path)
                # print(f"Notes data: {notes_data}")
                if notes_data and len(notes_data) > 1:  # Skip header row
                    # Save to CSV
                    csv_path = os.path.join(reports_dir, f'Notes_{datetime.now().strftime("%Y%m%d%H%M%S")}.csv')
                    notes_df = pd.DataFrame(notes_data[1:], columns=notes_data[0])
                    save_report_with_device_info(notes_df, csv_path, device_info, "NOTES REPORT")
                    if status_callback:
                        status_callback(f"Saved notes to {csv_path}")
                    
                    # Process for UI display
                    headers = notes_data[0]
                    notes = []
                    for row in notes_data[1:]:
                        note = {}
                        for i, header in enumerate(headers):
                            if i < len(row):
                                note[header] = row[i]
                            else:
                                note[header] = ''
                        notes.append(note)
                    results['notes'] = notes
                    if status_callback:
                        status_callback(f"Found {len(notes)} notes")
            except Exception as e:
                if status_callback:
                    status_callback(f"Error processing notes: {e}")
        # Process TCC permissions
        if "64d0019cb3d46bfc8cce545a8ba54b93e7ea9347" in artifact or "TCC.db" in artifact:
            if status_callback:
                status_callback("Processing app permissions...")
            try:
                permissions_data = parse_ios_backup.sqlite_run_TCC(file_path)
                if permissions_data and len(permissions_data) > 1:  # Skip header row
                    # Save to CSV
                    csv_path = os.path.join(reports_dir, f'App_Permissions_{datetime.now().strftime("%Y%m%d%H%M%S")}.csv')
                    permissions_df = pd.DataFrame(permissions_data[1:], columns=permissions_data[0])
                    save_report_with_device_info(permissions_df, csv_path, device_info, "APP PERMISSIONS REPORT")
                    if status_callback:
                        status_callback(f"Saved app permissions to {csv_path}")
                    
                    # Process for UI display
                    headers = permissions_data[0]
                    permissions = []
                    for row in permissions_data[1:]:
                        permission = {}
                        for i, header in enumerate(headers):
                            if i < len(row):
                                permission[header] = row[i]
                            else:
                                permission[header] = ''
                        permissions.append(permission)
                    results['permissions'] = permissions
                    if status_callback:
                        status_callback(f"Found {len(permissions)} app permissions")
            except Exception as e:
                if status_callback:
                    status_callback(f"Error processing app permissions: {e}")

        # Process Safari history
        if "History.db" in artifact:
            if status_callback:
                status_callback("Processing Safari browsing history...")
            try:
                safari_data = parse_ios_backup.sqlite_run_safarihistory(file_path)
                if safari_data and len(safari_data) > 1:  # Skip header row
                    # Save to CSV
                    csv_path = os.path.join(reports_dir, f'Safari_History_{datetime.now().strftime("%Y%m%d%H%M%S")}.csv')
                    safari_df = pd.DataFrame(safari_data[1:], columns=safari_data[0])
                    save_report_with_device_info(safari_df, csv_path, device_info, "SAFARI BROWSING HISTORY REPORT", timezone=timezone)
                    if status_callback:
                        status_callback(f"Saved Safari history to {csv_path}")
                    
                    # Process for UI display
                    headers = safari_data[0]
                    safari_history = []
                    for row in safari_data[1:]:
                        history_item = {}
                        for i, header in enumerate(headers):
                            if i < len(row):
                                history_item[header] = row[i]
                            else:
                                history_item[header] = ''
                        safari_history.append(history_item)
                    results['safari_history'] = safari_history
                    if status_callback:
                        status_callback(f"Found {len(safari_history)} Safari history records")
            except Exception as e:
                if status_callback:
                    status_callback(f"Error processing Safari history: {e}")

        if "interactionC.db" in artifact:
            if status_callback:
                status_callback("Processing interaction data...")
            try:
                interaction_data = parse_ios_backup.sqlite_run_interactionC(file_path)
                # print(f"Interaction data: {interaction_data}")
                if interaction_data and len(interaction_data) > 1:
                    csv_path = os.path.join(reports_dir, f'InteractionC_{datetime.now().strftime("%Y%m%d%H%M%S")}.csv')
                    interaction_df = pd.DataFrame(interaction_data[1:], columns=interaction_data[0])
                    save_report_with_device_info(interaction_df, csv_path, device_info, "InteractionC REPORT", timezone=timezone)
                    results['interactions'] = interaction_data[1:]
                    if status_callback:
                        status_callback(f"Saved interactions to {csv_path}")
            except Exception as e:
                print(f"Error processing interaction data: {e}")
        
        if 'Photos.sqlite' in artifact:  # Photos.sqlite
            # Skip photo processing entirely if no taxonomy target is provided
            if taxonomy_target is None:
                if status_callback:
                    status_callback("Skipping photo processing (option not selected)")
                continue  # Skip to the next artifact
            
            print("Processing photos...")
            
            # Initialize list for file IDs
            list_of_paths = []
            
            # Fix variable name
            accountdata = os.path.join(report_output_destination, 'Artifacts', artifact)
            
            # Create photos output dir
            photo_folder = "Photos_" + taxonomy_target
            photo_output_destination = os.path.join(report_output_destination, photo_folder)
            os.makedirs(photo_output_destination, exist_ok=True)
            print(f"Photo output destination: {photo_output_destination}")
            
            try:
                taxonomyquery = parse_ios_backup.photo_taxonomy(accountdata)
                taxonomyquery['Confidence'] = pd.to_numeric(taxonomyquery['Confidence'], errors='coerce')
                filtered_df = taxonomyquery[(taxonomyquery['Scene Classification'] == taxonomy_target) & (taxonomyquery['Confidence'] > 5)] 
                print(f"Filtered DataFrame: {filtered_df}")
                photo_records = filtered_df.to_dict('records')
                results['photo_analysis'] = photo_records
                print(f"Added {len(photo_records)} photo records to results dictionary")
    
                pathdf = (filtered_df['Path'] + '/' + filtered_df['Filename'])
                for thing in pathdf:
                    print(f"Processing photo: {thing}")
                    fileid = parse_ios_backup.calculate_itunes_photofile_name(thing)
                    print(f"File ID: {fileid}")
                    list_of_paths.append(fileid)

            except Exception as e:
                print(f"Error running photo taxonomy: {e}")
            
        
            try:    
                # Use correct variable name
                extracted_count = parse_ios_backup.retrieve_photos_from_backup(
                    backup_path=backup_path, 
                    filedestination=photo_output_destination, 
                    password=password, 
                    list_of_fileIDs=list_of_paths
                )
            except Exception as e:
                if status_callback:
                    status_callback(f"Error retrieving photos: {e}")

        # If standard extraction produced no results, try direct method
        if 'extracted_count' in locals() and extracted_count == 0 and list_of_paths:
            if status_callback:
                status_callback("Standard extraction failed. Trying direct file extraction...")

            # Use the direct extraction method
            direct_extracted_count = parse_ios_backup.extract_photos_direct(
                backup_path=backup_path,
                filtered_df=filtered_df,
                output_dir=photo_output_destination,
                status_callback=status_callback
            )
            
            if direct_extracted_count > 0:
                if status_callback:
                    status_callback(f"Successfully extracted {direct_extracted_count} photos using direct method")
                results['extracted_photos_path'] = photo_output_destination

        # After trying the standard extraction and direct extraction methods, add:
        if 'extracted_count' in locals() and extracted_count == 0 and list_of_paths:
            if status_callback:
                status_callback("Direct extraction failed. Trying manifest.db extraction...")
            
            manifest_extracted_count = parse_ios_backup.extract_photos_manifest(
                backup_path=backup_path,
                filtered_df=filtered_df,
                output_dir=photo_output_destination,
                status_callback=status_callback,
                password=password
            )
            
            if manifest_extracted_count > 0:
                if status_callback:
                    status_callback(f"Successfully extracted {manifest_extracted_count} photos using manifest.db")
                results['extracted_photos_path'] = photo_output_destination

        # If all extraction methods fail, generate a failure report
        if 'extracted_count' in locals() and extracted_count == 0 and list_of_paths:
            report_photo_extraction_failure(
                backup_path=backup_path,
                filtered_df=filtered_df,
                output_dir=photo_output_destination,
                status_callback=status_callback
            )


    if photo_output_destination and os.path.exists(photo_output_destination) and filtered_df is not None:
        # Get the actual files in the output directory
        recovered_files = set(os.listdir(photo_output_destination))
        
        # Fix: Check using the original filenames, not the iTunes IDs
        def recovery_status(row):
            try:
                if row['Filename'] in recovered_files:
                    return "Recovered"
                else:
                    return "Missing"
            except:
                return "Error"
                
        # Add only ONE recovery status column - use text version which is more user-friendly
        filtered_df.loc[:, 'Recovery Status'] = filtered_df.apply(recovery_status, axis=1)
        
        # Create extraction summary with accurate counts
        recovered_count = (filtered_df['Recovery Status'] == 'Recovered').sum()
        total_attempted = len(filtered_df)
        missing_count = total_attempted - recovered_count
        
        if missing_count > 0:
            missing_files = filtered_df[filtered_df['Recovery Status'] == "Missing"]['Filename'].tolist()
            if len(missing_files) <= 10:
                missing_list = ", ".join(missing_files)
                extraction_summary += f"Missing files: {missing_list}\n"
            else:
                missing_list = ", ".join(missing_files[:10])
                extraction_summary += f"Missing files: {missing_list}... (and {len(missing_files) - 10} more)\n"
                
        extraction_summary += "\nEXTRACTION DETAILS\n"

        # Save just ONE report with accurate recovery status
        photo_report_csv = os.path.join(reports_dir, f'Photo_Report_{taxonomy_target}.csv')
        
        # Convert timestamps in the DataFrame if timezone specified
        if timezone:
            for column in filtered_df.columns:
                if 'date' in column.lower() or 'time' in column.lower():
                    filtered_df[column] = filtered_df[column].apply(
                        lambda x: convert_timezone(x, timezone) if x and 'UTC' in str(x) else x
                    )
        
        # FIX: Create device_header before using it
        device_header = f"PHOTO ANALYSIS REPORT\n\nDEVICE INFORMATION\n"
        if device_info:
            for key, value in device_info.items():
                if value:  # Only include non-empty values
                    device_header += f"{key}: {value}\n"
        device_header += "\n"
        
        # Write the summary first, then the DataFrame
        with open(photo_report_csv, 'w') as f:
            f.write(device_header)  # Add device info at the very top
            f.write(extraction_summary)
        
        # Append the DataFrame to the file with header but no index
        filtered_df.to_csv(photo_report_csv, mode='a', index=False)
        
        if status_callback:
            status_callback(f"Saved photo report with extraction summary to {photo_report_csv}")
    else:
        # Handle case when photo_output_destination is not set or doesn't exist
        extraction_summary += "No photos were extracted or photo extraction path does not exist.\n"

    results['reports_path'] = reports_dir
    
    if status_callback:
        status_callback(f"Parsing complete! Reports saved to: {reports_dir}")
    
    if photo_output_destination and os.path.exists(photo_output_destination):
        results["extracted_photos_path"] = photo_output_destination
    
    # Convert timestamps if timezone specified
    if timezone:
        for data_type, data_list in results.items():
            # Only process dictionary data types
            if (isinstance(data_list, list) and data_list and 
                isinstance(data_list[0], dict)):
                
                # Check for date fields in different formats
                date_fields = [field for field in data_list[0].keys() 
                            if 'date' in field.lower() or 'time' in field.lower()]
                
                # Convert timestamps in place
                for item in data_list:
                    for field in date_fields:
                        if field in item and 'UTC' in str(item[field]):
                            item[field] = convert_timezone(item[field], timezone)
    
    return results

class parse_ios_backup:
    # Updated taxonomy dictionary with comprehensive mappings
    taxonomy_Dict = {
        450: 'currency',
        492: 'document',
        554: 'firearm',
        759: 'keypad',
        881: 'people',
        983: 'phone',
        1447: 'vehicle',
        1605: 'body_part',
        1622: 'computer',
        1632: 'weapon',
        1664: 'handwriting',
        1665: 'screenshot',
        1668: 'laptop',
        1736: 'child',
        1758: 'teen',
        1777: 'underwear',
        1600: 'adult',
        8: 'building',
        139: 'atm',
        147: 'baby',
        1754: 'mask',
        1659: 'military_uniform',
        800: 'license_plate',
        13: 'fire',
        432: 'credit_card',
        1086: 'receipt',
        2147483655: 'outdoor_scene',
    }
    # Global variables
    phonetype = ""
    devicename = ""
    phonenum = ""
    imei = ""
    serialnum = ""
    target = ''

    list_of_paths = []
    now = datetime.now()
    def parse_args():
        parser = argparse.ArgumentParser(description="Darwin Analysis v1.0")
        parser.add_argument("--backup-path", required=True, help="Path to the iOS backup directory")
        parser.add_argument("--password", required=True, help="Password for the iOS backup")
        parser.add_argument("--report-output-destination", help="Output directory for reports")
        parser.add_argument("--target", default="", help="Target search term for photo classification")
        parser.add_argument("--report-type", default="csv", help="Type of report to generate (pdf, csv, or json)")

        return parser.parse_args()

    def parse_info_plist(file_path):
        try:
            with open(file_path, 'rb') as plist_file:
                plist_data = plistlib.load(plist_file)
                global phonetype, devicename, imei, phonenum, serialnum
                phonetype = plist_data.get('Product Type', '')
                devicename = plist_data.get('Device Name', '')
                imei = plist_data.get('IMEI', '')
                phonenum = plist_data.get('Phone Number', '')
                serialnum = plist_data.get('Serial Number', '')
        except Exception as e:
            print(f"Error: {e}")

    
    def replace_taxonomy_id_w_descr(df):   # use string id rather than number
        df['Scene Classification'] = df['Scene Classification'].replace(taxonomy_Dict)

    # Function to format a float as a percentage
    def format_as_percentage(value):
        return f'{value * 100:.0f}'
        # return f'{value * 100:.0f}%' removed to just get integer
    # Function to convert mac epoch to time
    def mac_absolute_time_to_datetime(mac_time):
        mac_epoch = datetime(2001, 1, 1, 0, 0, 0)
        dt = mac_epoch + timedelta(seconds=mac_time)
        dt = dt.replace(microsecond=0)
        return str(dt) + " UTC"
    def photo_taxonomy(photosqlitepath):        # query photo db to get scene descriptions
        sqlite_file = photosqlitepath
        if sqlite_file is None:
            print("The 'photos.sqlite' file was not found in the specified folder or its subfolders.")
            return
        try:
            conn = sqlite3.connect(sqlite_file)
            cur = conn.cursor()
        except sqlite3.Error as e:
            print(f"Error connecting to {sqlite_file}: {e}")
            return
    
        # Execute the SQL query
        query = """SELECT 

            ZSCENECLASSIFICATION.ZSCENEIDENTIFIER as 'Scene Classification',
            ZSCENECLASSIFICATION.ZCONFIDENCE as 'Confidence',
            ZASSET.ZDIRECTORY as 'Path',
            ZASSET.ZFILENAME as 'Filename',
            ZASSET.ZDATECREATED as 'Date Created',
            ZASSET.ZADDEDDATE as 'Date Added'
        FROM ZASSET
        INNER JOIN ZADDITIONALASSETATTRIBUTES ON ZADDITIONALASSETATTRIBUTES.ZASSET = ZASSET.Z_PK
        INNER JOIN ZSCENECLASSIFICATION ON ZSCENECLASSIFICATION.ZASSETATTRIBUTES = ZADDITIONALASSETATTRIBUTES.Z_PK
        """

        df = pd.read_sql_query(query, conn)
    
        # Reference taxonomy dictionary and replace numtag for word
        replace_taxonomy_id_w_descr(df=df)
        # Convert confidence to a percentile
        df['Confidence'] = df["Confidence"].apply(format_as_percentage)
        # Convert epoch to date time
        df["Date Created"] = df["Date Created"].apply(mac_absolute_time_to_datetime)
        df["Date Added"] = df["Date Added"].apply(mac_absolute_time_to_datetime)
        # Export to csv file
    
        conn.close()
        return(df)

    
    def sqlite_run_accounts3(accounts3path):
        connection = sqlite3.connect(accounts3path)
        cursor = connection.cursor()
        
        # Define the query - THIS WAS MISSING
        act3query = """SELECT 
            datetime('2001-01-01', ZACCOUNT.ZDATE || ' seconds') AS "Account Date",
            ZACCOUNT.ZUSERNAME AS "Username", 
            ZACCOUNT.ZACCOUNTDESCRIPTION AS "Description"
        FROM ZACCOUNT
        WHERE ZACCOUNT.ZDATE IS NOT NULL
            AND ZACCOUNT.ZUSERNAME IS NOT NULL
            AND ZACCOUNT.ZACCOUNTDESCRIPTION IS NOT NULL;"""

        # Execute the query
        cursor.execute(act3query)
        results = cursor.fetchall()

        # Fetch column headers using description
        column_headers = [description[0] for description in cursor.description]

        # Close the connection
        connection.close()

        # Combine column headers with data
        results_with_headers = [column_headers] + results

        return results_with_headers

    def sqlite_run_addressbook(addressbookpath):
        connection = sqlite3.connect(addressbookpath)
        cursor = connection.cursor()
        addressbookquery = """Select 
                            abperson.Last as 'Last',
                            abperson.First as 'First',
                            (select 
                                value from ABMultiValue where property = 3 and record_id = ABPerson.ROWID and 
                                label = (select ROWID from ABMultiValueLabel where value = '_$!<Main>!$_')) as 'Main',
                            (select 
                                value from ABMultiValue where property = 3 and record_id = ABPerson.ROWID and 
                                label = (select ROWID from ABMultiValueLabel where value = 'iPhone')) as 'iPhone',		
                            (select 
                                value from ABMultiValue where property = 3 and record_id = ABPerson.ROWID and 
                                label = (select ROWID from ABMultiValueLabel where value = '_$!<Mobile>!$_')) as 'Mobile',
                            (select 
                                value from ABMultiValue where property = 3 and record_id = ABPerson.ROWID and 
                                label = (select ROWID from ABMultiValueLabel where value = '_$!<Home>!$_')) as 'Home',
                            (select 
                                value from ABMultiValue where property = 3 and record_id = ABPerson.ROWID and 
                                label = (select ROWID from ABMultiValueLabel where value = '_$!<Work>!$_')) as 'Work',
                            (select 
                                value from ABMultiValue where property = 4 and record_id = ABPerson.ROWID and 
                                label is null) as 'Email'

                            --datetime('2001-01-01', abperson.CreationDate || ' seconds') as 'CreationDate'
                        
                            from abperson
                                join ABStore on abperson.StoreID = ABStore.ROWID
                                join ABAccount on ABStore.AccountID = ABAccount.ROWID
                                order by abperson.Last asc;"""
        cursor.execute(addressbookquery)
        results = cursor.fetchall()
        column_headers = [description[0] for description in cursor.description]

        # Close the connection
        connection.close()

        # Combine column headers with data
        results_with_headers = [column_headers] + results
    
        return results_with_headers

    def sqlite_run_datausage(datausagepath):
        connection = sqlite3.connect(datausagepath)
        cursor = connection.cursor()
        datausequery = """SELECT 
                    datetime('2001-01-01', ZLIVEUSAGE.ZTIMESTAMP || ' seconds') as 'Date', 
                    ZPROCESS.ZBUNDLENAME as 'Application Bundle', 
                    CAST(ZLIVEUSAGE.ZWWANIN AS REAL) / 1024.0 as 'WWAN In (KB)', 
                    CAST(ZLIVEUSAGE.ZWWANOUT AS REAL) / 1024.0 as 'WWAN Out (KB)'
                    FROM ZLIVEUSAGE
                    LEFT JOIN ZPROCESS ON ZPROCESS.Z_PK = ZLIVEUSAGE.ZHASPROCESS
                    WHERE (ZLIVEUSAGE.ZWWANIN > 0 OR ZLIVEUSAGE.ZWWANOUT > 0)
                    ORDER BY datetime('2001-01-01', ZLIVEUSAGE.ZTIMESTAMP || ' seconds') ASC;"""
    
        cursor.execute(datausequery)
        results = cursor.fetchall()
        column_headers = [description[0] for description in cursor.description]

        # Close the connection
        connection.close()

        # Combine column headers with data
        results_with_headers = [column_headers] + results
    
        return results_with_headers

    def sqlite_run_callhistory(callhistorypath):
        connection = sqlite3.connect(callhistorypath)
        cursor = connection.cursor()
        datausequery = """SELECT 
                        datetime('2001-01-01', zdate || ' seconds') as 'Date',
                        time(ZDURATION,'unixepoch') as 'Duration',
                        ZADDRESS as 'Other Party',
                        CASE ZORIGINATED 
                            WHEN 0 THEN 'Incoming'
                            WHEN 1 THEN 'Outgoing'
                        END as 'Call Direction',
                        CASE ZANSWERED
                            WHEN 0 THEN 'No'
                            WHEN 1 THEN 'Yes'
                        END as 'Answered',
                        CASE ZCALLTYPE 
                            WHEN 1 THEN 'Standard Call'
                            WHEN 8 THEN 'Facetime Video Call'
                            WHEN 16 THEN 'Facetime Audio Call'
                            ELSE CAST(ZCALLTYPE AS TEXT)  -- Assuming ZCALLTYPE is a numeric type
                        END as 'CallType' 
                    FROM zcallrecord
                    ORDER BY datetime('2001-01-01', zdate || ' seconds') ASC;"""
        cursor.execute(datausequery)
        results = cursor.fetchall()
        # print(results)
        column_headers = [description[0] for description in cursor.description]

        # Close the connection
        connection.close()

        # Combine column headers with data
        results_with_headers = [column_headers] + results

        return results_with_headers
    def sqlite_run_notes(notespath):
        connection = sqlite3.connect(notespath)
        cursor = connection.cursor()
        datausequery = """SELECT 
                        ZCONTENT
                        FROM ZNOTEBODY"""
        cursor.execute(datausequery)
        results = cursor.fetchall()
        column_headers = [description[0] for description in cursor.description]

        # Close the connection
        connection.close()
        
        # Clean HTML content from results
        cleaned_results = []
        for row in results:
            if row[0]:  # Check if content exists
                # Strip HTML tags using regex
                cleaned_content = re.sub(r'<[^>]+>', ' ', row[0])
                # Replace multiple spaces and newlines with single space
                cleaned_content = re.sub(r'\s+', ' ', cleaned_content)
                # Replace HTML entities like &nbsp;
                cleaned_content = re.sub(r'&[a-zA-Z]+;', ' ', cleaned_content)
                # Trim leading/trailing whitespace
                cleaned_content = cleaned_content.strip()
                cleaned_results.append([cleaned_content])
            else:
                cleaned_results.append([None])

        # Combine column headers with cleaned data
        results_with_headers = [column_headers] + cleaned_results

        return results_with_headers
    def sqlite_run_safarihistory(safarihistorypath):
        connection = sqlite3.connect(safarihistorypath)
        cursor = connection.cursor()
        datausequery = """SELECT 
                        datetime('2001-01-01', history_visits.visit_time || ' seconds') as 'Date',
                        history_visits.title as 'Page Title',
                        history_items.url as 'URL',
                        case history_visits.load_successful
                            when 0 then 'No'
                            when 1 then 'Yes'
                            end "Page Loaded",
                        history_items.visit_count as 'Total Visit Count'
                        FROM history_visits LEFT JOIN history_items on history_items.id = history_visits.history_item"""
        cursor.execute(datausequery)
        results = cursor.fetchall()
        column_headers = [description[0] for description in cursor.description]

        # Close the connection
        connection.close()

        # Combine column headers with data
        results_with_headers = [column_headers] + results

        return results_with_headers
    def sqlite_run_TCC(TCCpath):
        connection = sqlite3.connect(TCCpath)
        cursor = connection.cursor()
        datausequery = """SELECT
                    access.service as 'Device Permission',                       
                    ACCESS.client as 'Application Bundle',
                    CASE access.auth_value
                        WHEN 0 THEN 'Denied'
                        WHEN 1 THEN 'Unknown'
                        WHEN 2 THEN 'Granted'
                        WHEN 3 THEN 'Limited'
                        ELSE 'Unknown (' || access.auth_value || ')'
                    END as 'Permission Status'
                    FROM access 
                    ORDER BY access.service, access.client"""
        cursor.execute(datausequery)
        results = cursor.fetchall()
        column_headers = [description[0] for description in cursor.description]

        # Close the connection
        connection.close()

        # Combine column headers with data
        results_with_headers = [column_headers] + results

        return results_with_headers
    def sqlite_run_SMS(SMSdbPath):
        connection = sqlite3.connect(SMSdbPath)
        cursor = connection.cursor()
        
        # More accurate query for group chat identification
        group_chat_query = """
        SELECT 
            chat.ROWID as chat_id,
            chat.display_name as group_name,
            chat.chat_identifier,
            COUNT(DISTINCT chat_handle_join.handle_id) as participant_count,
            GROUP_CONCAT(handle.id, ', ') as participants
        FROM 
            chat
            LEFT JOIN chat_handle_join ON chat.ROWID = chat_handle_join.chat_id
            LEFT JOIN handle ON chat_handle_join.handle_id = handle.ROWID
        GROUP BY
            chat.ROWID
        """
        
        cursor.execute(group_chat_query)
        group_data = {}
        for row in cursor.fetchall():
            chat_id = row[0]
            participant_count = row[3] or 0
            # A chat is a group if it has multiple participants or specific markers
            is_group = (participant_count > 1 or 
                      (row[2] and row[2].startswith('chat')) or 
                      ('chat.plist' in (row[2] or '')))
            
            group_data[chat_id] = {
                "name": row[1] or "", 
                "participants": row[4] or "",
                "is_group": is_group,
                "participant_count": participant_count
            }
        
        # Main query with improved group chat handling
        smsQuery = """SELECT 
        case when message.date != 0 then datetime((message.date + 978307200000000000) / 1000000000, 'unixepoch') end as 'Message Date', 
        chat.ROWID as 'Chat ID',
        
        -- Contact identification
        CASE 
            WHEN handle.id IS NULL THEN ''
            ELSE handle.id 
        END as 'Contact',
        
        -- Fix sender identification to differentiate between user and others
        CASE 
            WHEN message.is_from_me = 1 THEN 'Sent'
            ELSE handle.id
        END as 'Sender',
        
        -- Add clear flag for messages from the user
        case message.is_from_me when 1 then 'Yes' else 'No' end as 'From Me',
        
        -- Other message details remain the same...
        handle.service as "Message Service",
        case message.is_from_me when 1 then 1 else 0 end as 'Is Sent',
        case message.is_delivered when 1 then 1 else 0 end as 'Is Delivered', 
        case message.is_read when 1 then 1 else 0 end as 'Is Read',
        
        case message.is_from_me
            when 1 then message.text
            end as 'Sent',
        case message.is_from_me
            when not 1 then message.text
            end as 'Received',
        
        -- Get detailed attachment information
        GROUP_CONCAT(attachment.filename, '; ') as 'Attachment Files',
        GROUP_CONCAT(attachment.mime_type, '; ') as 'Attachment Types',
        GROUP_CONCAT(attachment.transfer_name, '; ') as 'Attachment Names',
        
        -- Simple count of attachments
        COUNT(attachment.ROWID) as 'Attachment Count'

        FROM message
        LEFT JOIN handle ON message.handle_id = handle.ROWID
        JOIN chat_message_join ON chat_message_join.message_id = message.ROWID
        JOIN chat ON chat_message_join.chat_id = chat.ROWID
        LEFT JOIN message_attachment_join ON message.ROWID = message_attachment_join.message_id
        LEFT JOIN attachment ON attachment.ROWID = message_attachment_join.attachment_id

        GROUP BY message.ROWID
        ORDER BY message.date DESC"""
            
        cursor.execute(smsQuery)
        results = cursor.fetchall()
        
        # Get column headers
        column_headers = [description[0] for description in cursor.description]
        
        # Convert results to list of rows with headers
        results_with_headers = [column_headers]
        
        # Process each message row
        processed_results = []
        
        for row in results:
            row_list = list(row)
            
            # Add group chat information
            chat_id = row[column_headers.index('Chat ID')]
            if chat_id in group_data:
                # Add group chat flag
                is_group = 'Yes' if group_data[chat_id]['is_group'] else 'No'
                row_list.append(is_group)
                
                # Add group name/participants
                if group_data[chat_id]['is_group']:
                    if group_data[chat_id]['name']:
                        display_name = f"{group_data[chat_id]['name']}"
                    else:
                        # Format participants list
                        participants = group_data[chat_id]['participants'].split(', ')
                        if len(participants) <= 3:
                            display_name = f"{', '.join(participants)}"
                        else:
                            display_name = f"{', '.join(participants[:3])}... (+{len(participants)-3})"
                    row_list.append(display_name)
                else:
                    row_list.append('')  # No group name for individual chats
            else:
                row_list.extend(['No', ''])  # Not a group chat
                
            processed_results.append(row_list)
        
        # Update the column headers
        column_headers.extend(['Is Group Chat', 'Group Name'])
        results_with_headers = [column_headers] + processed_results
        
        # Create a DataFrame from the processed results
        df = pd.DataFrame(processed_results, columns=column_headers)
        
        # Close the connection
        connection.close()
        
        # Return both the results with headers and the DataFrame
        return results_with_headers, df

    def sqlite_run_interactionC(interactionCpath):
        connection = sqlite3.connect(interactionCpath)
        cursor = connection.cursor()
        datausequery = """SELECT
      DATETIME(ZINTERACTIONS.ZSTARTDATE + 978307200, 'UNIXEPOCH') AS 'Event Start',
      DATETIME(ZINTERACTIONS.ZENDDATE + 978307200, 'UNIXEPOCH') AS 'Event End',
      ZINTERACTIONS.ZBUNDLEID AS 'Application',
      CASE ZINTERACTIONS.ZDIRECTION
         WHEN '0' THEN 'Incoming'
         WHEN '1' THEN 'Outgoing'
      END 'Direction',
      ZCONTACTS.ZDISPLAYNAME AS 'Sender',
      ZCONTACTS.ZIDENTIFIER AS 'Sender ID',
      RECEIPIENTCONACT.ZDISPLAYNAME AS 'Recipient',
      RECEIPIENTCONACT.ZIDENTIFIER AS 'Recipient ID',
      ZINTERACTIONS.ZDOMAINIDENTIFIER AS 'Domain' 

   FROM ZINTERACTIONS 
   LEFT JOIN ZCONTACTS ON ZINTERACTIONS.ZSENDER = ZCONTACTS.Z_PK
   LEFT JOIN Z_1INTERACTIONS ON ZINTERACTIONS.Z_PK == Z_1INTERACTIONS.Z_3INTERACTIONS
   LEFT JOIN ZATTACHMENT ON Z_1INTERACTIONS.Z_1ATTACHMENTS == ZATTACHMENT.Z_PK
   LEFT JOIN Z_2INTERACTIONRECIPIENT ON ZINTERACTIONS.Z_PK== Z_2INTERACTIONRECIPIENT.Z_3INTERACTIONRECIPIENT
   LEFT JOIN ZCONTACTS RECEIPIENTCONACT ON Z_2INTERACTIONRECIPIENT.Z_2RECIPIENTS== RECEIPIENTCONACT.Z_PK 
            """
        cursor.execute(datausequery)
        results = cursor.fetchall()
        column_headers = [description[0] for description in cursor.description]

        # Close the connection
        connection.close()

        # Combine column headers with data
        results_with_headers = [column_headers] + results

        return results_with_headers

    def retrieve_files_from_backup(backup_path, filedestination, password):
        # File ids in manifest.db for artifacts
        # x photos_Sqlite = '12b144c0bd44f2b3dffd9186d3f9c05b917cee25'
        # x datausage_Sqlite = "0d609c54856a9bb2d56729df1d68f2958a88426b"
        # X addressbook_sqlitedb = "31bb7ba8914766d4ba40d6dfb6113c8b614be442"
        # X accounts3_sqlite = "943624fd13e27b800cc6d9ce1100c22356ee365c"
        # voicemail_db = "992df473bbb9e132f4b3b6e4d33f72171e97bc7a"  # can we do transcripts?
        # X sms_db = "3d0d7e5fb2ce288813306e4d4636395e047a3d28"  # giant csv? pdf takes forever
        # x TCC_db = "64d0019cb3d46bfc8cce545a8ba54b93e7ea9347"  # limit to access to camera, microphone, photos, 
        # x callhistory_sqlite = "5a4935c78a5255723f707230a451d79c540d2741"
        # safari_sqlite = "e74113c185fd8297e140cfcf9c99436c5cc06b57"  ?
        # x cellularusage.db ed1f8fb5a948b40504c19580a458c384659a605e
        # x keychainbackup.plist = "51a4616e576dd33cd2abadfea874eb8ff246bf0e"
        # x notes.sqlite = "ca3bc056d4da0bbf88b5fb3be254f3b7147e639c"
        # x interactionC.db = "1f5a521220a3ad80ebfdc196978df8e7a2e49dee"

        list_of_fileIDs = ['12b144c0bd44f2b3dffd9186d3f9c05b917cee25', "0d609c54856a9bb2d56729df1d68f2958a88426b", "1a0e7afc19d307da602ccdcece51af33afe92c53" ,
                        "31bb7ba8914766d4ba40d6dfb6113c8b614be442", "943624fd13e27b800cc6d9ce1100c22356ee365c",  "3d0d7e5fb2ce288813306e4d4636395e047a3d28", 
                        "64d0019cb3d46bfc8cce545a8ba54b93e7ea9347", "5a4935c78a5255723f707230a451d79c540d2741", "ed1f8fb5a948b40504c19580a458c384659a605e", 
                        "51a4616e576dd33cd2abadfea874eb8ff246bf0e", "ca3bc056d4da0bbf88b5fb3be254f3b7147e639c", "1f5a521220a3ad80ebfdc196978df8e7a2e49dee",
                        "e74113c185fd8297e140cfcf9c99436c5cc06b57", "992df473bbb9e132f4b3b6e4d33f72171e97bc7a"] 

        backup = Backup.from_path(backup_path=backup_path, password=password)
        
        for ID in list_of_fileIDs:
            try:
                backupd_plist = backup.extract_file_id(ID,path=filedestination)
            except Exception as e:
                if isinstance(e, Backup) and 'ErrorCode' in e.args and e.args['ErrorCode'] == 207:
                    print(f"Error extracting file ID {ID}: {e}")

                else:
                    print(f"Error extracting file ID {ID}: {e}")
                    continue
                 
                

    def calculate_itunes_photofile_name(filepathinbackup):      #converts path to sha1 used in backup file name
        builtpath = ('CameraRollDomain-Media/' + filepathinbackup)
        builtpath = builtpath.encode(encoding='UTF-8', errors='strict')
        filehash = sha1(builtpath).hexdigest()
        return str(filehash)

    def retrieve_photos_from_backup(backup_path, filedestination, password, list_of_fileIDs):
        """Extract specific photos from backup using file IDs"""
        try:
            if not list_of_fileIDs:
                print("No file IDs provided to retrieve")
                return 0

            backup = Backup.from_path(backup_path=backup_path, password=password)
            
            # Add counters for tracking
            extracted_count = 0
            failed_ids = []
            
            for ID in list_of_fileIDs:
                try:
                    backup.extract_file_id(ID, path=filedestination)
                    extracted_count += 1
                    print(f"Extracted: {ID}")
                except MissingEntryError:
                    # Handle missing entries specifically
                    failed_ids.append(ID)
                    print(f"Missing entry: {ID}")
                except Exception as e:
                    # Handle other errors
                    failed_ids.append(ID)
                    print(f"Error extracting {ID}: {str(e)}")
            
            print(f"Photo extraction complete: {extracted_count} successful, {len(failed_ids)} failed")
            return extracted_count
            
        except Exception as e:
            print(f"Error in photo extraction: {str(e)}")
            return 0
            backupd_plist = backup.extract_file_id(ID,path=filedestination)
            

    
    def save_to_csv(data_frame, csv_filename, additional_text=None):
        if additional_text is not None:
            with open(csv_filename, 'w') as file:
                file.write(f"{additional_text}\n")

        data_frame.to_csv(csv_filename, mode='a', index=False, header=additional_text is None)
        print(f"Data saved to {csv_filename}")

    def save_to_json(data_frame, json_filename):
        data_frame.to_json(json_filename, orient='records')
        print(f"Data saved to {json_filename}")

    def calculate_itunes_photofile_name(filepathinbackup):      #converts path to sha1 used in backup file name
        builtpath = ('CameraRollDomain-Media/' + filepathinbackup)
        builtpath = builtpath.encode(encoding='UTF-8', errors='strict')
        filehash = sha1(builtpath).hexdigest()
        return str(filehash)

    def retrieve_photos_from_backup(backup_path, filedestination, password, list_of_fileIDs):
        """Extract specific photos from backup using file IDs"""
        try:
            if not list_of_fileIDs:
                print("No file IDs provided to retrieve")
                return 0

            backup = Backup.from_path(backup_path=backup_path, password=password)

            # Add a counter for reporting
            extracted_count = 0
            failed_ids = []
            missing_entry_count = 0

            total_files = len(list_of_fileIDs)
            print(f"Attempting to extract {total_files} photos...")

            for ID in list_of_fileIDs:
                try:
                    backup.extract_file_id(ID, path=filedestination)
                    extracted_count += 1
                    print(f"Extracted {extracted_count}/{total_files}: {ID}")
                except MissingEntryError:
                    missing_entry_count += 1
                    failed_ids.append(ID)
                    print(f"Missing entry: {ID}")
                except Exception as e:
                    failed_ids.append(ID)
                    print(f"Error extracting {ID}: {str(e)}")

            # Print summary
            print(f"Photo extraction complete: {extracted_count} successful, {missing_entry_count} missing")
            if failed_ids and len(failed_ids) < 10:
                print(f"Failed IDs: {', '.join(failed_ids)}")
            elif failed_ids:
                print(f"Failed IDs: {', '.join(failed_ids[:10])}... (and {len(failed_ids) - 10} more)")

            return extracted_count

        except Exception as e:
            print(f"Error in photo extraction: {str(e)}")
            return 0


    def parse_backup(backup_path, password, status_callback=None, taxonomy_target=None):
        """
        Parse an iOS backup and return structured data
        
        Args:
            backup_path (str): Path to the iOS backup directory
            password (str): Password for the iOS backup
            status_callback (callable): Function to call with status updates
            
        Returns:
            dict: Parsed data from the backup
        """
        if status_callback:
            status_callback("Starting backup parsing...")
        
        # Create output folders - use a temporary directory for reports
        report_output_destination = os.path.join(os.path.dirname(backup_path), "ArsenicReports", datetime.now().strftime("%Y%m%d%H%M%S"))
        if not os.path.isdir(report_output_destination):
            os.makedirs(report_output_destination, exist_ok=True)
        
        file_output_destination = os.path.join(report_output_destination, 'Artifacts')
        if not os.path.isdir(file_output_destination):
            os.makedirs(file_output_destination, exist_ok=True)
            
        # Parse basic info
        info_plist_path = os.path.join(backup_path, 'Info.plist')
        device_info = {}
        if os.path.exists(info_plist_path):
            try:
                with open(info_plist_path, 'rb') as plist_file:
                    plist_data = plistlib.load(plist_file)
                    device_info = {
                        'Device Name': plist_data.get('Device Name', ''),
                        'Device Type': plist_data.get('Product Type', ''),
                        'Phone Number': plist_data.get('Phone Number', ''),
                        'IMEI': plist_data.get('IMEI', ''),
                        'Serial Number': plist_data.get('Serial Number', ''),
                        'iOS Version': plist_data.get('Product Version', ''),
                    }
                    
                    # Set global variables for report generation
                    global phonetype, devicename, imei, phonenum, serialnum
                    phonetype = device_info['Device Type']
                    devicename = device_info['Device Name']
                    imei = device_info['IMEI']
                    phonenum = device_info['Phone Number']
                    serialnum = device_info['Serial Number']
            except Exception as e:
                if status_callback:
                    status_callback(f"Error parsing Info.plist: {e}")
        
        # Check encryption status
        encryption_status = {
            'is_encrypted': False,
            'requires_password': False,
            'has_password': False
        }
        
        manifest_plist_path = os.path.join(backup_path, 'Manifest.plist')
        if os.path.exists(manifest_plist_path):
            try:
                with open(manifest_plist_path, 'rb') as plist_file:
                    manifest_data = plistlib.load(plist_file)
                    encryption_status['is_encrypted'] = manifest_data.get('IsEncrypted', False)
                    encryption_status['requires_password'] = encryption_status['is_encrypted']
                    encryption_status['has_password'] = bool(password) if encryption_status['is_encrypted'] else True
            except Exception as e:
                if status_callback:
                    status_callback(f"Error parsing Manifest.plist: {e}")
        
        if status_callback:
            status_callback(f"Device info retrieved: {device_info.get('Device Name', 'Unknown device')}")
        
        # Initialize results dictionary
        results = {
            'device_info': device_info,
            'encryption_status': encryption_status,
            'sms_messages': [],
            'call_history': [],
            'installed_apps': [],
            'contacts': [],
            'browser_history': [],
            'photo_analysis': []
        }
        
        # Extract files from backup
        if status_callback:
            status_callback("Extracting files from backup...")
        
        try:
            # List of file IDs to extract
            list_of_fileIDs = ['12b144c0bd44f2b3dffd9186d3f9c05b917cee25',  # Photos.sqlite
                              "0d609c54856a9bb2d56729df1d68f2958a88426b",   # DataUsage.sqlite
                              "31bb7ba8914766d4ba40d6dfb6113c8b614be442",   # AddressBook.sqlitedb
                              "943624fd13e27b800cc6d9ce1100c22356ee365c",   # Accounts3.sqlite
                              "3d0d7e5fb2ce288813306e4d4636395e047a3d28",   # sms.db
                              "64d0019cb3d46bfc8cce545a8ba54b93e7ea9347",   # TCC.db
                              "5a4935c78a5255723f707230a451d79c540d2741",   # CallHistory.storedata
                              "1f5a521220a3ad80ebfdc196978df8e7a2e49dee",   # interactionC 
                              "e74113c185fd8297e140cfcf9c99436c5cc06b57"]   
            
            backup = Backup.from_path(backup_path=backup_path, password=password)
            for ID in list_of_fileIDs:
                try:
                    backup.extract_file_id(ID, path=file_output_destination)
                    if status_callback:
                        status_callback(f"Extracted file {ID}")
                except Exception as e:
                    if status_callback:
                        status_callback(f"Error extracting file {ID}: {e}")
        except Exception as e:
            if status_callback:
                status_callback(f"Error setting up backup extraction: {e}")
        
        # Process the extracted files
        if status_callback:
            status_callback("Processing extracted files...")
        
        recovered_files = []
        if os.path.exists(file_output_destination):
            recovered_files = os.listdir(file_output_destination)
        
        for artifact in recovered_files:
            file_path = os.path.join(file_output_destination, artifact)
            
            if "sms.db" in artifact:
                if status_callback:
                    status_callback("Processing SMS messages...")
                try:
                    sms_data, sms_df = sqlite_run_SMS(file_path)
                    if len(sms_data) > 1:  # Skip header row
                        # Convert DataFrame to list of dicts for easier handling in the UI
                        messages = []
                        for _, row in sms_df.iterrows():
                            message = {
                                'date': row.get('Message Date', ''),
                                'phone_number': row.get('Contact', ''),
                                'service': row.get('Message Service', ''),
                                'direction': 'Sent' if pd.notna(row.get('Sent')) else 'Received',
                                'message': row.get('Sent') if pd.notna(row.get('Sent')) else row.get('Received', ''),
                                # Include ALL attachment fields directly:
                                'Attachment Names': row.get('Attachment Names', ''),
                                'Attachment Files': row.get('Attachment Files', ''),
                                'Attachment Types': row.get('Attachment Types', ''),
                                'Attachment Count': row.get('Attachment Count', 0)
                            }
                            messages.append(message)
                        results['sms_messages'] = messages
                except Exception as e:
                    if status_callback:
                        status_callback(f"Error processing SMS: {e}")
            
            # Process call history
            if 'CallHistory.storedata' in artifact:
                if status_callback:
                    status_callback("Processing call history...")
                try:
                    call_data = sqlite_run_callhistory(file_path)
                    if len(call_data) > 1:  # Skip header row
                        calls = []
                        for row in call_data[1:]:  # Skip the header
                            call = {
                                'date': row[0] if len(row) > 0 else '',
                                'duration': row[1] if len(row) > 1 else '',
                                'phone_number': row[2] if len(row) > 2 else '',
                                'direction': row[3] if len(row) > 3 else '',
                                'answered': row[4] if len(row) > 4 else '',
                                'call_type': row[5] if len(row) > 5 else ''
                            }
                            calls.append(call)
                        results['call_history'] = calls
                except Exception as e:
                    if status_callback:
                        status_callback(f"Error processing call history: {e}")
            
            # Process contacts
            if "AddressBook.sqlitedb" in artifact:
                if status_callback:
                    status_callback("Processing contacts...")
                try:
                    contact_data = sqlite_run_addressbook(file_path)
                    if len(contact_data) > 1:  # Skip header row
                        contacts = []
                        for row in contact_data[1:]:  # Skip the header
                            contact = {
                                'last_name': row[0] if len(row) > 0 else '',
                                'first_name': row[1] if len(row) > 1 else '',
                                'main_number': row[2] if len(row) > 2 else '',
                                'iphone_number': row[3] if len(row) > 3 else '',
                                'mobile_number': row[4] if len(row) > 4 else '',
                                'home_number': row[5] if len(row) > 5 else '',
                                'work_number': row[6] if len(row) > 6 else '',
                                'email': row[7] if len(row) > 7 else ''
                            }
                            contacts.append(contact)
                        results['contacts'] = contacts
                except Exception as e:
                    if status_callback:
                        status_callback(f"Error processing contacts: {e}")

            # Make sure to process data usage
            if "0d609c54856a9bb2d56729df1d68f2958a88426b" in artifact or "DataUsage.sqlite" in artifact:  # DataUsage.sqlite
                if status_callback:
                    status_callback("Processing data usage...")
                try:
                    data_usage = parse_ios_backup.sqlite_run_datausage(file_path)
                    if data_usage and len(data_usage) > 1:  # Skip header row
                        headers = data_usage[0]
                        usage_data = []
                        for row in data_usage[1:]:
                            usage_entry = {}
                            for i, header in enumerate(headers):
                                if i < len(row):
                                    usage_entry[header] = row[i]
                                else:
                                    usage_entry[header] = ''
                            usage_data.append(usage_entry)
                        results['data_usage'] = usage_data
                except Exception as e:
                    if status_callback:
                        status_callback(f"Error processing data usage: {e}")

            # Process accounts
            if "943624fd13e27b800cc6d9ce1100c22356ee365c" in artifact or "Accounts3.sqlite" in artifact:  # Accounts3.sqlite
                if status_callback:
                    status_callback("Processing accounts...")
                try:
                    accounts_data = parse_ios_backup.sqlite_run_accounts3(file_path)
                    if accounts_data and len(accounts_data) > 1:  # Skip header row
                        headers = accounts_data[0]
                        accounts = []
                        for row in accounts_data[1:]:
                            account = {}
                            for i, header in enumerate(headers):
                                if i < len(row):
                                    account[header] = row[i]
                                else:
                                    account[header] = ''
                            accounts.append(account)
                        results['accounts'] = accounts
                except Exception as e:
                    if status_callback:
                        status_callback(f"Error processing accounts: {e}")

            # Process TCC permissions
            if "64d0019cb3d46bfc8cce545a8ba54b93e7ea9347" in artifact or "TCC.db" in artifact:  # TCC.db
                if status_callback:
                    status_callback("Processing app permissions...")
                try:
                    permissions_data = parse_ios_backup.sqlite_run_TCC(file_path)
                    if permissions_data and len(permissions_data) > 1:  # Skip header row
                        headers = permissions_data[0]
                        permissions = []
                        for row in permissions_data[1:]:
                            permission = {}
                            for i, header in enumerate(headers):
                                if i < len(row):
                                    permission[header] = row[i]
                                else:
                                    permission[header] = ''
                        permissions.append(permission)
                        results['permissions'] = permissions
                except Exception as e:
                    if status_callback:
                        status_callback(f"Error processing app permissions: {e}")
     
            if "interactionC.db" in artifact:
                if status_callback:
                    status_callback("Processing app interactions...")
                try:
                    interactions_data = parse_ios_backup.sqlite_run_interactionC(file_path)
                    if interactions_data and len(interactions_data) > 1:  # Skip header row
                        headers = interactions_data[0]
                        interactions = []
                        for row in interactions_data[1:]:
                            interaction = {}
                            for i, header in enumerate(headers):
                                if i < len(row):
                                    interaction[header] = row[i]
                                else:
                                    interaction[header] = ''
                        interactions.append(interaction)
                        results['interactions'] = interactions
                except Exception as e:
                    if status_callback:
                        status_callback(f"Error processing interactions: {e}")
     
        if status_callback:
            status_callback("Parsing complete!")
        
        return results

def format_device_info_header(device_info):
    """Create a standardized header with device information for reports"""
    header = "DEVICE INFORMATION\n"
    if device_info:
        for key, value in device_info.items():
            if value:  # Only include non-empty values
                header += f"{key}: {value}\n"
    header += "\n"
    return header


# For the photo report (and can be applied to other reports):
if 'photo_output_destination' in locals() and os.path.exists(photo_output_destination) and 'filtered_df' in locals():

    # Create report with device info header
    device_header = format_device_info_header(device_info)
    
    # Create extraction summary with accurate counts
    recovered_count = filtered_df['Recovered'].sum()
    total_attempted = len(filtered_df)
    missing_count = total_attempted - recovered_count
    
    extraction_summary = (
        f"EXTRACTION SUMMARY\n"
        f"Photos successfully extracted: {recovered_count}/{total_attempted}\n"
        f"Photos not found (missing entries): {missing_count}\n"
    )
    if missing_count > 0:
        extraction_summary += f"Missing entries: {', '.join(filtered_df[filtered_df['Recovered'] == 0]['File ID'].tolist())}\n"        
    extraction_summary += "\nEXTRACTION DETAILS\n"

    # Save report with device info header
    photo_report_csv = os.path.join(reports_dir, f'Photo_Report_{taxonomy_target}.csv')
    
    # Write headers first, then the DataFrame
    with open(photo_report_csv, 'w') as f:
        f.write(device_header)  # Add device info at the very top
        f.write(extraction_summary)
    
    # Append the DataFrame to the file with header but no index
    filtered_df.to_csv(photo_report_csv, mode='a', index=False)



def create_timeline_report(report_path, device_info, report_title="TIMELINE REPORT", timezone=None):
   return None

# Update the description generation for SMS messages
def create_sms_description(row):
    parts = []
    
    # Add contact info if available (differentiates between group and individual chats)
    if "Contact" in df.columns and pd.notna(row.get("Contact")):
        parts.append(f"Contact: {row['Contact']}")
    
    # Always show who sent the message (more important in group chats)
    if "Sender" in df.columns and pd.notna(row.get("Sender")):
        sender = row["Sender"]
        # Check if this is a group chat
        if "Is Group Chat" in df.columns and row.get("Is Group Chat") == "Yes":
            is_from_me = row.get("From Me") == "Yes"
            if is_from_me:
                parts.append("Sender: Me")
            else:
                parts.append(f"Sender: {sender}")
    
    # Indicate if the message has attachments
    if "Attachment Count" in df.columns and pd.notna(row.get("Attachment Count")) and int(row.get("Attachment Count", 0)) > 0:
        parts.append(f"📎 {row['Attachment Count']} attachment(s)")
    
    # Add group chat info if available
    if "Is Group Chat" in df.columns and pd.notna(row.get("Is Group Chat")) and row["Is Group Chat"] == "Yes":
        if "Group Name" in df.columns and pd.notna(row.get("Group Name")):
            parts.append(f"Group: {row['Group Name']}")
        else:
            parts.append("Group chat")
    
    return " | ".join(parts)

# In app.py, add to the photos tab/section:

def display_photos(self, photo_output_path):
    """Display extracted photos in a responsive grid layout"""
    # Clear existing content
    for widget in self.photos_frame.winfo_children():
        widget.destroy()
    
    # Check if photos were extracted
    if not os.path.exists(photo_output_path) or not os.listdir(photo_output_path):
        no_photos_label = ttk.Label(self.photos_frame, text="No photos found or extracted")
        no_photos_label.pack(pady=20)
        return
        
    # Create a scrollable frame for photos
    canvas = tk.Canvas(self.photos_frame)
    scrollbar = ttk.Scrollbar(self.photos_frame, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)
    
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    
    # Create photo grid layout
    photo_grid = ttk.Frame(scrollable_frame)
    photo_grid.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Load and display photos
    try:
        photo_files = [f for f in os.listdir(photo_output_path) 
                      if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))]
        
        # Sort by modification time (newest first)
        photo_files.sort(key=lambda x: os.path.getmtime(os.path.join(photo_output_path, x)), 
                         reverse=True)
        
        # Create thumbnails and add to grid
        MAX_COLUMNS = 4  # Number of thumbnails per row
        THUMBNAIL_SIZE = 150
        
        for i, photo_file in enumerate(photo_files):
            row, col = divmod(i, MAX_COLUMNS)
            
            # Create frame for each photo
            photo_frame = ttk.Frame(photo_grid)
            photo_frame.grid(row=row, column=col, padx=5, pady=5)
            
            try:
                # Load and resize image
                img_path = os.path.join(photo_output_path, photo_file)
                img = Image.open(img_path)
                img.thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE))
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(THUMBNAIL_SIZE, THUMBNAIL_SIZE))
                img_label = ctk.CTkLabel(photo_frame, image=ctk_img, text="")
                
                # Store reference to prevent garbage collection
                photo_frame.image = ctk_img
                
                # Add the image to a label
                img_label.pack()
                
                # Add file name as label
                name_label = ttk.Label(photo_frame, text=photo_file[:15] + "..." if len(photo_file) > 15 else photo_file)
                name_label.pack()
                
                # Add click behavior to show full-size image
                img_label.bind("<Button-1>", lambda e, path=img_path: self.show_full_image(path))
                
            except Exception as e:
                error_label = ttk.Label(photo_frame, text=f"Error: {str(e)[:20]}...")
                error_label.pack(padx=10, pady=10)
        
    except Exception as e:
        error_label = ttk.Label(scrollable_frame, text=f"Error loading photos: {str(e)}")
        error_label.pack(pady=20)
    
    # Pack the canvas and scrollbar
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

def convert_timezone(timestamp_str, target_timezone):
    """Convert a timestamp string from UTC to the target timezone"""
    import datetime
    import pytz
    from tzlocal import get_localzone
    
    if not timestamp_str:
        return timestamp_str
    
    try:
        # Handle different timestamp formats
        dt_utc = None
        formats_to_try = [
            "%Y-%m-%d %H:%M:%S UTC",  # Format with UTC suffix
            "%Y-%m-%d %H:%M:%S",      # Format without timezone
            "%Y-%m-%d %H:%M:%S.%f",   # Format with microseconds
            "%Y-%m-%d",               # Date only format
            "%m/%d/%Y %H:%M:%S",      # US format with time
            "%Y-%m-%dT%H:%M:%S"       # ISO format
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
                    dt_utc = dt_utc.replace(tzinfo=pytz.UTC)  # Assume UTC 
                    break
            except ValueError:
                continue
        
        if not dt_utc:
            return timestamp_str
            
        # Convert to selected timezone with consistent format
        timezone_format = "%Y-%m-%d %H:%M:%S (%Z)"
        
        if target_timezone.startswith("System Time"):
            local_tz = get_localzone()
            dt_local = dt_utc.astimezone(local_tz)
            return dt_local.strftime(timezone_format)
        elif target_timezone == "UTC":
            # Use consistent format for UTC
            return dt_utc.strftime(timezone_format)
        else:
            # Handle other timezone options
            target_tz = pytz.timezone(target_timezone)
            dt_target = dt_utc.astimezone(target_tz)
            return dt_target.strftime(timezone_format)
    except Exception as e:
        print(f"Error converting timestamp '{timestamp_str}': {e}")
        return timestamp_str

