import re
import asyncio
from typing import Dict, Optional, Tuple, Any
from urllib.parse import urlparse, parse_qs

from scrapers.mapi_scraper.base import BaseModule
from scrapers.mapi_scraper.http import _get_with_meta, _aget_with_meta, _ok, _err, _save_debug_item, logger, _EPI_API_V1, _EPI_API_V2, _EPI_MERCHANT_API, _make_sync_fetcher, _make_async_fetcher

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
        self.page_index = 1
        self.total_pages = 0

    async def _api_get(self, fetch_fn, url: str, params: Optional[Dict] = None, debug: bool = False) -> Tuple[int, Any, Dict]:
        code, data, meta = await fetch_fn(self.site, url, params=params, extra_headers=self.headers, parse_json=True, save_raw=debug)
        return code, data, meta

    async def listing(self, fetch_fn, path: str, page: int = 1, debug: bool = False) -> Dict:
        """Fetch products from a listing (category/filter) URL."""
        url = f"{_EPI_API_V2}/product/listing/products"
        params = {
            "store_id": "2",
            "query[]": path,
            "lang": "ua",
            "page_size": 60,
            "rankSort": "by_rank"
        }
        if page > 1: params["page"] = page
        code, data, meta = await self._api_get(fetch_fn, url, params, debug=debug)
        if code == 200: 
            return {"ok": True, "products": data, "meta": meta}
        return {"ok": False, "error": f"HTTP {code}", "code": code, "meta": meta}

    async def merchant(self, fetch_fn, name: str, page: int = 1, debug: bool = False) -> Dict:
        """Fetch products from a specific merchant."""
        url = _EPI_MERCHANT_API
        params = {
            "lang": "ua",
            "name": name,
            "page_size": 60
        }
        if page > 1: params["page"] = page
        code, data, meta = await self._api_get(fetch_fn, url, params, debug=debug)
        if code == 200:
            return {"ok": True, "products": data, "meta": meta}
        return {"ok": False, "error": f"HTTP {code}", "code": code, "meta": meta}

    async def brand(self, fetch_fn, slug: str, page: int = 1, debug: bool = False) -> Dict:
        """Fetch products from a brand brand page."""
        url = f"{_EPI_API_V1}/brands/brand"
        params = {
            "store_id": "2",
            "slug": slug,
            "lang": "ru",
            "page_size": 60
        }
        if page > 1: params["page"] = page
        code, data, meta = await self._api_get(fetch_fn, url, params, debug=debug)
        if code == 200:
            return {"ok": True, "products": data, "meta": meta}
        return {"ok": False, "error": f"HTTP {code}", "code": code, "meta": meta}

    async def search(self, fetch_fn, find: str, page: int = 1, debug: bool = False) -> Dict:
        """Fetch search results."""
        url = f"{_EPI_API_V1}/search"
        params = {
            "find": find,
            "store_id": "2",
            "lang": "ua",
            "page": page,
            "search_size": 40
        }
        code, data, meta = await self._api_get(fetch_fn, url, params, debug=debug)
        if code == 200:
            return {"ok": True, "products": data, "meta": meta}
        return {"ok": False, "error": f"HTTP {code}", "code": code, "meta": meta}

    async def product_full(self, fetch_fn, slug: str, debug: bool = False) -> Dict:
        """Fetch full product details."""
        url = f"{_EPI_API_V1}/product/card/full"
        params = {
            "store_id": "2",
            "slug": slug,
            "lang": "ua"
        }
        code, data, meta = await self._api_get(fetch_fn, url, params, debug=debug)
        if code == 200:
            return {"ok": True, "products": data, "meta": meta}
        return {"ok": False, "error": f"HTTP {code}", "code": code, "meta": meta}

    def normalize(self, raw_data: Any, context: str) -> Dict:
        """Unify different API responses into a single product list format."""
        products = []
        self.total_pages = 0
        self.page_index = 1
        
        inner = {}
        if isinstance(raw_data, dict):
            if isinstance(raw_data.get('data'), dict):
                inner = raw_data['data']
            else:
                inner = raw_data

        if context in ("listing", "search"):
            items = inner.get('items', [])
            self.page_index = inner.get('pageIndex', 1)
            self.total_pages = inner.get('totalPages', 0)
            
            if not self.total_pages and raw_data.get('total'):
                self.total_pages = (int(raw_data['total']) + 39) // 40

            for it in items:
                # Mapping Epicentr availability codes to standard labels
                raw_avail = it.get('availabilityStatus', {}).get('code') if isinstance(it.get('availabilityStatus'), dict) else it.get('avail')
                if raw_avail == 100:
                    avail_str = "В наявності"
                elif raw_avail == 400:
                    avail_str = "Немає в наявності"
                elif raw_avail in (250, 300):
                    avail_str = "Під замовлення"
                elif raw_avail == 500:
                    avail_str = "Знятий з виробництва"
                else:
                    avail_str = "Немає в наявності"

                seller_obj = it.get('seller') if isinstance(it.get('seller'), dict) else {}
                merchant_id = str(seller_obj.get('id') or it.get('merchantId') or it.get('merchant') or "")
                merchant_name = seller_obj.get('name') or it.get('merchantName') or it.get('merchant_name')
                
                if not merchant_name and not merchant_id:
                    merchant_name = "Epicentr"
                elif not merchant_name:
                    merchant_name = f"Seller {merchant_id}"

                products.append({
                    "id": str(it.get('productId') or it.get('id') or ""),
                    "sku": str(it.get('id')) if it.get('id') else None,
                    "name": it.get('name') or it.get('name_ua') or it.get('nameUa'),
                    "brand": it.get('brandName') or it.get('brand') or it.get('vendorUa') or it.get('brandUa'),
                    "price": it.get('price'),
                    "avail_code": avail_str,
                    "merchant_id": merchant_id,
                    "merchant_name": merchant_name,
                    "category_id": str(it.get('categoryId') or it.get('sectionId') or it.get('section_id') or ""),
                    "category_name_ua": it.get('sectionsUa') or it.get('sections_ua'),
                    "category_name_ru": it.get('section_ru') or it.get('sectionRu'),
                    "url": it.get('url'),
                    "image": (it.get('img', {}).get('url') if isinstance(it.get('img'), dict) else it.get('picture')),
                    "attributes": {p.get('name'): p.get('value') for p in it.get('properties', []) if isinstance(p, dict) and p.get('name')} if isinstance(it.get('properties'), list) else {},
                    "extra": {}
                })


        elif context == "merchant":
            params = raw_data.get('params', {})
            items = params.get('products', [])
            m_info = params.get('merchant', {})
            p_data = params.get('pagination', {})
            self.page_index = p_data.get('page', 1)
            self.total_pages = p_data.get('pages', 0)
            
            for it in items:
                # Mapping Epicentr availability codes to standard labels
                raw_avail = it.get('avail') or (it.get('availabilityStatus', {}).get('code') if isinstance(it.get('availabilityStatus'), dict) else None)
                if raw_avail == 100:
                    avail_str = "В наявності"
                elif raw_avail == 400:
                    avail_str = "Немає в наявності"
                elif raw_avail in (250, 300):
                    avail_str = "Під замовлення"
                elif raw_avail == 500:
                    avail_str = "Знятий з виробництва"
                else:
                    avail_str = "Немає в наявності"

                products.append({
                    "id": str(it.get('productId') or it.get('id') or ""),
                    "sku": str(it.get('id')) if it.get('id') else None,
                    "name": it.get('name_ua') or it.get('name') or it.get('nameUa'),
                    "brand": it.get('vendorUa') or it.get('brandUa'),
                    "price": it.get('price'),
                    "avail_code": avail_str,
                    "merchant_id": str(it.get('merchant') or it.get('merchantId') or ""),
                    "merchant_name": m_info.get('title') or m_info.get('name'),
                    "category_id": str(it.get('section_id') or it.get('sectionId') or it.get('categoryId') or ""),
                    "category_name_ua": it.get('sections_ua') or it.get('sectionsUa'),
                    "category_name_ru": it.get('section_ru') or it.get('sectionRu'),
                    "url": it.get('url'),
                    "image": it.get('picture') or (it.get('img', {}).get('url') if isinstance(it.get('img'), dict) else None),
                    "attributes": {p.get('name'): p.get('value') for p in it.get('properties', []) if isinstance(p, dict) and p.get('name')} if isinstance(it.get('properties'), list) else {},
                    "extra": {}
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
        fetch = _make_sync_fetcher()
        try:
            return asyncio.run(self._scrape_impl(url, page, debug, fetch))
        except RuntimeError as e:
            logger.warning(f"RuntimeError in sync scrape_url: {e}. Callers in async context must use async_scrape_url().", extra={"site": self.SITE_ID})
            raise

    async def async_scrape_url(self, url: str, page: int = 1, debug: bool = False, proxy: str | None = None) -> dict:
        fetch = _make_async_fetcher(proxy=proxy)
        return await self._scrape_impl(url, page, debug, fetch)

    async def _scrape_impl(self, url: str, page: int, debug: bool, fetch) -> dict:
        site = self.SITE_ID
        api = self._api
        mode = "url"
        
        if not url: return _err(site, mode, "URL required")
        
        res = None
        context = ""
        last_error = None
        
        # 1. Detect Merchant
        if "/merchant/" in url:
            try:
                parts = [p for p in url.split("/") if p]
                if "merchant" in parts:
                    idx = parts.index("merchant")
                    if idx + 1 < len(parts):
                        slug = parts[idx + 1]
                        res = await api.merchant(fetch, slug, page=int(page), debug=debug)
                        context = "merchant"
            except Exception as e:
                logger.debug(f"Merchant detection failed: {e}", extra={"site": site})

        # 2. Detect Product Card
        if not res and url.endswith(".html") and not "/brands/" in url:
            try:
                slug = url.split("/")[-1].replace(".html", "")
                _res = await api.product_full(fetch, slug, debug=debug)
                if _res.get("ok"):
                    res = _res
                    if debug:
                        meta = res.get("meta", {})
                        _save_debug_item(site, "api_direct_details", meta.get("url", url), meta, res.get("products", []), [])
                    return res
            except Exception as e:
                logger.debug(f"Product Card detection failed: {e}", extra={"site": site})

        # 3. Detect Brand
        if not res and "/brands/" in url:
            context = "merchant"
            try:
                # Strip trailing slash before split to get actual final segment
                slug = url.rstrip("/").split("/")[-1].replace(".html", "").split("?")[0]
                res = await api.brand(fetch, slug, page=int(page), debug=debug)
            except Exception as e:
                logger.debug(f"Brand detection failed: {e}", extra={"site": site})

        # 4. Detect Listing (Category)
        if not res and "/shop/" in url:
            try:
                path = urlparse(url).path
                # Clean path for API: remove locale and .html
                clean_path = path.replace("/ua/", "/").replace(".html", "").strip("/")
                res = await api.listing(fetch, clean_path, page=int(page), debug=debug)
                context = "listing"
            except Exception as e:
                logger.debug(f"Listing detection failed: {e}", extra={"site": site})
            
        # 5. Detect Search
        if not res and "/search" in url:
            try:
                query = parse_qs(urlparse(url).query).get("q", [""])[0]
                if query:
                    res = await api.search(fetch, query, page=int(page), debug=debug)
                    context = "search"
            except Exception as e:
                logger.debug(f"Search detection failed: {e}", extra={"site": site})

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

        # Nuxt Fallback
        logger.info(f"Falling back to SSR extraction for {url}", extra={"site": site})
        code, html, meta = await fetch(site, url, parse_json=False, save_raw=debug)
        if code == 200:
            match = re.search(r"window\.__NUXT__\s*=\s*(.*?);(?!<)", html, re.DOTALL)
            if match:
                # We found SSR state, but we don't have a Nuxt normalizer for Epicentr yet.
                # Returning empty list to prevent crashes, with state in meta for future.
                return _err(site, mode, "Epicentr SSR (window.__NUXT__) found but not yet supported for this URL pattern", 422)

        if last_error:
            return last_error

        return _err(site, mode, "Could not identify URL pattern or find SSR state for Epicentr", 404)
