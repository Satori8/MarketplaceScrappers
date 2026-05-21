## 2026-05-21 — DB Viewer: Snapshot Mode Column + Details Panel Scope View
### Done
- **`gui/db_browser_window.py`**: Added `t.task_type as mode` to the Snapshots SQL query. Replaced the wide `Scope (Params)` column (300px) with a compact `Mode` column (100px, filterable). The `scope` field (query_params JSON) is now fetched with `width=0` (hidden from treeview) and passed to the Details panel.
- **`gui/db_browser_window.py`**: Extended `_on_tree_select` to also trigger the Details panel for the `snapshots` table (previously only `all_products` and `snapshot_products` showed details).
- **`gui/panels/details_panel.py`**: Refactored `DetailsPanel` with a branching renderer: `_render_snapshot()` parses and displays the `scope` (query_params JSON) in a two-column layout showing Queries list and Marketplaces on the left, Run Settings (pages, threads, delay, skip_stock) on the right. `_render_product()` retains the existing attributes/extra/image display logic. Added helper methods `_label()`, `_section()`, `_kv()` for clean, consistent label rendering.
### Not done / deferred
- Snapshot Details tab-style split (currently inline panel at bottom, not a tabbed widget)
### Notes
- Scope data (query_params) is still fetched from DB for every snapshot row — just not rendered in the treeview column. Zero performance regression.

---

## 2026-05-20 — Allo Category Breadcrumb Fallback
### Done
- **Allo Scraper**: Updated `scrapers/mapi_scraper/sites/allo.py` in `AlloAPI.normalize` to check and fallback to the last breadcrumb item's `title` or `label` if the parsed `category_name` is `None` or empty.
- **Lightweight AJAX Scrape integration**: Modified the `_scrape_impl` method in `AlloModule` to pass the AJAX response `breadcrumbs` into the simulated `raw__allo` state so that `normalize` has access to the full breadcrumbs array when performing lightweight scrapes.
- **Unit Testing**: Created a dedicated automated test suite in `tests/test_allo_fallback.py` to verify the category fallback functionality against mock data structure variations.
### Notes
- Verified all new and existing tests pass successfully.

---

## 2026-05-20 — Prom isDisabled Availability Support
### Done
- **Prom GQL Queries**: Added `isDisabled` field to the standard GraphQL queries (`CategoryListingQuery`, `CompanyListingQuery`, `SearchListingQuery`, `ManufacturerListingQuery`) in `prom_queries.json` at the `products` sibling level.
- **Prom Parser & Availability**: Updated `scrapers/mapi_scraper/sites/prom.py` under both `graphql` and `html` parser pipelines to extract `isDisabled` and treat it as a factor in availability checks (`isDisabled: true` forces `avail_code` to `"Немає в наявності"`).
- **Unit Tests**: Added automated unit tests to `tests/test_availability.py` verifying that both active (`isDisabled: False` -> available) and disabled (`isDisabled: True` -> out of stock) products are correctly parsed.
### Notes
- Executed and validated all test cases successfully with zero regressions.

---

## 2026-05-20 — Availability Parsing Fix
### Done
- **Task Scheduler / Parser**: Implemented a case-insensitive unified `parse_availability_to_code` helper in `core/scheduler.py` to correctly map scraper availability strings to database codes and filter out-of-stock items. This resolves the bug where `"Немає в наявності"` (out of stock) was mistakenly mapped to `1` (in stock) due to containing the substring `"наявності"`.
- **Allo Scraper**: Updated `scrapers/mapi_scraper/sites/allo.py` to support `stock_status` values as both string and integer types (e.g. `"1"`, `"0"`, `1`, `0` formats) robustly.
### Notes
- Created `tests/test_availability.py` and `tests/test_scheduler_import.py` to verify the new parsing logic and ensure zero regression of scheduler imports.


---

## 2026-05-20 — Epicentr Attribute Extraction Fix
### Done
- **Epicentr Scraper**: Resolved a bug where product attributes were not being extracted correctly. The scraper now correctly maps `values` (plural) from the Epicentr MAPI response into the `attributes` dictionary, with a fallback to `value` (singular) for compatibility.
### Notes
- This fix ensures that specifications like "Brand", "Exchange & Return", etc., are correctly persisted in the database for Epicentr products.

---

## 2026-05-20 — Local Timezone Transition & DB Browser Enhancement
### Done
- **Database Browser**: Added `attributes` and `extra` fields to the `snapshot_products` SQL query in `gui/db_browser_window.py` to allow raw data inspection without modifying table columns.
- **Timezone Transition**: Migrated the entire application (snapshots, products, tasks, reports, cache, migrations) from UTC to local timezone (Kyiv) with explicit offsets for better local observability and "saved-as-seen" timestamps.
### Notes
- All future scrapes will now record time as `YYYY-MM-DDTHH:MM:SS.mmmmmm+03:00` (or similar), matching the user's local context.

---

