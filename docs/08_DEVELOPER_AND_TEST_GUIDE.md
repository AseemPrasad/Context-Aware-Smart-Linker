# CASL — Developer Onboarding & Testing Guide

This guide covers setting up a local development environment, running test suites, and adhering to code quality standards for CASL.

---

## 1. Local Environment Setup

### Prerequisites
- Python 3.11, 3.12, or 3.14
- Google Chrome (for testing the Manifest V3 extension)
- Docker & Docker Compose (optional, for running Redis and Qdrant locally)

### Installation
```bash
# Clone the repository
git clone https://github.com/your-username/casl.git
cd casl

# Create and activate virtual environment
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## 2. Running Test Suites

CASL maintains an extensive test suite across 5 core verification files:

| Test File | Focus Area | Test Count |
| :--- | :--- | :---: |
| `tests/test_finance_domain.py` | Structure chunker, ticker stop-words, citation math | 3 |
| `tests/test_tenant_security.py` | Multi-tenant vector store partitioning & isolation | 3 |
| `tests/test_saas_billing.py` | UsageMeter credit consumption and hard-cap checks | 3 |
| `tests/test_production_readiness.py` | Redis fallback, SEC cleaning, OIDC claims, remote encoders | 4 |
| `tests/test_institutional_readiness.py` | Bounded streaming reader, JWKS RS256 signature rejection, Stripe webhooks | 3 |

### Execute All Tests
```bash
python -m unittest tests/test_finance_domain.py tests/test_tenant_security.py tests/test_saas_billing.py tests/test_production_readiness.py tests/test_institutional_readiness.py
```
*Expected Result:*
```text
Ran 16 tests in 0.082s — OK
```

---

## 3. Verifying FastAPI Route Loading

To confirm that all 37 modular endpoints are wired and importable without runtime dependency errors:
```bash
python -c "from backend.main import app; print('FastAPI loaded cleanly with', len(app.routes), 'routes')"
```
*Expected Result:*
```text
FastAPI loaded cleanly with 37 routes
```

---

## 4. Testing the Chrome Extension Locally

1. Open Google Chrome and visit `chrome://extensions/`.
2. Enable **Developer mode** (toggle in upper right).
3. Click **Load unpacked** and select the repository root folder (`CASL/`).
4. Click the extension details $\rightarrow$ **Extension options** to open `options.html`.
5. Enter `http://localhost:8000` as the Gateway URL and `test_tenant` as the Tenant ID.
6. Open any financial article or SEC filing (e.g. on [SEC.gov](https://www.sec.gov)) and highlight text to test the overlay.

