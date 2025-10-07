from customtkinter import CTkFrame, CTkButton, CTkLabel, CTkEntry, CTkTextbox, CTkScrollbar
import os

class ParserFrame(CTkFrame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.initialize_ui()

    def initialize_ui(self):
        self.label = CTkLabel(self, text="Backup Parser", font=("Arial", 16))
        self.label.pack(pady=10)

        self.file_entry = CTkEntry(self, placeholder_text="Select backup file...")
        self.file_entry.pack(pady=5, padx=10, fill='x')

        self.browse_button = CTkButton(self, text="Browse", command=self.browse_file)
        self.browse_button.pack(pady=5)

        self.parse_button = CTkButton(self, text="Parse Backup", command=self.parse_backup)
        self.parse_button.pack(pady=5)

        self.result_label = CTkLabel(self, text="Parsed Results:")
        self.result_label.pack(pady=10)

        self.result_textbox = CTkTextbox(self, height=10)
        self.result_textbox.pack(pady=5, padx=10, fill='both', expand=True)

        self.scrollbar = CTkScrollbar(self, command=self.result_textbox.yview)
        self.result_textbox.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side='right', fill='y')

    def browse_file(self):
        file_path = self.master.file_dialog()  # Assuming a method to open file dialog
        if file_path:
            self.file_entry.delete(0, 'end')
            self.file_entry.insert(0, file_path)

    def parse_backup(self):
        backup_file = self.file_entry.get()
        if os.path.exists(backup_file):
            # Logic to parse the backup file and display results
            parsed_data = self.parse_backup_file(backup_file)  # Placeholder for actual parsing logic
            self.result_textbox.delete('1.0', 'end')
            self.result_textbox.insert('end', parsed_data)
        else:
            self.result_textbox.delete('1.0', 'end')
            self.result_textbox.insert('end', "File does not exist.")

    def parse_backup_file(self, file_path):
        # Placeholder for actual parsing logic
        return f"Parsed data from {file_path}"  # Replace with actual parsed data