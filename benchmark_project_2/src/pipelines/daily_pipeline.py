"""
Daily ETL Pipeline - Airflow DAG for daily data processing.

Orchestrates: ingestion -> validation -> cleaning -> feature engineering -> serving refresh.
Runs at 6:15 AM UTC, assuming S3 data has landed by 6:00 AM (see ingestion.py).

CRITICAL DEPENDENCY: This pipeline assumes S3 clickstream data arrives by 6:00 AM UTC.
If data is late, the pipeline proceeds with incomplete data (or previous day's fallback),
causing features to be computed on partial sessions. This has happened 3 times in 2024.

The pipeline does NOT automatically trigger retraining — that's handled by
retraining_pipeline.py based on drift detection signals.
"""

from datetime import datetime, timedelta
from typing import Dict
import logging

# Airflow imports (DAG definition)
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.sensors.s3_key_sensor import S3KeySensor
from airflow.utils.dates import days_ago

from src.data.ingestion import ingest_from_s3, ingest_from_postgres, ingest_from_api
from src.data.validation import validate_ingested_data
from src.data.cleaning import clean_pipeline
from src.data.feature_engineering import build_features
from src.monitoring.drift_detector import check_feature_drift

logger = logging.getLogger(__name__)

# DAG configuration
DAG_ID = "daily_ml_pipeline"
SCHEDULE = "15 6 * * *"  # 6:15 AM UTC — 15 min after S3 deadline
S3_TIMEOUT_MINUTES = 30  # Wait up to 30 min for S3 data

default_args = {
    "owner": "ml-team",
    "depends_on_past": False,
    "email_on_failure": True,
    "email": ["ml-alerts@company.com"],
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


dag = DAG(
    DAG_ID,
    default_args=default_args,
    description="Daily ML feature pipeline",
    schedule_interval=SCHEDULE,
    start_date=days_ago(1),
    catchup=False,
    tags=["ml", "daily", "production"],
)


def _run_ingestion(**context):
    """
    Ingest data from all sources.
    
    WARNING: If S3 sensor times out, we proceed with fallback data.
    This means features are computed on incomplete clickstream data.
    The validation step will flag this but won't halt the pipeline
    (it's a warning, not an error).
    """
    execution_date = context["ds"]
    
    # S3 clickstream (may be incomplete if data arrived late)
    clickstream = ingest_from_s3(execution_date, timeout_minutes=S3_TIMEOUT_MINUTES)
    
    # PostgreSQL transactions
    transactions = ingest_from_postgres(execution_date)
    
    # User profiles for active users
    active_users = transactions["user_id"].unique().tolist()
    profiles = ingest_from_api(active_users)
    
    # Push to XCom for downstream tasks
    context["ti"].xcom_push(key="clickstream_rows", value=len(clickstream))
    context["ti"].xcom_push(key="transaction_rows", value=len(transactions))
    
    return {"clickstream": clickstream, "transactions": transactions, "profiles": profiles}


def _run_validation(**context):
    """Validate all ingested data sources."""
    execution_date = context["ds"]
    
    # Pull data from upstream
    data = context["ti"].xcom_pull(task_ids="ingest_data")
    
    results = []
    for source, df in data.items():
        source_results = validate_ingested_data(df, source)
        results.extend(source_results)
    
    # Check for errors (warnings are logged but don't halt)
    errors = [r for r in results if r.severity == "error" and not r.passed]
    if errors:
        raise ValueError(f"Validation failed with {len(errors)} errors: {errors}")
    
    return {"validation_passed": True, "warnings": len([r for r in results if not r.passed])}


def _run_cleaning(**context):
    """Clean all data sources."""
    data = context["ti"].xcom_pull(task_ids="ingest_data")
    
    cleaned = {}
    for source, df in data.items():
        cleaned[source] = clean_pipeline(df)
    
    return cleaned


def _run_feature_engineering(**context):
    """
    Build features from cleaned data.
    
    IMPORTANT: Features are written to the feature store with a cache TTL.
    If retraining_pipeline runs before the cache expires, it may train on
    stale features from the previous day. See feature_store.py for TTL config.
    """
    execution_date = context["ds"]
    cleaned_data = context["ti"].xcom_pull(task_ids="clean_data")
    
    # Merge all sources
    import pandas as pd
    merged = cleaned_data["transactions"].merge(
        cleaned_data["profiles"], on="user_id", how="left"
    )
    
    # Build features (writes to feature store)
    features = build_features(merged, prediction_date=execution_date)
    
    return {"features_built": len(features), "feature_count": len(features.columns)}


def _run_drift_check(**context):
    """
    Check for feature drift after new features are computed.
    
    NOTE: This checks drift on the features listed in model_config.FEATURE_LIST.
    If a new feature is added to training but not to the drift detector's
    monitored list, drift in that feature goes undetected.
    """
    execution_date = context["ds"]
    drift_results = check_feature_drift(reference_date=execution_date)
    
    if drift_results["drift_detected"]:
        logger.warning(f"Feature drift detected: {drift_results['drifted_features']}")
        # This triggers the retraining pipeline via Airflow sensor
    
    return drift_results


# Task definitions
ingest_task = PythonOperator(
    task_id="ingest_data", python_callable=_run_ingestion, dag=dag
)

validate_task = PythonOperator(
    task_id="validate_data", python_callable=_run_validation, dag=dag
)

clean_task = PythonOperator(
    task_id="clean_data", python_callable=_run_cleaning, dag=dag
)

feature_task = PythonOperator(
    task_id="build_features", python_callable=_run_feature_engineering, dag=dag
)

drift_task = PythonOperator(
    task_id="check_drift", python_callable=_run_drift_check, dag=dag
)

# Pipeline ordering
ingest_task >> validate_task >> clean_task >> feature_task >> drift_task
