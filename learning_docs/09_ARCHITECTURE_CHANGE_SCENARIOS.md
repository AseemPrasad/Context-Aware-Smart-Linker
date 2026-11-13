# Architecture Change Scenarios - Reasoning Exercises

This document presents 24 realistic change scenarios ranging from simple (Level 1) to complex (Level 6). Each scenario forces you to reason about the existing CASL architecture and predict impact.

**How to use this:**
1. Read the requirement (solution hidden)
2. Answer the 6 guided questions
3. Write down your answers
4. Then reveal the model solution
5. Compare your solution with model
6. Understand the tradeoffs

---

# LEVEL 1: Small Changes

These scenarios involve adding small features without changing the core architecture. Difficulty: Low.

---

## Scenario 1.1: Add a "Confidence Score" Field to Search Results

**Requirement:**

Users want to know how confident the system is in each result. The search response currently returns:
```json
{
  "hits": [
    {
      "document_id": "doc_1",
      "passage": "...",
      "score": 0.95,
      "metadata": {}
    }
  ]
}
```

New requirement: Add a `confidence_score` field (0.0-1.0) that indicates how confident the system is that this result is correct.

**Constraints:**
- Don't break existing API
- Backward compatibility required (clients should work without the field)
- Must be calculated efficiently (not add latency)

---

### Guided Questions

**Q1: Which files/components would need to change?**

Write down:
- What data models change?
- What API responses change?
- What logic changes?

**Q2: Why those components?**

Explain:
- Why must the data model change?
- Is the middleware affected?
- Is the cache affected?

**Q3: What risks do you foresee?**

Identify:
- Backward compatibility risks
- Performance risks
- Data consistency risks

**Q4: How would you test it?**

Plan:
- Unit tests for confidence calculation
- Integration tests for end-to-end flow
- Backward compatibility tests

**Q5: What architectural tradeoffs?**