## 2026-05-20 — Human-readable Debug Timestamps
### Done
- **Debugging & Logging**: Switched `scrapers/mapi_scraper/http.py` from Unix timestamps to human-readable `YYYYMMDD_HHMMSS` format for `run_` directories in `logs/` and `results/`.
- **Run Identification**: Identified `run_1779231093` as started at `2026-05-20 01:51:33` and renamed its corresponding `results` folder for easier navigation.
### Not done / deferred
- Existing log folder `logs/run_1779231093` could not be immediately renamed as it is currently locked by the active scraper process.
### Notes
- This change simplifies the process of matching log/result files to specific application runs without requiring manual timestamp conversion.

---

## 2026-05-19 — Prom Query Override Configuration
### Done
- **Prom.ua MAPI Extraction**: Externalized GraphQL queries into `prom_queries.json` to allow easy administration and limit adjustments (Limit increased to 96 items per page, adjusting pagination math).
- **Task Query Customization**: Added `prom_query_config` column to `tasks` database table (Migration v14) to permanently store `extra_variables` and `custom_query_override` for individual parsing tasks.
- **GUI Integration**: Created `PromQueryConfigDialog` modal to visualize and edit query configurations. Attached dynamic saving capabilities mapped to the existing DbBrowser append/new tracking logic.
- **Scraper Pipeline Update**: Modified `core/scheduler.py` to securely fetch database config and dynamically merge override variables / manual GraphQL bodies into `PromAPI` before requesting Prom.ua data.
### Not done / deferred
- N/A
### Notes
- Extends the Master Specification for Prom.ua using `prom_queries.json` effectively serving as the live production configuration.

---

## 2026-05-18 — Database Integrity & Lock Stabilization
### Done
- **Structural Bug Fix (Critical)**: Resolved `FOREIGN KEY constraint failed` error by identifying and removing an orphan `REFERENCES products(id)` constraint on the `snapshot_products.product_id` column. This constraint remained from an old schema version even after the `products` table was dropped in Phase 3.
- **Migration v13**: Implemented a "shadow table" migration to safely recreate `snapshot_products` without the invalid FK constraint while preserving all existing data.
- **Lock Contention Mitigation**: 
    - Offloaded snapshot finalization (completion status and product count updates) to the `DbWriteQueue` to ensure the UI thread never competes for the SQLite write lock with background scraper threads.
    - Wrapped batch setup (Task/Snapshot creation) in `MainWindow` with explicit `BEGIN/COMMIT` transactions to ensure atomicity and reduce lock duration.
- **Database Extension**: Added `image` column to `snapshot_products` table and registered Migration v12 to automate the upgrade and view updates.
- **Data Persistence**: Updated `TaskScheduler` to map and persist `image_url` from scrapers into the new database column.
- **GUI Image Integration**:
    - Updated `DetailsPanel` to display product image URLs with click-to-open browser functionality.
    - Added `webbrowser` integration for native link handling.
- **UX Improvements**:
    - Implemented **Automatic Default Client** creation if the database is empty.
    - Added mandatory validation in `MainWindow` to stop execution if snapshot/task context initialization fails.
### Not done / deferred
- N/A
### Notes
- The "FOREIGN KEY constraint failed" was a silent structural issue that only manifested when `PRAGMA foreign_keys = ON` was enabled. It was caused by the `product_id` column referencing a table that was deleted during the "Phase 3 Cleanup".
- `database is locked` issues are now largely mitigated by routing ALL writes (including GUI-triggered status updates) through the serialized `DbWriteQueue`.

---

## 2026-05-18 — MAPI Normalization Schema Refactor
### Done
- Unified product normalization schema by removing the legacy `properties` field and migrating characteristics logic to the `attributes` dictionary across all MAPI scraper modules.
- Updated `extractors.py` to remove `properties` from the LD+JSON mapping utility and ensure `attributes` and `extra` are correctly initialized.
- Refactored `PromModule` (`prom.py`) to remove the redundant `properties: []` placeholder.
- Refactored `AlloModule` (`allo.py`) to convert internal `description_attributes` list into the standard `attributes` dictionary.
- Refactored `EpicentrModule` (`epicentr.py`) to map raw API properties into the unified `attributes` KV store.
- Refactored `RozetkaModule` (`rozetka.py`) to migrate docket, var_params, and brand information into the `attributes` dictionary and fixed critical indentation errors in the normalization loop.
- Updated `HotlineModule` (`hotline.py`) to include `attributes` and `extra` placeholders, maintaining output consistency.
- Updated `TaskScheduler` (`core/scheduler.py`) to correctly map the new `attributes` dictionary from MAPI outputs to the `RawProduct.raw_specs` field.
- Updated `AGENT_GUIDE.md` documentation to reflect the new `attributes` and `extra` dictionary-based schema.
### Not done / deferred
- N/A
### Notes
- This change ensures that all product characteristics are stored as key-value pairs, which is more efficient for searching and display in the UI than the previous list-based structure.

---

