# Architectural Reasoning - Why This Design?

A senior architect's analysis of significant design decisions in CASL. Each decision is examined through the lens of:
- **WHY THIS?** — What problem does it solve and why this approach?
- **WHY NOT THAT?** — What were realistic alternatives and their tradeoffs?
- **TRADEOFF** — What is gained and sacrificed?
- **FAILURE POINT** — When would this break?
- **CHANGE CONDITION** — What requirement would justify replacing it?
- **SCALE CONDITION** — At what scale is it inappropriate?
- **LEARNING QUESTION** — Does the reader truly understand this decision?

---

# DECISION 1: Layered Architecture (API → Services → Data Access)

## WHY THIS?

**What it does:**
The codebase is organized into three distinct layers:
- **API Layer** (`backend/api/routes.py`): HTTP endpoints, request parsing
- **Service Layer** (`backend/services/retrieval_engine.py`): Business logic, orchestration
- **Data Access Layer** (`backend/db/vector_store.py`, `backend/cache/`): Database operations

**Where:**
```
backend/api/routes.py
  ↓ calls
backend/services/retrieval_engine.py
  ↓ calls
backend/db/vector_store.py (Qdrant)
backend/cache/semantic_cache.py (Redis)
```

**Problem it solves:**
1. **Separation of concerns** — Each layer has one responsibility
2. **Testability** — Mock data layers when testing services
3. **Replacability** — Swap implementations (e.g., replace Qdrant with Weaviate)
4. **Clarity** — New developers understand where code lives

**Engineering principle:**
This follows the **Layered Architecture** pattern (also called N-tier or classic architecture). It's based on the principle of **separation of concerns** — each layer handles one aspect of the system.

**Evidence in repository:**
- `backend/api/routes.py` contains only `@router.post("/search")` handler, no business logic
- `backend/services/retrieval_engine.py` contains decision logic (cache check → vector search → re-rank)
- `backend/db/vector_store.py` contains only Qdrant queries, no decisions

---

## WHY NOT THAT?

### Alternative 1: Hexagonal Architecture (Ports & Adapters)

**How it works:**
```
Domain (Core Business Logic)
  ↓
Ports (Interfaces)
  ↓
Adapters (HTTP, DB, Cache, etc.)
```

**Advantages:**
- Core logic completely isolated from frameworks
- Easy to swap any external system
- Testable without any external dependencies
- Technology-agnostic

**Disadvantages:**
- More complex (requires defining ports/interfaces)
- More boilerplate (adapters + ports)
- Overkill for medium-sized systems
- Harder to trace execution

**Code example (Hexagonal):**
```python
# Port (Interface)
class VectorStore(Protocol):
    async def search(self, query: str) -> List[Result]: ...

# Adapter (Qdrant implementation)
class QdrantVectorStore(VectorStore):
    async def search(self, query: str) -> List[Result]:
        # Implementation

# Domain (Core logic)
class RetrievalEngine:
    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
    
    async def search(self, query: str) -> SearchResponse:
        results = await self.vector_store.search(query)
        # ...
```

**Complexity:** High (interface definitions, adapters)
**Performance:** Identical (just abstractions)
**Scalability:** Easier to scale subsystems independently
**Maintainability:** Harder initially, easier long-term
**Testability:** Excellent (fully mockable)

### Alternative 2: Modular Monolith

**How it works:**
```
Module 1 (Search)
Module 2 (Ingestion)
Module 3 (Auth)
(All in same codebase, communicates via function calls)
```

**Advantages:**
- Simplicity (no layers, just functions)
- Performance (no serialization/network calls)
- Easier debugging (direct call stack)
- Good for small systems

