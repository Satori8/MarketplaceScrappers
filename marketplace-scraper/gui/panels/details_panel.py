import json
import tkinter as tk
import webbrowser
import customtkinter as ctk
from gui.styles import COLORS, FONTS

class DetailsPanel(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, height=150, corner_radius=0, fg_color="#1e1e1e")
        self.grid_propagate(False)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=3)
        self.rowconfigure(0, weight=1)

        self.left_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        self.right_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        
        self.is_visible = False

    def show(self, row_data: dict):
        if not row_data:
            self.hide()
            return

        self.grid(row=3, column=0, sticky="ew")
        self.is_visible = True
        
        for w in self.left_frame.winfo_children(): w.destroy()
        for w in self.right_frame.winfo_children(): w.destroy()
        
        ctk.CTkLabel(self.left_frame, text="Attributes", font=("Segoe UI", 12, "bold"), text_color=COLORS["accent"]).pack(anchor="w")
        
        attributes = row_data.get("attributes")
        if attributes:
            try:
                attrs = json.loads(attributes)
                if isinstance(attrs, dict):
                    for k, v in attrs.items():
                        ctk.CTkLabel(self.left_frame, text=f"• {k}: {v}", font=("Segoe UI", 11), text_color=COLORS["fg"]).pack(anchor="w")
                elif isinstance(attrs, list):
                    for attr in attrs:
                        ctk.CTkLabel(self.left_frame, text=f"• {attr}", font=("Segoe UI", 11), text_color=COLORS["fg"]).pack(anchor="w")
                else:
                    ctk.CTkLabel(self.left_frame, text=str(attrs), font=("Segoe UI", 11), text_color=COLORS["fg"]).pack(anchor="w")
            except Exception:
                ctk.CTkLabel(self.left_frame, text=str(attributes), font=("Segoe UI", 11), text_color=COLORS["fg"]).pack(anchor="w")
        else:
            ctk.CTkLabel(self.left_frame, text="No attributes available.", font=("Segoe UI", 10), text_color="#888888").pack(anchor="w")

        ctk.CTkLabel(self.right_frame, text="Additional Data", font=("Segoe UI", 12, "bold"), text_color=COLORS["accent"]).pack(anchor="w")
        
        for key in ["extra"]:
            val = row_data.get(key)
            if not val:
                continue
            
            ctk.CTkLabel(self.right_frame, text=key.capitalize(), font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(5, 0))
            if isinstance(val, str) and (val.startswith("{") or val.startswith("[")):
                try:
                    parsed = json.loads(val)
                    if isinstance(parsed, dict):
                        for k, v in parsed.items():
                            ctk.CTkLabel(self.right_frame, text=f"{k}: {v}", font=("Segoe UI", 11), text_color=COLORS["fg"]).pack(anchor="w")
                    else:
                        ctk.CTkLabel(self.right_frame, text=str(parsed), font=("Segoe UI", 11), text_color=COLORS["fg"]).pack(anchor="w")
                except Exception:
                    ctk.CTkLabel(self.right_frame, text=str(val), font=("Segoe UI", 11), text_color=COLORS["fg"]).pack(anchor="w")
            else:
                ctk.CTkLabel(self.right_frame, text=str(val), font=("Segoe UI", 11), text_color=COLORS["fg"]).pack(anchor="w")
                
        img_url = row_data.get("image")
        if img_url:
            ctk.CTkLabel(self.right_frame, text="Product Image: ", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(5, 0))
            lbl = ctk.CTkLabel(self.right_frame, text=img_url, font=("Segoe UI", 11), text_color="#8ab4f8", cursor="hand2")
            lbl.pack(anchor="w")
            lbl.bind("<Button-1>", lambda e, url=img_url: webbrowser.open(url))
            
        self.update_idletasks()

    def hide(self):
        self.grid_remove()
        self.is_visible = False
