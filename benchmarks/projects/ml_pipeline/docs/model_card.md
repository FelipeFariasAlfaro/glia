# Model Card: Churn Prediction (XGBoost)

## Model Overview

- **Model Name**: churn_xgboost
- **Version**: v2024-06-15
- **Owner**: ML Team (ml-team@company.com)
- **Last Updated**: 2024-06-15
- **Framework**: XGBoost 1.7.6

## What It Predicts

Binary classification: Will a customer churn (no purchase) within the next 30 days?

- **Output**: Probability score [0, 1] where higher = more likely to churn
- **Risk Tiers**: Low (<0.3), Medium (0.3-0.7), High (>0.7)
- **Use Case**: Proactive retention campaigns, customer success prioritization

## Training Data

- **Source**: PostgreSQL transactions + S3 clickstream + Profile API
- **Time Range**: 180 days of historical data
- **Sample Size**: ~130K users per training run
- **Label Definition**: User made no purchase in 30 days following observation date
- **Class Balance**: ~25% churn rate (handled via scale_pos_weight=3.0)

## Features

14 features from `src/config/model_config.py`:
- Temporal: days_since_last_order, order_count_{7,14,30,60,90}d, avg_days_between_orders
- Monetary: total_spend, avg_order_value, std_order_value, max_order_value, order_count
- Behavioral: category_diversity, return_rate

## Performance Metrics

| Metric | Value | Threshold |
|--------|-------|-----------|
| AUC | 0.78 | > 0.70 |
| F1 | 0.65 | > 0.55 |
| Precision | 0.72 | - |
| Recall | 0.60 | - |

## Fairness Assessment

Evaluated across: age_group, gender, region

- Demographic parity ratio: 0.85 (threshold: > 0.80) ✓
- Equalized odds difference: 0.07 (threshold: < 0.10) ✓
- Predictive parity ratio: 0.82 (threshold: > 0.80) ✓

## Known Limitations

1. **Cold-start users**: Users with < 3 orders have unreliable predictions (insufficient history)
2. **Seasonal bias**: Model trained on non-holiday data may over-predict churn during holiday lulls
3. **Enterprise segment**: Lower accuracy for enterprise customers due to irregular purchase patterns
4. **Feature leakage risk**: Temporal features must use strict cutoff (see 2024-02 incident)

## Ethical Considerations

- Model does NOT use race, ethnicity, or income directly
- Age and region are used as features but monitored for fairness
- Retention campaigns should not be discriminatory in their targeting
- Model predictions should not be used for credit decisions or service denial

## Architecture Decision

XGBoost was chosen over deep learning (see ADR-001) because:
- Better interpretability for business stakeholders
- Lower infrastructure cost (CPU inference vs GPU)
- Comparable performance on tabular data
- Faster iteration cycles

## Monitoring

- Feature drift: Monitored via PSI and KS tests (drift_detector.py)
- Model performance: Daily AUC tracking with alert at < 0.72
- Prediction distribution: Mean score monitored for distribution shift
- Alert thresholds calibrated per model version (alerts.py)

## Incident History

- **2024-02**: Target leakage via order_timestamp (see incidents/2024-02-feature-leak.md)
- **2024-06**: Model degradation from schema change (see incidents/2024-06-model-degradation.md)
