"""
Experiment Tracking - MLflow-based experiment logging and comparison.

Tracks all training runs with parameters, metrics, and artifacts.
Used by training.py to log experiments and by the team to compare model versions.

Integration points:
- training.py logs each training run
- retraining_pipeline.py logs automated retraining runs
- evaluation.py metrics are attached to the run
- registry.py links model versions to experiment runs
"""

import mlflow
from mlflow.tracking import MlflowClient
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

# MLflow tracking server
MLFLOW_TRACKING_URI = "https://mlflow.internal"
EXPERIMENT_NAME = "churn-prediction"


class ExperimentTracker:
    """
    MLflow experiment tracker for the churn prediction model.
    
    Logs parameters, metrics, artifacts, and model lineage.
    Each training run gets a unique run_id that links to the model registry.
    """
    
    def __init__(self):
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        mlflow.set_experiment(EXPERIMENT_NAME)
        self.client = MlflowClient()
    
    def log_run(
        self,
        model_name: str,
        params: Dict[str, Any],
        metrics: Dict[str, float],
        artifacts: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Log a complete training run.
        
        Returns the MLflow run_id for linking to model registry.
        """
        with mlflow.start_run() as run:
            # Log parameters
            for key, value in params.items():
                mlflow.log_param(key, value)
            
            # Log metrics
            for key, value in metrics.items():
                mlflow.log_metric(key, value)
            
            # Log artifacts (model, feature importance, etc.)
            if artifacts:
                for name, artifact in artifacts.items():
                    if name == "model":
                        mlflow.xgboost.log_model(artifact, "model")
                    else:
                        mlflow.log_artifact(artifact)
            
            # Log tags
            mlflow.set_tag("model_name", model_name)
            mlflow.set_tag("training_date", datetime.utcnow().isoformat())
            if tags:
                for key, value in tags.items():
                    mlflow.set_tag(key, value)
            
            run_id = run.info.run_id
            logger.info(f"Logged experiment run {run_id} for {model_name}")
            return run_id
    
    def compare_runs(self, run_ids: List[str]) -> Dict:
        """Compare metrics across multiple runs."""
        comparison = {}
        for run_id in run_ids:
            run = self.client.get_run(run_id)
            comparison[run_id] = {
                "params": run.data.params,
                "metrics": run.data.metrics,
                "tags": run.data.tags,
            }
        return comparison
    
    def get_best_run(self, metric: str = "cv_auc_mean") -> Dict:
        """Get the best run by a specific metric."""
        experiment = self.client.get_experiment_by_name(EXPERIMENT_NAME)
        runs = self.client.search_runs(
            experiment_ids=[experiment.experiment_id],
            order_by=[f"metrics.{metric} DESC"],
            max_results=1
        )
        if runs:
            best = runs[0]
            return {
                "run_id": best.info.run_id,
                "metrics": best.data.metrics,
                "params": best.data.params,
            }
        return {}
    
    def log_drift_event(self, drift_report: Dict):
        """Log a drift detection event for tracking."""
        with mlflow.start_run(run_name="drift_detection"):
            mlflow.set_tag("event_type", "drift_detection")
            mlflow.log_param("drifted_features", json.dumps(drift_report["drifted_features"]))
            mlflow.log_metric("n_drifted_features", len(drift_report["drifted_features"]))
            mlflow.log_metric("max_psi", max(drift_report["psi_scores"].values()) if drift_report["psi_scores"] else 0)
