import time
import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from . import scrape
@dataclass
class PaginationResult:
    site: str
    url: str
    pages_fetched: int
    total_pages_reported: int
    products: List[Dict] = field(default_factory=list)
    log: List[Dict] = field(default_factory=list) # Note: With in-place file logging, this might not track per-request logs but rather per page summaries
    errors: List[str] = field(default_factory=list)

class Paginator:
    def __init__(self, delay: float = 2.0):
        self.delay = delay

    def _inject_page_rozetka(self, url: str, page: int) -> str:
        if page <= 1:
            return url
            
        parsed = urlparse(url)
        # Search / Seller uses query param `page`
        if "/search/" in parsed.path or "/seller/" in parsed.path:
            qs = parse_qs(parsed.query)
            qs["page"] = [str(page)]
            new_query = urlencode(qs, doseq=True)
            return urlunparse(parsed._replace(query=new_query))
            
        # Category: auto.rozetka.com.ua/.../c4654538/ -> .../c4654538/page=3/
        match = re.search(r'(/c\d+/)(.*)', parsed.path)
        if match:
            prefix = match.group(1)
            suffix = match.group(2)
            
            # remove existing page=N from suffix if any, handle both ; and / separators
            suffix = re.sub(r'page=\d+[;/]?', '', suffix)
            
            if suffix and suffix != "/":
                # If we have filters, inject page=N; at the start of suffix
                new_path = f"{parsed.path[:match.start(1)]}{prefix}page={page};{suffix.lstrip('/')}"
            else:
                # If no filters, just page=N/
                new_path = f"{parsed.path[:match.start(1)]}{prefix}page={page}/"
                
            return urlunparse(parsed._replace(path=new_path))

        return url

    def _inject_page_prom(self, url: str, page: int) -> str:
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

    def _inject_page_epicentr(self, url: str, page: int) -> str:
        if page <= 1:
            return url
            
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        qs["PAGEN_1"] = [str(page)]
        new_query = urlencode(qs, doseq=True)
        return urlunparse(parsed._replace(query=new_query))

    def _inject_page_allo(self, url: str, page: int) -> str:
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

    def _get_paginated_url(self, site: str, url: str, page: int) -> str:
        if site == "rozetka": return self._inject_page_rozetka(url, page)
        if site == "prom": return self._inject_page_prom(url, page)
        if site == "epicentr": return self._inject_page_epicentr(url, page)
        if site == "allo": return self._inject_page_allo(url, page)
        return url

    def paginate(self, site: str, url: str, max_pages: Optional[int] = None, debug: bool = False) -> PaginationResult:
        result = PaginationResult(site=site, url=url, pages_fetched=0, total_pages_reported=0)
        seen_ids = set()
        
        page = 1
        while True:
            target_url = self._get_paginated_url(site, url, page)
            
            try:
                res = scrape(site, "url", url=target_url, debug=debug, page=page)
            except Exception as e:
                result.errors.append(f"Exception on page {page}: {str(e)}")
                break
                
            if not res.get("ok"):
                result.errors.append(res.get("error", "Unknown error"))
                break
            
            products = res.get("products", [])
            if isinstance(products, dict):
                products = []
            
            new_products_found = 0
            
            for p in products:
                if not isinstance(p, dict):
                     # edge case: skip strings
                     continue
                pid = p.get("id")
                if pid is not None:
                    if pid not in seen_ids:
                        seen_ids.add(pid)
                        result.products.append(p)
                        new_products_found += 1
                else:
                    result.products.append(p)
                    new_products_found += 1
                    
            result.pages_fetched += 1
            
            pagination = res.get("pagination")
            if pagination:
                reported_total = pagination.get("total_pages", 0)
                if reported_total > result.total_pages_reported:
                     result.total_pages_reported = reported_total
            
            result.log.append({
                "page": page,
                "url": target_url,
                "products_found": len(products),
                "new_products": new_products_found,
            })
            
            # Stop conditions
            if len(products) == 0:
                break
            if max_pages is not None and page >= max_pages:
                break
            # If total_pages_reported is 0 or None, treat as 1 and stop
            if result.total_pages_reported <= 0 or page >= result.total_pages_reported:
                break
                
            page += 1
            time.sleep(self.delay)

        # If reported total was 0, assume we just fetched 1
        if result.total_pages_reported == 0 and result.pages_fetched > 0:
             result.total_pages_reported = 1
             
        return result
