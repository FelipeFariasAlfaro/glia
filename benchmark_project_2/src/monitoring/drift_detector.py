"""
Feature Drift Detection - Monitors production features for distribution shifts.

Uses Kolmogorov-Smirnov test and Population Stability Index (PSI) to detect
when feature distributions have shifted significantly from the training baseline.

CRITICAL COUPLING: This module monitors features listed in model_config.FEATURE_LIST.
If a new feature is added to the model training but NOT added to the drift detector's
monitored features, drift in that feature will go UNDETECTED, causing silent model
degradation without triggering any alerts.

The drift detector runs as part of the daily pipeline (daily_pipeline.py) and can
also trigger the retraining pipeline (retraining_pipeline.py) when drift is severe.
"""

import numpy as np
import pandas as pd
from scipy import stats
from typing import Dict, List, Tuple, Optional
from src.config.model_config import FEATURE_LIST
from src.utils.feature_store import FeatureStoreClient
import logging

logger = logging.getLogger(__name__)

# PSI thresholds (Population Stability Index)
PSI_THRESHOLD_WARNING = 0.1   # Moderate drift — log warning
PSI_THRESHOLD_CRITICAL = 0.2  # Severe drift — trigger retraining

# KS test significance level
KS_ALPHA = 0.05

# Number of bins for PSI calculation
PSI_BINS = 10

# Features to monitor — MUST match model_config.FEATURE_LIST
# If you add a feature to training, ADD IT HERE or drift goes undetected!
MONITORED_FEATURES = FEATURE_LIST  # Imported from model_config

feature_store = FeatureStoreClient()


def check_feature_drift(reference_date: str, 
                        lookback_days: int = 30) -> Dict:
    """
    Compare current feature distributions against reference baseline.
    
    Returns drift report with per-feature KS statistics and PSI scores.
    This is called by daily_pipeline.py after feature engineering completes.
    
    NOTE: Only monitors features in MONITORED_FEATURES (= model_config.FEATURE_LIST).
    Any feature not in this list is invisible to drift detection.
    """
    # Load reference distribution (training data baseline)
    reference_features = feature_store.read_features(
        feature_group="churn_prediction",
        features=MONITORED_FEATURES,
        as_of_date=reference_date,
        window_days=lookback_days
    )
    
    # Load current production features (latest day)
    current_features = feature_store.read_features(
        feature_group="churn_prediction",
        features=MONITORED_FEATURES,
        as_of_date=reference_date,
        window_days=1
    )
    
    drift_report = {
        "reference_date": reference_date,
        "drift_detected": False,
        "drifted_features": [],
        "ks_results": {},
        "psi_scores": {},
        "severity": "none",
    }
    
    for feature in MONITORED_FEATURES:
        if feature not in reference_features.columns or feature not in current_features.columns:
            logger.warning(f"Feature '{feature}' missing from data — skipping drift check")
            continue
        
        ref_values = reference_features[feature].dropna()
        cur_values = current_features[feature].dropna()
        
        # KS test
        ks_stat, ks_pvalue = _ks_test(ref_values, cur_values)
        drift_report["ks_results"][feature] = {
            "statistic": ks_stat,
            "p_value": ks_pvalue,
            "significant": ks_pvalue < KS_ALPHA
        }
        
        # PSI
        psi = _calculate_psi(ref_values, cur_values)
        drift_report["psi_scores"][feature] = psi
        
        # Check thresholds
        if psi >= PSI_THRESHOLD_CRITICAL or ks_pvalue < KS_ALPHA:
            drift_report["drifted_features"].append(feature)
            drift_report["drift_detected"] = True
    
    # Determine severity
    if len(drift_report["drifted_features"]) > 0:
        max_psi = max(drift_report["psi_scores"].values()) if drift_report["psi_scores"] else 0
        if max_psi >= PSI_THRESHOLD_CRITICAL:
            drift_report["severity"] = "critical"
        elif max_psi >= PSI_THRESHOLD_WARNING:
            drift_report["severity"] = "warning"
    
    logger.info(f"Drift check complete: {len(drift_report['drifted_features'])} features drifted")
    return drift_report


def _ks_test(reference: pd.Series, current: pd.Series) -> Tuple[float, float]:
    """Two-sample Kolmogorov-Smirnov test."""
    statistic, p_value = stats.ks_2samp(reference, current)
    return float(statistic), float(p_value)


def _calculate_psi(reference: pd.Series, current: pd.Series) -> float:
    """
    Calculate Population Stability Index (PSI).
    
    PSI < 0.1: No significant shift
    0.1 <= PSI < 0.2: Moderate shift (warning)
    PSI >= 0.2: Significant shift (action required)
    """
    # Create bins from reference distribution
    bins = np.linspace(reference.min(), reference.max(), PSI_BINS + 1)
    bins[0] = -np.inf
    bins[-1] = np.inf
    
    # Calculate proportions in each bin
    ref_counts = np.histogram(reference, bins=bins)[0]
    cur_counts = np.histogram(current, bins=bins)[0]
    
    # Normalize to proportions (add small epsilon to avoid division by zero)
    epsilon = 1e-6
    ref_props = (ref_counts + epsilon) / (ref_counts.sum() + epsilon * len(ref_counts))
    cur_props = (cur_counts + epsilon) / (cur_counts.sum() + epsilon * len(cur_counts))
    
    # PSI formula
    psi = np.sum((cur_props - ref_props) * np.log(cur_props / ref_props))
    return float(psi)


def get_drift_report(date: str) -> Dict:
    """Get the most recent drift report (used by retraining pipeline)."""
    return check_feature_drift(reference_date=date)
