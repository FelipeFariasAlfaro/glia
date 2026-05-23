"""
Data Validation Module - Quality checks between pipeline stages.

Performs statistical validation, schema checks, and drift detection on incoming data.
Runs after ingestion and before cleaning to catch issues early.

KNOWN GAP (2024-06): Our validation was purely statistical (distribution checks,
null rates, value ranges) but did NOT validate column types/schema. When PostgreSQL
changed `amount` from NUMERIC(10,2) to FLOAT8, the values looked statistically
similar but caused floating-point precision errors in feature engineering.
We've since added schema validation, but the statistical-only approach was the
root cause of the model degradation incident.

See: docs/incidents/2024-06-model-degradation.md
"""

import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from src.utils.data_contracts import DataContract, load_contract
import logging

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a validation check."""
    passed: bool
    check_name: str
    details: str
    severity: str  # "error", "warning", "info"


def validate_ingested_data(df: pd.DataFrame, source: str) -> List[ValidationResult]:
    """
    Run all validation checks on ingested data.
    
    Returns list of validation results. Pipeline should halt on any "error" severity.
    Added schema validation after the 2024-06 incident.
    """
    results = []
    
    # Schema validation (added post-incident 2024-06)
    contract = load_contract(source)
    results.extend(_validate_schema(df, contract))
    
    # Statistical validation
    results.extend(_validate_statistics(df, source))
    
    # Completeness checks
    results.extend(_validate_completeness(df, source))
    
    # Freshness check
    results.extend(_validate_freshness(df))
    
    errors = [r for r in results if r.severity == "error" and not r.passed]
    warnings = [r for r in results if r.severity == "warning" and not r.passed]
    
    logger.info(f"Validation complete: {len(errors)} errors, {len(warnings)} warnings")
    return results


def _validate_schema(df: pd.DataFrame, contract: DataContract) -> List[ValidationResult]:
    """
    Validate column names, types, and constraints against the data contract.
    
    This check was MISSING before 2024-06. The PostgreSQL schema change went
    undetected because we only checked statistical properties, not actual dtypes.
    """
    results = []
    
    # Check all expected columns exist
    missing_cols = set(contract.required_columns) - set(df.columns)
    results.append(ValidationResult(
        passed=len(missing_cols) == 0,
        check_name="schema_columns_present",
        details=f"Missing columns: {missing_cols}" if missing_cols else "All columns present",
        severity="error"
    ))
    
    # Check column types match contract
    for col, expected_type in contract.column_types.items():
        if col in df.columns:
            actual_type = str(df[col].dtype)
            type_match = _types_compatible(actual_type, expected_type)
            results.append(ValidationResult(
                passed=type_match,
                check_name=f"schema_type_{col}",
                details=f"{col}: expected {expected_type}, got {actual_type}",
                severity="error"
            ))
    
    return results


def _validate_statistics(df: pd.DataFrame, source: str) -> List[ValidationResult]:
    """
    Statistical validation: check distributions haven't shifted dramatically.
    
    NOTE: This alone is NOT sufficient to catch schema changes. A column can change
    from NUMERIC to FLOAT and still pass KS tests. Always pair with schema checks.
    """
    results = []
    
    # Null rate check (should be below historical threshold)
    for col in df.columns:
        null_rate = df[col].isnull().mean()
        threshold = 0.05  # 5% null rate threshold
        results.append(ValidationResult(
            passed=null_rate <= threshold,
            check_name=f"null_rate_{col}",
            details=f"{col} null rate: {null_rate:.3f} (threshold: {threshold})",
            severity="warning" if null_rate <= 0.1 else "error"
        ))
    
    # Value range checks for numerical columns
    numerical_cols = df.select_dtypes(include=["number"]).columns
    for col in numerical_cols:
        if df[col].min() < 0 and col in ["amount", "quantity"]:
            results.append(ValidationResult(
                passed=False,
                check_name=f"value_range_{col}",
                details=f"{col} has negative values (min: {df[col].min()})",
                severity="warning"
            ))
    
    return results


def _validate_completeness(df: pd.DataFrame, source: str) -> List[ValidationResult]:
    """Check row count is within expected range for the source."""
    expected_ranges = {
        "s3_clickstream": (100000, 5000000),
        "postgres_transactions": (10000, 500000),
        "api_profiles": (1000, 100000),
    }
    
    min_rows, max_rows = expected_ranges.get(source, (0, float("inf")))
    row_count = len(df)
    
    return [ValidationResult(
        passed=min_rows <= row_count <= max_rows,
        check_name="row_count_range",
        details=f"Got {row_count} rows (expected {min_rows}-{max_rows})",
        severity="error" if row_count < min_rows * 0.5 else "warning"
    )]


def _validate_freshness(df: pd.DataFrame) -> List[ValidationResult]:
    """Check that data is recent enough (not stale)."""
    if "order_timestamp" in df.columns:
        max_ts = pd.to_datetime(df["order_timestamp"]).max()
        hours_old = (pd.Timestamp.now() - max_ts).total_seconds() / 3600
        return [ValidationResult(
            passed=hours_old < 48,
            check_name="data_freshness",
            details=f"Most recent record is {hours_old:.1f} hours old",
            severity="warning" if hours_old < 72 else "error"
        )]
    return []


def _types_compatible(actual: str, expected: str) -> bool:
    """Check if actual dtype is compatible with expected type from contract."""
    compatible_map = {
        "float64": ["float64", "float32", "numeric"],
        "int64": ["int64", "int32", "integer"],
        "object": ["object", "string", "varchar"],
    }
    return actual in compatible_map.get(expected, [expected])
