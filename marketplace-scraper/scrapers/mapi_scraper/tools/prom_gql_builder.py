import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext
import json
import os
import re
try:
    import pyperclip
except ImportError:
    pyperclip = None
import asyncio
import time
from curl_cffi import requests

# Paths
BASE_DIR = os.path.dirname(__file__)
QUERIES_FILE = os.path.join(BASE_DIR, "prom_queries.json")
PRESETS_FILE = os.path.join(BASE_DIR, "prom_presets.json")
GQL_URL = "https://prom.ua/graphql"

DEFAULT_HEADERS = {
    "content-type": "application/json",
    "x-language": "uk",
    "x-requested-with": "XMLHttpRequest",
    "referer": "https://prom.ua/",
    "origin": "https://prom.ua",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

def load_queries():
    if os.path.exists(QUERIES_FILE):
        with open(QUERIES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {} # Fallback

QUERIES = load_queries()

class ImportDialog(simpledialog.Dialog):
    def body(self, master):
        ttk.Label(master, text="Paste JSON or CURL:").pack(pady=5)
        self.text = scrolledtext.ScrolledText(master, width=100, height=30, font=("Consolas", 10)); self.text.pack(fill=tk.BOTH, expand=True)
        return self.text
    def apply(self): self.result = self.text.get("1.0", tk.END).strip()

class GQLBuilderApp:
    def __init__(self, root):
        self.root = root; self.root.title("Prom.ua GQL Master Builder"); self.root.geometry("1750x950")
        self.current_op = tk.StringVar(value="CategoryListingQuery"); self.current_preset = tk.StringVar(value="Default")
        self.available_fields = {op: dict(config["fields"]) for op, config in QUERIES.items()}
        self.field_vars, self.presets = {}, self.load_presets()
        self.setup_ui(); self.refresh_ui()

    def load_presets(self):
        if os.path.exists(PRESETS_FILE):
            try:
                with open(PRESETS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for op, op_presets in data.items():
                        if op in self.available_fields:
                            for p_name, p_data in op_presets.items():
                                for f_name in p_data.get("fields", {}):
                                    if f_name not in self.available_fields[op]: self.available_fields[op][f_name] = False
                    return data
            except: pass
        return {}
    def save_presets(self):
        with open(PRESETS_FILE, 'w', encoding='utf-8') as f: json.dump(self.presets, f, indent=2, ensure_ascii=False)

    def setup_ui(self):
        ctrl = ttk.LabelFrame(self.root, text=" 1. Structure ", padding=10); ctrl.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        ttk.Label(ctrl, text="Operation:").pack(anchor=tk.W)
        self.op_combo = ttk.Combobox(ctrl, values=list(QUERIES.keys()), textvariable=self.current_op, state="readonly"); self.op_combo.pack(fill=tk.X, pady=5); self.op_combo.bind("<<ComboboxSelected>>", self.on_op_change)
        ttk.Label(ctrl, text="Preset:").pack(anchor=tk.W, pady=(5,0))
        self.preset_combo = ttk.Combobox(ctrl, textvariable=self.current_preset, state="readonly"); self.preset_combo.pack(fill=tk.X, pady=5); self.preset_combo.bind("<<ComboboxSelected>>", self.on_preset_change); self.update_preset_list()
        
        btn_row = ttk.Frame(ctrl); btn_row.pack(fill=tk.X, pady=5)
        ttk.Button(btn_row, text="Sync from Editor", command=self.sync_from_editor).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(btn_row, text="Del Preset", command=self.delete_current_preset).pack(side=tk.LEFT)
        
        ttk.Separator(ctrl).pack(fill=tk.X, pady=10); af = ttk.Frame(ctrl); af.pack(fill=tk.X, pady=5)
        self.new_field_var = tk.StringVar(); ttk.Entry(af, textvariable=self.new_field_var).pack(side=tk.LEFT, fill=tk.X, expand=True); ttk.Button(af, text="+", width=3, command=self.add_custom_field).pack(side=tk.LEFT)
        fc = ttk.Frame(ctrl); fc.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(fc, highlightthickness=0, width=500); sb = ttk.Scrollbar(fc, orient="vertical", command=self.canvas.yview)
        self.sf = ttk.Frame(self.canvas); self.sf.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.sf, anchor="nw"); self.canvas.configure(yscrollcommand=sb.set); self.canvas.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y"); self.build_field_checkboxes()
        
        ttk.Button(ctrl, text="Import (CURL/JSON)", command=self.import_raw_data).pack(fill=tk.X, pady=2)
        ttk.Button(ctrl, text="Save to Queries", command=self.save_to_standard_queries).pack(fill=tk.X, pady=2)
        ttk.Button(ctrl, text="Restore Defaults", command=self.reset_defaults).pack(fill=tk.X, pady=2)
        ttk.Button(ctrl, text="Save As Preset", command=self.save_current_as_preset).pack(fill=tk.X, pady=2)
        
        edit = ttk.LabelFrame(self.root, text=" 2. Editor ", padding=10); edit.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.query_text = tk.Text(edit, height=35, font=("Consolas", 10), wrap="none", undo=True); self.query_text.pack(fill=tk.BOTH, expand=True, pady=5)
        self.vars_text = tk.Text(edit, height=12, font=("Consolas", 10), undo=True); self.vars_text.pack(fill=tk.X, pady=5)

        res = ttk.LabelFrame(self.root, text=" 3. Execution ", padding=10); res.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        bf = ttk.Frame(res); bf.pack(fill=tk.X, pady=5)
        ttk.Button(bf, text="Run Request", command=self.run_request).pack(side=tk.LEFT, padx=5); ttk.Button(bf, text="Copy CURL", command=self.copy_curl).pack(side=tk.LEFT, padx=5); ttk.Button(bf, text="Copy GQL JSON", command=self.copy_json_payload).pack(side=tk.LEFT, padx=5); ttk.Button(bf, text="Apply Changes", command=self.apply_checkboxes).pack(side=tk.LEFT, padx=5)
        mf = ttk.Frame(res); mf.pack(fill=tk.X, pady=5); self.meta_label = ttk.Label(mf, text="Status: N/A", font=("Segoe UI", 9, "bold")); self.meta_label.pack(side=tk.LEFT)
        self.resp_text = scrolledtext.ScrolledText(res, font=("Consolas", 10), bg="#f8f8f8"); self.resp_text.pack(fill=tk.BOTH, expand=True, pady=5)

    def refresh_ui(self):
        op = self.current_op.get(); self.vars_text.delete("1.0", tk.END); self.vars_text.insert(tk.END, json.dumps(QUERIES[op]["vars"], indent=2, ensure_ascii=False)); self.apply_checkboxes()

    def add_custom_field(self, fn=None, ch=True):
        f = fn or self.new_field_var.get().strip(); op = self.current_op.get()
        if f and f not in self.available_fields[op]: self.available_fields[op][f] = ch; self.build_field_checkboxes(); self.new_field_var.set("")

    def delete_field(self, f):
        op = self.current_op.get()
        if f in self.available_fields[op]: del self.available_fields[op][f]
        self.build_field_checkboxes(); self.apply_checkboxes()

    def save_to_standard_queries(self):
        op = self.current_op.get()
        prompt = simpledialog.askstring("Save Operation", f"Operation name (can be new):", initialvalue=op)
        if not prompt: return
        op = prompt

        query = self.query_text.get("1.0", tk.END).strip()
        try: variables = json.loads(self.vars_text.get("1.0", tk.END).strip())
        except: variables = {}

        # Autodetect Signature
        sig_match = re.search(r'query\s+\w+\s*(\([^)]+\))', query)
        sig = sig_match.group(1) if sig_match else ""

        # Autodetect Root
        root_m = re.search(r'{\s*([^\s{]+(?:\([^)]+\))?)', query.split('{', 1)[1] if '{' in query else "")
        root = root_m.group(1).strip() if root_m else ""

        # Build fields mapping
        fields_state = {f: var.get() for f, var in self.field_vars.items()}
        
        new_config = {"root": root, "vars": variables, "fields": fields_state, "sig": sig}
        
        # If complex, save as template
        if "fragment" in query or query.count('{') > 5:
            sel = [f for f, v in fields_state.items() if v]
            if sel:
                fs = "\n      "+"\n      ".join(sel) if "Listing" in op else "\n    "+"\n    ".join(sel)
                new_config["template"] = query.replace(fs, "{FIELDS}")
            else: new_config["template"] = query
        
        global QUERIES
        QUERIES[op] = new_config
        with open(QUERIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(QUERIES, f, indent=2, ensure_ascii=False)
        
        self.op_combo['values'] = list(QUERIES.keys())
        self.current_op.set(op)
        messagebox.showinfo("Success", f"Query saved as standard operation '{op}'")

    def sync_from_editor(self):
        q = self.query_text.get("1.0", tk.END).strip(); op = self.current_op.get()
        # Find target block (product or filters)
        sk = "filters" if "Filters" in op else ("product" if "Listing" in op else QUERIES[op]["root"].split('(')[0].split(':')[-1].strip())
        m = re.search(r'\b' + re.escape(sk) + r'\s*\{', q)
        if not m: messagebox.showwarning("Sync", f"Block '{sk}' not found."); return
        
        sp, lvl, c = m.end()-1, 0, ""
        for i in range(sp, len(q)):
            ch = q[i]; c += ch
            if ch == '{': lvl += 1
            elif ch == '}': lvl -= 1
            if lvl == 0: break
            
        inner = c[1:-1].strip(); fs, cur, l, p = set(), "", 0, 0
        for ch in inner:
            if ch == '{': l += 1
            elif ch == '}': l -= 1
            elif ch == '(': p += 1
            elif ch == ')': p -= 1
            if ch == '\n' and l == 0 and p == 0:
                f = cur.strip(); (fs.add(f) if f and f != "__typename" else None); cur = ""
            else: cur += ch
        f = cur.strip(); (fs.add(f) if f and f != "__typename" else None)

        for ex_f in list(self.available_fields[op].keys()): self.available_fields[op][ex_f] = (ex_f in fs)
        for nw_f in fs: 
            if nw_f not in self.available_fields[op]: self.available_fields[op][nw_f] = True
        self.build_field_checkboxes(); messagebox.showinfo("Sync", "Done.")

    def import_raw_data(self):
        d = ImportDialog(self.root, "Import GQL")
        if d.result:
            try: p = json.loads(d.result)
            except:
                m = re.search(r'--data-raw\s*[\'"]({.*?})[\'"]', d.result) or re.search(r'"body":\s*[\'"](\{.*?\})[\'"]', d.result)
                try: p = json.loads(m.group(1).replace('\\"', '"').replace('\\n', '\n'))
                except: p = None
            if p:
                op = p.get("operationName"); (self.current_op.set(op) if op in QUERIES else None); self.query_text.delete("1.0", tk.END); self.query_text.insert(tk.END, p.get("query",""))
                self.vars_text.delete("1.0", tk.END); self.vars_text.insert(tk.END, json.dumps(p.get("variables",{}), indent=2, ensure_ascii=False)); self.sync_from_editor()

    def build_field_checkboxes(self, states=None):
        for w in self.sf.winfo_children(): w.destroy()
        op = self.current_op.get(); self.field_vars = {}; defs = QUERIES[op]["fields"].keys()
        for f in sorted(self.available_fields[op].keys(), key=lambda x: (x not in defs, x.lower())):
            v = states.get(f, False) if states else self.available_fields[op][f]; var = tk.BooleanVar(value=v); self.field_vars[f] = var
            r = ttk.Frame(self.sf); r.pack(fill=tk.X, pady=1)
            ttk.Button(r, text="Г—", width=2, command=lambda x=f: self.delete_field(x)).pack(side=tk.LEFT, padx=(5, 2))
            ttk.Checkbutton(r, text=f, variable=var, command=self.on_checkbox_toggle).pack(side=tk.LEFT, fill=tk.X, expand=True)

    def on_checkbox_toggle(self):
        op = self.current_op.get()
        for f, v in self.field_vars.items(): self.available_fields[op][f] = v.get()
        self.apply_checkboxes()

    def delete_current_preset(self):
        op, n = self.current_op.get(), self.current_preset.get()
        if n != "Default" and messagebox.askyesno("Del", f"Delete '{n}'?"): del self.presets[op][n]; self.save_presets(); self.update_preset_list(); self.reset_defaults()

    def update_preset_list(self): op = self.current_op.get(); self.preset_combo['values'] = ["Default"] + list(self.presets.get(op, {}).keys())

    def save_current_as_preset(self):
        n = simpledialog.askstring("Save", "Name:"); op = self.current_op.get()
        if n and n != "Default":
            if op not in self.presets: self.presets[op] = {}
            try: v = json.loads(self.vars_text.get("1.0", tk.END).strip())
            except: v = QUERIES[op]["vars"]
            self.presets[op][n] = {"vars":v, "fields":{f:v.get() for f,v in self.field_vars.items()}}; self.save_presets(); self.update_preset_list(); self.current_preset.set(n)

    def on_preset_change(self, e):
        op, n = self.current_op.get(), self.current_preset.get()
        if n == "Default": self.reset_defaults(); return
        p = self.presets.get(op, {}).get(n)
        if p:
            for fn in p.get("fields",{}): self.available_fields[op][fn] = False
            self.available_fields[op].update(p.get("fields",{}))
            self.build_field_checkboxes(); self.vars_text.delete("1.0", tk.END); self.vars_text.insert(tk.END, json.dumps(p.get("vars",{}), indent=2, ensure_ascii=False)); self.apply_checkboxes()

    def reset_defaults(self): op = self.current_op.get(); self.current_preset.set("Default"); self.available_fields[op] = dict(QUERIES[op]["fields"]); self.build_field_checkboxes(); self.refresh_ui()

    def on_op_change(self, e): self.current_preset.set("Default"); self.update_preset_list(); self.reset_defaults()

    def apply_checkboxes(self):
        op = self.current_op.get(); config = QUERIES[op]; sel = [f for f, v in self.available_fields[op].items() if v]
        fs = "\n".join(["      "+f for f in (sel or ["id"])]) if "Listing" in op else "\n".join(["    "+f for f in (sel or ["id"])])
        if "template" in config: q = config["template"].replace("{FIELDS}", fs)
        elif "Listing" in op: q = f"query {op}{config['sig']} {{\n  {config['root']} {{\n    page {{\n      total\n      products {{\n        product {{\n{fs}\n        }}\n      }}\n    }}\n  }}\n}}"
        else: q = f"query {op}{config['sig']} {{\n  {config['root']} {{\n{fs}\n  }}\n}}"
        self.query_text.delete("1.0", tk.END); self.query_text.insert(tk.END, q.strip())

    def get_payload(self):
        try: return {"operationName": self.current_op.get(), "variables": json.loads(self.vars_text.get("1.0", tk.END).strip()), "query": self.query_text.get("1.0", tk.END).strip()}
        except Exception as e: messagebox.showerror("Err", f"JSON Err: {e}"); return None

    def copy_curl(self):
        p = self.get_payload(); (pyperclip.copy(f'curl "{GQL_URL}" -X POST {" ".join([f"-H \"{k}: {v}\"" for k,v in DEFAULT_HEADERS.items()])} --data-raw {json.dumps(json.dumps(p, ensure_ascii=False))}') if p and pyperclip else None)

    def copy_json_payload(self):
        p = self.get_payload(); (pyperclip.copy(json.dumps(p, indent=2, ensure_ascii=False)) if p and pyperclip else None)

    def run_request(self):
        p = self.get_payload()
        if p:
            self.resp_text.delete("1.0", tk.END); self.resp_text.insert(tk.END, "Loading..."); self.meta_label.config(text="Status: Loading..."); self.root.update()
            async def run():
                try: return requests.post(GQL_URL, json=p, headers=DEFAULT_HEADERS, impersonate="chrome124")
                except Exception as e: return e
            res = asyncio.new_event_loop().run_until_complete(run()); self.meta_label.config(text=f"Status: {getattr(res, 'status_code', 'ERR')}"); self.resp_text.delete("1.0", tk.END)
            try: self.resp_text.insert(tk.END, json.dumps(res.json(), indent=2, ensure_ascii=False))
            except: self.resp_text.insert(tk.END, str(res))

if __name__ == "__main__": root = tk.Tk(); GQLBuilderApp(root); root.mainloop()
