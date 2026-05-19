# Rozetka REST API Query Map (MAPI)

This document maps Rozetka URL patterns to their respective REST API operations and response structures.

## 1. Connection Details
- **Base URL**: `https://common-api.rozetka.com.ua/v1/api`
- **Method**: `GET`
- **Region/Lang**: Query params `country=UA&lang=ua`.

---

## 2. API Operations

| Operation | URL Path | Description |
| :--- | :--- | :--- |
| **Catalog Search** | `/catalog/search` | keyword-based search. |
| **Category Listing** | `/pages/catalog/category` | Full URL based listing. |
| **Producer Listing** | `/catalog/producer` | Brand/Manufacturer slug. |
| **Seller Details** | `/sellers` | Merchant info from slug. |
| **Product Details** | `/product/details` | Bulk fetch by IDs. |

---

## 3. Sample Input & Response Structures

### Category Listing
**Request**: `GET /pages/catalog/category?url=https%3A%2F%2Frozetka.com.ua%2Fua%2Frazvitie-i-obuchenie%2Fc211750%2F`

**Response Structure**:
```json
{
  "data": {
    "goods": [
      {
        "id": 123456,
        "title": "Конструктор LEGO",
        "price": 1500,
        "sell_status": "available",
        "category_id": 211750,
        "seller_id": 1,
        "brand": "LEGO",
        "images": {
          "main": "https://xl.rozetka.com.ua/main.jpg"
        },
        "href": "https://rozetka.com.ua/ua/lego-123/p123/"
      }
    ],
    "pagination": {
      "total_pages": 15,
      "shown_page": 1
    }
  }
}
```

### Product Details (Bulk)
**Request**: `GET /product/details?ids=123,456`

**Response Structure**:
```json
{
  "data": [
    {
      "id": 123,
      "name": "Product 123",
      "price": 500,
      "sell_status": "available",
      "seller": {
        "id": 1,
        "title": "Rozetka"
      }
    }
  ]
}
```

---

## 4. Normalization Mapping

| Standard Field | JSON Path | Notes |
| :--- | :--- | :--- |
| `id` | `id` | |
| `name` | `title` or `name` | |
| `price` | `price.current.value` or `price` | Handle nested dict or flat. |
| `avail_code` | `sell_status` | avail="available", OOS="unavailable". |
| `merchant_name`| `seller.title` | |
| `image` | `images.main` | |

---

## 5. Header Checklist
```http
Referer: https://rozetka.com.ua/
Accept: application/json
User-Agent: Mozilla/5.0 ...
```
