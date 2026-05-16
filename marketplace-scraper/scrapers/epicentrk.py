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

    async def search_products(self, query: str, pages: int = 1, skip_urls: set[str] = None, stop_event=None, skip_out_of_stock: bool = True) -> list[RawProduct]:
        method = self.config.get("method_preference", "Auto")
        if method == "Browser":
            return await self._search_playwright(query, pages, skip_urls, stop_event=stop_event, skip_out_of_stock=skip_out_of_stock)
        return await self._search_httpx(query, pages, skip_urls, stop_event=stop_event, skip_out_of_stock=skip_out_of_stock)

    async def _search_playwright(self, query: str, pages: int = 1, skip_urls: set[str] = None, stop_event=None, skip_out_of_stock: bool = True) -> list[RawProduct]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return await self._search_httpx(query, pages, skip_urls, stop_event=stop_event, skip_out_of_stock=skip_out_of_stock)

        cfg = self.config.get("marketplaces", {}).get("epicentrk", {})
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
                    logger.info("[Epicentrk] Stop requested.")
                    break
                if has_reached_out_of_stock: break
                await page.goto(current_url, wait_until="networkidle")
                await self.wait_for_captcha(page)
                await self.auto_scroll_async(page)
                await page.wait_for_timeout(2000)

                # B17 fix: safety guard against missing selectors
                # Robust card discovery: try config first, then fallback to common Epicentr classes
                card_sel = selectors.get("product_card") or '.card'
                if not card_sel:
                    logger.error("[Epicentrk] 'product_card' selector is missing in config!")
                    break
                
                # Wait for at least one card to appear
                try:
                    # Try more specific first, then a broad one
                    await page.wait_for_selector(f"{card_sel}, .card, .p-card, .goods-tile", timeout=10000)
                except:
                    logger.warning(f"[Epicentrk] Timeout waiting for cards on {current_url}. Page might be empty.")
                
                cards = await page.query_selector_all(card_sel)
                if not cards:
                    # Fallback attempt if config selector is stale
                    cards = await page.query_selector_all('.card, .p-card, .goods-tile')
                    if cards:
                        logger.info(f"[Epicentrk] Config selector '{card_sel}' failed, but found {len(cards)} items using fallback classes.")

                logger.info(f"[Epicentrk] Discovered {len(cards)} products on page {p_idx+1}.")
                if not cards:
                    # Diagnostics: log a snippet of HTML if zero cards found
                    body_text = await page.evaluate("() => document.body.innerText.substring(0, 500)")
                    logger.info(f"[Epicentrk] Diagnostics: Page begins with: {body_text}")
                
                for card in cards:
                    try:
                        # Use JS for atomic data and high-precision markers
                        data = await card.evaluate("""(node) => {
                            const find = (sel) => node.querySelector(sel);
                            const text = node.innerText;
                            
                            // 1. URL & Link (Epicentr often has links deep or on the name)
                            const a = find('a[href*="/shop/"]') || find('a[href*="/ua/"]') || find('a');
                            const href = a ? a.getAttribute('href') : null;
                            
                            // 2. Title - check name classes first
                            const titleEl = find('.card__name') || find('.p-card__title') || find('[itemprop="name"]') || a;
                            const title = titleEl ? titleEl.innerText.trim() : '';
                            
                            // 3. Price - find common sum classes
                            const priceEl = find('.card__price-sum') || find('.p-price__main') || find('.card__price-sum-main') || find('[itemprop="price"]');
                            let priceText = priceEl ? priceEl.innerText : "";
                            
                            // Fallback for price if main node has zero text (likely empty span)
                            if (!priceText.trim()) {
                                const anyPrice = find('[class*="price"]');
                                if (anyPrice) priceText = anyPrice.innerText;
                            }
                            
                            // 4. Ad Detection (User Markers)
                            const adSpan = find('span._P14qTLgW');
                            const isAd = (adSpan && adSpan.innerText.includes('Реклама')) || text.includes('Реклама');
                            
                            // 5. Stock Detection (User Markers)
                            let availability = 'InStock';
                            if (text.includes('Немає в наявності') || text.includes('Закінчився')) {
                                availability = 'OutOfStock';
                            }
                            
                            return { href, title, priceText, isAd, availability };
                        }""")
                        
                        if data.get('isAd'):
                            # logger.debug(f"[Epicentrk] Skipping Ad: {data['title']}")
                            continue
                        
                        if not data['href']:
                            logger.warning(f"[Epicentrk] Skipping card: No URL found for '{data['title']}'")
                            continue
                        
                        if not data['title']:
                            continue
                        
                        if skip_out_of_stock and data['availability'] == "OutOfStock":
                            logger.info(f"[Epicentrk] Hit Out of Stock at '{data['title']}'. Stopping pagination.")
                            has_reached_out_of_stock = True
                            break

                        price = self.parse_price(data['priceText'])
                        if price is None:
                            logger.warning(f"[Epicentrk] Skipping '{data['title']}': Could not parse price from '{data['priceText']}'")
                            continue
                        
                        products.append(
                            RawProduct(
                                title=data['title'],
                                price=price,
                                currency="UAH",
                                url=urljoin(base_url, data['href']),
                                marketplace="epicentrk",
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
                    logger.warning("[Epicentrk] Pagination stuck on same URL. Stopping.")
                    break
                current_url = nxt_url
            
            await browser.close()
        return products

    async def _search_httpx(self, query: str, pages: int, skip_urls: set | None = None, stop_event=None, skip_out_of_stock: bool = True) -> list[RawProduct]:
        import httpx
        from bs4 import BeautifulSoup
        cfg = self.config.get("marketplaces", {}).get("epicentrk", {})
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
                    logger.info("[Epicentrk] Stop requested.")
                    break
                if has_reached_out_of_stock: break
                response = await client.get(current_url)
                if response.status_code != 200: break
                soup = BeautifulSoup(response.text, "html.parser")
                cards = soup.select(selectors.get("product_card"))
                page_found = 0
                for card in cards:
                    # Ad check
                    ad_span = card.select_one("span._P14qTLgW")
                    if ad_span and "Реклама" in ad_span.get_text(): 
                        continue
                    
                    t_node = card.select_one(selectors.get("title"))
                    p_node = card.select_one(selectors.get("price"))
                    u_node = card.select_one(selectors.get("product_url"))
                    if not all([t_node, p_node, u_node]): continue
                    
                    # Stock check
                    card_text = card.get_text()
                    availability = "InStock"
                    if "Немає в наявності" in card_text or "Закінчився" in card_text:
                        availability = "OutOfStock"
                    
                    if skip_out_of_stock and availability == "OutOfStock":
                        self.logger.info(f"[Epicentrk HTTPX] Hit Out of Stock at '{t_node.get_text(strip=True)}'. Stopping pagination.")
                        has_reached_out_of_stock = True
                        break

                    price = self.parse_price(p_node.get_text())
                    if price:
                        products.append(
                            RawProduct(
                                title=t_node.get_text(strip=True),
                                price=price,
                                currency="UAH",
                                url=urljoin(base_url, u_node.get("href")),
                                marketplace="epicentrk",
                                brand=None, raw_specs={}, description=None,
                                image_url=None, availability=availability,
                                rating=None, reviews_count=None, category_path=None,
                                scraped_at=datetime.now(timezone.utc)
                            )
                        )
                        page_found += 1
                
                if has_reached_out_of_stock: break
                logger.info(f"[Epicentrk] Page {_ + 1}: Found {page_found} products.")
                
                nxt = soup.select_one(selectors.get("next_page"))
                if not nxt or not nxt.get("href"): break
                nxt_url = urljoin(base_url, nxt.get("href"))
                if nxt_url == current_url: 
                    logger.warning("[Epicentrk] Next page URL is same as current. Stopping.")
                    break
                current_url = nxt_url
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
