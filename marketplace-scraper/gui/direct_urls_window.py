import tkinter as tk
import customtkinter as ctk

class DirectUrlsWindow(ctk.CTkToplevel):
    def __init__(self, master, current_configs: list[dict], on_save: callable):
        super().__init__(master)
        self.master = master
        self.on_save = on_save 
        self.title("Target Link Manager")
        self.geometry("800x650")
        
        # current_configs is list of {"url": "...", "tag": "..."}
        self.configs = current_configs if current_configs else []
        self.rows = []

        self._setup_ui()
        self.grab_set()
        self.after(10, self.lift)
        self.focus_force()

    def _setup_ui(self):
        self.main_frame = ctk.CTkFrame(self, corner_radius=0)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(self.main_frame, text="URL Input Widget", font=("Segoe UI", 18, "bold")).pack(anchor="w", pady=(0, 5))
        ctk.CTkLabel(self.main_frame, text="Specify direct marketplace URLs and optional tags for product identification.", font=("Segoe UI", 12), text_color="gray").pack(anchor="w", pady=(0, 15))
        
        # Headers
        header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 5))
        ctk.CTkLabel(header_frame, text="Marketplace URL", font=("Segoe UI", 11, "bold"), width=450, anchor="w").pack(side="left", padx=(5, 0))
        ctk.CTkLabel(header_frame, text="Prefix/Tag (optional)", font=("Segoe UI", 11, "bold"), width=150, anchor="w").pack(side="left", padx=(10, 0))

        # Scrollable area for rows
        self.scroll_frame = ctk.CTkScrollableFrame(self.main_frame, fg_color="#222222", border_width=1)
        self.scroll_frame.pack(fill="both", expand=True, pady=(0, 15))

        # Action Buttons
        self.btn_row = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.btn_row.pack(fill="x")
        
        ctk.CTkButton(self.btn_row, text="+ ADD URL ROW", command=self._add_empty_row, width=140).pack(side="left")
        ctk.CTkButton(self.btn_row, text="CLEAR ALL", command=self._clear_all, width=100, fg_color="#c0392b", hover_color="#e74c3c").pack(side="left", padx=10)
        
        ctk.CTkButton(self.btn_row, text="SAVE LINKS", command=self._on_save, height=35).pack(side="right", padx=5)
        ctk.CTkButton(self.btn_row, text="CANCEL", command=self.destroy, height=35, fg_color="#555555").pack(side="right")

        # Load existing
        if not self.configs:
            self._add_empty_row()
        else:
            for cfg in self.configs:
                self._add_row(cfg.get("url", ""), cfg.get("tag", ""))

    def _add_empty_row(self):
        self._add_row("", "")

    def _add_row(self, url="", tag=""):
        row_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        row_frame.pack(fill="x", pady=2)

        url_var = tk.StringVar(value=url)
        tag_var = tk.StringVar(value=tag)

        url_entry = ctk.CTkEntry(row_frame, textvariable=url_var, placeholder_text="https://prom.ua/p/...", width=450)
        url_entry.pack(side="left", padx=(0, 10))
        
        # Paste binding
        url_entry.bind("<Control-v>", lambda e, v=url_var: self._on_paste(e, v))

        tag_entry = ctk.CTkEntry(row_frame, textvariable=tag_var, placeholder_text="e.g. Battery_A", width=150)
        tag_entry.pack(side="left")

        remove_btn = ctk.CTkButton(row_frame, text="×", width=30, height=28, fg_color="transparent", text_color="#e74c3c", font=("Arial", 16, "bold"), hover_color="#333333", command=lambda f=row_frame: self._remove_row(f))
        remove_btn.pack(side="right", padx=(5, 0))

        self.rows.append({
            "frame": row_frame,
            "url_var": url_var,
            "tag_var": tag_var
        })

    def _remove_row(self, frame):
        for i, row in enumerate(self.rows):
            if row["frame"] == frame:
                frame.destroy()
                self.rows.pop(i)
                break
        if not self.rows:
            self._add_empty_row()

    def _clear_all(self):
        for row in self.rows:
            row["frame"].destroy()
        self.rows = []
        self._add_empty_row()

    def _on_paste(self, event, var):
        # We need to wait a bit or use clipboard_get() to handle multi-line paste split
        try:
            pasted = self.clipboard_get()
            if "\n" in pasted:
                # Split and add multiple rows
                lines = [l.strip() for l in pasted.split("\n") if l.strip()]
                if not lines: return "break"
                
                # set first line to the current row
                var.set(lines[0])
                
                # add and populate remaining lines
                for line in lines[1:]:
                    self._add_row(line, "")
                
                return "break" # Handled
        except:
            pass
        return None

    def _on_save(self):
        results = []
        for row in self.rows:
            u = row["url_var"].get().strip()
            t = row["tag_var"].get().strip()
            if u.startswith("http"):
                results.append({"url": u, "tag": t if t else None})
        
        if self.on_save:
            self.on_save(results)
        self.destroy()
