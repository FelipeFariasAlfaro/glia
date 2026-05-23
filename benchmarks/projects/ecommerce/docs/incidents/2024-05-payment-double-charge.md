# Incident Post-Mortem: Payment Double-Charge (May 2024)

## Summary
A race condition between `src/services/order_service.py` and `src/services/payment_service.py` allowed concurrent requests to charge a customer twice for the same order.

## Timeline
- **May 8, 2024 14:22 UTC**: Customer support receives complaint about double charge
- **May 8, 2024 14:45 UTC**: Engineering confirms 3 customers affected in the last 24 hours
- **May 8, 2024 15:00 UTC**: Root cause identified — read-then-write race condition
- **May 8, 2024 16:30 UTC**: Fix deployed (advisory locks + idempotency keys)
- **May 8, 2024 17:00 UTC**: Affected customers refunded manually
- **May 9, 2024**: Added payment_records audit table (migration v4)

## Root Cause

The order creation flow had a **read-then-write race condition**:

```python
# VULNERABLE FLOW (simplified)
# Request A and Request B arrive simultaneously for same order

# Both read: "order not yet charged"
order = await db.get(Order, order_id)
if order.payment_intent_id is None:  # Both pass this check
    # Both proceed to charge
    intent = await payment_service.authorize(...)  # DOUBLE CHARGE
    order.payment_intent_id = intent.id
    await db.commit()
```

The window between the read (`if order.payment_intent_id is None`) and the write (`order.payment_intent_id = intent.id`) allowed a second concurrent request to also pass the check.

## How It Happened
1. Client's network was flaky, causing the browser to retry the order creation request
2. Both requests hit different API server instances simultaneously
3. Both read the order as "not yet charged" (no locking)
4. Both called Stripe to authorize payment
5. Both succeeded (Stripe doesn't know they're for the same order without idempotency key)
6. Customer was charged twice

## Fix Applied

Three layers of protection added:

### Layer 1: PostgreSQL Advisory Lock (in order_service.py)
```python
# Acquire lock before payment operations
await db.execute("SELECT acquire_order_lock($1)", order_id)
```
This prevents concurrent transactions from proceeding simultaneously for the same order.

### Layer 2: Stripe Idempotency Key (in payment_service.py)
```python
intent = stripe.PaymentIntent.create(
    ...,
    idempotency_key=idempotency_key  # Same key → same result
)
```
Even if the advisory lock fails, Stripe will return the same intent for the same key.

### Layer 3: Application-Level Check (in payment_service.py)
```python
existing = await self.redis.get(f"payment_idem:{idempotency_key}")
if existing:
    return {"intent_id": existing, "status": "already_authorized"}
```
Fast Redis check before even calling Stripe.

## Files Modified
- `src/services/order_service.py` — Added idempotency_key generation, advisory lock acquisition
- `src/services/payment_service.py` — Added Redis idempotency check, pass key to Stripe
- `src/models/order.py` — Added idempotency_key field
- `src/database/migrations.py` — Migration v4: payment_records table + advisory lock function

## Impact
- **Severity**: High (financial impact)
- **Customers affected**: 3
- **Total overcharge**: $847.32
- **Resolution**: Manual refunds processed within 24 hours

## Lessons Learned

1. **Read-then-write is always a race condition** without proper locking
2. **Idempotency keys should be generated client-side** (we now accept X-Idempotency-Key header)
3. **Multiple layers of protection** for financial operations (advisory lock + Stripe idempotency + Redis check)
4. **Audit trail is essential** — added payment_records table to track all payment operations

## Prevention Measures
- All payment-related operations now require advisory locks
- Idempotency key is required for order creation (enforced at API level)
- Added monitoring alert for duplicate payment intents per order
- Load testing with concurrent requests added to CI pipeline

## Related
- `src/services/order_service.py`: create_order() with advisory lock
- `src/services/payment_service.py`: authorize() with idempotency
- `src/database/migrations.py`: Migration v4 (payment_records + advisory lock function)
- `src/models/order.py`: idempotency_key field