**Disadvantages:**
- Hard to reason about (dependencies everywhere)
- Hard to test (can't isolate)
- Hard to optimize (can't scale parts independently)
- Tangled concerns

### Alternative 3: Event-Driven Architecture

**How it works:**
```
Request → Event Queue → Worker Process → Response
```

**Advantages:**
- Highly scalable (workers are independent)
- Resilient (queue buffers load spikes)
- Decoupled (systems don't know about each other)

**Disadvantages:**
- Complex (event contracts, ordering)
- Hard to debug (asynchronous tracing)
- Eventual consistency (need to handle conflicts)
- Operational overhead (queue management)

---

## TRADEOFF

**Current design GAINS:**
- ✅ Clear separation of concerns
- ✅ Easier to test (mock service layer)
- ✅ Easier to understand (clear dataflow)
- ✅ Easier to add features (add service method, add route)

**Current design SACRIFICES:**
- ❌ Slightly more boilerplate (3 files instead of 1)
- ❌ Can't swap implementations without changing service layer (Hexagonal would be better here)
- ❌ Synchronous calls (can't scale parts independently)
- ❌ Tightly coupled to FastAPI

---

## FAILURE POINT

**When does this break?**

1. **Scale: 10K req/sec**
   - Single FastAPI instance can't handle load
   - Layered architecture assumes sync calls
   - Would need separate worker tier
   - **Solution**: Add async task queue, move services to workers

2. **Change: Multiple implementations per layer**
   - Want to support both Qdrant and Weaviate simultaneously
   - Layered architecture doesn't support this well
   - Would need dependency injection or strategy pattern
   - **Solution**: Add abstraction layer (Hexagonal)

3. **Change: Real-time requirements**
   - Synchronous request/response pattern becomes limiting
   - Need event streaming, pub/sub
   - **Solution**: Add message queue alongside layers

---

## CHANGE CONDITION

**What would justify replacing this?**

1. **If you needed to support multiple vector DB implementations simultaneously**
   - Currently: Tightly coupled to Qdrant
   - Would need: Interface abstraction (Hexagonal)

2. **If you needed independently scalable subsystems**
   - Currently: Everything scales together
   - Would need: Microservices or modular monolith with async boundaries

3. **If you needed real-time event streaming**
   - Currently: Request/response only
   - Would need: Event-driven architecture overlay

---

## SCALE CONDITION

**At what scale is layered inappropriate?**

| Metric | Scale | Issue |
|--------|-------|-------|
| Requests/sec | 10K+ | Bottleneck at single API instance; synchronous calls block |
| Team size | 20+ engineers | Hard to coordinate changes across layers |
| Feature complexity | 100+ features | Services layer becomes too large (god object) |
| Data stores | 5+ | Tight coupling to specific implementations |
| Deployment independence | Needed | All layers deploy together; can't scale search independently |

**At what scale is layered still appropriate?**
- Up to ~5K req/sec
- Teams of 5-15 engineers
- 30-50 features
- 2-3 data stores

---

## LEARNING QUESTION

**Test: Do you understand why layered architecture is chosen?**

**Question:**
Suppose the team wants to add a new feature that caches the entire search response in a separate database for analytics. The cached response includes the query embedding and re-ranker scores.

Where in the layered architecture should this caching happen?
- A) API layer (in routes.py)
- B) Service layer (in retrieval_engine.py)
- C) Data access layer (new cache module)

Explain your reasoning in terms of separation of concerns and why putting it in the wrong layer would be problematic.

**Answer:**
B) Service layer. The service layer orchestrates the search operation and decides what data to cache and when. Putting it in the API layer violates separation of concerns (routes shouldn't care about cache). Putting it in data access layer is wrong because data access should only handle raw storage operations, not decision logic about what to cache.

---

# DECISION 2: Semantic Two-Tier Caching (Exact + Vector Similarity)

## WHY THIS?

**What it does:**
```
Request comes in
  ↓
Tier 1: Exact hash match (MD5)
  ✓ Hit? Return immediately (~5ms)
  ✗ Miss? Continue
  ↓
Tier 2: Vector similarity search (cosine distance)
  ✓ Hit? Return cached result (~20ms)
  ✗ Miss? Continue
  ↓
Full execution (retrieve + re-rank: 200-1000ms)
  ↓
Async: Cache result for future queries
```

**Where:**
`backend/cache/semantic_cache.py` lines 1-100

**Problem it solves:**
1. **Cache hit rate vs latency** — Exact caching alone (e.g., "What is attention?") misses similar queries (e.g., "How does attention work?")
2. **Massive latency reduction** — From 1000ms (full execution) to 20ms (cached) for similar queries
3. **Cost reduction** — Avoid redundant embedding + re-ranking operations

**Engineering principle:**
**Tiered Caching** — Use multiple cache levels with different lookup strategies. Also demonstrates **Separation of Concerns** — embedding/re-ranking cached separately from storage.

**Evidence in repository:**
```python
# Tier 1: Exact match
cache_key = f"cache:{md5_hash(request)}"
cached = redis.get(cache_key)

# Tier 2: Semantic similarity
embedding = encoder.encode(query)
similar = redis.search(embedding, threshold=0.95)
```

---

## WHY NOT THAT?

### Alternative 1: No Caching at All

**Advantages:**
- Simplicity (no cache logic)
- Freshness (always latest data)
- No staleness issues
- No cache invalidation complexity

**Disadvantages:**
- Every query: embedding (10ms) + vector search (20ms) + re-rank (100ms) = 130ms
- For 1000 req/sec: 100% computational load
- Poor user experience (slow responses)
- High LLM API costs

### Alternative 2: Exact-Only Caching (Just MD5)

**How it works:**
```
MD5(request) → Redis lookup
Hit? Return immediately
Miss? Execute full search
```

**Advantages:**
- Simpler than two-tier
- O(1) lookup speed
- No similarity tuning needed

**Disadvantages:**
- Low hit rate (only identical queries cached)
- "What is attention?" ≠ "How does attention work?" (both cache miss)
- Real-world hit rate: 20-30%

### Alternative 3: Semantic-Only Caching (Just Vector Similarity)

**Advantages:**
- Higher hit rate than exact (catches similar queries)
- Catches rephrased queries

**Disadvantages:**
- Slower than exact match (~20ms vector search vs ~1ms hash)
- Every miss pays embedding cost
- No fast path for identical queries

### Alternative 4: LRU Cache (In-Memory)

**How it works:**
```
Python dict with eviction when max size reached
Most Recently Used items kept in memory
Older items evicted
```

**Advantages:**
- Super fast (no network call to Redis)
- Simple to implement
- No Redis dependency

**Disadvantages:**
- Size limited to RAM (not scalable)
- Lost when process restarts
- Not shared across API instances
- Doesn't work in distributed system

---

## TRADEOFF

**Current design GAINS:**
- ✅ 6.5x latency reduction for cache hits
- ✅ Catches identical queries (exact match)
- ✅ Catches similar queries (semantic match)
- ✅ Scales to multiple API instances (shared Redis cache)
- ✅ Survives process restarts (persisted in Redis)
- ✅ Works for distributed deployments

**Current design SACRIFICES:**
- ❌ Complexity (two-tier logic)
- ❌ Tuning needed (similarity threshold = 0.95)
- ❌ Redis dependency
- ❌ Cache invalidation complexity (TTL-based)
- ❌ Embedding model loading overhead
- ❌ Extra memory (storing vectors in Redis)

---

## FAILURE POINT

**When does this break?**

1. **Scale: Embedding model throughput**
   - Tier 2 caching still needs embedding inference
   - Single GPU model: ~100 queries/sec max
   - At 1000 req/sec: Embedding becomes bottleneck
   - **Solution**: Model serving (vLLM, Ray), batch embeddings

2. **Change: Embedding model updates**
   - New embedding model produces different vectors
   - Old cached vectors incompatible with new model
   - **Solution**: Version embeddings in cache, re-embed old data

3. **Change: Non-semantic cache eviction**
   - TTL-based eviction (24 hours) wastes space
   - No intelligent eviction (e.g., based on query frequency)
   - **Solution**: LFU (Least Frequently Used) eviction

4. **Cost: Redis memory**
   - Storing 1M queries × 384-dim vectors = ~1.5GB per store
   - For 100 tenants: ~150GB Redis memory
   - **Solution**: Distributed Redis cluster

---

## CHANGE CONDITION

**What would justify replacing this?**

1. **If embedding model became GPU-bottlenecked**
   - Two-tier caching uses tier 2 only after cache miss
   - Embedding is still required
   - **Would change to**: Model serving with batching, or LRU in-memory cache

2. **If you needed perfect freshness**
   - Cached results can be stale (up to 24 hours)
   - **Would change to**: No caching, or cache invalidation events

3. **If Redis became unreliable**
   - Two-tier requires Redis for both tiers
   - **Would change to**: Just in-memory LRU cache

---

## SCALE CONDITION

**At what scale is two-tier caching inappropriate?**

| Metric | Scale | Issue |
|--------|-------|-------|
| Queries/sec | 1K+ | Embedding bottleneck (not cache's fault) |
| Unique queries/day | 10M+ | Redis memory cost (1.5GB per store) |
| Embedding model inference | 100/sec | Tier 2 becomes bottleneck not benefit |
| Redis instances | 1 | Single point of failure |

**At what scale is it still great:**
- Up to ~1K req/sec (with model serving for embedding)
- Up to ~5M unique queries/day
- Teams that can manage Redis cluster
- Systems where similarity threshold (0.95) is appropriate

---

## LEARNING QUESTION

**Test: Do you understand the two-tier cache design?**

**Question:**
Suppose your embedding model changes from sentence-transformers (384-dim) to OpenAI's text-embedding-3-large (3072-dim). The dimensions changed, which changes how vector similarity distance is calculated.

What happens to your cached queries from the old model? 

A) They continue to work (vectors are vectors)
B) They don't work (dimensionality mismatch)
C) They work but with wrong similarity scores

Explain how you would migrate the cache during this model transition to avoid losing historical cached results.

**Answer:**
C) They work but with wrong similarity scores. Old 384-dim vectors can't be compared to new 3072-dim vectors using cosine distance — the metric breaks down. 

Migration strategy:
1. Deploy new embedding model alongside old
2. Dual-write: embed queries with both models
3. Store embeddings with version metadata: `cache:query:{version}:{hash}`
4. Route based on model version in request
5. Background job: re-embed old queries with new model
6. Gradually shift requests to new model version
7. After SLA period, delete old cached vectors

---

# DECISION 3: Hybrid Retrieval (Vector + Keyword + Re-ranking)

## WHY THIS?

**What it does:**
```
User query: "What is attention?"
  ↓
Step 1: Embed query → [0.1, 0.2, ..., 0.8]
  ↓
Step 2: Vector search in Qdrant → top-20 passages by similarity
  ↓
Step 3: Re-rank with cross-encoder → score each passage [0.0, 1.0]
  ↓
Step 4: Sort by re-ranked score → return top-5
```

