import json
import re
from typing import Any, List, Dict

def find_products_recursive(data: Any) -> List[Dict]:
    """Recursively search for lists of objects that look like products."""
    products = []
    
    if isinstance(data, dict):
        # Check if this dict is a product
        if all(k in data for k in ["id", "name"]) and ("price" in data or "final_price" in data):
             # It's an item, but we usually want it inside a list or search for more
             pass
        
        # Look at values
        for key, val in data.items():
            if key in ["products", "items", "itemListElement", "goods"]:
                if isinstance(val, list):
                    for item in val:
                        # Extract product if it's a dict or has a 'product' key (Prom)
                        p_obj = item.get("product") if isinstance(item, dict) and "product" in item else item
                        if isinstance(p_obj, dict) and ("name" in p_obj or "caption" in p_obj):
                            products.append(p_obj)
            else:
                products.extend(find_products_recursive(val))
                
    elif isinstance(data, list):
        for item in data:
            products.extend(find_products_recursive(item))
            
    return products

def map_to_unified_schema(site: str, item: Dict) -> Dict:
    """Maps a raw product object from any site to the unified schema."""
    p = {
        "product_id": item.get("id") or item.get("entity_id") or item.get("product_id") or item.get("sku"),
        "brand": item.get("brand") or item.get("brand_name") or item.get("mfr"),
        "product_name": item.get("name") or item.get("caption") or item.get("title"),
        "price": item.get("price") or item.get("final_price") or item.get("priceOriginal"),
        "in_stock": 1,
        "product_images": [],
        "product_url": item.get("url") or item.get("href"),
        "product_category_tree": [],
        "product_category_id": item.get("categoryId") or item.get("category_id"),
        "seller_id": item.get("sellerId") or item.get("company_id") or item.get("seller_id"),
        "seller_name": item.get("sellerName") or item.get("company_name") or item.get("seller_name"),
        "seller_url": None,
        "characteristics": []
    }
    
    # Handle Prom Specifics
    if site == "prom":
        if "presence" in item and isinstance(item["presence"], dict):
            p["in_stock"] = 1 if item["presence"].get("isAvailable") else 0
        elif item.get("presence") == "available":
            p["in_stock"] = 1
            
        if "images" in item and isinstance(item["images"], list):
            p["product_images"] = [img.get("url") if isinstance(img, dict) else img for img in item["images"]]
        elif "image" in item:
            p["product_images"] = [item["image"]]

    # Handle Allo Specifics
    if site == "allo":
        if "stock_status" in item:
            p["in_stock"] = 1 if item["stock_status"] == "in_stock" else 0
        if "images" in item:
            p["product_images"] = item["images"] if isinstance(item["images"], list) else [item["images"]]

    # Handle Epicentr Specifics
    if site == "epicentr":
        if "availability" in item:
            p["in_stock"] = 0 if item["availability"] == "out_of_stock" else 1
        if "image" in item:
            p["product_images"] = [item["image"]]

    # Normalize price to numeric if possible
    if p["price"] and isinstance(p["price"], (str, int, float)):
        try:
            # Strip non-numeric except dot
            p["price"] = re.sub(r'[^\d.]', '', str(p["price"]))
        except: pass

    return p

def normalize(site: str, raw_data: Dict) -> List[Dict]:
    """Entry point for normalization with deep search."""
    if not raw_data or not raw_data.get("ok"):
        return []
    
    data = raw_data.get("data") or {}
    
    # Pre-process strings (Nuxt/Apollo IIFEs)
    processed_data = data
    for key, val in data.items():
        if isinstance(val, str) and ("{" in val or "(function" in val):
            # Try to extract JSON from string
            try:
                # Look for largest JSON block
                json_match = re.search(r'(\{.*\})', val, re.DOTALL)
                if json_match:
                    # Very risky with IIFE args, but let's try a simple find for products
                    pass
            except: pass
            
    # Find all product-like objects
    raw_products = find_products_recursive(data)
    
    # Additional regex fallback for IIFE strings if recursive search found nothing
    if not raw_products:
        for key, val in data.items():
            if isinstance(val, str):
                # Look for patterns like {"id":123,"name":"..."}
                matches = re.finditer(r'\{"id":\d+,"name":".*?"(.*?)\}', val)
                for item_match in matches:
                    try:
                         # Attempt to parse minimal blob
                         blob = item_match.group(0)
                         # Fix common IIFE issues like unquoted keys if any (though usually it's JSON-like)
                         raw_products.append(json.loads(blob))
                    except: continue

    # Map to unified schema
    unified = [map_to_unified_schema(site, p) for p in raw_products]
    
    # De-duplicate by ID
    seen = set()
    unique = []
    for p in unified:
        if p["product_id"] and p["product_id"] not in seen:
            unique.append(p)
            seen.add(p["product_id"])
            
    return unique
