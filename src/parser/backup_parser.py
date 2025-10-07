#Copyright (c) 2025 North Loop Consulting, LLC - Charlie Rubisoff
#GPLv3 License - https://www.gnu.org/licenses/gpl-3.0.en.html

from pyiosbackup import Backup
from pyiosbackup.exceptions import MissingEntryError
import plistlib
import sqlite3
import os
import re
from datetime import datetime, timedelta
import pandas as pd
from hashlib import sha1

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


def save_report_with_device_info(df, csv_path, device_info, report_title, timezone=None):
    
    device_header = f"{report_title}\n\nDEVICE INFORMATION\n"
    if device_info:
        for key, value in device_info.items():
            if value:  # Only include non-empty values
                device_header += f"{key}: {value}\n"
    device_header += "\n"
    
    if timezone:
        for column in df.columns:
            if 'date' in column.lower() or 'time' in column.lower():
                df[column] = df[column].apply(
                    lambda x: convert_timezone(x, timezone) if x and 'UTC' in str(x) else x
                )
    with open(csv_path, 'w') as f:
        f.write(device_header)
    
    df.to_csv(csv_path, mode='a', index=False)
    
    return csv_path
def replace_taxonomy_id_w_descr(df):   # use string id rather than number
    df['Scene Classification'] = df['Scene Classification'].replace(taxonomy_Dict)

def mac_absolute_time_to_datetime(mac_time):
    mac_epoch = datetime(2001, 1, 1, 0, 0, 0)
    dt = mac_epoch + timedelta(seconds=mac_time)
    dt = dt.replace(microsecond=0)
    return str(dt) + " UTC"

def format_as_percentage(value):
    return f'{value * 100:.0f}'
