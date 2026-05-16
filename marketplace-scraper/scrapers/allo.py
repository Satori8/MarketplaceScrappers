from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.parse import quote_plus, urljoin

from core.models import RawProduct
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class AlloScraper(BaseScraper):
    def __init__(self, db=None, config_path: str = "config.yaml", captcha_callback=None) -> None:
        super().__init__(marketplace_name="allo", config_path=config_path, captcha_callback=captcha_callback)
        self.db = db

    async def search_products(self, query: str, pages: int = 1, skip_urls: set[str] = None, stop_event=None, skip_out_of_stock: bool = True) -> list[RawProduct]:
        method = self.config.get("method_preference", "Auto")
        if method == "Browser":
            return await self._search_playwright(query, pages, skip_urls, stop_event=stop_event, skip_out_of_stock=skip_out_of_stock)
        return await self._search_httpx(query, pages, skip_urls, stop_event=stop_event, skip_out_of_stock=skip_out_of_stock)

    async def _search_playwright(self, query: str, pages: int, skip_urls: set | None = None, stop_event=None, skip_out_of_stock: bool = True) -> list[RawProduct]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return await self._search_httpx(query, pages, skip_urls)

        cfg = self.config.get("marketplaces", {}).get("allo", {})
        base_url = cfg.get("base_url")
        search_template = cfg.get("search_url")
        selectors = cfg.get("selectors", {})
        
        products: list[RawProduct] = []
        if query.startswith("http"):
            current_url = query
        else:
            current_url = search_template.format(query=quote_plus(query))

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(user_agent=self.get_random_user_agent())
            await self.anti_bot.apply_stealth_async(context)
            page = await context.new_page()
            
            has_reached_out_of_stock = False
            for p_idx in range(int(pages)):
                if stop_event and stop_event.is_set():
                    logger.info("[Allo] Stop requested.")
                    break
                if has_reached_out_of_stock: break
                await page.goto(current_url, wait_until="domcontentloaded", timeout=60000)
                await self.wait_for_captcha(page)
                await self.auto_scroll_async(page)
                await page.wait_for_timeout(2000)

                # B17 fix: safety guard against missing selectors
                card_sel = selectors.get("product_card")

                cards = await page.query_selector_all(card_sel) if card_sel else []
                if not cards:
                    for fb in ["div.products-layout__item", ".product-card", "a.product-card__title"]:
                        cards = await page.query_selector_all(fb)
                        if cards:
                            logger.info(f"[Allo] Found {len(cards)} cards using fallback '{fb}'")
                            break
                            
                for card in cards:
                    try:
                        # Extract data using JS for precision and speed
                        data = await card.evaluate("""(node) => {
                            const find = (sel) => node.querySelector(sel);
                            
                            // 1. Link & URL
                            const a = find('a.product-card__title') || (node.tagName === 'A' ? node : find('a'));
                            const href = a ? a.getAttribute('href') : null;
                            
                            // 2. Title
                            const title = a ? a.innerText.trim() : '';
                            
                            // 3. Price
                            const priceEl = find('.v-pb__cur .sum') || find('.price-box__cur') || find('.v-price-box__cur .sum');
                            const priceText = priceEl ? priceEl.innerText : "";
                            
                            // 4. Stock Detection (User Markers)
                            const buyBtn = find('.v-btn--cart');
                            const outOfStockBtn = find('.v-btn--out-stock');
                            const outOfStockSpan = find('.out-stock');
                            
                            let availability = 'InStock';
                            if (outOfStockBtn || outOfStockSpan || (buyBtn && buyBtn.title.includes('наличии'))) {
                                availability = 'OutOfStock';
                            } else if (buyBtn || (priceText && !outOfStockSpan)) {
                                availability = 'InStock';
                            }
                            
                            return { href, title, priceText, availability };
                        }""")
                        
                        if not data['href'] or not data['title']: continue
                        
                        
                        if skip_out_of_stock and data['availability'] == "OutOfStock":
                            logger.info(f"[Allo] Hit Out of Stock at '{data['title']}'. Stopping pagination.")
                            has_reached_out_of_stock = True
                            break

                        price = self.parse_price(data['priceText'])
                        if price is None: continue
                        
                        products.append(
                            RawProduct(
                                title=data['title'],
                                price=price,
                                currency="UAH",
                                url=urljoin(base_url, data['href']),
                                marketplace="allo",
                                brand=None, raw_specs={}, description=None,
                                image_url=None, availability=data['availability'],
                                rating=None, reviews_count=None, category_path=None,
                                scraped_at=datetime.now(timezone.utc)
                            )
                        )
                    except: continue
                
                nxt = await page.query_selector(selectors.get("next_page"))
                if not nxt: break
                nxt_url = urljoin(base_url, await nxt.get_attribute("href"))
                if nxt_url == current_url:
                    logger.warning("[Allo] Pagination stuck on same page. Stopping.")
                    break
                current_url = nxt_url
            
            await browser.close()
        return products

    async def _search_httpx(self, query: str, pages: int, skip_urls: set | None = None, stop_event=None, skip_out_of_stock: bool = True) -> list[RawProduct]:
        import httpx
        from bs4 import BeautifulSoup
        cfg = self.config.get("marketplaces", {}).get("allo", {})
        base_url = cfg.get("base_url")
        search_template = cfg.get("search_url")
        selectors = cfg.get("selectors", {})
        
        products: list[RawProduct] = []
        if query.startswith("http"):
            current_url = query
        else:
            current_url = search_template.format(query=quote_plus(query))
        headers = {"User-Agent": self.get_random_user_agent()}
        
        has_reached_out_of_stock = False
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=headers) as client:
            for _ in range(int(pages)):
                if stop_event and stop_event.is_set():
                    logger.info("[Allo] Stop requested.")
                    break
                if has_reached_out_of_stock: break
                response = await client.get(current_url)
                if response.status_code != 200: break
                soup = BeautifulSoup(response.text, "html.parser")
                card_sel = selectors.get("product_card")
                cards = soup.select(card_sel) if card_sel else []
                if not cards:
                    for fb in ["div.products-layout__item", ".product-card", "a.product-card__title"]:
                        cards = soup.select(fb)
                        if cards:
                            logger.info(f"[Allo] Found {len(cards)} cards using fallback '{fb}'")
                            break
                            
                page_count = 0
                has_reached_out_of_stock = False
                for card in cards:
                    title_sel = selectors.get("title")
                    price_sel = selectors.get("price")
                    url_sel = selectors.get("product_url")
                    
                    t_node = card.select_one(title_sel) if title_sel else None
                    p_node = card.select_one(price_sel) if price_sel else None
                    u_node = card.select_one(url_sel) if url_sel else None
                    
                    if not u_node and card.name == "a":
                        u_node = card
                    if not t_node and card.name == "a":
                        t_node = card
                        
                    if not t_node or not u_node:
                        t_node = card.select_one("a.product-card__title") or t_node
                        u_node = card.select_one("a.product-card__title") or u_node
                        if not t_node or not u_node: continue
                    
                    if not p_node:
                        p_node = card.select_one(".v-pb__cur .sum") or card.select_one(".price-box__cur")
                        if not p_node and u_node == card:
                            parent = card.parent
                            for _ in range(3):
                                if parent and parent.name != 'body':
                                    p_node = parent.select_one(".v-pb__cur .sum") or parent.select_one(".price-box__cur")
                                    if p_node: break
                                    parent = parent.parent

                    price_text = p_node.get_text() if p_node else ""
                    price = self.parse_price(price_text) or 0.0

                    # Stock Detection (User Markers)
                    buy_btn = card.select_one(".v-btn--cart")
                    out_stock_btn = card.select_one(".v-btn--out-stock")
                    out_stock_span = card.select_one(".out-stock")
                    
                    availability = "InStock"
                    if out_stock_btn or out_stock_span or (buy_btn and "наявності" in (buy_btn.get("title") or "")):
                        availability = "OutOfStock"
                    
                    if skip_out_of_stock and availability == "OutOfStock":
                        logger.info(f"[Allo HTTPX] Hit Out of Stock at '{t_node.get_text(strip=True)}'. Stopping pagination.")
                        has_reached_out_of_stock = True
                        break

                    products.append(
                        RawProduct(
                            title=t_node.get_text(strip=True),
                            price=price,
                            currency="UAH",
                            url=urljoin(base_url, u_node.get("href")),
                            marketplace="allo",
                            brand=None,
                            raw_specs={},
                            description=None,
                            image_url=None,
                            availability=availability,
                            rating=None,
                            reviews_count=None,
                            category_path=None,
                            scraped_at=datetime.now(timezone.utc)
                        )
                    )
                    page_count += 1
                
                logger.info(f"[Allo] Page {_ + 1}: Found {page_count} products.")
                
                nxt = soup.select_one(selectors.get("next_page"))
                if not nxt or not nxt.get("href"): break
                current_url = urljoin(base_url, nxt.get("href"))
        return products

    def _create_raw(self, title, price, url, mp):
        return RawProduct(
            title=title, price=price, currency="UAH", url=url, marketplace=mp,
            brand=None, raw_specs={}, description=None,
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
                
                # Price - Allo detail page selectors vary, trying common ones
                price = 0.0
                p_node = soup.select_one(".v-pb__cur .sum") or soup.select_one(".price-box__cur")
                if p_node:
                    price = self.parse_price(p_node.get_text()) or 0.0
                
                return self._create_raw(title or "Unknown Allo Product", price, url, "allo")
        except Exception as e:
            logger.error(f"[Allo] Error getting details for {url}: {e}")
            return None

    def parse_price(self, raw_text: str) -> float | None:
        if not raw_text: return None
        cleaned = "".join(c for c in raw_text if c.isdigit() or c in ".,")
        cleaned = cleaned.replace(",", ".")
        try: return float(cleaned)
        except: return None

    def detect_captcha(self, page) -> bool:
        return False
