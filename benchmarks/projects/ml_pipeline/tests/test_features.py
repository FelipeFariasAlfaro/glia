"""
Feature Engineering Tests - Validates feature correctness and leakage prevention.

These tests were added after the 2024-02 target leakage incident.
They specifically verify that temporal features do NOT use future information.

Key test categories:
1. Temporal leakage prevention (no future data in features)
2. Feature value correctness (aggregations compute correctly)
3. Feature completeness (all features in FEATURE_LIST are produced)
4. Edge cases (new users, single-order users, etc.)
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from src.data.feature_engineering import build_features, _add_temporal_features
from src.config.model_config import FEATURE_LIST, TEMPORAL_FEATURES


@pytest.fixture
def sample_transactions():
    """Create sample transaction data for testing."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", "2024-03-31", freq="D")
    
    records = []
    for user_id in range(1, 51):
        n_orders = np.random.randint(3, 20)
        order_dates = np.random.choice(dates, size=n_orders, replace=False)
        for i, date in enumerate(sorted(order_dates)):
            records.append({
                "user_id": str(user_id),
                "order_id": f"order_{user_id}_{i}",
                "amount": np.random.uniform(10, 500),
                "order_timestamp": date,
                "product_category": np.random.choice(["electronics", "clothing", "food"]),
                "payment_method": np.random.choice(["credit", "debit", "paypal"]),
                "is_returned": np.random.random() < 0.1,
            })
    
    return pd.DataFrame(records)


class TestTemporalLeakagePrevention:
    """Tests that verify no future information leaks into features."""
    
    def test_no_future_orders_in_features(self, sample_transactions):
        """
        CRITICAL: Features must only use data BEFORE the prediction date.
        This is the exact bug that caused the 2024-02 incident.
        """
        prediction_date = "2024-03-01"
        
        with patch("src.data.feature_engineering.feature_store") as mock_fs:
            mock_fs.write_features = MagicMock()
            features = build_features(sample_transactions, prediction_date)
        
        # Verify: no order after prediction_date influenced the features
        future_orders = sample_transactions[
            sample_transactions["order_timestamp"] >= pd.to_datetime(prediction_date)
        ]
        future_users = set(future_orders["user_id"].unique())
        
        # Users with ONLY future orders should have NaN temporal features
        only_future_users = future_users - set(
            sample_transactions[
                sample_transactions["order_timestamp"] < pd.to_datetime(prediction_date)
            ]["user_id"].unique()
        )
        
        for user_id in only_future_users:
            user_features = features[features["user_id"] == user_id]
            if not user_features.empty:
                assert user_features["days_since_last_order"].isna().all(), \
                    f"User {user_id} has temporal features but only has future orders!"
    
    def test_days_since_last_order_uses_prediction_date(self, sample_transactions):
        """days_since_last_order must be relative to prediction_date, not current time."""
        prediction_date = "2024-02-15"
        pred_dt = pd.to_datetime(prediction_date)
        
        with patch("src.data.feature_engineering.feature_store") as mock_fs:
            mock_fs.write_features = MagicMock()
            features = build_features(sample_transactions, prediction_date)
        
        # For each user, verify days_since_last_order is correct
        historical = sample_transactions[sample_transactions["order_timestamp"] < pred_dt]
        
        for _, row in features.iterrows():
            user_orders = historical[historical["user_id"] == row["user_id"]]
            if not user_orders.empty:
                expected_days = (pred_dt - user_orders["order_timestamp"].max()).days
                assert row["days_since_last_order"] == expected_days, \
                    f"Expected {expected_days} days, got {row['days_since_last_order']}"
    
    def test_order_count_windows_respect_cutoff(self, sample_transactions):
        """Order count features must only count orders before prediction date."""
        prediction_date = "2024-03-01"
        pred_dt = pd.to_datetime(prediction_date)
        
        with patch("src.data.feature_engineering.feature_store") as mock_fs:
            mock_fs.write_features = MagicMock()
            features = build_features(sample_transactions, prediction_date)
        
        # Verify 30-day window
        window_start = pred_dt - timedelta(days=30)
        historical = sample_transactions[
            (sample_transactions["order_timestamp"] >= window_start) &
            (sample_transactions["order_timestamp"] < pred_dt)
        ]
        
        expected_counts = historical.groupby("user_id").size()
        
        for _, row in features.iterrows():
            expected = expected_counts.get(row["user_id"], 0)
            actual = row.get("order_count_30d", 0)
            if not pd.isna(actual):
                assert actual == expected, \
                    f"User {row['user_id']}: expected {expected} orders in 30d, got {actual}"


class TestFeatureCorrectness:
    """Tests that verify feature values are computed correctly."""
    
    def test_total_spend_is_sum(self, sample_transactions):
        """total_spend should be sum of all historical order amounts."""
        prediction_date = "2024-03-15"
        
        with patch("src.data.feature_engineering.feature_store") as mock_fs:
            mock_fs.write_features = MagicMock()
            features = build_features(sample_transactions, prediction_date)
        
        historical = sample_transactions[
            sample_transactions["order_timestamp"] < pd.to_datetime(prediction_date)
        ]
        expected_spend = historical.groupby("user_id")["amount"].sum()
        
        for _, row in features.iterrows():
            expected = expected_spend.get(row["user_id"], 0)
            assert abs(row["total_spend"] - expected) < 0.01
    
    def test_return_rate_bounded(self, sample_transactions):
        """return_rate must be between 0 and 1."""
        prediction_date = "2024-03-15"
        
        with patch("src.data.feature_engineering.feature_store") as mock_fs:
            mock_fs.write_features = MagicMock()
            features = build_features(sample_transactions, prediction_date)
        
        assert (features["return_rate"] >= 0).all()
        assert (features["return_rate"] <= 1).all()


class TestFeatureCompleteness:
    """Tests that all expected features are produced."""
    
    def test_all_features_in_output(self, sample_transactions):
        """Output must contain all features listed in model_config.FEATURE_LIST."""
        prediction_date = "2024-03-15"
        
        with patch("src.data.feature_engineering.feature_store") as mock_fs:
            mock_fs.write_features = MagicMock()
            features = build_features(sample_transactions, prediction_date)
        
        for feature_name in FEATURE_LIST:
            assert feature_name in features.columns, \
                f"Feature '{feature_name}' missing from output (listed in FEATURE_LIST)"
    
    def test_no_all_null_features(self, sample_transactions):
        """No feature should be entirely null (indicates computation bug)."""
        prediction_date = "2024-03-15"
        
        with patch("src.data.feature_engineering.feature_store") as mock_fs:
            mock_fs.write_features = MagicMock()
            features = build_features(sample_transactions, prediction_date)
        
        for col in FEATURE_LIST:
            assert not features[col].isna().all(), \
                f"Feature '{col}' is entirely null — computation may be broken"
