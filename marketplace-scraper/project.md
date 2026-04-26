# Marketplace Scraper — Project Documentation

## Project status
Current stage: 14 — Data Visualization & Deep Scrape Suite (done, audit in progress)
Last updated: 2026-04-23 16:45

---

## Architecture Overview

### Entry Point
- `main.py` → `gui/app.py` → `gui/main_window.py` (MainWindow)

### Execution Flow
1. User fills keywords/links → clicks **RUN BATCH**
2. `run_batch()` (daemon thread) builds a flat list of `(mp, method, query)` tasks
3. `ThreadPoolExecutor(max_workers=10)` calls `scheduler.run_individual_discovery()` per task
4. Each task calls `asyncio.run(scheduler._run_scraper_async(mp, method, task))`
5. `_run_scraper_async` instantiates the scraper, calls `search_products()`, upserts results via `ProductRepository`
6. After all futures complete → `asyncio.run(scheduler.normalize_all_pending())` — Global AI pass
7. Products normalized in batches of 15 via `DataNormalizer` → `GeminiClient`

### Key Design Decisions
| Decision | Reason |
|----------|--------|
| SQLite WAL mode | Safe concurrent writes from parallel scraper threads |
| Thread-local DB connections | `sqlite3` connections must not be shared across threads |
| Playwright visible mode | Anti-bot: headless browsers are more detectable |
| `queue.Queue` + `root.after()` | Non-blocking GUI: scrapers run in threads, GUI receives events via queue |
| Gemini model caching (`_last_working_model`) | Skip 404 retries on next calls |
| Multi-Channel Log Console | Tabbed Notebook: ALL / AI / SCHEDULER / per-MP / SYSTEM |
| Flat Discovery Task Pool | Each `(mp, query)` is an independent job; fast scrapers don't wait for slow peers |
| Global Normalization Phase | Single AI batch after all discovery — saves RAM/CPU, avoids redundant calls |
| Hybrid Discovery | Keyword searches AND direct marketplace URLs in the same batch |

---

## File Map

| File | Status | Purpose |
|------|--------|---------|
| `main.py` | ✅ | Entry point, CLI arg parsing, launches `gui/app.py` |
| `gui/app.py` | ✅ | Tkinter root creation, calls `MainWindow` |
| `gui/main_window.py` | ✅ (has bugs) | Main dashboard: LIVE DATA table, sidebar, log tabs |
| `gui/db_browser_window.py` | ✅ (has bugs) | Advanced DB browser: filters, deduplication, export |
| `gui/direct_urls_window.py` | ✅ | Toplevel for pasting target URLs |
| `gui/api_status_window.py` | ✅ | Shows status of each Gemini key per model |
| `gui/styles.py` | ✅ | COLORS, FONTS, `apply_styles()` for ttk |
| `core/models.py` | ✅ | Dataclasses: `RawProduct`, `NormalizedProduct`, `ScrapeTask`, `ScrapeResult` |
| `core/scheduler.py` | ✅ (has bugs) | `TaskScheduler`: discovery pool, `normalize_all_pending()` |
| `core/normalizer.py` | ✅ | `DataNormalizer`: batches titles → Gemini → `NormalizedProduct` |
| `core/anti_bot.py` | ✅ | Random delays, UA rotation, stealth, captcha detection |
| `core/cache.py` | ✅ | Simple in-memory cache (unused in main flow) |
| `db/database.py` | ✅ | Thread-local SQLite connections, WAL, schema init |
| `db/product_repo.py` | ✅ (has bugs) | CRUD: `upsert_product`, `search_products`, `save_specs` |
| `db/migrations.py` | ✅ | Simple column-add migrations |
| `ai/gemini_client.py` | ✅ (has bugs) | Key rotation, rate limiting, model fallback, JSON parsing |
| `ai/normalizer.py` | ✅ | Thin wrapper (re-exports `DataNormalizer`) |
| `ai/schema_generator.py` | ✅ | Gemini-based schema auto-generation (secondary feature) |
| `scrapers/base_scraper.py` | ✅ | ABC: config load, stealth wait, selector tools |
| `scrapers/rozetka.py` | ✅ (missing `_search_httpx`) | Playwright persistent context, Rozetka search |
| `scrapers/hotline.py` | ✅ | Playwright: product list → detail pages → offers extraction |
| `scrapers/prom.py` | ✅ | Playwright + httpx (httpx missing `stop_event`) |
| `scrapers/allo.py` | ✅ | Playwright + httpx |
| `scrapers/epicentrk.py` | ✅ | Playwright + httpx |
| `scrapers/custom_scraper.py` | ⚠️ (returns None) | Config-driven scraper with AI selector auto-detection |
| `scrapers/m_ua.py` | ❌ empty | Not implemented |
| `exporters/excel_exporter.py` | ✅ | openpyxl export |
| `config.yaml` | ✅ | All settings: Gemini keys, selectors, anti-bot params |

