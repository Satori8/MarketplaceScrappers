# MAPI Agent Guide

This guide serves as the primary technical documentation for the MAPI (Marketplace API) scraper module. It is intended for AI agents and engineers adding new site modules or maintained existing ones.

---

## 1. Overview

MAPI is a high-performance, async-first scraping engine designed to replace legacy browser-based scrapers. It uses `curl_cffi` for TLS fingerprint impersonation (stealth), direct API discovery (REST/GraphQL), and lightweight HTML parsing. Key features include native proxy support, stateless module design, and a unified API for both synchronous (GUI) and asynchronous (high-concurrency) tasks.

---

## 2. Architecture

```text
scrapers/mapi_scraper/
├── __init__.py           # Public API & Module Registry
├── base.py               # MarketplaceModule Protocol & BaseModule
├── http.py               # HTTP layer (AsyncSession, logging, debug)
├── extractors.py         # Reusable HTML/JS data extraction utilities
├── paginator.py          # Unified multi-page scraper integration
├── sites/                # Site-specific implementations
│   ├── allo.py           # Site Module: Allo (JS-heavy, execjs)
│   ├── epicentr.py       # Site Module: Epicentr (REST API)
│   ├── prom.py           # Site Module: Prom (GraphQL)
│   ├── rozetka.py        # Site Module: Rozetka (Multi-path API fallback)
│   └── hotline.py        # Site Module: Hotline (BS4 fallback)
├── logs/                 # Run-specific logs
└── results/              # Debug artifacts (raw vs normalized JSON)
```

### Module Relationship
1. **`__init__.py`**: Entry point for all callers. Discovers and routes requests to modules.
2. **`base.py`**: Defines the `MarketplaceModule` contract.
3. **`http.py`**: Handles network I/O via `curl_cffi`. Provides the `fetch` and `post` toolkits.
4. **`extractors.py`**: Toolset for pulling JSON out of HTML scripts/blocks.
5. **`sites/*.py`**: Implements business logic (URL discovery -> Extraction -> Normalization).

### Module Registry (`_MODULES`)
Modules are singletons registered during package initialization.
- `_register_module(module)`: Adds a module to the global registry.
- `get_module_for_url(url)`: Automatically selects the module by matching the URL domain against `module.DOMAINS`.

---

## 3. Public API

Located in `scrapers/mapi_scraper/__init__.py`.

### Functions

- **`scrape(site, mode, **kw)`**  
  *Sync, legacy-compatible.* Used by the GUI thread. Internally calls `asyncio.run()`.
- **`async_scrape(site, url, page, debug, proxy)`**  
  *Async, preferred.* native awaitable entry point with proxy support.
- **`async_scrape_url_auto(url, page, debug, proxy)`**  
  *Async.* Auto-detects the site from the URL and scrapes it.
- **`get_module(site_id)`**  
  Returns the module instance for a given ID (e.g., "rozetka").
- **`get_module_for_url(url)`**  
  Returns the module instance that handles the given URL.

### Parallel Execution Example
This is the primary pattern used for high-speed scraping:

```python
import asyncio
from scrapers.mapi_scraper import async_scrape

async def scrape_parallel(tasks: list[dict]) -> list[dict]:
    """
    tasks = [
        {"site": "rozetka", "url": "https://...", "proxy": "http://user:pass@h:p"},
        {"site": "prom",    "url": "https://...", "proxy": None},
    ]
    """
    coros = [
        async_scrape(t["site"], t["url"], proxy=t.get("proxy"))
        for t in tasks
    ]
    # return_exceptions=False ensures we stop on the first crash for safety
    return await asyncio.gather(*coros, return_exceptions=False)

# From a non-async (GUI/CLI) thread:
results = asyncio.run(scrape_parallel(tasks))
```

### Proxy Usage Example
Proxies are passed as strings: `http://user:pass@host:port`.
```python
# Single proxy call
result = await async_scrape("rozetka", url, proxy="http://proxyuser:proxypass@1.2.3.4:8080")

# Batch with rotation (caller's responsibility)
proxies = ["http://p1...", "http://p2..."]
tasks = [async_scrape("allo", url, proxy=proxies[i % len(proxies)]) for i, url in enumerate(urls)]
```

