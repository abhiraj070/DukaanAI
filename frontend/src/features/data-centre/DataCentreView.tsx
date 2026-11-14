"use client";

import React, { useEffect, useState } from "react";
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  Clock,
  Copy,
  Database,
  Eye,
  FileCheck2,
  FileSpreadsheet,
  FileText,
  FileUp,
  Info,
  Loader2,
  RefreshCw,
  Send,
  Shield,
  Sparkles,
  Store,
  Upload,
  UserCheck,
  XCircle,
} from "lucide-react";

import {
  confirmDocument,
  getDocumentExtraction,
  listDocuments,
  parseNaturalLanguageText,
  updateDocumentExtraction,
  uploadDocument,
} from "@/lib/api";
import type {
  CandidateCreditTransaction,
  CandidateExpense,
  CandidateSale,
  DocumentExtractionData,
  DocumentExtractionResponse,
  UploadedDocumentSummary,
} from "@/lib/types/ingestion";

const SAMPLE_NOTE = `Ramesh Verma ko 1200 ka rashan udhar diya
Bijli ka bill 2450 bhara
Sold 4 sugar packets 440 cash
Suresh Kumar se 500 jama mila
Anita 750`;

const SAMPLE_CSV_SALES = `Date,Item,Qty,Rate,Total,Payment_Mode
2026-11-12,Aashirvaad Atta 10kg,2,450.00,900.00,CASH
2026-11-12,Mustard Oil 1L,3,165.00,495.00,UPI
2026-11-12,Chana Dal 1kg,5,110.00,550.00,CASH`;

const SAMPLE_CSV_UDHAR = `Date,Customer,Amount,Type
2026-11-10,Ramesh Verma,1200.00,udhar
2026-11-11,Ramesh Verma,500.00,jama
2026-11-12,Suresh Kumar,800.00,unknown_direction
2026-11-13,Pooja Sharma,INVALID_AMT,udhar`;