---

## Known Bugs (do NOT fix without user approval)

### 🔴 Critical

| ID | Location | Description |
|----|----------|-------------|
| B1 | `core/scheduler.py:150` | Dead code after `return` in `run_individual_discovery()` — session never finalized, `on_finished` never fires |
| B2 | `gui/main_window.py:295` | `"product"` queue message unpacked as `(prod, norm, db_id)` but `norm` is actually `is_new: bool` — causes `AttributeError` on `.normalized_specs` |
| B3 | `scrapers/custom_scraper.py:190` | `search_products()` has no `return` statement → returns `None`; also missing `stop_event` parameter |
| B4 | `db/product_repo.py:131` | `float(product.price)` not guarded when `product.price is None` but `old_price` is set → `TypeError` |
| B5 | `db/database.py:15` | `check_same_thread=False` passed alongside thread-local pattern — unnecessary, masks thread bugs |

### 🟠 High

| ID | Location | Description |
|----|----------|-------------|
| B6 | `ai/gemini_client.py:136` | `gemini-3.1-flash-preview` and `gemini-3-flash-preview` don't exist → 2 guaranteed 404s per call |
| B7 | `ai/gemini_client.py:107` | Rate limiter token consumed before request, not returned on failure |
| B8 | `ai/gemini_client.py:183` | `_save_config()` called on every generation → disk I/O + race condition between threads |
| B9 | `core/scheduler.py:212` | Index mapping `to_norm[i] → normalized[i]` breaks if normalizer returns fewer items than input |
| B10 | `core/normalizer.py:78` | Only checks `"products"` key in Gemini dict response; other wrapping keys cause crash |
| B11 | `scrapers/rozetka.py:221` | `parse_price` treats `.` as decimal — `"4.200"` → `4.2` instead of `4200` |
| B12 | `scrapers/prom.py:88` | `_search_httpx` missing `stop_event` param → STOP button ignored for Prom (httpx mode) |
| B13 | `gui/db_browser_window.py:54` | Button calls `self._on_normalize_all` but method is named `_on_normalize_remaining` → `AttributeError` |
| B14 | `gui/main_window.py:340` | `DbBrowserWindow` created without `scheduler=` arg → `self.scheduler is None` always → normalize broken |

### 🟡 Medium

| ID | Location | Description |
|----|----------|-------------|
| B15 | `gui/direct_urls_window.py:38` | Writes `master.target_links` directly — tight coupling, fragile |
| B16 | `scrapers/hotline.py:178` | Blocking httpx redirect-resolution in async loop per offer — can hang for minutes |
| B17 | `scrapers/allo.py:51`, `epicentrk.py:51` | `query_selector_all(None)` crashes Playwright if selectors missing from config |
| B18 | `core/scheduler.py:140` | `TaskScheduler.run()` is an empty stub — no scraping happens if called directly |
| B19 | `scrapers/rozetka.py:25` | `_search_httpx` method called but not defined → `AttributeError` if method != "Browser" |
| B20 | `gui/main_window.py:264` | `asyncio.run()` called from daemon thread for normalization — can fail on Windows |

---

## Database Schema (V1.8+)

