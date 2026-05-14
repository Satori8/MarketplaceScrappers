import sys
import re

with open(r'd:\Scrappers\marketplace-scraper\scrapers\mapi_scraper\sites\epicentr.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Remove state from EpicentrAPI.__init__
text = text.replace('        self.total_pages = 0\n        self.page_index = 0\n', '')

# 2. Localize pagination in normalizer
def replace_normalize(match):
    body = match.group(0)
    body = body.replace("self.page_index = inner.get('pageIndex', 1)", "page_index = inner.get('pageIndex', 1)")
    body = body.replace("self.total_pages = inner.get('totalPages', 0)", "total_pages = inner.get('totalPages', 0)")
    body = body.replace("not self.total_pages and raw_data.get('total')", "not total_pages and raw_data.get('total')")
    body = body.replace("self.total_pages = (int(raw_data['total']) + 39) // 40", "total_pages = (int(raw_data['total']) + 39) // 40")
    
    body = body.replace("self.page_index = p_data.get('page', 1)", "page_index = p_data.get('page', 1)")
    body = body.replace("self.total_pages = p_data.get('pages', 0)", "total_pages = p_data.get('pages', 0)")
    
    body = body.replace("f\"Extracted 0 products from {context} (page {self.page_index})\"", 'f"Extracted 0 products from {context} (page {page_index})"')
    body = body.replace("f\"Extracted {len(products)} products from {context} (page {self.page_index})\"", 'f"Extracted {len(products)} products from {context} (page {page_index})"')
    
    body = body.replace('"total_pages": self.total_pages,', '"total_pages": total_pages,')
    body = body.replace('"page_index": self.page_index', '"page_index": page_index')
    
    # Insert default assignments at top
    body = body.replace('products = []\n        \n        inner = {}', 'products = []\n        total_pages = 0\n        page_index = 1\n        \n        inner = {}')
    return body

text = re.sub(r'    def normalize\(self, raw_data: Any, context: str\) -> Dict:.*?        \}', replace_normalize, text, flags=re.DOTALL)

# 3. Add API Async Methods
if 'async def async_api_get' not in text:
    async_api_get = """
    async def async_api_get(self, url: str, params: Optional[Dict] = None, debug: bool = False, proxy: str | None = None) -> Tuple[int, Any, Dict]:
        code, data, meta = await _aget_with_meta(self.site, url, params=params, extra_headers=self.headers, parse_json=True, save_raw=debug, proxy=proxy)
        return code, data, meta

    async def async_listing(self, path: str, page: int = 1, debug: bool = False, proxy: str | None = None) -> Dict:
        url = f"{_EPI_API_V2}/product/listing/products"
        params = {"store_id": "2", "query[]": path, "lang": "ua", "page_size": 60, "rankSort": "by_rank"}
        if page > 1: params["page"] = page
        code, data, meta = await self.async_api_get(url, params, debug=debug, proxy=proxy)
        if code == 200: return {"ok": True, "products": data, "meta": meta}
        return {"ok": False, "error": f"HTTP {code}", "code": code, "meta": meta}

    async def async_section_data(self, path: str, debug: bool = False, proxy: str | None = None) -> Dict:
        url = f"{_EPI_API_V2}/product/listing/section-data"
        params = {"store_id": "2", "query[]": path, "lang": "ua"}
        code, data, meta = await self.async_api_get(url, params, debug=debug, proxy=proxy)
        if code == 200:
             out = _ok(self.site, data, "section_data")
             out["meta"] = meta
             return out
        return _err(self.site, "section_data", f"HTTP {code}", code)

    async def async_merchant(self, name: str, page: int = 1, debug: bool = False, proxy: str | None = None) -> Dict:
        url = _EPI_MERCHANT_API
        params = {"lang": "ua", "name": name, "page_size": 60}
        if page > 1: params["page"] = page
        code, data, meta = await self.async_api_get(url, params, debug=debug, proxy=proxy)
        if code == 200: return {"ok": True, "products": data, "meta": meta}
        return {"ok": False, "error": f"HTTP {code}", "code": code, "meta": meta}

    async def async_search(self, find: str, page: int = 1, debug: bool = False, proxy: str | None = None) -> Dict:
        url = f"{_EPI_API_V1}/search"
        params = {"find": find, "store_id": "2", "lang": "ua", "page": page, "search_size": 40}
        code, data, meta = await self.async_api_get(url, params, debug=debug, proxy=proxy)
        if code == 200: return {"ok": True, "products": data, "meta": meta}
        return {"ok": False, "error": f"HTTP {code}", "code": code, "meta": meta}

    async def async_product_full(self, slug: str, debug: bool = False, proxy: str | None = None) -> Dict:
        url = f"{_EPI_API_V1}/product/card/full"
        params = {"store_id": "2", "slug": slug, "lang": "ua"}
        code, data, meta = await self.async_api_get(url, params, debug=debug, proxy=proxy)
        if code == 200: return {"ok": True, "products": data, "meta": meta}
        return {"ok": False, "error": f"HTTP {code}", "code": code, "meta": meta}
"""
    # Insert right before normalize
    text = text.replace('    def normalize(', async_api_get + '\n    def normalize(')


# 4. Clone and Modify Module scrape_url
if 'async def async_scrape_url' not in text:
    scrape_url_code = text.split('    def scrape_url(self, url: str, page: int = 1, debug: bool = False) -> dict:\n')[1]
    async_code = '    async def async_scrape_url(\n        self,\n        url: str,\n        page: int = 1,\n        debug: bool = False,\n        proxy: str | None = None,\n    ) -> dict:\n' + scrape_url_code

    async_code = async_code.replace('_get_with_meta(', 'await _aget_with_meta(')
    async_code = async_code.replace('save_raw=debug)', 'save_raw=debug, proxy=proxy)')
    
    # Replace api calls
    async_code = async_code.replace('api.merchant(', 'await api.async_merchant(')
    async_code = async_code.replace('api.product_full(', 'await api.async_product_full(')
    async_code = async_code.replace('api.listing(', 'await api.async_listing(')
    async_code = async_code.replace('api.search(', 'await api.async_search(')
    
    # Add proxy param
    async_code = async_code.replace('debug=debug)', 'debug=debug, proxy=proxy)')

    text = text + '\n' + async_code

if '_aget_with_meta' not in text:
    text = text.replace('from scrapers.mapi_scraper.http import _get_with_meta,', 'from scrapers.mapi_scraper.http import _get_with_meta, _aget_with_meta,')

with open(r'd:\Scrappers\marketplace-scraper\scrapers\mapi_scraper\sites\epicentr.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("DONE")
