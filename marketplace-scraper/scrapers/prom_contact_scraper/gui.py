import os
import json
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
from pathlib import Path

try:
    from scrapers.prom_contact_scraper.scraper import run_category, get_db_connection
except ImportError:
    # If run standalone as python gui.py from within the dir rather than module
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    from scrapers.prom_contact_scraper.scraper import run_category, get_db_connection
    
import openpyxl

class PromContactScraperGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Prom.ua Contact Scraper")
        self.root.geometry("600x500")
        
        self.categories = self._load_categories()
        
        self.is_running = False
        self.stop_event = threading.Event()
        self.worker_thread = None
        
        self._build_ui()

    def _load_categories(self):
        base_dir = Path(__file__).resolve().parent.parent.parent
        cat_file = base_dir / "scrapers" / "mapi_scraper" / "prom_priority_categories.json"
        if not cat_file.exists():
            messagebox.showerror("Error", f"Categories file not found: {cat_file}")
            return []
        
        try:
            with open(cat_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load categories: {e}")
            return []

    def _build_ui(self):
        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        # Category Selection
        ttk.Label(frame, text="Select Category:").pack(anchor=tk.W)
        self.cat_var = tk.StringVar()
        self.combo = ttk.Combobox(frame, textvariable=self.cat_var, state="readonly", width=60)
        
        combo_values = []
        for c in self.categories:
            combo_values.append(f"{c['caption']} [{c['alias']}]")
            
        self.combo['values'] = combo_values
        if combo_values:
            self.combo.current(0)
        self.combo.pack(anchor=tk.W, pady=(0, 10))

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.start_btn = ttk.Button(btn_frame, text="Start", command=self.toggle_scraping)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.view_db_btn = ttk.Button(btn_frame, text="View Database", command=self.open_db_viewer)
        self.view_db_btn.pack(side=tk.LEFT, padx=(5, 0))

        # Progress
        self.progress_var = tk.IntVar()
        self.progress_bar = ttk.Progressbar(frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(0, 5))

        self.status_label = ttk.Label(frame, text="0 / 0 products scanned | 0 contacts found")
        self.status_label.pack(anchor=tk.W, pady=(0, 10))

        # Log Text
        self.log_area = scrolledtext.ScrolledText(frame, wrap=tk.WORD, height=15)
        self.log_area.pack(fill=tk.BOTH, expand=True)
        self.log_area.config(state=tk.DISABLED)

    def log(self, text: str):
        self.root.after(0, self._log_ui, text)

    def _log_ui(self, text: str):
        self.log_area.config(state=tk.NORMAL)
        self.log_area.insert(tk.END, text + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state=tk.DISABLED)

    def update_progress(self, offset: int, total: int, new_contacts: int):
        self.root.after(0, self._update_progress_ui, offset, total, new_contacts)

    def _update_progress_ui(self, offset: int, total: int, new_contacts: int):
        if total > 0:
            self.progress_bar["maximum"] = total
            self.progress_var.set(min(offset, total))
        self.status_label.config(text=f"{offset} / {total} products scanned | {new_contacts} contacts found")
        
        if offset > 0 and offset >= total and total > 0 and self.is_running:
            self.log(f"Done. {new_contacts} contacts saved.")
            self._set_ui_stopped()

    def toggle_scraping(self):
        if self.is_running:
            self.stop_scraping()
        else:
            self.start_scraping()

    def start_scraping(self):
        selection = self.cat_var.get()
        if not selection:
            return
            
        parts = selection.rsplit(" [", 1)
        if len(parts) != 2:
            return
        caption = parts[0]
        alias = parts[1].rstrip("]")

        self.is_running = True
        self.stop_event.clear()
        self.start_btn.config(text="Stop")
        self.combo.config(state=tk.DISABLED)
        self.log(f"Starting generic scrape for {caption}...")
        
        self.worker_thread = threading.Thread(target=self._worker, args=(alias, caption), daemon=True)
        self.worker_thread.start()

    def stop_scraping(self):
        self.log("Stopping... please wait for the current page to finish.")
        self.start_btn.config(state=tk.DISABLED, text="Stopping...")
        self.stop_event.set()

    def _set_ui_stopped(self):
        self.is_running = False
        self.start_btn.config(state=tk.NORMAL, text="Start")
        self.combo.config(state="readonly")
        
    def _worker(self, alias: str, caption: str):
        try:
            run_category(alias, caption, self.update_progress, self.stop_event)
            if self.stop_event.is_set():
                self.log("Stopped by user.")
        except Exception as e:
            self.log(f"Error: {str(e)}")
        finally:
            self.root.after(0, self._set_ui_stopped)

    def open_db_viewer(self):
        DBViewerWindow(self.root)

class DBViewerWindow:
    def __init__(self, parent):
        self.top = tk.Toplevel(parent)
        self.top.title("Database Viewer - Prom Contacts")
        self.top.geometry("1000x600")
        
        self.email_filter_var = tk.BooleanVar(value=False)
        
        self.build_ui()
        self.load_data()
        
    def build_ui(self):
        frame = ttk.Frame(self.top, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        columns = ("ID", "Name", "Slug", "Email", "Phones", "Category", "Scraped At")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="extended")
        
        for col in columns:
            self.tree.heading(col, text=col)
            # Make columns a bit thinner, except for Name and Phones
            width = 100
            if col == "Name": width = 200
            elif col == "Phones": width = 250
            elif col == "Email": width = 150
            elif col == "Category": width = 120
            elif col == "ID": width = 70
            self.tree.column(col, width=width, anchor=tk.W)
            
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.tree.grid(column=0, row=0, sticky="nsew")
        vsb.grid(column=1, row=0, sticky="ns")
        hsb.grid(column=0, row=1, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        
        btn_frame = ttk.Frame(self.top, padding=10)
        btn_frame.pack(fill=tk.X)
        
        self.export_json_btn = ttk.Button(btn_frame, text="Export JSON", command=self.export_json)
        self.export_json_btn.pack(side=tk.RIGHT, padx=5)
        
        self.export_excel_btn = ttk.Button(btn_frame, text="Export Excel", command=self.export_excel)
        self.export_excel_btn.pack(side=tk.RIGHT, padx=5)
        
        self.refresh_btn = ttk.Button(btn_frame, text="Refresh", command=self.load_data)
        self.refresh_btn.pack(side=tk.LEFT, padx=5)
        
        self.filter_chk = ttk.Checkbutton(btn_frame, text="Only with Email", variable=self.email_filter_var, command=self.load_data)
        self.filter_chk.pack(side=tk.LEFT, padx=15)
        
        # Status / Count
        self.status_var = tk.StringVar()
        ttk.Label(btn_frame, textvariable=self.status_var, font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT, padx=20)
        
    def load_data(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        try:
            conn = get_db_connection()
            # Verify table exists to prevent crash on empty DB
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='prom_contacts'")
            if not cur.fetchone():
                self.status_var.set("Table 'prom_contacts' does not exist yet.")
                conn.close()
                return
                
            query = "SELECT company_id, name, slug, email, phones, category_caption, scraped_at FROM prom_contacts"
            if self.email_filter_var.get():
                query += " WHERE email IS NOT NULL AND email != ''"
            query += " ORDER BY scraped_at DESC"
                
            cur.execute(query)
            rows = cur.fetchall()
            
            for row in rows:
                phones = row["phones"]
                # Pretty print phones JSON
                try:
                    if phones:
                        phones_list = json.loads(phones)
                        phones = ", ".join(phones_list)
                except:
                    pass
                self.tree.insert("", tk.END, values=(
                    row["company_id"], 
                    row["name"], 
                    row["slug"], 
                    row["email"], 
                    phones, 
                    row["category_caption"], 
                    row["scraped_at"]
                ))
            
            self.status_var.set(f"Loaded {len(rows)} records.")
            conn.close()
            
        except Exception as e:
            messagebox.showerror("Database error", str(e))
            self.status_var.set("Error loading data.")

    def _fetch_all_dicts(self):
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            query = "SELECT * FROM prom_contacts"
            if self.email_filter_var.get():
                query += " WHERE email IS NOT NULL AND email != ''"
            query += " ORDER BY scraped_at DESC"
            
            cur.execute(query)
            rows = cur.fetchall()
            
            results = []
            for r in rows:
                d = dict(r)
                if d.get("phones"):
                    try:
                        d["phones"] = json.loads(d["phones"])
                    except:
                        pass
                results.append(d)
                
            conn.close()
            return results
        except Exception as e:
            messagebox.showerror("Error fetching data", str(e))
            return None

    def export_json(self):
        data = self._fetch_all_dicts()
        if data is None:
            return
            
        if not data:
            messagebox.showinfo("Export", "No data to export.")
            return
            
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            title="Save JSON Export"
        )
        
        if not filepath:
            return
            
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("Success", f"Exported {len(data)} records to JSON.")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def export_excel(self):
        data = self._fetch_all_dicts()
        if data is None:
            return
            
        if not data:
            messagebox.showinfo("Export", "No data to export.")
            return
            
        filepath = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel Files", "*.xlsx"), ("All Files", "*.*")],
            title="Save Excel Export"
        )
        
        if not filepath:
            return
            
        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Prom Contacts"
            
            # Header
            headers = ["Company ID", "Name", "Slug", "Email", "Phones", "Category Alias", "Category Caption", "Scraped At"]
            ws.append(headers)
            
            for row in data:
                phones = row.get("phones", [])
                if isinstance(phones, list):
                    phones_str = ", ".join(phones)
                else:
                    phones_str = str(phones)
                    
                ws.append([
                    row.get("company_id"),
                    row.get("name"),
                    row.get("slug"),
                    row.get("email"),
                    phones_str,
                    row.get("category_alias"),
                    row.get("category_caption"),
                    row.get("scraped_at")
                ])
                
            wb.save(filepath)
            messagebox.showinfo("Success", f"Exported {len(data)} records to Excel.")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

def launch_gui():
    root = tk.Tk()
    app = PromContactScraperGUI(root)
    root.mainloop()

if __name__ == "__main__":
    launch_gui()
