import os
import datetime
import traceback
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import textwrap

class AndroidTriagePDFGenerator:
    def __init__(self):
        """Initialize the PDF generator with custom styles"""
        self.styles = getSampleStyleSheet()
        self._create_custom_styles()
        self.story = []
        
    def _create_custom_styles(self):
        """Create simplified custom paragraph styles for the report"""
        # Title style - simplified
        self.styles.add(ParagraphStyle(
            name='ReportTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.black,
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        # Section header style - simplified
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.black,
            spaceAfter=12,
            spaceBefore=20,
            fontName='Helvetica-Bold'
        ))
        
        # Subsection header style - simplified
        self.styles.add(ParagraphStyle(
            name='SubsectionHeader',
            parent=self.styles['Heading3'],
            fontSize=14,
            textColor=colors.black,
            spaceAfter=8,
            spaceBefore=12,
            fontName='Helvetica-Bold'
        ))
        
        # Key-value style - simplified
        self.styles.add(ParagraphStyle(
            name='KeyValue',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=3,
            leftIndent=20,
            fontName='Helvetica'
        ))
        
        # Important finding style - minimal highlighting
        self.styles.add(ParagraphStyle(
            name='ImportantFinding',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=6,
            leftIndent=20,
            fontName='Helvetica-Bold'
        ))
        
        # List item style
        self.styles.add(ParagraphStyle(
            name='ListItem',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=3,
            leftIndent=30,
            bulletIndent=20,
            fontName='Helvetica'
        ))
        
        # Footer style
        self.styles.add(ParagraphStyle(
            name='Footer',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.grey,
            alignment=TA_CENTER
        ))

    def generate_report(self, case_folder, results, case_number):
        """Generate the complete PDF report"""
        try:
            print(f"PDF Generator: Starting report generation")
            print(f"PDF Generator: case_folder = {case_folder}")
            print(f"PDF Generator: case_number = {case_number}")
            print(f"PDF Generator: results keys = {list(results.keys()) if results else 'No results'}")
            
            # Store case folder for use in hyperlinks - FIX: Store it as instance variable
            self._case_folder = case_folder
            
            # Ensure case folder exists
            if not os.path.exists(case_folder):
                print(f"PDF Generator: Case folder doesn't exist, creating: {case_folder}")
                os.makedirs(case_folder, exist_ok=True)
            
            # Define output path
            pdf_filename = f"Triage_Report_{case_number}.pdf"
            pdf_path = os.path.join(case_folder, pdf_filename)
            print(f"PDF Generator: Output path = {pdf_path}")
            
            # Check write permissions
            try:
                test_file = os.path.join(case_folder, "test_write.txt")
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
                print("PDF Generator: Write permissions confirmed")
            except Exception as perm_error:
                print(f"PDF Generator: Write permission error: {perm_error}")
                return None
            
            # Create PDF document
            try:
                doc = SimpleDocTemplate(
                    pdf_path,
                    pagesize=letter,
                    rightMargin=72,
                    leftMargin=72,
                    topMargin=72,
                    bottomMargin=72
                )
                print("PDF Generator: SimpleDocTemplate created")
            except Exception as doc_error:
                print(f"PDF Generator: Error creating document: {doc_error}")
                return None
            
            # Clear story
            self.story = []
            print("PDF Generator: Building content...")
            
            # Build report content with error handling for each section
            try:
                self._add_title_page(case_number, case_folder)
                print("PDF Generator: Title page added")
            except Exception as e:
                print(f"PDF Generator: Error adding title page: {e}")
            
            try:
                self._add_executive_summary(results)
                print("PDF Generator: Executive summary added")
            except Exception as e:
                print(f"PDF Generator: Error adding executive summary: {e}")
            
            try:
                self._add_device_information(results.get('device_details', {}))
                print("PDF Generator: Device information added")
            except Exception as e:
                print(f"PDF Generator: Error adding device information: {e}")
            
            try:
                self._add_applications_analysis(results.get('apps', []))
                print("PDF Generator: Applications analysis added")
            except Exception as e:
                print(f"PDF Generator: Error adding applications analysis: {e}")
            
            try:
                self._add_content_artifacts_analysis(results.get('artifacts', {}))
                print("PDF Generator: Content artifacts analysis added")
            except Exception as e:
                print(f"PDF Generator: Error adding content artifacts analysis: {e}")
            
            try:
                self._add_external_files_analysis(results.get('external_files', {}))
                print("PDF Generator: External files analysis added")
            except Exception as e:
                print(f"PDF Generator: Error adding external files analysis: {e}")
            
            try:
                self._add_appendices(results)
                print("PDF Generator: Appendices added")
            except Exception as e:
                print(f"PDF Generator: Error adding appendices: {e}")
            
            print(f"PDF Generator: Story contains {len(self.story)} elements")
            
            # Build PDF
            try:
                print("PDF Generator: Building PDF...")
                doc.build(self.story, onFirstPage=self._add_header_footer, onLaterPages=self._add_header_footer)
                print("PDF Generator: PDF built successfully")
            except Exception as build_error:
                print(f"PDF Generator: Error building PDF: {build_error}")
                import traceback
                traceback.print_exc()
                return None
            
            # Verify the file was created
            if os.path.exists(pdf_path):
                file_size = os.path.getsize(pdf_path)
                print(f"PDF Generator: Success! File created at {pdf_path} ({file_size:,} bytes)")
                return pdf_path
            else:
                print(f"PDF Generator: Error - File was not created at {pdf_path}")
                return None
            
        except Exception as e:
            print(f"PDF Generator: Fatal error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _add_header_footer(self, canvas, doc):
        """Add header and footer to each page"""
        canvas.saveState()
        
        # Header
        canvas.setFont('Helvetica-Bold', 10)
        canvas.setFillColor(colors.darkblue)
        canvas.drawString(72, letter[1] - 50, "Device Triage Report")
        canvas.drawRightString(letter[0] - 72, letter[1] - 50, f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Header line
        canvas.setStrokeColor(colors.darkblue)
        canvas.line(72, letter[1] - 55, letter[0] - 72, letter[1] - 55)
        
        # Footer
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.grey)
        canvas.drawCentredString(letter[0]/2, 50, f"Page {doc.page}")
        canvas.restoreState()

    def _add_title_page(self, case_number, case_folder):
        """Add title page to the report"""
        # Main title
        self.story.append(Spacer(1, 2*inch))
        self.story.append(Paragraph("DEVICE TRIAGE REPORT", self.styles['ReportTitle']))
        self.story.append(Spacer(1, 0.5*inch))
        
        # Case information table
        case_data = [
            ['Case Number:', case_number],
            ['Generated:', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            ['Case Folder:', os.path.basename(case_folder)],
            ['Report Type:', 'Device Triage'],
            ['Generated By:', 'Arsenic Toolkit']
        ]
        
        case_table = Table(case_data, colWidths=[2*inch, 4*inch])
        case_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (0,-1), colors.lightgrey),
            ('TEXTCOLOR', (0,0), (0,-1), colors.darkblue),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
            ('FONTNAME', (1,0), (1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 12),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0,0), (-1,-1), [colors.white, colors.lightgrey])
        ]))
        
        self.story.append(case_table)
        self.story.append(Spacer(1, 1*inch))
        
        # Disclaimer
        disclaimer = """
        <b>CONFIDENTIALITY NOTICE:</b><br/>
        This report contains confidential and potentially sensitive information obtained through 
        digital forensic analysis. Distribution should be limited to authorized parties only. 
        """
        self.story.append(Paragraph(disclaimer, self.styles['Normal']))
        self.story.append(PageBreak())

    def _add_executive_summary(self, results):
        """Add executive summary section"""
        self.story.append(Paragraph("EXECUTIVE SUMMARY", self.styles['SectionHeader']))
        
        # Calculate key metrics
        total_apps = len(results.get('apps', []))
        artifacts = results.get('artifacts', {})
        external_files = results.get('external_files', {})
        notifications = results.get('notifications', {})
        
        sms_count = artifacts.get('sms_data', {}).get('record_count', 0) if artifacts.get('sms_data') else 0
        mms_count = artifacts.get('mms_data', {}).get('record_count', 0) if artifacts.get('mms_data') else 0
        contacts_count = artifacts.get('contacts_data', {}).get('record_count', 0) if artifacts.get('contacts_data') else 0
        call_logs_count = artifacts.get('call_logs_data', {}).get('record_count', 0) if artifacts.get('call_logs_data') else 0
        
        videos_count = external_files.get('videos_data', {}).get('record_count', 0) if external_files.get('videos_data') else 0
        images_count = external_files.get('images_data', {}).get('record_count', 0) if external_files.get('images_data') else 0
        
        notifications_count = notifications.get('notifications_data', {}).get('record_count', 0) if notifications.get('notifications_data') else 0
        
        # Fixed summary text with proper HTML formatting
        summary_text = f"""
        This report was generated in the course of a digital forensic triage examination. Digital forensic 
        triage is the initial phase of an investigation, designed to rapidly assess and prioritize digital evidence 
        by quickly identifying and categorizing information that may be relevant to the case. The triage process 
        is intended to allow investigators to efficiently identify items of investigative interest without conducting 
        a full, in-depth analysis. As such, further examination of the subject device may be necessary.
        
        <br/><br/>
        <b>Key Findings Summary:</b><br/>
        • <b>Applications:</b> {total_apps:,} applications identified across all user profiles<br/>
        • <b>SMS Messages:</b> {sms_count:,} text message records recovered<br/>
        • <b>MMS Messages:</b> {mms_count:,} multimedia message records recovered<br/>
        • <b>Contacts:</b> {contacts_count:,} contact records identified<br/>
        • <b>Call Logs:</b> {call_logs_count:,} call log entries recovered<br/>
        • <b>External Media:</b> {videos_count:,} videos and {images_count:,} images catalogued<br/>
        • <b>Notifications:</b> {notifications_count:,} notification records analyzed<br/>
        
        <br/>
        <b>Analysis Scope:</b><br/>
        The analysis included device identification, application enumeration, communication artifacts 
        recovery, multimedia file cataloging, and forensic pattern analysis. All data was extracted 
        using non-invasive logical acquisition methods.
        """
        
        self.story.append(Paragraph(summary_text, self.styles['Normal']))
        self.story.append(Spacer(1, 0.3*inch))

    def _add_device_information(self, device_details):
        """Add device information section"""
        self.story.append(Paragraph("DEVICE INFORMATION & IDENTIFIERS", self.styles['SectionHeader']))
        
        if not device_details:
            self.story.append(Paragraph("No device information available.", self.styles['Normal']))
            return
        
        # Device identifiers subsection
        self.story.append(Paragraph("Device Identifiers", self.styles['SubsectionHeader']))
        
        identifier_data = []
        identifier_keys = ["IMEI", "MEID", "Serial", "Phone Numbers", "ICCID", "IMSI"]
        
        for key in identifier_keys:
            if key in device_details and device_details[key]:
                identifier_data.append([key + ":", str(device_details[key])])
        
        if identifier_data:
            id_table = Table(identifier_data, colWidths=[1.5*inch, 4*inch])
            id_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (0,-1), colors.lightblue),
                ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
                ('FONTNAME', (1,0), (1,-1), 'Helvetica'),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('GRID', (0,0), (-1,-1), 1, colors.black),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
            ]))
            self.story.append(id_table)
        
        self.story.append(Spacer(1, 0.2*inch))
        
        # Device specifications subsection
        self.story.append(Paragraph("Device Specifications", self.styles['SubsectionHeader']))
        
        spec_data = []
        spec_keys = ["Device Name", "Model", "Manufacturer", "Brand", "Android Version", 
                    "API Level", "Build ID", "Build Date", "Bootloader", "Security Patch", 
                    "Hardware", "Chipset", "ABI", "Encryption Status"]
        
        for key in spec_keys:
            if key in device_details and device_details[key]:
                spec_data.append([key + ":", str(device_details[key])])
        
        if spec_data:
            spec_table = Table(spec_data, colWidths=[1.5*inch, 4*inch])
            spec_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (0,-1), colors.lightgreen),
                ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
                ('FONTNAME', (1,0), (1,-1), 'Helvetica'),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('GRID', (0,0), (-1,-1), 1, colors.black),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
            ]))
            self.story.append(spec_table)
        
        # User accounts subsection
        if "Users" in device_details and device_details["Users"]:
            self.story.append(Spacer(1, 0.2*inch))
            self.story.append(Paragraph("User Accounts", self.styles['SubsectionHeader']))
            
            users = device_details["Users"]
            if isinstance(users, list):
                user_data = [['User ID', 'Name', 'Type', 'Status']]
                for user in users:
                    if isinstance(user, dict):
                        user_id = user.get('id', 'Unknown')
                        user_name = user.get('name', 'Unknown')
                        user_type = user.get('type', 'Unknown')
                        user_state = user.get('state', 'Unknown')
                        user_data.append([user_id, user_name, user_type, user_state])
                
                user_table = Table(user_data, colWidths=[1*inch, 1.5*inch, 1.5*inch, 1*inch])
                user_table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
                    ('FONTSIZE', (0,0), (-1,-1), 10),
                    ('GRID', (0,0), (-1,-1), 1, colors.black),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.lightgrey])
                ]))
                self.story.append(user_table)

    def _add_applications_analysis(self, apps_data):
        """Add applications analysis section"""
        self.story.append(PageBreak())
        self.story.append(Paragraph("APPLICATIONS ANALYSIS", self.styles['SectionHeader']))
        
        if not apps_data:
            self.story.append(Paragraph("No application data available.", self.styles['Normal']))
            return
        
        # Summary
        total_apps = len(apps_data)
        self.story.append(Paragraph(f"Total Applications Identified: <b>{total_apps:,}</b>", self.styles['Normal']))
        
        # Group apps by user
        apps_by_user = {}
        for app in apps_data:
            user_id = app.get('user_id', '0')
            if user_id not in apps_by_user:
                apps_by_user[user_id] = []
            apps_by_user[user_id].append(app)
        
        # User summary table
        self.story.append(Spacer(1, 0.2*inch))
        self.story.append(Paragraph("Applications by User Profile", self.styles['SubsectionHeader']))
        
        user_summary_data = [['User ID', 'User Type', 'App Count']]
        for user_id in sorted(apps_by_user.keys()):
            user_type = "Primary User"
            if user_id == "10":
                user_type = "Work Profile"
            elif user_id == "150":
                user_type = "Secure Folder"
            user_summary_data.append([user_id, user_type, str(len(apps_by_user[user_id]))])
        
        user_summary_table = Table(user_summary_data, colWidths=[1*inch, 2*inch, 1*inch])
        user_summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
        ]))
        self.story.append(user_summary_table)
        
        # Notable applications (if any special apps detected)
        notable_apps = []
        security_keywords = ['vpn', 'proxy', 'encrypt', 'secure', 'private', 'hide', 'vault', 'meraki', 'wasted', 'keepass', 'bitwarden', 'lastpass', '1password', 'onion browser', 'orbot', 'tutanota', 'protonmail', 'k9 mail']
        communication_keywords = ['message', 'chat', 'call', 'video', 'voice', 'telegram', 'signal', 'whatsapp', 'snapchat', 'discord', 'skype', 'zoom', 'teams', 'slack', 'wechat', 'line', 'viber', 'kik', 'icq', 'hangouts', 'facebook messenger', 'instagram', 'tiktok', 'twitter', 'reddit', 'threema', 'wire', 'element', 'riot', 'matrix', 'tinder', 'bumble', 'okcupid', 'grindr', 'happn', 'plenty of fish', 'meetup', 'badoo', 'hike', 'imo', 'kakao talk', 'qq', 'weibo', 'vkontakte', 'odnoklassniki']
        file_share = ['bittorrent', 'utorrent', 'transmission', 'qbit', 'deluge', 'frostwire', 'limewire', 'kazaa', 'emule', 'soulseek', 'napster', 'aMule', 'BitComet', 'FrostWire', 'flud', 'tTorrent', 'zbigz', 'torrentio', 'webtorrent', 'peerio', 'syncplay', 'resilio sync', 'syncthing', 'seafile', 'owncloud', 'nextcloud', 'pcloud', 'dropbox', 'google drive', 'onedrive', 'mega', 'mediafire', '4shared', 'sendspace', 'zippyshare', 'filemail', 'wetransfer', 'transfernow', 'file.io', 'anonfiles', 'filebin', 'filedropper']

        for app in apps_data:
            app_name = app.get('name', '').lower()
            package_name = app.get('package', '').lower()
            
            # Check for security/privacy apps
            if any(keyword in app_name or keyword in package_name for keyword in security_keywords):
                notable_apps.append((app, "Security/Privacy"))
            # Check for communication apps
            elif any(keyword in app_name or keyword in package_name for keyword in communication_keywords):
                notable_apps.append((app, "Communication"))
            elif any(keyword in app_name or keyword in package_name for keyword in file_share):
                notable_apps.append((app, "File Sharing"))
        
        if notable_apps:
            self.story.append(Spacer(1, 0.2*inch))
            self.story.append(Paragraph("Notable Applications", self.styles['SubsectionHeader']))
            
            notable_data = [['Application', 'Package Name', 'User', 'Category']]
            for app, category in notable_apps[:20]:  # Limit to first 20
                app_name = app.get('name', 'Unknown')
                package_name = app.get('package', 'Unknown')
                user_id = app.get('user_id', '0')
                notable_data.append([app_name, package_name, user_id, category])
            
            notable_table = Table(notable_data, colWidths=[1.5*inch, 2.5*inch, 0.7*inch, 1.3*inch])
            notable_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.darkorange),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
                ('FONTSIZE', (0,0), (-1,-1), 9),
                ('GRID', (0,0), (-1,-1), 1, colors.black),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.lightyellow])
            ]))
            self.story.append(notable_table)

    def _add_content_artifacts_analysis(self, artifacts_data):
        """Add content artifacts analysis section with simplified formatting"""
        self.story.append(PageBreak())
        self.story.append(Paragraph("CONTENT ARTIFACTS ANALYSIS", self.styles['SectionHeader']))
        
        if not artifacts_data:
            self.story.append(Paragraph("No content artifacts available.", self.styles['Normal']))
            return
        
        # Simple summary table
        summary_data = [['Artifact Type', 'Records Found', 'Status']]
        
        artifact_types = [
            ('sms_data', 'SMS Messages'),
            ('mms_data', 'MMS Messages'),
            ('contacts_data', 'Contacts'),
            ('call_logs_data', 'Call Logs')
        ]
        
        # Add summary data for each artifact type
        for key, name in artifact_types:
            if key in artifacts_data and artifacts_data[key]:
                count = artifacts_data[key].get('record_count', 0)
                status = "Extracted" if count > 0 else "No Data"
                summary_data.append([name, f"{count:,}", status])
            else:
                summary_data.append([name, "0", "Not Available"])
        
        summary_table = Table(summary_data, colWidths=[2*inch, 1.5*inch, 1.5*inch])
        summary_table.setStyle(self._create_simple_table_style())
        self.story.append(summary_table)
        
        # Add detailed forensic analysis from files
        if 'analysis_files' in artifacts_data and artifacts_data['analysis_files']:
            self.story.append(Spacer(1, 0.3*inch))
            self.story.append(Paragraph("Detailed Forensic Analysis", self.styles['SubsectionHeader']))
            
            analysis_files = artifacts_data['analysis_files']
            
            # SMS Analysis
            if 'sms_data' in analysis_files:
                sms_analysis_file = analysis_files['sms_data']
                if os.path.exists(sms_analysis_file):
                    self.story.append(PageBreak())
                    self.story.append(Paragraph("SMS Messages Forensic Analysis", self.styles['SectionHeader']))
                    self._add_analysis_content(sms_analysis_file)
    
            # MMS Analysis
            if 'mms_data' in analysis_files:
                mms_analysis_file = analysis_files['mms_data']
                if os.path.exists(mms_analysis_file):
                    self.story.append(PageBreak())
                    self.story.append(Paragraph("MMS Messages Forensic Analysis", self.styles['SectionHeader']))
                    self._add_analysis_content(mms_analysis_file)
    
            # Contacts Analysis
            if 'contacts_data' in analysis_files:
                contacts_analysis_file = analysis_files['contacts_data']
                if os.path.exists(contacts_analysis_file):
                    self.story.append(PageBreak())
                    self.story.append(Paragraph("Contacts Forensic Analysis", self.styles['SectionHeader']))
                    self._add_analysis_content(contacts_analysis_file)
    
            # Call Logs Analysis
            if 'call_logs_data' in analysis_files:
                call_logs_analysis_file = analysis_files['call_logs_data']
                if os.path.exists(call_logs_analysis_file):
                    self.story.append(PageBreak())
                    self.story.append(Paragraph("Call Logs Forensic Analysis", self.styles['SectionHeader']))
                    self._add_analysis_content(call_logs_analysis_file)


    def _add_analysis_content(self, analysis_file_path):
        """Add the full content of an analysis file to the PDF"""
        try:
            with open(analysis_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Split content into sections
            lines = content.split('\n')
            current_section = []
            
            for line in lines:
                line = line.strip()
                
                # Skip separator lines (====== or ------)
                if line and (line.startswith('=') or line.startswith('-')) and len(set(line)) <= 2:
                    continue
                
                # Skip empty lines
                if not line:
                    if current_section:
                        # Process current section
                        self._process_analysis_section(current_section)
                        current_section = []
                    continue
                
                current_section.append(line)
            
            # Process any remaining section
            if current_section:
                self._process_analysis_section(current_section)
        
        except Exception as e:
            error_msg = f"Error reading analysis file: {str(e)}"
            self.story.append(Paragraph(error_msg, self.styles['Normal']))
            print(f"PDF Generator: {error_msg}")

    def _process_analysis_section(self, section_lines):
        """Process a section of analysis content and add appropriate formatting"""
        if not section_lines:
            return
        
        # Join the lines back together
        section_text = '\n'.join(section_lines)
        
        # Detect section types and apply appropriate formatting
        first_line = section_lines[0]
        
        # Major section headers (ALL CAPS)
        if first_line.isupper() and len(first_line) > 10:
            self.story.append(Spacer(1, 0.2*inch))
            self.story.append(Paragraph(first_line, self.styles['SubsectionHeader']))
            
            # Add remaining content if any
            if len(section_lines) > 1:
                remaining_content = '\n'.join(section_lines[1:])
                self._format_analysis_text(remaining_content)
        
        # Generated timestamp line
        elif 'Generated:' in first_line:
            self.story.append(Paragraph(f"<i>{first_line}</i>", self.styles['Normal']))
        
        # IMSI section with country/carrier info
        elif 'IMSI' in section_text and ('Country:' in section_text or 'Network Operator:' in section_text):
            self._format_imsi_section(section_text)
        
        # Tables or lists with statistics
        elif any(char in section_text for char in [':', '•', '-']) and ('Total' in section_text or 'Found' in section_text):
            self._format_statistics_section(section_text)
        
        # Investigative indicators (important findings)
        elif 'HIGH:' in section_text or 'MEDIUM:' in section_text or 'LOW:' in section_text:
            self._format_investigative_indicators(section_text)
        
        # Regular content
        else:
            self._format_analysis_text(section_text)

    def _format_analysis_text(self, text):
        """Format regular analysis text content"""
        if not text.strip():
            return
        
        # Split into paragraphs
        paragraphs = text.split('\n\n')
        
        for para in paragraphs:
            para = para.strip()
            if para:
                # Convert simple formatting
                formatted_para = para.replace('\n', '<br/>')
                
                # Make certain patterns bold
                formatted_para = self._apply_text_formatting(formatted_para)
                
                self.story.append(Paragraph(formatted_para, self.styles['Normal']))
                self.story.append(Spacer(1, 0.1*inch))

    def _format_imsi_section(self, text):
        """Format IMSI analysis section with simple styling"""
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # IMSI headers with country/carrier info - simple bold formatting
            if line.startswith('IMSI') and (' - ' in line):
                # Extract IMSI number and details
                parts = line.split(' - ')
                imsi_part = parts[0]
                details = ' - '.join(parts[1:]) if len(parts) > 1 else ''
                
                # Simple formatting
                formatted_line = f"<b>{imsi_part}</b>"
                if details:
                    formatted_line += f" ({details})"
                
                self.story.append(Paragraph(formatted_line, self.styles['ImportantFinding']))
            
            # Indented details - simple formatting
            elif line.startswith('  '):
                detail = line[2:].strip()
                if ':' in detail:
                    key, value = detail.split(':', 1)
                    formatted_detail = f"<b>{key.strip()}:</b> {value.strip()}"
                else:
                    formatted_detail = detail
                
                self.story.append(Paragraph(formatted_detail, self.styles['KeyValue']))
            
            # Regular IMSI content
            else:
                formatted_line = self._apply_simple_text_formatting(line)
                self.story.append(Paragraph(formatted_line, self.styles['Normal']))

    def _format_statistics_section(self, text):
        """Format sections with statistics using simple formatting"""
        lines = text.split('\n')
        
        # Create simple list instead of complex tables
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if line looks like a statistic
            if ':' in line and any(char.isdigit() for char in line):
                # Simple key-value formatting
                parts = line.split(':', 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    formatted_line = f"<b>{key}:</b> {value}"
                    self.story.append(Paragraph(formatted_line, self.styles['KeyValue']))
                else:
                    self.story.append(Paragraph(line, self.styles['Normal']))
            else:
                formatted_line = self._apply_simple_text_formatting(line)
                self.story.append(Paragraph(formatted_line, self.styles['Normal']))
    
        self.story.append(Spacer(1, 0.1*inch))

    def _format_investigative_indicators(self, text):
        """Format investigative indicators with color coding"""
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Color code by severity
            if '🔴 HIGH:' in line or 'HIGH:' in line:
                formatted_line = f"<b><font color='red'>⚠ HIGH PRIORITY:</font></b> {line.replace('🔴 HIGH:', '').replace('HIGH:', '').strip()}"
                self.story.append(Paragraph(formatted_line, self.styles['ImportantFinding']))
            
            elif '🟡 MEDIUM:' in line or 'MEDIUM:' in line:
                formatted_line = f"<b><font color='orange'>⚠ MEDIUM:</font></b> {line.replace('🟡 MEDIUM:', '').replace('MEDIUM:', '').strip()}"
                self.story.append(Paragraph(formatted_line, self.styles['KeyValue']))
            
            elif '🟢 LOW:' in line or 'LOW:' in line:
                formatted_line = f"<b><font color='green'>ℹ LOW:</font></b> {line.replace('🟢 LOW:', '').replace('LOW:', '').strip()}"
                self.story.append(Paragraph(formatted_line, self.styles['Normal']))
            
            else:
                formatted_line = self._apply_text_formatting(line)
                self.story.append(Paragraph(formatted_line, self.styles['Normal']))
            
            self.story.append(Spacer(1, 0.05*inch))

    def _apply_text_formatting(self, text):
        """Apply basic text formatting (bold, italics, etc.)"""
        # Make numbers in statistics bold
        import re
        
        # Bold numbers with commas (statistics)
        text = re.sub(r'\b(\d{1,3}(?:,\d{3})*)\b', r'<b>\1</b>', text)
        
        # Bold key terms
        key_terms = ['Total', 'Found', 'Detected', 'Analyzed', 'Extracted', 'Country', 'Operator', 'Network']
        for term in key_terms:
            text = text.replace(f'{term}:', f'<b>{term}:</b>')
        
        # Italicize phone numbers and emails
        text = re.sub(r'\b\+?[\d\-\(\)\s]{10,}\b', r'<i>\g<0></i>', text)
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', r'<i>\g<0></i>', text)
        
        return text

    def _apply_simple_text_formatting(self, text):
        """Apply minimal text formatting"""
        import re
        
        # Bold numbers in statistics (keep this minimal)
        text = re.sub(r'\b(\d{1,3}(?:,\d{3})*)\b', r'<b>\1</b>', text)
        
        # Bold only essential key terms
        key_terms = ['Total', 'Found', 'Country', 'Operator']
        for term in key_terms:
            text = text.replace(f'{term}:', f'<b>{term}:</b>')
        
        return text

    def _add_external_files_analysis(self, external_files_data):
        """Add external files analysis section with simple formatting"""
        self.story.append(PageBreak())
        self.story.append(Paragraph("EXTERNAL FILES ANALYSIS", self.styles['SectionHeader']))
        
        if not external_files_data:
            self.story.append(Paragraph("No external files data available.", self.styles['Normal']))
            return
        
        # Simple summary table
        summary_data = [['File Type', 'Count', 'Status']]
        
        file_types = [
            ('videos_data', 'Video Files'),
            ('images_data', 'Image Files'),
            ('downloads_data', 'Downloads'),
            ('my_downloads_data', 'My Downloads')
        ]
        
        total_files = 0
        for key, name in file_types:
            if key in external_files_data and external_files_data[key]:
                count = external_files_data[key].get('record_count', 0)
                total_files += count
                status = "Catalogued" if count > 0 else "No Files"
                summary_data.append([name, f"{count:,}", status])
            else:
                summary_data.append([name, "0", "Not Available"])
        
        # Add total row
        summary_data.append(['TOTAL FILES', f"{total_files:,}", ""])
        
        summary_table = Table(summary_data, colWidths=[2*inch, 1.5*inch, 1.5*inch])
        
        # Apply simple table style
        table_style = self._create_simple_table_style()
        # Add bold formatting for total row
        table_style.add('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold')
        summary_table.setStyle(table_style)
        
        self.story.append(summary_table)

    def _add_appendices(self, results):
        """Add appendices section with hyperlinked file references"""
        self.story.append(PageBreak())
        self.story.append(Paragraph("APPENDICES", self.styles['SectionHeader']))
        
        # Appendix A: Technical Details
        self.story.append(Paragraph("Appendix A: Technical Methodology", self.styles['SubsectionHeader']))
        
        methodology = """
        <b>Data Acquisition Method:</b> Logical acquisition using Android Debug Bridge (ADB)<br/>
        <b>Tools Used:</b> Arsenic Toolkit, Android Debug Bridge<br/>
        <b>Analysis Scope:</b> Non-invasive logical extraction of user-accessible data<br/>
        <b>Limitations:</b> Analysis limited to data accessible through standard Android APIs and ADB commands. 
        Root access was not obtained, and encrypted databases requiring special permissions may not be fully accessible.<br/>
        """
        self.story.append(Paragraph(methodology, self.styles['Normal']))
        
        # Appendix B: File Locations with Hyperlinks
        self.story.append(Spacer(1, 0.2*inch))
        self.story.append(Paragraph("Appendix B: Generated Files and Locations", self.styles['SubsectionHeader']))
        
        # FIX: Use the stored case folder
        case_folder = getattr(self, '_case_folder', '')
        print(f"PDF Generator: Using case folder for links: {case_folder}")
        
        # Build file links with actual file paths
        file_links = self._build_file_links(results, case_folder)
        
        self.story.append(Paragraph(file_links, self.styles['Normal']))

    def _build_file_links(self, results, case_folder):
        """Build HTML with hyperlinks to actual files"""
        
        print(f"PDF Generator: Building file links for case folder: {case_folder}")
        
        # Start with description
        file_info = """
        The following files were generated during the triage process. Click on any file name to open it:<br/><br/>
        """
        
        # Check if case folder exists
        if not case_folder or not os.path.exists(case_folder):
            file_info += "<b>Error:</b> Case folder path not available for file links.<br/>"
            return file_info
        
        # Raw Data Files section - IN ARTIFACTS FOLDER
        file_info += "<b>Raw Data Files (Artifacts folder):</b><br/>"
        
        # Define file paths to check in Artifacts folder
        file_checks = [
            ("SMS Messages", os.path.join(case_folder, "Artifacts", "sms_messages.txt"), os.path.join(case_folder, "Artifacts", "sms_messages.csv")),
            ("MMS Messages", os.path.join(case_folder, "Artifacts", "mms_messages.txt"), os.path.join(case_folder, "Artifacts", "mms_messages.csv")),
            ("Contacts", os.path.join(case_folder, "Artifacts", "contacts_data.txt"), os.path.join(case_folder, "Artifacts", "contacts_data.csv")),
            ("Call Logs", os.path.join(case_folder, "Artifacts", "call_logs.txt"), os.path.join(case_folder, "Artifacts", "call_logs.csv"))
        ]
        
        for name, txt_path, csv_path in file_checks:
            if os.path.exists(txt_path):
                print(f"PDF Generator: Found {name} files")
                file_info += f'• {name}: <a href="file://{txt_path}" color="blue">{os.path.basename(txt_path)}</a>'
                if os.path.exists(csv_path):
                    file_info += f', <a href="file://{csv_path}" color="blue">{os.path.basename(csv_path)}</a>'
                file_info += '<br/>'
            else:
                print(f"PDF Generator: {name} files not found at {txt_path}")
        
        # Notifications files - NOW IN ARTIFACTS/NOTIFICATIONS FOLDER
        notifications_raw_path = os.path.join(case_folder, "Artifacts", "Notifications", "notifications_raw.txt")
        notifications_csv_path = os.path.join(case_folder, "Artifacts", "Notifications", "notifications.csv")
        if os.path.exists(notifications_raw_path):
            print(f"PDF Generator: Found notifications files")
            file_info += f'• Notifications: <a href="file://{notifications_raw_path}" color="blue">notifications_raw.txt</a>'
            if os.path.exists(notifications_csv_path):
                file_info += f', <a href="file://{notifications_csv_path}" color="blue">notifications.csv</a>'
            file_info += '<br/>'
    
        # External Files folder - NOW IN ARTIFACTS/EXTERNAL_FILES FOLDER
        external_files_folder = os.path.join(case_folder, "Artifacts", "External_Files")
        if os.path.exists(external_files_folder):
            print(f"PDF Generator: Found External_Files folder")
            file_info += f'• External Files: <a href="file://{external_files_folder}" color="blue">External_Files/ folder</a><br/>'
            
            # Add specific external file types if they exist
            external_file_checks = [
                ("external_videos.csv", os.path.join(external_files_folder, "external_videos.csv")),
                ("external_images.csv", os.path.join(external_files_folder, "external_images.csv")),
                ("downloads.csv", os.path.join(external_files_folder, "downloads.csv"))
            ]
            
            for filename, filepath in external_file_checks:
                if os.path.exists(filepath):
                    file_info += f'  - <a href="file://{filepath}" color="blue">{filename}</a><br/>'
    
        file_info += '<br/>'
        
        # Analysis Files section - IN REPORTS FOLDER
        file_info += "<b>Forensic Analysis Files (Reports folder):</b><br/>"
        
        analysis_file_checks = [
            ("SMS Forensic Analysis", os.path.join(case_folder, "Reports", "sms_forensic_analysis.txt")),
            ("MMS Analysis", os.path.join(case_folder, "Reports", "mms_forensic_analysis.txt")),
            ("Contacts Analysis", os.path.join(case_folder, "Reports", "contacts_forensic_analysis.txt")),
            ("Call Logs Analysis", os.path.join(case_folder, "Reports", "call_logs_forensic_analysis.txt"))
        ]
        
        for name, filepath in analysis_file_checks:
            if os.path.exists(filepath):
                print(f"PDF Generator: Found {name}")
                file_info += f'• {name}: <a href="file://{filepath}" color="blue">{os.path.basename(filepath)}</a><br/>'
    
        # Add case folder link
        file_info += f'<br/><b>Case Folder:</b> <a href="file://{case_folder}" color="blue">Open Case Folder</a><br/>'
        
        print(f"PDF Generator: Generated file links HTML (length: {len(file_info)})")
        
        return file_info
    
    # Add this method to AndroidTriagePDFGenerator class in pdf_report_gen.py:

    def _extract_full_forensic_analysis(self, analysis_file, analysis_type):
        """Extract basic summary from forensic analysis files"""
        try:
            if not os.path.exists(analysis_file):
                return [f"Analysis file not found: {analysis_file}"]
            
            with open(analysis_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract just the executive summary section
            if "EXECUTIVE SUMMARY" in content:
                start = content.find("EXECUTIVE SUMMARY")
                # Find the next major section
                next_section = content.find("\n\n", start + 100)  # Look for double newline after some content
                if next_section > start:
                    summary = content[start:next_section]
                    # Clean up and format
                    lines = summary.split('\n')
                    formatted_lines = []
                    for line in lines[1:]:  # Skip the header
                        line = line.strip()
                        if line and not line.startswith('-'):
                            formatted_lines.append(line)
                    
                    return [f"<b>Summary:</b><br/>{'<br/>'.join(formatted_lines[:5])}"]  # First 5 lines only
            
            return [f"Summary available in: {os.path.basename(analysis_file)}"]
            
        except Exception as e:
            return [f"Error reading analysis file: {str(e)}"]
    
    def _create_simple_table_style(self):
        """Create a simple table style with minimal formatting"""
        return TableStyle([
            # Header styling - minimal
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 11),
            
            # Data styling
            ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,1), (-1,-1), 10),
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            
            # Padding
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ])