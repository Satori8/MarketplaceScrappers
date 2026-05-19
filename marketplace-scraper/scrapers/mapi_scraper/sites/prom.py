import re
import asyncio
from typing import Dict, Tuple, Optional
from typing import Dict, Tuple, Optional, List
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from scrapers.mapi_scraper.base import BaseModule
from scrapers.mapi_scraper.http import (
    _get_with_meta, _aget_with_meta, _ok, _err, _save_debug_item, logger, 
    _PROM_HEADERS, _make_sync_fetcher, _make_async_fetcher, 
    _make_sync_poster, _make_async_poster
)
from scrapers.mapi_scraper.extractors import _extract_json_assignment, _extract_ld_json, _map_ld_json_offer

class PromAPI:
    def __init__(self):
        self.site = "prom"

    _GRAPHQL_QUERIES = {
        "CategoryListingQuery": """query CategoryListingQuery($alias: String!, $params: Any, $offset: Int, $limit: Int, $regionId: Int, $subdomain: String) {
          listing: categoryListing(alias: $alias, params: $params, offset: $offset, limit: $limit, region: {id: $regionId, subdomain: $subdomain}) {
            category { id caption __typename }
            page { total products { product { id name: nameForCatalog sku price discountedPrice priceCurrency priceCurrencyLocalized urlText categoryId categoryIds image(width: 200, height: 200) presence { presence isAvailable __typename } company { id name slug opinionStats { opinionPositivePercent opinionTotal __typename } __typename } category { id caption __typename } manufacturerInfo { id name __typename } catalogPresence { title __typename } __typename } __typename } __typename } __typename } }""",
        "SearchListingQuery": """query SearchListingQuery($search_term: String!, $params: Any, $offset: Int, $limit: Int, $regionId: Int, $subdomain: String) {
          listing: searchListing(search_term: $search_term, params: $params, offset: $offset, limit: $limit, region: {id: $regionId, subdomain: $subdomain}) {
            page { total products { product { id name: nameForCatalog sku price discountedPrice priceCurrency priceCurrencyLocalized urlText categoryId categoryIds image(width: 200, height: 200) presence { presence isAvailable __typename } company { id name slug opinionStats { opinionPositivePercent opinionTotal __typename } __typename } category { id caption __typename } manufacturerInfo { id name __typename } catalogPresence { title __typename } __typename } __typename } __typename } __typename } }""",
        "CompanyListingQuery": """query CompanyListingQuery($company_id: Int!, $params: Any, $offset: Int, $limit: Int, $regionId: Int, $subdomain: String) {
          listing: companyListing(company_id: $company_id, params: $params, offset: $offset, limit: $limit, region: {id: $regionId, subdomain: $subdomain}) {
            page { total products { product { id name: nameForCatalog sku price discountedPrice priceCurrency priceCurrencyLocalized urlText categoryId categoryIds image(width: 200, height: 200) presence { presence isAvailable __typename } company { id name slug opinionStats { opinionPositivePercent opinionTotal __typename } __typename } category { id caption __typename } manufacturerInfo { id name __typename } catalogPresence { title __typename } __typename } __typename } __typename } __typename } }""",
        "ManufacturerListingQuery": """query ManufacturerListingQuery($alias: String!, $params: Any, $offset: Int, $limit: Int, $regionId: Int, $subdomain: String) {
          listing: manufacturerListing(alias: $alias, params: $params, offset: $offset, limit: $limit, region: {id: $regionId, subdomain: $subdomain}) {
            page { total products { product { id name: nameForCatalog sku price discountedPrice priceCurrency priceCurrencyLocalized urlText categoryId categoryIds image(width: 200, height: 200) presence { presence isAvailable __typename } company { id name slug opinionStats { opinionPositivePercent opinionTotal __typename } __typename } category { id caption __typename } manufacturerInfo { id name __typename } catalogPresence { title __typename } __typename } __typename } __typename } __typename } }"""
    }

    def parse_url_to_graphql(self, url: str, page: int = 1) -> Optional[Tuple[str, Dict]]:
        """Parses Prom.ua URL to GraphQL operation and variables."""
        try:
            parsed = urlparse(url)
            path = parsed.path
            if parsed.params:
                path += ';' + parsed.params
            
            query = parse_qs(parsed.query)
            
            params = {"binary_filters": []}
            for key, values in query.items():
                if key in ("search_term", "page"): continue
                params[key] = values[0] if len(values) == 1 else values
            
            limit = 29
            offset = (page - 1) * limit
            
            path_lower = path.lower()
            if path_lower.startswith("/ua/search") or path_lower.startswith("/search"):
                search_term = query.get("search_term", [""])[0]
                return "SearchListingQuery", {
                    "search_term": search_term, "regionId": None, "params": params, "limit": limit, "offset": offset
                }
            elif "/c" in path_lower and "-" in path and path.endswith(".html"):
                c_index = path_lower.find("/c") + 2
                dash_index = path.find("-", c_index)
                company_id = int(path[c_index:dash_index])
                params["company_id"] = str(company_id)
                params["company_name"] = path[dash_index+1:].split(";")[0].replace(".html", "")
                return "CompanyListingQuery", {
                    "company_id": company_id, "regionId": None, "params": params, "limit": limit, "offset": offset
                }
            elif "/brands/" in path_lower:
                alias = path.split("/brands/")[-1] if "/brands/" in path else path.split("/Brands/")[-1]
                alias = alias.split("?")[0].split(";")[0]
                return "ManufacturerListingQuery", {
                    "alias": alias, "regionId": None, "params": params, "limit": limit, "offset": offset
                }
            else:
                alias = path.split("/")[-1].split(";")[0]
                return "CategoryListingQuery", {
                    "alias": alias, "regionId": None, "params": params, "limit": limit, "offset": offset
                }
        except:
            return None

    def normalize(self, raw_data: Dict) -> Dict:
        """Extracts products from Apollo state or LD+JSON."""
        products = []
        source = raw_data.get("source")
        total_pages = 0
        page_index = 1
        
        if source == "window.ApolloCacheState":
            state = raw_data.get("apollo_state", {})
            cache = state.get("_FAST_CACHE", state)
            
            listing_key = next((k for k in cache.keys() if "ListingQuery" in k or "SearchQuery" in k or "CompanyListing" in k), None)
            listing_data = cache.get(listing_key, {}) if listing_key else {}
            
            res = listing_data.get("result", {})
            listing = res.get("listing", {})
            page_info = listing.get("page", {})
            if not page_info:
                 page_info = res.get("page", {})

            total_items = page_info.get("total", 0)
            total_pages = (total_items // 29) + (1 if total_items % 29 > 0 else 0)
            
            try:
                offset_match = re.search(r'"offset":(\d+)', str(listing_key))
                if offset_match:
                    offset = int(offset_match.group(1))
                    page_index = (offset // 29) + 1
            except:
                page_index = 1

            listing = res.get("listing") or {}
            listing_page = listing.get("page") or {}
            category_path = (listing_page.get("topHitsCategory") or {}).get("path", [])
            
            if not category_path:
                seo_key = next((k for k in cache.keys() if "SeoNavigationQuery" in k), None)
                if seo_key:
                    seo_res = cache.get(seo_key, {}).get("result", {})
                    category_path = (seo_res.get("category") or {}).get("path", [])
                    if not category_path:
                         cat_obj = seo_res.get("category")
                         if cat_obj and cat_obj.get("caption"):
                             category_path = [cat_obj]

            if not category_path:
                category_path = (res.get("category") or {}).get("path", [])

            raw_items = listing.get("products") or []
            if not raw_items:
                raw_items = listing_page.get("products") or []
            if not raw_items:
                raw_items = res.get("products") or []
            if not raw_items:
                raw_items = [{"__ref": k} for k in state.keys() if k.startswith("ProductItem:")]

            for ref in raw_items:
                if not isinstance(ref, dict): continue
                ref_id = ref.get("__ref")
                item = state.get(ref_id) if ref_id else ref
                if not item: continue
                
                p_ref = item.get("product")
                if p_ref:
                    p = state.get(p_ref.get("__ref")) if isinstance(p_ref, dict) and p_ref.get("__ref") else p_ref
                else:
                    p = item
                
                if not p or not isinstance(p, dict): continue
                
                c_ref = p.get("company") or {}
                c = state.get(c_ref.get("__ref")) if isinstance(c_ref, dict) and c_ref.get("__ref") else c_ref
                
                cat_ref = p.get("category") or {}
                cat = state.get(cat_ref.get("__ref")) if isinstance(cat_ref, dict) and cat_ref.get("__ref") else cat_ref
                
                m_ref = p.get("manufacturerInfo") or {}
                m = state.get(m_ref.get("__ref")) if isinstance(m_ref, dict) and m_ref.get("__ref") else m_ref

                p_cat_id_str = str(p.get("categoryId") or "")
                best_cat_name = None
                max_match_len = -1
                
                for path_node in category_path:
                    node_id_str = str(path_node.get("id", ""))
                    if not node_id_str or node_id_str == "0": continue
                    if p_cat_id_str.startswith(node_id_str):
                        match_len = len(node_id_str)
                        if match_len > max_match_len:
                            max_match_len = match_len
                            best_cat_name = path_node.get("caption")

                if not best_cat_name:
                    for attr_filter in (listing_page.get("quickFilters") or []):
                        if attr_filter.get("name") == "category":
                            for val in (attr_filter.get("values") or []):
                                if str(val.get("value")) == p_cat_id_str:
                                    best_cat_name = val.get("title")
                                    break
                        if best_cat_name: break

                p_id = p.get("id")
                p_slug = p.get("urlText")
                p_url = f"https://prom.ua/ua/p{p_id}-{p_slug}.html" if p_id and p_slug else None
                
                c_id = c.get("id") if isinstance(c, dict) else p.get("company_id")
                c_slug = c.get("slug") if isinstance(c, dict) else ((p.get("company") or {}).get("slug") if isinstance(p.get("company"), dict) else None)
                merchant_url = f"https://prom.ua/ua/c{c_id}-{c_slug}.html" if c_id and c_slug else None

                products.append({
                    "id": p_id,
                    "sku": p.get("sku"),
                    "name": p.get("name"),
                    "brand": m.get("name") if isinstance(m, dict) else None,
                    "price": p.get("discountedPrice") or p.get("price") or p.get("priceOriginal"),
                    "avail_code": 1 if ((p.get("presence") or {}).get("isAvailable") if isinstance(p.get("presence"), dict) else False) else 0,
                    "merchant_id": c_id,
                    "merchant_name": c.get("name") if isinstance(c, dict) else ((p.get("company") or {}).get("name") if isinstance(p.get("company"), dict) else None),
                    "merchant_url": merchant_url,
                    "category_id": cat.get("id") if isinstance(cat, dict) else p.get("categoryId"),
                    "category_name_ua": best_cat_name,
                    "category_name_ru": None,
                    "url": p_url,
                    "image": p.get("image"),
                    "attributes": {c.get("name"): c.get("value") for c in p.get("characteristics", []) if c.get("name") and c.get("value")} if isinstance(p.get("characteristics"), list) else {},
                    "extra": {"orders_count": p.get("ordersCount") or p.get("orders_count") or 0}
                })

        elif source == "graphql":
            data = raw_data.get("data", {})
            listing = data.get("listing") or {}
            page_info = listing.get("page") or {}
            total_items = page_info.get("total", 0)
            total_pages = (total_items // 29) + (1 if total_items % 29 > 0 else 0)
            page_index = raw_data.get("page_index", 1)
            
            # Listing-level context fallback
            listing_cat_name = (listing.get("category") or {}).get("caption")

            for item in page_info.get("products", []):
                p = item.get("product")
                if not p: continue
                c = p.get("company") or {}
                p_id = p.get("id")
                p_slug = p.get("urlText")
                c_id = c.get("id")
                c_slug = c.get("slug")
                
                # Enhanced category name resolution
                # 1. Direct from product.category
                # 2. Fallback to listing-level category
                best_cat_name = (p.get("category") or {}).get("caption") or listing_cat_name
                
                # Standardized availability strings
                presence = p.get("presence") or {}
                is_available = presence.get("isAvailable")
                avail_str = "В наявності" if is_available else "Немає в наявності"
                
                products.append({
                    "id": str(p.get("id")),
                    "sku": p.get("sku"),
                    "name": p.get("name"),
                    "brand": (p.get("manufacturerInfo") or {}).get("name"),
                    "price": p.get("discountedPrice") or p.get("price"),
                    "avail_code": avail_str,
                    "merchant_id": str(p.get("company_id") or ""),
                    "merchant_name": c.get("name"),
                    "merchant_url": f"https://prom.ua/ua/c{c_id}-{c_slug}.html" if c_id and c_slug else None,
                    "category_id": p.get("categoryId") or (p.get("categoryIds") or [None])[0],
                    "category_name_ua": best_cat_name,
                    "category_name_ru": None,
                    "url": f"https://prom.ua/ua/p{p_id}-{p_slug}.html" if p_id and p_slug else None,
                    "image": p.get("image"),
                    "attributes": {c.get("name"): c.get("value") for c in p.get("characteristics", []) if c.get("name") and c.get("value")} if isinstance(p.get("characteristics"), list) else {},
                    "extra": {"orders_count": p.get("ordersCount") or p.get("orders_count") or 0}
                })

        elif source == "ld+json":
            items = raw_data.get("ld_json_products", [])
            for it in items:
                products.append(_map_ld_json_offer(it))

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


class PromModule(BaseModule):
    SITE_ID = "prom"
    DOMAINS = ["prom.ua"]
    
    def __init__(self):
        self._api = PromAPI()
        
    def scrape_url(self, url: str, page: int = 1, debug: bool = False) -> dict:
        fetch = _make_sync_fetcher()
        post = _make_sync_poster()
        try:
            return asyncio.run(self._scrape_impl(url, page, debug, fetch, post))
        except RuntimeError as e:
            logger.warning(f"RuntimeError in sync scrape_url: {e}.", extra={"site": self.SITE_ID})
            raise

    async def async_scrape_url(self, url: str, page: int = 1, debug: bool = False, proxy: str | None = None) -> dict:
        fetch = _make_async_fetcher(proxy=proxy)
        post = _make_async_poster(proxy=proxy)
        return await self._scrape_impl(url, page, debug, fetch, post)

    async def _scrape_impl(self, url: str, page: int, debug: bool, fetch, post) -> dict:
        site = self.SITE_ID
        api = self._api
        mode = "url"
        if not url: return _err(site, mode, "URL is required")

        # 1. Try GraphQL
        parsed_gql = api.parse_url_to_graphql(url, page=int(page))
        if parsed_gql:
            op_name, variables = parsed_gql
            query = api._GRAPHQL_QUERIES.get(op_name)
            if query:
                headers = {
                    "content-type": "application/json",
                    "x-language": "uk", 
                    "x-requested-with": "XMLHttpRequest",
                    "x-apollo-operation-name": op_name,
                    "referer": url,
                    "origin": "https://prom.ua"
                }
                payload = {"operationName": op_name, "variables": variables, "query": query}
                logger.info(f"FETCH GraphQL {op_name} for {url}", extra={"site": site})
                try:
                    resp, elapsed_ms = await post("https://prom.ua/graphql", headers=headers, json=payload)
                    if resp.status_code == 200:
                        gql_data = resp.json()
                        if "data" in gql_data and gql_data["data"]:
                            raw = {"source": "graphql", "data": gql_data["data"], "page_index": int(page)}
                            normalized_data = api.normalize(raw)
                            if debug:
                                meta = {"url": "https://prom.ua/graphql", "status": 200, "elapsed_ms": elapsed_ms, "bytes": len(resp.content)}
                                _save_debug_item(site, "graphql_api", url, meta, gql_data, normalized_data.get("products", []))
                            if normalized_data and normalized_data.get("products"):
                                out = _ok(site, normalized_data["products"], mode)
                                if "pagination" in normalized_data:
                                    out["pagination"] = normalized_data["pagination"]
                                if debug: out["debug"] = True
                                return out
                except Exception as e:
                    logger.warning(f"GraphQL extraction failed: {e}", extra={"site": site})

        # 2. Fallback: HTML extraction
        paginated_url = self._inject_page(url, page)
        logger.info(f"Falling back to HTML extraction for {paginated_url}", extra={"site": site})
        code, html, meta = await fetch(site, paginated_url, extra_headers=_PROM_HEADERS, parse_json=False, save_raw=debug)
        normalized_data = None
        apollo = None
        try:
            apollo = _extract_json_assignment(html, "window.ApolloCacheState")
        except Exception as e:
            logger.debug(f"Apollo extraction failed: {e}", extra={"site": site})

        if apollo:
            raw = {"source": "window.ApolloCacheState", "apollo_state": apollo}
            normalized_data = api.normalize(raw)
        else:
            ld_blocks = _extract_ld_json(html)
            products = [b for b in ld_blocks if b.get("@type") == "Product"]
            if products:
                raw = {"source": "ld+json", "ld_json_products": products}
                normalized_data = api.normalize(raw)

        if debug:
            products = normalized_data.get("products", []) if normalized_data else []
            debug_raw = {"apollo_state": apollo} if apollo else {"html_snippet": html[:5000]}
            _save_debug_item(site, "html_extraction", meta["url"], meta, debug_raw, products)

        if normalized_data is not None:
             out = _ok(site, normalized_data.get("products", []), mode)
             if "pagination" in normalized_data:
                 out["pagination"] = normalized_data["pagination"]
             if debug: out["debug"] = True
             return out

        out = _err(site, mode, "Could not find Apollo state or LD+JSON on Prom", 404)
        if debug: out["debug"] = True
        return out

    def _inject_page(self, url: str, page: int) -> str:
        if page <= 1:
            return url
            
        parsed = urlparse(url)
        if "/search" in parsed.path:
            qs = parse_qs(parsed.query)
            qs["page"] = [str(page)]
            new_query = urlencode(qs, doseq=True)
            return urlunparse(parsed._replace(query=new_query))
            
        # Category/Shop: append ;{N} before .html or at end of path
        path = parsed.path
        if ".html" in path:
            path = re.sub(r';\d+(\.html)$', r'\1', path) # strip existing
            path = path.replace(".html", f";{page}.html")
        else:
            path = re.sub(r';\d+/?$', '', path) # strip existing
            path = path.rstrip("/") + f";{page}"
        
        return urlunparse(parsed._replace(path=path))
