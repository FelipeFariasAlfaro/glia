# Incident Post-Mortem: Target Leakage in Feature Engineering

**Date**: 2024-02-14
**Severity**: High
**Duration**: ~3 weeks undetected
**Impact**: Model appeared to have 0.95 AUC in training but actual production performance was 0.72

---

## Summary

A target leakage bug in `src/data/feature_engineering.py` caused the `hours_since_last_order` feature (later renamed to `days_since_last_order`) to use the current order's timestamp rather than strictly historical data. This leaked future information into training, inflating offline metrics while production performance was significantly lower.

## Timeline

- **2024-01-20**: New temporal feature `hours_since_last_order` added to feature engineering
- **2024-01-22**: Model retrained with new feature, AUC jumped from 0.78 to 0.95
- **2024-01-23**: Team celebrated "breakthrough" improvement
- **2024-02-05**: Production AUC monitoring showed no improvement (still ~0.72)
- **2024-02-10**: Discrepancy flagged during weekly model review
- **2024-02-14**: Root cause identified — feature was using `order_timestamp` from the prediction row itself
- **2024-02-15**: Fix deployed — strict temporal cutoff enforced

## Root Cause

In `feature_engineering.py`, the temporal feature computation used:
```python
# BUGGY CODE (before fix)
last_order_ts = df.groupby("user_id")["order_timestamp"].max()
hours_since = (datetime.now() - last_order_ts).dt.total_seconds() / 3600
```

The issue: `df` included the current order (the one we're trying to predict churn after). So `order_timestamp.max()` was the timestamp of the very event we're predicting from, which is trivially correlated with the target.

## Fix

```python
# FIXED CODE
# Filter to only orders BEFORE the prediction date
df = df[df["order_timestamp"] < prediction_date]
last_order_ts = df.groupby("user_id")["order_timestamp"].max()
days_since = (prediction_date - last_order_ts).dt.days
```

## Why It Wasn't Caught Sooner

1. **Offline metrics looked great**: 0.95 AUC is suspicious but not impossible
2. **No automated leakage detection**: We didn't have checks for temporal leakage
3. **Production monitoring gap**: We tracked production AUC but didn't compare to training AUC
4. **Auto-promotion was enabled**: The model was auto-promoted without human review

## Connection to 2024-06 Incident

This incident was only fully understood AFTER the 2024-06 model degradation incident. During that investigation, we reviewed all historical feature changes and realized the leakage had been masking the true model performance. When the leakage was fixed, the model's actual AUC (0.72-0.78) became visible, and subsequent degradation from the schema change was more impactful.

## Action Items

- [x] Fix temporal feature computation with strict cutoff
- [x] Add leakage detection tests (test_features.py)
- [x] Disable auto-promotion (require human review)
- [x] Add training vs production AUC comparison alert
- [x] Document temporal feature guidelines for team
- [ ] Implement automated feature leakage scanning tool

## Lessons Learned

1. If a feature improvement seems too good to be true, it probably is
2. Always compare training metrics to production metrics
3. Temporal features need strict cutoff enforcement
4. Auto-promotion without human review is dangerous for ML models
5. The gap between offline and online metrics is a critical monitoring signal
