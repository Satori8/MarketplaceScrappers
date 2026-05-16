import sys
import json
import time
import os
import asyncio
import traceback
from datetime import datetime
from typing import Optional, List, Dict, Any

# Add parent dir to path so we can import scrapers
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.mapi_scraper import async_scrape, get_module_for_url
from scrapers.mapi_scraper.http import logger

# List of URLs for testing with their expected page counts or None for "all"
TEST_CASES = [
    {"url": "https://prom.ua/ua/Kulony", "max_pages": 3},
    {
        "url": "https://prom.ua/ua/Kulony?a5527=132944&a644=8058&a3810=138428",
        "max_pages": 3,
    },
    {
        "url": "https://prom.ua/ua/Kurtki-rabochie;2?delivery=delivery_auto&a5100=32849",
        "max_pages": None,
    },
    {
        "url": "https://prom.ua/ua/search?search_term=t100&opinions=opinions_with_media&a18=26704&price_local__lte=179",
        "max_pages": None,
    },
    {
        "url": "https://prom.ua/ua/brands/Spektr-3;2?a15323=310684&a15323=220312",
        "max_pages": None,
    },
    {
        "url": "https://prom.ua/ua/c2885189-master-taras-internet.html?a18=3664&price_local__lte=428",
        "max_pages": None,
    },
    {
        "url": "https://allo.ua/ua/kacheli/kolv_mest-chetyrehmestnye/tip_kacheli-kacheli_divan/",
        "max_pages": None,
    },
    {
        "url": "https://allo.ua/ua/catalogsearch/result/index/proizvoditel-lenovo/?q=t1000",
        "max_pages": None,
    },
    {
        "url": "https://allo.ua/ua/partner_protocol-1/proizvoditel-samsung/",
        "max_pages": None,
    },
    {
        "url": "https://allo.ua/ua/schetki-dlja-lica/price_from-99/price_to-5524/seller-allo_plus/",
        "max_pages": None,
    },
    {
        "url": "https://bt.rozetka.com.ua/ua/fans/c80186/strana-proizvoditelj-tovara-90098=619924/",
        "max_pages": None,
    },
    {
        "url": "https://build.rozetka.com.ua/ua/svetodiodnaya-lenta/c234721/istochnik-pitaniya-210103=ot-akkumulyatora,ot-batareek;naznachenie-210109=dlya-lestnitsi,dlya-stola,dlya-televizora,dlya-ulitsi,dlya-zerkala/",
        "max_pages": None,
    },
    {
        "url": "https://rozetka.com.ua/ua/seller/est/goods/?producer=led-stil",
        "max_pages": None,
    },
    {
        "url": "https://rozetka.com.ua/ua/search/?section_id=80004&strana-proizvoditelj-tovara-90098=544331&text=t1000",
        "max_pages": 3,
    },
    {
        "url": "https://rozetka.com.ua/ua/producer/asus/?delivery=fast-delivery&strana-proizvoditelj-tovara-90098=544331",
        "max_pages": None,
    },
    {
        "url": "https://epicentrk.ua/ua/shop/mebel-dlya-spalni/filter/prop_4328-is-b17c0c27aefaabd2cd8962fa46b072cb/prop_10375-is-125ce58cc708540bce6608a3a0696438/apply/",
        "max_pages": None,
    },
    {
        "url": "https://epicentrk.ua/ua/shop/keramicheskaya-plitka-i-keramogranit/filter/prop_2419-is-18314ba851a9feed7a6a9407980eec24/apply/",
        "max_pages": None,
    },
    {
        "url": "https://epicentrk.ua/ua/search/?q=t100&SECTION_ID=2826",
        "max_pages": None,
    },
    {
        "url": "https://epicentrk.ua/ua/search/?PAGEN_1=7&q=t100&SELLER=other",
        "max_pages": None,
    },
    {"url": "https://epicentrk.ua/ua/merchant/tivoli-land/", "max_pages": None},
    {"url": "https://epicentrk.ua/ua/brands/luna.html?SELLER=other", "max_pages": None},
]


