"""
prom_multipage_test.py
======================
Comprehensive multipage test for Prom.ua GraphQL API using the universal schema.
Executes batch pagination requests across different listing types and logs results.

Usage:
    .venv\Scripts\python tests/prom_multipage_test.py
"""
import math
import time
import urllib.parse
from curl_cffi import requests

OUT_FILE = "tests/prom_multipage_test_results.md"

def build_query(operationName):
    listing_call = ""
    args = ""
    if operationName == "CategoryListingQuery":
        args = "$alias: String!, $params: Any, $offset: Int, $limit: Int, $regionId: Int, $subdomain: String"
        listing_call = "listing: categoryListing(alias: $alias, params: $params, offset: $offset, limit: $limit, region: {id: $regionId, subdomain: $subdomain})"
    elif operationName == "SearchListingQuery":
        args = "$search_term: String!, $params: Any, $offset: Int, $limit: Int, $regionId: Int, $subdomain: String"
        listing_call = "listing: searchListing(search_term: $search_term, params: $params, offset: $offset, limit: $limit, region: {id: $regionId, subdomain: $subdomain})"
    elif operationName == "CompanyListingQuery":
        args = "$company_id: Int!, $params: Any, $offset: Int, $limit: Int, $regionId: Int, $subdomain: String, $showShowroomProducts: Boolean!, $opinionPageType: String"
        listing_call = "listing: companyListing(company_id: $company_id, params: $params, offset: $offset, limit: $limit, region: {id: $regionId, subdomain: $subdomain})"
    elif operationName == "ManufacturerListingQuery":
        args = "$alias: String!, $params: Any, $offset: Int, $limit: Int, $regionId: Int, $subdomain: String"
        listing_call = "listing: manufacturerListing(alias: $alias, params: $params, offset: $offset, limit: $limit, region: {id: $regionId, subdomain: $subdomain})"

    return f"""query {operationName}({args}) {{
  {listing_call} {{
    page {{
      total
      products {{
        product {{
          id
          name: nameForCatalog
          price
          priceCurrencyLocalized
          presence {{
            isAvailable
            __typename
          }}
          __typename
        }}
        __typename
      }}
      __typename
    }}
    __typename
  }}
}}"""


def parse_base_payload(url: str):
    parsed = urllib.parse.urlparse(url)
    path = parsed.path
    query = urllib.parse.parse_qs(parsed.query)
    
    params = {"binary_filters": []}
    for key, values in query.items():
        if key in ("search_term", "page"):
            continue
        params[key] = values[0] if len(values) == 1 else values

    if path.startswith("/ua/search") or path.startswith("/search"):
        operation = "SearchListingQuery"
        variables = {
            "search_term": query.get("search_term", [""])[0],
            "regionId": None,
            "params": params,
            "includePremiumAdvBlock": False
        }
    elif "/c" in path and "-" in path and path.endswith(".html"):
        operation = "CompanyListingQuery"
        c_index = path.find("/c") + 2
        dash_index = path.find("-", c_index)
        company_id = int(path[c_index:dash_index])
        company_name = path[dash_index+1:].replace(".html", "")
        params["company_id"] = str(company_id)
        params["company_name"] = company_name
        variables = {
            "opinionPageType": "portal-company_page",
            "regionId": None,
            "params": params,
            "company_id": company_id,
            "showShowroomProducts": False
        }
    elif "/brands/" in path:
        operation = "ManufacturerListingQuery"
        alias = path.split("/brands/")[-1].split("?")[0].split(";")[0]
        variables = {
            "alias": alias,
            "regionId": None,
            "params": params
        }
    else:
        operation = "CategoryListingQuery"
        alias = path.split("/")[-1].split(";")[0]
        variables = {
            "alias": alias,
            "regionId": None,
            "params": params,
            "includePremiumAdvBlock": False
        }

    return operation, variables

