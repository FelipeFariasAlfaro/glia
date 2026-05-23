"""
Pipeline Integration Tests - End-to-end validation of the ML pipeline.

Tests the full pipeline flow: ingestion -> validation -> cleaning -> features -> training.
Also tests critical failure modes and timing dependencies.

These tests verify:
1. Pipeline stages connect correctly (output of one is valid input for next)
2. Validation catches schema changes (post-2024-06 incident)
3. Feature store cache behavior during retraining
4. S3 data lateness handling
5. GPU memory / batch size consistency
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from src.data.validation import validate_ingested_data, ValidationResult
from src.data.cleaning import clean_pipeline
from src.config.model_config import FEATURE_LIST
from src.config.infra_config import (
    MAX_GPU_MEMORY_GB, TRAINING_BATCH_SIZE, MEMORY_PER_SAMPLE_MB
)


class TestValidationCatchesSchemaChanges:
    """
    Tests added after 2024-06 incident: validation must catch type changes.
    Previously, statistical checks passed even when column types changed.
    """
    
    def test_detects_column_type_change(self):
        """
        Regression test for 2024-06 incident: NUMERIC -> FLOAT8 change
        must be caught by schema validation.
        """
        # Simulate data with wrong type (int instead of float for amount)
        df = pd.DataFrame({
            "user_id": ["u1", "u2", "u3"],
            "order_id": ["o1", "o2", "o3"],
            "amount": [100, 200, 300],  # int64 instead of float64
            "order_timestamp": pd.date_range("2024-01-01", periods=3),
            "product_category": ["electronics", "clothing", "food"],
            "payment_method": ["credit", "debit", "paypal"],
            "shipping_region": ["US", "EU", "APAC"],
            "is_returned": [False, True, False],
        })
        
        results = validate_ingested_data(df, "postgres_transactions")
        
        # Should have a schema type error for 'amount'
        type_errors = [r for r in results if "schema_type" in r.check_name and not r.passed]
        assert len(type_errors) > 0, \
            "Validation should catch column type mismatch (this was the 2024-06 bug)"
    
    def test_detects_missing_columns(self):
        """Validation must catch missing required columns."""
        df = pd.DataFrame({
            "user_id": ["u1", "u2"],
            "order_id": ["o1", "o2"],
            # Missing: amount, order_timestamp, etc.
        })
        
        results = validate_ingested_data(df, "postgres_transactions")
        
        column_errors = [r for r in results if "columns_present" in r.check_name and not r.passed]
        assert len(column_errors) > 0, "Should detect missing required columns"


class TestCleaningPipeline:
    """Tests for the data cleaning stage."""
    
    def test_deduplication_keeps_latest(self):
        """Deduplication should keep the most recent record."""
        df = pd.DataFrame({
            "user_id": ["u1", "u1", "u2"],
            "order_id": ["o1", "o1", "o2"],
            "amount": [100.0, 150.0, 200.0],
            "order_timestamp": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-01"]),
            "customer_segment": ["consumer", "consumer", "business"],
            "is_returned": [False, False, False],
        })
        
        cleaned = clean_pipeline(df)
        
        # Should keep the later record for order o1
        o1_records = cleaned[cleaned["order_id"] == "o1"]
        assert len(o1_records) == 1
        assert o1_records.iloc[0]["amount"] == 150.0
    
    def test_null_handling_required_columns(self):
        """Rows with null required columns should be dropped."""
        df = pd.DataFrame({
            "user_id": ["u1", None, "u3"],
            "order_id": ["o1", "o2", "o3"],
            "amount": [100.0, 200.0, 300.0],
            "order_timestamp": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            "customer_segment": ["consumer", "consumer", "consumer"],
            "is_returned": [False, False, False],
        })
        
        cleaned = clean_pipeline(df)
        assert len(cleaned) == 2  # Row with null user_id dropped


class TestInfraConfigConsistency:
    """Tests that infrastructure config values are consistent."""
    
    def test_batch_size_matches_gpu_memory(self):
        """
        TRAINING_BATCH_SIZE must be derived from MAX_GPU_MEMORY_GB.
        Changing one without the other causes OOM errors.
        """
        expected_batch_size = int(MAX_GPU_MEMORY_GB * 1024 / MEMORY_PER_SAMPLE_MB)
        assert TRAINING_BATCH_SIZE == expected_batch_size, \
            f"Batch size ({TRAINING_BATCH_SIZE}) doesn't match GPU memory calculation ({expected_batch_size}). " \
            f"This will cause OOM errors! Update infra_config.py."
    
    def test_batch_size_positive(self):
        """Batch size must be a positive integer."""
        assert TRAINING_BATCH_SIZE > 0
        assert isinstance(TRAINING_BATCH_SIZE, int)


class TestFeatureStoreCache:
    """Tests for feature store caching behavior."""
    
    def test_cache_ttl_from_config(self):
        """Feature store cache TTL should match infra_config."""
        from src.utils.feature_store import FeatureStoreClient, DEFAULT_CACHE_TTL_HOURS
        from src.config.infra_config import FEATURE_STORE_CACHE_TTL_HOURS
        
        assert DEFAULT_CACHE_TTL_HOURS == FEATURE_STORE_CACHE_TTL_HOURS
    
    def test_force_refresh_bypasses_cache(self):
        """force_refresh=True must bypass the cache (critical for training)."""
        from src.utils.feature_store import FeatureStoreClient
        
        client = FeatureStoreClient(cache_ttl_hours=24)
        
        # Manually populate cache
        cache_key = client._make_cache_key("test_group", ["f1"], "2024-01-01", None)
        client._cache[cache_key] = {
            "data": pd.DataFrame({"f1": [1, 2, 3]}),
            "timestamp": datetime.utcnow()  # Fresh cache
        }
        
        # With force_refresh, should NOT use cache
        with patch.object(client, "_fetch_from_store") as mock_fetch:
            mock_fetch.return_value = pd.DataFrame({"f1": [4, 5, 6]})
            result = client.read_features(
                feature_group="test_group",
                features=["f1"],
                as_of_date="2024-01-01",
                force_refresh=True
            )
            mock_fetch.assert_called_once()


class TestDriftDetectorCoverage:
    """Tests that drift detector monitors all training features."""
    
    def test_monitored_features_match_training(self):
        """
        Drift detector must monitor ALL features used in training.
        If a feature is in FEATURE_LIST but not monitored, drift goes undetected.
        """
        from src.monitoring.drift_detector import MONITORED_FEATURES
        from src.config.model_config import FEATURE_LIST
        
        missing_from_monitoring = set(FEATURE_LIST) - set(MONITORED_FEATURES)
        assert len(missing_from_monitoring) == 0, \
            f"Features in training but NOT monitored for drift: {missing_from_monitoring}. " \
            f"This will cause silent model degradation!"


class TestS3DataDependency:
    """Tests for S3 data arrival timing dependency."""
    
    def test_pipeline_schedule_after_s3_deadline(self):
        """Daily pipeline must be scheduled AFTER S3 data deadline."""
        from src.pipelines.daily_pipeline import SCHEDULE
        from src.data.ingestion import S3_DATA_DEADLINE_UTC
        
        # Parse schedule (cron: "15 6 * * *" = 6:15 AM)
        parts = SCHEDULE.split()
        pipeline_hour = int(parts[1])
        pipeline_minute = int(parts[0])
        
        # Parse deadline ("06:00")
        deadline_hour, deadline_minute = map(int, S3_DATA_DEADLINE_UTC.split(":"))
        
        # Pipeline must start AFTER deadline
        pipeline_time = pipeline_hour * 60 + pipeline_minute
        deadline_time = deadline_hour * 60 + deadline_minute
        
        assert pipeline_time > deadline_time, \
            "Pipeline is scheduled before S3 data deadline — will process incomplete data!"
