"""
Product Model with Variants and Pricing.

Products support multiple variants (size, color, etc.) with independent
stock tracking per variant. Pricing can vary by variant.

STOCK MANAGEMENT:
- Stock is tracked at the variant level, not product level.
- product.total_stock is a computed field (sum of variant stocks).
- Available stock = total stock - active reservations (managed by inventory_service).
- Reservations are tracked in Redis, not in this model.
"""

from uuid import UUID, uuid4
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass, field


@dataclass
class ProductVariant:
    """A specific variant of a product (e.g., "Large, Blue").
    
    Each variant has its own SKU, price, and stock level.
    Stock here is the "total" stock - available stock accounts for
    reservations tracked by inventory_service in Redis.
    """
    id: UUID = field(default_factory=uuid4)
    product_id: UUID = field(default_factory=uuid4)
    sku: str = ""
    name: str = ""  # e.g., "Large", "Blue", "Large Blue"
    attributes: dict = field(default_factory=dict)  # {"size": "L", "color": "blue"}
    price: float = 0.0
    stock: int = 0  # Total stock (not accounting for reservations)
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id), "sku": self.sku, "name": self.name,
            "attributes": self.attributes, "price": self.price,
            "stock": self.stock, "is_active": self.is_active
        }


@dataclass
class Product:
    """Product entity with category, variants, and computed stock.
    
    Search is powered by PostgreSQL full-text search with trigram similarity.
    Product listing cache is invalidated when stock changes (via inventory events).
    """
    id: UUID = field(default_factory=uuid4)
    name: str = ""
    description: str = ""
    category: str = ""
    base_price: float = 0.0  # Default price if variant doesn't override
    variants: List[ProductVariant] = field(default_factory=list)
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)  # Flexible attributes

    @property
    def total_stock(self) -> int:
        """Sum of all active variant stock levels.
        
        NOTE: This doesn't account for reservations. For real-time availability,
        use inventory_service.get_stock_levels() which subtracts active reservations.
        """
        return sum(v.stock for v in self.variants if v.is_active)

    @property
    def price(self) -> float:
        """Lowest variant price, or base_price if no variants."""
        if self.variants:
            active_prices = [v.price for v in self.variants if v.is_active and v.price > 0]
            return min(active_prices) if active_prices else self.base_price
        return self.base_price

    def to_dict(self, include_variants: bool = False) -> dict:
        """Serialize product for API response."""
        data = {
            "id": str(self.id), "name": self.name,
            "description": self.description, "category": self.category,
            "price": self.price, "total_stock": self.total_stock,
            "is_active": self.is_active
        }
        if include_variants:
            data["variants"] = [v.to_dict() for v in self.variants]
        return data
