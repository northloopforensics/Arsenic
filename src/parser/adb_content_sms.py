#!/usr/bin/env python3
"""
ADB Content SMS Parser
======================

This module parses SMS messages extracted from Android devices using ADB content queries.
It processes the raw output from 'adb shell content query --uri content://sms' and
extracts structured forensic information for triage analysis.

Author: Arsenic Forensics
"""

import re
import json
import csv
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from pathlib import Path


class SMSMessage:
    """Represents a single SMS message with all its metadata."""
    
    def __init__(self, raw_data: str):
        """Initialize SMS message from raw ADB content query row."""
        self.raw_data = raw_data
        self.fields = self._parse_fields(raw_data)
        
    def _parse_fields(self, raw_data: str) -> Dict[str, Any]:
        """Parse the comma-separated field=value pairs from ADB output."""
        fields = {}
        
        # Remove 'Row: X ' prefix
        data = re.sub(r'^Row: \d+\s+', '', raw_data)
        
        # Split by comma, but handle commas within quoted values
        field_pattern = r'(\w+)=((?:[^,=]+|NULL|"[^"]*")*)(?:,\s*|$)'
        matches = re.findall(field_pattern, data)
        
        for field, value in matches:
            # Clean up the value
            if value == 'NULL':
                fields[field] = None
            elif value.startswith('"') and value.endswith('"'):
                fields[field] = value[1:-1]  # Remove quotes
            elif value.isdigit():
                fields[field] = int(value)
            elif value.replace('.', '').isdigit():
                fields[field] = float(value)
            else:
                fields[field] = value
                
        return fields
    
    @property
    def id(self) -> Optional[int]:
        """Message ID."""
        return self.fields.get('_id')
    
    @property
    def thread_id(self) -> Optional[int]:
        """Thread ID (conversation group)."""
        return self.fields.get('thread_id')
    
    @property
    def address(self) -> Optional[str]:
        """Sender/recipient phone number or name."""
        return self.fields.get('address')
    
    @property
    def body(self) -> Optional[str]:
        """Message body/content."""
        return self.fields.get('body')
    
    @property
    def date(self) -> Optional[datetime]:
        """Message date/time."""
        timestamp = self.fields.get('date')
        if timestamp:
            try:
                # Convert from milliseconds to seconds
                return datetime.fromtimestamp(timestamp / 1000)
            except (ValueError, TypeError):
                return None
        return None
    
    @property
    def date_sent(self) -> Optional[datetime]:
        """Date/time when message was sent."""
        timestamp = self.fields.get('date_sent')
        if timestamp and timestamp != 0:
            try:
                return datetime.fromtimestamp(timestamp / 1000)
            except (ValueError, TypeError):
                return None
        return None
    
    @property
    def type(self) -> str:
        """Message type (1=received, 2=sent, 3=draft, 4=outbox, 5=failed, 6=queued)."""
        msg_type = self.fields.get('type', 0)
        type_map = {
            1: 'received',
            2: 'sent',
            3: 'draft',
            4: 'outbox',
            5: 'failed',
            6: 'queued'
        }
        return type_map.get(msg_type, 'unknown')
    
    @property
    def read(self) -> bool:
        """Whether message has been read."""
        return bool(self.fields.get('read', 0))
    
    @property
    def seen(self) -> bool:
        """Whether message has been seen."""
        return bool(self.fields.get('seen', 0))
    
    @property
    def sim_slot(self) -> Optional[int]:
        """SIM slot used for the message."""
        return self.fields.get('sim_slot')
    
    @property
    def sim_imsi(self) -> Optional[str]:
        """SIM IMSI number."""
        return self.fields.get('sim_imsi')
    
    @property
    def service_center(self) -> Optional[str]:
        """SMS service center number."""
        return self.fields.get('service_center')
    
    @property
    def creator(self) -> Optional[str]:
        """App that created/handled the message."""
        return self.fields.get('creator')
    
    @property
    def is_spam(self) -> bool:
        """Whether message is marked as spam."""
        return bool(self.fields.get('spam_report', 0))
    
    @property
    def is_secure(self) -> bool:
        """Whether message is in secure/secret mode."""
        return bool(self.fields.get('secret_mode', 0))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'thread_id': self.thread_id,
            'address': self.address,
            'body': self.body,
            'date': self.date.isoformat() if self.date else None,
            'date_sent': self.date_sent.isoformat() if self.date_sent else None,
            'type': self.type,
            'read': self.read,
            'seen': self.seen,
            'sim_slot': self.sim_slot,
            'sim_imsi': self.sim_imsi,
            'service_center': self.service_center,
            'creator': self.creator,
            'is_spam': self.is_spam,
            'is_secure': self.is_secure,
            'all_fields': self.fields
        }