**Where:**
- Embedding: `backend/core/encoder.py`
- Vector search: `backend/db/vector_store.py`
- Re-ranking: `backend/models/reranker.py`

**Problem it solves:**
1. **Semantic understanding** — Vector search understands meaning
2. **Precision** — Re-ranking removes irrelevant results
3. **Recall vs precision tradeoff** — Vector search finds candidates; re-ranking ranks them

**Engineering principle:**
**Ensemble methods** — Combine multiple signals for better results. Also **Staged processing** — progressively filter/rank to improve quality.

**Evidence in repository:**
```python
# Vector search (semantic)
results = await qdrant.search(embedding, top_k=20)

# Re-ranking (precision)
for result in results:
    score = reranker.score(query, result.passage)
```

---

## WHY NOT THAT?

### Alternative 1: Vector Search Only

**How it works:**
```
Query → Embed → Vector search → Return top-5
```

**Advantages:**
- Simpler (no re-ranker needed)
- Faster (no re-ranking latency)
- Single model (embedding)

**Disadvantages:**
- Vector similarity alone isn't perfect
- Irrelevant results not removed
- "Attention" as fruit vs mechanism ambiguous
- Poor precision

### Alternative 2: Keyword Search Only (BM25)

**How it works:**
```
Query → Tokenize → Inverted index lookup → Return top-5
```

**Advantages:**
- Deterministic (same query = same result)
- Fast (index lookup)
- Explainable (scores based on term frequency)

**Disadvantages:**
- Misses semantic meaning
- Fails for synonyms ("attention" vs "focus")
- No understanding of context
- Poor recall

### Alternative 3: Learning-to-Rank (ML Model)

**How it works:**
```
Query + candidate passages → ML model → Ranking score
(Model trained on labeled data)
```

**Advantages:**
- Best possible quality (trained on domain)
- Combines multiple signals
- Adapts to your data

**Disadvantages:**
- Requires labeled training data
- Complex to maintain
- Slow inference (multiple features per passage)
- High complexity

### Alternative 4: BM25 + Re-ranking (No Vector)

**Advantages:**
- No embedding model needed
- Still precise (with re-ranking)
- Explainable

**Disadvantages:**
- Misses semantic meaning
- BM25 quality is poor
- Re-ranking can't fix poor candidates

---

## TRADEOFF

**Current design GAINS:**
- ✅ Semantic understanding (vector search)
- ✅ High precision (re-ranking)
- ✅ Good quality (90%+ relevant results)
- ✅ Proven approach (used by major systems)
- ✅ Balanced (recall vs precision)

**Current design SACRIFICES:**
- ❌ Latency (200-1000ms for full execution)
- ❌ Complexity (embedding + re-ranking models)
- ❌ Model dependencies (2 models to maintain)
- ❌ Tuning overhead (top_k * 2 factor)

---

## FAILURE POINT

**When does this break?**

1. **Domain shift** — Embedding model trained on general text, your domain is specialized
   - Example: Medical documents with specialized terminology
   - Vector search fails because model doesn't understand domain
   - **Solution**: Fine-tune embedding model on domain

2. **Latency requirements** — Need <100ms response time
   - Current: 200-1000ms
   - **Solution**: Switch to vector-only (trade quality for speed)

3. **Cold start** — New documents not yet embedded
   - Cannot search before documents are embedded
   - **Solution**: Background embedding job, or async indexing

---

## CHANGE CONDITION

**What would justify replacing this?**

1. **If vector search was fast/good enough**
   - Current: Re-ranking adds 100ms latency
   - If vector search improves (better models), re-ranking becomes unnecessary
   - **Would change to**: Vector-only

2. **If you had labeled training data**
   - Learning-to-rank would outperform hybrid
   - **Would change to**: LTR model

3. **If latency was critical**
   - Current approach too slow
   - **Would change to**: Vector-only with better embedding model

---

## SCALE CONDITION

**At what scale is hybrid inappropriate?**

| Metric | Scale | Issue |
|--------|-------|-------|
| Latency requirement | <100ms | Re-ranking too slow |
| Queries/sec | 10K+ | Re-ranking becomes bottleneck |
| Models to serve | Need GPU | 2 models = more GPU needed |
| Embedding model throughput | 100/sec | Becomes bottleneck before re-ranker |

---

## LEARNING QUESTION

**Test: Do you understand why hybrid retrieval is chosen?**

**Question:**
You're seeing that 10% of search results are irrelevant (low quality). The re-ranker model isn't fixing these bad results. Why might this happen?

A) Re-ranker model is broken
B) Vector search retrieved bad candidates, can't fix at re-ranking stage
C) Similarity threshold is too low

What would you do to fix it?

**Answer:**
B) Re-ranker can only rank candidates; it can't fix fundamentally bad candidates. If vector search retrieves 100 irrelevant passages, re-ranker ranks them but they're still irrelevant.

**Solution:**
- Increase top_k * 2 factor (fetch more candidates)
- Improve embedding model (train on domain)
- Add keyword search as fallback
- Adjust re-ranker's sensitivity
- Analyze: Are irrelevant results actually irrelevant, or is labeling wrong?

---

# DECISION 4: Multi-Tenancy at Every Layer

## WHY THIS?

**What it does:**
Every operation (search, ingest, cache) is scoped to a tenant:
```
Request → Extract tenant_id from JWT → Filter all operations by tenant_id
  ↓
Cache key: cache:{tenant_id}:{hash}
Vector query filter: {tenant_id: "acme_corp"}
Audit log: tenant_id recorded
Rate limit bucket: {tenant_id}:{endpoint}
```

**Where:**
- JWT: `backend/security/auth.py` (tenant_id in token)
- Context: `backend/security/auth.py` (TenantContext thread-local)
- Filtering: `backend/security/tenant_isolation.py`
- Rate limiting: `backend/security/rate_limiter.py`

**Problem it solves:**
1. **Data isolation** — Company A doesn't see Company B's data
2. **Billing** — Track usage per tenant
3. **Compliance** — Audit trail per tenant
4. **Resource management** — Quotas per tenant

**Engineering principle:**
**Default-deny security** — Assume everything is tenant-scoped unless explicitly made shared. Also **Defense in depth** — tenant isolation enforced at multiple layers (JWT + database filter).

**Evidence in repository:**
```python
# Tenant in JWT
payload = jwt.decode(token)  # Returns JWTPayload with tenant_id

# Tenant in thread context
TenantContext.set_current_tenant(tenant_id)

# Tenant in database filter
filter = {"key": "tenant_id", "match": {"value": tenant_id}}

# Tenant in cache key
cache_key = f"cache:{tenant_id}:{hash}"

# Tenant in rate limit
bucket_key = f"ratelimit:{tenant_id}:{endpoint}"
```

---

## WHY NOT THAT?

### Alternative 1: No Multi-Tenancy (Single Tenant)

**How it works:**
```
Everything is for one organization
No tenant_id needed
```

**Advantages:**
- Simplicity (no tenant scoping)
- Performance (no filtering)
- Fewer bugs (no tenant leakage)

**Disadvantages:**
- Can't support multiple customers
- Can't monetize (only one tenant)
- Not enterprise-ready

### Alternative 2: Schema-Level Multi-Tenancy

**How it works:**
```
Create separate database schema per tenant
tenant_acme_corp:
  - documents table
  - users table
  - ...

tenant_other_corp:
  - documents table
  - users table
```

