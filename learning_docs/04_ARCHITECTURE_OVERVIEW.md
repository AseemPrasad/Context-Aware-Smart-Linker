# Architecture Overview

## Architectural Style

CASL uses a **layered microservice-inspired architecture** with clear separation of concerns:

```
┌──────────────────────────────────────────────────────────────────┐
│ PRESENTATION LAYER                                               │
│ Chrome Extension (JavaScript)                                    │
└───────────────────────┬──────────────────────────────────────────┘
                        │ HTTP REST
                        │
┌───────────────────────▼──────────────────────────────────────────┐
│ API/GATEWAY LAYER                                                │
│ FastAPI Application (main.py)                                    │
├──────────────────────────────────────────────────────────────────┤
│ Route Handlers: Search, Ingest, Agents, Tasks, Streaming, Auth   │
└───────────────────────┬──────────────────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────────────────┐
│ MIDDLEWARE LAYER (Request/Response Processing)                   │
├──────────────────────────────────────────────────────────────────┤
│ • AuthMiddleware → Validates JWT, injects tenant context         │
│ • RateLimitMiddleware → Token bucket checks                      │
│ • TelemetryMiddleware → OpenTelemetry tracing                    │
│ • SanitizationMiddleware → PII masking, injection detection      │
│ • TenantContextMiddleware → Auto-filter by tenant               │
└───────────────────────┬──────────────────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────────────────┐
│ BUSINESS LOGIC LAYER (Services)                                  │
├──────────────────────────────────────────────────────────────────┤
│ • RetrievalEngine → Search, embedding, re-ranking               │
│ • IngestionEngine → Document processing, chunking               │
│ • AgentExecutor → LangGraph state machine                       │
│ • TokenManager → JWT lifecycle (issue, refresh, revoke)         │
│ • TenantFilter → Multi-tenant query filtering                   │
│ • AuditLogger → Security event logging                          │
└───────────────────────┬──────────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┬─────────────────┐
        │               │               │                 │
        ▼               ▼               ▼                 ▼
┌──────────────┐ ┌──────────────┐ ┌─────────────┐ ┌──────────────┐
│ DATA ACCESS  │ │CACHING LAYER │ │TASK QUEUE   │ │LLM GATEWAY   │
├──────────────┤ ├──────────────┤ ├─────────────┤ ├──────────────┤
│VectorStore   │ │SemanticCache │ │Celery Tasks │ │ProviderRouter│
│(Qdrant)      │ │(Redis)       │ │(RabbitMQ)   │ │CircuitBreaker│
└──────────────┘ └──────────────┘ └─────────────┘ └──────────────┘
        │               │               │                 │
        │               │               │                 │
        ▼               ▼               ▼                 ▼
    ┌───────────────────────────────────────────────────────────┐
    │ EXTERNAL SERVICES                                         │
    ├───────────────────────────────────────────────────────────┤
    │ • Qdrant (Vector DB)                                      │
    │ • Redis (Cache + Revocation + Task Broker)               │
    │ • LLM APIs (Groq, OpenAI, Anthropic, Ollama)             │
    │ • SentenceTransformers (Embedding Model)                 │
    │ • RabbitMQ (Celery Broker)                               │
    │ • OpenTelemetry Collector (Tracing)                      │
    └───────────────────────────────────────────────────────────┘
```

---

## Architectural Patterns

### 1. **Layered Architecture**
- **Separation of Concerns**: Each layer has a single responsibility
- **Dependency Flow**: Upper layers depend on lower layers (not vice versa)
- **Testability**: Each layer can be tested independently

```
Request → API Layer → Middleware → Business Logic → Data Access → External Service
```

### 2. **Middleware Chain Pattern**
```python
# In main.py
if os.getenv("AUTH_ENABLED", "false").lower() == "true":
    app.add_middleware(AuthMiddleware)
    app.add_middleware(RateLimitMiddleware)
app.add_middleware(TelemetryMiddleware)
```

