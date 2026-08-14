# CASL Backend: Executive Summary

## What Is This System?

CASL (Context-Aware Smart Linker) is a **hybrid retrieval-augmented generation (RAG) backend** that:

1. **Ingests** unstructured documents into a vector database (Qdrant)
2. **Retrieves** semantically relevant passages for queries
3. **Re-ranks** results to improve relevance
4. **Generates** contextual explanations via LLM
5. **Caches** expensive operations for speed
6. **Enforces** enterprise security (JWT auth, RBAC, rate limiting, multi-tenancy)
7. **Runs agents** that autonomously plan and execute multi-step tasks
8. **Evaluates** search quality with synthetic datasets
9. **Streams** token-by-token responses in real-time
10. **Observes** itself with OpenTelemetry tracing and Prometheus metrics

The frontend is a Chrome Extension (Manifest V3) that highlights text on webpages and fetches contextual AI explanations from this backend in a floating UI.

---

## System at a Glance

```
┌─────────────────────────────────────────────────────────────────┐
│ CHROME EXTENSION                                                 │
│ (Highlight text → Fetch explanation)                            │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP REST API
                         │ POST /search, /agents/run, etc.
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ FASTAPI BACKEND GATEWAY                                         │
│                                                                  │
│  ┌─ MIDDLEWARE LAYER ────────────────────────────────────────┐ │
│  │ • Authentication (JWT)                                    │ │
│  │ • Authorization (RBAC)                                    │ │
│  │ • Rate Limiting (Token Bucket)                            │ │
│  │ • Telemetry (OpenTelemetry)                               │ │
│  │ • Security Sanitization (PII masking, injection detection)│ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌─ API ROUTERS ─────────────────────────────────────────────┐ │
│  │ • /search       → Hybrid retrieval + re-ranking           │ │
│  │ • /ingest       → Chunk + embed + store documents         │ │
│  │ • /agents/run   → LangGraph autonomous agents             │ │
│  │ • /stream       → Server-Sent Events for token streaming  │ │
│  │ • /tasks        → Async Celery jobs                       │ │
│  │ • /gateway      → Multi-model LLM routing                 │ │
│  │ • /cache/stats  → Cache performance metrics               │ │
│  │ • /security/*   → Auth endpoints and status               │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌─ CORE SERVICES ───────────────────────────────────────────┐ │
│  │ • Retrieval Engine (Qdrant vector search)                 │ │
│  │ • Re-ranker (Cross-encoder scoring)                       │ │
│  │ • Semantic Cache (Redis + embeddings)                     │ │
│  │ • Token Manager (JWT creation/refresh/revocation)         │ │
│  │ • Tenant Isolation (Multi-tenant filtering)               │ │
│  │ • Audit Logger (Security event logging)                   │ │
│  │ • Agent Executor (LangGraph state machine)                │ │
│  │ • Task Queue (Celery distributed jobs)                    │ │
│  │ • Evaluation Harness (RAGAS metrics)                      │ │
│  └──────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┬──────────────────┐
        │                │                │                  │
        ▼                ▼                ▼                  ▼
    ┌────────────┐  ┌─────────────┐  ┌────────┐         ┌─────────┐
    │  Qdrant    │  │   Redis     │  │Celery/ │         │ Groq    │
    │  (Vector   │  │  (Cache +   │  │RabbitMQ│         │ OpenAI  │
    │  DB)       │  │  Revocation)│  │(Broker)│         │ Ollama  │
    └────────────┘  └─────────────┘  └────────┘         │ Anthropic
                                                         └─────────┘
```

---

## Key Statistics

