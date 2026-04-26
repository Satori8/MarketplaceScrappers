import tkinter as tk
from tkinter import ttk, messagebox
import threading
import logging
from gui.styles import COLORS, FONTS

logger = logging.getLogger(__name__)

class ApiKeyStatusWindow(tk.Toplevel):
    def __init__(self, master, gemini_client):
        super().__init__(master)
        self.gemini_client = gemini_client
        self.title("Gemini API Key Status")
        self.geometry("650x450")
        self.configure(bg=COLORS["bg"])
        self.transient(master)
        
        self._setup_ui()
        self.refresh_status()

    def _setup_ui(self):
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill="both", expand=True)

        ttk.Label(main_frame, text="Gemini API Keys Status", style="Header.TLabel").pack(pady=(0, 20))

        # Table for keys and models
        self.tree_frame = ttk.Frame(main_frame)
        self.tree_frame.pack(fill="both", expand=True)

        columns = ("key", "gemini_3_1", "gemini_3_0", "gemini_2_5", "gemini_2_0", "gemini_1_5")
        self.tree = ttk.Treeview(self.tree_frame, columns=columns, show="headings", height=10)
        
        self.tree.heading("key", text="API Key (Partial)")
        self.tree.heading("gemini_3_1", text="3.1 Flash")
        self.tree.heading("gemini_3_0", text="3.0 Flash")
        self.tree.heading("gemini_2_5", text="2.5 Flash")
        self.tree.heading("gemini_2_0", text="2.0 Flash")
        self.tree.heading("gemini_1_5", text="1.5 Flash")

        self.tree.column("key", width=160)
        self.tree.column("gemini_3_1", width=90, anchor="center")
        self.tree.column("gemini_3_0", width=90, anchor="center")
        self.tree.column("gemini_2_5", width=90, anchor="center")
        self.tree.column("gemini_2_0", width=90, anchor="center")
        self.tree.column("gemini_1_5", width=90, anchor="center")

        self.tree.pack(side="left", fill="both", expand=True)
        
        sb = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=sb.set)
        sb.pack(side="right", fill="y")

        # Tags for coloring
        self.tree.tag_configure("OK", foreground=COLORS["success"])
        self.tree.tag_configure("EXHAUSTED", foreground=COLORS["warning"])
        self.tree.tag_configure("NOT_FOUND", foreground="gray")
        self.tree.tag_configure("ERROR", foreground=COLORS["error"])

        # Control Frame
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x", pady=(20, 0))

        self.refresh_btn = ttk.Button(btn_frame, text="REFRESH / TEST ALL KEYS", command=self.refresh_status)
        self.refresh_btn.pack(side="left")

        ttk.Button(btn_frame, text="Close", command=self.destroy).pack(side="right")

        self.status_label = ttk.Label(main_frame, text="Ready")
        self.status_label.pack(fill="x", pady=(10, 0))

    def refresh_status(self):
        self.refresh_btn.config(state="disabled")
        self.status_label.config(text="Testing keys... Please wait (this can take 30s+)")
        
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)

        def run_check():
            try:
                # Use a separate instance or lock if needed, but here we just read
                report = self.gemini_client.check_keys_status()
                self.after(0, lambda: self._update_table(report))
            except Exception as e:
                logger.error("Key check error: %s", e)
                self.after(0, lambda: messagebox.showerror("Error", f"Failed to check keys: {e}"))
                self.after(0, lambda: self.refresh_btn.config(state="normal"))

        threading.Thread(target=run_check, daemon=True).start()

    def _update_table(self, report):
        for entry in report:
            key_label = f"Key #{entry['index'] + 1} ({entry['key']})"
            m31 = entry["models"].get("models/gemini-3.1-flash-preview", "N/A")
            m30 = entry["models"].get("models/gemini-3-flash-preview", "N/A")
            m25 = entry["models"].get("models/gemini-2.5-flash", "N/A")
            m20 = entry["models"].get("models/gemini-2.0-flash", "N/A")
            m15 = entry["models"].get("models/gemini-1.5-flash", "N/A")
            
            self.tree.insert("", "end", values=(key_label, m31, m30, m25, m20, m15))

        self.status_label.config(text="Check completed.")
        self.refresh_btn.config(state="normal")
