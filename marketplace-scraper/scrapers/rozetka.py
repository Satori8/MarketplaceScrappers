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

    async def search_products(self, query: str, pages: int = 1, skip_urls: set[str] = None, stop_event=None, skip_out_of_stock: bool = True) -> list[RawProduct]:
        method = self.config.get("method_preference", "Auto")
        if method == "Browser":
            return await self._search_playwright(query, pages, skip_urls, stop_event=stop_event, skip_out_of_stock=skip_out_of_stock)
        return await self._search_httpx(query, pages, skip_urls, stop_event=stop_event, skip_out_of_stock=skip_out_of_stock)

    async def _search_playwright(self, query: str, pages: int = 1, skip_urls: set[str] = None, stop_event=None, skip_out_of_stock: bool = True) -> list[RawProduct]:
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
        has_reached_out_of_stock = False

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
                if has_reached_out_of_stock: break
                logger.info(f"[Rozetka] Navigating to page {page_index+1}: {current_url}")
                await page.goto(current_url, wait_until="networkidle", timeout=timeout)
                
                # Active Captcha/Spinner Wait
                await self.wait_for_captcha(page)
                await self.auto_scroll_async(page)
                
                # Check for "Skeleton" (Lazy-loading placeholders)
                for attempt in range(2):
                    if stop_event and stop_event.is_set(): break
                    try:
                        # Success condition: product cards or anything looking like a product block (price + link)
                        results = await page.evaluate("""() => {
                            const has_tile = document.querySelectorAll('li.catalog-grid__cell, div.goods-tile, .goods-tile, .catalog-grid .catalog-grid__cell, .tile').length > 0;
                            if (has_tile) return { present: true, skeleton: false };
                            
                            // Heuristic: any block with a currency symbol and a product link
                            const suspects = document.querySelectorAll('li, div, article');
                            for (let s of suspects) {
                                if (s.innerText.includes('₴') && s.querySelector('a[href*="/p/"]')) {
                                    return { present: true, skeleton: false };
                                }
                            }
                            
                            const s = document.querySelector('.goods-tile--skeleton, .skeleton, [class*="skeleton"]');
                            const has_skeleton = !!(s && s.offsetParent !== null && s.innerText.length < 50);
                            return { present: false, skeleton: has_skeleton };
                        }""")
                        
                        if results['present']: 
                            break

                        if results['skeleton']:
                             logger.info(f"[Rozetka] Skeletons visible. Auto-reloading page (Attempt {attempt+1}/2)...")
                             await page.reload(wait_until="networkidle")
                             await self.wait_for_captcha(page)
                             await page.wait_for_timeout(4000)
                        else:
                             # No cards and no skeletons? Might be a very slow load or different layout
                             await page.evaluate("window.scrollTo(0, 400)")
                             await page.wait_for_timeout(1500)
                             break
                    except Exception as e:
                        if "closed" in str(e).lower(): break
                        raise e
                
                # Check for "Empty results"
                if "Нічого не знайдено" in await page.content():
                    logger.warning(f"[Rozetka] No results for '{query}'")
                    break

                # Ensure cards are loaded with broader selectors for subdomains
                try:
                    await page.wait_for_selector("li.catalog-grid__cell, div.goods-tile, .goods-tile, rz-product-tile, rz-catalog-tile, .item, .catalog-grid__cell, a[href*='/p/']", timeout=10000)
                except:
                    pass

                # Deep Heuristic Discovery: Find everything that looks like a product
                # We find links to products and walk up to the container that has a price.
                cards = []
                try:
                    js_discovery = """() => {
                        // Check for specific web components first
                        const components = document.querySelectorAll('rz-product-tile, rz-catalog-tile, .goods-tile, .item');
                        if (components.length > 2) {
                            return Array.from(components).map(c => {
                                if (!c.id) c.id = 'rz-detected-' + Math.random().toString(36).substr(2, 9);
                                return '#' + c.id;
                            });
                        }

                        const productLinks = document.querySelectorAll('a[href*="/p"]');
                        const containers = new Set();
                        for (let a of productLinks) {
                            const hr = a.getAttribute('href') || '';
                            if (!hr.includes('/p')) continue;
                            
                            let curr = a.parentElement;
                            let depth = 0;
                            while (curr && curr.tagName !== 'BODY' && depth < 8) {
                                const text = curr.innerText;
                                const tagName = curr.tagName.toLowerCase();
                                if (tagName === 'footer' || tagName === 'header' || tagName === 'nav') break;
                                
                                if ((text.includes('₴') || text.includes('грн')) && curr.offsetHeight > 150 && text.length > 50) {
                                    containers.add(curr);
                                    break;
                                }
                                curr = curr.parentElement;
                                depth++;
                            }
                        }
                        return Array.from(containers).map(c => {
                             if (!c.id) c.id = 'rz-discovered-' + Math.random().toString(36).substr(2, 9);
                             return '#' + c.id;
                        });
                    }"""
                    card_selectors = await page.evaluate(js_discovery)
                    for sel in card_selectors:
                        node = await page.query_selector(sel)
                        if node: cards.append(node)
                    
                    if cards:
                        logger.info(f"[Rozetka] Discovered {len(cards)} products (Heuristic).")
                except Exception as e:
                    logger.error(f"[Rozetka] Deep Discovery failed: {e}")

                if not cards:
                    # Final fallback to existing selectors
                    selectors_to_try = [
                        "li.catalog-grid__cell", 
                        "rz-product-tile",
                        "rz-catalog-tile",
                        "div.goods-tile", 
                        ".item",
                        ".catalog-grid__cell",
                        ".catalog-grid .catalog-grid__cell",
                        ".tile",
                        "a[href*='/p/']"
                    ]
                    for sel in selectors_to_try:
                        try:
                            found = await page.query_selector_all(sel)
                            if found and len(found) >= 1:
                                cards = found
                                break
                        except: continue

                added_on_page = 0
                for card in cards:
                    if stop_event and stop_event.is_set(): break
                    try:
                        # Extract data using JS to handle nesting and Shadow DOM properly
                        data = await card.evaluate("""(node) => {
                            const find = (sel) => {
                                try {
                                    return node.querySelector(sel) || 
                                           (node.shadowRoot ? node.shadowRoot.querySelector(sel) : null);
                                } catch (e) { return null; }
                            };
                            
                            const text = (node.innerText || node.textContent || '').toLowerCase();
                            const html = (node.innerHTML || '').toLowerCase();
                            
                            // 1. Link & URL
                            const a = find('a[href*="/p"]') || find('a');
                            const href = a ? a.getAttribute('href') : (node.getAttribute('data-url') || node.getAttribute('data-href'));
                            
                            // 2. Title
                            const titleEl = find('.tile-title') || find('.goods-tile__title') || find('[class*="title"]') || find('a[title]') || a;
                            const title = titleEl ? titleEl.innerText.trim() : '';
                            
                            // 3. Price
                            const priceEl = find('.tile-price') || find('.price') || find('[class*="price"]') || find('.product-price__big');
                            const priceText = priceEl ? priceEl.innerText.trim() : "";
                            
                            // 4. High-Precision Ad Detection (User Markers)
                            const sponsoredLink = find('a[rel*="sponsored"]');
                            const adSpan = find('span.color-black-60');
                            const isAd = !!sponsoredLink || 
                                         (adSpan && adSpan.innerText.includes('Реклама')) || 
                                         text.includes('реклама');
                            
                            // 5. High-Precision Stock Detection (User Markers)
                            const sellStatus = find('rz-tile-sell-status') || find('.status-label');
                            let availability = 'InStock';
                            
                            const isTileDisabled = node.classList.contains('tile-disabled') || !!find('.tile-disabled');
                            const statusText = sellStatus ? sellStatus.innerText.toLowerCase() : '';
                            const isGrayStatus = sellStatus && sellStatus.classList.contains('gray');
                            
                            if (isTileDisabled || isGrayStatus || statusText.includes('немає') || statusText.includes('закінчився')) {
                                availability = 'OutOfStock';
                            } else if (text.includes('під замовлення') || html.includes('toorder')) {
                                availability = 'ToOrder';
                            }
                            
                            return { 
                                href, 
                                title: title || node.innerText.split('\\n')[0].substring(0, 100), 
                                priceText: priceText || node.innerText,
                                isAd: !!isAd,
                                availability,
                                tag: node.tagName
                            };
                        }""")
                        
                        if data.get('isAd'):
                            logger.info(f"[Rozetka] Skipping Ad Product: {data.get('title')}")
                            continue

                        availability = data.get('availability') or "InStock"
                        
                        if skip_out_of_stock and availability == "OutOfStock":
                            logger.info(f"[Rozetka] Hit Out of Stock at '{data.get('title')}'. Stopping pagination.")
                            has_reached_out_of_stock = True
                            break

                        href = data.get('href')
                        title_text = data.get('title')
                        price_text = data.get('priceText')

                        if not href or '/p' not in href: 
                            # logger.debug(f"[Rozetka] Card skipped: No product link found in {data.get('tag')}")
                            continue

                        if not title_text or len(title_text) < 3:
                            logger.warning(f"[Rozetka] Card skipped: Title too short")
                            continue
                            
                        price_val = self.parse_price(price_text) or 0
                            
                        clean_url = self._clean_url(urljoin(base_url, href))
                        products.append(self._create_raw(title_text, price_val, clean_url, availability))
                        added_on_page += 1
                    except Exception as e:
                        logger.warning(f"[Rozetka] Extraction error on card: {e}")
                        continue
                
                if not products and cards:
                    try:
                        # Final log for debugging if everything failed
                        text_sample = await page.evaluate("document.body.innerText.substring(0, 500)")
                        logger.info(f"[Rozetka] Final extraction fail. Body text: {text_sample.replace('\\n', ' ')}")
                    except: pass

                logger.info(f"[Rozetka] Successfully extracted {added_on_page} products from page {page_index+1}")

                # Next page
                page_index += 1
                if page_index >= total_pages or (stop_event and stop_event.is_set()):
                    break
                    
                try:
                    # Rozetka has multiple pagination styles, try targeted and generic
                    next_btn = await page.query_selector("a[data-testid='pagination_to_next_page'], .pagination__direction--forward, a.arrow-right:not(.disabled)")
                    if not next_btn:
                        break
                    
                    # Check if button is visually/functionally disabled
                    is_disabled = await next_btn.evaluate("el => el.classList.contains('disabled') || el.getAttribute('aria-disabled') === 'true'")
                    if is_disabled:
                        logger.info("[Rozetka] Reached last page (Next button disabled).")
                        break

                    current_url = urljoin(base_url, await next_btn.get_attribute("href"))
                    await page.wait_for_timeout(2000)
                except Exception as e:
                    if "closed" in str(e).lower(): break
                    logger.error(f"[Rozetka] Pagination error: {e}")
                    break

            try:
                await browser_context.close()
            except:
                pass
        
        # Deduplicate by URL
        seen_urls = set()
        final_products = []
        for p in products:
            if p.url not in seen_urls:
                seen_urls.add(p.url)
                final_products.append(p)
        
        return final_products

    async def _search_httpx(self, query: str, pages: int = 1, skip_urls: set[str] = None, stop_event=None, skip_out_of_stock: bool = True) -> list[RawProduct]:
        """Uses Rozetka's internal JSON search API (same endpoint as their Angular frontend).
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
                        
                    has_reached_out_of_stock = False
                    for item in items:
                        title = item.get("title", "").strip()
                        price_raw = item.get("price") or item.get("sell_price") or 0
                        url = item.get("href") or item.get("url") or ""
                        if not title or not url:
                            continue
                        
                        # Stock Check
                        sell_status = item.get("sell_status", "available")
                        availability = "OutOfStock" if sell_status == "unavailable" else "InStock"
                        if skip_out_of_stock and availability == "OutOfStock":
                             logger.info(f"[Rozetka HTTPX] Hit Out of Stock at '{title}'. Stopping pagination.")
                             has_reached_out_of_stock = True
                             break

                        price_val = self.parse_price(str(price_raw))
                        if price_val is None:
                            continue
                            
                        clean_url = self._clean_url(urljoin(base_url, url))
                        products.append(RawProduct(
                            title=title, price=price_val, currency="UAH",
                            url=clean_url, marketplace="rozetka",
                            brand=item.get("brand"), model=None, raw_specs={},
                            description=None, image_url=item.get("image_url"),
                            availability=availability, rating=item.get("rating"),
                            reviews_count=item.get("comments_amount"),
                            category_path=None,
                            scraped_at=datetime.now(timezone.utc)
                        ))
                    
                    if has_reached_out_of_stock: break
                    logger.info(f"[Rozetka] httpx page {page_idx}: Found {len(items)} products")
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
    
    def _create_raw(self, title: str, price: float, url: str, availability: str = "InStock") -> RawProduct:
        return RawProduct(
            title=title,
            price=price,
            currency="UAH",
            url=url,
            marketplace="rozetka",
            brand=None,
            model=None,
            raw_specs={},
            description=None,
            image_url=None,
            availability=availability,
            rating=None,
            reviews_count=None,
            category_path=None,
            scraped_at=datetime.now(timezone.utc)
        )
