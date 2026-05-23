"""
Data Contracts - Schema definitions for pipeline stage boundaries.

Defines the expected schema (columns, types, constraints) for data flowing
between pipeline stages. Used by validation.py to catch schema drift.

These contracts were added AFTER the 2024-06 incident where a PostgreSQL
schema change (NUMERIC -> FLOAT8) went undetected because we only had
statistical validation, not schema-level checks.

Contract hierarchy:
1. ingestion_contract: What raw data should look like from each source
2. cleaning_contract: What cleaned data should look like
3. feature_contract: What engineered features should look like

If upstream changes a column type, the contract check in validation.py
will catch it immediately (unlike statistical checks which may not).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class DataContract:
    """
    Schema contract for a data pipeline stage.
    
    Defines required columns, their types, and value constraints.
    Used by validation.py to perform schema-level checks.
    """
    name: str
    version: str
    required_columns: List[str]
    column_types: Dict[str, str]  # column_name -> expected_dtype
    nullable_columns: Set[str] = field(default_factory=set)
    value_constraints: Dict[str, Dict] = field(default_factory=dict)
    description: str = ""


# === INGESTION CONTRACTS ===

POSTGRES_TRANSACTIONS_CONTRACT = DataContract(
    name="postgres_transactions",
    version="2.0",  # Updated after 2024-06 incident
    description="Transaction data from PostgreSQL orders table",
    required_columns=[
        "user_id", "order_id", "amount", "order_timestamp",
        "product_category", "payment_method", "shipping_region", "is_returned"
    ],
    column_types={
        "user_id": "object",
        "order_id": "object",
        "amount": "float64",  # Was NUMERIC(10,2), now FLOAT8 — caught by this contract
        "order_timestamp": "datetime64[ns]",
        "product_category": "object",
        "payment_method": "object",
        "shipping_region": "object",
        "is_returned": "bool",
    },
    nullable_columns={"shipping_region", "product_category"},
    value_constraints={
        "amount": {"min": 0, "max": 1000000},
        "is_returned": {"values": [True, False]},
    }
)

S3_CLICKSTREAM_CONTRACT = DataContract(
    name="s3_clickstream",
    version="1.1",
    description="Clickstream events from S3 (partitioned by date)",
    required_columns=[
        "user_id", "session_id", "event_type", "timestamp",
        "page_url", "duration_seconds"
    ],
    column_types={
        "user_id": "object",
        "session_id": "object",
        "event_type": "object",
        "timestamp": "datetime64[ns]",
        "page_url": "object",
        "duration_seconds": "float64",
    },
    nullable_columns={"duration_seconds"},
    value_constraints={
        "duration_seconds": {"min": 0, "max": 7200},
        "event_type": {"values": ["page_view", "click", "add_to_cart", "purchase", "search"]},
    }
)

API_PROFILES_CONTRACT = DataContract(
    name="api_profiles",
    version="1.0",
    description="User profile data from profile service API",
    required_columns=[
        "user_id", "age_group", "gender", "region",
        "account_age_days", "customer_segment"
    ],
    column_types={
        "user_id": "object",
        "age_group": "object",
        "gender": "object",
        "region": "object",
        "account_age_days": "int64",
        "customer_segment": "object",
    },
    nullable_columns={"gender"},
    value_constraints={
        "age_group": {"values": ["18-24", "25-34", "35-44", "45-54", "55-64", "65+"]},
        "customer_segment": {"values": ["consumer", "business", "enterprise"]},
        "account_age_days": {"min": 0, "max": 10000},
    }
)

# === FEATURE CONTRACTS ===

FEATURE_OUTPUT_CONTRACT = DataContract(
    name="feature_output",
    version="1.2",
    description="Engineered features output (must match model_config.FEATURE_LIST)",
    required_columns=["user_id"] + [
        "days_since_last_order", "order_count_7d", "order_count_14d",
        "order_count_30d", "order_count_60d", "order_count_90d",
        "avg_days_between_orders", "total_spend", "avg_order_value",
        "std_order_value", "max_order_value", "order_count",
        "category_diversity", "return_rate",
    ],
    column_types={
        "user_id": "object",
        "days_since_last_order": "float64",
        "total_spend": "float64",
        "avg_order_value": "float64",
        "return_rate": "float64",
        "category_diversity": "int64",
    },
    nullable_columns={"avg_days_between_orders", "std_order_value"},
)


# === CONTRACT REGISTRY ===

_CONTRACT_REGISTRY: Dict[str, DataContract] = {
    "postgres_transactions": POSTGRES_TRANSACTIONS_CONTRACT,
    "s3_clickstream": S3_CLICKSTREAM_CONTRACT,
    "api_profiles": API_PROFILES_CONTRACT,
    "feature_output": FEATURE_OUTPUT_CONTRACT,
}


def load_contract(source: str) -> DataContract:
    """Load a data contract by source name."""
    if source not in _CONTRACT_REGISTRY:
        logger.warning(f"No contract found for source '{source}', using empty contract")
        return DataContract(name=source, version="0.0", required_columns=[], column_types={})
    return _CONTRACT_REGISTRY[source]


def validate_against_contract(df, contract: DataContract) -> List[str]:
    """Validate a DataFrame against a contract. Returns list of violations."""
    violations = []
    
    # Check required columns
    missing = set(contract.required_columns) - set(df.columns)
    if missing:
        violations.append(f"Missing required columns: {missing}")
    
    # Check types
    for col, expected_type in contract.column_types.items():
        if col in df.columns and str(df[col].dtype) != expected_type:
            violations.append(f"Type mismatch for '{col}': expected {expected_type}, got {df[col].dtype}")
    
    return violations
