# Prom.ua GraphQL API Reproduction Guide
**For AI Agents and Developers**

This document describes how to implement a `curl_cffi` based API scraper for Prom.ua's GraphQL endpoints, without relying on cookies or authentication sessions. It covers reverse-engineered URL parsing, schema construction, payload formation, and how WAF limitations are bypassed.

## 1. Environment Requirements
- Python Library: `curl_cffi` must be used to bypass CloudFlare / Anti-Bot mechanisms because it matches real browser TLS/JA3 fingerprints. 
- Setting: `impersonate="chrome124"` (or `chrome110`). Standard Python `requests` or `httpx` will fail with 403 Forbidden.

## 2. API Endpoint & Missing Auth
The endpoint is completely public for product listing.

- **URL:** `https://prom.ua/graphql`
- **Method:** `POST`
- **Headers:** No session cookies needed. However, you MUST pass specific `X-` headers mimicking the Apollo client:

```python
HEADERS = {
    "content-type": "application/json",
    "accept": "*/*",
    "accept-language": "uk-UA,uk;q=0.9",
    "x-language": "uk", 
    "x-requested-with": "XMLHttpRequest",
    "x-apollo-operation-name": "{OPERATION_NAME}", # e.g. "CategoryListingQuery"
    "x-forwarded-proto": "https",
    "origin": "https://prom.ua",
    "referer": "{ORIGINAL_REQUEST_URL}"
}
```

## 3. URL Parsing to Payload Variables

Prom.ua applies a universal variable object. Query parameters from a standard URL map directly to the `params` dictionary in the GraphQL variables payload.

**Parsing Rules:**
1. Check the base URL to identify the operation:
   - `.../ua/search?search_term=...` -> `SearchListingQuery`
   - `.../ua/c{ID}-{slug}.html` -> `CompanyListingQuery`
   - `.../ua/brands/{alias}` -> `ManufacturerListingQuery`
   - `.../ua/{slug}...` -> `CategoryListingQuery`
2. Every `url_param=value` belongs in the GraphQL variable `params: { ... }`.
3. If a parameter appears multiple times (`?a11867=123&a11867=456`), it maps to an array: `"params": { "a11867": ["123", "456"] }`.
4. Pagination: Extracted from `page=N` in the query (or `;2` in legacy URL slugs).
   `limit = 29` (default for Prom)
   `offset = (page - 1) * limit`
5. Base elements like `search_term` or `company_id` are placed in the root of the variables JSON, AND often redundantly within the `params` wrapper for backend routing.

### Example Variable Mapping: Wait, how does it look?

**Original URL:** 
`https://prom.ua/ua/c3889692-greatshopping.html?a1315=70330&a11867=313454&a11867=279079&page=2`

**Extracted GraphQL Variables:**
```json
{
  "opinionPageType": "portal-company_page",
  "regionId": null,
  "company_id": 3889692,
  "limit": 29,
  "offset": 29,
  "showShowroomProducts": false,
  "params": {
    "company_id": "3889692",
    "company_name": "greatshopping",
    "a1315": "70330",
    "a11867": ["313454", "279079"],
    "binary_filters": []
  }
}
```

## 4. Universal GraphQL Query Schema

Prom.ua uses distinct root objects, but the internal return structures map back to a universal `ListingPage`. The query structure looks like this:

```graphql
query CategoryListingQuery(
  $alias: String!, $params: Any, $offset: Int, $limit: Int, $regionId: Int, $subdomain: String
) {
  listing: categoryListing(
    alias: $alias, params: $params, offset: $offset, limit: $limit, region: {id: $regionId, subdomain: $subdomain}
  ) {
    page {
      total
      products {
        product {
          id
          name: nameForCatalog
          price
          priceCurrencyLocalized
          urlText
          categoryIds
          image(width: 200, height: 200)
          presence {
            presence
            isAvailable
            __typename
          }
          company {
            id
            name
            slug
            deliveryStats {
              deliverySpeed
            }
            __typename
          }
          __typename
        }
        __typename
      }
      __typename
    }
    __typename
  }
}
```

*For `SearchListingQuery`, replace `categoryListing(alias...)` with `searchListing(search_term...)`.*
*For `CompanyListingQuery`, replace `categoryListing(alias...)` with `companyListing(company_id...)`.*
*For `ManufacturerListingQuery`, replace `categoryListing(alias...)` with `manufacturerListing(alias...)`.*

> **⚠️ Critical Observation:** The products are NOT stored at `listing.items`. They are stored under `listing.page.products[].product`.

## 5. Python Implementation Template

When building `PromAPI.normalize` or the internal scraper routine, use this template:

```python
import urllib.parse
from curl_cffi import requests

def build_payload_from_url(url: str):
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query)
    
    params = {"binary_filters": []}
    for key, values in query.items():
        if key in ("search_term", "page"):
            continue
        params[key] = values[0] if len(values) == 1 else values
            
    page = int(query.get("page", ["1"])[0])
    limit = 29
    offset = (page - 1) * limit
    
    # Example for search:
    variables = {
        "search_term": query.get("search_term", [""])[0],
        "params": params,
        "regionId": None,
        "limit": limit,
        "offset": offset
    }
    
    payload = {
        "operationName": "SearchListingQuery",
        "variables": variables,
        "query": "...(Insert Query Schema)..."
    }
    return payload

def scrape_prom(url: str):
    payload = build_payload_from_url(url)
    
    headers = {
        "content-type": "application/json",
        "x-language": "uk",
        "x-requested-with": "XMLHttpRequest",
        "x-apollo-operation-name": payload["operationName"],
        "referer": url,
        "origin": "https://prom.ua",
    }
    
    response = requests.post(
        "https://prom.ua/graphql",
        headers=headers,
        json=payload,
        impersonate="chrome124",
        timeout=30
    )
    
    data = response.json()["data"]["listing"]["page"]
    total_results = data["total"]
    products = data["products"]
    
    return total_results, products
```
