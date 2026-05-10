import requests
url = 'https://common-api.rozetka.com.ua/v1/api/product/details?country=UA&lang=ua&ids=205938877'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Referer': 'https://rozetka.com.ua/',
}
r = requests.get(url, headers=headers, timeout=10)
print(r.status_code, r.text[:500])
