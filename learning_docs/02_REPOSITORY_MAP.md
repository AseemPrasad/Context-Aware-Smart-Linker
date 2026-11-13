# Repository Map & Inventory

## Directory Structure

```
casl/
├── backend/                           # Main FastAPI application
│   ├── __init__.py
│   ├── main.py                        # App initialization + route registration
│   ├── agents/                        # LangGraph autonomous agents
│   ├── api/                           # REST API endpoints
│   ├── cache/                         # Semantic caching layer
│   ├── core/                          # Shared configuration
│   ├── db/                            # Database access layer
│   ├── gateway/                       # Multi-model LLM routing
│   ├── middleware/                    # HTTP middleware
│   ├── models/                        # ML model wrappers (re-ranker)
│   ├── observability/                 # Tracing, metrics, monitoring
│   ├── schemas/                       # Pydantic data models
│   ├── security/                      # Auth, RBAC, rate limiting
│   ├── services/                      # Core business logic
│   ├── tasks/                         # Async task queue (Celery)
│   └── tools/                         # Agent tools
├── evals/                             # Evaluation pipeline
│   ├── adapters/                      # RAGAS evaluation adapters
│   ├── datasets/                      # Synthetic data generation
│   ├── metrics/                       # Quality metrics
│   └── reporting.py                   # Report generation
├── .env.example                       # Configuration template
├── CACHE_ARCHITECTURE.md              # Caching design doc
├── SECURITY_GUARDRAILS.md             # Security design doc
├── README.md                          # Project overview
├── manifest.json                      # Chrome Extension manifest
├── background.js                      # Extension service worker
├── content.js                         # Extension content script
├── stream_handler.js                  # SSE streaming client
└── styles.css                         # Extension UI styling
```

---

## Module Inventory

### 1. **backend/main.py** (147 lines)
**Purpose**: FastAPI application factory and route registration

**Key Components**:
- `app = FastAPI()` — Main application instance
- Conditional middleware registration (`if AUTH_ENABLED`)
- Router inclusion:
  - `routes` → Search/ingestion API
  - `gateway_router` → Multi-model LLM routing
  - `tasks_router` → Async job management
  - `monitoring_router` → Task monitoring
  - `stream_router` → Server-Sent Events
- Endpoints:
  - `GET /health` — Liveness probe
  - `GET /cache/stats` — Cache performance metrics
  - `GET /security/stats` → Security guardrails stats
  - `GET /telemetry/metrics` → Token budget metrics
  - `GET /evals/metrics` → Evaluation metrics
  - `GET /agents/metrics` → Agent execution stats
  - `POST /auth/token` → Issue JWT (Step 9)
  - `POST /auth/token/refresh` → Refresh JWT (Step 9)
  - `GET /security/status` → Auth/RBAC/rate limit status (Step 9)

**Dependencies**: All routers, middleware, configs

**Architectural Role**: Central orchestrator; brings all systems together

---

### 2. **backend/agents/** (LangGraph Autonomous Agents)

#### **agents/config.py** (140 lines)
**Purpose**: Agent system configuration

**Key Components**:
- `AgentConfig` — Master config class
  - `enabled` (boolean)
  - `max_iterations` (to prevent infinite loops)
  - `model` (LLM to use for agent)
  - `temperature`
  - `max_tokens`
  - Safety settings

**Architectural Role**: Externalize agent behavior via environment variables

#### **agents/state.py** (110 lines)
**Purpose**: LangGraph state schema

**Key Components**:
- `AgentState` (TypedDict)
  - `input`: Original user query
  - `history`: Conversation log
  - `tools_used`: Tracking of which tools were called
  - `current_step`: Step counter
  - `output`: Final response
  - `intermediate_results`: Reasoning chain

**Architectural Role**: Define the state machine structure

#### **agents/graph.py** (180 lines)
**Purpose**: Build LangGraph workflow

**Key Components**:
- `build_agent_graph()` → Create state machine
- Nodes:
  - `analyze_input` → Parse intent
  - `plan` → Generate multi-step plan
  - `execute_step` → Run tool or query
  - `reflect` → Evaluate outcome
  - `generate_output` → Summarize results
- Edges: Conditional routing based on state

**Architectural Role**: Define agent decision-making flow

