from __future__ import annotations

import asyncio
import json
import logging
import threading
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ai.gemini_client import GeminiClient
from core.anti_bot import AntiBotManager


logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    def __init__(
        self,
        marketplace_name: str,
        config_path: str = "config.yaml",
        captcha_callback=None,
    ) -> None:
        self.marketplace_name = marketplace_name
        if config_path == "config.yaml":
            config_path = str(Path(__file__).resolve().parent.parent / "config.yaml")
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.anti_bot = AntiBotManager(config=self.config, captcha_callback=captcha_callback)
        self.captcha_event = threading.Event()
        self.captcha_callback = captcha_callback
        self.gemini = GeminiClient(config_path=config_path)

    def _load_config(self) -> dict[str, Any]:
        if not self.config_path.exists():
            return {}
        try:
            import yaml
        except Exception:
            logger.warning("PyYAML not installed; config could not be loaded.")
            return {}
        with self.config_path.open("r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}

    def _save_config(self, config: dict[str, Any]) -> None:
        try:
            import yaml
        except Exception as exc:
            raise RuntimeError("PyYAML is required to save config.yaml.") from exc
        with self.config_path.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(config, fh, allow_unicode=True, sort_keys=False)

    @abstractmethod
    async def search_products(
        self, query: str, pages: int = 1, skip_urls: set[str] = None, stop_event: Optional[asyncio.Event] = None
    ) -> list:
        """Search by query. Skip URLs in skip_urls if provided."""

    @abstractmethod
    async def get_product_details(self, url: str):
        """Fetch full product card with all specs."""

    @abstractmethod
    def parse_price(self, raw_text: str) -> float | None:
        """Extract float from strings like '4 200 грн', 'від 3800₴'."""

    @abstractmethod
    def detect_captcha(self, page) -> bool:
        """Return True if a captcha is detected on this page."""

    async def wait_for_captcha(self, page) -> bool:
        """
        Robustly pauses while captcha/WAF challenge is visible.
        """
        # Inject Deep Stealth Script
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            const newProto = navigator.__proto__;
            delete newProto.webdriver;
            navigator.__proto__ = newProto;
            window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {}, app: {} };
            Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
            Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
        """)

        detected = False
        consecutive_clean_checks = 0
        
        while True:
            content = await page.content()
            title = await page.title()
            
            # Detect Success Markers (Strong priority)
            has_success_marker = ("rz-header" in content or 
                                 "common-header" in content or
                                 "catalog-grid" in content or
                                 "search-result" in content.lower())
            
            # Detect Challenge Markers
            # Success overrides soft CF markers (stale iframes)
            if has_success_marker:
                is_cf = False
            else:
                is_cf = ("challenges.cloudflare.com" in content or 
                         "One more step" in content or 
                         "Один момент" in title or 
                         "Checking your browser" in content or
                         "Verify you are human" in content or
                         "cf-browser-verification" in content or
                         "cf-spinner" in content)
            
            if is_cf:
                if not detected:
                    logger.info(f"[{self.marketplace_name.upper()}] Cloudflare/WAF Challenge detected. Please solve it in the browser.")
                    detected = True
                consecutive_clean_checks = 0
                await page.wait_for_timeout(3000)
            else:
                if has_success_marker:
                    consecutive_clean_checks += 1
                    if consecutive_clean_checks == 1:
                        logger.info(f"[{self.marketplace_name.upper()}] Success markers detected. Verifying stability...")
                else:
                    consecutive_clean_checks = 0
                    await page.wait_for_timeout(2000)
                    # If it's a blank page or something else, but not CF
                    if not content or len(content) < 500:
                        continue
                    else:
                        # Assume okay if no CF and non-empty
                        consecutive_clean_checks = 2

                if consecutive_clean_checks >= 2:
                    if detected:
                        logger.info(f"[{self.marketplace_name.upper()}] Challenge resolved.")
                    break
                else:
                    await page.wait_for_timeout(1500)
                    
        return detected

    def random_delay(self) -> None:
        self.anti_bot.random_delay()

    def get_random_user_agent(self) -> str:
        return self.anti_bot.get_random_user_agent()

    def handle_captcha_pause(self) -> None:
        if self.captcha_callback is None:
            return
        resolved = bool(self.captcha_callback(self.marketplace_name))
        if resolved:
            self.captcha_event.set()

    def auto_detect_selectors(self, url: str) -> dict:
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            raise RuntimeError("Playwright is required for selector auto-detection.") from exc

        html = ""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page(user_agent=self.get_random_user_agent())
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            self.random_delay()
            html = page.content()
            browser.close()

        prompt = (
            "Extract candidate CSS selectors from this marketplace search-result HTML.\n"
            "Return strict JSON object with keys:\n"
            "product_card, title, price, product_url, availability, image, next_page\n"
            "Use null where not found.\n"
            f"HTML:\n{html[:200000]}"
        )
        system = "You are a CSS selector extraction assistant. Return JSON only."
        selector_dict = self.gemini.generate_json(prompt=prompt, system=system)

        config = self._load_config()
        config.setdefault("marketplaces", {})
        config["marketplaces"].setdefault(self.marketplace_name, {})
        config["marketplaces"][self.marketplace_name]["selectors"] = selector_dict
        self._save_config(config)
        return selector_dict

    def validate_selectors(self, url: str) -> dict:
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            raise RuntimeError("Playwright is required for selector validation.") from exc

        config = self._load_config()
        selectors = (
            config.get("marketplaces", {})
            .get(self.marketplace_name, {})
            .get("selectors", {})
        )
        broken: list[str] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page(user_agent=self.get_random_user_agent())
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            for key, selector in selectors.items():
                if not selector:
                    broken.append(key)
                    continue
                try:
                    element = page.query_selector(selector)
                    if element is None:
                        broken.append(key)
                except Exception:
                    broken.append(key)
            browser.close()

        if broken:
            logger.warning(
                "Broken selectors for %s: %s",
                self.marketplace_name,
                json.dumps(broken, ensure_ascii=False),
            )

        return {
            "valid": len(broken) == 0,
            "broken": broken,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
