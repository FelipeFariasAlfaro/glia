"""
Model Serving Module - FastAPI endpoint for real-time churn predictions.

Serves the production model with request batching and prediction caching.
The model version served is controlled by the model registry (registry.py).

Performance notes:
- P99 latency target: 50ms for single predictions, 200ms for batch
- Prediction cache TTL: 1 hour (user features don't change faster than this)
- Batch size limited to 1000 users per request

IMPORTANT: The served model version must match the feature list in model_config.py.
If features are added/removed in training but the serving endpoint isn't updated,
predictions will fail or silently use wrong feature ordering.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, validator
from typing import List, Dict, Optional
import xgboost as xgb
import numpy as np
import redis
import json
import time
from src.models.registry import ModelRegistry
from src.utils.feature_store import FeatureStoreClient
from src.config.model_config import FEATURE_LIST
import logging

logger = logging.getLogger(__name__)

app = FastAPI(title="Churn Prediction Service", version="2.1.0")

# Components
registry = ModelRegistry()
feature_store = FeatureStoreClient()
cache = redis.Redis(host="redis.internal", port=6379, db=0)

# Cache TTL for predictions (1 hour)
PREDICTION_CACHE_TTL = 3600
MAX_BATCH_SIZE = 1000

# Current loaded model (lazy-loaded on first request)
_current_model: Optional[xgb.Booster] = None
_current_version: Optional[str] = None


class PredictionRequest(BaseModel):
    """Single prediction request."""
    user_id: str


class BatchPredictionRequest(BaseModel):
    """Batch prediction request."""
    user_ids: List[str]
    
    @validator("user_ids")
    def validate_batch_size(cls, v):
        if len(v) > MAX_BATCH_SIZE:
            raise ValueError(f"Batch size {len(v)} exceeds max {MAX_BATCH_SIZE}")
        return v


class PredictionResponse(BaseModel):
    """Prediction response with metadata."""
    user_id: str
    churn_probability: float
    risk_tier: str  # "low", "medium", "high"
    model_version: str
    cached: bool


@app.on_event("startup")
async def load_model():
    """Load the current production model from registry on startup."""
    global _current_model, _current_version
    _current_model, _current_version = registry.get_production_model()
    logger.info(f"Loaded model version {_current_version}")


@app.post("/predict", response_model=PredictionResponse)
async def predict_single(request: PredictionRequest):
    """Single user churn prediction with caching."""
    # Check cache first
    cached = _get_cached_prediction(request.user_id)
    if cached:
        return PredictionResponse(**cached, cached=True)
    
    # Get features from store
    features = feature_store.read_features(
        feature_group="churn_prediction",
        features=FEATURE_LIST,
        entity_ids=[request.user_id]
    )
    
    if features.empty:
        raise HTTPException(status_code=404, detail="User features not found")
    
    # Predict
    dmatrix = xgb.DMatrix(features[FEATURE_LIST])
    prob = float(_current_model.predict(dmatrix)[0])
    
    response = PredictionResponse(
        user_id=request.user_id,
        churn_probability=prob,
        risk_tier=_classify_risk(prob),
        model_version=_current_version,
        cached=False
    )
    
    # Cache the prediction
    _cache_prediction(request.user_id, response.dict())
    
    return response


@app.post("/predict/batch", response_model=List[PredictionResponse])
async def predict_batch(request: BatchPredictionRequest):
    """Batch prediction for multiple users."""
    start_time = time.time()
    
    # Split into cached and uncached
    results = []
    uncached_ids = []
    
    for uid in request.user_ids:
        cached = _get_cached_prediction(uid)
        if cached:
            results.append(PredictionResponse(**cached, cached=True))
        else:
            uncached_ids.append(uid)
    
    # Batch predict uncached
    if uncached_ids:
        features = feature_store.read_features(
            feature_group="churn_prediction",
            features=FEATURE_LIST,
            entity_ids=uncached_ids
        )
        
        if not features.empty:
            dmatrix = xgb.DMatrix(features[FEATURE_LIST])
            probs = _current_model.predict(dmatrix)
            
            for uid, prob in zip(uncached_ids, probs):
                resp = PredictionResponse(
                    user_id=uid,
                    churn_probability=float(prob),
                    risk_tier=_classify_risk(float(prob)),
                    model_version=_current_version,
                    cached=False
                )
                results.append(resp)
                _cache_prediction(uid, resp.dict())
    
    elapsed = time.time() - start_time
    logger.info(f"Batch prediction: {len(request.user_ids)} users in {elapsed:.3f}s")
    
    return results


def _classify_risk(probability: float) -> str:
    """Classify churn probability into risk tiers."""
    if probability >= 0.7:
        return "high"
    elif probability >= 0.3:
        return "medium"
    return "low"


def _get_cached_prediction(user_id: str) -> Optional[Dict]:
    """Get cached prediction from Redis."""
    key = f"pred:churn:{user_id}"
    cached = cache.get(key)
    return json.loads(cached) if cached else None


def _cache_prediction(user_id: str, prediction: Dict):
    """Cache prediction in Redis with TTL."""
    key = f"pred:churn:{user_id}"
    cache.setex(key, PREDICTION_CACHE_TTL, json.dumps(prediction))
