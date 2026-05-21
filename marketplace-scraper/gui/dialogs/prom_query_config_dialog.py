import json
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

from gui.styles import COLORS, FONTS, apply_styles
from scrapers.mapi_scraper.sites.prom import _extract_default_fields

class PromQueryConfigDialog(ctk.CTkToplevel):
    def __init__(self, master, task_id=None, in_memory_config=None, on_save_callback=None):
        super().__init__(master)
        self.master = master
        self.task_id = task_id
        self.in_memory_config = in_memory_config
        self.on_save_callback = on_save_callback
        
        # Get DB from master
        self.db = getattr(self.master, "db", None)

        self.title("Prom Query Configuration")
        self.geometry("600x550")
        self.resizable(False, False)
        self.grab_set()
        
        apply_styles()
        
        # Extract and store just the product fields block for display and comparison
        self._default_fields = _extract_default_fields()
        
        self.config_data = {
            "extra_variables": {
                "company_id": None,
                "manufacturer_id": None,
                "sort": None
            },
            "custom_query_override": None
        }

        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(main_frame, text="Extra Variables", font=FONTS["title"], text_color=COLORS["accent"]).pack(anchor="w", pady=(0, 10))

        vars_frame = ctk.CTkFrame(main_frame)
        vars_frame.pack(fill="x", pady=(0, 20))

        # company_id
        row1 = ctk.CTkFrame(vars_frame, fg_color="transparent")
        row1.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(row1, text="Company ID (int):", width=140, anchor="w").pack(side="left")
        self.company_id_var = tk.StringVar()
        ctk.CTkEntry(row1, textvariable=self.company_id_var, width=200).pack(side="left")

        # manufacturer_id
        row2 = ctk.CTkFrame(vars_frame, fg_color="transparent")
        row2.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(row2, text="Manufacturer ID (int):", width=140, anchor="w").pack(side="left")
        self.manufacturer_id_var = tk.StringVar()
        ctk.CTkEntry(row2, textvariable=self.manufacturer_id_var, width=200).pack(side="left")

        # sort
        row3 = ctk.CTkFrame(vars_frame, fg_color="transparent")
        row3.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(row3, text="Sort (str, e.g. price_asc):", width=140, anchor="w").pack(side="left")
        self.sort_var = tk.StringVar()
        ctk.CTkEntry(row3, textvariable=self.sort_var, width=200).pack(side="left")

        ctk.CTkLabel(main_frame, text="Custom Query Override", font=FONTS["title"], text_color=COLORS["accent"]).pack(anchor="w", pady=(10, 5))
        ctk.CTkLabel(main_frame, text="Valid GraphQL query. Leave blank to use defaults.", text_color="#888", font=FONTS["small"]).pack(anchor="w", pady=(0, 5))

        self.override_text = ctk.CTkTextbox(main_frame, height=180, font=("Consolas", 12))
        self.override_text.pack(fill="x", pady=(0, 15))

        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(fill="x", side="bottom")

        ctk.CTkButton(btn_frame, text="Cancel", fg_color="#333", width=100, command=self.destroy).pack(side="right", padx=5)
        ctk.CTkButton(btn_frame, text="Reset", fg_color=COLORS["error"], width=100, command=self._on_reset).pack(side="right", padx=5)
        ctk.CTkButton(btn_frame, text="Save Config", fg_color=COLORS["success"], width=140, command=self._on_save).pack(side="right", padx=5)

    def _load_data(self):
        loaded_cfg = None

        if self.task_id and self.db:
            try:
                conn = self.db.get_connection()
                row = conn.execute("SELECT prom_query_config FROM tasks WHERE id = ?", (self.task_id,)).fetchone()
                if row and row["prom_query_config"]:
                    loaded_cfg = json.loads(row["prom_query_config"])
            except Exception as e:
                print(f"Error loading prom config: {e}")
        elif self.in_memory_config:
            loaded_cfg = self.in_memory_config

        if loaded_cfg:
            self.config_data.update(loaded_cfg)

        extra = self.config_data.get("extra_variables", {})
        if extra.get("company_id") is not None:
            self.company_id_var.set(str(extra["company_id"]))
        if extra.get("manufacturer_id") is not None:
            self.manufacturer_id_var.set(str(extra["manufacturer_id"]))
        if extra.get("sort"):
            self.sort_var.set(extra["sort"])

        override = self.config_data.get("custom_query_override")
        # Show the custom fields if set, otherwise show the default fields block
        display = override if override else self._default_fields
        if display:
            self.override_text.insert("0.0", display)

    def _on_reset(self):
        self.company_id_var.set("")
        self.manufacturer_id_var.set("")
        self.sort_var.set("")
        self.override_text.delete("0.0", "end")
        # Restore the default fields block
        if self._default_fields:
            self.override_text.insert("0.0", self._default_fields)

    def _on_save(self):
        custom_q = self.override_text.get("0.0", "end").strip()
        
        # Validations
        c_id = self.company_id_var.get().strip()
        m_id = self.manufacturer_id_var.get().strip()
        sort_val = self.sort_var.get().strip()

        if c_id:
            try: int(c_id)
            except: 
                messagebox.showerror("Validation logic Error", "Company ID must be an integer.")
                return
        if m_id:
            try: int(m_id)
            except: 
                messagebox.showerror("Validation logic Error", "Manufacturer ID must be an integer.")
                return

        # If fields match the default — treat as "no override" (save None)
        is_default = (custom_q == self._default_fields.strip()) if self._default_fields else not bool(custom_q)
        
        new_config = {
            "extra_variables": {
                "company_id": int(c_id) if c_id else None,
                "manufacturer_id": int(m_id) if m_id else None,
                "sort": sort_val if sort_val else None
            },
            "custom_query_override": None if is_default else (custom_q if custom_q else None)
        }

        # Validate JSON serialization
        try:
            config_json = json.dumps(new_config)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to serialize config: {e}")
            return

        if self.task_id and self.db:
            try:
                conn = self.db.get_connection()
                conn.execute("UPDATE tasks SET prom_query_config = ? WHERE id = ?", (config_json, self.task_id))
                conn.commit()
            except Exception as e:
                messagebox.showerror("Database error", f"Failed to save to tasks table: {e}")
                return

        if self.on_save_callback:
            self.on_save_callback(new_config)

        self.destroy()
