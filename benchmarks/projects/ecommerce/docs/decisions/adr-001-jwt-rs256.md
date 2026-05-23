# ADR-001: JWT Signing with RS256

## Status
Accepted (March 2024)

## Context

After the March 2024 token leak incident, we needed to re-evaluate our JWT signing strategy. Previously, we used HS256 (HMAC with shared secret), which has a critical weakness: any service that can verify tokens can also forge them, because verification and signing use the same key.

During the incident, if the attacker had obtained the HS256 secret (which was stored in environment variables on all service instances), they could have forged arbitrary tokens with any user_id and role.

## Decision

Switch from HS256 to RS256 (RSA with SHA-256) for JWT signing.

## Rationale

### Security Benefits
1. **Separation of concerns**: Only the auth service holds the private key (signing). All other services only need the public key (verification).
2. **Reduced blast radius**: Compromising a verification-only service doesn't allow token forgery.
3. **Key rotation**: Can rotate the private key without updating all services simultaneously (public key can verify tokens signed by either old or new key during transition).

### Trade-offs
1. **Performance**: RS256 signing is ~10x slower than HS256. Mitigated by short token lifetime (15 min) reducing sign operations.
2. **Token size**: RS256 tokens are ~300 bytes larger. Acceptable for our use case.
3. **Key management**: Must securely store and distribute RSA key pair. Using Kubernetes secrets in production.

## Implementation

### Files Affected
- `src/utils/crypto.py` — `sign_token()` and `verify_token_signature()` use RS256
- `src/services/auth_service.py` — Loads private key for signing, public key for verification
- `src/config/settings.py` — JWT_PRIVATE_KEY and JWT_PUBLIC_KEY loaded from files

### Key Generation
```bash
# Generate 4096-bit RSA key pair
openssl genrsa -out keys/private.pem 4096
openssl rsa -in keys/private.pem -pubout -out keys/public.pem
```

### Token Structure
```json
{
  "sub": "user-uuid",
  "role": "customer",
  "session_id": "session-uuid",
  "exp": 1710000000,
  "iat": 1709999100
}
```

## Consequences

### Positive
- Token forgery requires private key access (single point, heavily guarded)
- Public key can be freely distributed to any service needing verification
- Aligns with zero-trust architecture principles

### Negative
- Slightly larger tokens (acceptable)
- Slower signing (mitigated by caching and short token lifetime)
- More complex key management (handled by infrastructure team)

## Related
- Incident: docs/incidents/2024-03-token-leak.md
- Implementation: src/utils/crypto.py, src/services/auth_service.py
- Configuration: src/config/settings.py (key loading)
