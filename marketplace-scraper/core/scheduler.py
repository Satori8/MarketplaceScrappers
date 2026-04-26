import asyncio
import concurrent.futures
import json
import logging
import threading
from datetime import datetime, timezone
from typing import Callable, Any

from core.models import ScrapeTask, ScrapeResult, RawProduct
from db.database import Database
from db.product_repo import ProductRepository

# Import scrapers
from scrapers.hotline import HotlineScraper
from scrapers.rozetka import RozetkaScraper
from scrapers.prom import PromScraper
from scrapers.allo import AlloScraper
from scrapers.epicentrk import EpicentrkScraper
from scrapers.custom_scraper import CustomScraper
from core.normalizer import DataNormalizer

logger = logging.getLogger(__name__)


class TaskScheduler:
    """
    Multi-threaded Task Scheduler for managing parallel scraper execution.
    Executes each requested marketplace in its own thread with its own asyncio loop.
    Emits real-time callbacks.
    """

    def __init__(self, db: Database, config_path: str = "config.yaml", on_keys_exhausted=None):
        self.db = db
        self.config_path = config_path
        self.repo = ProductRepository(self.db)
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
        
        # Callbacks
        self.on_progress: Callable[[int, int], None] = lambda scraped, total: None
        self.on_product_found: Callable[[RawProduct, bool, float | None], None] = lambda prod, is_new, delta: None
        self.on_error: Callable[[str], None] = lambda msg: None
        self.on_captcha: Callable[[str], None] = lambda mp: None
        self.on_finished: Callable[[str, str], None] = lambda sid, status: None
        self.on_selector_warning: Callable[[str], None] = lambda msg: None
        self.on_mp_status: Callable[[str, str], None] = lambda mp, status: None

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

    def _create_session(self, task: ScrapeTask) -> None:
        conn = self.db.get_connection()
        conn.execute(
            """
            INSERT INTO scrape_sessions (
                id, query, product_type, marketplaces, status, products_found, started_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task.session_id,
                task.query,
                task.product_type,
                json.dumps(task.marketplaces),
                "running",
                0,
                datetime.now(timezone.utc).isoformat()
            )
        )
        conn.commit()

    def _update_session(self, session_id: str, status: str, err: list, count: int) -> None:
        conn = self.db.get_connection()
        conn.execute(
            """
            UPDATE scrape_sessions 
            SET status = ?, finished_at = ?, errors_json = ?, products_found = products_found + ?
            WHERE id = ?
            """,
            (
                status,
                datetime.now(timezone.utc).isoformat(),
                json.dumps(err) if err else None,
                count,
                session_id
            )
        )
        conn.commit()

    def _update_session_count(self, session_id: str, count: int) -> None:
        conn = self.db.get_connection()
        conn.execute("UPDATE scrape_sessions SET products_found = products_found + ? WHERE id = ?", (count, session_id))
        conn.commit()

    def run(self, task: ScrapeTask):
        """Blocking call. Launches threadpool for marketplaces and awaits them."""
        logger.info(f"--- Starting Scrape Task: {task.query} (ID: {task.session_id}) ---")
        
        self._stop_event.clear()
        self._create_session(task)
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
        self._update_session(task.session_id, final_status, [], 0)
        logger.info(f"--- Scrape Task {final_status.upper()} (ID: {task.session_id}) ---")

    def run_individual_discovery(self, mp: str, method: str, query: str, pages: int, session_id: str):
        """Standalone discovery for a single (marketplace, query) job.

        Called concurrently by the GUI ThreadPoolExecutor — one call per job.
        GUI tracks batch completion via futures; session count is updated best-effort
        (silently no-ops if the batch session row was not pre-created).
        """
        # B1 fix: removed premature `return asyncio.run(...)` that made all session
        # finalization code unreachable (dead code). Now runs scraper then updates count.
        task = ScrapeTask(
            query=query, session_id=session_id, product_type=None,
            marketplaces={mp: method}, pages_limit=pages,
            use_category_urls=False, category_urls={}, skip_known_urls=False
        )
        try:
            products = asyncio.run(self._run_scraper_async(mp, method, task))
            self._update_session_count(task.session_id, len(products))
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
                price=0, currency="UAH", brand=None, model=None,
                raw_specs=specs, description=None, image_url=None,
                availability=None, rating=None, reviews_count=None,
                category_path=None, scraped_at=datetime.now(timezone.utc)
            )
            rp._db_id = r["id"]
            to_norm.append(rp)
            
        def save_results(chunk_results):
            # Inner helper to save results immediately
            count = 0
            for norm in chunk_results:
                db_id = getattr(norm.raw, "_db_id", None)
                if db_id:
                    self.repo.save_specs(db_id, norm)
                    conn.execute("UPDATE products SET product_type = ?, is_relevant = ? WHERE id = ?", 
                                 (norm.product_type, 1 if norm.normalized_specs.get("is_relevant", True) else 0, db_id))
                    count += 1
            conn.commit()
            logger.info(f"[Scheduler] Immediate DB Update: Persisted {count} products from current batch.")

        # Step 2: Normalize with immediate callback
        normalized = await self.normalizer.normalize_batch(
            to_norm, 
            "Global Cleanup Batch", 
            stop_event=stop_event,
            on_chunk_callback=save_results
        )
        
        logger.info(f"[Scheduler] Global Intelligence Phase complete. Normalized {len(normalized)}/{len(to_norm)} products.")

    async def _run_scraper_async(self, marketplace: str, method: str, task: ScrapeTask) -> list[RawProduct]:
        """Async context for a single scraper execution, meant to run inside a per-thread event loop."""
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
            relevant_urls = []
            if task.direct_urls:
                for url in task.direct_urls:
                    if marketplace in url.lower() or (marketplace == "epicentrk" and "epicentr" in url.lower()):
                        relevant_urls.append(url)

            if relevant_urls:
                logger.info(f"Scraper '{marketplace}' processing {len(relevant_urls)} direct URLs.")
                # Process URLs in parallel tasks within the current event loop
                tasks = [scraper.get_product_details(url) for url in relevant_urls]
                detail_prods = await asyncio.gather(*tasks)
                products.extend([p for p in detail_prods if p and p.title])
            
            # If there's a real query, also run the search
            if task.query and task.query != "Direct URLs Scan":
                logger.info(f"Scraper '{marketplace}' searching for: {task.query}")
                search_prods = await scraper.search_products(task.query, pages=pages, skip_urls=set(), stop_event=self._stop_event)
                products.extend(search_prods)
            
            for prod in products:
                if self._stop_event.is_set():
                    logger.info("Scraper '%s' halting due to stop event.", marketplace)
                    break
                
                prod.scraped_at = datetime.now(timezone.utc)
                prod.marketplace = marketplace  # ensure sync
                
                pid, is_new, delta = self.repo.upsert_product(prod, task.session_id)
                
                with self._stats_lock:
                    if is_new:
                        self._total_new += 1
                    elif delta is not None:
                        self._total_updated += 1

                self.on_product_found(prod, is_new, delta)
                found_products.append(prod)
                
            self.on_mp_status(marketplace, f"Finished ({len(products)})")
            self.on_progress(pages, pages)
        except Exception as e:
            self.on_mp_status(marketplace, "Error")
            logger.error("Scraper '%s' execution failed: %s", marketplace, e)
            raise

        return found_products
