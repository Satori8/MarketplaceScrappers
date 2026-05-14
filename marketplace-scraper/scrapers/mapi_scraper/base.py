from typing import Protocol, runtime_checkable, Any

@runtime_checkable
class MarketplaceModule(Protocol):
    """
    Protocol every MAPI site module must satisfy.
    Phase 1: modules implement scrape_url() only.
    """
    
    SITE_ID: str                    # e.g. "rozetka", "prom", "allo", "epicentr"
    DOMAINS: list[str]              # e.g. ["rozetka.com.ua", "auto.rozetka.com.ua"]
    
    def scrape_url(
        self,
        url: str,
        page: int = 1,
        debug: bool = False,
    ) -> dict:
        """
        Sync entry point. Returns standard result dict:
        {
            "ok": bool,
            "site": str,
            "mode": "url",
            "products": list[dict],        # normalized, see API_DOCS.md schema
            "pagination": {
                "total_pages": int,
                "page_index": int
            },
            "code": int,                   # HTTP status of primary request
            "debug": dict | None           # populated only if debug=True
        }
        On error: {"ok": False, "site": str, "mode": "url", "error": str, "code": int}
        """
        ...

    async def async_scrape_url(
        self,
        url: str,
        page: int = 1,
        debug: bool = False,
    ) -> dict:
        """
        Async entry point — wraps scrape_url() via asyncio executor by default.
        Site modules may override with native async implementation (Phase 2).
        """
        ...

class BaseModule:
    """
    Default mixin providing async_scrape_url() as executor wrapper.
    Site modules inherit from this to get async for free in Phase 1.
    Override async_scrape_url() in Phase 2 when rewriting with AsyncSession.
    """
    SITE_ID: str = ""
    DOMAINS: list[str] = []

    def scrape_url(self, url: str, page: int = 1, debug: bool = False) -> dict:
        raise NotImplementedError

    async def async_scrape_url(self, url: str, page: int = 1, debug: bool = False) -> dict:
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.scrape_url, url, page, debug)
