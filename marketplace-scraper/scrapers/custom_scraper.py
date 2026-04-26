from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.parse import quote_plus, urljoin

from core.models import RawProduct
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class CustomScraper(BaseScraper):
    """
    Basic custom scraper scaffold.
    SECONDARY: extended multi-site config-driven mode is intentionally deferred
    until all primary scrapers are fully verified.
    """

    def __init__(self, db=None, config_path: str = "config.yaml", captcha_callback=None) -> None:
        super().__init__(marketplace_name="custom", config_path=config_path, captcha_callback=captcha_callback)
        self.db = db

    def _get_custom_config(self) -> dict:
        marketplaces = self.config.get("marketplaces", {})
        custom_cfg = marketplaces.get("custom", [])
        if isinstance(custom_cfg, list) and custom_cfg:
            first = custom_cfg[0]
            if isinstance(first, dict):
                return first
        if isinstance(custom_cfg, dict):
            return custom_cfg
        return {}

    def _set_custom_config(self, updated_cfg: dict) -> None:
        config = self._load_config()
        config.setdefault("marketplaces", {})
        custom_cfg = config["marketplaces"].get("custom", [])
        if isinstance(custom_cfg, list):
            if custom_cfg and isinstance(custom_cfg[0], dict):
                custom_cfg[0] = updated_cfg
            else:
                custom_cfg = [updated_cfg]
            config["marketplaces"]["custom"] = custom_cfg
        else:
            config["marketplaces"]["custom"] = updated_cfg
        self._save_config(config)
        self.config = config

    def auto_detect_selectors_async(self, html: str) -> dict:
        import logging
        logger = logging.getLogger(__name__)
        prompt = (
            "Extract candidate CSS selectors from this marketplace HTML.\n"
            "Return strict JSON object with keys:\n"
            "product_card, title, price, product_url, availability, image, next_page\n"
            "Use null where not found.\n"
            f"HTML:\n{html[:200000]}"
        )
        system = "You are a CSS selector extraction assistant. Return JSON only."
        detected = self.gemini.generate_json(prompt=prompt, system=system)
        logger.info("Auto-detected custom selectors: %s", detected)
        if isinstance(detected, dict):
            return detected
        return {}

    async def search_products(self, query: str, pages: int = 1, skip_urls: set | None = None, stop_event=None) -> list[RawProduct]:
        from bs4 import BeautifulSoup
        try:
            from playwright.async_api import async_playwright
        except Exception as exc:
            raise RuntimeError("Playwright is required for custom scraper.") from exc

        skip_urls = skip_urls or set()
        cfg = self._get_custom_config()
        base_url = str(cfg.get("base_url", "")).strip()
        search_template = str(cfg.get("search_url", "")).strip()

        if not base_url or not search_template:
            raise RuntimeError("Custom scraper requires custom.base_url and custom.search_url in config.yaml.")

        requested_pages = max(1, int(pages))
        pages_limit = int(cfg.get("pages_limit", requested_pages))
        total_pages = min(requested_pages, pages_limit)

        current_url = search_template.format(query=quote_plus(query))
        products: list[RawProduct] = []

        if not hasattr(self, "_instance_selectors"):
            self._instance_selectors = {}

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(user_agent=self.get_random_user_agent())
            page = await context.new_page()
            await self.anti_bot.apply_stealth_async(page)
            
            for page_num in range(total_pages):
                if stop_event and stop_event.is_set():
                    logger.info("[Custom] Stop requested.")
                    break
                await page.goto(current_url, wait_until="domcontentloaded", timeout=45000)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                self.random_delay()
                
                html = await page.content()
                
                if not self._instance_selectors:
                    self._instance_selectors = self.auto_detect_selectors_async(html)

                selectors = self._instance_selectors
                card_sel = selectors.get("product_card")
                title_sel = selectors.get("title")
                price_sel = selectors.get("price")
                url_sel = selectors.get("product_url")
                image_sel = selectors.get("image")
                avail_sel = selectors.get("availability")
                next_sel = selectors.get("next_page")

                if not all([card_sel, title_sel, price_sel, url_sel]):
                    break

                soup = BeautifulSoup(html, "html.parser")
                cards = soup.select(card_sel)
                if not cards:
                    break

                for card in cards:
                    title_node = card.select_one(title_sel)
                    url_node = card.select_one(url_sel)
                    price_node = card.select_one(price_sel)
                    if not title_node or not url_node or not price_node:
                        continue

                    href = url_node.get("href")
                    if not href:
                        continue
                    product_url = urljoin(base_url, href)
                    if product_url in skip_urls:
                        continue

                    price = self.parse_price(price_node.get_text(" ", strip=True))
                    if price is None:
                        continue

                    title = (title_node.get("title") or title_node.get_text(" ", strip=True)).strip()
                    if not title:
                        continue

                    availability = None
                    if avail_sel:
                        availability_node = card.select_one(avail_sel)
                        if availability_node:
                            availability = availability_node.get_text(" ", strip=True) or None

                    image_url = None
                    if image_sel:
                        image_node = card.select_one(image_sel)
                        if image_node:
                            image_url = (
                                image_node.get("src")
                                or image_node.get("data-src")
                                or (image_node.get("srcset", "").split(" ")[0] if image_node.get("srcset") else None)
                            )
                            if image_url:
                                image_url = urljoin(base_url, image_url)

                    products.append(
                        RawProduct(
                            title=title,
                            price=price,
                            currency="UAH",
                            url=product_url,
                            marketplace="custom",
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

                if not next_sel:
                    break
                next_node = soup.select_one(next_sel)
                href = None if next_node is None else next_node.get("href")
                if not href:
                    break
                current_url = urljoin(base_url, href)

            await browser.close()

        return products  # B3 fix: was missing, causing method to return None

    async def get_product_details(self, url: str) -> RawProduct:
        try:
            from playwright.async_api import async_playwright
        except Exception as exc:
            raise RuntimeError("Playwright is required.") from exc

        from bs4 import BeautifulSoup
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(user_agent=self.get_random_user_agent())
            page = await context.new_page()
            await self.anti_bot.apply_stealth_async(page)
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            self.random_delay()
            html = await page.content()
            await browser.close()

        soup = BeautifulSoup(html, "html.parser")

        title = ""
        og_title = soup.select_one("meta[property='og:title']")
        if og_title is not None:
            title = (og_title.get("content") or "").strip()
        if not title:
            title = (soup.title.string.strip() if soup.title and soup.title.string else url)

        image_url = None
        og_image = soup.select_one("meta[property='og:image']")
        if og_image is not None:
            image_url = (og_image.get("content") or "").strip() or None

        return RawProduct(
            title=title,
            price=0.0,
            currency="UAH",
            url=url,
            marketplace="custom",
            brand=None,
            model=None,
            raw_specs={},
            description=None,
            image_url=image_url,
            availability=None,
            rating=None,
            reviews_count=None,
            category_path=None,
            scraped_at=datetime.now(timezone.utc),
        )

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
