## 2026-05-15 — Allo Lightweight AJAX Integration
### Done
- Implemented lightweight, stateless AJAX scraping for Allo (`AlloModule`).
- Added in-memory discovery cache (`_DEEPLINK_CACHE`) to eliminate redundant SSR fetching during pagination.
- Added universal `allomobileua://` deeplink parsing for dynamic filter strings and generic parameters.
- Built partner context fallback logic for URLs containing `partner_` keys.
- Confirmed paginator accurately processes successive pages without loop triggering or 400 errors.

---

## 2026-05-15 — Standardization of Availability Labels
### Done
- Unified `avail_code` output across all marketplaces to use standardized string labels.
- Implemented core mapping for "В наявності" and "Немає в наявності" as defaults.
- Added site-specific granular labels:
    - **Epicentr**: 250/300 -> "Під замовлення", 500 -> "Знятий з виробництва".
    - **Rozetka**: limited -> "Закінчується".
- Updated `PromAPI`, `RozetkaAPI`, `AlloAPI`, `EpicentrAPI`, and shared `LD+JSON` extractors to support the new schema.
- Verified correct mapping with `tests/test_prom_gql_fields.py`.

---



## 2026-05-15 — Resolution of Rozetka API Subdomain and Producer Issues
### Done
- Corrected Rozetka category/producer API request logic to use full URLs (including subdomains) in the `url=` parameter.
- Implemented handling for API-level 301 redirects (e.g., to `bt.rozetka.com.ua`) returned in 200 OK JSON responses.
- Integrated dedicated `/v1/api/catalog/producer` endpoint for producer-specific pages, ensuring full query filter support.
- Preserved `/ua/` locale prefix in API request URLs to ensure correct server-side routing.
- Improved robustness with automated fallback to HTML extraction if redirected API calls return zero products.
- Verified across category, producer, search, and seller endpoints with a complex multi-domain test suite.

---

## 2026-05-15 — Resolution of Async Pagination Anomalies
### Done
- Resolved Rozetka producer page infinite loops by implementing explicit `page` parameter passing to the Category API.
- Fixed Allo duplicate product extraction by implementing `/p-N/` path segment injection.
- Added site-specific `_inject_page` logic for Prom and Rozetka fallback HTML extractions.
- Enhanced `AsyncPaginator` in `tests/test_mapi_pagination.py` with duplicate detection and unreported `total_pages` safety breaks.
- Verified fixes with a 21-URL stress test; 100% success on loop prevention and 95%+ success on multi-page extraction accuracy.

---

## 2026-05-15 — Async Pagination Stress-Test
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

## 2026-05-14 â€” Modular MAPI Scraper Architecture
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

## 2026-05-14 â€” Prom.ua Company Pagination Fix
### Done
- Fixed `PromAPI.parse_url_to_graphql` to correctly handle secondary pages for company listings.
- Resolved issue where `urllib.parse.urlparse` separated pagination parameters (e.g., `;2.html`) into `parsed.params`, causing the company pattern matcher to fail.
- Implemented combined `path` + `params` evaluation for robust operation identification.
- Refined `company_name` extraction to strip pagination suffixes before passing to GraphQL variables.
- Verified fix with `tests/test_mapi_pagination.py`: 100% success rate on multi-page seller scrapes.

---

## 2026-05-14 â€” Marketplace API (MAPI) Refactor & Migration
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

## 2026-05-14 — MAPI Architecture Refactoring & Cleanup
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
