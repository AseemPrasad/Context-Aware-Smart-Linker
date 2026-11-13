# CASL — SEC EDGAR Ingestion Pipeline

The SEC EDGAR ingestion pipeline (`backend/tasks/sec_edgar_pipeline.py`) continuously indexes public corporate disclosures into the `public_markets` shared tenant partition.

---

## 1. Pipeline Architecture

```mermaid
flowchart LR
    A[SEC EDGAR Atom Feed] -->|Poll every 15 min| B[Celery Beat Task]
    B --> C[SecEdgarPipeline]
    C --> D[SecDocumentFetcher]
    D -->|Bounded 64KB Streams| E[Clean HTML & Strip iXBRL]
    E --> F[Isolate Item 1A Risk Factors & Item 7 MD&A]
    F --> G[FinancialDocumentParser Chunker]
    G --> H[get_encoder Dense Embeddings]
    H --> I[VectorStore / Qdrant Ingest]
```

---

## 2. Bounded Streaming Reader (OOM Protection)

Full SEC 10-K filings can reach 20MB to 50MB of raw text. Attempting to buffer multiple full filings simultaneously inside a single Celery worker process on standard cloud VMs causes Linux Out-Of-Memory (OOM) kills.

`SecDocumentFetcher` solves this with a **bounded streaming buffer**:
```python
total_read = 0
chunks = []
while total_read < max_bytes:  # 1MB bounded ceiling
    chunk = response.read(65536)  # 64KB bounded chunks
    if not chunk:
        break
    chunks.append(chunk)
    total_read += len(chunk)
```
- Restricts total memory allocated per document to a flat 1MB ceiling.
- Discards non-essential exhibit lists, inline stylesheets, and oversized balance sheet tables.
- Guarantees worker memory usage remains stable under heavy batch loads.

---

## 3. Regulatory Compliance & Rate Limiting

The SEC strictly monitors automated web traffic and blocks IP addresses that violate its terms of use:
1. **Corporate User-Agent**:
   - The SEC requires automated traffic to supply a specific User-Agent format: `SampleCompany AdminContact@<domain>.com`.
   - CASL configures this via `SEC_EDGAR_USER_AGENT`, defaulting to `CASLResearchPlatform compliance@casl-research.com`.
2. **Rate Limit Conformance**:
   - The SEC enforces a maximum ceiling of **10 requests per second**.
   - Celery tasks batch filing ingestion and serialize requests with rate-limiting pauses, preventing IP bans.

