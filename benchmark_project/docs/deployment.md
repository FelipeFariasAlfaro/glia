# Deployment Guide

## Environments

| Environment | Purpose | Infrastructure |
|-------------|---------|---------------|
| Development | Local development | Docker Compose (PG + Redis) |
| Staging | Pre-production testing | AWS ECS, RDS, ElastiCache |
| Production | Live traffic | AWS ECS (Fargate), RDS Multi-AZ, ElastiCache (Redis Sentinel) |

## Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+ (Sentinel mode in production)
- Stripe account (test keys for dev/staging)
- SMTP server (SES in production)

## Environment Variables

```bash
# Core
APP_ENV=production
DEBUG=false
HOST=0.0.0.0
PORT=8000
WORKERS=4

# Database
DATABASE_URL=postgresql://user:pass@host:5432/ecommerce
DB_POOL_MIN=10
DB_POOL_MAX=50

# Redis (shared across sessions, rate limiting, events, reservations)
REDIS_URL=redis://host:6379/0
REDIS_PASSWORD=secret
REDIS_POOL_SIZE=50

# JWT (RS256 keys mounted as Kubernetes secrets)
JWT_KEY_DIR=/secrets/jwt

# Stripe
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Email
SMTP_HOST=email-smtp.us-east-1.amazonaws.com
SMTP_PORT=587
SMTP_USER=AKIA...
SMTP_PASSWORD=...
EMAIL_FROM=orders@example.com
```

## Deployment Steps

### 1. Database Migration
```bash
python -m src.database.migrations
```
Migrations are idempotent and run in order. Check `schema_migrations` table for current version.

### 2. Generate JWT Keys (first time only)
```bash
openssl genrsa -out keys/private.pem 4096
openssl rsa -in keys/private.pem -pubout -out keys/public.pem
```
In production, these are stored in AWS Secrets Manager and mounted into containers.

### 3. Deploy Application
```bash
docker build -t ecommerce-api .
docker push ecr.aws/ecommerce-api:latest
aws ecs update-service --cluster prod --service api --force-new-deployment
```

### 4. Deploy Workers
Workers run as separate ECS tasks:
```bash
# Email worker
aws ecs run-task --cluster prod --task-definition email-worker

# Webhook worker  
aws ecs run-task --cluster prod --task-definition webhook-worker
```

## Health Checks

- **API**: `GET /health` → checks PostgreSQL and Redis connectivity
- **Workers**: Heartbeat via Redis key (checked by CloudWatch alarm)

## Scaling Considerations

- **API**: Horizontal scaling via ECS desired count (stateless)
- **Workers**: Scale based on queue depth (CloudWatch metric on Redis list length)
- **Database**: Vertical scaling (RDS instance size) + read replicas for queries
- **Redis**: ElastiCache cluster mode for sharding if single node is insufficient

## Rollback Procedure

1. Revert ECS task definition to previous version
2. If database migration was applied, run rollback migration
3. Verify health checks pass
4. Monitor error rates for 15 minutes

## Known Issues

- Redis is a single point of failure for multiple subsystems (see architecture.md)
- If Redis Sentinel failover takes >15s, inventory reservations may expire during the gap
- Workers don't have graceful shutdown — in-flight jobs may be lost on deploy (accepted risk)
