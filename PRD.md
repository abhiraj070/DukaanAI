# DukaanAI — Product Requirements Document

**Version:** 2.0  
**Status:** Revised product baseline  
**Market:** Indian micro and small retailers, initially kirana stores  
**Positioning:** Predictive Business Intelligence & Decision Intelligence Platform

## 1. Product vision

DukaanAI turns everyday business data—sales, inventory, purchases, expenses, customer credit (udhar), supplier documents and owner-entered notes—into verified business facts, forecasts, simulations and actionable recommendations.

The product answers five questions:

1. **What happened?** Sales, costs, margins, expenses, inventory and receivables.
2. **What is likely to happen?** Demand, stockouts, seasonal changes and collections.
3. **What if I make this decision?** Pricing, purchasing, discounts, supplier and cash-flow scenarios.
4. **What should I do next?** Profitable, feasible actions with evidence.
5. **Who owes me money?** Customer-wise udhar, overdue balances and repayment history.

The flagship experience is the **AI Decision Lab**: a natural-language interface orchestrated by one PydanticAI agent using a controlled set of typed tools. Deterministic backend services—not the LLM—calculate authoritative numbers.

**Product promise:** From business data to better business decisions.

## 2. Target users and jobs

### Primary persona: Kirana / neighbourhood retail owner
- Manages sales, purchases, stock, expenses and udhar using notebooks, spreadsheets, bills or basic POS exports.
- Has limited time and analytical expertise.
- May prefer Hindi, Hinglish or English.
- Needs practical recommendations, not BI jargon.
- Must retain control over credit adjustments, purchase orders and financial actions.

### Secondary persona: Store manager / accountant
- Enters and reconciles daily transactions.
- Imports invoices and ledgers.
- Reviews alerts, statements and purchase-order drafts.
- Needs traceability and correction workflows.

### Core jobs to be done
- Identify best-selling, profitable, slow-moving and stockout-risk products.
- Know when and how much to reorder.
- Understand revenue, gross profit, expenses and cash constraints.
- Record customer credit sales and partial/full repayments.
- Track outstanding udhar, overdue balances and customer history.
- Compare decisions before committing money.
- Prepare for Indian festivals and seasonal demand.
- Convert paper/PDF/image/text information into usable records.

## 3. Product principles

1. **Evidence before explanation:** recommendations expose source facts, date windows, calculations and assumptions.
2. **Deterministic numbers:** revenue, profit, stock, udhar balances, forecasts and optimization outputs come from backend services.
3. **Ledger integrity:** financial activity is append-only or corrected through explicit reversing/adjustment entries.
4. **Human approval:** extracted records are drafts until reviewed; consequential actions require explicit confirmation.
5. **Tenant isolation:** every business-owned record and retrieval is scoped to authenticated `business_id`.
6. **Provenance:** imported records retain source document/page/row, extraction version and confirmation status.
7. **Honest uncertainty:** distinguish observed facts, calculated metrics, forecasts and scenario assumptions.
8. **Graceful cold start:** disclose insufficient history and use transparent baselines or owner-defined assumptions.
9. **Indian context:** INR, `Asia/Kolkata`, Hindi/Hinglish/English and an editable festival calendar.
10. **One coherent product:** inventory, udhar, simulation, profitability and festival intelligence share one data model.
11. **Agent boundaries:** PydanticAI orchestrates typed tools; domain services own business rules.
12. **No fabricated integrations:** unsupported POS, banking, supplier, WhatsApp or payment integrations are not represented as working.

## 4. Scope and capabilities

### 4.1 Business data workspace
- Configure a business/store, region, currency and timezone.
- Maintain products, categories, units, selling prices, cost prices, stock, reorder settings and suppliers.
- Maintain customers and optional credit preferences.
- Record sales, purchases, expenses, inventory movements, udhar entries and repayments.
- Import CSV/XLSX with column mapping, preview, validation and duplicate detection.
- Show data freshness, import status and data-quality warnings.

### 4.2 AI Data Ingestion Centre
Accept:
- Natural-language text in English, Hindi or Hinglish.
- Images: invoices, receipts, expense bills and handwritten ledgers.
- PDFs: invoices, supplier price lists, reports and catalogues.
- CSV/XLSX structured imports.

