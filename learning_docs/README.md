# CASL Learning Documentation

This folder contains comprehensive learning materials for understanding the CASL backend system.

## What's Included

### ✅ Completed Documents

1. **[00_INDEX.md](00_INDEX.md)** — Master index and reading guide
   - How to use this curriculum
   - Reading paths for different roles
   - Topics quick reference
   - Estimated reading times

2. **[01_EXECUTIVE_SUMMARY.md](01_EXECUTIVE_SUMMARY.md)** — Overview and context
   - What is CASL?
   - System at a glance
   - Key statistics
   - Major components
   - Problem space and evolution
   - What you'll learn

3. **[02_REPOSITORY_MAP.md](02_REPOSITORY_MAP.md)** — File-by-file inventory
   - Complete directory structure
   - Module inventory (backend/agents, backend/api, etc.)
   - File responsibilities and line counts
   - Configuration files
   - Frontend files
   - Key files summary
   - Dependency relationships

4. **[03_SYSTEM_MENTAL_MODEL.md](03_SYSTEM_MENTAL_MODEL.md)** — How it all works
   - The problem CASL solves
   - High-level flow (user action → response)
   - Core concepts:
     - Multi-tenancy
     - Hybrid retrieval
     - Semantic caching
     - RBAC
     - Rate limiting (token bucket)
     - Agents (autonomous execution)
   - Detailed request lifecycle
   - Key invariants/guarantees
   - Optional features (all disabled by default)
   - What happens without each feature

5. **[04_ARCHITECTURE_OVERVIEW.md](04_ARCHITECTURE_OVERVIEW.md)** — System design patterns
   - Architectural style (layered + microservice-inspired)
   - Architectural patterns:
     - Layered architecture
     - Middleware chain
     - Singleton pattern
     - Dependency injection
     - Factory pattern
     - Circuit breaker
     - Observer pattern
     - Decorator pattern
     - Async/await pattern
   - Detailed request processing flow
   - Separation of concerns (horizontal and vertical slicing)
   - Dependency graph
   - Data flow architecture
   - Key architectural decisions (with tradeoffs)
   - Scaling considerations

### 📋 Planned Documents

These documents have been planned but not yet written. The structure and outline is ready.

6. **[05_RUNTIME_FLOWS.md]** — Trace specific operations
   - Search request flow (detailed step-by-step)
   - Document ingestion flow
   - Agent execution flow
   - Cache hit vs miss scenarios
   - Async cache population
   - Token refresh flow
   - Rate limit exceeded flow

7. **[06_COMPONENT_ARCHITECTURE.md]** — Deep-dive into each major component
   - API Layer
   - Services Layer (Retrieval Engine, Ingestion Engine)
   - Data Access Layer
   - Cache Layer
   - Security Layer
   - Agent Layer
   - Task Queue Layer

8. **[07_SECURITY_ARCHITECTURE.md]** — Security implementation details
   - Authentication (JWT)
   - Authorization (RBAC)
   - Rate Limiting (Token Bucket with Lua atomicity)
   - Multi-tenancy enforcement
   - Audit logging
   - PII masking and injection detection
   - Threat model and security boundaries

9. **[08_CACHING_STRATEGY.md]** — Deep-dive into caching
   - Two-tier cache design
   - Exact match caching (Tier 1)
   - Semantic similarity caching (Tier 2)
   - Cache invalidation strategies
   - Performance metrics and monitoring
   - Redis-based implementation

10. **[09_AGENT_EXECUTION.md]** — Agent system details
    - LangGraph state machine
    - Node definitions
    - Tool calling mechanisms
    - Reflection and adaptation
    - Safety guardrails
    - Monitoring agent execution

11. **[10_MULTI_MODEL_GATEWAY.md]** — LLM routing system
    - Provider routing logic
    - Cost estimation
    - Latency prediction
    - Circuit breakers
    - Fallback chains
    - Support for Groq, OpenAI, Anthropic, Ollama

12. **[11_OBSERVABILITY.md]** — Monitoring and tracing
    - OpenTelemetry tracing setup
    - Prometheus metrics
    - Token budgeting
    - Health checks
    - Performance monitoring

13. **[12_DESIGN_PATTERNS.md]** — Design patterns explained
    - Layered architecture
    - Middleware chain
    - Singleton pattern
    - Dependency injection (via FastAPI Depends)
    - Factory pattern
    - Circuit breaker
    - Observer pattern
    - Decorator pattern
    - Async/await patterns
    - Repository pattern

14. **[13_DATA_ARCHITECTURE.md]** — Data models and storage
    - SearchRequest and SearchResponse models
    - Vector storage (Qdrant integration)
    - Cache storage (Redis)
    - Document schema
    - Metadata handling
    - Tenant scoping in data

