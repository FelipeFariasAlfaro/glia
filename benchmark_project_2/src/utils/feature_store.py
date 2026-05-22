"""
Feature Store Client - Read/write features with versioning and caching.

Provides a unified interface to the centralized feature store (Feast-based).
Features are cached locally with a configurable TTL to reduce latency.

CRITICAL TIMING ISSUE: The cache TTL (default 4 hours from infra_config.py)
means that if the retraining pipeline runs within 4 hours of the daily pipeline
writing new features, it may train on STALE cached features from the previous day.

This was identified during the 2024-06 model degradation investigation — the model
was training on features that were 1 day behind because the cache hadn't expired.

Mitigation: Use force_refresh=True when reading features for training.
The retraining_pipeline.py calls invalidate_cache() before training.

See: docs/decisions/adr-002-feature-store.md for why we centralized features.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from src.config.infra_config import FEATURE_STORE_CACHE_TTL_HOURS
import hashlib
import json
import logging

logger = logging.getLogger(__name__)

# Default cache TTL from infrastructure config
DEFAULT_CACHE_TTL_HOURS = FEATURE_STORE_CACHE_TTL_HOURS  # 4 hours


class FeatureStoreClient:
    """
    Client for the centralized feature store.
    
    Features are versioned by date and cached locally.
    Cache TTL is configured in infra_config.py (FEATURE_STORE_CACHE_TTL_HOURS).
    
    WARNING: Stale cache can cause training on outdated features.
    Always use force_refresh=True for training workloads.
    """
    
    def __init__(self, cache_ttl_hours: int = DEFAULT_CACHE_TTL_HOURS):
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        self._cache: Dict[str, Dict] = {}  # key -> {"data": df, "timestamp": datetime}
        self._feast_client = None  # Lazy-initialized
    
    def read_features(
        self,
        feature_group: str,
        features: List[str],
        as_of_date: Optional[str] = None,
        entity_ids: Optional[List[str]] = None,
        window_days: Optional[int] = None,
        force_refresh: bool = False
    ) -> pd.DataFrame:
        """
        Read features from the store with caching.
        
        Args:
            feature_group: Name of the feature group (e.g., "churn_prediction")
            features: List of feature names to retrieve
            as_of_date: Point-in-time for feature retrieval
            entity_ids: Optional filter by entity IDs
            window_days: Optional lookback window
            force_refresh: If True, bypass cache (USE FOR TRAINING!)
            
        Returns:
            DataFrame with requested features
            
        WARNING: Without force_refresh, cached data may be up to {cache_ttl} old.
        For training, ALWAYS set force_refresh=True to avoid stale features.
        """
        cache_key = self._make_cache_key(feature_group, features, as_of_date, entity_ids)
        
        # Check cache (unless force_refresh)
        if not force_refresh and cache_key in self._cache:
            cached = self._cache[cache_key]
            age = datetime.utcnow() - cached["timestamp"]
            if age < self.cache_ttl:
                logger.debug(f"Cache hit for {feature_group} (age: {age})")
                return cached["data"]
            else:
                logger.debug(f"Cache expired for {feature_group} (age: {age})")
        
        # Fetch from feature store
        logger.info(f"Fetching {len(features)} features from {feature_group}")
        df = self._fetch_from_store(feature_group, features, as_of_date, entity_ids, window_days)
        
        # Update cache
        self._cache[cache_key] = {
            "data": df,
            "timestamp": datetime.utcnow()
        }
        
        return df
    
    def write_features(
        self,
        df: pd.DataFrame,
        feature_group: str,
        version: str
    ):
        """
        Write features to the store with versioning.
        
        Features are written with a version tag (typically the date).
        This does NOT invalidate the read cache — readers may still get
        old cached data until TTL expires or force_refresh is used.
        """
        logger.info(f"Writing {len(df)} rows to {feature_group} (version: {version})")
        
        # Write to Feast feature store
        self._write_to_store(df, feature_group, version)
        
        # NOTE: We intentionally do NOT invalidate cache here.
        # The retraining pipeline explicitly calls invalidate_cache() when needed.
        logger.debug("Write complete. Note: read cache NOT invalidated.")
    
    def invalidate_cache(self, feature_group: Optional[str] = None):
        """
        Invalidate cached features.
        
        Called by retraining_pipeline.py before training to ensure fresh features.
        If feature_group is None, invalidates ALL cached features.
        """
        if feature_group:
            keys_to_remove = [k for k in self._cache if feature_group in k]
            for key in keys_to_remove:
                del self._cache[key]
            logger.info(f"Invalidated {len(keys_to_remove)} cache entries for {feature_group}")
        else:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Invalidated all {count} cache entries")
    
    def _make_cache_key(self, feature_group, features, as_of_date, entity_ids) -> str:
        """Generate deterministic cache key."""
        key_parts = [feature_group, str(sorted(features)), str(as_of_date)]
        if entity_ids:
            key_parts.append(hashlib.md5(str(sorted(entity_ids)).encode()).hexdigest())
        return ":".join(key_parts)
    
    def _fetch_from_store(self, feature_group, features, as_of_date, 
                          entity_ids, window_days) -> pd.DataFrame:
        """Fetch features from the underlying Feast store."""
        # In production, this calls Feast's get_historical_features or get_online_features
        # Simplified here for clarity
        if self._feast_client is None:
            self._feast_client = self._init_feast()
        
        entity_df = pd.DataFrame({"user_id": entity_ids}) if entity_ids else None
        
        # Feast feature retrieval
        features_refs = [f"{feature_group}:{f}" for f in features]
        result = self._feast_client.get_historical_features(
            entity_df=entity_df,
            features=features_refs,
        )
        return result.to_df()
    
    def _write_to_store(self, df, feature_group, version):
        """Write features to Feast store."""
        if self._feast_client is None:
            self._feast_client = self._init_feast()
        self._feast_client.materialize_incremental(end_date=datetime.utcnow())
    
    def _init_feast(self):
        """Initialize Feast client."""
        from feast import FeatureStore
        return FeatureStore(repo_path="/feature_store/repo")