class AsyncPaginator:
    def __init__(self, delay: float = 1.0):
        self.delay = delay

    async def paginate(
        self, url: str, max_pages: Optional[int] = None, debug: bool = False
    ) -> Dict[str, Any]:
        module = get_module_for_url(url)
        if not module:
            return {"ok": False, "error": f"No module found for URL: {url}"}

        site = module.SITE_ID
        result = {
            "site": site,
            "url": url,
            "pages_fetched": 0,
            "total_pages_reported": 0,
            "products": [],
            "log": [],
            "errors": [],
            "anomalies": [],
        }

        seen_ids = set()
        page = 1

        while True:
            try:
                res = await async_scrape(site, url, page=page, debug=debug)

                if not res.get("ok"):
                    err_msg = res.get("error", "Unknown error")
                    result["errors"].append(f"Page {page}: {err_msg}")
                    break

                products = res.get("products", [])
                if not isinstance(products, list):
                    products = []

                new_count = 0
                for p in products:
                    pid = p.get("id") or p.get("sku")
                    if pid:
                        if pid not in seen_ids:
                            seen_ids.add(pid)
                            result["products"].append(p)
                            new_count += 1
                    else:
                        result["products"].append(p)
                        new_count += 1

                pagination = res.get("pagination", {})
                total_pages = pagination.get("total_pages", 0)
                if total_pages > result["total_pages_reported"]:
                    result["total_pages_reported"] = total_pages

                result["pages_fetched"] += 1
                result["log"].append(
                    {
                        "page": page,
                        "products_found": len(products),
                        "new_products": new_count,
                        "reported_total": total_pages,
                    }
                )

                # Check for anomalies
                if len(products) == 0 and total_pages > 0 and page <= total_pages:
                    result["anomalies"].append(
                        f"Page {page} empty but reported total_pages {total_pages}"
                    )

                # Stop conditions
                if len(products) == 0:
                    break
                if max_pages and page >= max_pages:
                    break
                # Stop if we reached reported total or if total is not reported
                if total_pages <= 0 or page >= total_pages:
                    break

                # Loop detection: if we get products but none are new (on page > 1), it's a loop
                if len(products) > 0 and new_count == 0 and page > 1:
                    result["anomalies"].append(
                        f"Page {page} returned {len(products)} products but all were duplicates. Pagination loop detected."
                    )
                    break

                # Safety break for "all pages" to avoid infinite loops if pagination is broken
                if page >= 100:
                    result["anomalies"].append("Stopped at 100 pages safety limit")
                    break

                page += 1
                await asyncio.sleep(self.delay)

            except Exception as e:
                result["errors"].append(f"Page {page} Exception: {str(e)}")
                result["anomalies"].append(traceback.format_exc())
                break

        return result


async def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    paginator = AsyncPaginator(delay=1.5)
    debug = True

    print(f"Starting Async Pagination Tests | Timestamp: {timestamp}")
    print("-" * 80)

    all_results = []

    for i, case in enumerate(TEST_CASES):
        url = case["url"]
        max_p = case["max_pages"]

        print(f"[{i+1}/{len(TEST_CASES)}] Testing: {url}")
        print(f"  Target: {'all' if max_p is None else max_p} pages")

        start_t = time.time()
        res = await paginator.paginate(url, max_pages=max_p, debug=debug)
        elapsed = time.time() - start_t

        status = "OK"
        if res.get("errors"):
            status = "ERROR"
        if res.get("anomalies"):
            status = "ANOMALY"
        if not res.get("ok", True):
            status = "FAIL"

        print(
            f"  Status: {status} | Processed {res.get('pages_fetched', 0)} pages | Found {len(res.get('products', []))} products | {elapsed:.1f}s"
        )

        for entry in res.get("log", []):
            print(
                f"    - Page {entry['page']}: {entry['products_found']} items (total_reported: {entry['reported_total']})"
            )

        if res.get("errors"):
            for err in res["errors"]:
                print(f"    ! Error: {err}")
        if res.get("anomalies"):
            for anom in res["anomalies"]:
                print(f"    ? Anomaly: {anom}")

        all_results.append(res)
        print("-" * 40)

    # Save results
    results_dir = os.path.join(os.path.dirname(__file__), "results")
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)

    out_file = os.path.join(results_dir, f"test_pagination_async_{timestamp}.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(
            {"timestamp": timestamp, "cases": len(TEST_CASES), "results": all_results},
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"\nFinal Summary saved to: {out_file}")


if __name__ == "__main__":
    asyncio.run(main())