### CLI Usage Example
The module can be invoked directly:
```bash
# General format: python -m scrapers.mapi_scraper {site} {mode} {key=val}
python -m scrapers.mapi_scraper rozetka url url=https://rozetka.com.ua/ua/search/?text=iphone

# With debug mode (saves raw files)
python -m scrapers.mapi_scraper epicentr url url=https://epicentrk.ua/... debug=true
```

---

## 4. Result Schema

Every `scrape_url` call must return a dictionary following this structure.

### Success
```python
{
    "ok": True,
    "site": "rozetka",
    "status": "ok",
    "mode": "url",
    "code": 200,                # HTTP status of the primary API/HTML request
    "products": [...],          # List of product objects
    "pagination": {
        "total_pages": 12,
        "page_index": 1
    },
    "debug": {...}              # Optional, present if debug=True
}
```

### Error
```python
{
    "ok": False,
    "site": "prom",
    "mode": "url",
    "error": "HTTP 403",
    "code": 403
}
```

### Product Object Schema
| Field | Type | Required | Description |
|---|---|---|---|
| `id` | `str` | Yes | Unique site-specific product ID |
| `name` | `str` | Yes | Full product title |
| `price` | `float\|str` | Yes | Current price (do not coerce type unnecessarily) |
| `avail_code` | `any` | Yes | **Do not normalize.** Preserve site's exact code/string |
| `url` | `str` | Yes | Absolute URL to product page |
| `sku` | `str` | No | Manufacturer SKU |
| `brand` | `str` | No | Brand/Manufacturer name |
| `merchant_name`| `str` | No | Seller name (if marketplace) |
| `properties` | `list` | No | `[{"name": "...", "value": "..."}, ...]` |
| `image` | `str` | No | URL to primary product image |

### `avail_code` Behavior
Callers must be prepared to handle various types. Modules should preserve the values found in source data:
- **Rozetka**: Strings like `"available"`, `"unavailable"`, `"limited"`.
- **Epicentr**: Integers like `100` (In Stock), `400` (OOS).
- **Prom**: Integers `1` (Available), `0` (OOS).
- **Allo**: Integer `1` or `0` based on `stock_status`.
- **LD+JSON**: Usually strings like `"В наявності"`.

---

## 5. HTTP Layer (`http.py`)

Always use these helpers instead of raw `requests` or `httpx`.

| Function | Async | Description |
|---|---|---|
| `_aget_with_meta` | Yes | The workhorse. Returns `(code, data, meta)`. Handles proxy and timing. |
| `_make_sync_fetcher` | Yes* | Factory returning a coroutine that calls sync `requests` (Phase 1 legacy support). |
| `_make_async_fetcher`| Yes | Factory returning a coroutine that uses `AsyncSession`. Correct choice for Phase 2. |
| `_make_async_poster` | Yes | Similar to fetcher, but for POST (e.g., GraphQL). |
| `_ok`, `_err` | No | Converters for standard result dicts. |
| `_save_debug_item` | No | Saves raw + normalized data to files when `debug=True`. |

**Concurrency Pattern**: `http.py` uses `AsyncSession` per request. This ensures unique TLS fingerprints and reduces detection risk compared to keeping a session open across hundreds of requests.

---

## 6. Extractors (`extractors.py`)

Utilities for common scraping tasks:
- `_extract_ld_json(html)`: Finds and parses all `application/ld+json` blocks.
- `_extract_js_assignment_raw(html, var_name)`: Heuristic parser for JS variables (handles dicts, lists, and simple primitives).
- `_extract_json_assignment(html, var_name)`: Wraps the above with `json.loads()`.
- `_find_common_api_request_in_client_state(text)`: Rozetka-specific utility to find API endpoints hidden in `rz-client-state`.
- `_map_ld_json_offer(item)`: Standard mapper for Schema.org Product/Offer objects to MAPI schema.

---

## 7. Step-by-Step: Implementing a New Module

### Step 1: Create the Module
File: `scrapers/mapi_scraper/sites/{site_id}.py`

