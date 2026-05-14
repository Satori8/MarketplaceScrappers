# Epicentr API Agent Implementation Guide

This guide specifies the implementation for the Epicentr marketplace scraper module using the reverse-engineered API endpoints. All endpoints have been confirmed to work **without cookies** or authentication headers, provided specific fingerprint headers are maintained.

### Overview
- **Method**: All requests are `GET`.
- **Client**: Use `curl_cffi` with `impersonate="chrome120"` to handle TLS fingerprints.
- **Fingerprint**: Maintain `ssr-platform: nuxt` and `x-is-robot: 0`.

---

### Endpoints

#### 1. Catalog / Category Listing
- **URL Pattern**: `https://api.epicentrk.ua/api/v2/product/listing/products?store_id=2&lang=ua&page_size=60&rankSort=by_rank&query[]={encoded_path}&page={page_number}`
- **Placeholders**:
  - `{encoded_path}`: HTML URL path (e.g., `/shop/komplektuyuschie-k-filtram-dlya-vody/`).
  - `{page_number}`: Incrementing integer starting at 1.
- **Required Headers**: See [Minimal Headers](#minimal-headers).
- **Pagination**: Increment `page` parameter.
- **Response Structure**:
  - List: `data.items`
  - Total: `data.totalCount`

#### 2. Search listing
- **URL Pattern**: `https://api.epicentrk.ua/api/v1/search?find={query}&store_id=2&lang=ua&search_size=40&page={page_number}`
- **Placeholders**:
  - `{query}`: URL-encoded search string.
- **Response Structure**:
  - List: `data.items`
  - Total: `total` (top level) or `data.totalCount`

#### 3. Merchant storefront
- **URL Pattern**: `https://api.epicentrk.ua/api/v1/merchant?lang=ua&name={merchant_name}&page_size=60&page={page_number}`
- **Placeholders**:
  - `{merchant_name}`: Merchant slug.
- **Response Structure**:
  - List: `params.products`
  - Total: `params.total`

---

### Minimal Headers
```python
HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "uk-UA,uk;q=0.9",
    "ssr-platform": "nuxt",
    "x-is-robot": "0",
    "referer": "https://epicentrk.ua/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
}
```

### curl_cffi Implementation Pattern
```python
from curl_cffi import requests

def fetch_epic_category(path, page=1):
    url = f"https://api.epicentrk.ua/api/v2/product/listing/products"
    params = {
        "store_id": 2,
        "lang": "ua",
        "page_size": 60,
        "rankSort": "by_rank",
        "query[]": path,
        "page": page
    }
    
    response = requests.get(url, params=params, headers=HEADERS, impersonate="chrome120")
    response.raise_for_status()
    data = response.json()
    return data.get("data", {}).get("items", [])
```

### Known Failure Modes
- **403 Forbidden**: Usually triggered by missing `ssr-platform` or `x-is-robot` headers.
- **410 Gone**: Occurs when requesting a page number beyond the available results.
- **0 Products Returned**: Occurs if the `query[]` path is malformed or doesn't start/end with `/`.

### Out of Scope for Agent
- Do NOT implement token/cookie acquisition (unnecessary).
- Do NOT use standard `httpx` or `requests` (TLS fingerprinting may cause blocks).
- Do NOT change `store_id=2` unless regional variations are specifically requested.
