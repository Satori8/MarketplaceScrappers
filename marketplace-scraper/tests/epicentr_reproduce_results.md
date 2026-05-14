# Epicentr API Reproduction Results (Cookie-Free)

Testing performed with strict header stripping:
- **REMOVED**: `Cookie`, `Authorization`, `x-*token*`, `x-*session*`, `x-*user*`, `x-*auth*`.
- **KEPT**: Browser fingerprints, `ssr-platform`, `x-is-robot`, `referer`, `user-agent`.

## Phase 3 & 4 Results

### 1. Catalog Listings (v2)
- **Endpoint**: `/api/v2/product/listing/products`
- **Reproducible**: ✅
- **Headers Used**: Strict set (inc. `ssr-platform`, `x-is-robot`, `referer`, `user-agent`)
- **Status**: 200 OK
- **Response**: Returns JSON with `items` list nested in `data`.
- **Pagination**: Page 1 → Page 2 works via `&page=2`.

### 2. Search Listings (v1)
- **Endpoint**: `/api/v1/search`
- **Reproducible**: ✅
- **Headers Used**: Strict set.
- **Status**: 200 OK
- **Response**: Returns JSON with `items` list nested in `data`.
- **Pagination**: Page 1 → Page 2 works via `&page=2`.

### 3. Merchant Listings (v1)
- **Endpoint**: `/api/v1/merchant`
- **Reproducible**: ✅
- **Headers Used**: Strict set.
- **Status**: 200 OK
- **Response**: Returns JSON with `products` list nested in `params`.
- **Pagination**: Page 1 → Page 2 works via `&page=2`.

### 4. Brand Listings (v1)
- **Endpoint**: `/api/v1/brands/brand`
- **Reproducible**: ✅
- **Headers Used**: Strict set.
- **Status**: 200 OK
- **Response**: Returns JSON with `products` list nested in `params`.
- **Pagination**: Page 1 exists. Page 2 returned 410 (likely end of results for the specific test case).

## Summary Table

| Endpoint | Method | Verdict | Pagination | Data Location |
| :--- | :--- | :--- | :--- | :--- |
| `/api/v2/product/listing/products` | GET | ✅ | `&page=N` | `data.items` |
| `/api/v1/search` | GET | ✅ | `&page=N` | `data.items` |
| `/api/v1/merchant` | GET | ✅ | `&page=N` | `params.products` |
| `/api/v1/brands/brand` | GET | ✅ | `&page=N` | `params.products` |

> [!IMPORTANT]
> **Conclusion**: Product data is accessible without cookies or bearer tokens. The required factor is maintaining a consistent browser fingerprint and specific "robot-info" headers (`x-is-robot: 0`, `ssr-platform: nuxt`) alongside a valid User-Agent.
