# DukaanAI — Implementation Phases and Delivery Gates

**Version:** 2.0  
**Purpose:** Controlled implementation sequence for Antigravity/Codex.  
**Rule:** Complete and verify each phase before proceeding. Generated code alone is not proof of completion.

## Coding-agent operating rules

1. Read `PRD.md`, `architecture.md` and `memory.md` before editing.
2. Inspect repository, git status, manifests, tests and conventions first.
3. Preserve working code; do not rewrite wholesale without approval.
4. State a short plan, dependencies, risks and likely files before each phase.
5. Implement only the current phase; do not silently skip acceptance gates.
6. Run tests, lint/type checks, migrations and local smoke tests.
7. Report exact commands and outcomes; never fabricate test results or integration status.
8. Update `memory.md` after meaningful sessions.
9. Record architectural changes in `architecture.md` as ADRs.
10. Consult current official PydanticAI documentation and pin the version actually tested.

## Phase map

| Phase | Name | Outcome |
|---|---|---|
| 0 | Repository discovery and foundation | Reproducible app skeleton |
| 1 | Domain model, database and tenant security | Relational foundation |
| 2 | Core domain services and typed contracts | Business rules independent of UI/agent |
| 3 | Data Centre and ingestion | Reviewable, traceable records |
| 4 | Core analytics | Trusted historical metrics |
| 5 | Udhar Management | Auditable customer credit ledger |
| 6 | Predictive inventory | Forecasts and reorder recommendations |
| 7 | What-if simulation | Explainable scenario comparison |
| 8 | Profit optimization | Budget-constrained recommendations |
| 9 | Festival intelligence | Evidence-based seasonal planning |
| 10 | RAG retrieval tool | Tenant-safe document search |
| 11 | PydanticAI and Decision Lab | Typed tool-using copilot |
| 12 | Operational workflows | Owner-approved actions |
| 13 | Hardening and release | Secure, tested demo/product |

## Phase 0 — Repository discovery and foundation

**Tasks**
- Inspect repository, manifests, environment files, tests and git status.
- Confirm runtimes/package managers.
- Preserve or establish Next.js + React + TypeScript frontend and FastAPI backend.
- Define API contract strategy.
- Add `.env.example`, README setup, formatter/linter/test commands.
- Add backend health endpoint and frontend connectivity check.
- Define API errors and request IDs.

**Gate**
- Frontend/backend start locally; `/health` works; frontend reaches backend; clean setup is documented; no secrets committed.

**Avoid**
- Adding agents/vector DB/forecasting packages before the skeleton works.

## Phase 1 — Domain model, database and tenant security

**Tasks**
- Configure PostgreSQL and migrations.
- Implement users, businesses, memberships, products, suppliers, sales/purchases/expenses.
- Create customers and udhar tables early, even if UI arrives later.
- Resolve business membership server-side.
- Add tenant-scoped repository patterns, indexes and constraints.
- Implement inventory movements and audit log foundation.
- Isolate demo fixtures.

**Gate**
- Migrations run from empty DB; cross-tenant tests cover products, customers, ledger and documents; currency uses Decimal/NUMERIC; inventory reconciles to movements.

**Avoid**
- Trusting client `business_id`; mutating stock without movement; float currency.

## Phase 2 — Core domain services and typed contracts

**Tasks**
- Define Pydantic schemas for analytics, inventory, udhar, simulation, optimization and actions.
- Implement repositories and deterministic domain services.
- Keep business logic out of routes and agent tool adapters.
- Define evidence result convention: source IDs, date window, method, assumptions, freshness and warnings.
- Add Decimal-safe helpers and deterministic fixtures.

**Gate**
- Services are callable without an LLM; outputs validate; tenant scope is enforced; key formulas have hand-checked tests.

## Phase 3 — Data Centre and ingestion

