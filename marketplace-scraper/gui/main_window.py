import json
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import customtkinter as ctk
import logging
import threading
import queue
import uuid
import concurrent.futures
from datetime import datetime, timezone
from typing import Dict, List, Optional

from db.database import Database
from gui.styles import COLORS, FONTS, apply_styles, AutohideScrollbar
from core.scheduler import TaskScheduler
from core.models import ScrapeTask
from gui.direct_urls_window import DirectUrlsWindow

logger = logging.getLogger(__name__)


class MainWindow(ctk.CTkFrame):
    def __init__(self, master, db: Database):
        super().__init__(master)
        self.master = master
        self.db = db
        self.db = db
        self.scheduler = TaskScheduler(self.db)
        
        # UI State
        self.active_client_id = None
        self.clients_dict = {}
        self.marketplaces_vars = {}
        self.marketplaces_methods = {} # mp -> StringVar (Auto/Browser/Requests)
        self.marketplaces_status_labels = {}
        self.is_running = False
        self.msg_queue = queue.Queue()
        self.active_mps = ["ROZETKA", "PROM", "ALLO", "EPICENTRK", "HOTLINE"]
        self.log_widgets: Dict[str, ctk.CTkTextbox] = {}
        self.target_links = []
        self.skip_stock_var = tk.BooleanVar(value=True)
        self.pages_all_var = tk.BooleanVar(value=False)
        self.threads_var = tk.StringVar(value="1")
        self.delay_var = tk.StringVar(value="1.5")
        self.debug_var = tk.BooleanVar(value=False)
        self.product_count = 0
        
        # New Snapshot Mode State
        self.snap_mode_var = tk.StringVar(value="new")
        self.snapshots_dict = {} # "Run At - [ID]" -> id
        self.url_configs = [] # list of {"url": "...", "tag": "..."}
        self.prom_query_config = None # In-memory buffer for Prom API config
        
        self._setup_ui()
        self._setup_logging()
        self._setup_callbacks()
        self._poll_queue()
        self._refresh_clients()

    def _setup_logging(self):
        class MultiChannelHandler(logging.Handler):
            def __init__(self, q):
                super().__init__()
                self.queue = q
            def emit(self, record):
                import re
                msg = self.format(record)
                group = "SYSTEM"
                name = record.name.lower()
                
                # Check for [MARKETPLACE] tag in message
                match = re.search(r"\[([A-Z0-9_]{3,15})\]", msg)
                if match:
                    group = match.group(1).upper()
                elif "gemini" in name or "ai." in name: 
                    group = "AI"
                elif "scheduler" in name: 
                    group = "SCHEDULER"
                    # Smart routing: If scheduler info mentions a marketplace, also copy it there
                    for mp in ["ROZETKA", "PROM", "ALLO", "EPICENTRK", "HOTLINE"]:
                        if f"[{mp}]" in msg or f" {mp.lower()} " in msg.lower():
                            group = mp
                            break
                elif "scrapers." in name or "scraper" in name:
                    parts = record.name.split(".")
                    # First fallback: use parts[1] (e.g. scrapers.prom -> PROM)
                    group = parts[1].upper() if len(parts) > 1 else "SYSTEM"
                    
                    # MAPI modules log with extra={"site": "rozetka"} but use a flat
                    # logger name ("scraper"), so parts[1] doesn't exist.
                    # Check the `site` attribute injected via extra= to route correctly.
                    if group == "SYSTEM":
                        site_attr = getattr(record, "site", None)
                        if site_attr:
                            group = str(site_attr).upper()
                    
                    # High-precision routing: check if message contains [MP] tag
                    match_mp = re.search(r"\[([A-Z0-9_]{3,15})\]", msg)
                    if match_mp:
                        group = match_mp.group(1).upper()
                
                # Fix for common aliases
                if group == "EPICENTR": group = "EPICENTRK"
                
                # Verify tab exists, else use SYSTEM or ALL only
                self.queue.put(("product_log" if "[LIVE]" in msg else "log", group.upper(), record.levelname, msg))
        
        handler = MultiChannelHandler(self.msg_queue)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', '%H:%M:%S'))
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.INFO)

    def _setup_ui(self):
        self.master.title("Marketplace CRM & Scraper")
        self.master.geometry("1450x920")
        
        apply_styles()

        # Layout
        self.grid_columnconfigure(0, weight=0, minsize=420)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=420, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        self.content = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew", padx=0, pady=15)

        # ----------------- Sidebar Content ---------------------------------------
        main_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=5)

        # 1. client Selection
        ctk.CTkLabel(main_frame, text="ACTIVE client", font=FONTS["title"], text_color=COLORS["accent"]).pack(pady=(0, 2), anchor="w")
        proj_row = ctk.CTkFrame(main_frame, fg_color="transparent")
        proj_row.pack(fill="x", pady=(0, 10))
        
        self.client_var = tk.StringVar()
        self.client_dropdown = ctk.CTkComboBox(proj_row, values=[], variable=self.client_var, command=self._on_client_selected)
        self.client_dropdown.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        ctk.CTkButton(proj_row, text="+", width=34, height=34, font=FONTS["title"], command=self._on_new_client_click).pack(side="right")

        # 2. Parsing Mode
        ctk.CTkLabel(main_frame, text="PARSING MODE", font=FONTS["title"], text_color=COLORS["accent"]).pack(pady=(2, 2), anchor="w")
        self.mode_var = tk.StringVar(value="search")
        modes = [
            ("Search", "search"),
            ("URLs", "url")
        ]
        mode_frame = ctk.CTkFrame(main_frame, fg_color="#2a2a2a", corner_radius=8)
        mode_frame.pack(fill="x", pady=(0, 10), padx=2)
        
        mode_inner = ctk.CTkFrame(mode_frame, fg_color="transparent")
        mode_inner.pack(padx=10, pady=5)
        for text, val in modes:
             ctk.CTkRadioButton(mode_inner, text=text, variable=self.mode_var, value=val, font=("Segoe UI", 12), command=self._on_mode_change).pack(side="left", padx=15)

        # 3. Mode Inputs
        self.input_container = ctk.CTkFrame(main_frame, fg_color="transparent")
        self.input_container.pack(fill="x", pady=0)
        self._rebuild_mode_inputs()

        # 4. Marketplaces & Methods
        ctk.CTkLabel(main_frame, text="MARKETPLACES", font=FONTS["title"], text_color=COLORS["accent"]).pack(pady=(15, 5), anchor="w")
        
        mp_container = ctk.CTkFrame(main_frame, fg_color="transparent")
        mp_container.pack(fill="x", pady=5)
        
        for mp in self.active_mps:
            row = ctk.CTkFrame(mp_container, fg_color="transparent")
            row.pack(fill="x", pady=2)
            
            var = tk.BooleanVar(value=True)
            self.marketplaces_vars[mp.lower()] = var
            cb = ctk.CTkCheckBox(row, text=mp, variable=var, width=100)
            cb.pack(side="left")
            
            method_var = tk.StringVar(value="MAPI")
            self.marketplaces_methods[mp.lower()] = method_var
            m_opt = ctk.CTkOptionMenu(row, values=["Auto", "Browser", "Requests", "MAPI"], variable=method_var, width=110, height=28, font=FONTS["small"])
            m_opt.pack(side="right")
            
            # Prom configuration button
            if mp.lower() == "prom":
                ctk.CTkButton(row, text="⚙", width=28, height=28, font=("Arial", 16), command=self._open_prom_config_dialog).pack(side="right", padx=(5, 0))
            
            # Status dot/label
            lbl = ctk.CTkLabel(row, text="●", text_color="#333333", font=("Arial", 14))
            lbl.pack(side="right", padx=10)
            self.marketplaces_status_labels[mp.lower()] = lbl

        # 4b. Snapshot Target (New)
        ctk.CTkLabel(main_frame, text="SNAPSHOT TARGET", font=FONTS["title"], text_color=COLORS["accent"]).pack(pady=(15, 5), anchor="w")
        self.snap_mode_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        self.snap_mode_frame.pack(fill="x", pady=2)
        
        ctk.CTkRadioButton(self.snap_mode_frame, text="New", variable=self.snap_mode_var, value="new", font=FONTS["small"]).pack(side="left")
        ctk.CTkRadioButton(self.snap_mode_frame, text="Append to existing", variable=self.snap_mode_var, value="append", font=FONTS["small"], command=self._refresh_snapshots).pack(side="left", padx=10)
        
        self.snap_dropdown = ctk.CTkComboBox(main_frame, values=[], width=380, font=FONTS["small"])
        self.snap_dropdown.pack(fill="x", pady=(2, 5))
        self.snap_dropdown.set("Select Snapshot...")
        ctk.CTkLabel(main_frame, text="OPTIONS", font=FONTS["title"], text_color=COLORS["accent"]).pack(pady=(15, 5), anchor="w")
        
        opt_row = ctk.CTkFrame(main_frame, fg_color="transparent")
        opt_row.pack(fill="x", pady=2)
        ctk.CTkCheckBox(opt_row, text="Skip OOS", variable=self.skip_stock_var, font=FONTS["small"]).pack(side="left")
        ctk.CTkCheckBox(opt_row, text="Debug", variable=self.debug_var, font=FONTS["small"]).pack(side="left", padx=10)

        # Concurrency & Throttling
        ctk_row2 = ctk.CTkFrame(main_frame, fg_color="transparent")
        ctk_row2.pack(fill="x", pady=5)
        
        ctk.CTkLabel(ctk_row2, text="Threads:", font=FONTS["small"]).pack(side="left")
        ctk.CTkEntry(ctk_row2, textvariable=self.threads_var, width=40, height=24).pack(side="left", padx=(5, 10))
        
        ctk.CTkLabel(ctk_row2, text="Delay (s):", font=FONTS["small"]).pack(side="left")
        ctk.CTkEntry(ctk_row2, textvariable=self.delay_var, width=40, height=24).pack(side="left", padx=5)
        
        self.start_btn = ctk.CTkButton(main_frame, text="START EXTRACTION", font=FONTS["title"], height=38, fg_color=COLORS["success"], hover_color="#27ae60", command=self._on_start_click)
        self.start_btn.pack(fill="x", pady=(15, 5))
        
        self.stop_btn = ctk.CTkButton(main_frame, text="STOP", font=FONTS["title"], height=38, state="disabled", fg_color="#333333", command=self._on_stop_click)
        self.stop_btn.pack(fill="x", pady=0)

        # 6. Database Tools
        ctk.CTkLabel(main_frame, text="TOOLS", font=FONTS["title"], text_color=COLORS["accent"]).pack(pady=(15, 2), anchor="w")
        ctk.CTkButton(main_frame, text="Database Control Panel", height=32, command=self._on_db_browser_click).pack(fill="x", pady=5)

        # --- Main Content Area -----------------------------------------------
        header_row = ctk.CTkFrame(self.content, fg_color="transparent")
        header_row.pack(fill="x", pady=(0, 15), padx=20)
        
        self.status_label = ctk.CTkLabel(header_row, text="Ready", font=FONTS["normal"])
        self.status_label.pack(side="left")

        self.selection_label = ctk.CTkLabel(header_row, text="0 items selected", font=FONTS["small"], text_color="#888888")
        self.selection_label.pack(side="right")
        
        self.progress = ctk.CTkProgressBar(self.content, mode="determinate")
        self.progress.pack(fill="x", pady=(0, 15), padx=20)
        self.progress.set(0)

        self.log_tabs = ctk.CTkTabview(self.content, height=500)
        self.log_tabs.pack(fill="both", expand=True, padx=20)
        
        self.log_tabs.add("LIVE DATA")
        data_frame = self.log_tabs.tab("LIVE DATA")
        
        cols = ("#", "MP", "TITLE", "PRICE")
        self.tree = ttk.Treeview(data_frame, columns=cols, show="headings", height=15)
        widths = {"#": 40, "MP": 90, "TITLE": 750, "PRICE": 110}
        
        for c in cols:
            self.tree.heading(c, text=c, command=lambda _c=c: self._sort_treeview_column(self.tree, _c, False))
            self.tree.column(c, width=widths.get(c, 100), anchor="w" if c=="TITLE" else "center")
            
        self.tree.pack(side="left", fill="both", expand=True)
        data_scroll = AutohideScrollbar(data_frame, orientation="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=data_scroll.set)
        data_scroll.pack(side="right", fill="y")

        # Bottom row for selection stats
        
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        tab_names = ["ALL", "AI", "SCHEDULER"] + self.active_mps + ["SYSTEM"]
        for name in tab_names:
            self.log_tabs.add(name)
            tab_frame = self.log_tabs.tab(name)
            txt = ctk.CTkTextbox(tab_frame, font=("Consolas", 12), border_width=0)
            txt.pack(fill="both", expand=True)
            # CTkTextbox is a wrapper; we must config the internal tk.Text for tags
            for tag, color in [("ERROR", "#ff5555"), ("WARNING", "#ffb86c"), ("SUCCESS", "#50fa7b"), ("INFO", "#f8f8f2")]:
                txt._textbox.tag_config(tag, foreground=color)
            txt.configure(state="disabled")
            self.log_widgets[name.upper()] = txt

    def _rebuild_mode_inputs(self):
        for w in self.input_container.winfo_children():
            w.destroy()
            
        mode = self.mode_var.get()
        if mode == "search":
            ctk.CTkLabel(self.input_container, text="Search Keywords (comma separated):").pack(anchor="w")
            self.query_entry = ctk.CTkEntry(self.input_container)
            self.query_entry.pack(fill="x", pady=(2, 8))
            self.query_entry.insert(0, "lifepo4 100ah 12v")
            
        elif mode == "url":
            self.url_btn = ctk.CTkButton(self.input_container, text=f"Paste URLs ({len(self.url_configs)} loaded)", command=self._open_url_modal)
            self.url_btn.pack(fill="x", pady=(10, 8))

        # Common 'Pages' entry for search/url
        ctk.CTkLabel(self.input_container, text="Pages:").pack(anchor="w")
        
        pages_row = ctk.CTkFrame(self.input_container, fg_color="transparent")
        pages_row.pack(fill="x", pady=(2, 0))
        
        self.pages_var = tk.StringVar(value="1")
        self.pages_entry = ctk.CTkEntry(pages_row, textvariable=self.pages_var, width=80)
        self.pages_entry.pack(side="left")
        
        def _toggle_pages():
            if self.pages_all_var.get():
                self.pages_entry.configure(state="disabled")
            else:
                self.pages_entry.configure(state="normal")
        
        ctk.CTkCheckBox(pages_row, text="All", variable=self.pages_all_var, width=50, command=_toggle_pages).pack(side="left", padx=10)
        _toggle_pages() # init state

    def _open_url_modal(self):
        def _on_save(configs):
            self.url_configs = configs
            if hasattr(self, "url_btn"):
                self.url_btn.configure(text=f"Paste URLs ({len(self.url_configs)} loaded)")
        
        modal = DirectUrlsWindow(self, self.url_configs, _on_save)
        modal.focus_set()

    def _open_prom_config_dialog(self):
        from gui.dialogs.prom_query_config_dialog import PromQueryConfigDialog
        
        is_append = self.snap_mode_var.get() == "append"
        task_id = None
        
        if is_append:
            selected_name = self.snap_dropdown.get()
            snap_db_id = self.snapshots_dict.get(selected_name)
            if snap_db_id:
                try:
                    conn = self.db.get_connection()
                    row = conn.execute("SELECT task_id FROM snapshots WHERE id = ?", (snap_db_id,)).fetchone()
                    if row:
                        task_id = row["task_id"]
                except Exception as e:
                    logger.error(f"Failed to fetch task_id for config: {e}")
            if not task_id:
                messagebox.showwarning("Error", "Please select a valid snapshot first to configure the appended task.")
                return
                
        def _on_save_config(new_config):
            self.prom_query_config = new_config

        modal = PromQueryConfigDialog(self, task_id=task_id, in_memory_config=self.prom_query_config, on_save_callback=_on_save_config)
        modal.grab_set()

    def _refresh_clients(self):
        try:
            conn = self.db.get_connection()
            rows = conn.execute("SELECT id, name FROM clients ORDER BY name").fetchall()
            
            if not rows:
                # Automagically create a default client if none exist (e.g. fresh DB)
                conn.execute("INSERT INTO clients (name) VALUES ('Default Client')")
                conn.commit()
                rows = conn.execute("SELECT id, name FROM clients ORDER BY name").fetchall()

            self.clients_dict = {r["name"]: r["id"] for r in rows}
            names = list(self.clients_dict.keys())
            self.client_dropdown.configure(values=names)
            if names and not self.active_client_id:
                self.client_var.set(names[0])
                self.active_client_id = self.clients_dict[names[0]]
        except Exception as e:
            logger.error(f"Failed to load clients: {e}")

    def _on_client_selected(self, name):
        self.active_client_id = self.clients_dict.get(name)
        logger.info(f"Switched to client: {name} (ID: {self.active_client_id})")
        self._refresh_snapshots()

    def _refresh_snapshots(self):
        if not self.active_client_id:
            self.snap_dropdown.configure(values=[])
            self.snap_dropdown.set("Select Snapshot...")
            return
        try:
            conn = self.db.get_connection()
            rows = conn.execute("""
                SELECT s.id, s.run_at, t.title 
                FROM snapshots s
                JOIN tasks t ON s.task_id = t.id
                WHERE t.client_id = ?
                ORDER BY s.run_at DESC
                LIMIT 30
            """, (self.active_client_id,)).fetchall()
            
            self.snapshots_dict = {}
            names = []
            for r in rows:
                name = f"{r['run_at'][:16]} - {r['title'][:30]} [#{r['id']}]"
                self.snapshots_dict[name] = r["id"]
                names.append(name)
            
            self.snap_dropdown.configure(values=names)
            if names:
                if self.snap_dropdown.get() not in names:
                    self.snap_dropdown.set(names[0])
            else:
                self.snap_dropdown.set("No snapshots found")
        except Exception as e:
            logger.error(f"Failed to load snapshots: {e}")

    def _on_new_client_click(self):
        name = simpledialog.askstring("New client", "Enter client name:")
        if name:
             try:
                conn = self.db.get_connection()
                conn.execute("INSERT INTO clients (name) VALUES (?)", (name,))
                conn.commit()
                self._refresh_clients()
             except Exception as e:
                 messagebox.showerror("Error", str(e))

    def _on_mode_change(self):
        self._rebuild_mode_inputs()

    def _on_start_click(self):
        self.product_count = 0 
        self.tree.delete(*self.tree.get_children())
        
        mode = self.mode_var.get()
        selected_mps = {mp: self.marketplaces_methods[mp].get() for mp, v in self.marketplaces_vars.items() if v.get()}
        
        if not selected_mps:
            messagebox.showwarning("Marketplaces", "Select at least one marketplace.")
            return

        # Prepare tasks based on mode
        discovery_tasks = [] # (mp, method, data)
        try: 
            if self.pages_all_var.get():
                pages = 9999 # Unlimited (early stop will handle it)
            else:
                pages = int(self.pages_var.get())
        except: 
            pages = 1
        
        if mode == "search":
            queries = [q.strip() for q in self.query_entry.get().split(",") if q.strip()]
            if not queries: return
            for q in queries:
                for mp, meth in selected_mps.items():
                    discovery_tasks.append((mp, meth, q, None))
                    
        elif mode == "url":
            if not self.url_configs: 
                messagebox.showwarning("Required", "Please click 'Paste URLs' and add at least one target link.")
                return
            for cfg in self.url_configs:
                url = cfg["url"]
                url_l = url.lower()
                mp_detect = None
                if "rozetka" in url_l: mp_detect = "rozetka"
                elif "hotline" in url_l: mp_detect = "hotline"
                elif "prom" in url_l: mp_detect = "prom"
                elif "allo" in url_l: mp_detect = "allo"
                elif "epicentr" in url_l: mp_detect = "epicentrk"

                if mp_detect and mp_detect in selected_mps:
                    discovery_tasks.append((mp_detect, selected_mps[mp_detect], url, cfg.get("tag")))
                else:
                    logger.warning(f"Marketplace for URL {url} not selected or not supported. Check that the marketplace checkbox is enabled.")
        
        skip_stock = self.skip_stock_var.get()
        debug_mode = self.debug_var.get()
        try:
            threads = int(self.threads_var.get())
            delay = float(self.delay_var.get())
        except:
            threads = 1
            delay = 1.5
            
        append_mode = self.snap_mode_var.get() == "append"
        task_data = None
        
        # Open task modal only for new tasks
        if not append_mode:
            queries = list({t[2] for t in discovery_tasks})
            mps = list({t[0] for t in discovery_tasks})
            query_str = ", ".join(queries[:5])
            mp_label = ", ".join(sorted(mps)).upper()
            default_title = f"{query_str[:60]}  [{mp_label}]"
            
            from gui.task_dialog import TaskDialog
            dialog = TaskDialog(self, title="New Task parameters", task_data={"title": default_title, "task_type": "discovery"})
            task_data = dialog.get_result()
            
            if not task_data:
                # User cancelled parsing
                return
            
        self._run_discovery_batch(discovery_tasks, pages, skip_stock, threads, delay, debug_mode, task_id=None, task_data=task_data)

    def _run_discovery_batch(self, tasks, pages, skip_stock, threads=1, delay=1.5, debug=False, task_id=None, task_data=None):
        self.is_running = True
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.scheduler._stop_event.clear()

        # Derive query and marketplace set for the session record
        mode = self.mode_var.get()
        queries = list({t[2] for t in tasks})
        mps = list({t[0] for t in tasks})
        session_id = str(uuid.uuid4())
        query_str = ", ".join(queries[:5])  # cap for display

        # Route session creation through the scheduler's serialized write queue
        task_stub = ScrapeTask(
            query=query_str,
            session_id=session_id,
            product_type=None,
            marketplaces={m: "MAPI" for m in mps}, # Stub for tracking
            pages_limit=pages,
            use_category_urls=False,
            category_urls={},
            skip_known_urls=False,
            skip_out_of_stock=skip_stock,
            threads_per_site=threads,
            request_delay=delay,
            direct_urls=self.url_configs if mode == "url" else None,
            debug=debug
        )
        self.scheduler.create_session(task_stub)

        # -- Snapshot Handling --
        append_mode = self.snap_mode_var.get() == "append"
        _snap_db_id: Optional[int] = None
        if append_mode:
            selected_name = self.snap_dropdown.get()
            _snap_db_id = self.snapshots_dict.get(selected_name)
            if not _snap_db_id:
                messagebox.showerror("Error", "Selected snapshot not found. Please refresh list.")
                return
            logger.info(f"[DB] Appending results to existing snapshot #{_snap_db_id}")

        # Derive task record
        _task_db_id: Optional[int] = task_id
        if self.active_client_id is not None or _task_db_id is not None:
            try:
                conn = self.db.get_connection()
                conn.execute("BEGIN")
                now_iso = datetime.now().astimezone().isoformat()
                
                # If we have a snapshot ID but no task ID, find the task ID
                if _snap_db_id and not _task_db_id:
                    row = conn.execute("SELECT task_id FROM snapshots WHERE id = ?", (_snap_db_id,)).fetchone()
                    if row: _task_db_id = row["task_id"]

                mode = self.mode_var.get()
                task_type = "search" if mode == "search" else "url_list"
                mp_label = ", ".join(sorted(mps)).upper()
                task_title = f"{query_str[:60]}  [{mp_label}]"
                query_params_json = json.dumps({
                    "queries": queries,
                    "marketplaces": mps,
                    "pages": pages,
                    "threads": threads,
                    "delay": delay,
                    "skip_stock": skip_stock,
                    "session_id": session_id,
                }, ensure_ascii=False)

                if _task_db_id is None:
                    t_title = task_data["title"] if task_data else task_title
                    t_type = task_data["task_type"] if task_data else task_type
                    t_desc = task_data.get("description") if task_data else None

                    # If prom config exists in memory, save it to tasks table
                    p_cfg = json.dumps(self.prom_query_config) if getattr(self, "prom_query_config", None) else None

                    conn.execute(
                        """INSERT INTO tasks
                           (client_id, title, task_type, description, schedule_type, query_params, prom_query_config, created_at, updated_at)
                           VALUES (?, ?, ?, ?, 'one_time', ?, ?, ?, ?)""",
                        (self.active_client_id, t_title, t_type, t_desc,
                         query_params_json, p_cfg, now_iso, now_iso)
                    )
                    _task_db_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                else:
                    # Update existing task timestamp
                    conn.execute("UPDATE tasks SET updated_at = ? WHERE id = ?", (now_iso, _task_db_id))

                if not _snap_db_id:
                    conn.execute(
                        """INSERT INTO snapshots (task_id, run_at, status)
                           VALUES (?, ?, 'running')""",
                        (_task_db_id, now_iso)
                    )
                    _snap_db_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                else:
                    # Update existing snapshot status
                    conn.execute("UPDATE snapshots SET status = 'running' WHERE id = ?", (_snap_db_id,))
                
                conn.execute("COMMIT")
                logger.info(f"[DB] Using task #{_task_db_id} and snapshot #{_snap_db_id}")
            except Exception as _e:
                logger.exception(f"[DB] Failed to setup task/snapshot context: {_e}")
                messagebox.showerror("Database Error", f"Failed to initialize snapshot: {_e}")
                self._on_stop_click()
                return

        if not _snap_db_id:
             logger.error("[DB] No snapshot ID available. Scraper results will not be persisted.")
             messagebox.showerror("Error", "Required database snapshot could not be created. Is a client selected?")
             self._on_stop_click()
             return

        def run_batch():
            self.msg_queue.put(("status_update", f"Processing {len(tasks)} jobs..."))
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [
                    executor.submit(
                        self.scheduler.run_individual_discovery,
                        mp, meth, data, pages, _snap_db_id or session_id, skip_stock, threads, delay, debug, tag
                    )
                    for mp, meth, data, tag in tasks
                ]
                try:
                    for _ in concurrent.futures.as_completed(futures):
                        if not self.is_running:
                            break
                        # Accessing result to propagate exceptions for logging within loop
                        try: _.result()
                        except Exception as e:
                            logger.error(f"Scraper individual failure: {e}")
                except Exception as e:
                    logger.error(f"Error in batch execution loop: {e}")

            # -- Finalise snapshot --
            if _snap_db_id is not None:
                def _finalize_snap(sid=_snap_db_id, count=self.scheduler._total_new, running=self.is_running):
                    conn = self.db.get_connection()
                    status = "stopped" if not running else "completed"
                    try:
                        conn.execute("UPDATE snapshots SET product_count = ?, status = ? WHERE id = ?", (count, status, sid))
                        conn.commit()
                        logger.info(f"[DB] Snapshot #{sid} finalized - {count} products total")
                    except Exception as e:
                        logger.error(f"[DB] Failed to finalize snapshot: {e}")

                self.scheduler._db_write_queue.submit(_finalize_snap)


            # Normalization is manual-only вЂ” launch from DB Control Panel
            self.msg_queue.put(("batch_finished", None))

        threading.Thread(target=run_batch, daemon=True).start()

    def _on_stop_click(self):
        self.is_running = False
        self.scheduler.stop()
        self.status_label.configure(text="Stopping...", text_color=COLORS["error"])

    def _poll_queue(self):
        if not self.master.winfo_exists(): return
        try:
            while not self.msg_queue.empty():
                try:
                    msg = self.msg_queue.get_nowait()
                    self._handle_msg(msg)
                except Exception as e:
                    print(f"Error handling UI message: {e}")
        except Exception as e:
            print(f"Error in poll queue loop: {e}")
        finally:
            self.master.after(100, self._poll_queue)

    def _handle_msg(self, msg):
        mtype, *args = msg
        if mtype == "log":
            group, level, text = args
            for target in ["ALL", group]:
                if target in self.log_widgets:
                    w = self.log_widgets[target]
                    w.configure(state="normal")
                    # Use internal textbox for tagged insert
                    try:
                        w._textbox.insert("end", text + "\n", level)
                        w.see("end")
                    except: pass
                    w.configure(state="disabled")
        elif mtype == "product":
            prod, is_new, delta = args
            self.product_count += 1
            d_str = f" (О”{delta:+.0f})" if delta is not None else ""
            clean_title = str(prod.title).replace("\n", " ").strip()
            iid = self.tree.insert("", "end", values=(self.product_count, prod.marketplace.upper(), clean_title, f"{prod.price}{d_str}"))
            try:
                self.tree.see(iid)
            except: pass
        elif mtype == "status_update":
            self.status_label.configure(text=args[0], text_color=COLORS["accent"])
        elif mtype == "batch_finished":
            self.is_running = False
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
            self.status_label.configure(text="Ready", text_color=COLORS["fg"])
            self.progress.set(1.0)
        elif mtype == "mp_status":
            mp, status = args
            if mp.lower() in self.marketplaces_status_labels:
                clr = COLORS["success"] if "Finished" in status else COLORS["accent"]
                self.marketplaces_status_labels[mp.lower()].configure(text_color=clr)

    def _setup_callbacks(self):
        self.scheduler.on_product_found = lambda p, n, d: self.msg_queue.put(("product", p, n, d))
        self.scheduler.on_mp_status = lambda mp, status: self.msg_queue.put(("mp_status", mp, status))

    def _on_tree_select(self, event):
        count = len(self.tree.selection())
        self.selection_label.configure(text=f"{count} items selected")

    def _on_db_browser_click(self):
        from gui.db_browser_window import DbBrowserWindow
        win = DbBrowserWindow(self, self.db, scheduler=self.scheduler)
        # Hook into win destroy to refresh our clients
        def on_win_closed(event):
            if event.widget == win: self._refresh_clients()
        win.bind("<Destroy>", on_win_closed)

    def _on_normalize_excel_click(self):
        # ... logic remains as before ...
        pass

    def _on_gemini_keys_exhausted(self, client): return False

    def _sort_treeview_column(self, tv, col, reverse):
        l = [(tv.set(k, col), k) for k in tv.get_children('')]
        
        # Try numeric sort for specific columns
        if col in ("#", "PRICE"):
            try:
                l.sort(key=lambda t: float(t[0].split(' ')[0]), reverse=reverse)
            except ValueError:
                l.sort(reverse=reverse)
        else:
            l.sort(reverse=reverse)

        for index, (val, k) in enumerate(l):
            tv.move(k, '', index)

        tv.heading(col, command=lambda: self._sort_treeview_column(tv, col, not reverse))
