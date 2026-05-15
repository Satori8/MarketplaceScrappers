import json
import os
import time
import re
import logging
from typing import Any, Dict, List, Optional, Tuple
from curl_cffi import requests
from curl_cffi.requests import AsyncSession

_RUN_TIMESTAMP = int(time.time())

# --- Constants & Config ---
_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
_RZ_API = "https://rozetka.com.ua/api/product-api/v4"
_RZ_GW = "https://rozetka.com.ua/api/product-api/v4/graphql"
_PROM_API = "https://prom.ua/api/v1"
_ALLO_API = "https://allo.ua/ua/api"
_EPI_API = "https://epicentrk.ua/api/active/v2"
_EPI_API_V1 = "https://api.epicentrk.ua/api/v1"
_EPI_API_V2 = "https://api.epicentrk.ua/api/v2"
_EPI_MERCHANT_API = f"{_EPI_API_V1}/merchant"
_HOTLINE_API = "https://hotline.ua/ua"

# --- Logging Setup ---
logger = logging.getLogger("scraper")
logger.setLevel(logging.INFO)

def _get_log_run_dir():
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    run_dir = os.path.join(log_dir, f"run_{_RUN_TIMESTAMP}")
    os.makedirs(run_dir, exist_ok=True)
    return run_dir

def _get_results_run_dir():
    results_dir = os.path.join(os.path.dirname(__file__), "results")
    run_dir = os.path.join(results_dir, f"run_{_RUN_TIMESTAMP}")
    os.makedirs(run_dir, exist_ok=True)
    return run_dir

def _setup_logging():
    if logger.handlers: return # Avoid duplicate handlers
    
    run_dir = _get_log_run_dir()
    log_file = os.path.join(run_dir, "scraper.log")
    
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] [%(site)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    
    # File Handler
    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    # Console Handler
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)

_setup_logging()

_COMMON_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
    "Origin": "https://rozetka.com.ua",
    "Referer": "https://rozetka.com.ua/",
}

_ALLO_HEADERS = {
    **_COMMON_HEADERS,
    "Origin": "https://allo.ua",
    "Referer": "https://allo.ua/",
}

_PROM_HEADERS = {
    **_COMMON_HEADERS,
    "Origin": "https://prom.ua",
    "Referer": "https://prom.ua/",
}

# --- Internal Fetchers ---

def _get(site: str, url: str, params: Optional[Dict] = None, extra_headers: Optional[Dict] = None) -> Tuple[int, Any]:
    """Internal HTTP GET wrapper using curl_cffi for HTTP/2 support and stealth."""
    headers = _COMMON_HEADERS.copy()
    if extra_headers: headers.update(extra_headers)
    
    logger.info(f"GET {url}", extra={"site": site})
    try:
        response = requests.get(url, params=params, headers=headers, impersonate="chrome110", timeout=15)
        if response.status_code != 200:
            logger.warning(f"HTTP {response.status_code} for {url}", extra={"site": site})
        try:
            return response.status_code, response.json()
        except:
            return response.status_code, response.text
    except Exception as e:
        logger.error(f"Network error for {url}: {e}", extra={"site": site})
        return 0, str(e)

def _get_with_meta(site: str, url: str, params: Optional[Dict] = None, extra_headers: Optional[Dict] = None, parse_json: bool = True, save_raw: bool = False) -> Tuple[int, Any, Dict[str, Any]]:
    headers = _COMMON_HEADERS.copy()
    if extra_headers: headers.update(extra_headers)

    logger.info(f"FETCH {url}", extra={"site": site})
    started = time.perf_counter()
    try:
        response = requests.get(url, params=params, headers=headers, impersonate="chrome110", timeout=15)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        body_bytes = len(response.content or b"")

        if response.status_code != 200:
            logger.warning(f"HTTP {response.status_code} (in {elapsed_ms}ms) for {url}", extra={"site": site})
            if body_bytes > 0:
                snippet = response.text[:500].replace('\\n', ' ')
                logger.debug(f"Error Body: {snippet}", extra={"site": site})

        data: Any
        if parse_json:
            try:
                data = response.json()
            except:
                data = response.text
        else:
            data = response.text

        meta = {
            "url": response.url,
            "status": response.status_code,
            "elapsed_ms": elapsed_ms,
            "bytes": body_bytes,
        }
        if save_raw:
            if parse_json and isinstance(data, (dict, list)):
                meta["raw_response"] = data
            else:
                meta["raw_response"] = str(data)[:2000]

        return response.status_code, data, meta
    except Exception as e:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.error(f"EXCEPTION for {url}: {e}", extra={"site": site})
        return 0, str(e), {
            "url": url,
            "status": 0,
            "elapsed_ms": elapsed_ms,
            "bytes": 0,
        }

async def _aget(
    site: str,
    url: str,
    params: dict | None = None,
    extra_headers: dict | None = None,
    proxy: str | None = None,
) -> tuple[int, Any]:
    """Async GET. Drop-in async replacement for _get()."""
    headers = _COMMON_HEADERS.copy()
    if extra_headers:
        headers.update(extra_headers)
    try:
        async with AsyncSession(impersonate="chrome124") as session:
            resp = await session.get(
                url,
                params=params,
                headers=headers,
                proxies={"https": proxy, "http": proxy} if proxy else None,
                timeout=15,
            )
            try:
                return resp.status_code, resp.json()
            except Exception:
                return resp.status_code, resp.text
    except Exception as e:
        logger.error(f"Network error for {url}: {e}", extra={"site": site})
        return 0, str(e)


