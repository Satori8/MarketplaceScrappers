# Marketplace Scraper — Project Documentation

## Project status
Current stage: 15 — Business Intelligence Layer & Project-Rooted Workflows ✅ (Phase 1 Complete)
Last updated: 2026-05-09 21:10

---

## Strategic Goal (from Obsidian vault — Projects/Parser)

This is an **internal production tool** for generating **market intelligence reports**:
- Project-based management of client catalogs.
- Automated price monitoring of specific competitors.
- Selling intelligence: Excel reports, Price Audits, and AI summaries.

**Workflow:**
```
Select Project → Set Mode (Search/Category/Seller/Update) → Scrape → DB Control Panel → Export Report
```

---

## Architecture Overview — Refactored

### Entry Point
- `main.py` → `gui/main_window.py` (MainWindow)

### Core Components
- **Project Selection**: All operations are now rooted in an `active_project_id`.
- **Parsing Modes**:
  1. **Search**: Keyword discovery at scale.
  2. **Filter/Category**: Deep parse of specific marketplace category URLs.
  3. **Seller/Store**: Extraction of full product lists from specific sellers.
  4. **Price Update**: High-priority re-scraping of `monitored_products` for the active project.
- **Database Control Panel** (`gui/db_browser_window.py`):
  - Sidebar-driven navigation (Projects vs Raw Data vs Business Layer).
  - Advanced Treeview: Click-to-sort, multi-select delete, keyword + per-column filters.
  - Modal form system for adding/editing business data.

---

## File Map (Updated Phase 1)

| File | Status | Notes |
|------|--------|-------|
| `gui/main_window.py` | ✅ | Refactored with Project selector & 4 parsing modes. |
| `gui/db_browser_window.py` | ✅ | Fully rewritten as a Database Control Panel. |
| `db/product_repo.py` | ✅ | Added `delete_rows`, `clear_table`, and `remove_duplicates`. |
| `db/migrations.py` | ✅ | Managed migration for 7 new business tables. |
| `db/database.py` | ✅ | PRAGMA foreign_keys=ON; WAL mode enabled. |
| `scrapers/rozetka.py` | ✅ | Stabilized subdomain parsing & high-precision stock detection. |
| `scrapers/epicentrk.py` | ✅ | Modernized with high-precision Ad/Stock markers & early exit. |
| `prom.md` | ✅ | Documentation for Prom.ua extraction logic & stock markers. |

---

## Bug Audit — 2026-05-09 (Post-Refactor)

### ✅ Fixed

| ID | Location | Fix summary |
|----|----------|-------------|
| B1–B23 | Various | See previous audit. All critical stabilization bugs resolved. |
| B24 | `db_browser_window.py` | SQL Syntax error: Project filter now injected correctly before `ORDER BY`. |
| B25 | `product_repo.py` | IntegrityError: Deletion and Clearing now manually handle legacy non-cascading dependencies. |
| B26 | `rozetka.py` | Stabilized Subdomain Parsing: Discovered 32 products on `auto.rozetka.com.ua` using JS Deep Heuristic Discovery. |
| B27 | `prom.py`, `rozetka.py`, `allo.py`, `epicentrk.py`| High-Precision Filtering: Implemented custom ad-blockers and stock detection (Реклама / Немає в наявності). |
| B28 | `main_window.py` | Added "Skip Out of Stock" global filter checkbox (active by default). |
| B29 | Core Scrapers | Early Exit Optimization: Scrapers now stop pagination immediately upon hitting the first OutOfStock item. |
| B30 | `epicentrk.py`, `hotline.py`| Fixed `TypeError` by harmonizing `search_products` signatures to accept `skip_out_of_stock`. |
| B31 | `main_window.py` | GUI Fix: "Pages" spinbox now visible and respected for Filter and Seller URL modes. |
| B32 | `prom.py` | Fixed indentation error and missing `try` block in Playwright loop. |

### ⚠️ Remaining / Low priority

| ID | Location | Status |
|----|----------|--------|
| — | `scrapers/m_ua.py` | Empty stub — m.ua scraper not implemented. |
| — | Report Engine | `report_runs` table exists, but core Excel report generator (Phase 5) logic is pending. |

---

## Database Schema (v2.0 — Full Business Layer)

### Raw Scrape Layer (Discovery)
- `products`: Raw discovery results.
- `price_history`: Log of every price seen during discovery.
- `scrape_sessions`: Metadata for every LAUNCH AGENTS run.

### Business Layer (CRM & Monitoring)
- `projects`: The root entity. All business data belongs to a project.
- `project_products`: The client's own product catalog.
- `competitors`: Defined sellers/shops to be watched.
- `monitored_products`: Specific URL-to-URL links between a `project_product` and a `competitor`.
- `price_observations`: Clean, historical price data specifically for monitored items (used for reports).
- `report_runs`: History of generated Excel/PDF intelligence reports.

---

## Implementation Roadmap (Updated)

### Phase 0 — Stabilize Scraper ✅ (Complete)

### Phase 1 — Business Database Layer ✅ (Complete)
- [x] Create Projects, Competitors, and Monitoring tables.
- [x] Integrate Project Selector in Main UI.
- [x] Implement Full Database Control Panel (CRUD).
- [x] Handle FK constraints for cleanup.

### Phase 2 — Client Product Catalog ⏳ (Next)
- [ ] Implement "Import from Excel" for `project_products`.
- [ ] Add batch matching: auto-link `products` (discovery) to `project_products` (catalog) via AI.

### Phase 3 — Competitor Monitoring Set ⏳
- [ ] UI to quickly add `monitored_products` from the Discovery tab.

### Phase 4 — Automated Price Updates ⏳
- [ ] Refine the "Update Price Watchlist" mode to handle massive lists via background queue.

### Phase 5 — Price Audit Report ⏳ (First Sellable Output)
- [ ] Implement the Excel Report Engine to generate competitive analysis workbooks.
