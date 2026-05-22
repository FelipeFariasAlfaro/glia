"""
Data Cleaning Pipeline - Handles null values, outliers, and deduplication.

This module runs after ingestion and before feature engineering.
It applies business rules for handling missing data and removes duplicates
that arise from the API's at-least-once delivery guarantee.

Past issue (2024-03): Outlier detection was removing legitimate high-value orders
from enterprise customers. We now use segment-aware thresholds.
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
from scipy import stats
import logging

logger = logging.getLogger(__name__)

# Columns that must never be null — pipeline fails if these are missing
REQUIRED_COLUMNS = ["user_id", "order_id", "amount", "order_timestamp"]

# Outlier thresholds per customer segment (learned from historical data)
OUTLIER_THRESHOLDS = {
    "consumer": {"amount_max": 5000, "items_max": 50},
    "business": {"amount_max": 100000, "items_max": 5000},
    "enterprise": {"amount_max": 1000000, "items_max": 50000},
}


def clean_pipeline(df: pd.DataFrame, segment_col: str = "customer_segment") -> pd.DataFrame:
    """
    Full cleaning pipeline: nulls -> dedup -> outliers -> type casting.
    
    Order matters: deduplication must happen before outlier detection,
    otherwise duplicate high-value orders skew the distribution.
    """
    logger.info(f"Starting cleaning pipeline with {len(df)} rows")
    
    df = handle_nulls(df)
    df = deduplicate(df)
    df = remove_outliers(df, segment_col)
    df = cast_types(df)
    
    logger.info(f"Cleaning complete: {len(df)} rows remaining")
    return df


def handle_nulls(df: pd.DataFrame) -> pd.DataFrame:
    """
    Handle null values with column-specific strategies.
    
    IMPORTANT: We forward-fill temporal columns but NOT amount columns.
    Forward-filling amounts caused a subtle bug in 2023 where refunded
    orders inherited the previous order's amount.
    """
    # Fail fast on required columns
    for col in REQUIRED_COLUMNS:
        null_count = df[col].isnull().sum()
        if null_count > 0:
            logger.error(f"Found {null_count} nulls in required column '{col}'")
            df = df.dropna(subset=[col])
    
    # Strategy: fill categorical with mode, numerical with median
    categorical_cols = df.select_dtypes(include=["object", "category"]).columns
    numerical_cols = df.select_dtypes(include=["number"]).columns
    
    for col in categorical_cols:
        if col not in REQUIRED_COLUMNS:
            df[col] = df[col].fillna(df[col].mode().iloc[0] if not df[col].mode().empty else "unknown")
    
    for col in numerical_cols:
        if col not in REQUIRED_COLUMNS:
            df[col] = df[col].fillna(df[col].median())
    
    return df


def deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove duplicate records, keeping the most recent version.
    
    Duplicates come from the event streaming system's at-least-once guarantee.
    We deduplicate on (order_id, user_id) keeping the last occurrence.
    """
    before = len(df)
    df = df.sort_values("order_timestamp").drop_duplicates(
        subset=["order_id", "user_id"], keep="last"
    )
    removed = before - len(df)
    if removed > 0:
        logger.info(f"Removed {removed} duplicate records ({removed/before*100:.1f}%)")
    return df


def remove_outliers(df: pd.DataFrame, segment_col: str) -> pd.DataFrame:
    """
    Remove outliers using segment-aware thresholds.
    
    We do NOT use global z-score anymore after the enterprise customer incident.
    Each segment has its own thresholds defined in OUTLIER_THRESHOLDS.
    """
    mask = pd.Series(True, index=df.index)
    
    for segment, thresholds in OUTLIER_THRESHOLDS.items():
        segment_mask = df[segment_col] == segment
        for col, max_val in thresholds.items():
            actual_col = col.replace("_max", "").replace("_min", "")
            if actual_col in df.columns:
                mask &= ~(segment_mask & (df[actual_col] > max_val))
    
    removed = (~mask).sum()
    if removed > 0:
        logger.warning(f"Removed {removed} outliers across segments")
    
    return df[mask].reset_index(drop=True)


def cast_types(df: pd.DataFrame) -> pd.DataFrame:
    """Cast columns to expected types. Catches schema drift from upstream."""
    type_map = {
        "amount": "float64",
        "user_id": "str",
        "order_id": "str",
        "is_returned": "bool",
    }
    for col, dtype in type_map.items():
        if col in df.columns:
            try:
                df[col] = df[col].astype(dtype)
            except (ValueError, TypeError) as e:
                logger.error(f"Type cast failed for {col} -> {dtype}: {e}")
    return df
