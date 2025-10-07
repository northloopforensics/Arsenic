
import json
import csv
import os
import subprocess
import tarfile
import sys

# Windows-specific subprocess flag to prevent console windows
if sys.platform == "win32":
    SUBPROCESS_FLAGS = subprocess.CREATE_NO_WINDOW
else:
    SUBPROCESS_FLAGS = 0

class BackupExtractor:
    def __init__(self, ab_file, abe_jar, unpack_dir, password=None):
        self.ab_file = ab_file
        self.abe_jar = abe_jar
        self.unpack_dir = unpack_dir
        self.password = password
        self.tar_file = os.path.join(unpack_dir, 'backup.tar')
        self.error_message = None  # Store detailed error message
        os.makedirs(unpack_dir, exist_ok=True)

    def extract(self):
        print(f"=" * 60)
        print(f"🔓 Starting ADB Backup Extraction")
        print(f"=" * 60)
        print(f"📱 Input:  {self.ab_file}")
        print(f"📦 Output: {self.tar_file}")
        print(f"🔧 Tool:   {self.abe_jar}")
        
        # Check if input file exists
        if not os.path.exists(self.ab_file):
            self.error_message = f"Backup file not found: {self.ab_file}"
            print(f"❌ Error: {self.error_message}")
            return False
        
        ab_size = os.path.getsize(self.ab_file)
        print(f"📊 Backup size: {ab_size / (1024*1024*1024):.2f} GB")
        
        # Check if abe.jar exists
        if not os.path.exists(self.abe_jar):
            self.error_message = f"abe.jar not found: {self.abe_jar}"
            print(f"❌ Error: {self.error_message}")
            return False
        
        print(f"\n🚀 Unpacking with abe.jar...")
        
        # Build command with optional password support
        cmd = ['java', '-jar', self.abe_jar, 'unpack', self.ab_file, self.tar_file]
        if self.password:
            cmd.append(self.password)
            print(f"🔐 Using password-protected backup extraction...")
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, 
                                  encoding='utf-8', errors='replace', creationflags=SUBPROCESS_FLAGS)
            if result.stdout:
                print(result.stdout)
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr
            print(f"Error running abe.jar: {error_msg}")
            
            # Check for password-related errors
            if "BadPaddingException" in error_msg or "bad key is used" in error_msg:
                self.error_message = "Incorrect password - The backup is encrypted but the password doesn't match"
                print(f"❌ Backup extraction failed: {self.error_message}")
                print("💡 Please verify the backup password and try again")
            elif "Wrong password" in error_msg or "Invalid password" in error_msg:
                self.error_message = "Invalid password provided"
                print(f"❌ Backup extraction failed: {self.error_message}")
                print("💡 Please check the backup password and try again")
            elif "password" in error_msg.lower() and not self.password:
                self.error_message = "Backup is password-protected but no password was provided"
                print(f"❌ Backup extraction failed: {self.error_message}")
                print("💡 Please provide the backup password to extract this backup")
            else:
                self.error_message = f"ABE extraction failed: {error_msg[:200]}"  # First 200 chars
            
            return False
        
        # Check if tar file was actually created
        if not os.path.exists(self.tar_file):
            print(f"❌ Error: Tar file was not created by abe.jar")
            print(f"   Expected: {self.tar_file}")
            return False
        
        tar_size = os.path.getsize(self.tar_file)
        if tar_size == 0:
            print(f"❌ Error: Tar file is empty (0 bytes)")
            return False
        
        print(f"📦 Tar file created: {tar_size / (1024*1024*1024):.2f} GB")
        
        # Extract tar archive to directories
        extraction_successful = False
        extraction_partial = False
        
        try:
            print(f"📦 Extracting tar archive to directories...")
            print(f"📂 Extraction destination: {self.unpack_dir}")
            with tarfile.open(self.tar_file) as tar:
                # Try to get list of members for logging (may fail on corrupted archives)
                try:
                    members = tar.getmembers()
                    print(f"📂 Found {len(members)} items in backup archive")
                except Exception as e:
                    print(f"⚠️  Warning: Could not read full archive contents: {e}")
                    print(f"📦 Attempting partial extraction anyway...")
                
                # Extract all files and directories
                # Note: filter parameter requires Python 3.12+, we're using 3.8
                print(f"🚀 Starting tar.extractall()...")
                tar.extractall(self.unpack_dir)
                extraction_successful = True
                print(f"✅ tar.extractall() completed successfully")
                    
        except tarfile.ReadError as e:
            print(f"⚠️  Tar archive read error: {str(e)}")
            print(f"📦 Attempting recovery extraction using system tar...")
            
            # Fallback: Use system tar command which handles errors better
            try:
                print(f"🔧 Running: tar -xf {os.path.basename(self.tar_file)} --ignore-zeros")
                result = subprocess.run(
                    ['tar', '-xf', self.tar_file, '--ignore-zeros'],
                    cwd=self.unpack_dir,
                    capture_output=True,
                    text=True
                )
                print(f"📊 System tar exit code: {result.returncode}")
                if result.stderr:
                    print(f"📝 System tar stderr: {result.stderr[:500]}")
                    
                if result.returncode == 0:
                    extraction_successful = True
                    print(f"✅ Successfully extracted using system tar")
                else:
                    # Even with errors, files may have been extracted
                    if "Truncated" in result.stderr or "Error exit delayed" in result.stderr:
                        extraction_partial = True
                        print(f"⚠️  Partial extraction completed (archive appears truncated)")
                        print(f"💡 Some data may be missing from the end of the backup")
                    else:
                        print(f"❌ System tar extraction failed: {result.stderr}")
                        self.error_message = f"Tar extraction failed: {result.stderr[:200]}"
                        return False
            except FileNotFoundError:
                print(f"❌ System tar command not found. Cannot recover from corrupted archive.")
                return False
            except Exception as e:
                print(f"❌ Recovery extraction failed: {str(e)}")
                return False
                
        except Exception as e:
            print(f"❌ Error extracting tar archive: {str(e)}")
            return False
        
        # Check if any files were extracted
        print(f"🔍 Checking extraction directory: {self.unpack_dir}")
        extracted_items = []
        try:
            all_items = os.listdir(self.unpack_dir)
            print(f"📂 All items in directory: {all_items}")
            for item in all_items:
                if item != "backup.tar":
                    extracted_items.append(item)
            print(f"📊 Extracted items (excluding tar): {extracted_items}")
        except Exception as e:
            print(f"⚠️  Error listing directory: {e}")
        
        if not extracted_items:
            print(f"❌ No files were extracted from the backup")
            self.error_message = "No files were extracted from the backup"
            return False
        
        if extraction_successful:
            print(f"✅ Successfully extracted backup to: {self.unpack_dir}")
            print(f"📦 Extracted {len(extracted_items)} top-level items: {', '.join(extracted_items)}")
        elif extraction_partial:
            print(f"⚠️  Partial extraction completed to: {self.unpack_dir}")
            print(f"✅ Extracted: {', '.join(extracted_items)}")
        
        # Clean up intermediate tar file
        try:
            if os.path.exists(self.tar_file):
                os.remove(self.tar_file)
                print(f"🧹 Cleaned up intermediate tar file")
        except Exception as e:
            print(f"⚠️  Warning: Could not remove intermediate tar file: {e}")
            
        return True

    def list_files(self):
        """List all extracted files in the backup"""
        for root, dirs, files in os.walk(self.unpack_dir):
            for file in files:
                print(f"Extracted file: {os.path.join(root, file)}")
    
    def get_extraction_summary(self):
        """Get a summary of the extracted backup structure"""
        if not os.path.exists(self.unpack_dir):
            return {"error": "Extraction directory does not exist"}
        
        summary = {
            "extraction_path": self.unpack_dir,
            "directories": [],
            "file_count": 0,
            "total_size_bytes": 0
        }
        
        # Walk through the extracted directories
        for root, dirs, files in os.walk(self.unpack_dir):
            # Track directories (relative to unpack_dir)
            rel_root = os.path.relpath(root, self.unpack_dir)
            if rel_root != ".":
                summary["directories"].append(rel_root)
            
            # Count files and calculate total size
            for file in files:
                if file != "backup.tar":  # Skip the intermediate tar if it still exists
                    summary["file_count"] += 1
                    file_path = os.path.join(root, file)
                    try:
                        summary["total_size_bytes"] += os.path.getsize(file_path)
                    except:
                        pass
        
        # Format size for display
        size_mb = summary["total_size_bytes"] / (1024 * 1024)
        summary["total_size_mb"] = round(size_mb, 2)
        
        return summary

