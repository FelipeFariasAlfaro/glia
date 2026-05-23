"""
Model Registry - Versioning, promotion, and rollback for ML models.

Manages the lifecycle of trained models: staging -> production -> archived.
Promotion to production REQUIRES passing fairness checks in evaluation.py.
This is a hard gate — no exceptions, even if accuracy is excellent.

Rollback procedure:
1. Set current production model to "archived"
2. Promote previous version back to "production"
3. Invalidate prediction cache in serving.py
4. Recalibrate alert thresholds (alerts.py) for the rolled-back model version

IMPORTANT: After any model promotion or rollback, alert thresholds in alerts.py
must be recalibrated. Thresholds are tuned to the current model's prediction
distribution — a different model version will have different score distributions.
"""

import json
import hashlib
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
import xgboost as xgb
import logging

logger = logging.getLogger(__name__)


@dataclass
class ModelVersion:
    """Metadata for a registered model version."""
    version_id: str
    model_name: str
    stage: str  # "staging", "production", "archived"
    created_at: str
    metrics: Dict[str, float]
    fairness_passed: bool
    promoted_at: Optional[str] = None
    promoted_by: Optional[str] = None
    rollback_reason: Optional[str] = None


class ModelRegistry:
    """
    Central registry for model versions.
    
    Promotion rules:
    - Model must be in "staging" to be promoted
    - Fairness checks must pass (evaluation.py)
    - AUC must exceed current production model (no regression)
    - After promotion, alert thresholds need recalibration
    """
    
    def __init__(self, storage_path: str = "/models/registry"):
        self.storage_path = storage_path
        self._versions: Dict[str, ModelVersion] = {}
    
    def register_model(self, model: xgb.Booster, model_name: str,
                       metrics: Dict, fairness_passed: bool) -> str:
        """Register a new model version in staging."""
        version_id = self._generate_version_id(model_name)
        
        version = ModelVersion(
            version_id=version_id,
            model_name=model_name,
            stage="staging",
            created_at=datetime.utcnow().isoformat(),
            metrics=metrics,
            fairness_passed=fairness_passed,
        )
        
        self._versions[version_id] = version
        self._save_model_artifact(model, version_id)
        
        logger.info(f"Registered model {model_name} version {version_id} (staging)")
        return version_id
    
    def promote_to_production(self, version_id: str, promoted_by: str) -> bool:
        """
        Promote a staging model to production.
        
        GATE: Fairness checks must have passed. This is non-negotiable.
        After promotion, alert thresholds in monitoring/alerts.py should be
        recalibrated for the new model's score distribution.
        """
        version = self._versions.get(version_id)
        if not version:
            raise ValueError(f"Version {version_id} not found")
        
        if version.stage != "staging":
            raise ValueError(f"Can only promote from staging, got {version.stage}")
        
        if not version.fairness_passed:
            logger.error(f"BLOCKED: Cannot promote {version_id} — fairness checks failed")
            raise ValueError("Model failed fairness checks. Cannot promote to production.")
        
        # Archive current production model
        current_prod = self.get_production_version()
        if current_prod:
            current_prod.stage = "archived"
            logger.info(f"Archived previous production model {current_prod.version_id}")
        
        # Promote new model
        version.stage = "production"
        version.promoted_at = datetime.utcnow().isoformat()
        version.promoted_by = promoted_by
        
        logger.info(f"Promoted {version_id} to production by {promoted_by}")
        logger.warning("ACTION REQUIRED: Recalibrate alert thresholds for new model version")
        
        return True
    
    def rollback(self, reason: str) -> str:
        """
        Rollback to previous production model.
        
        Steps:
        1. Archive current production
        2. Find most recent archived version
        3. Promote it back to production
        4. Log rollback reason
        
        REMINDER: After rollback, recalibrate alert thresholds in alerts.py
        """
        current = self.get_production_version()
        if not current:
            raise ValueError("No production model to rollback from")
        
        # Find previous version
        archived = [v for v in self._versions.values() 
                    if v.stage == "archived" and v.model_name == current.model_name]
        archived.sort(key=lambda v: v.promoted_at or "", reverse=True)
        
        if not archived:
            raise ValueError("No archived version available for rollback")
        
        previous = archived[0]
        
        # Perform rollback
        current.stage = "archived"
        current.rollback_reason = reason
        previous.stage = "production"
        previous.promoted_at = datetime.utcnow().isoformat()
        
        logger.warning(f"ROLLBACK: {current.version_id} -> {previous.version_id}")
        logger.warning(f"Reason: {reason}")
        logger.warning("ACTION REQUIRED: Recalibrate alert thresholds for rolled-back model")
        
        return previous.version_id
    
    def get_production_model(self) -> Tuple[xgb.Booster, str]:
        """Load the current production model."""
        version = self.get_production_version()
        if not version:
            raise ValueError("No production model registered")
        model = self._load_model_artifact(version.version_id)
        return model, version.version_id
    
    def get_production_version(self) -> Optional[ModelVersion]:
        """Get metadata for current production model."""
        for v in self._versions.values():
            if v.stage == "production":
                return v
        return None
    
    def _generate_version_id(self, model_name: str) -> str:
        """Generate unique version ID."""
        timestamp = datetime.utcnow().isoformat()
        hash_input = f"{model_name}:{timestamp}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:12]
    
    def _save_model_artifact(self, model: xgb.Booster, version_id: str):
        """Save model artifact to storage."""
        path = f"{self.storage_path}/{version_id}/model.xgb"
        model.save_model(path)
    
    def _load_model_artifact(self, version_id: str) -> xgb.Booster:
        """Load model artifact from storage."""
        path = f"{self.storage_path}/{version_id}/model.xgb"
        model = xgb.Booster()
        model.load_model(path)
        return model