export function DataCentreView() {
  const [activeTab, setActiveTab] = useState<"upload" | "text" | "review" | "history">("upload");
  const [documents, setDocuments] = useState<UploadedDocumentSummary[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [extraction, setExtraction] = useState<DocumentExtractionResponse | null>(null);

  // Upload state
  const [dragActive, setDragActive] = useState<boolean>(false);
  const [uploading, setUploading] = useState<boolean>(false);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Natural Language state
  const [noteText, setNoteText] = useState<string>(SAMPLE_NOTE);
  const [parsingNote, setParsingNote] = useState<boolean>(false);
  const [parsedData, setParsedData] = useState<DocumentExtractionData | null>(null);

  // Confirming state
  const [savingEdits, setSavingEdits] = useState<boolean>(false);
  const [confirming, setConfirming] = useState<boolean>(false);
  const [confirmSuccess, setConfirmSuccess] = useState<string | null>(null);
  const [copiedHash, setCopiedHash] = useState<boolean>(false);

  const fetchDocs = async () => {
    try {
      const res = await listDocuments();
      setDocuments(res.documents);
    } catch {
      // Ignored if offline
    }
  };

  useEffect(() => {
    let isMounted = true;
    listDocuments()
      .then((res) => {
        if (isMounted) {
          setDocuments(res.documents);
        }
      })
      .catch(() => {});
    return () => {
      isMounted = false;
    };
  }, []);

  const loadDocumentExtraction = async (id: string) => {
    try {
      setSelectedDocId(id);
      setActiveTab("review");
      setConfirmSuccess(null);
      const res = await getDocumentExtraction(id);
      setExtraction(res);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to load extraction");
    }
  };

  const handleFileUpload = async (file: File) => {
    setUploading(true);
    setUploadError(null);
    setUploadMessage(null);

    try {
      const res = await uploadDocument(file, true);
      setUploadMessage(res.message);
      await fetchDocs();
      await loadDocumentExtraction(res.document_id);
    } catch (err: unknown) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  };

  const handleParseNote = async (saveDraft: boolean) => {
    if (!noteText.trim()) return;
    setParsingNote(true);
    try {
      const data = await parseNaturalLanguageText(noteText, saveDraft);
      setParsedData(data);
      if (saveDraft) {
        await fetchDocs();
        const docs = await listDocuments();
        if (docs.documents.length > 0) {
          await loadDocumentExtraction(docs.documents[0].id);
        }
      }
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Parsing failed");
    } finally {
      setParsingNote(false);
    }
  };

  const handleSaveEdits = async () => {
    if (!extraction) return;
    setSavingEdits(true);
    try {
      const updated = await updateDocumentExtraction(extraction.document_id, extraction.data);
      setExtraction(updated);
      alert("Draft candidate records updated successfully.");
      await fetchDocs();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to save edits");
    } finally {
      setSavingEdits(false);
    }
  };

  const handleConfirmPosting = async () => {
    if (!extraction) return;
    setConfirming(true);
    try {
      const res = await confirmDocument(extraction.document_id);
      setConfirmSuccess(
        `Posted successfully! ${res.sales_posted} sales, ${res.expenses_posted} expenses, and ${res.credit_transactions_posted} credit entries confirmed into authoritative ledger.`
      );
      // Reload document status
      const updated = await getDocumentExtraction(extraction.document_id);
      setExtraction(updated);
      await fetchDocs();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Confirmation failed");
    } finally {
      setConfirming(false);
    }
  };

  const copyHash = (hash: string) => {
    navigator.clipboard.writeText(hash);
    setCopiedHash(true);
    setTimeout(() => setCopiedHash(false), 2000);
  };

  const createSampleFile = (content: string, filename: string) => {
    const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
    const file = new File([blob], filename, { type: "text/csv" });
    handleFileUpload(file);
  };

  return (
    <div className="space-y-6">
      {/* Top Controls & Tenant Context */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 sm:p-5 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-indigo-50 text-indigo-700">
            <Store className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-slate-900">AI Data Centre & Ingestion Hub</h2>
              <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">
                Phase 3 Active
              </span>
            </div>
            <p className="text-xs text-slate-500">
              Deterministic validation • Draft extractions • Owner review gate • Idempotent posting
            </p>
          </div>
        </div>

        {/* Tab Buttons */}
        <div className="flex items-center gap-1.5 p-1 rounded-lg bg-slate-100 border border-slate-200 text-xs font-semibold">
          <button
            onClick={() => setActiveTab("upload")}
            className={`px-3 py-1.5 rounded-md transition-all ${
              activeTab === "upload"
                ? "bg-white text-slate-900 shadow-xs"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <span className="flex items-center gap-1.5">
              <Upload className="w-3.5 h-3.5" />
              Upload Files
            </span>
          </button>
          <button
            onClick={() => setActiveTab("text")}
            className={`px-3 py-1.5 rounded-md transition-all ${
              activeTab === "text"
                ? "bg-white text-slate-900 shadow-xs"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <span className="flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5" />
              Hinglish Note
            </span>
          </button>
          <button
            onClick={() => setActiveTab("review")}
            className={`px-3 py-1.5 rounded-md transition-all ${
              activeTab === "review"
                ? "bg-white text-slate-900 shadow-xs"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <span className="flex items-center gap-1.5">
              <FileCheck2 className="w-3.5 h-3.5" />
              Review & Confirm
              {extraction && !extraction.is_confirmed && (
                <span className="w-2 h-2 rounded-full bg-amber-500" />
              )}
            </span>
          </button>
          <button
            onClick={() => setActiveTab("history")}
            className={`px-3 py-1.5 rounded-md transition-all ${
              activeTab === "history"
                ? "bg-white text-slate-900 shadow-xs"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <span className="flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5" />
              History ({documents.length})
            </span>
          </button>
        </div>
      </div>

      {/* Mode 1: File Upload */}
      {activeTab === "upload" && (
        <div className="space-y-6">
          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            className={`border-2 border-dashed rounded-2xl p-8 sm:p-12 text-center transition-all bg-white ${
              dragActive ? "border-indigo-600 bg-indigo-50/50" : "border-slate-300 hover:border-slate-400"
            }`}
          >
            <div className="max-w-md mx-auto space-y-4">
              <div className="w-14 h-14 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center mx-auto shadow-inner">
                {uploading ? (
                  <Loader2 className="w-7 h-7 animate-spin" />
                ) : (
                  <FileUp className="w-7 h-7" />
                )}
              </div>

              <div>
                <h3 className="text-base font-bold text-slate-900">
                  Drag and drop documents here
                </h3>
                <p className="text-xs text-slate-500 mt-1">
                  Supports CSV, Excel (.xlsx), PDF invoices, and text notes up to 15MB.
                </p>
              </div>

              <div className="pt-2">
                <label className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 text-white text-xs font-semibold hover:bg-indigo-700 cursor-pointer shadow-xs transition-colors">
                  <Upload className="w-4 h-4" />
                  <span>Browse Device Files</span>
                  <input
                    type="file"
                    className="hidden"
                    accept=".csv,.xlsx,.xls,.pdf,.txt"
                    onChange={(e) => {
                      if (e.target.files && e.target.files[0]) {
                        handleFileUpload(e.target.files[0]);
                      }
                    }}
                  />
                </label>
              </div>

              {uploadMessage && (
                <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
                  <span>{uploadMessage}</span>
                </div>
              )}

              {uploadError && (
                <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-center gap-2">
                  <XCircle className="w-4 h-4 shrink-0 text-rose-600" />
                  <span>{uploadError}</span>
                </div>
              )}
            </div>
          </div>

          {/* Quick Sample File Launchers */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-3">
            <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-2">
              <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
              Quick Test Templates (Click to ingest instantly)
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <button
                onClick={() => createSampleFile(SAMPLE_CSV_SALES, "daily_sales_sample.csv")}
                className="p-3 rounded-lg border border-slate-200 hover:border-indigo-300 hover:bg-indigo-50/30 text-left transition-all flex items-start gap-3 group"
              >
                <div className="p-2 rounded-md bg-blue-50 text-blue-600 group-hover:bg-blue-100">
                  <FileSpreadsheet className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-xs font-semibold text-slate-900">
                    Daily Kirana Sales (CSV)
                  </div>
                  <div className="text-[11px] text-slate-500">
                    Atta, Mustard Oil, Chana Dal with quantities and payment modes
                  </div>
                </div>
              </button>

              <button
                onClick={() => createSampleFile(SAMPLE_CSV_UDHAR, "udhar_ledger_sample.csv")}
                className="p-3 rounded-lg border border-slate-200 hover:border-amber-300 hover:bg-amber-50/30 text-left transition-all flex items-start gap-3 group"
              >
                <div className="p-2 rounded-md bg-amber-50 text-amber-600 group-hover:bg-amber-100">
                  <FileText className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-xs font-semibold text-slate-900">
                    Udhar Ledger with Ambiguity & Invalid Row (CSV)
                  </div>
                  <div className="text-[11px] text-slate-500">
                    Tests credit charge, repayment, direction flag & row error reporting
                  </div>
                </div>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Mode 2: Natural Language Note */}
      {activeTab === "text" && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 sm:p-6 shadow-xs space-y-4">
          <div>
            <h3 className="text-sm font-bold text-slate-900">
              Conversational Hinglish / Hindi Ingestion
            </h3>
            <p className="text-xs text-slate-500">
              Enter raw daily notes like kirana owners write on rough bahi-khata sheets.
            </p>
          </div>

          <textarea
            rows={6}
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            className="w-full rounded-lg border border-slate-300 p-3 text-xs font-mono text-slate-900 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
            placeholder="Type your notes here..."
          />

          <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
            <span className="text-[11px] text-slate-500">
              Supports: Udhar (diya / mila), Expenses (bijli / rent), and Sales (sold / becha).
            </span>

            <div className="flex items-center gap-2">
              <button
                onClick={() => handleParseNote(false)}
                disabled={parsingNote}
                className="px-4 py-2 rounded-lg border border-slate-300 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors disabled:opacity-50"
              >
                Preview Candidates Only
              </button>

              <button
                onClick={() => handleParseNote(true)}
                disabled={parsingNote}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-indigo-600 text-white text-xs font-semibold hover:bg-indigo-700 transition-colors shadow-xs disabled:opacity-50"
              >
                {parsingNote ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Send className="w-3.5 h-3.5" />
                )}
                <span>Save as Draft Document</span>
              </button>
            </div>
          </div>

          {/* Inline Parsed Preview if not saved as draft */}
          {parsedData && (
            <div className="mt-4 pt-4 border-t border-slate-100 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-800">
                  Extracted Candidates ({parsedData.extraction_type})
                </span>
                <span className="text-xs text-slate-500 font-mono">
                  {parsedData.credit_transactions.length} Udhar • {parsedData.sales.length} Sales •{" "}
                  {parsedData.expenses.length} Expenses
                </span>
              </div>

              {parsedData.credit_transactions.length > 0 && (
                <div className="rounded-lg border border-slate-200 overflow-hidden text-xs">
                  <div className="bg-slate-50 px-3 py-2 font-semibold text-slate-700 border-b border-slate-200">
                    Udhar Ledger Entries
                  </div>
                  {parsedData.credit_transactions.map((c, idx) => (
                    <div
                      key={idx}
                      className="p-3 border-b border-slate-100 last:border-0 flex items-center justify-between gap-2"
                    >
                      <div>
                        <span className="font-semibold text-slate-900">
                          {c.customer_candidate_name}
                        </span>
                        <span className="text-slate-500 ml-2">({c.snippet})</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span
                          className={`px-2 py-0.5 rounded text-[11px] font-semibold ${
                            c.transaction_type === "CHARGE"
                              ? "bg-rose-100 text-rose-800"
                              : "bg-emerald-100 text-emerald-800"
                          }`}
                        >
                          {c.transaction_type}
                        </span>
                        <span className="font-mono font-bold text-slate-900">
                          ₹{c.amount}
                        </span>
                        {c.ambiguity_flags.length > 0 && (
                          <span className="px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 text-[10px] font-semibold">
                            Ambiguous
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Mode 3: Review & Confirm Extraction */}
      {activeTab === "review" && (
        <div className="space-y-6">
          {!extraction ? (
            <div className="bg-white rounded-xl border border-slate-200 p-8 text-center space-y-3">
              <FileCheck2 className="w-10 h-10 text-slate-400 mx-auto" />
              <h3 className="text-sm font-semibold text-slate-800">No Document Selected</h3>
              <p className="text-xs text-slate-500 max-w-sm mx-auto">
                Select an uploaded document from the History tab or upload a new file to review draft candidates.
              </p>
              <button
                onClick={() => setActiveTab("history")}
                className="px-4 py-2 rounded-lg bg-slate-900 text-white text-xs font-medium hover:bg-slate-800"
              >
                View Uploaded Documents
              </button>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Document Provenance Header Card */}
              <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <h3 className="text-base font-bold text-slate-900">
                        {extraction.filename}
                      </h3>
                      <span
                        className={`px-2.5 py-0.5 rounded-full text-xs font-bold ${
                          extraction.is_confirmed
                            ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                            : "bg-amber-100 text-amber-800 border border-amber-300"
                        }`}
                      >
                        {extraction.is_confirmed ? "CONFIRMED & POSTED" : "DRAFT (AWAITING REVIEW)"}
                      </span>
                    </div>
                    <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
                      <span>Type: <strong className="text-slate-700">{extraction.file_type}</strong></span>
                      <span>•</span>
                      <span>Detection: <strong className="text-slate-700">{extraction.extraction_type}</strong></span>
                      <span>•</span>
                      <span>Engine: <strong className="text-slate-700">{extraction.extraction_version}</strong></span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => loadDocumentExtraction(extraction.document_id)}
                      className="p-2 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 text-xs"
                      title="Refresh"
                    >
                      <RefreshCw className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Provenance SHA-256 fingerprint */}
                <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-xs">
                  <div className="flex items-center gap-2 text-slate-600 truncate">
                    <Shield className="w-3.5 h-3.5 text-indigo-600 shrink-0" />
                    <span className="font-semibold text-slate-700">SHA-256 Fingerprint:</span>
                    <span className="font-mono text-[11px] truncate">{extraction.sha256_hash}</span>
                  </div>
                  <button
                    onClick={() => copyHash(extraction.sha256_hash)}
                    className="p-1 rounded hover:bg-slate-200 text-slate-600 shrink-0"
                    title="Copy full SHA256 hash"
                  >
                    {copiedHash ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                  </button>
                </div>

                {/* Ambiguity Warning Banner */}
                {extraction.ambiguity_count > 0 && !extraction.is_confirmed && (
                  <div className="p-4 rounded-lg bg-amber-50 border border-amber-300 flex items-start gap-3">
                    <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                    <div className="space-y-1">
                      <div className="text-xs font-bold text-amber-900">
                        {extraction.ambiguity_count} Transaction Ambiguity Flagged
                      </div>
                      <p className="text-xs text-amber-800 leading-relaxed">
                        The transaction direction (Credit Given vs Repayment Received) was unclear in the source file.
                        Review and set the direction below before confirming.
                      </p>
                    </div>
                  </div>
                )}

                {/* Invalid Rows Alert (Never Silently Dropped) */}
                {extraction.data.invalid_rows.length > 0 && (
                  <div className="p-4 rounded-lg bg-rose-50 border border-rose-300 space-y-2">
                    <div className="flex items-center gap-2 text-xs font-bold text-rose-900">
                      <XCircle className="w-4 h-4 text-rose-600" />
                      <span>
                        {extraction.data.invalid_rows.length} Invalid Rows Flagged (Preserved - Not Dropped)
                      </span>
                    </div>
                    <div className="space-y-1.5 max-h-36 overflow-y-auto">
                      {extraction.data.invalid_rows.map((row, idx) => (
                        <div
                          key={idx}
                          className="p-2 rounded bg-white/70 border border-rose-200 text-xs text-rose-900 flex items-center justify-between"
                        >
                          <span className="font-semibold">Row {row.row_number}:</span>
                          <span className="text-rose-700 italic">{row.error_reason}</span>
                          <span className="font-mono text-[11px] text-slate-600">
                            {JSON.stringify(row.raw_data)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Confirmation Success Banner */}
                {confirmSuccess && (
                  <div className="p-4 rounded-lg bg-emerald-50 border border-emerald-300 flex items-center gap-3 text-xs text-emerald-900 font-medium">
                    <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
                    <span>{confirmSuccess}</span>
                  </div>
                )}
              </div>

              {/* 1. Udhar Ledger Candidate Table */}
              {extraction.data.credit_transactions.length > 0 && (
                <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
                  <div className="p-4 border-b border-slate-100 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <UserCheck className="w-4 h-4 text-amber-600" />
                      <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                        Customer Udhar Candidates ({extraction.data.credit_transactions.length})
                      </h4>
                    </div>
                    <span className="text-[11px] text-slate-500">
                      Draft state • Review customer and direction
                    </span>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-xs text-left">
                      <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold">
                        <tr>
                          <th className="p-3">Customer</th>
                          <th className="p-3">Direction</th>
                          <th className="p-3">Amount (₹)</th>
                          <th className="p-3">Source Row</th>
                          <th className="p-3">Confidence</th>
                          <th className="p-3">Status / Flags</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {extraction.data.credit_transactions.map((tx: CandidateCreditTransaction, idx: number) => (
                          <tr key={idx} className="hover:bg-slate-50/60">
                            <td className="p-3 font-semibold text-slate-900">
                              {extraction.is_confirmed ? (
                                tx.customer_candidate_name
                              ) : (
                                <input
                                  type="text"
                                  value={tx.customer_candidate_name}
                                  onChange={(e) => {
                                    const copy = { ...extraction };
                                    copy.data.credit_transactions[idx].customer_candidate_name = e.target.value;
                                    setExtraction(copy);
                                  }}
                                  className="w-full px-2 py-1 border border-slate-200 rounded text-xs"
                                />
                              )}
                            </td>
                            <td className="p-3">
                              {extraction.is_confirmed ? (
                                <span
                                  className={`px-2 py-0.5 rounded font-bold text-[11px] ${
                                    tx.transaction_type === "CHARGE"
                                      ? "bg-rose-100 text-rose-800"
                                      : "bg-emerald-100 text-emerald-800"
                                  }`}
                                >
                                  {tx.transaction_type === "CHARGE" ? "CREDIT GIVEN" : "REPAYMENT"}
                                </span>
                              ) : (
                                <select
                                  value={tx.transaction_type}
                                  onChange={(e) => {
                                    const copy = { ...extraction };
                                    copy.data.credit_transactions[idx].transaction_type = e.target.value;
                                    copy.data.credit_transactions[idx].ambiguity_flags = [];
                                    setExtraction(copy);
                                  }}
                                  className="px-2 py-1 border border-slate-200 rounded text-xs font-semibold"
                                >
                                  <option value="CHARGE">CHARGE (Credit Given)</option>
                                  <option value="REPAYMENT">REPAYMENT (Jama Mila)</option>
                                </select>
                              )}
                            </td>
                            <td className="p-3 font-mono font-bold text-slate-900">
                              {extraction.is_confirmed ? (
                                `₹${tx.amount}`
                              ) : (
                                <input
                                  type="text"
                                  value={tx.amount}
                                  onChange={(e) => {
                                    const copy = { ...extraction };
                                    copy.data.credit_transactions[idx].amount = e.target.value;
                                    setExtraction(copy);
                                  }}
                                  className="w-24 px-2 py-1 border border-slate-200 rounded text-xs font-mono font-bold"
                                />
                              )}
                            </td>
                            <td className="p-3 font-mono text-slate-500">
                              Row #{tx.source_row || "-"}
                            </td>
                            <td className="p-3">
                              <span className="px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 text-[11px] font-semibold">
                                {Math.round(tx.confidence * 100)}%
                              </span>
                            </td>
                            <td className="p-3">
                              {tx.ambiguity_flags.length > 0 ? (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 text-[10px] font-bold">
                                  <AlertTriangle className="w-3 h-3" />
                                  Ambiguous Direction
                                </span>
                              ) : (
                                <span className="text-emerald-700 font-medium flex items-center gap-1 text-[11px]">
                                  <Check className="w-3.5 h-3.5" />
                                  Ready
                                </span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* 2. Sales Candidate Table */}
              {extraction.data.sales.length > 0 && (
                <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
                  <div className="p-4 border-b border-slate-100 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Database className="w-4 h-4 text-blue-600" />
                      <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                        Sales Transactions ({extraction.data.sales.length})
                      </h4>
                    </div>
                    <span className="text-[11px] text-slate-500">
                      Auto-dispatches stock movements on confirmation
                    </span>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-xs text-left">
                      <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold">
                        <tr>
                          <th className="p-3">Sale #</th>
                          <th className="p-3">Line Items</th>
                          <th className="p-3">Total Amount</th>
                          <th className="p-3">Mode</th>
                          <th className="p-3">Source Row</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {extraction.data.sales.map((s: CandidateSale, idx: number) => (
                          <tr key={idx} className="hover:bg-slate-50/60">
                            <td className="p-3 font-semibold text-slate-900 font-mono">
                              {s.sale_number}
                            </td>
                            <td className="p-3">
                              <div className="space-y-1">
                                {s.items.map((it, itIdx) => (
                                  <div key={itIdx} className="flex items-center gap-2">
                                    <span className="font-semibold text-slate-800">
                                      {it.product_name}
                                    </span>
                                    <span className="text-slate-500">
                                      ({it.quantity} @ ₹{it.unit_price})
                                    </span>
                                  </div>
                                ))}
                              </div>
                            </td>
                            <td className="p-3 font-mono font-bold text-slate-900">
                              ₹{s.total_amount}
                            </td>
                            <td className="p-3">
                              <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-semibold text-[11px]">
                                {s.payment_mode}
                              </span>
                            </td>
                            <td className="p-3 font-mono text-slate-500">
                              Row #{s.source_row || "-"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* 3. Expenses Candidate Table */}
              {extraction.data.expenses.length > 0 && (
                <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
                  <div className="p-4 border-b border-slate-100 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <FileSpreadsheet className="w-4 h-4 text-rose-600" />
                      <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                        Business Expenses ({extraction.data.expenses.length})
                      </h4>
                    </div>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-xs text-left">
                      <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold">
                        <tr>
                          <th className="p-3">Category</th>
                          <th className="p-3">Description</th>
                          <th className="p-3">Amount</th>
                          <th className="p-3">Mode</th>
                          <th className="p-3">Source Row</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {extraction.data.expenses.map((exp: CandidateExpense, idx: number) => (
                          <tr key={idx} className="hover:bg-slate-50/60">
                            <td className="p-3">
                              <span className="px-2 py-0.5 rounded font-bold text-[11px] bg-rose-50 text-rose-800">
                                {exp.category}
                              </span>
                            </td>
                            <td className="p-3 text-slate-700">{exp.description || "-"}</td>
                            <td className="p-3 font-mono font-bold text-slate-900">
                              ₹{exp.amount}
                            </td>
                            <td className="p-3 font-semibold text-slate-600">{exp.payment_mode}</td>
                            <td className="p-3 font-mono text-slate-500">
                              Row #{exp.source_row || "-"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Action Buttons Bar */}
              <div className="flex flex-col sm:flex-row items-center justify-between gap-3 p-4 bg-white rounded-xl border border-slate-200 shadow-xs">
                <div className="text-xs text-slate-500 flex items-center gap-1.5">
                  <Info className="w-4 h-4 text-indigo-600" />
                  <span>
                    Confirming records writes directly to authoritative sales, inventory dispatch, and Udhar ledger tables.
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  {!extraction.is_confirmed && (
                    <button
                      onClick={handleSaveEdits}
                      disabled={savingEdits || confirming}
                      className="px-4 py-2 rounded-lg border border-slate-300 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                    >
                      {savingEdits ? "Saving..." : "Save Edits"}
                    </button>
                  )}

                  <button
                    onClick={handleConfirmPosting}
                    disabled={confirming}
                    className={`inline-flex items-center gap-2 px-5 py-2 rounded-lg text-xs font-bold text-white shadow-xs transition-all ${
                      extraction.is_confirmed
                        ? "bg-emerald-600 hover:bg-emerald-700"
                        : "bg-indigo-600 hover:bg-indigo-700"
                    } disabled:opacity-50`}
                  >
                    {confirming ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>Posting to Ledger...</span>
                      </>
                    ) : (
                      <>
                        <CheckCircle2 className="w-4 h-4" />
                        <span>
                          {extraction.is_confirmed
                            ? "Re-Confirm (Idempotent Test)"
                            : "Confirm & Post to Ledger"}
                        </span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Mode 4: Ingestion History */}
      {activeTab === "history" && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
          <div className="p-4 sm:p-5 border-b border-slate-100 flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-900">Document Ingestion History</h3>
            <button
              onClick={fetchDocs}
              className="p-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 text-xs"
              title="Refresh"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>

          {documents.length === 0 ? (
            <div className="p-8 text-center space-y-2">
              <FileSpreadsheet className="w-8 h-8 text-slate-400 mx-auto" />
              <p className="text-xs text-slate-500">No documents ingested yet.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold">
                  <tr>
                    <th className="p-3">Filename</th>
                    <th className="p-3">Type</th>
                    <th className="p-3">Size</th>
                    <th className="p-3">Status</th>
                    <th className="p-3">Ambiguities</th>
                    <th className="p-3">Created</th>
                    <th className="p-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {documents.map((doc) => (
                    <tr
                      key={doc.id}
                      className={`hover:bg-slate-50/60 ${
                        selectedDocId === doc.id ? "bg-indigo-50/40" : ""
                      }`}
                    >
                      <td className="p-3 font-semibold text-slate-900">
                        {doc.filename}
                      </td>
                      <td className="p-3 font-mono">{doc.file_type}</td>
                      <td className="p-3 font-mono">
                        {(doc.file_size_bytes / 1024).toFixed(1)} KB
                      </td>
                      <td className="p-3">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            doc.is_confirmed
                              ? "bg-emerald-100 text-emerald-800"
                              : doc.status === "PROCESSED"
                              ? "bg-amber-100 text-amber-800"
                              : "bg-slate-100 text-slate-700"
                          }`}
                        >
                          {doc.is_confirmed ? "CONFIRMED" : doc.status}
                        </span>
                      </td>
                      <td className="p-3 font-mono">
                        {doc.ambiguity_count > 0 ? (
                          <span className="text-amber-700 font-bold">
                            {doc.ambiguity_count} flagged
                          </span>
                        ) : (
                          <span className="text-slate-400">0</span>
                        )}
                      </td>
                      <td className="p-3 text-slate-500">
                        {new Date(doc.created_at).toLocaleString("en-IN", {
                          dateStyle: "short",
                          timeStyle: "short",
                        })}
                      </td>
                      <td className="p-3 text-right">
                        <button
                          onClick={() => loadDocumentExtraction(doc.id)}
                          className="inline-flex items-center gap-1 px-3 py-1 rounded bg-slate-100 text-slate-700 hover:bg-slate-900 hover:text-white transition-all text-xs font-semibold"
                        >
                          <Eye className="w-3.5 h-3.5" />
                          <span>Review</span>
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