class ForensicDataParser:
    def __init__(self, base_dir, output_dir):
        self.base_dir = base_dir
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)


    def _format_timestamp(self, value):
        # Handles both ms and s timestamps, returns timezone-aware UTC datetime
        import datetime
        try:
            v = int(value)
            # If it's in ms, convert to seconds
            if v > 1e12:
                v = v // 1000
            dt = datetime.datetime.fromtimestamp(v, tz=datetime.timezone.utc)
            return dt.strftime('%Y/%m/%d %H:%M:%S')
        except Exception:
            return value

    def write_csv(self, data, csv_path, fieldnames, timestamp_fields=None):
        if timestamp_fields is None:
            timestamp_fields = []
        # Insert timezone columns after each timestamp field
        output_fieldnames = []
        for fn in fieldnames:
            output_fieldnames.append(fn)
            if fn in timestamp_fields:
                output_fieldnames.append(f"{fn}_timezone")
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=output_fieldnames)
            writer.writeheader()
            for row in data:
                filtered_row = {k: row.get(k, "") for k in fieldnames}
                for tf in timestamp_fields:
                    if tf in filtered_row and filtered_row[tf]:
                        filtered_row[tf] = self._format_timestamp(filtered_row[tf])
                        filtered_row[f"{tf}_timezone"] = "UTC"
                    else:
                        filtered_row[f"{tf}_timezone"] = ""
                writer.writerow(filtered_row)

    def parse_json_file(self, json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def parse_all(self):
        # Contacts
        contacts = self.parse_json_file(os.path.join(self.base_dir, 'contacts.json'))
        self.write_csv(contacts, os.path.join(self.output_dir, 'contacts.csv'),
                      ['id', 'display_name', 'has_phone_number', 'lookup_key', 'source'])

        # SMS Messages with human-readable type
        sms = self.parse_json_file(os.path.join(self.base_dir, 'sms_messages.json'))
        sms_type_labels = {
            1: 'Incoming',
            2: 'Outgoing',
        }
        for msg in sms:
            try:
                type_value = int(msg.get('type')) if msg.get('type') is not None else None
            except Exception:
                type_value = msg.get('type')
            msg['sms_type_label'] = sms_type_labels.get(type_value, str(type_value) if type_value is not None else '')
        self.write_csv(sms, os.path.join(self.output_dir, 'sms_messages.csv'),
                      ['id', 'address', 'body', 'date', 'type', 'sms_type_label', 'read', 'thread_id', 'source'],
                      timestamp_fields=['date'])

        # Call Logs with human-readable call type
        calls = self.parse_json_file(os.path.join(self.base_dir, 'call_logs.json'))
        call_type_labels = {
            1: 'Incoming',
            2: 'Outgoing',
            3: 'Missed',
            4: 'Voicemail',
            5: 'Rejected',
            6: 'Blocked',
            7: 'Answered Externally',
        }
        for call in calls:
            try:
                type_value = int(call.get('type')) if call.get('type') is not None else None
            except Exception:
                type_value = call.get('type')
            call['call_type_label'] = call_type_labels.get(type_value, str(type_value) if type_value is not None else '')
        self.write_csv(calls, os.path.join(self.output_dir, 'call_logs.csv'),
                      ['id', 'number', 'date', 'duration', 'type', 'cached_name', 'call_type_label'],
                      timestamp_fields=['date'])

        # Calendar Events
        events = self.parse_json_file(os.path.join(self.base_dir, 'calendar_events.json'))
        self.write_csv(events, os.path.join(self.output_dir, 'calendar_events.csv'),
                      ['id', 'title', 'description', 'start_date', 'end_date', 'location', 'calendar_id', 'organizer', 'source'],
                      timestamp_fields=['start_date', 'end_date'])

        # System Settings
        settings = self.parse_json_file(os.path.join(self.base_dir, 'system_settings.json'))
        self.write_csv(settings, os.path.join(self.output_dir, 'system_settings.csv'),
                      ['name', 'value', 'source'])

        # Collection Summary (text)
        with open(os.path.join(self.base_dir, 'collection_summary.txt'), 'r', encoding='utf-8') as f:
            summary = f.read()
        with open(os.path.join(self.output_dir, 'collection_summary.txt'), 'w', encoding='utf-8') as f:
            f.write(summary)

def main():
    # Example usage for integration
    base_dir = 'app_collected_data'
    output_dir = 'parsed_reports'
    ab_file = 'android_backup_20250718_211002.ab'
    abe_jar = 'abe.jar'
    unpack_dir = 'ab_extracted'

    # Extract backup
    extractor = BackupExtractor(ab_file, abe_jar, unpack_dir)
    if extractor.extract():
        extractor.list_files()

    # Parse forensic data
    parser = ForensicDataParser(base_dir, output_dir)
    parser.parse_all()
    print("Parsing complete. CSV reports are in:", output_dir)

if __name__ == "__main__":
    main()