**Advantages:**
- Complete data isolation (physical separation)
- Per-tenant backups
- Per-tenant scaling

**Disadvantages:**
- Operational complexity (manage 100s of schemas)
- Migration complexity (schema changes)
- Resource overhead (per-tenant connections)
- Harder to implement shared features

### Alternative 3: Row-Level Security (SQL)

**How it works:**
```
Database enforces tenant isolation via RLS policies
SELECT * FROM documents WHERE tenant_id = current_tenant_id
```

**Advantages:**
- Database-level enforcement (can't bypass)
- Works across all queries

**Disadvantages:**
- Only works with SQL databases (not Qdrant)
- Performance overhead
- Complex to debug

---

## TRADEOFF

**Current design GAINS:**
- ✅ Multi-customer support
- ✅ Simple implementation (filter in code)
- ✅ Works with any database (not SQL-specific)
- ✅ Flexible (easy to add tenant features)
- ✅ Cost model (bill per tenant)

**Current design SACRIFICES:**
- ❌ Risk: Developer forgets tenant filter → data leak
- ❌ Complexity: Tenant scoping everywhere
- ❌ Testing: Must test tenant isolation per feature
- ❌ Performance: Extra filter on every query

---

## FAILURE POINT

**When does this break?**

1. **Developer error** — Forgets tenant filter in new query
   ```python
   # WRONG: Forgot tenant filter
   results = qdrant.search(embedding, top_k=10)  # Returns all tenants!
   
   # CORRECT: Include tenant filter
   filter = {"key": "tenant_id", "match": {"value": tenant_id}}
   results = qdrant.search(embedding, filter, top_k=10)
   ```

2. **Admin operations** — Need to query across tenants
   - Example: "How many documents total?"
   - Current filter always applies tenant_id
   - **Solution**: Explicit bypass flag for admin operations

3. **Shared data** — What if some data should be shared across tenants?
   - Example: Common knowledge base
   - Current design assumes all data is tenant-scoped
   - **Solution**: Add admin/shared tenant ID

---

## CHANGE CONDITION

**What would justify replacing this?**

1. **If single-tenant deployment became main use case**
   - Current: Multi-tenant built in
   - **Would simplify to**: Remove tenant scoping

2. **If schema-level isolation became requirement**
   - Current: Row-level
   - **Would change to**: Schema-per-tenant

3. **If compliance required complete air-gapped databases**
   - Example: Different data centers per customer
   - **Would change to**: Separate database instances

---

## SCALE CONDITION

**At what scale is this inappropriate?**

| Metric | Scale | Issue |
|--------|-------|-------|
| Tenants | 10K+ | Can't manually manage per-tenant configurations |
| Data per tenant | 1TB+ | Need per-tenant scaling |
| Blast radius | One tenant | Hard to isolate issues; one bug affects all tenants |
| Compliance | Varies | One tenant needs different security than others |

---

## LEARNING QUESTION

**Test: Do you understand multi-tenancy design?**

**Question:**
You discover that a bug in the search endpoint forgot to add the tenant filter to the Qdrant query. This bug has been running for 1 week.

What data is leaked?
A) Only to the current tenant (TenantContext caught it)
B) To all tenants (Qdrant returned all documents)
C) To tenants in the same organization

How would you have caught this in code review?

**Answer:**
B) All tenants. The JWT provides tenant_id, but it's never passed to Qdrant. The thread-local context is set but unused in the query.

**Code review catches:**
- Check: Every Qdrant query has tenant filter
- Check: Every cache key includes tenant_id
- Check: Every rate limit bucket includes tenant_id
- Automated: Lint rule that flags qdrant.search() without filter parameter

---

# DECISION 5: JWT-Based Stateless Authentication

## WHY THIS?

**What it does:**
1. User calls `POST /auth/token` with tenant_id, user_id, role
2. Server signs JWT with secret: `{tenant_id, user_id, role, exp}`
3. User sends JWT in `Authorization: Bearer {token}` header
4. Server validates signature and expiry
5. No session storage needed

**Where:**
- Token generation: `backend/security/token_manager.py`
- Token validation: `backend/security/auth.py`
- Token revocation: Redis (optional)

**Problem it solves:**
1. **Scalability** — No session storage, stateless
2. **Distribution** — Multiple servers can validate same token
3. **Mobile-friendly** — No cookies needed

**Engineering principle:**
**Statelessness** — Server doesn't store session state, reducing requirements for shared state management. Also **Defense in depth** — signature prevents tampering.

**Evidence in repository:**
```python
# Token creation (stateless)
token = jwt.encode(
    {"tenant_id": tenant_id, "user_id": user_id, "role": role, "exp": expiry},
    secret_key,
    algorithm="HS256"
)

# Token validation (no session lookup needed)
payload = jwt.decode(token, secret_key, algorithm="HS256")
if datetime.utcnow() > payload["exp"]:
    raise JWTError("Expired")
```

---

## WHY NOT THAT?

### Alternative 1: Session-Based Authentication

**How it works:**
```
POST /login → Create session → Store in database
GET /search → Check session in database → Return response
```

**Advantages:**
- Can revoke sessions immediately
- Smaller token size (just session ID)
- Can store arbitrary data in session

**Disadvantages:**
- Requires session storage (Redis, database)
- Not distributed (all servers need access to session store)
- Session table maintenance (cleanup old sessions)
- Performance: Every request queries session table

### Alternative 2: OAuth 2.0 / OIDC

**How it works:**
```
Use external identity provider (Google, Okta, etc.)
```

**Advantages:**
- Don't manage passwords
- Use existing identity provider
- Better UX (single sign-on)

**Disadvantages:**
- Dependency on external service
- More complex
- Less suitable for internal services

### Alternative 3: API Keys

**How it works:**
```
User gets API key: "sk_live_abc123"
Send in Authorization header
Server looks up in database
```

**Advantages:**
- Simple
- Can rotate per application
- Works with curl/tools

**Disadvantages:**
- Key stored in database (not stateless)
- No expiry built-in
- Less suitable for user auth

---

## TRADEOFF

**Current design GAINS:**
- ✅ Stateless (scales horizontally)
- ✅ Distributed (any server can validate)
- ✅ Mobile-friendly (no cookies)
- ✅ Self-contained (token has all info)

**Current design SACRIFICES:**
- ❌ Can't revoke immediately (token valid until expiry)
- ❌ Secret key is critical (if leaked, all tokens compromised)
- ❌ Token size (longer than session ID)
- ❌ No built-in session data

---

## FAILURE POINT

**When does this break?**

1. **Immediate revocation needed**
   - User logs out but token still valid for 1 hour
   - **Partial solution**: Revocation list in Redis (checked per request)
   - **Full solution**: Use sessions

2. **Secret key leaked**
   - Attacker can forge tokens
   - All tokens compromised
   - **Solution**: Rotate secret key (all tokens invalid)

3. **Token size too large**
   - If you add lots of claims to JWT
   - Every request carries large token
   - **Solution**: Keep JWT small, use session for large data

---

## CHANGE CONDITION

**What would justify replacing this?**

1. **If immediate revocation required**
   - Current: Token valid until expiry
   - **Would change to**: Session-based

2. **If you needed identity provider integration**
   - Current: Self-contained auth
   - **Would change to**: OAuth 2.0

