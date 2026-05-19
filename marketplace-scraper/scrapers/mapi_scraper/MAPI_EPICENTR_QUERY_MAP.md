# Epicentrk REST API Query Map (MAPI)

Epicentr utilizes a stateless JSON API split across two versions (v1 and v2) to serve product listings, searches, and merchant data.

## 1. Connection Details
- **v1 Root**: `https://api.epicentrk.ua/api/v1`
- **v2 Root**: `https://epicentrk.ua/api/active/v2`
- **Method**: `GET`
- **Region**: `store_id=2` (Default for Kiev/Global).

---

## 2. API Operations Map

| Operation | Context | Endpoint | Parameters |
| :--- | :--- | :--- | :--- |
| **Listing** | Category | `v2/.../products` | `query[]={path}`, `page={n}`, `page_size=60` |
| **Search** | Search | `v1/search` | `find={query}`, `page={n}`, `search_size=40` |
| **Merchant** | Seller | `v1/merchant` | `name={slug}`, `page_size=60` |
| **Brand** | Brand | `v1/brands/brand` | `slug={slug}`, `page_size=60` |
| **Full Card** | Details | `v1/product/card/full` | `slug={slug}` |

---

## 3. Sample Input & Response Structures

### Category Listing
**Request**: `GET /product/listing/products?store_id=2&query[]=/raznoobraznye-instrumenty-i-oborudovanie/pylesosy&lang=ua`

**Response Structure (Inner Data)**:
```json
{
  "data": {
    "items": [
      {
        "id": 8090123,
        "name": "Пилосос Epic Power",
        "price": 4500,
        "availabilityStatus": {
          "code": 100,
          "title": "В наявності"
        },
        "merchantId": "epicentrk",
        "brandName": "EpicBrand",
        "sectionsUa": "Інструменти / Пилососи",
        "url": "/ua/shop/p8090123.html",
        "img": { "url": "https://epicentrk.ua/img.jpg" }
      }
    ],
    "totalPages": 20,
    "pageIndex": 1
  }
}
```

### Search Results
**Request**: `GET /search?find=bosch&store_id=2&lang=ua&page=1`

**Response Structure**:
```json
{
  "total": 1200,
  "data": {
    "items": [...]
  }
}
```

---

## 4. Normalization Mapping (Status Codes)

| Status Code | Label | Description |
| :--- | :--- | :--- |
| `100` | **В наявності** | Available. |
| `400` | **Немає в наявності** | Out of Stock. |
| `250` / `300` | **Під замовление** | Backorder. |
| `500` | **Знятий з виробництва** | Discontinued. |

---

## 5. Header Checklist
```http
Accept: application/json
SSR-Platform: nuxt
X-Is-Robot: 0
Referer: https://epicentrk.ua/
```
