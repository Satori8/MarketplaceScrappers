from __future__ import annotations

from ai.schema_generator import SchemaGenerator
from core.models import ProductSchema, RawProduct


class Normalizer:
    def __init__(self, schema_generator: SchemaGenerator | None = None) -> None:
        self.schema_generator = schema_generator or SchemaGenerator()

    def normalize(self, products: list[RawProduct], schema: ProductSchema) -> list[dict]:
        payload = []
        for product in products:
            payload.append(
                {
                    "title": product.title,
                    "brand": product.brand,
                    "model": product.model,
                    "raw_specs": product.raw_specs,
                    "description": product.description,
                }
            )
        return self.schema_generator.normalize_products(payload, schema)
