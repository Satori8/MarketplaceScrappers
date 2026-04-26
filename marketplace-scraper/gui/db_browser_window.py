import tkinter as tk
import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog
import threading
import logging
import json
import os
from datetime import datetime, timezone
from gui.styles import COLORS, FONTS
from core.models import RawProduct

logger = logging.getLogger(__name__)

class DbBrowserWindow(ctk.CTkToplevel):
    def __init__(self, master, db, repo, scheduler=None):
        super().__init__(master)
        self.db = db
        self.repo = repo
        self.scheduler = scheduler
        self.title("Marketplace Database Browser")
        self.geometry("1200x850")
        
        self.current_results = []
        self.column_filters = {} # column -> entry
        self._setup_ui()
        
        self.after(200, self._on_search)
        self.grab_set()
        self.after(10, self.lift)
        self.focus_force()

    def _setup_ui(self):
        # --- Top Filter Bar ---
        self.top_bar = ctk.CTkFrame(self, height=60, corner_radius=0)
        self.top_bar.pack(fill="x", side="top")

        ctk.CTkLabel(self.top_bar, text="Search:").pack(side="left", padx=(20, 5))
        self.search_ent = ctk.CTkEntry(self.top_bar, width=250, placeholder_text="Keyword / ID...")
        self.search_ent.pack(side="left", padx=(0, 15))
        self.search_ent.bind("<Return>", lambda e: self._on_search())

        ctk.CTkLabel(self.top_bar, text="MP:").pack(side="left", padx=(0, 5))
        self.mp_filter = ctk.CTkComboBox(self.top_bar, values=["All", "hotline", "rozetka", "prom", "allo", "epicentrk"], width=120)
        self.mp_filter.set("All")
        self.mp_filter.pack(side="left", padx=(0, 15))

        ctk.CTkLabel(self.top_bar, text="Rel:").pack(side="left", padx=(0, 5))
        self.rel_filter = ctk.CTkComboBox(self.top_bar, values=["All", "Relevant", "Mismatch"], width=120)
        self.rel_filter.set("All")
        self.rel_filter.pack(side="left", padx=(0, 15))

        ctk.CTkButton(self.top_bar, text="SEARCH", width=100, command=self._on_search).pack(side="left", padx=(0, 20))

        # --- Sidebar / Toolbar ---
        self.toolbar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.toolbar.pack(side="right", fill="y")
        
        ctk.CTkLabel(self.toolbar, text="ACTIONS", font=FONTS["title"], text_color=COLORS["accent"]).pack(pady=20)
        
        ctk.CTkButton(self.toolbar, text="Norm Remaining", command=self._on_normalize_remaining).pack(padx=10, pady=5, fill="x")
        ctk.CTkButton(self.toolbar, text="Deduplicate", command=self._on_dedupe).pack(padx=10, pady=5, fill="x")
        ctk.CTkButton(self.toolbar, text="Sync Selected", command=self._on_normalize_selected).pack(padx=10, pady=20, fill="x")
        
        ctk.CTkButton(self.toolbar, text="EXPORT EXCEL", fg_color=COLORS["success"], hover_color="#27ae60", command=self._on_export).pack(padx=10, pady=5, side="bottom")
        ctk.CTkButton(self.toolbar, text="CLOSE", fg_color=COLORS["sidebar"], command=self.destroy).pack(padx=10, pady=20, side="bottom")

        # --- Main View Container ---
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        # --- Column Filters Row ---
        self.filter_row = ctk.CTkFrame(self.main_container, height=40)
        self.filter_row.pack(fill="x", pady=(0, 10))
        
        cols_for_filters = ["MP", "Brand", "Model", "V", "Ah"]
        widths = [80, 100, 120, 50, 50]
        
        for col, w in zip(cols_for_filters, widths):
            f = ctk.CTkFrame(self.filter_row, fg_color="transparent")
            f.pack(side="left", padx=5)
            # ctk.CTkLabel(f, text=col, font=FONTS["small"]).pack(anchor="w")
            e = ctk.CTkEntry(f, width=w, placeholder_text=col, height=28)
            e.pack(side="left")
            e.bind("<KeyRelease>", lambda e: self._apply_column_filters())
            self.column_filters[col] = e

        # --- Treeview ---
        self.tree_frame = ctk.CTkFrame(self.main_container)
        self.main_container.pack(fill="both", expand=True) # Redundant but safe
        self.tree_frame.pack(fill="both", expand=True)

        cols = ("id", "marketplace", "brand", "model", "v", "ah", "price", "title")
        self.tree = ttk.Treeview(self.tree_frame, columns=cols, show="headings")
        
        headings = ["ID", "MP", "Brand", "Model", "V", "Ah", "Price", "Full Title"]
        for c, h in zip(cols, headings):
            self.tree.heading(c, text=h)

        self.tree.column("id", width=40, anchor="center")
        self.tree.column("marketplace", width=80)
        self.tree.column("brand", width=100)
        self.tree.column("model", width=120)
        self.tree.column("v", width=50, anchor="center")
        self.tree.column("ah", width=50, anchor="center")
        self.tree.column("price", width=80, anchor="e")
        self.tree.column("title", width=450)

        self.tree.pack(side="left", fill="both", expand=True)
        
        sb = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=sb.set)
        sb.pack(side="right", fill="y")

        self.tree.tag_configure("mismatch", background="#2a2a2a", foreground="#777777")

        # stats
        self.stats_lbl = ctk.CTkLabel(self.main_container, text="Found: 0 products", font=FONTS["small"])
        self.stats_lbl.pack(anchor="w", pady=5)

    def _on_search(self):
        if not self.winfo_exists(): return
        
        query = self.search_ent.get()
        mp = self.mp_filter.get()
        rel = self.rel_filter.get()
        
        filters = {}
        if mp != "All": filters["marketplace"] = mp
        if rel != "All": filters["is_relevant"] = (rel == "Relevant")

        self.current_results = self.repo.search_products(query, filters)
        self._refresh_tree(self.current_results)

    def _apply_column_filters(self, *args):
        filtered = []
        for row in self.current_results:
            match = True
            for col, entry in self.column_filters.items():
                val = entry.get().lower()
                if not val: continue
                
                cell = ""
                if col == "MP": cell = str(row.get("marketplace", ""))
                elif col == "Brand": cell = str(row.get("norm_brand", ""))
                elif col == "Model": cell = str(row.get("norm_model", ""))
                elif col == "V": cell = str(row.get("norm_voltage", ""))
                elif col == "Ah": cell = str(row.get("norm_capacity", ""))
                
                if val not in cell.lower():
                    match = False
                    break
            if match:
                filtered.append(row)
        self._refresh_tree(filtered)

    def _refresh_tree(self, data):
        self.tree.delete(*self.tree.get_children())
        for row in data:
            tag = "" if row.get("is_relevant") else "mismatch"
            self.tree.insert("", "end", values=(
                row["id"], row["marketplace"], row["norm_brand"] or "", 
                row["norm_model"] or "", row["norm_voltage"] or "", 
                row["norm_capacity"] or "", row["price"], row["title"]
            ), tags=(tag,))
        self.stats_lbl.configure(text=f"Displaying {len(data)} results")

    def _on_normalize_remaining(self):
        if not self.scheduler: return
        remaining = [r for r in self.current_results if r["norm_brand"] is None]
        if not remaining:
            messagebox.showinfo("Done", "No products without normalization found in current view.")
            return
        
        # Convert to RawProduct objects
        raws = []
        for r in remaining:
            raws.append(RawProduct(
                title=r["title"], price=r["price"], currency=r["currency"],
                url=r["url"], marketplace=r["marketplace"],
                brand=r["brand"], model=r["model"], raw_specs=json.loads(r["raw_specs"]),
                description=r["description"], image_url=r["image_url"],
                availability=r["availability"], rating=r["rating"],
                reviews_count=r["reviews_count"], category_path=r["category_path"]
            ))
        
        self.stats_lbl.configure(text=f"AI Normalizing {len(raws)} products...", text_color=COLORS["accent"])
        
        def work():
            import asyncio
            asyncio.run(self.scheduler.normalizer.normalize_batch(
                raws, query="Manual Sync", 
                on_chunk_callback=lambda batch: self.scheduler.repo.save_normalized_batch(batch)
            ))
            self.after(0, self._on_search)
            self.after(0, lambda: messagebox.showinfo("Success", "Normalization complete."))

        threading.Thread(target=work, daemon=True).start()

    def _on_normalize_selected(self):
        items = self.tree.selection()
        if not items:
            messagebox.showwarning("Warning", "Select products to normalize first.")
            return
        
        ids = [self.tree.item(i)["values"][0] for i in items]
        selected_rows = [r for r in self.current_results if r["id"] in ids]
        
        raws = []
        for r in selected_rows:
            raws.append(RawProduct(
                title=r["title"], price=r["price"], currency=r["currency"],
                url=r["url"], marketplace=r["marketplace"],
                brand=r["brand"], model=r["model"], raw_specs=json.loads(r["raw_specs"]),
                description=r["description"], image_url=r["image_url"],
                availability=r["availability"], rating=r["rating"],
                reviews_count=r["reviews_count"], category_path=r["category_path"]
            ))
            
        def work():
            import asyncio
            asyncio.run(self.scheduler.normalizer.normalize_batch(
                raws, query="Manual Selection Sync", 
                on_chunk_callback=lambda batch: self.scheduler.repo.save_normalized_batch(batch)
            ))
            self.after(0, self._on_search)
            
        threading.Thread(target=work, daemon=True).start()

    def _on_dedupe(self):
        count = self.repo.remove_duplicates()
        messagebox.showinfo("Deduplication", f"Removed {count} exact duplicate URLs from database.")
        self._on_search()

    def _on_export(self):
        if not self.current_results: return
        file_path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")])
        if not file_path: return

        from exporters.excel_exporter import ExcelExporter
        
        def work():
            # fetch raw specs if needed or map directly
            # B12 fix: Convert dict results back to RawProduct for exporter compatibility
            export_list = []
            for r in self.current_results:
                raw = RawProduct(
                    title=r["title"], price=r["price"], currency=r["currency"],
                    url=r["url"], marketplace=r["marketplace"],
                    brand=r["brand"], model=r["model"], raw_specs=json.loads(r["raw_specs"]),
                    description=r["description"], image_url=r["image_url"],
                    availability=r["availability"], rating=r["rating"],
                    reviews_count=r["reviews_count"], category_path=r["category_path"]
                    # scraped_at is usually missing in rows but not critical for export
                )
                export_list.append(raw)
            
            exporter = ExcelExporter(file_path)
            exporter.export(export_list)
            self.after(0, lambda: messagebox.showinfo("Success", f"Exported {len(export_list)} items to {file_path}"))
            
        threading.Thread(target=work, daemon=True).start()
