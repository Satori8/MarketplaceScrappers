import re
import json
from typing import Dict, Any

from scrapers.mapi_scraper.base import BaseModule
from scrapers.mapi_scraper.http import _get, _get_with_meta, _aget_with_meta, _ok, _err, _save_debug_item, logger
from scrapers.mapi_scraper.extractors import (
    _extract_ld_json, _extract_script_by_id, 
    _find_common_api_request_in_client_state
)

class RozetkaAPI:
    def __init__(self):
        self.site = "rozetka"

    def normalize(self, raw_data: Dict) -> Dict:
        """Standardizes Rozetka responses from LD+JSON or JS state."""
        products = []
        source = raw_data.get("source")
        
        total_pages = 0
        page_index = 1
        
        if source == "ld+json":
            ld = raw_data.get("ld_json", {})
            items = ld.get("itemListElement", [])
            for it in items:
                p_item = it.get("item", {})
                products.append({
                    "id": p_item.get("sku") or p_item.get("identifier"),
                    "sku": p_item.get("sku"),
                    "name": p_item.get("name"),
                    "brand": p_item.get("brand", {}).get("name") if isinstance(p_item.get("brand"), dict) else p_item.get("brand"),
                    "price": p_item.get("offers", {}).get("price") if isinstance(p_item.get("offers"), dict) else None,
                    "avail_code": 1 if "InStock" in str(p_item.get("offers", {}).get("availability")) else 0,
                    "merchant_id": None,
                    "merchant_name": p_item.get("offers", {}).get("seller", {}).get("name") if isinstance(p_item.get("offers"), dict) else None,
                    "category_id": None,
                    "category_name_ua": None,
                    "category_name_ru": None,
                    "properties": [],
                    "description": p_item.get("description"),
                    "url": p_item.get("url"),
                    "image": p_item.get("image")
                })
        
        elif source == "window.RZ.goods":
            items = raw_data.get("ld_json", {}) # Reused same field for convenience
            if isinstance(items, list):
                for it in items:
                    products.append({
                        "id": it.get("id"),
                        "sku": it.get("id"),
                        "name": it.get("title"),
                        "brand": it.get("brand"),
                        "price": it.get("price"),
                        "avail_code": it.get("status"),
                        "merchant_id": it.get("seller_id"),
                        "merchant_name": None,
                        "category_id": it.get("category_id"),
                        "category_name_ua": None,
                        "category_name_ru": None,
                        "properties": [],
                        "description": None,
                        "url": it.get("href"),
                        "image": it.get("image_url")
                    })

        elif source in ["rz-client-state", "api_direct_search", "api_direct_category", "api_direct_details"]:
            # API data structure can be a list or a dict containing a list
            api_data = raw_data.get("api_data", {})
            if isinstance(api_data, dict):
                # Standard wrapper
                data_val = api_data.get("data", {})
                
                # Fetch local pagination
                if isinstance(data_val, dict):
                    pagination = data_val.get("pagination") or data_val.get("paginator") or {}
                    if isinstance(pagination, dict):
                        total_pages = pagination.get("total_pages") or pagination.get("totalPages", 0)
                        page_index = pagination.get("shown_page") or pagination.get("shownPage", 1)
                
                if "goods" in api_data and isinstance(api_data["goods"], dict):
                    total_pages = api_data["goods"].get("total_pages", total_pages)
                    page_index = api_data["goods"].get("shown_page", page_index)
                elif isinstance(data_val, dict) and "goods" in data_val and isinstance(data_val["goods"], dict):
                    total_pages = data_val["goods"].get("total_pages", total_pages)
                    page_index = data_val["goods"].get("shown_page", page_index)
                
                cat_map = {}
                brands_map = {}

                if isinstance(data_val, dict):
                    for c_tile in data_val.get("categoryTiles", []):
                        if isinstance(c_tile, dict) and c_tile.get("id"):
                            cat_map[str(c_tile.get("id"))] = c_tile.get("title") or c_tile.get("name")
                        
                    filters = data_val.get("filters", {})
                    if isinstance(filters, dict):
                        for f in filters.get("list", []):
                            if f.get("id") == "producer":
                                for opt in f.get("options", []):
                                    brands_map[str(opt.get("id"))] = opt.get("title") or opt.get("name")

                items = []
                if isinstance(data_val, list):
                    items = data_val
                elif isinstance(data_val, dict):
                    # Check nested goods/products keys
                    g = data_val.get("goods")
                    if isinstance(g, list):
                        items = g
                    elif isinstance(g, dict):
                        items = g.get("tiles", [])
                    
                    if not items:
                        content = data_val.get("content", {})
                        if isinstance(content, dict):
                            items = content.get("goods", [])
                    
                    if not items:
                        items = data_val.get("products", [])
                
                # Check top-level goods/tiles/products if data was empty or not found
                if not items:
                    g = api_data.get("goods")
                    if isinstance(g, list): items = g
                    elif isinstance(g, dict): items = g.get("tiles", [])
                    
                if not items:
                    items = api_data.get("products", [])

                for it in items:
                    if not isinstance(it, dict): continue
                    if it.get("adv"): continue
                    
                    raw_id = it.get("id")
                    title_raw = it.get("title") or it.get("name")
                    name = ""
                    if isinstance(title_raw, dict):
                        name = title_raw.get("text") or ""
                    else:
                        name = str(title_raw or "")
                    
                    p_raw = it.get("price")
                    price = 0.0
                    if isinstance(p_raw, dict):
                        price = (p_raw.get("current") or {}).get("value") or 0.0
                    elif isinstance(p_raw, (int, float)):
                        price = float(p_raw)
                    
                    status = it.get("sell_status") or it.get("status") or it.get("state")
                    img_raw = it.get("images") or it.get("image_url") or it.get("primary_image_url")
                    
                    image = ""
                    if isinstance(img_raw, dict):
                        image = img_raw.get("main") or img_raw.get("preview") or ""
                    else:
                        image = str(img_raw or "")

                    # Merchant Extraction
                    s_id = it.get("seller_id")
                    s_name = None
                    seller_obj = it.get("seller")
                    if isinstance(seller_obj, dict):
                        s_name = seller_obj.get("title") or seller_obj.get("name")
                        if not s_id: s_id = seller_obj.get("id")
                    
                    if not s_id: s_id = it.get("merchant_id")

                    # Category Extraction
                    c_id = it.get("category_id")
                    c_name_ru = None
                    c_name_ua = None
                    category_obj = it.get("category")
                    
                    if isinstance(category_obj, dict):
                        c_name_ru = category_obj.get("title") or category_obj.get("name")
                        if not c_id: c_id = category_obj.get("id")

                    if not c_id and isinstance(it.get("category"), (int, str)):
                        c_id = it.get("category")

                    # Fallback to Global Category Map (Category Tiles)
                    if not c_name_ru and c_id:
                        c_name_ru = cat_map.get(str(c_id))
                    
                    # Unified category name (Rozetka often returns RU by default)
                    # We'll put it in ua if we can't distinguish, or leave as is
                    c_name_ua = c_name_ru 

                    # Parameters (Properties) Extraction
                    properties = []
                    
                    # 1. From docket (Specs)
                    docket = it.get("docket")
                    if isinstance(docket, list):
                        for d in docket:
                            if isinstance(d, dict):
                                opt_title = d.get("option_title")
                                value_title = d.get("value_title")
                                if opt_title and value_title:
                                    properties.append({"name": opt_title, "value": value_title})
                    
                    # 2. From var_params (Variants/Options)
                    var_params = it.get("var_params", {})
                    if isinstance(var_params, dict):
                        # Color case
                        colors = var_params.get("color")
                        if isinstance(colors, list):
                            color_vals = [str(c.get("value")) for c in colors if c.get("value") is not None]
                            if color_vals:
                                properties.append({"name": "Цвет", "value": "; ".join(color_vals)})
                        
                        # Block case (nested categories of parameters)
                        block = var_params.get("block")
                        if isinstance(block, dict):
                            for b_name, b_items in block.items():
                                if isinstance(b_items, list):
                                    b_vals = [str(bi.get("value")) for bi in b_items if bi.get("value") is not None]
                                    if b_vals:
                                        properties.append({"name": b_name, "value": "; ".join(b_vals)})
                    
                    b_raw = it.get("brand")
                    brand_name = None
                    if isinstance(b_raw, dict):
                        b_id = str(b_raw.get("id"))
                        brand_name = b_raw.get("title") or b_raw.get("name") or brands_map.get(b_id) or b_id
                    else:
                        brand_name = str(b_raw or "")

                    desc_raw = it.get("description")
                    description_text = ""
                    if isinstance(desc_raw, list):
                        for group in desc_raw:
                            if isinstance(group, dict):
                                g_title = group.get("title")
                                g_items = group.get("items", [])
                                if g_items and g_title:
                                    g_vals = [str(gi.get("title")) for gi in g_items if isinstance(gi, dict) and gi.get("title")]
                                    if g_vals:
                                        properties.append({"name": g_title, "value": "; ".join(g_vals)})
                    elif isinstance(desc_raw, str):
                        description_text = desc_raw

                    products.append({
                        "id": str(raw_id) if raw_id else "",
                        "sku": str(raw_id) if raw_id else "",
                        "name": name,
                        "brand": brand_name,
                        "price": price,
                        "avail_code": status,
                        "merchant_id": str(s_id) if s_id else None,
                        "merchant_name": s_name,
                        "category_id": str(c_id) if c_id else None,
                        "category_name_ua": c_name_ua,
                        "category_name_ru": c_name_ru,
                        "properties": properties,
                        "description": description_text,
                        "url": it.get("href") or f"https://rozetka.com.ua/ua/{raw_id}/p{raw_id}/",
                        "image": image
                    })
                # Placeholder for direct list responses
                pass

        if not products and total_pages > 0:
            logger.warning(f"Extracted 0 products from {source}, but total_pages={total_pages}", extra={"site": self.site})
        else:
            logger.info(f"Extracted {len(products)} products from {source}", extra={"site": self.site})

        return {
            "products": products,
            "pagination": {
                "total_pages": total_pages,
                "page_index": page_index
            }
        }


