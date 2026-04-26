from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.parse import quote_plus, urljoin, urlparse
from pathlib import Path

from core.models import RawProduct
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class RozetkaScraper(BaseScraper):
    def __init__(self, db=None, config_path: str = "config.yaml", captcha_callback=None) -> None:
        super().__init__(marketplace_name="rozetka", config_path=config_path, captcha_callback=captcha_callback)
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
            logger.error("Playwright not installed.")
            return []

        cfg = self.config.get("marketplaces", {}).get("rozetka", {})
        base_url = cfg.get("base_url", "https://rozetka.com.ua")
        search_template = cfg.get("search_url", "https://rozetka.com.ua/ua/search/?text={query}")
        selectors = cfg.get("selectors", {})
        
        card_sel = selectors.get("product_card")
        title_sel = selectors.get("title") or ".goods-tile__title"
        price_sel = selectors.get("price") or ".goods-tile__price-value"
        url_sel = selectors.get("product_url") or ".goods-tile__heading"
        
        products: list[RawProduct] = []
        if query.startswith("http"):
            current_url = query
        else:
            current_url = search_template.format(query=quote_plus(query))
        total_pages = int(pages)

        async with async_playwright() as p:
            # Use a local directory for persistent profile data
            user_data_dir = str(Path("data/browser_profile").resolve())
            
            browser_context = await p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-infobars",
                    "--disable-dev-shm-usage"
                ],
                ignore_default_args=["--enable-automation"],
                viewport={"width": 1280, "height": 800},
                user_agent=self.get_random_user_agent()
            )
            
            # Deeper Stealth & WebGL Masking
            await browser_context.add_init_script("""
                // WebGL Masking
                const getParameter = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(parameter) {
                    if (parameter === 37445) return 'Intel Inc.';
                    if (parameter === 37446) return 'Intel(R) Iris(TM) Plus Graphics 640';
                    return getParameter(parameter);
                };

                // Remove CDC string from window name
                Object.defineProperty(window, 'name', { get: () => '' });
                
                // Hide Playwright specific bindings
                delete navigator.__proto__.webdriver;
                
                // Final mask for webdriver
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            """)
            
            await self.anti_bot.apply_stealth_async(browser_context)
            page = browser_context.pages[0] if browser_context.pages else await browser_context.new_page()
            
            # Initial visit to landing page to "warm up" session
            logger.info("[Rozetka] Warming up session on landing page...")
            await page.goto(base_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)
                
            timeout = 60000 
            page_index = 0
            while page_index < total_pages:
                logger.info(f"[Rozetka] Navigating to page {page_index+1}: {current_url}")
                await page.goto(current_url, wait_until="networkidle", timeout=timeout)
                
                # Active Captcha/Spinner Wait
                await self.wait_for_captcha(page)
                
                # Check for "Skeleton" (Lazy-loading placeholders)
                for attempt in range(2):
                    if stop_event and stop_event.is_set(): break
                    try:
                        content = await page.content()
                        if "skeleton" in content.lower() or "placeholder" in content.lower():
                             logger.info(f"[Rozetka] Skeletons persist. Auto-reloading page (Attempt {attempt+1}/2)...")
                             await page.reload(wait_until="networkidle")
                             await self.wait_for_captcha(page)
                             await page.wait_for_timeout(3000)
                        else:
                            break
                    except Exception as e:
                        if "closed" in str(e).lower(): break
                        raise e
                
                # Check for "Empty results"
                if "Нічого не знайдено" in await page.content():
                    logger.warning(f"[Rozetka] No results for '{query}'")
                    break

                # Ensure cards are loaded
                try:
                    await page.wait_for_selector("li.catalog-grid__cell, div.goods-tile, .goods-tile", timeout=15000)
                except:
                    logger.warning("[Rozetka] Timeout waiting for cards.")

                selectors_to_try = [
                    "li.catalog-grid__cell", 
                    "div.goods-tile", 
                    "rz-grid-list li", 
                    ".catalog-grid__cell",
                    "a.goods-tile__heading"
                ]
                cards = []
                for sel in selectors_to_try:
                    cards = await page.query_selector_all(sel)
                    if cards:
                        logger.info(f"[Rozetka] Found {len(cards)} cards with {sel}")
                        break
                
                if not cards:
                    cards = await page.query_selector_all(card_sel)

                added_on_page = 0
                for card in cards:
                    if stop_event and stop_event.is_set(): break
                    try:
                        title_node = await card.query_selector(title_sel) or await card.query_selector(".goods-tile__title")
                        price_node = await card.query_selector(price_sel) or await card.query_selector(".goods-tile__price-value")
                        url_node = await card.query_selector(url_sel) or await card.query_selector("a.goods-tile__heading")
                        
                        if not title_node or not url_node:
                            continue
                            
                        title_text = (await title_node.inner_text()).strip()
                        href = await url_node.get_attribute("href")
                        
                        price_text = ""
                        if price_node:
                            price_text = await price_node.inner_text()
                        else:
                            alt_price = await card.query_selector(".goods-tile__price")
                            if alt_price: price_text = await alt_price.inner_text()
                            
                        price_val = self.parse_price(price_text)
                        
                        if not href or price_val is None:
                            continue
                            
                        clean_url = self._clean_url(urljoin(base_url, href))
                        products.append(self._create_raw(title_text, price_val, clean_url, "rozetka"))
                        added_on_page += 1
                    except Exception:
                        continue

                logger.info(f"[Rozetka] Successfully extracted {added_on_page} products from page {page_index+1}")

                # Next page
                page_index += 1
                if page_index >= total_pages or (stop_event and stop_event.is_set()):
                    break
                    
                try:
                    next_btn = await page.query_selector(".pagination__direction--forward")
                    if not next_btn:
                        break
                    
                    current_url = urljoin(base_url, await next_btn.get_attribute("href"))
                    await page.wait_for_timeout(2000)
                except Exception as e:
                    if "closed" in str(e).lower(): break
                    raise e

            try:
                await browser_context.close()
            except:
                pass
        return products

    async def _search_httpx(self, query: str, pages: int = 1, skip_urls: set[str] = None, stop_event=None) -> list[RawProduct]:
        """B19 fix: was missing — caused AttributeError when method_preference != 'Browser'.
        Uses Rozetka's internal JSON search API (same endpoint as their Angular frontend).
        """
        import httpx

        cfg = self.config.get("marketplaces", {}).get("rozetka", {})
        base_url = cfg.get("base_url", "https://rozetka.com.ua")
        api_url = "https://search.rozetka.com.ua/ua/search/api/v6/"

        if query.startswith("http"):
            # Direct URL mode — httpx cannot render Angular; fall back to a warning
            logger.warning("[Rozetka] httpx mode does not support direct URLs. Returning empty.")
            return []

        products: list[RawProduct] = []
        headers = {
            "User-Agent": self.get_random_user_agent(),
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=headers) as client:
            for page_idx in range(1, int(pages) + 1):
                if stop_event and stop_event.is_set():
                    logger.info("[Rozetka] Stop requested.")
                    break
                try:
                    resp = await client.get(api_url, params={"text": query, "page": page_idx})
                    resp.raise_for_status()
                    data = resp.json()
                    items = data.get("data", {}).get("goods", []) or []
                    if not items:
                        break
                    for item in items:
                        title = item.get("title", "").strip()
                        price_raw = item.get("price") or item.get("sell_price") or 0
                        url = item.get("href") or item.get("url") or ""
                        if not title or not url:
                            continue
                        price_val = self.parse_price(str(price_raw))
                        if price_val is None:
                            continue
                            
                        clean_url = self._clean_url(urljoin(base_url, url))
                        products.append(RawProduct(
                            title=title, price=price_val, currency="UAH",
                            url=clean_url, marketplace="rozetka",
                            brand=item.get("brand"), model=None, raw_specs={},
                            description=None, image_url=item.get("image_url"),
                            availability=None, rating=item.get("rating"),
                            reviews_count=item.get("comments_amount"),
                            category_path=None,
                            scraped_at=datetime.now(timezone.utc)
                        ))
                    logger.info("[Rozetka] httpx page %d: %d products", page_idx, len(items))
                except Exception as e:
                    logger.error("[Rozetka] httpx error on page %d: %s", page_idx, e)
                    break

        return products

    async def get_product_details(self, url: str) -> RawProduct | None:
        import httpx
        from bs4 import BeautifulSoup
        
        url = self._clean_url(url)
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
                
                # Price - Rozetka detail pages often have rz-product-main-info or meta
                price = 0.0
                p_meta = soup.select_one("meta[property='product:price:amount']")
                if p_meta:
                    price = self.parse_price(p_meta.get("content") or "0") or 0.0
                else:
                    # Generic price search
                    p_node = soup.select_one(".product-price__big") or soup.select_one(".p-price__main")
                    if p_node: price = self.parse_price(p_node.get_text()) or 0.0
                
                return self._create_raw(title or "Unknown Rozetka Product", price, url, "rozetka")
        except Exception as e:
            logger.error(f"[Rozetka] Error getting details for {url}: {e}")
            return None

    def parse_price(self, raw_text: str) -> float | None:
        if not raw_text: return None
        # B11 fix: handle thousands separators (dots or spaces)
        # Rozetka often uses dots as thousands separators: "4.200 грн"
        cleaned = raw_text.replace("\xa0", "").replace(" ", "").replace("грн", "").replace("₴", "").strip()
        
        # If there's a dot/comma, we need to decide if it's a decimal or thousands separator
        if "," in cleaned and "." in cleaned:
            # Both? Likely dot=thousands, comma=decimal: 4.200,50
            cleaned = cleaned.replace(".", "").replace(",", ".")
        elif "," in cleaned:
            # Just comma? Decimal.
            cleaned = cleaned.replace(",", ".")
        elif "." in cleaned:
            # Is it thousands or decimal? "4.200" vs "49.99"
            parts = cleaned.split(".")
            if len(parts[-1]) == 3: # 4.200 -> 4200
                cleaned = cleaned.replace(".", "")
            else: # 49.99 -> 49.99
                pass
                
        try:
            return float(cleaned)
        except:
            return None

    def detect_captcha(self, page) -> bool:
        return False

    def _clean_url(self, url: str) -> str:
        """Strips tracking tokens and junk from Rozetka URLs."""
        if not url: return ""
        # Cut at query params
        if "?" in url:
            url = url.split("?")[0]
        # Cut at fragment
        if "#" in url:
            url = url.split("#")[0]
        # Ensure trailing slash for consistency
        if not url.endswith("/"):
            url += "/"
        return url
