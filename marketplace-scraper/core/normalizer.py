import logging
import json
from typing import Optional, Any, Callable
from core.models import RawProduct, NormalizedProduct, ProductSchema, SchemaField
from ai.gemini_client import GeminiClient, GeminiKeysExhaustedError

logger = logging.getLogger(__name__)

class DataNormalizer:
    def __init__(self, config_path: str = "config.yaml", on_keys_exhausted: Callable = None):
        self.gemini = GeminiClient(
            config_path=config_path,
            on_keys_exhausted=on_keys_exhausted,
        )
        self.schemas: dict[str, ProductSchema] = {}

    async def normalize_batch(self, raw_products: list[RawProduct], query: str, stop_event=None, on_chunk_callback: Callable = None) -> list[NormalizedProduct]:
        if not raw_products: return []
        
        # Pull batch size from config
        cfg = self.gemini._load_config()
        batch_size = int(cfg.get("gemini", {}).get("batch_size", 15))
        
        results = []
        consecutive_errors = 0
        for i in range(0, len(raw_products), batch_size):
            if stop_event and stop_event.is_set():
                logger.info("[Normalizer] Normalization aborted due to stop event.")
                break
            
            chunk = raw_products[i : i + batch_size]
            try:
                chunk_results = await self._process_chunk(chunk, query)
                results.extend(chunk_results)
                
                # Immediate DB Update Trigger
                if on_chunk_callback:
                    try:
                        on_chunk_callback(chunk_results)
                    except Exception as cb_err:
                        logger.error("[Normalizer] Callback error: %s", cb_err)

                # Successful chunk reset error counter
                consecutive_errors = 0
            except Exception as e:
                consecutive_errors += 1
                logger.error("[Normalizer] Chunk error (%d/5): %s", consecutive_errors, e)
                # Add chunk as 'as-is'
                for r in chunk:
                    results.append(NormalizedProduct(raw=r, product_type="Error", normalized_specs={"is_relevant": True}, schema_version="0"))
            
        return results

    async def _process_chunk(self, chunk: list[RawProduct], query: str) -> list[NormalizedProduct]:
        # B10 fix: include index, url, and description in prompt for maximum intelligence
        data_with_id = []
        for i, p in enumerate(chunk):
            data_with_id.append({
                "id": i, 
                "title": p.title,
                "url": p.url,
                "description": (p.description or "")[:500]
            })
        
        prompt = (
            f"Original Search Query: '{query}'\n\n"
            "Analyze the following products and extract structured data. Check if they match the search query intent.\n"
            "IMPORTANT: Use the 'url' if the title is insufficient, as it often contains brand, voltage, and capacity in the slug.\n"
            "Rules:\n"
            "1. If 'Model' is not explicitly stated, use the descriptive text following the manufacturer/brand name as the model.\n"
            "2. Category (e.g. 'Battery LiFePO4').\n"
            "3. Extract Brand, Model, Voltage, Capacity.\n"
            "4. 12.8V is EQUIVALENT to 12V; 25.6V is EQUIVALENT to 24V.\n"
            "5. Be strict: if query asks for 100Ah and title says 150Ah, mark 'is_relevant': false.\n\n"
            "Return JSON. Format: { \"products\": [ { \"id\": 0, \"is_relevant\": ..., \"brand\": ..., \"model\": ..., \"voltage\": ..., \"capacity\": ..., \"category\": ... }, ... ] }\n"
            f"Input Data: {json.dumps(data_with_id, ensure_ascii=False)}"
        )
        
        try:
            system_prompt = "You are a product data specialist. Return ONLY valid JSON."
            extracted_data = self.gemini.generate_json(prompt, system=system_prompt)
            
            # B10 robustness: check common keys or raw list
            if isinstance(extracted_data, dict):
                for key in ["products", "items", "data", "results"]:
                    if key in extracted_data and isinstance(extracted_data[key], list):
                        extracted_data = extracted_data[key]
                        break
            
            # Convert to a dict for fast lookup by our internal index
            id_map = {}
            if isinstance(extracted_data, list):
                for item in extracted_data:
                    if isinstance(item, dict) and "id" in item:
                        id_map[int(item["id"])] = item

            normalized_chunk = []
            for idx, raw in enumerate(chunk):
                # Map back by index (id). Default to irrelevant if missing.
                specs = id_map.get(idx, {"is_relevant": False})
                
                # Dynamic category mapping
                p_type = specs.get("category") or specs.get("Category") or specs.get("product_type") or "Battery"
                
                normalized_chunk.append(NormalizedProduct(
                    raw=raw,
                    product_type=p_type,
                    normalized_specs=specs,
                    schema_version="1.2"
                ))
            return normalized_chunk

        except GeminiKeysExhaustedError as e:
            logger.warning("[Normalizer] All Gemini keys exhausted — skipping normalization for this chunk: %s", e)
            return [NormalizedProduct(raw=r, product_type="Unknown", normalized_specs={"is_relevant": True}, schema_version="0") for r in chunk]

        except Exception as e:
            logger.error("[Normalizer] Chunk error: %s", e)
            return [
                NormalizedProduct(
                    raw=r,
                    product_type="Error",
                    normalized_specs={"is_relevant": True},
                    schema_version="0"
                ) for r in chunk
            ]
