from __future__ import annotations

import json
import logging
import threading
import webbrowser
from datetime import datetime, timezone
from tkinter import ttk, messagebox, filedialog
import tkinter as tk
import customtkinter as ctk
from typing import Any, Optional

from gui.styles import COLORS, FONTS

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────── table defs ──
# Each entry: label, icon, section, table (actual SQL table), sql (SELECT),
#   cols [(key, header, width, filterable)], editable, pk,
#   project_join (column to filter by project_id, optional),
#   form [(field, label, type)]  where type is text|number|bool|multiline|select:a,b|project_select

TABLES: dict[str, dict[str, Any]] = {
    "raw_products": {
        "label": "Discovered Products", "icon": "🔍", "section": "raw",
        "table": "products",
        "sql": """
            SELECT p.id, p.marketplace, p.norm_brand AS brand, p.norm_model AS model,
                   p.norm_voltage AS v, p.norm_capacity AS ah, ph.price,
                   CASE p.is_relevant WHEN 1 THEN '✓' ELSE '✗' END AS rel,
                   p.title, p.url, DATE(p.first_seen_at) AS seen
            FROM products p
            LEFT JOIN (
                SELECT product_id, price,
                       ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY scraped_at DESC) rn
                FROM price_history
            ) ph ON p.id = ph.product_id AND ph.rn = 1
            ORDER BY p.last_seen_at DESC LIMIT 10000
        """,
        "cols": [
            ("id","ID",40,False), ("marketplace","MP",65,True),
            ("brand","Brand",100,True), ("model","Model",110,True),
            ("v","V",45,True), ("ah","Ah",45,True), ("price","Price",75,True),
            ("rel","Rel",35,True), ("title","Title",280,True),
            ("url","URL",0,False), ("seen","Seen",80,False),
        ],
        "editable": False, "pk": "id",
    },
    "raw_price_history": {
        "label": "Price History", "icon": "💰", "section": "raw",
        "table": "price_history",
        "sql": """
            SELECT ph.id, p.title AS product, p.marketplace,
                   ph.price, ph.currency, ph.availability, DATE(ph.scraped_at) AS scraped
            FROM price_history ph JOIN products p ON ph.product_id=p.id
            ORDER BY ph.scraped_at DESC LIMIT 5000
        """,
        "cols": [
            ("id","ID",40,False), ("product","Product",300,True),
            ("marketplace","MP",65,True), ("price","Price",75,True),
            ("currency","Cur",40,False), ("availability","Avail",80,True),
            ("scraped","Date",90,False),
        ],
        "editable": False, "pk": "id",
    },
    "raw_sessions": {
        "label": "Scrape Sessions", "icon": "🔄", "section": "raw",
        "table": "scrape_sessions",
        "sql": """
            SELECT id, query, marketplaces, status, products_found, DATE(started_at) AS date
            FROM scrape_sessions ORDER BY started_at DESC
        """,
        "cols": [
            ("id","ID",100,False), ("query","Query",200,True),
            ("marketplaces","Marketplaces",140,True), ("status","Status",80,True),
            ("products_found","Found",55,False), ("date","Date",85,False),
        ],
        "editable": False, "pk": "id",
    },
    "projects": {
        "label": "Projects", "icon": "📋", "section": "project",
        "table": "projects",
        "sql": "SELECT id, name, client_name, contact, status, notes, DATE(created_at) AS created FROM projects ORDER BY created_at DESC",
        "cols": [
            ("id","ID",40,False), ("name","Name",180,True),
            ("client_name","Client",130,True), ("contact","Contact",130,True),
            ("status","Status",75,True), ("notes","Notes",220,True),
            ("created","Created",80,False),
        ],
        "editable": True, "pk": "id",
        "form": [
            ("name","Project Name *","text"), ("client_name","Client Name","text"),
            ("contact","Contact","text"),
            ("status","Status","select:active,paused,archived"),
            ("notes","Notes","multiline"),
        ],
    },
    "project_products": {
        "label": "Client Products", "icon": "📦", "section": "business",
        "table": "project_products", "project_join": "pp.project_id",
        "sql": """
            SELECT pp.id, pr.name AS project, pp.sku, pp.title, pp.brand, pp.model,
                   pp.category, pp.cost_price, pp.selling_price, pp.marketplace,
                   CASE pp.is_active WHEN 1 THEN '✓' ELSE '✗' END AS active
            FROM project_products pp LEFT JOIN projects pr ON pp.project_id=pr.id
        """,
        "cols": [
            ("id","ID",40,False), ("project","Project",100,True),
            ("sku","SKU",70,True), ("title","Title",220,True),
            ("brand","Brand",80,True), ("model","Model",100,True),
            ("category","Cat",90,True), ("cost_price","Cost",65,True),
            ("selling_price","Sale",65,True), ("marketplace","MP",75,True),
            ("active","Active",45,False),
        ],
        "editable": True, "pk": "id",
        "form": [
            ("project_id","Project *","project_select"),
            ("sku","SKU","text"), ("title","Title *","text"),
            ("brand","Brand","text"), ("model","Model","text"),
            ("category","Category","text"),
            ("cost_price","Cost Price","number"), ("selling_price","Selling Price","number"),
            ("marketplace","MP","select:rozetka,prom,allo,epicentrk,hotline,m.ua,other"),
            ("product_url","Product URL","text"), ("is_active","Active","bool"),
        ],
    },
    "competitors": {
        "label": "Competitors", "icon": "🏪", "section": "business",
        "table": "competitors", "project_join": "c.project_id",
        "sql": """
            SELECT c.id, pr.name AS project, c.name, c.marketplace, c.seller_url, c.notes
            FROM competitors c LEFT JOIN projects pr ON c.project_id=pr.id
        """,
        "cols": [
            ("id","ID",40,False), ("project","Project",100,True),
            ("name","Name",160,True), ("marketplace","MP",75,True),
            ("seller_url","Seller URL",250,True), ("notes","Notes",200,True),
        ],
        "editable": True, "pk": "id",
        "form": [
            ("project_id","Project *","project_select"),
            ("name","Competitor Name *","text"),
            ("marketplace","MP","select:rozetka,prom,allo,epicentrk,hotline,m.ua,other"),
            ("seller_url","Seller URL","text"), ("notes","Notes","multiline"),
        ],
    },
    "monitored_products": {
        "label": "Monitored", "icon": "👁", "section": "business",
        "table": "monitored_products",
        "sql": """
            SELECT mp.id, pp.title AS client_product, c.name AS competitor,
                   mp.competitor_product_url, mp.marketplace,
                   CASE mp.enabled WHEN 1 THEN '✓' ELSE '✗' END AS enabled,
                   mp.last_status, DATE(mp.last_checked_at) AS checked
            FROM monitored_products mp
            LEFT JOIN project_products pp ON mp.project_product_id=pp.id
            LEFT JOIN competitors c ON mp.competitor_id=c.id
        """,
        "cols": [
            ("id","ID",40,False), ("client_product","My Product",180,True),
            ("competitor","Competitor",120,True),
            ("competitor_product_url","Competitor URL",220,True),
            ("marketplace","MP",70,True), ("enabled","On",35,False),
            ("last_status","Status",80,True), ("checked","Checked",85,False),
        ],
        "editable": True, "pk": "id",
        "form": [
            ("project_product_id","Client Product ID","number"),
            ("competitor_id","Competitor ID","number"),
            ("competitor_product_url","Competitor URL *","text"),
            ("marketplace","MP","select:rozetka,prom,allo,epicentrk,hotline,m.ua,other"),
            ("title_snapshot","Title Snapshot","text"),
            ("enabled","Enabled","bool"),
            ("check_frequency","Frequency","select:daily,weekly,manual"),
        ],
    },
    "price_observations": {
        "label": "Price Observations", "icon": "📈", "section": "business",
        "table": "price_observations",
        "sql": """
            SELECT po.id, pp.title AS client_product, mp.competitor_product_url AS comp_url,
                   po.price, po.currency, po.availability, DATE(po.scraped_at) AS scraped, po.raw_title
            FROM price_observations po
            LEFT JOIN monitored_products mp ON po.monitored_product_id=mp.id
            LEFT JOIN project_products pp ON mp.project_product_id=pp.id
            ORDER BY po.scraped_at DESC LIMIT 5000
        """,
        "cols": [
            ("id","ID",40,False), ("client_product","My Product",180,True),
            ("comp_url","Competitor URL",200,True), ("price","Price",75,True),
            ("currency","Cur",40,False), ("availability","Avail",80,True),
            ("scraped","Date",85,False), ("raw_title","Raw Title",180,True),
        ],
        "editable": False, "pk": "id",
    },
    "report_runs": {
        "label": "Reports", "icon": "📄", "section": "business",
        "table": "report_runs", "project_join": "rr.project_id",
        "sql": """
            SELECT rr.id, pr.name AS project, rr.report_type,
                   rr.period_start, rr.period_end, rr.output_path,
                   SUBSTR(rr.summary, 1, 80) AS summary, DATE(rr.created_at) AS created
            FROM report_runs rr LEFT JOIN projects pr ON rr.project_id=pr.id
            ORDER BY rr.created_at DESC
        """,
        "cols": [
            ("id","ID",40,False), ("project","Project",100,True),
            ("report_type","Type",100,True),
            ("period_start","From",90,False), ("period_end","To",90,False),
            ("output_path","File",200,True), ("summary","Summary",220,True),
            ("created","Created",85,False),
        ],
        "editable": False, "pk": "id",
    },
}

