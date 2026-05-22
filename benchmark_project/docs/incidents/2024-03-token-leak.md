# Incident Post-Mortem: Token Leak (March 2024)

## Summary
A cryptographic vulnerability in `src/utils/crypto.py` allowed an attacker with Redis read access to recover JWT tokens stored encrypted at rest.

## Timeline
- **March 12, 2024 09:00 UTC**: Security researcher reports that encrypted tokens in Redis show patterns (identical ciphertext for same session)
- **March 12, 2024 10:30 UTC**: Engineering confirms the issue — deterministic IV in AES-CBC encryption
- **March 12, 2024 11:00 UTC**: Incident declared, all hands on deck
- **March 12, 2024 13:00 UTC**: Fix deployed (random IV generation)
- **March 12, 2024 13:30 UTC**: All existing sessions invalidated, users forced to re-login
- **March 12, 2024 14:00 UTC**: Token expiry reduced from 1 hour to 15 minutes

## Root Cause

The `encrypt_at_rest()` function in `src/utils/crypto.py` used a **deterministic IV** derived from the session ID:

```python
# VULNERABLE CODE (removed)
iv = hashlib.md5(session_id.encode()).digest()
```

This meant that the same session always produced the same ciphertext. An attacker with Redis read access could:
1. Observe that certain ciphertext values repeated
2. Correlate encrypted tokens across time
3. Use known-plaintext attacks (since token structure is predictable)

## Impact
- **Severity**: High
- **Users affected**: Potentially all users with active sessions
- **Data exposed**: JWT tokens (containing user_id and role)
- **Exploitation confirmed**: No evidence of actual exploitation, but vulnerability was exploitable

## Fix Applied

1. **Immediate**: Changed `encrypt_at_rest()` to use `os.urandom(16)` for IV generation
2. **Immediate**: Invalidated all sessions (cleared Redis session store)
3. **Immediate**: Reduced token expiry from 1 hour to 15 minutes
4. **Follow-up**: Added token rotation (one-time-use refresh tokens) in `auth_service.py`
5. **Follow-up**: Added token reuse detection (terminates all sessions on reuse)
6. **Follow-up**: Switched from HS256 to RS256 (see ADR-001)

## Files Modified
- `src/utils/crypto.py` — Fixed IV generation (deterministic → random)
- `src/services/auth_service.py` — Added token rotation and reuse detection
- `src/config/constants.py` — Reduced TOKEN_EXPIRY_ACCESS from 3600 to 900
- `src/models/user.py` — Added token_version field for mass invalidation

## Lessons Learned

1. **Deterministic IVs are never safe for CBC mode** — even if the goal is "just encryption at rest"
2. **Defense in depth**: Token rotation means even if a token leaks, it's single-use
3. **Reduce blast radius**: Shorter token expiry limits the window of exploitation
4. **RS256 > HS256**: If the signing key leaks, HS256 allows token forgery. RS256 separates signing from verification.

## Prevention Measures
- Added security review checklist for crypto-related changes
- Automated scanning for deterministic IV patterns in CI
- Redis access now requires mTLS (previously only password auth)

## Related
- ADR-001: JWT RS256 Migration
- `src/utils/crypto.py`: encrypt_at_rest() function
- `src/services/auth_service.py`: Token rotation logic
