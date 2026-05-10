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
from gui.styles import COLORS, FONTS, apply_styles
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
                elif "scheduler" in name: 
                    group = "SCHEDULER"
                    # Smart routing: If scheduler info mentions a marketplace, also copy it there
                    for mp in ["ROZETKA", "PROM", "ALLO", "EPICENTRK", "HOTLINE"]:
                        if mp.lower() in msg.lower():
                            group = mp
                            break
                elif "scrapers." in name or "scraper" in name:
                    parts = record.name.split(".")
                    # First fallback: use parts[1] (e.g. scrapers.prom -> PROM)
                    group = parts[1].upper() if len(parts) > 1 else "SYSTEM"
                    
                    # High-precision routing: check if message contains [MP] tag or scraper name
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
        main_frame = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # 1. Project Selection
        ctk.CTkLabel(main_frame, text="ACTIVE PROJECT", font=FONTS["title"], text_color=COLORS["accent"]).pack(pady=(0, 5), anchor="w")
        proj_row = ctk.CTkFrame(main_frame, fg_color="transparent")
        proj_row.pack(fill="x", pady=(0, 15))
        
        self.project_var = tk.StringVar()
        self.project_dropdown = ctk.CTkComboBox(proj_row, values=[], variable=self.project_var, command=self._on_project_selected)
        self.project_dropdown.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        ctk.CTkButton(proj_row, text="＋", width=34, height=34, font=FONTS["title"], command=self._on_new_project_click).pack(side="right")

        # 2. Parsing Mode
        ctk.CTkLabel(main_frame, text="PARSING MODE", font=FONTS["title"], text_color=COLORS["accent"]).pack(pady=(5, 5), anchor="w")
        self.mode_var = tk.StringVar(value="search")
        modes = [
            ("Parse Search Keywords", "search"),
            ("Parse Filter/Category URLs", "filter"),
            ("Parse Seller/Store list", "seller"),
            ("Update Price Watchlist", "update")
        ]
        mode_frame = ctk.CTkFrame(main_frame, fg_color="#2a2a2a", corner_radius=8)
        mode_frame.pack(fill="x", pady=(0, 15), padx=2)
        
        for text, val in modes:
             ctk.CTkRadioButton(mode_frame, text=text, variable=self.mode_var, value=val, font=("Segoe UI", 12), command=self._on_mode_change).pack(anchor="w", padx=12, pady=8)

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
            
            method_var = tk.StringVar(value="Auto")
            self.marketplaces_methods[mp.lower()] = method_var
            m_opt = ctk.CTkOptionMenu(row, values=["Auto", "Browser", "Requests"], variable=method_var, width=110, height=28, font=FONTS["small"])
            m_opt.pack(side="right")
            
            # Status dot/label
            lbl = ctk.CTkLabel(row, text="●", text_color="#333333", font=("Arial", 14))
            lbl.pack(side="right", padx=10)
            self.marketplaces_status_labels[mp.lower()] = lbl

        # 5. Global Controls
        ctk.CTkLabel(main_frame, text="OPTIONS", font=FONTS["title"], text_color=COLORS["accent"]).pack(pady=(20, 5), anchor="w")
        ctk.CTkCheckBox(main_frame, text="Skip Out of Stock", variable=self.skip_stock_var).pack(anchor="w", pady=5)
        
        self.start_btn = ctk.CTkButton(main_frame, text="START EXTRACTION", font=FONTS["title"], height=45, fg_color=COLORS["success"], hover_color="#27ae60", command=self._on_start_click)
        self.start_btn.pack(fill="x", pady=(25, 10))
        
        self.stop_btn = ctk.CTkButton(main_frame, text="STOP", font=FONTS["title"], height=45, state="disabled", fg_color="#333333", command=self._on_stop_click)
        self.stop_btn.pack(fill="x", pady=0)

        # 6. Database Tools
        ctk.CTkLabel(main_frame, text="TOOLS", font=FONTS["title"], text_color=COLORS["accent"]).pack(pady=(30, 5), anchor="w")
        ctk.CTkButton(main_frame, text="Database Control Panel", command=self._on_db_browser_click).pack(fill="x", pady=5)

        # ── Main Content Area ────────────────────────────────────────────────
        header_row = ctk.CTkFrame(self.content, fg_color="transparent")
        header_row.pack(fill="x", pady=(0, 15), padx=20)
        
        self.status_label = ctk.CTkLabel(header_row, text="Ready", font=FONTS["normal"])
        self.status_label.pack(side="left")
        
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
        data_scroll = ttk.Scrollbar(data_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=data_scroll.set)
        data_scroll.pack(side="right", fill="y")

        # Bottom row for selection stats
        self.selection_label = ctk.CTkLabel(data_frame, text="0 items selected", font=FONTS["small"], text_color="#aaaaaa")
        self.selection_label.pack(side="bottom", anchor="w", padx=5, pady=2)
        
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
            
        elif mode in ("filter", "seller"):
            ctk.CTkLabel(self.input_container, text="Paste URLs (one per line):").pack(anchor="w")
            self.url_text = ctk.CTkTextbox(self.input_container, height=120)
            self.url_text.pack(fill="x", pady=(2, 8))
            
        elif mode == "update":
            desc = "Mode: Update Prices\nOnly currently monitored products in selected project will be re-scraped."
            ctk.CTkLabel(self.input_container, text=desc, text_color="#aaaaaa", justify="left", wraplength=380).pack(anchor="w", pady=5)
            # Standard return to avoid showing Pages for individual update
            return

        # Common 'Pages' entry for search/filter/seller
        ctk.CTkLabel(self.input_container, text="Pages:").pack(anchor="w")
        self.pages_var = tk.StringVar(value="1")
        self.pages_entry = ctk.CTkEntry(self.input_container, textvariable=self.pages_var, width=80)
        self.pages_entry.pack(anchor="w")

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
            pages = int(self.pages_var.get())
        except: 
            pages = 1
        
        if mode == "search":
            queries = [q.strip() for q in self.query_entry.get().split(",") if q.strip()]
            if not queries: return
            for q in queries:
                for mp, meth in selected_mps.items():
                    discovery_tasks.append((mp, meth, q))
                    
        elif mode in ("filter", "seller"):
            urls = [u.strip() for u in self.url_text.get("1.0", "end").splitlines() if u.strip()]
            if not urls: return
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

        elif mode == "update":
            # LOGIC: Fetch monitored products for current project
            try:
                conn = self.db.get_connection()
                products = conn.execute("""
                    SELECT mp.marketplace, mp.competitor_product_url 
                    FROM monitored_products mp
                    JOIN project_products pp ON mp.project_product_id = pp.id
                    WHERE pp.project_id = ? AND mp.enabled = 1
                """, (self.active_project_id,)).fetchall()
                for p in products:
                    m = p["marketplace"].lower()
                    if m in selected_mps:
                        discovery_tasks.append((m, selected_mps[m], p["competitor_product_url"]))
                if not discovery_tasks:
                    messagebox.showinfo("Empty", "No active monitored products found for this project.")
                    return
            except Exception as e:
                messagebox.showerror("Error", str(e))
                return
        
        skip_stock = self.skip_stock_var.get()
        self._run_discovery_batch(discovery_tasks, pages, skip_stock)

    def _run_discovery_batch(self, tasks, pages, skip_stock):
        self.is_running = True
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.scheduler._stop_event.clear()

        # Derive query and marketplace set for the session record
        queries = list({t[2] for t in tasks})
        mps = list({t[0] for t in tasks})
        session_id = str(uuid.uuid4())
        query_str = ", ".join(queries[:5])  # cap for display

        # Write the session row NOW so _update_session_count can find it
        try:
            conn = self.db.get_connection()
            conn.execute(
                """INSERT INTO scrape_sessions (id, query, marketplaces, status, products_found, started_at)
                   VALUES (?, ?, ?, 'running', 0, ?)""",
                (session_id, query_str, str(mps), datetime.now(timezone.utc).isoformat())
            )
            conn.commit()
        except Exception as e:
            logger.warning(f"Could not create session row: {e}")

        def run_batch():
            self.msg_queue.put(("status_update", f"Processing {len(tasks)} jobs…"))
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [
                    executor.submit(
                        self.scheduler.run_individual_discovery,
                        mp, meth, data, pages, session_id, skip_stock
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

            # Update session final status
            final = "stopped" if not self.is_running else "completed"
            try:
                conn = self.db.get_connection()
                conn.execute(
                    "UPDATE scrape_sessions SET status=?, finished_at=? WHERE id=?",
                    (final, datetime.now(timezone.utc).isoformat(), session_id)
                )
                conn.commit()
            except Exception as e:
                logger.warning(f"Could not finalize session row: {e}")

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
