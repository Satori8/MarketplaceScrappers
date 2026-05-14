import json
from curl_cffi import requests
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

def filter_headers(original_headers, req_obj=None):
    new_headers = {}
    for k, v in original_headers.items():
        k_lower = k.lower()
        if k_lower in ["cookie", "authorization", "bearer"]:
            continue
        if k_lower.startswith("x-") and any(word in k_lower for word in ["token", "session", "user", "auth"]):
            continue
        new_headers[k] = v
        
    if "referer" not in new_headers and "Referer" not in new_headers:
        if req_obj and req_obj.get("referrer"):
            new_headers["referer"] = req_obj.get("referrer")
        else:
            new_headers["referer"] = "https://epicentrk.ua/"
            
    if "user-agent" not in {k.lower() for k in new_headers.keys()}:
        new_headers["user-agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"

    return new_headers

def extract_products(data):
    if not data: return []
    # Schema 1: Search / v1 / v2 nested in data
    if isinstance(data.get("data"), dict):
        inner = data["data"]
        if "items" in inner and isinstance(inner["items"], list): return inner["items"]
        if "products" in inner and isinstance(inner["products"], list): return inner["products"]
    
    # Schema 2: Top level items/products
    if "items" in data and isinstance(data["items"], list): return data["items"]
    if "products" in data and isinstance(data["products"], list): return data["products"]
    
    # Schema 3: params.products (Merchant/Brand)
    if isinstance(data.get("params"), dict):
        params = data["params"]
        if "products" in params and isinstance(params["products"], list): return params["products"]
            
    return []

def main():
    with open('epicentr_requests_raw.json', 'r', encoding='utf-8') as f:
        reqs = json.load(f)

    endpoints = {}
    for req in reqs:
        parsed_url = urlparse(req["url"])
        path = parsed_url.path
        if path not in endpoints: endpoints[path] = []
        endpoints[path].append(req)

    results = []

    def test_endpoint(test_url, method, endpoint_name, req_orig, test_type="P1"):
        print(f"\nTesting {endpoint_name} ({test_type}): {test_url}")
        filtered = filter_headers(req_orig["headers"], req_orig)
        try:
            res = requests.get(test_url, headers=filtered, impersonate="chrome120")
            status = res.status_code
            data = res.json() if res.ok else None
        except Exception as e:
            print(f"Error: {e}")
            return None
        
        products = extract_products(data)
        has_products = len(products) > 0
        total_count = None
        
        if data:
            if isinstance(data.get("data"), dict):
                total_count = data["data"].get("totalCount") or data["data"].get("total")
            if not total_count:
                total_count = data.get("totalCount") or data.get("total") or data.get("count")
            if not total_count and isinstance(data.get("params"), dict):
                total_count = data["params"].get("total")

        verdict = "✅" if has_products else "❌"
        print(f"Status: {status}, Products: {len(products)}, Verdict: {verdict}")
        
        return {
            "endpoint": endpoint_name,
            "test_type": test_type,
            "url": test_url,
            "status": status,
            "has_products": has_products,
            "count": len(products),
            "verdict": verdict,
            "total_count": total_count,
            "used_headers": filtered
        }

    for path, group in endpoints.items():
        req = group[0]
        res1 = test_endpoint(req["url"], req["method"], path, req, "P1")
        if res1:
            results.append(res1)
            if res1["verdict"] == "✅":
                parsed_url = urlparse(req["url"])
                qs = parse_qs(parsed_url.query)
                qs["page"] = ["2"]
                new_query = urlencode(qs, doseq=True)
                new_url = urlunparse(parsed_url._replace(query=new_query))
                res2 = test_endpoint(new_url, req["method"], path, req, "P2")
                if res2:
                    results.append(res2)

    with open('epicentr_test_results_v2.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

if __name__ == '__main__':
    main()