Minimum Template:
```python
import asyncio
from scrapers.mapi_scraper.base import BaseModule
from scrapers.mapi_scraper.http import (
    _make_sync_fetcher, _make_async_fetcher, _ok, _err, logger
)

class {Site}API:
    def normalize(self, raw_data: dict) -> dict:
        # 1. Extract products and pagination info
        # 2. Return structure: {"products": [...], "pagination": {"total_pages": int, "page_index": int}}
        return {"products": [], "pagination": {"total_pages": 0, "page_index": 1}}

class {Site}Module(BaseModule):
    SITE_ID = "{site_id}"
    DOMAINS = ["{site}.com.ua", "{site}.ua"]

    def __init__(self):
        self._api = {Site}API()

    def scrape_url(self, url, page=1, debug=False):
        return asyncio.run(self._scrape_impl(url, page, debug, _make_sync_fetcher()))

    async def async_scrape_url(self, url, page=1, debug=False, proxy=None):
        return await self._scrape_impl(url, page, debug, _make_async_fetcher(proxy))

    async def _scrape_impl(self, url, page, debug, fetch) -> dict:
        code, data, meta = await fetch(self.SITE_ID, url, parse_json=False)
        if code != 200: return _err(self.SITE_ID, "url", f"HTTP {code}", code)
        
        # Primary parsing logic here...
        norm = self._api.normalize({"source": "html", "html": data})
        return _ok(self.SITE_ID, norm["products"], "url")
```

### Step 2: Register in `__init__.py`
1. Import your class at the top.
2. Call `_register_module({Site}Module())`.

### Step 3: Add Pagination Rule
In `paginator.py`, update `_get_paginated_url` to handle the new site ID if it requires special URL injection (e.g., adding `/p-2/` or `?page=2`).

---

## 8. The `_scrape_impl` Pattern

To avoid code duplication between `scrape_url` (sync) and `async_scrape_url` (async), use a shared `_scrape_impl`.

Passing `fetch` as a dependency allows the same business logic to run in both contexts:
- In sync path, `fetch` wraps the blocking `requests` library.
- In async path, `fetch` uses `AsyncSession`.

```python
async def _scrape_impl(self, url, page, debug, fetch):
    # fetch is a coroutine passed from the caller
    code, data, meta = await fetch(site, url, ...) 
```

**Special Case: execjs**
If using `execjs` (as in `allo.py`), wrap it in an executor because it's synchronous:
```python
loop = asyncio.get_running_loop()
result = await loop.run_in_executor(None, self._run_js_parsing, raw_html)
```

---

## 9. Logging and Debug Mode

### Logging
Always pass `extra={"site": self.SITE_ID}` to the logger:
```python
logger.info("Starting api discovery", extra={"site": self.SITE_ID})
```
This enables the `[site_id]` prefix in logs.

### Debug Mode (`debug=True`)
- Activates `_save_debug_item()`.
- Saves two files per request to `results/run_{timestamp}/`:
    1. `NNN_{site}_{step}_..._raw.json`: Timing meta and raw response.
    2. `NNN_{site}_{step}_..._norm.json`: The extracted products.

**Implementation Pattern in `_scrape_impl`:**
```python
async def _scrape_impl(self, url, page, debug, fetch):
    # 1. Fetch data
    code, data, meta = await fetch(self.SITE_ID, url, ..., save_raw=debug)
    
    # 2. Normalize
    norm = self._api.normalize(data)
    
    # 3. Save debug files if requested
    if debug:
        from scrapers.mapi_scraper.http import _save_debug_item
        _save_debug_item(self.SITE_ID, "discovery", url, meta, data, norm["products"])
        
    return _ok(self.SITE_ID, norm["products"], "url")
```

---

## 10. Rules and Constraints

- **DO NOT** use `self.state` in `*API` or `*Module` classes. Every scrape call must be independent (stateless) to support parallel execution.
- **DO NOT** import from `core/` or `gui/` modules. MAPI is a leaf dependency.
- **DO NOT** use bare `except: pass`. Always log the error at `debug` or `warning` level.
- **DO NOT** call `asyncio.run()` inside an async context (e.g., inside `_scrape_impl`).
- **MUST** return `{"products": [], "pagination": {...}}` from `normalize`.
- **MUST** include all domain variants in `DOMAINS` for auto-detection.

---

## 11. Common Mistakes

| Mistake | Consequence | Fix |
|---|---|---|
| Storing page index in `self.page` | Race condition in large batch | Return page info from `normalize` |
| Missing `extra={"site": ...}` | Logs are hard to filter | Always provide the extra dict |
| Forgeting `_register_module` | `get_module` returns `None` | Add to `__init__.py` |
| Calling `scrape_url` from async | Loop error | Call `async_scrape_url` |
| Using `time.sleep` in `_scrape_impl` | Blocks entire async loop | Use `await asyncio.sleep()` |

---
*Generated based on the MAPI modular architecture refactor.*
