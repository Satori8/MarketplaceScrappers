# CHANGELOG — Marketplace Scraper

Format: newest entry first.
Updated by coding agent at the end of every completed task.

---

## 2026-05-14 — Modular MAPI Scraper Architecture
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

## 2026-05-14 — Prom.ua Company Pagination Fix
### Done
- Fixed `PromAPI.parse_url_to_graphql` to correctly handle secondary pages for company listings.
- Resolved issue where `urllib.parse.urlparse` separated pagination parameters (e.g., `;2.html`) into `parsed.params`, causing the company pattern matcher to fail.
- Implemented combined `path` + `params` evaluation for robust operation identification.
- Refined `company_name` extraction to strip pagination suffixes before passing to GraphQL variables.
- Verified fix with `tests/test_mapi_pagination.py`: 100% success rate on multi-page seller scrapes.

---

## 2026-05-14 — Marketplace API (MAPI) Refactor & Migration
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