Each middleware:
- Processes request before reaching handler
- Can transform request context
- Can return early (e.g., 401, 429)
- Processes response before returning to client

### 3. **Singleton Pattern**
Most services are singletons to avoid creating multiple instances:

```python
# Bad: Creates new instance each time
def get_vector_store():
    return VectorStore()

# Good: Reuse same instance
_vector_store = None
def get_vector_store():
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
```

Examples in CASL:
- `RedisClient` (single connection pool)
- `VectorStore` (single Qdrant connection)
- `TokenManager` (single JWT handler)
- `RateLimiter` (single token bucket manager)
- `AuditLogger` (single audit log)

### 4. **Dependency Injection via FastAPI `Depends`**
```python
@router.post("/search")
async def search(
    request: SearchRequest,
    _tenant = Depends(TenantContextDependency)  # Injected
):
    # _tenant is auto-populated
    return await retrieval_engine.search(request)
```

Benefits:
- Decouples handler from infrastructure
- Easy to test (mock dependencies)
- Centralized context management

### 5. **Thread-Local Context Storage**
```python
# In TenantContext
_thread_local = threading.local()

def set_current_tenant(tenant_id: str):
    _thread_local.tenant_id = tenant_id

def get_current_tenant() -> str:
    return getattr(_thread_local, "tenant_id", "default")
```

Why?
- Each HTTP request runs in its own thread
- Context doesn't leak between requests
- No need to pass tenant_id through all function calls

### 6. **Factory Pattern for LLM Providers**
```python
def get_llm_provider(model_name: str) -> LLMProvider:
    if model_name == "gpt-4":
        return OpenAIProvider(model="gpt-4")
    elif model_name == "mixtral":
        return OllamaProvider(model="mixtral")
    elif model_name == "claude":
        return AnthropicProvider(model="claude-3")
    else:
        raise ValueError(f"Unknown model: {model_name}")
```

### 7. **Circuit Breaker Pattern (for Resilience)**
```
Provider Status:
CLOSED   (working)  → Route requests normally
         │ (failures accumulate)
         ▼
OPEN     (broken)   → Reject new requests immediately
         │ (after backoff)
         ▼
HALF_OPEN (testing) → Allow one request to test recovery
         │
         ├─ (success) → CLOSED
         └─ (failure) → OPEN
```

Used for LLM providers to prevent cascading failures.

### 8. **Observer Pattern (for Audit Logging)**
```python
# In RateLimitMiddleware
if rate_limit_exceeded:
    audit_logger.log_rate_limit_event(
        tenant_id=tenant_id,
        endpoint=endpoint,
        reset_seconds=reset_seconds
    )
```

Audit logging is decoupled from rate limiting logic.

### 9. **Async/Await Pattern**
```python
@router.post("/search")
async def search(request: SearchRequest):
    # Concurrent I/O operations
    embedding = await encoder.encode_async(request.query)
    candidates = await qdrant.search_async(embedding)
    response = await build_response_async(candidates)
    
    # Non-blocking cache population
    celery_app.send_task("cache_result", args=[request, response])
    
    return response
```

Benefits:
- No thread pool overhead (single thread, async I/O)
- Scalable to thousands of concurrent connections
- Non-blocking operations for long-running tasks

### 10. **Decorator Pattern (for RBAC)**
```python
@require_role("admin")
@require_permission("delete")
async def delete_document(doc_id: str):
    # Only admin role with delete permission reaches here
    pass
```

Decorators can be stacked for multiple checks.

---

## Request Processing Flow (Detailed)