#### **agents/nodes.py** (220 lines)
**Purpose**: Individual node implementations

**Key Components**:
- `analyze_input_node(state)` → Extract intent, detect tools needed
- `plan_node(state)` → LLM generates plan
- `execute_node(state)` → Call tools (search, agents, etc.)
- `reflect_node(state)` → Evaluate + adapt
- `generate_output_node(state)` → Create final response

**Architectural Role**: Implement each step in agent logic

#### **agents/middleware.py** (85 lines)
**Purpose**: Agent-level middleware for safety checks

**Key Components**:
- `validate_tool_call()` → Ensure tool exists and is authorized
- `check_rate_limits()` → Prevent tool call storms
- `log_agent_action()` → Audit trail

**Architectural Role**: Guard rails around agent actions

#### **agents/safety.py** (160 lines)
**Purpose**: Monitoring and safety checks for agent execution

**Key Components**:
- `AgentHealthMonitor` singleton
- `check_health()` → Is agent system operational?
- `get_stats()` → Execution metrics
- Failure tracking and alerts

**Architectural Role**: Observability + safety

#### **agents/output.py** (95 lines)
**Purpose**: Format agent output

**Key Components**:
- `AgentOutput` dataclass
  - `response`: Generated text
  - `reasoning`: Explanation of steps taken
  - `tools_used`: List of tools called
  - `execution_time`: Milliseconds
- Serialization to JSON

**Architectural Role**: Consistent response format

---

### 3. **backend/api/** (REST Endpoints)

#### **api/routes.py** (420+ lines)
**Purpose**: Main REST API endpoints

**Key Components**:
- `POST /ingest` → Upload documents (chunking + embedding + indexing)
- `POST /search` → Hybrid retrieval + re-ranking
- `GET /ingestion/status` → Check ingestion progress

**Architecture**: Each endpoint calls services layer

**Architectural Role**: HTTP request → business logic

#### **api/stream_endpoints.py** (180 lines)
**Purpose**: Server-Sent Events (SSE) for token streaming

**Key Components**:
- `@router.get("/stream/search")`
- `async def stream_search()`
  - Streams tokens one-by-one as they're generated
  - Browser receives partial responses instantly
  - Builds UI incrementally

**Architecture**: FastAPI `StreamingResponse` with async generator

**Architectural Role**: Real-time user feedback without WebSocket overhead

#### **api/stream_builder.py** (140 lines)
**Purpose**: Build streaming response

**Key Components**:
- `StreamBuilder` class
  - Manages token accumulation
  - Tracks token count + cost
  - Builds JSON events
- `build_event(token)` → Create SSE event payload
- `build_final_event()` → Wrap up stream

**Architectural Role**: Abstract streaming logic

#### **api/stream_config.py** (60 lines)
**Purpose**: SSE configuration

**Key Components**:
- Timeout settings
- Chunk size
- Max tokens before cutoff

#### **api/stream_generator.py** (120 lines)
**Purpose**: LLM token generation with streaming

**Key Components**:
- `generate_tokens(prompt)` → Async generator
- Integrates with gateway for LLM selection
- Tracks tokens/cost in real-time

#### **api/stream_metrics.py** (100 lines)
**Purpose**: Metrics for streaming operations

**Key Components**:
- Latency tracking (TTFT = time to first token)
- Token throughput
- Stream completion rate

---

### 4. **backend/cache/** (Semantic Caching)

#### **cache/redis_client.py** (90 lines)
**Purpose**: Redis connection management

