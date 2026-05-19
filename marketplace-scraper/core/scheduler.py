import asyncio
import concurrent.futures
import json
import logging
import queue
import threading
from datetime import datetime, timezone
from typing import Callable, Any

from core.models import ScrapeTask, ScrapeResult, RawProduct
from db.database import Database

# Import scrapers
from scrapers.hotline import HotlineScraper
from scrapers.rozetka import RozetkaScraper
from scrapers.prom import PromScraper
from scrapers.allo import AlloScraper
from scrapers.epicentrk import EpicentrkScraper
from scrapers.custom_scraper import CustomScraper
from core.normalizer import DataNormalizer

logger = logging.getLogger(__name__)


class DbWriteQueue:
    """
    Serializes all SQLite write operations through a single dedicated writer thread.
    Multiple scraper threads submit callables via submit(); the writer executes them
    one-at-a-time, preventing 'database is locked' under high concurrency.
    """

    _SENTINEL = object()

    def __init__(self) -> None:
        self._queue: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._worker, daemon=True, name="db-writer"
        )
        self._thread.start()
        logger.info("[DbWriteQueue] Writer thread started.")

    def stop(self) -> None:
        self._queue.put(self._SENTINEL)
        if self._thread:
            self._thread.join(timeout=10)
            self._thread = None
        logger.info("[DbWriteQueue] Writer thread stopped.")

    def _worker(self) -> None:
        while True:
            item = self._queue.get()
            if item is self._SENTINEL:
                break
            fn, event, holder = item
            try:
                holder["result"] = fn()
            except Exception as exc:
                holder["error"] = exc
            finally:
                event.set()

    def submit(self, fn: Callable) -> Any:
        """Enqueue fn and block until it completes on the writer thread."""
        event = threading.Event()
        holder: dict = {}
        self._queue.put((fn, event, holder))
        event.wait()
        if "error" in holder:
            raise holder["error"]
        return holder["result"]