15. **[14_ALTERNATIVES_AND_TRADEOFFS.md]** — Design decisions explained
    - Layered vs hexagonal architecture
    - Token bucket vs sliding window rate limiting
    - Semantic cache vs naive caching
    - Qdrant vs other vector DBs (Weaviate, Milvus, Pinecone)
    - OpenTelemetry vs custom logging
    - LangGraph vs ReAct agents
    - Celery vs other task queues (Temporal, RQ)

16. **[15_WEAKNESSES_AND_RISKS.md]** — Critical analysis
    - Architectural smells
    - Scalability risks
    - Security risks
    - Reliability risks
    - Performance risks
    - Testing gaps
    - Technical debt
    - Dependency risks

17. **[16_TESTING_STRATEGY.md]** — How to test this system
    - Unit testing approach
    - Integration testing
    - End-to-end testing
    - Security testing
    - Performance testing
    - Load testing considerations

18. **[17_LEARNING_CURRICULUM.md]** — Structured learning path
    - Topic-by-topic learning objectives
    - Prerequisites for each topic
    - Key concepts to understand
    - Practical exercises
    - Architecture exercises
    - Recommended reading order

19. **[18_GLOSSARY.md]** — Terminology reference
    - RAG, embedding, vector search, semantic similarity
    - RBAC, RAGAS, OTEL, SSE, JWT, JTI
    - Token bucket, circuit breaker, re-ranker
    - System-specific terms and acronyms

20. **[19_FAQ.md]** — Common questions and answers
    - Common questions about features
    - Troubleshooting guide
    - Performance tuning tips
    - Extension patterns
    - Deployment considerations

21. **[20_RECOMMENDED_DEEP_DIVES.md]** — Topic-specific guides
    - Interested in caching? Start with [08_CACHING_STRATEGY.md]
    - Interested in security? Start with [07_SECURITY_ARCHITECTURE.md]
    - Interested in agents? Start with [09_AGENT_EXECUTION.md]
    - Interested in LLM routing? Start with [10_MULTI_MODEL_GATEWAY.md]
    - And more...

---

## How to Use This Documentation

### For First-Time Readers
1. Start with [00_INDEX.md](00_INDEX.md) to understand the structure
2. Read [01_EXECUTIVE_SUMMARY.md](01_EXECUTIVE_SUMMARY.md) for context
3. Read [02_REPOSITORY_MAP.md](02_REPOSITORY_MAP.md) to understand file organization
4. Read [03_SYSTEM_MENTAL_MODEL.md](03_SYSTEM_MENTAL_MODEL.md) to learn how the system works
5. Read [04_ARCHITECTURE_OVERVIEW.md](04_ARCHITECTURE_OVERVIEW.md) for design patterns

### For Architects/Senior Engineers
1. Skim [01_EXECUTIVE_SUMMARY.md](01_EXECUTIVE_SUMMARY.md) and [03_SYSTEM_MENTAL_MODEL.md](03_SYSTEM_MENTAL_MODEL.md)
2. Read [04_ARCHITECTURE_OVERVIEW.md](04_ARCHITECTURE_OVERVIEW.md)
3. Read [14_ALTERNATIVES_AND_TRADEOFFS.md](14_ALTERNATIVES_AND_TRADEOFFS.md)
4. Read [15_WEAKNESSES_AND_RISKS.md](15_WEAKNESSES_AND_RISKS.md)

### For Security Team
1. Read [07_SECURITY_ARCHITECTURE.md](07_SECURITY_ARCHITECTURE.md)
2. Read [15_WEAKNESSES_AND_RISKS.md](15_WEAKNESSES_AND_RISKS.md) (security section)
3. Read [16_TESTING_STRATEGY.md](16_TESTING_STRATEGY.md)

### For Performance Engineers
1. Read [03_SYSTEM_MENTAL_MODEL.md](03_SYSTEM_MENTAL_MODEL.md)
2. Read [08_CACHING_STRATEGY.md](08_CACHING_STRATEGY.md)
3. Read [10_MULTI_MODEL_GATEWAY.md](10_MULTI_MODEL_GATEWAY.md)
4. Read [11_OBSERVABILITY.md](11_OBSERVABILITY.md)

---

## Learning Paths

### Quick Overview (30 minutes)
- [00_INDEX.md](00_INDEX.md)
- [01_EXECUTIVE_SUMMARY.md](01_EXECUTIVE_SUMMARY.md)
- [02_REPOSITORY_MAP.md](02_REPOSITORY_MAP.md) (skim)

### Comprehensive Beginner (2 hours)
- [00_INDEX.md](00_INDEX.md)
- [01_EXECUTIVE_SUMMARY.md](01_EXECUTIVE_SUMMARY.md)
- [02_REPOSITORY_MAP.md](02_REPOSITORY_MAP.md)
- [03_SYSTEM_MENTAL_MODEL.md](03_SYSTEM_MENTAL_MODEL.md)

