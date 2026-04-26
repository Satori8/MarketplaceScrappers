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
    """Initializes CustomTkinter global settings."""
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