## 2026-05-18 — DbBrowserWindow Modular Refactor
### Done
- Extracted `EditFormDialog` to `gui/dialogs/edit_form_dialog.py`.
- Extracted `PromptEditorDialog` to `gui/dialogs/prompt_editor_dialog.py`.
- Extracted `DiffPanel` to `gui/panels/diff_panel.py`.
- Created `DetailsPanel` in `gui/panels/details_panel.py` to show extended JSON attributes natively below the main dashboard table.
- Removed unused and legacy code from `gui/db_browser_window.py` (`_on_dedup`, `_on_view_product_history`).
- Significantly streamlined DB browser window layout implementation and improved architecture maintainability.
### Not done / deferred
- N/A
### Notes
- The Database Control Panel now cleanly delegates UI modals/dialogs to respective files.

---

## 2026-05-18 — Database Schema Cleanup (Phase 3)
### Done
- Implemented Database Schema Migration v9 (`db/migrations.py`) to remove legacy and redundant tables: `price_history`, `price_observations`, `monitored_products`, `project_products`, `projects`, `competitors`, `report_runs`, and `content_templates`.
- Added safety verification logic to migration v9: non-empty tables (except `price_history`) are preserved to prevent data loss, with warnings logged.
- Redesigned DB Browser sidebar (`gui/db_browser_window.py`):
    - Removed legacy "Price History" and "Discovered Products" views from the RAW DATA section.
    - Added "All Products" view pointing directly to the `products` table for simplified discovery browsing.
- Resolved SQL join dependencies on `price_history` by updating the `all_products` query to be standalone.
- Updated project documentation (`project.md`) to reflect the leaner v3.0 Database Schema.
### Not done / deferred
- Automatic data migration: historical price data in `price_history` was dropped (per requirements) as it duplicated `snapshot_products` data.
### Notes
- This cleanup significantly reduces database bloat and simplifies the maintenance of the Business Intelligence layer.

---

## 2026-05-18 — Extended Product Schema with Attributes and Extra
### Done
- Extended the `NormalizedProduct` and `RawProduct` dataclasses in `core/models.py` with `attributes` and `extra` optional dict fields.
- Implemented Database Schema Migration v8 (`db/migrations.py`) to add `attributes` and `extra` columns (TEXT, default '{}') to both `products` and `snapshot_products` tables.
- Updated `db/product_repo.py` to correctly map and persist `attributes` and `extra` into the database during insertions and updates.
- Ensured that `gui/main_window.py` successfully reads and provisions these columns back into target `snapshot_products`.
- Upgraded mapping logic inside MAPI pipelines: `PromModule` now accurately injects product characteristics into `attributes` and captures `ordersCount` within `extra`.
- Maintained schema consistency across `Rozetka`, `Allo`, `Epicentr`, and `Hotline` site extractors to return empty dicts gracefully mitigating potential failures.

---

## 2026-05-18 — Task Creation Workflow & UI Improvements
- Created a reusable `TaskDialog` modal (`gui/task_dialog.py`) for creating and editing tasks with name, type, and description fields, complete with non-empty validation for the task name and project themed aesthetics.
- Hooked `TaskDialog` into `gui/main_window.py` to trigger prior to starting extraction for *new tasks*. Parsing correctly aborts if the user cancels.
- Enhanced DB Browser sidebar (`gui/db_browser_window.py`) to display `task_type` formatted as `title [task_type]`. Double-clicking a task now opens the `TaskDialog` to edit its details directly.
- Developed and applied Schema Migration v7 (`db/migrations.py`) which adds the `description` column to the `tasks` table and refactors the `task_type` column to allow flexible values by using standard SQLite schema alteration techniques (Add, Update, Drop, Rename) without dropping existing data.

---

## 2026-05-18 — Professional README Update
### Done
- Analyzed `project.md` and recent `CHANGELOG.md` entries to synthesize the current project state.
- Completely redesigned `README.md` in the workspace root to showcase the shift from a simple scraper to a Business Intelligence tool.
- Added technical deep dives for **SQLite Serialized Writes**, **GraphQL Master Spec**, and **Professional Reporting Engine**.
- Updated tech stack badges to include **Gemini 3 Flash** and **openpyxl**.
- Modernized the Architecture diagram (Mermaid) to reflect the current modular MAPI pipeline, BI layer, and reporting flow.

---

## 2026-05-17 — Prom.ua Contact Scraper
### Done
- Created a standalone `scrapers/prom_contact_scraper/` utility for extracting seller contacts out of category listings via `https://prom.ua/graphql`.
- Built `gui.py` containing a fully disconnected Tkinter GUI with robust category dropdown, scrolling log output, and custom threading.
- Built `scraper.py` which persists additive `prom_contacts` and `prom_crawl_progress` tables to the existing active database (`config.yaml`).
- Implemented robust error stopping and offset resume logic to recover gracefully from network or user interruption.
- Added a Database Viewer (`DBViewerWindow`) inside `gui.py` to inspect extracted contacts via a `ttk.Treeview`.
- Implemented `Export to Excel` (using `openpyxl`) and `Export to JSON` functionalities directly from the DB Viewer.

---

