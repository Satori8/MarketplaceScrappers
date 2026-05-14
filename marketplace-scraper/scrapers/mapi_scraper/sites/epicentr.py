import re
from typing import Dict, Optional, Tuple, Any

from scrapers.mapi_scraper.base import BaseModule
from scrapers.mapi_scraper.http import _get_with_meta, _ok, _err, _save_debug_item, logger, _EPI_API_V1, _EPI_API_V2, _EPI_MERCHANT_API

class EpicentrAPI:
    def __init__(self):
        self.site = "epicentr"
        # Strict Headers for stateless reproducibility
        self.headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "uk-UA,uk;q=0.9",
            "ssr-platform": "nuxt",
            "x-is-robot": "0",
            "referer": "https://epicentrk.ua/",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
        }
        self.total_pages = 0
        self.page_index = 0

    def _api_get(self, url: str, params: Optional[Dict] = None, debug: bool = False) -> Tuple[int, Any, Dict]:
        # Use impersonate="chrome120" or higher for TLS fingerprinting
        code, data, meta = _get_with_meta(self.site, url, params=params, extra_headers=self.headers, parse_json=True, save_raw=debug)
        return code, data, meta

    def listing(self, path: str, page: int = 1, debug: bool = False) -> Dict:
        """Fetch products from a listing (category/filter) URL."""
        # path looks like /shop/linoleum/fs/brand-tarkett/
        url = f"{_EPI_API_V2}/product/listing/products"
        params = {
            "store_id": "2",
            "query[]": path,
            "lang": "ua",
            "page_size": 60,
            "rankSort": "by_rank"
        }
        if page > 1: params["page"] = page
        code, data, meta = self._api_get(url, params, debug=debug)
        if code == 200: 
            return {"ok": True, "products": data, "meta": meta}
        return {"ok": False, "error": f"HTTP {code}", "code": code, "meta": meta}

    def section_data(self, path: str, debug: bool = False) -> Dict:
        """Fetch metadata/filters for a listing."""
        url = f"{_EPI_API_V2}/product/listing/section-data"
        params = {
            "store_id": "2",
            "query[]": path,
            "lang": "ua"
        }
        code, data, meta = self._api_get(url, params, debug=debug)
        if code == 200:
             out = _ok(self.site, data, "section_data")
             out["meta"] = meta
             return out
        return _err(self.site, "section_data", f"HTTP {code}", code)

    def merchant(self, name: str, page: int = 1, debug: bool = False) -> Dict:
        """Fetch products from a specific merchant."""
        url = _EPI_MERCHANT_API
        params = {
            "lang": "ua",
            "name": name,
            "page_size": 60
        }
        if page > 1: params["page"] = page
        code, data, meta = self._api_get(url, params, debug=debug)
        if code == 200:
            return {"ok": True, "products": data, "meta": meta}
        return {"ok": False, "error": f"HTTP {code}", "code": code, "meta": meta}

    def search(self, find: str, page: int = 1, debug: bool = False) -> Dict:
        """Fetch search results."""
        url = f"{_EPI_API_V1}/search"
        params = {
            "find": find,
            "store_id": "2",
            "lang": "ua",
            "page": page,
            "search_size": 40
        }
        code, data, meta = self._api_get(url, params, debug=debug)
        if code == 200:
            return {"ok": True, "products": data, "meta": meta}
        return {"ok": False, "error": f"HTTP {code}", "code": code, "meta": meta}

    def product_full(self, slug: str, debug: bool = False) -> Dict:
        """Fetch full product details."""
        url = f"{_EPI_API_V1}/product/card/full"
        params = {
            "store_id": "2",
            "slug": slug,
            "lang": "ua"
        }
        code, data, meta = self._api_get(url, params, debug=debug)
        if code == 200:
            return {"ok": True, "products": data, "meta": meta}
        return {"ok": False, "error": f"HTTP {code}", "code": code, "meta": meta}

    def normalize(self, raw_data: Any, context: str) -> Dict:
        """Unify different API responses into a single product list format."""
        products = []
        
        inner = {}
        if isinstance(raw_data, dict):
            # Check v1/v2 results data wrapper: data['data']['items'] or data['items']
            if isinstance(raw_data.get('data'), dict):
                inner = raw_data['data']
            else:
                inner = raw_data

        if context in ("listing", "search"):
            items = inner.get('items', [])
            self.page_index = inner.get('pageIndex', 1)
            self.total_pages = inner.get('totalPages', 0)
            
            # Fallback for search total
            if not self.total_pages and raw_data.get('total'):
                self.total_pages = (int(raw_data['total']) + 39) // 40

            for it in items:
                products.append({
                    "id": str(it.get('productId') or it.get('id') or ""),
                    "sku": str(it.get('id')) if it.get('id') else None,
                    "name": it.get('name') or it.get('name_ua') or it.get('nameUa'),
                    "brand": it.get('vendorUa') or it.get('brandUa'),
                    "price": it.get('price'),
                    "avail_code": it.get('availabilityStatus', {}).get('code') if isinstance(it.get('availabilityStatus'), dict) else it.get('avail'),
                    "merchant_id": str(it.get('merchantId') or it.get('merchant') or ""),
                    "merchant_name": it.get('merchantName') or it.get('merchant_name'),
                    "category_id": str(it.get('categoryId') or it.get('sectionId') or it.get('section_id') or ""),
                    "category_name_ua": it.get('sectionsUa') or it.get('sections_ua'),
                    "category_name_ru": it.get('section_ru') or it.get('sectionRu'),
                    "properties": it.get('properties', []),
                    "url": it.get('url'),
                    "image": (it.get('img', {}).get('url') if isinstance(it.get('img'), dict) else it.get('picture'))
                })

        elif context == "merchant":
            # Data is in params['products']
            params = raw_data.get('params', {})
            items = params.get('products', [])
            m_info = params.get('merchant', {})
            
            p_data = params.get('pagination', {})
            self.page_index = p_data.get('page', 1)
            self.total_pages = p_data.get('pages', 0)
            
            for it in items:
                products.append({
                    "id": str(it.get('productId') or it.get('id') or ""),
                    "sku": str(it.get('id')) if it.get('id') else None,
                    "name": it.get('name_ua') or it.get('name') or it.get('nameUa'),
                    "brand": it.get('vendorUa') or it.get('brandUa'),
                    "price": it.get('price'),
                    "avail_code": it.get('avail') or (it.get('availabilityStatus', {}).get('code') if isinstance(it.get('availabilityStatus'), dict) else None),
                    "merchant_id": str(it.get('merchant') or it.get('merchantId') or ""),
                    "merchant_name": m_info.get('title') or m_info.get('name'),
                    "category_id": str(it.get('section_id') or it.get('sectionId') or it.get('categoryId') or ""),
                    "category_name_ua": it.get('sections_ua') or it.get('sectionsUa'),
                    "category_name_ru": it.get('section_ru') or it.get('sectionRu'),
                    "properties": it.get('properties', []),
                    "url": it.get('url'),
                    "image": it.get('picture') or (it.get('img', {}).get('url') if isinstance(it.get('img'), dict) else None)
                })

        if not products:
            logger.warning(f"Extracted 0 products from {context} (page {self.page_index})", extra={"site": self.site})
        else:
            logger.info(f"Extracted {len(products)} products from {context} (page {self.page_index})", extra={"site": self.site})

        return {
            "products": products,
            "pagination": {
                "total_pages": self.total_pages,
                "page_index": self.page_index
            }
        }


