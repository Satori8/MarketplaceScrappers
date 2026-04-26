from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from urllib.parse import quote_plus, urljoin
from pathlib import Path

from core.models import RawProduct
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class HotlineScraper(BaseScraper):
    def __init__(self, db=None, config_path: str = "config.yaml", captcha_callback=None) -> None:
        super().__init__(marketplace_name="hotline", config_path=config_path, captcha_callback=captcha_callback)
        self.db = db

    async def search_products(self, query: str, pages: int = 1, skip_urls: set[str] = None, stop_event: asyncio.Event = None) -> list[RawProduct]:
        method = self.config.get("method_preference", "Auto")
        if method == "Browser":
             return await self._search_playwright(query, pages, skip_urls, stop_event=stop_event)
        return await self._search_httpx(query, pages, skip_urls)

    async def _search_playwright(self, query: str, pages: int = 1, skip_urls: set[str] = None, stop_event: asyncio.Event = None) -> list[RawProduct]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return await self._search_httpx(query, pages, skip_urls)

        cfg = self.config.get("marketplaces", {}).get("hotline", {})
        base_url = cfg.get("base_url", "https://hotline.ua")
        search_template = cfg.get("search_url", "https://hotline.ua/ua/sr/?q={query}")
        selectors = cfg.get("selectors", {})
        card_sel = selectors.get("product_card") or ".list-item.product-item"
        
        products: list[RawProduct] = []
        if query.startswith("http"):
            current_url = query
        else:
            current_url = search_template.format(query=quote_plus(query))

        async with async_playwright() as p:
            user_data_dir = str(Path("data/browser_profile_hotline").resolve())
            browser_context = await p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=False,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
                ignore_default_args=["--enable-automation"],
                viewport={"width": 1280, "height": 800},
                user_agent=self.get_random_user_agent()
            )
            await self.anti_bot.apply_stealth_async(browser_context)
            page = browser_context.pages[0] if browser_context.pages else await browser_context.new_page()
            
            logger.info(f"[Hotline] Processing: {current_url}")
            await page.goto(current_url, wait_until="networkidle")
            await self.wait_for_captcha(page)
            
            # Find product items with multiple selector fallbacks
            selectors_to_try = [".product-item", "li.list-item", ".list-item", "div[data-id='product-item']"]
            cards = []
            for sel in selectors_to_try:
                cards = await page.query_selector_all(sel)
                if cards:
                    logger.info(f"[Hotline] Found {len(cards)} products using selector: {sel}")
                    break
            
            if not cards:
                logger.warning("[Hotline] No product cards found on search page. Checking page content...")
                # Fallback: find any link that looks like a product
                links = await page.query_selector_all("a[href*='/ua/']:not([href*='/sr/'])")
                product_urls = []
                for link in links:
                    href = await link.get_attribute("href")
                    if href and "/ua/" in href and len(href.split("/")) > 4:
                        product_urls.append(urljoin(base_url, href))
                product_urls = list(dict.fromkeys(product_urls))[:10]
            else:
                product_urls = []
                for card in cards[:12]: 
                    url_node = await card.query_selector("a[data-eventlabel='Product Name'], .item-info a, a.link--black")
                    if url_node:
                        href = await url_node.get_attribute("href")
                        if href: product_urls.append(urljoin(base_url, href))

            if not product_urls:
                logger.error("[Hotline] Could not extract any product URLs from the search results.")
                await browser_context.close()
                return []

            for p_url in product_urls:
                # IMMEDIATE STOP CHECK
                if stop_event and stop_event.is_set():
                    logger.info("[Hotline] Stop requested. Terminating current task.")
                    break
                    
                logger.info(f"[Hotline] Extracting offers from: {p_url}")
                det_page = await browser_context.new_page()
                try:
                    # Target the prices tab directly
                    target_url = p_url.split("?")[0].strip("/") + "/prices/"
                    await det_page.goto(target_url, wait_until="networkidle", timeout=30000)
                    await self.wait_for_captcha(det_page)
                    
                    # Ensure title is loaded
                    title_node = await det_page.query_selector("h1.text-3xl, h1, .title-21")
                    product_title = (await title_node.inner_text()).strip() if title_node else "Unknown Product"

                    # 1. Find unique rows using valid CSS
                    # We look for containers that HAVE a goprice link inside
                    offer_containers = await det_page.query_selector_all("div[class*='_3R0mOsD'], .list-item--offer, [data-tracking-id='offer-1']")
                    
                    # Convert to unique row containers
                    unique_rows = []
                    seen_handles = set()
                    for item in offer_containers:
                        row = await item.evaluate_handle("el => el.closest('div[class*=\"_\"]') || el.closest('.list-item') || el")
                        if row:
                            is_new = await det_page.evaluate("el => { if(!el || el.dataset.seen) return false; el.dataset.seen='1'; return true; }", row)
                            if is_new: unique_rows.append(row)
                    
                    offer_containers = unique_rows

                    added_offers = 0
                    junk_names = ["купити", "відвантаження", "читати", "відгуки", "поскаржитись", "магазина"]

                    # B16 optimization: use one client for all offers on this page
                    import httpx
                    async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
                        for row in offer_containers:
                            if self._stop_event.is_set(): break
                            if added_offers >= 15: break
                            
                            # Inside each row, find the visible price
                            all_visible_text = await det_page.evaluate("el => el.innerText", row)
                            if not all_visible_text: continue
                            
                            # Extract price (look for numbers near ₴)
                            import re
                            price_match = re.search(r"([\d\s]+)\s*₴", all_visible_text.replace("\xa0", " "))
                            if not price_match: continue
                            
                            price_val = self.parse_price(price_match.group(1))
                            if not price_val: continue
                            
                            # Find the best shop name candidate inside this row
                            # Priority 1: data-tracking-id="goprice-2" (Official shop name link)
                            shop_link = await row.query_selector("a[data-tracking-id='goprice-2'], a[class*='shop']")
                            shop_name = ""
                            if shop_link:
                                 shop_name = (await shop_link.inner_text()).strip()
                            
                            # Priority 2: Alt text from logo image
                            if not shop_name or any(j in shop_name.lower() for j in junk_names):
                                 img = await row.query_selector("img[alt*='інтернет-магазин']")
                                 if img:
                                     shop_alt = await img.get_attribute("alt")
                                     shop_name = shop_alt.replace("Логотип інтернет-магазина", "").replace("Логотип", "").strip()
                            
                            # Final check for junk
                            if not shop_name or any(j in shop_name.lower() for j in junk_names) or len(shop_name) < 2:
                                 # Try to see if there's any link that is NOT just a generic button
                                 other_links = await row.query_selector_all("a[href*='/go/price/']")
                                 for ol in other_links:
                                      t = (await ol.inner_text()).strip()
                                      if t and not any(j in t.lower() for j in junk_names) and len(t) > 2:
                                           shop_name = t
                                           break

                            if not shop_name or any(j in shop_name.lower() for j in junk_names):
                                 continue # Still junk, skip this row
                            
                            # Extract the redirect URL
                            final_link = target_url # Fallback
                            go_link_node = await row.query_selector("a[href*='/go/price/']")
                            if go_link_node:
                                 href = await go_link_node.get_attribute("href")
                                 if href:
                                     go_link = urljoin(base_url, href)
                                     # Try to resolve redirect
                                     try:
                                         # B16 fix: reuse the client from outer context
                                         r = await client.get(go_link, headers={"User-Agent": self.get_random_user_agent()})
                                         final_link = str(r.url)
                                     except:
                                         final_link = go_link # Use the go/price link if resolution fails

                            products.append(self._create_raw(f"{product_title} | {shop_name}", price_val, final_link, "hotline"))
                            added_offers += 1
                    
                    logger.info(f"[Hotline] Successfully extracted {added_offers} unique shop offers for {product_title}")
                except Exception as e:
                    logger.warning(f"[Hotline] Detail error for {p_url}: {e}")
                finally:
                    await det_page.close()
                
            await browser_context.close()
        return products

    async def _search_httpx(self, query: str, pages: int, skip_urls: set | None = None, stop_event=None) -> list[RawProduct]:
        import httpx
        from bs4 import BeautifulSoup
        cfg = self.config.get("marketplaces", {}).get("hotline", {})
        base_url = cfg.get("base_url", "https://hotline.ua")
        search_template = cfg.get("search_url", "https://hotline.ua/ua/sr/?q={query}")
        
        products: list[RawProduct] = []
        if query.startswith("http"):
            current_url = query
        else:
            current_url = search_template.format(query=quote_plus(query))
        
        headers = {"User-Agent": self.get_random_user_agent()}
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=headers) as client:
            resp = await client.get(current_url)
            if resp.status_code != 200: return []
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Extract main product links from search
            links = [urljoin(base_url, a["href"]) for a in soup.select(".item-info a[href]") if "/ua/" in a["href"]]
            
            for p_url in list(dict.fromkeys(links))[:10]: # De-duplicate and limit
                try:
                    target_url = p_url if "/prices/" in p_url else p_url.strip("/") + "/prices/"
                    det_resp = await client.get(target_url)
                    det_soup = BeautifulSoup(det_resp.text, "html.parser")
                    
                    title = det_soup.find("h1").get_text(strip=True) if det_soup.find("h1") else "Product"
                    offers = det_soup.select(".list-item--offer")
                    for off in offers:
                        s_node = off.select_one(".shop__title")
                        p_node = off.select_one(".price__value")
                        if s_node and p_node:
                            price = self.parse_price(p_node.get_text())
                            if price:
                                products.append(self._create_raw(f"{title} | {s_node.get_text(strip=True)}", price, p_url, "hotline"))
                except: continue
        return products

    def _create_raw(self, title, price, url, mp):
        return RawProduct(
            title=title, price=price, currency="UAH", url=url, marketplace=mp,
            brand=None, model=None, raw_specs={}, description=None,
            image_url=None, availability=None, rating=None, reviews_count=None,
            category_path=None, scraped_at=datetime.now(timezone.utc)
        )

    async def get_product_details(self, url: str) -> RawProduct:
        return self._create_raw("", 0.0, url, "hotline")

    def parse_price(self, raw_text: str) -> float | None:
        if not raw_text: return None
        # Handle cases like "10 000 — 15 000" by taking the lower bound
        if "—" in raw_text:
            raw_text = raw_text.split("—")[0]
        if "-" in raw_text:
            raw_text = raw_text.split("-")[0]
            
        cleaned = "".join(c for c in raw_text if c.isdigit() or c in ".,")
        cleaned = cleaned.replace(",", ".")
        try: return float(cleaned)
        except: return None

    def detect_captcha(self, page) -> bool:
        return False