def run_multipage(url: str, max_pages_to_scrape: int = None):
    print(f"\\n{'='*50}\\nTASK: {url}\\n[Max Pages: {max_pages_to_scrape or 'ALL'}]\\n{'='*50}")
    
    op_name, base_vars = parse_base_payload(url)
    query = build_query(op_name)
    limit = 29
    
    headers = {
        "content-type": "application/json",
        "accept": "*/*",
        "accept-language": "uk-UA,uk;q=0.9",
        "x-language": "uk",
        "x-requested-with": "XMLHttpRequest",
        "x-apollo-operation-name": op_name,
        "x-forwarded-proto": "https",
        "origin": "https://prom.ua",
        "referer": url,
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    
    current_page = 1
    total_found = None
    all_products = []
    log_lines = [f"## URL: `{url}`\\n- **Operation**: `{op_name}`\\n- **Variables**: `{base_vars}`\\n"]
    
    while True:
        offset = (current_page - 1) * limit
        variables = base_vars.copy()
        variables["limit"] = limit
        variables["offset"] = offset
        
        payload = {
            "operationName": op_name,
            "variables": variables,
            "query": query
        }

        print(f"  Fetching Page {current_page} (offset: {offset})...", end="", flush=True)
        t0 = time.time()
        resp = requests.post("https://prom.ua/graphql", headers=headers, json=payload, impersonate="chrome124", timeout=30)
        t1 = time.time()
        
        if resp.status_code != 200:
            print(f" ERROR {resp.status_code}")
            log_lines.append(f"❌ **Page {current_page} (offset {offset})** - ERROR {resp.status_code}: {resp.text[:200]}")
            break
            
        data = resp.json()
        if "errors" in data and data["errors"]:
            print(" GRAPHQL ERROR")
            log_lines.append(f"❌ **Page {current_page} (offset {offset})** - GraphQL Error: {data['errors']}")
            break
            
        page_node = data.get("data", {}).get("listing", {}).get("page", {})
        total_found = page_node.get("total", 0)
        items = page_node.get("products", [])
        
        all_products.extend(items)
        print(f" OK  (Took {t1-t0:.2f}s). Received {len(items)} items. Total available: {total_found}")
        log_lines.append(f"✅ **Page {current_page} (offset {offset})** - Extracted {len(items)} items in {t1-t0:.2f}s.")
        
        if len(items) > 0 and current_page == 1:
            samp = items[0].get("product", {})
            log_lines.append(f"   > *Sample:* `{samp.get('id')}` | **{samp.get('name')}** | {samp.get('price')} UAH")
            
        max_possible_pages = math.ceil(total_found / limit) if total_found > 0 else 0
        
        if len(items) < limit:
            print("  -> Partial page returned, reached end of catalog.")
            break
        
        if current_page >= max_possible_pages:
            print("  -> Reached calculated maximum total pages.")
            break
            
        if max_pages_to_scrape and current_page >= max_pages_to_scrape:
            print(f"  -> Reached artificial max pages limit ({max_pages_to_scrape}).")
            break
            
        current_page += 1
        time.sleep(0.5)
        
    summary = f"**Final Result:** Checked {current_page} pages, extracted {len(all_products)} products total. Server says {total_found} exist."
    log_lines.append(summary)
    print(f"\\n  {summary}")
    
    with open(OUT_FILE, "a", encoding="utf-8") as f:
        f.write("\\n\\n" + "\\n".join(log_lines))

if __name__ == "__main__":
    # Wipe log
    import os
    if os.path.exists(OUT_FILE):
        os.remove(OUT_FILE)
        
    test_cases = [
        # (url, max_pages)
        ("https://prom.ua/ua/brands/Uwatch?delivery=nova_poshta&category=5090319&a10006=83769", 3),
        ("https://prom.ua/ua/search?search_term=bosch&category=120229", 3),
        ("https://prom.ua/ua/c3715782-uadron.html?product_group=122638575", None),
        ("https://prom.ua/ua/c3741020-houseshop.html", None),
        ("https://prom.ua/ua/Video-diski-videokassety", 3),
        ("https://prom.ua/ua/Futlyary-dlya-dragotsennostej?delivery=delivery_auto&a644=33404", None)
    ]
    
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write("# Prom.ua Multipage GraphQL Automation Validation\\n")
        
    for url, pages in test_cases:
        run_multipage(url, pages)
    
    print(f"\\n[DONE] Logs written to {OUT_FILE}")
