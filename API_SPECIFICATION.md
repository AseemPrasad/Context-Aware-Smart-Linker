# CASL — API Specification & Endpoint Reference

The CASL FastAPI Backend exposes **37 active endpoints** across Financial Due Diligence, SaaS Billing, Document Ingestion, Hybrid Search, Observability, and Healthchecks.

- **Base URL**: `http://localhost:8000` (Local) / `https://api.yourfirm.com` (Production)
- **Interactive Documentation**: Swagger UI at `/docs`, ReDoc at `/redoc`

---

## 1. Financial Due Diligence Endpoints

### 1.1 `POST /api/v1/finance/explain`
The primary in-situ research endpoint invoked by the Chrome extension when text is highlighted.

- **Authentication**: Optional Bearer token (required when `AUTH_ENABLED=true`).
- **Credit Cost**:
  - `0 credits` if resolved via Semantic Cache hit.
  - `1 credit` for live Hybrid RAG retrieval and synthesis.

#### Request Headers
```http
Content-Type: application/json
Authorization: Bearer <token_or_jwt>
```

#### Request Body
```json
{
  "term": "Negative Pledge",
  "surrounding_context": "The Borrower covenants that neither it nor any Subsidiary will create or permit to exist any Lien on any property or assets now owned or hereafter acquired under Section 7.02.",
  "page_title": "Credit Agreement - Apple Inc. (10-Q)",
  "tenant_id": "firm_alpha",
  "strict_citations": true
}
```

#### Response (200 OK)
```json
{
  "term": "Negative Pledge",
  "executive_summary": "A negative pledge clause prevents a borrower from pledging its assets as collateral to other creditors, protecting unsecured lenders against structural subordination.",
  "historical_context": "Commonly incorporated into revolving credit facilities following landmark leveraged buyout disputes.",
  "risk_implications": "Breaching Section 7.02 triggers an immediate Event of Default, permitting syndicated lenders to accelerate principal repayment.",
  "citations": [
    {
      "source_document": "Credit Agreement (Section 7.02)",
      "filing_accession": "0000320193-23-000106",
      "ticker": "AAPL",
      "form_type": "10-Q",
      "section": "Section 7.02",
      "deep_link": "https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm",
      "relevance_score": 0.94
    }
  ],
  "confidence_score": 0.96,
  "cached": false
}
```

#### Response (402 Payment Required)
Returned when the tenant's monthly research credit quota is exhausted.
```json
{
  "detail": "Monthly credit quota exceeded (5000/5000). Please upgrade plan."
}
```

---

### 1.2 `GET /api/v1/finance/health`
Healthcheck for the financial due diligence subsystem.
```http
GET /api/v1/finance/health
```
#### Response (200 OK)
```json
{
  "status": "healthy",
  "domain": "finance",
  "hybrid_search_ready": true,
  "reranker_ready": true
}
```

---

## 2. SaaS Billing & Monetization Endpoints

### 2.1 `GET /api/v1/billing/usage/{tenant_id}`
Returns customer consumption telemetry, remaining credits, and active seats.

```http
GET /api/v1/billing/usage/firm_alpha
```
#### Response (200 OK)
```json
{
  "tenant_id": "firm_alpha",
  "plan": "professional",
  "seats_allocated": 10,
  "seats_active": 4,
  "credits_quota": 5000,
  "credits_used": 1420,
  "credits_remaining": 3580,
  "percent_consumed": 28.4
}
```

---

### 2.2 `POST /api/v1/billing/upgrade/{tenant_id}`
Admin endpoint to upgrade workspace tier and expand monthly credit allowances.

```http
POST /api/v1/billing/upgrade/firm_alpha?target_plan=enterprise
```
#### Response (200 OK)
```json
{
  "status": "upgraded",
  "tenant_id": "firm_alpha",
  "new_plan": "enterprise",
  "new_quota": 50000,
  "seats_allocated": 100
}
```

---

### 2.3 `POST /api/v1/billing/stripe/webhook`
Webhook listener for automated Stripe billing events.

- **Headers**: `stripe-signature: t=...,v1=...`
- **Supported Events**:
  - `checkout.session.completed`: Expands workspace tier and credits.
  - `invoice.paid`: Resets monthly query allowances on cycle renewal.
  - `customer.subscription.deleted`: Downgrades workspace on cancellation.

#### Response (200 OK)
```json
{
  "status": "processed",
  "event_type": "checkout.session.completed"
}
```

---

## 3. Core Ingestion & Retrieval Endpoints

### 3.1 `POST /api/v1/ingest`
Ingests, chunks, embeds, and indexes arbitrary text or deal room documents under a specific tenant partition.

#### Request Body
```json
{
  "document_id": "credit_agreement_2026",
  "text": "The Borrower shall not incur any funded debt exceeding 3.5x Consolidated EBITDA...",
  "tenant_id": "firm_alpha",
  "metadata": {
    "deal_code": "PROJECT_TITAN",
    "confidential": "true"
  }
}
```

#### Response (200 OK)
```json
{
  "status": "indexed",
  "document_id": "credit_agreement_2026",
  "chunks_created": 4,
  "tenant_id": "firm_alpha"
}
```

---

### 3.2 `POST /api/v1/search`
Pure dense semantic vector search restricted to a single tenant partition.

#### Request Body
```json
{
  "tenant_id": "firm_alpha",
  "query": "What is the maximum allowed leverage ratio?",
  "top_k": 5
}
```

#### Response (200 OK)
```json
{
  "hits": [
    {
      "document_id": "credit_agreement_2026",
      "passage": "The Borrower shall not incur any funded debt exceeding 3.5x Consolidated EBITDA...",
      "score": 0.892,
      "metadata": { "deal_code": "PROJECT_TITAN" }
    }
  ],
  "total_hits": 1,
  "latency_ms": 14.2,
  "cached": false
}
```

---

### 3.3 `POST /api/v1/hybrid_search`
Fuses dense vector nearest-neighbors with sparse BM25 keyword rankings via Reciprocal Rank Fusion (RRF).

---

## 4. Observability & Telemetry Endpoints

### 4.1 `GET /health`
Global gateway health check.
```json
{ "status": "ok" }
```

### 4.2 `GET /cache/stats`
Telemetry statistics for the two-tier semantic cache (exact hash and vector hit ratios).
```json
{
  "exact_hits": 182,
  "vector_hits": 49,
  "misses": 310,
  "total_queries": 541,
  "hit_ratio": 0.427
}
```

### 4.3 `GET /security/stats`
Rate limiter and security guardrail metrics per tenant.

### 4.4 `GET /telemetry/metrics`
Token budget consumption and OpenTelemetry Prometheus metrics exported in JSON.

