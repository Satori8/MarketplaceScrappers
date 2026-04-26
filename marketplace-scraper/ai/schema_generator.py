from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from ai.gemini_client import GeminiClient
from core.models import ProductSchema, SchemaField


logger = logging.getLogger(__name__)


class SchemaGenerator:
    def __init__(self, gemini_client: GeminiClient | None = None, config: dict | None = None) -> None:
        self.gemini = gemini_client or GeminiClient()
        self.config = config or {"gemini": {"batch_size": 20}}

    def determine_product_type(self, query: str, sample_titles: list) -> str:
        prompt = (
            "Determine the product type from the search query and sample titles.\n"
            "Return ONLY a snake_case identifier, no explanation.\n"
            "Examples: lifepo4_battery, laptop, power_bank, tv\n"
            f"Query: {query}\n"
            f"Sample titles: {sample_titles[:5]}\n"
        )
        system = "You classify product categories for e-commerce normalization."
        return self.gemini.generate(prompt, system).strip()

    def generate_schema(self, product_type: str, sample_specs: list) -> ProductSchema:
        prompt = (
            "Generate a JSON object with fields: product_type, display_name, fields.\n"
            "display_name must be Ukrainian.\n"
            "fields must be a JSON array of objects with keys:\n"
            "key, label, field_type, unit, required, enum_values, description.\n"
            "field_type must be one of: number, boolean, string, enum, range, list.\n"
            f"product_type: {product_type}\n"
            f"sample_specs: {sample_specs[:10]}"
        )
        system = "You design structured product schemas for normalization."
        payload = self.gemini.generate_json(prompt, system)

        fields_payload = payload.get("fields", []) if isinstance(payload, dict) else []
        fields: list[SchemaField] = []
        for entry in fields_payload:
            if not isinstance(entry, dict):
                continue
            fields.append(
                SchemaField(
                    key=str(entry.get("key", "")).strip(),
                    label=str(entry.get("label", "")).strip(),
                    field_type=str(entry.get("field_type", "string")).strip(),
                    unit=entry.get("unit"),
                    required=bool(entry.get("required", False)),
                    enum_values=entry.get("enum_values"),
                    description=entry.get("description"),
                )
            )

        return ProductSchema(
            product_type=str(payload.get("product_type", product_type)).strip(),
            display_name=str(payload.get("display_name", product_type)).strip(),
            fields=fields,
            auto_generated=True,
            last_updated=datetime.now(timezone.utc).isoformat(),
            version="1.0",
        )

    def normalize_products(self, products: list, schema: ProductSchema) -> list:
        batch_size = int(self.config.get("gemini", {}).get("batch_size", 20))
        if batch_size <= 0:
            batch_size = 20

        normalized_all: list[dict[str, Any]] = []
        schema_dict = {
            "product_type": schema.product_type,
            "display_name": schema.display_name,
            "fields": [
                {
                    "key": f.key,
                    "label": f.label,
                    "field_type": f.field_type,
                    "unit": f.unit,
                    "required": f.required,
                    "enum_values": f.enum_values,
                    "description": f.description,
                }
                for f in schema.fields
            ],
        }

        for start in range(0, len(products), batch_size):
            batch = products[start : start + batch_size]
            prompt = (
                "Normalize this list of product specs according to the provided schema.\n"
                "Return ONLY a JSON array where each item is a normalized specs object.\n"
                f"Schema: {schema_dict}\n"
                f"Products: {batch}"
            )
            system = "You normalize raw e-commerce specs to a strict schema."
            payload = self.gemini.generate(prompt, system)
            parsed = self._safe_parse_json_array(payload)
            normalized_all.extend(parsed)

        return normalized_all

    def _safe_parse_json_array(self, text: str) -> list[dict[str, Any]]:
        import json

        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                return [item for item in parsed if isinstance(item, dict)]
        except json.JSONDecodeError:
            logger.warning("Failed to parse normalized JSON array from Gemini.")
        return []
