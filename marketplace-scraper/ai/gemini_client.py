from __future__ import annotations

import json
import logging
import threading
import time
import yaml
from collections import deque
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


class GeminiKeysExhaustedError(RuntimeError):
    """Raised when all Gemini API keys are exhausted after retrying."""


class GeminiClient:
    """
    Key rotation strategies:
    - "on_limit":    switch key only on 429 / ResourceExhausted error
    - "round_robin": advance key on every request

    Exhaustion flow:
    1. All keys tried → wait 60 s (keys may reset)
    2. Retry all keys once more
    3. If still failing → call on_keys_exhausted callback (GUI dialog for new key)
    4. If callback adds a key → continue; otherwise raise GeminiKeysExhaustedError
       so the caller (normalizer) can skip normalization gracefully.
    """

    def __init__(
        self,
        config_path: str = "config.yaml",
        on_keys_exhausted: Callable[["GeminiClient"], bool] | None = None,
    ) -> None:
        if config_path == "config.yaml":
            config_path = str(Path(__file__).resolve().parent.parent / "config.yaml")
        self.config_path = Path(config_path)
        self.config = self._load_config()
        gemini_cfg = self.config.get("gemini", {})
        self.keys: list[str] = [k.strip() for k in gemini_cfg.get("keys", []) if str(k).strip()]
        self.rotation_strategy = str(gemini_cfg.get("rotation_strategy", "on_limit"))
        self.model_name = str(gemini_cfg.get("model", "gemini-2.0-flash"))
        self.current_key_index = int(gemini_cfg.get("current_key_index", 0) or 0)

        # Rate limiter: sliding window
        self._rpm_limit: int = int(gemini_cfg.get("requests_per_minute", 15))
        self._request_times: deque = deque()
        self._rate_lock = threading.Lock()
        self._config_lock = threading.Lock()
        self._last_working_model: str | None = None

        # Callback invoked when all keys fail (GUI can ask user for a new key)
        self.on_keys_exhausted: Callable[["GeminiClient"], bool] | None = on_keys_exhausted

    # ------------------------------------------------------------------ config

    def _load_config(self) -> dict[str, Any]:
        if not self.config_path.exists():
            logger.warning("Config file does not exist: %s", self.config_path)
            return {}
        with self.config_path.open("r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}

    def _save_config(self) -> None:
        """Persist current keys list and key index back to config.yaml."""
        with self._config_lock:
            # Re-load to get latest changes from other threads
            cfg = self._load_config()
            cfg.setdefault("gemini", {})
            cfg["gemini"]["keys"] = self.keys
            cfg["gemini"]["current_key_index"] = self.current_key_index
            with self.config_path.open("w", encoding="utf-8") as fh:
                yaml.safe_dump(cfg, fh, allow_unicode=True, sort_keys=False)

    def add_key(self, new_key: str) -> None:
        """Add a new API key at runtime and persist it to config.yaml."""
        new_key = new_key.strip()
        if new_key and new_key not in self.keys:
            self.keys.append(new_key)
            logger.info("[Gemini] New key added (total: %d).", len(self.keys))
            self._save_config()

    # ------------------------------------------------------------------ genai

    def _get_client(self, key_index: int):
        from google import genai  # lazy import
        return genai.Client(api_key=self.keys[key_index])

    @staticmethod
    def _is_rate_limit_error(exc: Exception) -> bool:
        text = str(exc).lower()
        return "429" in text or "resource_exhausted" in text or "rate_limit" in text or "quota" in text

    # ------------------------------------------------------------------ rate limiter

    def _wait_for_rate_limit(self) -> None:
        """Sliding-window rate limiter. Lock released during sleep."""
        while True:
            with self._rate_lock:
                now = time.monotonic()
                while self._request_times and now - self._request_times[0] >= 60.0:
                    self._request_times.popleft()
                if len(self._request_times) < self._rpm_limit:
                    self._request_times.append(now)
                    return
                wait_for = 60.0 - (now - self._request_times[0])
            logger.info(
                "[Gemini] Rate limit (%d rpm). Waiting %.1fs...",
                self._rpm_limit, wait_for,
            )
            time.sleep(max(wait_for, 0.5))

    # ------------------------------------------------------------------ generate

    def generate(self, prompt: str, system: str) -> str:
        """
        Send a prompt using the new google-genai SDK.
        """
        if not self.keys:
            raise GeminiKeysExhaustedError("No Gemini API keys configured.")

        from google.genai import types

        self._wait_for_rate_limit()

        # Use the last working model first to save time
        model_variants = []
        if self._last_working_model:
            model_variants.append(self._last_working_model)
        
        # B6 fix: removed hallucinated model names (gemini-3.1/3-flash-preview don't exist).
        # Every call was wasting 2 API round-trips on guaranteed 404s.
        defaults = [
            "models/gemini-2.5-flash-preview-04-17",
            "models/gemini-2.5-flash",
            "models/gemini-2.0-flash",
            "models/gemini-1.5-flash",
        ]
        for d in defaults:
            if d not in model_variants:
                model_variants.append(d)
        
        if self.model_name:
             nm = self.model_name if self.model_name.startswith("models/") else f"models/{self.model_name}"
             if nm not in model_variants:
                 model_variants.append(nm)
        
        model_variants = [m for m in model_variants if m]

        for pass_number in range(3):
            tried_keys = 0
            start_key_index = self.current_key_index % len(self.keys)

            while tried_keys < len(self.keys):
                key_index = (start_key_index + tried_keys) % len(self.keys)
                self.current_key_index = key_index
                
                # Create a client for the current key
                client = self._get_client(key_index)
                logger.info("[Gemini] Using key index %d / %d.", key_index + 1, len(self.keys))

                for model_variant in model_variants:
                    try:
                        response = client.models.generate_content(
                            model=model_variant,
                            contents=prompt,
                            config=types.GenerateContentConfig(
                                system_instruction=system,
                                http_options={'timeout': 60000} # 60s in ms
                            )
                        )
                        text = response.text or ""
                        if text:
                            logger.info("[Gemini] Generation successful (%s). Parsing JSON...", model_variant)
                            self._last_working_model = model_variant
                        
                        if self.rotation_strategy == "round_robin":
                            new_index = (key_index + 1) % len(self.keys)
                            if new_index != self.current_key_index:
                                self.current_key_index = new_index
                                # B8 fix: only persist when key index actually changes.
                                # Previously called on every generation → heavy disk I/O + thread race.
                                self._save_config()
                        
                        return text.strip()

                    except Exception as exc:
                        exc_str = str(exc).lower()
                        is_rate = self._is_rate_limit_error(exc)
                        is_timeout = any(t in exc_str for t in ["deadline", "timeout", "504"])
                        is_not_found = "not found" in exc_str or "404" in exc_str

                        if is_timeout or is_rate:
                            reason = "rate-limited" if is_rate else "timed out"
                            logger.warning("[Gemini] Key %d %s. Rotating key.", key_index + 1, reason)
                            break # Next KEY

                        if is_not_found:
                            logger.warning("[Gemini] Key %d Model %s not found. Trying next.", key_index+1, model_variant)
                            continue
                        else:
                            logger.error("[Gemini] Key %d unexpected error: %s", key_index + 1, exc)
                            break 

                tried_keys += 1

            # Recovery logic after all keys exhausted in pass
            if pass_number == 0:
                logger.warning("[Gemini] All keys exhausted. Waiting 60s before retry...")
                time.sleep(60)
                continue
            if pass_number == 1 and self.on_keys_exhausted:
                if self.on_keys_exhausted(self):
                    continue
                raise GeminiKeysExhaustedError("All keys exhausted after retry.")

        raise GeminiKeysExhaustedError("Exhausted all recovery attempts.")

    def check_keys_status(self) -> list[dict[str, Any]]:
        from google.genai import types
        model_variants = [
            "models/gemini-3.1-flash-preview",
            "models/gemini-3-flash-preview",
            "models/gemini-2.5-flash",
            "models/gemini-2.0-flash",
            "models/gemini-1.5-flash"
        ]
        report = []
        
        for i, key in enumerate(self.keys):
            key_status = {"index": i, "key": key[:10] + "..." + key[-4:], "models": {}}
            client = self._get_client(i)
            for model_name in model_variants:
                try:
                    client.models.generate_content(
                        model=model_name,
                        contents="test",
                        config=types.GenerateContentConfig(http_options={'timeout': 10000})
                    )
                    key_status["models"][model_name] = "OK"
                except Exception as e:
                    err = str(e).lower()
                    if any(t in err for t in ["429", "quota", "limit", "exhausted"]):
                        key_status["models"][model_name] = "EXHAUSTED"
                    elif "not found" in err or "404" in err:
                        key_status["models"][model_name] = "NOT_FOUND"
                    else:
                        key_status["models"][model_name] = "ERROR"
            report.append(key_status)
        return report


    # ------------------------------------------------------------------ JSON helper

    def _strip_markdown_fences(self, text: str) -> str:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
        return cleaned

    def generate_json(self, prompt: str, system: str) -> dict:
        for attempt in range(3):
            try:
                raw = self.generate(prompt, system)
            except GeminiKeysExhaustedError:
                raise  # let normalizer handle gracefully
            cleaned = self._strip_markdown_fences(raw)
            try:
                parsed = json.loads(cleaned)
                return parsed if isinstance(parsed, (dict, list)) else {}
            except json.JSONDecodeError:
                logger.warning("[Gemini] JSON parse failed (attempt %d/3).", attempt + 1)
        logger.error("[Gemini] JSON parse failed after 3 attempts.")
        return {}