**Key Components**:
- `RedisClient` singleton
- Fail-silent (logs errors but doesn't crash)
- Connection pooling
- JSON serialization

**Architectural Role**: External state store for cache + token revocation

#### **cache/semantic_cache.py** (210+ lines)
**Purpose**: Two-tiered caching strategy

**Key Components**:
- Tier 1: Exact hash match (MD5 of request)
- Tier 2: Vector similarity (embed query, find similar vectors in Redis)
- `cache.get(request)` → Check both tiers
- `cache.set(request, response)` → Store with TTL

**Architecture**:
```
Query → MD5 hash → Redis lookup (O(1))
  ↓ (miss)
Query → Embed → Vector search in Redis
  ↓ (miss or low similarity)
Execute retrieval + cache asynchronously
```

**Tradeoff**: Extra embedding latency vs. avoiding unnecessary LLM calls

#### **cache/decorator.py** (60 lines)
**Purpose**: Decorator for caching function results

**Key Components**:
- `@cached` decorator
- Extract cache key from function args
- Transparent caching

**Note**: Present but unused (reference implementation)

#### **cache/monitor.py** (140 lines)
**Purpose**: Cache performance monitoring

**Key Components**:
- `CacheMonitor` singleton
- Hit rate tracking
- Latency metrics
- Eviction tracking
- `/cache/stats` endpoint data

---

### 5. **backend/core/** (Shared Configuration)

#### **core/config.py** (200+ lines)
**Purpose**: Centralized environment configuration

**Key Components**:
- `CacheConfig`: Redis, TTL, similarity threshold
- `VectorStoreConfig`: Qdrant connection
- `LLMConfig`: Model selection, API keys
- `AgentConfig`: Agent settings
- `SecurityConfig`: Auth, RBAC, rate limiting
- Task configuration
- Evaluation configuration

**Architectural Role**: Single source of truth for env vars

#### **core/encoder.py** (80 lines)
**Purpose**: Shared embedding model singleton

**Key Components**:
- `get_encoder()` → Returns loaded SentenceTransformer
- Lazy loading (only when cache/evals need it)
- Model caching in memory

**Architectural Role**: Avoid loading embedding model multiple times

---

### 6. **backend/db/** (Data Access Layer)

#### **db/vector_store.py** (320+ lines)
**Purpose**: Qdrant vector database integration

**Key Components**:
- `VectorStore` singleton
- `ingest(documents, embeddings)` → Upload vectors + metadata
- `search(query_embedding, top_k)` → Retrieve similar documents
- `delete_collection()` → Cleanup
- Batch operations for efficiency

**Architecture**: 
- Wraps Qdrant Python client
- Handles connection, retry logic, error handling
- Manages collection lifecycle

**Architectural Role**: Abstract vector database operations

---

### 7. **backend/gateway/** (Multi-Model LLM Routing)

#### **gateway/router.py** (200+ lines)
**Purpose**: Route requests to optimal LLM provider

**Key Components**:
- Provider selection logic
  - Cost estimation (tokens × price per provider)
  - Latency prediction (based on provider SLA)
  - Route to lowest-cost or lowest-latency provider
- Fallback chain if provider fails

**Architecture**: 
```
Request → Estimate cost/latency for each provider
        → Select best → Call provider
        → Fallback if fails
```

#### **gateway/base.py** (150 lines)
**Purpose**: Abstract provider interface

**Key Components**:
- `LLMProvider` abstract base class
- `generate(prompt, temperature, max_tokens)` → Async generation
- `estimate_cost(prompt)` → Cost calculation
- `estimate_latency()` → SLA-based prediction

#### **gateway/circuit_breaker.py** (180 lines)
**Purpose**: Prevent cascading failures

**Key Components**:
- `CircuitBreaker` for each provider
  - States: CLOSED (working), OPEN (broken), HALF_OPEN (testing)
  - Tracks failure rate
  - Auto-recovery with backoff

**Architectural Role**: Resilience pattern for distributed systems

#### **gateway/complexity.py** (100 lines)
**Purpose**: Estimate prompt complexity (cost proxy)

**Key Components**:
- Token counting (without calling LLM)
- Input/output token estimation
- Cost calculation per provider

#### **gateway/config.py** (120 lines)
**Purpose**: Provider configuration

**Key Components**:
- `ProviderConfig` per LLM (OpenAI, Groq, Ollama, Anthropic)
- API keys, endpoints, pricing
- Rate limits

#### **gateway/metrics.py** (140 lines)
**Purpose**: Track gateway performance

**Key Components**:
- Provider selection metrics
- Cost tracking
- Latency aggregation
- Fallback frequency

#### **gateway/providers/** (Multiple providers)

**anthropic_provider.py** (140 lines):
- Anthropic API integration
- Streaming support
- Cost estimation

**openai_provider.py** (140 lines):
- OpenAI API integration
- GPT-3.5, GPT-4 support
- Token counting via tiktoken

**ollama_provider.py** (120 lines):
- Local Ollama server integration
- Zero cost (local inference)
- Fallback option

---

### 8. **backend/middleware/** (HTTP Request Processing)

#### **middleware/telemetry.py** (200+ lines)
**Purpose**: OpenTelemetry tracing

**Key Components**:
- `TelemetryMiddleware`
- Traces every HTTP request
- Records:
  - Request method, path, query params
  - Response status, latency
  - Errors and exceptions
  - Token usage (for LLM calls)
- Exports to OTEL collector

**Architectural Role**: Observability without code changes

#### **middleware/sanitizer.py** (180 lines)
**Purpose**: Security sanitization (PII masking, injection detection)

**Key Components**:
- `SanitizationMiddleware` (optional, if `SECURITY_ENABLED=true`)
- Input validation
- PII anonymization
- Prompt injection detection
- Output validation for leaked credentials

---

### 9. **backend/models/** (ML Model Wrappers)

#### **models/reranker.py** (200+ lines)
**Purpose**: Cross-encoder re-ranking

**Key Components**:
- `Reranker` singleton
- Load cross-encoder model (e.g., mxbai-rerank-large-v1)
- `rerank(query, documents)` → Score each document
- Sorts by relevance score

**Architectural Role**: Improve retrieval relevance (semantic search alone isn't enough)

**Why Needed**: BM25 (keyword search) + vector similarity (semantic) → Re-ranker (true relevance)

---

### 10. **backend/observability/** (Monitoring & Metrics)

#### **observability/tracer.py** (180 lines)
**Purpose**: Setup OpenTelemetry

**Key Components**:
- `setup_telemetry()` → Initialize OTEL
- Trace provider, exporter configuration
- Span processors
- Instrument FastAPI

#### **observability/metrics.py** (250+ lines)
**Purpose**: Prometheus metrics and token budgeting

**Key Components**:
- `TokenBudgetManager` singleton
  - Track input tokens, output tokens, total cost
  - Per-tenant budgets
  - Alerts when over budget
- Prometheus collectors:
  - Request latency histogram
  - Token counter gauge
  - Cost gauge per tenant
  - Cache hit rate

**Architectural Role**: Observability + cost control

---

### 11. **backend/schemas/** (Data Models)

#### **schemas/retrieval.py** (140 lines)
**Purpose**: Pydantic models for search API

**Key Components**:
- `SearchRequest`
  - `tenant_id`
  - `query`
  - `top_k` (number of results)
  - `filters` (optional metadata filtering)
  - `use_cache` (optional cache bypass)
- `SearchResponse`
  - `tenant_id`
  - `query`
  - `hits` (list of relevant passages)
  - `execution_time_ms`
- `Document` (in search hits)
  - `document_id`
  - `passage`
  - `score` (relevance score)
  - `metadata`

**Architectural Role**: Data contract between API clients and server

#### **schemas/cache.py** (100 lines)
**Purpose**: Cache-related data models

**Key Components**:
- `CachedSearchPayload`
- `CacheMetadata` (TTL, embedding used, distance)
- `CacheStatsResponse`

---

### 12. **backend/security/** (Authentication, Authorization, Rate Limiting)

#### **security/auth.py** (212 lines)
**Purpose**: JWT authentication

**Key Components**:
- `JWTConfig` — Configuration
- `JWTPayload` dataclass
  - `tenant_id` — Tenant identifier
  - `user_id` — User identifier
  - `user_role` — admin/editor/viewer
  - `exp`, `iat`, `jti` — Expiry, issued-at, JWT ID
- `TokenValidator` — Signature verification + parsing
- `TenantContext` — Thread-local tenant storage
- `get_current_tenant()`, `get_current_user()`, `get_current_role()` — Helper functions

**Architectural Role**: Stateless multi-tenant authentication

#### **security/rate_limiter.py** (207 lines)
**Purpose**: Token-bucket rate limiting

**Key Components**:
- `RateLimitConfig` — Tier-based limits
- `TokenBucket` — In-memory bucket per tenant + endpoint
- `RateLimiter` singleton
- Lua script for atomic check-and-decrement
- `acquire(tenant_id, endpoint)` → Returns (allowed, remaining, reset_seconds)

**Architecture**: Per-tenant + per-endpoint limit with Redis atomicity

#### **security/rbac.py** (198 lines)
**Purpose**: Role-Based Access Control

**Key Components**:
- `Role` enum (admin, editor, viewer)
- `RBACConfig` — Permission matrix per role
- `RBACEnforcer` singleton
- `@require_role("admin")` decorator
- `@require_permission("delete")` decorator

**Architectural Role**: Action-level authorization

#### **security/middleware.py** (137 lines)
**Purpose**: Middleware for auth + rate limiting

**Key Components**:
- `AuthMiddleware` — Extract JWT, validate, inject context
- `RateLimitMiddleware` — Check rate limit, return 429 if exceeded
- Conditional registration based on `AUTH_ENABLED`

#### **security/token_manager.py** (142 lines)
**Purpose**: Token lifecycle (issue, refresh, revoke)

**Key Components**:
- `TokenManager` singleton
- `issue_token(tenant_id, user_id, role)` → Create new JWT
- `refresh_token(old_token)` → Validate, revoke, issue new
- `revoke_token(jti)` → Add to Redis revocation list with TTL
- `is_revoked(jti)` → Check revocation status

#### **security/tenant_isolation.py** (100 lines)
**Purpose**: Automatic multi-tenant filtering

**Key Components**:
- `TenantFilter` utility
  - `apply_to_request()` — Inject tenant_id into search request
  - `apply_to_query()` — Add tenant condition to Qdrant filter
  - `scope_document_id()`, `unscope_document_id()` — ID scoping
- `TenantContextDependency` — FastAPI dependency

**Architectural Role**: Double-blind tenant isolation (JWT + database filtering)

#### **security/enterprise.py** (157 lines)
**Purpose**: Enterprise tier management and quotas

**Key Components**:
- `TenantTier` enum (free, pro, enterprise)
- `TenantQuota` dataclass with limits
- `TenantManager` singleton
- Tier definitions and quota defaults
- Per-tenant tier overrides via environment

#### **security/audit_logger.py** (210 lines)
**Purpose**: Security event logging

**Key Components**:
- `SecurityEventType` enum (auth_success, auth_failure, rbac_denied, rate_limit_exceeded, etc.)
- `SecurityEvent` dataclass
- `AuditLogger` singleton
- Structured JSON logging
- Anomaly detection (repeated failures, high rate limit events)

#### **security/monitor.py** (120 lines)
**Purpose**: Security system monitoring

**Key Components**:
- `SecurityMonitor` singleton
- Health checks for auth, RBAC, rate limiting
- Stats: failure counts, rate limit breaches

---

### 13. **backend/services/** (Business Logic)

#### **services/retrieval_engine.py** (280+ lines)
**Purpose**: Core RAG orchestration

**Key Components**:
1. **Query Processing**
   - Embed query
   - Check cache (if enabled)
2. **Retrieval**
   - Vector search in Qdrant
   - Metadata filtering
3. **Re-ranking**
   - Cross-encoder scoring
   - Sort by relevance
4. **Response Building**
   - Format as SearchResponse
5. **Async Cache Population**
   - Non-blocking cache update

**Flow**:
```
SearchRequest → Embed query
              → Cache lookup (Tier 1: exact, Tier 2: semantic)
              → Hit? Return cached response
              → Retrieve from Qdrant (top_k * 2 for re-ranking)
              → Re-rank with cross-encoder
              → Build SearchResponse
              → Async: Cache populate
              → Return response
```

**Architectural Role**: Heart of the RAG system

#### **services/ingestion.py** (250+ lines)
**Purpose**: Document ingestion pipeline

**Key Components**:
1. **Document Loading** — Accept markdown, PDF, text
2. **Chunking** — Split into semantic chunks (with overlap)
3. **Embedding** — Generate vectors for chunks
4. **Indexing** — Upload to Qdrant with metadata
5. **Progress Tracking** — Store state in Redis

**Flow**:
```
RawDocument → Parse format
            → Split into chunks
            → Embed chunks
            → Batch upload to Qdrant
            → Update progress
```

---

### 14. **backend/tasks/** (Async Task Queue)

#### **tasks/celery_app.py** (80 lines)
**Purpose**: Celery application initialization

**Key Components**:
- `app = Celery('casl')`
- Broker configuration (Redis/RabbitMQ)
- Worker pool settings

#### **tasks/config.py** (100 lines)
**Purpose**: Task queue configuration

**Key Components**:
- Broker URL
- Result backend
- Task serialization (JSON)
- Retry policies

#### **tasks/jobs.py** (180 lines)
**Purpose**: Async job definitions

**Key Components**:
- `@app.task` decorated functions:
  - `cache_search_result()` — Async cache population
  - `process_ingestion()` — Long-running document ingestion
  - `cleanup_expired_tokens()` — Token revocation cleanup
  - `generate_synthetic_dataset()` — Eval dataset generation

#### **tasks/endpoints.py** (180 lines)
**Purpose**: REST API for task management

**Key Components**:
- `POST /tasks/submit` — Submit long-running job
- `GET /tasks/{task_id}` — Check status
- `GET /tasks/{task_id}/result` — Retrieve result
- `POST /tasks/{task_id}/cancel` — Cancel job

#### **tasks/monitoring.py** (150 lines)
**Purpose**: Task execution monitoring

**Key Components**:
- `TaskMonitor` singleton
- Track active tasks
- Success/failure rates
- Latency metrics
- `/tasks/metrics` endpoint

#### **tasks/queue.py** (120 lines)
**Purpose**: Task queue wrapper

**Key Components**:
- `TaskQueue` singleton
- `submit(job_type, **kwargs)` → Queue task
- Retry logic
- Dead letter queue

#### **tasks/worker.py** (100 lines)
**Purpose**: Celery worker entrypoint

**Key Components**:
- `app.worker_main()` — Start worker process
- Graceful shutdown
- Logging

#### **tasks/backend.py** (80 lines)
**Purpose**: Task result persistence

**Key Components**:
- Redis backend for storing task results
- Cleanup logic for old results

#### **tasks/models.py** (100 lines)
**Purpose**: Pydantic models for tasks

**Key Components**:
- `TaskRequest` — Job definition
- `TaskResponse` — Job status/result
- `TaskMetrics` — Execution stats

---

### 15. **backend/tools/** (Agent Tools)

#### **tools/search_tool.py** (150 lines)
**Purpose**: Search tool for agents

**Key Components**:
- `SearchTool` class
- Agents can call this to search
- Wraps retrieval engine
- Returns formatted results for agent consumption

**Architectural Role**: Bridge between agent execution and RAG system

---

### 16. **evals/** (Evaluation & Quality Metrics)

#### **evals/eval_harness.py** (280+ lines)
**Purpose**: Main evaluation orchestrator

**Key Components**:
- `EvaluationHarness` singleton
- Load synthetic datasets
- Run searches over dataset
- Compute RAGAS metrics
- Track metric history
- Detect regressions

#### **evals/config.py** (120 lines)
**Purpose**: Evaluation configuration

**Key Components**:
- Model selection for evaluation
- Dataset settings
- Metric thresholds
- Regression alert thresholds

#### **evals/datasets/generator.py** (200+ lines)
**Purpose**: Generate synthetic datasets

**Key Components**:
- `SyntheticDatasetGenerator` class
- Generate documents
- Generate questions based on docs
- Generate ground truth answers

#### **evals/datasets/manager.py** (160 lines)
**Purpose**: Dataset management

**Key Components**:
- Load/save datasets
- Version tracking
- Dataset statistics

#### **evals/metrics/ragas_eval.py** (220+ lines)
**Purpose**: RAGAS evaluation metrics

**Key Components**:
- Context relevance
- Answer relevance
- Faithfulness (hallucination detection)
- Retrieval metrics

#### **evals/adapters/retrieval_adapter.py** (140 lines)
**Purpose**: Adapt retrieval engine to RAGAS interface

**Key Components**:
- Implement RAGAS adapter protocol
- Convert SearchResponse to RAGAS format

#### **evals/regression_detector.py** (120 lines)
**Purpose**: Detect metric regressions

**Key Components**:
- Compare current metrics to baseline
- Alert if metrics degrade
- Track regression history

#### **evals/reporting.py** (100 lines)
**Purpose**: Generate evaluation reports

**Key Components**:
- Metric summaries
- Visualizations
- Regression alerts

---

## Configuration Files

### **.env.example** (31KB)
Master configuration template covering:

**Authentication**: `AUTH_ENABLED`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_EXPIRY_SECONDS`, `REQUIRE_AUTH`

**Rate Limiting**: `RATE_LIMIT_ENABLED`, `RATE_LIMIT_FAIL_OPEN`, tier-based limits

**RBAC**: `RBAC_ENABLED`, `DEFAULT_ROLE`, per-role permissions

**Multi-tenancy**: `DEFAULT_TIER`, `TENANT_TIER_*`, quota overrides

**Caching**: `REDIS_ENABLED`, `CACHE_SIMILARITY_THRESHOLD`, TTLs

**LLM**: Model selection, API keys, temperature, max tokens

**Observability**: OTEL endpoint, sampling rate, token budget limits

**Evaluation**: Dataset paths, metric thresholds

**Tasks**: Celery broker URL, worker count

**Database**: Qdrant URL, collection names

---

## Frontend Files (Chrome Extension)

### **manifest.json**
- Extension metadata
- Content script + service worker permissions
- Icon definitions

### **background.js** (Service Worker)
- Listen for context menu events ("Explain this")
- Send message to content script
- Fetch from backend API
- Manage extension state/storage

### **content.js** (Content Script)
- Detect text selection
- Show "Explain" button
- Capture page context (title, surrounding text)
- Communicate with background worker

### **stream_handler.js**
- Manage SSE connection
- Buffer and display tokens
- Handle errors + reconnects
- Format response UI

### **styles.css**
- Floating tooltip styling
- Animation effects
- Dark/light mode

---

## Framework & Library Files

### Python Frameworks
- **FastAPI** — REST API framework (in main.py)
- **Pydantic** — Data validation (in schemas/)
- **LangGraph** — Agent orchestration (in agents/)
- **Celery** — Distributed task queue (in tasks/)

### External Services
- **Qdrant** — Vector database
- **Redis** — Cache + revocation list
- **Groq/OpenAI/Anthropic/Ollama** — LLM providers
- **SentenceTransformers** — Embedding model
- **RAGAS** — Evaluation metrics

---

## Key Files Summary

| File | Purpose | LOC | Importance |
|------|---------|-----|------------|
| `backend/main.py` | App initialization | 147 | Critical |
| `backend/api/routes.py` | Search/ingest endpoints | 420+ | Critical |
| `backend/services/retrieval_engine.py` | RAG orchestration | 280+ | Critical |
| `backend/security/auth.py` | JWT authentication | 212 | High |
| `backend/security/middleware.py` | Request middleware | 137 | High |
| `backend/cache/semantic_cache.py` | Two-tier caching | 210+ | High |
| `backend/gateway/router.py` | LLM routing | 200+ | High |
| `backend/agents/graph.py` | Agent orchestration | 180 | High |
| `backend/tasks/celery_app.py` | Task queue | 80 | Medium |
| `backend/observability/tracer.py` | Tracing | 180 | Medium |
| `evals/eval_harness.py` | Quality evaluation | 280+ | Medium |

---

## Dependency Relationships

```
main.py
  ├─ api/routes.py ──► services/retrieval_engine.py ──► db/vector_store.py
  │                                                    ├─ cache/semantic_cache.py
  │                                                    └─ models/reranker.py
  ├─ gateway/endpoint.py ──► gateway/router.py ──► gateway/providers/*
  ├─ middleware/telemetry.py ──► observability/tracer.py
  ├─ middleware/sanitizer.py ──► security/* (PII, injection detection)
  ├─ security/middleware.py ──► security/auth.py
  │                        ──► security/rate_limiter.py
  ├─ agents/graph.py ──► agents/nodes.py ──► agents/safety.py
  ├─ tasks/endpoints.py ──► tasks/celery_app.py
  └─ evals/eval_harness.py

services/retrieval_engine.py depends on:
  ├─ cache/semantic_cache.py
  ├─ db/vector_store.py
  ├─ models/reranker.py
  ├─ core/encoder.py
  └─ schemas/retrieval.py

security/middleware.py depends on:
  ├─ security/auth.py
  ├─ security/rate_limiter.py
  ├─ security/tenant_isolation.py
  └─ security/audit_logger.py
```

---

## Next Steps

Continue to [03_SYSTEM_MENTAL_MODEL.md](03_SYSTEM_MENTAL_MODEL.md) for a high-level explanation of how all these pieces fit together.
