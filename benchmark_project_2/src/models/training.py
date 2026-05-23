"""
Model Training Pipeline - XGBoost churn prediction model.

Trains the primary churn prediction model using features from the feature store.
Uses Bayesian hyperparameter optimization and time-series aware cross-validation.

IMPORTANT: Batch size during training is constrained by GPU memory limits defined
in infra_config.py. If you change MAX_GPU_MEMORY_GB or the model complexity without
adjusting TRAINING_BATCH_SIZE, you'll get OOM errors on the training instances.

See: docs/decisions/adr-001-xgboost-over-neural.md for why we chose XGBoost.
"""

import xgboost as xgb
import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from typing import Dict, Tuple, Optional
from src.config.model_config import (
    FEATURE_LIST, HYPERPARAMETERS, TARGET_COLUMN,
    N_CV_FOLDS, EARLY_STOPPING_ROUNDS
)
from src.config.infra_config import (
    MAX_GPU_MEMORY_GB, TRAINING_BATCH_SIZE, TRAINING_INSTANCE_TYPE
)
from src.utils.feature_store import FeatureStoreClient
from src.utils.experiment_tracker import ExperimentTracker
import logging

logger = logging.getLogger(__name__)

# Batch size is derived from GPU memory — DO NOT change independently
# See infra_config.py: TRAINING_BATCH_SIZE = int(MAX_GPU_MEMORY_GB * 1024 / 0.5)
EFFECTIVE_BATCH_SIZE = TRAINING_BATCH_SIZE

feature_store = FeatureStoreClient()
tracker = ExperimentTracker()


def train_model(
    training_date: str,
    lookback_days: int = 180,
    tune_hyperparams: bool = True
) -> Tuple[xgb.Booster, Dict]:
    """
    Train churn prediction model on historical features.
    
    WARNING: Features are loaded from the feature store which has a cache TTL.
    If this runs shortly after feature engineering, cached (stale) features may
    be returned. Ensure cache has expired or force-refresh before training.
    """
    # Load features from store (may be cached — see feature_store.py TTL)
    features_df = feature_store.read_features(
        feature_group="churn_prediction",
        features=FEATURE_LIST,
        as_of_date=training_date
    )
    
    labels_df = _load_labels(training_date, lookback_days)
    
    # Merge features with labels
    dataset = features_df.merge(labels_df, on="user_id", how="inner")
    X = dataset[FEATURE_LIST]
    y = dataset[TARGET_COLUMN]
    
    logger.info(f"Training on {len(X)} samples with {len(FEATURE_LIST)} features")
    logger.info(f"Using batch size {EFFECTIVE_BATCH_SIZE} (GPU: {MAX_GPU_MEMORY_GB}GB)")
    
    # Hyperparameter tuning (optional)
    if tune_hyperparams:
        best_params = _bayesian_optimization(X, y)
    else:
        best_params = HYPERPARAMETERS
    
    # Time-series cross-validation (no random splits — temporal ordering matters)
    cv_results = _cross_validate(X, y, best_params)
    
    # Train final model on all data
    dtrain = xgb.DMatrix(X, label=y)
    model = xgb.train(
        best_params,
        dtrain,
        num_boost_round=best_params.get("n_estimators", 500),
        early_stopping_rounds=EARLY_STOPPING_ROUNDS,
        evals=[(dtrain, "train")],
        verbose_eval=False
    )
    
    # Log experiment
    metrics = {
        "cv_auc_mean": cv_results["auc_mean"],
        "cv_auc_std": cv_results["auc_std"],
        "n_samples": len(X),
        "n_features": len(FEATURE_LIST),
        "batch_size": EFFECTIVE_BATCH_SIZE,
    }
    tracker.log_run(
        model_name="churn_xgboost",
        params=best_params,
        metrics=metrics,
        artifacts={"model": model}
    )
    
    return model, metrics


def _bayesian_optimization(X: pd.DataFrame, y: pd.Series) -> Dict:
    """Bayesian hyperparameter optimization with Optuna."""
    import optuna
    
    def objective(trial):
        params = {
            "max_depth": trial.suggest_int("max_depth", 3, 10),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "n_estimators": trial.suggest_int("n_estimators", 100, 1000),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
            "tree_method": "gpu_hist",
        }
        cv_result = _cross_validate(X, y, params)
        return cv_result["auc_mean"]
    
    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=50)
    
    return study.best_params


def _cross_validate(X: pd.DataFrame, y: pd.Series, params: Dict) -> Dict:
    """Time-series cross-validation (respects temporal ordering)."""
    tscv = TimeSeriesSplit(n_splits=N_CV_FOLDS)
    aucs = []
    
    for train_idx, val_idx in tscv.split(X):
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
        
        dtrain = xgb.DMatrix(X_train, label=y_train)
        dval = xgb.DMatrix(X_val, label=y_val)
        
        model = xgb.train(params, dtrain, num_boost_round=params.get("n_estimators", 500))
        preds = model.predict(dval)
        
        from sklearn.metrics import roc_auc_score
        aucs.append(roc_auc_score(y_val, preds))
    
    return {"auc_mean": np.mean(aucs), "auc_std": np.std(aucs)}


def _load_labels(training_date: str, lookback_days: int) -> pd.DataFrame:
    """Load churn labels: 1 if user didn't order in 30 days after observation."""
    # Labels are pre-computed and stored in the feature store
    return feature_store.read_features(
        feature_group="churn_labels",
        features=["user_id", "churned"],
        as_of_date=training_date
    )
