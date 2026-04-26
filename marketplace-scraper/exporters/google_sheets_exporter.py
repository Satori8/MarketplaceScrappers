import json
from typing import List
from datetime import datetime

try:
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError:
    gspread = None

from exporters.base_exporter import BaseExporter
from core.models import RawProduct

class GoogleSheetsExporter(BaseExporter):
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self._load_config()

    def _load_config(self):
        import yaml
        from pathlib import Path
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f)
                gs_cfg = cfg.get("google_sheets", {})
                self.credentials_path = gs_cfg.get("credentials_path", "credentials/google_service_account.json")
                self.spreadsheet_id = gs_cfg.get("spreadsheet_id", "")
        except Exception:
            self.credentials_path = "credentials/google_service_account.json"
            self.spreadsheet_id = ""

    def export(self, products: List[RawProduct], filename: str = "") -> str:
        if not gspread:
            raise ImportError("gspread and google-auth are required for Google Sheets export.")
        
        if not self.spreadsheet_id:
            raise ValueError("Google Spreadsheet ID is not configured in config.yaml.")

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        try:
            creds = Credentials.from_service_account_file(self.credentials_path, scopes=scopes)
            client = gspread.authorize(creds)
            sh = client.open_by_key(self.spreadsheet_id)
            ws = sh.get_worksheet(0) # Use first sheet
        except Exception as e:
            raise RuntimeError(f"Failed to connect to Google Sheets: {e}")

        # Prepare data
        headers = ["Marketplace", "Title", "Price", "Availability", "URL", "Last Scraped"]
        rows = [headers]
        for p in products:
            rows.append([
                p.marketplace,
                p.title,
                p.price,
                p.availability or "N/A",
                p.url,
                p.scraped_at.strftime("%Y-%m-%d %H:%M:%S") if p.scraped_at else "N/A"
            ])

        # Overwrite or append? 
        # For simplicity in v1.0, we'll append or clear/rewrite.
        # Let's clear and rewrite to ensure the sheet has the latest search results.
        ws.clear()
        ws.update(rows, "A1")
        
        return f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}"