**Tasks**
- Validate uploads and store originals.
- Parse CSV/XLSX/PDF; use OCR/multimodal extraction when needed.
- Define Pydantic candidate schemas for invoices, sales, expenses, customer credit entries and repayments.
- Validate totals, dates, units, entity matches and duplicate fingerprints.
- Build review/edit/confirm UI.
- Post confirmed records transactionally and idempotently.
- Preserve source document/page/row/snippet/confidence/extraction version/reviewer.

**Gate**
- Explicit success/failure for supported file types; udhar ledger image produces drafts only; ambiguous customer/direction flagged; retry creates no duplicates; provenance visible.

**Avoid**
- Treating OCR confidence as approval or silently dropping invalid rows.

## Phase 4 — Core business analytics

**Tasks**
- Implement revenue, COGS, gross profit, margin, units, product ranking, inventory valuation, expenses and turnover.
- Integrate receivables KPI only after Phase 5 is implemented.
- Define date/timezone semantics.
- Build dashboard and show data coverage/missing-cost warnings.
- Reuse same service functions for future agent tools.

**Gate**
- Tests cover returns/adjustments, empty data and date boundaries; dashboard matches fixtures; revenue is never labelled profit; missing cost yields unavailable profit.

## Phase 5 — Udhar Management

**Tasks**
- Customer directory, archive and duplicate warnings.
- Credit accounts and optional credit limits.
- Confirmed charge/credit ledger entries.
- Full/partial repayments with cash/UPI/bank/other modes.
- Repayment-to-charge allocations, including multi-charge allocations.
- Owner-confirmed opening-balance entries.
- Derived outstanding balance and due-date aging.
- Customer ledger with running balance.
- Statement generation/export.
- Reminder draft/copy only; no outbound send without real integration and consent.
- Reversal/adjustment workflows and audit events.

**Gate**
- Credit increases outstanding; partial/full repayment reduces it; allocations cannot exceed repayment or open charge; statement reconciles; aging handles missing due dates; repayments are not revenue; duplicate requests do not duplicate; cross-tenant tests pass; UI supports add credit, record repayment and inspect ledger.

**Avoid**
- Manually editable authoritative balance; destructive ledger edits; receivables-as-cash; unconsented reminders.

## Phase 6 — Predictive Inventory Intelligence

**Tasks**
- Implement naive, rolling mean and weekday-aware baselines.
- Select method based on history/data quality.
- Calculate days cover, stockout date, reorder point and quantity.
- Account for supplier lead time, safety stock and incoming POs.
- Respect MOQ/pack size only when known.
- Return method, training window, assumptions and quality.
- Persist forecast run/model version.

**Gate**
- Deterministic tests for sparse history, zero demand, zero stock, incoming orders and lead-time boundaries; no unsupported confidence intervals; reorder examples hand-verified.

## Phase 7 — What-if Simulation

**Tasks**
- Define typed scenario inputs/outputs.
- Support price, discount, cost, demand, delay, purchase, festival and cash/collection scenarios.
- Separate observed baseline from user assumptions.
- Return deltas, constraints, warnings and model version.
- Save scenarios and build comparison UI.
- Do not assume price elasticity without an explicit model/assumption.

**Gate**
- Deterministic tests for each scenario; receivables not cash by default; invalid/infeasible inputs rejected; assumptions visible in UI.

## Phase 8 — Profit Optimization

**Tasks**
- Implement product profitability and turnover analysis.
- Build budget-constrained procurement optimizer using SciPy or transparent deterministic fallback.
- Consider on-hand/incoming stock, forecast demand, supplier cost, MOQ/pack size and budget.
- Keep current cash separate from receivables and assumed collections.
- Define objective and constraints; return alternatives and explanation.

**Gate**
- Never exceeds budget; respects known pack sizes/MOQ; surfaces missing inputs; reproducible and hand-verified.

## Phase 9 — Festival Demand Intelligence

**Tasks**
- Create editable festival calendar with region/category mapping.
- Compare historical festival windows with comparable baseline periods.
- Calculate uplift only with sufficient history.
- Otherwise allow clearly labelled user-defined assumptions.
- Feed festival context into forecasts/simulations with provenance.

