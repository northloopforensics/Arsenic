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
from customtkinter import CTkFrame, CTkButton, CTkLabel, CTkEntry, CTkProgressBar
import logging

class BackupFrame(CTkFrame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.create_widgets()

    def create_widgets(self):
        self.label = CTkLabel(self, text="Backup Manager")
        self.label.pack(pady=10)

        self.backup_path_label = CTkLabel(self, text="Backup Path:")
        self.backup_path_label.pack(pady=5)

        self.backup_path_entry = CTkEntry(self)
        self.backup_path_entry.pack(pady=5)

        self.backup_button = CTkButton(self, text="Start Backup", command=self.start_backup)
        self.backup_button.pack(pady=10)

        self.progress_bar = CTkProgressBar(self)
        self.progress_bar.pack(pady=10)

        self.status_label = CTkLabel(self, text="")
        self.status_label.pack(pady=5)

    def start_backup(self):
        backup_path = self.backup_path_entry.get()
        if not backup_path:
            self.status_label.configure(text="Please enter a backup path.")
            return
        
        self.status_label.configure(text="Backing up...")
        self.progress_bar.start()

        try:
            # Call the backup logic from device_backup.py here
            # Example: device_backup.create_backup(backup_path)
            logging.info(f"Backup started at {backup_path}")
            # Simulate backup process
            self.after(2000, self.complete_backup)  # Simulate a 2-second backup process
        except Exception as e:
            logging.error(f"Backup failed: {e}")
            self.status_label.configure(text="Backup failed.")

    def complete_backup(self):
        self.progress_bar.stop()
        self.status_label.configure(text="Backup completed successfully!")