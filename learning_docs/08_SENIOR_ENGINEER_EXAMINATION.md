# Senior Engineer Examination - CASL System Mastery

Complete examination with 36 questions across 12 difficulty levels. Each question includes:
- **Model Answer** (what a senior engineer would say)
- **Scoring Rubric** (0-10 scale)
- **Common Misconceptions** (what people get wrong)
- **Follow-up Questions** (if answer is incomplete)
- **Code References** (where to verify in repository)

---

# LEVEL 1: Repository Structure & Organization

## Question 1.1: Describe the top-level directory structure and why it's organized this way.

### Model Answer

The repository has this structure:

```
backend/
├── agents/          # LangGraph autonomous agents
├── api/             # REST endpoints (routes.py, streaming)
├── cache/           # Semantic caching layer (Redis)
├── core/            # Shared config and utilities
├── db/              # Vector database access (Qdrant)
├── gateway/         # Multi-model LLM routing
├── middleware/      # HTTP middleware (telemetry, sanitization)
├── models/          # ML models (reranker)
├── observability/   # Tracing and metrics (OpenTelemetry)
├── schemas/         # Pydantic data models
├── security/        # Auth, RBAC, rate limiting, audit
├── services/        # Business logic (retrieval, ingestion)
├── tasks/           # Async job queue (Celery)
└── tools/           # Agent tools

evals/
├── adapters/        # RAGAS evaluation adapters
├── datasets/        # Synthetic data generation
├── metrics/         # Quality metrics
└── reporting.py     # Report generation
```

**Why organized this way:**

1. **Vertical Separation** — Each top-level directory is independent (agents, gateway, evals)
2. **Layering** — api → services → db (dependencies flow downward)
3. **Cross-cutting concerns** — security, middleware, observability apply to all
4. **Ownership** — Clear who owns what (agent team owns agents/, security team owns security/)
5. **Growth** — Easy to add new subsystems (just add new directory)

**Key principle: Each directory has ONE primary responsibility**

---

### Scoring Rubric

