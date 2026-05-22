"""
Model Configuration - Hyperparameters, feature lists, and training settings.

This is the SINGLE SOURCE OF TRUTH for which features the model uses.
Other modules (drift_detector, serving, feature_engineering) import FEATURE_LIST
from here to stay in sync.

CRITICAL: If you add a feature here, you MUST also ensure:
1. feature_engineering.py computes it
2. drift_detector.py monitors it (it imports FEATURE_LIST from here)
3. serving.py can access it from the feature store
4. data_contracts.py includes it in the schema

If drift_detector doesn't monitor a new feature, drift goes undetected.
If serving doesn't have the feature, predictions fail at inference time.
"""

from typing import Dict, List

# === FEATURE CONFIGURATION ===
# Master feature list — used by training, serving, and drift detection
# Order matters for model input (XGBoost uses positional features)
FEATURE_LIST: List[str] = [
    # Temporal features (recency/frequency)
    "days_since_last_order",
    "order_count_7d",
    "order_count_14d",
    "order_count_30d",
    "order_count_60d",
    "order_count_90d",
    "avg_days_between_orders",
    
    # Spending features (monetary)
    "total_spend",
    "avg_order_value",
    "std_order_value",
    "max_order_value",
    "order_count",
    
    # Behavioral features
    "category_diversity",
    "return_rate",
    
    # NOTE: 'preferred_payment' is categorical — encoded as one-hot in feature_engineering
    # Not included here as it expands to multiple columns
]

# Temporal features subset (used for leakage checks)
TEMPORAL_FEATURES: List[str] = [
    "days_since_last_order",
    "order_count_7d",
    "order_count_14d",
    "order_count_30d",
    "order_count_60d",
    "order_count_90d",
    "avg_days_between_orders",
]

# === TARGET CONFIGURATION ===
TARGET_COLUMN = "churned"
PREDICTION_HORIZON_DAYS = 30  # Predict churn within next 30 days

# === HYPERPARAMETERS ===
# Default hyperparameters (overridden by Bayesian optimization during training)
HYPERPARAMETERS: Dict = {
    "max_depth": 6,
    "learning_rate": 0.05,
    "n_estimators": 500,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "min_child_weight": 5,
    "tree_method": "gpu_hist",  # Requires GPU — see infra_config.py
    "objective": "binary:logistic",
    "eval_metric": "auc",
    "scale_pos_weight": 3.0,  # Class imbalance: ~25% churn rate
}

# === TRAINING SETTINGS ===
N_CV_FOLDS = 5
EARLY_STOPPING_ROUNDS = 50
TRAINING_LOOKBACK_DAYS = 180  # Use 6 months of historical data

# === MODEL METADATA ===
MODEL_NAME = "churn_xgboost"
MODEL_DESCRIPTION = "XGBoost binary classifier for 30-day customer churn prediction"
MODEL_OWNER = "ml-team"
MODEL_TAGS = ["churn", "xgboost", "production", "gpu"]

# === FEATURE IMPORTANCE (from last training run) ===
# Used by retraining_pipeline to prioritize which drifted features matter most
FEATURE_IMPORTANCE: Dict[str, float] = {
    "days_since_last_order": 0.25,
    "order_count_30d": 0.18,
    "avg_order_value": 0.12,
    "total_spend": 0.10,
    "order_count_7d": 0.09,
    "avg_days_between_orders": 0.08,
    "category_diversity": 0.06,
    "return_rate": 0.05,
    "std_order_value": 0.03,
    "order_count_14d": 0.02,
    "order_count_60d": 0.01,
    "order_count_90d": 0.005,
    "max_order_value": 0.003,
    "order_count": 0.002,
}
