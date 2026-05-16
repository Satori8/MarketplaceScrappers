from typing import Dict, Any, Type, Optional
from urllib.parse import urlparse

from scrapers.mapi_scraper.base import MarketplaceModule
from scrapers.mapi_scraper.http import _err, logger

# Import site modules
from scrapers.mapi_scraper.sites.rozetka import RozetkaModule
from scrapers.mapi_scraper.sites.prom import PromModule
from scrapers.mapi_scraper.sites.allo import AlloModule
from scrapers.mapi_scraper.sites.epicentr import EpicentrModule
from scrapers.mapi_scraper.sites.hotline import HotlineModule

# Registry of available modules
_MODULES: Dict[str, MarketplaceModule] = {}

def _register_module(module: MarketplaceModule):
    _MODULES[module.SITE_ID] = module

# Initialize and register modules
_register_module(RozetkaModule())
_register_module(PromModule())
_register_module(AlloModule())
_register_module(EpicentrModule())
_register_module(HotlineModule())

# "epicentrk" is the marketplace ID used throughout the scheduler and GUI,
# but EpicentrModule.SITE_ID = "epicentr". Register the alias so both work.
_MODULES["epicentrk"] = _MODULES["epicentr"]

def get_module(site_id: str) -> Optional[MarketplaceModule]:
    return _MODULES.get(site_id)

def get_module_for_url(url: str) -> Optional[MarketplaceModule]:
    """Find the appropriate module for a given URL based on its domain."""
    try:
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
            
        for module in _MODULES.values():
            if any(domain == d or domain.endswith("." + d) for d in module.DOMAINS):
                return module
    except Exception:
        pass
    return None

def scrape(site: str, mode: str, **kw) -> Dict[str, Any]:
    """Universal entry point for scraping.
    
    This function bridges the old functional API to the new class-based modules.
    """
    module = get_module(site)
    if not module:
        # Fallback to URL detection if site isn't explicitly known but URL is provided
        url = kw.get('url')
        if url:
             module = get_module_for_url(url)
             if module:
                 site = module.site_id()
                 
    if not module:
        return _err(site, mode, f"Site {site} not supported or URL not recognized")

    if mode == "url":
        url = kw.get('url')
        if not url: return _err(site, mode, "URL is required")
        page = kw.get('page', 1)
        debug = kw.get('debug', False)
        return module.scrape_url(url, page=int(page), debug=debug)
    else:
        return _err(site, mode, f"Mode '{mode}' implies specific endpoints which are deprecated. Use mode='url'")

async def async_scrape(
    site: str,
    url: str,
    page: int = 1,
    debug: bool = False,
    proxy: str | None = None,
) -> dict:
    module = get_module(site)
    if not module:
        return _err(site, "url", f"Site {site} not supported")
    return await module.async_scrape_url(url, page=page, debug=debug, proxy=proxy)

async def async_scrape_url_auto(
    url: str,
    page: int = 1,
    debug: bool = False,
    proxy: str | None = None,
) -> dict:
    host = urlparse(url).hostname or ""
    for site_id, mod in _MODULES.items():
        if any(d in host for d in mod.DOMAINS):
            return await mod.async_scrape_url(url, page=page, debug=debug, proxy=proxy)
    raise ValueError(f"No registered module matches URL: {url}")

if __name__ == "__main__":
    # Quick test
    import sys
    import json
    if len(sys.argv) > 1:
        site, mode = sys.argv[1:3]
        args = dict(arg.split('=') for arg in sys.argv[3:])
        print(json.dumps(scrape(site, mode, **args), indent=2, ensure_ascii=False))