class SMSThread:
    """Represents a conversation thread (group of messages)."""
    
    def __init__(self, thread_id: int):
        self.thread_id = thread_id
        self.messages: List[SMSMessage] = []
        self.participants: set = set()
    
    def add_message(self, message: SMSMessage):
        """Add a message to this thread."""
        self.messages.append(message)
        if message.address:
            self.participants.add(message.address)
    
    @property
    def message_count(self) -> int:
        """Number of messages in thread."""
        return len(self.messages)
    
    @property
    def first_message_date(self) -> Optional[datetime]:
        """Date of first message in thread."""
        dates = [msg.date for msg in self.messages if msg.date]
        return min(dates) if dates else None
    
    @property
    def last_message_date(self) -> Optional[datetime]:
        """Date of last message in thread."""
        dates = [msg.date for msg in self.messages if msg.date]
        return max(dates) if dates else None
    
    @property
    def unread_count(self) -> int:
        """Number of unread messages."""
        return sum(1 for msg in self.messages if not msg.read)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert thread to dictionary."""
        return {
            'thread_id': self.thread_id,
            'participants': list(self.participants),
            'message_count': self.message_count,
            'unread_count': self.unread_count,
            'first_message': self.first_message_date.isoformat() if self.first_message_date else None,
            'last_message': self.last_message_date.isoformat() if self.last_message_date else None,
            'messages': [msg.to_dict() for msg in self.messages]
        }


class SMSParser:
    """Main SMS parser class for processing ADB content query output."""
    
    def __init__(self):
        self.messages: List[SMSMessage] = []
        self.threads: Dict[int, SMSThread] = {}
        self.contacts: Dict[str, Dict[str, Any]] = {}
        
    def parse_file(self, file_path: Union[str, Path]) -> None:
        """Parse SMS data from ADB content query output file."""
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"SMS file not found: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        self.parse_content(content)
    
    def parse_content(self, content: str) -> None:
        """Parse SMS data from raw content string."""
        lines = content.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if line.startswith('Row:'):
                try:
                    message = SMSMessage(line)
                    self.messages.append(message)
                    self._add_to_thread(message)
                    self._update_contact_info(message)
                except Exception as e:
                    print(f"Error parsing SMS line: {e}")
                    continue
    
    def _add_to_thread(self, message: SMSMessage) -> None:
        """Add message to appropriate thread."""
        if message.thread_id is not None:
            if message.thread_id not in self.threads:
                self.threads[message.thread_id] = SMSThread(message.thread_id)
            self.threads[message.thread_id].add_message(message)
    
    def _update_contact_info(self, message: SMSMessage) -> None:
        """Update contact information from message."""
        if message.address and isinstance(message.address, str):
            if message.address not in self.contacts:
                self.contacts[message.address] = {
                    'address': message.address,
                    'message_count': 0,
                    'first_contact': None,
                    'last_contact': None,
                    'sim_slots': set(),
                    'service_centers': set()
                }
            
            contact = self.contacts[message.address]
            contact['message_count'] += 1
            
            if message.date:
                if not contact['first_contact'] or message.date < datetime.fromisoformat(contact['first_contact']):
                    contact['first_contact'] = message.date.isoformat()
                if not contact['last_contact'] or message.date > datetime.fromisoformat(contact['last_contact']):
                    contact['last_contact'] = message.date.isoformat()
            
            if message.sim_slot is not None:
                contact['sim_slots'].add(message.sim_slot)
            if message.service_center:
                contact['service_centers'].add(message.service_center)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get SMS statistics for forensic analysis."""
        if not self.messages:
            return {'error': 'No messages parsed'}
        
        # Basic counts
        total_messages = len(self.messages)
        sent_messages = sum(1 for msg in self.messages if msg.type == 'sent')
        received_messages = sum(1 for msg in self.messages if msg.type == 'received')
        unread_messages = sum(1 for msg in self.messages if not msg.read)
        spam_messages = sum(1 for msg in self.messages if msg.is_spam)
        secure_messages = sum(1 for msg in self.messages if msg.is_secure)
        
        # Date range
        dates = [msg.date for msg in self.messages if msg.date]
        first_message = min(dates) if dates else None
        last_message = max(dates) if dates else None
        
        # SIM analysis
        sim_slots = set()
        sim_imsis = set()
        for msg in self.messages:
            if msg.sim_slot is not None:
                sim_slots.add(msg.sim_slot)
            if msg.sim_imsi:
                sim_imsis.add(msg.sim_imsi)
        
        # App analysis
        apps = {}
        for msg in self.messages:
            if msg.creator:
                apps[msg.creator] = apps.get(msg.creator, 0) + 1
        
        # Most active contacts
        contact_activity = []
        for addr, info in self.contacts.items():
            contact_activity.append({
                'address': addr,
                'message_count': info['message_count'],
                'first_contact': info['first_contact'],
                'last_contact': info['last_contact']
            })
        contact_activity.sort(key=lambda x: x['message_count'], reverse=True)
        
        return {
            'total_messages': total_messages,
            'sent_messages': sent_messages,
            'received_messages': received_messages,
            'unread_messages': unread_messages,
            'spam_messages': spam_messages,
            'secure_messages': secure_messages,
            'total_threads': len(self.threads),
            'total_contacts': len(self.contacts),
            'date_range': {
                'first_message': first_message.isoformat() if first_message else None,
                'last_message': last_message.isoformat() if last_message else None
            },
            'sim_analysis': {
                'sim_slots': list(sim_slots),
                'sim_imsis': list(sim_imsis),
                'dual_sim': len(sim_slots) > 1
            },
            'messaging_apps': apps,
            'top_contacts': contact_activity[:10]
        }
    
    def get_forensic_indicators(self) -> Dict[str, Any]:
        """Extract forensic indicators of interest."""
        indicators = {
            'verification_codes': [],
            'banking_messages': [],
            'location_data': [],
            'suspicious_links': [],
            'international_numbers': [],
            'premium_services': [],
            'authentication_apps': []
        }
        
        # Patterns for forensic analysis
        verification_patterns = [
            r'verification code[:\s]*[is]*[:\s]*(\d{4,8})',
            r'code[:\s]*[is]*[:\s]*(\d{4,8})',
            r'OTP[:\s]*[is]*[:\s]*(\d{4,8})',
            r'pin[:\s]*[is]*[:\s]*(\d{4,8})',
            r'(\d{6})\s+is your',
            r'(\d{4,8})\s+is your.*code',
            r'code.*[:\s](\d{4,8})'
        ]
        
        banking_keywords = ['bank', 'account', 'balance', 'transaction', 'payment', 'credit', 'debit']
        location_keywords = ['location', 'address', 'GPS', 'coordinates', 'latitude', 'longitude']
        
        for message in self.messages:
            if not message.body or not isinstance(message.body, str):
                continue
            
            body_lower = message.body.lower()
            
            # Check for verification codes
            for pattern in verification_patterns:
                matches = re.findall(pattern, message.body, re.IGNORECASE)
                if matches:
                    indicators['verification_codes'].append({
                        'message_id': message.id,
                        'sender': message.address,
                        'date': message.date.isoformat() if message.date else None,
                        'code': matches[0],
                        'full_text': message.body[:100] + '...' if len(message.body) > 100 else message.body
                    })
            
            # Check for banking messages
            if any(keyword in body_lower for keyword in banking_keywords):
                indicators['banking_messages'].append({
                    'message_id': message.id,
                    'sender': message.address,
                    'date': message.date.isoformat() if message.date else None,
                    'preview': message.body[:100] + '...' if len(message.body) > 100 else message.body
                })
            
            # Check for location data
            if any(keyword in body_lower for keyword in location_keywords):
                indicators['location_data'].append({
                    'message_id': message.id,
                    'sender': message.address,
                    'date': message.date.isoformat() if message.date else None,
                    'preview': message.body[:100] + '...' if len(message.body) > 100 else message.body
                })
            
            # Check for suspicious links
            url_pattern = r'https?://[^\s]+'
            urls = re.findall(url_pattern, message.body)
            if urls:
                indicators['suspicious_links'].append({
                    'message_id': message.id,
                    'sender': message.address,
                    'date': message.date.isoformat() if message.date else None,
                    'urls': urls,
                    'preview': message.body[:100] + '...' if len(message.body) > 100 else message.body
                })
            
            # Check for international numbers
            if message.address and isinstance(message.address, str) and message.address.startswith('+'):
                country_code = message.address[1:3]
                if country_code not in ['27', '1']:  # Assuming local country codes
                    indicators['international_numbers'].append({
                        'number': message.address,
                        'country_code': country_code,
                        'message_count': sum(1 for msg in self.messages if msg.address == message.address)
                    })
            
            # Check for authentication apps
            auth_apps = ['whatsapp', 'telegram', 'signal', 'discord', 'facebook', 'google', 'apple', 'microsoft', 
                         'amazon', 'netflix', 'paypal', 'venmo', 'cashapp', 'uber', 'tinder', 'instagram', 'snapchat', 
                         'tiktok', 'linkedin', 'gmail', 'yahoo', 'outlook']
            if any(app in body_lower for app in auth_apps):
                indicators['authentication_apps'].append({
                    'message_id': message.id,
                    'sender': message.address,
                    'date': message.date.isoformat() if message.date else None,
                    'app': next(app for app in auth_apps if app in body_lower),
                    'preview': message.body[:100] + '...' if len(message.body) > 100 else message.body
                })
        
        # Remove duplicates from international numbers
        seen_numbers = set()
        unique_international = []
        for item in indicators['international_numbers']:
            if item['number'] not in seen_numbers:
                seen_numbers.add(item['number'])
                unique_international.append(item)
        indicators['international_numbers'] = unique_international
        
        return indicators
    
    def export_to_json(self, output_path: Union[str, Path]) -> None:
        """Export parsed SMS data to JSON."""
        output_path = Path(output_path)
        
        data = {
            'metadata': {
                'export_date': datetime.now().isoformat(),
                'total_messages': len(self.messages),
                'total_threads': len(self.threads)
            },
            'statistics': self.get_statistics(),
            'forensic_indicators': self.get_forensic_indicators(),
            'threads': [thread.to_dict() for thread in self.threads.values()],
            'contacts': {addr: {**info, 'sim_slots': list(info['sim_slots']), 
                               'service_centers': list(info['service_centers'])} 
                        for addr, info in self.contacts.items()}
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def export_to_csv(self, output_path: Union[str, Path]) -> None:
        """Export SMS messages to CSV format."""
        output_path = Path(output_path)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Write header
            writer.writerow([
                'ID', 'Thread ID', 'Address', 'Body', 'Date', 'Date Sent',
                'Type', 'Read', 'Seen', 'SIM Slot', 'SIM IMSI', 'Service Center',
                'Creator App', 'Is Spam', 'Is Secure'
            ])
            
            # Write messages
            for message in self.messages:
                writer.writerow([
                    message.id,
                    message.thread_id,
                    message.address,
                    message.body,
                    message.date.isoformat() if message.date else '',
                    message.date_sent.isoformat() if message.date_sent else '',
                    message.type,
                    message.read,
                    message.seen,
                    message.sim_slot,
                    message.sim_imsi,
                    message.service_center,
                    message.creator,
                    message.is_spam,
                    message.is_secure
                ])
    
    def generate_report(self, output_path: Union[str, Path]) -> None:
        """Generate a comprehensive forensic report."""
        output_path = Path(output_path)
        
        stats = self.get_statistics()
        indicators = self.get_forensic_indicators()
        
        report = []
        report.append("=" * 60)
        report.append("SMS FORENSIC ANALYSIS REPORT")
        report.append("=" * 60)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # Executive Summary
        report.append("EXECUTIVE SUMMARY")
        report.append("-" * 20)
        report.append(f"Total Messages: {stats['total_messages']}")
        report.append(f"Sent Messages: {stats['sent_messages']}")
        report.append(f"Received Messages: {stats['received_messages']}")
        report.append(f"Unread Messages: {stats['unread_messages']}")
        report.append(f"Conversation Threads: {stats['total_threads']}")
        report.append(f"Unique Contacts: {stats['total_contacts']}")
        
        if stats['date_range']['first_message'] and stats['date_range']['last_message']:
            report.append(f"Date Range: {stats['date_range']['first_message']} to {stats['date_range']['last_message']}")
        
        if stats['sim_analysis']['dual_sim']:
            report.append("DUAL SIM DEVICE DETECTED")
        
        report.append("")
        
        # SIM Analysis
        report.append("SIM CARD ANALYSIS")
        report.append("-" * 20)
        report.append(f"SIM Slots Used: {stats['sim_analysis']['sim_slots']}")
        report.append(f"SIM IMSIs: {stats['sim_analysis']['sim_imsis']}")
        report.append("")
        
        # Messaging Apps
        if stats['messaging_apps']:
            report.append("MESSAGING APPLICATIONS")
            report.append("-" * 25)
            for app, count in sorted(stats['messaging_apps'].items(), key=lambda x: x[1], reverse=True):
                report.append(f"{app}: {count} messages")
            report.append("")
        
        # Top Contacts
        if stats['top_contacts']:
            report.append("TOP CONTACTS")
            report.append("-" * 12)
            for i, contact in enumerate(stats['top_contacts'][:10], 1):
                report.append(f"{i}. {contact['address']}: {contact['message_count']} messages")
                if contact['last_contact']:
                    report.append(f"   Last contact: {contact['last_contact']}")
            report.append("")
        
        # Investigative Indicators
        report.append("INVESTIGATIVE INDICATORS")
        report.append("-" * 18)
        
        if indicators['verification_codes']:
            report.append(f"Verification Codes Found: {len(indicators['verification_codes'])}")
            for code in indicators['verification_codes'][:5]:
                report.append(f"  - {code['sender']}: {code['code']} ({code['date']})")
        
        if indicators['banking_messages']:
            report.append(f"Banking Messages: {len(indicators['banking_messages'])}")
        
        if indicators['international_numbers']:
            report.append(f"International Numbers: {len(indicators['international_numbers'])}")
            for num in indicators['international_numbers'][:5]:
                report.append(f"  - {num['number']} (Country: +{num['country_code']})")
        
        if indicators['suspicious_links']:
            report.append(f"Messages with Links: {len(indicators['suspicious_links'])}")
        
        if indicators['authentication_apps']:
            report.append(f"Authentication App Messages: {len(indicators['authentication_apps'])}")
        
        report.append("")
        report.append("=" * 60)
        report.append("END OF REPORT")
        report.append("=" * 60)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report))


