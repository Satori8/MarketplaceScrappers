from scrapers.mapi_scraper import scrape
import json

urls = [
    "https://prom.ua/ua/Brands/Uwatch?delivery=nova_poshta&category=5090319&a10006=83769",
    "https://prom.ua/ua/search?search_term=iphone",
    "https://prom.ua/ua/Detskie-noski-i-golfy",
    "https://prom.ua/ua/c3741020-houseshop.html"
]

for url in urls:
    res = scrape("prom", "url", url=url, debug=True)
    print(f"URL: {url}")
    print(f"  Status OK: {res.get('ok')}")
    if res.get('ok'):
        print(f"  Products: {len(res.get('products', []))}")
        if res.get('products'):
            print(f"  Sample: {res['products'][0]['name']}")
            print(f"  Source: {res.get('mode')} (API should have used GraphQL)")
    else:
        print(f"  Error: {res.get('error')}")
    print("-" * 30)
