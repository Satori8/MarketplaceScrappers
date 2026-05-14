import re
import json
import execjs
from typing import Dict

from scrapers.mapi_scraper.base import BaseModule
from scrapers.mapi_scraper.http import _get_with_meta, _ok, _err, _save_debug_item, logger, _ALLO_HEADERS
from scrapers.mapi_scraper.extractors import _extract_ld_json, _extract_js_assignment_raw

class AlloAPI:
    def __init__(self):
        self.site = "allo"
        self.total_pages = 0
        self.page_index = 0

    def normalize(self, raw_data: Dict) -> Dict:
        """Standardizes Allo responses from LD+JSON or window.__ALLO__ state.

        window.__ALLO__ structure (confirmed via JSON analysis):
          products:   state["catalog/category/product-list"]["products"]
          pagination: state["catalog/category/product-list"]["pagination"]
          categories: state["catalog/category"]
          properties: map description_attributes as properties[]
          sku vs id:  they are separate fields
        """
        products = []
        source = raw_data.get("source")
        
        if source == "ld+json":
            ld = raw_data.get("ld_json", {})
            # Allo often wraps items in @graph
            graph = ld.get("@graph", [ld])
            
            for block in graph:
                if block.get("@type") == "ItemList":
                    items = block.get("itemListElement", [])
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
                            "url": p_item.get("url"),
                            "image": p_item.get("image")
                        })
        
        elif source == "window.__ALLO__":
            raw = raw_data.get("raw__allo", {})
            if not isinstance(raw, dict):
                return {"products": [], "pagination": {"total_pages": 0, "page_index": 0}}

            state = raw.get("state", {})
            pl_data = state.get("catalog/category/product-list", {})
            cat_root = state.get("catalog/category", {})
            cat_inner = cat_root.get("category", {}) or {}

            products_raw = pl_data.get("products", [])
            pagination_raw = pl_data.get("pagination", {})
            
            # Pagination
            items_total = pagination_raw.get("total_number_of_items") or 0
            per_page = pagination_raw.get("items_per_page") or 60
            self.total_pages = int(pagination_raw.get("total_pages") or 0)
            if self.total_pages == 0 and items_total > 0:
                self.total_pages = (items_total + per_page - 1) // per_page
            self.page_index = int(pagination_raw.get("current_page") or 1)
            
            # Category info
            category_id = cat_inner.get("categoryId") or cat_root.get("categoryId")
            category_name = cat_inner.get("name") or cat_inner.get("label")
            if not category_name:
                crumbs = state.get("common", {}).get("breadcrumbs", [])
                if crumbs:
                    category_name = crumbs[-1].get("label")

            # Build merchant mapping from seoMicroMarkup (found inside catalog/category)
            merchant_map = {}
            seo_markup = cat_root.get("seoMicroMarkup", {})
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

                products.append({
                    "id": str(pid) if pid is not None else psku,
                    "sku": psku,
                    "name": p.get("name"),
                    "brand": p.get("brand"),
                    "price": str(price_val) if price_val is not None else None,
                    "avail_code": 1 if p.get("stock_status") == 1 else 0,
                    "merchant_id": None,
                    "merchant_name": merchant_map.get(psku),
                    "category_id": category_id or p.get("category_id"),
                    "category_name_ua": category_name,
                    "category_name_ru": None,
                    "properties": properties,
                    "url": p.get("url"),
                    "image": image_url
                })

        if not products and self.total_pages > 0:
            logger.warning(f"Extracted 0 products from {source}, but total_pages={self.total_pages}", extra={"site": self.site})
        else:
            logger.info(f"Extracted {len(products)} products from {source}", extra={"site": self.site})

        return {
            "products": products,
            "pagination": {
                "total_pages": self.total_pages,
                "page_index": self.page_index
            }
        }


class AlloModule(BaseModule):
    SITE_ID = "allo"
    DOMAINS = ["allo.ua"]
    
    def __init__(self):
        self._api = AlloAPI()

    def scrape_url(self, url: str, page: int = 1, debug: bool = False) -> dict:
        site = self.SITE_ID
        api = self._api
        mode = "url"
        
        if not url:
            return _err(site, mode, "URL is required")

        logger.info(f"Fetching Allo URL: {url}", extra={"site": site})
        code, html, meta = _get_with_meta(site, url, extra_headers=_ALLO_HEADERS, parse_json=False, save_raw=debug)
        
        normalized_data = None
        
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
            except:
                pass

        if js_value:
            try:
                # We use a wrapper function to ensure window.__ALLO__ is returned correctly
                full_js = f"""
                var window = {{}};
                var document = {{ 
                    createElement: function() {{ return {{}}; }},
                    getElementsByTagName: function() {{ return [{{ appendChild: function() {{}} }}]; }}
                }};
                var navigator = {{ userAgent: "" }};
                window.__ALLO__ = {js_value};
                """
                full_js = full_js.encode('ascii', 'backslashreplace').decode('ascii')
                
                ctx = execjs.compile(full_js)
                
                # TO PREVENT UnicodeDecodeError on Windows pipe: 
                # We stringify the result and escape all non-ASCII characters on the Node side.
                # This ensures the STDOUT pipe only contains ASCII characters.
                eval_script = (
                    "JSON.stringify(window.__ALLO__).replace(/[\\u007f-\\uffff]/g, "
                    "function(c) { return \"\\\\u\" + (\"0000\" + c.charCodeAt(0).toString(16)).slice(-4); })"
                )
                json_str = ctx.eval(eval_script)
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
