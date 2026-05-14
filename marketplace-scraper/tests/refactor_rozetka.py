import os

file_path = r"d:\Scrappers\marketplace-scraper\scrapers\mapi_scraper\sites\rozetka.py"

with open(file_path, "r", encoding="utf-8") as f:
    text = f.read()

# 1. Remove state from RozetkaAPI.__init__
text = text.replace("""    def __init__(self):
        self.site = "rozetka"
        self.total_pages = 0
        self.page_index = 0""", """    def __init__(self):
        self.site = "rozetka\"""")

# 2. Add local pagination variables to normalize()
text = text.replace("""    def normalize(self, raw_data: Dict) -> Dict:
        \"\"\"Standardizes Rozetka responses from LD+JSON or JS state.\"\"\"
        products = []
        source = raw_data.get("source")""", """    def normalize(self, raw_data: Dict) -> Dict:
        \"\"\"Standardizes Rozetka responses from LD+JSON or JS state.\"\"\"
        products = []
        source = raw_data.get("source")
        total_pages = 0
        page_index = 1""")

# 3. Extract pagination in the API source block of normalize()
text = text.replace("""        elif source in ["rz-client-state", "api_direct_search", "api_direct_category", "api_direct_details"]:
            # API data structure can be a list or a dict containing a list
            api_data = raw_data.get("api_data", {})
            if isinstance(api_data, dict):
                # Standard wrapper
                data_val = api_data.get("data", {})""", """        elif source in ["rz-client-state", "api_direct_search", "api_direct_category", "api_direct_details"]:
            # API data structure can be a list or a dict containing a list
            api_data = raw_data.get("api_data", {})
            if isinstance(api_data, dict):
                # Standard wrapper
                data_val = api_data.get("data", {})
                
                # Fetch pagination
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
                    page_index = data_val["goods"].get("shown_page", page_index)\""")

# 4. Update the return block of normalize() to not use self.total_pages
text = text.replace("""        if not products and self.total_pages > 0:
            logger.warning(f"Extracted 0 products from {source}, but total_pages={self.total_pages}", extra={"site": self.site})
        else:
            logger.info(f"Extracted {len(products)} products from {source}", extra={"site": self.site})

        return {
            "products": products,
            "pagination": {
                "total_pages": self.total_pages,
                "page_index": self.page_index
            }
        }""", """        if not products and total_pages > 0:
            logger.warning(f"Extracted 0 products from {source}, but total_pages={total_pages}", extra={"site": self.site})
        else:
            logger.info(f"Extracted {len(products)} products from {source}", extra={"site": self.site})

        return {
            "products": products,
            "pagination": {
                "total_pages": total_pages,
                "page_index": page_index
            }
        }""")

# 5. Fix callers reading `api.total_pages`
# Let's just fix the usage of api.total_pages in scrape_url.
text = text.replace("api.total_pages =", "total_pages =")
text = text.replace("api.page_index =", "page_index =")
text = text.replace("api.total_pages", "total_pages")
text = text.replace("api.page_index", "page_index")

# Add async_scrape_url 
# I will grab scrape_url and duplicate it as async_scrape_url replacing _get_with_meta with _aget_with_meta

async_method_code = "\n" + text.split("    def scrape_url(")[1]
async_method_code = "    async def async_scrape_url(\n        self,\n        url: str,\n        page: int = 1,\n        debug: bool = False,\n        proxy: str | None = None,\n    ) -> dict:" + async_method_code.split(":", 1)[1]
async_method_code = async_method_code.replace("_get_with_meta(", "await _aget_with_meta(")
# Inject proxy to _aget_with_meta calls
async_method_code = async_method_code.replace("save_raw=debug_enabled)", "save_raw=debug_enabled, proxy=proxy)")

# Since we need to import _aget_with_meta, let's fix imports
text = text.replace("from scrapers.mapi_scraper.http import _get, _get_with_meta, _ok, _err, _save_debug_item, logger",
                    "from scrapers.mapi_scraper.http import _get, _get_with_meta, _aget_with_meta, _ok, _err, _save_debug_item, logger")

text = text + "\n" + async_method_code

with open(file_path, "w", encoding="utf-8") as f:
    f.write(text)

print("Done")
