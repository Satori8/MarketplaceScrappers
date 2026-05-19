import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from typing import Optional, Dict, Any
from gui.styles import COLORS, FONTS

class TaskDialog(ctk.CTkToplevel):
    def __init__(self, master, title: str = "Task details", task_data: Optional[Dict[str, Any]] = None):
        super().__init__(master)
        self.title(title)
        self.geometry("450x450")
        self.resizable(False, False)
        
        self.result = None # Will store dict if saved, else None
        
        # Fixed task types
        self.task_types = [
            "discovery",
            "price_monitoring", 
            "competitor_audit", 
            "seller_intelligence", 
            "gap_analysis"
        ]
        
        # Default values if editing
        self.initial_data = dict(task_data) if task_data is not None else {}
        
        self._setup_ui()
        
        # Modal behavior
        self.grab_set()
        self.lift()
        self.focus_set()
        
        # Handle close window button
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        
    def _setup_ui(self):
        # Container
        main = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=25, pady=20)
        
        # Title
        ctk.CTkLabel(
            main, text="TASK PARAMETERS", font=FONTS["title"], 
            text_color=COLORS["accent"], anchor="w"
        ).pack(fill="x", pady=(0, 20))
        
        # Name field
        ctk.CTkLabel(main, text="Name *", font=FONTS["small"]).pack(anchor="w")
        self.name_entry = ctk.CTkEntry(main, font=FONTS["normal"], placeholder_text="e.g. LiFePO4 Market Discovery")
        self.name_entry.pack(fill="x", pady=(2, 15))
        if "title" in self.initial_data:
            self.name_entry.insert(0, self.initial_data["title"])
        elif "name" in self.initial_data: # flexibility
            self.name_entry.insert(0, self.initial_data["name"])
            
        # Task Type field
        ctk.CTkLabel(main, text="Task Type *", font=FONTS["small"]).pack(anchor="w")
        self.type_var = tk.StringVar(value=self.initial_data.get("task_type", "discovery"))
        self.type_combo = ctk.CTkComboBox(
            main, values=self.task_types, variable=self.type_var, font=FONTS["normal"]
        )
        # Ensure it's read-only for selection from list
        self.type_combo.configure(state="readonly")
        self.type_combo.pack(fill="x", pady=(2, 15))
        
        # Description field
        ctk.CTkLabel(main, text="Description (optional)", font=FONTS["small"]).pack(anchor="w")
        self.desc_text = ctk.CTkTextbox(main, height=100, font=FONTS["normal"])
        self.desc_text.pack(fill="x", pady=(2, 25))
        if "description" in self.initial_data and self.initial_data["description"]:
            self.desc_text.insert("1.0", self.initial_data["description"])
            
        # Buttons
        btn_row = ctk.CTkFrame(main, fg_color="transparent")
        btn_row.pack(fill="x")
        
        self.save_btn = ctk.CTkButton(
            btn_row, text="SAVE", font=FONTS["title"], height=40,
            fg_color=COLORS["success"], hover_color="#27ae60",
            command=self._on_save
        )
        self.save_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.cancel_btn = ctk.CTkButton(
            btn_row, text="CANCEL", font=FONTS["title"], height=40,
            fg_color="#333333", command=self._on_cancel
        )
        self.cancel_btn.pack(side="right", fill="x", expand=True)

    def _on_save(self):
        name = self.name_entry.get().strip()
        task_type = self.type_var.get()
        description = self.desc_text.get("1.0", "end").strip()
        
        if not name:
            messagebox.showwarning("Validation Error", "Task name is required.")
            self.name_entry.focus_set()
            return
            
        self.result = {
            "title": name,
            "task_type": task_type,
            "description": description
        }
        self.destroy()
        
    def _on_cancel(self):
        self.result = None
        self.destroy()

    def get_result(self) -> Optional[Dict[str, Any]]:
        self.master.wait_window(self)
        return self.result
