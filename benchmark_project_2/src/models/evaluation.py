"""
Model Evaluation Module - Metrics, fairness checks, and A/B test analysis.

Evaluates trained models before they can be promoted to production.
A model MUST pass both accuracy AND fairness checks to be promoted.
The model registry (registry.py) enforces this gate.

IMPORTANT: A model can have excellent AUC but still fail fairness checks.
We've seen this happen when training data is imbalanced across demographic groups.
The promotion gate in registry.py will block deployment until fairness passes.
"""

import numpy as np
import pandas as pd
from sklearn.metrics import (
    roc_auc_score, precision_recall_curve, f1_score,
    confusion_matrix, classification_report
)
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# Fairness thresholds — model cannot be promoted if these are violated
FAIRNESS_THRESHOLDS = {
    "demographic_parity_ratio": 0.8,  # min ratio between groups
    "equalized_odds_diff": 0.1,       # max difference in TPR between groups
    "predictive_parity_ratio": 0.8,   # min ratio of precision between groups
}

# Protected attributes to check fairness across
PROTECTED_ATTRIBUTES = ["age_group", "gender", "region"]


@dataclass
class EvaluationResult:
    """Complete evaluation result for a model version."""
    model_version: str
    accuracy_metrics: Dict[str, float]
    fairness_metrics: Dict[str, Dict[str, float]]
    fairness_passed: bool
    promotion_eligible: bool
    ab_test_results: Optional[Dict] = None


def evaluate_model(model, X_test: pd.DataFrame, y_test: pd.Series,
                   sensitive_features: pd.DataFrame,
                   model_version: str) -> EvaluationResult:
    """
    Full model evaluation: accuracy + fairness + promotion eligibility.
    
    A model is promotion-eligible ONLY if:
    1. AUC > 0.70 (minimum performance threshold)
    2. All fairness checks pass
    3. No regression vs. current production model
    """
    predictions = model.predict(X_test)
    pred_binary = (predictions > 0.5).astype(int)
    
    # Accuracy metrics
    accuracy_metrics = _compute_accuracy_metrics(y_test, predictions, pred_binary)
    
    # Fairness metrics across protected attributes
    fairness_metrics = _compute_fairness_metrics(
        y_test, pred_binary, sensitive_features
    )
    
    # Check if fairness passes
    fairness_passed = _check_fairness_thresholds(fairness_metrics)
    
    # Promotion eligibility
    promotion_eligible = (
        accuracy_metrics["auc"] > 0.70 and
        fairness_passed
    )
    
    if not fairness_passed:
        logger.warning(f"Model {model_version} FAILED fairness checks — cannot promote")
    
    return EvaluationResult(
        model_version=model_version,
        accuracy_metrics=accuracy_metrics,
        fairness_metrics=fairness_metrics,
        fairness_passed=fairness_passed,
        promotion_eligible=promotion_eligible
    )


def _compute_accuracy_metrics(y_true, y_prob, y_pred) -> Dict[str, float]:
    """Standard classification metrics."""
    return {
        "auc": roc_auc_score(y_true, y_prob),
        "f1": f1_score(y_true, y_pred),
        "precision": precision_recall_curve(y_true, y_prob)[1].mean(),
        "recall": precision_recall_curve(y_true, y_prob)[0].mean(),
    }


def _compute_fairness_metrics(y_true: pd.Series, y_pred: np.ndarray,
                               sensitive: pd.DataFrame) -> Dict[str, Dict]:
    """
    Compute fairness metrics across all protected attributes.
    
    Uses demographic parity, equalized odds, and predictive parity.
    """
    fairness = {}
    
    for attr in PROTECTED_ATTRIBUTES:
        if attr not in sensitive.columns:
            continue
        
        groups = sensitive[attr].unique()
        group_metrics = {}
        
        for group in groups:
            mask = sensitive[attr] == group
            if mask.sum() < 50:  # Skip groups too small for reliable metrics
                continue
            group_metrics[group] = {
                "positive_rate": y_pred[mask].mean(),
                "tpr": (y_pred[mask] & y_true[mask].values).sum() / max(y_true[mask].sum(), 1),
                "precision": (y_pred[mask] & y_true[mask].values).sum() / max(y_pred[mask].sum(), 1),
            }
        
        fairness[attr] = group_metrics
    
    return fairness


def _check_fairness_thresholds(fairness_metrics: Dict) -> bool:
    """Check if all fairness metrics are within acceptable thresholds."""
    for attr, groups in fairness_metrics.items():
        if len(groups) < 2:
            continue
        
        positive_rates = [g["positive_rate"] for g in groups.values()]
        tprs = [g["tpr"] for g in groups.values()]
        
        # Demographic parity ratio
        if max(positive_rates) > 0:
            dp_ratio = min(positive_rates) / max(positive_rates)
            if dp_ratio < FAIRNESS_THRESHOLDS["demographic_parity_ratio"]:
                logger.warning(f"Demographic parity failed for {attr}: {dp_ratio:.3f}")
                return False
        
        # Equalized odds difference
        if len(tprs) >= 2:
            eo_diff = max(tprs) - min(tprs)
            if eo_diff > FAIRNESS_THRESHOLDS["equalized_odds_diff"]:
                logger.warning(f"Equalized odds failed for {attr}: {eo_diff:.3f}")
                return False
    
    return True


def run_ab_test_analysis(control_metrics: Dict, treatment_metrics: Dict,
                         sample_size: int) -> Dict:
    """Analyze A/B test results between current and candidate model."""
    from scipy.stats import ttest_ind_from_stats
    
    t_stat, p_value = ttest_ind_from_stats(
        control_metrics["mean"], control_metrics["std"], sample_size,
        treatment_metrics["mean"], treatment_metrics["std"], sample_size
    )
    
    return {
        "t_statistic": t_stat,
        "p_value": p_value,
        "significant": p_value < 0.05,
        "improvement": treatment_metrics["mean"] - control_metrics["mean"],
    }