class RozetkaModule(BaseModule):
    SITE_ID = "rozetka"
    DOMAINS = ["rozetka.com.ua", "auto.rozetka.com.ua", "hard.rozetka.com.ua"]
    
    def __init__(self):
        self._api = RozetkaAPI()
        
    def scrape_url(self, url: str, page: int = 1, debug: bool = False) -> dict:
        site = self.SITE_ID
        api = self._api
        mode = "url"
        
        debug_enabled = debug
        debug_log: Dict[str, Any] = {"requests": []} if debug_enabled else {}

        # 1. PRIORITY: Direct API call if we can map the URL
        # Search: .../search/?text=iphone
        if "/search/" in url:
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            text = qs.get("text", [None])[0]
            if text:
                api_url = f"https://common-api.rozetka.com.ua/v1/api/catalog/search?country=UA&lang=ua&page={page}&text={text}"
                api_code, api_data, api_meta = _get_with_meta(site, api_url, parse_json=True, save_raw=debug_enabled)
                
                product_ids = []
                if api_code == 200:
                    goods_list = api_data.get("data", {}).get("goods", [])
                    product_ids = [str(g.get("id")) for g in goods_list if isinstance(g, dict) and g.get("id") and not g.get("adv")]

                if debug_enabled:
                    # Rozetka catalog search response contains product IDs but not full details
                    _save_debug_item(site, "catalog_search", api_url, api_meta, api_data, [])
                
                if api_code == 200:
                    pagination = api_data.get("data", {}).get("pagination") or api_data.get("data", {}).get("paginator") or {}
                    total_pages = pagination.get("total_pages") or pagination.get("totalPages", 0)
                    page_index = pagination.get("shown_page") or pagination.get("shownPage", 1)
                    
                    if product_ids:
                        all_products = []
                        CHUNK_SIZE = 60
                        for i in range(0, len(product_ids), CHUNK_SIZE):
                            chunk = product_ids[i:i + CHUNK_SIZE]
                            details_url = f"https://common-api.rozetka.com.ua/v1/api/product/details?country=UA&lang=ua&ids={','.join(chunk)}"
                            det_code, det_data, det_meta = _get_with_meta(site, details_url, parse_json=True, save_raw=debug_enabled)
                            
                            det_products = []
                            if det_code == 200:
                                raw = {"source": "api_direct_details", "api_url": details_url, "api_data": det_data}
                                normalized = api.normalize(raw)
                                det_products = normalized["products"]
                                all_products.extend(det_products)

                            if debug_enabled:
                                _save_debug_item(site, "product_details", details_url, det_meta, det_data, det_products)
                                
                        if all_products:
                            logger.info(f"Collected total {len(all_products)} products via detail chunks", extra={"site": site})
                            out = _ok(site, all_products, mode)
                            out["pagination"] = {"total_pages": total_pages, "page_index": page_index}
                            if debug_enabled: out["debug"] = debug_log
                            return out
                        else:
                            logger.warning(f"No products found in detail chunks for {len(product_ids)} IDs", extra={"site": site})
                            
                    raw = {"source": "api_direct_search", "api_url": api_url, "api_data": api_data}
                    normalized = api.normalize(raw)
                    out = _ok(site, normalized["products"], mode)
                    out["pagination"] = {"total_pages": total_pages, "page_index": page_index}
                    if debug_enabled: out["debug"] = debug_log
                    return out

        # Category: .../c80004/...
        cat_match = re.search(r'/c(\d+)/', url)
        if cat_match:
            from urllib.parse import quote
            api_url = f"https://common-api.rozetka.com.ua/v1/api/pages/catalog/category?country=UA&lang=ua&url={quote(url)}"
            api_code, api_data, api_meta = _get_with_meta(site, api_url, parse_json=True, save_raw=debug_enabled)
            
            product_ids = []
            if api_code == 200:
                goods_list = api_data.get("data", {}).get("goods", [])
                if isinstance(goods_list, dict) and "tiles" in goods_list:
                    goods_list = goods_list["tiles"]
                product_ids = [str(g.get("id")) for g in goods_list if isinstance(g, dict) and g.get("id") and not g.get("adv")]

            if debug_enabled:
                _save_debug_item(site, "api_direct_category", api_url, api_meta, api_data, [])

            if api_code == 200:
                pagination = api_data.get("data", {}).get("pagination") or api_data.get("data", {}).get("paginator") or {}
                total_pages = pagination.get("total_pages") or pagination.get("totalPages", 0)
                page_index = pagination.get("shown_page") or pagination.get("shownPage", 1)
                
                if product_ids:
                    all_products = []
                    CHUNK_SIZE = 60
                    for i in range(0, len(product_ids), CHUNK_SIZE):
                        chunk = product_ids[i:i + CHUNK_SIZE]
                        details_url = f"https://common-api.rozetka.com.ua/v1/api/product/details?country=UA&lang=ua&ids={','.join(chunk)}"
                        det_code, det_data, det_meta = _get_with_meta(site, details_url, parse_json=True, save_raw=debug_enabled)
                        
                        det_products_count = 0
                        if det_code == 200:
                            raw = {"source": "api_direct_details", "api_url": details_url, "api_data": det_data}
                            normalized = api.normalize(raw)
                            det_products_count = len(normalized["products"])
                            all_products.extend(normalized["products"])

                        if debug_enabled:
                            _save_debug_item(site, "product_details", details_url, det_meta, det_data, normalized.get("products", []))
                        
                    if all_products:
                        logger.info(f"Collected total {len(all_products)} products via category detail chunks", extra={"site": site})
                        out = _ok(site, all_products, mode)
                        out["pagination"] = {"total_pages": total_pages, "page_index": page_index}
                        if debug_enabled: out["debug"] = debug_log
                        return out
                    else:
                        logger.warning(f"No products found in category detail chunks for {len(product_ids)} IDs", extra={"site": site})

                raw = {"source": "api_direct_category", "api_url": api_url, "api_data": api_data}
                normalized = api.normalize(raw)
                out = _ok(site, normalized["products"], mode)
                out["pagination"] = {"total_pages": total_pages, "page_index": page_index}
                if debug_enabled: out["debug"] = debug_log
                return out

        # Seller: .../seller/{slug}/goods/
        seller_match = re.search(r'/seller/([^/]+)/', url)
        if seller_match:
            slug = seller_match.group(1)
            # 1. Fetch Seller ID
            sellers_url = f"https://common-api.rozetka.com.ua/v1/api/sellers?country=UA&lang=ua&name={slug}"
            s_code, s_data, s_meta = _get_with_meta(site, sellers_url, parse_json=True, save_raw=debug_enabled)
            
            seller_id = None
            if s_code == 200 and isinstance(s_data, dict):
                data_dict = s_data.get("data", {})
                if data_dict:
                    # Get the first key which is usually the ID, or look for 'id' inside the value
                    first_key = next(iter(data_dict))
                    seller_info = data_dict[first_key]
                    # INPORTANT: catalog-api often expects owox_id as the 'id' parameter
                    seller_id = seller_info.get("owox_id") or seller_info.get("id")
            
            if seller_id:
                catalog_url = f"https://catalog-api.rozetka.com.ua/v0.1/api/category/seller/catalog?country=UA&lang=ua&id={seller_id}"
                if int(page) > 1:
                    catalog_url += f"&filters=page:{page}"
                
                cat_code, cat_data, cat_meta = _get_with_meta(site, catalog_url, parse_json=True, save_raw=debug_enabled)
                
                if debug_enabled:
                    _save_debug_item(site, "api_seller_catalog", catalog_url, cat_meta, cat_data, [])

                product_ids = []
                if cat_code == 200 and isinstance(cat_data, dict):
                    goods = cat_data.get("data", {}).get("goods", {})
                    product_ids = [str(pid) for pid in goods.get("ids", [])]
                    
                    total_pages = goods.get("total_pages", 0)
                    page_index = goods.get("shown_page", 1)

                if product_ids:
                    all_products = []
                    CHUNK_SIZE = 60
                    for i in range(0, len(product_ids), CHUNK_SIZE):
                        chunk = product_ids[i:i + CHUNK_SIZE]
                        details_url = f"https://common-api.rozetka.com.ua/v1/api/product/details?country=UA&lang=ua&ids={','.join(chunk)}"
                        det_code, det_data, det_meta = _get_with_meta(site, details_url, parse_json=True, save_raw=debug_enabled)
                        
                        if det_code == 200:
                            raw = {"source": "api_direct_details", "api_url": details_url, "api_data": det_data}
                            normalized = api.normalize(raw)
                            all_products.extend(normalized["products"])

                        if debug_enabled:
                            _save_debug_item(site, "product_details", details_url, det_meta, det_data, (normalized.get("products", []) if det_code == 200 else []))
                    
                    if all_products:
                        logger.info(f"Collected total {len(all_products)} products via seller detail chunks", extra={"site": site})
                        out = _ok(site, all_products, mode)
                        out["pagination"] = {"total_pages": total_pages, "page_index": page_index}
                        if debug_enabled: out["debug"] = debug_log
                        return out
                    else:
                        logger.warning(f"No products found in seller detail chunks for {len(product_ids)} IDs", extra={"site": site})

        # 2. FALLBACK: Load HTML for LD+JSON or rz-client-state
        logger.info(f"Falling back to HTML extraction for {url}", extra={"site": site})
        code, html, html_meta = _get_with_meta(site, url, extra_headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Referer": "https://rozetka.com.ua/"}, parse_json=False, save_raw=debug_enabled)
        if debug_enabled:
            _save_debug_item(site, "html_fetch", url, html_meta, {"html_snippet": html[:2000]}, [])

        if code != 200:
            logger.warning(f"HTML fallback failed with status {code}", extra={"site": site})
            out = _err(site, mode, f"HTTP {code}", code)
            if debug_enabled: out["debug"] = debug_log
            return out

        # 3. Method: LD+JSON (Fastest fallback from HTML)
        ld_blocks = _extract_ld_json(html)
        for block in ld_blocks:
            if block.get("@type") == "ItemList" and block.get("itemListElement"):
                raw = {"source": "ld+json", "ld_json": block}
                normalized = api.normalize(raw)
                out = _ok(site, normalized["products"], mode)
                out["pagination"] = normalized.get("pagination", {"total_pages": 0, "page_index": 1})
                if debug_enabled: out["debug"] = debug_log
                return out

        # 4. Method: Unified rz-client-state (2nd API Query)
        client_state = _extract_script_by_id(html, "rz-client-state")
        if client_state:
            # Reconstruct the best API request from state keys
            api_url_enc = _find_common_api_request_in_client_state(client_state)
            if api_url_enc:
                api_code, api_data, api_meta = _get_with_meta(site, api_url_enc, parse_json=True, save_raw=debug_enabled)
                if debug_enabled:
                    debug_log["requests"].append({"kind": "api_client_state", **api_meta})
                if api_code == 200:
                    raw = {"source": "rz-client-state", "api_url": api_url_enc, "api_data": api_data}
                    normalized = api.normalize(raw)
                    if debug_enabled:
                        products = normalized.get("products", []) if normalized else []
                        _save_debug_item(site, "api_client_state", api_url_enc, api_meta, api_data, products)
                    if normalized["products"]:
                        out = _ok(site, normalized["products"], mode)
                        out["pagination"] = normalized.get("pagination", {"total_pages": 0, "page_index": 1})
                        if debug_enabled: out["debug"] = debug_log
                        return out
                elif debug_enabled:
                    _save_debug_item(site, "api_client_state_err", api_url_enc, api_meta, api_meta.get("raw_response"), [])

        # 5. Method: Legacy variable fallback (window.RZ.goods)
        match = re.search(r"window\.RZ\.goods\s*=\s*(\{.*?\});", html)
        if match:
            try:
                raw = {"source": "window.RZ.goods", "ld_json": json.loads(match.group(1))}
                normalized = api.normalize(raw)
                out = _ok(site, normalized["products"], mode)
                if debug_enabled: out["debug"] = debug_log
                return out
            except: pass

        out = _err(site, mode, "Could not find any data source for Rozetka", 404)
        if debug_enabled: out["debug"] = debug_log
        return out

    async def async_scrape_url(
        self,
        url: str,
        page: int = 1,
        debug: bool = False,
        proxy: str | None = None,
    ) -> dict:
        site = self.SITE_ID
        api = self._api
        mode = "url"
        
        debug_enabled = debug
        debug_log: Dict[str, Any] = {"requests": []} if debug_enabled else {}

        # 1. PRIORITY: Direct API call if we can map the URL
        # Search: .../search/?text=iphone
        if "/search/" in url:
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            text = qs.get("text", [None])[0]
            if text:
                api_url = f"https://common-api.rozetka.com.ua/v1/api/catalog/search?country=UA&lang=ua&page={page}&text={text}"
                api_code, api_data, api_meta = await _aget_with_meta(site, api_url, parse_json=True, save_raw=debug_enabled, proxy=proxy)
                
                product_ids = []
                if api_code == 200:
                    goods_list = api_data.get("data", {}).get("goods", [])
                    product_ids = [str(g.get("id")) for g in goods_list if isinstance(g, dict) and g.get("id") and not g.get("adv")]

                if debug_enabled:
                    # Rozetka catalog search response contains product IDs but not full details
                    _save_debug_item(site, "catalog_search", api_url, api_meta, api_data, [])
                
                if api_code == 200:
                    pagination = api_data.get("data", {}).get("pagination") or api_data.get("data", {}).get("paginator") or {}
                    total_pages = pagination.get("total_pages") or pagination.get("totalPages", 0)
                    page_index = pagination.get("shown_page") or pagination.get("shownPage", 1)
                    
                    if product_ids:
                        all_products = []
                        CHUNK_SIZE = 60
                        for i in range(0, len(product_ids), CHUNK_SIZE):
                            chunk = product_ids[i:i + CHUNK_SIZE]
                            details_url = f"https://common-api.rozetka.com.ua/v1/api/product/details?country=UA&lang=ua&ids={','.join(chunk)}"
                            det_code, det_data, det_meta = await _aget_with_meta(site, details_url, parse_json=True, save_raw=debug_enabled, proxy=proxy)
                            
                            det_products = []
                            if det_code == 200:
                                raw = {"source": "api_direct_details", "api_url": details_url, "api_data": det_data}
                                normalized = api.normalize(raw)
                                det_products = normalized["products"]
                                all_products.extend(det_products)

                            if debug_enabled:
                                _save_debug_item(site, "product_details", details_url, det_meta, det_data, det_products)
                                
                        if all_products:
                            logger.info(f"Collected total {len(all_products)} products via detail chunks", extra={"site": site})
                            out = _ok(site, all_products, mode)
                            out["pagination"] = {"total_pages": total_pages, "page_index": page_index}
                            if debug_enabled: out["debug"] = debug_log
                            return out
                        else:
                            logger.warning(f"No products found in detail chunks for {len(product_ids)} IDs", extra={"site": site})
                            
                    raw = {"source": "api_direct_search", "api_url": api_url, "api_data": api_data}
                    normalized = api.normalize(raw)
                    out = _ok(site, normalized["products"], mode)
                    out["pagination"] = {"total_pages": total_pages, "page_index": page_index}
                    if debug_enabled: out["debug"] = debug_log
                    return out

        # Category: .../c80004/...
        cat_match = re.search(r'/c(\d+)/', url)
        if cat_match:
            from urllib.parse import quote
            api_url = f"https://common-api.rozetka.com.ua/v1/api/pages/catalog/category?country=UA&lang=ua&url={quote(url)}"
            api_code, api_data, api_meta = await _aget_with_meta(site, api_url, parse_json=True, save_raw=debug_enabled, proxy=proxy)
            
            product_ids = []
            if api_code == 200:
                goods_list = api_data.get("data", {}).get("goods", [])
                if isinstance(goods_list, dict) and "tiles" in goods_list:
                    goods_list = goods_list["tiles"]
                product_ids = [str(g.get("id")) for g in goods_list if isinstance(g, dict) and g.get("id") and not g.get("adv")]

            if debug_enabled:
                _save_debug_item(site, "api_direct_category", api_url, api_meta, api_data, [])

            if api_code == 200:
                pagination = api_data.get("data", {}).get("pagination") or api_data.get("data", {}).get("paginator") or {}
                total_pages = pagination.get("total_pages") or pagination.get("totalPages", 0)
                page_index = pagination.get("shown_page") or pagination.get("shownPage", 1)
                
                if product_ids:
                    all_products = []
                    CHUNK_SIZE = 60
                    for i in range(0, len(product_ids), CHUNK_SIZE):
                        chunk = product_ids[i:i + CHUNK_SIZE]
                        details_url = f"https://common-api.rozetka.com.ua/v1/api/product/details?country=UA&lang=ua&ids={','.join(chunk)}"
                        det_code, det_data, det_meta = await _aget_with_meta(site, details_url, parse_json=True, save_raw=debug_enabled, proxy=proxy)
                        
                        det_products_count = 0
                        if det_code == 200:
                            raw = {"source": "api_direct_details", "api_url": details_url, "api_data": det_data}
                            normalized = api.normalize(raw)
                            det_products_count = len(normalized["products"])
                            all_products.extend(normalized["products"])

                        if debug_enabled:
                            _save_debug_item(site, "product_details", details_url, det_meta, det_data, normalized.get("products", []))
                        
                    if all_products:
                        logger.info(f"Collected total {len(all_products)} products via category detail chunks", extra={"site": site})
                        out = _ok(site, all_products, mode)
                        out["pagination"] = {"total_pages": total_pages, "page_index": page_index}
                        if debug_enabled: out["debug"] = debug_log
                        return out
                    else:
                        logger.warning(f"No products found in category detail chunks for {len(product_ids)} IDs", extra={"site": site})

                raw = {"source": "api_direct_category", "api_url": api_url, "api_data": api_data}
                normalized = api.normalize(raw)
                out = _ok(site, normalized["products"], mode)
                out["pagination"] = {"total_pages": total_pages, "page_index": page_index}
                if debug_enabled: out["debug"] = debug_log
                return out

        # Seller: .../seller/{slug}/goods/
        seller_match = re.search(r'/seller/([^/]+)/', url)
        if seller_match:
            slug = seller_match.group(1)
            # 1. Fetch Seller ID
            sellers_url = f"https://common-api.rozetka.com.ua/v1/api/sellers?country=UA&lang=ua&name={slug}"
            s_code, s_data, s_meta = await _aget_with_meta(site, sellers_url, parse_json=True, save_raw=debug_enabled, proxy=proxy)
            
            seller_id = None
            if s_code == 200 and isinstance(s_data, dict):
                data_dict = s_data.get("data", {})
                if data_dict:
                    # Get the first key which is usually the ID, or look for 'id' inside the value
                    first_key = next(iter(data_dict))
                    seller_info = data_dict[first_key]
                    # INPORTANT: catalog-api often expects owox_id as the 'id' parameter
                    seller_id = seller_info.get("owox_id") or seller_info.get("id")
            
            if seller_id:
                catalog_url = f"https://catalog-api.rozetka.com.ua/v0.1/api/category/seller/catalog?country=UA&lang=ua&id={seller_id}"
                if int(page) > 1:
                    catalog_url += f"&filters=page:{page}"
                
                cat_code, cat_data, cat_meta = await _aget_with_meta(site, catalog_url, parse_json=True, save_raw=debug_enabled, proxy=proxy)
                
                if debug_enabled:
                    _save_debug_item(site, "api_seller_catalog", catalog_url, cat_meta, cat_data, [])

                product_ids = []
                if cat_code == 200 and isinstance(cat_data, dict):
                    goods = cat_data.get("data", {}).get("goods", {})
                    product_ids = [str(pid) for pid in goods.get("ids", [])]
                    
                    total_pages = goods.get("total_pages", 0)
                    page_index = goods.get("shown_page", 1)

                if product_ids:
                    all_products = []
                    CHUNK_SIZE = 60
                    for i in range(0, len(product_ids), CHUNK_SIZE):
                        chunk = product_ids[i:i + CHUNK_SIZE]
                        details_url = f"https://common-api.rozetka.com.ua/v1/api/product/details?country=UA&lang=ua&ids={','.join(chunk)}"
                        det_code, det_data, det_meta = await _aget_with_meta(site, details_url, parse_json=True, save_raw=debug_enabled, proxy=proxy)
                        
                        if det_code == 200:
                            raw = {"source": "api_direct_details", "api_url": details_url, "api_data": det_data}
                            normalized = api.normalize(raw)
                            all_products.extend(normalized["products"])

                        if debug_enabled:
                            _save_debug_item(site, "product_details", details_url, det_meta, det_data, (normalized.get("products", []) if det_code == 200 else []))
                    
                    if all_products:
                        logger.info(f"Collected total {len(all_products)} products via seller detail chunks", extra={"site": site})
                        out = _ok(site, all_products, mode)
                        out["pagination"] = {"total_pages": total_pages, "page_index": page_index}
                        if debug_enabled: out["debug"] = debug_log
                        return out
                    else:
                        logger.warning(f"No products found in seller detail chunks for {len(product_ids)} IDs", extra={"site": site})

        # 2. FALLBACK: Load HTML for LD+JSON or rz-client-state
        logger.info(f"Falling back to HTML extraction for {url}", extra={"site": site})
        code, html, html_meta = await _aget_with_meta(site, url, extra_headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Referer": "https://rozetka.com.ua/"}, parse_json=False, save_raw=debug_enabled, proxy=proxy)
        if debug_enabled:
            _save_debug_item(site, "html_fetch", url, html_meta, {"html_snippet": html[:2000]}, [])

        if code != 200:
            logger.warning(f"HTML fallback failed with status {code}", extra={"site": site})
            out = _err(site, mode, f"HTTP {code}", code)
            if debug_enabled: out["debug"] = debug_log
            return out

        # 3. Method: LD+JSON (Fastest fallback from HTML)
        ld_blocks = _extract_ld_json(html)
        for block in ld_blocks:
            if block.get("@type") == "ItemList" and block.get("itemListElement"):
                raw = {"source": "ld+json", "ld_json": block}
                normalized = api.normalize(raw)
                out = _ok(site, normalized["products"], mode)
                out["pagination"] = normalized.get("pagination", {"total_pages": 0, "page_index": 1})
                if debug_enabled: out["debug"] = debug_log
                return out

        # 4. Method: Unified rz-client-state (2nd API Query)
        client_state = _extract_script_by_id(html, "rz-client-state")
        if client_state:
            # Reconstruct the best API request from state keys
            api_url_enc = _find_common_api_request_in_client_state(client_state)
            if api_url_enc:
                api_code, api_data, api_meta = await _aget_with_meta(site, api_url_enc, parse_json=True, save_raw=debug_enabled, proxy=proxy)
                if debug_enabled:
                    debug_log["requests"].append({"kind": "api_client_state", **api_meta})
                if api_code == 200:
                    raw = {"source": "rz-client-state", "api_url": api_url_enc, "api_data": api_data}
                    normalized = api.normalize(raw)
                    if debug_enabled:
                        products = normalized.get("products", []) if normalized else []
                        _save_debug_item(site, "api_client_state", api_url_enc, api_meta, api_data, products)
                    if normalized["products"]:
                        out = _ok(site, normalized["products"], mode)
                        out["pagination"] = normalized.get("pagination", {"total_pages": 0, "page_index": 1})
                        if debug_enabled: out["debug"] = debug_log
                        return out
                elif debug_enabled:
                    _save_debug_item(site, "api_client_state_err", api_url_enc, api_meta, api_meta.get("raw_response"), [])

        # 5. Method: Legacy variable fallback (window.RZ.goods)
        match = re.search(r"window\.RZ\.goods\s*=\s*(\{.*?\});", html)
        if match:
            try:
                raw = {"source": "window.RZ.goods", "ld_json": json.loads(match.group(1))}
                normalized = api.normalize(raw)
                out = _ok(site, normalized["products"], mode)
                if debug_enabled: out["debug"] = debug_log
                return out
            except: pass

        out = _err(site, mode, "Could not find any data source for Rozetka", 404)
        if debug_enabled: out["debug"] = debug_log
        return out
