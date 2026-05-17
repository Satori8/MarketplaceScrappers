# Marketplace Scraper — Project Documentation

### Project status
Current stage: Phase 2.18 — Data Directory Consolidation & Path Robustness
Next stage: Phase 3 — Global Intelligence Phase (Gemini Normalization)
Last updated: 2026-05-18 (Updated README to reflect BI Layer and Reporting Engine progress)

---

## Strategic Goal (from Obsidian vault — Projects/Parser)

This is an **internal production tool** for generating **market intelligence reports**:
- Project-based management of client catalogs.
- Automated price monitoring of specific competitors.
- Selling intelligence: Excel reports, Price Audits, and AI summaries.

**Workflow:**
```
Select Project → Set Mode (Search/URL) → Scrape (via Marketplace API Scraper) → DB Control Panel → Export Report
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
  Features Project Selector (`active_project_id`) and 2 primary parsing modes: Search, Target URL (with modal paste).
- **`gui/db_browser_window.py`:**
  Database Control Panel. Includes Treeview for exploring Business Database Layer (Projects, Competitors, Raw Data). Has modal form systems for modifying CRM data.

### 2. Marketplace API (MAPI) Layer (`scrapers/mapi_scraper/`)
Refactored from a monolithic `mapi_scraper.py` into a modular package. 
- **`AGENT_GUIDE.md`**: Comprehensive developer guide for the MAPI module (Architecture, API, Templates).
- **`__init__.py`**: Public API. Exposes `scrape(...)`, `async_scrape(...)`, and `async_scrape_url_auto(...)`. Registry of all site-specific modules.
- **`base.py`**: Defines `MarketplaceModule` protocol and `BaseModule` mixin for standardization.
- **`http.py`**: Shared HTTP layer using `curl_cffi`, common headers, and integrated structured logging.
- **`extractors.py`**: Shared utility functions for HTML extraction (LD+JSON, JS assignments, scripts by ID).
- **`paginator.py`**: Logic for URL-based pagination across different marketplaces.
- **`sites/`**: Site-specific implementations:
  - `rozetka.py`: Multi-source extraction (GraphQL, API, LD+JSON, client-state). See `MAPI_ROZETKA_QUERY_MAP.md`.
  - `prom.py`: GraphQL-first extraction with Apollo Cache fallback. See `prom_graph.ql` (Master GQL Spec).
  - `allo.py`: ExecJS-based Nuxt state processing. See `MAPI_ALLO_QUERY_MAP.md`.
  - `epicentr.py`: Stateless API interaction (v1/v2). See `MAPI_EPICENTR_QUERY_MAP.md`.
  - `hotline.py`: BS4-based HTML parsing.

### 3. Normalization Engine
All raw data from APIs/SSR maps into a strict common schema before database ingestion.
- Site-specific modules implement a `normalize(raw_data)` method to map site-specific JSON to standard keys: `id`, `sku`, `price`, `name`, `avail_code`, `merchant_name`, `url`, and `properties[]`.

### 4. Persistence & Database Layer (`db/`)
- **`db/database.py`**: Database connection pooling, PRAGMA config, execution helpers.
- **`db/product_repo.py`**: Core CRUD operations. Exposes functions like `delete_rows`, `remove_duplicates`, and pagination logic.
- **`db/schema_manager.py` / `db/migrations.py`:** Manages DB tables and structure.

### 5. Reporting Engine (`reports/`)
- **`reports/snapshot_report.py`**: logic to generate professional, multi-sheet Excel (.xlsx) comparison reports. Features KPIs, price dynamics analysis, and line charts using `openpyxl`. Integrates directly with the DB Browser's snapshot selection.

### 6. Standalone Utilities (`scrapers/prom_contact_scraper/`)
- A specialized scraping tool designed to extract seller contact details (email, phones) from Prom.ua category listings.
- Features robust pagination, additive thread-local SQLite schemas (`prom_contacts` and `prom_crawl_progress`), resume/stop logic, and a standalone GUI (`gui.py`) disconnected from the main app.

---

## Database Schema (v2.0 — Full Business Layer)

### Raw Scrape Layer (Discovery)
- `products`: Raw discovery results.
- `price_history`: Log of every price seen during discovery.
- `scrape_sessions`: Metadata for every parser run.

### Business Layer (CRM & Monitoring)
- `clients`: The root entity representing a customer or internal organization.
- `tasks`: Specific parsing/monitoring tasks belonging to a client (e.g. tracking or discovery) holding querying logic.
- `snapshots`: Immutable points-in-time holding a snapshot of the parsed layout.
- `snapshot_products`: The specific products that matched the task query during a snapshot execution, mapped back to the raw source data.

---

## Stabilization Notes & Current Edge Cases
- **Modular Refactor**: As of 2026-05-14, the scraper is fully modular. Site logic resides in `sites/`.
- **Async Pagination Stability**: As of 2026-05-15, resolved identified anomalies (Rozetka loops, Allo duplicate pages, Rozetka subdomain redirects, and Producer endpoint fixes) by implementing explicit page injection, subdomain redirect handling, and specialized producer API logic.
- **Stateless Epicentr**: Epicentr logic is now fully API-driven and stateless, bypassing previous SSR/session issues.
- **Prom GraphQL**: Prom.ua uses direct GraphQL queries for speed and reliability. Detailed API structure and documentation added in `scrapers/mapi_scraper/prom_graph.ql`.
- **Allo Lightweight API**: As of 2026-05-15, Allo relies on a direct AJAX API following an initial SSR discovery fetch. In-memory `_DEEPLINK_CACHE` is used for pagination speed, drastically reducing Node/execjs dependency overhead.
- **MAPI Debug Mode**: As of 2026-05-16, implemented full debug flag propagation from GUI to Scraper Engines. Raw JSON responses and normalized results are now persisted to `scrapers/mapi_scraper/results/` when the debug checkbox is enabled.
- **Epicentr Merchant Accuracy**: Refined Epicentr normalization to correctly identify marketplace vs. first-party sellers using the `seller` field and improved category path extraction via `sectionsUa`.
- **MAPI Dependency**: Still reliant on Node.js availability to process Nuxt object injections using `execjs` when lightweight discovery fails. Ensure Node is on the PATH for Windows hosts.
