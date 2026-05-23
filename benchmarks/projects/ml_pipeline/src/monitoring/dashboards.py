"""
Metrics Dashboard Generation - Creates monitoring dashboards for the ML pipeline.

Generates Grafana dashboard JSON configs and computes summary metrics
for model performance, data quality, and pipeline health.

Dashboards are refreshed every 5 minutes and show:
- Model prediction distribution (should match alert threshold ranges)
- Feature drift PSI scores over time
- Pipeline execution times and failure rates
- Data freshness and completeness metrics
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# Grafana dashboard configuration
GRAFANA_API_URL = "https://grafana.internal/api/dashboards"
DASHBOARD_REFRESH_INTERVAL = "5m"
RETENTION_DAYS = 90


@dataclass
class DashboardPanel:
    """A single panel in a Grafana dashboard."""
    title: str
    panel_type: str  # "graph", "stat", "table", "heatmap"
    query: str
    thresholds: Optional[Dict] = None


def generate_model_performance_dashboard(model_version: str) -> Dict:
    """
    Generate model performance monitoring dashboard.
    
    Panels include AUC over time, prediction distribution, and latency.
    Threshold lines are drawn from alerts.py ALERT_THRESHOLDS.
    """
    from src.monitoring.alerts import ALERT_THRESHOLDS
    
    panels = [
        DashboardPanel(
            title="Model AUC (Daily)",
            panel_type="graph",
            query='SELECT mean("auc") FROM "model_metrics" WHERE $timeFilter GROUP BY time(1d)',
            thresholds={"critical": ALERT_THRESHOLDS["model_auc_min"]}
        ),
        DashboardPanel(
            title="Prediction Score Distribution",
            panel_type="heatmap",
            query='SELECT "churn_score" FROM "predictions" WHERE $timeFilter',
            thresholds={
                "low": ALERT_THRESHOLDS["churn_score_mean_range"][0],
                "high": ALERT_THRESHOLDS["churn_score_mean_range"][1]
            }
        ),
        DashboardPanel(
            title="P99 Latency (ms)",
            panel_type="graph",
            query='SELECT percentile("latency_ms", 99) FROM "serving_metrics" WHERE $timeFilter GROUP BY time(5m)',
            thresholds={"warning": ALERT_THRESHOLDS["prediction_latency_p99_ms"]}
        ),
        DashboardPanel(
            title="Daily Prediction Count",
            panel_type="stat",
            query='SELECT count("prediction_id") FROM "predictions" WHERE $timeFilter GROUP BY time(1d)',
            thresholds={"critical": ALERT_THRESHOLDS["daily_prediction_count_min"]}
        ),
    ]
    
    return _build_grafana_dashboard(
        title=f"ML Model Performance - {model_version}",
        panels=panels,
        tags=["ml", "model", "production"]
    )


def generate_data_quality_dashboard() -> Dict:
    """Generate data quality monitoring dashboard."""
    panels = [
        DashboardPanel(
            title="Feature Null Rates",
            panel_type="graph",
            query='SELECT mean("null_rate") FROM "data_quality" WHERE $timeFilter GROUP BY "feature", time(1d)',
        ),
        DashboardPanel(
            title="Feature Drift PSI",
            panel_type="graph",
            query='SELECT "psi" FROM "drift_metrics" WHERE $timeFilter GROUP BY "feature"',
            thresholds={"warning": 0.1, "critical": 0.2}
        ),
        DashboardPanel(
            title="Data Freshness (hours)",
            panel_type="stat",
            query='SELECT last("hours_since_update") FROM "data_freshness"',
            thresholds={"warning": 24, "critical": 48}
        ),
        DashboardPanel(
            title="Row Count by Source",
            panel_type="graph",
            query='SELECT count(*) FROM "ingestion_metrics" WHERE $timeFilter GROUP BY "source", time(1d)',
        ),
    ]
    
    return _build_grafana_dashboard(
        title="Data Quality Monitoring",
        panels=panels,
        tags=["ml", "data-quality"]
    )


def generate_pipeline_health_dashboard() -> Dict:
    """Generate pipeline execution health dashboard."""
    panels = [
        DashboardPanel(
            title="Pipeline Execution Time",
            panel_type="graph",
            query='SELECT mean("duration_seconds") FROM "pipeline_runs" WHERE $timeFilter GROUP BY "task", time(1d)',
        ),
        DashboardPanel(
            title="Pipeline Failures",
            panel_type="stat",
            query='SELECT count(*) FROM "pipeline_runs" WHERE "status" = \'failed\' AND $timeFilter GROUP BY time(1d)',
        ),
        DashboardPanel(
            title="S3 Data Arrival Time",
            panel_type="graph",
            query='SELECT "arrival_hour_utc" FROM "s3_arrivals" WHERE $timeFilter',
            thresholds={"warning": 6.0}  # Should arrive by 6 AM
        ),
        DashboardPanel(
            title="Feature Store Cache Hit Rate",
            panel_type="graph",
            query='SELECT mean("cache_hit_rate") FROM "feature_store_metrics" WHERE $timeFilter GROUP BY time(1h)',
        ),
    ]
    
    return _build_grafana_dashboard(
        title="Pipeline Health",
        panels=panels,
        tags=["ml", "pipeline", "infrastructure"]
    )


def _build_grafana_dashboard(title: str, panels: List[DashboardPanel], 
                              tags: List[str]) -> Dict:
    """Build Grafana dashboard JSON structure."""
    dashboard = {
        "dashboard": {
            "title": title,
            "tags": tags,
            "refresh": DASHBOARD_REFRESH_INTERVAL,
            "time": {"from": f"now-{RETENTION_DAYS}d", "to": "now"},
            "panels": [
                {
                    "id": i + 1,
                    "title": panel.title,
                    "type": panel.panel_type,
                    "targets": [{"rawSql": panel.query}],
                    "thresholds": panel.thresholds or {},
                }
                for i, panel in enumerate(panels)
            ]
        },
        "overwrite": True,
    }
    return dashboard


def publish_dashboards(model_version: str):
    """Publish all dashboards to Grafana."""
    import requests
    
    dashboards = [
        generate_model_performance_dashboard(model_version),
        generate_data_quality_dashboard(),
        generate_pipeline_health_dashboard(),
    ]
    
    for dashboard in dashboards:
        try:
            resp = requests.post(GRAFANA_API_URL, json=dashboard, timeout=30)
            resp.raise_for_status()
            logger.info(f"Published dashboard: {dashboard['dashboard']['title']}")
        except Exception as e:
            logger.error(f"Failed to publish dashboard: {e}")
