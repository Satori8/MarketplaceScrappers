import json
import tkinter as tk
import webbrowser
import customtkinter as ctk
from gui.styles import COLORS, FONTS

class DetailsPanel(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, height=170, corner_radius=0, fg_color="#1e1e1e")
        self.grid_propagate(False)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=3)
        self.rowconfigure(0, weight=1)

        self.left_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        self.right_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        
        self.is_visible = False

    # ─────────────────────────── helpers ─────────────────────────────────────

    def _label(self, parent, text, bold=False, color=None, wrap=0):
        font = ("Segoe UI", 11, "bold") if bold else ("Segoe UI", 11)
        kw = {"text_color": color} if color else {}
        lbl = ctk.CTkLabel(parent, text=text, font=font, anchor="w", wraplength=wrap, **kw)
        lbl.pack(anchor="w")
        return lbl

    def _section(self, parent, title):
        self._label(parent, title, bold=True, color=COLORS["accent"])

    def _kv(self, parent, key, val, val_color=None):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", anchor="w", pady=1)
        ctk.CTkLabel(row, text=f"{key}:", font=("Segoe UI", 11, "bold"),
                     text_color="#888888", width=130, anchor="w").pack(side="left")
        ctk.CTkLabel(row, text=str(val) if val is not None else "—",
                     font=("Segoe UI", 11), text_color=val_color or COLORS["fg"],
                     anchor="w", wraplength=400).pack(side="left", fill="x", expand=True)

    # ─────────────────────────── public API ──────────────────────────────────

    def show(self, row_data: dict):
        if not row_data:
            self.hide()
            return

        self.grid(row=3, column=0, sticky="ew")
        self.is_visible = True

        for w in self.left_frame.winfo_children():
            w.destroy()
        for w in self.right_frame.winfo_children():
            w.destroy()

        # ── Determine mode: snapshot row vs. product row ──────────────────
        has_scope = "scope" in row_data
        if has_scope:
            self._render_snapshot(row_data)
        else:
            self._render_product(row_data)

        self.update_idletasks()

    # ─────────────────────────── snapshot view ───────────────────────────────

    def _render_snapshot(self, row_data: dict):
        scope_raw = row_data.get("scope")
        if not scope_raw:
            self._section(self.left_frame, "Scope / Params")
            self._label(self.left_frame, "No params stored for this snapshot.", color="#888888")
            return

        try:
            params = json.loads(scope_raw)
        except Exception:
            self._section(self.left_frame, "Scope / Params (raw)")
            self._label(self.left_frame, str(scope_raw), color=COLORS["fg"])
            return

        # ── Left: search targets ──────────────────────────────────────────
        self._section(self.left_frame, "Scope / Params")

        queries = params.get("queries", [])
        if queries:
            self._label(self.left_frame, "Queries:", bold=True, color="#888888")
            for q in queries:
                self._label(self.left_frame, f"  • {q}", color=COLORS["fg"])

        mps = params.get("marketplaces", [])
        if mps:
            self._kv(self.left_frame, "Marketplaces", ", ".join(mps))

        # ── Right: run settings ───────────────────────────────────────────
        self._section(self.right_frame, "Run Settings")

        setting_keys = [
            ("pages",       "Pages"),
            ("threads",     "Threads"),
            ("delay",       "Delay (s)"),
            ("skip_stock",  "Skip In-Stock"),
            ("task_type",   "Task Type"),
        ]
        for field, label in setting_keys:
            val = params.get(field)
            if val is not None:
                self._kv(self.right_frame, label, val)

        # Any extra keys not yet shown
        shown = {"queries", "marketplaces", "pages", "threads", "delay", "skip_stock", "task_type"}
        extras = {k: v for k, v in params.items() if k not in shown}
        if extras:
            self._label(self.right_frame, "Other:", bold=True, color="#888888")
            for k, v in extras.items():
                self._kv(self.right_frame, k, v)

    # ─────────────────────────── product view ────────────────────────────────

    def _render_product(self, row_data: dict):
        # Left: attributes
        self._section(self.left_frame, "Attributes")

        attributes = row_data.get("attributes")
        if attributes:
            try:
                attrs = json.loads(attributes)
                if isinstance(attrs, dict):
                    for k, v in attrs.items():
                        self._kv(self.left_frame, k, v)
                elif isinstance(attrs, list):
                    for attr in attrs:
                        self._label(self.left_frame, f"• {attr}", color=COLORS["fg"])
                else:
                    self._label(self.left_frame, str(attrs), color=COLORS["fg"])
            except Exception:
                self._label(self.left_frame, str(attributes), color=COLORS["fg"])
        else:
            self._label(self.left_frame, "No attributes available.", color="#888888")

        # Right: extra + image
        self._section(self.right_frame, "Additional Data")

        extra = row_data.get("extra")
        if extra:
            if isinstance(extra, str) and (extra.startswith("{") or extra.startswith("[")):
                try:
                    parsed = json.loads(extra)
                    if isinstance(parsed, dict):
                        for k, v in parsed.items():
                            self._kv(self.right_frame, k, v)
                    else:
                        self._label(self.right_frame, str(parsed), color=COLORS["fg"])
                except Exception:
                    self._label(self.right_frame, str(extra), color=COLORS["fg"])
            else:
                self._label(self.right_frame, str(extra), color=COLORS["fg"])

        img_url = row_data.get("image")
        if img_url:
            self._label(self.right_frame, "Product Image:", bold=True, color="#888888")
            lbl = ctk.CTkLabel(self.right_frame, text=img_url, font=("Segoe UI", 11),
                               text_color="#8ab4f8", cursor="hand2", anchor="w")
            lbl.pack(anchor="w")
            lbl.bind("<Button-1>", lambda e, url=img_url: webbrowser.open(url))

    def hide(self):
        self.grid_remove()
        self.is_visible = False
