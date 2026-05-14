import sys
with open(r'd:\Scrappers\marketplace-scraper\scrapers\mapi_scraper\sites\prom.py', 'r', encoding='utf-8') as f:
    text = f.read()

if 'async def async_scrape_url' not in text:
    scrape_url_code = text.split('    def scrape_url(self, url: str, page: int = 1, debug: bool = False) -> dict:\n')[1]
    async_code = '    async def async_scrape_url(\n        self,\n        url: str,\n        page: int = 1,\n        debug: bool = False,\n        proxy: str | None = None,\n    ) -> dict:\n' + scrape_url_code

    async_code = async_code.replace('_get_with_meta(', 'await _aget_with_meta(')
    async_code = async_code.replace('save_raw=debug)', 'save_raw=debug, proxy=proxy)')

    POST_REPLACE = """from curl_cffi.requests import AsyncSession
                    async with AsyncSession(impersonate="chrome124") as session:
                        resp = await session.post("https://prom.ua/graphql", headers=headers, json=payload, timeout=15, proxies={"https": proxy, "http": proxy} if proxy else None)"""
    async_code = async_code.replace('resp = requests.post("https://prom.ua/graphql", headers=headers, json=payload, impersonate="chrome124", timeout=15)', POST_REPLACE)

    text = text.replace('from scrapers.mapi_scraper.http import _get_with_meta,', 'from scrapers.mapi_scraper.http import _get_with_meta, _aget_with_meta,')

    with open(r'd:\Scrappers\marketplace-scraper\scrapers\mapi_scraper\sites\prom.py', 'w', encoding='utf-8') as f:
        f.write(text + '\n' + async_code)
print('DONE')