```
1. HTTP Request arrives
   POST /search
   Authorization: Bearer {token}
   Content-Type: application/json
   
2. FastAPI router matches endpoint → search handler

3. Middleware Chain (in reverse order of registration):
   
   3.1 AuthMiddleware
       ├─ Extract token from Authorization header
       ├─ Validate signature using JWT_SECRET_KEY
       ├─ Parse JWTPayload (tenant_id, user_id, role)
       ├─ Store in TenantContext (thread-local)
       └─ If invalid + REQUIRE_AUTH=true → Return 401
   
   3.2 RateLimitMiddleware
       ├─ Get tenant_id from context
       ├─ Check Redis token bucket
       ├─ If exceeded → Return 429 + Retry-After header
       └─ If allowed → Decrement tokens, continue
   
   3.3 TelemetryMiddleware
       ├─ Start OpenTelemetry span
       ├─ Record request metadata
       └─ Attach to request.state
   
   3.4 SanitizationMiddleware (if SECURITY_ENABLED)
       ├─ Detect PII in query + context
       ├─ Mask sensitive data
       ├─ Detect prompt injections
       └─ Block if severity >= threshold
   
   3.5 (Request reaches handler)

4. Search Handler
   @router.post("/search")
   async def search(request: SearchRequest):
       # Inject tenant_id from context
       request.tenant_id = TenantContext.get_current_tenant()
       
       # Call business logic
       response = await retrieval_engine.search(request)
       
       return response

5. RetrievalEngine.search()
   
   5.1 Cache Layer
       ├─ Tier 1: Exact hash match
       │  └─ Hit? Return immediately (~5ms)
       └─ Tier 2: Semantic vector similarity
          └─ Hit? Return (~20ms)
   
   5.2 Embedding
       ├─ Encode query using SentenceTransformer
       └─ Get embedding vector [0.1, ..., 0.8]
   
   5.3 Vector Search (Qdrant)
       ├─ Search with filter: {tenant_id: request.tenant_id}
       ├─ Get top-k * 2 candidates (for re-ranking)
       └─ Return list of passages + metadata
   
   5.4 Re-ranking
       ├─ Load cross-encoder model
       ├─ Score each passage [0.0, 1.0]
       ├─ Sort by score
       └─ Keep top-k
   
   5.5 Response Building
       ├─ Create SearchResponse
       ├─ Attach metadata (timestamps, scores)
       └─ Return response
   
   5.6 Async Cache Population (non-blocking)
       └─ Queue Celery task: cache_search_result(request, response)

6. Audit Logging
   ├─ Log successful search
   ├─ Record tenant_id, query, results count
   ├─ Check for anomalies
   └─ Store in audit log

7. OpenTelemetry Span Completion
   ├─ Record execution time
   ├─ Record tokens used
   ├─ Export to OTEL collector

8. Response returned to client
   200 OK
   {
     "tenant_id": "default",
     "query": "What is attention?",
     "hits": [...]
   }

9. Client displays results in floating UI
```

---

## Separation of Concerns

### Horizontal Slicing (Layers)
```
┌─ API Layer (routes.py)
   ├─ Responsibility: Parse HTTP requests, build responses
   └─ Files: api/routes.py, api/stream_endpoints.py

├─ Service Layer (services/)
   ├─ Responsibility: Business logic (RAG orchestration)
   └─ Files: services/retrieval_engine.py, services/ingestion.py

├─ Data Access Layer (db/)
   ├─ Responsibility: Vector database operations
   └─ Files: db/vector_store.py

├─ Cache Layer (cache/)
   ├─ Responsibility: Two-tier semantic caching
   └─ Files: cache/semantic_cache.py, cache/redis_client.py

└─ Security Layer (security/)
    ├─ Responsibility: Auth, RBAC, rate limiting, audit
    └─ Files: security/auth.py, security/rbac.py, security/rate_limiter.py
```

### Vertical Slicing (Features)
```
┌─ Agent Subsystem (agents/)
   ├─ agents/config.py
   ├─ agents/graph.py
   ├─ agents/nodes.py
   ├─ agents/state.py
   └─ agents/safety.py

├─ Streaming Subsystem (api/)
   ├─ api/stream_endpoints.py
   ├─ api/stream_builder.py
   ├─ api/stream_generator.py
   └─ api/stream_metrics.py

├─ Gateway Subsystem (gateway/)
   ├─ gateway/router.py
   ├─ gateway/circuit_breaker.py
   ├─ gateway/providers/
   └─ gateway/metrics.py

├─ Task Queue Subsystem (tasks/)
   ├─ tasks/celery_app.py
   ├─ tasks/jobs.py
   ├─ tasks/endpoints.py
   └─ tasks/monitoring.py

└─ Evaluation Subsystem (evals/)
    ├─ evals/eval_harness.py
    ├─ evals/datasets/
    ├─ evals/metrics/
    └─ evals/reporting.py
```

