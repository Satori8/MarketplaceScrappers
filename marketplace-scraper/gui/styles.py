import customtkinter as ctk

# Custom Palette for specific accents
COLORS = {
    "bg": "#1e1e1e",
    "fg": "#ffffff",
    "sidebar": "#252526",
    "accent": "#1f538d", # CTk Blue-ish
    "table_bg": "#2d2d2d",
    "table_fg": "#cccccc",
    "success": "#27ae60",
    "error": "#e74c3c",
    "warning": "#f1c40f",
}

FONTS = {
    "title": ("Segoe UI", 14, "bold"),
    "normal": ("Segoe UI", 12),
    "small": ("Segoe UI", 10),
    "mono": ("Consolas", 11),
}

class AutohideScrollbar(ctk.CTkScrollbar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pack_data = None
        self._grid_data = None

    def pack(self, **kwargs):
        self._pack_data = kwargs
        super().pack(**kwargs)

    def grid(self, **kwargs):
        self._grid_data = kwargs
        super().grid(**kwargs)

    def set(self, start, end):
        if float(start) <= 0.0 and float(end) >= 1.0:
            if self.winfo_manager() == "pack": self.pack_forget()
            elif self.winfo_manager() == "grid": self.grid_remove()
        else:
            if not self.winfo_manager():
                if self._pack_data is not None:
                    super().pack(**self._pack_data)
                elif self._grid_data is not None:
                    super().grid(**self._grid_data)
        super().set(start, end)

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
