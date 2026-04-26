from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class RawProduct:
    title: str
    price: float
    currency: str
    url: str
    marketplace: str
    brand: Optional[str]
    model: Optional[str]
    raw_specs: dict
    description: Optional[str]
    image_url: Optional[str]
    availability: Optional[str]
    rating: Optional[float]
    reviews_count: Optional[int]
    category_path: Optional[str]
    scraped_at: datetime


@dataclass
class NormalizedProduct:
    raw: RawProduct
    product_type: str
    normalized_specs: dict
    schema_version: str


@dataclass
class SchemaField:
    key: str
    label: str
    field_type: str
    unit: Optional[str]
    required: bool
    enum_values: Optional[list]
    description: Optional[str]


@dataclass
class ProductSchema:
    product_type: str
    display_name: str
    fields: list
    auto_generated: bool
    last_updated: str
    version: str


@dataclass
class ScrapeTask:
    query: str
    session_id: str
    product_type: Optional[str]
    marketplaces: dict[str, str] # mp_name -> method (Requests/Browser)
    pages_limit: int
    use_category_urls: bool
    category_urls: dict
    skip_known_urls: bool
    direct_urls: list[str] = None
    method_preference: str = "Auto"


@dataclass
class ScrapeResult:
    task: ScrapeTask
    raw_products: list
    normalized_products: list
    schema: Optional[ProductSchema]
    errors: list
    new_products_count: int
    updated_prices_count: int
    started_at: datetime
    finished_at: datetime
