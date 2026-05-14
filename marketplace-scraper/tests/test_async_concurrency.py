import asyncio
from scrapers.mapi_scraper import async_scrape_url_auto

async def main():
    urls = [
        "https://rozetka.com.ua/ua/search/?text=iphone",
        "https://prom.ua/ua/search?search_term=iphone",
        "https://allo.ua/ua/catalogsearch/result/?q=iphone",
        "https://epicentrk.ua/shop/search/?q=iphone"
    ]
    
    print("Starting concurrent scraping...")
    results = await asyncio.gather(*(async_scrape_url_auto(url) for url in urls))
    
    for url, res in zip(urls, results):
        if res.get("ok"):
            products = res.get("products", [])
            print(f"✅ {url} -> {len(products)} products found")
        else:
            print(f"❌ {url} -> Failed: {res.get('error')}")

if __name__ == "__main__":
    asyncio.run(main())
