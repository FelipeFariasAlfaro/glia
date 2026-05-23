"""
Retraining Pipeline - Automated model retraining triggered by drift detection.

This pipeline is triggered when the drift detector (drift_detector.py) identifies
significant feature drift. It retrains the model, evaluates it, and registers
the new version for potential promotion.

CRITICAL TIMING ISSUE: This pipeline reads features from the feature store.
The feature store has a cache TTL (default 4 hours). If retraining triggers
shortly after the daily pipeline writes new features, the feature store may
still serve CACHED (stale) features from the previous version.

Mitigation: We force a cache refresh before training, but this adds latency.
See feature_store.py FeatureStoreClient.read_features(force_refresh=True).

Flow:
1. Drift detected -> trigger retraining
2. Load fresh features (force cache refresh)
3. Train new model
4. Evaluate (accuracy + fairness)
5. Register in model registry (staging)
6. If auto-promote enabled and checks pass -> promote to production
7. After promotion -> recalibrate alert thresholds
"""

from datetime import datetime
from typing import Dict, Optional
from src.models.training import train_model
from src.models.evaluation import evaluate_model
from src.models.registry import ModelRegistry
from src.monitoring.drift_detector import get_drift_report
from src.monitoring.alerts import recalibrate_thresholds
from src.utils.feature_store import FeatureStoreClient
from src.utils.experiment_tracker import ExperimentTracker
from src.config.model_config import FEATURE_LIST
import logging

logger = logging.getLogger(__name__)

# Auto-promotion: if True, models that pass all checks are promoted without human review
AUTO_PROMOTE = False  # Disabled after the 2024-02 incident — now requires human approval

feature_store = FeatureStoreClient()
registry = ModelRegistry()
tracker = ExperimentTracker()


def trigger_retraining(drift_report: Dict, execution_date: str) -> Dict:
    """
    Main retraining flow triggered by drift detection.
    
    Returns summary of retraining outcome including whether model was promoted.
    """
    logger.info(f"Retraining triggered by drift: {drift_report['drifted_features']}")
    
    # Step 1: Force refresh features to avoid stale cache
    logger.info("Forcing feature store cache refresh before training...")
    feature_store.invalidate_cache(feature_group="churn_prediction")
    
    # Step 2: Train new model
    model, train_metrics = train_model(
        training_date=execution_date,
        lookback_days=180,
        tune_hyperparams=True
    )
    
    # Step 3: Evaluate model (accuracy + fairness)
    eval_result = _evaluate_new_model(model, execution_date)
    
    # Step 4: Register in model registry
    version_id = registry.register_model(
        model=model,
        model_name="churn_xgboost",
        metrics=train_metrics,
        fairness_passed=eval_result.fairness_passed
    )
    
    # Step 5: Auto-promote if enabled and checks pass
    promoted = False
    if AUTO_PROMOTE and eval_result.promotion_eligible:
        registry.promote_to_production(version_id, promoted_by="auto-retraining")
        # Step 6: Recalibrate alert thresholds for new model
        recalibrate_thresholds(model_version=version_id)
        promoted = True
        logger.info(f"Auto-promoted model {version_id} to production")
    elif eval_result.promotion_eligible:
        logger.info(f"Model {version_id} eligible for promotion — awaiting human approval")
    else:
        logger.warning(f"Model {version_id} NOT eligible for promotion")
        if not eval_result.fairness_passed:
            logger.warning("Reason: Fairness checks failed")
    
    return {
        "version_id": version_id,
        "metrics": train_metrics,
        "fairness_passed": eval_result.fairness_passed,
        "promotion_eligible": eval_result.promotion_eligible,
        "promoted": promoted,
        "drift_trigger": drift_report["drifted_features"],
    }


def _evaluate_new_model(model, execution_date: str):
    """Evaluate the newly trained model on holdout set."""
    # Load test features (force refresh to get latest)
    test_features = feature_store.read_features(
        feature_group="churn_prediction",
        features=FEATURE_LIST,
        as_of_date=execution_date,
        force_refresh=True
    )
    
    test_labels = feature_store.read_features(
        feature_group="churn_labels",
        features=["user_id", "churned"],
        as_of_date=execution_date
    )
    
    sensitive_features = feature_store.read_features(
        feature_group="user_demographics",
        features=["user_id", "age_group", "gender", "region"],
        as_of_date=execution_date
    )
    
    # Merge and evaluate
    import pandas as pd
    dataset = test_features.merge(test_labels, on="user_id")
    dataset = dataset.merge(sensitive_features, on="user_id")
    
    return evaluate_model(
        model=model,
        X_test=dataset[FEATURE_LIST],
        y_test=dataset["churned"],
        sensitive_features=dataset[["age_group", "gender", "region"]],
        model_version=f"retrain_{execution_date}"
    )


def should_retrain(drift_report: Dict) -> bool:
    """
    Decide if drift is severe enough to trigger retraining.
    
    Criteria:
    - At least 2 features drifted significantly
    - OR any feature in the top-5 importance list drifted
    - OR PSI > 0.2 for any feature
    """
    if len(drift_report.get("drifted_features", [])) >= 2:
        return True
    
    # Check if important features drifted
    important_features = FEATURE_LIST[:5]  # Top 5 by importance
    drifted = set(drift_report.get("drifted_features", []))
    if drifted.intersection(important_features):
        return True
    
    # Check PSI threshold
    for feature, psi in drift_report.get("psi_scores", {}).items():
        if psi > 0.2:
            return True
    
    return False