def photo_taxonomy(photosqlitepath):       
    sqlite_file = photosqlitepath
    if sqlite_file is None:
        print("The 'photos.sqlite' file was not found in the specified folder or its subfolders.")
        return pd.DataFrame()  # Return empty DataFrame instead of None
    try:
        conn = sqlite3.connect(sqlite_file)
        cur = conn.cursor()
    except sqlite3.Error as e:
        print(f"Error connecting to {sqlite_file}: {e}")
        return pd.DataFrame()  # Return empty DataFrame instead of None
   
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
    # DO NOT convert taxonomy IDs to descriptions here - that should happen after filtering
    # replace_taxonomy_id_w_descr(df=df)  # ❌ REMOVED - this breaks numeric filtering
    df['Confidence'] = df["Confidence"].apply(format_as_percentage)
    df["Date Created"] = df["Date Created"].apply(mac_absolute_time_to_datetime)
    df["Date Added"] = df["Date Added"].apply(mac_absolute_time_to_datetime)
    conn.close()
    return df


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
    list_of_paths = []  # Initialize list for photo file IDs

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
        
        if status_callback:
            status_callback(f"Opening backup at: {backup_path}")
        try:
            backup = Backup.from_path(backup_path=backup_path, password=password)
            if status_callback:
                status_callback("Backup opened successfully")
        except Exception as backup_error:
            if status_callback:
                if "BackupPasswordIsRequired" in str(type(backup_error)):
                    status_callback("ERROR: This backup is encrypted and requires a password!")
                    status_callback("Please provide the backup password and try again.")
                else:
                    status_callback(f"Error opening backup: {backup_error}")
                    status_callback(f"Backup error type: {type(backup_error)}")
            return results  # Return early if backup can't be opened
            
        for ID in list_of_fileIDs:
            try:
                backup.extract_file_id(ID, path=file_output_destination)
                if status_callback:
                    status_callback(f"Successfully extracted file {ID}")
            except Exception as e:
                if status_callback:
                    status_callback(f"Error extracting file {ID}: {e}")
    except Exception as e:
        if status_callback:
            status_callback(f"Error setting up backup extraction: {e}")
            status_callback(f"Backup path: {backup_path}")
            status_callback(f"Password provided: {'Yes' if password else 'No'}")
        return results  # Return early if backup can't be opened
    
    # Process the extracted files
    if status_callback:
        status_callback("Processing extracted files...")
    
    recovered_files = []
    if os.path.exists(file_output_destination):
        recovered_files = os.listdir(file_output_destination)
        if status_callback:
            status_callback(f"Found {len(recovered_files)} files to process")
            if recovered_files:
                status_callback(f"Extracted files: {', '.join(recovered_files)}")
    else:
        if status_callback:
            status_callback(f"Artifact directory does not exist: {file_output_destination}")
    
    # Single loop for processing all files
    for artifact in recovered_files:
        file_path = os.path.join(file_output_destination, artifact)
        
        if status_callback:
            status_callback(f"Processing file: {artifact}")
        
        # Process SMS messages - look for both file ID and common name
        if "3d0d7e5fb2ce288813306e4d4636395e047a3d28" in artifact or "sms.db" in artifact:
            if status_callback:
                status_callback(f"Found SMS database file: {artifact}")
                status_callback("Processing SMS messages...")
            try:
                sms_data, sms_df = parse_ios_backup.sqlite_run_SMS(file_path)
                if status_callback:
                    status_callback(f"SMS extraction returned {len(sms_data)} records")
                    status_callback(f"SMS DataFrame columns: {list(sms_df.columns) if hasattr(sms_df, 'columns') else 'No columns'}")
                    status_callback(f"SMS DataFrame shape: {sms_df.shape if hasattr(sms_df, 'shape') else 'No shape'}")
                    
                if len(sms_data) > 1:  # Skip header row
                    # Save to CSV
                    csv_path = os.path.join(reports_dir, 'Messages.csv')
                    save_report_with_device_info(sms_df, csv_path, device_info, "SMS MESSAGES REPORT", timezone=timezone)

                    if status_callback:
                        status_callback(f"Saved SMS messages to {csv_path}")
                    
                    # Process for UI display
                    if status_callback:
                        status_callback(f"SMS DataFrame shape: {sms_df.shape}")
                        status_callback(f"SMS DataFrame columns: {list(sms_df.columns)}")
                        status_callback(f"SMS DataFrame first few rows: {sms_df.head(2).to_dict()}")
                    
                    messages = []
                    for idx, row in sms_df.iterrows():
                        # Use the actual column names from the CSV file
                        message = {
                            'date': row.get('Message Date', ''),
                            'phone_number': row.get('Contact', ''),
                            'service': row.get('Message Service', ''),
                            'direction': 'Sent' if row.get('From Me') == 'Yes' else 'Received',
                            'message': row.get('Sent', '') if pd.notna(row.get('Sent')) and row.get('Sent') != '' else row.get('Received', ''),
                            'sender': row.get('Sender', ''),
                            'is_sent': row.get('Is Sent', ''),
                            'is_delivered': row.get('Is Delivered', ''),
                            'is_read': row.get('Is Read', ''),
                            'attachment_files': row.get('Attachment Files', ''),
                            'attachment_types': row.get('Attachment Types', ''),
                            'attachment_names': row.get('Attachment Names', ''),
                            'attachment_count': row.get('Attachment Count', 0),
                            'is_group_chat': row.get('Is Group Chat', ''),
                            'group_name': row.get('Group Name', ''),
                            'chat_id': row.get('Chat ID', '')
                        }
                        messages.append(message)
                        if len(messages) <= 3 and status_callback:  # Debug first few messages
                            status_callback(f"Message {len(messages)}: {message}")
                    
                    results['sms_messages'] = messages
                    if status_callback:
                        status_callback(f"Added {len(messages)} SMS messages to results")
                else:
                    if status_callback:
                        status_callback(f"SMS data length check failed: {len(sms_data)} <= 1")
            except Exception as e:
                if status_callback:
                    status_callback(f"Error processing SMS: {e}")
                    status_callback(f"SMS error type: {type(e)}")
                import traceback
                if status_callback:
                    status_callback(f"SMS traceback: {traceback.format_exc()}")
        
        # Process call history
        if "5a4935c78a5255723f707230a451d79c540d2741" in artifact or "CallHistory.storedata" in artifact:
            if status_callback:
                status_callback(f"Found call history file: {artifact}")
                status_callback("Processing call history...")
            try:
                call_data = parse_ios_backup.sqlite_run_callhistory(file_path)
                if status_callback:
                    status_callback(f"Call history extraction returned {len(call_data)} records")
                if len(call_data) > 1:  # Skip header row
                    # Save to CSV
                    csv_path = os.path.join(reports_dir, 'Call_History.csv')
                    call_df = pd.DataFrame(call_data[1:], columns=call_data[0])
                    save_report_with_device_info(call_df, csv_path, device_info, "CALL HISTORY REPORT", timezone=timezone)

                    
                    if status_callback:
                        status_callback(f"Saved call history to {csv_path}")
                    
                    # Process for UI display
                    calls = []
                    for row in call_data[1:]:  # Skip the header
                        call = {
                            'date': row[0] if len(row) > 0 else '',           # Date
                            'duration': row[1] if len(row) > 1 else '',       # Duration  
                            'phone_number': row[2] if len(row) > 2 else '',   # Other Party
                            'direction': row[3] if len(row) > 3 else '',      # Call Direction
                            'answered': row[4] if len(row) > 4 else '',       # Answered
                            'call_type': row[5] if len(row) > 5 else ''       # CallType
                        }
                        calls.append(call)
                    results['call_history'] = calls
                    if status_callback:
                        status_callback(f"Added {len(calls)} call records to results")
            except Exception as e:
                if status_callback:
                    status_callback(f"Error processing call history: {e}")
        
        # Process contacts
        if "31bb7ba8914766d4ba40d6dfb6113c8b614be442" in artifact or "AddressBook.sqlitedb" in artifact:
            if status_callback:
                status_callback("Processing contacts...")
            try:
                contact_data = parse_ios_backup.sqlite_run_addressbook(file_path)
                if status_callback:
                    status_callback(f"Contact data length: {len(contact_data)}")
                    if len(contact_data) > 0:
                        status_callback(f"Contact data header: {contact_data[0] if len(contact_data) > 0 else 'No header'}")
                        if len(contact_data) > 1:
                            status_callback(f"Contact data first row: {contact_data[1] if len(contact_data) > 1 else 'No first row'}")
                
                if len(contact_data) > 1:  # Skip header row
                    # Save to CSV
                    csv_path = os.path.join(reports_dir, 'Contacts.csv')
                    contact_df = pd.DataFrame(contact_data[1:], columns=contact_data[0])
                    save_report_with_device_info(contact_df, csv_path, device_info, "CONTACTS REPORT", timezone=timezone)
                    if status_callback:
                        status_callback(f"Saved contacts to {csv_path}")
                    
                    # Process for UI display using the DataFrame for consistency
                    contacts = []
                    for idx, row in contact_df.iterrows():
                        contact = {
                            'first_name': str(row.get('First', '')),
                            'last_name': str(row.get('Last', '')),
                            'main_number': str(row.get('Phone', '')),
                            'mobile_number': str(row.get('Phone', '')),  # Use Phone for mobile since that's the main number
                            'home_number': str(row.get('Phone', '')) if str(row.get('Phone_label', '')).lower() == 'home' else '',
                            'work_number': str(row.get('Phone', '')) if str(row.get('Phone_label', '')).lower() == 'work' else '',
                            'email': str(row.get('Email', ''))
                        }
                        contacts.append(contact)
                    results['contacts'] = contacts
                    if status_callback:
                        status_callback(f"Added {len(contacts)} contacts to results")
                        if len(contacts) > 0:
                            status_callback(f"First contact example: {contacts[0]}")
                else:
                    if status_callback:
                        status_callback(f"No contact data found or insufficient data: {len(contact_data)}")
            except Exception as e:
                if status_callback:
                    status_callback(f"Error processing contacts: {e}")
                import traceback
                status_callback(f"Contact error traceback: {traceback.format_exc()}")

        # Process data usage
        if "0d609c54856a9bb2d56729df1d68f2958a88426b" in artifact or "DataUsage.sqlite" in artifact:
            if status_callback:
                status_callback("Processing data usage...")
            try:
                data_usage = parse_ios_backup.sqlite_run_datausage(file_path)
                if len(data_usage) > 1:  # Skip header row
                    # Save to CSV
                    csv_path = os.path.join(reports_dir, 'Data_Usage.csv')

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
                    csv_path = os.path.join(reports_dir, 'Accounts.csv')
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
                    csv_path = os.path.join(reports_dir, 'Notes.csv')
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
                    csv_path = os.path.join(reports_dir, 'App_Permissions.csv')
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
                    csv_path = os.path.join(reports_dir, 'Safari_History.csv')
                    safari_df = pd.DataFrame(safari_data[1:], columns=safari_data[0])
                    save_report_with_device_info(safari_df, csv_path, device_info, "SAFARI BROWSING HISTORY REPORT", timezone=timezone)
                    if status_callback:
                        status_callback(f"Saved Safari history to {csv_path}")
                    
                    # Process for UI display
                    # headers = safari_data[0]

                    # safari_history = []
                    # for row in safari_data[1:]:
                    #     history_item = {}
                    #     for i, header in enumerate(headers):
                    #         if i < len(row):
                    #             history_item[header] = row[i]
                    #         else:
                    #             history_item[header] = ''
                    #     safari_history.append(history_item)
                    # results['safari_history'] = safari_history
                    headers = safari_data[0]
                    safari_history = []
                    for row in safari_data[1:]:
                        history_item = { header: row[i] if i < len(row) else '' 
                                        for i, header in enumerate(headers) }
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
                    csv_path = os.path.join(reports_dir, 'InteractionC.csv')
                    interaction_df = pd.DataFrame(interaction_data[1:], columns=interaction_data[0])
                    save_report_with_device_info(interaction_df, csv_path, device_info, "InteractionC REPORT", timezone=timezone)
                    headers = interaction_data[0]
                    interactions = [
                        dict(zip(headers, row))
                        for row in interaction_data[1:]
                    ]
                    results['interactions'] = interactions
                if status_callback:
                    status_callback(f"Saved interactions to {csv_path}")
            except Exception as e:
                print(f"Error processing interaction data: {e}")
        
        # DEBUG: Print what artifact we're checking
        print(f"DEBUG: Processing artifact: {artifact}")
        
        # Check for Photos.sqlite file (either by file ID or renamed filename)
        if '12b144c0bd44f2b3dffd9186d3f9c05b917cee25' in artifact or 'Photos.sqlite' in artifact:
            print("DEBUG: Found Photos.sqlite file for processing")
            # Skip photo processing entirely if no taxonomy target is provided
            if taxonomy_target is None:
                if status_callback:
                    status_callback("Skipping photo processing (option not selected)")
                continue  # Skip to the next artifact
            
            print(f"Processing photos for taxonomy target: {taxonomy_target}")
            
            # Use the correct path to the Photos.sqlite file in Artifacts folder
            photosqlite_path = os.path.join(file_output_destination, artifact)
            print(f"Photos.sqlite path: {photosqlite_path}")
            
            # Create photos output dir with descriptive name
            taxonomy_description = taxonomy_Dict.get(taxonomy_target, f"unknown_{taxonomy_target}")
            photo_folder = f"Photos_{taxonomy_description}_{taxonomy_target}"
            photo_output_destination = os.path.join(report_output_destination, photo_folder)
            os.makedirs(photo_output_destination, exist_ok=True)
            print(f"Photo output destination: {photo_output_destination}")
            
            if status_callback:
                status_callback(f"Analyzing photos for: {taxonomy_description}")
            
            try:
                print("Running photo taxonomy analysis...")
                taxonomyquery = parse_ios_backup.photo_taxonomy(photosqlite_path)
                print(f"Raw taxonomy query returned {len(taxonomyquery)} total records")
                
                taxonomyquery['Confidence'] = pd.to_numeric(taxonomyquery['Confidence'], errors='coerce')
                # Filter by the numeric taxonomy_target
                filtered_df = taxonomyquery[(taxonomyquery['Scene Classification'] == taxonomy_target) & (taxonomyquery['Confidence'] > 5)].copy() 
                print(f"Filtered DataFrame has {len(filtered_df)} matching records")
                
                if len(filtered_df) > 0:
                    photo_records = filtered_df.to_dict('records')
                    results['photo_analysis'] = photo_records
                    print(f"Added {len(photo_records)} photo records to results dictionary")
                    
                    if status_callback:
                        status_callback(f"Found {len(photo_records)} images matching {taxonomy_description}")
        
                    # Build list of file IDs for extraction
                    pathdf = (filtered_df['Path'] + '/' + filtered_df['Filename'])
                    for thing in pathdf:
                        print(f"Processing photo path: {thing}")
                        fileid = parse_ios_backup.calculate_itunes_photofile_name(thing)
                        print(f"Generated File ID: {fileid}")
                        list_of_paths.append(fileid)
                    
                    print(f"Total file IDs for extraction: {len(list_of_paths)}")
                    
                    # Extract the photos from backup
                    if list_of_paths:
                        try:    
                            print("Starting photo extraction from backup...")
                            if status_callback:
                                status_callback(f"Extracting {len(list_of_paths)} photos from backup...")
                            
                            extracted_count = parse_ios_backup.retrieve_photos_from_backup(
                                backup_path=backup_path, 
                                filedestination=photo_output_destination, 
                                password=password, 
                                list_of_fileIDs=list_of_paths
                            )
                            
                            print(f"Successfully extracted {extracted_count} photos")
                            if status_callback:
                                status_callback(f"Successfully extracted {extracted_count} photos to {photo_folder}")
                            
                            # Store extraction results
                            results['extracted_photos_count'] = extracted_count
                            results['extracted_photos_path'] = photo_output_destination
                            
                            # Generate photo report with thumbnails here (within scope of filtered_df)
                            generate_photo_report(filtered_df, photo_output_destination, reports_dir, taxonomy_target, taxonomy_description, device_info, extracted_count, timezone, status_callback)
                            
                        except Exception as e:
                            print(f"Error retrieving photos: {e}")
                            if status_callback:
                                status_callback(f"Error retrieving photos: {e}")
                    else:
                        print("No photo file IDs generated for extraction")
                else:
                    print(f"No images found matching taxonomy target {taxonomy_target}")
                    if status_callback:
                        status_callback(f"No images found matching {taxonomy_description}")

            except Exception as e:
                print(f"Error running photo taxonomy: {e}")
                if status_callback:
                    status_callback(f"Error analyzing photos: {e}")
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

        # After photo extraction, add summary information
        if 'extracted_count' in locals() and extracted_count > 0:
            if status_callback:
                status_callback(f"Successfully extracted {extracted_count} photos")
            results['extracted_photos_path'] = photo_output_destination
        elif list_of_paths:
            if status_callback:
                status_callback("Photo extraction completed but some files may not have been found")

        # Continue with other processing:
        # Log completion of photo extraction attempt
        if 'extracted_count' in locals() and list_of_paths:
            if extracted_count > 0:
                if status_callback:
                    status_callback(f"Successfully extracted {extracted_count} photos")
                results['extracted_photos_path'] = photo_output_destination
            else:
                if status_callback:
                    status_callback(f"Warning: Could not extract {len(list_of_paths)} photos from backup")

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
    
    # Add device info to results
    results['device_info'] = device_info
    
    # Debug output before returning
    if status_callback:
        status_callback(f"DEBUG: Returning results with keys: {list(results.keys())}")
        for key, value in results.items():
            if isinstance(value, list):
                status_callback(f"DEBUG: {key}: {len(value)} items")
            elif isinstance(value, dict):
                status_callback(f"DEBUG: {key}: {len(value)} keys")
            else:
                status_callback(f"DEBUG: {key}: {type(value)}")
    
    # Return all collected results
    return results

