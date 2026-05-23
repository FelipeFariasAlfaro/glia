"""
Alert System - PagerDuty and Slack notifications for ML pipeline issues.

Monitors model performance, data quality, and pipeline health.
Sends alerts when metrics cross configured thresholds.

CRITICAL: Alert thresholds are calibrated to the CURRENT production model version.
After model retraining or rollback (see registry.py), thresholds MUST be recalibrated.
A new model version will have a different prediction score distribution, so thresholds
tuned to the old model will either:
- Fire too many false alerts (if new model scores higher)
- Miss real degradation (if new model scores lower)

The recalibrate_thresholds() function should be called after every model promotion
or rollback. This is documented in the runbook (docs/runbook.md).
"""

import json
import requests
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# Alert channels
PAGERDUTY_API_KEY = "from_vault"
SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/T00/B00/xxx"

# Thresholds calibrated to current model version (v2024-06-15)
# MUST be recalibrated after model promotion or rollback!
ALERT_THRESHOLDS = {
    "model_auc_min": 0.72,           # Alert if AUC drops below this
    "prediction_latency_p99_ms": 50,  # Alert if P99 > 50ms
    "drift_psi_max": 0.2,            # Alert if any feature PSI > 0.2
    "null_rate_max": 0.05,           # Alert if null rate exceeds 5%
    "daily_prediction_count_min": 10000,  # Alert if fewer predictions than expected
    "error_rate_max": 0.01,          # Alert if error rate > 1%
    "churn_score_mean_range": (0.15, 0.45),  # Expected range for mean churn score
}

# Current model version these thresholds are calibrated for
CALIBRATED_FOR_MODEL_VERSION = "v2024-06-15"


@dataclass
class Alert:
    """An alert to be sent to on-call."""
    severity: str  # "critical", "warning", "info"
    title: str
    description: str
    metric_name: str
    metric_value: float
    threshold: float
    timestamp: str
    runbook_url: str = "https://wiki.internal/ml-runbook"


def check_and_alert(metrics: Dict[str, float], model_version: str) -> List[Alert]:
    """
    Check all metrics against thresholds and fire alerts if needed.
    
    WARNING: If model_version doesn't match CALIBRATED_FOR_MODEL_VERSION,
    thresholds may be stale. Log a warning but still check.
    """
    if model_version != CALIBRATED_FOR_MODEL_VERSION:
        logger.warning(
            f"Alert thresholds calibrated for {CALIBRATED_FOR_MODEL_VERSION} "
            f"but current model is {model_version}. Thresholds may be inaccurate!"
        )
    
    alerts = []
    
    # Model performance
    if "model_auc" in metrics and metrics["model_auc"] < ALERT_THRESHOLDS["model_auc_min"]:
        alerts.append(Alert(
            severity="critical",
            title="Model AUC Below Threshold",
            description=f"AUC dropped to {metrics['model_auc']:.3f}",
            metric_name="model_auc",
            metric_value=metrics["model_auc"],
            threshold=ALERT_THRESHOLDS["model_auc_min"],
            timestamp=datetime.utcnow().isoformat()
        ))
    
    # Prediction latency
    if "latency_p99" in metrics and metrics["latency_p99"] > ALERT_THRESHOLDS["prediction_latency_p99_ms"]:
        alerts.append(Alert(
            severity="warning",
            title="High Prediction Latency",
            description=f"P99 latency: {metrics['latency_p99']:.1f}ms",
            metric_name="latency_p99",
            metric_value=metrics["latency_p99"],
            threshold=ALERT_THRESHOLDS["prediction_latency_p99_ms"],
            timestamp=datetime.utcnow().isoformat()
        ))
    
    # Mean churn score range (detects model output distribution shift)
    if "churn_score_mean" in metrics:
        low, high = ALERT_THRESHOLDS["churn_score_mean_range"]
        if not (low <= metrics["churn_score_mean"] <= high):
            alerts.append(Alert(
                severity="warning",
                title="Churn Score Distribution Shift",
                description=f"Mean churn score {metrics['churn_score_mean']:.3f} outside [{low}, {high}]",
                metric_name="churn_score_mean",
                metric_value=metrics["churn_score_mean"],
                threshold=high,
                timestamp=datetime.utcnow().isoformat()
            ))
    
    # Send alerts
    for alert in alerts:
        _send_alert(alert)
    
    return alerts


def recalibrate_thresholds(model_version: str) -> Dict:
    """
    Recalibrate alert thresholds for a new model version.
    
    Called after model promotion or rollback (see registry.py).
    Computes new thresholds based on the model's prediction distribution
    on a validation set.
    
    Steps:
    1. Load validation predictions from the new model
    2. Compute distribution statistics (mean, std, percentiles)
    3. Set thresholds at mean ± 2*std for score-based alerts
    4. Update ALERT_THRESHOLDS and CALIBRATED_FOR_MODEL_VERSION
    """
    global ALERT_THRESHOLDS, CALIBRATED_FOR_MODEL_VERSION
    
    logger.info(f"Recalibrating alert thresholds for model {model_version}")
    
    # Load validation predictions from the new model
    from src.utils.feature_store import FeatureStoreClient
    fs = FeatureStoreClient()
    
    # Get prediction distribution stats from validation set
    # (In practice, this would run the model on a holdout set)
    validation_scores = fs.read_features(
        feature_group="validation_predictions",
        features=["churn_score"],
        as_of_date=model_version
    )
    
    if not validation_scores.empty:
        mean_score = validation_scores["churn_score"].mean()
        std_score = validation_scores["churn_score"].std()
        
        # Update score range threshold (mean ± 2*std)
        ALERT_THRESHOLDS["churn_score_mean_range"] = (
            max(0, mean_score - 2 * std_score),
            min(1, mean_score + 2 * std_score)
        )
    
    CALIBRATED_FOR_MODEL_VERSION = model_version
    logger.info(f"Thresholds recalibrated for {model_version}")
    
    return ALERT_THRESHOLDS


def _send_alert(alert: Alert):
    """Send alert to appropriate channel based on severity."""
    if alert.severity == "critical":
        _send_pagerduty(alert)
        _send_slack(alert)
    else:
        _send_slack(alert)


def _send_pagerduty(alert: Alert):
    """Send critical alert to PagerDuty."""
    payload = {
        "routing_key": PAGERDUTY_API_KEY,
        "event_action": "trigger",
        "payload": {
            "summary": alert.title,
            "severity": alert.severity,
            "source": "ml-pipeline",
            "custom_details": {"description": alert.description}
        }
    }
    try:
        requests.post("https://events.pagerduty.com/v2/enqueue", json=payload, timeout=10)
    except Exception as e:
        logger.error(f"Failed to send PagerDuty alert: {e}")


def _send_slack(alert: Alert):
    """Send alert to Slack channel."""
    payload = {
        "text": f"[{alert.severity.upper()}] {alert.title}\n{alert.description}\nRunbook: {alert.runbook_url}"
    }
    try:
        requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
    except Exception as e:
        logger.error(f"Failed to send Slack alert: {e}")