Workflow:
1. Upload or submit input.
2. Identify document/input type.
3. Extract candidate structured records.
4. Validate schema, totals, dates, units and entity matches.
5. Present a review screen with confidence and source evidence.
6. Owner confirms or edits.
7. Persist transactionally and idempotently.
8. Retain original file and provenance.

Udhar extraction creates draft transactions only. Ambiguous customer identity or debit/credit direction must be resolved by the owner.

### 4.3 Business dashboard
Show configurable date ranges and KPI definitions:
- Gross sales/revenue.
- COGS, where cost data exists.
- Gross profit and gross margin.
- Units sold and transaction count.
- Inventory value with valuation method disclosed.
- Low-stock and stockout-risk products.
- Top products by revenue, units and gross profit.
- Slow-moving products.
- Expense trends and anomalies.
- Total customer receivables / outstanding udhar.
- Overdue receivables and collections received in period.

Never label revenue as profit. Receivables are not cash. If cost data is missing, gross profit is unavailable rather than guessed.

### 4.4 Predictive Inventory Intelligence
For each product show:
- Historical demand and data coverage.
- Forecast horizon (7/14/30 days when supported).
- Forecast demand and quality indicator.
- Days of cover and estimated stockout date.
- Supplier lead time.
- Safety stock and reorder point.
- Suggested reorder quantity and estimated procurement cost.

Baseline formulas:

`Days of cover = current usable stock / average daily demand`

`ROP = expected demand during lead time + safety stock`

For varying forecasts:

`ROP = sum(forecast demand over lead-time days) + safety stock`

Order quantity considers on-hand stock, confirmed incoming stock, target coverage, pack size/MOQ when known, and budget if provided. Avoid double-counting incoming orders.

Use naive/rolling-average baselines first, weekday-aware baselines where data permits, and advanced forecasting only when enough observations exist. Expose method and data sufficiency.

### 4.5 What-if Simulation Engine
Support:
- Selling price and discount changes.
- Supplier cost changes.
- Demand changes.
- Supplier delivery delays.
- Additional inventory purchases.
- Festival demand assumptions.
- Udhar collection-rate/timing assumptions.
- Cash availability scenarios based on receivables, payables and planned procurement.

Each simulation returns baseline, assumptions, outputs, delta, constraints/warnings and calculation version.

Do not assume demand remains constant after a price change unless explicitly selected. If elasticity is unknown, use user-defined assumptions or scenario ranges. Expected udhar collections are estimates, not guaranteed cash.

### 4.6 Profit Optimization
Provide decision support for:
- Product gross margin and contribution.
- High-volume/low-margin opportunities.
- Low-turnover and ageing inventory.
- Discount/bundle scenarios.
- Procurement allocation under a stated budget.
- Supplier price/lead-time comparisons where data exists.
- Working-capital awareness using receivables and known supplier obligations.

Optimization objective and constraints must be explicit. Example:

`maximize expected gross contribution from selected purchase quantities`

Subject to budget, supplier availability/MOQ/pack sizes, storage capacity if configured, forecast demand/target coverage, on-hand stock and incoming stock.

Do not present an unconstrained optimum as guaranteed profit. Do not count outstanding udhar as available cash unless evaluating a clearly labelled collection scenario.

### 4.7 Festival Demand Intelligence
- Maintain editable festival/event calendar with date, region and relevant categories.
- Compare product/category sales around historical festival windows with a comparable baseline.
- Calculate uplift only when sufficient historical data exists.
- Feed evidence-based uplift into forecasts and procurement simulations.
- Without historical evidence, use a clearly labelled owner-defined scenario assumption; never invent uplift percentages.

### 4.8 Udhar Management — first-class module

#### Customer ledger
- Create, edit and archive customers.
- Store only necessary data: display name, optional phone, notes and reminder preferences/consent.
- Show customer-wise ledger and derived outstanding balance.
- Support opening balances as dated, sourced, owner-confirmed entries.
- Search customers and warn about possible duplicates.

#### Credit entries
- Record credit sale/udhar charge against a customer.
- Capture amount, date, optional due date, description/reference and source.
- Optionally link to a sale/invoice without double-counting.
- Never infer that every sale is on credit.

#### Repayments
- Record full and partial repayments.
- Capture amount, date, payment mode (cash, UPI, bank transfer, other), optional reference and notes.
- Allocate a repayment to one or more open credit entries, or leave unallocated under explicit policy.
- Prevent allocation beyond repayment amount or open receivable.
- Correct errors through compensating entries, not destructive edits.
- A repayment is a collection against receivables, not new sales revenue.