```sql
CREATE TABLE products (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    url             TEXT NOT NULL UNIQUE,
    marketplace     TEXT NOT NULL,
    title           TEXT NOT NULL,
    brand           TEXT,
    model           TEXT,
    norm_brand      TEXT,        -- AI-extracted brand
    norm_model      TEXT,        -- AI-extracted model
    norm_voltage    TEXT,        -- normalized e.g. "12V"
    norm_capacity   TEXT,        -- normalized e.g. "100Ah"
    norm_category   TEXT,        -- e.g. "Акумулятор LiFePO4"
    is_relevant     INTEGER DEFAULT 1,
    category_path   TEXT,
    product_type    TEXT,
    image_url       TEXT,
    description     TEXT,
    first_seen_at   TEXT NOT NULL,
    last_seen_at    TEXT NOT NULL,
    is_active       INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE price_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id),
    price      REAL NOT NULL,
    currency   TEXT NOT NULL DEFAULT 'UAH',
    availability TEXT,
    scraped_at TEXT NOT NULL,
    scrape_session TEXT NOT NULL
);

CREATE TABLE product_specs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id     INTEGER NOT NULL REFERENCES products(id),
    schema_version TEXT NOT NULL,
    specs_json     TEXT NOT NULL,   -- same as raw_specs_json (BUG B23)
    raw_specs_json TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);

CREATE TABLE scrape_sessions (
    id             TEXT PRIMARY KEY,
    query          TEXT NOT NULL,
    product_type   TEXT,
    marketplaces   TEXT NOT NULL,
    status         TEXT NOT NULL,  -- 'running' | 'completed' | 'stopped'
    products_found INTEGER NOT NULL DEFAULT 0,
    errors_json    TEXT,
    started_at     TEXT NOT NULL,
    finished_at    TEXT
);
```

**Note:** `product_specs` UNIQUE constraint is on `(product_id)` via `INSERT OR REPLACE`. Each product has at most one spec row.

---

## Normalizer → DB field mapping

The normalizer returns `NormalizedProduct.normalized_specs` as a dict. Key names must match:

| Gemini JSON key | DB column | Note |
|-----------------|-----------|------|
| `Brand` | `norm_brand` | |
| `Model` | `norm_model` | |
| `Voltage` | `norm_voltage` | Normalized: `"12V"`, `"24V"` |
| `Capacity` | `norm_capacity` | Normalized: `"100Ah"` |
| `Category` | `norm_category` | |
| `is_relevant` | `is_relevant` | boolean → 0/1 |

---

## Config Structure (`config.yaml`)

```yaml
gemini:
  keys: [...]            # List of API keys (rotated)
  rotation_strategy: "on_limit"  # or "round_robin"
  model: "gemini-2.0-flash"      # Base model; also tried: 2.5-flash, 1.5-flash
  batch_size: 15                 # Products per Gemini call
  requests_per_minute: 10        # Sliding-window rate limit
  current_key_index: 0           # Persisted between runs

anti_bot:
  delay_min: 2.0
  delay_max: 6.0
  user_agents: [...]

marketplaces:
  rozetka:
    base_url / search_url / pages_limit / method / selectors
  prom: ...
  hotline: ...
  allo: ...
  epicentrk: ...
  custom:          # list of dicts, only first is used
    - name / base_url / search_url / pages_limit / selectors
```

---

## How to Run

```powershell
.\.venv\Scripts\activate
python main.py
```

1. **Keyword Scrape**: Enter comma-separated keywords → select marketplaces → **RUN BATCH**
2. **Link Scrape**: Click **LINK ENTRY** → paste URLs (one per line) → check **Use Target Links** → **RUN BATCH**
3. Watch **LIVE DATA** tab for real-time results; check **ROZETKA / PROM / AI** tabs for logs
4. Click **Browse Database** → filter, deduplicate, re-normalize old data, export to Excel

---

## Implemented Stages

- [x] Stage 1–13: Foundations, SQLite, Gemini AI, all 5 scrapers, Playwright anti-bot, GUI, parallel scraping
- [x] Stage 14: LIVE DATA table, Link Entry manager, DB Browser with filters + deduplication, Scheduler-integrated normalization
- [ ] Stage 15 (planned): Fix known bugs (B1–B20), add m.ua scraper, CLI mode
