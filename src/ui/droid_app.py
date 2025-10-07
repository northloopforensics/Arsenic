import os
import tkinter as tk
from tkinter import filedialog, messagebox
import tkinter.ttk as ttk  # For Treeview widgets
import customtkinter as ctk
import threading
import logging
from PIL import Image, ImageTk
from tzlocal import get_localzone
import sys

# Import the DroidTriageFrame and DroidBackupFrame
from src.ui.droid_triage_frame import DroidTriageFrame
from src.ui.droid_backup_frame import DroidBackupFrame

# Configure CustomTkinter appearance
ctk.set_appearance_mode("System")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.timezone_preference = f"System Time ({get_localzone()})"
        self.return_to_main_callback = None
        # Configure window
        self.title("Arsenic Triage Tool - North Loop Consulting © 2025")
        self.geometry("1000x750")  # More compact window size
        self.minsize(900, 600)
        
        # Configure logging
        logging.basicConfig(level=logging.INFO, 
                           format='%(asctime)s - %(levelname)s - %(message)s')
        
        # Create the UI
        self.create_widgets()
    
    def create_widgets(self):
        # Create header frame first - always create it regardless of icon loading
        header_frame = ctk.CTkFrame(self)
        header_frame.pack(fill="x", padx=10, pady=(5, 0))
        
        # For now, skip the icon to avoid PIL image conflicts
        # Create logo with emoji
        logo_label = ctk.CTkLabel(header_frame, text="🤖", font=ctk.CTkFont(size=32))
        logo_label.pack(side="left", padx=10, pady=5)
    
        # Add title next to logo (always create this)
        title_label = ctk.CTkLabel(
            header_frame, 
            text="Arsenic Android Triage Tool", 
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_label.pack(side="left", padx=10, pady=5)
        
        # Add back button to right side (always create this)
        self.back_button = ctk.CTkButton(
            header_frame,
            text="← Back to Main",
            font=ctk.CTkFont(size=14),
            width=120,
            command=self.go_back_to_main
        )
        self.back_button.pack(side="right", padx=10, pady=5)
        
        # Create tabview
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        
        # Create tabs
        self.tab_triage = self.tabview.add("Triage")
        self.tab_backup = self.tabview.add("Backup")
        self.tab_parse = self.tabview.add("Analysis")
        
        # Add the DroidTriageFrame to the triage tab
        self.triage_frame = DroidTriageFrame(self.tab_triage)
        self.triage_frame.pack(fill="both", expand=True)
        
        # Add the DroidBackupFrame to the backup tab
        self.backup_frame = DroidBackupFrame(self.tab_backup)
        self.backup_frame.pack(fill="both", expand=True)
        
        # Setup other tabs
        self.setup_parse_tab()
    
    # def go_back_to_main(self):
    #     """Go back to the main platform selection window"""
    #     try:
    #         # Clean up current resources
    #         if hasattr(self, 'triage_frame') and hasattr(self.triage_frame, 'stop_device_check'):
    #             self.triage_frame.stop_device_check()
            
    #         # Hide this window
    #         self.withdraw()
    #         if self.return_to_main_callback:
    #             self.return_to_main_callback()
    #         else:
    #             current_dir = os.path.dirname(os.path.abspath(__file__))
    #             project_root = os.path.dirname(os.path.dirname(current_dir))
    #             if project_root not in sys.path:
    #                 sys.path.insert(0, project_root)
    #             # Import and show the main app
    #             from main import PlatformSelector as MainApp
    #             main_app = MainApp()
    #             main_app.mainloop()
                
    #             # Close this window completely
    #             self.quit()
    #             self.destroy()
            
    #     except Exception as e:
    #         print(f"Error going back to main: {e}")
    #         self.deiconify()
    #         messagebox.showerror("Error", f"Could not return to main window: {str(e)}")
    def deiconify(self):
        """Override deiconify to refresh device status when app becomes visible"""
        super().deiconify()
        
        # When the app becomes visible again, try to refresh the device status
        try:
            if hasattr(self, 'triage_frame') and hasattr(self.triage_frame, 'refresh_device_status'):
                # Schedule a device status refresh after the window is fully visible
                self.after(500, self.triage_frame.refresh_device_status)
            if hasattr(self, 'backup_frame') and hasattr(self.backup_frame, 'check_device_status'):
                # Also refresh backup frame device status
                self.after(500, self.backup_frame.check_device_status)
        except Exception as e:
            print(f"Error refreshing device status on deiconify: {e}")
    
    def setup_parse_tab(self):
        # Create a frame for extraction
        extract_frame = ctk.CTkFrame(self.tab_parse)
        extract_frame.pack(fill="both", expand=True, padx=20, pady=20)

        extract_label = ctk.CTkLabel(
            extract_frame,
            text="Extract Existing Android Backup (.ab):",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        extract_label.pack(pady=10)

        file_frame = ctk.CTkFrame(extract_frame)
        file_frame.pack(fill="x", padx=20, pady=20)

        file_label = ctk.CTkLabel(
            file_frame,
            text="Select Android Backup File:",
            font=ctk.CTkFont(size=14)
        )
        file_label.pack(pady=5, anchor="w")

        self.backup_file_entry = ctk.CTkEntry(file_frame, width=400)
        self.backup_file_entry.pack(side="left", padx=5, fill="x", expand=True)

        browse_button = ctk.CTkButton(
            file_frame,
            text="Browse",
            width=80,
            command=self.browse_backup_file
        )
        browse_button.pack(side="right", padx=5)

        extract_backup_button = ctk.CTkButton(
            extract_frame,
            text="📂 Extract Backup",
            command=self.extract_backup_file
        )
        extract_backup_button.pack(padx=10, pady=5)

    def browse_backup_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Android Backup File",
            filetypes=[("Android Backup", "*.ab"), ("All Files", "*.*")]
        )
        if file_path:
            self.backup_file_entry.delete(0, tk.END)
            self.backup_file_entry.insert(0, file_path)

    def extract_backup_file(self):
        backup_path = self.backup_file_entry.get().strip()
        if not backup_path:
            messagebox.showerror("Error", "Please select a backup file!")
            return
        if not os.path.exists(backup_path):
            messagebox.showerror("Error", "Backup file not found!")
            return
        def extract():
            try:
                from src.Droid_backup.android_backup_collector import ArsenicTriageCollector
                collector = ArsenicTriageCollector()
                success = collector.extract_adb_backup(backup_path)
                if success:
                    success_msg = f"Backup extracted successfully!\nExtracted to: {collector.output_dir}"
                    messagebox.showinfo("Success", success_msg)
                else:
                    messagebox.showerror("Error", "Backup extraction failed!")
            except Exception as e:
                error_msg = f"Extraction failed: {str(e)}"
                messagebox.showerror("Error", error_msg)
        threading.Thread(target=extract, daemon=True).start()
    
    def show_device_selection(self):
        """Method that can be called from DroidTriageFrame to go back to device selection"""
        # This would be implemented if you want the back button to work
        pass
    
    def update_status(self, message):
        """Update status message (placeholder)"""
        print(f"Status: {message}")
    
    def browse_folder(self):
        """Browse for a folder (placeholder)"""
        folder_path = filedialog.askdirectory()
        if folder_path:
            print(f"Selected folder: {folder_path}")
    
    def destroy(self):
        """Clean up resources before closing"""
        if hasattr(self, 'triage_frame') and hasattr(self.triage_frame, 'stop_device_check'):
            self.triage_frame.stop_device_check()
        if hasattr(self, 'backup_frame'):
            self.backup_frame.destroy()
        super().destroy()

    
    def on_closing(self):
        """Handle window closing event"""
        try:
            # Stop device monitoring
            if hasattr(self, 'triage_frame') and hasattr(self.triage_frame, 'stop_device_check'):
                self.triage_frame.stop_device_check()
            
            # Clean up backup frame
            if hasattr(self, 'backup_frame'):
                self.backup_frame.destroy()
            
            # Hide this window
            self.withdraw()
            
            # Call the return callback if it exists
            if hasattr(self, 'return_to_main_callback') and self.return_to_main_callback:
                self.return_to_main_callback()
            else:
                # If no callback, just destroy the window
                self.destroy()
                
        except Exception as e:
            print(f"Error during window closing: {e}")
            # Force close if there's an error
            try:
                self.destroy()
            except:
                pass

    def go_back_to_main(self):
        """Handle back button press"""
        self.on_closing()