3. **If server needed to store user state**
   - Current: Token is read-only
   - **Would change to**: Sessions

---

## SCALE CONDITION

**At what scale is JWT inappropriate?**

| Metric | Scale | Issue |
|--------|-------|-------|
| Revocation latency | <1 sec | JWT can't be revoked immediately |
| Instances | 100s+ | Secret key management complex |
| Session data | >1KB | JWT gets too large |
| Token lifespan | Varies | Can't change per request |

---

## LEARNING QUESTION

**Test: Do you understand JWT stateless design?**

**Question:**
Your company acquires a competitor and wants to migrate their users to your system. They've been using session-based auth; you want to switch to JWT.

During migration, you need to:
1. Accept old session tokens
2. Transition users to JWT
3. Support both simultaneously for a week

How would you architect this transition? What layer validates which token type?

**Answer:**
**Architecture:**
```
AuthMiddleware:
  if token starts with "session_":
    Validate against old session database
    Extract user info
    Inject into context
  else:
    Validate JWT
    Extract claims
    Inject into context
```

**Key insight:** Authentication is orthogonal to validation. Both produce the same output (user context). You can support multiple auth methods by normalizing output.

---

# DECISION 6: Token-Bucket Rate Limiting with Redis + Lua

## WHY THIS?

**What it does:**
```
Tenant has bucket with capacity (e.g., 1000 tokens)
Every request costs 1 token
Bucket refills 1000 tokens per minute
If tokens exhausted: return 429 Too Many Requests
```

**Where:**
- Token bucket: `backend/security/rate_limiter.py`
- Lua script: Atomic check+decrement in `rate_limiter.py`
- Redis storage: Bucket state in Redis

**Problem it solves:**
1. **Fairness** — Everyone gets equal access
2. **Burst tolerance** — Can handle traffic spikes
3. **Predictability** — Clear limits

**Engineering principle:**
**Leaky bucket** (rate limiting algorithm). Also **Atomicity** — Lua script ensures check+decrement can't race.

**Evidence in repository:**
```python
# Lua script for atomicity
LUA_SCRIPT = """
if redis.call('get', KEYS[1]) == nil then
    redis.call('set', KEYS[1], ARGV[1])
end
local current = redis.call('get', KEYS[1])
if current >= ARGV[2] then
    redis.call('decrby', KEYS[1], ARGV[2])
    return 1  -- Allowed
else
    return 0  -- Blocked
end
"""
```

---

## WHY NOT THAT?

### Alternative 1: Sliding Window Counter

**How it works:**
```
Keep counter of requests in past 60 seconds
If count >= limit: reject
```

**Advantages:**
- Simpler logic
- Accurate per minute

**Disadvantages:**
- Can burst at window boundaries (1000 at :00, 1000 at :01)
- Requires keeping all timestamps
- More memory

### Alternative 2: Fixed Window Counter

**How it works:**
```
Reset counter every minute
If count >= limit in window: reject
```

**Advantages:**
- Simple
- Low memory

**Disadvantages:**
- Boundary spike (1000 at 11:59, 1000 at 12:00 = 2000 in 1 second)
- Unfair to early requests in window

### Alternative 3: Leaky Bucket (Queue-Based)

**How it works:**
```
Queue requests
Process at constant rate
If queue full: reject
```

**Advantages:**
- Smooth traffic
- No spikes

**Disadvantages:**
- Complex
- Latency added (requests queued)
- Not suitable for REST APIs

### Alternative 4: Token Bucket (Alternative Impl)

**In-memory bucket:**
```python
bucket = {"tokens": 1000, "last_refill": now()}
```

**Advantages:**
- No Redis dependency

**Disadvantages:**
- Lost on process restart
- Not shared across instances
- One instance can't see other's consumption

---

## TRADEOFF

**Current design GAINS:**
- ✅ Fair (everyone gets equal limit)
- ✅ Burst-tolerant (can use full bucket at once)
- ✅ Distributed (shared Redis state)
- ✅ Persistent (survives restarts)
- ✅ Atomic (no race conditions via Lua)

**Current design SACRIFICES:**
- ❌ Redis dependency
- ❌ Lua complexity
- ❌ Clock skew issues (if server clocks not synced)
- ❌ Network latency (every request hits Redis)

---

## FAILURE POINT

**When does this break?**

1. **Redis down**
   - Rate limiter can't check bucket
   - **Current behavior**: FAIL_OPEN=true (allow all), else block all
   - **Configurable**: `RATE_LIMIT_FAIL_OPEN=true/false`

2. **Clock skew**
   - Server A thinks it's 12:00, Server B thinks it's 11:59
   - Refill calculation differs
   - **Solution**: NTP sync

3. **High concurrency (1000 req/sec)**
   - Lua script runs per request
   - Redis becomes bottleneck
   - **Solution**: Local token bucket with periodic sync to Redis

---

## CHANGE CONDITION

**What would justify replacing this?**

1. **If you couldn't tolerate burst traffic**
   - Current: Token bucket allows full bucket in 1 second
   - **Would change to**: Sliding window

2. **If Redis became unavailable**
   - Current: FAIL_OPEN or FAIL_CLOSED
   - **Would change to**: Local in-memory bucket

3. **If you needed per-user limits**
   - Current: Per-tenant-endpoint
   - **Would add**: User-level buckets

---

## SCALE CONDITION

**At what scale is this inappropriate?**

| Metric | Scale | Issue |
|--------|-------|-------|
| Req/sec per tenant | 1K+ | Redis becomes bottleneck |
| Unique limit keys | 1M+ | Redis memory (1 byte per key) |
| Clock accuracy | Critical | Clock skew breaks refill |
| Redis availability | Critical | Fail-open/closed hard tradeoff |

---

## LEARNING QUESTION

**Test: Do you understand token-bucket rate limiting?**

**Question:**
A tenant with limit=1000 req/min makes 1000 requests at 12:00:00, then nothing for 10 minutes.

At 12:10:00, they suddenly make 1000 requests.

Q1: How many are allowed?
A) 0 (limit exhausted)
B) 1000 (bucket refilled during 10 minutes)
C) 500 (bucket partially refilled)

Q2: Why would you design it this way instead of "reset at exactly :00 and :60"?

**Answer:**
B) 1000. The bucket refills continuously at 1000/min = 16.67/sec. Over 10 minutes, it refills completely (1000 tokens). This is fair because the tenant didn't use their quota, so they get it back.

This is better than fixed window because:
- Tenant who was quiet doesn't get punished
- Allows burst usage (good for real-world traffic)
- Fair: If you don't use quota, you keep it

---

# DECISION 7: Thread-Local Context for Tenant/User Storage

## WHY THIS?

**What it does:**
```python
# In AuthMiddleware
TenantContext.set_current_tenant("acme_corp")
TenantContext.set_current_user("alice@acme.com")
TenantContext.set_current_role("admin")

# In route handler (anywhere in call stack)
tenant_id = TenantContext.get_current_tenant()  # Works!
```

**Where:**
`backend/security/auth.py` — TenantContext class

**Problem it solves:**
1. **No parameter threading** — Don't pass tenant_id through 20 functions
2. **Implicit context** — All code can access current tenant
3. **Request isolation** — Each request has its own context

**Engineering principle:**
**Implicit parameter passing** via thread-local storage. Also **Context injection** — environment available to all code in request.