| Aspect | Count |
|--------|-------|
| Python modules | 92 files |
| Main packages | 15 (agents, api, cache, db, gateway, middleware, models, observability, schemas, security, services, tasks, tools, core, evals) |
| API endpoints | ~30+ (search, ingest, agents, tasks, streaming, gateway, cache, auth, security) |
| Middleware layers | 5 (auth, rate limiting, telemetry, security sanitization, tenant filtering) |
| External integrations | 4 (Qdrant, Redis, Celery, LLMs: Groq/OpenAI/Ollama/Anthropic) |
| Data stores | 2 (Qdrant for vectors, Redis for caching + revocation lists) |
| Security features | 5 (JWT auth, RBAC, rate limiting, PII masking, injection detection) |
| Enterprise tiers | 3 (free, pro, enterprise) |
| Lines of code (backend) | ~3,500+ |
| Lines of code (evals) | ~500+ |

---

## Problem Space

### Original Problem
When users encounter unfamiliar terms or jargon while browsing, they:
1. Open new tabs to search for explanations
2. Lose context and focus
3. Accumulate browser tabs
4. Interrupt their reading flow

### CASL Solution
- **In-place explanations** without context loss (Chrome Extension UI)
- **Context-aware** (understands page context, not just isolated terms)
- **Instant** (sub-second responses via caching)
- **Enterprise-grade** (multi-tenant, secure, auditable)
- **Scalable** (distributed task queue, semantic caching)

### Evolution
The initial MVP (simple Chrome Extension) evolved into:
- **Phase 1**: Basic LLM integration (Groq API calls)
- **Phase 2**: Document ingestion + vector retrieval (RAG)
- **Phase 3**: Caching layer (Redis semantic cache)
- **Phase 4**: Security enforcement (JWT, RBAC, rate limiting)
- **Phase 5**: Agent automation (LangGraph autonomous decision-making)
- **Phase 6**: Enterprise features (multi-tenancy, evaluation, observability)

---

## Major Components (Layers)

### 1. **API Layer** (`backend/api/`, `backend/gateway/`)
- REST endpoints for search, ingestion, agents
- Server-Sent Events (SSE) for real-time token streaming
- Multi-model LLM routing with circuit breakers and cost/latency optimization

### 2. **Authentication & Authorization** (`backend/security/`)
- JWT token issuance and validation
- Role-Based Access Control (RBAC)
- Token-bucket rate limiting per tenant and endpoint
- PII masking and prompt injection detection
- Audit logging of all security events

### 3. **Data Access Layer** (`backend/db/`, `backend/services/`)
- Vector database integration (Qdrant)
- Document ingestion pipeline (chunking, embedding, indexing)
- Retrieval and re-ranking

### 4. **Caching Layer** (`backend/cache/`)
- Two-tier semantic cache (exact hash + vector similarity)
- Redis backend with TTL-based cleanup
- Async cache population (non-blocking)

### 5. **Agent Execution** (`backend/agents/`)
- LangGraph-based state machine for autonomous agents
- Graph traversal with custom nodes
- Safety checks and monitoring

### 6. **Task Queue** (`backend/tasks/`)
- Celery for async/background jobs
- RabbitMQ or Redis as message broker
- Long-running process monitoring

### 7. **Observability** (`backend/observability/`)
- OpenTelemetry tracing
- Prometheus metrics
- Token budget tracking

### 8. **Evaluation & Quality** (`evals/`)
- RAGAS metrics for search quality
- Synthetic dataset generation
- Regression detection

---

## Core Concepts

### Multi-Tenancy
Every request includes a `tenant_id` that filters all operations:
- JWT token carries `tenant_id` claim
- All database queries auto-filtered by tenant
- Rate limits and quotas per tenant
- Audit logs tagged with tenant
- Document IDs scoped to tenant

### Optional Security by Default
All security features are **disabled by default**:
- `AUTH_ENABLED=false` → No JWT validation
- `RBAC_ENABLED=false` → No role checks
- `RATE_LIMIT_ENABLED=false` → No rate limits
- `SECURITY_ENABLED=false` → No PII masking/injection detection

This allows **gradual rollout** from development (no security) → staging (partial security) → production (full security).

### Semantic Caching
Instead of just exact-match caching:
1. Hash the query for O(1) exact-match lookup
2. If miss, embed the query and search Redis for similar vectors
3. Cosine distance < threshold? → Return cached result
4. Otherwise execute and cache asynchronously

