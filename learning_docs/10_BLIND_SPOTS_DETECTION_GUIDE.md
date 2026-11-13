# Blind Spots Detection Guide - Self-Assessment Framework

This document helps you identify what you THINK you understand about CASL but actually don't understand deeply. It's designed to be used AFTER you work through the scenarios and exams.

## How to Use This Guide

1. **Work through scenarios (Document 09)** - Write your answers without looking at solutions
2. **Review your answers** - Reread what you wrote
3. **Use this guide** - Check if you've fallen into common blind spots
4. **Take the exposure test** - Can you answer a question that requires deep understanding?
5. **Do the practical exercise** - Build something to close the gap

---

# Critical Blind Spots

These are dangerous because they seem intuitive but are wrong.

---

## Blind Spot 1: "Caching is Just Speed, Not Correctness"

### What You Think You Understand
"Caching improves latency. If cache is wrong, results are stale but still work. Cache doesn't affect correctness, only speed."

### What You're Actually Missing
1. **Cache invalidation is hard** - Cache can silently return wrong data without errors
2. **Consistency model is complex** - Eventual consistency has subtle failures
3. **Cache creates new failure modes** - System can fail in ways that don't exist without cache
4. **Race conditions** - Cache + concurrent updates = inconsistency

### Why This Matters
```
Without understanding cache correctness:
- You'll design systems that silently return wrong data
- You won't understand distributed consistency
- You'll miss critical test cases
- You'll fail to predict system failures under load
```

### Repository Example: Two-Tier Cache

**What you probably think:**
- Tier 1 (exact match) gets exact results
- Tier 2 (semantic) gets similar results
- Both are correct

**What you're missing:**
```
Scenario 1: Document Hidden After Cached
- User searches "secret docs"
- Results cached (includes hidden document)
- Admin hides document
- User searches again → Cache returns HIDDEN document
- Result is silently wrong (admin intended to hide it)

Scenario 2: Collection Changed After Cached
- User searches in collection "A"
- Results cached
- Admin moves document to collection "B"
- User searches same query → Cache returns doc in wrong collection

Scenario 3: Similarity Threshold Not What You Think
- Tier 2: threshold = 0.95 cosine similarity
- Query A embedding: [0.1, 0.2, 0.3, ...]
- Query B embedding: [0.1, 0.2, 0.31, ...]  (0.01 difference)
- Cosine similarity: 0.9999 (will hit cache!)
- But queries are DIFFERENT ("attention" vs "attend")
- False cache hit!
```

### Exposure Test

**Question:** A document is marked as "hidden" by admin. At exactly that moment, user searches and gets the document from cache. Is this a bug?

**If you answer:** "Sort of, it's eventual consistency" → You're missing it
**Correct answer:** "Yes. Admin action should be immediate. Cache must invalidate on hide."

### Practical Exercise

**Exercise: Build a cache invalidation system**

Modify `backend/cache/semantic_cache.py`:

```python
# Add cache invalidation when document changes
class SemanticCache:
    async def invalidate_by_document(self, doc_id: str):
        """Remove all cache entries containing this document."""
        # Problem 1: How do you know which cache entries have this doc?
        # The cache stores responses, not document lists
        
        # Problem 2: Semantic cache stores vectors, not document IDs
        # How do you find similar vectors that contain this doc?
        
        # Problem 3: What about Tier 1 cache?
        # Different queries might return same document
        # Need to invalidate all containing this doc
        pass

# Implement this correctly
# Answer: You can't efficiently invalidate by document
# Better solution: Invalidate by query (customer initiates)
# Or: Add document_ids to cached response metadata
```

**Why this matters:** This exercise shows you that cache invalidation IS hard, and the current CASL design makes assumptions about correctness that may not hold.

---

## Blind Spot 2: "Multi-Tenancy is Just Filtering"

### What You Think You Understand
"Multi-tenancy means filtering queries by tenant_id. Add a WHERE clause in database queries."