### Complete Intermediate (4 hours)
- All beginner materials
- [04_ARCHITECTURE_OVERVIEW.md](04_ARCHITECTURE_OVERVIEW.md)
- [05_RUNTIME_FLOWS.md] (when available)
- [06_COMPONENT_ARCHITECTURE.md] (when available)

### Complete Advanced (8+ hours)
- All beginner + intermediate materials
- [07_SECURITY_ARCHITECTURE.md]
- [08_CACHING_STRATEGY.md]
- [09_AGENT_EXECUTION.md]
- [10_MULTI_MODEL_GATEWAY.md]
- [11_OBSERVABILITY.md]
- [12_DESIGN_PATTERNS.md]
- [14_ALTERNATIVES_AND_TRADEOFFS.md]
- [15_WEAKNESSES_AND_RISKS.md]

---

## Key Concepts to Understand

By the end of this curriculum, you should understand:

- **RAG (Retrieval-Augmented Generation)** — Retrieve relevant documents, then generate responses
- **Hybrid Retrieval** — Combine vector search, keyword search, and re-ranking
- **Semantic Caching** — Cache based on meaning, not just exact text match
- **Multi-tenancy** — Isolate data and resources per tenant
- **RBAC** — Role-based access control (admin, editor, viewer)
- **JWT** — Stateless authentication with bearer tokens
- **Token Bucket** — Fair rate limiting algorithm with atomic operations
- **LangGraph** — State machine for autonomous agent execution
- **Circuit Breaker** — Resilience pattern to prevent cascading failures
- **OpenTelemetry** — Vendor-agnostic observability/tracing
- **Middleware Chain** — Cross-cutting concerns applied to all requests

---

## Document Status

| Document | Status | Audience |
|----------|--------|----------|
| 00_INDEX.md | ✅ Complete | Everyone |
| 01_EXECUTIVE_SUMMARY.md | ✅ Complete | Beginner |
| 02_REPOSITORY_MAP.md | ✅ Complete | Beginner |
| 03_SYSTEM_MENTAL_MODEL.md | ✅ Complete | Beginner |
| 04_ARCHITECTURE_OVERVIEW.md | ✅ Complete | Intermediate |
| 05_RUNTIME_FLOWS.md | 📋 Planned | Intermediate |
| 06_COMPONENT_ARCHITECTURE.md | 📋 Planned | Intermediate |
| 07_SECURITY_ARCHITECTURE.md | 📋 Planned | Advanced |
| 08_CACHING_STRATEGY.md | 📋 Planned | Advanced |
| 09_AGENT_EXECUTION.md | 📋 Planned | Advanced |
| 10_MULTI_MODEL_GATEWAY.md | 📋 Planned | Advanced |
| 11_OBSERVABILITY.md | 📋 Planned | Advanced |
| 12_DESIGN_PATTERNS.md | 📋 Planned | Reference |
| 13_DATA_ARCHITECTURE.md | 📋 Planned | Reference |
| 14_ALTERNATIVES_AND_TRADEOFFS.md | 📋 Planned | Reference |
| 15_WEAKNESSES_AND_RISKS.md | 📋 Planned | Reference |
| 16_TESTING_STRATEGY.md | 📋 Planned | Reference |
| 17_LEARNING_CURRICULUM.md | 📋 Planned | Reference |
| 18_GLOSSARY.md | 📋 Planned | Reference |
| 19_FAQ.md | 📋 Planned | Reference |
| 20_RECOMMENDED_DEEP_DIVES.md | 📋 Planned | Reference |

---

## Notes for Readers

### This is NOT a step-by-step tutorial
This documentation is designed to help you **understand the system deeply**, not to guide you through implementation. You won't find copy-paste code snippets (except for illustration). Instead, you'll find:
- System design rationale
- Architectural patterns and why they were chosen
- Data flow and request processing
- Tradeoffs and design decisions
- How different components interact

### All features are optional by default
The system is designed so that security, caching, agents, and other features are **disabled by default**. This is documented throughout so you understand the system is non-breaking and can be extended incrementally.

### Code is the source of truth
When reading this documentation, have the actual code open. These documents explain the code, but the code itself is authoritative. If you find a discrepancy, check the code first.

### Questions to ask yourself
After reading each section, ask:
- What problem does this solve?
- Why was this approach chosen?
- What are the alternatives?
- What are the tradeoffs?
- What could go wrong?
- How would I extend this?

---

## Feedback

These materials are comprehensive but may have gaps or errors. If you find:
- Incorrect information
- Confusing explanations
- Missing topics
- Typos or formatting issues

Please note them and provide feedback.

---

## Start Reading

👉 **Begin with [00_INDEX.md](00_INDEX.md)** to see the full reading guide.

Then, based on your role and interests:
- **Beginner**: Read Executive Summary → Repository Map → System Mental Model
- **Architect**: Read Overview → Architecture → Alternatives → Weaknesses
- **Security**: Read Security Architecture → Weaknesses (security section)
- **Performance**: Read Caching → Gateway → Observability sections

Happy learning! 🚀