## 2026-05-17 — Data Consolidation & Path Robustness
- Consolidated `D:\Scrappers\data` into `D:\Scrappers\marketplace-scraper\data`.
- Replaced the 0.9MB database with the 7.3MB historical database to restore missing records.
- Removed the redundant parent `D:\Scrappers\data` directory.
- Updated `db/database.py` to resolve relative database paths against the project root.
- Updated `BaseScraper`, `rozetka.py`, and `hotline.py` to use absolute data paths relative to project root for browser profiles, preventing duplicate folder creation.

---

## 2026-05-17 — Prom.ua GraphQL Query Enrichment
### Done
- Added `CategoryListingQuery_Full` to `prom_queries.json` with a comprehensive list of 50+ fields extracted from production GraphQL fragments.
- Implemented a more robust `template` for `CategoryListingQuery_Full` that includes top-level metadata like `country`, `context`, `region`, and `breadCrumbs`.
- Synchronized variables and signatures to support `includePremiumAdvBlock` and `regionDelivery` parameters in the GQL Builder.

---

## 2026-05-17 — Prom.ua GraphQL Documentation
### Done
- Created `prom_graph.ql` as a **Master Specification** for Prom.ua GraphQL API.
- Created `scrapers/mapi_scraper/tools/prom_gql_builder.py`: A standalone module & GUI tool for constructing, testing, and exporting GQL requests (CURL/JSON/Presets).
- Added **Preset Management** to the GQL builder for persistent custom requests.
- Consolidated Discovery, Enrichment, Contacts, and Category Tree mapping into a single source of truth.
- Created technical query maps for Rozetka (`MAPI_ROZETKA_QUERY_MAP.md`), Allo (`MAPI_ALLO_QUERY_MAP.md`), and Epicentr (`MAPI_EPICENTR_QUERY_MAP.md`).
- Updated `project.md` and Obsidian `INDEX.md`.

---

## 2026-05-17 — Excel Reporting Engine
### Done
- Implemented `reports/snapshot_report.py`: a functional interface to generate professional 4-sheet comparison reports using `openpyxl`.
- Report includes:
  - **Summary**: Key Performance Indicators (KPIs) and trend charts (Product Count, Avg Price).
  - **Current Products**: Full list of the latest snapshot with price delta vs the earliest one, including color-coding (Red = Price Up, Green = Price Down, Blue = New).
  - **Price Dynamics**: Tracking historical price changes for products present in 2+ snapshots.
  - **Appeared - Disappeared**: Categorized view of new arrivals and discontinued items.
- Integrated "Export Report" button into the DB Browser toolbar.
- The button is context-aware: only enabled in the "Snapshots" view and when 2+ snapshots are selected.
- Handled `openpyxl` restrictions (renamed sheet from "/" to "-" to avoid ValueError).
- Verified with a dedicated smoke-test `tests/test_snapshot_report.py`.

---

## 2026-05-16 — Business Layer Stabilization
### Done
- Fixed "Client -> Task -> Snapshot" drill-down navigation in DB Browser.
- Implemented automatic Task/Snapshot creation when running scrapes from the Main Window.
- Added Migration v2 to safely add `client_id` to the `tasks` table if it was missing.
- Fixed `snapshot_products` filtering: it now correctly loads products for the selected snapshot.
- Rebuilt "Compare Snapshots" (Diff) logic: now shows NEW, GONE, CHANGED, and UNCHANGED products with price delta.
- Added "View Price History" context menu action for products in the DB Browser.
- Added `import json` to `main_window.py` to fix serialization errors.
- Fixed SQL alias mismatch in `db_browser_window.py` (all `fk_join` now use aliases like `t.client_id`, `s.task_id`).
- Added Migration v3 to safely add `task_id` to the `snapshots` table if it was missing.
- Resolved "no such column" errors in the DB Browser when filtering for tasks or snapshots.
- UI is significantly more reactive with double-click and single-click drill-downs.

---

## 2026-05-16 — DB Browser Fix & MAPI Restoration
### Done
- **DB Browser Query Builder**:
  - Implemented robust top-level `WHERE` detection in `gui/db_browser_window.py`.
  - Resolved `near "AND": syntax error` which occurred when subqueries in column definitions contained their own `WHERE` clauses.
- **MAPI Engine Restoration**:
  - Restored missing `scrapers/mapi_scraper/sites/` directory via `git restore`.
  - Verified that all site-specific modules (`rozetka.py`, `prom.py`, `allo.py`, `epicentr.py`, `hotline.py`) are present and importable.
  - Resolved `No module named 'scrapers.mapi_scraper.sites'` error in the TaskScheduler.

---
## 2026-05-16 — Business Layer Refactoring: Clients, Tasks, and Snapshots
### Done
- **Database Schema Migration**:
  - Implemented MigrationManager to manage additive SQLite schema upgrades securely.
  - V1 Migration enacted adding clients, 	asks, snapshots, and snapshot_products tables.
  - Safely removed references to the legacy nested "Projects" business schema across the repository.
- **Context-Sensitive Sidebar Navigation**:
  - Restructured db_browser_window.py sidebar to reflect the new Client -> Task hierarchy.
  - Implemented expandable tasks and immediate data-grid synchronization (loading snapshots when a task is selected).
