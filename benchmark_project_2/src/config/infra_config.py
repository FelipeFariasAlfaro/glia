"""
Infrastructure Configuration - GPU instances, memory limits, and resource allocation.

Defines compute resources for training and serving. These settings directly affect
model training batch sizes and serving throughput.

CRITICAL COUPLING: TRAINING_BATCH_SIZE is derived from MAX_GPU_MEMORY_GB.
If you change GPU instance type (and thus memory), you MUST recalculate batch size.
Formula: TRAINING_BATCH_SIZE = int(MAX_GPU_MEMORY_GB * 1024 / MEMORY_PER_SAMPLE_MB)

Changing MAX_GPU_MEMORY_GB without updating TRAINING_BATCH_SIZE -> OOM errors.
Changing TRAINING_BATCH_SIZE without enough GPU memory -> OOM errors.

Past incident (2024-04): Someone upgraded to p3.8xlarge (4 GPUs) but didn't update
batch size. Training used single-GPU batch size on multi-GPU setup, wasting 75% capacity.
"""

from typing import Dict

# === GPU TRAINING CONFIGURATION ===
# Current instance: p3.2xlarge (1x V100, 16GB GPU memory)
TRAINING_INSTANCE_TYPE = "p3.2xlarge"
MAX_GPU_MEMORY_GB = 16  # V100 has 16GB HBM2
NUM_GPUS = 1

# Memory per sample during XGBoost training (empirically measured)
MEMORY_PER_SAMPLE_MB = 0.5  # ~0.5MB per sample with our feature set

# Batch size derived from GPU memory — DO NOT change independently!
# Formula: MAX_GPU_MEMORY_GB * 1024 / MEMORY_PER_SAMPLE_MB
TRAINING_BATCH_SIZE = int(MAX_GPU_MEMORY_GB * 1024 / MEMORY_PER_SAMPLE_MB)  # = 32768

# Maximum dataset size that fits in GPU memory for full training
MAX_TRAINING_SAMPLES = TRAINING_BATCH_SIZE * 4  # ~131K samples with gradient accumulation

# === SERVING CONFIGURATION ===
SERVING_INSTANCE_TYPE = "c5.2xlarge"  # CPU-only for inference (cost optimization)
SERVING_MEMORY_GB = 16
SERVING_VCPUS = 8
MAX_CONCURRENT_REQUESTS = 100
REQUEST_TIMEOUT_MS = 200

# Auto-scaling configuration
AUTOSCALE_MIN_INSTANCES = 2
AUTOSCALE_MAX_INSTANCES = 10
AUTOSCALE_TARGET_CPU = 70  # Scale up at 70% CPU utilization

# === FEATURE STORE CONFIGURATION ===
FEATURE_STORE_INSTANCE = "r5.xlarge"  # Memory-optimized for feature lookups
FEATURE_STORE_CACHE_SIZE_GB = 32
FEATURE_STORE_CACHE_TTL_HOURS = 4  # Cache TTL — affects retraining freshness!

# === PIPELINE CONFIGURATION ===
AIRFLOW_INSTANCE_TYPE = "m5.large"
AIRFLOW_WORKER_COUNT = 4
PIPELINE_TIMEOUT_MINUTES = 120  # Max time for daily pipeline

# === STORAGE ===
MODEL_ARTIFACT_BUCKET = "ml-models-prod"
FEATURE_STORE_BUCKET = "ml-features-prod"
RAW_DATA_BUCKET = "ml-pipeline-raw-data"

# === NETWORKING ===
VPC_ID = "vpc-ml-production"
SUBNET_IDS = ["subnet-a1b2c3", "subnet-d4e5f6"]
SECURITY_GROUP_ID = "sg-ml-training"

# === COST CONTROLS ===
MAX_TRAINING_COST_PER_RUN = 50.0  # USD — alert if training exceeds this
MAX_MONTHLY_SERVING_COST = 2000.0  # USD
SPOT_INSTANCE_ENABLED = True  # Use spot for training (not serving)
SPOT_MAX_PRICE_MULTIPLIER = 1.5  # Pay up to 1.5x on-demand price

# === RESOURCE LIMITS ===
RESOURCE_LIMITS: Dict[str, Dict] = {
    "training": {
        "max_memory_gb": MAX_GPU_MEMORY_GB,
        "max_runtime_hours": 4,
        "max_cost_usd": MAX_TRAINING_COST_PER_RUN,
    },
    "serving": {
        "max_memory_gb": SERVING_MEMORY_GB,
        "max_latency_ms": REQUEST_TIMEOUT_MS,
        "max_instances": AUTOSCALE_MAX_INSTANCES,
    },
    "feature_store": {
        "max_cache_gb": FEATURE_STORE_CACHE_SIZE_GB,
        "cache_ttl_hours": FEATURE_STORE_CACHE_TTL_HOURS,
    },
}
