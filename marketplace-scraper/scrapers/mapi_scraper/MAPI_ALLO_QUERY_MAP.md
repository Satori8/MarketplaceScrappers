# Allo AJAX API Query Map (MAPI)

This document describes the Allo.ua AJAX implementation, including the transition from SSR Discovery to lightweight background updates.

## 1. Connection Details
- **Base URLs**: 
  - Category: `https://allo.ua/ua/catalog/category/update/`
  - Search: `https://allo.ua/ua/catalogsearch/result/update/`
- **Method**: `GET`
- **Identifier**: `isAjax=1` must be present.

---

## 2. Discovery Phase (SSR)
Before AJAX can be used, the scraper extracts a `current_deeplink` from the HTML state of the page (cached per base URL).
- **Extraction**: `allo.current_deeplink = '{deeplink}';`

---

## 3. AJAX Parameters Map

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `p` | Int | Yes | Page number (1-indexed). |
| `category_id` | Int | Category only | Numeric ID of the target category. |
| `q` | String | Search only | Search keyword. |
| `toolbar` | JSON (Encoded) | Yes | Sorting mapping: `{"dir":"desc","order":"product_top_weight"}`. |
| `filters` | JSON (Encoded) | Yes | Active filters map: `{"attribute_code": [val1, val2]}`. |
| `isAjax` | 1 | Yes | Forces JSON response. |

---

## 4. Sample Output Structure (JSON)

**Endpoint**: `.../update/?p=1&isAjax=1&...`

**Response Structure**:
```json
{
  "product_list": {
    "items": [
      {
        "id": 12345,
        "sku": "555-666-BLK",
        "name": "Смартфон Allo Special",
        "url": "https://allo.ua/ua/smartfon-allo.html",
        "stock_status": 1,
        "brand": "BrandX",
        "price": {
          "amount": 9999,
          "currency": "UAH"
        },
        "seller_id": 5598,
        "seller_name": "Partner Store",
        "gallery": {
          "gallery": [
             { "image_xl": "https://i.allo.ua/img.jpg" }
          ]
        },
        "description_attributes": [
           { "label": "Екран", "value": "6.7\"" }
        ]
      }
    ],
    "total_count": 450
  },
  "layered_navigation": {
     "category_filter": [...]
  }
}
```

---

## 5. Normalization Mapping

| Standard Field | JSON Path | Notes |
| :--- | :--- | :--- |
| `sku` | `sku` | Primary key for Allo. |
| `price` | `price.amount` | |
| `avail_code` | `stock_status` | 1 = "В наявності". |
| `merchant_name`| `seller_name` | Fallbacks to Partner ID if name missing. |
| `category_name`| `layered_navigation.category_filter` | Extracted from filters or breadcrumbs. |
| `image` | `gallery.gallery[0].image_xl` | |

---

## 6. Header Checklist
```http
X-Requested-With: XMLHttpRequest
X-Use-Nuxt: 1
Accept: application/json
Referer: [Base URL]
```
