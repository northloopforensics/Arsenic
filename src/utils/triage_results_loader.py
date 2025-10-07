#!/usr/bin/env python3

import os
import glob
import json
import pandas as pd
from datetime import datetime

def find_latest_android_triage_results(output_directory):
    """Find the latest and most complete Android triage results"""
    
    # Use the configured output directory
    if not output_directory or not output_directory.strip():
        print("DEBUG: No output directory configured")
        return None
    
    if not os.path.exists(output_directory):
        print(f"DEBUG: Configured output directory does not exist: {output_directory}")
        return None
    
    # Look for Android triage folders in the configured directory
    pattern = os.path.join(output_directory, "Android_Triage_*")
    triage_folders = glob.glob(pattern)
    
    print(f"DEBUG: Searching for triage folders in: {output_directory}")
    print(f"DEBUG: Found {len(triage_folders)} triage folders")
    
    if not triage_folders:
        return None
    
    # Sort by modification time, newest first
    triage_folders.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    
    best_folder = None
    best_score = 0
    
    for folder in triage_folders:
        # Calculate completeness score
        score = 0
        
        # Check for key files/folders in new organized structure
        data_dir = os.path.join(folder, "Data")
        messages_dir = os.path.join(data_dir, "Messages")
        contacts_dir = os.path.join(data_dir, "Contacts")
        call_logs_dir = os.path.join(data_dir, "CallLogs")
        apps_dir = os.path.join(folder, "Apps")
        reports_dir = os.path.join(folder, "Reports")
        device_details = os.path.join(folder, "device_details.txt")
        
        if os.path.exists(data_dir):
            score += 10
            
            # Check for specific data files in organized structure
            sms_csv = os.path.join(messages_dir, "sms_messages.csv")
            mms_csv = os.path.join(messages_dir, "mms_messages.csv")
            contacts_csv = os.path.join(contacts_dir, "contacts_data.csv")
            call_logs_csv = os.path.join(call_logs_dir, "call_logs.csv")
            
            if os.path.exists(sms_csv):
                score += 5
            if os.path.exists(contacts_csv):
                score += 5
            if os.path.exists(mms_csv):
                score += 3
            if os.path.exists(call_logs_csv):
                score += 3
        
        if os.path.exists(apps_dir):
            score += 5
        
        if os.path.exists(reports_dir):
            score += 5
            
        if os.path.exists(device_details):
            score += 3
            
        # Check for PDF report
        pdf_files = glob.glob(os.path.join(folder, "Triage_Report_*.pdf"))
        if pdf_files:
            score += 5
        
        if score > best_score:
            best_score = score
            best_folder = folder
    
    return best_folder

def load_triage_data_from_folder(folder_path):
    """Load structured triage data from a folder"""
    if not folder_path or not os.path.exists(folder_path):
        return None
    
    triage_data = {
        "case_folder": folder_path,
        "timestamp": datetime.now().isoformat(),
        "artifacts": {},
        "device_details": {},
        "apps": []
    }
    
    # Load device details
    device_details_file = os.path.join(folder_path, "device_details.txt")
    if os.path.exists(device_details_file):
        try:
            with open(device_details_file, 'r') as f:
                content = f.read()
                # Parse device details from the text file
                for line in content.split('\n'):
                    if ':' in line and line.strip():
                        key, value = line.split(':', 1)
                        triage_data["device_details"][key.strip()] = value.strip()
        except Exception as e:
            print(f"Error loading device details: {e}")
    
    # Load CSV data from organized structure
    data_dir = os.path.join(folder_path, "Data")
    
    # Define data locations in new organized structure
    data_locations = {
        "sms_data": os.path.join(data_dir, "Messages", "sms_messages.csv"),
        "mms_data": os.path.join(data_dir, "Messages", "mms_messages.csv"), 
        "contacts_data": os.path.join(data_dir, "Contacts", "contacts_data.csv"),
        "call_logs_data": os.path.join(data_dir, "CallLogs", "call_logs.csv"),
        # Notifications and external files remain in Artifacts as forensic evidence
        "notifications_data": os.path.join(folder_path, "Artifacts", "Notifications", "notifications.csv"),
        "external_images_data": os.path.join(folder_path, "Artifacts", "External_Files", "external_images.csv"),
        "external_videos_data": os.path.join(folder_path, "Artifacts", "External_Files", "external_videos.csv")
    }
    
    # Load each data type from its organized location
    for data_type, csv_path in data_locations.items():
        if os.path.exists(csv_path):
            try:
                df = pd.read_csv(csv_path)
                
                # Clean the data - replace NaN values with empty strings
                df = df.fillna('')
                
                # Convert to records and ensure JSON serializable
                records = df.to_dict('records')
                
                # Clean each record to ensure JSON serializable values
                clean_records = []
                for record in records:
                    clean_record = {}
                    for key, value in record.items():
                        # Handle various problematic values
                        if pd.isna(value) or value != value:  # NaN check
                            clean_record[key] = ""
                        elif isinstance(value, (int, float)) and not pd.isna(value):
                            # Ensure numeric values are finite
                            if pd.isfinite(value):
                                clean_record[key] = value
                            else:
                                clean_record[key] = ""
                        else:
                            clean_record[key] = str(value) if value is not None else ""
                    clean_records.append(clean_record)
                
                triage_data["artifacts"][data_type] = {
                    "record_count": len(clean_records),
                    "records": clean_records
                }
                
                # Also put the actual records at the top level for easy access (like apps)
                triage_data[data_type] = clean_records
            except Exception as e:
                print(f"Error loading {data_type} from {csv_path}: {e}")
    
    # Load app summary if available in Apps directory
    app_summary_file = os.path.join(folder_path, "Apps", "app_summary.txt")
    if os.path.exists(app_summary_file):
        try:
            with open(app_summary_file, 'r') as f:
                content = f.read()
                # Simple parsing - each line is an app
                apps = [line.strip() for line in content.split('\n') if line.strip()]
                triage_data["apps"] = apps
        except Exception as e:
            print(f"Error loading app summary: {e}")
    
    return triage_data