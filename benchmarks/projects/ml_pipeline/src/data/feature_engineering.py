"""
Feature Engineering Module - Creates ML features from cleaned transaction data.

Generates temporal features, aggregations, and embedding lookups for the
churn prediction model. Features are written to the feature store with versioning.

CRITICAL BUG HISTORY (2024-02): We had target leakage through `order_timestamp`.
The `hours_since_last_order` feature was computed using the CURRENT order's timestamp,
which leaked future information during training. The model appeared to have 0.95 AUC
but was actually memorizing temporal proximity to churn events. Fixed by using
only timestamps PRIOR to the prediction point.

See: docs/incidents/2024-02-feature-leak.md
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from src.utils.feature_store import FeatureStoreClient
from src.config.model_config import FEATURE_LIST, TEMPORAL_FEATURES
import logging

logger = logging.getLogger(__name__)

# Feature store client — features are cached with TTL (see feature_store.py)
# WARNING: If retraining runs before cache expires, it trains on stale features
feature_store = FeatureStoreClient()

# Lookback windows for temporal aggregations
LOOKBACK_WINDOWS = [7, 14, 30, 60, 90]


def build_features(df: pd.DataFrame, prediction_date: str) -> pd.DataFrame:
    """
    Build all features for a given prediction date.
    
    IMPORTANT: All temporal features must use data STRICTLY BEFORE prediction_date
    to avoid target leakage. This was the root cause of the 2024-02 incident.
    """
    pred_dt = pd.to_datetime(prediction_date)
    
    # Filter to only historical data (leakage prevention)
    df = df[df["order_timestamp"] < pred_dt].copy()
    
    features = pd.DataFrame({"user_id": df["user_id"].unique()})
    
    # Temporal features (using safe lookback)
    features = _add_temporal_features(features, df, pred_dt)
    
    # Aggregation features
    features = _add_aggregation_features(features, df)
    
    # Behavioral features
    features = _add_behavioral_features(features, df)
    
    # Write to feature store (cached with TTL)
    feature_store.write_features(
        features, 
        feature_group="churn_prediction",
        version=prediction_date
    )
    
    logger.info(f"Built {len(features.columns)-1} features for {len(features)} users")
    return features[["user_id"] + FEATURE_LIST]


def _add_temporal_features(features: pd.DataFrame, df: pd.DataFrame, 
                           pred_dt: datetime) -> pd.DataFrame:
    """
    Temporal features: recency, frequency, time-based patterns.
    
    BUG FIX (2024-02): Previously used df["order_timestamp"].max() per user which
    could include the prediction-day order itself. Now strictly uses pred_dt as cutoff.
    """
    user_groups = df.groupby("user_id")
    
    # Days since last order (relative to prediction date, NOT current timestamp)
    last_order = user_groups["order_timestamp"].max()
    features = features.merge(
        (pred_dt - last_order).dt.days.rename("days_since_last_order"),
        on="user_id", how="left"
    )
    
    # Order frequency in each lookback window
    for window in LOOKBACK_WINDOWS:
        cutoff = pred_dt - timedelta(days=window)
        window_orders = df[df["order_timestamp"] >= cutoff].groupby("user_id").size()
        features = features.merge(
            window_orders.rename(f"order_count_{window}d"),
            on="user_id", how="left"
        )
    
    # Average days between orders
    def avg_gap(group):
        if len(group) < 2:
            return np.nan
        sorted_ts = group.sort_values()
        gaps = sorted_ts.diff().dt.days.dropna()
        return gaps.mean()
    
    avg_gaps = user_groups["order_timestamp"].apply(avg_gap).rename("avg_days_between_orders")
    features = features.merge(avg_gaps, on="user_id", how="left")
    
    return features


def _add_aggregation_features(features: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    """Spending aggregations: total, average, std, trend."""
    user_groups = df.groupby("user_id")
    
    agg_features = user_groups["amount"].agg(
        total_spend="sum",
        avg_order_value="mean",
        std_order_value="std",
        max_order_value="max",
        order_count="count"
    ).reset_index()
    
    features = features.merge(agg_features, on="user_id", how="left")
    return features


def _add_behavioral_features(features: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    """Behavioral patterns: category diversity, return rate, payment preferences."""
    user_groups = df.groupby("user_id")
    
    # Category diversity (number of unique categories)
    cat_diversity = user_groups["product_category"].nunique().rename("category_diversity")
    features = features.merge(cat_diversity, on="user_id", how="left")
    
    # Return rate
    return_rate = user_groups["is_returned"].mean().rename("return_rate")
    features = features.merge(return_rate, on="user_id", how="left")
    
    # Preferred payment method (mode)
    pref_payment = user_groups["payment_method"].agg(
        lambda x: x.mode().iloc[0] if not x.mode().empty else "unknown"
    ).rename("preferred_payment")
    features = features.merge(pref_payment, on="user_id", how="left")
    
    return features
