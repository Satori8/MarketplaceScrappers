import re
from typing import Dict

from scrapers.mapi_scraper.base import BaseModule
from scrapers.mapi_scraper.http import _get, _ok, _err, _save_debug_item, logger

class HotlineAPI:
    def __init__(self):
        self.site = "hotline"
        self.total_pages = 0
        self.page_index = 0

    def normalize(self, raw_data: Dict) -> Dict:
        """Extracts products from Hotline search or category HTML/JSON."""
        products = []
        source = raw_data.get("source")
        
        if source == "search_html":
            # This would come from BeautifulSoup parsing of search results
            items = raw_data.get("items", [])
            for it in items:
                products.append({
                    "id": it.get("id"),
                    "sku": it.get("sku"),
                    "name": it.get("name"),
                    "brand": it.get("brand"),
                    "price": it.get("price"),
                    "avail_code": it.get("avail_code"),
                    "merchant_id": None,
                    "merchant_name": it.get("merchant_name"),
                    "category_id": None,
                    "category_name_ua": it.get("category"),
                    "category_name_ru": None,
                    "url": it.get("url"),
                    "image": it.get("image"),
                    "attributes": it.get("attributes") or {},
                    "extra": it.get("extra") or {}
                })
        
        return {
            "products": products,
            "pagination": {
                "total_pages": self.total_pages,
                "page_index": self.page_index
            }
        }


class HotlineModule(BaseModule):
    SITE_ID = "hotline"
    DOMAINS = ["hotline.ua"]
    
    def __init__(self):
        self._api = HotlineAPI()
        
    def scrape_url(self, url: str, page: int = 1, debug: bool = False) -> dict:
        site = self.SITE_ID
        api = self._api
        mode = "url"
        
        if not url: return _err(site, mode, "URL is required")
        
        code, html = _get(site, url)
        if code != 200: return _err(site, mode, f"HTTP {code}", code)
        
        # Hotline parser logic (simplified version of scrapers/hotline.py)
        # Note: For full speed, we avoid BeautifulSoup if regex is enough
        # but for complex HTML, BS4 might be better. 
        # However, fast_scraper aims for zero-dependency where possible, 
        # or minimal logic.
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        
        products = []
        # Check if it's a list (search/category) or product detail
        if "/sr/" in url or "/shop/" in url:
            # Listing page
            cards = soup.select(".product-item, .list-item")
            for card in cards:
                title_node = card.select_one(".item-info a[href], .link--black")
                price_node = card.select_one(".price__value")
                if title_node and price_node:
                    title = title_node.get_text(strip=True)
                    href = title_node.get('href')
                    price_str = price_node.get_text(strip=True).replace("\xa0", "").replace(" ", "")
                    price = re.search(r"(\d+)", price_str)
                    
                    products.append({
                        "name": title,
                        "url": "https://hotline.ua" + href if href.startswith("/") else href,
                        "price": price.group(1) if price else None,
                        "avail_code": 1,
                        "attributes": {},
                        "extra": {}
                    })
            
            normalized = api.normalize({"source": "search_html", "items": products})
            out = _ok(site, normalized["products"], mode)
            out["pagination"] = normalized.get("pagination")
            return out

        return _err(site, mode, "Unsupported Hotline URL pattern", 400)