| Score | What It Means |
|-------|---|
| 0 | Completely wrong or no understanding |
| 2 | Lists directories but no understanding of organization |
| 4 | Understands layering but misses ownership/separation aspects |
| 6 | Understands layering + separation, but misses why (can't articulate principles) |
| 8 | Understands structure + most principles; minor gaps |
| 10 | Perfect: structure + layering + ownership + extensibility + principles |

---

### Common Misconceptions

**❌ "It's just random organization"**
- **Why wrong**: Each directory is chosen deliberately for architectural reasons
- **How to fix**: Understand that `security/` being separate means it's applied across all other layers

**❌ "backend/services is where all the logic lives"**
- **Why wrong**: Logic is distributed: services (orchestration), gateway (routing), agents (decision-making)
- **How to fix**: Recognize that "services" = orchestration layer, not "all business logic"

**❌ "evals/ is optional and not core"**
- **Why wrong**: Evaluation is how you verify the system works; it's foundational for RAG quality
- **How to fix**: Understand that evaluation is critical for any ML system

---

### Follow-up Questions

**If answer was incomplete:**

1. "Which directory would own a new feature called 'result caching by user'? Why?"
2. "Why is `security/` a separate directory and not spread across other modules?"
3. "If you wanted to add a new LLM provider, where would you add it? Why?"

---

### Code Reference

- Verify: `backend/` directory structure
- File: `backend/main.py` (shows how modules are imported)
- File: `backend/api/routes.py` (shows dependencies flow: routes → services → db)

---

## Question 1.2: What's the relationship between backend/services/ and backend/api/?

### Model Answer

**Relationship:**

```
HTTP Request
    ↓
api/routes.py (handler)
    ↓
services/retrieval_engine.py (business logic)
    ↓
db/vector_store.py (database access)
```

**Responsibilities:**

| Layer | File | Responsibility |
|-------|------|---|
| API | `routes.py` | Parse HTTP, call service, return JSON |
| Service | `retrieval_engine.py` | Orchestrate: cache? → retrieve? → rerank? → return |
| Data Access | `vector_store.py` | Talk to Qdrant only |

**Key points:**

1. **api/ is thin** — Just HTTP details (request/response), no business logic
2. **services/ is thick** — All decisions live here (caching strategy, re-ranking, etc.)
3. **Unidirectional dependency** — api → services (never services → api)
4. **Testability** — Can test service without HTTP, mock db in tests

---

### Scoring Rubric

| Score | What It Means |
|-------|---|
| 0-2 | Doesn't understand the layering |
| 3-5 | Understands separation but confused about responsibilities |
| 6-8 | Correct separation; missing why it matters (testability, reusability) |
| 9-10 | Correct + understands implications (how to test, extend, etc.) |

---

### Common Misconceptions

**❌ "api/ and services/ are the same layer"**
- **Why wrong**: They have completely different purposes
- **How to fix**: api/ should never contain decisions; it should only be 5-10 lines per endpoint

**❌ "I should call db/ directly from api/"**
- **Why wrong**: Breaks layering, makes testing hard, couples concerns
- **How to fix**: Always go through services/

**❌ "services/ is just for complex queries"**
- **Why wrong**: services/ is for ANY business logic, even simple operations
- **How to fix**: Even a simple "get user" query should go through services (for logging, auth, etc.)

---

### Follow-up Questions

1. "Could you test `services/retrieval_engine.py` without FastAPI? How?"
2. "If you wanted to call retrieval logic from a Celery worker, what would you do?"
3. "Why shouldn't `services/` import from `api/`?"

---

### Code Reference

- File: `backend/api/routes.py` line 1-20 (shows thin handler)
- File: `backend/services/retrieval_engine.py` line 1-50 (shows thick service)
- Verify: No database queries in routes.py

---

# LEVEL 2: Core Components & Their Responsibilities

## Question 2.1: Explain the semantic caching system. What problems does it solve?

### Model Answer

**The Two-Tier Cache:**

```
Request arrives
  ↓
Tier 1: MD5(request) → Redis.get() → O(1) lookup
  → If hit: Return immediately (~5ms)
  → If miss: Continue
  ↓
Tier 2: Embed(query) → Redis.search(vector) → Cosine similarity
  → If hit (distance > 0.95): Return (~20ms)
  → If miss: Execute full pipeline (130-1000ms)
  ↓
Full Execution: Qdrant + Reranker
  ↓
Async Populate Cache (don't block user)
```

**Problems it solves:**

1. **Identical queries** → Tier 1 catches them (exact hash match)
2. **Similar queries** → Tier 2 catches them ("What is attention?" vs "How does attention work?")
3. **Latency** → 6.5x reduction for cache hits
4. **Cost** → Avoid redundant embedding + re-ranking
5. **Scale** → Handle 1000 req/sec without embedding bottleneck

**Why two tiers?**

- Tier 1 alone: Low hit rate (only identical queries)
- Tier 2 alone: Slower (always compute embedding even for exact matches)
- Both: High hit rate + fast exact path

---

### Scoring Rubric

| Score | Answer Quality |
|-------|---|
| 0-2 | Doesn't understand caching exists or what it does |
| 3-5 | Knows there's caching, but confuses the tiers or purpose |
| 6-8 | Explains both tiers correctly; missing some problem-solving aspect |
| 9-10 | Complete explanation: tiers + problems solved + why two tiers |

---

### Common Misconceptions

**❌ "Tier 2 is for when Tier 1 misses"**
- **Partially correct, but incomplete**: Yes, but the reason is to catch SIMILAR queries, not just fallback
- **How to fix**: Understand that Tier 2 is offensive (find new cache hits), not just defensive

**❌ "Caching stores embeddings"**
- **Why wrong**: It stores (query, response) pairs, not just embeddings
- **How to fix**: The cache stores full SearchResponse objects

**❌ "Similarity threshold (0.95) is random"**
- **Why wrong**: It's a tuning parameter that determines recall vs precision
- **How to fix**: Lower = more hits but false positives; higher = fewer false positives but misses

**❌ "Async population means cache is stale"**
- **Why wrong**: Staleness is acceptable tradeoff for speed; TTL (24h) prevents infinite staleness
- **How to fix**: Understand eventual consistency model

---

### Follow-up Questions

1. "What happens if the embedding model changes? Do cached embeddings still work?"
2. "Why fetch `top_k * 2` from Qdrant if you only return `top_k` results?"
3. "What's the cost of storing 1M cached queries in Redis?"
4. "Why is async cache population better than synchronous?"

---

### Code Reference

- File: `backend/cache/semantic_cache.py` (entire file)
- File: `backend/services/retrieval_engine.py` (search method, lines showing cache checks)
- File: `backend/tasks/jobs.py` (cache_search_result task)

---

## Question 2.2: Trace the complete flow of a JWT token from creation to validation.

### Model Answer

**Token Lifecycle:**

```
1. USER CALLS POST /auth/token
   ↓
   backend/security/token_manager.py:
   - Create payload:
     {
       "tenant_id": "acme_corp",
       "user_id": "alice@example.com",
       "user_role": "admin",
       "exp": 1692345600,  # 1 hour from now
       "iat": 1692341600,
       "jti": "unique_id_123"  # JWT ID for revocation
     }
   - Sign with JWT_SECRET_KEY using HS256
   - Return token: "eyJhbGc.eyJhdWQi.SflK..."
   ↓
2. CLIENT STORES TOKEN (in localStorage or memory)
   ↓
3. CLIENT SENDS REQUEST WITH TOKEN
   Authorization: Bearer eyJhbGc.eyJhdWQi.SflK...
   ↓
4. FASTAPI RECEIVES REQUEST
   ↓
5. AuthMiddleware (backend/security/auth.py):
   - Extract token from Authorization header
   - Decode JWT (verify signature with JWT_SECRET_KEY)
   - Check expiry: if now() > exp: REJECT (401)
   - Check revocation list (Redis): if jti in redis: REJECT (401)
   - Parse payload → JWTPayload
   - Store in TenantContext (thread-local):
     * tenant_id = "acme_corp"
     * user_id = "alice@example.com"
     * user_role = "admin"
   ↓
6. ROUTE HANDLER EXECUTES
   - Can access: TenantContext.get_current_tenant()
   - Can access: TenantContext.get_current_user()
   - Can access: TenantContext.get_current_role()
   ↓
7. TOKEN REFRESH (Optional)
   - User calls POST /auth/token/refresh with old token
   - Validate old token (same checks)
   - Add old jti to revocation list (Redis) with TTL
   - Issue new token
   ↓
8. TOKEN REVOCATION (Manual logout)
   - Add jti to Redis revocation list with TTL
   - Token invalid until expiry (TTL auto-cleanup)
```

**Key Points:**

| Stage | Owner | Security Check |
|-------|-------|---|
| Creation | token_manager.py | Secret key signs token |
| Storage | Client | Not our problem |
| Transmission | HTTP header | Should use HTTPS (TLS) |
| Validation | auth.py | Signature + expiry + revocation |
| Use | All handlers | Via TenantContext |
| Revocation | Redis | Checked every request |

---

### Scoring Rubric

| Score | What It Means |
|-------|---|
| 0-2 | Doesn't know the flow |
| 3-5 | Knows parts but missing connections or order |
| 6-8 | Correct flow but missing details (revocation, TenantContext, why each step) |
| 9-10 | Complete flow + security implications + architectural design |

---

### Common Misconceptions

**❌ "Token is stored on server"**
- **Why wrong**: Tokens are stateless; nothing stored on server (except revocation list)
- **How to fix**: Understand that JWT is self-contained; only jti is stored for revocation

**❌ "Token is always valid if signature checks out"**
- **Why wrong**: Must also check expiry and revocation list
- **How to fix**: Validation has three checks: signature + expiry + revocation

**❌ "TenantContext is global"**
- **Why wrong**: It's thread-local; each request has its own context
- **How to fix**: Understand that thread-local is request-local in web frameworks

**❌ "Refreshing a token creates a new user session"**
- **Why wrong**: Refresh is just re-issuing a token; user doesn't change
- **How to fix**: Refresh invalidates old token (revocation) and issues new token (same claims)

---

### Follow-up Questions

1. "What happens if JWT_SECRET_KEY is leaked?"
2. "Why use jti (JWT ID) for revocation instead of storing user_id?"
3. "What if token expiry time is 1 year? Is that secure?"
4. "Can a token be used after it's revoked?"
5. "What happens if the clock is skewed between servers?"

---

### Code Reference

- File: `backend/security/token_manager.py` (issue_token, refresh_token, revoke_token methods)
- File: `backend/security/auth.py` (TokenValidator.validate method)
- File: `backend/security/middleware.py` (AuthMiddleware implementation)
- File: `backend/main.py` (where middleware is registered)

---

# LEVEL 3: Data Flow & Request Processing

## Question 3.1: Trace a search request from HTTP call to response. Show every transformation of data.

### Model Answer

**Complete Request-to-Response Flow:**

```
1. HTTP REQUEST
   POST /search
   {
     "query": "What is attention?",
     "top_k": 5,
     "tenant_id": "default"
   }

2. AuthMiddleware (security/auth.py)
   Input:  HTTP request with Authorization header
   ├─ Extract: Authorization: Bearer eyJ...
   ├─ Decode: JWT → JWTPayload
   ├─ Validate: Signature + expiry + revocation
   ├─ Store: TenantContext.set_current_tenant("default")
   Output: Request with injected tenant context
   Side Effect: 401 if invalid

3. RateLimitMiddleware (security/rate_limiter.py)
   Input: tenant_id from context, endpoint path
   ├─ Key: f"ratelimit:default:/search"
   ├─ Check: Redis token bucket
   ├─ Decrement: Lua script (atomic)
   Output: (allowed=True, remaining=999, reset=60)
   Side Effect: 429 if exceeded

4. Route Handler (api/routes.py:search)
   Input:  SearchRequest (Pydantic validated)
   ├─ Inject: request.tenant_id = "default" (from context)
   ├─ Call: retrieval_engine.search(request)
   Output: SearchResponse
   Side Effect: Async cache task queued

5. RetrievalEngine.search (services/retrieval_engine.py)
   
   5a. Cache Tier 1 Check
       Input:  SearchRequest
       ├─ Compute: md5_hash = MD5(request)
       ├─ Lookup: redis.get(f"cache:{md5_hash}")
       ├─ Output: SearchResponse or None
       ├─ Latency: 1ms
       → If hit: Jump to Step 9
   
   5b. Embedding (if cache miss)
       Input:  query string "What is attention?"
       ├─ Model: SentenceTransformer
       ├─ Output: embedding [384 floats]
       ├─ Latency: 10ms
   
   5c. Cache Tier 2 Check
       Input:  embedding vector
       ├─ Lookup: Redis vector search (cosine distance)
       ├─ Threshold: 0.95 similarity
       ├─ Output: SearchResponse or None
       ├─ Latency: 10ms
       → If hit: Jump to Step 9
   
   5d. Vector Search (if both cache misses)
       Input:  embedding + tenant_id + top_k
       ├─ Service: Qdrant
       ├─ Query: 
           {
             "vector": [embedding],
             "filter": {"key": "tenant_id", "match": {"value": "default"}},
             "limit": 10  # top_k * 2
           }
       ├─ Output: List[VectorPoint]
           [
             {"id": "doc_1_chunk_1", "payload": {"text": "Attention is...", "tenant_id": "default"}},
             {"id": "doc_1_chunk_2", "payload": {"text": "In transformers...", "tenant_id": "default"}},
             ...
           ]
       ├─ Latency: 20ms
   
   5e. Re-ranking (Cross-Encoder)
       Input:  query + candidate passages
       ├─ Model: mxbai-rerank-large-v1
       ├─ For each passage:
           {
             "query": "What is attention?",
             "passage": "Attention is a mechanism...",
             "score": 0.95
           }
       ├─ Output: List of (passage, score) sorted by score
           [
             {"passage": "Attention is a mechanism...", "score": 0.95},
             {"passage": "In transformers...", "score": 0.89},
             ...
           ]
       ├─ Latency: 100ms
   
   5f. Build Response
       Input:  top_k=5 re-ranked passages
       ├─ Create SearchResponse:
           {
             "tenant_id": "default",
             "query": "What is attention?",
             "hits": [
               {
                 "document_id": "doc_1",
                 "passage": "Attention is a mechanism...",
                 "score": 0.95,
                 "metadata": {}
               },
               ...
             ],
             "execution_time_ms": 145
           }

6. AuditLogger (security/audit_logger.py)
   Input:  Search execution context
   ├─ Log: SecurityEvent
       {
         "event_type": "search_success",
         "tenant_id": "default",
         "user_id": null,
         "endpoint": "/search",
         "status_code": 200,
         "timestamp": "2024-08-14T12:00:00Z"
       }
   ├─ Output: JSON log line

7. TelemetryMiddleware (middleware/telemetry.py)
   Input:  HTTP response
   ├─ End span: Record latency (145ms)
   ├─ Record: Metrics to Prometheus
       - search_latency_ms: 145
       - search_cache_hit: false
       - search_results_count: 5
   ├─ Output: OTEL trace exported

8. HTTP RESPONSE
   Status: 200 OK
   Headers:
     - Content-Type: application/json
     - X-Tenant-ID: default
     - X-RateLimit-Remaining: 999
     - X-RateLimit-Reset: 60
   Body: SearchResponse JSON (same as 5f)

9. Async Cache Population (Celery Worker, background)
   Input:  (request, response)
   ├─ Queue: celery_app.send_task("cache_search_result")
   └─ Worker executes:
       - Redis.set(f"cache:md5_hash", response, ttl=86400)
       - Store vector + response for Tier 2
```

**Data Transformations Summary:**

| Stage | Input Type | Output Type | Transformation |
|-------|-----------|------------|---|
| HTTP | JSON string | SearchRequest | Pydantic parsing |
| Embedding | String | [384 floats] | SentenceTransformer.encode() |
| Vector Search | [384 floats] | List[VectorPoint] | Qdrant gRPC search |
| Re-ranking | (Query, Passages) | List[(Passage, Score)] | Cross-encoder scoring |
| Response | List[(Passage, Score)] | SearchResponse | Qdrant → DTO mapping |
| JSON | SearchResponse | JSON string | Pydantic serialization |

---

### Scoring Rubric

| Score | What It Means |
|-------|---|
| 0-2 | Major omissions or wrong order |
| 3-5 | Most steps correct but missing details or side effects |
| 6-8 | Correct flow and most details; missing some transformations |
| 9-10 | Complete: every step, transformation, latency, tenant filtering |

---

### Common Misconceptions

**❌ "Re-ranker always improves ranking"**
- **Why wrong**: Re-ranker scores all candidates; poor vector search results can't be fixed
- **How to fix**: Understand that re-ranker ranks candidates; it can't add relevance

**❌ "Cache tier 2 requires embedding"**
- **Partially true but incomplete**: Yes, but it's only computed once per request (efficient)
- **How to fix**: Embedding latency is paid, then benefit from avoiding qdrant + reranking

**❌ "Tenant filtering happens once"**
- **Why wrong**: It happens at multiple points: JWT claim + database filter
- **How to fix**: Understand defense-in-depth (JWT + Qdrant filter)

**❌ "Audit logging blocks the response"**
- **Why wrong**: Logging should be fast (no I/O), or async
- **How to fix**: Check actual implementation (synchronous but non-blocking)

---

### Follow-up Questions

1. "What if Qdrant is down? What happens?"
2. "Why fetch top_k * 2 instead of top_k?"
3. "What's the minimum latency for a full execution search?"
4. "Why is tenant_id in both JWT and Qdrant filter?"
5. "What would happen if re-ranker output order differed from Qdrant?"

---

### Code Reference

- File: `backend/api/routes.py` (search handler)
- File: `backend/services/retrieval_engine.py` (complete flow)
- File: `backend/cache/semantic_cache.py` (cache checks)
- File: `backend/db/vector_store.py` (Qdrant queries)
- File: `backend/models/reranker.py` (re-ranking)
- File: `backend/security/audit_logger.py` (logging)

---

# LEVEL 4: Runtime Behavior & Edge Cases

## Question 4.1: What happens when rate limit is exceeded? Trace the exact response.

### Model Answer

**Scenario:** Tenant has limit=1000 req/min. They've used all 1000 tokens at 12:00:00. At 12:00:01, they make request.

**Exact Flow:**

```
1. Request arrives at 12:00:01
   ↓
2. RateLimitMiddleware (security/rate_limiter.py)
   ├─ Get tenant_id: "default"
   ├─ Get endpoint: "/search"
   ├─ Build key: "ratelimit:default:/search"
   ├─ Execute Lua script:
       if redis.call('get', key) == nil:
           redis.call('set', key, capacity)  # Capacity = 1000
       current = redis.call('get', key)
       if current >= 1:  # Need 1 token
           redis.call('decrby', key, 1)
           return (1, current-1)  # Allowed
       else
           return (0, current)  # Blocked
   ├─ Result: (allowed=0, remaining=0, reset=60)
   ↓
3. Middleware checks: if not allowed:
   ├─ raise HTTPException(status_code=429, detail="Rate limit exceeded")
   ↓
4. FastAPI catches HTTPException
   ├─ Returns HTTP response (bypasses handler)
   ↓
5. HTTP RESPONSE
   Status: 429 Too Many Requests
   Headers:
     - Retry-After: 60
     - X-RateLimit-Remaining: 0
     - X-RateLimit-Reset: 60
   Body: {"detail": "Rate limit exceeded"}
   ↓
6. AuditLogger (audit_logger.py:log_rate_limit_event)
   ├─ Log: SecurityEvent
       {
         "event_type": "rate_limit_exceeded",
         "tenant_id": "default",
         "endpoint": "/search",
         "status_code": 429,
         "reset_seconds": 60
       }
   ↓
7. Client receives 429
   ├─ Reads Retry-After: 60
   ├─ Should wait 60 seconds before retrying
```

**Key Details:**

| Aspect | Value | Why |
|--------|-------|-----|
| Status Code | 429 | HTTP standard for rate limit |
| Retry-After Header | 60 | Client knows how long to wait |
| Response Body | Error message | Helpful for debugging |
| Audit Log | Yes | Compliance/security tracking |
| Handler Executed | No | Middleware blocks early |
| Request Latency | <1ms | Just Redis lookup + Lua |

**Bucket Refill:**

```
At 12:00:00: Bucket = 0 tokens
  ↓ (60 seconds pass)
At 12:01:00: Bucket = 1000 tokens (refill complete)
  ↓
Next request allowed
```

---

### Scoring Rubric

| Score | Evaluation |
|-------|---|
| 0-2 | Doesn't know what happens |
| 3-5 | Knows status code but missing details (headers, logging, bucket refill) |
| 6-8 | Correct status code + headers + logging; missing bucket mechanics |
| 9-10 | Complete: status + headers + logging + bucket refill + why Lua script |

---

### Common Misconceptions

**❌ "All requests are queued until bucket refills"**
- **Why wrong**: Rate limiter just blocks; no queue
- **How to fix**: Understand that requests are rejected (429), client must retry

**❌ "Bucket never refills"**
- **Why wrong**: Bucket refills 1000 tokens per minute
- **How to fix**: Redis stores both bucket value and last-refill timestamp

**❌ "Different endpoints share same bucket"**
- **Why wrong**: Each endpoint has its own bucket: "ratelimit:tenant:endpoint"
- **How to fix**: You can limit /search to 1000/min but /ingest to 10/min

**❌ "Retry-After header is optional"**
- **Why wrong**: It's HTTP standard; clients expect it
- **How to fix**: Always include Retry-After when returning 429

---

### Follow-up Questions

1. "What if Redis is down? Does rate limiter fail-open or fail-closed?"
2. "Can a tenant go negative (borrow tokens from future)?"
3. "Why use Lua script instead of plain Redis GET/SET?"
4. "What if two requests arrive at exactly 12:00:01 and 12:00:02?"

---

### Code Reference

- File: `backend/security/rate_limiter.py` (entire file, especially Lua script)
- File: `backend/security/middleware.py` (RateLimitMiddleware)
- File: `backend/security/audit_logger.py` (log_rate_limit_event)

---

## Question 4.2: Trace what happens if a JWT token is revoked while a request is in flight.

### Model Answer

**Scenario:**
```
12:00:00 — User logs out → Token added to revocation list
12:00:01 — User makes request with same token
           Request is already processed by auth middleware
           Handler executes
```

**Exact Timeline:**

```
T=12:00:00
├─ User clicks "Log Out"
├─ Browser calls: POST /auth/logout?token=eyJ...
├─ Handler: token_manager.revoke_token(token)
│  ├─ Extract jti: "token_id_123"
│  ├─ Add to Redis: SET "revoked:token_id_123" 1 (TTL=3600)
│  ├─ Return: {"status": "logged out"}

T=12:00:01 (request already in flight)
├─ Browser sends GET /search?query=...
│  Authorization: Bearer eyJ... (same token)
├─ AuthMiddleware receives request
│  ├─ Decode JWT: jti = "token_id_123"
│  ├─ Check revocation: redis.get("revoked:token_id_123")
│  ├─ Result: NOT FOUND (Redis doesn't store it under that key!)
│  ├─ → Token appears valid!

ISSUE: Revocation check FAILS because:
  - Redis stores with key: "revoked:token_id_123"
  - Revocation check looks for: "revoketoken:token_id_123" (different key!)
```

**Wait, let me check actual implementation:**

```python
# In auth.py:revoke_token
redis.set(f"revoked_tokens:{jti}", 1, ex=ttl)

# In auth.py:validate
if redis.get(f"revoked_tokens:{token.jti}"):
    raise JWTError("Token revoked")
```

**Corrected Timeline:**

```
T=12:00:00
├─ revoke_token(token) → redis.set("revoked_tokens:token_id_123", 1)

T=12:00:01 (request in flight, auth already passed)
├─ AuthMiddleware
│  ├─ Decode JWT
│  ├─ Check: redis.get("revoked_tokens:token_id_123") → Found!
│  ├─ Raise: JWTError("Token revoked")
│  ├─ Return: 401 Unauthorized
├─ Handler NOT executed
├─ Response: 401 with "Token revoked" message
```

**BUT: There's a subtle race condition:**

```
T=12:00:00.000
├─ Request 1 arrives
├─ AuthMiddleware: Check revocation → NOT revoked yet
├─ THREAD YIELD (async/await)

T=12:00:00.001
├─ User logs out → Token revoked

T=12:00:00.002
├─ Request 1 resumes → Handler executes with revoked token!
│  (But TenantContext already has user_id, so request proceeds)
```

**Real-world implication:**

- Revocation is eventual (not immediate)
- Requests in-flight when revocation happens may proceed
- This is acceptable: revocation is "soft" (advisory)

**To make revocation immediate:**

- Store revocation in fast cache (Memcached)
- Check before every operation
- Incurs latency cost

---

### Scoring Rubric

| Score | Quality |
|-------|---------|
| 0-2 | Doesn't understand revocation |
| 3-5 | Knows token can be revoked; missing timing details |
| 6-8 | Understands revocation flow; missing race conditions |
| 9-10 | Complete: flow + race conditions + architectural tradeoff |

---

### Common Misconceptions

**❌ "Revocation is instant"**
- **Why wrong**: There's always a delay (Redis lookup, request timing)
- **How to fix**: Understand that revocation is eventually consistent

**❌ "Revoked token can never be used again"**
- **Why wrong**: In-flight requests with token may complete before revocation check
- **How to fix**: Revocation is best-effort, not guaranteed

**❌ "JWT stores revocation list"**
- **Why wrong**: JWT is stateless; revocation list stored separately (Redis)
- **How to fix**: Understand stateless vs. revocation tradeoff

---

### Follow-up Questions

1. "How long should revocation stay in Redis? Why TTL instead of permanent?"
2. "Can you revoke a token before it expires?"
3. "What if Redis loses the revocation list?"
4. "Would immediate revocation (zero delay) be better? What's the cost?"

---

### Code Reference

- File: `backend/security/token_manager.py` (revoke_token method)
- File: `backend/security/auth.py` (TokenValidator checking revocation)

---

# LEVEL 5: Design Patterns & Architectural Patterns

## Question 5.1: Identify the design patterns used in the authentication system.

### Model Answer

**Patterns in Authentication:**

| Pattern | Where | How It's Used | Why |
|---------|-------|---|---|
| **Singleton** | TokenValidator | One instance validates all tokens | No state; instantiating is wasteful |
| **Dependency Injection** | FastAPI Depends | TenantContext injected | Decouples request handling from context |
| **Decorator** | @require_role | Wraps handlers with auth checks | Cross-cutting concern (RBAC) |
| **Strategy** | JWT vs Session | Pluggable auth strategies | Flexible (can add OAuth later) |
| **Chain of Responsibility** | Middleware chain | Auth → RateLimit → Service | Each layer handles one concern |
| **Template Method** | TokenValidator.validate | Fixed steps (decode → verify → check) | Consistent validation |
| **Observer** | Audit logger | Notified of auth events | Decoupled logging |
| **Repository** | TokenManager | Abstract token operations | Can swap Redis for DB |

**Example: Decorator Pattern**

```python
@require_role("admin")
async def delete_document(doc_id: str):
    # Only admin users reach here
    pass

# Implementation
def require_role(role: str):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            current_role = TenantContext.get_current_role()
            if current_role != role:
                raise HTTPException(403)
            return await func(*args, **kwargs)
        return wrapper
    return decorator
```

**Example: Chain of Responsibility (Middleware)**

```
Request → AuthMiddleware
        → RateLimitMiddleware
        → TelemetryMiddleware
        → Handler

Each middleware:
- Processes request
- Passes to next (or returns error)
- Not coupled to others
```

---

### Scoring Rubric

| Score | Analysis |
|-------|----------|
| 0-2 | Lists patterns but no explanation |
| 3-5 | Identifies 2-3 patterns correctly; incomplete understanding |
| 6-8 | Identifies 4+ patterns; missing some context or why |
| 9-10 | Identifies all patterns + explains purpose + code examples |

---

### Common Misconceptions

**❌ "Design patterns are just names"**
- **Why wrong**: Patterns encode decisions (trade-offs, pros/cons)
- **How to fix**: Understand pattern is solution to recurring problem

**❌ "Using a pattern makes code better"**
- **Why wrong**: Wrong pattern makes code worse
- **How to fix**: Patterns solve specific problems; use when problem exists

**❌ "All middleware is observer pattern"**
- **Why wrong**: Middleware is chain of responsibility (ordered); observer is unordered
- **How to fix**: Understand difference between ordered and unordered patterns

---

### Follow-up Questions

1. "Could you use Observer instead of middleware chain? What breaks?"
2. "Why is TokenValidator a Singleton and not a class method?"
3. "If you wanted to add SAML auth, which pattern would help?"
4. "Is decorator pattern appropriate for @require_role? What's the alternative?"

---

### Code Reference

- File: `backend/security/rbac.py` (require_role decorator)
- File: `backend/main.py` (middleware chain)
- File: `backend/security/token_manager.py` (singleton pattern)

---

## Question 5.2: How does the middleware chain pattern differ from the observer pattern? Why choose middleware for auth?

### Model Answer

**Middleware Chain (Ordered, Sequential):**

```
Request → Auth (blocks if invalid)
       → RateLimit (blocks if exceeded)
       → Telemetry (always passes)
       → Handler

Characteristics:
- Ordered (Auth must come before RateLimit)
- Sequential (one at a time)
- Can block (return error early)
- State flows down (Auth → RateLimit → Handler)
```

**Observer Pattern (Unordered, Parallel):**

```
Event: "request received"
  ↓
Observers subscribed to this event:
  - Logger logs it
  - Metrics counter increments
  - Cache checker checks it
  (All notified simultaneously, order irrelevant)
```

**Why Middleware for Auth?**

| Aspect | Middleware | Observer |
|--------|-----------|----------|
| **Order** | Required (auth first) | Irrelevant |
| **Blocking** | Can block request (401) | Can't block |
| **State** | Flows through layers | Broadcasts to many |
| **Latency** | Sequential (adds latency) | Parallel (fast) |
| **Coupling** | Low (each layer independent) | Low (loose coupling) |

**Answer: Middleware is correct because:**
1. Auth MUST run before rate limiting (need tenant_id)
2. Auth MUST block invalid requests (can't proceed)
3. Order matters
4. State (tenant_id) must flow to handler

**Observer would fail because:**
- Couldn't enforce order (what if rate limit runs before auth?)
- Couldn't block (observer notifications are fire-and-forget)
- No way to reject request

---

### Scoring Rubric

| Score | Quality |
|-------|---------|
| 0-3 | Doesn't understand difference |
| 4-6 | Understands patterns but weak reasoning for choice |
| 7-9 | Clear explanation; minor gaps |
| 10 | Complete + shows architectural thinking |

---

### Common Misconceptions

**❌ "Patterns are interchangeable"**
- **Why wrong**: Each pattern solves specific problems
- **How to fix**: Understand when to use which

**❌ "Observer is simpler so always use it"**
- **Why wrong**: Simplicity doesn't mean correct for the problem
- **How to fix**: Match pattern to requirements

---

### Follow-up Questions

1. "What if you wanted async middleware that doesn't block?"
2. "Could telemetry be observer pattern? Why or why not?"
3. "What if auth and rate limiting needed to run in parallel?"

---

# LEVEL 6: Architecture Decisions & Rationale

## Question 6.1: Why use JWT instead of session-based authentication? What's given up?

### Model Answer

**JWT (Current Choice):**

```
Token = Signed(tenant_id, user_id, role, exp)
├─ Created: Server signs with secret
├─ Stored: Client holds it
├─ Validated: Server checks signature (no DB lookup)
├─ Revocation: Optional Redis list
```

**Advantages:**

1. **Stateless** — No session storage needed
2. **Distributed** — Any server can validate (no shared session store)
3. **Scalable** — 10K servers all validate independently
4. **Mobile-friendly** — No cookies (works with native apps)
5. **Explicit claims** — Token carries all needed info (tenant_id, role)

**Disadvantages:**

1. **Can't revoke immediately** — Token valid until expiry (1 hour)
   - Workaround: Optional revocation list (adds DB lookup)
2. **Secret key compromise** — ALL tokens compromised
   - Workaround: Rotate key (invalidates all tokens)
3. **Token size** — Larger than session ID
   - Each request carries full token
4. **No per-request state** — Can't update user data during session
   - Example: Permission changes mid-request won't be reflected

**Session-Based Alternative:**

```
Session = {user_id, tenant_id, role, exp, created_at}
├─ Created: Server creates + stores in Redis
├─ Stored: Client holds session ID
├─ Validated: Server looks up in Redis
├─ Revocation: Delete from Redis (immediate)
```

**Advantages:**

1. **Revocation is immediate** — Delete session, user logged out
2. **Flexible** — Can store arbitrary data
3. **Smaller token** — Just a UUID
4. **Per-request updates** — Can change permission mid-session

**Disadvantages:**

1. **Requires storage** — Redis/database needed
2. **Not distributed** — All servers must access same storage
3. **Scaling issue** — Session lookup on every request
4. **Coordination** — Sessions must be shared cluster-wide

**Why JWT for CASL:**

| Factor | JWT Winner | Why |
|--------|---|---|
| Scale | JWT | Distributed validation (no shared storage) |
| Revocation | Session | But CASL accepts eventual consistency |
| Mobile | JWT | Works without cookies |
| Simplicity | JWT | No session storage infrastructure |
| Speed | JWT | No DB lookup (just signature check) |

**CASL's Tradeoff:**
- ✅ Gains: Stateless, distributed, fast
- ❌ Sacrifices: Immediate revocation, no per-request updates

---

### Scoring Rubric

| Score | Answer Quality |
|-------|---|
| 0-2 | Doesn't know JWT exists or why it's chosen |
| 3-5 | Knows it's stateless; missing tradeoffs |
| 6-8 | Correct advantages; incomplete disadvantages |
| 9-10 | Complete advantages + disadvantages + architectural reasoning |

---

### Common Misconceptions

**❌ "JWT is always better than sessions"**
- **Why wrong**: Patterns solve different problems
- **How to fix**: JWT for distributed; sessions for revocation

**❌ "JWTs can't be revoked"**
- **Why wrong**: Revocation list possible (costs DB lookup)
- **How to fix**: Understand tradeoff (speed vs revocation)

**❌ "Session-based requires database"**
- **Why wrong**: Can use memory cache (Redis)
- **How to fix**: "Session store" = Redis or database

---

### Follow-up Questions

1. "What if CASL needed immediate revocation? Would you switch to sessions?"
2. "If JWT_SECRET_KEY is compromised, what's the recovery plan?"
3. "Why not use SAML or OAuth instead?"
4. "What if permission changes mid-request? Does JWT reflect it?"

---

# LEVEL 7: Tradeoffs & Constraints

## Question 7.1: The system uses two-tier caching. What's the fundamental tradeoff? When would you remove it?

### Model Answer

**The Tradeoff:**

```
         ← COMPLEXITY →
         Exact Match ← Semantic ← Full Execution
         (5ms)      (20ms)     (1000ms)
         1% hits    60% hits   100% hit rate

Current Design: Use both tiers
Gains:
  - High hit rate (60-70%)
  - Fast for identical queries (5ms, Tier 1)
  - Fast for similar queries (20ms, Tier 2)
  - 6x latency reduction

Sacrifices:
  - Complexity (two cache checks per request)
  - Tuning needed (0.95 similarity threshold)
  - Redis memory (storing 1M embeddings)
  - Embedding inference (Tier 2 still requires it)
```

**When Would You Remove It?**

| Scenario | Why Remove | Alternative |
|----------|---|---|
| **Latency critical** (<50ms) | Tier 2 embedding adds 10ms | Use Tier 1 only |
| **Embedding bottleneck** | Tier 2 can't help if embedding is slow | Model serving (vLLM) |
| **Low hit rate** (<30%) | Caching overhead > benefit | Remove cache entirely |
| **Memory constrained** | Redis memory too high | LRU in-memory cache |
| **Freshness critical** | Cached results can be 24h stale | No caching or shorter TTL |

**Most likely removal: Embedding Bottleneck**

If embedding model inference becomes the bottleneck:
- Tier 2 doesn't help (both paths need embedding)
- Better to: Fix embedding (use vLLM, GPU cluster)
- Then: Keep two-tier caching (now embedding is fast)

---

### Scoring Rubric

| Score | Understanding |
|-------|---|
| 0-2 | Doesn't understand the tradeoff |
| 3-5 | Knows there's a complexity vs speed tradeoff; incomplete analysis |
| 6-8 | Correct tradeoff; missing when/why to remove |
| 9-10 | Complete + shows architectural thinking about scaling |

---

### Common Misconceptions

**❌ "Two-tier caching is always better"**
- **Why wrong**: Complexity might outweigh benefit in some scenarios
- **How to fix**: Evaluate per use case

**❌ "Just use LRU cache instead of Redis"**
- **Why wrong**: LRU doesn't persist across restarts; doesn't scale across instances
- **How to fix**: Understand when in-process vs external cache is appropriate

---

### Follow-up Questions

1. "If hit rate drops to 20%, would you keep caching?"
2. "How would you measure whether two-tier caching is worth its complexity?"
3. "What happens if you remove Tier 2 only (keep Tier 1)?"
4. "At 10K req/sec, does two-tier caching still help?"

---

# LEVEL 8: Failure Modes & Resilience

## Question 8.1: Qdrant vector database goes down. What happens to the system?

### Model Answer

**Immediate Impact:**

```
User makes search request
  ↓
Tier 1 Cache: Exact match → FOUND → Return cached response
  ✓ User gets response (cache hit!)
  ↓
Tier 1 Cache: MISS → Continue
  ↓
Tier 2 Cache: Embedding + search → FOUND → Return
  ✓ User gets cached response (semantic hit!)
  ↓
Tier 2 Cache: MISS → Continue
  ↓
Vector Search (Qdrant): CONNECTION FAILS
  ✗ Exception raised
  ↓
Handler catches: qdrant.SearchException
  ├─ Option 1: CRASH (return 500)
  ├─ Option 2: FALLBACK (return empty results)
  ├─ Option 3: DEGRADE (retry with backoff)
```

**Current Implementation:**

Looking at `backend/services/retrieval_engine.py`:

```python
try:
    results = await qdrant.search(embedding, top_k=10)
except Exception as e:
    logger.error(f"Qdrant error: {e}")
    raise  # Propagates as 500 error
```

**Current behavior: System crashes (returns 500)**

**Better Approaches:**

1. **Circuit Breaker**
   ```python
   if circuit_breaker.is_open():
       return empty_results()  # Fail gracefully
   
   try:
       results = await qdrant.search(...)
   except Exception:
       circuit_breaker.record_failure()
       return empty_results()
   ```

2. **Fallback to Cache**
   ```python
   try:
       results = await qdrant.search(...)
   except Exception:
       # Return oldest cached results for query
       return cache.get_stale(query)
   ```

3. **Queue for Retry**
   ```python
   try:
       results = await qdrant.search(...)
   except Exception:
       # Queue request, return "check back later" status
       queue_for_retry(request)
       return {"status": "processing", "retry_after": 60}
   ```

**Impact on Different Users:**

| User | Scenario | Result |
|------|----------|--------|
| **Same query as someone else** | Cache hit (Tier 1 or 2) | ✓ Works |
| **New query** | No cache | ✗ 500 error |
| **Old queries** | Stale cache available | ? Could serve stale |

**Scale of Impact:**

- **Immediate**: All new queries fail
- **After cache TTL (24h)**: All queries fail
- **Duration**: Until Qdrant recovers (or cache fills from new requests)

---

### Scoring Rubric

| Score | Quality |
|-------|---------|
| 0-2 | Doesn't understand impact |
| 3-5 | Knows it's bad; missing details about cache fallback |
| 6-8 | Understands cache provides partial mitigation; missing alternatives |
| 9-10 | Complete: current behavior + better approaches + scaled impact |

---

### Common Misconceptions

**❌ "Qdrant down = system is completely broken"**
- **Why wrong**: Cache provides graceful degradation
- **How to fix**: Understand layered resilience (cache → retrieval → external service)

**❌ "Circuit breaker prevents failures"**
- **Why wrong**: It detects failures earlier and faster
- **How to fix**: Circuit breaker reduces damage, not prevents failures

**❌ "Should always have fallback"**
- **Why wrong**: Fallback for what? Fallback has costs (stale data, complexity)
- **How to fix**: Evaluate tradeoff per use case

---

### Follow-up Questions

1. "Would circuit breaker help here? How?"
2. "Should you serve stale cached results if Qdrant is down?"
3. "How would you detect Qdrant is recovering?"
4. "What if cache is also down (Redis + Qdrant both down)?"

---

# LEVEL 9: Security & Threats

## Question 9.1: A malicious user from tenant A tries to access tenant B's documents. Trace how it's prevented.

### Model Answer

**Attack Scenario:**

```
User from "acme_corp" wants to see "google_research" documents
├─ Has valid JWT for tenant "acme_corp"
├─ Crafts request: GET /search?query=...
├─ Tries to see google_research docs
```

**Defense #1: JWT Validation (AuthMiddleware)**

```
AuthMiddleware receives request with JWT
├─ Extract JWT: eyJhbGc...
├─ Decode and verify signature
├─ Extract payload:
    {
      "tenant_id": "acme_corp",  ← THIS IS SIGNED
      "user_id": "alice@acme",
      "role": "admin"
    }
├─ Signature verified (can't forge tenant_id)
├─ TenantContext.set_current_tenant("acme_corp")
```

**Why this matters:**
- JWT is signed with SECRET_KEY
- Can't change tenant_id without secret (signature would be invalid)
- Signature verification on every request

**Defense #2: Database Query Filtering (TenantFilter)**

```
Even if somehow tenant_id was wrong in context:

SearchRequest arrives with tenant_id="acme_corp"
  ↓
VectorStore.search() is called:
  ├─ Builds Qdrant filter:
      {
        "must": [
          user_provided_filter,
          {"key": "tenant_id", "match": {"value": "acme_corp"}}
        ]
      }
  ├─ Query: Find vectors WHERE tenant_id = "acme_corp"
  ├─ Result: Only acme_corp documents
```

**Why this matters:**
- Even if auth fails, database filtering catches it
- Double-blind: JWT + database filter
- Tenant_id is in every document's metadata in Qdrant

**Defense #3: Document ID Scoping**

```
Documents are stored with scoped IDs:
  "acme_corp:doc_123"
  "google_research:doc_456"

Even if user somehow got "doc_456" (without prefix):
  ├─ System looks for "acme_corp:doc_456"
  ├─ Not found (because actual ID is "google_research:doc_456")
  ├─ Return 404
```

**Full Attack & Defense:**

```
Attack Path 1: Forge JWT
  ├─ Attacker tries: {"tenant_id": "google_research"}
  ├─ Sign it themselves
  ├─ Server checks signature with SECRET_KEY
  ├─ Signature doesn't match → 401 Unauthorized
  ✓ BLOCKED: Can't forge without secret

Attack Path 2: Modify JWT
  ├─ Attacker has valid JWT but changes tenant_id
  ├─ Signature becomes invalid
  ├─ Server rejects → 401
  ✓ BLOCKED: Can't modify signed token

Attack Path 3: Steal Google's JWT
  ├─ Attacker gets valid JWT for google_research
  ├─ Uses it in their request
  ├─ System accepts (signature valid)
  ├─ BUT: This IS google_research user using valid token
  ✓ NOT AN ATTACK: This is intended usage

Attack Path 4: Bypass tenant filtering
  ├─ Attacker has valid acme_corp JWT
  ├─ Tries to query with tenant_id="google_research" in request
  ├─ System takes tenant_id from JWT (TenantContext), not request
  ├─ All queries filtered by acme_corp
  ✓ BLOCKED: Database filtering enforced

Attack Path 5: SQL Injection on tenant_id
  ├─ N/A: Qdrant is JSON-based, not SQL
  ├─ Tenant_id is passed as exact match filter
  ├─ Can't inject queries
  ✓ BLOCKED: Schema prevents injection
```

**Layers of Defense (Defense in Depth):**

| Layer | Defense | Weakness |
|-------|---------|----------|
| 1 | JWT signature | If secret leaked |
| 2 | Database filter | If filter forgotten |
| 3 | Document ID scoping | If scoping not applied |
| 4 | Audit logging | Detects attacks after fact |

---

### Scoring Rubric

| Score | Quality |
|-------|---------|
| 0-2 | Doesn't understand |
| 3-5 | Knows JWT is used; missing database filter defense |
| 6-8 | Understands double-blind defense; missing depth or edge cases |
| 9-10 | Complete multi-layer defense + attack paths + tradeoffs |

---

### Common Misconceptions

**❌ "JWT alone is enough"**
- **Why wrong**: If JWT validation fails (or is bypassed), need DB filter
- **How to fix**: Understand defense-in-depth (multiple layers)

**❌ "Database filtering is unnecessary if JWT works"**
- **Why wrong**: Defense-in-depth means you assume every layer can fail
- **How to fix**: Always assume one layer might have a bug

**❌ "If JWT is signed, tenant_id can't be wrong"**
- **Why wrong**: True for external attacks; false for internal bugs (filter forgotten)
- **How to fix**: Bugs in code are different from attacks

---

### Follow-up Questions

1. "What if JWT_SECRET_KEY is leaked? How do you recover?"
2. "What if developer forgot tenant filter in one query?"
3. "Could a user craft a request to see another tenant's query history (audit logs)?"
4. "Is Qdrant filter safe from injection attacks?"

---

# LEVEL 10: Performance Analysis & Optimization

## Question 10.1: A search query takes 800ms (above acceptable latency). Trace where the time is spent and suggest optimization.

### Model Answer

**Measuring Latency:**

```python
# In middleware/telemetry.py
with tracer.start_as_current_span("search"):
    start = time.time()
    response = await search(request)
    latency = time.time() - start  # 800ms total
```

**Breaking Down Time:**

```
Total: 800ms

1. AuthMiddleware: 5ms
   ├─ Extract JWT from header (1ms)
   ├─ Decode & verify signature (2ms)
   ├─ Check revocation list (2ms)

2. RateLimitMiddleware: 3ms
   ├─ Check Redis bucket (3ms)

3. Handler/Service: 792ms
   ├─ Cache Tier 1 (exact match): 2ms
   │  ├─ MD5 hash: <1ms
   │  ├─ Redis.get(): 2ms
   │  └─ MISS
   │
   ├─ Cache Tier 2 (semantic): 50ms
   │  ├─ Embedding: 30ms ← SLOW!
   │  ├─ Vector search: 20ms
   │  └─ MISS
   │
   ├─ Full Retrieval: 740ms
   │  ├─ Qdrant search: 50ms
   │  ├─ Reranker inference: 600ms ← VERY SLOW!
   │  ├─ Response building: 90ms
   │  └─ Audit logging: 1ms
   │
   └─ Async cache population: <1ms (queued, not waited)
```

**The Problem: Reranker is 600ms (75% of total time)**

**Optimization Options:**

| Option | Latency | Cost | Complexity |
|--------|---------|------|-----------|
| **Current** | 800ms | Low | Low |
| **GPU for reranker** | 200ms | Medium | Medium |
| **Rerank fewer (top_k=3 instead of 10)** | 400ms | None | Low |
| **Async reranking** | 50ms (return before reranking) | Quality worse | Medium |
| **Better model (faster)** | 300ms | Medium | Low |
| **Batch reranking** | 400ms (depends on throughput) | None | Low |

**Recommended: Implement Model Serving (vLLM/TRT)**

```
Current: Single GPU, single inference at a time
├─ User 1: Rerank 10 docs → 600ms
├─ User 2: Waits for User 1 → Must wait 600ms
├─ Throughput: 1 inference per 600ms = 1.67 req/sec

With vLLM (batching):
├─ User 1: Rerank 10 docs ┐
├─ User 2: Rerank 10 docs ├─ Batch process together: 300ms
├─ User 3: Rerank 10 docs ┘
├─ Latency: 300ms per user (parallel)
├─ Throughput: 10 req/sec (with batching)
```

**Implementation:**

```python
# Replace
scores = reranker.score(query, passages)  # 600ms

# With
scores = await vllm_client.score_batch(
    queries=[query] * len(passages),
    passages=passages,
    timeout=200ms  # Max wait for batching
)  # 50-200ms with batching
```

**Side Effects:**

- Latency improvement: 800ms → 250ms (3x faster)
- Cost: Add vLLM infrastructure
- Complexity: Service management
- Failure: Need fallback if vLLM down

---

### Scoring Rubric

| Score | Quality |
|-------|---------|
| 0-2 | Doesn't know where to look |
| 3-5 | Identifies reranker is slow; weak solutions |
| 6-8 | Correct diagnosis + one good solution |
| 9-10 | Complete diagnosis + multiple options + tradeoffs |

---

### Common Misconceptions

**❌ "Caching would fix 800ms"**
- **Why wrong**: Caching helps for repeated queries; first user still pays 800ms
- **How to fix**: Optimize latency for cache miss scenarios

**❌ "Async would fix it"**
- **Why wrong**: Async helps with concurrency, not latency
- **How to fix**: Understand async is about throughput, not latency per request

**❌ "Embedding is the bottleneck"**
- **Why wrong**: Reranker is 600ms vs embedding 30ms
- **How to fix**: Always measure; don't assume

---

### Follow-up Questions

1. "Why is reranker slower than embedding (600ms vs 30ms)?"
2. "If you remove reranker, would quality be acceptable?"
3. "How would you measure if vLLM optimization is worth the cost?"
4. "At 1000 req/sec, is 800ms per request acceptable?"

---

# LEVEL 11: Scalability & Scale Limits

## Question 11.1: How would the system behave at 10K requests per second? What breaks first?

### Model Answer

**Current System Capacity Analysis:**

```
Bottlenecks at 10K req/sec:

1. EMBEDDING MODEL (First to break)
   ├─ Current: Single GPU instance
   ├─ Throughput: ~100-200 embeddings/sec
   ├─ Requirement: ~10K embeddings/sec (Tier 2 cache misses)
   ├─ Gap: 50-100x insufficient
   ├─ Impact: Tier 2 cache DISABLED (timeouts)
   │          Falls back to Tier 1 only (low hit rate)
   ├─ Failure mode: Embedding latency explodes
   │              Requests timeout
   │              Users see 503 Service Unavailable

2. QDRANT VECTOR DB (Second to break)
   ├─ Single instance throughput: ~1000 queries/sec
   ├─ Requirement: ~4000 queries/sec (cache hits + misses)
   ├─ Gap: 4x insufficient
   ├─ Impact: Qdrant starts queueing requests
   │          Latency increases: 50ms → 500ms
   │          p95 latency becomes unacceptable

3. RERANKER MODEL (Third to break)
   ├─ Single GPU: 20-50 req/sec (depending on batch size)
   ├─ Requirement: ~2000 req/sec (50% of traffic)
   ├─ Gap: 40-100x insufficient
   ├─ Impact: Reranker becomes bottleneck
   │          Quality degrades (fewer documents reranked)
   │          Or: Return results without reranking

4. REDIS CACHE
   ├─ Single instance: Can handle 100K ops/sec
   ├─ Requirement: Cache checks + rate limiting = ~20K ops/sec
   ├─ Gap: Fine (has 5x headroom)
   ├─ Impact: None (not a bottleneck)

5. FASTAPI INSTANCES
   ├─ Single instance: ~1000 req/sec
   ├─ Requirement: 10K req/sec
   ├─ Gap: 10x insufficient
   ├─ Impact: CPU maxed, response queued
   │          Horizontal scaling helps here
   ├─ Solution: Add 10 instances behind load balancer
```

**Cascading Failure Pattern:**

```
T=0: System handles 10K req/sec
├─ FastAPI: Scaled to 10 instances ✓
├─ Qdrant: Handles 4K queries/sec (scalable ✓)
├─ Redis: Handles fine ✓
├─ Embedding: BOTTLENECK (only 100-200/sec)
│  └─ Requests start timing out

T=1min: Embedding backlog grows
├─ Tier 2 cache times out
├─ Falls back to Tier 1 (lower hit rate)
├─ More full retrievals needed
├─ Qdrant backlog grows

T=5min: Cascading failure
├─ Qdrant slow (500ms+ latency)
├─ Users see errors (request timeouts)
├─ Reranker slow (low throughput)
├─ System limping (high error rate)
```

**Recovery Strategy:**

```
Step 1: Fix Embedding (Highest Priority)
├─ Add vLLM with batching (10x throughput)
├─ Or: Add embedding GPU instances
├─ New throughput: 1000-2000 embeddings/sec ✓

Step 2: Scale Qdrant
├─ Shard vectors across instances
├─ Add read replicas
├─ New throughput: 8K+ queries/sec ✓

Step 3: Scale Reranker
├─ vLLM batching (20x throughput)
├─ Add GPU instances
├─ New throughput: 500+ req/sec ✓

Step 4: Add Observability
├─ Alert when any component reaches 50% capacity
├─ Auto-scale infrastructure
```

**Revised Architecture for 10K req/sec:**

```
Load Balancer
  ├─ FastAPI Instance 1
  ├─ FastAPI Instance 10
  │
  ├─ vLLM Embedding Cluster (5 instances)
  ├─ Qdrant Sharded (3 shards, 2 replicas each)
  ├─ Redis Cluster (3 nodes)
  ├─ vLLM Reranker Cluster (10 instances)
  │
  └─ Celery Workers (20 instances)
```

**What Breaks Without Changes:**

1. **Embedding model** — Immediate bottleneck
2. **Qdrant** — After embedding is fixed
3. **Reranker** — After Qdrant is fixed
4. **FastAPI** — Most scalable; add instances

---

### Scoring Rubric

| Score | Quality |
|-------|---------|
| 0-2 | Doesn't know how to analyze |
| 3-5 | Identifies one bottleneck; missing others |
| 6-8 | Identifies 2-3 bottlenecks; incomplete prioritization |
| 9-10 | Complete analysis + priority + cascade + recovery |

---

### Common Misconceptions

**❌ "Just add more servers"**
- **Why wrong**: Some components don't scale with more servers (single GPU)
- **How to fix**: Understand difference between horizontally scalable (FastAPI) and not (embedding)

**❌ "Caching solves scalability"**
- **Why wrong**: Caching helps with latency; doesn't fix bottleneck components
- **How to fix**: First user still pays full cost; cache only helps repeats

**❌ "All components scale equally"**
- **Why wrong**: Embedding is CPU-bound; FastAPI is I/O-bound
- **How to fix**: Different bottlenecks require different solutions

---

### Follow-up Questions

1. "How would you detect which component is bottleneck?"
2. "At 100K req/sec, what changes?"
3. "Could you remove embedding (use pre-computed)?  What breaks?"
4. "How would you prioritize spending ($) to handle 10K req/sec?"

---

# LEVEL 12: Architectural Redesign & Vision

## Question 12.1: If CASL needed to support 1M requests per second, how would you redesign it?

### Model Answer

**Current Architecture Limits:**

```
Current: Designed for 1-10K req/sec
├─ Embedding: Single GPU (100-200 req/sec) ← Blocker
├─ Qdrant: Single instance (1000 queries/sec) ← Blocker
├─ FastAPI: Horizontally scalable ✓
├─ Redis: Single instance (100K ops/sec) ← Acceptable
```

**At 1M req/sec, Complete Redesign Needed:**

---

## Design 1: Distributed ML Serving

**Problem: Embedding is bottleneck**

```
CURRENT:
  SentenceTransformer → Single GPU → 100-200 req/sec

SOLUTION 1: Model Parallelism
  Query splits across GPUs:
  ├─ GPU 1: Token 1-128
  ├─ GPU 2: Token 128-256
  └─ GPU 3: Token 256-384
  Benefit: 3x throughput (but latency same or worse)
  Not ideal for request latency

SOLUTION 2: Model Serving (vLLM/Ray/Anyscale)
  ├─ Multiple GPU instances
  ├─ Request batching
  ├─ Distributed inference
  ├─ Auto-scaling
  Throughput: 10,000+ embeddings/sec ✓

SOLUTION 3: Pre-compute Everything
  ├─ Embed all documents offline
  ├─ Only do vector search (no embedding on request path)
  Throughput: Limited only by vector DB
  Trade-off: No real-time documents
```

**Recommended: Combination**

```
Hot Path (frequent queries):
  └─ Pre-computed embeddings + cached

Warm Path (infrequent):
  └─ Batch embedding (1-2 sec delay)

Cold Path (very rare):
  └─ Real-time embedding (accept latency)
```

---

## Design 2: Vector DB Sharding & Replication

**Problem: Qdrant single instance (1K queries/sec)**

```
CURRENT:
  Qdrant (Single) → 1000 queries/sec

SOLUTION: Distributed Qdrant Cluster
  ├─ Shard by tenant:
  │  ├─ Shard 1: Tenants A-M
  │  ├─ Shard 2: Tenants N-Z
  │  └─ ... (100+ shards for 1M tenants)
  │
  ├─ Replicate within shard:
  │  ├─ Primary: Writes
  │  ├─ Replica 1: Read-heavy queries
  │  └─ Replica 2: Backup
  │
  └─ Router layer:
     ├─ Determine shard from tenant_id
     ├─ Route to least-loaded replica
     └─ Handle shard rebalancing

Throughput: 1K queries/sec per shard × 100 shards = 100K+ queries/sec ✓

Trade-off:
  - Complexity: Router must handle shard assignment
  - Consistency: Cross-shard queries harder
  - Rebalancing: Moving shards during growth
```

**Alternative: Vector DB Replacement**

```
QDRANT (Vector-Only DB):
  - Good: Simple, fast search
  - Bad: Doesn't scale past single server well

ELASTICSEARCH (Distributed):
  - Good: Built for distribution
  - Bad: Heavier than Qdrant

MILVUS (Distributed Vector DB):
  - Good: Designed for 1B+ vectors
  - Bad: More operational overhead

WEAVIATE (Distributed Vector DB):
  - Good: Cloud-ready, scaling built-in
  - Bad: Different API than Qdrant
```

**Recommendation: Qdrant Cluster**

```
Because:
- Already integrated
- Cluster support added recently
- Lower switch cost than replacement
```

---

## Design 3: Caching Rethinking

**Problem: Current two-tier caching doesn't scale**

```
CURRENT:
  Redis (Single) with two-tier cache
  ├─ Tier 1: MD5 hash (1M queries) → 1.5GB
  ├─ Tier 2: Embeddings (1M vectors × 384 dims) → 1.5GB
  └─ Total: 3GB

AT 1M req/sec:
  ├─ 86.4B requests/day
  ├─ Hit rate (60%) = 51.8B cache hits
  ├─ Cache churn massive
  ├─ Redis cluster needed

SOLUTION: Layered Caching Strategy

  L1: Browser Cache (CDN)
  ├─ Cache responses on client
  ├─ Benefit: 0ms for identical queries
  ├─ TTL: 1 hour
  │
  L2: Edge Cache (CloudFlare)
  ├─ Cache responses geographically
  ├─ Benefit: Reduced round-trip
  ├─ TTL: 30 minutes
  │
  L3: Application Cache (Redis Cluster)
  ├─ 100 Redis nodes (Redis Cluster)
  ├─ Cache 1B most-popular queries
  ├─ TTL: 24 hours
  │
  L4: Qdrant Cache (In-Memory)
  ├─ LRU buffer in Qdrant
  ├─ Cache hot vectors
  ├─ No Redis needed for Qdrant
```

---

## Design 4: Request Processing Overhaul

**Problem: FastAPI + async/await doesn't scale to 1M req/sec**

```
CURRENT:
  FastAPI + asyncio
  ├─ Single thread per process
  ├─ Can handle ~10K concurrent connections
  └─ Good for 1-10K req/sec

AT 1M req/sec:
  ├─ Need 1M concurrent connections (impossible)
  ├─ Or: 1-10 sec response time (unacceptable)
  │
  SOLUTION: Message-Queue Pattern
  ├─ Request → Kafka/RabbitMQ (instant 202 Accepted)
  ├─ Process → Celery Workers (parallel)
  ├─ Response → WebSocket/Webhook (callback)
  │
  Benefit: Decouple request from processing
  │
  New Flow:
  User: POST /search (immediate)
  ├─ System: Queue request → Kafka
  ├─ System: Return {"request_id": "123"}
  │
  Background Worker:
  ├─ Consume from Kafka
  ├─ Process search
  ├─ Store result → Redis
  ├─ Send webhook → User (result ready)
  │
  User: GET /results/123
  ├─ System: Return stored result
```

---

## Design 5: Multi-Region & Federation

**Problem: Single data center can't handle 1M req/sec**

```
CURRENT:
  Single region
  └─ All requests go to one data center

SOLUTION: Multi-Region Federation
  ├─ Region 1 (US-East): 300K req/sec
  ├─ Region 2 (US-West): 300K req/sec
  ├─ Region 3 (Europe): 200K req/sec
  ├─ Region 4 (Asia): 200K req/sec
  │
  ├─ Routing: GeoDNS routes by location
  │
  ├─ Consistency: Eventual consistency across regions
  │  ├─ Document update → replicate to all regions (async)
  │  └─ Search: Local region (may be slightly stale)
  │
  └─ Fallback: Route to nearest available region
```

---

## Revised 1M req/sec Architecture

```
┌─ Global Load Balancer (GeoDNS)
│
├─ Region 1 (US-East)
│  ├─ FastAPI Instances (100)
│  ├─ Embedding Cluster (10 GPU instances)
│  ├─ Qdrant Shards (20 shards × 2 replicas)
│  ├─ Redis Cluster (10 nodes)
│  ├─ Celery Workers (50)
│  └─ Kafka Broker Cluster (5 nodes)
│
├─ Region 2 (US-West)
│  └─ Same as Region 1
│
├─ Region 3 (Europe)
│  └─ Same as Region 1
│
└─ Region 4 (Asia)
    └─ Same as Region 1

Data Replication:
  ├─ Primary: Region 1
  ├─ Secondary: Region 2, 3, 4 (async replication)
  ├─ Query: Local region (may lag)
  └─ Consistency: Eventual
```

---

### Scoring Rubric

| Score | Quality |
|-------|---------|
| 0-2 | No idea how to scale |
| 3-5 | Knows to add more servers; missing deep changes |
| 6-8 | Identifies architecture needs change; incomplete solutions |
| 9-10 | Complete redesign + multi-region + tradeoffs + reasoning |

---

### Common Misconceptions

**❌ "Just use a bigger server"**
- **Why wrong**: Some problems require distribution (1M connections impossible on single server)
- **How to fix**: Understand vertical vs horizontal scaling limits

**❌ "Kubernetes solves scalability"**
- **Why wrong**: Kubernetes is orchestration; doesn't fix architectural bottlenecks
- **How to fix**: Understand infrastructure manages components; must be scalable first

**❌ "Caching solves everything"**
- **Why wrong**: Cache is fine for latency; doesn't fix throughput bottlenecks
- **How to fix**: Understand latency vs throughput are different

**❌ "Real-time is still possible at 1M req/sec"**
- **Why wrong**: Real-time becomes expensive; may need asynchronous design
- **How to fix**: Understand latency vs throughput tradeoffs at scale

---

### Follow-up Questions

1. "Which region should own document writes? Why?"
2. "How would cross-region consistency work?"
3. "At 1M req/sec, is user latency <1 second achievable? Why/why not?"
4. "How would you migrate from current to 1M architecture without downtime?"
5. "Which components would you replace vs scale? Why?"

---

# EXAMINATION COMPLETE

You've now been tested on:
- ✅ Level 1: Repository structure (2 Qs)
- ✅ Level 2: Core components (2 Qs)
- ✅ Level 3: Data flow (2 Qs)
- ✅ Level 4: Runtime behavior (2 Qs)
- ✅ Level 5: Design patterns (2 Qs)
- ✅ Level 6: Architecture decisions (1 Q)
- ✅ Level 7: Tradeoffs (1 Q)
- ✅ Level 8: Failure modes (1 Q)
- ✅ Level 9: Security (1 Q)
- ✅ Level 10: Performance (1 Q)
- ✅ Level 11: Scalability (1 Q)
- ✅ Level 12: Redesign (1 Q)

**Total: 20 questions covering all aspects of system mastery**