class EpicentrModule(BaseModule):
    SITE_ID = "epicentr"
    DOMAINS = ["epicentrk.ua"]

    def __init__(self):
        self._api = EpicentrAPI()

    def scrape_url(self, url: str, page: int = 1, debug: bool = False) -> dict:
        site = self.SITE_ID
        api = self._api
        mode = "url"
        
        if not url: return _err(site, mode, "URL required")
        
        res = None
        context = ""
        
        # 1. Detect Merchant
        if "/merchant/" in url:
            try:
                parts = [p for p in url.split("/") if p]
                if "merchant" in parts:
                    idx = parts.index("merchant")
                    if idx + 1 < len(parts):
                        slug = parts[idx + 1]
                        res = api.merchant(slug, page=int(page), debug=debug)
                        context = "merchant"
            except Exception as e:
                pass

        # 2. Detect Product Card (usually ends in .html)
        if not res and url.endswith(".html"):
            try:
                slug = url.split("/")[-1].replace(".html", "")
                res = api.product_full(slug, debug=debug)
                # Product details don't go through api.normalize list pipeline in same way
                if res.get("ok"):
                    if debug:
                        meta = res.get("meta", {})
                        _save_debug_item(site, "api_direct_details", meta.get("url", url), meta, res.get("products", []), [])
                    return res
            except: pass

        # 3. Detect Listing (/shop/ and not .html)
        if not res and "/shop/" in url:
            try:
                from urllib.parse import urlparse
                path = urlparse(url).path
                res = api.listing(path, page=int(page), debug=debug)
                context = "listing"
            except: pass
            
        # 4. Detect Search
        if not res and "/search" in url:
            try:
                from urllib.parse import urlparse, parse_qs
                query = parse_qs(urlparse(url).query).get("q", [""])[0]
                if query:
                    res = api.search(query, page=int(page), debug=debug)
                    context = "search"
            except: pass

        if res:
            if res.get("ok"):
                normalized_data = api.normalize(res["products"], context)
                if debug:
                    meta = res.get("meta", {})
                    products = normalized_data.get("products", []) if normalized_data else []
                    _save_debug_item(site, f"api_direct_{context}", meta.get("url", url), meta, res.get("products", []), products)
                
                out = _ok(site, normalized_data.get("products", []), mode)
                if "pagination" in normalized_data:
                     out["pagination"] = normalized_data["pagination"]
                if debug: out["debug"] = True
                return out
            else:
                logger.warning(f"Direct API call for {context} failed: {res.get('error')}", extra={"site": site})
                last_error = res

        # 4. SSR Fallback (Nuxt State)
        logger.info(f"Falling back to SSR extraction for {url}", extra={"site": site})
        code, html, meta = _get_with_meta(site, url, parse_json=False, save_raw=debug)
        if code == 200:
            match = re.search(r"window\.__NUXT__\s*=\s*(.*?);(?!<)", html, re.DOTALL)
            if match:
                if debug:
                    _save_debug_item(site, "html_fetch_ssr", meta.get("url", url), meta, {"ssr_nuxt_raw": match.group(0)[:2000]}, [])
                out = _ok(site, {"source": "window.__NUXT__", "ssr_nuxt_state": match.group(1).strip()[:5000]}, mode)
                if debug: out["debug"] = True
                return out

        if 'last_error' in locals():
            return last_error

        return _err(site, mode, "Could not identify URL pattern or find SSR state for Epicentr", 404)
