# Fast Scraper API

A high-performance marketplace scraping layer built on top of `curl_cffi` to bypass Cloudflare/WAF with minimal overhead. It prioritizes direct API interaction but automatically falls back to SSR (Server-Side Rendered) state extraction when APIs are blocked or restricted.

## Features
- **Stealth Fetching**: Uses `curl_cffi` with `chrome124` impersonation.
- **SSR Fallbacks**: Automatically extracts data from `window.__INITIAL_STATE__`, `window.__NUXT__`, `window.__ALLO__`, and `ld+json` if JSON APIs return 404/403.
- **GraphQL Support**: Fully implemented GraphQL dispatching for Prom.ua.
- **Mode: URL**: Special universal mode to scrape any category or product listing directly by its URL.
- **Automatic Retries**: Integrates with `AntiBotManager` to harvest cookies via Playwright if a hard block is detected.

## Supported Marketplaces
1. **Rozetka**: API + LD-JSON fallback.
2. **Prom**: GraphQL (Search, Seller, Product) + Apollo State fallback.
3. **Epicentr**: API + window.__NUXT__ fallback.
4. **Allo**: API + window.__ALLO__ fallback.
5. **Hotline**: Direct JSON-param API.

## Usage

### Simple Scrape
```python
from fast_api.fast_scraper import scrape

# Get products from a category URL (Universal Mode)
res = scrape("rozetka", "url", url="https://build.rozetka.com.ua/ua/vinilovie-oboi/c4657848/")

if res["ok"]:
    print(res["data"])
else:
    print(f"Error: {res['error']}")
```

### Modes
- `product`: Get item details by ID.
- `search`: Keyword search.
- `seller`: List products for a specific seller.
- `filtered_page`: Category scraping with filters.
- `characteristics`: Detailed technical specs.
- `reviews`: Customer reviews.
- `categories`: Catalog tree navigation.
- `url`: Direct listing extraction from any valid marketplace URL.

## Reliability
The API includes built-in **`normalize()`** methods for each site-specific class (`PromAPI`, `EpicentrAPI`, `AlloAPI`, `RozetkaAPI`). These methods unify volatile raw data (from hidden APIs or SSR states) into a consistent schema:
- **Unified ID/SKU**: Distinct `id` (backend) and `sku` (article) mapping.
- **Characteristics**: Automatic transformation of site-specific attributes into a standard `properties[]` array.
- **Pagination**: Consistent `page_index` and `total_pages` metadata across all providers.
- **Merchant Mapping**: Cross-references internal data to identify sellers even when not directly present in the product listing.
