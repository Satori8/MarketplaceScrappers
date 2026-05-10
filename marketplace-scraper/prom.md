# Prom.ua Scraper Documentation

## Overview
The Prom.ua scraper is designed to handle both standard keyword searches and direct product/category parsing. It supports two execution modes: **Browser (Playwright)** and **HTTPX (Requests)**.

## High-Precision Stock Detection
As of the latest update, the scraper uses a sophisticated heuristic to detect product availability based on technical markers provided by the site's layout (`data-qaid` attributes).

### In-Stock Markers
A product is considered **InStock** if any of the following are found:
- An element with `data-qaid="buy-button"` containing the text **"Купити"**.
- A `product_presence` label containing the text **"В наявності"**.

### Out-of-Stock Markers
A product is marked as **OutOfStock** and filtered if the "Skip Out of Stock" option is enabled in the GUI:
- An element with `data-qaid="see_button"` containing the text **"Дивитись"** (this replaces the buy button for unavailable items).
- A `product_presence` label containing the text **"Недоступний"**.

## Parsing Modes
1. **Playwright (Browser)**: Uses a JavaScript evaluate payload for atomic data extraction, ensuring high accuracy against dynamic Angular components.
2. **HTTPX**: Fast, request-based parsing using BeautifulSoup for large-scale discovery where JavaScript rendering is not mandatory.

## Configuration
Selectors for Prom.ua are managed via `config.yaml` but are supplemented by hardcoded fallbacks in `prom.py` to ensure resilience against layout changes.