#### Outstanding and aging
- Derive balance from confirmed ledger entries and repayment allocations.
- Show customer-wise and total outstanding.
- Initial configurable aging buckets: not due, 1–7, 8–30, 31–60 and 60+ days overdue.
- Distinguish due date from transaction date.
- Show largest balances and longest overdue amounts.
- Handle partial payments and multiple due dates.

#### Credit controls
- Optional customer credit limit and due date.
- Warn when a new credit entry exceeds the configured limit; hard blocking is opt-in.
- No automatic interest, penalties, legal notices or opaque credit scoring in initial scope.

#### Statements and reminders
- Generate customer statements with opening balance, charges, repayments, adjustments and closing balance.
- Export/print statements.
- Prepare reminder text in Hindi, Hinglish or English.
- WhatsApp/SMS sending is out of scope until a real provider, consent and opt-out controls exist. Initial implementation may copy a clearly labelled unsent draft.
- Track delivery only when a real integration exists.

#### Udhar analytics
- Total outstanding, overdue amount and customer count.
- Aging distribution.
- Collections received over a date range.
- Payment history and descriptive repayment regularity.
- Expected collections only from explicit due dates or a transparent labelled estimate.
- No hidden customer risk score.

#### AI Decision Lab examples
- “Mera total kitna udhar baaki hai?”
- “30 din se zyada overdue customers dikhao.”
- “Is hafte kitni repayment receive hui?”
- “Ramesh ka poora ledger dikhao.”
- “Top 5 customers by outstanding amount?”
- “Agar ₹10,000 collect ho jaye toh main kitna stock khareed sakta hoon?”
- “Generate a polite reminder for overdue customers.”

The AI retrieves balances and aging from the Udhar service. It may draft language but must not invent or send reminders without explicit authorization.

### 4.9 Evidence-backed AI Decision Lab
One PydanticAI orchestrator:
1. Receives question and trusted business context.
2. Selects from controlled typed tools.
3. Calls deterministic domain services.
4. Receives structured outputs with source IDs, date windows, methods and warnings.
5. Explains results in the user's language.
6. Shows evidence, assumptions, freshness and safe next actions.

Initial tool catalogue:
- `get_business_metrics`
- `get_product_performance`
- `get_inventory_status`
- `forecast_product_demand`
- `simulate_business_scenario`
- `optimize_procurement`
- `get_festival_insights`
- `search_business_documents`
- `get_total_receivables`
- `get_customer_ledger`
- `get_overdue_customers`
- `get_credit_aging_report`
- `get_customer_payment_history`
- `get_expected_collections`
- `generate_customer_statement`
- `create_purchase_order_draft` (draft only)

If data is insufficient, explain what is missing. No arbitrary SQL, shell or filesystem tools.

### 4.10 Operational actions
- Generate purchase-order drafts from approved recommendations.
- Let owner edit quantities and supplier.
- Show estimated total and unit-cost provenance.
- Approve, cancel and export/print drafts.
- Record credit and repayment through explicit forms or reviewed imports.
- Generate statements and reminder drafts.
- All consequential actions are auditable and require explicit confirmation.
- No external order placement, payments or outbound reminders initially.

## 5. Information architecture

1. Onboarding — business name, region, INR, timezone, business type and optional opening data.
2. Overview — KPIs, trends, alerts, outstanding udhar and recent activity.
3. AI Decision Lab — multilingual chat, evidence, assumptions and safe actions.
4. Inventory — products, stock, forecast, cover and reorder recommendations.
5. Sales & Analytics — sales, profitability, expenses and data coverage.
6. Udhar Management — customer directory, ledger, credit entry, repayment, aging, statements and reminder drafts.
7. Simulations — scenario builder and baseline-vs-scenario comparison.
8. Profit Optimization — product profitability and procurement allocation.
9. Festival Planner — calendar, historical uplift and planning.
10. Data Centre — text/file ingestion, review queue, document history and errors.
11. Purchase Orders — drafts, approvals, line items and exports.
12. Settings — business profile, suppliers, credit defaults, team access and data controls.

## 6. Functional requirements and acceptance criteria

### FR-01 Tenant isolation
Every request resolves authenticated business membership. Every query/mutation is scoped to that business. Cross-tenant access tests include RAG, conversations, customers and udhar.