- **Core Operations**:
  - Bound generic _show_edit_form to new clients and 	asks modal forms.
  - Created logic to capture the current state of newly discovered products that match a query string into a frozen snapshot.
  - Deprecated legacy "Import to Project" logic.
- **Snapshot Diff UI**:
  - Built a snapshot comparison feature to instantly highlight "NEW", "MISSING", and "CHANGED" products between two runs of a single task.

### Notes
- This paves the way for the Global Intelligence Phase to integrate tracking/discovery results into stable deliverables.

---
## 2026-05-16 вЂ” Portfolio Presentation & README
### Done
- **High-Impact README**: Created a professional, technical-first `README.md` optimized for portfolio presentation. 
  - Included interactive architecture diagrams (Mermaid).
  - Documented "Why it's hard" section covering TLS fingerprinting and SSR state extraction.
  - Defined business context and product monetization strategy.
  - Added technical stack badges and roadmap.

---

## 2026-05-16 вЂ” GUI Aesthetics & Compact Layout
### Done
- **Compact Sidebar**:
  - Inlined "Search" and "URLs" mode selectors.
  - Inlined "Skip OOS" and "Debug" checkboxes into a single row.
  - Condensed "Threads" and "Delay" settings into a single row.
  - Reduced vertical padding across all sidebar sections to eliminate scrolling requirements.
- **Scrollbar Modernization**:
  - Replaced legacy Win98-style `ttk.Scrollbar` with modern `ctk.CTkScrollbar` in `main_window.py` (Live Data), `db_browser_window.py` (Table views), and `api_status_window.py` (Status table).
  - Ensured horizontal and vertical scrollbars match the CustomTkinter theme.
- **API Status Window Refresh**:
  - Upgraded `ApiKeyStatusWindow` from `tk.Toplevel` to `ctk.CTkToplevel` for consistent styling.

---

## 2026-05-16 вЂ” MAPI Debug Flag & Site Data Extraction Stabilization
### Done
- **MAPI Debug Propagation**: Fixed critical bug where the `debug` flag was not passed from GUI/TaskScheduler to the scraping engine.
- **Debug Persistence**: 
  - Resolved directory creation issues in `http.py` ensuring `results/run_TS` folders exist.
  - Implemented automatic saving of raw and normalized JSON data when the "Debug" checkbox is enabled.
- **Epicentr Parsing Refinement**:
  - Updated `EpicentrAPI.normalize` to correctly handle `seller` logic (epicentrk vs marketplace).
  - Improved Category Path extraction using `sectionsUa`.
  - Added defensive `isinstance` checks to prevent crashes on non-dict responses.
- **Allo Data Extraction**:
  - Fixed category extraction in Allo by looking into `layered_navigation` for `category_filter`.
  - Verified merchant identification for direct Allo sales.
- **Cleanup**: Removed temporary debug logging from `http.py`, `allo.py`, and `epicentr.py`.
### Notes
- Debug artifacts can now be found in `scrapers/mapi_scraper/results/run_<timestamp>/`.
- Epicentr merchant names for marketplace sellers are currently not provided by the search API and default to "Marketplace Seller" or the seller UUID.

---

## 2026-05-16 вЂ” Database & Model Schema Modernization
### Done
- **GUI Column Cleanup**: Removed legacy `V`, `Ah`, and `Model` columns from "Discovered Products" and "Client Products" views in `db_browser_window.py`.
- **New GUI Columns**: Added `SKU`, `Merchant`, and `Category` columns to the Discovered Products table for better traceability.
- **Database Schema Migration**:
  - Removed `model` and `norm_model` from the `products` table in `database.py`.
  - Updated initialization logic and migration checks to align with the new schema.
- **Repository Optimization**: Refactored `product_repo.py` to remove `norm_model` from update queries.
- **Normalizer Refinement**: Simplified the AI normalization prompt in `normalizer.py` by removing instructions for deprecated spec extraction (Voltage, Capacity, Model).
- **Core Model Update**: Removed the `model` field from the `RawProduct` dataclass in `models.py`.
- **Global Code Cleanup**: Updated `scheduler.py` and all legacy scrapers (`rozetka.py`, `prom.py`, `allo.py`, `epicentrk.py`, `hotline.py`, `custom_scraper.py`) to remove `model=...` arguments from `RawProduct` instantiations.
- **Bug Fixes (Post-Cleanup)**:
  - Fixed `'RawProduct' object has no attribute 'model'` crash in `db/product_repo.py` and `ai/normalizer.py` where the field was still being accessed after removal from the dataclass.
  - Fixed `[HOTLINE] Scraper error: Expected list of products, got dict` in `scheduler.py` by correcting the response format in `mapi_scraper/sites/hotline.py`.
### Not done / deferred
- Migration of existing data: the system currently drops and recreates or alters tables without full data migration for the removed columns.
### Notes
- This cleanup aligns the entire system with the MAPI-based normalizer schema, reducing technical debt and improving UI clarity.

---