### What You're Actually Missing
1. **It's a security boundary** - Not adding tenant filter = data leak
2. **It affects caching** - Cache key must include tenant_id (can't mix tenants)
3. **It affects rate limiting** - Buckets must be per-tenant
4. **It affects authorization** - Can't just check role, must check role + tenant
5. **It affects data model** - Tenant_id in every query, JWT, metadata, audit log

### Why This Matters
```
Without understanding tenant-safety:
- You'll write queries that accidentally leak data
- You'll design caches that mix tenants
- You'll create permission escalation bugs
- You'll fail to understand security model
```

### Repository Example: The Double-Blind Tenant Check

**What you probably think:**
- JWT has tenant_id (secure because signed)
- Database query filtered by tenant_id (defense in depth)
- One of these alone is enough

**What you're missing:**
```
Scenario: What if JWT validation is bypassed?
- Attacker forges JWT with tenant_id="google_research"
- JWT signature invalid, so rejected
- But what if code has bug and skips signature check?
- JWT still has wrong tenant_id
- But database filter still protects (filters for attacker's real tenant)
- This is the double-blind: both must be correct

Scenario: What if developer forgets tenant filter?
- Query runs: SELECT * FROM documents WHERE id = ?
- No tenant filter!
- Attacker queries any document, any tenant
- This is a critical bug

Scenario: What if cache mixing?
- Tenant A searches "secret"
- Cache key: "cache:search:secret" (NO tenant!)
- Tenant B searches "secret"
- Hits cache (wrong tenant's results!)
- Critical data leak
```

### Exposure Test

**Question:** In CASL, tenant_id appears in JWT, in TenantContext, and in Qdrant metadata filter. Is this redundant or necessary?

**If you answer:** "Redundant, just need it in JWT" → You're missing security defense-in-depth

**Correct answer:** "Necessary. Each layer is a defense. If one fails, others protect. This is 'defense in depth'."

### Practical Exercise

**Exercise: Find the tenant_id usage**

```python
# In your code, trace tenant_id through a search request
# Questions:
# 1. Where is tenant_id validated?
# 2. Where is it stored (TenantContext)?
# 3. Where is it used in database query?
# 4. Where is it used in cache key?
# 5. Where is it used in rate limit key?
# 6. What breaks if one is missing?

# Try this: Comment out the Qdrant filter tenant_id
#   (don't run this, just imagine)
# What could go wrong?
# Answer: User could query any tenant's data

# Try this: Comment out TenantContext injection
# What could go wrong?
# Answer: Wrong tenant in cache key, cache mixing

# Try this: Use wrong tenant_id in JWT
# What could go wrong?
# Answer: JWT signature verification fails, request rejected
```

This exercise shows that each tenant_id check is essential.

---

## Blind Spot 3: "Async Operations Are Safe From Race Conditions"

### What You Think You Understand
"Async/await prevents race conditions. If I use async, concurrent requests won't interfere."

### What You're Actually Missing
1. **Async ≠ atomic** - Async code can interleave just like threads
2. **No implicit locking** - Multiple coroutines can access same data
3. **Order not guaranteed** - Async tasks can complete in any order
4. **Check-then-act is racy** - Checking a condition then acting based on it is unsafe

### Why This Matters
```
Without understanding async safety:
- You'll write race conditions in async code
- You'll assume things happen in order when they don't
- You'll create data corruption bugs
- Rate limiting + caching will have correctness bugs
```

### Repository Example: Token Bucket Race Condition

**What you probably think:**
```python
# In Python asyncio, this is safe:
tokens = 100
if tokens > 0:
    tokens -= 1  # Use a token
# Multiple coroutines won't interfere
```

**What you're missing:**
```
Race scenario (even with async):
Coroutine A: Check (if tokens > 0) → True
Coroutine B: Check (if tokens > 0) → True  [BOTH see 100!]
Coroutine A: Decrement → 99
Coroutine B: Decrement → 99  [Should be 98!]

Result: Both coroutines used one token, but bucket only decremented once
Token leak! Rate limit bypassed!

This is why CASL uses Lua script in Redis:
```python
# Lua script (atomic):
if redis.call('get', key) >= 1:
    redis.call('decrby', key, 1)
    return 1  # Allowed
else
    return 0  # Blocked
# This is atomic - no interleaving possible
```

### Exposure Test

**Question:** If you moved rate limiting from Redis Lua to Python asyncio, what breaks?

**If you answer:** "Nothing, asyncio is safe" → You're missing it

**Correct answer:** "Multiple coroutines could read the same bucket value, both decrement, causing bucket to underflow. This is a race condition even in async."

### Practical Exercise

**Exercise: Implement unsafe rate limiting, then fix it**

```python
# UNSAFE (even with asyncio):
class UnsafeRateLimiter:
    def __init__(self):
        self.bucket = 100
    
    async def acquire(self):
        if self.bucket > 0:
            self.bucket -= 1
            return True
        return False

# This WILL have race conditions
# Simulate concurrent calls:
import asyncio

async def test_unsafe():
    limiter = UnsafeRateLimiter()
    
    # Concurrent requests
    results = await asyncio.gather(
        *[limiter.acquire() for _ in range(150)]
    )
    
    # Expected: ~100 True, ~50 False
    # Actual: ~150 True (bucket underflowed!)
    allowed = sum(results)
    print(f"Allowed: {allowed} (expected ~100)")
    print(f"Final bucket: {limiter.bucket} (expected 0)")

asyncio.run(test_unsafe())
# Output: Allowed: 150, Final bucket: -50
# WRONG! Rate limit completely broken
```

This shows that async alone doesn't prevent race conditions.

---

## Blind Spot 4: "Error Handling in Middleware is Transparent"

### What You Think You Understand
"Middleware catches errors. If something fails (auth, rate limit), return error response. No impact on request flow."

### What You're Actually Missing
1. **Where errors go affects behavior** - 401 vs 429 vs 500 have different meanings
2. **Logging affects debugging** - Missing error logs = impossible to debug
3. **Metrics are affected** - Error rate metrics must be accurate
4. **Some errors must not be cached** - A 500 should not cache like a 200
5. **Partial failure = complex** - If rate limit fails, should you block or allow?

### Why This Matters
```
Without understanding error handling:
- You'll lose visibility into system failures
- You'll cache errors incorrectly
- You'll ship systems that fail silently
- You won't understand why production is broken
```

### Repository Example: RATE_LIMIT_FAIL_OPEN

**What you probably think:**
- If Redis is down, ignore rate limiting
- Return 200 (allow request)
- Problem solved

**What you're missing:**
```
Scenario: Redis down for 10 minutes
1. Rate limiter can't reach Redis
2. Decisions:
   - FAIL_OPEN=true: Allow all requests (some unlimited requests, some limited)
   - FAIL_OPEN=false: Block all requests (users see 429)

Which is correct?
- FAIL_OPEN=true:
  ✅ Users can still use system (availability)
  ❌ Rate limits not enforced (abuse possible)
  ❌ One tenant could abuse others' quota

- FAIL_OPEN=false:
  ✅ Rate limits stay safe (security)
  ❌ System appears down (availability)
  ❌ Legitimate users get 429

There's no right answer! It's a choice:
- Security team: Use FAIL_OPEN=false (security > availability)
- Availability team: Use FAIL_OPEN=true (availability > security)

Without understanding this tradeoff, you'll make wrong decision.
```

### Exposure Test

**Question:** If rate limiter fails (Redis down), what should happen?

**If you answer:** "Return 200, allow request" → You're missing the tradeoff

**Correct answer:** "Depends on configuration (FAIL_OPEN). Security vs availability tradeoff. Must be explicit."

### Practical Exercise

**Exercise: Implement both fail modes**

```python
# Current (simplified):
class RateLimiter:
    async def acquire(self, tenant_id):
        try:
            result = await redis.get_bucket(tenant_id)
            return result  # (allowed, remaining, reset)
        except RedisError:
            if FAIL_OPEN:
                return (True, float('inf'), 0)  # Allow all
            else:
                return (False, 0, 60)  # Block all

# Question: Which one does CASL use?
# Check: backend/security/rate_limiter.py
# Answer: Look for "RATE_LIMIT_FAIL_OPEN" config

# Why does this matter?
# - Security teams need FAIL_OPEN=false
# - Availability teams need FAIL_OPEN=true
# - You must understand the tradeoff to choose correctly
```

---

# High Priority Blind Spots

These are important but less immediately dangerous.

---

## Blind Spot 5: "Semantic Caching Threshold (0.95) is Magic"

### What You Think You Understand
"Tier 2 cache uses 0.95 cosine similarity threshold. Similar queries hit cache."

### What You're Missing
1. **How was 0.95 chosen?** - Empirically? Guessed? Research-based?
2. **What's the tradeoff?** - Higher = fewer false positives, lower hit rate
3. **Different embeddings differ** - Different models have different similarity distributions
4. **No error checking** - What if similarity computation is wrong?

### Why This Matters
```
If threshold is too high (0.99):
  - Almost no cache hits (cache useless)
  
If threshold is too low (0.90):
  - Many false positives (wrong results returned)
  - Silent data corruption
  
The right threshold depends on:
  - Query diversity (how different are queries?)
  - Embedding model (what space are we in?)
  - Acceptable false-positive rate
  - Required hit rate
```

### Exposure Test

**Question:** If you switched embedding models from sentence-transformers to OpenAI embeddings, would threshold of 0.95 still work?

**If you answer:** "Yes, 0.95 is universal" → You're missing it

**Correct answer:** "No. OpenAI embeddings have different similarity distribution. 0.95 might be too high/low. Need to retune threshold."

### Practical Exercise

Implement threshold tuning:
1. Collect 1000 search queries
2. Group by "same intent" or "different intent"
3. Compute similarities between:
   - Same intent queries
   - Different intent queries
4. Find threshold that maximizes:
   - True positive rate (same intent hits cache)
   - True negative rate (different intent misses cache)
5. This is ROC curve analysis

---

## Blind Spot 6: "Rate Limiting is Just Counting"

### What You Think You Understand
"Count requests per minute, return 429 when limit exceeded."

### What You're Missing
1. **Clock skew** - Server clocks differ, threshold becomes inconsistent
2. **Token refill logic** - When exactly do tokens refill?
3. **Burst handling** - Can user spend all tokens at once or must spread?
4. **Multiple services** - How do distributed rate limiters coordinate?
5. **Different per-endpoint limits** - How does rate limit multiply across endpoints?

### Why This Matters
```
Example: "1000 req/min" looks simple
But what about:
- Burst: Can user send 1000 in 1 second, then 0 for 59 seconds?
  (Token bucket says YES - tokens accumulate)
- Clock skew: If server A thinks it's 12:00:01 and B thinks 12:00:05
  (They'll compute different refill rates!)
- Multiple endpoints: If /search and /ingest both have 1000 req/min
  (Can user send 2000 by splitting between endpoints?)
```

### Exposure Test

**Question:** In CASL, can a user send 1000 requests in 1 second, then nothing for 59 seconds?

**If you answer:** "No, must spread evenly" → You're missing how token bucket works

**Correct answer:** "Yes. Token bucket allows bursts. This is a feature, not a bug."

### Practical Exercise

Simulate token bucket behavior:

```python
# Bucket starts with 1000 tokens
# Refill rate: 1000 tokens/min = 16.67 tokens/sec

# Scenario:
# Second 0: Send 1000 requests → 1000 tokens spent, 0 left
# Seconds 1-59: Send 0 requests
# Second 60: Tokens refilled to 1000

# Question: What about second 30?
# Tokens refilled: 16.67 * 30 = 500 tokens available
# Can send 500 requests at second 30

# This is correct behavior!
# It's not "unfair", it's how token bucket is designed
```

---

## Blind Spot 7: "Tenant_id in JWT is Sufficient for Security"

### What You Think You Understand
"JWT has tenant_id and it's signed, so tenant can't be changed."

### What You're Missing
1. **The JWT can be validated but SKIP** - Bug in auth code = validation bypassed
2. **The tenant_id can be extracted wrong** - Extraction logic might have bug
3. **The value might not be used** - Validated but forgotten in query
4. **Defense in depth** - Multiple layers catch different bugs

### Why This Matters
```
Security is layered:
1. JWT validation (check signature) → Prevents external tampering
2. Extraction (get tenant_id from payload) → Prevents extraction bugs
3. Storage (TenantContext) → Ensures accessible throughout request
4. Usage (filter every query) → Ensures it's actually used
5. Verification (audit log) → Detects breaches after they happen

If ANY layer fails, tenants can leak data.
This is not redundant - it's defense in depth.
```

### Exposure Test

**Question:** What would break if you removed the tenant_id filter from Qdrant queries?

**If you answer:** "Nothing, JWT validates it" → You're missing it

**Correct answer:** "Data leak. User could see all tenants' documents. JWT doesn't prevent this - only database filter does."

---

# Medium Priority Blind Spots

These are subtle but important for advanced understanding.

---

## Blind Spot 8: "Async Cache Population is Fire-and-Forget"

### What You Think You Understand
"Cache is populated asynchronously in background. Doesn't affect response."

### What You're Missing
1. **Multiple workers competing** - Race between workers populating same cache
2. **Order not guaranteed** - Which worker finishes first determines cached value
3. **Stale data from slow worker** - First worker to finish writes cache, even if slower
4. **Cache coherency** - New requests might see partially cached data

### Exposure Test

**Question:** Two workers complete the same search with different latencies. Worker B (slower, 200ms) finishes first due to queue delays. Will cache contain Worker B's result or Worker A's result?

**Answer:** Worker B's result (whoever writes first). This could be stale if A's result was more fresh.

---

## Blind Spot 9: "Re-ranking Always Improves Results"

### What You Think You Understand
"Re-ranker scores documents, sorts by score. Higher score = better result."

### What You're Missing
1. **Re-ranker can be wrong** - Trained on different data, different goals
2. **Re-ranker can be slow** - Cost of re-ranking might not be worth small quality gain
3. **Re-ranker can't fix bad retrieval** - If Qdrant retrieves wrong documents, re-ranker can't fix it
4. **Combining multiple signals is hard** - How much weight to vector score vs re-ranker score?

### Exposure Test

**Question:** If Qdrant retrieves documents [A, B, C] with scores [0.95, 0.85, 0.75], and re-ranker scores them [0.5, 0.9, 0.7], should result be [B, C, A]?

**Answer:** Not necessarily. Combining scores requires careful weighting, not just swapping order.

---

## Blind Spot 10: "Document IDs Scoped to Tenant Prevent Cross-Tenant Access"

### What You Think You Understand
"Documents stored as tenant_id:doc_id. Uniquely identifies per tenant."

### What You're Missing
1. **It's not a permission check** - It's just a naming scheme
2. **Database must still filter** - Having tenant_id in ID doesn't prevent queries
3. **Scoping is invisible to users** - User shouldn't know about scoping implementation
4. **Migration complexity** - If tenant_id changes, all document IDs invalid

### Exposure Test

**Question:** If you have document ID "acme:doc_123", can you directly query it without tenant_id filter?

**Answer:** Depends on database. If no filter, you get "acme:doc_123" regardless of current tenant. Scoping alone doesn't secure it.

---

# Low Priority Blind Spots

These are less critical but good to understand.

---

## Blind Spot 11: "Embedding Model is a Black Box"

### What You Think You Understand
"Embedding model converts text to vectors. Done."

### What You're Missing
1. **Model determines similarity metric** - Different models have different similarity distributions
2. **Model has capacity limits** - Can't distinguish nuanced differences in some cases
3. **Model trains on specific data** - Generalizes poorly to out-of-domain text
4. **Model updates break cache** - Different model = different embeddings = all cache invalid

### Exposure Test

**Question:** If you want to find "similar questions" to a user's search, should you use the same embedding model as for documents?

**Answer:** Probably, but depends on:
- Whether model was trained on questions
- Whether document embeddings and query embeddings are in same space
- Whether cross-domain similarity makes sense

---

## Blind Spot 12: "Circuit Breaker is Just Error Handling"

### What You Think You Understand
"If something fails, open circuit, fast-fail."

### What You're Missing
1. **Circuit state machine is complex** - CLOSED → OPEN → HALF_OPEN → CLOSED
2. **Timing matters** - How long to wait before trying again?
3. **Threshold is tunable** - When do you open the circuit (3 failures? 50%? How quickly?)
4. **Can cause cascading failures** - Aggressive circuit breaking can crash entire system

### Why This Matters

```
Circuit breaker states:
CLOSED: Normal operation, let requests through
OPEN: Failing, fast-fail new requests (don't retry)
HALF_OPEN: Testing if system recovered, allow one request

If threshold too low (open too quickly):
  - System appears down when one service has issues
  - Cascading failure

If threshold too high (stay open too long):
  - Repeated failures waste time
  - Slow recovery
```

---

# Self-Assessment Tool

## Use This After Working Through Scenarios

For each blind spot above, rate yourself 0-5:

```
5 = I can explain this with examples and edge cases
4 = I understand this but need to think about details
3 = I know this exists but haven't internalized it
2 = I've heard of this but don't really understand
1 = First time seeing this
0 = Actively confused
```

If you score <3 on any "Critical" blind spot, you should revisit that section.

---

# Practical Exercise: Find Your Own Blind Spot

## Exercise Process

1. **Read a subsystem** (e.g., rate_limiter.py)
2. **Assume you understand it**
3. **Ask yourself**: "What would I do wrong if I built this myself?"
4. **Check the actual code** - What did they do differently?
5. **Understand why** - What assumption was I making that was wrong?

## Example

**Subsystem: Rate Limiting** (backend/security/rate_limiter.py)

**My assumption:** "Probably just gets bucket from Redis and decrements"

**What I might get wrong:**
- Race conditions (check then decrement)
- Token refill calculation
- Per-endpoint bucket isolation
- Config overrides

**What actual code does:**
- Uses Lua script for atomicity
- Refill calculated as: (current_time - last_refill) * refill_rate
- Per-tenant-endpoint isolation: key format includes both
- Config merges tier defaults + custom overrides

**What I learned:** Atomicity is critical. Lua script prevents race conditions that async alone can't.

---

# How to Use This Document

### After Each Scenario:
1. Review your answer
2. Check if you fell into any of these blind spots
3. Look at the exposure test - can you answer it?
4. Do the practical exercise

### After All Scenarios:
1. Self-assess on the rating scale (0-5)
2. Revisit "Critical" blind spots where you scored <3
3. Do the practical exercises for those areas

### Before Interviews/Production:
1. Mentally run through each blind spot
2. Can you explain why each one matters?
3. Can you give repository-specific examples?

---

# The Meta-Blind Spot

**The biggest blind spot:** Assuming you understand something you haven't built.

You think you understand rate limiting until you try to implement it. Then you discover:
- Race conditions
- Clock skew
- Token refill timing
- Multiple endpoints
- Config merging
- Monitoring

This is why the practical exercises matter. Building forces understanding.

**Your job:** Treat these blind spots as hypotheses, not facts. Verify each one by:
1. Reading the code
2. Building something
3. Breaking it on purpose
4. Fixing it
5. Understanding why it failed

That's when you truly understand.