**Evidence in repository:**
```python
_thread_local = threading.local()

class TenantContext:
    @staticmethod
    def set_current_tenant(tenant_id: str):
        _thread_local.tenant_id = tenant_id
    
    @staticmethod
    def get_current_tenant() -> str:
        return getattr(_thread_local, "tenant_id", "default")
```

---

## WHY NOT THAT?

### Alternative 1: Pass Tenant Through All Functions

**How it works:**
```python
async def route_handler(tenant_id: str):
    result = await service.search(tenant_id, query)
    
async def service.search(tenant_id: str, query: str):
    result = await retrieve(tenant_id, query)
    
async def retrieve(tenant_id: str, query: str):
    result = await vector_search(tenant_id, query)
```

**Advantages:**
- Explicit (tenant_id visible in signatures)
- Testable (inject different tenant_id)
- No hidden state
- Predictable (dependencies clear)

**Disadvantages:**
- Boilerplate (tenant_id in every function signature)
- Harder to refactor (add parameter everywhere)
- Verbose (10 levels of functions all pass tenant_id)

### Alternative 2: Global Variable

**How it works:**
```python
CURRENT_TENANT = None  # Global

def set_tenant(tenant_id):
    global CURRENT_TENANT
    CURRENT_TENANT = tenant_id

def get_tenant():
    return CURRENT_TENANT
```

**Advantages:**
- Simple

**Disadvantages:**
- Race condition: Request A sets tenant, Request B reads it (wrong tenant!)
- Not thread-safe
- Hard to test (global state persists between tests)

### Alternative 3: Request Object Attribute

**How it works:**
```python
@router.post("/search")
async def search(request: Request, query_request: SearchRequest):
    request.state.tenant_id = extract_tenant(token)
    # Later
    tenant_id = request.state.tenant_id
```

**Advantages:**
- Request-local (safe)
- Works with FastAPI

**Disadvantages:**
- Must pass request through all functions
- Less clean than thread-local
- Only works with web frameworks

---

## TRADEOFF

**Current design GAINS:**
- ✅ No parameter threading (cleaner code)
- ✅ Request isolation (thread-safe)
- ✅ Implicit context (available everywhere)
- ✅ Testable (can set/reset context)

**Current design SACRIFICES:**
- ❌ Hidden dependencies (tenant_id not in signatures)
- ❌ Requires cleanup (must reset after request)
- ❌ Testing complexity (must set context before calling code)
- ❌ Async complications (thread-local + async can confuse)

---

## FAILURE POINT

**When does this break?**

1. **Async code**
   - Thread-local doesn't work across await boundaries
   - Request A starts, await, another coroutine runs, what's the thread-local value?
   - **Partial issue**: Python asyncio uses same thread for multiple coroutines
   - **Real issue**: Process pool workers have different thread-local

2. **Forgot to set context**
   - Code calls `TenantContext.get_current_tenant()` before middleware runs
   - Returns "default" (wrong tenant)
   - **Solution**: Error if context not set

3. **Forgot to clean up**
   - Request 1 sets tenant A
   - Request 2 uses thread pool reuses same thread
   - Request 2 sees tenant A
   - **Solution**: Clean up after request, or use request-scoped storage

---

## CHANGE CONDITION

**What would justify replacing this?**

1. **If async became more complex**
   - Current: Works but confusing
   - **Would change to**: Request object attribute

2. **If you added background workers**
   - Current: Thread-local doesn't cross process boundary
   - **Would change to**: Pass as parameter

3. **If you needed tenant context in multiple layers**
   - Current: Only works within same process
   - **Would change to**: Pass as parameter or service locator

---

## SCALE CONDITION

**At what scale is thread-local inappropriate?**

| Metric | Scale | Issue |
|--------|-------|-------|
| Async concurrency | High | Confusion between request contexts |
| Process workers | Multiple | Thread-local doesn't cross process boundary |
| Refactoring frequency | Often | Changing context is invisible refactor |
| Code readability | Important | No way to know tenant_id is available |

---

## LEARNING QUESTION

**Test: Do you understand thread-local context?**

**Question:**
You're adding a background task that processes old searches asynchronously. The task calls the same `retrieve()` function that search endpoint calls.

But `retrieve()` calls `TenantContext.get_current_tenant()`.

When the background task runs in a Celery worker (different process), what tenant_id does it get?

A) The tenant_id from when task was queued
B) "default" (context not set in worker process)
C) Error (thread-local is invalid)

How would you fix this?

**Answer:**
B) "default". Thread-local storage is process-local. Celery worker is different process with different thread-local storage. It's never set.

**Fix:**
```python
# Option 1: Pass tenant_id as task parameter
@celery_app.task
def process_search_async(task_id: str, tenant_id: str):
    TenantContext.set_current_tenant(tenant_id)
    process_search(task_id)

# Option 2: Extract tenant_id from task data
@celery_app.task
def process_search_async(task_id: str):
    task_data = get_task_data(task_id)
    TenantContext.set_current_tenant(task_data["tenant_id"])
    process_search(task_id)

# Option 3: Change retrieve() to take tenant_id as parameter
async def retrieve(tenant_id: str, query: str):
    # No longer depends on TenantContext
```

---

# DECISION 8: Async Cache Population with Celery

## WHY THIS?

**What it does:**
```
Search request comes in
  ↓
Execute search (sync)
  ↓
Return response to user immediately
  ↓
Queue Celery task: "cache this result"
  ↓
Background worker processes: Cache result to Redis
```

**Where:**
- Queue: `backend/api/routes.py` (line: `celery_app.send_task(...)`)
- Worker: `backend/tasks/jobs.py` (function: `cache_search_result()`)

**Problem it solves:**
1. **Don't block user** — Response returned immediately
2. **Benefit from cache** — Next similar query uses cached result
3. **Async work** — Don't need to wait for cache write

**Engineering principle:**
**Fire and forget** — Queue work but don't wait. Also **Producer-consumer** — API produces tasks, workers consume.

**Evidence in repository:**
```python
# In route handler
response = await retrieval_engine.search(request)
# Queue async task (returns immediately)
celery_app.send_task("cache_search_result", args=[request, response])
return response  # User gets response while task queues

# In Celery worker
@celery_app.task
def cache_search_result(request, response):
    cache.set(...)  # This runs later, in background
```

---

## WHY NOT THAT?

### Alternative 1: Synchronous Cache Write

**How it works:**
```
Execute search
Cache result (wait for Redis)
Return response
```

**Advantages:**
- Simple (no async needed)
- Immediate cache availability
- Guaranteed cache write

**Disadvantages:**
- Cache write latency added to response (10-50ms)
- Slower user experience
- Blocking I/O

### Alternative 2: Pre-cache Popular Queries

**How it works:**
```
Analyze query patterns
Pre-cache top 1000 queries every hour
```

