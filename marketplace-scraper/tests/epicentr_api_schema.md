# Epicentr API Schema

## Unique Endpoints
1. `GET /api/v2/product/listing/products`
2. `GET /api/v1/search`
3. `GET /api/v1/merchant`
4. `GET /api/v1/brands/brand`

---

### 1. Endpoint: `/api/v2/product/listing/products`
- **HTTP Method:** GET
- **Serves:** Catalog categories, Sub-categories, and Filtered catalogs.
- **Payload Structure (URL Queries):**
  - `store_id`: integer (e.g. `2`)
  - `query[]`: string containing the URL path of the category and selected filters (e.g. `%2Fshop%2Framki-dlya-foto%2Ffilter%2Fbrand-is-rumz6vpdhtfm79yh%2Fapply%2F`)
  - `lang`: string (`ua`)
  - `page_size`: integer (`60`)
  - `rankSort`: string (`by_rank`)
  - `page`: integer (used for pagination)
- **Pagination Pattern:** Uses the `page` query parameter (e.g., `&page=2`). Without it, page 1 is assumed.

### 2. Endpoint: `/api/v1/search`
- **HTTP Method:** GET
- **Serves:** Global product search.
- **Payload Structure (URL Queries):**
  - `find`: string (search keywords, e.g. `t200`)
  - `store_id`: integer (`2`)
  - `lang`: string (`ua`)
  - `search_size`: integer (`40`)
  - `page`: integer 
- **Pagination Pattern:** Uses the `page` query parameter (e.g., `&page=2`).

### 3. Endpoint: `/api/v1/merchant`
- **HTTP Method:** GET
- **Serves:** Third-party seller (merchant) storefront and listing.
- **Payload Structure (URL Queries):**
  - `lang`: string (`ua`)
  - `name`: string (merchant slug name, e.g. `avtomoda`)
  - `page_size`: integer (`60`)
  - `brands[]`: string or array of strings (e.g. `AVTM`)
  - `page`: integer
- **Pagination Pattern:** Uses the `page` query parameter (e.g., `&page=3`).

### 4. Endpoint: `/api/v1/brands/brand`
- **HTTP Method:** GET
- **Serves:** Brand-specific category listing.
- **Payload Structure (URL Queries):**
  - `store_id`: integer (`2`)
  - `slug`: string (brand name slug, e.g. `bosch`)
  - `lang`: string (`ua`)
  - `page_size`: integer (`60`)
  - `section`: integer (category section id, e.g. `2569`)
  - `prop_XXXX[0]`: array or string specifying filter property
  - `page`: integer
- **Pagination Pattern:** Uses the `page` query parameter.

---

## Headers Classification

- `accept`: **likely-required**
- `accept-language`: **likely-required**
- `ssr-platform`: (`nuxt`) **likely-required**
- `x-is-robot`: (`0`) **likely-required**
- `x-fuser-id`: **session-specific** / fingerprint
- `x-xsrf-token`: **session-specific** / required for CSRF protection
- `sec-ch-ua`: **fingerprint**
- `sec-ch-ua-mobile`: **fingerprint**
- `sec-ch-ua-platform`: **fingerprint**
- `sec-fetch-dest`: **fingerprint**
- `sec-fetch-mode`: **fingerprint**
- `sec-fetch-site`: **fingerprint**
- `cache-control`: **ignorable**
- `pragma`: **ignorable**
- `priority`: **ignorable**

*(Note: Original requests were dispatched via JS with `credentials: "include"`, implying cookies were transmitted but obfuscated from the explicit header dict).*