## 2026-05-16 вЂ” MAPI Developer Documentation
### Done
- **Developer Guide**: Created `scrapers/mapi_scraper/AGENT_GUIDE.md` containing comprehensive documentation for the MAPI module.
- **Architecture Mapping**: Documented the relationship between core HTTP layer, extractors, and site-specific modules.
- **Implementation Templates**: Provided checklist and code templates for adding new marketplace modules.
- **Standardization**: Documented the `_scrape_impl` pattern, sync/async unification, and `avail_code` preservation rules.
- **Project Update**: Updated `project.md` to reflect the new documentation standard.

---

## 2026-05-16 вЂ” MAPI Stability, Pagination & GUI Polish
### Done
- **GUI Refactor**: Simplified sidebar to only 2 modes: "Search" and "URL".
  - Moved the URL entry to a specialized Modal Window to keep the sidebar clean.
  - Removed deprecated/half-implemented modes (Seller, Update).
- **MAPI Pagination Stop**:
  - Implemented early-exit in `scheduler.py`: breaks the loop if a marketplace returns 0 valid (filtered) products or reaches the reported `total_pages`.
  - Fixed **Allo** phantom pagination: replaced dummy `page + 1` with real count extraction and threshold-based stopping.
- **Epicentr Module Fixes**:
  - Registered `"epicentrk"` alias in `mapi_scraper/__init__.py` to match scheduler usage.
  - Restored missing `for` loop in `epicentr.py` normalizer that caused 0 extraction results.
  - **Brand Support**: Implemented specialized `/v1/brands/brand` API endpoint for brand pages. Now correctly using `merchant` normalization context (`params.products`) for brand data.
  - **Slug Robustness**: Fixed empty slug extraction bug by stripping trailing slashes before splitting URLs.
  - **Path Cleaning**: Improved URL path normalization in the listing fallback.
- **OOS Filter Fix**: Updated `scheduler.py` to recognize Ukrainian terms ("РќРµРјР°С”", "Р—РЅСЏС‚РёР№") so "Skip out of stock" works for MAPI.
- **MAPI Guard**: Added type-checking for product lists in `scheduler.py` to prevent crashes if a module returns strings or dicts (fixed `'str' has no attribute 'get'`).
- **Log Enrichment**: Added per-page URL logging with marketplace-first tags for correct GUI routing.
- **GUI Log Routing**: Cleaned up duplicate scheduler routing logic and improved marketplace-tagged log steering to ensure scheduler reports appear in correct tabs.
- **Session Reports**: Each scraper now logs a final summary: "Products parsed: total {}, in stock {}, out-of-stock {}" after completion.
- **Database Concurrency (Final Fix)**: 
  - Routed GUI-side session creation and finalization through the `TaskScheduler.DbWriteQueue`.
  - Refactored all direct `commit()` calls in `scheduler.py` into the serialization queue.
  - This guarantees a single writer thread for the entire application, eliminating "database is locked" errors.
- **GUI Addition**: Added "All" checkbox next to page count. When enabled, the scraper automatically fetches all available pages (stopped by early-exit logic).
- **Concurrency Control**: Added "Threads per domain" and "Request delay" settings to the GUI. 
- **Site-Level Throttling**: TaskScheduler now enforces domain-specific concurrency via semaphores, allowing parallel marketplace runs while limiting per-domain pressure.
- **Request Pacing**: Integrated configurable delay between page requests in the MAPI scraper loop.

---

## 2026-05-16 вЂ” MAPI Crash & DB Lock Fixes
### Done
- **`db/product_repo.py`** вЂ” Fixed `'list' object has no attribute 'get'` crash in `_save_raw_specs`:
  - MAPI scrapers pass `properties` as a `list` of `{name, value}` dicts into `raw_specs`; the method previously called `.get()` on it unconditionally.
  - Added `isinstance(specs, dict)` guard: JSON serialization runs for both types; the `norm_brand/model/category` UPDATE only runs when `specs` is a dict.
  - Added `try/except` around `json.dumps` with a warning log.
- **`db/database.py`** вЂ” Added `PRAGMA busy_timeout=5000` to every new connection:
  - SQLite now retries write-lock acquisition for up to 5 seconds before raising `database is locked`.
  - Covers all direct DB writes that don't go through `DbWriteQueue` (session finalization in GUI, `_update_session_count` in scheduler, DB Control Panel operations).
### Notes
- These two bugs were independent: the `list` crash caused MAPI scrapers to raise before writing most products; the lock error hit session finalization from the GUI batch thread racing the writer thread.

---

## 2026-05-16 вЂ” Serialized DB Writes via DbWriteQueue
### Done
- Added `DbWriteQueue` class to `core/scheduler.py`: a single background writer thread that processes all SQLite write jobs sequentially via a `queue.Queue`.
- All `repo.upsert_product()` calls in both `_run_mapi_async` and `_run_scraper_async` now go through `self._db_write_queue.submit(lambda ...)` instead of calling SQLite directly.
- Writer thread starts once in `TaskScheduler.__init__` and runs for the lifetime of the scheduler (daemon thread, cleaned up on app exit).
- Eliminates `database is locked` errors caused by 5+ parallel scraper threads writing concurrently under MAPI mode.
### Notes
- `_update_session_count` writes are still direct (called once per marketplace after scraper finishes, not in a hot loop вЂ” low collision risk).
- Lambda default-argument capture (`p=prod, s=sid`) ensures correct variable binding across the loop.

