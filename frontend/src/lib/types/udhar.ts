/**
 * TypeScript types for Udhar Management, Customer Ledger, Aging, and Statements.
 */

import { DomainResult } from "./analytics";

export interface AgingBucket {
  bucket_key: "NOT_DUE" | "1_7_DAYS" | "8_30_DAYS" | "31_60_DAYS" | "60_PLUS_DAYS" | string;
  label: string;
  amount: number | string;
  customer_count: number;
}

export interface UdharSummary {
  total_receivables: number | string;
  overdue_amount: number | string;
  customers_with_balance_count: number;
  aging_buckets: AgingBucket[];
  currency: string;
}

export interface StatementLineItem {
  transaction_id: string;
  transaction_at: string;
  transaction_type: "CHARGE" | "OPENING_BALANCE" | "REPAYMENT" | "ADJUSTMENT_DEBIT" | "ADJUSTMENT_CREDIT" | "REVERSAL" | string;
  description: string | null;
  reference: string | null;
  charge_amount: number | string | null;
  repayment_amount: number | string | null;
  running_balance: number | string;
}

export interface CustomerStatement {
  customer_id: string;
  customer_name: string;
  phone: string | null;
  currency: string;
  start_date: string | null;
  end_date: string | null;
  opening_balance: number | string;
  total_charges: number | string;
  total_repayments: number | string;
  closing_balance: number | string;
  lines: StatementLineItem[];
}

export interface CustomerDuplicateMatch {
  existing_customer_id: string;
  existing_display_name: string;
  existing_phone: string | null;
  match_type: "PHONE_MATCH" | "EXACT_NAME" | "FUZZY_NAME" | string;
}

export interface CustomerCreate {
  display_name: string;
  phone_e164?: string | null;
  notes?: string | null;
  credit_limit?: number | string | null;
  opening_balance?: number | string | null;
  opening_balance_due_at?: string | null;
  opening_balance_notes?: string | null;
}

export interface CustomerUpdate {
  display_name?: string | null;
  phone_e164?: string | null;
  notes?: string | null;
  credit_limit?: number | string | null;
  reminder_consent_status?: string | null;
}

export interface CustomerResponse {
  id: string;
  display_name: string;
  phone_e164: string | null;
  notes: string | null;
  credit_limit: number | string | null;
  currency: string;
  is_active: boolean;
  reminder_consent_status: string;
  created_at: string;
  archived_at: string | null;
  outstanding_balance: number | string;
  overdue_amount: number | string;
  aging_bucket: string;
  transaction_count: number;
}

export interface CustomerCreateResponse {
  customer: CustomerResponse;
  warnings: string[];
  duplicate_matches: CustomerDuplicateMatch[];
}

export interface ChargeCreate {
  customer_id: string;
  amount: number | string;
  due_at?: string | null;
  description?: string | null;
  reference?: string | null;
  idempotency_key?: string | null;
}

export interface ChargeResponse {
  transaction_id: string;
  customer_id: string;
  amount: number | string;
  transaction_type: string;
  transaction_at: string;
  due_at: string | null;
  description: string | null;
  reference: string | null;
  status: string;
  credit_limit_warning: string | null;
  new_balance: number | string;
}

export interface AllocationInput {
  charge_transaction_id: string;
  amount: number | string;
}

export interface AllocationResponse {
  id: string;
  charge_transaction_id: string;
  allocated_amount: number | string;
  created_at: string;
}

export interface RepaymentCreate {
  customer_id: string;
  amount: number | string;
  payment_mode: "CASH" | "UPI" | "BANK_TRANSFER" | "CHEQUE" | "OTHER";
  reference?: string | null;
  description?: string | null;
  idempotency_key?: string | null;
  allocations?: AllocationInput[] | null;
  auto_allocate?: boolean;
}

export interface RepaymentResponse {
  transaction_id: string;
  customer_id: string;
  amount: number | string;
  payment_mode: string;
  transaction_at: string;
  reference: string | null;
  status: string;
  allocated_amount: number | string;
  unallocated_amount: number | string;
  allocations: AllocationResponse[];
  new_balance: number | string;
}

export interface ReversalCreate {
  reason: string;
}

export interface ReversalResponse {
  reversal_transaction_id: string;
  original_transaction_id: string;
  amount: number | string;
  reversed_at: string;
  new_balance: number | string;
}

export interface CustomerLedgerResponse {
  customer_id: string;
  customer_name: string;
  outstanding_balance: number | string;
  credit_limit: number | string | null;
  currency: string;
  lines: StatementLineItem[];
}

export interface ReminderDraftRequest {
  language: "Hinglish" | "Hindi" | "English";
}

export interface ReminderDraftResponse {
  customer_id: string;
  customer_name: string;
  phone: string | null;
  outstanding_balance: number | string;
  overdue_amount: number | string;
  due_at: string | null;
  language: string;
  draft_text: string;
  whatsapp_link: string | null;
  consent_status: string;
  disclaimer: string;
}

export type UdharSummaryResult = DomainResult<UdharSummary>;
export type CustomerStatementResult = DomainResult<CustomerStatement>;
