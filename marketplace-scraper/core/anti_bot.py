from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Any, Callable


class AntiBotManager:
    def __init__(
        self,
        config: dict[str, Any] | None = None,
        config_path: str = "config.yaml",
        captcha_callback: Callable[[str], bool] | None = None,
    ) -> None:
        if config_path == "config.yaml":
            config_path = str(Path(__file__).resolve().parent.parent / "config.yaml")
        self.config = config or self._load_config(config_path)
        self.anti_bot_cfg = self.config.get("anti_bot", {})
        self.captcha_callback = captcha_callback

    def _load_config(self, config_path: str) -> dict[str, Any]:
        path = Path(config_path)
        if not path.exists():
            return {}
        try:
            import yaml
        except Exception:
            return {}
        with path.open("r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}

    def random_delay(self, min_s: float | None = None, max_s: float | None = None) -> None:
        delay_min = float(min_s if min_s is not None else self.anti_bot_cfg.get("delay_min", 2.0))
        delay_max = float(max_s if max_s is not None else self.anti_bot_cfg.get("delay_max", 6.0))
        if delay_max < delay_min:
            delay_max = delay_min
        time.sleep(random.uniform(delay_min, delay_max))

    def random_mouse_move(self, page) -> None:
        viewport = page.viewport_size or {"width": 1280, "height": 800}
        x = random.randint(0, max(0, int(viewport.get("width", 1280)) - 1))
        y = random.randint(0, max(0, int(viewport.get("height", 800)) - 1))
        page.mouse.move(x, y)

    def random_scroll(self, page) -> None:
        delta = random.randint(150, 900)
        page.mouse.wheel(0, delta)

    def apply_stealth(self, page_or_context) -> None:
        try:
            from playwright_stealth import stealth_sync
        except Exception:
            return
        stealth_sync(page_or_context)

    async def apply_stealth_async(self, page_or_context) -> None:
        try:
            from playwright_stealth import stealth_async
        except Exception:
            return
        await stealth_async(page_or_context)

    def get_random_user_agent(self) -> str:
        user_agents = self.anti_bot_cfg.get("user_agents", [])
        if not user_agents:
            return (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        return random.choice(user_agents)

    def detect_captcha(self, page) -> dict:
        checks = {
            "hcaptcha": [
                "iframe[src*='hcaptcha']",
                "[data-sitekey][data-hcaptcha-response]",
            ],
            "recaptcha": [
                "iframe[src*='recaptcha']",
                ".g-recaptcha",
            ],
            "cloudflare": [
                "iframe[src*='challenges.cloudflare.com']",
                "#challenge-running",
                ".cf-challenge",
            ],
        }
        for captcha_type, selectors in checks.items():
            for selector in selectors:
                try:
                    if page.query_selector(selector):
                        return {"detected": True, "type": captcha_type}
                except Exception:
                    continue
        return {"detected": False, "type": None}

    def exponential_backoff(self, attempt: int) -> float:
        return float(60 * (2 ** max(0, int(attempt))))
