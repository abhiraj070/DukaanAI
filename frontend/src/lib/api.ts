/**
 * DukaanAI Frontend API Client and Connectivity Utilities
 */

import type {
  AnalyticsTrendsResponse,
  CategoryBreakdownResponse,
  DomainResult,
  KPIOverview,
  ProductRankingResponse,
} from "./types/analytics";
import type {
  DocumentConfirmResponse,
  DocumentExtractionData,
  DocumentExtractionResponse,
  DocumentListResponse,
  ImportPreviewResponse,
  UploadDocumentResponse,
} from "./types/ingestion";
import type {
  ChargeCreate,
  ChargeResponse,
  CustomerCreate,
  CustomerCreateResponse,
  CustomerLedgerResponse,
  CustomerResponse,
  CustomerStatementResult,
  CustomerUpdate,
  ReminderDraftResponse,
  RepaymentCreate,
  RepaymentResponse,
  ReversalCreate,
  ReversalResponse,
  UdharSummaryResult,
} from "./types/udhar";
import type { SavedScenario, ScenarioInput } from "./types/simulation";

export interface HealthResponse {
  status: string;
  app: string;
  version: string;
  environment: string;
  timestamp: string;
  timezone: string;
  request_id?: string | null;
}

export interface APIErrorPayload {
  code: string;
  message: string;
  details?: Record<string, unknown> | null;
  request_id?: string | null;
}

export interface APIErrorResponse {
  error: APIErrorPayload;
}

export interface ConnectivityResult {
  ok: boolean;
  data?: HealthResponse;
  latencyMs: number;
  error?: string;
  requestId?: string;
}

export interface AuthSession {
  accessToken: string;
  tokenType: string;
  userId: string;
  fullName: string;
  businessId: string;
  businessName: string;
}

export interface PurchaseOrderItem {
  id: string; product_id: string; product_name: string; quantity: string;
  unit_cost: string; unit_cost_source: string; received_quantity: string;
}
export interface PurchaseOrder {
  id: string; supplier_id: string | null; status: string; notes: string | null;
  total_amount: string; items: PurchaseOrderItem[]; created_at: string;
  approved_at: string | null; received_at: string | null; cancelled_at: string | null;
}

