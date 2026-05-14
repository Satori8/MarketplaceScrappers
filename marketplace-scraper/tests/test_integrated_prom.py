from scrapers.mapi_scraper import scrape
import json

url = "https://prom.ua/ua/Brands/Uwatch?delivery=nova_poshta&category=5090319&a10006=83769"
res = scrape("prom", "url", url=url, debug=True)

print(f"Status OK: {res.get('ok')}")
if res.get('ok'):
    print(f"Products count: {len(res.get('products', []))}")
    if res.get('products'):
        print(f"Sample product: {res['products'][0]['name']}")
else:
    print(f"Error: {res.get('error')}")