class parse_ios_backup:
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
    phonetype = ""
    devicename = ""
    phonenum = ""
    imei = ""
    serialnum = ""
    target = ''

    list_of_paths = []
    now = datetime.now()
    

    def replace_taxonomy_id_w_descr(df):   # use string id rather than number
        df['Scene Classification'] = df['Scene Classification'].replace(taxonomy_Dict)

    def format_as_percentage(value):
        return f'{value * 100:.0f}'
        
    def mac_absolute_time_to_datetime(mac_time):
        mac_epoch = datetime(2001, 1, 1, 0, 0, 0)
        dt = mac_epoch + timedelta(seconds=mac_time)
        dt = dt.replace(microsecond=0)
        return str(dt) + " UTC"
    
    @staticmethod
    def sqlite_run_accounts3(accounts3path):
        connection = sqlite3.connect(accounts3path)
        cursor = connection.cursor()
        
        act3query = """SELECT 
            datetime('2001-01-01', ZACCOUNT.ZDATE || ' seconds') AS "Account Date",
            ZACCOUNT.ZUSERNAME AS "Username", 
            ZACCOUNT.ZACCOUNTDESCRIPTION AS "Description"
        FROM ZACCOUNT
        WHERE ZACCOUNT.ZDATE IS NOT NULL
            AND ZACCOUNT.ZUSERNAME IS NOT NULL
            AND ZACCOUNT.ZACCOUNTDESCRIPTION IS NOT NULL;"""

        cursor.execute(act3query)
        results = cursor.fetchall()

        column_headers = [description[0] for description in cursor.description]
        connection.close()
        results_with_headers = [column_headers] + results

        return results_with_headers

    @staticmethod
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
        connection.close()
        results_with_headers = [column_headers] + results
    
        return results_with_headers

    @staticmethod
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
        connection.close()
        results_with_headers = [column_headers] + results
    
        return results_with_headers

    @staticmethod
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
        column_headers = [description[0] for description in cursor.description]
        connection.close()
        results_with_headers = [column_headers] + results

        return results_with_headers
    
    @staticmethod
    def sqlite_run_notes(notespath):
        connection = sqlite3.connect(notespath)
        cursor = connection.cursor()
        datausequery = """SELECT 
                ZNOTE.ZTITLE as 'Title',
                datetime('2001-01-01', ZNOTE.ZCREATIONDATE || ' seconds') as 'Creation Date',
                datetime('2001-01-01', ZNOTE.ZMODIFICATIONDATE || ' seconds') as 'Modification Date',
                ZNOTEBODY.ZCONTENT as 'Data'
            FROM ZNOTEBODY
            LEFT JOIN ZNOTE ON ZNOTEBODY.ZOWNER = ZNOTE.Z_PK
            WHERE ZNOTEBODY.ZCONTENT IS NOT NULL
            ORDER BY ZNOTE.ZMODIFICATIONDATE DESC;"""
        cursor.execute(datausequery)
        results = cursor.fetchall()
        column_headers = [description[0] for description in cursor.description]
        connection.close()
        
        # get rid of html content
        cleaned_results = []
        for row in results:
            cleaned_row = list(row)
            # Clean the 'Data' field (4th column - index 3)
            if len(cleaned_row) >= 4 and cleaned_row[3]:  # Data is the 4th column (index 3)
                content = cleaned_row[3]
                # Strip HTML tags using regex
                cleaned_content = re.sub(r'<[^>]+>', ' ', content)
                # Replace multiple spaces and newlines with single space
                cleaned_content = re.sub(r'\s+', ' ', cleaned_content)
                # Replace HTML entities like &nbsp;
                cleaned_content = re.sub(r'&[a-zA-Z]+;', ' ', cleaned_content)
                # Trim leading/trailing whitespace
                cleaned_content = cleaned_content.strip()
                cleaned_row[3] = cleaned_content
            
            cleaned_results.append(cleaned_row)

        results_with_headers = [column_headers] + cleaned_results
        return results_with_headers
    
    @staticmethod
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
        connection.close()
        results_with_headers = [column_headers] + results
        return results_with_headers
    
    @staticmethod
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
        connection.close()
        results_with_headers = [column_headers] + results

        return results_with_headers
    
    @staticmethod
    def sqlite_run_SMS(SMSdbPath):
        connection = sqlite3.connect(SMSdbPath)
        cursor = connection.cursor()
        
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
            # A chat is group if it has multiple handles or marked chat
            is_group = (participant_count > 1 or 
                      (row[2] and row[2].startswith('chat')) or 
                      ('chat.plist' in (row[2] or '')))
            
            group_data[chat_id] = {
                "name": row[1] or "", 
                "participants": row[4] or "",
                "is_group": is_group,
                "participant_count": participant_count
            }
        
        smsQuery = """SELECT 
        case when message.date != 0 then datetime((message.date + 978307200000000000) / 1000000000, 'unixepoch') end as 'Message Date', 
        chat.ROWID as 'Chat ID',
        
        CASE 
            WHEN handle.id IS NULL THEN ''
            ELSE handle.id 
        END as 'Contact',
        
        CASE 
            WHEN message.is_from_me = 1 THEN 'Sent'
            ELSE handle.id
        END as 'Sender',
        
        case message.is_from_me when 1 then 'Yes' else 'No' end as 'From Me',
        
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
        
        GROUP_CONCAT(attachment.filename, '; ') as 'Attachment Files',
        GROUP_CONCAT(attachment.mime_type, '; ') as 'Attachment Types',
        GROUP_CONCAT(attachment.transfer_name, '; ') as 'Attachment Names',
        
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
        
        column_headers = [description[0] for description in cursor.description]        
        results_with_headers = [column_headers]        
        processed_results = []
        
        for row in results:
            row_list = list(row)
            
            chat_id = row[column_headers.index('Chat ID')]
            if chat_id in group_data:
                is_group = 'Yes' if group_data[chat_id]['is_group'] else 'No'
                row_list.append(is_group)
                
                if group_data[chat_id]['is_group']:
                    if group_data[chat_id]['name']:
                        display_name = f"{group_data[chat_id]['name']}"
                    else:
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
        
        column_headers.extend(['Is Group Chat', 'Group Name'])
        results_with_headers = [column_headers] + processed_results        
        df = pd.DataFrame(processed_results, columns=column_headers)        
        connection.close()        
        return results_with_headers, df

    @staticmethod
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
        connection.close()
        results_with_headers = [column_headers] + results

        return results_with_headers    

    @staticmethod
    def calculate_itunes_photofile_name(filepathinbackup):      #converts path to sha1 used in backup file name
        builtpath = ('CameraRollDomain-Media/' + filepathinbackup)
        builtpath = builtpath.encode(encoding='UTF-8', errors='strict')
        filehash = sha1(builtpath).hexdigest()
        return str(filehash)

    def retrieve_photos_from_backup(backup_path, filedestination, password, list_of_fileIDs):
        try:
            if not list_of_fileIDs:
                print("No file IDs provided to retrieve")
                return 0

            backup = Backup.from_path(backup_path=backup_path, password=password)
            
            extracted_count = 0
            failed_ids = []
            
            for ID in list_of_fileIDs:
                try:
                    backup.extract_file_id(ID, path=filedestination)
                    extracted_count += 1
                    print(f"Extracted: {ID}")
                except MissingEntryError:
                    failed_ids.append(ID) # missing entry
                    print(f"Missing entry: {ID}")
                except Exception as e:
                    failed_ids.append(ID)
                    print(f"Error extracting {ID}: {str(e)}")
            
            print(f"Photo extraction complete: {extracted_count} successful, {len(failed_ids)} failed")
            return extracted_count
            
        except Exception as e:
            print(f"Error in photo extraction: {str(e)}")
            return 0
            backupd_plist = backup.extract_file_id(ID,path=filedestination)
    

    @staticmethod
    def retrieve_photos_from_backup(backup_path, filedestination, password, list_of_fileIDs):
        """Extract specific photos from backup using file IDs"""
        try:
            if not list_of_fileIDs:
                print("No file IDs provided to retrieve")
                return 0

            backup = Backup.from_path(backup_path=backup_path, password=password)

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

            print(f"Photo extraction complete: {extracted_count} successful, {missing_entry_count} missing")
            if failed_ids and len(failed_ids) < 10:
                print(f"Failed IDs: {', '.join(failed_ids)}")
            elif failed_ids:
                print(f"Failed IDs: {', '.join(failed_ids[:10])}... (and {len(failed_ids) - 10} more)")

            return extracted_count

        except Exception as e:
            print(f"Error in photo extraction: {str(e)}")
            return 0

    @staticmethod
    def photo_taxonomy(photosqlitepath):       
        sqlite_file = photosqlitepath
        if sqlite_file is None:
            print("The 'photos.sqlite' file was not found in the specified folder or its subfolders.")
            return pd.DataFrame()  # Return empty DataFrame instead of None
        try:
            conn = sqlite3.connect(sqlite_file)
            cur = conn.cursor()
        except sqlite3.Error as e:
            print(f"Error connecting to {sqlite_file}: {e}")
            return pd.DataFrame()  # Return empty DataFrame instead of None
    
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
        # DO NOT convert taxonomy IDs to descriptions here - that should happen after filtering
        # replace_taxonomy_id_w_descr(df=df)  # ❌ REMOVED - this breaks numeric filtering
        df['Confidence'] = df["Confidence"].apply(format_as_percentage)
        df["Date Created"] = df["Date Created"].apply(mac_absolute_time_to_datetime)
        df["Date Added"] = df["Date Added"].apply(mac_absolute_time_to_datetime)
        conn.close()
        return df

def format_device_info_header(device_info):
    """Create a standardized header with device information for reports"""
    header = "DEVICE INFORMATION\n"
    if device_info:
        for key, value in device_info.items():
            if value:  # Only include non-empty values
                header += f"{key}: {value}\n"
    header += "\n"
    return header

# End of backup_parser.py



def create_timeline_report(report_path, device_info, report_title="TIMELINE REPORT", timezone=None):
    return None


def convert_timezone(timestamp_str, target_timezone):
    """Convert a timestamp string from UTC to the target timezone"""
    import datetime
    import pytz
    from tzlocal import get_localzone
    
    if not timestamp_str:
        return timestamp_str
    
    try:
        # times
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
            
        timezone_format = "%Y-%m-%d %H:%M:%S (%Z)"
        
        if target_timezone.startswith("System Time"):
            local_tz = get_localzone()
            dt_local = dt_utc.astimezone(local_tz)
            return dt_local.strftime(timezone_format)
        elif target_timezone == "UTC":
            return dt_utc.strftime(timezone_format)
        else: # other timezones
            target_tz = pytz.timezone(target_timezone)
            dt_target = dt_utc.astimezone(target_tz)
            return dt_target.strftime(timezone_format)
    except Exception as e:
        print(f"Error converting timestamp '{timestamp_str}': {e}")


def generate_photo_report(filtered_df, photo_output_destination, reports_dir, taxonomy_target, taxonomy_description, device_info, extracted_count, timezone, status_callback):
    """Generate a photo report CSV with thumbnail information"""
    try:
        # Add extracted file path information to the DataFrame
        if photo_output_destination and os.path.exists(photo_output_destination):
            print(f"Adding extracted file paths for photos in: {photo_output_destination}")
            
            def get_extracted_file_path(row):
                if 'Filename' in row:
                    # The extracted files use the original filename, not the SHA1 hash
                    original_filename = str(row['Filename'])
                    extracted_file_path = os.path.join(photo_output_destination, original_filename)
                    if os.path.exists(extracted_file_path):
                        print(f"Found file: {extracted_file_path}")
                        return extracted_file_path
                    else:
                        # Try with path prefix removed (just filename)
                        filename_only = os.path.basename(original_filename)
                        extracted_file_path_alt = os.path.join(photo_output_destination, filename_only)
                        if os.path.exists(extracted_file_path_alt):
                            print(f"Found file (basename): {extracted_file_path_alt}")
                            return extracted_file_path_alt
                        else:
                            print(f"File not found: {original_filename}")
                return ''
            
            filtered_df['Extracted_File_Path'] = filtered_df.apply(get_extracted_file_path, axis=1)
            
            # Report how many files were found
            found_count = (filtered_df['Extracted_File_Path'] != '').sum()
            total_count = len(filtered_df)
            print(f"Photo report: Found {found_count} out of {total_count} extracted files")
        else:
            print(f"Photo output destination not found: {photo_output_destination}")
        
        # Create device header
        device_header = f"PHOTO ANALYSIS REPORT\n\nDEVICE INFORMATION\n"
        if device_info:
            for key, value in device_info.items():
                if value:  # Only include non-empty values
                    device_header += f"{key}: {value}\n"
        device_header += "\n"
        
        # Create extraction summary
        extraction_summary = f"EXTRACTION SUMMARY\n"
        extraction_summary += f"Taxonomy: {taxonomy_description} (ID: {taxonomy_target})\n"
        extraction_summary += f"Total images found: {len(filtered_df)}\n"
        extraction_summary += f"Successfully extracted: {extracted_count}\n"
        extraction_summary += f"Extraction path: {photo_output_destination}\n\n"
        
        # Convert timestamps if timezone specified
        if timezone:
            for column in filtered_df.columns:
                if 'date' in column.lower() or 'time' in column.lower():
                    filtered_df[column] = filtered_df[column].apply(
                        lambda x: convert_timezone(x, timezone) if x and 'UTC' in str(x) else x
                    )
        
        # Save the photo report
        # Use taxonomy_description (name) instead of taxonomy_target (ID) for better readability
        photo_report_csv = os.path.join(reports_dir, f'Photo_Report_{taxonomy_description}.csv')
        
        # Write the summary first, then the DataFrame
        with open(photo_report_csv, 'w') as f:
            f.write(device_header)
            f.write(extraction_summary)
        
        # Append the DataFrame to the file with header but no index
        filtered_df.to_csv(photo_report_csv, mode='a', index=False)
        
        if status_callback:
            status_callback(f"Saved photo report with thumbnails to Photo_Report_{taxonomy_description}.csv")
        
        print(f"Photo report generated: {photo_report_csv}")
        
    except Exception as e:
        print(f"Error generating photo report: {e}")
        if status_callback:
            status_callback(f"Error generating photo report: {e}")

def extract_image_exif(image_path):
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
                    # Convert any non-serializable types to strings
                    if isinstance(value, bytes):
                        try:
                            value = value.decode('utf-8')
                        except:
                            value = str(value)
                    elif hasattr(value, 'numerator') and hasattr(value, 'denominator'):
                        # Handle rational numbers
                        if value.denominator != 0:
                            value = float(value.numerator) / float(value.denominator)
                        else:
                            value = float(value.numerator)
                    else:
                        value = str(value)
                    exif_data[decoded] = value
        
        return exif_data
    except Exception as e:
        return {"Error": f"Failed to extract EXIF: {str(e)}"}

def convert_gps_coordinate(coord_list):
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

def extract_heic_exif(image_path):
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
                        lat_degrees = convert_gps_coordinate(gps_info['GPSLatitude'])
                        if gps_info['GPSLatitudeRef'] == 'S':
                            lat_degrees = -lat_degrees
                        exif_data['GPS Latitude'] = f"{lat_degrees:.6f}° {gps_info['GPSLatitudeRef']}"
                        exif_data['GPS Latitude Decimal'] = lat_degrees
                    
                    if 'GPSLongitude' in gps_info and 'GPSLongitudeRef' in gps_info:
                        lon_degrees = convert_gps_coordinate(gps_info['GPSLongitude'])
                        if gps_info['GPSLongitudeRef'] == 'W':
                            lon_degrees = -lon_degrees
                        exif_data['GPS Longitude'] = f"{lon_degrees:.6f}° {gps_info['GPSLongitudeRef']}"
                        exif_data['GPS Longitude Decimal'] = lon_degrees
                    
                    # Create Google Maps link if we have coordinates
                    if 'GPS Latitude Decimal' in exif_data and 'GPS Longitude Decimal' in exif_data:
                        lat = exif_data['GPS Latitude Decimal']
                        lon = exif_data['GPS Longitude Decimal']
                        exif_data['Google Maps Link'] = f"https://maps.google.com/?q={lat},{lon}"
                        exif_data['Apple Maps Link'] = f"https://maps.apple.com/?q={lat},{lon}"
                    
                    # GPS altitude
                    if 'GPSAltitude' in gps_info:
                        altitude = convert_gps_coordinate([gps_info['GPSAltitude']])
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
            
            return exif_data
            
        except ImportError:
            print("DEBUG: pillow-heif not available, trying standard PIL")
            # Fallback to standard PIL for JPEG and other formats
            img = Image.open(image_path)
            
            file_size = os.path.getsize(image_path)
            file_modified = datetime.fromtimestamp(os.path.getmtime(image_path)).strftime('%Y-%m-%d %H:%M:%S')
            
            exif_data = {
                'File Type': image_path.split('.')[-1].upper(),
                'File Name': os.path.basename(image_path),
                'File Size': f"{file_size:,} bytes ({file_size / (1024*1024):.2f} MB)",
                'File Modified': file_modified,
                'Image Width': img.width,
                'Image Height': img.height,
                'Color Mode': img.mode,
                'Image Resolution': f"{img.width} x {img.height}",
            }
            
            if hasattr(img, '_getexif'):
                exif_info = img._getexif()
                if exif_info:
                    for tag, value in exif_info.items():
                        decoded = TAGS.get(tag, tag)
                        exif_data[decoded] = str(value)
            
            return exif_data
    
    except Exception as e:
        print(f"DEBUG: Error in extract_heic_exif: {e}")
        return {
            'Error': f"Failed to extract EXIF: {str(e)}",
            'File Type': image_path.split('.')[-1].upper() if '.' in image_path else 'Unknown',
            'File Size': f"{os.path.getsize(image_path)} bytes" if os.path.exists(image_path) else 'Unknown'
        }

