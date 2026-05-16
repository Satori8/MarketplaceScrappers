import re
import json
import execjs
import asyncio
import threading
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from scrapers.mapi_scraper.base import BaseModule
from scrapers.mapi_scraper.http import _get_with_meta, _aget_with_meta, _ok, _err, _save_debug_item, logger, _ALLO_HEADERS, _make_sync_fetcher, _make_async_fetcher
from scrapers.mapi_scraper.extractors import _extract_ld_json, _extract_js_assignment_raw, _map_ld_json_offer

class AlloAPI:
    def __init__(self):
        self.site = "allo"

    def normalize(self, raw_data: Dict) -> Dict:
        """Standardizes Allo responses from LD+JSON or window.__ALLO__ state."""
        products = []
        source = raw_data.get("source")
        total_pages = 0
        page_index = 1
        
        if source == "ld+json":
            ld = raw_data.get("ld_json", {})
            # Allo often wraps items in @graph
            graph = ld.get("@graph", [ld])
            
            for block in graph:
                if block.get("@type") == "ItemList":
                    items = block.get("itemListElement", [])
                    for it in items:
                        p_item = it.get("item", {})
                        products.append(_map_ld_json_offer(p_item))
        
        elif source == "window.__ALLO__":
            raw = raw_data.get("raw__allo", {})
            if not isinstance(raw, dict):
                return {"products": [], "pagination": {"total_pages": 0, "page_index": 0}}

            state = raw.get("state", {})
            
            # Try category path first
            pl_data = state.get("catalog/category/product-list") or state.get("catalog/search/product-list") or {}
            cat_root = state.get("catalog/category") or state.get("catalog/search") or {}
            cat_inner = cat_root.get("category", {}) or {}

            products_raw = pl_data.get("products", [])
            pagination_raw = pl_data.get("pagination", {})
            
            # Pagination
            items_total = pagination_raw.get("total_number_of_items") or 0
            per_page = pagination_raw.get("items_per_page") or 60
            total_pages = int(pagination_raw.get("total_pages") or 0)
            if total_pages == 0 and items_total > 0:
                total_pages = (items_total + per_page - 1) // per_page
            page_index = int(pagination_raw.get("current_page") or 1)
            
            # Category info
            category_id = cat_inner.get("categoryId") or cat_root.get("categoryId")
            category_name = cat_inner.get("name") or cat_inner.get("label")
            
            # Step 1.5: Build Category Map from Layered Navigation (useful for search results)
            cat_map = {}
            layered = state.get("layered_navigation") or {}
            cat_filters = layered.get("category_filter", [])
            for cf in cat_filters:
                if cf.get("categoryId"):
                    cat_map[str(cf.get("categoryId"))] = cf.get("label")
                for child in cf.get("children", []):
                    if child.get("cat_id"):
                        cat_map[str(child.get("cat_id"))] = child.get("label")

            if not category_name:
                crumbs = state.get("common", {}).get("breadcrumbs", [])
                if crumbs:
                    category_name = crumbs[-1].get("label")

            # Build merchant mapping from seoMicroMarkup
            merchant_map = {}
            seo_markup = cat_root.get("seoMicroMarkup") or {}
            if not seo_markup:
                # Try global seo markup if category-specific is missing
                seo_markup = state.get("common", {}).get("seoMicroMarkup") or {}
                
            graph = seo_markup.get("@graph", [])
            for node in graph:
                if isinstance(node, dict) and node.get("@type") == "Product":
                    offers = node.get("offers", [])
                    if isinstance(offers, dict): # Sometimes it's a single dict instead of list
                        offers = [offers]
                    for offer in offers:
                        sku = offer.get("sku")
                        seller = offer.get("seller")
                        if sku and isinstance(seller, dict):
                            merchant_map[sku] = seller.get("name")

            for p in products_raw:
                pid = p.get("id")
                psku = p.get("sku")
                
                # Image extraction from gallery
                gallery = p.get("gallery", {}).get("gallery", [])
                image_url = None
                if gallery:
                    g0 = gallery[0]
                    # Prefer image_xl, then lg, etc.
                    image_url = g0.get("image_xl") or g0.get("image_lg") or g0.get("image_md") or g0.get("image_sm")

                # Mapping description_attributes to properties
                properties = []
                for attr in p.get("description_attributes", []):
                    properties.append({
                        "name": attr.get("label"),
                        "values": attr.get("value")
                    })

                # Price from price object
                price_obj = p.get("price", {})
                price_val = price_obj.get("price") or price_obj.get("amount")

                # Merchant logic: check SKU suffix for partner ID (e.g. 12345-5598 -> 5598 is Partner ID)
                sku_parts = psku.split("-") if psku else []
                partner_id = sku_parts[-1] if len(sku_parts) > 1 and sku_parts[-1].isdigit() else ""
                
                products.append({
                    "id": str(pid) if pid is not None else psku,
                    "sku": psku,
                    "name": p.get("name"),
                    "brand": p.get("brand"),
                    "price": str(price_val) if price_val is not None else None,
                    "avail_code": "В наявності" if p.get("stock_status") == 1 else "Немає в наявності",
                    "merchant_id": str(p.get("seller_id") or p.get("seller", {}).get("id") or partner_id),
                    "merchant_name": p.get("seller_name") or p.get("seller", {}).get("name") or merchant_map.get(psku) or ("Allo" if not partner_id else f"Seller {partner_id}"),
                    "category_id": category_id or p.get("category_id"),
                    "category_name_ua": category_name or p.get("category_name") or cat_map.get(str(p.get("category_id"))),
                    "category_name_ru": None,
                    "properties": properties,
                    "url": p.get("url"),
                    "image": image_url
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


_EXACT_AJAX_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "uk-UA,uk;q=0.9,en-GB;q=0.8,en-US;q=0.7,en;q=0.6",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "priority": "u=1, i",
    "sec-ch-ua": "\"Chromium\";v=\"148\", \"Google Chrome\";v=\"148\", \"Not/A)Brand\";v=\"99\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"Windows\"",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "x-requested-with": "XMLHttpRequest",
    "x-use-nuxt": "1"
}

class AlloModule(BaseModule):
    SITE_ID = "allo"
    DOMAINS = ["allo.ua"]
    
    _DEEPLINK_CACHE = {} 
    _CACHE_LOCK = threading.Lock()
    
    def __init__(self):
        self._api = AlloAPI()

    def _extract_deeplink(self, html: str) -> Optional[str]:
        tail = html[-10000:]
        match = re.search(r"allo\.current_deeplink\s*=\s*'(.*?)';", tail)
        if match: return match.group(1)
        match = re.search(r"allo\.current_deeplink\s*=\s*'(.*?)';", html)
        if match: return match.group(1)
        return None

    def _parse_deeplink(self, deeplink: str) -> Dict[str, str]:
        if '?' not in deeplink: return {}
        parts_str = deeplink.split('?', 1)[1].rstrip(';')
        parts = parts_str.split('/')
        data = {}
        for p in parts:
            if '=' in p:
                k, v = p.split('=', 1)
                data[k] = v
        return data

    def _build_ajax_url(self, parsed_deeplink: Dict[str, str], page: int = 1) -> str:
        category_id = parsed_deeplink.get('category')
        sort_order = parsed_deeplink.get('sort_order', 'product_top_weight')
        sort_dir = parsed_deeplink.get('sort_dir', 'desc')
        filters_str = parsed_deeplink.get('filters', '')
        
        toolbar = {"dir": sort_dir, "order": sort_order, "mode": "list"}
        filters = {}
        if filters_str:
            for group in filters_str.split(';'):
                if '-' in group:
                    fk, fv_str = group.split('-', 1)
                    vals = [int(v) if v.isdigit() else v for v in fv_str.split(',') if v]
                    if fk == 'popular_filters' and (181590 in vals or '181590' in vals):
                        filters['discount'] = 'da'
                    elif fk == 'popular_filters' and (181591 in vals or '181591' in vals):
                        filters['action'] = 'da'
                    else:
                        filters[fk] = vals
        
        search_query = parsed_deeplink.get('search')
        base = "https://allo.ua/ua/catalogsearch/result/update/?" if search_query else "https://allo.ua/ua/catalog/category/update/?"
        
        parts = []
        parts.append(f"toolbar={json.dumps(toolbar, separators=(',', ':'))}")
        parts.append(f"filters={json.dumps(filters or {}, separators=(',', ':'))}")
        parts.append("qty=60")
        
        special_keys = {'search', 'category', 'parent_category', 'filters', 'sort_order', 'sort_dir', 'category_id'}
        for k, v in parsed_deeplink.items():
            if k not in special_keys and v is not None:
                parts.append(f"{k}={v}")

        if search_query: parts.append(f"q={search_query}")
        
        final_cat_id = parsed_deeplink.get('category_id') or category_id
        if not search_query and final_cat_id:
             parts.append(f"category_id={final_cat_id}")
        
        if page > 1: parts.append(f"p={page}")
        elif "p=" not in [p.split('=')[0] for p in parts if '=' in p]: parts.append("p=1")
        parts.append("isAjax=1")
        parts.append("currentLocale=uk_UA")
        
        quoted_parts = []
        for p in parts:
             if '=' in p:
                 k, v = p.split('=', 1)
                 v_quoted = v.replace('{', '%7B').replace('}', '%7D').replace('"', '%22').replace('[', '%5B').replace(']', '%5D')
                 quoted_parts.append(f"{k}={v_quoted}")
             else:
                 quoted_parts.append(p)
             
        return base + "&".join(quoted_parts)

    def scrape_url(self, url: str, page: int = 1, debug: bool = False) -> dict:
        fetch = _make_sync_fetcher()
        try:
            return asyncio.run(self._scrape_impl(url, page, debug, fetch))
        except RuntimeError as e:
            # Caller is already in an async event loop
            logger.warning(f"RuntimeError in sync scrape_url: {e}. Callers in async context must use async_scrape_url().", extra={"site": self.SITE_ID})
            raise

    async def async_scrape_url(self, url: str, page: int = 1, debug: bool = False, proxy: str | None = None) -> dict:
        fetch = _make_async_fetcher(proxy=proxy)
        return await self._scrape_impl(url, page, debug, fetch)

    async def _scrape_impl(self, url: str, page: int, debug: bool, fetch) -> dict:
        site = self.SITE_ID
        api = self._api
        mode = "url"
        
        if not url:
            return _err(site, mode, "URL is required")

        paginated_url = self._inject_page(url, page)
        
        # Strip pagination and search prefixes to generate a stable base URL for the discovery cache
        parsed = urlparse(url)
        c_path = re.sub(r'/p-\d+/?', '/', parsed.path)
        c_path = re.sub(r'/+', '/', c_path)
        if "/catalogsearch/" in c_path and "index/" in c_path:
            c_path = c_path.replace("index/", "") 
        base_url = urlunparse(parsed._replace(path=c_path))

        with self._CACHE_LOCK:
            cached_deeplink = self._DEEPLINK_CACHE.get(base_url)

        # 1. Attempt Discovery / SSR fetch if no deeplink cached
        html = None
        if not cached_deeplink:
            logger.info(f"Fetching SSR Discovery Page: {url}", extra={"site": site})
            code, html, meta = await fetch(site, url, extra_headers=_ALLO_HEADERS, parse_json=False, save_raw=debug)
            
            if code == 200:
                extracted = self._extract_deeplink(html)
                if extracted:
                    cached_deeplink = extracted
                    with self._CACHE_LOCK:
                        self._DEEPLINK_CACHE[base_url] = cached_deeplink
                        logger.info(f"Cached deeplink for {base_url}", extra={"site": site})

        normalized_data = None
        
        # 2. Attempt Lightweight AJAX implementation if deeplink found
        if cached_deeplink:
            parsed_deeplink = self._parse_deeplink(cached_deeplink)
            
            # Partner overrides
            if "partner_" in url:
                partner_match = re.search(r"partner_([^/]+)", url)
                if partner_match:
                    partner_key = partner_match.group(1).rstrip("/")
                    for k in ["category", "parent_category", "partner_products"]:
                        parsed_deeplink.pop(k, None)
                    parsed_deeplink["partner_url_key"] = partner_key
                    parsed_deeplink["is_partner_root_page"] = 1
                    parsed_deeplink["category_id"] = 2
            elif html:
                # Nuxt state fallback
                for key in ["category_id"]:
                    m_nuxt = re.search(f'"{key}"\\s*:\\s*"?([^,",\\]}}]+)"?', html)
                    if m_nuxt:
                        val = m_nuxt.group(1).strip()
                        if key not in parsed_deeplink or parsed_deeplink[key] is None:
                            parsed_deeplink[key] = int(val) if val.isdigit() else (None if val.lower() == "null" else val)
                            
            ajax_url = self._build_ajax_url(parsed_deeplink, page=page)
            ajax_headers = _EXACT_AJAX_HEADERS.copy()
            ajax_headers["Referer"] = url
            
            logger.info(f"Fetching AJAX Page {page}: {ajax_url}", extra={"site": site})
            code_ajax, data_ajax, meta_ajax = await fetch(site, ajax_url, extra_headers=ajax_headers, parse_json=True, save_raw=debug)
            
            if code_ajax == 200 and isinstance(data_ajax, dict):
                products = data_ajax.get("product_list", {}).get("items", [])

                # Determine real total_pages from AJAX response.
                # Allo AJAX may expose total_count at data_ajax["product_list"]["total_count"].
                per_page = 60
                product_list = data_ajax.get("product_list") or {}
                total_count = product_list.get("total_count") or product_list.get("totalCount") or 0
                if total_count:
                    calc_total_pages = (int(total_count) + per_page - 1) // per_page
                elif products and len(products) >= per_page:
                    calc_total_pages = page + 1  # full page → at least one more
                else:
                    calc_total_pages = page  # partial/empty page → this is the last

                mock_raw = {
                    "source": "window.__ALLO__",
                    "raw__allo": {
                        "state": {
                            "catalog/category/product-list": {
                                "products": products,
                                "pagination": {
                                    "total_pages": calc_total_pages,
                                    "current_page": page,
                                }
                            },
                            "catalog/category": {
                                "categoryId": parsed_deeplink.get("category_id"),
                                "category": {"name": parsed_deeplink.get("category_name")}
                            },
                            "layered_navigation": data_ajax.get("layered_navigation")
                        }
                    }
                }
                normalized_data = api.normalize(mock_raw)
                if normalized_data and normalized_data.get("products"):
                    if debug:
                        from scrapers.mapi_scraper.http import _save_debug_item
                        _save_debug_item(site, "ajax", ajax_url, meta_ajax, data_ajax, normalized_data["products"])
                    out = _ok(site, normalized_data["products"], mode)
                    if "pagination" in normalized_data: out["pagination"] = normalized_data["pagination"]
                    if debug: out["debug"] = True
                    return out
            
            logger.warning("Lightweight AJAX scrape failed or returned 0 products. Falling back to SSR.", extra={"site": site})
        
        # 3. Fallback to Legacy SSR implementation
        logger.info(f"Using Legacy SSR pipeline for: {paginated_url}", extra={"site": site})
        # If we didn't fetch HTML above for page > 1, fetch it now
        if not html or html is None:
             code, html, meta = await fetch(site, paginated_url, extra_headers=_ALLO_HEADERS, parse_json=False, save_raw=debug)
        
        # Primary: Allo embeds LD+JSON with @graph array containing ItemList / Product entries
        ld_blocks = _extract_ld_json(html)
        graph_block = None
        for block in ld_blocks:
            if "@graph" in block or (block.get("@type") == "ItemList" and block.get("itemListElement")):
                graph_block = block
                break
        
        js_value = _extract_js_assignment_raw(html, "window.__ALLO__")
        if js_value:
            # 2. Attempt "Dirty" JSON parse (handle IIFEs and common JS-isms like undefined) before Node
            try:
                clean_js = js_value
                # If it's an IIFE, try to extract the return value object
                if clean_js.startswith('(') and 'return' in clean_js:
                    m_ret = re.search(r'return\s+([\{\[])', clean_js)
                    if m_ret:
                        # Extract starting from the brace/bracket
                        inner_raw = _extract_js_assignment_raw(clean_js[m_ret.start(1):], "")
                        if inner_raw:
                            clean_js = inner_raw

                # Replace undefined with null
                clean_js = re.sub(r':\s*undefined([,\}\s])', r': null\1', clean_js)
                res = json.loads(clean_js)
                if res:
                    raw = {"source": "window.__ALLO__", "raw__allo": res}
                    normalized_data = api.normalize(raw)
                    if normalized_data and normalized_data.get("products"):
                        js_value = None
            except Exception as e:
                logger.debug(f"Dirty JSON parse failed: {e}", extra={"site": site})

        if js_value:
            try:
                def run_js(val):
                    full_js = f"""
                    var window = {{}};
                    var document = {{ 
                        createElement: function() {{ return {{}}; }},
                        getElementsByTagName: function() {{ return [{{ appendChild: function() {{}} }}]; }}
                    }};
                    var navigator = {{ userAgent: "" }};
                    window.__ALLO__ = {val};
                    """
                    full_js = full_js.encode('ascii', 'backslashreplace').decode('ascii')
                    ctx = execjs.compile(full_js)
                    eval_script = (
                        "JSON.stringify(window.__ALLO__).replace(/[\\u007f-\\uffff]/g, "
                        "function(c) { return \"\\\\u\" + (\"0000\" + c.charCodeAt(0).toString(16)).slice(-4); })"
                    )
                    return ctx.eval(eval_script)
                loop = asyncio.get_running_loop()
                json_str = await loop.run_in_executor(None, run_js, js_value)
                if json_str:
                    res = json.loads(json_str)
                    raw = {"source": "window.__ALLO__", "raw__allo": res}
                    normalized_data = api.normalize(raw)
            except Exception as e:
                logger.error(f"ExecJS Error (Allo): {e}", extra={"site": site})
        
        if normalized_data is None and graph_block:
            logger.info("Falling back to LD+JSON for Allo", extra={"site": site})
            raw = {"source": "ld+json", "ld_json": graph_block}
            normalized_data = api.normalize(raw)

        if debug:
            products = normalized_data.get("products", []) if normalized_data else []
            _save_debug_item(site, "html_extraction", meta["url"], meta, js_value or {"ld_json": graph_block}, products)

        if normalized_data and normalized_data.get("products"):
            out = _ok(site, normalized_data["products"], mode)
            if "pagination" in normalized_data:
                 out["pagination"] = normalized_data["pagination"]
            if debug: out["debug"] = True
            return out

        # Fallback: window.__NUXT__ or window.__ALLO__ raw strings
        ssr_data = {}
        nuxt_match = re.search(r"window\.__NUXT__\s*=\s*(.*?);(?!<)", html, re.DOTALL)
        allo_match = re.search(r"window\.__ALLO__\s*=\s*(.*?);(?!<)", html, re.DOTALL)
        if nuxt_match: ssr_data["ssr_nuxt_state_raw"] = nuxt_match.group(1).strip()[:2000]
        if allo_match: ssr_data["ssr_allo_state_raw"] = allo_match.group(1).strip()[:2000]
        if ssr_data: 
             out = _ok(site, ssr_data, mode)
             if debug: out["debug"] = True
             return out

        out = _err(site, mode, "Could not find LD+JSON or SSR state on Allo", 404)
        if debug: out["debug"] = True
        return out

    def _inject_page(self, url: str, page: int) -> str:
        if page <= 1:
            return url
            
        parsed = urlparse(url)
        path = parsed.path
        
        # strip existing /p-N/ if present
        path = re.sub(r'/p-\d+/?', '/', path)
        path = re.sub(r'/+', '/', path)
        
        if "/catalogsearch/" in path:
             # inject `index/p-{N}/` into path
             if "index/" in path:
                 path = path.replace("index/", f"index/p-{page}/")
             else:
                 path = path.rstrip("/") + f"/index/p-{page}/"
        else:
             # inject `/p-{N}/` before last trailing slash or at end of path
             if path.endswith("/"):
                 path = f"{path.rstrip('/')}/p-{page}/"
             else:
                 path = f"{path}/p-{page}/"
                 
        return urlunparse(parsed._replace(path=path))
