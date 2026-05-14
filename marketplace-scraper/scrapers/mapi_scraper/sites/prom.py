import re
import time
from typing import Dict, Tuple, Optional
from curl_cffi import requests

from scrapers.mapi_scraper.base import BaseModule
from scrapers.mapi_scraper.http import _get_with_meta, _ok, _err, _save_debug_item, logger, _PROM_HEADERS
from scrapers.mapi_scraper.extractors import _extract_json_assignment, _extract_ld_json

class PromAPI:
    def __init__(self):
        self.site = "prom"
        self.total_pages = 0
        self.page_index = 0

    _GRAPHQL_QUERIES = {
        "CategoryListingQuery": """query CategoryListingQuery($alias: String!, $params: Any, $offset: Int, $limit: Int, $regionId: Int, $subdomain: String) {
          listing: categoryListing(alias: $alias, params: $params, offset: $offset, limit: $limit, region: {id: $regionId, subdomain: $subdomain}) {
            category { id alias caption url numProducts __typename }
            page { total products { product { id name: nameForCatalog price priceCurrencyLocalized urlText categoryIds image(width: 200, height: 200) presence { presence isAvailable __typename } company { id name slug __typename } __typename } __typename } __typename } __typename } }""",
        "SearchListingQuery": """query SearchListingQuery($search_term: String!, $params: Any, $offset: Int, $limit: Int, $regionId: Int, $subdomain: String) {
          listing: searchListing(search_term: $search_term, params: $params, offset: $offset, limit: $limit, region: {id: $regionId, subdomain: $subdomain}) {
            page { total products { product { id name: nameForCatalog price priceCurrencyLocalized urlText categoryIds image(width: 200, height: 200) presence { presence isAvailable __typename } company { id name slug __typename } __typename } __typename } __typename } __typename } }""",
        "CompanyListingQuery": """query CompanyListingQuery($company_id: Int!, $params: Any, $offset: Int, $limit: Int, $regionId: Int, $subdomain: String) {
          listing: companyListing(company_id: $company_id, params: $params, offset: $offset, limit: $limit, region: {id: $regionId, subdomain: $subdomain}) {
            page { total products { product { id name: nameForCatalog price priceCurrencyLocalized urlText categoryIds image(width: 200, height: 200) presence { presence isAvailable __typename } company { id name slug __typename } __typename } __typename } __typename } __typename } }""",
        "ManufacturerListingQuery": """query ManufacturerListingQuery($alias: String!, $params: Any, $offset: Int, $limit: Int, $regionId: Int, $subdomain: String) {
          listing: manufacturerListing(alias: $alias, params: $params, offset: $offset, limit: $limit, region: {id: $regionId, subdomain: $subdomain}) {
            page { total products { product { id name: nameForCatalog price priceCurrencyLocalized urlText categoryIds image(width: 200, height: 200) presence { presence isAvailable __typename } company { id name slug __typename } __typename } __typename } __typename } __typename } }"""
    }

    def parse_url_to_graphql(self, url: str, page: int = 1) -> Optional[Tuple[str, Dict]]:
        """Parses Prom.ua URL to GraphQL operation and variables."""
        try:
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(url)
            # Combine path and params because Prom uses ';' for pagination (e.g. ;2.html)
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
        
        if source == "window.ApolloCacheState":
            state = raw_data.get("apollo_state", {})
            
            # Prom sometimes wraps state in _FAST_CACHE
            cache = state.get("_FAST_CACHE", state)
            
            # 1. Find the listing query result
            listing_key = next((k for k in cache.keys() if "ListingQuery" in k or "SearchQuery" in k or "CompanyListing" in k), None)
            listing_data = cache.get(listing_key, {}) if listing_key else {}
            
            # 2. Extract pagination
            res = listing_data.get("result", {})
            listing = res.get("listing", {})
            page_info = listing.get("page", {})
            if not page_info: # fallback for some company pages
                 page_info = res.get("page", {})

            total_items = page_info.get("total", 0)
            self.total_pages = (total_items // 29) + (1 if total_items % 29 > 0 else 0)
            
            try:
                offset_match = re.search(r'"offset":(\d+)', str(listing_key))
                if offset_match:
                    offset = int(offset_match.group(1))
                    self.page_index = (offset // 29) + 1
            except:
                self.page_index = 1

            listing = res.get("listing")
            if not listing:
                listing = {}

            # 2. Get top hits category for names (path-based)
            listing_page = listing.get("page") or {}
            category_path = (listing_page.get("topHitsCategory") or {}).get("path", [])
            
            # Fallback 1: SeoNavigationQuery often contains the full category path
            if not category_path:
                seo_key = next((k for k in cache.keys() if "SeoNavigationQuery" in k), None)
                if seo_key:
                    seo_res = cache.get(seo_key, {}).get("result", {})
                    category_path = (seo_res.get("category") or {}).get("path", [])
                    if not category_path:
                         # Sometimes it's just a single category object
                         cat_obj = seo_res.get("category")
                         if cat_obj and cat_obj.get("caption"):
                             category_path = [cat_obj]

            if not category_path:
                # Some other listings might have category path elsewhere or result.category
                category_path = (res.get("category") or {}).get("path", [])

            # 3. Resolve products
            raw_items = listing.get("products") or []
            if not raw_items:
                raw_items = (listing.get("page") or {}).get("products") or []
            if not raw_items:
                # Fallback: maybe it's search or different structure
                raw_items = res.get("products") or []
            
            if not raw_items:
                # Last resort: search all ProductItem keys in the FLAT state
                raw_items = [{"__ref": k} for k in state.keys() if k.startswith("ProductItem:")]

            for ref in raw_items:
                if not isinstance(ref, dict): continue
                # Handle both direct objects and references
                ref_id = ref.get("__ref")
                item = state.get(ref_id) if ref_id else ref
                if not item: continue
                
                # In some cases, 'item' is already the Product object (if it didn't have __typename: ProductItem)
                # But usually it's a ProductItem with a 'product' field
                p_ref = item.get("product")
                if p_ref:
                    p = state.get(p_ref.get("__ref")) if isinstance(p_ref, dict) and p_ref.get("__ref") else p_ref
                else:
                    # Maybe 'item' is the product itself
                    p = item
                
                if not p or not isinstance(p, dict): continue
                
                # De-reference company
                c_ref = p.get("company") or {}
                c = state.get(c_ref.get("__ref")) if isinstance(c_ref, dict) and c_ref.get("__ref") else c_ref
                
                # De-reference category
                cat_ref = p.get("category") or {}
                cat = state.get(cat_ref.get("__ref")) if isinstance(cat_ref, dict) and cat_ref.get("__ref") else cat_ref
                
                # De-reference manufacturer
                m_ref = p.get("manufacturerInfo") or {}
                m = state.get(m_ref.get("__ref")) if isinstance(m_ref, dict) and m_ref.get("__ref") else m_ref

                # Extract category name using "best match" logic
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

                # 4. Resolve category name from quickFilters as a secondary fallback
                if not best_cat_name:
                    # Search in quickFilters if available
                    listing_page = listing.get("page") or {}
                    for attr_filter in (listing_page.get("quickFilters") or []):
                        if attr_filter.get("name") == "category":
                            for val in (attr_filter.get("values") or []):
                                if str(val.get("value")) == p_cat_id_str:
                                    best_cat_name = val.get("title")
                                    break
                        if best_cat_name: break

                # URL Formats
                # Product: https://prom.ua/ua/p{id}-{slug}.html
                p_id = p.get("id")
                p_slug = p.get("urlText")
                p_url = f"https://prom.ua/ua/p{p_id}-{p_slug}.html" if p_id and p_slug else None
                
                # Company URL: https://prom.ua/ua/c{id}-{slug}.html
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
                    "properties": [],
                    "url": p_url,
                    "image": p.get("image")
                })

        elif source == "graphql":
            data = raw_data.get("data", {})
            listing = data.get("listing", {})
            page_info = listing.get("page", {})
            
            total_items = page_info.get("total", 0)
            self.total_pages = (total_items // 29) + (1 if total_items % 29 > 0 else 0)
            self.page_index = raw_data.get("page_index", 1)
            
            best_cat_name = (listing.get("category") or {}).get("caption")

            for item in page_info.get("products", []):
                p = item.get("product")
                if not p: continue
                
                c = p.get("company") or {}
                p_id = p.get("id")
                p_slug = p.get("urlText")
                c_id = c.get("id")
                c_slug = c.get("slug")
                
                products.append({
                    "id": p_id,
                    "sku": p.get("sku"),
                    "name": p.get("name"),
                    "brand": None,
                    "price": p.get("price"),
                    "avail_code": 1 if (p.get("presence") or {}).get("isAvailable") else 0,
                    "merchant_id": c_id,
                    "merchant_name": c.get("name"),
                    "merchant_url": f"https://prom.ua/ua/c{c_id}-{c_slug}.html" if c_id and c_slug else None,
                    "category_id": (p.get("categoryIds") or [None])[0],
                    "category_name_ua": best_cat_name,
                    "category_name_ru": None,
                    "properties": [],
                    "url": f"https://prom.ua/ua/p{p_id}-{p_slug}.html" if p_id and p_slug else None,
                    "image": p.get("image")
                })

        elif source == "ld+json":
            # Handle LD+JSON Product blocks (fallback)
            items = raw_data.get("ld_json_products", [])
            for it in items:
                products.append({
                    "id": it.get("sku") or it.get("identifier"),
                    "sku": it.get("sku"),
                    "name": it.get("name"),
                    "brand": it.get("brand", {}).get("name") if isinstance(it.get("brand"), dict) else it.get("brand"),
                    "price": it.get("offers", {}).get("price") if isinstance(it.get("offers"), dict) else None,
                    "avail_code": 1 if "InStock" in str(it.get("offers", {}).get("availability")) else 0,
                    "merchant_id": None,
                    "merchant_name": it.get("offers", {}).get("seller", {}).get("name") if isinstance(it.get("offers"), dict) else None,
                    "category_id": None,
                    "category_name_ua": None,
                    "category_name_ru": None,
                    "properties": [],
                    "url": it.get("url"),
                    "image": it.get("image")
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


class PromModule(BaseModule):
    SITE_ID = "prom"
    DOMAINS = ["prom.ua"]
    
    def __init__(self):
        self._api = PromAPI()
        
    def scrape_url(self, url: str, page: int = 1, debug: bool = False) -> dict:
        site = self.SITE_ID
        api = self._api
        mode = "url"
        
        if not url: return _err(site, mode, "URL is required")

        # 1. Primary: Try GraphQL directly
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
                
                started = time.perf_counter()
                logger.info(f"FETCH GraphQL {op_name} for {url} (vars: {variables})", extra={"site": site})
                try:
                    resp = requests.post("https://prom.ua/graphql", headers=headers, json=payload, impersonate="chrome124", timeout=15)
                    elapsed_ms = int((time.perf_counter() - started) * 1000)
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
                                if debug: out["debug"] = True # Can be expanded to actual debug dict
                                return out
                except Exception as e:
                    logger.warning(f"GraphQL extraction failed: {e}", extra={"site": site})
                    pass

        # 2. Fallback: HTML extraction (Apollo Cache)
        logger.info(f"Falling back to HTML extraction for {url}", extra={"site": site})
        code, html, meta = _get_with_meta(site, url, extra_headers=_PROM_HEADERS, parse_json=False, save_raw=debug)
        
        normalized_data = None
        
        # Prom uses Apollo Cache in window.ApolloCacheState
        apollo = _extract_json_assignment(html, "window.ApolloCacheState")
        if apollo:
            raw = {"source": "window.ApolloCacheState", "apollo_state": apollo}
            normalized_data = api.normalize(raw)
        else:
            # Fallback: LD+JSON Product blocks
            ld_blocks = _extract_ld_json(html)
            products = [b for b in ld_blocks if b.get("@type") == "Product"]
            if products:
                raw = {"source": "ld+json", "ld_json_products": products}
                normalized_data = api.normalize(raw)

        if debug:
            products = normalized_data.get("products", []) if normalized_data else []
            # We already have raw data from extractors
            debug_raw = {"apollo_state": apollo} if 'apollo' in locals() and apollo else {"html_snippet": html[:5000]}
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
