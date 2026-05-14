import sys
import json
import time
import os
import traceback
from datetime import datetime

# Add parent dir to path so we can import fast_api
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.mapi_scraper.paginator import Paginator

TEST_CASES = [
    # Rozetka
    {
        "site": "rozetka",
        "url": "https://auto.rozetka.com.ua/ua/dopolnitelnie-elektropribori-v-avto/c4654538/",
    },
    {"site": "rozetka", "url": "https://rozetka.com.ua/ua/search/?text=iphone"},
    {"site": "rozetka", "url": "https://rozetka.com.ua/ua/seller/bubonets/goods/"},
    {
        "site": "rozetka",
        "url": "https://hard.rozetka.com.ua/ua/monitors/c80089/producer=gigabyte;23522=usb-type-c-5196312/",
    },
    # Prom
    {"site": "prom", "url": "https://prom.ua/ua/Kukly"},
    {"site": "prom", "url": "https://prom.ua/ua/search?search_term=iphone"},
    {"site": "prom", "url": "https://prom.ua/ua/c4041439-online-shop-easy.html"},
    # Epicentr
    {
        "site": "epicentr",
        "url": "https://epicentrk.ua/ua/shop/filtry-dlya-pitevoy-vody/",
    },
    {"site": "epicentr", "url": "https://epicentrk.ua/ua/search/?q=t100"},
    {"site": "epicentr", "url": "https://epicentrk.ua/ua/merchant/loftsvet/"},
    # Allo
    {"site": "allo", "url": "https://allo.ua/ua/televizory/proizvoditel-hisense/"},
    {"site": "allo", "url": "https://allo.ua/ua/catalogsearch/result/?q=bosch"},
    {"site": "allo", "url": "https://allo.ua/ua/partner_sakic-yulo/"},
]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    debug_flag = "--debug"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    results = []

    print(f"Starting Pagination Tests (Debug: {debug_flag})")
    print("-" * 50)

    # Optional delay parameter; requirement specified default 2 seconds.
    paginator = Paginator(delay=2.0)

    summary = []

    for case in TEST_CASES:
        site = case["site"]
        url = case["url"]

        print(f"[{site}] {url}")

        try:
            start_time = time.time()
            res = paginator.paginate(site, url, max_pages=2, debug=debug_flag)
            total_time_ms = int((time.time() - start_time) * 1000)

            for log_entry in res.log:
                page = log_entry["page"]
                p_found = log_entry["products_found"]
                print(f"  page {page}: {p_found} products | url: {log_entry['url']}")

            total_p = len(res.products)

            # test should also count number of products in output
            if res.errors:
                print(
                    f"  TOTAL: {total_p} products | {res.pages_fetched} pages | total_reported={res.total_pages_reported} [WITH ERRORS]"
                )
                for err in res.errors:
                    print(f"    error: {err}")
                summary.append(
                    {
                        "site": site,
                        "url": url[:30] + "...",
                        "status": "FAIL",
                        "num_products": total_p,
                        "pages": res.pages_fetched,
                    }
                )
            else:
                print(
                    f"  TOTAL: {total_p} products | {res.pages_fetched} pages | total_reported={res.total_pages_reported}"
                )
                summary.append(
                    {
                        "site": site,
                        "url": url[:30] + "...",
                        "status": "OK",
                        "num_products": total_p,
                        "pages": res.pages_fetched,
                    }
                )

            results.append(
                {
                    "site": site,
                    "url": url,
                    "pages_fetched": res.pages_fetched,
                    "total_pages_reported": res.total_pages_reported,
                    "products_count": total_p,
                    "errors": res.errors,
                    "log": res.log,
                }
            )

        except Exception as e:
            print(f"  CRASH: {traceback.format_exc()}")
            summary.append(
                {
                    "site": site,
                    "url": url[:30] + "...",
                    "status": "CRASH",
                    "num_products": 0,
                    "pages": 0,
                }
            )

        print()

    print("SUMMARY")
    print("-" * 50)
    for s in summary:
        print(
            f"{s['site']:<10} {s['url']:<35} {s['status']:<5} {s['num_products']} products  {s['pages']} pages"
        )

    # Save results
    results_dir = os.path.join(os.path.dirname(__file__), "results")
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)

    out_file = os.path.join(results_dir, f"test_pagination_{timestamp}.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(
            {"timestamp": timestamp, "debug": debug_flag, "results": results},
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"\nResults saved to {out_file}")


if __name__ == "__main__":
    main()