_BUSINESS_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT,
    client_name TEXT,
    contact     TEXT,
    notes       TEXT,
    status      TEXT NOT NULL DEFAULT 'active',
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS project_products (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id    INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    sku           TEXT,
    title         TEXT NOT NULL,
    brand         TEXT,
    model         TEXT,
    category      TEXT,
    cost_price    REAL,
    selling_price REAL,
    marketplace   TEXT,
    product_url   TEXT,
    image_url     TEXT,
    description   TEXT,
    specs_json    TEXT,
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS competitors (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    marketplace TEXT,
    seller_url  TEXT,
    notes       TEXT,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS monitored_products (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    project_product_id     INTEGER REFERENCES project_products(id) ON DELETE CASCADE,
    competitor_id          INTEGER REFERENCES competitors(id) ON DELETE SET NULL,
    competitor_product_url TEXT NOT NULL,
    marketplace            TEXT,
    title_snapshot         TEXT,
    enabled                INTEGER NOT NULL DEFAULT 1,
    check_frequency        TEXT DEFAULT 'daily',
    last_checked_at        TEXT,
    last_status            TEXT,
    created_at             TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS price_observations (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    monitored_product_id INTEGER NOT NULL REFERENCES monitored_products(id) ON DELETE CASCADE,
    price                REAL NOT NULL,
    currency             TEXT NOT NULL DEFAULT 'UAH',
    availability         TEXT,
    scraped_at           TEXT NOT NULL,
    raw_title            TEXT,
    raw_data_json        TEXT
);
CREATE TABLE IF NOT EXISTS report_runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id   INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    report_type  TEXT NOT NULL,
    period_start TEXT,
    period_end   TEXT,
    output_path  TEXT,
    summary      TEXT,
    created_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS content_templates (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    marketplace   TEXT,
    name          TEXT NOT NULL,
    prompt        TEXT,
    output_format TEXT,
    is_default    INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pp_project  ON project_products(project_id);
CREATE INDEX IF NOT EXISTS idx_comp_proj   ON competitors(project_id);
CREATE INDEX IF NOT EXISTS idx_mon_pp      ON monitored_products(project_product_id);
CREATE INDEX IF NOT EXISTS idx_po_mon      ON price_observations(monitored_product_id);
CREATE INDEX IF NOT EXISTS idx_rr_proj     ON report_runs(project_id);
"""


# ─────────────────────────────────────────────────────── Control Panel ───────

class DbBrowserWindow(ctk.CTkToplevel):

    def __init__(self, master, db, repo, scheduler=None):
        super().__init__(master)
        self.db = db
        self.repo = repo
        self.scheduler = scheduler

        self.title("Database Control Panel")
        self.geometry("1440x900")
        self.minsize(1100, 650)

        # state
        self._current_table: str = "raw_products"
        self._current_project_id: Optional[int] = None
        self._all_rows: list[dict] = []
        self._displayed_rows: list[dict] = []
        self._sort_col: Optional[str] = None
        self._sort_dir: int = 1   # 1=ASC -1=DESC
        self._filter_vars: dict[str, tk.StringVar] = {}
        self._global_var = tk.StringVar()
        self._global_var.trace_add("write", self._on_filter_change)
        self._col_keys: list[str] = []
        self._active_nav: Optional[ctk.CTkButton] = None

        self._ensure_business_schema()
        self._setup_styles()
        self._setup_ui()
        self._refresh_project_sidebar()
        self._load_table("raw_products")

        self.grab_set()
        self.after(20, self.lift)
        self.focus_force()

    # ── schema ───────────────────────────────────────────────────────────────

    def _ensure_business_schema(self):
        conn = self.db.get_connection()
        conn.executescript(_BUSINESS_SCHEMA)
        conn.commit()

    # ── styles ───────────────────────────────────────────────────────────────

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("default")
        bg, fg, sel = "#2d2d2d", "#cccccc", "#1f538d"
        hdr = "#1e1e1e"
        style.configure("DB.Treeview",
            background=bg, foreground=fg, fieldbackground=bg,
            rowheight=24, borderwidth=0, font=("Segoe UI", 11))
        style.configure("DB.Treeview.Heading",
            background=hdr, foreground="#8ab4f8",
            font=("Segoe UI", 11, "bold"), relief="flat", padding=(4, 4))
        style.map("DB.Treeview",
            background=[("selected", sel)],
            foreground=[("selected", "#ffffff")])
        style.map("DB.Treeview.Heading",
            background=[("active", "#333333")])

    # ── UI layout ─────────────────────────────────────────────────────────────

    def _setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # sidebar
        self._sidebar = ctk.CTkScrollableFrame(self, width=210, corner_radius=0,
                                               fg_color=COLORS["sidebar"])
        self._sidebar.grid(row=0, column=0, sticky="nsew")

        # main area
        main = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        main.grid_rowconfigure(2, weight=1)
        main.grid_columnconfigure(0, weight=1)

        self._build_toolbar(main)
        self._build_filter_bar(main)
        self._build_treeview(main)
        self._build_statusbar(main)

    # ── sidebar ───────────────────────────────────────────────────────────────

    def _sidebar_section(self, text: str):
        ctk.CTkLabel(self._sidebar, text=text, font=("Segoe UI", 10, "bold"),
                     text_color="#888888", anchor="w").pack(fill="x", padx=10, pady=(12, 2))

    def _sidebar_btn(self, text: str, command, indent=0) -> ctk.CTkButton:
        btn = ctk.CTkButton(
            self._sidebar, text=text, anchor="w",
            fg_color="transparent", hover_color="#3a3a3a",
            text_color=COLORS["fg"], font=("Segoe UI", 12),
            height=30, command=command,
        )
        btn.pack(fill="x", padx=(8 + indent, 8), pady=1)
        return btn

    def _set_active_nav(self, btn: ctk.CTkButton):
        if self._active_nav:
            try:
                self._active_nav.configure(fg_color="transparent")
            except Exception:
                pass
        self._active_nav = btn
        btn.configure(fg_color="#1f538d")

    def _refresh_project_sidebar(self):
        for w in self._sidebar.winfo_children():
            w.destroy()

        # ── New Project button ──
        ctk.CTkButton(
            self._sidebar, text="＋ New Project", height=34,
            font=FONTS["normal"], command=self._on_new_project
        ).pack(fill="x", padx=8, pady=(8, 4))

        # ── Projects section ──
        self._sidebar_section("PROJECTS")
        self._all_proj_btn = self._sidebar_btn(
            "📋  All Projects",
            lambda: self._on_nav_project(None, self._all_proj_btn)
        )

        conn = self.db.get_connection()
        try:
            rows = conn.execute(
                "SELECT id, name FROM projects ORDER BY created_at DESC"
            ).fetchall()
        except Exception:
            rows = []
        self._proj_btns: dict[int, ctk.CTkButton] = {}
        for r in rows:
            pid = r["id"]
            pname = r["name"]
            btn = self._sidebar_btn(
                f"  📁  {pname}",
                lambda p=pid, n=pname: self._on_nav_project_by_id(p),
                indent=8,
            )
            self._proj_btns[pid] = btn

        # ── Raw Data section ──
        self._sidebar_section("RAW DATA")
        for key in ("raw_products", "raw_price_history", "raw_sessions"):
            d = TABLES[key]
            btn = self._sidebar_btn(
                f"{d['icon']}  {d['label']}",
                lambda k=key: self._on_nav_table(k),
            )

        # ── Business section ──
        self._sidebar_section("BUSINESS")
        for key in ("projects", "project_products", "competitors",
                    "monitored_products", "price_observations", "report_runs"):
            d = TABLES[key]
            btn = self._sidebar_btn(
                f"{d['icon']}  {d['label']}",
                lambda k=key: self._on_nav_table(k),
            )

    # ── toolbar ───────────────────────────────────────────────────────────────

    def _build_toolbar(self, parent):
        tb = ctk.CTkFrame(parent, height=46, fg_color="#252526", corner_radius=0)
        tb.grid(row=0, column=0, sticky="ew")
        tb.grid_propagate(False)

        def btn(text, cmd, color=None):
            kw = {"fg_color": color} if color else {}
            ctk.CTkButton(tb, text=text, width=0, height=30,
                          font=("Segoe UI", 11), command=cmd, **kw).pack(
                side="left", padx=4, pady=8)

        btn("＋ Add Row", self._on_add_row)
        btn("✎ Edit Row", self._on_edit_row)
        btn("🗑 Delete Selected", self._on_delete_selected, COLORS["error"])
        btn("⊘ Clear Table", self._on_clear_table, "#8B4513")
        btn("⧉ Deduplicate", self._on_dedup)
        btn("📥 Import to Project", self._on_import_to_project, "#1f538d")
        btn("📊 Normalize", self._on_normalize)
        btn("✏ Edit AI Prompt", self._on_edit_prompt)
        btn("💾 Export Excel", self._on_export, COLORS["success"])
        btn("↺ Refresh", self._on_refresh)

        self._stats_lbl = ctk.CTkLabel(tb, text="", font=("Segoe UI", 10),
                                       text_color="#888888")
        self._stats_lbl.pack(side="right", padx=12)

    # ── filter bar ────────────────────────────────────────────────────────────

    def _build_filter_bar(self, parent):
        fb = ctk.CTkFrame(parent, fg_color="#1e1e1e", height=38, corner_radius=0)
        fb.grid(row=1, column=0, sticky="ew")
        fb.grid_propagate(False)

        ctk.CTkLabel(fb, text="🔍", font=("Segoe UI", 13)).pack(side="left", padx=(8, 2), pady=4)
        self._search_entry = ctk.CTkEntry(
            fb, textvariable=self._global_var,
            placeholder_text="Search all columns…",
            width=260, height=28, font=("Segoe UI", 11))
        self._search_entry.pack(side="left", padx=(0, 16), pady=5)

        # Per-column filters frame (populated dynamically)
        self._col_filter_frame = ctk.CTkFrame(fb, fg_color="transparent")
        self._col_filter_frame.pack(side="left", fill="x", expand=True)

    def _rebuild_col_filters(self, cols):
        for w in self._col_filter_frame.winfo_children():
            w.destroy()
        self._filter_vars = {}
        for key, header, width, filterable in cols:
            if not filterable or width == 0:
                continue
            var = tk.StringVar()
            var.trace_add("write", self._on_filter_change)
            self._filter_vars[key] = var
            cell = ctk.CTkFrame(self._col_filter_frame, fg_color="transparent")
            cell.pack(side="left", padx=3)
            ctk.CTkLabel(cell, text=header, font=("Segoe UI", 9),
                         text_color="#666666").pack(anchor="w")
            ctk.CTkEntry(cell, textvariable=var, width=max(40, min(width, 120)),
                         height=22, font=("Segoe UI", 10)).pack()

    # ── treeview ──────────────────────────────────────────────────────────────

    def _build_treeview(self, parent):
        tf = tk.Frame(parent, background="#2d2d2d")
        tf.grid(row=2, column=0, sticky="nsew")
        parent.grid_rowconfigure(2, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        self._tree = ttk.Treeview(tf, style="DB.Treeview",
                                  selectmode="extended", show="headings")
        vsb = ttk.Scrollbar(tf, orient="vertical", command=self._tree.yview)
        hsb = ttk.Scrollbar(tf, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tf.grid_rowconfigure(0, weight=1)
        tf.grid_columnconfigure(0, weight=1)

        # Tag styling
        self._tree.tag_configure("odd", background="#262626")
        self._tree.tag_configure("even", background="#2d2d2d")
        self._tree.tag_configure("irrelevant", foreground="#555555")

        self._tree.bind("<Double-1>", self._on_edit_row)
        self._tree.bind("<Delete>", lambda e: self._on_delete_selected())
        self._tree.bind("<Button-3>", self._show_context_menu)

    # ── status bar ────────────────────────────────────────────────────────────

    def _build_statusbar(self, parent):
        sb = ctk.CTkFrame(parent, height=26, fg_color="#1a1a1a", corner_radius=0)
        sb.grid(row=3, column=0, sticky="ew")
        sb.grid_propagate(False)
        self._status_lbl = ctk.CTkLabel(sb, text="Ready", font=("Segoe UI", 10),
                                        text_color="#666666", anchor="w")
        self._status_lbl.pack(side="left", padx=10)

    def _set_status(self, msg: str):
        try:
            self._status_lbl.configure(text=msg)
        except Exception:
            pass

    # ── navigation ────────────────────────────────────────────────────────────

    def _on_nav_table(self, key: str):
        self._load_table(key)

    def _on_nav_project(self, project_id: Optional[int], btn):
        self._current_project_id = project_id
        self._set_active_nav(btn)
        self._load_table(self._current_table)

    def _on_nav_project_by_id(self, project_id: int):
        self._current_project_id = project_id
        # Switch to project_products when clicking a project
        if self._current_table in ("raw_products", "raw_price_history", "raw_sessions"):
            self._load_table("project_products")
        else:
            self._load_table(self._current_table)

    # ── data loading ──────────────────────────────────────────────────────────

    def _load_table(self, key: str):
        if key not in TABLES:
            return
        self._current_table = key
        td = TABLES[key]
        cols = td["cols"]

        # Reconfigure treeview columns
        visible = [c for c in cols if c[2] > 0]
        col_ids = [c[0] for c in visible]
        self._col_keys = col_ids
        self._tree.configure(columns=col_ids)

        for key_c, header, width, _ in visible:
            self._tree.heading(
                key_c, text=header,
                command=lambda c=key_c: self._sort_column(c))
            self._tree.column(key_c, width=width, minwidth=30, stretch=(width > 150))

        self._rebuild_col_filters(cols)
        self._global_var.set("")
        self._sort_col = None
        self._sort_dir = 1
        self._fetch_and_display()

    def _fetch_and_display(self):
        td = TABLES[self._current_table]
        sql = td["sql"]
        params: list = []

        # Inject project filter if applicable
        proj_join = td.get("project_join")
        if proj_join and self._current_project_id is not None:
            low = sql.lower()
            
            # Find the best place to insert (before ORDER BY or LIMIT)
            insert_pos = len(sql)
            for marker in [" order by ", " limit "]:
                pos = low.find(marker)
                if pos != -1 and pos < insert_pos:
                    insert_pos = pos
            
            main_sql = sql[:insert_pos]
            suffix = sql[insert_pos:]
            
            if "where" in main_sql.lower():
                main_sql += f" AND {proj_join} = ?"
            else:
                main_sql += f" WHERE {proj_join} = ?"
            
            sql = main_sql + suffix
            params.append(self._current_project_id)

        try:
            conn = self.db.get_connection()
            rows = conn.execute(sql, params).fetchall()
            self._all_rows = [dict(r) for r in rows]
        except Exception as exc:
            logger.error("[DBPanel] Query error: %s", exc)
            self._all_rows = []
            self._set_status(f"Query error: {exc}")

        self._apply_filters()

    def _apply_filters(self, *_):
        global_q = self._global_var.get().lower().strip()
        col_filters = {k: v.get().lower().strip() for k, v in self._filter_vars.items() if v.get().strip()}

        result = []
        for row in self._all_rows:
            # Global search
            if global_q:
                combined = " ".join(str(v) for v in row.values() if v is not None).lower()
                if global_q not in combined:
                    continue
            # Per-column
            skip = False
            for col, fval in col_filters.items():
                cell = str(row.get(col, "") or "").lower()
                if fval not in cell:
                    skip = True
                    break
            if skip:
                continue
            result.append(row)

        # Sort
        if self._sort_col:
            try:
                result.sort(
                    key=lambda r: (r.get(self._sort_col) is None,
                                   str(r.get(self._sort_col, "") or "")),
                    reverse=(self._sort_dir == -1))
            except Exception:
                pass

        self._displayed_rows = result
        self._populate_treeview()

    def _populate_treeview(self):
        self._tree.delete(*self._tree.get_children())
        td = TABLES[self._current_table]
        visible_keys = self._col_keys

        for i, row in enumerate(self._displayed_rows):
            vals = [row.get(k, "") for k in visible_keys]
            tag = "odd" if i % 2 else "even"
            if row.get("rel") == "✗" or row.get("is_relevant") == 0:
                tag = "irrelevant"
            iid = str(row.get(td["pk"], i))
            self._tree.insert("", "end", iid=iid, values=vals, tags=(tag,))

        total = len(self._all_rows)
        shown = len(self._displayed_rows)
        table_label = TABLES[self._current_table]["label"]
        self._stats_lbl.configure(
            text=f"{table_label}  |  {shown} / {total} rows")
        self._set_status(f"Loaded {shown} rows" + (f" (filtered from {total})" if shown != total else ""))

    def _on_filter_change(self, *_):
        self.after(200, self._apply_filters)

    # ── sorting ───────────────────────────────────────────────────────────────

    def _sort_column(self, col: str):
        if self._sort_col == col:
            self._sort_dir = -1 if self._sort_dir == 1 else (0 if self._sort_dir == -1 else 1)
            if self._sort_dir == 0:
                self._sort_col = None
        else:
            self._sort_col = col
            self._sort_dir = 1

        # Update header text
        td = TABLES[self._current_table]
        for key_c, header, _, _ in td["cols"]:
            if key_c not in self._col_keys:
                continue
            indicator = ""
            if self._sort_col == key_c:
                indicator = " ▲" if self._sort_dir == 1 else " ▼"
            try:
                self._tree.heading(key_c, text=header + indicator)
            except Exception:
                pass

        self._apply_filters()

    # ── toolbar actions ───────────────────────────────────────────────────────

    def _on_new_project(self):
        self._load_table("projects")
        self._show_edit_form(row_data=None)

    def _on_add_row(self):
        td = TABLES[self._current_table]
        if not td.get("editable"):
            messagebox.showinfo("Read-only", "This table is read-only. Rows are created by the scraper.")
            return
        self._show_edit_form(row_data=None)

    def _on_edit_row(self, event=None):
        sel = self._tree.selection()
        if not sel:
            return
        td = TABLES[self._current_table]
        if not td.get("editable"):
            messagebox.showinfo("Read-only", "This table is read-only.")
            return
        pk = td["pk"]
        try:
            row_id = int(sel[0])
        except ValueError:
            return
        row_data = next((r for r in self._displayed_rows if str(r.get(pk)) == str(row_id)), None)
        if row_data:
            self._show_edit_form(row_data=row_data)

    def _on_delete_selected(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Nothing selected", "Select one or more rows first.")
            return
        td = TABLES[self._current_table]
        n = len(sel)
        if not messagebox.askyesno("Confirm Delete",
                                   f"Delete {n} selected row(s) from '{td['label']}'?\nThis cannot be undone."):
            return
        ids = []
        for iid in sel:
            try:
                ids.append(int(iid))
            except ValueError:
                pass
        try:
            deleted = self.repo.delete_rows(td["table"], td["pk"], ids)
            self._set_status(f"Deleted {deleted} row(s).")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
        self._fetch_and_display()

    def _on_clear_table(self):
        td = TABLES[self._current_table]
        if not messagebox.askyesno(
                "⚠ Clear Table",
                f"Delete ALL rows from '{td['label']}' ({td['table']})?\n\nThis cannot be undone!",
                icon="warning"):
            return
        try:
            n = self.repo.clear_table(td["table"])
            self._set_status(f"Cleared {n} rows from {td['table']}.")
            self._fetch_and_display()
            if td["section"] == "project":
                self._refresh_project_sidebar()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _on_dedup(self):
        if self._current_table != "raw_products":
            messagebox.showinfo("Info", "Deduplication is only for Discovered Products.")
            return
        n = self.repo.remove_duplicates()
        messagebox.showinfo("Deduplicate", f"Removed {n} duplicate URL(s).")
        self._fetch_and_display()

    def _on_import_to_project(self):
        """Import selected raw discovered products into a project as project_products."""
        if self._current_table != "raw_products":
            messagebox.showinfo("Info", "Select rows in Discovered Products to import.")
            return

        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Nothing selected", "Select one or more rows to import.")
            return

        # Pick a project
        try:
            conn = self.db.get_connection()
            proj_rows = conn.execute(
                "SELECT id, name FROM projects ORDER BY name"
            ).fetchall()
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        if not proj_rows:
            messagebox.showwarning("No Projects", "Create a project first in the sidebar.")
            return

        proj_names = [r["name"] for r in proj_rows]
        proj_dict  = {r["name"]: r["id"] for r in proj_rows}

        # Dialog: choose target project
        pick_win = ctk.CTkToplevel(self)
        pick_win.title("Import to Project")
        pick_win.geometry("360x180")
        pick_win.grab_set()
        pick_win.lift()

        ctk.CTkLabel(pick_win, text="Choose target project:",
                     font=FONTS["normal"]).pack(pady=(20, 8))
        proj_var = tk.StringVar(value=proj_names[0])
        ctk.CTkComboBox(pick_win, values=proj_names, variable=proj_var,
                        width=280).pack()

        result = {"go": False}

        def _do_import():
            result["go"] = True
            pick_win.destroy()

        btn_row = ctk.CTkFrame(pick_win, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=16)
        ctk.CTkButton(btn_row, text="Import", command=_do_import,
                      fg_color=COLORS["success"]).pack(side="left", expand=True, padx=(0, 4))
        ctk.CTkButton(btn_row, text="Cancel", command=pick_win.destroy,
                      fg_color=COLORS["sidebar"]).pack(side="left", expand=True)

        pick_win.wait_window()
        if not result["go"]:
            return

        project_id = proj_dict[proj_var.get()]
        now = datetime.now(timezone.utc).isoformat()

        # Gather selected rows
        pk = TABLES["raw_products"]["pk"]
        selected_ids = []
        for iid in sel:
            try:
                selected_ids.append(int(iid))
            except ValueError:
                pass

        if not selected_ids:
            return

        # Fetch full rows for selected IDs
        try:
            conn = self.db.get_connection()
            ph = ",".join("?" for _ in selected_ids)
            raw_rows = conn.execute(
                f"SELECT id, title, norm_brand, norm_model, norm_voltage, norm_capacity, "
                f"norm_category, marketplace, url, is_relevant "
                f"FROM products WHERE id IN ({ph})",
                selected_ids
            ).fetchall()
        except Exception as e:
            messagebox.showerror("Error fetching rows", str(e))
            return

        imported = 0
        skipped  = 0
        for r in raw_rows:
            try:
                conn.execute(
                    """INSERT INTO project_products
                       (project_id, title, brand, model, category, marketplace, product_url,
                        is_active, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
                    (
                        project_id,
                        r["title"],
                        r["norm_brand"] or "",
                        r["norm_model"] or "",
                        r["norm_category"] or "",
                        r["marketplace"],
                        r["url"] or "",
                        now, now,
                    )
                )
                imported += 1
            except Exception:
                skipped += 1  # likely a UNIQUE constraint on url

        conn.commit()
        msg = f"Imported {imported} product(s) into '{proj_var.get()}'."
        if skipped:
            msg += f"\n{skipped} skipped (already exist)."
        messagebox.showinfo("Import Complete", msg)
        self._refresh_project_sidebar()

    def _on_normalize(self):
        if self._current_table != "raw_products" or not self.scheduler:
            messagebox.showinfo("Info", "Normalization is only available for Discovered Products.")
            return
        self._set_status("AI Normalization running…")

        def work():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    self.scheduler.normalize_all_pending(stop_event=self.scheduler._stop_event))
            finally:
                loop.close()
            self.after(0, lambda: (self._fetch_and_display(),
                                   self._set_status("Normalization complete.")))

        threading.Thread(target=work, daemon=True).start()

    def _on_edit_prompt(self):
        """Open a window to view and edit the AI normalization prompt."""
        import yaml
        from pathlib import Path

        cfg_path = Path(__file__).resolve().parent.parent / "config.yaml"

        # Load current overrides (if any) from config.yaml
        try:
            cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        except Exception:
            cfg = {}

        gemini_cfg = cfg.get("gemini", {})

        # Default prompt template (mirrors normalizer.py logic)
        default_prompt = (
            "Original Search Query: '{query}'\n\n"
            "Analyze the following products and extract structured data. "
            "Check if they match the search query intent.\n"
            "IMPORTANT: Use the 'url' if the title is insufficient, as it often contains "
            "brand, voltage, and capacity in the slug.\n"
            "Rules:\n"
            "1. If 'Model' is not explicitly stated, use the descriptive text following "
            "the manufacturer/brand name as the model.\n"
            "2. Category (e.g. 'Battery LiFePO4').\n"
            "3. Extract Brand, Model, Voltage, Capacity.\n"
            "4. 12.8V is EQUIVALENT to 12V; 25.6V is EQUIVALENT to 24V.\n"
            "5. Be strict: if query asks for 100Ah and title says 150Ah, "
            "mark 'is_relevant': false.\n\n"
            'Return JSON. Format: { "products": [ { "id": 0, "is_relevant": ..., '
            '"brand": ..., "model": ..., "voltage": ..., "capacity": ..., '
            '"category": ... }, ... ] }\n'
            "Input Data: {data_json}"
        )
        default_system = "You are a product data specialist. Return ONLY valid JSON."

        current_prompt = gemini_cfg.get("norm_prompt", default_prompt)
        current_system = gemini_cfg.get("norm_system_prompt", default_system)

        # Build window
        win = ctk.CTkToplevel(self)
        win.title("Edit AI Normalization Prompt")
        win.geometry("900x700")
        win.grab_set()
        win.lift()

        ctk.CTkLabel(win, text="AI Normalization Prompt Editor",
                     font=FONTS["title"], text_color=COLORS["accent"]).pack(pady=(14, 4))
        ctk.CTkLabel(win, text="Use {query} and {data_json} as placeholders (inserted automatically).",
                     font=("Segoe UI", 10), text_color="#888888").pack(pady=(0, 8))

        # System prompt (single line)
        ctk.CTkLabel(win, text="System Prompt:", font=("Segoe UI", 11, "bold"),
                     anchor="w").pack(fill="x", padx=16)
        sys_entry = ctk.CTkEntry(win, font=("Consolas", 11))
        sys_entry.pack(fill="x", padx=16, pady=(2, 10))
        sys_entry.insert(0, current_system)

        # Main prompt (multiline)
        ctk.CTkLabel(win, text="Main Prompt Template:", font=("Segoe UI", 11, "bold"),
                     anchor="w").pack(fill="x", padx=16)
        prompt_box = ctk.CTkTextbox(win, font=("Consolas", 11), wrap="word")
        prompt_box.pack(fill="both", expand=True, padx=16, pady=(2, 8))
        prompt_box.insert("1.0", current_prompt)

        def _reset():
            prompt_box.delete("1.0", "end")
            prompt_box.insert("1.0", default_prompt)
            sys_entry.delete(0, "end")
            sys_entry.insert(0, default_system)

        def _save():
            new_prompt = prompt_box.get("1.0", "end").strip()
            new_system = sys_entry.get().strip()
            try:
                cfg.setdefault("gemini", {})
                cfg["gemini"]["norm_prompt"] = new_prompt
                cfg["gemini"]["norm_system_prompt"] = new_system
                import yaml
                cfg_path.write_text(
                    yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
                messagebox.showinfo("Saved", "Prompt saved to config.yaml.\n"
                                    "Changes apply to the next Normalize run.", parent=win)
                win.destroy()
            except Exception as e:
                messagebox.showerror("Save Error", str(e), parent=win)

        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=10)
        ctk.CTkButton(btn_row, text="💾 Save", command=_save,
                      fg_color=COLORS["success"]).pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_row, text="↺ Reset to Default", command=_reset,
                      fg_color="#555555").pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_row, text="Cancel", command=win.destroy,
                      fg_color=COLORS["sidebar"]).pack(side="left")

    def _on_export(self):
        if not self._displayed_rows:
            messagebox.showinfo("Empty", "Nothing to export.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            title="Export current view")
        if not path:
            return
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = TABLES[self._current_table]["label"][:30]

            # Header
            headers = [c[1] for c in TABLES[self._current_table]["cols"] if c[2] > 0]
            keys = self._col_keys
            ws.append(headers)

            for row in self._displayed_rows:
                ws.append([row.get(k, "") for k in keys])

            # Auto-width
            for col_cells in ws.columns:
                length = max(len(str(c.value or "")) for c in col_cells)
                ws.column_dimensions[col_cells[0].column_letter].width = min(length + 2, 60)

            wb.save(path)
            messagebox.showinfo("Exported", f"Saved {len(self._displayed_rows)} rows to:\n{path}")
        except Exception as exc:
            messagebox.showerror("Export error", str(exc))

    def _on_refresh(self):
        self._refresh_project_sidebar()
        self._fetch_and_display()
        self._set_status("Refreshed.")

    # ── context menu ──────────────────────────────────────────────────────────

    def _show_context_menu(self, event):
        item = self._tree.identify_row(event.y)
        if not item:
            return
        if item not in self._tree.selection():
            self._tree.selection_set(item)

        menu = tk.Menu(self, tearoff=0,
                       background="#2d2d2d", foreground="#cccccc",
                       activebackground="#1f538d", activeforeground="#ffffff")

        # URL actions if there's a url column
        row = next((r for r in self._displayed_rows
                    if str(r.get(TABLES[self._current_table]["pk"])) == item), None)
        url = (row or {}).get("url") or (row or {}).get("product_url") or \
              (row or {}).get("seller_url") or (row or {}).get("competitor_product_url") or \
              (row or {}).get("comp_url") or (row or {}).get("output_path")

        if url and url.startswith("http"):
            menu.add_command(label="🌐  Open URL", command=lambda: webbrowser.open(url))
            menu.add_command(label="📋  Copy URL", command=lambda: (
                self.clipboard_clear(), self.clipboard_append(url)))
            menu.add_separator()

        menu.add_command(label="✎  Edit Row", command=self._on_edit_row)
        menu.add_command(label="🗑  Delete Row", command=self._on_delete_selected)
        menu.tk_popup(event.x_root, event.y_root)

    # ── edit / add form ───────────────────────────────────────────────────────

    def _show_edit_form(self, row_data: Optional[dict]):
        td = TABLES[self._current_table]
        form_fields = td.get("form", [])
        is_new = row_data is None
        title = f"{'Add' if is_new else 'Edit'} — {td['label']}"

        win = ctk.CTkToplevel(self)
        win.title(title)
        win.geometry("480x560")
        win.grab_set()
        win.lift()

        # Title bar
        ctk.CTkLabel(win, text=title, font=FONTS["title"],
                     text_color=COLORS["accent"]).pack(pady=(16, 8))

        scroll = ctk.CTkScrollableFrame(win, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16, pady=4)

        widgets: dict[str, Any] = {}

        # Load list of projects for project_select fields
        projects_list: list[tuple[int, str]] = []
        try:
            conn = self.db.get_connection()
            rows = conn.execute("SELECT id, name FROM projects ORDER BY name").fetchall()
            projects_list = [(r["id"], r["name"]) for r in rows]
        except Exception:
            pass

        for field, label, ftype in form_fields:
            ctk.CTkLabel(scroll, text=label, font=("Segoe UI", 11),
                         anchor="w").pack(fill="x", pady=(6, 0))

            current_val = str(row_data.get(field, "") or "") if row_data else ""

            if ftype == "multiline":
                w = ctk.CTkTextbox(scroll, height=70, font=("Segoe UI", 11))
                w.pack(fill="x")
                if current_val:
                    w.insert("1.0", current_val)
                widgets[field] = ("text", w)

            elif ftype.startswith("select:"):
                choices = ftype.split(":")[1].split(",")
                var = tk.StringVar(value=current_val or choices[0])
                w = ctk.CTkComboBox(scroll, values=choices, variable=var, font=("Segoe UI", 11))
                w.pack(fill="x")
                widgets[field] = ("combovar", var)

            elif ftype == "project_select":
                choices = [f"{pid}  {pname}" for pid, pname in projects_list]
                var = tk.StringVar(value=current_val)
                # Try to match current value
                for pid, pname in projects_list:
                    if str(pid) == current_val:
                        var.set(f"{pid}  {pname}")
                        break
                w = ctk.CTkComboBox(scroll, values=choices or ["—"], variable=var,
                                    font=("Segoe UI", 11))
                w.pack(fill="x")
                widgets[field] = ("project_var", var)

            elif ftype == "bool":
                var = tk.BooleanVar(value=bool(int(current_val or 0)))
                w = ctk.CTkCheckBox(scroll, text="", variable=var)
                w.pack(anchor="w")
                widgets[field] = ("boolvar", var)

            elif ftype == "number":
                var = tk.StringVar(value=current_val)
                w = ctk.CTkEntry(scroll, textvariable=var, font=("Segoe UI", 11))
                w.pack(fill="x")
                widgets[field] = ("strvar", var)

            else:  # text
                var = tk.StringVar(value=current_val)
                w = ctk.CTkEntry(scroll, textvariable=var, font=("Segoe UI", 11))
                w.pack(fill="x")
                widgets[field] = ("strvar", var)

        # Buttons
        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=12)

        def _collect() -> dict:
            data = {}
            for f, (wtype, w) in widgets.items():
                if wtype == "text":
                    data[f] = w.get("1.0", "end").strip()
                elif wtype in ("combovar", "strvar"):
                    data[f] = w.get()
                elif wtype == "project_var":
                    raw = w.get()
                    data[f] = int(raw.split()[0]) if raw and raw[0].isdigit() else None
                elif wtype == "boolvar":
                    data[f] = 1 if w.get() else 0
            return data

        def _save():
            data = _collect()
            now = datetime.now(timezone.utc).isoformat()
            try:
                conn = self.db.get_connection()
                if is_new:
                    # Build INSERT
                    data["created_at"] = now
                    if "updated_at" in [f for f, _, _ in form_fields]:
                        data["updated_at"] = now
                    cols_sql = ", ".join(data.keys())
                    phs = ", ".join("?" for _ in data)
                    conn.execute(f"INSERT INTO {td['table']} ({cols_sql}) VALUES ({phs})",
                                 list(data.values()))
                else:
                    # Build UPDATE
                    if "updated_at" in [f for f, _, _ in form_fields]:
                        data["updated_at"] = now
                    set_sql = ", ".join(f"{k}=?" for k in data)
                    vals = list(data.values()) + [row_data[td["pk"]]]
                    conn.execute(f"UPDATE {td['table']} SET {set_sql} WHERE {td['pk']}=?", vals)
                conn.commit()
                win.destroy()
                if td["section"] == "project":
                    self._refresh_project_sidebar()
                self._fetch_and_display()
            except Exception as exc:
                messagebox.showerror("Save error", str(exc), parent=win)

        ctk.CTkButton(btn_row, text="Save", command=_save,
                      fg_color=COLORS["success"]).pack(side="left", expand=True, padx=(0, 4))
        ctk.CTkButton(btn_row, text="Cancel", command=win.destroy,
                      fg_color=COLORS["sidebar"]).pack(side="left", expand=True, padx=(4, 0))