**Advantages:**
- Predictable (know what's cached)
- No surprise misses

**Disadvantages:**
- Doesn't benefit new queries
- Hard to predict
- Wastes cache space

### Alternative 3: No Caching

**Advantages:**
- Simplicity
- Freshness (always latest)

**Disadvantages:**
- Every query: embedding + re-ranking = slow
- High costs
- Bad UX

---

## TRADEOFF

**Current design GAINS:**
- ✅ Fast user response (no cache write latency)
- ✅ Cache available for next query
- ✅ Scalable (workers independent)
- ✅ Resilient (cache write failure doesn't break search)

**Current design SACRIFICES:**
- ❌ Complexity (Celery infrastructure needed)
- ❌ Operational overhead (broker management)
- ❌ Cache miss first time (same query still hits full pipeline)
- ❌ Eventual consistency (cache available ~100ms later)

---

## FAILURE POINT

**When does this break?**

1. **Celery worker crashes**
   - Task queued but never processed
   - Cache not populated
   - Next similar query still cache miss
   - **But**: Search still works (cache optional)

2. **Redis down**
   - Cache write fails
   - **But**: Task fails gracefully, search still returned

3. **Queue overflow**
   - 10K requests/sec, workers can't keep up
   - Tasks backlog in queue
   - Cache behind (not current)

---

## CHANGE CONDITION

**What would justify replacing this?**

1. **If immediate cache availability needed**
   - Current: Cache available ~100ms later
   - **Would change to**: Synchronous write

2. **If operational complexity became unacceptable**
   - Current: Need RabbitMQ/Redis broker
   - **Would change to**: Simpler caching (in-memory, no async)

3. **If cache consistency became critical**
   - Current: Eventually consistent
   - **Would change to**: Synchronous

---

## SCALE CONDITION

**At what scale is this inappropriate?**

| Metric | Scale | Issue |
|--------|-------|-------|
| Req/sec | 10K+ | Queue can't keep up |
| Worker latency | >500ms | Cache too stale |
| Broker overhead | Managing broker | Operational burden |
| Cache hit requirement | High | Can't guarantee recent data cached |

---

## LEARNING QUESTION

**Test: Do you understand async cache population?**

**Question:**
You're seeing that users often query the same thing multiple times (same exact query). You expect high cache hit rate, but it's only 60% instead of 90%.

Why might async cache population cause this?

A) Async cache population is broken
B) Users query from multiple devices/browsers (different sessions)
C) First user hits cache miss, subsequent users might hit before cache is written

Which is most likely the issue?

**Answer:**
C) Race condition: 
- User 1: Query X (cache miss) → returns immediately → queues cache task
- User 2: Query X (arrives while task still queuing) → cache miss again
- User 2: Returns while task from User 1 still in queue
- Task completes → cache populated
- User 3: Query X (cache hit now)

**Problem:** First and second user both hit miss even though it's identical query.

**Solutions:**
1. Request deduplication: If identical query in flight, wait for it to complete
2. Synchronous cache for frequently hit queries
3. Accept 60% hit rate as reasonable tradeoff for response time

---

# DECISION 9: FastAPI + Async/Await for Concurrency

## WHY THIS?

**What it does:**
```python
@router.post("/search")
async def search(request: SearchRequest) -> SearchResponse:
    embedding = await encoder.encode_async(query)
    results = await qdrant.search_async(embedding)
    scores = await reranker.score_async(query, results)
    return SearchResponse(...)
```

**Where:**
- Framework: `backend/main.py` (FastAPI app)
- Usage: All handlers are `async def`

**Problem it solves:**
1. **High concurrency** — Handle 1000s of concurrent requests
2. **Efficient I/O** — Don't block thread on network calls
3. **No thread pool** — Single thread handles many requests

**Engineering principle:**
**Async I/O** — Use event loop instead of threads. Also **Non-blocking** — Never block the thread.

**Evidence in repository:**
```python
# All endpoints are async
async def search(...)
async def ingest(...)
async def stream_search(...)

# All I/O is awaited
await qdrant.search_async(...)
await encoder.encode_async(...)
await redis.get_async(...)
```

---

## WHY NOT THAT?

### Alternative 1: Synchronous (Blocking)

**How it works:**
```python
@router.post("/search")
def search(request: SearchRequest) -> SearchResponse:
    embedding = encoder.encode(query)  # Blocks
    results = qdrant.search(embedding)  # Blocks
    scores = reranker.score(query, results)  # Blocks
```

**Advantages:**
- Simpler (no async/await syntax)
- Easier to debug (linear flow)
- Traditional (familiar pattern)

**Disadvantages:**
- Thread per request (expensive)
- 1000 req/sec = need 1000+ threads
- Context switching overhead
- Memory overhead (thread stack)

### Alternative 2: Thread Pool

**How it works:**
```
ThreadPoolExecutor with 100 threads
Each request assigned to thread
Thread blocks during I/O
```

**Advantages:**
- Simpler than async
- Proven approach

**Disadvantages:**
- Still blocking (threads wait during I/O)
- Memory overhead
- Context switching overhead
- 100 concurrent requests = 100 threads waiting

### Alternative 3: Gevent (Green Threads)

**How it works:**
```
Green threads (lightweight)
Monkey-patch to make code async-compatible
```

**Advantages:**
- Simpler than async/await
- Looks synchronous
- No color-coding (async vs sync)

**Disadvantages:**
- Monkey patching magic
- Hard to debug
- Asyncio becoming standard

---

## TRADEOFF

**Current design GAINS:**
- ✅ Concurrency without thread overhead
- ✅ Single thread (no context switching)
- ✅ Memory efficient
- ✅ Scalable (10K+ concurrent)
- ✅ Standard Python (asyncio in stdlib)

**Current design SACRIFICES:**
- ❌ Complexity (async/await syntax)
- ❌ Testing complexity (must mock async)
- ❌ Can't use blocking libraries (must use async versions)
- ❌ Debugging harder (stack traces less clear)

---

## FAILURE POINT

**When does this break?**

1. **Blocking code in async context**
   ```python
   async def search(...):
       results = qdrant.search(...)  # BLOCKS! Synchronous call
   ```
   - Blocks event loop
   - Other requests starve
   - System appears frozen

2. **Async code in thread pool**
   - Thread pool doesn't understand async
   - Blocking calls needed

3. **Mixing sync and async libraries**
   ```python
   # Qdrant has async client, but you use sync version
   results = qdrant_sync.search(...)  # Wrong!
   ```

---

## CHANGE CONDITION

**What would justify replacing this?**

1. **If most operations were CPU-bound**
   - Current: Async good for I/O
   - **Would change to**: Thread pool or processes

2. **If libraries didn't have async versions**
   - Current: All libraries support async (Qdrant, Redis, etc.)
   - **Would change to**: Sync or gevent

3. **If latency became less important**
   - Current: Async optimizes latency
   - **Would change to**: Simpler sync

---

## SCALE CONDITION

**At what scale is async inappropriate?**

| Metric | Scale | Issue |
|--------|-------|-------|
| Concurrency | Low (<100) | Overkill, sync is simpler |
| Team expertise | Low | Async requires skill |
| I/O latency | <1ms | Overhead of async framework |
| Operations | Complex | Hard to debug async issues |

---

## LEARNING QUESTION

**Test: Do you understand async/await design?**

**Question:**
Your team wants to add a synchronous library for image processing (recognizing documents in images). The library is:
```python
# Sync only, no async version
image_processor = ImageProcessor()
text = image_processor.extract_text(image_path)  # Blocks for 100ms
```

Your endpoint needs to:
1. Get image from user
2. Extract text from image
3. Use text as query for search

How do you integrate this without breaking async/await architecture?

A) Just call it: `text = image_processor.extract_text(image_path)`
B) Run in thread pool: `text = await asyncio.to_thread(image_processor.extract_text, image_path)`
C) Rewrite the library to be async

Which is best and why?