Reduces LLM latency from ~1.2s to <15ms for cache hits.

### Agent Autonomy
Agents use LangGraph (a state machine framework) to:
- **Perceive** the environment (available tools, user intent)
- **Plan** multi-step sequences
- **Act** by calling tools (search, agent calls, etc.)
- **Reflect** on outcomes and adapt

Example: "Find papers about attention mechanisms and summarize them"
→ Agent decides to search, re-rank, summarize without explicit instructions per step.

### Enterprise Tiers
Quotas vary by tier:
- **Free**: 60 req/min, 1K documents, 1 concurrent search
- **Pro**: 1K req/min, 100K documents, 10 concurrent searches, agents enabled
- **Enterprise**: 5K req/min, 1M documents, 100 concurrent searches, all features

---

## Key Architectural Decisions

| Decision | Why | Tradeoff |
|----------|-----|----------|
| **Hybrid Retrieval** (Qdrant + re-ranking) | Semantic search + relevance scoring | More complex than pure vector search |
| **Semantic Caching** | Avoid redundant LLM calls | Embedding latency + vector similarity tuning |
| **Multi-model Gateway** | Support Groq, OpenAI, Ollama, Anthropic | Routing complexity + cost tracking |
| **JWT Authentication** | Stateless, scalable, multi-tenant | Token revocation via Redis |
| **Token-bucket Rate Limiting** | Fair, per-endpoint limits with Lua atomicity | Redis dependency for consistency |
| **LangGraph for Agents** | Structured state machine, clear graph flow | Less flexible than custom reasoning loops |
| **Celery + Redis** | Async tasks, distributed workers | Operational complexity (broker management) |
| **OpenTelemetry** | Vendor-agnostic observability | Instrumentation overhead |

---

## Non-Breaking Architecture

The entire system is designed for **optional, additive functionality**:

```
┌─ No Auth, No Cache, No Agents (Default MVP)
├─ + Cache (transparent speedup)
├─ + Auth (JWT + RBAC enabled)
├─ + Rate Limiting (token bucket)
├─ + Agents (autonomous multi-step tasks)
├─ + SSE Streaming (real-time tokens)
├─ + Evaluation (quality metrics)
├─ + Observability (OpenTelemetry + Prometheus)
└─ Full Enterprise System (all features)

At any point:
- Disable feature → System still works
- New middleware layers are added conditionally
- Existing code never modified
- Backward compatible with previous versions
```

---

## What Makes This System Non-Trivial

1. **Multi-tenancy at every layer** — Not just schema-level isolation, but JWT claims, rate limit buckets, quota checks, audit logs
2. **Semantic caching** — Requires embedding model + vector similarity matching + async population
3. **Multi-model LLM routing** — Cost estimation, latency tracking, circuit breakers per provider
4. **Agent autonomy** — Graph traversal, tool calling, reflection, adaptive planning
5. **Enterprise security** — JWT tokens, RBAC decorators, rate limiting with Lua atomicity, PII detection
6. **Real-time streaming** — SSE protocol implementation, token-by-token generation
7. **Observability** — Distributed tracing, token budgeting, metrics aggregation
8. **Evaluation pipeline** — Synthetic dataset generation, RAGAS metrics, regression detection

---

## What You'll Learn

After studying this system, you should understand:

✅ How to build a production-grade RAG system  
✅ How to implement multi-tenancy correctly  
✅ How to layer authentication, authorization, and rate limiting  
✅ How to integrate semantic caching for LLM optimization  
✅ How to structure FastAPI applications at scale  
✅ How to use LangGraph for agent orchestration  
✅ How to implement distributed task queues  
✅ How to stream responses in real-time  
✅ How to add observability without coupling  
✅ How to evaluate AI system quality  

---

## Next Steps

Start with [02_REPOSITORY_MAP.md](02_REPOSITORY_MAP.md) for a detailed inventory of all files and modules.
