# ADR-001: XGBoost Over Deep Learning for Churn Prediction

**Status**: Accepted
**Date**: 2023-09-15
**Decision Makers**: ML Team, Engineering Lead, Product Manager

---

## Context

We needed to choose a model architecture for the customer churn prediction system. The candidates were:

1. **XGBoost** (gradient boosted trees)
2. **Deep Neural Network** (feedforward or transformer-based)
3. **Logistic Regression** (baseline)

The model would serve real-time predictions via API and be retrained periodically based on drift detection.

## Decision

We chose **XGBoost** as the primary model architecture.

## Rationale

### Performance on Tabular Data

- XGBoost consistently matches or outperforms deep learning on structured/tabular data
- Our feature set is 14 engineered features (not high-dimensional embeddings)
- Internal benchmarks showed XGBoost AUC: 0.78 vs DNN AUC: 0.76 vs LR AUC: 0.71

### Infrastructure Cost

- XGBoost inference runs on CPU (c5.2xlarge: ~$0.34/hr)
- DNN inference requires GPU (p3.2xlarge: ~$3.06/hr) — 9x more expensive
- At our prediction volume (~100K/day), CPU inference meets latency SLA (P99 < 50ms)
- Training still uses GPU for speed (tree_method="gpu_hist") but inference doesn't need it

### Interpretability

- Business stakeholders need to understand why a customer is flagged as high-risk
- XGBoost provides feature importance and SHAP values natively
- DNN explanations (LIME, integrated gradients) are approximations and less trusted
- Regulatory requirements may require model explainability in the future

### Operational Simplicity

- XGBoost models are single files (~10MB), easy to version and rollback
- No GPU serving infrastructure needed (simpler autoscaling)
- Faster retraining cycles (minutes vs hours for DNN)
- Smaller team can maintain the system

### Training Infrastructure Coupling

- XGBoost with gpu_hist uses GPU memory proportional to dataset size
- Batch size is derived from GPU memory (see infra_config.py)
- This coupling is simpler than managing GPU memory for DNN training + serving

## Consequences

### Positive
- Lower serving costs (~$2K/month vs ~$18K/month for GPU serving)
- Faster iteration (retrain in 15 min vs 2 hours)
- Better interpretability for business users
- Simpler infrastructure (CPU-only serving)

### Negative
- May miss complex non-linear interactions that DNN could capture
- If we move to embedding-based features (e.g., user behavior sequences), XGBoost is less suitable
- Feature engineering burden is higher (DNN can learn features from raw data)

### Risks
- If prediction volume grows 10x, CPU inference may not meet latency SLA
- If we add high-dimensional features (text, images), architecture may need revisiting
- GPU training dependency means batch size is coupled to infra_config (OOM risk if misconfigured)

## Alternatives Considered

### Deep Neural Network
- Rejected due to: higher cost, lower interpretability, marginal performance gain
- Would reconsider if: feature set becomes high-dimensional or sequential

### Logistic Regression
- Rejected due to: significantly lower performance (AUC 0.71 vs 0.78)
- Useful as: baseline comparison and sanity check

### Ensemble (XGBoost + DNN)
- Rejected due to: operational complexity of maintaining two models
- Would reconsider if: single model can't meet performance requirements

## Review Triggers

Revisit this decision if:
- Prediction volume exceeds 1M/day (latency concerns)
- Feature set grows beyond 50 features or includes embeddings
- AUC requirement increases above 0.85
- Team grows to support more complex infrastructure
