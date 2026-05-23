"""
Database Schema Migrations.

Manages PostgreSQL schema versioning and migration execution.
Migrations are applied in order and tracked in a migrations table.

SCHEMA OVERVIEW:
- users: Authentication and profile data
- products: Product catalog with full-text search index
- product_variants: SKU-level stock and pricing
- orders: Order header with state machine status
- order_items: Line items linking orders to product variants
- order_reservations: Links orders to inventory reservations
- notifications: User notification history
- notification_preferences: Per-user channel preferences
- webhooks: Registered webhook endpoints
- payment_records: Payment audit trail (added after double-charge incident)
"""

from typing import List
from datetime import datetime

from src.database.connection import get_db_session


MIGRATIONS: List[dict] = [
    {
        "version": 1,
        "name": "initial_schema",
        "sql": """
            CREATE TABLE IF NOT EXISTS users (
                id UUID PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                full_name VARCHAR(255) NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(50) DEFAULT 'customer',
                is_active BOOLEAN DEFAULT true,
                token_version INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW(),
                last_login TIMESTAMP
            );
            CREATE INDEX idx_users_email ON users(email);
            
            CREATE TABLE IF NOT EXISTS products (
                id UUID PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                category VARCHAR(100),
                base_price DECIMAL(10,2),
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX idx_products_category ON products(category);
            
            CREATE TABLE IF NOT EXISTS product_variants (
                id UUID PRIMARY KEY,
                product_id UUID REFERENCES products(id),
                sku VARCHAR(100) UNIQUE,
                name VARCHAR(255),
                attributes JSONB DEFAULT '{}',
                price DECIMAL(10,2),
                stock INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT true
            );
        """
    },
    {
        "version": 2,
        "name": "orders_and_payments",
        "sql": """
            CREATE TABLE IF NOT EXISTS orders (
                id UUID PRIMARY KEY,
                user_id UUID REFERENCES users(id),
                status VARCHAR(50) DEFAULT 'pending',
                total DECIMAL(10,2),
                payment_intent_id VARCHAR(255),
                idempotency_key VARCHAR(255) UNIQUE,
                created_at TIMESTAMP DEFAULT NOW(),
                confirmed_at TIMESTAMP,
                shipped_at TIMESTAMP,
                delivered_at TIMESTAMP,
                cancelled_at TIMESTAMP,
                cancellation_reason TEXT
            );
            CREATE INDEX idx_orders_user_status ON orders(user_id, status);
            
            CREATE TABLE IF NOT EXISTS order_items (
                id UUID PRIMARY KEY,
                order_id UUID REFERENCES orders(id),
                product_id UUID REFERENCES products(id),
                variant_id UUID REFERENCES product_variants(id),
                quantity INTEGER NOT NULL,
                unit_price DECIMAL(10,2),
                reservation_id VARCHAR(255)
            );
        """
    },
    {
        "version": 3,
        "name": "notifications_and_webhooks",
        "sql": """
            CREATE TABLE IF NOT EXISTS notifications (
                id UUID PRIMARY KEY,
                user_id UUID REFERENCES users(id),
                channel VARCHAR(50),
                subject VARCHAR(255),
                body TEXT,
                read_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX idx_notifications_user ON notifications(user_id, read_at);
            
            CREATE TABLE IF NOT EXISTS webhooks (
                id UUID PRIMARY KEY,
                user_id UUID REFERENCES users(id),
                url VARCHAR(500) NOT NULL,
                events TEXT[] DEFAULT '{}',
                active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """
    },
    {
        "version": 4,
        "name": "payment_audit_trail",
        "description": "Added after May 2024 double-charge incident for better payment tracking",
        "sql": """
            CREATE TABLE IF NOT EXISTS payment_records (
                id UUID PRIMARY KEY,
                order_id UUID REFERENCES orders(id),
                payment_intent_id VARCHAR(255),
                idempotency_key VARCHAR(255),
                amount DECIMAL(10,2),
                status VARCHAR(50),
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(order_id, idempotency_key)
            );
            CREATE INDEX idx_payment_records_order ON payment_records(order_id);
            
            -- Advisory lock function for preventing double-charge race condition
            CREATE OR REPLACE FUNCTION acquire_order_lock(order_uuid UUID)
            RETURNS BOOLEAN AS $$
            BEGIN
                RETURN pg_try_advisory_lock(hashtext(order_uuid::text));
            END;
            $$ LANGUAGE plpgsql;
        """
    },
    {
        "version": 5,
        "name": "fulltext_search",
        "sql": """
            -- Full-text search for products
            ALTER TABLE products ADD COLUMN IF NOT EXISTS search_vector tsvector;
            CREATE INDEX idx_products_search ON products USING gin(search_vector);
            
            -- Trigram extension for fuzzy matching
            CREATE EXTENSION IF NOT EXISTS pg_trgm;
            CREATE INDEX idx_products_name_trgm ON products USING gin(name gin_trgm_ops);
        """
    }
]


async def get_current_version() -> int:
    """Get the latest applied migration version."""
    async with get_db_session() as db:
        try:
            result = await db.fetchval(
                "SELECT MAX(version) FROM schema_migrations"
            )
            return result or 0
        except Exception:
            return 0


async def run_migrations():
    """Apply all pending migrations in order.
    
    Each migration runs in a transaction. If it fails, that migration
    is rolled back but previously applied migrations remain.
    """
    current = await get_current_version()
    
    async with get_db_session() as db:
        # Ensure migrations table exists
        await db.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name VARCHAR(255),
                applied_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        for migration in MIGRATIONS:
            if migration["version"] > current:
                async with db.transaction():
                    await db.execute(migration["sql"])
                    await db.execute(
                        "INSERT INTO schema_migrations (version, name) VALUES ($1, $2)",
                        migration["version"], migration["name"]
                    )
                print(f"Applied migration {migration['version']}: {migration['name']}")