---

## 2026-05-16 вЂ” MAPI Default Method & Rozetka Bug Fix
### Done
- Set MAPI as the default execution method for all marketplaces in `gui/main_window.py` (was `Auto`).
- Fixed `'list' object has no attribute 'get'` crash in `scrapers/mapi_scraper/sites/rozetka.py`:
  - Added `isinstance(api_data, dict)` guard in the `/search/` path (search API response was a list in some edge cases).
  - Added `isinstance(api_data, dict)` guard in the category `/c\d+/` path.
### Not done / deferred
- Similar guard not audited yet for producer and seller paths (likely safe, but not tested).
### Notes
- Error triggered when Rozetka API returned a JSON array instead of dict (e.g. rate-limited or error response).

---

## 2026-05-15 вЂ” Tkinter GUI Integration of MAPI Scraper
### Done
- Replaced monolithic legacy routing in `core/scheduler.py` by intercepting `method == "MAPI"` in `_run_scraper_async`.
- Updated Tkinter `gui/main_window.py` to expose "MAPI" inside the marketplace Method drop-down per session.
- Seamlessly handled MAPI -> `RawProduct` mapping to preserve downstream logic without mutating core signatures.
- Implemented additive SQLite schema migrations in `db/database.py` adding `sku`, `merchant_id`, and `merchant_name`.
- Updated `RawProduct` dataclass and repository logic to correctly intercept and persist new database fields natively.

---

## 2026-05-15 вЂ” Allo Lightweight AJAX Integration
### Done
- Implemented lightweight, stateless AJAX scraping for Allo (`AlloModule`).
- Added in-memory discovery cache (`_DEEPLINK_CACHE`) to eliminate redundant SSR fetching during pagination.
- Added universal `allomobileua://` deeplink parsing for dynamic filter strings and generic parameters.
- Built partner context fallback logic for URLs containing `partner_` keys.
- Confirmed paginator accurately processes successive pages without loop triggering or 400 errors.

---

## 2026-05-15 вЂ” Standardization of Availability Labels
### Done
- Unified `avail_code` output across all marketplaces to use standardized string labels.
- Implemented core mapping for "Р’ РЅР°СЏРІРЅРѕСЃС‚С–" and "РќРµРјР°С” РІ РЅР°СЏРІРЅРѕСЃС‚С–" as defaults.
- Added site-specific granular labels:
    - **Epicentr**: 250/300 -> "РџС–Рґ Р·Р°РјРѕРІР»РµРЅРЅСЏ", 500 -> "Р—РЅСЏС‚РёР№ Р· РІРёСЂРѕР±РЅРёС†С‚РІР°".
    - **Rozetka**: limited -> "Р—Р°РєС–РЅС‡СѓС”С‚СЊСЃСЏ".
- Updated `PromAPI`, `RozetkaAPI`, `AlloAPI`, `EpicentrAPI`, and shared `LD+JSON` extractors to support the new schema.
- Verified correct mapping with `tests/test_prom_gql_fields.py`.

---



## 2026-05-15 вЂ” Resolution of Rozetka API Subdomain and Producer Issues
### Done
- Corrected Rozetka category/producer API request logic to use full URLs (including subdomains) in the `url=` parameter.
- Implemented handling for API-level 301 redirects (e.g., to `bt.rozetka.com.ua`) returned in 200 OK JSON responses.
- Integrated dedicated `/v1/api/catalog/producer` endpoint for producer-specific pages, ensuring full query filter support.
- Preserved `/ua/` locale prefix in API request URLs to ensure correct server-side routing.
- Improved robustness with automated fallback to HTML extraction if redirected API calls return zero products.
- Verified across category, producer, search, and seller endpoints with a complex multi-domain test suite.

---

## 2026-05-15 вЂ” Resolution of Async Pagination Anomalies
### Done
- Resolved Rozetka producer page infinite loops by implementing explicit `page` parameter passing to the Category API.
- Fixed Allo duplicate product extraction by implementing `/p-N/` path segment injection.
- Added site-specific `_inject_page` logic for Prom and Rozetka fallback HTML extractions.
- Enhanced `AsyncPaginator` in `tests/test_mapi_pagination.py` with duplicate detection and unreported `total_pages` safety breaks.
- Verified fixes with a 21-URL stress test; 100% success on loop prevention and 95%+ success on multi-page extraction accuracy.

---

## 2026-05-15 вЂ” Async Pagination Stress-Test
### Done
- Updated `tests/test_mapi_pagination.py` to use the new modular async architecture.
- Implemented `AsyncPaginator` using `async_scrape` and `get_module_for_url`.
- Executed tests across 21 diverse marketplace URLs (Categories, Search, Sellers, Producers).
- Identified major pagination anomalies:
    - **Rozetka**: Producer pages loop on page 1 when `total_pages` is unreported.
    - **Allo/Rozetka**: Category subdomains often return duplicate products for pages 2+.
