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
from db.product_repo import ProductRepository
from gui.styles import COLORS, FONTS, apply_styles, AutohideScrollbar
from core.scheduler import TaskScheduler
from core.models import ScrapeTask

logger = logging.getLogger(__name__)


class MainWindow(ctk.CTkFrame):
    def __init__(self, master, db: Database):
        super().__init__(master)
        self.master = master
        self.db = db
        self.repo = ProductRepository(self.db)
        self.scheduler = TaskScheduler(self.db)
        
        # UI State
        self.active_project_id = None
        self.projects_dict = {}
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
        
        self._setup_ui()
        self._setup_logging()
        self._setup_callbacks()
        self._poll_queue()
        self._refresh_projects()

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

        # ── Sidebar Content ──────────────────────────────────────────────────
        main_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=5)

        # 1. Project Selection
        ctk.CTkLabel(main_frame, text="ACTIVE PROJECT", font=FONTS["title"], text_color=COLORS["accent"]).pack(pady=(0, 2), anchor="w")
        proj_row = ctk.CTkFrame(main_frame, fg_color="transparent")
        proj_row.pack(fill="x", pady=(0, 10))
        
        self.project_var = tk.StringVar()
        self.project_dropdown = ctk.CTkComboBox(proj_row, values=[], variable=self.project_var, command=self._on_project_selected)
        self.project_dropdown.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        ctk.CTkButton(proj_row, text="＋", width=34, height=34, font=FONTS["title"], command=self._on_new_project_click).pack(side="right")

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
            
            # Status dot/label
            lbl = ctk.CTkLabel(row, text="●", text_color="#333333", font=("Arial", 14))
            lbl.pack(side="right", padx=10)
            self.marketplaces_status_labels[mp.lower()] = lbl

        # 5. Global Controls
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

        # ── Main Content Area ────────────────────────────────────────────────
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
            self.url_btn = ctk.CTkButton(self.input_container, text=f"Paste URLs ({len(getattr(self, 'url_list', []))} loaded)", command=self._open_url_modal)
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
        modal = ctk.CTkToplevel(self)
        modal.title("Paste Target URLs")
        modal.geometry("500x400")
        modal.transient(self)
        modal.grab_set()
        
        ctk.CTkLabel(modal, text="Paste URLs (one per line):").pack(pady=(10, 5), padx=10, anchor="w")
        txt = ctk.CTkTextbox(modal, height=250)
        txt.pack(fill="both", expand=True, padx=10, pady=5)
        
        curr_urls = getattr(self, "url_list", [])
        if curr_urls:
            txt.insert("1.0", "\n".join(curr_urls))
            
        def _save():
            content = txt.get("1.0", "end").splitlines()
            cleaned = [u.strip() for u in content if u.strip().startswith("http")]
            self.url_list = cleaned
            if hasattr(self, "url_btn"):
                self.url_btn.configure(text=f"Paste URLs ({len(self.url_list)} loaded)")
            modal.destroy()
            
        btn_frame = ctk.CTkFrame(modal, fg_color="transparent")
        btn_frame.pack(fill="x", pady=10, padx=10)
        ctk.CTkButton(btn_frame, text="Cancel", width=100, fg_color="#555", command=modal.destroy).pack(side="left")
        ctk.CTkButton(btn_frame, text="Save URLs", width=100, command=_save).pack(side="right")

    def _refresh_projects(self):
        try:
            conn = self.db.get_connection()
            rows = conn.execute("SELECT id, name FROM projects ORDER BY name").fetchall()
            self.projects_dict = {r["name"]: r["id"] for r in rows}
            names = list(self.projects_dict.keys())
            self.project_dropdown.configure(values=names)
            if names and not self.active_project_id:
                self.project_var.set(names[0])
                self.active_project_id = self.projects_dict[names[0]]
        except Exception as e:
            logger.error(f"Failed to load projects: {e}")

    def _on_project_selected(self, name):
        self.active_project_id = self.projects_dict.get(name)
        logger.info(f"Switched to project: {name} (ID: {self.active_project_id})")

    def _on_new_project_click(self):
        name = simpledialog.askstring("New Project", "Enter project name:")
        if name:
             try:
                conn = self.db.get_connection()
                conn.execute("INSERT INTO projects (name) VALUES (?)", (name,))
                conn.commit()
                self._refresh_projects()
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
                    discovery_tasks.append((mp, meth, q))
                    
        elif mode == "url":
            urls = getattr(self, "url_list", [])
            if not urls: 
                messagebox.showwarning("Required", "Please click 'Paste URLs' and add at least one target link.")
                return
            for url in urls:
                url_l = url.lower()
                mp_detect = None
                if "rozetka" in url_l: mp_detect = "rozetka"
                elif "hotline" in url_l: mp_detect = "hotline"
                elif "prom" in url_l: mp_detect = "prom"
                elif "allo" in url_l: mp_detect = "allo"
                elif "epicentr" in url_l: mp_detect = "epicentrk"

                if mp_detect and mp_detect in selected_mps:
                    discovery_tasks.append((mp_detect, selected_mps[mp_detect], url))
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
            
        self._run_discovery_batch(discovery_tasks, pages, skip_stock, threads, delay, debug_mode)

    def _run_discovery_batch(self, tasks, pages, skip_stock, threads=1, delay=1.5, debug=False):
        self.is_running = True
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.scheduler._stop_event.clear()

        # Derive query and marketplace set for the session record
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
            debug=debug
        )
        self.scheduler.create_session(task_stub)

        def run_batch():
            self.msg_queue.put(("status_update", f"Processing {len(tasks)} jobs…"))
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [
                    executor.submit(
                        self.scheduler.run_individual_discovery,
                        mp, meth, data, pages, session_id, skip_stock, threads, delay, debug
                    )
                    for mp, meth, data in tasks
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

            # Update session final status via serialized queue
            final = "stopped" if not self.is_running else "completed"
            self.scheduler.update_session(session_id, final, [], 0)

            # Normalization is manual-only — launch from DB Control Panel
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
            d_str = f" (Δ{delta:+.0f})" if delta is not None else ""
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
        win = DbBrowserWindow(self.master, self.db, self.repo, scheduler=self.scheduler)
        # Hook into win destroy to refresh our projects
        def on_win_closed(event):
            if event.widget == win: self._refresh_projects()
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
