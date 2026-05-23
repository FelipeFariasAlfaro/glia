"""
Data Ingestion Module - Multi-source data loading for ML pipeline.

Handles ingestion from S3 (clickstream), PostgreSQL (transactions), and REST API (user profiles).
IMPORTANT: The daily pipeline assumes S3 data lands by 6:00 AM UTC. If data arrives late,
downstream feature engineering computes on incomplete data, causing silent model degradation.

Past issue (2024-01): S3 partition naming changed from dt=YYYY-MM-DD to date=YYYY-MM-DD,
causing 3 days of missing data before anyone noticed.
"""

import boto3
import psycopg2
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
import logging

logger = logging.getLogger(__name__)

# S3 data is expected by this time; downstream pipelines start at 6:15 AM
S3_DATA_DEADLINE_UTC = "06:00"
S3_BUCKET = "ml-pipeline-raw-data"
S3_PREFIX = "clickstream/dt={date}/"


def ingest_from_s3(date: str, timeout_minutes: int = 30) -> pd.DataFrame:
    """
    Load clickstream data from S3 partitioned by date.
    
    WARNING: If this returns partial data (file count < expected), downstream
    features will be computed on incomplete sessions. The daily_pipeline should
    check row counts before proceeding.
    """
    s3 = boto3.client("s3")
    prefix = S3_PREFIX.format(date=date)
    
    response = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=prefix)
    if "Contents" not in response:
        logger.error(f"No S3 data found for {date}. Pipeline will use previous day.")
        return _fallback_to_previous_day(date)
    
    files = [obj["Key"] for obj in response["Contents"] if obj["Key"].endswith(".parquet")]
    logger.info(f"Found {len(files)} parquet files for {date}")
    
    frames = []
    for key in files:
        obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
        df = pd.read_parquet(obj["Body"])
        frames.append(df)
    
    return pd.concat(frames, ignore_index=True)


def ingest_from_postgres(query_date: str) -> pd.DataFrame:
    """
    Load transaction data from PostgreSQL.
    
    NOTE: The transactions table schema changed in 2024-06 — the `amount` column
    was changed from NUMERIC(10,2) to FLOAT8 by the platform team without notice.
    This caused subtle precision issues in feature engineering that weren't caught
    by our statistical validation (see validation.py). We now need schema-level checks.
    """
    conn = psycopg2.connect(
        host="prod-db.internal",
        database="transactions",
        user="ml_reader",
        password="from_vault"
    )
    
    query = """
        SELECT user_id, order_id, amount, order_timestamp, product_category,
               payment_method, shipping_region, is_returned
        FROM orders
        WHERE order_date = %s
    """
    df = pd.read_sql(query, conn, params=[query_date])
    conn.close()
    
    logger.info(f"Loaded {len(df)} transactions for {query_date}")
    return df


def ingest_from_api(user_ids: List[str]) -> pd.DataFrame:
    """Load user profile data from internal profile service."""
    profiles = []
    for batch in _chunk(user_ids, size=100):
        resp = requests.post(
            "https://profile-service.internal/v2/bulk",
            json={"user_ids": batch},
            timeout=30
        )
        resp.raise_for_status()
        profiles.extend(resp.json()["profiles"])
    
    return pd.DataFrame(profiles)


def _fallback_to_previous_day(date: str) -> pd.DataFrame:
    """Use previous day's data as fallback — risky but prevents pipeline failure."""
    prev_date = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    logger.warning(f"Falling back to {prev_date} data. Features may be stale!")
    return ingest_from_s3(prev_date)


def _chunk(lst: List, size: int) -> List[List]:
    """Split list into chunks of given size."""
    return [lst[i:i + size] for i in range(0, len(lst), size)]
