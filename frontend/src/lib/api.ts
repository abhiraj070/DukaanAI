/**
 * DukaanAI Frontend API Client and Connectivity Utilities
 */

import type {
  DocumentConfirmResponse,
  DocumentExtractionData,
  DocumentExtractionResponse,
  DocumentListResponse,
  ImportPreviewResponse,
  UploadDocumentResponse,
} from "./types/ingestion";

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
  // Delete Content-Type so browser sets boundary for multipart/form-data
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