**Gate**
- Historical uplift reproducible; insufficient history labelled as assumption; dates/mappings editable.

## Phase 10 — RAG knowledge retrieval

**Tasks**
- Enable pgvector.
- Chunk documents by section while preserving page/table context.
- Embed through provider abstraction; evaluate Hindi/English/Hinglish.
- Store tenant, document, page, type, timestamp and embedding version metadata.
- Implement mandatory tenant-filtered retrieval and optional hybrid ranking.
- Return source/page citations; treat retrieved text as untrusted.
- Create a small retrieval evaluation set.

**Gate**
- Relevant test retrieval; zero cross-tenant chunks; source/page citations; matching embedding dimensions; idempotent re-indexing.

**Avoid**
- ArangoDB without graph traversal need; LangChain by default; raw vector access for agent.

## Phase 11 — PydanticAI orchestrator and AI Decision Lab

**Tasks**
- Read current PydanticAI docs and pin a tested version/provider combination.
- Implement one `DukaanBusinessAgent`.
- Inject typed dependencies containing trusted business context and service interfaces.
- Use typed final output contract.
- Implement narrow tool adapters for analytics, inventory, udhar, forecast, simulation, optimization, festivals and RAG.
- Add draft/preparation tools only; writes go through separate authorized endpoints.
- Configure timeouts, retries, token/usage limits and safe errors.
- Persist tenant-scoped conversations/tool traces with retention rules.
- Return answer, evidence, assumptions, limitations and proposed actions.
- Support Hindi/Hinglish/English.

**Gate**
- Representative questions select expected tools; arguments/results validate; numeric claims match outputs; prompt injection cannot alter permissions; unsupported questions abstain/clarify; no action commits without confirmation; tenant isolation covers history and tools.

**Avoid**
- Arbitrary SQL/code/shell/HTTP tools; premature multi-agent swarm; chat history as authorization.

## Phase 12 — Operational workflows

**Tasks**
- Create/edit/approve/cancel PO drafts.
- Preserve recommendation, owner-edited quantities and unit-cost source.
- Generate customer statements and reminder drafts.
- Add confirmation UX for ledger entries/reversals.
- Record audit events and idempotency keys.
- Keep external supplier submission, payments and messaging out of scope unless separately approved.

**Gate**
- PO lifecycle auditable; stock changes only on receipt; statements reconcile; reminders labelled unsent; corrections are compensating entries; duplicate actions do not duplicate.

## Phase 13 — Hardening, evaluation and release

**Tasks**
- Run backend unit/integration tests, frontend typecheck/lint/build and clean migrations.
- Review auth, tenant isolation, upload validation, secrets, CORS and rate limits.
- Evaluate extraction, retrieval, tool selection, groundedness, multilingual intent and prompt injection.
- Backtest forecasts against naive baselines.
- Test udhar invariants, partial repayments, allocations, aging and statements.
- Review responsive UX/accessibility.
- Add monitoring for API errors, ingestion jobs, agent latency/token use and ledger failures.
- Document deployment, migration, backup and retention.
- Create isolated demo seed/reset scripts.
- Update README, OpenAPI, architecture and memory.

**Gate**
- Clean setup documented; required checks pass; no critical tenant/ledger issue; limitations documented; seeded end-to-end demo works.

## Cross-phase quality gates

Every phase maintains tenant context, Pydantic validation, calculation/ledger tests, Decimal/NUMERIC currency, secrets hygiene, no fabricated data/integrations, clear UI states and updated docs.

## Handoff template

Append to `memory.md` after each phase:

```md
## Phase N — <name>
- Status: complete | blocked | in progress
- Date:
- Summary:
- Decisions:
- Files created/modified:
- Migrations:
- Commands run:
- Test results:
- Known issues:
- Deferred work:
- Next phase:
```