---

## Dependency Graph (Simplified)

```
main.py (Application entry point)
    ├─→ api/routes.py (Search/ingest endpoints)
    │     └─→ services/retrieval_engine.py (RAG orchestration)
    │           ├─→ cache/semantic_cache.py
    │           ├─→ db/vector_store.py (Qdrant)
    │           └─→ models/reranker.py
    │
    ├─→ gateway/endpoint.py (LLM routing)
    │     └─→ gateway/router.py (Provider selection)
    │           └─→ gateway/providers/* (API integrations)
    │
    ├─→ agents/graph.py (Agent orchestration)
    │     ├─→ agents/nodes.py
    │     └─→ agents/safety.py
    │
    ├─→ tasks/endpoints.py (Async job API)
    │     └─→ tasks/celery_app.py
    │
    ├─→ security/middleware.py (Auth + rate limiting)
    │     ├─→ security/auth.py (JWT validation)
    │     ├─→ security/rate_limiter.py (Token bucket)
    │     ├─→ security/tenant_isolation.py (Multi-tenant filtering)
    │     └─→ security/audit_logger.py (Event logging)
    │
    ├─→ middleware/telemetry.py (OpenTelemetry tracing)
    │
    └─→ evals/eval_harness.py (Quality evaluation)
          ├─→ evals/datasets/ (Synthetic data)
          └─→ evals/metrics/ (RAGAS metrics)
```

---

## Data Flow Architecture

### Search Request
```
Client Query
     │
     ▼
[Embedding Model] ──→ Query Vector
     │
     ├─ [Cache Tier 1] (MD5 hash)
     │   └─ Hit? ✓ Return cached response
     │
     ├─ [Cache Tier 2] (Vector similarity)
     │   └─ Hit? ✓ Return cached response
     │
     ├─ [Qdrant Vector DB]
     │   ├─ Search: vector similarity
     │   └─ Filter: tenant_id = "tenant_x"
     │   └─ Return: Top-k passages
     │
     ├─ [Cross-Encoder Model]
     │   └─ Score passages [0.0, 1.0]
     │
     └─ [Response] ──→ Client
         (async cache population in background)
```

### Ingestion Pipeline
```
Raw Documents
     │
     ├─ [Parser] → Extract text from PDF/markdown
     │
     ├─ [Chunker] → Split into semantic chunks (~200 tokens each)
     │
     ├─ [Embedding Model] → Generate vectors
     │
     ├─ [Qdrant Uploader]
     │   ├─ Scope document IDs: tenant_id:doc_id
     │   └─ Store vectors + metadata
     │
     └─ [Progress Tracker] → Redis (for status polling)
```

### Agent Execution
```
User Query: "Find and summarize attention papers"
     │
     ├─ [LLM] → Analyze intent (add search_tool, summarize_tool to context)
     │
     ├─ [LangGraph State Machine]
     │   ├─ Node 1: Analyze Input → Extract intent
     │   ├─ Node 2: Plan → Generate multi-step plan
     │   ├─ Node 3: Execute → Call search_tool
     │   ├─ Node 4: Reflect → Evaluate results
     │   └─ Node 5: Generate Output → Synthesize summary
     │
     └─ [Response] → Client
```

---

## Key Architectural Decisions

### 1. Why Layered Architecture?
**Decision**: Divide system into API → Services → Data Access layers

**Why**:
- Clear separation of concerns
- Easy to test each layer independently
- Easy to replace implementations (e.g., swap Qdrant for Weaviate)

**Tradeoff**: More files/folders, slightly more complexity than a monolithic design

