from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.parse import quote_plus, urljoin

from core.models import RawProduct
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class EpicentrkScraper(BaseScraper):
    def __init__(self, db=None, config_path: str = "config.yaml", captcha_callback=None) -> None:
        super().__init__(marketplace_name="epicentrk", config_path=config_path, captcha_callback=captcha_callback)
        self.db = db

    async def search_products(self, query: str, pages: int = 1, skip_urls: set[str] = None, stop_event=None) -> list[RawProduct]:
        method = self.config.get("method_preference", "Auto")
        if method == "Browser":
            return await self._search_playwright(query, pages, skip_urls, stop_event=stop_event)
        return await self._search_httpx(query, pages, skip_urls, stop_event=stop_event)

    async def _search_playwright(self, query: str, pages: int = 1, skip_urls: set[str] = None, stop_event=None) -> list[RawProduct]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return await self._search_httpx(query, pages, skip_urls)

        cfg = self.config.get("marketplaces", {}).get("epicentrk", {})
        base_url = cfg.get("base_url")
        search_template = cfg.get("search_url")
        selectors = cfg.get("selectors", {})
        
        products: list[RawProduct] = []
        current_url = search_template.format(query=quote_plus(query))

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(user_agent=self.get_random_user_agent())
            await self.anti_bot.apply_stealth_async(context)
            page = await context.new_page()
            
            for p_idx in range(int(pages)):
                if stop_event and stop_event.is_set():
                    logger.info("[Epicentrk] Stop requested.")
                    break
                await page.goto(current_url, wait_until="networkidle")
                await self.wait_for_captcha(page)
                await page.wait_for_timeout(2000)

                # B17 fix: safety guard against missing selectors
                card_sel = selectors.get("product_card")
                if not card_sel:
                    logger.error("[Epicentrk] 'product_card' selector is missing in config!")
                    break

                cards = await page.query_selector_all(card_sel)
                for card in cards:
                    try:
                        title_sel = selectors.get("title")
                        price_sel = selectors.get("price")
                        url_sel = selectors.get("product_url")
                        
                        if not all([title_sel, price_sel, url_sel]):
                            continue

                        title_node = await card.query_selector(title_sel)
                        price_node = await card.query_selector(price_sel)
                        url_node = await card.query_selector(url_sel)
                        if not all([title_node, price_node, url_node]): continue
                        
                        title = (await title_node.inner_text()).strip()
                        price = self.parse_price(await price_node.inner_text())
                        href = await url_node.get_attribute("href")
                        if not href or price is None: continue
                        
                        products.append(self._create_raw(title, price, urljoin(base_url, href), "epicentrk"))
                    except: continue
                
                next_btn = await page.query_selector(selectors.get("next_page"))
                if not next_btn: break
                current_url = urljoin(base_url, await next_btn.get_attribute("href"))
            
            await browser.close()
        return products

    async def _search_httpx(self, query: str, pages: int, skip_urls: set | None = None, stop_event=None) -> list[RawProduct]:
        import httpx
        from bs4 import BeautifulSoup
        cfg = self.config.get("marketplaces", {}).get("epicentrk", {})
        base_url = cfg.get("base_url")
        search_template = cfg.get("search_url")
        selectors = cfg.get("selectors", {})
        
        products: list[RawProduct] = []
        current_url = search_template.format(query=quote_plus(query))
        headers = {"User-Agent": self.get_random_user_agent()}
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=headers) as client:
            for _ in range(int(pages)):
                if stop_event and stop_event.is_set():
                    logger.info("[Epicentrk] Stop requested.")
                    break
                response = await client.get(current_url)
                if response.status_code != 200: break
                soup = BeautifulSoup(response.text, "html.parser")
                cards = soup.select(selectors.get("product_card"))
                page_found = 0
                for card in cards:
                    t_node = card.select_one(selectors.get("title"))
                    p_node = card.select_one(selectors.get("price"))
                    u_node = card.select_one(selectors.get("product_url"))
                    if not all([t_node, p_node, u_node]): continue
                    
                    price = self.parse_price(p_node.get_text())
                    if price:
                        products.append(self._create_raw(t_node.get_text(strip=True), price, urljoin(base_url, u_node.get("href")), "epicentrk"))
                        page_found += 1
                
                logger.info(f"[Epicentrk] Page {_ + 1}: Found {page_found} products.")
                
                nxt = soup.select_one(selectors.get("next_page"))
                if not nxt or not nxt.get("href"): break
                current_url = urljoin(base_url, nxt.get("href"))
        return products

    def _create_raw(self, title, price, url, mp):
        return RawProduct(
            title=title, price=price, currency="UAH", url=url, marketplace=mp,
            brand=None, model=None, raw_specs={}, description=None,
            image_url=None, availability=None, rating=None, reviews_count=None,
            category_path=None, scraped_at=datetime.now(timezone.utc)
        )

    async def get_product_details(self, url: str) -> RawProduct | None:
        import httpx
        from bs4 import BeautifulSoup
        
        headers = {"User-Agent": self.get_random_user_agent()}
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=headers) as client:
                response = await client.get(url)
                if response.status_code != 200: return None
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Title
                title = ""
                og_title = soup.select_one("meta[property='og:title']")
                if og_title: title = (og_title.get("content") or "").strip()
                if not title: title = (soup.title.string or "").strip() if soup.title else ""
                
                # Price - Epicentr uses itemprop='price' or specific classes
                price = 0.0
                p_node = soup.select_one("[itemprop='price']") or soup.select_one(".p-price__main")
                if p_node:
                    price = self.parse_price(p_node.get_text() or p_node.get("content") or "0") or 0.0
                
                return self._create_raw(title or "Unknown Epicentr Product", price, url, "epicentrk")
        except Exception as e:
            logger.error(f"[Epicentrk] Error getting details for {url}: {e}")
            return None

    def parse_price(self, raw_text: str) -> float | None:
        if not raw_text: return None
        cleaned = "".join(c for c in raw_text if c.isdigit() or c in ".,")
        cleaned = cleaned.replace(",", ".")
        try: return float(cleaned)
        except: return None

    def detect_captcha(self, page) -> bool:
        return False
