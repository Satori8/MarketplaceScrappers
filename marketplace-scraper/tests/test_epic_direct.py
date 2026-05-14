import json
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.mapi_scraper import scrape

def test_epicentr_listing():
    print("Testing Epicentr Listing...")
    url = "https://epicentrk.ua/ua/shop/komplektuyuschie-k-filtram-dlya-vody/"
    res = scrape("epicentr", "url", url=url, debug=True)
    if res.get("ok"):
        products = res.get("products", [])
        print(f"✅ Success! Found {len(products)} products.")
        if products:
            print(f"Sample: {products[0].get('name')} | Price: {products[0].get('price')} | Merchant: {products[0].get('merchant_name')}")
        pagination = res.get("pagination", {})
        print(f"Pagination: {pagination}")
    else:
        print(f"❌ Failed: {res.get('error')}")

def test_epicentr_search():
    print("\nTesting Epicentr Search...")
    url = "https://epicentrk.ua/ua/search/?q=t200"
    res = scrape("epicentr", "url", url=url, debug=True)
    if res.get("ok"):
        products = res.get("products", [])
        print(f"✅ Success! Found {len(products)} products.")
        pagination = res.get("pagination", {})
        print(f"Pagination: {pagination}")
    else:
        print(f"❌ Failed: {res.get('error')}")

def test_epicentr_merchant():
    print("\nTesting Epicentr Merchant...")
    url = "https://epicentrk.ua/ua/merchant/avtomoda/"
    res = scrape("epicentr", "url", url=url, debug=True)
    if res.get("ok"):
        products = res.get("products", [])
        print(f"✅ Success! Found {len(products)} products.")
        pagination = res.get("pagination", {})
        print(f"Pagination: {pagination}")
    else:
        print(f"❌ Failed: {res.get('error')}")

if __name__ == "__main__":
    test_epicentr_listing()
    test_epicentr_search()
    test_epicentr_merchant()
