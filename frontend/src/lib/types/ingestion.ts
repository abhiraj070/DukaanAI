/**
 * Typed domain contracts for AI Data Centre & Ingestion pipeline.
 */

export interface CandidateSaleItem {
  product_name: string;
  sku?: string | null;
  quantity: string | number;
  unit_price: string | number;
  unit_cost?: string | number | null;
  total_amount: string | number;
  source_row?: number | null;
}

export interface CandidateSale {
  sale_number?: string | null;
  sold_at?: string | null;
  total_amount: string | number;
  payment_mode: string;
  customer_name?: string | null;
  items: CandidateSaleItem[];
  source_row?: number | null;
  confidence: number;
  warnings: string[];
}

export interface CandidateExpense {
  category: string;
  amount: string | number;
  expense_date?: string | null;
  description?: string | null;
  payment_mode: string;
  source_row?: number | null;
  confidence: number;
  warnings: string[];
}

export interface CandidateCreditTransaction {
  customer_candidate_name: string;
  phone?: string | null;
  transaction_type: "CHARGE" | "REPAYMENT" | string;
  amount: string | number;
  transaction_at?: string | null;
  due_at?: string | null;
  description?: string | null;
  reference?: string | null;
  source_page?: number | null;
  source_row?: number | null;
  snippet?: string | null;
  confidence: number;
  ambiguity_flags: string[];
  requires_owner_review: boolean;
}

export interface InvalidRowRecord {
  row_number: number;
  raw_data: (string | number | null)[] | Record<string, unknown>;
  error_reason: string;
}

export interface DocumentExtractionData {
  extraction_type: "SALES" | "EXPENSES" | "INVENTORY" | "UDHAR_LEDGER" | "MIXED" | string;
  sales: CandidateSale[];
  expenses: CandidateExpense[];
  credit_transactions: CandidateCreditTransaction[];
  invalid_rows: InvalidRowRecord[];
}

export interface UploadedDocumentSummary {
  id: string;
  filename: string;
  file_type: string;
  file_size_bytes: number;
  sha256_hash: string;
  status: "PENDING" | "PROCESSING" | "PROCESSED" | "CONFIRMED" | "FAILED" | string;
  ambiguity_count: number;
  is_confirmed: boolean;
  created_at: string;
  updated_at: string;
}

export interface UploadDocumentResponse {
  document_id: string;
  filename: string;
  file_type: string;
  file_size_bytes: number;
  sha256_hash: string;
  status: string;
  message: string;
}

export interface DocumentExtractionResponse {
  document_id: string;
  filename: string;
  file_type: string;
  sha256_hash: string;
  status: string;
  extraction_type: string;
  extraction_version: string;
  data: DocumentExtractionData;
  ambiguity_count: number;
  is_confirmed: boolean;
  confirmed_at?: string | null;
}

export interface DocumentConfirmResponse {
  document_id: string;
  is_confirmed: boolean;
  sales_posted: number;
  expenses_posted: number;
  credit_transactions_posted: number;
  message: string;
}

export interface DocumentListResponse {
  documents: UploadedDocumentSummary[];
  total: number;
}

export interface ImportPreviewResponse {
  filename: string;
  file_type: string;
  detected_type: string;
  total_rows: number;
  valid_rows_count: number;
  invalid_rows_count: number;
  candidates: DocumentExtractionData;
}
