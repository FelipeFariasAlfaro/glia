# ML Pipeline Operational Runbook

## Overview

This runbook covers common operational scenarios for the churn prediction ML pipeline.
Follow these procedures when responding to alerts or performing maintenance.

---

## Alert Response Procedures

### 1. Model AUC Drop (Critical)

**Alert**: "Model AUC Below Threshold" from alerts.py
**Threshold**: AUC < 0.72

**Steps**:
1. Check drift detector results: Has feature drift been detected?
2. Check data quality: Run validation.py manually on recent data
3. Check if a recent schema change occurred upstream (PostgreSQL, S3)
4. If drift is confirmed, trigger retraining: `python -m src.pipelines.retraining_pipeline`
5. If data quality issue, fix upstream and re-run daily pipeline

**Root Cause History**:
- 2024-06: PostgreSQL schema change caused silent degradation (see incidents/)
- 2024-02: Feature leakage inflated training AUC, production AUC was actually lower

### 2. Feature Drift Detected (Warning/Critical)

**Alert**: Drift PSI > 0.2 for one or more features
**Source**: drift_detector.py via daily_pipeline.py

**Steps**:
1. Identify which features drifted (check drift report)
2. Determine if drift is in top-5 importance features (see model_config.py FEATURE_IMPORTANCE)
3. If critical features drifted: trigger retraining
4. If non-critical features: monitor for 3 days, retrain if persistent
5. Investigate root cause: data source change? seasonal pattern? bug?

**IMPORTANT**: The drift detector only monitors features in model_config.FEATURE_LIST.
If a new feature was added to training but not to the monitored list, drift in that
feature will NOT trigger this alert. Check model_config.py for completeness.

### 3. High Prediction Latency (Warning)

**Alert**: P99 latency > 50ms
**Source**: serving.py metrics

**Steps**:
1. Check serving instance CPU/memory utilization
2. Check feature store cache hit rate (low hit rate = slow lookups)
3. Check if batch size increased (more concurrent requests)
4. Scale up serving instances if needed (infra_config.py AUTOSCALE settings)
5. Consider increasing prediction cache TTL if features are stable

### 4. Pipeline Failure (Critical)

**Alert**: Daily pipeline task failed
**Source**: Airflow DAG (daily_pipeline.py)

**Steps**:
1. Check which task failed (ingestion, validation, cleaning, features, drift)
2. For ingestion failures: Check S3 data availability (expected by 6:00 AM UTC)
3. For validation failures: Check error details — schema or statistical?
4. For feature failures: Check feature store connectivity
5. Re-run failed task after fixing root cause

---

## Model Promotion Procedure

### Prerequisites
- Model passes accuracy threshold (AUC > 0.70)
- Model passes ALL fairness checks (evaluation.py)
- No regression vs current production model

### Steps
1. Review model metrics in MLflow experiment tracker
2. Verify fairness report (evaluation.py output)
3. Promote via registry: `registry.promote_to_production(version_id, promoted_by="your-name")`
4. **CRITICAL**: Recalibrate alert thresholds: `alerts.recalibrate_thresholds(new_version)`
5. Monitor prediction distribution for 24 hours
6. Update dashboards if needed

### Post-Promotion Checklist
- [ ] Alert thresholds recalibrated for new model version
- [ ] Prediction cache invalidated (serving.py)
- [ ] Dashboard threshold lines updated
- [ ] On-call team notified of new model version

---

## Rollback Procedure

### When to Rollback
- Model AUC drops significantly after promotion
- Fairness violation detected in production
- Unexpected prediction distribution shift
- Business stakeholder reports incorrect predictions

### Steps
1. Execute rollback: `registry.rollback(reason="description of issue")`
2. **CRITICAL**: Recalibrate alert thresholds for rolled-back model version
3. Invalidate prediction cache in serving.py
4. Verify rolled-back model is serving correctly
5. Investigate root cause of the issue
6. File incident report if customer-impacting

---

## Retraining Procedure

### Automated (Drift-Triggered)
- Triggered by drift_detector.py when PSI > 0.2 or 2+ features drift
- Runs retraining_pipeline.py automatically
- Auto-promotion is DISABLED (requires human approval after 2024-02 incident)

### Manual Retraining
1. Ensure feature store cache is fresh: `feature_store.invalidate_cache()`
2. Run training: `python -m src.models.training --date=YYYY-MM-DD`
3. Review evaluation results (accuracy + fairness)
4. Register model: goes to "staging" in registry
5. Follow Model Promotion Procedure above

### Timing Considerations
- Feature store cache TTL is 4 hours (infra_config.py)
- If retraining within 4 hours of daily pipeline, force cache refresh
- Training batch size is tied to GPU memory — don't change independently

---

## Common Issues

| Issue | Likely Cause | Fix |
|-------|-------------|-----|
| OOM during training | Batch size too large for GPU | Check infra_config.py TRAINING_BATCH_SIZE vs MAX_GPU_MEMORY_GB |
| Stale features in training | Feature store cache not expired | Use force_refresh=True or invalidate_cache() |
| Missing drift alerts | New feature not in MONITORED_FEATURES | Add to model_config.FEATURE_LIST |
| False alerts after promotion | Thresholds not recalibrated | Run recalibrate_thresholds() |
| Incomplete daily features | S3 data arrived late (after 6 AM) | Check S3 arrival time, consider extending deadline |
