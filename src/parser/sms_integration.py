#!/usr/bin/env python3
"""
SMS Parser Integration Module
=============================

Integration module for parsing SMS data extracted via ADB content queries.
This module provides easy integration with the main Arsenic application.

Author: Arsenic Forensics
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

# Windows-specific subprocess flag to prevent console windows
if sys.platform == "win32":
    SUBPROCESS_FLAGS = subprocess.CREATE_NO_WINDOW
else:
    SUBPROCESS_FLAGS = 0

def _run_subprocess_with_encoding(command, **kwargs):
    """Helper function to run subprocess with proper encoding handling"""
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

# Add the parser directory to Python path
parser_dir = Path(__file__).parent
sys.path.insert(0, str(parser_dir))

try:
    from adb_content_sms import SMSParser
except ImportError as e:
    print(f"Error importing SMS parser: {e}")
    SMSParser = None


def parse_sms_file(input_file: str, output_dir: str = None) -> Dict[str, Any]:
    """
    Parse SMS file and return analysis results.
    
    Args:
        input_file: Path to SMS data file
        output_dir: Output directory for reports (optional)
    
    Returns:
        Dictionary containing analysis results
    """
    if not SMSParser:
        return {'error': 'SMS parser not available'}
    
    try:
        parser = SMSParser()
        parser.parse_file(input_file)
        
        results = {
            'success': True,
            'statistics': parser.get_statistics(),
            'forensic_indicators': parser.get_forensic_indicators(),
            'message_count': len(parser.messages),
            'thread_count': len(parser.threads),
            'contact_count': len(parser.contacts)
        }
        
        # Generate reports if output directory specified
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(exist_ok=True)
            
            base_name = Path(input_file).stem
            
            try:
                # Generate JSON report
                json_path = output_path / f"{base_name}_sms_analysis.json"
                parser.export_to_json(json_path)
                results['json_report'] = str(json_path)
                
                # Generate CSV export
                csv_path = output_path / f"{base_name}_sms_messages.csv"
                parser.export_to_csv(csv_path)
                results['csv_export'] = str(csv_path)
                
                # Generate text report
                report_path = output_path / f"{base_name}_sms_report.txt"
                parser.generate_report(report_path)
                results['text_report'] = str(report_path)
                
            except Exception as e:
                results['report_error'] = str(e)
        
        return results
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def get_sms_summary(input_file: str) -> Dict[str, Any]:
    """
    Get a quick summary of SMS data without generating full reports.
    
    Args:
        input_file: Path to SMS data file
    
    Returns:
        Dictionary containing summary information
    """
    if not SMSParser:
        return {'error': 'SMS parser not available'}
    
    try:
        parser = SMSParser()
        parser.parse_file(input_file)
        
        stats = parser.get_statistics()
        indicators = parser.get_forensic_indicators()
        
        return {
            'success': True,
            'total_messages': stats['total_messages'],
            'sent_messages': stats['sent_messages'],
            'received_messages': stats['received_messages'],
            'unread_messages': stats['unread_messages'],
            'threads': stats['total_threads'],
            'contacts': stats['total_contacts'],
            'date_range': stats['date_range'],
            'dual_sim': stats['sim_analysis']['dual_sim'],
            'verification_codes': len(indicators['verification_codes']),
            'banking_messages': len(indicators['banking_messages']),
            'international_numbers': len(indicators['international_numbers']),
            'suspicious_links': len(indicators['suspicious_links']),
            'authentication_apps': len(indicators['authentication_apps'])
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def extract_sms_from_device(adb_path: str = "adb", output_file: str = "sms_output.txt") -> Dict[str, Any]:
    """
    Extract SMS data directly from connected Android device using ADB.
    
    Args:
        adb_path: Path to ADB executable
        output_file: Output file for SMS data
    
    Returns:
        Dictionary containing extraction results
    """
    try:
        import subprocess
        
        # Check if device is connected
        result = _run_subprocess_with_encoding([adb_path, "devices"], timeout=10)
        
        if result.returncode != 0:
            return {'success': False, 'error': 'ADB command failed'}
        
        if "device" not in result.stdout or result.stdout.count("\n") < 2:
            return {'success': False, 'error': 'No Android device connected'}
        
        # Extract SMS data
        sms_command = [adb_path, "shell", "content", "query", "--uri", "content://sms"]
        
        result = _run_subprocess_with_encoding(sms_command, timeout=60)
        
        if result.returncode != 0:
            return {'success': False, 'error': f'SMS extraction failed: {result.stderr}'}
        
        # Save to file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(result.stdout)
        
        return {
            'success': True,
            'output_file': output_file,
            'message': f'SMS data extracted to {output_file}'
        }
        
    except subprocess.TimeoutExpired:
        return {'success': False, 'error': 'ADB command timed out'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


# Example usage for testing
if __name__ == "__main__":
    # Test with existing SMS file
    test_file = "../utils/smsOUT.txt"
    if os.path.exists(test_file):
        print("Testing SMS parser integration...")
        
        # Get summary
        summary = get_sms_summary(test_file)
        if summary.get('success'):
            print(f"SMS Summary:")
            print(f"- Total Messages: {summary['total_messages']}")
            print(f"- Threads: {summary['threads']}")
            print(f"- Contacts: {summary['contacts']}")
            print(f"- Verification Codes: {summary['verification_codes']}")
            print(f"- Banking Messages: {summary['banking_messages']}")
            print(f"- International Numbers: {summary['international_numbers']}")
        else:
            print(f"Error: {summary.get('error')}")
    else:
        print(f"Test file not found: {test_file}")
