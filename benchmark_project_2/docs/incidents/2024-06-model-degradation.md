# Incident Post-Mortem: Model Performance Degradation

**Date**: 2024-06-03
**Severity**: High
**Duration**: 5 days before detection, 2 days to resolve
**Impact**: Model AUC dropped from 0.78 to 0.68, increased false negatives in churn prediction

---

## Summary

The churn prediction model experienced gradual performance degradation over 5 days after the platform team changed the PostgreSQL `orders.amount` column from `NUMERIC(10,2)` to `FLOAT8`. Our validation pipeline (validation.py) did not catch this because it only performed statistical checks (distribution shape, null rates) — not schema-level type validation. The values looked statistically similar but introduced floating-point precision errors that corrupted feature engineering calculations.

## Timeline

- **2024-05-28**: Platform team migrated `orders.amount` from NUMERIC(10,2) to FLOAT8 (no notification to ML team)
- **2024-05-29**: Daily pipeline ran successfully — validation passed (statistical checks only)
- **2024-06-01**: Subtle precision errors accumulated in aggregation features (avg_order_value, std_order_value)
- **2024-06-03**: Model AUC alert fired (dropped below 0.72 threshold)
- **2024-06-04**: Investigation began — drift detector showed no drift (features looked similar statistically)
- **2024-06-05**: Root cause identified — column type change caused precision loss
- **2024-06-06**: Schema validation added to validation.py, data contracts created
- **2024-06-07**: Model retrained on corrected features, performance restored

## Root Cause

The PostgreSQL column type change from `NUMERIC(10,2)` to `FLOAT8` caused:

1. **Precision loss**: Values like `99.99` became `99.98999999999999` in FLOAT8
2. **Aggregation errors**: When computing `avg_order_value` and `std_order_value`, these tiny errors accumulated across thousands of records
3. **Feature distribution shift**: The shift was too small for KS tests to detect (p-value remained > 0.05) but large enough to affect model predictions

## Why Validation Didn't Catch It

Our validation pipeline (`validation.py`) at the time only performed:
- Null rate checks ✓ (no change in nulls)
- Value range checks ✓ (values still in expected range)
- Distribution shape (KS test) ✓ (distributions looked similar)
- Row count checks ✓ (same number of rows)

What was MISSING:
- **Schema/type validation** ✗ — We never checked if column dtypes matched expectations
- **Precision validation** ✗ — We didn't check decimal precision
- **Data contract enforcement** ✗ — No formal contract between teams

## Connection to Feature Leak Incident (2024-02)

During this investigation, we also discovered that the 2024-02 feature leakage fix had been masking the model's true sensitivity to data quality issues. With the leakage present, the model was so overfit to temporal patterns that small precision errors didn't matter. After the leakage fix, the model relied more heavily on monetary features (avg_order_value, total_spend), making it vulnerable to precision issues in those columns.

## Fix

1. Added schema validation to `validation.py` (checks column types against data contracts)
2. Created `data_contracts.py` with formal schema definitions for each data source
3. Added the `amount` column type explicitly: `"amount": "float64"` with precision checks
4. Established communication protocol with platform team for schema changes

## Action Items

- [x] Add schema validation to validation.py
- [x] Create data contracts (data_contracts.py) for all sources
- [x] Add column type checking (not just statistical checks)
- [x] Establish schema change notification process with platform team
- [x] Retrain model on corrected data
- [x] Add precision validation for monetary columns
- [ ] Implement automated schema change detection from database metadata
- [ ] Add data contract CI checks to platform team's deployment pipeline

## Lessons Learned

1. Statistical validation alone is NOT sufficient — schema checks are essential
2. Upstream teams can change schemas without realizing downstream impact
3. Small precision errors can accumulate into significant model degradation
4. The drift detector (KS test, PSI) may not catch type-level changes
5. Data contracts between teams prevent silent breaking changes
6. The 2024-02 leakage fix made the model more sensitive to data quality (a good thing, but requires better validation)

## Metrics

| Metric | Before Incident | During Incident | After Fix |
|--------|----------------|-----------------|-----------|
| AUC | 0.78 | 0.68 | 0.78 |
| avg_order_value precision | 2 decimals | ~15 decimals | 2 decimals |
| Validation checks | Statistical only | Statistical only | Statistical + Schema |