async function poRequest<T>(path: string, body?: unknown): Promise<T> {
  const headers = await authHeaders() as Record<string, string>;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const response = await fetch(`${API_BASE_URL}/api/v1/purchase-orders${path}`, {
    method: body === undefined ? "GET" : "POST", headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(error?.error?.message ?? `Purchase order request failed (${response.status})`);
  }
  return response.json();
}
export const listPurchaseOrders = () => poRequest<PurchaseOrder[]>("");
export const approvePurchaseOrder = (id: string) => poRequest<PurchaseOrder>(`/${id}/approve`, {});
export const cancelPurchaseOrder = (id: string) => poRequest<PurchaseOrder>(`/${id}/cancel`, {});

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

let cachedToken: string | null = null;

export function setAuthToken(token: string) {
  cachedToken = token;
  if (typeof window !== "undefined") {
    localStorage.setItem("dukaan_token", token);
  }
}

export function getAuthToken(): string | null {
  if (cachedToken) return cachedToken;
  if (typeof window !== "undefined") {
    cachedToken = localStorage.getItem("dukaan_token");
  }
  return cachedToken;
}

/**
 * Fetch or auto-seed a verified demo session for Sharma Kirana Store.
 */
export async function getDemoSession(): Promise<AuthSession> {
  const res = await fetch(`${API_BASE_URL}/api/v1/auth/demo-token`, {
    method: "POST",
    headers: { Accept: "application/json" },
  });

  if (!res.ok) {
    throw new Error(`Failed to initialize session: ${res.statusText}`);
  }

  const data = await res.json();
  setAuthToken(data.access_token);
  return {
    accessToken: data.access_token,
    tokenType: data.token_type,
    userId: data.user_id,
    fullName: data.full_name,
    businessId: data.business_id,
    businessName: data.business_name,
  };
}

async function authHeaders(): Promise<HeadersInit> {
  let token = getAuthToken();
  if (!token) {
    try {
      const session = await getDemoSession();
      token = session.accessToken;
    } catch {
      // Continue without token if backend unreachable
    }
  }

  const headers: Record<string, string> = {
    Accept: "application/json",
    "X-Request-ID": `req_fe_${Math.random().toString(36).substring(2, 10)}`,
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  return headers;
}

export async function getAuthenticatedHeaders(): Promise<HeadersInit> {
  return authHeaders();
}

/**
 * Perform a health check query against the DukaanAI FastAPI backend.
 */
export async function checkBackendHealth(): Promise<ConnectivityResult> {
  const startTime = performance.now();
  const clientRequestId = `req_fe_${Math.random().toString(36).substring(2, 10)}`;

  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/health`, {
      method: "GET",
      headers: {
        Accept: "application/json",
        "X-Request-ID": clientRequestId,
      },
      cache: "no-store",
    });

    const latencyMs = Math.round(performance.now() - startTime);
    const serverRequestId = res.headers.get("X-Request-ID") || clientRequestId;

    if (!res.ok) {
      const errorBody = (await res.json().catch(() => null)) as APIErrorResponse | null;
      return {
        ok: false,
        latencyMs,
        requestId: serverRequestId,
        error:
          errorBody?.error?.message ||
          `Backend returned HTTP ${res.status}: ${res.statusText}`,
      };
    }

    const data = (await res.json()) as HealthResponse;
    return {
      ok: true,
      data,
      latencyMs,
      requestId: serverRequestId,
    };
  } catch (err: unknown) {
    const latencyMs = Math.round(performance.now() - startTime);
    const message =
      err instanceof Error ? err.message : "Failed to connect to backend server";
    return {
      ok: false,
      latencyMs,
      requestId: clientRequestId,
      error: message,
    };
  }
}

// ---------------------------------------------------------------------------
// Phase 3 Ingestion API Client Functions
// ---------------------------------------------------------------------------

/**
 * Upload a document (CSV, XLSX, PDF, TXT) and trigger candidate extraction.
 */
export async function uploadDocument(
  file: File,
  autoProcess: boolean = true
): Promise<UploadDocumentResponse> {
  const headers = await authHeaders();
  delete (headers as Record<string, string>)["Content-Type"];

  const formData = new FormData();
  formData.append("file", file);
  formData.append("auto_process", String(autoProcess));

  const res = await fetch(`${API_BASE_URL}/api/v1/documents/upload`, {
    method: "POST",
    headers,
    body: formData,
  });

  if (!res.ok) {
    const err = (await res.json().catch(() => null)) as APIErrorResponse | null;
    throw new Error(err?.error?.message || `Upload failed with HTTP ${res.status}`);
  }

  return res.json();
}

/**
 * List uploaded documents for the authenticated business.
 */
export async function listDocuments(status?: string): Promise<DocumentListResponse> {
  const headers = await authHeaders();
  const url = new URL(`${API_BASE_URL}/api/v1/documents`);
  if (status) url.searchParams.append("status", status);

  const res = await fetch(url.toString(), {
    method: "GET",
    headers,
    cache: "no-store",
  });

  if (!res.ok) {
    const err = (await res.json().catch(() => null)) as APIErrorResponse | null;
    throw new Error(err?.error?.message || `Failed to fetch documents (${res.status})`);
  }

  return res.json();
}

/**
 * Get document details and extracted candidate records for review.
 */
export async function getDocumentExtraction(
  documentId: string
): Promise<DocumentExtractionResponse> {
  const headers = await authHeaders();
  const res = await fetch(`${API_BASE_URL}/api/v1/documents/${documentId}`, {
    method: "GET",
    headers,
    cache: "no-store",
  });

  if (!res.ok) {
    const err = (await res.json().catch(() => null)) as APIErrorResponse | null;
    throw new Error(err?.error?.message || `Failed to fetch extraction (${res.status})`);
  }

  return res.json();
}

/**
 * Update candidate records (owner edits before confirmation).
 */
export async function updateDocumentExtraction(
  documentId: string,
  data: DocumentExtractionData
): Promise<DocumentExtractionResponse> {
  const headers = await authHeaders();
  (headers as Record<string, string>)["Content-Type"] = "application/json";

  const res = await fetch(`${API_BASE_URL}/api/v1/documents/${documentId}/extraction`, {
    method: "PATCH",
    headers,
    body: JSON.stringify(data),
  });

  if (!res.ok) {
    const err = (await res.json().catch(() => null)) as APIErrorResponse | null;
    throw new Error(err?.error?.message || `Failed to update extraction (${res.status})`);
  }

  return res.json();
}

/**
 * Transactionally and idempotently confirm and post records to domain tables.
 */
export async function confirmDocument(
  documentId: string
): Promise<DocumentConfirmResponse> {
  const headers = await authHeaders();
  (headers as Record<string, string>)["Content-Type"] = "application/json";

  const res = await fetch(`${API_BASE_URL}/api/v1/documents/${documentId}/confirm`, {
    method: "POST",
    headers,
    body: JSON.stringify({}),
  });

  if (!res.ok) {
    const err = (await res.json().catch(() => null)) as APIErrorResponse | null;
    throw new Error(err?.error?.message || `Failed to confirm document (${res.status})`);
  }

  return res.json();
}

/**
 * Quick parse of conversational Hinglish/English kirana notes.
 */
export async function parseNaturalLanguageText(
  text: string,
  saveDraft: boolean = false
): Promise<DocumentExtractionData> {
  const headers = await authHeaders();
  (headers as Record<string, string>)["Content-Type"] = "application/json";

  const url = new URL(`${API_BASE_URL}/api/v1/ingestion/text`);
  if (saveDraft) url.searchParams.append("save_draft", "true");

  const res = await fetch(url.toString(), {
    method: "POST",
    headers,
    body: JSON.stringify({ text }),
  });

  if (!res.ok) {
    const err = (await res.json().catch(() => null)) as APIErrorResponse | null;
    throw new Error(err?.error?.message || `Natural language parsing failed (${res.status})`);
  }

  return res.json();
}

/**
 * Instant tabular preview without persisting to disk.
 */
export async function previewImportFile(file: File): Promise<ImportPreviewResponse> {
  const headers = await authHeaders();
  delete (headers as Record<string, string>)["Content-Type"];

  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE_URL}/api/v1/ingestion/preview`, {
    method: "POST",
    headers,
    body: formData,
  });

  if (!res.ok) {
    const err = (await res.json().catch(() => null)) as APIErrorResponse | null;
    throw new Error(err?.error?.message || `Preview failed (${res.status})`);
  }

  return res.json();
}

// ---------------------------------------------------------------------------
// Phase 4 Core Business Analytics API Client Functions
// ---------------------------------------------------------------------------

/**
 * Fetch authoritative business KPIs and evidence metadata.
 */
export async function getKPIs(
  period: string = "LAST_30_DAYS",
  startDate?: string,
  endDate?: string
): Promise<DomainResult<KPIOverview>> {
  const headers = await authHeaders();
  const url = new URL(`${API_BASE_URL}/api/v1/analytics/kpis`);
  url.searchParams.append("period", period);
  if (startDate) url.searchParams.append("start_date", startDate);
  if (endDate) url.searchParams.append("end_date", endDate);

  const res = await fetch(url.toString(), {
    method: "GET",
    headers,
    cache: "no-store",
  });

  if (!res.ok) {
    const err = (await res.json().catch(() => null)) as APIErrorResponse | null;
    throw new Error(err?.error?.message || `Failed to fetch KPIs (${res.status})`);
  }

  return res.json();
}

/**
 * Fetch top and slow-moving product rankings.
 */
export async function getProductRankings(
  period: string = "LAST_30_DAYS",
  startDate?: string,
  endDate?: string
): Promise<DomainResult<ProductRankingResponse>> {
  const headers = await authHeaders();
  const url = new URL(`${API_BASE_URL}/api/v1/analytics/products`);
  url.searchParams.append("period", period);
  if (startDate) url.searchParams.append("start_date", startDate);
  if (endDate) url.searchParams.append("end_date", endDate);

  const res = await fetch(url.toString(), {
    method: "GET",
    headers,
    cache: "no-store",
  });

  if (!res.ok) {
    const err = (await res.json().catch(() => null)) as APIErrorResponse | null;
    throw new Error(err?.error?.message || `Failed to fetch product rankings (${res.status})`);
  }

  return res.json();
}

/**
 * Fetch category performance breakdown.
 */
export async function getCategoryBreakdown(
  period: string = "LAST_30_DAYS",
  startDate?: string,
  endDate?: string
): Promise<DomainResult<CategoryBreakdownResponse>> {
  const headers = await authHeaders();
  const url = new URL(`${API_BASE_URL}/api/v1/analytics/categories`);
  url.searchParams.append("period", period);
  if (startDate) url.searchParams.append("start_date", startDate);
  if (endDate) url.searchParams.append("end_date", endDate);

  const res = await fetch(url.toString(), {
    method: "GET",
    headers,
    cache: "no-store",
  });

  if (!res.ok) {
    const err = (await res.json().catch(() => null)) as APIErrorResponse | null;
    throw new Error(err?.error?.message || `Failed to fetch categories (${res.status})`);
  }

  return res.json();
}

/**
 * Fetch daily revenue, COGS, and expense trends for timeline charts.
 */
export async function getAnalyticsTrends(
  period: string = "LAST_30_DAYS",
  startDate?: string,
  endDate?: string
): Promise<DomainResult<AnalyticsTrendsResponse>> {
  const headers = await authHeaders();
  const url = new URL(`${API_BASE_URL}/api/v1/analytics/trends`);
  url.searchParams.append("period", period);
  if (startDate) url.searchParams.append("start_date", startDate);
  if (endDate) url.searchParams.append("end_date", endDate);

  const res = await fetch(url.toString(), {
    method: "GET",
    headers,
    cache: "no-store",
  });

  if (!res.ok) {
    const err = (await res.json().catch(() => null)) as APIErrorResponse | null;
    throw new Error(err?.error?.message || `Failed to fetch trends (${res.status})`);
  }

  return res.json();
}

// -------------------------------------------------------------------------
// Phase 5: Udhar (Customer Credit) Management APIs
// -------------------------------------------------------------------------

/**
 * Fetch store-wide udhar receivables, overdue balances, and aging distribution.
 */
export async function getUdharSummary(asOfDate?: string): Promise<UdharSummaryResult> {
  const headers = await authHeaders();
  const url = new URL(`${API_BASE_URL}/api/v1/udhar/summary`);
  if (asOfDate) url.searchParams.append("as_of_date", asOfDate);

  const res = await fetch(url.toString(), {
    method: "GET",
    headers,
    cache: "no-store",
  });

  if (!res.ok) {
    const err = (await res.json().catch(() => null)) as APIErrorResponse | null;
    throw new Error(err?.error?.message || `Failed to fetch Udhar summary (${res.status})`);
  }

  return res.json();
}

export async function runSimulation(payload: ScenarioInput): Promise<{ data: SavedScenario["result"]; evidence: SavedScenario["evidence"] }> {
  const headers = await authHeaders();
  const res = await fetch(`${API_BASE_URL}/api/v1/simulation/scenarios`, {
    method: "POST",
    headers: { ...headers, "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = (await res.json().catch(() => null)) as APIErrorResponse | null;
    throw new Error(err?.error?.message || `Simulation failed (${res.status})`);
  }
  return res.json();
}

export async function listScenarios(): Promise<SavedScenario[]> {
  const headers = await authHeaders();
  const res = await fetch(`${API_BASE_URL}/api/v1/simulation/scenarios`, { headers, cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to load scenarios (${res.status})`);
  return res.json();
}

/**
 * List customers with derived balances, overdue amounts, and aging status.
 */
export async function listCustomers(
  query?: string,
  includeArchived: boolean = false
): Promise<CustomerResponse[]> {
  const headers = await authHeaders();
  const url = new URL(`${API_BASE_URL}/api/v1/udhar/customers`);
  if (query) url.searchParams.append("query", query);
  if (includeArchived) url.searchParams.append("include_archived", "true");

  const res = await fetch(url.toString(), {
    method: "GET",
    headers,
    cache: "no-store",
  });

  if (!res.ok) {
    const err = (await res.json().catch(() => null)) as APIErrorResponse | null;
    throw new Error(err?.error?.message || `Failed to list customers (${res.status})`);
  }

  return res.json();
}

/**
 * Create a new customer with optional opening balance, limit, and duplicate warnings.
 */
export async function createCustomer(payload: CustomerCreate): Promise<CustomerCreateResponse> {
  const headers = await authHeaders();
  const res = await fetch(`${API_BASE_URL}/api/v1/udhar/customers`, {
    method: "POST",
    headers: { ...headers, "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const err = (await res.json().catch(() => null)) as APIErrorResponse | null;
    throw new Error(err?.error?.message || `Failed to create customer (${res.status})`);
  }

  return res.json();
}

/**
 * Fetch customer profile by id.
 */
export async function getCustomer(customerId: string): Promise<CustomerResponse> {
  const headers = await authHeaders();
  const res = await fetch(`${API_BASE_URL}/api/v1/udhar/customers/${customerId}`, {
    method: "GET",
    headers,
    cache: "no-store",
  });

  if (!res.ok) {
    const err = (await res.json().catch(() => null)) as APIErrorResponse | null;
    throw new Error(err?.error?.message || `Failed to fetch customer (${res.status})`);
  }

  return res.json();
}

/**
 * Update customer details and credit limit.
 */
export async function updateCustomer(
  customerId: string,
  payload: CustomerUpdate
): Promise<CustomerResponse> {
  const headers = await authHeaders();
  const res = await fetch(`${API_BASE_URL}/api/v1/udhar/customers/${customerId}`, {
    method: "PUT",
    headers: { ...headers, "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const err = (await res.json().catch(() => null)) as APIErrorResponse | null;
    throw new Error(err?.error?.message || `Failed to update customer (${res.status})`);
  }

  return res.json();
}

/**
 * Archive customer (soft-delete).
 */
export async function archiveCustomer(customerId: string): Promise<CustomerResponse> {
  const headers = await authHeaders();
  const res = await fetch(`${API_BASE_URL}/api/v1/udhar/customers/${customerId}/archive`, {
    method: "POST",
    headers,
  });

  if (!res.ok) {
    const err = (await res.json().catch(() => null)) as APIErrorResponse | null;
    throw new Error(err?.error?.message || `Failed to archive customer (${res.status})`);
  }

  return res.json();
}

/**
 * Unarchive / restore customer.
 */
export async function unarchiveCustomer(customerId: string): Promise<CustomerResponse> {
  const headers = await authHeaders();
  const res = await fetch(`${API_BASE_URL}/api/v1/udhar/customers/${customerId}/unarchive`, {
    method: "POST",
    headers,
  });

  if (!res.ok) {
    const err = (await res.json().catch(() => null)) as APIErrorResponse | null;
    throw new Error(err?.error?.message || `Failed to restore customer (${res.status})`);
  }

  return res.json();
}

/**
 * Fetch chronological customer ledger with line-by-line running balance.
 */
export async function getCustomerLedger(customerId: string): Promise<CustomerLedgerResponse> {
  const headers = await authHeaders();
  const res = await fetch(`${API_BASE_URL}/api/v1/udhar/customers/${customerId}/ledger`, {
    method: "GET",
    headers,
    cache: "no-store",
  });

  if (!res.ok) {
    const err = (await res.json().catch(() => null)) as APIErrorResponse | null;
    throw new Error(err?.error?.message || `Failed to fetch customer ledger (${res.status})`);
  }

  return res.json();
}

/**
 * Generate reconciled customer statement with opening, charges, repayments, and closing balances.
 */
export async function getCustomerStatement(
  customerId: string,
  startDate?: string,
  endDate?: string
): Promise<CustomerStatementResult> {
  const headers = await authHeaders();
  const url = new URL(`${API_BASE_URL}/api/v1/udhar/customers/${customerId}/statement`);
  if (startDate) url.searchParams.append("start_date", startDate);
  if (endDate) url.searchParams.append("end_date", endDate);

  const res = await fetch(url.toString(), {
    method: "GET",
    headers,
    cache: "no-store",
  });

  if (!res.ok) {
    const err = (await res.json().catch(() => null)) as APIErrorResponse | null;
    throw new Error(err?.error?.message || `Failed to generate statement (${res.status})`);
  }

  return res.json();
}

/**
 * Generate un-sent polite reminder draft preview (Hinglish, Hindi, English) with WhatsApp link.
 */
export async function generateReminderDraft(
  customerId: string,
  language: "Hinglish" | "Hindi" | "English" = "Hinglish"
): Promise<ReminderDraftResponse> {
  const headers = await authHeaders();
  const res = await fetch(`${API_BASE_URL}/api/v1/udhar/customers/${customerId}/reminder-draft`, {
    method: "POST",
    headers: { ...headers, "Content-Type": "application/json" },
    body: JSON.stringify({ language }),
  });

  if (!res.ok) {
    const err = (await res.json().catch(() => null)) as APIErrorResponse | null;
    throw new Error(err?.error?.message || `Failed to generate reminder draft (${res.status})`);
  }

  return res.json();
}

/**
 * Record a credit sale (charge) entry.
 */
export async function recordCharge(payload: ChargeCreate): Promise<ChargeResponse> {
  const headers = await authHeaders();
  const res = await fetch(`${API_BASE_URL}/api/v1/udhar/charges`, {
    method: "POST",
    headers: { ...headers, "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const err = (await res.json().catch(() => null)) as APIErrorResponse | null;
    throw new Error(err?.error?.message || `Failed to record credit charge (${res.status})`);
  }

  return res.json();
}

/**
 * Record a customer repayment collection.
 */
export async function recordRepayment(payload: RepaymentCreate): Promise<RepaymentResponse> {
  const headers = await authHeaders();
  const res = await fetch(`${API_BASE_URL}/api/v1/udhar/repayments`, {
    method: "POST",
    headers: { ...headers, "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const err = (await res.json().catch(() => null)) as APIErrorResponse | null;
    throw new Error(err?.error?.message || `Failed to record repayment (${res.status})`);
  }

  return res.json();
}

/**
 * Post a compensating reversal for a transaction.
 */
export async function reverseTransaction(
  transactionId: string,
  payload: ReversalCreate
): Promise<ReversalResponse> {
  const headers = await authHeaders();
  const res = await fetch(`${API_BASE_URL}/api/v1/udhar/transactions/${transactionId}/reverse`, {
    method: "POST",
    headers: { ...headers, "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const err = (await res.json().catch(() => null)) as APIErrorResponse | null;
    throw new Error(err?.error?.message || `Failed to reverse transaction (${res.status})`);
  }

  return res.json();
}
