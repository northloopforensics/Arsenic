#!/usr/bin/env python3
"""
Android Backup Encryption Detector
Detects if an Android backup (.ab) file is encrypted and prompts for password if needed.
"""

import os
import struct
import tkinter as tk
from tkinter import messagebox, simpledialog
import threading


class AndroidBackupAnalyzer:
    """Analyzes Android backup files to detect encryption and format"""
    
    def __init__(self):
        pass
    
    def analyze_backup_file(self, backup_file_path):
        """
        Analyze an Android backup file to determine its properties
        
        Args:
            backup_file_path: Path to the .ab backup file
            
        Returns:
            dict: Analysis results containing:
                - is_valid: bool - Is this a valid Android backup file
                - is_encrypted: bool - Is the backup encrypted
                - version: int - Backup format version
                - compression: str - Compression method used
                - error: str - Error message if analysis failed
        """
        result = {
            'is_valid': False,
            'is_encrypted': False, 
            'version': None,
            'compression': None,
            'error': None
        }
        
        try:
            if not os.path.exists(backup_file_path):
                result['error'] = f"Backup file not found: {backup_file_path}"
                return result
            
            with open(backup_file_path, 'rb') as f:
                # Read the Android backup header
                header_line = f.readline().decode('ascii', errors='ignore').strip()
                
                if not header_line.startswith('ANDROID BACKUP'):
                    result['error'] = "Not a valid Android backup file (missing header)"
                    return result
                
                result['is_valid'] = True
                
                # Parse version
                version_line = f.readline().decode('ascii', errors='ignore').strip()
                try:
                    result['version'] = int(version_line)
                except ValueError:
                    result['error'] = f"Invalid version format: {version_line}"
                    return result
                
                # Parse compression (0 = none, 1 = deflate)
                compression_line = f.readline().decode('ascii', errors='ignore').strip()
                try:
                    compression_code = int(compression_line)
                    result['compression'] = 'deflate' if compression_code == 1 else 'none'
                except ValueError:
                    result['error'] = f"Invalid compression format: {compression_line}"
                    return result
                
                # Parse encryption (none, AES-256, etc.)
                encryption_line = f.readline().decode('ascii', errors='ignore').strip()
                result['is_encrypted'] = encryption_line.lower() != 'none'
                
                if result['is_encrypted']:
                    print(f"🔐 Detected encrypted backup with encryption: {encryption_line}")
                else:
                    print(f"🔓 Detected unencrypted backup")
                
        except Exception as e:
            result['error'] = f"Error analyzing backup file: {str(e)}"
            
        return result
    
    def prompt_for_password(self, parent=None):
        """
        Prompt user for backup password using a GUI dialog
        
        Args:
            parent: Parent window for the dialog
            
        Returns:
            str or None: Password if provided, None if cancelled
        """
        try:
            # Create a simple password dialog
            password = simpledialog.askstring(
                "Encrypted Backup Detected",
                "This backup is encrypted and requires a password.\n\nPlease enter the backup password:",
                show='*',  # Hide password characters
                parent=parent
            )
            return password
        except Exception as e:
            print(f"Error showing password dialog: {e}")
            return None
    
    def show_encryption_info(self, analysis_result, parent=None):
        """
        Show information about the backup encryption status
        
        Args:
            analysis_result: Result from analyze_backup_file()
            parent: Parent window for dialogs
        """
        if not analysis_result['is_valid']:
            messagebox.showerror(
                "Invalid Backup",
                f"The selected file is not a valid Android backup:\n{analysis_result['error']}",
                parent=parent
            )
            return
        
        if analysis_result['is_encrypted']:
            messagebox.showinfo(
                "Encrypted Backup Detected", 
                f"Backup Information:\n"
                f"• Version: {analysis_result['version']}\n"
                f"• Compression: {analysis_result['compression']}\n"
                f"• Status: Encrypted (password required)\n\n"
                f"You will be prompted for the password during extraction.",
                parent=parent
            )
        else:
            messagebox.showinfo(
                "Backup Analysis Complete",
                f"Backup Information:\n"
                f"• Version: {analysis_result['version']}\n" 
                f"• Compression: {analysis_result['compression']}\n"
                f"• Status: Unencrypted (no password required)\n\n"
                f"Ready for extraction.",
                parent=parent
            )


def test_backup_analyzer():
    """Test function for the backup analyzer"""
    analyzer = AndroidBackupAnalyzer()
    
    # Test with a sample file path (replace with actual backup file for testing)
    test_file = "/path/to/test/backup.ab"
    
    if os.path.exists(test_file):
        result = analyzer.analyze_backup_file(test_file)
        print(f"Analysis result: {result}")
        
        if result['is_valid']:
            if result['is_encrypted']:
                password = analyzer.prompt_for_password()
                print(f"Password provided: {'Yes' if password else 'No'}")
    else:
        print(f"Test file not found: {test_file}")


if __name__ == "__main__":
    test_backup_analyzer()