### 2. Why Middleware Chain?
**Decision**: Authentication/rate limiting/telemetry as middleware, not in route handlers

**Why**:
- Cross-cutting concerns (apply to all routes)
- Can be enabled/disabled conditionally
- Decouples security from business logic

**Tradeoff**: Middleware execution order matters, harder to debug

### 3. Why Semantic Caching Over Just Exact Match?
**Decision**: Two-tier cache (exact + vector similarity)

**Why**:
- Exact matching alone misses similar queries
- Vector similarity catches semantic equivalence
- Huge latency reduction (1200ms → 20ms for hits)

**Tradeoff**: Embedding overhead, vector similarity tuning complexity

### 4. Why Re-ranking After Vector Search?
**Decision**: Vector search → Re-rank (instead of just vector search)

**Why**:
- Vector search alone isn't perfect
- Re-ranking improves relevance significantly
- Cross-encoder captures true semantic similarity better

**Tradeoff**: Extra inference latency, but worth for quality

### 5. Why LangGraph for Agents?
**Decision**: Use LangGraph state machine instead of custom loops

**Why**:
- Clear graph structure (visualizable)
- Built-in retry/error handling
- Community support and examples
- Structured state management

**Tradeoff**: Learning curve, less flexible than custom code

### 6. Why Celery for Async Tasks?
**Decision**: Use Celery + RabbitMQ/Redis for background jobs

**Why**:
- Distributed task queue (scale workers independently)
- Retry logic built-in
- Job persistence
- Monitoring/admin tools

**Tradeoff**: Operational complexity (broker management)

### 7. Why OpenTelemetry for Observability?
**Decision**: Use OTEL instead of custom logging

**Why**:
- Vendor-agnostic (works with Datadog, New Relic, Jaeger, etc.)
- Structured traces capture request flow
- Token budgeting built-in

**Tradeoff**: Instrumentation code overhead

---

## Scaling Considerations

### Horizontal Scaling (Add More Instances)

**What scales well**:
- FastAPI request handlers (stateless)
- Celery workers (distributed)
- Vector search load (Qdrant is distributed)

**What's the bottleneck**:
- Embedding model (single instance, not distributed)
- Re-ranker model (single instance)
- Redis (single instance, can use cluster mode)

**How to scale**:
```
┌─ Load Balancer
   ├─ FastAPI Instance 1
   ├─ FastAPI Instance 2
   └─ FastAPI Instance 3
        ├─ All read from shared Qdrant cluster
        ├─ All read from shared Redis cluster
        └─ All connect to shared embedding model (or distributed)

Celery Workers (can have many):
   ├─ Worker 1
   ├─ Worker 2
   └─ Worker N
        └─ All read from shared RabbitMQ broker
```

### Vertical Scaling (Bigger Machines)

**Embedding Model**: Larger models slower but more accurate
**Re-ranker**: Larger models better but slower
**Vector DB**: More RAM = faster search
**Cache**: More RAM = larger cache, fewer misses

---

## Non-Breaking Extensibility

The system is designed so new features don't break existing code:

```
Version 1: Base system (search, ingest)

Version 1.1: + Caching
  ├─ New: cache/ module
  ├─ Modified: retrieval_engine (1 line: check cache)
  └─ Behavior: Transparent speedup

Version 1.2: + Auth
  ├─ New: security/ module
  ├─ Modified: main.py (conditional middleware)
  └─ Behavior: Optional auth, fail-open by default

Version 1.3: + Agents
  ├─ New: agents/ module
  ├─ New: tools/ module
  └─ Behavior: New /agents/run endpoint

Version 1.4: + Streaming
  ├─ New: api/stream_* modules
  ├─ New: /stream/search endpoint
  └─ Behavior: SSE instead of full response

Version 1.5: + Evaluation
  ├─ New: evals/ module
  └─ Behavior: New /evals/metrics endpoint
```

Each version adds features without modifying core logic.

---

## Next Steps

Continue to [05_RUNTIME_FLOWS.md](05_RUNTIME_FLOWS.md) to trace specific operations through the system.
