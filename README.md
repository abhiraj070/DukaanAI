# DukaanAI 🏪🤖

> **Agentic Predictive Business Intelligence & Decision Intelligence Platform for India's Small Businesses**

DukaanAI is an agentic platform designed specifically for Indian micro and small retail businesses (starting with neighbourhood kirana stores). It turns everyday business data—sales, inventory, purchases, expenses, customer credit (*udhar*), and supplier documents—into verified facts, predictive forecasts, scenario simulations, and owner-approved operational decisions.

---

## Architecture Overview

```text
Next.js (React + TypeScript + Tailwind CSS)
    ↓
FastAPI Backend (Authentication + Tenant Context)
    ↓
PydanticAI Business Agent (Single Orchestrator)
    ↓
Typed, Allowlisted Tool Adapters
    ↓
Deterministic Domain Services (Analytics, Inventory, Udhar Ledger, Simulation, Optimization, Festivals)
    ↓
PostgreSQL (Neon) + pgvector + Supabase Object Storage
```

- **Domain services calculate authoritative numbers:** The LLM interprets questions and explains results, but backend services compute all financial and inventory values.
- **Append-only Udhar ledger:** Balances derive from confirmed charges and repayment allocations; receivables are not cash, repayments are not revenue.
- **Strict tenant isolation:** All reads, writes, vector searches, and conversation histories are strictly filtered by authenticated `business_id`.
- **Human confirmation:** Ingestion extractions and operational actions (purchase orders, reminders) produce drafts requiring owner confirmation.

---

## Repository Structure

```text
DukaanAI/
├── backend/                  # Python FastAPI modular monolith
│   ├── app/
│   │   ├── api/v1/           # API v1 endpoints and master router
│   │   │   └── endpoints/
│   │   │       └── health.py # Health endpoints (/health, /api/v1/health)
│   │   ├── core/             # Configuration, error envelopes, and middleware
│   │   │   ├── config.py     # Pydantic Settings
│   │   │   ├── errors.py     # Uniform API error responses
│   │   │   └── middleware.py # Request ID (X-Request-ID) and timing
│   │   └── main.py           # FastAPI entrypoint and CORS
│   ├── tests/                # Pytest async test suite
│   ├── pyproject.toml        # Backend configuration and dependencies
│   ├── requirements.txt      # Production requirements
│   └── requirements-dev.txt  # Dev requirements (pytest, ruff, httpx)
├── frontend/                 # Next.js 15+ App Router frontend
│   ├── src/
│   │   ├── app/              # App router pages and layouts
│   │   ├── components/       # UI components
│   │   └── lib/              # API client and connectivity utilities
│   ├── package.json          # Node dependencies
│   └── tsconfig.json         # TypeScript configuration
├── .env.example              # Environment variables template
├── architecture.md           # Approved Technical Architecture and ADRs
├── memory.md                 # Project Memory and Session Log
├── phases.md                 # Implementation Phases and Quality Gates
├── PRD.md                    # Product Requirements Document
└── README.md                 # Project documentation and quickstart
```

---

## Prerequisites

- **Python:** 3.12 (or 3.11+)
- **Node.js:** v20+ (tested on v22)
- **Package Manager:** `pnpm` (or `npm`)

---

## Quickstart

### 1. Environment Setup

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

### 2. Backend Setup

From the repository root:

```bash
# Create and activate virtual environment
py -3.12 -m venv backend/.venv

# Windows PowerShell:
backend\.venv\Scripts\Activate.ps1
# Linux/macOS:
source backend/.venv/bin/activate

# Install dependencies (including editable package and dev tools)
pip install -r backend/requirements-dev.txt
pip install -e backend

# Run linting and code formatting check
ruff check backend
ruff format --check backend

# Run automated tests
pytest backend

# Start development server (runs on http://127.0.0.1:8000)
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 3. Frontend Setup

In a separate terminal:

```bash
cd frontend

# Install dependencies
pnpm install

# Run type check and lint
pnpm lint

# Start Next.js development server (runs on http://localhost:3000)
pnpm dev
```

---

## API Contract & Standards

### Health Check

- `GET /health` and `GET /api/v1/health`
- Returns operational status, app metadata, UTC timestamp, and default timezone (`Asia/Kolkata`):
```json
{
  "status": "ok",
  "app": "DukaanAI",
  "version": "0.1.0",
  "environment": "development",
  "timestamp": "2026-11-14T07:55:00.000Z",
  "timezone": "Asia/Kolkata",
  "request_id": "req_84f9b8c9e012"
}
```

### Request ID Tracing

Every request generates or preserves an `X-Request-ID` header. The request ID is automatically included in:
- Response HTTP headers: `X-Request-ID`
- Processing time header: `X-Process-Time-Ms`
- Error response envelopes
- Health check responses

### Standard Error Response Envelope

All API errors return a uniform structure:

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Resource not found",
    "details": null,
    "request_id": "req_84f9b8c9e012"
  }
}
```

Standard error codes include `BAD_REQUEST`, `UNAUTHORIZED`, `FORBIDDEN`, `NOT_FOUND`, `CONFLICT`, `VALIDATION_ERROR`, and `INTERNAL_SERVER_ERROR`.

---

## Quality Gates & Verification

Each implementation phase must strictly pass acceptance criteria before proceeding:
- **Phase 0 (Foundation):** Clean startup, `/health` endpoint verified, frontend reaches backend, zero committed secrets.
- **Phase 1 (Domain Model & Multi-Tenancy):** Migrations run from scratch, cross-tenant isolation tested, NUMERIC currency.
- **Phase 2 (Core Domain Services):** Deterministic logic tested independently of LLM.
- **Phases 3–13:** Ingestion, Analytics, Udhar Ledger, Forecasting, Simulation, Optimization, Festivals, RAG, PydanticAI Copilot, Workflows, Hardening.

Refer to `phases.md` for complete delivery gate definitions.
