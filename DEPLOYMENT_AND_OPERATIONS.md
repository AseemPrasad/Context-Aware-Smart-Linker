# CASL — Production Deployment & Operations Runbook

This document is the operational guide for deploying, maintaining, and scaling CASL in staging and enterprise production environments.

---

## 1. Environment Configuration Dictionary

All configuration is driven via environment variables with intelligent, non-breaking fallbacks:

| Variable | Default (Dev) | Production Target | Description |
| :--- | :--- | :--- | :--- |
| `DATABASE_URL` | None | `postgresql+psycopg2://user:pass@rds-host:5432/casl_prod` | Relational database connection string for credit ledger. |
| `REDIS_URL` | `redis://localhost:6379/0` | `redis://redis-cluster:6379/0` | Primary Redis instance for atomic credit metering and rate limits. |
| `ENABLE_REDIS_METER` | `false` | `true` | When true, activates atomic multi-replica usage accounting. |
| `QDRANT_URL` | None (In-memory) | `http://qdrant:6333` | Persistent Qdrant vector database URL. |
| `AUTH_ENABLED` | `false` | `true` | Enforces enterprise JWT / Bearer token validation on protected endpoints. |
| `OIDC_JWKS_URL` | None | `https://your-tenant.okta.com/oauth2/v1/keys` | Public JWKS URL for asymmetric RS256 token verification. |
| `OIDC_ISSUER` | None | `https://your-tenant.okta.com/oauth2/default` | Expected token issuer (`iss` claim). |
| `STRIPE_WEBHOOK_SECRET`| None | `whsec_...` | Cryptographic signature secret for Stripe webhooks. |
| `EMBEDDING_API_URL` | None (Local CPU) | `https://api.openai.com` or `http://tei-cluster:8080` | External endpoint for offloading dense vector embeddings. |
| `EMBEDDING_API_KEY` | None | `sk-proj-...` | API key for external embedding service. |
| `SEC_EDGAR_USER_AGENT` | `CASLResearch compliance@casl.com` | `Company AdminContact@firm.com` | Compliant corporate User-Agent required by SEC EDGAR. |
| `TELEMETRY_ENABLED` | `false` | `true` | Activates OpenTelemetry distributed tracing. |
| `OTEL_EXPORTER_OTLP_ENDPOINT`| None | `http://jaeger:4317` | OpenTelemetry collector gRPC endpoint. |

---

## 2. Docker Production Deployment

### 2.1 Booting the Stack
To launch the complete enterprise topology with persistent storage volumes:
```bash
docker-compose -f docker-compose.prod.yml up -d --build
```

### 2.2 Verifying Service Health
```bash
# Check running containers and health checks
docker-compose -f docker-compose.prod.yml ps
```
All services (`casl-api-prod`, `casl-qdrant-prod`, `casl-redis-prod`, `casl-celery-worker-prod`, `casl-celery-beat-prod`, `casl-jaeger-prod`) should report `Up (healthy)`.

---

## 3. Production Scaling Architecture (AWS Reference)

```mermaid
flowchart TD
    subgraph Clients
        Ext[Chrome Extensions]
        Web[Admin Web Dashboards]
    end

    subgraph Ingress
        CF[Cloudflare WAF / CDN]
        ALB[AWS Application Load Balancer]
    end

    subgraph Compute [AWS ECS / EKS Cluster]
        API1[FastAPI Replica 1]
        API2[FastAPI Replica 2]
        API3[FastAPI Replica N]
        Worker1[Celery Worker: SEC Ingestion]
        Worker2[Celery Worker: Batch Indexing]
        Beat[Celery Beat Scheduler]
    end

    subgraph Data [AWS Managed Services]
        RDS[(Amazon Aurora PostgreSQL)]
        Redis[(Amazon ElastiCache Redis)]
        Qdrant[(Qdrant Cloud / ECS Cluster)]
        S3[(Amazon S3: Raw Filings)]
    end

    Clients -->|HTTPS:443| CF --> ALB
    ALB --> API1 & API2 & API3
    API1 & API2 & API3 -->|Atomic Limits| Redis
    API1 & API2 & API3 -->|Ledger Audit| RDS
    API1 & API2 & API3 -->|Vector Search| Qdrant
    Beat -->|Enqueue Periodic Tasks| Redis
    Redis -->|Dequeue Jobs| Worker1 & Worker2
    Worker1 -->|Store Filings| S3
    Worker1 -->|Index Chunks| Qdrant
```

---

## 4. Maintenance & Operational Runbooks

### 4.1 Upgrading Database Migrations
When deploying schema updates for the relational ledger:
```bash
docker exec -it casl-api-prod alembic upgrade head
```

### 4.2 Flushing and Re-indexing SEC Filings
To trigger an immediate on-demand ingestion of latest SEC disclosures:
```bash
docker exec -it casl-celery-worker-prod python -c "from backend.tasks.sec_edgar_pipeline import sync_latest_sec_filings_task; print(sync_latest_sec_filings_task())"
```

### 4.3 Investigating Tenant Quotas
To inspect an enterprise tenant's credit usage directly in Redis:
```bash
docker exec -it casl-redis-prod redis-cli GET "casl:usage:firm_alpha:202611"
```

### 4.4 Distributed Tracing & APM
1. Open your browser and navigate to `http://<host>:16686`.
2. Select service `casl-backend`.
3. Filter by tag `tenant_id=firm_alpha` or `http.status_code=402` to inspect latency bottlenecks and failed queries.

