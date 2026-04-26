import tkinter as tk
import customtkinter as ctk

class DirectUrlsWindow(ctk.CTkToplevel):
    def __init__(self, master, current_urls: list[str], on_save: callable):
        super().__init__(master)
        self.master = master
        self.on_save = on_save 
        self.title("Target Link Manager")
        self.geometry("700x550")
        
        self.result_urls = current_urls
        self._setup_ui()
        self.grab_set()
        self.after(10, self.lift)
        self.focus_force()

    def _setup_ui(self):
        self.main_frame = ctk.CTkFrame(self, corner_radius=0)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(self.main_frame, text="Direct Marketplace URLs", font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 5))
        ctk.CTkLabel(self.main_frame, text="Enter one URL per line. These will bypass the discovery phase.", font=("Segoe UI", 11), text_color="gray").pack(anchor="w", pady=(0, 15))
        
        self.txt = ctk.CTkTextbox(self.main_frame, font=("Consolas", 12), border_width=1)
        self.txt.pack(fill="both", expand=True, pady=(0, 20))
        
        # Load current
        if self.result_urls:
            self.txt.insert("1.0", "\n".join(self.result_urls))

        self.btn_poly = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.btn_poly.pack(fill="x")
        
        ctk.CTkButton(self.btn_poly, text="SAVE LINKS", command=self._on_save, height=35).pack(side="right", padx=5)
        ctk.CTkButton(self.btn_poly, text="CANCEL", command=self.destroy, height=35, fg_color="gray").pack(side="right")

    def _on_save(self):
        raw = self.txt.get("1.0", "end").split("\n")
        self.result_urls = [line.strip() for line in raw if line.strip() and line.strip().startswith("http")]
        if self.on_save:
            self.on_save(self.result_urls)
        self.destroy()
