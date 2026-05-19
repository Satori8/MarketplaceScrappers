import tkinter as tk
import customtkinter as ctk
from tkinter import ttk, messagebox
from typing import List

from gui.styles import COLORS, FONTS

class DiffPanel(ctk.CTkToplevel):
    def __init__(self, master, db, s1: int, s2: int):
        super().__init__(master)
        self.db = db
        self.s1 = s1
        self.s2 = s2
        
        self.title(f"Diff: Snapshots {s1} vs {s2}")
        self.geometry("1200x700")
        
        # Diff Tree
        cols = [
            ("status", "Status", 100), ("name", "Name", 350), 
            ("prev", "Prev Price", 100), ("curr", "Curr Price", 100),
            ("delta", "Delta", 90), ("url", "URL", 250)
        ]
        self.tree = ttk.Treeview(self, columns=[c[0] for c in cols], show="headings")
        for cid, heading, width in cols:
            self.tree.heading(cid, text=heading)
            self.tree.column(cid, width=width)
        
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.tree.tag_configure("NEW", background="#1c3d25", foreground="#ffffff")
        self.tree.tag_configure("CHANGED", background="#3d3d1c", foreground="#ffffff")
        self.tree.tag_configure("GONE", background="#4a2222", foreground="#ffffff")
        self.tree.tag_configure("UNCHANGED", foreground="#888888")

        self.load_data()

    def load_data(self):
        conn = self.db.get_connection()
        p1 = conn.execute("SELECT * FROM snapshot_products WHERE snapshot_id = ?", (self.s1,)).fetchall()
        p2 = conn.execute("SELECT * FROM snapshot_products WHERE snapshot_id = ?", (self.s2,)).fetchall()

        def index_prods(rows):
            idx = {}
            for r in rows:
                k = r["url"] or r["name"]
                idx[k] = r
            return idx

        idx1 = index_prods(p1)
        idx2 = index_prods(p2)

        diffs = []
        
        for k, r2 in idx2.items():
            p2_val = r2["price"] or 0
            if k not in idx1:
                diffs.append(("NEW", r2["name"], "", p2_val, "", r2["url"]))
            else:
                r1 = idx1[k]
                p1_val = r1["price"] or 0
                if p1_val != p2_val:
                    delta = p2_val - p1_val
                    diffs.append(("CHANGED", r2["name"], p1_val, p2_val, f"{delta:+.2f}", r2["url"]))
                else:
                    diffs.append(("UNCHANGED", r2["name"], p1_val, p2_val, "0.00", r2["url"]))
        
        for k, r1 in idx1.items():
            if k not in idx2:
                diffs.append(("GONE", r1["name"], r1["price"], "", "", r1["url"]))
                
        for d in diffs:
            self.tree.insert("", "end", values=d, tags=(d[0],))

    def show(self):
        self.grab_set()
        self.lift()