class TaskScheduler:
    """
    Multi-threaded Task Scheduler for managing parallel scraper execution.
    Executes each requested marketplace in its own thread with its own asyncio loop.
    Emits real-time callbacks.
    """

    def __init__(self, db: Database, config_path: str = "config.yaml", on_keys_exhausted=None):
        self.db = db
        self.config_path = config_path
        self.normalizer = DataNormalizer(
            config_path=self.config_path,
            on_keys_exhausted=on_keys_exhausted,
        )
        
        self._stop_event = threading.Event()
        self._active_futures = []
        self._executor = None
        
        self._total_new = 0
        self._total_updated = 0
        self._stats_lock = threading.Lock()

        # Single-writer queue: all DB upserts from parallel scraper threads go here.
        self._db_write_queue = DbWriteQueue()
        self._db_write_queue.start()
        
        # Callbacks
        self.on_progress: Callable[[int, int], None] = lambda scraped, total: None
        self.on_product_found: Callable[[RawProduct, bool, float | None], None] = lambda prod, is_new, delta: None
        self.on_error: Callable[[str], None] = lambda msg: None
        self.on_captcha: Callable[[str], None] = lambda mp: None
        self.on_finished: Callable[[str, str], None] = lambda sid, status: None
        self.on_selector_warning: Callable[[str], None] = lambda msg: None
        self.on_mp_status: Callable[[str, str], None] = lambda mp, status: None
        
        # Concurrency management
        self._site_semaphores = {}
        self._sem_lock = threading.Lock()

    def _get_site_semaphore(self, site: str, limit: int) -> threading.Semaphore:
        with self._sem_lock:
            if site not in self._site_semaphores:
                self._site_semaphores[site] = threading.Semaphore(limit)
            return self._site_semaphores[site]

    def stop(self) -> None:
        """Gracefully signal all threads/scrapers to stop execution."""
        logger.info("Scheduler Stop requested.")
        self._stop_event.set()

    def _get_scraper_instance(self, marketplace: str, method: str = "Auto") -> Any:
        try:
            scraper = None
            if marketplace == "hotline":
                scraper = HotlineScraper(db=self.db, config_path=self.config_path, captcha_callback=self._handle_captcha)
            elif marketplace == "rozetka":
                scraper = RozetkaScraper(db=self.db, config_path=self.config_path, captcha_callback=self._handle_captcha)
            elif marketplace == "prom":
                scraper = PromScraper(db=self.db, config_path=self.config_path, captcha_callback=self._handle_captcha)
            elif marketplace == "allo":
                scraper = AlloScraper(db=self.db, config_path=self.config_path, captcha_callback=self._handle_captcha)
            elif marketplace == "epicentrk":
                scraper = EpicentrkScraper(db=self.db, config_path=self.config_path, captcha_callback=self._handle_captcha)
            elif marketplace == "custom":
                scraper = CustomScraper(db=self.db, config_path=self.config_path, captcha_callback=self._handle_captcha)
            
            if scraper:
                # Inject method preference if chosen
                if method == "Browser":
                    scraper.config["method_preference"] = "Browser"
                elif method == "Requests":
                    scraper.config["method_preference"] = "Requests"
                return scraper
        except Exception as e:
            msg = f"Failed to initialize scraper {marketplace}: {e}"
            logger.error(msg)
            self.on_error(msg)
        return None

    def _handle_captcha(self, marketplace: str) -> bool:
        """Invoked when underlying anti_bot detects captcha."""
        self.on_captcha(marketplace)
        return False

    def create_session(self, task: ScrapeTask) -> None:
        # Business logic: Sessions are now handled entirely by the 'snapshots' table.
        # This is a no-op or wrapper for snapshot status updates.
        pass

    def update_session(self, session_id: str, status: str, err: list, count: int) -> None:
        # Wrapper for snapshot status updates if needed
        pass

    def update_session_count(self, session_id: str, count: int) -> None:
        pass

    def run(self, task: ScrapeTask):
        """Blocking call. Launches threadpool for marketplaces and awaits them."""
        logger.info(f"--- Starting Scrape Task: {task.query} (ID: {task.session_id}) ---")
        
        self._stop_event.clear()
        self.create_session(task)
        self._total_new = 0
        self._total_updated = 0
        
        # Launch threads for each mp
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(task.marketplaces) or 1) as executor:
            futures = []
            for mp, method in task.marketplaces.items():
                futures.append(executor.submit(
                    self.run_individual_discovery,
                    mp, method, task.query, task.pages_limit, task.session_id
                ))
            
            # Wait for all to finish
            concurrent.futures.wait(futures)

        # After discovery, run Global Normalization
        if not self._stop_event.is_set():
            import asyncio
            logger.info("Discovery phase complete. Starting AI Normalization...")
            asyncio.run(self.normalize_all_pending(stop_event=self._stop_event))

        final_status = "stopped" if self._stop_event.is_set() else "completed"
        # Snapshot status update is now handled by MainWindow
        logger.info(f"--- Scrape Task {final_status.upper()} (ID: {task.session_id}) ---")

    def run_individual_discovery(self, mp: str, method: str, query: str, pages: int, session_id: str, 
                                 skip_stock: bool = True, threads_per_site: int = 1, request_delay: float = 1.5, debug: bool = False, url_tag: str = None):
        """Standalone discovery for a single (marketplace, query) job.

        Called concurrently by the GUI ThreadPoolExecutor — one call per job.
        GUI tracks batch completion via futures; session count is updated best-effort
        (silently no-ops if the batch session row was not pre-created).
        """
        # B1 fix: removed premature `return asyncio.run(...)` that made all session
        # finalization code unreachable (dead code). Now runs scraper then
        task = ScrapeTask(
            query=query, session_id=session_id, product_type=None,
            marketplaces={mp: method}, pages_limit=pages,
            use_category_urls=False, category_urls={}, skip_known_urls=False,
            skip_out_of_stock=skip_stock,
            threads_per_site=threads_per_site,
            request_delay=request_delay,
            direct_urls=[{"url": query, "tag": url_tag}] if url_tag else None,
            debug=debug
        )
        
        sem = self._get_site_semaphore(mp, threads_per_site)
        with sem:
            try:
                products = asyncio.run(self._run_scraper_async(mp, method, task))
                self.update_session_count(task.session_id, len(products))
                return products
            except Exception as exc:
                logger.error("[Scheduler] Error in '%s' for '%s': %s", mp, query, exc)
                return []

    async def normalize_all_pending(self, stop_event=None):
        """Find all products in DB that aren't fully normalized and process them."""
        conn = self.db.get_connection()
        rows = conn.execute("""
            SELECT p.id, p.url, p.title, p.marketplace, ps.raw_specs_json
            FROM products p
            LEFT JOIN product_specs ps ON p.id = ps.product_id
            WHERE p.product_type IS NULL 
               OR p.product_type IN ('Unknown', 'Battery', 'Error')
               OR p.norm_brand IS NULL
        """).fetchall()
        
        if not rows:
            logger.info("[Scheduler] No pending products found for normalization.")
            return

        logger.info(f"[Scheduler] Global Intelligence Phase: Normalizing {len(rows)} products...")
        
        to_norm = []
        for r in rows:
            specs = json.loads(r["raw_specs_json"]) if r["raw_specs_json"] else {}
            rp = RawProduct(
                title=r["title"], url=r["url"], marketplace=r["marketplace"],
                price=0, currency="UAH", brand=None,
                raw_specs=specs, description=None, image_url=None,
                availability=None, rating=None, reviews_count=None,
                category_path=None, scraped_at=datetime.now(timezone.utc)
            )
            rp._db_id = r["id"]
            to_norm.append(rp)
            
        # Step 2: Normalize with immediate callback
        normalized = await self.normalizer.normalize_batch(
            to_norm, 
            "Global Cleanup Batch", 
            stop_event=stop_event,
            on_chunk_callback=None # Repository logic removed
        )
        
        logger.info(f"[Scheduler] Global Intelligence Phase complete. Normalized {len(normalized)}/{len(to_norm)} products.")

    async def _run_scraper_async(self, marketplace: str, method: str, task: ScrapeTask) -> list[RawProduct]:
        """Async context for a single scraper execution, meant to run inside a per-thread event loop."""
        
        # --- MAPI Intercept ---
        if method == "MAPI":
            return await self._run_mapi_async(marketplace, task)

        scraper = self._get_scraper_instance(marketplace, method)
        if not scraper:
            self.on_mp_status(marketplace, "Error: Init")
            return []
        
        self.on_mp_status(marketplace, "Running...")
        
        found_products = []
        try:
            pages = task.pages_limit
            products = []
            
            # If we have direct URLs for this marketplace, or the task is specifically for direct URLs
            relevant_configs = [] # List of {"url": "...", "tag": "..."}
            if task.direct_urls:
                for cfg in task.direct_urls:
                    url = cfg.get("url", "")
                    if marketplace in url.lower() or (marketplace == "epicentrk" and "epicentr" in url.lower()):
                        relevant_configs.append(cfg)

            if relevant_configs:
                logger.info(f"Scraper '{marketplace}' processing {len(relevant_configs)} direct URLs.")
                # Process URLs in parallel tasks within the current event loop
                tasks_list = []
                for cfg in relevant_configs:
                    tasks_list.append(scraper.get_product_details(cfg["url"]))
                
                detail_prods = await asyncio.gather(*tasks_list)
                
                for idx, prod in enumerate(detail_prods):
                    if prod and prod.title:
                        prod.url_tag = relevant_configs[idx].get("tag")
                        products.append(prod)
            
            # If there's a real query, also run the search
            if task.query and task.query != "Direct URLs Scan" and not task.query.startswith("http"):
                logger.info(f"Scraper '{marketplace}' searching for: {task.query}")
                search_prods = await scraper.search_products(
                    task.query, 
                    pages=pages, 
                    skip_urls=set(), 
                    stop_event=self._stop_event,
                    skip_out_of_stock=task.skip_out_of_stock
                )
                products.extend(search_prods)
            
            for prod in products:
                if self._stop_event.is_set():
                    logger.info("Scraper '%s' halting due to stop event.", marketplace)
                    break
                
                prod.scraped_at = datetime.now(timezone.utc)
                prod.marketplace = marketplace  # ensure sync
                
                # Filter by stock if requested
                if task.skip_out_of_stock and prod.availability and "Out" in prod.availability:
                    logger.info(f"Skipping '{prod.title}' - Out of Stock")
                    continue
                
                _prod_ref = prod
                _sid_ref = task.session_id # This should be the snapshot_id for direct writing
                
                def _do_snapshot_insert(p=prod, sid=task.session_id):
                    # In this refactor, session_id is expected to be the integer snapshot_id
                    if not isinstance(sid, int):
                        try: sid = int(sid)
                        except: pass

                    conn = self.db.get_connection()
                    try:
                        conn.execute("""
                            INSERT INTO snapshot_products 
                            (snapshot_id, product_id, mp, sku, name, category, image, price, avail_code, merchant_name, url, url_tag, attributes, extra)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            sid, p.id, p.marketplace, p.sku, p.title, p.category_path, p.image_url, p.price,
                            1 if p.availability and any(x in p.availability.lower() for x in ["наявності", "stock", "есть"]) else 0,
                            p.merchant_name, p.url, p.url_tag,
                            json.dumps(p.attributes or {}, ensure_ascii=False),
                            json.dumps(p.extra or {}, ensure_ascii=False)
                        ))
                    except Exception as e:
                        logger.error(f"[DB] Insert failed for sid={sid} (Type: {type(sid).__name__}): {e}")
                        raise
                    conn.commit()
                    return True # is_new = True for snapshot records

                is_new = self._db_write_queue.submit(_do_snapshot_insert)
                
                with self._stats_lock:
                    self._total_new += 1

                self.on_product_found(prod, is_new, 0)
                found_products.append(prod)
                
            self.on_mp_status(marketplace, f"Finished ({len(products)})")
            self.on_progress(pages, pages)
        except Exception as e:
            self.on_mp_status(marketplace, "Error")
            logger.error("Scraper '%s' execution failed: %s", marketplace, e)
            raise

        return found_products

    async def _run_mapi_async(self, marketplace: str, task: ScrapeTask) -> list[RawProduct]:
        """Specific async runner for MAPI modules."""
        from scrapers.mapi_scraper import async_scrape
        from urllib.parse import quote_plus
        
        self.on_mp_status(marketplace, "Running MAPI...")
        found_products = []
        sess_total = 0
        sess_in_stock = 0
        sess_oos = 0
        try:
            pages = task.pages_limit
            target_urls = []
            
            if task.direct_urls:
                for cfg in task.direct_urls:
                    url = cfg.get("url", "")
                    tag = cfg.get("tag", "")
                    if marketplace in url.lower() or (marketplace == "epicentrk" and "epicentr" in url.lower()):
                        target_urls.append((url, tag))
            
            if task.query and task.query != "Direct URLs Scan" and not task.query.startswith("http"):
                q = quote_plus(task.query)
                if marketplace == "rozetka": target_urls.append((f"https://rozetka.com.ua/ua/search/?text={q}", None))
                elif marketplace == "prom": target_urls.append((f"https://prom.ua/ua/search?search_term={q}", None))
                elif marketplace == "allo": target_urls.append((f"https://allo.ua/ua/catalogsearch/result/?q={q}", None))
                elif marketplace == "epicentrk": target_urls.append((f"https://epicentrk.ua/ua/search/?q={q}", None))
                elif marketplace == "hotline": target_urls.append((f"https://hotline.ua/sr/?q={q}", None))
            elif task.query and task.query.startswith("http"):
                if not any(t[0] == task.query for t in target_urls):
                    target_urls.append((task.query, None))

            for target_url_info in target_urls:
                target_url, url_tag = target_url_info
                for p in range(1, pages + 1):
                    if self._stop_event.is_set(): break
                    mp_tag = marketplace.upper()
                    logger.info(f"[{mp_tag}] MAPI Page {p}: {target_url}")
                    res = await async_scrape(marketplace, target_url, page=p, debug=task.debug)
                    
                    if not res.get("ok"):
                        logger.warning(f"[{mp_tag}] MAPI Failed — page {p}: {target_url}")
                        break
                        
                    raw_dicts = res.get("products", [])
                    if not isinstance(raw_dicts, list):
                        logger.error(f"[{mp_tag}] Scraper error: Expected list of products, got {type(raw_dicts).__name__}. Check scraper implementation.")
                        break

                    pagination = res.get("pagination", {})
                    total_pages = pagination.get("total_pages", 0)
                    logger.info(f"[{mp_tag}] MAPI Page {p} → {len(raw_dicts)} products (total_pages={total_pages or '?'})")
                    if not raw_dicts:
                        break
                    # Stop if we've reached the last known page — avoids a guaranteed-empty extra fetch
                    _is_last_page = total_pages > 0 and p >= total_pages
                    _page_valid_products = 0
                        
                    for d in raw_dicts:
                        if self._stop_event.is_set(): break
                        
                        price_val = d.get("price")
                        try:
                            price_val = float(price_val) if price_val is not None else 0.0
                        except:
                            price_val = 0.0
                            
                        prod = RawProduct(
                            title=d.get("name", "Unknown"),
                            price=price_val,
                            currency="UAH",
                            url=d.get("url", ""),
                            marketplace=marketplace,
                            brand=d.get("brand"),
                            raw_specs=d.get("attributes", {}),
                            description=d.get("description"),
                            image_url=d.get("image"),
                            availability=d.get("avail_code", "InStock"),
                            rating=None,
                            reviews_count=None,
                            category_path=d.get("category_name_ua") or d.get("category_name_ru"),
                            id=d.get("id"),
                            sku=d.get("sku"),
                            merchant_id=d.get("merchant_id"),
                            merchant_name=d.get("merchant_name"),
                            url_tag=url_tag,
                            attributes=d.get("attributes", {}),
                            extra=d.get("extra", {}),
                            scraped_at=datetime.now(timezone.utc)
                        )

                        # MAPI uses Ukrainian avail_code strings — "Out" alone never matches.
                        _OOS_TERMS = ("Немає", "Знятий", "Out of Stock", "Out")
                        if task.skip_out_of_stock and prod.availability and any(t in prod.availability for t in _OOS_TERMS):
                            continue

                        _prod_ref = prod
                        _sid_ref = task.session_id # expected to be snapshot_id
                        
                        def _do_snapshot_insert_mapi(p=prod, sid=task.session_id):
                            if not isinstance(sid, int):
                                try: sid = int(sid)
                                except: pass
                                
                            conn = self.db.get_connection()
                            try:
                                conn.execute("""
                                    INSERT INTO snapshot_products 
                                    (snapshot_id, product_id, mp, sku, name, category, image, price, avail_code, merchant_name, url, url_tag, attributes, extra)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    sid, p.id, p.marketplace, p.sku, p.title, p.category_path, p.image_url, p.price,
                                    1 if p.availability and any(x in p.availability.lower() for x in ["наявності", "stock", "есть"]) else 0,
                                    p.merchant_name, p.url, p.url_tag,
                                    json.dumps(p.attributes or {}, ensure_ascii=False),
                                    json.dumps(p.extra or {}, ensure_ascii=False)
                                ))
                            except Exception as e:
                                logger.error(f"[DB] MAPI Insert failed for sid={sid} (Type: {type(sid).__name__}): {e}")
                                raise
                            conn.commit()
                            return True

                        is_new = self._db_write_queue.submit(_do_snapshot_insert_mapi)

                        with self._stats_lock:
                            self._total_new += 1

                        self.on_product_found(prod, is_new, 0)
                        found_products.append(prod)
                        _page_valid_products += 1
                        sess_in_stock += 1
                    
                    sess_total += len(raw_dicts)
                    sess_oos += (len(raw_dicts) - _page_valid_products)

                    if _page_valid_products == 0 and raw_dicts:
                        logger.info(f"[{mp_tag}] MAPI stopping at page {p} — 0 valid/in-stock products found.")
                        break

                    # Break the page loop after all products on the last page are processed
                    if _is_last_page:
                        logger.info(f"[{mp_tag}] MAPI reached last page ({p}/{total_pages}), stopping.")
                        break
                    
                    # Throttling
                    if p < pages:
                        await asyncio.sleep(task.request_delay)

            # Final reporting
            mp_tag = marketplace.upper()
            logger.info(f"[{mp_tag}] Products parsed: total {sess_total}, in stock {sess_in_stock}, out-of-stock {sess_oos}")

            self.on_mp_status(marketplace, f"Finished MAPI ({len(found_products)})")
            self.on_progress(pages, pages)
        except Exception as e:
            self.on_mp_status(marketplace, "Error")
            logger.error("MAPI Scraper '%s' execution failed: %s", marketplace, e)
            raise
        finally:
            # Cleanly signal completion even on error
            pass

        return found_products
