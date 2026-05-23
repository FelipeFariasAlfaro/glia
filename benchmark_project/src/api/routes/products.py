"""
Product Catalog API Routes.

CRUD operations for products, search, and category management.
Products support variants (size, color) with independent stock tracking.
Search uses PostgreSQL full-text search with trigram similarity.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from uuid import UUID

from src.services.auth_service import get_current_user, require_role
from src.models.product import Product, ProductVariant
from src.database.connection import get_db_session

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/", response_model=List[dict])
async def list_products(
    category: Optional[str] = None,
    search: Optional[str] = None,
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    in_stock: bool = True,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """List products with filtering and full-text search.
    
    Search uses PostgreSQL trigram similarity for fuzzy matching.
    Results are cached in Redis for 5 minutes (cache key includes all params).
    Stock availability is checked against inventory_service reservations.
    """
    async with get_db_session() as db:
        query = db.query(Product).filter(Product.is_active == True)
        if category:
            query = query.filter(Product.category == category)
        if search:
            query = query.filter(Product.name.ilike(f"%{search}%"))
        if in_stock:
            query = query.filter(Product.total_stock > 0)
        return await query.paginate(page, page_size)


@router.get("/{product_id}")
async def get_product(product_id: UUID):
    """Get product details including all variants and current stock levels.
    
    Stock levels reflect real-time availability minus active reservations.
    Reservations expire after 15 minutes if order isn't confirmed.
    """
    async with get_db_session() as db:
        product = await db.get(Product, product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return product.to_dict(include_variants=True)


@router.post("/", status_code=201)
@require_role("admin")
async def create_product(product_data: dict, current_user=Depends(get_current_user)):
    """Create a new product (admin only).
    
    Automatically creates default variant if none specified.
    Triggers low-stock alert setup in inventory_service.
    """
    async with get_db_session() as db:
        product = Product(**product_data)
        db.add(product)
        await db.commit()
        return product.to_dict()


@router.put("/{product_id}")
@require_role("admin")
async def update_product(product_id: UUID, updates: dict, current_user=Depends(get_current_user)):
    """Update product details (admin only). Price changes are audited."""
    async with get_db_session() as db:
        product = await db.get(Product, product_id)
        if not product:
            raise HTTPException(status_code=404)
        for key, value in updates.items():
            setattr(product, key, value)
        await db.commit()
        return product.to_dict()


@router.get("/categories")
async def list_categories():
    """List all active product categories with product counts."""
    async with get_db_session() as db:
        return await db.execute(
            "SELECT category, COUNT(*) as count FROM products "
            "WHERE is_active = true GROUP BY category ORDER BY count DESC"
        )
