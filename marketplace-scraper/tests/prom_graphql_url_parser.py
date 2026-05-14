"""
prom_graphql_url_parser.py
=========================
Parses Prom.ua URLs (Search, Category, Seller) including query parameters
(filters like delivery, custom attributes like a11867) into GraphQL 
variable payloads, and performs a live test using the universal schema.

Usage:
    .venv\Scripts\python tests/prom_graphql_url_parser.py
"""
import urllib.parse
import json
from pathlib import Path

def parse_prom_url(url: str) -> dict:
    """
    Parses a typical Prom.ua URL and returns the required GraphQL operation
    name and the corresponding variables payload.
    """
    parsed = urllib.parse.urlparse(url)
    path = parsed.path
    query = urllib.parse.parse_qs(parsed.query)
    
    # 1. Parse params array (filters)
    params = {"binary_filters": []}
    
    for key, values in query.items():
        if key == "search_term" or key == "page":
            continue # Handled separately
        if len(values) == 1:
            params[key] = values[0]
        else:
            params[key] = values # Array of values, e.g. a11867=[val1, val2]
            
    # Calculate offset
    page = int(query.get("page", ["1"])[0])
    limit = 29
    offset = (page - 1) * limit
    
    # 2. Determine operation type and core variables based on URL path
    if path.startswith("/ua/search") or path.startswith("/search"):
        operation = "SearchListingQuery"
        search_term = query.get("search_term", [""])[0]
        variables = {
            "search_term": search_term,
            "regionId": None,
            "params": params,
            "limit": limit,
            "offset": offset,
            "includePremiumAdvBlock": False
        }
    elif "/c" in path and "-" in path and path.endswith(".html"):
        # Seller page, e.g., /ua/c3889692-greatshopping.html
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
            "limit": limit,
            "offset": offset,
            "offset": offset,
            "showShowroomProducts": False
        }
    elif "/brands/" in path:
        # Manufacturer page, e.g., /ua/brands/Bosch
        operation = "ManufacturerListingQuery"
        alias = path.split("/brands/")[-1].split("?")[0].split(";")[0]
        variables = {
            "alias": alias,
            "regionId": None,
            "params": params,
            "limit": limit,
            "offset": offset
        }
    else:
        # Category page, e.g., /ua/Detskie-noski-i-golfy
        operation = "CategoryListingQuery"
        alias = path.split("/")[-1].split(";")[0] # handle legacy pagination slug like ;2
        variables = {
            "alias": alias,
            "regionId": None,
            "params": params,
            "limit": limit,
            "offset": offset,
            "includePremiumAdvBlock": False
        }
        
    return {
        "operationName": operation,
        "variables": variables
    }

HEADERS_NO_COOKIES = {
    "content-type": "application/json",
    "accept": "*/*",
    "accept-language": "uk-UA,uk;q=0.9",
    "x-language": "uk",
    "x-requested-with": "XMLHttpRequest",
    "x-forwarded-proto": "https",
    "origin": "https://prom.ua",
}

def build_graphql_query(operationName):
    # This is a minimized but universal fields query structure we discovered.
    # It dynamically inserts the correct listing object name based on operation.
    
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
          urlText
          categoryIds
          image(width: 200, height: 200)
          presence {{
            presence
            isAvailable
            __typename
          }}
          company {{
            id
            name
            slug
            deliveryStats {{
              deliverySpeed
            }}
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

def test_url(url: str):
    from curl_cffi import requests
    print(f"\\n[TEST] URL: {url}")
    
    parsed = parse_prom_url(url)
    op_name = parsed["operationName"]
    variables = parsed["variables"]
    
    print(f"  Mapped Operation: {op_name}")
    print(f"  Constructed Params:")
    print(f"    {json.dumps(variables['params'], ensure_ascii=False)}")
    
    query = build_graphql_query(op_name)
    
    headers = {**HEADERS_NO_COOKIES}
    headers["x-apollo-operation-name"] = op_name
    headers["referer"] = url
    headers["user-agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    
    payload = {
        "operationName": op_name,
        "variables": variables,
        "query": query
    }
    
    resp = requests.post(
        "https://prom.ua/graphql", 
        headers=headers, 
        json=payload, 
        impersonate="chrome124", 
        timeout=30
    )
    
    if resp.status_code == 200:
        data = resp.json()
        try:
            page = data["data"]["listing"]["page"]
            items = page.get("products", [])
            total = page.get("total", 0)
            print(f"  [SUCCESS] Status: {resp.status_code}. Total products: {total}. Returned on page: {len(items)}")
            if len(items) > 0:
                p = items[0]["product"]
                print(f"  [SAMPLE] {p['id']} - {p['name']} - {p['price']} UAH - Seller: {p['company']['name']}")
        except Exception as e:
            print(f"  [ERROR] Parsing response: {e}, Response: {str(data)[:200]}")
    else:
        print(f"  [ERROR] Status: {resp.status_code}, Body: {resp.text[:200]}")


if __name__ == "__main__":
    # Test cases representing the user's scenarios and edge cases
    test_urls = [
        "https://prom.ua/ua/search?search_term=iphone2",
        "https://prom.ua/ua/Detskie-noski-i-golfy?delivery=ukrposhta",
        "https://prom.ua/ua/c3889692-greatshopping.html?a1315=70330",
        "https://prom.ua/ua/c3889692-greatshopping.html?a1315=70330&a714=214230&a11867=313454&a11867=279079&page=2",
        "https://prom.ua/ua/brands/Uwatch?delivery=nova_poshta"
    ]
    
    for url in test_urls:
        test_url(url)
        