- Verified stable async performance and structured logging.
### Not done / deferred
- Fixing identified pagination anomalies (requires module-specific regex/logic updates).
- Integration of these URLs into continuous CI/CD pipeline.
### Notes
- Sequential execution with 1.5s delay proved stable for anti-bot measures.

---

## 2026-05-14 Гўв‚¬вЂќ Modular MAPI Scraper Architecture
### Done
- Refactored `scrapers/mapi_scraper/mapi_scraper.py` monolith into a modular package.
- Created `scrapers/mapi_scraper/base.py` defining `MarketplaceModule` protocol and `BaseModule` mixin.
- Created `scrapers/mapi_scraper/http.py` for shared HTTP logic, headers, and structured logging.
- Created `scrapers/mapi_scraper/extractors.py` for shared HTML extraction utilities.
- Implemented site-specific modules in `scrapers/mapi_scraper/sites/`:
  - `rozetka.py`: Migrated and standardized Rozetka extraction logic.
  - `prom.py`: Migrated Prom.ua GraphQL and HTML fallback logic.
  - `allo.py`: Migrated Allo Nuxt/ExecJS processing.
  - `epicentr.py`: Migrated stateless Epicentr API logic.
  - `hotline.py`: Migrated BS4-based Hotline extraction.
- Updated `scrapers/mapi_scraper/__init__.py` to provide a unified `scrape()` entry point and a domain-based module resolver.
- Updated `scrapers/mapi_scraper/paginator.py` to use the new module-based architecture.
- Verified architecture with a full test suite run across all supported marketplaces and modes (Search, Category, Seller/Merchant).
- Achieved zero-regression while significantly improving codebase maintainability.

### Not done / deferred
- Migration of `normalizer.py` recursive logic into `MarketplaceModule` structure (currently kept as a separate utility).

---

## 2026-05-14 Гўв‚¬вЂќ Prom.ua Company Pagination Fix
### Done
- Fixed `PromAPI.parse_url_to_graphql` to correctly handle secondary pages for company listings.
- Resolved issue where `urllib.parse.urlparse` separated pagination parameters (e.g., `;2.html`) into `parsed.params`, causing the company pattern matcher to fail.
- Implemented combined `path` + `params` evaluation for robust operation identification.
- Refined `company_name` extraction to strip pagination suffixes before passing to GraphQL variables.
- Verified fix with `tests/test_mapi_pagination.py`: 100% success rate on multi-page seller scrapes.

---

## 2026-05-14 Гўв‚¬вЂќ Marketplace API (MAPI) Refactor & Migration
### Done
- Refactored `fast_api` module into a unified nested package: `scrapers/mapi_scraper/`.
- Renamed the component from "Fast API" to "Marketplace API (MAPI)".
- Moved `mapi_scraper.py`, `normalizer.py`, `paginator.py`, and diagnostic folders (`logs/`, `results/`) into the new subfolder.
- Implemented convenience import in `scrapers/mapi_scraper/__init__.py` to maintain a clean public API (`from scrapers.mapi_scraper import scrape`).
- Relinked all internal and external imports to the new path.
- Updated documentation and project status to reflect the new structure.

### Not done / deferred
- Cleaned up potentially unused diagnostic variables in `mapi_scraper.py` (awaiting user confirmation on specific helper functions).

---
...
 
## 2026-05-14 - Phase 2 Async Rewrite 
### Done 
- Removed mutable pagination state from RozetkaAPI, PromAPI, AlloAPI, and EpicentrAPI to ensure thread-safety. 
- Added native sync_scrape_url to all marketplace modules with asynchronous requests via curl_cffi.AsyncSession. 
- Created _aget and _aget_with_meta in http.py with support for per-request proxy injection. 
- Wrapped execjs execution in llo.py inside syncio.get_running_loop().run_in_executor to prevent event loop blocking. 
- Exposed sync_scrape and sync_scrape_url_auto in __init__.py. 
### Not done / deferred 
- Global Intelligence Phase (Gemini Normalization) is deferred to Phase 3. 
### Notes 
- Backward compatibility is fully maintained; legacy synchronous scrape_url remains functional.

## 2026-05-14 вЂ” MAPI Architecture Refactoring & Cleanup
### Done
- Unified synchronous and asynchronous scraping logic using fetcher/poster factories in http.py.
- Refactored llo.py, prom.py, ozetka.py, and epicentr.py to use the new _scrape_impl pattern, eliminating ~1000 lines of duplicated code.
- Centralized LD+JSON product mapping via _map_ld_json_offer in extractors.py.
- Deleted unused 
ormalizer.py.
- Cleaned up inline imports and resolved variable scoping issues (e.g., pollo in prom.py).
- Replaced bare except: pass blocks with debug logging.
### Not done / deferred
- Full functional validation across all modes (Search/Category/Seller) due to network environment constraints in test runner; manual verification recommended.
### Notes
- The new architecture significantly reduces technical debt and prepares the system for easier integration of new marketplaces.

