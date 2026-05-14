import json
from curl_cffi import requests
from scrapers.mapi_scraper import scrape


# https://api.epicentrk.ua/api/v1/search?find=bosch&store_id=2&lang=ua&page=1&search_size=40
# https://api.epicentrk.ua/api/v2/catalog?store_id=2&slug=mobilnyye-telefony&lang=ua
# https://api.epicentrk.ua/api/v2/product/listing/products?store_id=2&query[]=%2Fshop%2Fgarnitury%2Ffs%2Fstandart-bluetooth-bluetooth-5-1%2F&lang=ua&page_size=60&rankSort=by_rank
# https://api.epicentrk.ua/api/v2/product/listing/products?store_id=2&query[]=%2Fshop%2Fsmartfony-i-mobilnye-telefony%2Ffs%2Fbrand-xiaomi%2F&lang=ua&page=2&page_size=60&rankSort=by_rank
# https://api.epicentrk.ua/api/v2/product/listing/products?store_id=2&query[]=%2Fshop%2Fsmartfony-i-mobilnye-telefony%2Ffilter%2Fbrand-is-uz1440254300h8f4%2Fprop_1535-is-256.0000%2Fapply%2F&lang=ua&page_size=60&rankSort=by_rank
# https://api.epicentrk.ua/api/v2/product/listing/section-data?store_id=2&query[]=%2Fshop%2Fgarnitury%2Ffs%2Fstandart-bluetooth-bluetooth-5-1%2F&lang=ua&page_size=60&rankSort=by_rank
# https://api.epicentrk.ua/api/v1/merchant?lang=ua&name=electronicsvolt&page_size=60
# https://api.epicentrk.ua/api/v1/product/card/full?store_id=2&slug=smartfon-apple-iphone-17-pro-256gb-silver-mg8g4af-a&lang=ua


def run():
    s = requests.Session(impersonate="chrome")
    h = {"referer": "https://epicentrk.ua/"}

    # 2. Получаем товары (чистый JSON)
    url = f"https://api.epicentrk.ua/api/v1/product/card/full?store_id=2&slug=mplc-kran-dla-sistemi-ocisenna-ecosoft-krapla-odinarnij-wdf104-1eeaa476-a979-661c-addb-7546f34bf768&lang=ua"
    r_p = s.get(url, headers=h)

    if r_p.status_code == 200:
        with open("output.txt", "w", encoding="utf-8") as f:
            json.dump(r_p.json(), f, indent=4, ensure_ascii=False)

        print("Успешно! Проверьте файл output.txt")
    else:
        print(f"Ошибка API: {r_p.status_code}")


run()