### FR-02 Ingestion
Validate file type/size; preview extracted values; retain provenance; retrying confirmation does not duplicate records. Udhar customer matching and transaction direction require review when ambiguous.

### FR-03 Ledger integrity
Use PostgreSQL NUMERIC/Decimal. Use transactions and idempotency. Derive udhar balances from ledger and allocations. Corrections use reversal/adjustment entries. Repayments cannot over-allocate and are not revenue.

### FR-04 Analytics
Backend functions generate all KPIs. Missing data is unavailable, not zero unless zero is known. Receivables are separate from cash and revenue.

### FR-05 Forecasting
Return method, horizon, training/data window and quality. Handle sparse data. Reproducible for same input/version.

### FR-06 Simulation/optimization
Return assumptions and model version. Verify constraints server-side. Receivables are not cash absent an explicit collection scenario.

### FR-07 Udhar
Support multiple charges and partial/multi-entry repayments. Ledger and statements reconcile. Aging uses configured due-date semantics. Corrections preserve audit history. Tenant isolation passes.

### FR-08 Agent
Tools are typed, allowlisted and tenant-scoped. Numeric claims match tool outputs. Retrieved text is untrusted. Unsupported questions abstain/clarify. Side effects require explicit confirmation.

### FR-09 Purchase orders
POs are drafts until approved. Draft/approval does not increase stock; receipt does. No external ordering/payment initially.

### FR-10 UX
Responsive layout, clear loading/empty/error states, INR formatting, Hindi/Hinglish support and auditable confirmations.

## 7. Data model overview

Core entities:
- `users`, `businesses`, `business_memberships`
- `products`, `categories`, `suppliers`, `supplier_products`
- `sales`, `sale_items`, `expenses`
- `inventory_balances`, `inventory_movements`
- `customers`, `credit_accounts`, `credit_transactions`, `credit_allocations`
- `purchase_orders`, `purchase_order_items`
- `uploaded_documents`, `document_extractions`, `document_chunks`
- `festival_events`, `forecast_runs`, `forecast_points`, `simulation_runs`, `recommendations`
- `audit_logs`, `agent_conversations`, `agent_messages`, `agent_tool_runs`

Every business-owned entity is tenant-scoped directly or through a verified parent relation.

## 8. AI, RAG and analytics boundaries

| Concern | Responsible component |
|---|---|
| Interpret question/select tool | PydanticAI orchestrator |
| Extract candidate records | Parsers + multimodal model |
| Confirm transactions | Backend validation + owner review |
| Revenue/profit/stock/udhar | SQL/domain services |
| Demand forecast | Forecasting service |
| Procurement optimization | Optimization service |
| Supplier terms/document Q&A | Tenant-filtered RAG |
| Explain results | LLM grounded in typed outputs |
| Execute action | Authorized workflow + explicit confirmation |

RAG is one capability exposed as a tool. It is not the source of truth for structured business metrics.

## 9. Non-functional requirements

- Secrets in environment/secret manager only.
- Authorize every resource server-side.
- Validate uploads and treat document content as untrusted.
- Minimize customer PII and avoid logging ledger contents.
- Use transactions, idempotency and background jobs for long-running ingestion.
- Paginate large ledgers and product/customer lists.
- Index tenant/date/customer/product query paths.
- Track ingestion failures, extraction corrections, agent tool latency, retrieval quality, forecast runs and ledger failures.

## 10. Success metrics

- Time from upload to confirmed records.
- Extraction acceptance/correction rate and duplicate import rate.
- Recommendations with complete evidence.
- Forecast error against naive baseline where history permits.
- Stockout alerts reviewed and acted on.
- Purchase-order drafts created/approved.
- Udhar ledger reconciliation failures: target zero.
- Duplicate credit/repayment postings: target zero.
- Statements that reconcile.
- Unsupported numerical claims and cross-tenant leakage: target zero.
- Reminder sent without consent/authorization: target zero.

## 11. Out of scope initially

Autonomous supplier ordering/payments; GST filing/tax advice; full ERP/POS replacement; bank aggregation; automated credit scoring; interest/penalties/legal notices; unconsented messaging; guaranteed profit/collection claims; general-purpose web agent; graph database dependency.

## 12. Definition of Done

A feature is done only when its end-to-end flow works, validation and tenant authorization are tested, important calculations have tests and documented assumptions, ledger invariants pass, errors/empty states are handled, no demo data leaks into real records, and docs/memory are updated.