Consider:
- Adding complexity to SearchResponse
- Calculating confidence adds latency
- Caching implications (cached responses have confidence, new ones don't)

**Q6: How is confidence_score calculated?**

Reason:
- From re-ranker score? (0.95 score = 0.95 confidence?)
- From additional model?
- From ensemble?

---

### Model Solution

**How to implement:**

1. **Data Model Change** (`backend/schemas/retrieval.py`)
   ```python
   class SearchHit(BaseModel):
       document_id: str
       passage: str
       score: float  # Re-ranker score (0-1)
       confidence_score: float = 0.5  # Default for backward compatibility
       metadata: dict = {}
   ```

2. **Confidence Calculation** (`backend/services/retrieval_engine.py`)
   ```python
   # Use re-ranker score as confidence proxy
   # (Assumption: re-ranker score = confidence in relevance)
   hit.confidence_score = hit.score
   
   # Or: More complex model
   # confidence = model.predict(query, passage, score)
   ```

3. **Cache Update** (`backend/cache/semantic_cache.py`)
   - Cache stores full SearchResponse including confidence
   - No changes needed (already caches the entire response)

4. **Backward Compatibility**
   - `confidence_score` has default value (0.5)
   - Old clients ignore the field
   - New clients use the field

**Testing:**
- Unit: Test confidence calculation logic
- Integration: Verify end-to-end with cache hits/misses
- Backward compat: Verify old API consumers still work

---

### Comparison with Existing Architecture

**What changed:**
- ✅ Small: Only added one field to existing model
- ✅ Contained: No middleware changes
- ✅ No logic changes needed (use existing score)

**What didn't need to change:**
- Middleware (no new security concerns)
- Rate limiting (same endpoint)
- Caching strategy (cache stores full response already)
- Database queries (Qdrant search unchanged)

**Architectural learning:**
This scenario shows that well-designed data models (using Pydantic with defaults) make small feature additions low-risk. The `SearchResponse` structure was extensible by design.

---

## Scenario 1.2: Add Rate Limit Exception for VIP Users

**Requirement:**

Premium customers want their VIP users to have 10x higher rate limits. Current limit for pro tier is 1000 req/min.

New requirement: VIP users should get 10,000 req/min instead.

**Constraints:**
- VIP status stored in user database (external, not in JWT)
- Rate limit check must be <1ms (critical path)
- Must work with Redis clustering

---

### Guided Questions

**Q1: Which components change?**

**Q2: How do you get VIP status without adding latency?**

**Q3: What if user's VIP status changes mid-session?**

**Q4: How do you test rate limiting at 10K req/min?**

**Q5: What race conditions could occur?**

**Q6: Should VIP be in JWT or looked up per request?**

---

### Model Solution

**Approach 1: VIP Status in JWT (Recommended)**

JWT payload:
```json
{
  "tenant_id": "acme_corp",
  "user_id": "alice@acme.com",
  "is_vip": true,  // Added
  "rate_limit_override": 10000  // Added
}
```

Changes:
1. `backend/security/auth.py` - Extract is_vip from JWT
2. `backend/security/rate_limiter.py` - Check is_vip:
   ```python
   if is_vip:
       capacity = context.rate_limit_override  # 10,000
   else:
       capacity = get_tier_limit(tier)  # 1,000
   ```

**Approach 2: Redis Lookup (Alternative)**

```python
# During rate limit check
vip_key = f"vip:{user_id}"
if redis.get(vip_key):
    capacity = 10000
else:
    capacity = 1000
```

**Tradeoff:** Approach 1 (JWT) is faster (no Redis lookup) but requires JWT refresh for VIP status changes. Approach 2 is flexible but adds latency.

**Testing:**
- Unit: Test rate limiter with is_vip=true/false
- Integration: Verify 10K limit enforced correctly
- Edge case: User with 9,999 tokens + 10 requests → 1 rejected

---

## Scenario 1.3: Add Query Logging for Analytics

**Requirement:**

Product wants to understand what users search for. No privacy concerns (only counting, not storing queries).

New requirement: Log every search query to a analytics table with: `{user_id, tenant_id, query, result_count, latency_ms, timestamp}`.

**Constraints:**
- Logging must not block request (must be async)
- Queries contain no PII
- Analytics table grows 1GB/day

---

### Guided Questions

**Q1: Where does the logging happen?**

**Q2: Should it be async? How would you implement?**

**Q3: What about failed searches (errors)?**

**Q4: How do you avoid querying logs and make them available to analytics?**

**Q5: Where is this data stored?**

**Q6: What about compliance (data retention)?**

---

### Model Solution

**Implementation:**

1. **Add to RetrievalEngine** (`backend/services/retrieval_engine.py`)
   ```python
   async def search(request):
       start = time.time()
       results = await retrieve()
       latency = time.time() - start
       
       # Async logging (don't block user)
       celery_app.send_task(
           "log_search_analytics",
           args=[request.tenant_id, request.user_id, request.query, len(results), latency]
       )
       
       return results
   ```

2. **New Celery Task** (`backend/tasks/jobs.py`)
   ```python
   @celery_app.task
   def log_search_analytics(tenant_id, user_id, query, result_count, latency_ms):
       # Write to analytics database or warehouse
       analytics_db.insert({
           "tenant_id": tenant_id,
           "user_id": user_id,
           "query": query,
           "result_count": result_count,
           "latency_ms": latency_ms,
           "timestamp": datetime.utcnow()
       })
   ```

3. **Analytics Storage** (Options)
   - ClickHouse (time-series data warehouse) ← Recommended
   - BigQuery (cloud warehouse)
   - Separate analytics database

**Testing:**
- Unit: Mock Celery task
- Integration: Verify task queued
- End-to-end: Query analytics DB after search

---

## Scenario 1.4: Add a "Similar Queries" Recommendation

**Requirement:**

After search, suggest similar queries user might want to search for.

Example:
```
User searches: "What is attention?"
Response includes:
  "similar_queries": [
    "How does attention work?",
    "Attention mechanism in transformers"
  ]
```

**Constraints:**
- Similar queries fetched from recent searches (within 7 days)
- Max 3 suggestions
- Must add <50ms to response time

---

### Guided Questions

**Q1: Where do you get similar queries from?**

**Q2: How do you find "similar" without computing embeddings again?**

**Q3: What if there are no similar queries?**

**Q4: Should similar_queries be cached?**

**Q5: What privacy concerns?**

**Q6: How would you implement the "find similar" logic?**

---

### Model Solution

**Approach:**

1. **Keep recent searches in cache** (`backend/cache/semantic_cache.py`)
   - When search completes, store query embedding + query text
   - TTL: 7 days
   - Key: `recent_queries:{tenant_id}:*`

2. **Find similar at request time**
   ```python
   # During search processing
   query_embedding = encoder.encode(request.query)
   
   # Find similar embeddings from recent queries
   similar_embeddings = redis.search(query_embedding, threshold=0.8, limit=3)
   similar_queries = [qe.metadata["query_text"] for qe in similar_embeddings]
   ```

3. **Add to response**
   ```python
   class SearchResponse(BaseModel):
       hits: List[SearchHit]
       similar_queries: List[str] = []  # New field
   ```

**Testing:**
- Unit: Mock Redis searches
- Integration: Verify similar_queries populated
- Edge case: Zero similar queries found

---

# LEVEL 2: Feature Changes

These scenarios introduce new business capabilities or user roles. Difficulty: Medium.

---

## Scenario 2.1: Add a "Collections" Feature

**Requirement:**

Users want to organize documents into "collections" (e.g., "ML Papers", "Product Docs", "API Reference"). When searching, users specify which collection(s) to search in.

New API:
```
POST /search
{
  "query": "What is attention?",
  "collections": ["ML Papers", "Product Docs"],  // New
  "top_k": 5
}
```

**Constraints:**
- Collections are tenant-specific
- Documents belong to exactly one collection
- Backward compatible (if no collections specified, search all)

---

### Guided Questions

**Q1: How is collection info stored?**

**Q2: Where in the request flow do you filter by collection?**

**Q3: Does this affect caching strategy?**

**Q4: What new fields are needed in Qdrant?**

**Q5: How do you test collection filtering?**

**Q6: What if a document belongs to multiple collections later?**

---

### Model Solution

**Architecture Changes:**

1. **Data Model** (`backend/schemas/retrieval.py`)
   ```python
   class SearchRequest(BaseModel):
       query: str
       collections: List[str] = []  # New, defaults to all
       top_k: int = 5
   ```

2. **Qdrant Metadata** 
   - Add `collection` field to document metadata during ingestion
   - Example metadata: `{"tenant_id": "acme", "collection": "ML Papers"}`

3. **Qdrant Query Filter** (`backend/services/retrieval_engine.py`)
   ```python
   filter_conditions = [
       {"key": "tenant_id", "match": {"value": tenant_id}},
       {"key": "collection", "match": {"value": collection}} 
       if collections else None
   ]
   filter = {"must": [c for c in filter_conditions if c]}
   
   results = await qdrant.search(embedding, filter=filter, top_k=10)
   ```

4. **Cache Implications**
   - Cache key now includes collections: `cache:{hash(query+collections)}`
   - Tier 2 similarity search also filters by collection

5. **Ingestion Changes** (`backend/services/ingestion.py`)
   - Require collection name during ingestion
   - Store in document metadata

**Testing:**
- Unit: Test filter building logic
- Integration: Search with/without collections
- Edge cases: Search non-existent collection (empty results)

---

## Scenario 2.2: Add Search History & "Search Again" Feature

**Requirement:**

Users want to see their search history and quickly re-run old searches. New endpoints:

```
GET /search/history → Returns last 100 searches for user
GET /search/history/{search_id} → Re-run that search
```

**Constraints:**
- History limited to last 100 searches per user
- Privacy: Users only see their own history
- Re-running a search should benefit from current cache

---

### Guided Questions

**Q1: Where is search history stored?**

**Q2: What data do you save in history (just query, or full response)?**

**Q3: When do you prune old searches?**

**Q4: How do you prevent users from seeing other users' history?**

**Q5: What happens if you re-run a search and results have changed?**

**Q6: How do you generate search_id?**

---

### Model Solution

**Storage:**

1. **Search History Storage** (Redis or Database)
   ```python
   # In Redis:
   # Key: search_history:{user_id}
   # Value: List of {search_id, query, timestamp, result_count}
   # TTL: 30 days
   ```

2. **Implementation** (New task in `backend/tasks/jobs.py`)
   ```python
   @celery_app.task
   def save_search_history(user_id, search_id, query, result_count):
       search_history = {
           "search_id": search_id,
           "query": query,
           "timestamp": datetime.utcnow(),
           "result_count": result_count
       }
       # Prepend to list (most recent first)
       redis.lpush(f"search_history:{user_id}", json.dumps(search_history))
       # Keep only last 100
       redis.ltrim(f"search_history:{user_id}", 0, 99)
   ```

3. **New Endpoints** (`backend/api/routes.py`)
   ```python
   @router.get("/search/history")
   async def get_search_history():
       user_id = TenantContext.get_current_user()
       history = redis.lrange(f"search_history:{user_id}", 0, 99)
       return [json.loads(h) for h in history]
   
   @router.get("/search/history/{search_id}")
   async def replay_search(search_id: str):
       # Lookup original search query
       original_search = redis.get(f"search:{search_id}")
       # Execute current search with that query
       return await search(original_search)
   ```

---

## Scenario 2.3: Add an "Admin" Role with Content Moderation

**Requirement:**

Add new admin role that can:
- Mark documents as "hidden"
- Mark search results as "inappropriate"
- View all user searches (audit)

Current roles: admin, editor, viewer. New role: admin (but expanded capabilities).

**Constraints:**
- Admins shouldn't see hidden documents in search results
- Moderator actions must be audit-logged
- Must work with current JWT-based auth

---

### Guided Questions

**Q1: Should "hidden" be a document property in Qdrant?**

**Q2: How do you prevent hidden docs from appearing in search?**

**Q3: Does moderator action require a separate service?**

**Q4: What data model changes?**

**Q5: How do you test moderation actions?**

**Q6: What if a regular user searches and finds a hidden doc?**

---

### Model Solution

**Changes:**

1. **Qdrant Metadata**
   ```python
   # Add to document metadata during ingestion:
   "is_hidden": false,  // Set to true by admin
   "hidden_by": null,   // Admin user_id
   "hidden_at": null    // Timestamp
   ```

2. **Search Filter** (`backend/services/retrieval_engine.py`)
   ```python
   user_role = TenantContext.get_current_role()
   
   # Admins see all; others don't see hidden
   if user_role != "admin":
       filter_conditions.append(
           {"key": "is_hidden", "match": {"value": false}}
       )
   ```

3. **Moderation Endpoint** (New in `backend/api/routes.py`)
   ```python
   @router.post("/documents/{doc_id}/hide")
   @require_role("admin")
   async def hide_document(doc_id: str):
       # Update Qdrant metadata
       qdrant.update_metadata(doc_id, {
           "is_hidden": true,
           "hidden_by": TenantContext.get_current_user(),
           "hidden_at": datetime.utcnow()
       })
       
       # Audit log
       audit_logger.log_moderation({
           "action": "hide_document",
           "document_id": doc_id,
           "admin_id": TenantContext.get_current_user()
       })
   ```

4. **Cache Invalidation**
   - When document hidden, invalidate cache entries that contained it
   - Challenge: Cache doesn't know which queries returned this doc
   - Solution: Flush document-specific cache entries

---

# LEVEL 3: Infrastructure Changes

These scenarios involve replacing or adding infrastructure components. Difficulty: High.

---

## Scenario 3.1: Replace Redis Cache with Memcached

**Requirement:**

The team wants to use Memcached instead of Redis for caching (due to operational familiarity and different resource requirements).

**Constraints:**
- Memcached has simpler API (no complex data structures)
- No native vector search support (loses Tier 2 cache)
- Significantly cheaper per GB
- Same TTL/expiry capabilities

---

### Guided Questions

**Q1: What caching features would be lost?**

**Q2: How would you implement Tier 2 caching without Redis?**

**Q3: What about rate limiting (currently uses Redis)?**

**Q4: Is this even a good idea? What's the tradeoff?**

**Q5: What's the migration strategy?**

**Q6: How would you test the new cache backend?**

---

### Model Solution

**What breaks:**

1. **Tier 2 Cache** (Vector similarity search)
   - Memcached can't do vector similarity
   - Would need to remove Tier 2, fall back to:
     - In-memory LRU cache (only works for single instance)
     - Remove Tier 2 entirely (use Tier 1 only, lower hit rate)

2. **Rate Limiting**
   - Current uses Lua scripts (Memcached doesn't support)
   - Would need application-level rate limiting (less safe, race conditions possible)

**Recommendation:** DON'T DO IT

Rationale:
- Loss of Tier 2 caching = 60% hit rate → 20% hit rate
- Loss of atomic rate limiting = race conditions
- Cost savings not worth the quality loss

**Alternative:** Keep Redis but optimize it
- Redis Cluster for scaling
- Redis Sentinel for HA
- Still simpler than Memcached migration

---

## Scenario 3.2: Replace Qdrant with Pinecone (Managed Service)

**Requirement:**

Use Pinecone (fully managed vector DB) instead of self-hosted Qdrant to reduce operational burden.

**Constraints:**
- Pinecone is cloud-only (SaaS)
- Different API than Qdrant
- Pricing model per query + storage
- Network latency (cloud call vs local)

---

### Guided Questions

**Q1: What code changes are needed?**

**Q2: How does latency change (local Qdrant → cloud Pinecone)?**

**Q3: What about cost (operational vs. per-query)?**

**Q4: How do you handle metadata filtering (tenant_id, collection)?**

**Q5: What if Pinecone is down?**

**Q6: Is this migration backward compatible?**

---

### Model Solution

**Required Changes:**

1. **Database Abstraction** (`backend/db/vector_store.py`)
   ```python
   # Current: Qdrant-specific
   class VectorStore:
       async def search(self, embedding, filter, top_k):
           return await qdrant_client.search(...)
   
   # New: Abstract interface
   class VectorStore(ABC):
       @abstractmethod
       async def search(self, embedding, filter, top_k): ...
   
   # Implementations
   class QdrantVectorStore(VectorStore): ...
   class PineconeVectorStore(VectorStore): ...
   ```

2. **Pinecone Implementation**
   ```python
   class PineconeVectorStore(VectorStore):
       async def search(self, embedding, filter, top_k):
           # Pinecone API
           results = pinecone_index.query(
               vector=embedding,
               top_k=top_k,
               filter=filter,  # Pinecone has different filter syntax
               include_metadata=True
           )
           return results
   ```

3. **Configuration** (`backend/core/config.py`)
   ```python
   VECTOR_DB_PROVIDER = os.getenv("VECTOR_DB_PROVIDER", "qdrant")
   # qdrant, pinecone, weaviate, etc.
   
   if VECTOR_DB_PROVIDER == "pinecone":
       vector_store = PineconeVectorStore(api_key, index_name)
   else:
       vector_store = QdrantVectorStore(qdrant_url)
   ```

**Tradeoffs:**
- ✅ Gain: No ops burden (Pinecone manages)
- ❌ Loss: Latency (network call vs local)
- ❌ Loss: Data residency (data in Pinecone cloud)
- ❌ Loss: Cost model (per-query pricing scales poorly)

**Recommendation:** Migrate gradually
1. Deploy abstract interface (no change to behavior)
2. Implement Pinecone backend
3. Run parallel (dual-write, Qdrant primary)
4. Switch traffic gradually
5. Monitor latency/cost

---

## Scenario 3.3: Add a Message Queue (Kafka) for Async Processing

**Requirement:**

Current system uses Celery + Redis for task queue. Team wants Kafka for:
- Persistent event log
- Multiple consumers per topic
- Replay capability

Add Kafka alongside Celery (not replacing yet).

**Constraints:**
- Kafka needs operational setup
- Different model than Celery (publish-subscribe vs task queue)
- Must not break existing Celery jobs

---

### Guided Questions

**Q1: What events would you publish to Kafka?**

**Q2: How would Kafka fit alongside Celery?**

**Q3: What topics would you create?**

**Q4: How do you handle event ordering?**

**Q5: What about failure handling (dead letter queue)?**

**Q6: When would you use Kafka vs Celery?**

---

### Model Solution

**Event Topics:**

1. **search.completed**
   ```json
   {
     "search_id": "...",
     "tenant_id": "...",
     "query": "...",
     "result_count": 5,
     "latency_ms": 145,
     "timestamp": "..."
   }
   ```

2. **document.ingested**
3. **token.revoked**
4. **rate_limit.exceeded**

**Implementation:**

```python
# In retrieval_engine.py
def search(...):
    results = ...
    
    # Publish event to Kafka (not Celery)
    kafka_producer.send("search.completed", {
        "search_id": search_id,
        "tenant_id": tenant_id,
        "query": query,
        "result_count": len(results),
        "latency_ms": latency
    })
```

**Consumers:**

1. **Analytics Consumer**
   ```python
   def consume_search_events():
       for event in kafka_consumer.subscribe("search.completed"):
           analytics_db.insert(event)
   ```

2. **Cache Warming Consumer**
   ```python
   def consume_search_events():
       for event in kafka_consumer.subscribe("search.completed"):
           cache.set(event.query, event.results)
   ```

3. **Monitoring Consumer**
   ```python
   def consume_all_events():
       for event in kafka_consumer.subscribe("*"):
           metrics.increment(f"event.{event.type}")
   ```

**Tradeoffs:**
- ✅ Gain: Event replay, multiple consumers
- ✅ Gain: Decoupled services
- ❌ Loss: Added operational complexity
- ❌ Loss: More infrastructure to manage

**When to use:**
- Kafka: For event log, multiple consumers, replay
- Celery: For one-off tasks, retries, scheduling

---

# LEVEL 4: Scale Scenarios

These scenarios force you to think about system behavior at high scale. Difficulty: Very High.

---

## Scenario 4.1: System Must Handle 10x Traffic (10K req/sec)

**Requirement:**

Traffic increases from 1K to 10K req/sec. Current system starts failing.

**Constraints:**
- Latency must stay <500ms p95
- Cost can't increase 10x
- 99.99% uptime required

---

### Guided Questions

**Q1: Which component hits the ceiling first?**

**Q2: What's the cheapest way to add capacity?**

**Q3: Do you need to change the architecture or just scale components?**

**Q4: What about the database (Qdrant)?**

**Q5: What about embeddings (still 100 req/sec max)?**

**Q6: How would you deploy this without downtime?**

---

### Model Solution

**Bottleneck Analysis:**

1. **Embedding Model** (100 req/sec → 10K needed)
   - ❌ Single GPU can't do 10K embeddings/sec
   - Solution: vLLM with batching + GPU cluster

2. **Qdrant** (1K queries/sec → 4K needed)
   - ✅ Can scale with clustering
   - Add read replicas

3. **FastAPI Instances** (1K → 10K)
   - ✅ Stateless, just add more instances
   - Behind load balancer

4. **Redis** (cache + rate limit)
   - ✅ Can scale with clustering
   - 100K ops/sec, plenty of headroom

5. **Reranker** (20 req/sec → 2K needed)
   - ❌ Single GPU bottleneck
   - Solution: vLLM batching

**Architecture Changes:**

```
┌─ Load Balancer
│
├─ FastAPI Instances (10) ← From 1
├─ vLLM Embedding Cluster (10 GPUs) ← From 1
├─ Qdrant Cluster (3 shards, 2 replicas) ← From 1 instance
├─ Redis Cluster (6 nodes) ← From 1 instance
├─ vLLM Reranker Cluster (8 GPUs) ← From 1
└─ Celery Workers (20) ← From 5
```

**Cost:**
- Compute: ↑ 8x (mostly GPU for embedding/reranker)
- Storage: ↑ 1x (Qdrant data doesn't grow 10x)
- Network: ↑ 2x (more inter-service calls)
- Total cost: ~4-5x (not 10x)

---

## Scenario 4.2: Embedding Model Becomes the Bottleneck

**Requirement:**

After fixing infrastructure, embedding inference is 50% of search latency. 10K req/sec → 60% of requests need embedding.

Current: 30ms per embedding (serial)
Needed: 5ms per embedding (for 100ms total search)

**Constraints:**
- Can't change the embedding model (external requirement)
- Budget is limited
- Latency requirement is hard

---

### Guided Questions

**Q1: Is batching enough?**

**Q2: What if you removed Tier 2 caching (no embedding on hit)?**

**Q3: Could you pre-compute embeddings?**

**Q4: What about a cheaper embedding model?**

**Q5: Should searches without cache hits be handled differently?**

**Q6: What's the minimum latency theoretically possible?**

---

### Model Solution

**Options:**

1. **Batching + vLLM**
   - Current: 100 req/sec serial = 30ms per request
   - With batching: 1000 req/sec batch = 1ms per request
   - ✅ Works, cost-effective

2. **Pre-compute Common Queries**
   - Analyze top 10K queries from history
   - Pre-compute embeddings offline
   - Hit rate: 70% (no embedding needed)
   - ✅ Hybrid approach

3. **Cheaper Embedding Model**
   - Current: sentence-transformers (full, 384-dim)
   - Alternative: DistilBERT (50% faster, 2% quality loss)
   - ✅ Quick win, 15ms → 10ms

4. **Accept Cache-Miss Latency**
   - First user of query pays 100ms
   - Subsequent users hit cache (5ms)
   - ✅ Acceptable SLA

**Recommended: Combination**
```
- Use faster embedding model (DistilBERT) → 10ms
- Add batching (vLLM) → Amortized to 2ms
- Pre-compute top 10K queries → 70% cache hit
- Result: Tier 2 cache misses cost ~12ms (acceptable)
```

---

# LEVEL 5: Failure Scenarios

These scenarios involve system failures that you must handle gracefully. Difficulty: Very High.

---

## Scenario 5.1: Qdrant Database Goes Down (15 minute outage)

**Requirement:**

Qdrant is completely unavailable for 15 minutes. What happens? How does the system behave?

**Constraints:**
- Must not crash
- Cache available (Redis is up)
- 50% of traffic needs full search (cache miss)

---

### Guided Questions

**Q1: What's the current behavior? (Does it crash or degrade?)**

**Q2: What could you improve?**

**Q3: How would you serve cache hits during outage?**

**Q4: What about cache misses?**

**Q5: How would monitoring detect Qdrant down?**

**Q6: How long can system operate without Qdrant?**

---

### Model Solution

**Current Behavior:**

```python
# backend/services/retrieval_engine.py
try:
    results = await qdrant.search(embedding, filter, top_k)
except Exception as e:
    logger.error(f"Qdrant error: {e}")
    raise  # Propagates as 500 error
```

**Problem:** Returns 500 for cache misses during Qdrant outage.

**Improved Behavior:**

1. **Circuit Breaker Pattern**
   ```python
   @property
   def circuit_breaker(self):
       if circuit_breaker.is_open():
           # Stop trying Qdrant, return immediately
           return cache.get_stale(query) or empty_results()
   
   try:
       results = await qdrant.search(...)
       circuit_breaker.record_success()
   except Exception:
       circuit_breaker.record_failure()
       if circuit_breaker.is_open():
           # Fast-fail, serve stale cache
           return cache.get_stale(query) or []
   ```

2. **Stale Cache Serving**
   ```python
   # After cache TTL expires, keep results for 24h more
   # Mark as "stale" but still serve during outages
   results = cache.get(query)  # Fresh
   if not results:
       results = cache.get_stale(query)  # 1-7 days old
   if not results:
       results = []  # No results available
   ```

3. **Graceful Degradation Response**
   ```json
   {
     "hits": [...],
     "stale": true,  // New field
     "freshness": "1 day old",
     "message": "Results from cache (database unavailable)"
   }
   ```

**Monitoring:**

```python
# Alert when Qdrant down >1 minute
if circuit_breaker.failure_count > 10:
    alert("Qdrant appears down, serving stale cache")
```

---

## Scenario 5.2: Duplicate Requests (Idempotency Problem)

**Requirement:**

A user loses network connection mid-request and retries. The system processes the same search twice and returns duplicate results.

**Constraints:**
- User sees duplicate results in response
- Search is logged twice (inflating analytics)
- Audit log has duplicates

---

### Guided Questions

**Q1: Is search idempotent? (Should be, it's read-only)**

**Q2: What about side effects (logging, caching)?**

**Q3: How would you detect a duplicate request?**

**Q4: Should you deduplicate at API or service layer?**

**Q5: What about distributed duplicate requests (from different IPs)?**

**Q6: Is this worth fixing? What's the cost?**

---

### Model Solution

**Root Cause:**

Search is idempotent (no side effects on the database). But:
1. Logging (analytics) gets duplicate
2. Caching happens twice
3. Audit log duplicates

**Solution: Deduplicate at API Layer**

```python
# backend/api/routes.py
@router.post("/search")
async def search(request: SearchRequest, x_request_id: str = Header(None)):
    # Client must send unique X-Request-ID header
    if not x_request_id:
        x_request_id = str(uuid.uuid4())
    
    # Check if we've seen this request recently
    cache_key = f"request_dedup:{x_request_id}"
    cached_response = redis.get(cache_key)
    if cached_response:
        return json.loads(cached_response)
    
    # First time seeing this request
    response = await retrieval_engine.search(request)
    
    # Cache response for 60 seconds (dedup window)
    redis.setex(cache_key, 60, json.dumps(response))
    
    return response
```

**Benefits:**
- ✅ Exactly-once semantics
- ✅ Client-driven (client chooses when to retry)
- ✅ Cheap (just Redis lookup)

**Tradeoffs:**
- ❌ Requires clients to send X-Request-ID
- ❌ 60 second dedup window (longer → more memory)
- ❌ Added latency (Redis lookup per request)

**Alternative: Server-Generated IDs**
```python
# Server generates unique ID for each request
request_id = str(uuid.uuid4())
# But can't deduplicate automatic retries (browser, HTTP client)
# Requires application-level dedup (more complex)
```

---

## Scenario 5.3: Network Partition Between Regions

**Requirement:**

You have data in US-East and US-West. Network partition occurs → US-West can't reach US-East.

Which data is which? How do searches work?

**Constraints:**
- Documents ingested in US-East (primary)
- US-West has replicas
- Replicas might be stale (15 minutes behind)

---

### Guided Questions

**Q1: Can US-West serve requests during partition?**

**Q2: What about new documents ingested in US-West?**

**Q3: Should US-West reject requests or serve stale data?**

**Q4: How does consistency work during partition?**

**Q5: What happens when network heals?**

**Q6: Is this a real concern? How common are partitions?**

---

### Model Solution

**Architecture (Before Partition):**

```
US-East (Primary)
  └─ Qdrant: Writes + Reads
  └─ Redis: Primary

US-West (Secondary)
  └─ Qdrant: Read-only replicas (15 min lag)
  └─ Redis: Replicas (5 sec lag)
```

**During Partition:**

```
US-West can:
  ✅ Read from local replicas (15-min stale)
  ✅ Use local Redis cache (5-sec stale)
  ❌ Ingest documents (can't write to primary)
  ❌ Get fresh data (can't reach US-East)
```

**Implementation:**

1. **Detect Partition**
   ```python
   def health_check():
       try:
           response = primary_qdrant.health()
           return True
       except ConnectionError:
           return False
   ```

2. **Degrade Gracefully**
   ```python
   if not primary_qdrant_healthy:
       # Serve from replicas
       results = local_qdrant_replica.search(...)
       return SearchResponse(..., stale=True)
   ```

3. **Reject Ingestion**
   ```python
   @router.post("/ingest")
   async def ingest(request: IngestionRequest):
       if not primary_qdrant_healthy:
           raise HTTPException(503, "Ingestion unavailable (replica mode)")
   ```

4. **On Recovery**
   - Primary comes back
   - Replicas sync fresh data
   - Resume normal operation

**Tradeoff:**
- ✅ Gain: Availability (can serve stale results)
- ❌ Loss: Consistency (15-min stale data)
- ❌ Loss: Write availability (can't ingest)

---

# LEVEL 6: Architectural Redesigns

These scenarios require major architectural changes. Difficulty: Extreme.

---

## Scenario 6.1: Convert from Synchronous to Asynchronous Request Processing

**Requirement:**

Currently: User → Request → Response (sync)

New: User → Request queued → Response immediately (async)

Why? To decouple request processing from response latency.

**Constraints:**
- Response must be available within 5 minutes
- User needs to know when results are ready
- Progressive results (first result in 1 sec, more results as available)

---

### Guided Questions

**Q1: How does client get results if request returns immediately?**

**Q2: What does response contain?**

**Q3: How do you notify user when results ready?**

**Q4: What about multiple consumers (results come from Kafka)?**

**Q5: How do you handle cancellation (user abandons request)?**

**Q6: What components need to change?**

---

### Model Solution

**New Flow:**

```
1. Client: POST /search/async
   {
     "query": "What is attention?",
     "callback_url": "https://client.example.com/callback"
   }

2. Server: Returns immediately (202 Accepted)
   {
     "request_id": "search_123",
     "status_url": "/search/async/search_123/status",
     "check_again_in": 5  // seconds
   }

3. Queue: Search job added to Kafka
   topic: search.requested
   {
     "search_id": "search_123",
     "query": "...",
     "callback_url": "..."
   }

4. Worker: Processes search (takes 200ms)
   Publishes events:
   - "search.started"
   - "search.found_result" (multiple times)
   - "search.completed"

5. Client: Polls status (or gets webhook)
   GET /search/async/search_123/status
   → {"status": "completed", "results": [...]}

6. Client: Retrieves results
   GET /search/async/search_123/results
   → {"hits": [...]}
```

**Implementation:**

1. **New Endpoint** (`backend/api/routes.py`)
   ```python
   @router.post("/search/async")
   async def search_async(request: AsyncSearchRequest):
       search_id = str(uuid.uuid4())
       
       # Queue to Kafka
       kafka_producer.send("search.requested", {
           "search_id": search_id,
           "query": request.query,
           "callback_url": request.callback_url
       })
       
       # Return immediately
       return {
           "request_id": search_id,
           "status_url": f"/search/async/{search_id}/status"
       }
   ```

2. **Worker Process** (New Celery task or Kafka consumer)
   ```python
   def consume_search_requests():
       for event in kafka_consumer.subscribe("search.requested"):
           search_id = event.search_id
           
           # Process
           results = await retrieve_and_rerank(event.query)
           
           # Store results
           redis.set(f"search_results:{search_id}", json.dumps(results), ex=300)
           
           # Update status
           redis.set(f"search_status:{search_id}", "completed")
           
           # Webhook callback
           requests.post(event.callback_url, json={
               "search_id": search_id,
               "status": "completed"
           })
   ```

3. **Status Endpoint**
   ```python
   @router.get("/search/async/{search_id}/status")
   async def search_status(search_id: str):
       status = redis.get(f"search_status:{search_id}")
       return {"status": status or "pending"}
   ```

**Tradeoffs:**
- ✅ Gain: Scalability (decouple latency from queue depth)
- ✅ Gain: Handle spikes (queue can buffer)
- ❌ Loss: Synchronous expectations (must change client)
- ❌ Loss: Complexity (polling/webhooks, state management)

---

## Scenario 6.2: Introduce Event-Driven Architecture with CQRS

**Requirement:**

Current: Search request → Retrieve + Cache in one operation

New: Separate reading (query) from writing (events)

Why? To enable multiple consumers (analytics, caching, indexing) independently.

**Constraints:**
- Must not break existing sync API
- Events must be queryable (what searches happened?)
- Analytics must not slow down search

---

### Guided Questions

**Q1: What's the "command" vs "query" separation?**

**Q2: What events would you publish?**

**Q3: Who are the consumers of these events?**

**Q4: How does CQRS help with multiple consumers?**

**Q5: Does this fix any existing problems?**

**Q6: What's the complexity cost?**

---

### Model Solution

**CQRS Pattern:**

```
Command Side (Write):
  Search.Execute(query)
    └─ Validate
    └─ Emit SearchRequested event
    └─ Return

Query Side (Read):
  SearchEventLog.Query(filters)
    └─ Rebuild read model from events
    └─ Return results

Events:
  SearchRequested (query, tenant, user)
  CacheChecked (hit/miss, tier)
  VectorSearched (candidates_found)
  DocumentsReranked (top_k)
  SearchCompleted (latency, results)
```

**Implementation:**

1. **Event Store** (Kafka topic: search.events)
   ```python
   @dataclass
   class SearchEvent:
       event_type: str  # "search_requested", "cache_hit", etc.
       search_id: str
       timestamp: datetime
       tenant_id: str
       data: dict
   ```

2. **Command Handler**
   ```python
   @router.post("/search")
   async def search_command(request: SearchRequest):
       search_id = str(uuid.uuid4())
       
       # Emit event
       event_bus.publish(SearchEvent(
           event_type="search_requested",
           search_id=search_id,
           tenant_id=request.tenant_id,
           data={"query": request.query}
       ))
       
       # Process (same as before)
       results = await retrieval_engine.search(request)
       
       # Emit completion event
       event_bus.publish(SearchEvent(
           event_type="search_completed",
           search_id=search_id,
           data={"result_count": len(results)}
       ))
       
       return results
   ```

3. **Event Consumers**
   ```python
   # Consumer 1: Analytics
   def consume_for_analytics():
       for event in event_bus.subscribe("search.*"):
           analytics_db.insert(event)
   
   # Consumer 2: Caching
   def consume_for_caching():
       for event in event_bus.subscribe("search.completed"):
           cache.set(event.search_id, event.results)
   
   # Consumer 3: Monitoring
   def consume_for_monitoring():
       for event in event_bus.subscribe("search.*"):
           metrics.increment(f"search.{event.event_type}")
   ```

**Tradeoffs:**
- ✅ Gain: Decoupled consumers (can add without changing search)
- ✅ Gain: Event replay (rebuild analytics from events)
- ✅ Gain: Audit trail (all events logged)
- ❌ Loss: Complexity (event model, eventual consistency)
- ❌ Loss: Added infrastructure (event bus, consumers)

---

## Scenario 6.3: Split into Microservices

**Requirement:**

Current monolith: All functionality in one service.

Proposed: Split into:
1. **Search Service** (retrieval, caching)
2. **Ingestion Service** (document upload, embedding, indexing)
3. **Auth Service** (JWT, RBAC, rate limiting)
4. **Analytics Service** (logging, metrics)

**Constraints:**
- Must support same external API
- Services can fail independently
- Each service has different scaling needs

---

### Guided Questions

**Q1: How would services communicate?**

**Q2: What about shared state (cache, rate limit buckets)?**

**Q3: Which service owns Qdrant?**

**Q4: How do you handle distributed transactions?**

**Q5: Is this even a good idea? What's the upside?**

**Q6: How would you migrate without downtime?**

---

### Model Solution

**Service Boundaries:**

```
API Gateway
  ├─ Search Service
  │  ├─ RetrievalEngine
  │  ├─ Reranker
  │  └─ Qdrant (read-only replica)
  │
  ├─ Ingestion Service
  │  ├─ DocumentParser
  │  ├─ Chunker
  │  ├─ Embedder
  │  └─ Qdrant (primary)
  │
  ├─ Auth Service
  │  ├─ TokenValidator
  │  ├─ RateLimiter
  │  └─ RBACEnforcer
  │
  └─ Analytics Service
     ├─ EventConsumer
     └─ AnalyticsDB
```

**Communication:**

1. **Synchronous** (gRPC/REST for direct calls)
   - API Gateway calls Auth Service for token validation
   - Search Service calls Auth Service for rate limit

2. **Asynchronous** (Kafka for events)
   - Search Service publishes search.completed events
   - Analytics Service consumes them

**Shared State:**

1. **Redis Cluster** (shared by all services)
   - Cache (Search Service primary user)
   - Rate limit buckets (Auth Service)
   - Revocation list (Auth Service)

2. **Qdrant Cluster**
   - Ingestion Service: Primary (writes)
   - Search Service: Read-only replica

**Tradeoffs:**
- ✅ Gain: Independent scaling (if ingestion slow, doesn't affect search)
- ✅ Gain: Independent deployment (update search without restarting ingestion)
- ✅ Gain: Team ownership (each team owns one service)
- ❌ Loss: Distributed debugging (harder to trace issues)
- ❌ Loss: Network latency (inter-service calls)
- ❌ Loss: Operational complexity (manage 4 services)

**Migration Strategy:**

1. **Phase 1**: Deploy services alongside monolith
   - Monolith still running
   - New services get 1% traffic (canary)

2. **Phase 2**: Increase traffic to new services
   - Monitor errors, latency
   - Gradually increase to 50%

3. **Phase 3**: Decommission monolith
   - All traffic on microservices
   - Keep monolith as fallback for 1 month

---

# Summary

**Level 1**: Adding fields, endpoints, features → Low complexity
**Level 2**: New roles, workflows, capabilities → Medium complexity
**Level 3**: Infrastructure swaps → High complexity, major risks
**Level 4**: Scaling challenges → System design required
**Level 5**: Failure handling → Graceful degradation patterns
**Level 6**: Architecture redesigns → Major tradeoffs, careful migration

Each level builds on understanding the previous system before making changes. The key is:
- Understand existing design first
- Identify what must change
- Predict cascade effects
- Consider tradeoffs
- Plan migration strategy
