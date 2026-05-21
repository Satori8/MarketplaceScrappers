# Marketplace Intelligence Tool

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-WAL_Mode-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-Automated-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)
![Gemini 3 Flash](https://img.shields.io/badge/AI-Gemini_3_Flash-4285F4?style=for-the-badge&logo=google-gemini&logoColor=white)

**An industrial-grade competitive intelligence engine that transforms fragmented Ukrainian e-commerce data into actionable business structured insights.**

---

## 💼 Business & Product Context
In the highly competitive Ukrainian e-commerce landscape (dominated by Rozetka, Prom, and Allo), price agility and assortment depth define market share. For B2B sellers, manually tracking thousands of SKUs across multiple platforms is a bottleneck.

This tool solves the **fragmented data problem** by:
- **Consolidating Multi-Channel Data:** Aggregating pricing, availability, and specs from 6+ major marketplaces.
- **Enabling Price Intelligence:** Moving from "guessing" to data-driven pricing through automated snapshots and historical monitoring.
- **Reporting & Audits:** Generating professional, multi-sheet Excel reports with price dynamics, KPI summaries, and automated delta calculations.

---

## 🏗️ Architecture Overview

The system is built on a modular "MAPI" (Marketplace API) engine, designed to handle the heterogeneity of web architectures—ranging from legacy BS4 parsing to modern GraphQL and Nuxt.js SSR applications.

```mermaid
graph TD
    UI[Tkinter Dashboard / CustomTkinter] --> Controller[Task Scheduler & Serialized Writer]
    Controller --> Engine{MAPI Engine}
    
    subgraph Data Extraction Layers
        Engine --> HTTP[curl_cffi / TLS Fingerprint]
        Engine --> SSR[execjs / Node.js State Extraction]
        Engine --> Browser[Playwright / Selenium Fallback]
        Engine --> GQL[GraphQL / Apollo Fragments]
    end
    
    HTTP -.-> |REST| Sites
    SSR -.-> |Nuxt __NUXT__| Sites
    GQL -.-> |Prom.ua GQL| Sites
    Browser -.-> |DOM Scrape| Sites
    
    Sites[(Rozetka, Prom, Allo, etc.)] --> Parser[Modular Normalizer]
    Parser --> Intelligence[Gemini AI Normalization]
    Intelligence --> Storage[(SQLite WAL Mode)]
    Storage --> Reporting[Reporting Engine / openpyxl]
    Reporting --> Export[Professional XLSX Reports]
```

---

## 🛠️ Technical Deep Dive: Why It’s Hard

Building a scraper is easy; building a **resilient scraping pipeline** that survives production anti-bot measures is an engineering challenge.

### 1. The Cat-and-Mouse Game (TLS & Fingerprinting)
Modern marketplaces use sophisticated WAFs (Cloudflare/Akamai) that detect standard Python `requests` or `httpx` via TLS fingerprinting.
- **Solution:** Integrated `curl_cffi` to impersonate browser-level TLS fingerprints (JA3/JA3S). This allows for high-speed HEAD and GET requests without the overhead of a headless browser.

### 2. State Extraction & GraphQL Precision
Many modern targets (like Allo or Prom) either bake their data into internal JS state objects or use GraphQL.
- **Strategy:** Extracted raw `__NUXT__` objects via `execjs` for Allo and implemented a specialized **GraphQL Master Spec** for Prom.ua, ensuring 100% data fidelity compared to fragile HTML scraping.

### 3. SQLite Concurrency & Serialized Writes
Handling thousands of concurrent requests while maintaining a local database requires careful state management.
- **Solution:** Utilized **SQLite in WAL (Write-Ahead Logging) mode** with a dedicated `DbWriteQueue`. All writes are serialized through a single writer thread, eliminating "database is locked" errors during high-concurrency MAPI scrapes.

### 4. Professional Reporting Engine
Converting raw data into business value requires more than a CSV export.
- **Solution:** Built a multi-sheet reporting engine using `openpyxl` that generates comparison reports between snapshots, highlighting "New", "Gone", and "Changed" prices with automated KPI visualizations.

---

## ⚡ Key Technical Decisions

| Feature | Implementation | Rationale |
| :--- | :--- | :--- |
| **Concurrency** | `asyncio` + `TaskScheduler` | High throughput for I/O bound network requests. |
| **Business Layer** | Client -> Task -> Snapshot | Enables project-based management and historical tracking. |
| **Stability** | Absolute Path Enforcement | Centralized data storage (`/data/`) that thrives even after project relocation. |
| **GUI Aesthetics** | `CustomTkinter` Modernization | Replaced legacy widgets with modern, compact controls and custom scrollbars. |
| **Specialized Tools** | GQL Builder & Contact Scraper | Standalone utilities for advanced technical monitoring and lead generation. |

---

## 🚀 Roadmap & Current Status

- [x] **Phase 1: Multi-Engine Scraper:** Completed MAPI architecture for Rozetka, Prom, Allo, and Epicentr.
- [x] **Phase 2: Data Robustness:** Centralized directory structure and absolute path enforcement.
- [x] **Phase 2.1: BI Layer:** Implemented "Client → Task → Snapshot" hierarchy for historical persistence.
- [x] **Phase 2.2: Professional Reporting:** Multi-sheet Excel export engine with price dynamics.
- [x] **Phase 3: Data Integrity Refinement:**
  - [x] Modular MAPI refactor — site logic isolated in `sites/` package.
  - [x] Async pagination stability — Rozetka, Allo, and Producer endpoint fixes.
  - [x] Stateless Epicentr API integration (v1/v2).
  - [x] Prom GraphQL overrides — externalized query templates (`prom_queries.json`).
  - [x] Allo lightweight AJAX API with `_DEEPLINK_CACHE` for pagination speed.
  - [x] Debug mode — raw JSON + normalized results persisted to `results/` with human-readable timestamps.
  - [x] Unified availability parsing — case-insensitive `parse_availability_to_code` helper.
  - [x] Allo: Robust `stock_status` parsing (string + integer formats).
  - [x] Allo: Category fallback to last breadcrumb title when `category` is `None`.
  - [x] Prom: `isDisabled: true` → out-of-stock support in GQL query templates and parser.
  - [x] DB Viewer: `Mode` column (discovery/tracking) on Snapshots list + Details panel showing scope params inline.
- [ ] **Phase 4: Web Dashboard:** Transitioning from Tkinter to a Next.js / FastAPI web interface.

---

**Built with precision for the Ukrainian e-commerce market.**  
*Last updated: 2026-05-21 — Phase 3.3 Data Integrity complete.*
