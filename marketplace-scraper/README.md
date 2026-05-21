# 🛒 Ukrainian Marketplace Scraper

> **Internal production tool** for generating market intelligence reports across major Ukrainian e-commerce platforms.

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![SQLite](https://img.shields.io/badge/Database-SQLite3%20WAL-lightgrey)](https://sqlite.org)
[![Status](https://img.shields.io/badge/Stage-Phase%203.3%20Data%20Integrity-green)]()

---

## 📌 Overview

This tool scrapes product data from **Rozetka, Prom.ua, Allo, Epicentrk, and Hotline**, normalizes it into a unified schema, and stores it in a local SQLite database. A built-in Tkinter GUI provides full project/client management, snapshot comparison, and Excel report export.

**Core workflow:**
```
Select Client → Configure Task (Search / URL) → Scrape → DB Control Panel → Export Report
```

---

## 🏗️ Architecture

### Supported Marketplaces

| Marketplace | Extraction Method | Notes |
|---|---|---|
| **Rozetka** | GraphQL + API + LD+JSON | Multi-source with client-state fallback |
| **Prom.ua** | GraphQL (Apollo) | External query templates in `prom_queries.json` |
| **Allo** | AJAX API + ExecJS/Nuxt SSR | Lightweight AJAX with `_DEEPLINK_CACHE` |
| **Epicentrk** | Stateless REST API (v1/v2) | Fully API-driven |
| **Hotline** | HTML + BeautifulSoup4 | BS4-based parsing |

### Key Modules

```
marketplace-scraper/
├── main.py                          # Entry point
├── gui/
│   ├── main_window.py               # Main GUI (search, URL, task controls)
│   ├── db_browser_window.py         # DB Control Panel (Treeview + sidebar)
│   └── panels/
│       └── details_panel.py         # Inline detail view (product attrs & snapshot scope)
├── scrapers/
│   └── mapi_scraper/
│       ├── __init__.py              # Public API: scrape(), async_scrape()
│       ├── base.py                  # MarketplaceModule protocol
│       ├── http.py                  # curl_cffi HTTP layer + debug logging
│       ├── paginator.py             # Cross-marketplace pagination
│       ├── prom_queries.json        # Externalized Prom GQL query templates
│       └── sites/
│           ├── rozetka.py
│           ├── prom.py
│           ├── allo.py
│           ├── epicentr.py
│           └── hotline.py
├── core/
│   ├── scheduler.py                 # TaskScheduler + availability parsing
│   └── cache.py
├── db/
│   ├── database.py                  # SQLite connection pool (WAL, FK ON)
│   ├── product_repo.py              # CRUD operations
│   └── migrations.py               # Schema migrations
├── reports/
│   └── snapshot_report.py           # Excel report generation (openpyxl)
└── ai/
    └── schema_generator.py          # Gemini AI normalization pipeline
```

---

## 🗄️ Database Schema (v3.0)

### Business Layer (CRM & Monitoring)
| Table | Description |
|---|---|
| `clients` | Root entity — customer or internal organization |
| `tasks` | Scraping tasks per client (`discovery` or `tracking`) with query params |
| `snapshots` | Immutable point-in-time scrape results |
| `snapshot_products` | Products captured per snapshot, with `attributes` and `extra` JSON |

### Raw Scrape Layer
| Table | Description |
|---|---|
| `all_products` | Raw discovery results across all runs |
| `scrape_log` | Metadata per parser run |

---

## 🖥️ GUI Features

- **Sidebar navigation**: Clients → Tasks → Snapshots → Products drill-down
- **Snapshots view**: `Mode` column (discovery/tracking) + inline Details panel showing scope params
- **Details panel**: Shows query scope (queries, marketplaces, run settings) for snapshots; attributes/extra/image for products
- **Excel export**: Multi-sheet comparison reports with KPIs and price charts
- **AI normalize**: Gemini-powered batch normalization for product data
- **Snapshot Diff**: Side-by-side comparison between two snapshots

---

## ⚙️ Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.10+ |
| HTTP / TLS | `curl_cffi` (`chrome110` impersonation) |
| SSR JS eval | `execjs` + Node.js |
| GUI | `tkinter` + `customtkinter` |
| Database | SQLite3 (WAL mode, FK enforced) |
| Reports | `openpyxl` |
| AI | Google Gemini API |

---

## 🚀 Getting Started

```powershell
# 1. Clone and enter project
cd D:\Scrappers\marketplace-scraper

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy and configure environment
copy .env.example .env
# Set GEMINI_API_KEY in .env

# 5. Launch
python main.py
```

> **Note**: Node.js must be available on PATH for Allo Nuxt/SSR fallback processing.

---

## 📋 Requirements

- Python 3.10+
- Node.js (for `execjs` / Allo SSR fallback)
- Windows (tested on Windows 10/11)

---

## 📊 Current Status

**Phase 3.3 — Data Integrity Refinement**  
Last updated: 2026-05-21

### Recent changes
- ✅ **DB Viewer**: Snapshot `Mode` column + Details panel shows scope/params on row select
- ✅ **Allo**: Category fallback to last breadcrumb title when category is `None`
- ✅ **Prom**: `isDisabled: true` treated as out-of-stock in availability checks
- ✅ **Availability parsing**: Unified case-insensitive `parse_availability_to_code` helper
- ✅ **Debug mode**: Human-readable timestamps for run result directories

See [CHANGELOG.md](CHANGELOG.md) for full history.