async def _aget_with_meta(
    site: str,
    url: str,
    params: dict | None = None,
    extra_headers: dict | None = None,
    parse_json: bool = True,
    save_raw: bool = False,
    proxy: str | None = None,
) -> tuple[int, Any, dict]:
    """Async GET with timing/meta. Drop-in async replacement for _get_with_meta()."""
    headers = _COMMON_HEADERS.copy()
    if extra_headers:
        headers.update(extra_headers)
    started = time.perf_counter()
    try:
        async with AsyncSession(impersonate="chrome124") as session:
            resp = await session.get(
                url,
                params=params,
                headers=headers,
                proxies={"https": proxy, "http": proxy} if proxy else None,
                timeout=15,
            )
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            body_bytes = len(resp.content or b"")
            if parse_json:
                try:
                    data = resp.json()
                except Exception:
                    data = resp.text
            else:
                data = resp.text
            meta = {
                "url": str(resp.url),
                "status": resp.status_code,
                "elapsed_ms": elapsed_ms,
                "bytes": body_bytes,
            }
            if save_raw:
                if parse_json and isinstance(data, (dict, list)):
                    meta["raw_response"] = data
                else:
                    meta["raw_response"] = str(data)[:2000]
            return resp.status_code, data, meta
    except Exception as e:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.error(f"EXCEPTION for {url}: {e}", extra={"site": site})
        return 0, str(e), {"url": url, "status": 0, "elapsed_ms": elapsed_ms, "bytes": 0}

_log_counter = 0

def _get_log_dir():
    return _get_log_run_dir()

def _save_debug_item(site: str, step: str, url: str, meta: Dict, raw_data: Any, normalized_products: List[Dict]):
    global _log_counter
    _log_counter += 1
    
    # Extract part of target url after domain
    from urllib.parse import urlparse
    parsed = urlparse(url)
    url_part = (parsed.path + ("?" + parsed.query if parsed.query else "")).strip("/")
    # Sanitize for filename (Windows safe)
    url_part = re.sub(r'[^a-zA-Z0-9\\.\\-]', '_', url_part)
    url_part = re.sub(r'_+', '_', url_part).strip("_")
    if len(url_part) > 100: url_part = url_part[:100] # Limit length
    
    run_dir = _get_results_run_dir()
    prefix = f"{_log_counter:03d}_{site}_{step}"
    filename_base = f"{prefix}_{url_part}".strip("_")
    
    # 1. Save Raw File
    raw_file = os.path.join(run_dir, f"{filename_base}_raw.json")
    raw_entry = {
        "url": url,
        "meta": meta,
        "raw_data": raw_data
    }
    with open(raw_file, "w", encoding="utf-8") as f:
        json.dump(raw_entry, f, indent=2, ensure_ascii=False)
        
    # 2. Save Normalized File
    norm_file = os.path.join(run_dir, f"{filename_base}_norm.json")
    with open(norm_file, "w", encoding="utf-8") as f:
        json.dump(normalized_products, f, indent=2, ensure_ascii=False)

def _ok(site: str, data: Any, mode: str, code: int = 200) -> Dict:
    return {"ok": True, "site": site, "status": "ok", "mode": mode, "products": data, "code": code}

def _err(site: str, mode: str, error: str, code: int = 0) -> Dict:
    return {"ok": False, "site": site, "mode": mode, "error": error, "code": code}

def _make_sync_fetcher(proxy=None):
    """Returns a sync fetch coroutine factory compatible with _scrape_impl signature."""
    async def fetch(site, url, *, params=None, extra_headers=None, parse_json=True, save_raw=False):
        return _get_with_meta(site, url, params=params, extra_headers=extra_headers, parse_json=parse_json, save_raw=save_raw)
    return fetch

def _make_async_fetcher(proxy=None):
    """Returns an async fetch coroutine factory compatible with _scrape_impl signature."""
    async def fetch(site, url, *, params=None, extra_headers=None, parse_json=True, save_raw=False):
        return await _aget_with_meta(site, url, params=params, extra_headers=extra_headers, parse_json=parse_json, save_raw=save_raw, proxy=proxy)
    return fetch

def _make_sync_poster(proxy=None):
    """Returns a sync post coroutine for _scrape_impl (e.g. Prom GraphQL)."""
    async def post(url, headers, json):
        started = time.perf_counter()
        resp = requests.post(url, headers=headers, json=json, impersonate="chrome124", timeout=15)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return resp, elapsed_ms
    return post

def _make_async_poster(proxy=None):
    """Returns an async post coroutine for _scrape_impl (e.g. Prom GraphQL)."""
    async def post(url, headers, json):
        started = time.perf_counter()
        async with AsyncSession(impersonate="chrome124") as session:
            resp = await session.post(url, headers=headers, json=json, timeout=15, proxies={"https": proxy, "http": proxy} if proxy else None)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return resp, elapsed_ms
    return post

