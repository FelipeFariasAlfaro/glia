# ADR-002: Centralized Feature Store

**Status**: Accepted
**Date**: 2023-11-20
**Decision Makers**: ML Team, Data Engineering, Platform Team

---

## Context

Features were being computed in multiple places:
- Training pipeline computed features from raw data
- Serving endpoint re-computed features at inference time
- A/B tests used yet another feature computation path

This led to training-serving skew (features computed differently in training vs serving),
duplicated computation, and inconsistent feature definitions across teams.

## Decision

We adopted a **centralized feature store** (Feast-based) as the single source of truth
for all ML features. Both training and serving read from the same store.

## Rationale

### Training-Serving Consistency

- Before: Training computed features in batch (Spark), serving computed in real-time (Python)
- Subtle differences in aggregation logic caused training-serving skew
- Feature store ensures both paths read the same pre-computed values

### Feature Reuse

- Multiple models can share features (churn, LTV, recommendation)
- Feature engineering runs once, results are shared
- Reduces compute costs by ~40% vs redundant computation

### Point-in-Time Correctness

- Feature store supports point-in-time joins (critical for avoiding leakage)
- Training can request "features as of date X" without risk of future data leaking in
- This directly addresses the 2024-02 feature leakage incident

### Versioning and Lineage

- Features are versioned by date
- Can trace which feature version was used for which model version
- Enables reproducible training runs

## Architecture

```
[Daily Pipeline] -> [Feature Engineering] -> [Feature Store (Feast)]
                                                    |
                                    +---------------+---------------+
                                    |                               |
                            [Training Pipeline]              [Serving API]
                            (reads historical)               (reads online)
```

## Caching Strategy

The feature store client (`src/utils/feature_store.py`) implements local caching:
- **Cache TTL**: 4 hours (configured in `infra_config.py`)
- **Purpose**: Reduce latency for serving (avoid hitting Feast on every request)
- **Risk**: Stale features if retraining runs before cache expires

### Cache TTL Trade-off

| TTL | Serving Latency | Freshness Risk | Training Impact |
|-----|----------------|----------------|-----------------|
| 1 hour | Higher (more cache misses) | Low | Low |
| 4 hours (chosen) | Good | Medium | Medium — must force refresh |
| 24 hours | Best | High | High — always stale for retraining |

We chose 4 hours as a balance. The retraining pipeline explicitly calls
`invalidate_cache()` before training to mitigate staleness.

## Consequences

### Positive
- Eliminated training-serving skew
- Single feature definition shared across all consumers
- Point-in-time correctness prevents leakage
- Feature reuse across models
- Clear ownership and versioning

### Negative
- Added infrastructure complexity (Feast cluster, Redis for online store)
- Cache TTL introduces staleness risk for retraining
- Single point of failure (if feature store is down, serving degrades)
- Migration effort from existing ad-hoc feature computation

### Operational Considerations
- Feature store cache TTL (4 hours) means retraining must force-refresh
- Daily pipeline writes features, but cache may serve old values to other consumers
- Feature store availability is critical for serving — needs high availability setup
- Write-after-read consistency is NOT guaranteed within the cache TTL window

## Alternatives Considered

### Compute Features On-the-Fly
- Rejected: Training-serving skew, higher latency, duplicated logic
- Would reconsider if: Features become too dynamic to pre-compute

### Shared Feature Library (No Store)
- Rejected: Doesn't solve caching, versioning, or point-in-time queries
- Useful as: Complement to feature store for feature definition code

### Multiple Feature Stores per Team
- Rejected: Defeats the purpose of consistency and reuse
- Would reconsider if: Teams have fundamentally different latency requirements

## Review Triggers

Revisit this decision if:
- Feature store becomes a reliability bottleneck (>3 incidents/quarter)
- Cache staleness causes more than 1 training issue per quarter
- Feature computation needs to be real-time (sub-second freshness)
- Cost of Feast infrastructure exceeds savings from deduplication
