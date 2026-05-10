from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote_plus, urljoin
import logging

from core.models import RawProduct
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class PromScraper(BaseScraper):
    def __init__(self, db=None, config_path: str = "config.yaml", captcha_callback=None) -> None:
        super().__init__(marketplace_name="prom", config_path=config_path, captcha_callback=captcha_callback)
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

        cfg = self.config.get("marketplaces", {}).get(self.marketplace_name, {})
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
                if stop_event and stop_event.is_set(): break
                if has_reached_out_of_stock: break
                try:
                    await page.goto(current_url, wait_until="networkidle")
                    await self.wait_for_captcha(page)
                    await self.auto_scroll_async(page)
                    await page.wait_for_timeout(2000)

                    cards = await page.query_selector_all(selectors.get("product_card"))
                    if not cards:
                        for fb in ["[data-qaid='product_gallery'] > div", ".js-productad", "[data-qaid='product_block']", "a[href*='/p']"]:
                            cards = await page.query_selector_all(fb)
                            if cards:
                                logger.info(f"[Prom] Found {len(cards)} cards using fallback '{fb}'")
                                break

                    for card in cards:
                        if stop_event and stop_event.is_set(): break
                        try:
                            # Extract data using JS for precision
                            data = await card.evaluate("""(node) => {
                                const find = (sel) => node.querySelector(sel);
                                
                                // 1. Link & URL
                                const a = find('[data-qaid="product_link"]') || find('a[href*="/p"]') || (node.tagName === 'A' ? node : null);
                                const href = a ? a.getAttribute('href') : null;
                                
                                // 2. Title
                                const titleEl = find('[data-qaid="product_link"]') || find('.M3v0L') || find('a[title]') || a;
                                const title = titleEl ? titleEl.innerText.trim() : '';
                                
                                // 3. Price
                                const priceEl = find('[data-qaid="product_price"]') || find('.js-product-price');
                                const priceText = priceEl ? priceEl.innerText : "";
                                
                                // 4. Stock Detection (User Markers)
                                const buyBtn = find('[data-qaid="buy-button"]');
                                const seeBtn = find('[data-qaid="see_button"]');
                                const presence = find('[data-qaid="product_presence"]');
                                
                                let availability = 'InStock';
                                const presenceText = presence ? presence.innerText.toLowerCase() : '';
                                
                                if (seeBtn || presenceText.includes('недоступний') || presenceText.includes('немає')) {
                                    availability = 'OutOfStock';
                                } else if (buyBtn || presenceText.includes('наявності') || presenceText.includes('готовий')) {
                                    availability = 'InStock';
                                }
                                
                                return { href, title, priceText, availability };
                            }""")
                            
                            if not data['href'] or not data['title']: continue
                            
                            if skip_out_of_stock and data['availability'] == "OutOfStock":
                                logger.info(f"[Prom] Hit Out of Stock at '{data['title']}'. Stopping pagination.")
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
                                    marketplace="prom",
                                    brand=None, model=None, raw_specs={}, description=None,
                                    image_url=None, availability=data['availability'],
                                    rating=None, reviews_count=None, category_path=None,
                                    scraped_at=datetime.now(timezone.utc)
                                )
                            )
                        except Exception:
                            continue
                    
                    if has_reached_out_of_stock: break
                    if stop_event and stop_event.is_set(): break
                    next_btn = await page.query_selector(selectors.get("next_page"))
                    if not next_btn: break
                    current_url = urljoin(base_url, await next_btn.get_attribute("href"))
                except Exception as e:
                    if "closed" in str(e).lower(): break
                    logger.error(f"[Prom] Playwright error: {e}")
                    break
            
            try:
                await browser.close()
            except:
                pass
        return products

    async def _search_httpx(self, query: str, pages: int, skip_urls: set | None = None, stop_event=None, skip_out_of_stock: bool = True) -> list[RawProduct]:
        import httpx
        from bs4 import BeautifulSoup
        
        skip_urls = skip_urls or set()
        cfg = self.config.get("marketplaces", {}).get("prom", {})
        base_url = cfg.get("base_url", "https://prom.ua")
        search_template = cfg.get("search_url", "https://prom.ua/search?search_term={query}")
        selectors = cfg.get("selectors", {})

        card_sel = selectors.get("product_card")
        title_sel = selectors.get("title")
        price_sel = selectors.get("price")
        url_sel = selectors.get("product_url")
        image_sel = selectors.get("image")
        next_sel = selectors.get("next_page")

        if not all([card_sel, title_sel, price_sel, url_sel]):
            raise RuntimeError("Prom selectors are incomplete. Update config.yaml first.")

        requested_pages = max(1, int(pages))
        max_pages = int(cfg.get("pages_limit", requested_pages))
        total_pages = min(requested_pages, max_pages)

        if query.startswith("http"):
            current_url = query
        else:
            current_url = search_template.format(query=quote_plus(query))
        headers = {"User-Agent": self.get_random_user_agent()}
        products: list[RawProduct] = []

        has_reached_out_of_stock = False
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=headers) as client:
            for page_num in range(1, total_pages + 1):
                if stop_event and stop_event.is_set():
                    logger.info("[Prom] Stop requested in HTTPX loop.")
                    break
                if has_reached_out_of_stock: break
                
                response = await client.get(current_url)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")

                cards = soup.select(card_sel)
                if not cards:
                    for fb in ["[data-qaid='product_gallery'] > div", ".js-productad", "[data-qaid='product_block']", "a[href*='/p']"]:
                        cards = soup.select(fb)
                        if cards:
                            logger.info(f"[Prom] Found {len(cards)} cards using fallback '{fb}'")
                            break

                page_found = 0
                for card in cards:
                    title_node = card.select_one(title_sel) or card.select_one("[data-qaid='product_link']") or card.select_one(".M3v0L") or card.select_one("a[title]")
                    url_node = card.select_one(url_sel) or card.select_one("[data-qaid='product_link']") or card.select_one("a[href*='/p']")
                    price_node = card.select_one(price_sel) or card.select_one("[data-qaid='product_price']") or card.select_one(".js-product-price")

                    if not url_node and card.name == "a":
                        url_node = card
                    if not title_node and card.name == "a":
                        title_node = card

                    if title_node is None or url_node is None:
                        continue

                    href = url_node.get("href")
                    if not href:
                        continue
                    
                    if price_node is None:
                        # try parent fallback to find price if it's just an <a> tag
                        parent = card.parent
                        for _ in range(3):
                            if parent and parent.name != 'body':
                                price_node = parent.select_one(price_sel) or parent.select_one("[data-qaid='product_price']") or parent.select_one(".js-product-price")
                                if price_node: break
                                parent = parent.parent
                    product_url = urljoin(base_url, href)
                    if product_url in skip_urls:
                        continue

                    raw_price = price_node.get("data-qaprice") or price_node.get_text(" ", strip=True)
                    price = self.parse_price(raw_price or "")
                    if price is None:
                        continue

                    title = (title_node.get("title") or title_node.get_text(" ", strip=True)).strip()
                    if not title:
                        continue

                    image_url = None
                    if image_sel:
                        image_node = card.select_one(image_sel)
                        if image_node is not None:
                            image_url = (
                                image_node.get("src")
                                or image_node.get("data-src")
                                or (image_node.get("srcset", "").split(" ")[0] if image_node.get("srcset") else None)
                            )
                            if image_url:
                                image_url = urljoin(base_url, image_url)

                    # Stock Detection (User Markers)
                    buy_btn = card.select_one("[data-qaid='buy-button']")
                    see_btn = card.select_one("[data-qaid='see_button']")
                    presence = card.select_one("[data-qaid='product_presence']")
                    
                    availability = "InStock"
                    presence_text = presence.get_text().lower() if presence else ""
                    if see_btn or "недоступний" in presence_text or "немає" in presence_text:
                        availability = "OutOfStock"
                    elif buy_btn or "наявності" in presence_text:
                        availability = "InStock"
                    
                    if skip_out_of_stock and availability == "OutOfStock":
                        logger.info(f"[Prom HTTPX] Hit Out of Stock at '{title}'. Stopping pagination.")
                        has_reached_out_of_stock = True
                        break

                    products.append(
                        RawProduct(
                            title=title,
                            price=price,
                            currency="UAH",
                            url=product_url,
                            marketplace="prom",
                            brand=None,
                            model=None,
                            raw_specs={},
                            description=None,
                            image_url=image_url,
                            availability=availability,
                            rating=None,
                            reviews_count=None,
                            category_path=None,
                            scraped_at=datetime.now(timezone.utc),
                        )
                    )
                    page_found += 1

                logger.info(f"[Prom] Page {page_num}: Found {page_found} products.")

                if not next_sel:
                    break
                next_link = soup.select_one(next_sel)
                href = None if next_link is None else next_link.get("href")
                if not href:
                    break
                current_url = urljoin(base_url, href)
                self.random_delay()

        return products

    async def get_product_details(self, url: str) -> RawProduct | None:
        import httpx
        from bs4 import BeautifulSoup

        headers = {"User-Agent": self.get_random_user_agent()}
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=headers) as client:
                response = await client.get(url)
                if response.status_code != 200: return None
                soup = BeautifulSoup(response.text, "html.parser")

            title = ""
            og_title = soup.select_one("meta[property='og:title']")
            if og_title: title = (og_title.get("content") or "").strip()
            if not title: title = (soup.title.string or "").strip() if soup.title else ""

            # Price
            price = 0.0
            p_meta = soup.select_one("meta[property='product:price:amount']") or soup.select_one("meta[itemprop='price']")
            if p_meta:
                price = self.parse_price(p_meta.get("content") or "0") or 0.0
            else:
                # Fallback to specific data-qaprice or text search
                p_node = soup.select_one("[data-qaid='product_price']")
                if p_node: price = self.parse_price(p_node.get("data-qaprice") or p_node.get_text()) or 0.0

            image_url = None
            og_image = soup.select_one("meta[property='og:image']")
            if og_image: image_url = (og_image.get("content") or "").strip() or None

            return RawProduct(
                title=title or "Unknown Prom Product",
                price=price,
                currency="UAH",
                url=url,
                marketplace="prom",
                brand=None, model=None, raw_specs={}, description=None,
                image_url=image_url, availability=None, rating=None, reviews_count=None,
                category_path=None, scraped_at=datetime.now(timezone.utc),
            )
        except Exception as e:
            logger.error(f"[Prom] Error getting details for {url}: {e}")
            return None

    def parse_price(self, raw_text: str) -> float | None:
        cleaned = (
            raw_text.replace("\xa0", " ")
            .replace("грн", "")
            .replace("₴", "")
            .replace("/шт.", "")
            .replace("від", "")
            .strip()
        )
        number = "".join(ch for ch in cleaned if ch.isdigit() or ch in [".", ",", " "]).replace(" ", "")
        number = number.replace(",", ".")
        try:
            return float(number) if number else None
        except ValueError:
            return None

    def detect_captcha(self, page) -> bool:
        result = self.anti_bot.detect_captcha(page)
        return bool(result.get("detected"))
