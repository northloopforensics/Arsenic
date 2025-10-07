#!/usr/bin/env python3
"""
Dumpsys Parser for Android Forensic Analysis
Extracts key artifacts from ADB dumpsys reports for digital forensic investigations.

Author: Arsenic Forensic Tool
Date: June 2025
"""

import re
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DumpsysParser:
    """Parser for Android dumpsys reports with forensic focus."""
    
    def __init__(self, dumpsys_file_path: str):
        """
        Initialize the parser with dumpsys file path.
        
        Args:
            dumpsys_file_path: Path to the dumpsys output file
        """
        self.file_path = dumpsys_file_path
        self.content = ""
        self.services = {}
        
        # Communication apps of interest
        self.communication_apps = {
            'com.whatsapp': 'WhatsApp',
            'org.thoughtcrime.securesms': 'Signal',
            'com.facebook.katana': 'Facebook',
            'com.facebook.orca': 'Facebook Messenger',
            'com.discord': 'Discord',
            'com.skype.raider': 'Skype',
            'com.telegram.messenger': 'Telegram',
            'com.google.android.apps.tachyon': 'Google Duo',
            'com.snapchat.android': 'Snapchat',
            'com.instagram.android': 'Instagram',
            'com.twitter.android': 'Twitter',
            'com.linkedin.android': 'LinkedIn',
            'com.viber.voip': 'Viber',
            'com.google.android.gm': 'Gmail',
            'com.kik.android': 'Kik',
            
            'com.microsoft.office.outlook': 'Outlook'
        }
        
        # Browser apps
        self.browser_apps = {
            'com.android.chrome': 'Chrome',
            'com.sec.android.app.sbrowser': 'Samsung Internet',
            'org.mozilla.firefox': 'Firefox',
            'com.opera.browser': 'Opera',
            'com.microsoft.emmx': 'Edge',
            'com.duckduckgo.mobile.android': 'DuckDuckGo Browser',
            'com.brave.browser': 'Brave Browser',
            'com.android.webview': 'Android System WebView',
        }
        
        # Cloud storage apps
        self.cloud_apps = {
            'com.google.android.apps.photos': 'Google Photos',
            'com.microsoft.skydrive': 'OneDrive',
            'com.dropbox.android': 'Dropbox',
            'com.box.android': 'Box',
            'com.amazon.clouddrive.photos': 'Amazon Photos',
            'com.mega.android': 'MEGA',
            'com.samsung.android.app.scloud': 'Samsung Cloud',
            'com.google.android.apps.docs': 'Google Drive',
        }

    def load_dumpsys_file(self) -> bool:
        """Load and read the dumpsys file."""
        try:
            with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                self.content = f.read()
            logger.info(f"Successfully loaded dumpsys file: {self.file_path}")
            return True
        except Exception as e:
            logger.error(f"Error loading dumpsys file: {e}")
            return False

    def extract_device_info(self) -> Dict:
        """Extract basic device information."""
        device_info = {
            'analysis_timestamp': datetime.now().isoformat(),
            'device_model': None,
            'android_version': None,
            'build_info': {},
            'users': [],
            'battery_info': {},
            'telephony_state': {}
        }
        
        # Extract users information
        user_pattern = r'current users: \[([^\]]+)\]'
        user_match = re.search(user_pattern, self.content)
        if user_match:
            users = [int(u.strip()) for u in user_match.group(1).split(',')]
            device_info['users'] = users
            logger.info(f"Found users: {users}")
        
        # Extract battery information
        battery_pattern = r'Time on battery \(min\): ([0-9.]+)'
        battery_match = re.search(battery_pattern, self.content)
        if battery_match:
            device_info['battery_info']['time_on_battery_minutes'] = float(battery_match.group(1))
        
        # Extract telephony state
        phone_state_pattern = r'mCallState=(\d+)'
        if re.search(phone_state_pattern, self.content):
            device_info['telephony_state']['call_state_detected'] = True
            device_info['telephony_state']['out_of_service'] = 'OUT_OF_SERVICE' in self.content
        
        return device_info

    def extract_installed_apps(self) -> Dict:
        """Extract information about installed applications."""
        apps_info = {
            'communication_apps': [],
            'browser_apps': [],
            'cloud_apps': [],
            'all_packages': [],
            'secure_folder_apps': []
        }
        
        # Look for package information in dumpsys package service
        package_pattern = r'Package \[([^\]]+)\].*?userId=(\d+)'
        packages = re.findall(package_pattern, self.content, re.DOTALL)
        
        for package_name, user_id in packages:
            package_info = {
                'package': package_name,
                'user_id': int(user_id),
                'is_secure_folder': int(user_id) == 150
            }
            
            apps_info['all_packages'].append(package_info)
            
            # Categorize apps
            if package_name in self.communication_apps:
                app_info = package_info.copy()
                app_info['app_name'] = self.communication_apps[package_name]
                app_info['category'] = 'communication'
                apps_info['communication_apps'].append(app_info)
                
                if int(user_id) == 150:
                    apps_info['secure_folder_apps'].append(app_info)
            
            elif package_name in self.browser_apps:
                app_info = package_info.copy()
                app_info['app_name'] = self.browser_apps[package_name]
                app_info['category'] = 'browser'
                apps_info['browser_apps'].append(app_info)
                
            elif package_name in self.cloud_apps:
                app_info = package_info.copy()
                app_info['app_name'] = self.cloud_apps[package_name]
                app_info['category'] = 'cloud'
                apps_info['cloud_apps'].append(app_info)
        
        # Alternative method - look for installed packages in activity service
        activity_pattern = r'userId=(\d+).*?pkg=([^\s]+)'
        activity_packages = re.findall(activity_pattern, self.content)
        
        for user_id, package_name in activity_packages:
            if package_name in self.communication_apps and not any(
                app['package'] == package_name and app['user_id'] == int(user_id) 
                for app in apps_info['communication_apps']
            ):
                app_info = {
                    'package': package_name,
                    'user_id': int(user_id),
                    'app_name': self.communication_apps[package_name],
                    'category': 'communication',
                    'is_secure_folder': int(user_id) == 150
                }
                apps_info['communication_apps'].append(app_info)
        
        logger.info(f"Found {len(apps_info['communication_apps'])} communication apps")
        logger.info(f"Found {len(apps_info['secure_folder_apps'])} secure folder apps")
        
        return apps_info

    def extract_usage_stats(self) -> Dict:
        """Extract app usage statistics and recent activity."""
        usage_info = {
            'recent_events': [],
            'app_usage': [],
            'screen_activity': [],
            'configuration_changes': []
        }
        
        # Look for usage stats service
        usagestats_section = self._extract_service_section('usagestats')
        if usagestats_section:
            # Extract recent events
            event_pattern = r'time="([^"]+)" type=([^\s]+) package=([^\s]+)'
            events = re.findall(event_pattern, usagestats_section)
            
            for timestamp, event_type, package in events:
                usage_info['recent_events'].append({
                    'timestamp': timestamp,
                    'event_type': event_type,
                    'package': package
                })
            
            # Extract app usage times
            usage_pattern = r'package=([^\s]+) totalTimeUsed="([^"]+)" lastTimeUsed="([^"]+)" appLaunchCount=(\d+)'
            usage_matches = re.findall(usage_pattern, usagestats_section)
            
            for package, total_time, last_used, launch_count in usage_matches:
                if total_time != "00:00" or int(launch_count) > 0:
                    usage_info['app_usage'].append({
                        'package': package,
                        'total_time_used': total_time,
                        'last_time_used': last_used,
                        'launch_count': int(launch_count)
                    })
            
            # Extract screen activity
            screen_pattern = r'(screen-interactive|screen-non-interactive): (\d+)x for "([^"]+)"'
            screen_matches = re.findall(screen_pattern, usagestats_section)
            
            for activity_type, count, duration in screen_matches:
                usage_info['screen_activity'].append({
                    'activity_type': activity_type,
                    'count': int(count),
                    'duration': duration
                })
        
        return usage_info

    def extract_location_data(self) -> Dict:
        """Extract location-related information."""
        location_info = {
            'location_enabled': False,
            'recent_requests': [],
            'location_providers': [],
            'gps_status': {},
            'historical_records': []
        }
        
        location_section = self._extract_service_section('location')
        if location_section:
            # Check if location is enabled
            location_info['location_enabled'] = 'Location Enabled: true' in location_section
            
            # Extract recent location requests
            request_pattern = r'At ([^:]+): ([+-]) +([^:]+) request from ([^\s]+)'
            requests = re.findall(request_pattern, location_section)
            
            for timestamp, action, request_type, app in requests:
                location_info['recent_requests'].append({
                    'timestamp': timestamp.strip(),
                    'action': 'start' if action == '+' else 'stop',
                    'request_type': request_type.strip(),
                    'requesting_app': app.strip()
                })
            
            # Extract historical records
            historical_pattern = r'([^:]+): ([^:]+): Interval (\d+) seconds: Duration requested (\d+) total'
            historical_matches = re.findall(historical_pattern, location_section)
            
            for provider, app, interval, duration in historical_matches:
                location_info['historical_records'].append({
                    'provider': provider.strip(),
                    'app': app.strip(),
                    'interval_seconds': int(interval),
                    'duration_minutes': int(duration)
                })
        
        return location_info

    def extract_notifications(self) -> Dict:
        """Extract notification information."""
        notification_info = {
            'active_notifications': [],
            'notification_channels': [],
            'recent_interruptions': []
        }
        
        notification_section = self._extract_service_section('notification')
        if notification_section:
            # Extract active notifications
            notif_pattern = r'NotificationRecord\([^:]+: pkg=([^\s]+).*?id=(\d+).*?tag=([^\s]*)'
            notifications = re.findall(notif_pattern, notification_section, re.DOTALL)
            
            for package, notif_id, tag in notifications:
                notification_info['active_notifications'].append({
                    'package': package,
                    'notification_id': notif_id,
                    'tag': tag if tag else None
                })
            
            # Look for communication app notifications specifically
            for line in notification_section.split('\n'):
                if any(app in line for app in self.communication_apps.keys()):
                    if 'NotificationRecord' in line:
                        notification_info['recent_interruptions'].append(line.strip())
        
        return notification_info

    def extract_telephony_info(self) -> Dict:
        """Extract telephony and call-related information."""
        telephony_info = {
            'phone_state': {},
            'call_logs': [],
            'sms_info': [],
            'emergency_numbers': [],
            'carrier_info': {}
        }
        
        telephony_section = self._extract_service_section('telephony.registry')
        if telephony_section:
            # Extract phone state
            if 'mCallState=' in telephony_section:
                call_state_match = re.search(r'mCallState=(\d+)', telephony_section)
                if call_state_match:
                    telephony_info['phone_state']['call_state'] = int(call_state_match.group(1))
            
            # Extract emergency numbers
            emergency_pattern = r'mEmergencyNumberList=\{[^}]*\[([^\]]+)\]'
            emergency_match = re.search(emergency_pattern, telephony_section)
            if emergency_match:
                numbers = emergency_match.group(1)
                telephony_info['emergency_numbers'] = numbers.split(', ')
            
            # Extract service state
            if 'OUT_OF_SERVICE' in telephony_section:
                telephony_info['phone_state']['service_status'] = 'OUT_OF_SERVICE'
            elif 'IN_SERVICE' in telephony_section:
                telephony_info['phone_state']['service_status'] = 'IN_SERVICE'
        
        return telephony_info

    def _extract_service_section(self, service_name: str) -> Optional[str]:
        """Extract a specific service section from dumpsys output."""
        pattern = f'DUMP OF SERVICE {service_name}:(.*?)(?=DUMP OF SERVICE|$)'
        match = re.search(pattern, self.content, re.DOTALL)
        return match.group(1) if match else None

    def parse_all(self) -> Dict:
        """Parse all forensic artifacts from the dumpsys report."""
        if not self.load_dumpsys_file():
            return {}
        
        logger.info("Starting comprehensive dumpsys analysis...")
        
        forensic_data = {
            'device_info': self.extract_device_info(),
            'installed_apps': self.extract_installed_apps(),
            'usage_stats': self.extract_usage_stats(),
            'location_data': self.extract_location_data(),
            'notifications': self.extract_notifications(),
            'telephony_info': self.extract_telephony_info()
        }
        
        # Generate summary
        forensic_data['summary'] = self._generate_summary(forensic_data)
        
        logger.info("Dumpsys analysis completed")
        return forensic_data

    def _generate_summary(self, data: Dict) -> Dict:
        """Generate a forensic summary of the parsed data."""
        summary = {
            'total_communication_apps': len(data['installed_apps']['communication_apps']),
            'secure_folder_enabled': len(data['installed_apps']['secure_folder_apps']) > 0,
            'location_services_active': data['location_data']['location_enabled'],
            'active_notifications_count': len(data['notifications']['active_notifications']),
            'recent_activity_detected': len(data['usage_stats']['recent_events']) > 0,
            'telephony_status': data['telephony_info']['phone_state'].get('service_status', 'UNKNOWN'),
            'investigative_priority': 'HIGH' if len(data['installed_apps']['communication_apps']) > 3 else 'MEDIUM'
        }
        
        # Identify key apps of interest
        priority_apps = []
        for app in data['installed_apps']['communication_apps']:
            if app['package'] in ['com.whatsapp', 'org.thoughtcrime.securesms', 'com.facebook.katana']:
                priority_apps.append(app['app_name'])
        
        summary['priority_communication_apps'] = priority_apps
        
        return summary

    def save_results(self, output_file: str, data: Dict = None) -> bool:
        """Save parsed results to a JSON file."""
        if data is None:
            data = self.parse_all()
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
            logger.info(f"Results saved to: {output_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving results: {e}")
            return False

    def generate_report(self, data: Dict = None) -> str:
        """Generate a human-readable forensic report."""
        if data is None:
            data = self.parse_all()
        
        report = []
        report.append("=" * 60)
        report.append("ANDROID DUMPSYS FORENSIC ANALYSIS REPORT")
        report.append("=" * 60)
        report.append(f"Analysis Date: {data['device_info']['analysis_timestamp']}")
        report.append(f"Investigative Priority: {data['summary']['investigative_priority']}")
        report.append("")
        
        # Device Info
        report.append("DEVICE INFORMATION:")
        report.append("-" * 20)
        report.append(f"Users: {data['device_info']['users']}")
        if data['device_info']['battery_info']:
            report.append(f"Battery Time: {data['device_info']['battery_info'].get('time_on_battery_minutes', 'N/A')} minutes")
        report.append(f"Telephony Status: {data['summary']['telephony_status']}")
        report.append("")
        
        # Communication Apps
        report.append("COMMUNICATION APPLICATIONS:")
        report.append("-" * 30)
        for app in data['installed_apps']['communication_apps']:
            folder_indicator = " [SECURE FOLDER]" if app['is_secure_folder'] else ""
            report.append(f"• {app['app_name']} ({app['package']}){folder_indicator}")
        report.append("")
        
        # Recent Activity
        if data['usage_stats']['recent_events']:
            report.append("RECENT ACTIVITY (Last 10 events):")
            report.append("-" * 35)
            for event in data['usage_stats']['recent_events'][:10]:
                report.append(f"• {event['timestamp']} - {event['event_type']} - {event['package']}")
            report.append("")
        
        # Location Data
        report.append("LOCATION SERVICES:")
        report.append("-" * 17)
        report.append(f"Location Enabled: {data['location_data']['location_enabled']}")
        report.append(f"Recent Requests: {len(data['location_data']['recent_requests'])}")
        report.append("")
        
        # Notifications
        report.append("ACTIVE NOTIFICATIONS:")
        report.append("-" * 20)
        comm_notifications = [n for n in data['notifications']['active_notifications'] 
                            if n['package'] in self.communication_apps]
        for notif in comm_notifications:
            app_name = self.communication_apps.get(notif['package'], notif['package'])
            report.append(f"• {app_name}: ID {notif['notification_id']}")
        report.append("")
        
        # Recommendations
        report.append("FORENSIC RECOMMENDATIONS:")
        report.append("-" * 25)
        report.append("1. Extract communication app databases")
        if data['summary']['secure_folder_enabled']:
            report.append("2. Investigate Secure Folder (User 150) separately")
        if data['location_data']['location_enabled']:
            report.append("3. Collect location cache and GPS data")
        report.append("4. Analyze recent app usage patterns")
        report.append("5. Check browser history and downloads")
        
        return "\n".join(report)


def main():
    """Main function for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Parse Android dumpsys reports for forensic analysis')
    parser.add_argument('input_file', help='Path to dumpsys output file')
    parser.add_argument('--output', '-o', help='Output JSON file path')
    parser.add_argument('--report', '-r', help='Output text report file path')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize parser
    dumpsys_parser = DumpsysParser(args.input_file)
    
    # Parse data
    forensic_data = dumpsys_parser.parse_all()
    
    if not forensic_data:
        print("Error: Failed to parse dumpsys file")
        return 1
    
    # Save JSON output
    if args.output:
        dumpsys_parser.save_results(args.output, forensic_data)
    
    # Generate and save report
    if args.report:
        report = dumpsys_parser.generate_report(forensic_data)
        with open(args.report, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"Report saved to: {args.report}")
    else:
        # Print report to console
        print(dumpsys_parser.generate_report(forensic_data))
    
    return 0


if __name__ == '__main__':
    exit(main())