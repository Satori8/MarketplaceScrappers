import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime, timezone
from typing import Optional, Any

from gui.styles import COLORS, FONTS

class EditFormDialog:
    def __init__(self, master, db, table_config: dict, row_data: Optional[dict], on_saved_callback):
        self.master = master
        self.db = db
        self.td = table_config
        self.row_data = row_data
        self.on_saved_callback = on_saved_callback

    def show(self):
        form_fields = self.td.get("form", [])
        is_new = self.row_data is None
        title = f"{'Add' if is_new else 'Edit'} - {self.td['label']}"

        win = ctk.CTkToplevel(self.master)
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

        # Load list of clients for client_select fields
        clients_list: list[tuple[int, str]] = []
        try:
            conn = self.db.get_connection()
            rows = conn.execute("SELECT id, name FROM clients ORDER BY name").fetchall()
            clients_list = [(r["id"], r["name"]) for r in rows]
        except Exception:
            pass

        for field, label, ftype in form_fields:
            ctk.CTkLabel(scroll, text=label, font=("Segoe UI", 11),
                         anchor="w").pack(fill="x", pady=(6, 0))

            current_val = str(self.row_data.get(field, "") or "") if self.row_data else ""

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
            elif ftype == "client_select":
                choices = [f"{pid}  {pname}" for pid, pname in clients_list]
                var = tk.StringVar(value=current_val)
                for pid, pname in clients_list:
                    if str(pid) == current_val:
                        var.set(f"{pid}  {pname}")
                        break
                w = ctk.CTkComboBox(scroll, values=choices or ["-"], variable=var, font=("Segoe UI", 11))
                w.pack(fill="x")
                widgets[field] = ("client_var", var)

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
                elif wtype == "client_var":
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
                    conn.execute(f"INSERT INTO {self.td['table']} ({cols_sql}) VALUES ({phs})",
                                 list(data.values()))
                else:
                    # Build UPDATE
                    if "updated_at" in [f for f, _, _ in form_fields]:
                        data["updated_at"] = now
                    set_sql = ", ".join(f"{k}=?" for k in data)
                    vals = list(data.values()) + [self.row_data[self.td["pk"]]]
                    conn.execute(f"UPDATE {self.td['table']} SET {set_sql} WHERE {self.td['pk']}=?", vals)
                conn.commit()
                win.destroy()
                if self.on_saved_callback:
                    self.on_saved_callback(self.td["section"] == "project")
            except Exception as exc:
                messagebox.showerror("Save error", str(exc), parent=win)

        ctk.CTkButton(btn_row, text="Save", command=_save,
                      fg_color=COLORS["success"]).pack(side="left", expand=True, padx=(0, 4))
        ctk.CTkButton(btn_row, text="Cancel", command=win.destroy,
                      fg_color=COLORS["sidebar"]).pack(side="left", expand=True, padx=(4, 0))
