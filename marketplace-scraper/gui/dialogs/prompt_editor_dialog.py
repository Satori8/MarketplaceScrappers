import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox

from gui.styles import COLORS, FONTS

class PromptEditorDialog:
    def __init__(self, master):
        self.master = master

    def show(self):
        import yaml
        from pathlib import Path

        cfg_path = Path(__file__).resolve().parent.parent.parent / "config.yaml"

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
        win = ctk.CTkToplevel(self.master)
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
        ctk.CTkButton(btn_row, text="↶ Reset to Default", command=_reset,
                      fg_color="#555555").pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_row, text="Cancel", command=win.destroy,
                      fg_color=COLORS["sidebar"]).pack(side="left")
