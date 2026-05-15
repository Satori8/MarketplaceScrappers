import re
import json
import asyncio
from typing import Dict, Any, List
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from scrapers.mapi_scraper.base import BaseModule
from scrapers.mapi_scraper.http import (
    _get_with_meta, _aget_with_meta, _ok, _err, _save_debug_item, logger,
    _make_sync_fetcher, _make_async_fetcher
)
from scrapers.mapi_scraper.extractors import (
    _extract_ld_json, _extract_script_by_id, 
    _find_common_api_request_in_client_state, _map_ld_json_offer
)

class RozetkaAPI:
    def __init__(self):
        self.site = "rozetka"

    def normalize(self, raw_data: Dict) -> Dict:
        """Standardizes Rozetka responses from LD+JSON or JS state."""
        products = []
        source = raw_data.get("source") or "unknown"
        
        total_pages = 0
        page_index = 1
        
        if source == "ld+json":
            ld = raw_data.get("ld_json", {})
            items = ld.get("itemListElement", [])
            for it in items:
                p_item = it.get("item", {})
                mapped = _map_ld_json_offer(p_item)
                mapped["description"] = p_item.get("description")
                products.append(mapped)
        
        elif source == "window.RZ.goods":
            items = raw_data.get("ld_json", {})
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
            api_data = raw_data.get("api_data", {})
            if isinstance(api_data, dict):
                data_val = api_data.get("data", {})
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
                    g = data_val.get("goods")
                    if isinstance(g, list): items = g
                    elif isinstance(g, dict): items = g.get("tiles", [])
                    if not items:
                        content = data_val.get("content", {})
                        if isinstance(content, dict): items = content.get("goods", [])
                    if not items: items = data_val.get("products", [])
                
                if not items:
                    g = api_data.get("goods")
                    if isinstance(g, list): items = g
                    elif isinstance(g, dict): items = g.get("tiles", [])
                if not items: items = api_data.get("products", [])

                for it in items:
                    if not isinstance(it, dict): continue
                    if it.get("adv"): continue
                    
                    raw_id = it.get("id")
                    title_raw = it.get("title") or it.get("name")
                    name = title_raw.get("text") or "" if isinstance(title_raw, dict) else str(title_raw or "")
                    
                    p_raw = it.get("price")
                    price = 0.0
                    if isinstance(p_raw, dict): price = (p_raw.get("current") or {}).get("value") or 0.0
                    elif isinstance(p_raw, (int, float)): price = float(p_raw)
                    
                    status = it.get("sell_status") or it.get("status") or it.get("state")
                    img_raw = it.get("images") or it.get("image_url") or it.get("primary_image_url")
                    image = img_raw.get("main") or img_raw.get("preview") or "" if isinstance(img_raw, dict) else str(img_raw or "")

                    s_id = it.get("seller_id")
                    s_name = None
                    seller_obj = it.get("seller")
                    if isinstance(seller_obj, dict):
                        s_name = seller_obj.get("title") or seller_obj.get("name")
                        if not s_id: s_id = seller_obj.get("id")
                    if not s_id: s_id = it.get("merchant_id")

                    c_id = it.get("category_id")
                    c_name_ru = None
                    category_obj = it.get("category")
                    if isinstance(category_obj, dict):
                        c_name_ru = category_obj.get("title") or category_obj.get("name")
                        if not c_id: c_id = category_obj.get("id")
                    if not c_id and isinstance(it.get("category"), (int, str)):
                        c_id = it.get("category")
                    if not c_name_ru and c_id:
                        c_name_ru = cat_map.get(str(c_id))
                    
                    c_name_ua = c_name_ru 

                    properties = []
                    docket = it.get("docket")
                    if isinstance(docket, list):
                        for d in docket:
                            if isinstance(d, dict):
                                opt_title = d.get("option_title")
                                value_title = d.get("value_title")
                                if opt_title and value_title:
                                    properties.append({"name": opt_title, "value": value_title})
                    
                    var_params = it.get("var_params", {})
                    if isinstance(var_params, dict):
                        colors = var_params.get("color")
                        if isinstance(colors, list):
                            color_vals = [str(c.get("value")) for c in colors if c.get("value") is not None]
                            if color_vals: properties.append({"name": "Цвет", "value": "; ".join(color_vals)})
                        block = var_params.get("block")
                        if isinstance(block, dict):
                            for b_name, b_items in block.items():
                                if isinstance(b_items, list):
                                    b_vals = [str(bi.get("value")) for bi in b_items if bi.get("value") is not None]
                                    if b_vals: properties.append({"name": b_name, "value": "; ".join(b_vals)})
                    
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
                                    if g_vals: properties.append({"name": g_title, "value": "; ".join(g_vals)})
                    elif isinstance(desc_raw, str):
                        description_text = desc_raw

                    status_raw = it.get("sell_status") or it.get("status") or it.get("state")
                    if status_raw == "available":
                        avail_str = "В наявності"
                    elif status_raw == "unavailable":
                        avail_str = "Немає в наявності"
                    elif status_raw == "limited":
                        avail_str = "Закінчується"
                    else:
                        avail_str = "Немає в наявності"

                    products.append({
                        "id": str(raw_id) if raw_id else "",
                        "sku": str(raw_id) if raw_id else "",
                        "name": name,
                        "brand": brand_name,
                        "price": price,
                        "avail_code": avail_str,
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
        fetch = _make_sync_fetcher()
        try:
            return asyncio.run(self._scrape_impl(url, page, debug, fetch))
        except RuntimeError as e:
            logger.warning(f"RuntimeError in sync scrape_url: {e}.", extra={"site": self.SITE_ID})
            raise

    async def async_scrape_url(self, url: str, page: int = 1, debug: bool = False, proxy: str | None = None) -> dict:
        fetch = _make_async_fetcher(proxy=proxy)
        return await self._scrape_impl(url, page, debug, fetch)

    async def _scrape_impl(self, url: str, page: int, debug: bool, fetch) -> dict:
        site = self.SITE_ID
        api = self._api
        mode = "url"
        
        debug_log: Dict[str, Any] = {"requests": []} if debug else {}

        # 1. Direct Search
        if "/search/" in url:
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            text = qs.get("text", [None])[0]
            if text:
                api_url = f"https://common-api.rozetka.com.ua/v1/api/catalog/search?country=UA&lang=ua&page={page}&text={text}"
                api_code, api_data, api_meta = await fetch(site, api_url, parse_json=True, save_raw=debug)
                
                if api_code == 200:
                    goods_list = api_data.get("data", {}).get("goods", [])
                    product_ids = [str(g.get("id")) for g in goods_list if isinstance(g, dict) and g.get("id") and not g.get("adv")]
                    if debug: _save_debug_item(site, "catalog_search", api_url, api_meta, api_data, [])
                    
                    pagination = api_data.get("data", {}).get("pagination") or api_data.get("data", {}).get("paginator") or {}
                    total_pages = pagination.get("total_pages") or pagination.get("totalPages", 0)
                    page_index = pagination.get("shown_page") or pagination.get("shownPage", 1)
                    
                    if product_ids:
                        all_products = await self._fetch_details_chunks(site, product_ids, debug, fetch)
                        if all_products:
                            out = _ok(site, all_products, mode)
                            out["pagination"] = {"total_pages": total_pages, "page_index": page_index}
                            if debug: out["debug"] = debug_log
                            return out
                            
                    raw = {"source": "api_direct_search", "api_url": api_url, "api_data": api_data}
                    normalized = api.normalize(raw)
                    out = _ok(site, normalized["products"], mode)
                    out["pagination"] = {"total_pages": total_pages, "page_index": page_index}
                    if debug: out["debug"] = debug_log
                    return out

        # 2a. Producer / Brand — dedicated producer API endpoint
        # Endpoint: /v1/api/catalog/producer — passes name=slug + all query filters directly.
        is_producer = "/producer/" in url or "/brand/" in url
        if is_producer:
            parsed = urlparse(url)
            producer_match = re.search(r'/(?:producer|brand)/([^/]+)/', parsed.path)
            if producer_match:
                slug = producer_match.group(1)
                api_url = (
                    f"https://common-api.rozetka.com.ua/v1/api/catalog/producer"
                    f"?country=UA&lang=ua&name={slug}"
                )
                if page > 1:
                    api_url += f"&page={page}"
                if parsed.query:
                    api_url += f"&{parsed.query}"

                api_code, api_data, api_meta = await fetch(site, api_url, parse_json=True, save_raw=debug)

                if api_code == 200:
                    data_dict = (api_data.get("data") or {}) if isinstance(api_data, dict) else {}
                    goods_list = data_dict.get("goods", [])
                    if isinstance(goods_list, dict) and "tiles" in goods_list: goods_list = goods_list["tiles"]
                    product_ids = [str(g.get("id")) for g in goods_list if isinstance(g, dict) and g.get("id") and not g.get("adv")]
                    if debug: _save_debug_item(site, "api_direct_producer", api_url, api_meta, api_data, [])

                    pagination = data_dict.get("pagination") or data_dict.get("paginator") or {}
                    total_pages = pagination.get("total_pages") or pagination.get("totalPages", 0)
                    page_index = pagination.get("shown_page") or pagination.get("shownPage", 1)

                    if product_ids:
                        all_products = await self._fetch_details_chunks(site, product_ids, debug, fetch)
                        if all_products:
                            out = _ok(site, all_products, mode)
                            out["pagination"] = {"total_pages": total_pages, "page_index": page_index}
                            if debug: out["debug"] = debug_log
                            return out

                    raw = {"source": "api_direct_category", "api_url": api_url, "api_data": api_data}
                    normalized = api.normalize(raw)
                    out = _ok(site, normalized["products"], mode)
                    out["pagination"] = {"total_pages": total_pages, "page_index": page_index}
                    if debug: out["debug"] = debug_log
                    return out

        # 2b. Direct Category — uses pages/catalog/category with full URL
        is_category = bool(re.search(r'/c(\d+)/', url))
        if is_category:
            # Keep /ua/ locale prefix — the API requires it for correct routing on subdomains.
            # Browser always sends the full path: /ua/fans/c80186/page=2;filter=value/
            parsed = urlparse(url)
            paginated_path = self._inject_page_into_path(parsed.path, page)

            # The API url= parameter needs the FULL URL including domain, fully encoded.
            # urlencode() encodes slashes as %2F — matching exactly what the browser sends.
            full_url_for_api = urlunparse(parsed._replace(path=paginated_path))
            api_url = (
                "https://common-api.rozetka.com.ua/v1/api/pages/catalog/category?"
                + urlencode({"country": "UA", "lang": "ua", "url": full_url_for_api})
            )

            api_code, api_data, api_meta = await fetch(site, api_url, parse_json=True, save_raw=debug)

            was_redirected = False
            if api_code == 200 and isinstance(api_data, dict):
                # Handle API-level redirects in the JSON body (HTTP 200, data.redirect.code=301).
                # Happens when the URL belongs to a subdomain (bt, build, etc.).
                redirect_info = (api_data.get("data") or {}).get("redirect")
                if isinstance(redirect_info, dict) and redirect_info.get("url"):
                    redir_url = redirect_info["url"]
                    logger.info(
                        f"API body redirect {redirect_info.get('code', 301)} -> {redir_url}",
                        extra={"site": site}
                    )
                    # Follow redirect: use the canonical URL from the API body as-is.
                    # The API already encodes page position correctly in the redirect URL.
                    api_url = (
                        "https://common-api.rozetka.com.ua/v1/api/pages/catalog/category?"
                        + urlencode({"country": "UA", "lang": "ua", "url": redir_url})
                    )
                    api_code, api_data, api_meta = await fetch(site, api_url, parse_json=True, save_raw=debug)
                    was_redirected = True

            if api_code == 200:
                data_dict = api_data.get("data", {})
                goods_list = data_dict.get("goods", [])
                if isinstance(goods_list, dict) and "tiles" in goods_list: goods_list = goods_list["tiles"]
                product_ids = [str(g.get("id")) for g in goods_list if isinstance(g, dict) and g.get("id") and not g.get("adv")]
                if debug: _save_debug_item(site, "api_direct_category", api_url, api_meta, api_data, [])

                pagination = data_dict.get("pagination") or data_dict.get("paginator") or {}
                total_pages = pagination.get("total_pages") or pagination.get("totalPages", 0)
                page_index = pagination.get("shown_page") or pagination.get("shownPage", 1)

                if product_ids:
                    all_products = await self._fetch_details_chunks(site, product_ids, debug, fetch)
                    if all_products:
                        out = _ok(site, all_products, mode)
                        out["pagination"] = {"total_pages": total_pages, "page_index": page_index}
                        if debug: out["debug"] = debug_log
                        return out

                raw = {"source": "api_direct_category", "api_url": api_url, "api_data": api_data}
                normalized = api.normalize(raw)
                # If redirect was followed but still got 0 products, fall through to HTML
                if was_redirected and not normalized["products"]:
                    logger.warning(
                        f"API redirect led to 0 products for {url}, falling through to HTML",
                        extra={"site": site}
                    )
                else:
                    out = _ok(site, normalized["products"], mode)
                    out["pagination"] = {"total_pages": total_pages, "page_index": page_index}
                    if debug: out["debug"] = debug_log
                    return out

        # 3. Seller
        seller_match = re.search(r'/seller/([^/]+)/', url)
        if seller_match:
            slug = seller_match.group(1)
            sellers_url = f"https://common-api.rozetka.com.ua/v1/api/sellers?country=UA&lang=ua&name={slug}"
            s_code, s_data, s_meta = await fetch(site, sellers_url, parse_json=True, save_raw=debug)
            
            seller_id = None
            if s_code == 200 and isinstance(s_data, dict):
                data_dict = s_data.get("data", {})
                if data_dict:
                    first_key = next(iter(data_dict))
                    seller_info = data_dict[first_key]
                    seller_id = seller_info.get("owox_id") or seller_info.get("id")
            
            if seller_id:
                catalog_url = f"https://catalog-api.rozetka.com.ua/v0.1/api/category/seller/catalog?country=UA&lang=ua&id={seller_id}"
                if int(page) > 1: catalog_url += f"&filters=page:{page}"
                cat_code, cat_data, cat_meta = await fetch(site, catalog_url, parse_json=True, save_raw=debug)
                if debug: _save_debug_item(site, "api_seller_catalog", catalog_url, cat_meta, cat_data, [])

                if cat_code == 200 and isinstance(cat_data, dict):
                    goods = cat_data.get("data", {}).get("goods", {})
                    product_ids = [str(pid) for pid in goods.get("ids", [])]
                    total_pages = goods.get("total_pages", 0)
                    page_index = goods.get("shown_page", 1)

                    if product_ids:
                        all_products = await self._fetch_details_chunks(site, product_ids, debug, fetch)
                        if all_products:
                            out = _ok(site, all_products, mode)
                            out["pagination"] = {"total_pages": total_pages, "page_index": page_index}
                            if debug: out["debug"] = debug_log
                            return out

        # 4. Fallback HTML
        paginated_url = self._inject_page(url, page)
        logger.info(f"Falling back to HTML extraction for {paginated_url}", extra={"site": site})
        h_headers = {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Referer": "https://rozetka.com.ua/"}
        code, html, html_meta = await fetch(site, paginated_url, extra_headers=h_headers, parse_json=False, save_raw=debug)
        if debug: _save_debug_item(site, "html_fetch", paginated_url, html_meta, {"html_snippet": html[:2000]}, [])

        if code != 200:
            out = _err(site, mode, f"HTTP {code}", code)
            if debug: out["debug"] = debug_log
            return out

        ld_blocks = _extract_ld_json(html)
        for block in ld_blocks:
            if block.get("@type") == "ItemList" and block.get("itemListElement"):
                normalized = api.normalize({"source": "ld+json", "ld_json": block})
                out = _ok(site, normalized["products"], mode)
                out["pagination"] = normalized.get("pagination", {"total_pages": 0, "page_index": 1})
                if debug: out["debug"] = debug_log
                return out

        client_state = _extract_script_by_id(html, "rz-client-state")
        if client_state:
            api_url_enc = _find_common_api_request_in_client_state(client_state)
            if api_url_enc:
                api_code, api_data, api_meta = await fetch(site, api_url_enc, parse_json=True, save_raw=debug)
                if api_code == 200:
                    normalized = api.normalize({"source": "rz-client-state", "api_data": api_data})
                    if normalized["products"]:
                        out = _ok(site, normalized["products"], mode)
                        out["pagination"] = normalized.get("pagination", {"total_pages": 0, "page_index": 1})
                        if debug: out["debug"] = debug_log
                        return out

        match = re.search(r"window\.RZ\.goods\s*=\s*(\{.*?\});", html)
        if match:
            try:
                normalized = api.normalize({"source": "window.RZ.goods", "ld_json": json.loads(match.group(1))})
                out = _ok(site, normalized["products"], mode)
                if debug: out["debug"] = debug_log
                return out
            except Exception as e:
                logger.debug(f"Legacy window.RZ.goods parse failed: {e}", extra={"site": site})

        out = _err(site, mode, "Could not find any data source for Rozetka", 404)
        if debug: out["debug"] = debug_log
        return out

    async def _fetch_details_chunks(self, site: str, product_ids: List[str], debug: bool, fetch) -> List[Dict]:
        all_products = []
        CHUNK_SIZE = 60
        for i in range(0, len(product_ids), CHUNK_SIZE):
            chunk = product_ids[i:i + CHUNK_SIZE]
            details_url = f"https://common-api.rozetka.com.ua/v1/api/product/details?country=UA&lang=ua&ids={','.join(chunk)}"
            det_code, det_data, det_meta = await fetch(site, details_url, parse_json=True, save_raw=debug)
            if det_code == 200:
                normalized = self._api.normalize({"source": "api_direct_details", "api_data": det_data})
                all_products.extend(normalized["products"])
            if debug: _save_debug_item(site, "product_details", details_url, det_meta, det_data, normalized.get("products", []) if det_code == 200 else [])
        return all_products

    def _inject_page(self, url: str, page: int) -> str:
        if page <= 1:
            return url
            
        parsed = urlparse(url)
        path = parsed.path
        
        # 1. Search uses query param `page`
        if "/search/" in path:
            qs = parse_qs(parsed.query)
            qs["page"] = [str(page)]
            new_query = urlencode(qs, doseq=True)
            return urlunparse(parsed._replace(query=new_query))
            
        # 2. Others use path-based injection
        new_path = self._inject_page_into_path(path, page)
        return urlunparse(parsed._replace(path=new_path))

    def _inject_page_into_path(self, path: str, page: int) -> str:
        if page <= 1: return path
        
        # Strip existing
        path = re.sub(r'/page=\d+/?', '/', path)
        path = re.sub(r'page=\d+[;/]?', '', path)
        path = re.sub(r'/+', '/', path)
        
        # Find category ID or producer slug end
        match = re.search(r'(/c\d+/|/producer/[^/]+/|/brand/[^/]+/)(.*)', path)
        if match:
            prefix = match.group(1)
            suffix = match.group(2)
            if suffix and suffix != "/":
                return f"{path[:match.start(1)]}{prefix}page={page};{suffix.lstrip('/')}"
            else:
                return f"{path[:match.start(1)]}{prefix}page={page}/"
        
        # Fallback
        if path.endswith("/"):
            return f"{path.rstrip('/')}/page={page}/"
        else:
            return f"{path}/page={page}/"