def main():
    """Main function for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Parse SMS messages from ADB content query output')
    parser.add_argument('input_file', help='Input file containing ADB SMS query output')
    parser.add_argument('--output-dir', '-o', default='.', help='Output directory for reports')
    parser.add_argument('--format', '-f', choices=['json', 'csv', 'report', 'all'], 
                       default='all', help='Output format')
    
    args = parser.parse_args()
    
    try:
        sms_parser = SMSParser()
        sms_parser.parse_file(args.input_file)
        
        output_dir = Path(args.output_dir)
        output_dir.mkdir(exist_ok=True)
        
        base_name = Path(args.input_file).stem
        
        if args.format in ['json', 'all']:
            json_path = output_dir / f"{base_name}_sms_analysis.json"
            sms_parser.export_to_json(json_path)
            print(f"JSON report saved to: {json_path}")
        
        if args.format in ['csv', 'all']:
            csv_path = output_dir / f"{base_name}_sms_messages.csv"
            sms_parser.export_to_csv(csv_path)
            print(f"CSV export saved to: {csv_path}")
        
        if args.format in ['report', 'all']:
            report_path = output_dir / f"{base_name}_sms_report.txt"
            sms_parser.generate_report(report_path)
            print(f"Forensic report saved to: {report_path}")
        
        # Print summary to console
        stats = sms_parser.get_statistics()
        print(f"\nSMS Analysis Complete:")
        print(f"- Total Messages: {stats['total_messages']}")
        print(f"- Conversation Threads: {stats['total_threads']}")
        print(f"- Unique Contacts: {stats['total_contacts']}")
        
    except Exception as e:
        print(f"Error processing SMS data: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
