
import httpx
from bs4 import BeautifulSoup

url = "https://prom.ua/ua/search?search_term=LiFePO4"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

with httpx.Client(headers=headers, follow_redirects=True) as client:
    resp = client.get(url)
    print(f"Status: {resp.status_code}")
    print(f"Final URL: {resp.url}")
    soup = BeautifulSoup(resp.text, "html.parser")
    
    # Find data-qaid for ALL links
    results = []
    for a in soup.find_all("a", href=True):
        if "/p" in a["href"]:
            current = a
            qaid = None
            while current:
                if current.get("data-qaid"):
                    qaid = current.get("data-qaid")
                    break
                current = current.parent
            results.append((a.get_text(strip=True)[:40], a["href"][:40], qaid))
    
    print(f"Total product-like links found: {len(results)}")
    for i, (text, href, qaid) in enumerate(results[:60]):
        print(f"  {i+1}. [{qaid}] {text} -> {href}")




