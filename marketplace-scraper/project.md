# Marketplace Scraper — Project Documentation

### Project status
Current stage: Phase 2.5 — Modular Async MAPI Scraper Architecture ✅ (Stable)
Next stage: Phase 3 — Global Intelligence Phase (Gemini Normalization)
Last updated: 2026-05-15 (Standardized availability labels across all marketplaces)

---

## Strategic Goal (from Obsidian vault — Projects/Parser)

This is an **internal production tool** for generating **market intelligence reports**:
- Project-based management of client catalogs.
- Automated price monitoring of specific competitors.
- Selling intelligence: Excel reports, Price Audits, and AI summaries.

**Workflow:**
```
Select Project → Set Mode (Search/Category/Seller/Update) → Scrape (via Marketpalce API Scraper + Browser Fallbacks) → DB Control Panel → Export Report
```

---

## Tech Stack & Frameworks

- **Core Language:** Python 3
- **MAPI Extraction API (Current Standard):**
  - `curl_cffi` (For TLS impersonation `chrome110` to bypass Cloudflare/WAF checks).
  - `execjs` / Node.js (For evaluating SSR JS/Nuxt states, notably used for extracting state from `Allo`).
- **Legacy/Fallback Scrapers:** Playwright / Selenium (used primarily when MAPI fails or as a stealth harvester).
- **GUI Framework:** `Tkinter` (Python standard library using custom Treeviews and sidebars for the internal app).
- **Database:** SQLite3 with `sqlite3` driver. Foreign keys (PRAGMA foreign_keys=ON) enabled, WAL mode active.
- **Normalization Engine:** Modular `normalize` methods within site-specific modules and legacy `scrapers/mapi_scraper/normalizer.py`.

---

## Architecture Overview & File Map (Agent Guide)

This section serves as a map for any coding AI agent entering the project to quickly bootstrap development.

### 1. The Core GUI (Entry Point)
- **`main.py`** -> Loads the Tkinter app.
- **`gui/main_window.py` (MainWindow):**
  Features Project Selector (`active_project_id`) and 4 parsing modes: Search, Filter/Category, Seller/Store, Price Update.
- **`gui/db_browser_window.py`:**
  Database Control Panel. Includes Treeview for exploring Business Database Layer (Projects, Competitors, Raw Data). Has modal form systems for modifying CRM data.

### 2. Marketplace API (MAPI) Layer (`scrapers/mapi_scraper/`)
Refactored from a monolithic `mapi_scraper.py` into a modular package. 
- **`__init__.py`**: Public API. Exposes `scrape(...)`, `async_scrape(...)`, and `async_scrape_url_auto(...)`. Registry of all site-specific modules.
- **`base.py`**: Defines `MarketplaceModule` protocol and `BaseModule` mixin for standardization.
- **`http.py`**: Shared HTTP layer using `curl_cffi`, common headers, and integrated structured logging.
- **`extractors.py`**: Shared utility functions for HTML extraction (LD+JSON, JS assignments, scripts by ID).
- **`paginator.py`**: Logic for URL-based pagination across different marketplaces.
- **`sites/`**: Site-specific implementations:
  - `rozetka.py`: Multi-source extraction (GraphQL, API, LD+JSON, client-state).
  - `prom.py`: GraphQL-first extraction with Apollo Cache fallback.
  - `allo.py`: ExecJS-based Nuxt state processing.
  - `epicentr.py`: Stateless API interaction (v1/v2).
  - `hotline.py`: BS4-based HTML parsing.

### 3. Normalization Engine
All raw data from APIs/SSR maps into a strict common schema before database ingestion.
- Site-specific modules implement a `normalize(raw_data)` method to map site-specific JSON to standard keys: `id`, `sku`, `price`, `name`, `avail_code`, `merchant_name`, `url`, and `properties[]`.

### 4. Persistence & Database Layer (`db/`)
- **`db/database.py`**: Database connection pooling, PRAGMA config, execution helpers.
- **`db/product_repo.py`**: Core CRUD operations. Exposes functions like `delete_rows`, `remove_duplicates`, and pagination logic.
- **`db/schema_manager.py` / `db/migrations.py`:** Manages DB tables and structure.

---

## Database Schema (v2.0 — Full Business Layer)

### Raw Scrape Layer (Discovery)
- `products`: Raw discovery results.
- `price_history`: Log of every price seen during discovery.
- `scrape_sessions`: Metadata for every parser run.

### Business Layer (CRM & Monitoring)
- `projects`: The root entity. All business data organically belongs to an `active_project_id`.
- `project_products`: The client's own product catalog.
- `competitors`: Defined sellers/shops to be watched.
- `monitored_products`: Specific URL-to-URL links between a `project_product` and a `competitor`.
- `price_observations`: Clean, historical price data specifically meant for reporting.
- `report_runs`: Log of Excel/PDF reports generated as final output.

---

## Stabilization Notes & Current Edge Cases
- **Modular Refactor**: As of 2026-05-14, the scraper is fully modular. Site logic resides in `sites/`.
- **Async Pagination Stability**: As of 2026-05-15, resolved identified anomalies (Rozetka loops, Allo duplicate pages, Rozetka subdomain redirects, and Producer endpoint fixes) by implementing explicit page injection, subdomain redirect handling, and specialized producer API logic.
- **Stateless Epicentr**: Epicentr logic is now fully API-driven and stateless, bypassing previous SSR/session issues.
- **Prom GraphQL**: Prom.ua uses direct GraphQL queries for speed and reliability.
- **Allo Lightweight API**: As of 2026-05-15, Allo relies on a direct AJAX API following an initial SSR discovery fetch. In-memory `_DEEPLINK_CACHE` is used for pagination speed, drastically reducing Node/execjs dependency overhead.
- **MAPI Dependency**: Still reliant on Node.js availability to process Nuxt object injections using `execjs` when lightweight discovery fails. Ensure Node is on the PATH for Windows hosts.