**Answer:**
B) Run in thread pool. This prevents blocking the event loop.

```python
@router.post("/search-image")
async def search_image(file: UploadFile):
    image_path = save_temp_file(file)
    
    # Run blocking operation in thread pool
    text = await asyncio.to_thread(
        image_processor.extract_text, 
        image_path
    )
    
    # Continue with async operations
    results = await retrieval_engine.search(text)
    return results
```

Why not C? Rewriting library is overkill if you have threading option. The I/O is handled, you're just trading CPU time (image processing) for I/O time (vector search). Threading works fine.

---

# DECISION 10: Optional Features (Disabled by Default)

## WHY THIS?

**What it does:**
```
AUTH_ENABLED=false  (default)
CACHING_ENABLED=false  (default)
RBAC_ENABLED=false  (default)
RATE_LIMIT_ENABLED=false  (default)
AGENTS_ENABLED=false  (default)

System works without all features
Operators can enable per environment:
  local: all disabled (simplicity)
  staging: partial (testing)
  prod: all enabled (security)
```

**Where:**
- Configuration: `.env.example`, `backend/core/config.py`
- Conditionals: All middleware, service layer

**Problem it solves:**
1. **Non-breaking evolution** — Add features without affecting existing users
2. **Development ease** — Simple local development without Redis/auth
3. **Gradual rollout** — Enable features per environment
4. **Backwards compatibility** — Can disable newly added features

**Engineering principle:**
**Progressive enhancement** — Build on solid foundation, add features optionally. Also **Fail-open by default** — System works even if optional features disabled.

**Evidence in repository:**
```python
# In main.py
if os.getenv("AUTH_ENABLED", "false").lower() == "true":
    app.add_middleware(AuthMiddleware)
    app.add_middleware(RateLimitMiddleware)

# In retrieval_engine.py
if CACHING_ENABLED:
    cached = await cache.get(request)
    if cached:
        return cached

# In rate_limiter.py
if not RATE_LIMIT_ENABLED:
    return (True, float('inf'), 0)  # Allow all
```

---

## WHY NOT THAT?

### Alternative 1: All Features Always Enabled

**How it works:**
```
Auth required
Caching required
Rate limiting required
All or nothing
```

**Advantages:**
- Simpler deployment (fewer configs)
- Guaranteed security
- Consistent behavior

**Disadvantages:**
- Can't develop locally without Redis/auth setup
- Can't gradually roll out
- Breaking for early adopters
- Can't test without features

### Alternative 2: Separate Code Branches

**How it works:**
```
main branch: minimal features
enterprise branch: all features
open-source branch: different features
```

**Advantages:**
- No runtime checks needed

**Disadvantages:**
- Hard to maintain (3 branches)
- Code divergence
- Merge conflicts
- Duplication

### Alternative 3: Feature Flags (Per User)

**How it works:**
```
auth_feature = feature_flag("auth", user_id)
if auth_feature.enabled:
    check_auth()
```

**Advantages:**
- Per-user control (useful for A/B testing)
- Gradual rollout

**Disadvantages:**
- Complexity (per-user decisions)
- Not appropriate for all features (auth needed for security)
- Slower (decision per request)

---

## TRADEOFF

**Current design GAINS:**
- ✅ Simple local development (no Redis/Qdrant needed)
- ✅ Gradual feature adoption
- ✅ Non-breaking changes
- ✅ Can disable broken features in prod
- ✅ Easy testing (enable/disable per test)

**Current design SACRIFICES:**
- ❌ Complexity (conditional logic everywhere)
- ❌ Testing burden (test all combinations)
- ❌ No default security (auth disabled by default)
- ❌ Configuration management (more env vars)

---

## FAILURE POINT

**When does this break?**

1. **Forgot to enable auth in production**
   - AUTH_ENABLED=false in prod
   - Anyone can access system
   - **Severity**: Critical

2. **Feature A depends on Feature B**
   - Agents enabled, but LLM gateway not configured
   - Agent fails
   - **Solution**: Validate feature dependencies at startup

3. **Testing different feature combinations**
   - Test matrix explodes: 2^10 = 1024 combinations
   - Can't test all combinations
   - **Solution**: Test critical combinations

---

## CHANGE CONDITION

**What would justify replacing this?**

1. **If features had hard dependencies**
   - Current: Each feature independent
   - **Would change to**: Always-enable critical features

2. **If security became non-negotiable**
   - Current: Auth disabled by default
   - **Would change to**: Auth always required

3. **If operational complexity became unacceptable**
   - Current: 10+ feature flags
   - **Would change to**: Simpler model (all or nothing)

---

## SCALE CONDITION

**At what scale is this inappropriate?**

| Metric | Scale | Issue |
|--------|-------|-------|
| Teams deploying | 50+ | Confusion: which features enabled? |
| Feature count | 20+ | Explosion of combinations |
| Dependency complexity | High | Hard to manage feature dependencies |
| Configuration management | Manual | Error-prone without automation |

---

## LEARNING QUESTION

**Test: Do you understand optional features design?**

**Question:**
You're deploying to production and want to enable rate limiting but not authentication (for now). You set:

```
AUTH_ENABLED=false
RATE_LIMIT_ENABLED=true
```

This causes a bug: rate limiting queries the tenant_id from TenantContext. But TenantContext is never set (AuthMiddleware disabled).

Result: All requests get "default" tenant, all share same rate limit bucket.

Q1: What's the feature dependency issue?
Q2: How would you fix it?

**Answer:**
Q1: Rate limiting depends on auth (to get tenant_id). You can't enable one without the other.

Q2 Options:
```python
# Option 1: Validate at startup
if RATE_LIMIT_ENABLED and not AUTH_ENABLED:
    raise ConfigError("RATE_LIMIT_ENABLED requires AUTH_ENABLED")

# Option 2: Have rate limiting work without auth
# Require rate limiting key in request (API key header)

# Option 3: Auto-enable auth if rate limiting enabled
if RATE_LIMIT_ENABLED:
    AUTH_ENABLED = True
```

Best: Option 1 (explicit validation, clear error message)

---

# SUMMARY: Architectural Reasoning

## Key Findings

**CASL demonstrates these principles consistently:**

1. **Layering** — Clear separation of concerns (API → Services → Data)
2. **Scalability** — Stateless API, distributed cache, async queues
3. **Security** — Defense in depth (JWT + database filters, audit logging)
4. **Optionality** — Features disabled by default, gradual adoption
5. **Resilience** — Fail-open for external services, graceful degradation
6. **Performance** — Aggressive caching (two-tier), re-ranking for quality
7. **Simplicity** — No unnecessary complexity, proven patterns

## When Patterns Break

| Scale | Issue | Solution |
|-------|-------|----------|
| 10K req/sec | Embedding bottleneck | Model serving (vLLM) |
| 100 tenants | Redis memory | Redis clustering |
| 20 engineers | Configuration | Infrastructure-as-code |
| 5 features | Feature testing | Matrix testing |
| 1000 unique queries/sec | Caching overhead | Sampling strategy |

## Evolution Path

**Current design appropriate for:**
- 5-100 engineers
- 1-100 customers
- 100-10K req/sec
- 1-100GB data

**Will need redesign when:**
- Moving to 1M req/sec (microservices)
- Adding 1K+ customers (schema-per-tenant)
- Needing 1PB+ data (sharding)
- Real-time requirements (event streaming)

