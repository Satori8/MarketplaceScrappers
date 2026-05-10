import customtkinter as ctk

# Custom Palette for specific accents
COLORS = {
    "bg": "#1e1e1e",
    "fg": "#ffffff",
    "sidebar": "#252526",
    "accent": "#1f538d", # CTk Blue-ish
    "table_bg": "#2d2d2d",
    "table_fg": "#cccccc",
    "success": "#2ecc71",
    "error": "#e74c3c",
    "warning": "#f1c40f",
}

FONTS = {
    "title": ("Segoe UI", 14, "bold"),
    "normal": ("Segoe UI", 12),
    "small": ("Segoe UI", 10),
    "mono": ("Consolas", 11),
}

def apply_styles():
    """Initializes CustomTkinter global settings and Treeview Styles."""
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    from tkinter import ttk
    style = ttk.Style()
    style.theme_use("default")
    
    # Configure Treeview colors
    style.configure("Treeview", 
        background=COLORS["table_bg"],
        foreground=COLORS["fg"],
        fieldbackground=COLORS["table_bg"],
        rowheight=26,
        borderwidth=0,
        font=FONTS["small"]
    )
    style.map("Treeview", background=[("selected", COLORS["accent"])])
    
    # Header style
    style.configure("Treeview.Heading",
        background="#353535",
        foreground=COLORS["fg"],
        relief="flat",
        font=FONTS["small"]
    )
    style.map("Treeview.Heading", background=[("active", "#404040")])
