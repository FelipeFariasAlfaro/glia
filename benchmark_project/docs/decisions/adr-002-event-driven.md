# ADR-002: Event-Driven Architecture for Cross-Service Communication

## Status
Accepted (January 2024)

## Context

As the application grew, direct service-to-service calls created tight coupling:
- `order_service` imported `notification_service` to send emails
- `payment_service` imported `notification_service` for payment alerts
- `inventory_service` imported `notification_service` for low-stock alerts

This meant any change to notification logic required touching multiple services. It also made testing harder (mocking notification calls everywhere) and created circular dependency risks.

## Decision

Adopt event-driven architecture using Redis pub/sub for cross-service communication. Services emit domain events; interested services subscribe to relevant channels.

## Implementation

### Event Channels (Redis pub/sub)
- `order_events`: Emitted by `order_service` (order.created, order.status_changed, order.cancelled)
- `payment_events`: Emitted by `payment_service` (payment.refunded, payment.failed, payment.disputed)
- `inventory_events`: Emitted by `inventory_service` (inventory.low_stock)

### Event Producers
- `src/services/order_service.py` → `_emit_event()` publishes to `order_events`
- `src/services/payment_service.py` → `_emit_payment_event()` publishes to `payment_events`
- `src/services/inventory_service.py` → `_emit_low_stock_alert()` publishes to `inventory_events`

### Event Consumers
- `src/services/notification_service.py` → subscribes to all channels, dispatches notifications
- `src/workers/webhook_worker.py` → consumes from `webhook_queue` (populated by notification_service)
- `src/workers/email_worker.py` → consumes from `email_queue` (populated by notification_service)

### Event Format
```json
{
  "type": "order.created",
  "payload": {
    "order_id": "uuid",
    "user_id": "uuid",
    "total": 99.99
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Trade-offs

### Benefits
1. **Loose coupling**: notification_service doesn't import order_service (or vice versa)
2. **Independent deployment**: Can modify notification logic without touching order logic
3. **Extensibility**: New consumers can subscribe without modifying producers
4. **Testability**: Services can be tested in isolation (just verify event emission)

### Drawbacks
1. **Eventual consistency**: Notifications may be delayed if Redis is slow
2. **Debugging complexity**: Harder to trace event flow across services
3. **Redis dependency**: Events are lost if Redis goes down (no persistence)
4. **No guaranteed delivery**: Redis pub/sub is fire-and-forget

### Accepted Risks
- **Lost events**: If notification_service is down when event is published, the event is lost. Accepted because notifications are not critical path.
- **Redis SPOF**: Events, sessions, rate limiting, and reservations all depend on Redis. Mitigated with Redis Sentinel in production.
- **Ordering**: Events may arrive out of order under high load. notification_service handles this gracefully (idempotent processing).

## Future Considerations
- If event loss becomes unacceptable, migrate to Redis Streams (persistent) or Kafka
- Consider adding event sourcing for order state (full audit trail)
- May need dead letter handling for failed event processing

## Related
- Architecture: docs/architecture.md (Redis dependency analysis)
- Producers: src/services/order_service.py, payment_service.py, inventory_service.py
- Consumer: src/services/notification_service.py
- Workers: src/workers/email_worker.py, webhook_worker.py
- Redis connection: src/database/connection.py (shared pool)
