# Architecture Overview

## System Design

This is an e-commerce platform built as a modular monolith with event-driven communication between bounded contexts. While deployed as a single service, the internal architecture follows microservices principles for future decomposition.

## Core Components

### API Layer (`src/api/routes/`)
- **auth.py**: Authentication endpoints (login, register, refresh, logout)
- **orders.py**: Order lifecycle management
- **products.py**: Product catalog with search
- **notifications.py**: Notification preferences and webhook management

### Service Layer (`src/services/`)
- **auth_service.py**: JWT management, session handling, token rotation
- **order_service.py**: Order orchestration, state machine, event emission
- **payment_service.py**: Stripe integration, idempotency, refunds
- **notification_service.py**: Multi-channel dispatch, templating, rate limiting
- **inventory_service.py**: Stock reservations, availability tracking

### Infrastructure
- **PostgreSQL**: Primary data store (users, orders, products)
- **Redis**: Sessions, rate limiting, reservations, event pub/sub, queues

## Key Architecture Decisions

### Event-Driven Communication (ADR-002)
Services communicate through Redis pub/sub events rather than direct imports:
- `order_service` emits events → `notification_service` subscribes
- `payment_service` emits events → `notification_service` subscribes
- `inventory_service` emits events → `notification_service` subscribes

This decoupling means notification logic can change without affecting core business services.

### JWT with RS256 (ADR-001)
Switched from HS256 to RS256 after the March 2024 token leak incident. RS256 allows services to verify tokens without knowing the signing key.

## Critical Dependencies

### Redis as Single Point of Failure
The Redis instance is shared across:
1. **Session storage** (auth_service) - fails CLOSED (users can't authenticate)
2. **Rate limiting** (rate_limiter) - fails OPEN (allows all requests)
3. **Inventory reservations** (inventory_service) - fails CLOSED (can't create orders)
4. **Event pub/sub** (order_service → notification_service) - notifications stop
5. **Background queues** (email_worker, webhook_worker) - deliveries stop
6. **Idempotency keys** (payment_service) - double-charge risk increases

**Mitigation**: Redis Sentinel in production for automatic failover.

### Order-Inventory Coupling
- `order_service` calls `inventory_service.reserve_stock()` synchronously
- `order_service` calls `inventory_service.release_order_reservations()` on cancellation
- `inventory_service` does NOT know about order state
- If `order_service` crashes after payment but before reservation release, stock is leaked (recovered by TTL expiry)

### Payment Race Condition (Fixed May 2024)
- `order_service` uses PostgreSQL advisory locks before calling `payment_service`
- `payment_service` uses Stripe idempotency keys as second layer of protection
- Application-level idempotency check in Redis as third layer

## Data Flow: Order Creation

```
Client → POST /orders
  → order_service.create_order()
    → inventory_service.reserve_stock() [sync, must succeed]
    → payment_service.authorize() [sync, must succeed]
    → persist order to PostgreSQL
    → emit "order.created" event to Redis pub/sub [async]
      → notification_service.handle_order_event() [subscriber]
        → queue email via email_worker
        → queue webhook via webhook_worker
```

## Background Workers

- **email_worker.py**: Consumes from `email_queue`, sends via SMTP, retries 3x
- **webhook_worker.py**: Consumes from `webhook_queue`, delivers HTTP POST, retries 5x with exponential backoff

## Security Considerations

- Passwords: bcrypt with cost factor 12
- Tokens: RS256 JWT with 15-minute access / 7-day refresh
- Token rotation: one-time-use refresh tokens with theft detection
- Encryption at rest: AES-256-CBC with random IV (fixed after March 2024 incident)
- Webhook signatures: HMAC-SHA256 per endpoint
- Rate limiting: sliding window via Redis sorted sets
