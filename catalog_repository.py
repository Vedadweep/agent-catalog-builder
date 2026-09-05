"""
Repository pattern: this class is the ONLY place that knows catalog.yaml exists.
If we later swap YAML for a real database, only this file changes —
BuyerAgent and everything else stays untouched. This is the Dependency
Inversion Principle in action: high-level modules (BuyerAgent) depend on
this repository's interface, not on the storage detail underneath it.
"""

import yaml
from typing import Optional
from schema import Product


class CatalogRepository:
    def __init__(self, catalog_path: str = "catalog.yaml"):
        self._catalog_path = catalog_path
        self._products: list[Product] = []
        self._loaded = False

    def load(self) -> None:
        """Loads and validates the catalog from disk. Fails loudly on schema drift
        rather than silently serving bad data — important for an agent-readable
        catalog where a downstream AI buyer trusts this data is well-formed."""
        with open(self._catalog_path, "r") as f:
            raw = yaml.safe_load(f)

        self._products = [Product(**p) for p in raw.get("products", [])]
        self._loaded = True

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    def get_all(self) -> list[Product]:
        self._ensure_loaded()
        return self._products

    def find_by_category(self, category: str) -> list[Product]:
        self._ensure_loaded()
        return [p for p in self._products if category.lower() in p.category.lower()]

    def find_in_price_range(self, min_price: float = 0, max_price: float = float("inf")) -> list[Product]:
        self._ensure_loaded()
        return [p for p in self._products if min_price <= p.price.amount <= max_price]

    def find_variant_available(self, attribute: str, value: str) -> list[Product]:
        """e.g. find_variant_available('size', '9') -> products with a size=9
        variant that isn't out_of_stock."""
        self._ensure_loaded()
        matches = []
        for product in self._products:
            for variant in product.variants:
                if (
                    variant.attribute.lower() == attribute.lower()
                    and variant.value.lower() == value.lower()
                    and variant.availability != "out_of_stock"
                ):
                    matches.append(product)
                    break
        return matches

    def find_by_tag(self, tag: str) -> list[Product]:
        self._ensure_loaded()
        return [p for p in self._products if any(tag.lower() in t.lower() for t in p.tags)]
    
    def find_by_keyword(self, keyword: str) -> list[Product]:
        """Fuzzy match: checks category, tags, and name together, normalizing
        simple plurals (t-shirts vs t-shirt) so minor phrasing differences
        between customer language and merchant data don't cause false misses."""
        def normalize(s: str) -> str:
            return s.lower().strip().rstrip("s")

        self._ensure_loaded()
        kw = normalize(keyword)
        results = []
        for p in self._products:
            haystacks = [normalize(p.category), normalize(p.name)] + [normalize(t) for t in p.tags]
            if any(kw in h or h in kw for h in haystacks):
                results.append(p)
        return results