"use client";

import React, { useEffect, useState } from "react";
import {
  AlertCircle,
  Archive,
  ArrowDownLeft,
  ArrowUpRight,
  BookOpen,
  Calendar,
  CheckCircle2,
  Clock,
  Copy,
  FileSpreadsheet,
  Info,
  MessageSquare,
  RefreshCw,
  RotateCcw,
  Search,
  Send,
  ShieldAlert,
  UserPlus,
  Users,
  Wallet,
} from "lucide-react";

import {
  archiveCustomer,
  createCustomer,
  getCustomerLedger,
  getCustomerStatement,
  getUdharSummary,
  listCustomers,
  recordCharge,
  recordRepayment,
  reverseTransaction,
  unarchiveCustomer,
} from "@/lib/api";
import type {
  ChargeCreate,
  CustomerCreate,
  CustomerDuplicateMatch,
  CustomerLedgerResponse,
  CustomerResponse,
  CustomerStatement,
  RepaymentCreate,
  StatementLineItem,
  UdharSummary,
} from "@/lib/types/udhar";

export function UdharDashboard() {
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Data states
  const [summary, setSummary] = useState<UdharSummary | null>(null);
  const [customers, setCustomers] = useState<CustomerResponse[]>([]);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [includeArchived, setIncludeArchived] = useState<boolean>(false);

  // Active Modals
  const [showAddCustomerModal, setShowAddCustomerModal] = useState<boolean>(false);
  const [showChargeModal, setShowChargeModal] = useState<boolean>(false);
  const [showRepaymentModal, setShowRepaymentModal] = useState<boolean>(false);
  const [showLedgerModal, setShowLedgerModal] = useState<boolean>(false);
  const [showStatementModal, setShowStatementModal] = useState<boolean>(false);
  const [showReminderModal, setShowReminderModal] = useState<boolean>(false);
  const [showReverseModal, setShowReverseModal] = useState<boolean>(false);

  // Active Customer selection
  const [selectedCustomer, setSelectedCustomer] = useState<CustomerResponse | null>(null);
  const [activeLedger, setActiveLedger] = useState<CustomerLedgerResponse | null>(null);
  const [activeStatement, setActiveStatement] = useState<CustomerStatement | null>(null);
  const [statementStartDate, setStatementStartDate] = useState<string>("");
  const [statementEndDate, setStatementEndDate] = useState<string>("");

  // Reversal selection
  const [txToReverse, setTxToReverse] = useState<StatementLineItem | null>(null);
  const [reversalReason, setReversalReason] = useState<string>("");

  // Reminder State
  const [reminderLanguage, setReminderLanguage] = useState<"Hinglish" | "Hindi" | "English">("Hinglish");
  const [copiedDraft, setCopiedDraft] = useState<boolean>(false);

  // New Customer Form
  const [newCustName, setNewCustName] = useState<string>("");
  const [newCustPhone, setNewCustPhone] = useState<string>("");
  const [newCustLimit, setNewCustLimit] = useState<string>("");
  const [newCustOpeningBal, setNewCustOpeningBal] = useState<string>("");
  const [newCustOpeningDue, setNewCustOpeningDue] = useState<string>("");
  const [newCustNotes, setNewCustNotes] = useState<string>("");
  const [duplicateWarnings, setDuplicateWarnings] = useState<CustomerDuplicateMatch[]>([]);

  // Charge Form
  const [chargeAmount, setChargeAmount] = useState<string>("");
  const [chargeDueDate, setChargeDueDate] = useState<string>("");
  const [chargeDescription, setChargeDescription] = useState<string>("");
  const [chargeReference, setChargeReference] = useState<string>("");

  // Repayment Form
  const [repayAmount, setRepayAmount] = useState<string>("");
  const [repayMode, setRepayMode] = useState<"CASH" | "UPI" | "BANK_TRANSFER" | "CHEQUE" | "OTHER">("CASH");
  const [repayRef, setRepayRef] = useState<string>("");
  const [repayDesc, setRepayDesc] = useState<string>("");
  const [autoAllocate, setAutoAllocate] = useState<boolean>(true);

  // Load summary and customer list
  const refreshData = () => {
    setLoading(true);
    setError(null);
    Promise.all([
      getUdharSummary(),
      listCustomers(searchQuery, includeArchived),
    ])
      .then(([summaryRes, custList]) => {
        setSummary(summaryRes.data);
        setCustomers(custList);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load Udhar records");
      })
      .finally(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    let isMounted = true;
    Promise.all([
      getUdharSummary(),
      listCustomers(searchQuery, includeArchived),
    ])
      .then(([summaryRes, custList]) => {
        if (isMounted) {
          setSummary(summaryRes.data);
          setCustomers(custList);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (isMounted) {
          setError(err instanceof Error ? err.message : "Failed to load Udhar records");
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [searchQuery, includeArchived]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    refreshData();
  };

  const showNotification = (msg: string) => {
    setSuccessMsg(msg);
    setTimeout(() => setSuccessMsg(null), 4000);
  };

  // -------------------------------------------------------------
  // Customer Handlers
  // -------------------------------------------------------------
  const handleOpenAddCustomer = () => {
    setNewCustName("");
    setNewCustPhone("");
    setNewCustLimit("");
    setNewCustOpeningBal("");
    setNewCustOpeningDue("");
    setNewCustNotes("");
    setDuplicateWarnings([]);
    setShowAddCustomerModal(true);
  };

  const handleNameOrPhoneChange = (name: string, phone: string) => {
    setNewCustName(name);
    setNewCustPhone(phone);
    if (!name.trim()) {
      setDuplicateWarnings([]);
      return;
    }
    const cleanName = name.trim().toLowerCase();
    const cleanPhone = phone.trim();
    const matched: CustomerDuplicateMatch[] = [];

    customers.forEach((c) => {
      if (cleanPhone && c.phone_e164 && c.phone_e164.includes(cleanPhone)) {
        matched.push({
          existing_customer_id: c.id,
          existing_display_name: c.display_name,
          existing_phone: c.phone_e164,
          match_type: "PHONE_MATCH",
        });
      } else if (c.display_name.toLowerCase() === cleanName) {
        matched.push({
          existing_customer_id: c.id,
          existing_display_name: c.display_name,
          existing_phone: c.phone_e164,
          match_type: "EXACT_NAME",
        });
      }
    });
    setDuplicateWarnings(matched);
  };

  const handleCreateCustomerSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCustName.trim()) return;
    try {
      setLoading(true);
      const payload: CustomerCreate = {
        display_name: newCustName.trim(),
        phone_e164: newCustPhone.trim() || null,
        credit_limit: newCustLimit ? parseFloat(newCustLimit) : null,
        opening_balance: newCustOpeningBal ? parseFloat(newCustOpeningBal) : null,
        opening_balance_due_at: newCustOpeningDue ? new Date(newCustOpeningDue).toISOString() : null,
        notes: newCustNotes.trim() || null,
      };
      const res = await createCustomer(payload);
      setShowAddCustomerModal(false);
      showNotification(`Customer "${res.customer.display_name}" created successfully`);
      refreshData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create customer");
    } finally {
      setLoading(false);
    }
  };

  const handleToggleArchive = async (cust: CustomerResponse) => {
    try {
      setLoading(true);
      if (cust.is_active) {
        await archiveCustomer(cust.id);
        showNotification(`Customer "${cust.display_name}" archived`);
      } else {
        await unarchiveCustomer(cust.id);
        showNotification(`Customer "${cust.display_name}" restored`);
      }
      refreshData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to toggle archive status");
    } finally {
      setLoading(false);
    }
  };

  // -------------------------------------------------------------
  // Charge & Repayment Handlers
  // -------------------------------------------------------------
  const handleOpenCharge = (cust: CustomerResponse) => {
    setSelectedCustomer(cust);
    setChargeAmount("");
    setChargeDueDate("");
    setChargeDescription("");
    setChargeReference("");
    setShowChargeModal(true);
  };

  const handleRecordChargeSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCustomer || !chargeAmount) return;
    try {
      setLoading(true);
      const payload: ChargeCreate = {
        customer_id: selectedCustomer.id,
        amount: parseFloat(chargeAmount),
        due_at: chargeDueDate ? new Date(chargeDueDate).toISOString() : null,
        description: chargeDescription.trim() || null,
        reference: chargeReference.trim() || null,
      };
      const res = await recordCharge(payload);
      setShowChargeModal(false);
      showNotification(
        `Recorded charge of ₹${Number(res.amount).toFixed(2)}. New balance: ₹${Number(res.new_balance).toFixed(2)}`
      );
      refreshData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to record charge");
    } finally {
      setLoading(false);
    }
  };

  const handleOpenRepayment = (cust: CustomerResponse) => {
    setSelectedCustomer(cust);
    setRepayAmount("");
    setRepayMode("CASH");
    setRepayRef("");
    setRepayDesc("");
    setAutoAllocate(true);
    setShowRepaymentModal(true);
  };

  const handleRecordRepaymentSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCustomer || !repayAmount) return;
    try {
      setLoading(true);
      const payload: RepaymentCreate = {
        customer_id: selectedCustomer.id,
        amount: parseFloat(repayAmount),
        payment_mode: repayMode,
        reference: repayRef.trim() || null,
        description: repayDesc.trim() || null,
        auto_allocate: autoAllocate,
      };
      const res = await recordRepayment(payload);
      setShowRepaymentModal(false);
      showNotification(
        `Recorded repayment of ₹${Number(res.amount).toFixed(2)} via ${res.payment_mode}. New balance: ₹${Number(
          res.new_balance
        ).toFixed(2)}`
      );
      refreshData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to record repayment");
    } finally {
      setLoading(false);
    }
  };

  // -------------------------------------------------------------
  // Ledger & Statement Handlers
  // -------------------------------------------------------------
  const handleOpenLedger = async (cust: CustomerResponse) => {
    setSelectedCustomer(cust);
    try {
      setLoading(true);
      const ledger = await getCustomerLedger(cust.id);
      setActiveLedger(ledger);
      setShowLedgerModal(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to fetch customer ledger");
    } finally {
      setLoading(false);
    }
  };

  const handleOpenStatement = async (cust: CustomerResponse) => {
    setSelectedCustomer(cust);
    setStatementStartDate("");
    setStatementEndDate("");
    try {
      setLoading(true);
      const res = await getCustomerStatement(cust.id);
      setActiveStatement(res.data);
      setShowStatementModal(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to fetch statement");
    } finally {
      setLoading(false);
    }
  };

  const handleFilterStatement = async () => {
    if (!selectedCustomer) return;
    try {
      setLoading(true);
      const startIso = statementStartDate ? new Date(statementStartDate).toISOString() : undefined;
      const endIso = statementEndDate ? new Date(statementEndDate).toISOString() : undefined;
      const res = await getCustomerStatement(selectedCustomer.id, startIso, endIso);
      setActiveStatement(res.data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to update statement interval");
    } finally {
      setLoading(false);
    }
  };

  // -------------------------------------------------------------
  // Reversal Workflow
  // -------------------------------------------------------------
  const handlePromptReverse = (line: StatementLineItem) => {
    setTxToReverse(line);
    setReversalReason("");
    setShowReverseModal(true);
  };

  const handleConfirmReverse = async () => {
    if (!txToReverse || !reversalReason.trim() || !selectedCustomer) return;
    try {
      setLoading(true);
      await reverseTransaction(txToReverse.transaction_id, { reason: reversalReason.trim() });
      setShowReverseModal(false);
      showNotification(`Transaction ${txToReverse.transaction_id.slice(0, 8)} reversed successfully`);
      // Refresh ledger
      const updatedLedger = await getCustomerLedger(selectedCustomer.id);
      setActiveLedger(updatedLedger);
      refreshData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to reverse transaction");
    } finally {
      setLoading(false);
    }
  };

  // -------------------------------------------------------------
  // Reminder Draft Handler
  // -------------------------------------------------------------
  const handleOpenReminder = (cust: CustomerResponse) => {
    setSelectedCustomer(cust);
    setReminderLanguage("Hinglish");
    setCopiedDraft(false);
    setShowReminderModal(true);
  };

  const getDraftText = () => {
    if (!selectedCustomer) return "";
    const name = selectedCustomer.display_name;
    const bal = Number(selectedCustomer.outstanding_balance).toFixed(2);
    if (reminderLanguage === "Hindi") {
      return `नमस्ते ${name} जी, आपका शर्मा किराना स्टोर पर कुल बकाया उधार ₹${bal} है। कृपया समय पर भुगतान करने की कृपा करें। धन्यवाद!`;
    } else if (reminderLanguage === "English") {
      return `Dear ${name}, this is a gentle reminder regarding your outstanding balance of ₹${bal} at Sharma Kirana Store. Kindly settle the dues at your earliest convenience. Thank you!`;
    }
    return `Namaste ${name} ji, aapka Sharma Kirana Store par kul bakaya udhar ₹${bal} hai. Kripya samay par bhuqtan karein. Dhanyawaad!`;
  };

  const getWhatsAppLink = () => {
    if (!selectedCustomer || !selectedCustomer.phone_e164) return null;
    const cleanDigits = selectedCustomer.phone_e164.replace(/\D/g, "");
    const formatted = cleanDigits.length === 10 ? `91${cleanDigits}` : cleanDigits;
    return `https://api.whatsapp.com/send?phone=${formatted}&text=${encodeURIComponent(getDraftText())}`;
  };

  const handleCopyDraft = () => {
    navigator.clipboard.writeText(getDraftText());
    setCopiedDraft(true);
    setTimeout(() => setCopiedDraft(false), 2000);
  };

  // Calculate dynamic credit limit warning for charge modal
  const selectedBalanceNum = selectedCustomer ? Number(selectedCustomer.outstanding_balance) : 0;
  const chargeAmountNum = chargeAmount ? parseFloat(chargeAmount) || 0 : 0;
  const newEstimatedBalance = selectedBalanceNum + chargeAmountNum;
  const creditLimitNum = selectedCustomer && selectedCustomer.credit_limit ? Number(selectedCustomer.credit_limit) : null;
  const isOverLimit = creditLimitNum !== null && newEstimatedBalance > creditLimitNum;

  return (
    <div className="space-y-6">
      {/* Notifications */}
      {successMsg && (
        <div className="flex items-center gap-2 p-3 bg-emerald-50 text-emerald-800 border border-emerald-200 rounded-lg text-sm font-medium">
          <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 p-3 bg-rose-50 text-rose-800 border border-rose-200 rounded-lg text-sm font-medium">
          <AlertCircle className="w-5 h-5 text-rose-600 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Top Header & Summary KPI Cards */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <BookOpen className="w-7 h-7 text-indigo-600" />
            Udhar Management (Customer Khata)
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Deterministic customer receivables, chronological ledger events, overdue aging, and un-sent reminder previews.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={refreshData}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm font-medium rounded-lg transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
          <button
            onClick={handleOpenAddCustomer}
            className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg shadow-sm transition-colors"
          >
            <UserPlus className="w-4 h-4" />
            Add Customer
          </button>
        </div>
      </div>

      {/* Receivables & Overdue KPI Row */}
      {summary && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <div className="p-4 bg-white border border-slate-200 rounded-xl shadow-xs">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                Total Receivables
              </span>
              <span className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
                <Wallet className="w-5 h-5" />
              </span>
            </div>
            <div className="text-2xl font-extrabold text-slate-900 mt-2">
              ₹{Number(summary.total_receivables).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
            </div>
            <div className="text-xs text-slate-500 mt-1 flex items-center gap-1">
              <Info className="w-3.5 h-3.5" />
              <span>Receivables are distinct from cash & revenue</span>
            </div>
          </div>

          <div className="p-4 bg-white border border-slate-200 rounded-xl shadow-xs">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                Total Overdue
              </span>
              <span className="p-2 bg-rose-50 text-rose-600 rounded-lg">
                <Clock className="w-5 h-5" />
              </span>
            </div>
            <div className="text-2xl font-extrabold text-rose-600 mt-2">
              ₹{Number(summary.overdue_amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
            </div>
            <div className="text-xs text-slate-500 mt-1">
              Outstanding debt past customer due dates
            </div>
          </div>

          <div className="p-4 bg-white border border-slate-200 rounded-xl shadow-xs sm:col-span-2 lg:col-span-1">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                Active Debt Customers
              </span>
              <span className="p-2 bg-emerald-50 text-emerald-600 rounded-lg">
                <Users className="w-5 h-5" />
              </span>
            </div>
            <div className="text-2xl font-extrabold text-slate-900 mt-2">
              {summary.customers_with_balance_count} Customers
            </div>
            <div className="text-xs text-slate-500 mt-1">
              With balance &gt; ₹0.00
            </div>
          </div>
        </div>
      )}

      {/* Aging Distribution Buckets */}
      {summary && summary.aging_buckets && (
        <div className="p-4 bg-white border border-slate-200 rounded-xl shadow-xs">
          <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <Clock className="w-4 h-4 text-slate-400" />
            Receivables Overdue Aging Buckets
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {summary.aging_buckets.map((b) => {
              const isNotDue = b.bucket_key === "NOT_DUE";
              const isSevere = b.bucket_key === "60_PLUS_DAYS" || b.bucket_key === "31_60_DAYS";
              return (
                <div
                  key={b.bucket_key}
                  className={`p-3 rounded-lg border text-sm flex flex-col justify-between ${
                    isNotDue
                      ? "bg-emerald-50/50 border-emerald-200 text-emerald-950"
                      : isSevere
                      ? "bg-rose-50/50 border-rose-200 text-rose-950"
                      : "bg-amber-50/50 border-amber-200 text-amber-950"
                  }`}
                >
                  <span className="text-xs font-semibold">{b.label}</span>
                  <div className="mt-2">
                    <span className="text-base font-bold">
                      ₹{Number(b.amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                    </span>
                    <span className="text-xs opacity-75 block">
                      {b.customer_count} {b.customer_count === 1 ? "customer" : "customers"}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Customer Directory Bar & Search */}
      <div className="p-4 bg-white border border-slate-200 rounded-xl shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
          <form onSubmit={handleSearchSubmit} className="flex items-center gap-2 flex-1 max-w-md">
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search by customer name or phone..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
              />
            </div>
            <button
              type="submit"
              className="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm font-medium rounded-lg transition-colors"
            >
              Search
            </button>
          </form>

          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-xs font-medium text-slate-600 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={includeArchived}
                onChange={(e) => setIncludeArchived(e.target.checked)}
                className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
              />
              <span>Show Archived Customers</span>
            </label>
          </div>
        </div>

        {/* Customer Table */}
        <div className="overflow-x-auto border border-slate-100 rounded-lg">
          <table className="w-full text-left text-sm text-slate-700">
            <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase tracking-wider">
              <tr>
                <th className="py-3 px-4">Customer Name</th>
                <th className="py-3 px-4">Phone</th>
                <th className="py-3 px-4 text-right">Balance</th>
                <th className="py-3 px-4">Aging Status</th>
                <th className="py-3 px-4 text-right">Credit Limit</th>
                <th className="py-3 px-4 text-center">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-normal">
              {customers.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-8 text-slate-400 text-sm">
                    {loading ? "Loading customer directory..." : "No customers found. Add your first customer above."}
                  </td>
                </tr>
              ) : (
                customers.map((c) => {
                  const bal = Number(c.outstanding_balance);
                  const overdue = Number(c.overdue_amount);
                  const limit = c.credit_limit ? Number(c.credit_limit) : null;
                  return (
                    <tr
                      key={c.id}
                      className={`hover:bg-slate-50/75 transition-colors ${
                        !c.is_active ? "opacity-60 bg-slate-50/50" : ""
                      }`}
                    >
                      <td className="py-3 px-4">
                        <div className="font-semibold text-slate-900 flex items-center gap-2">
                          {c.display_name}
                          {!c.is_active && (
                            <span className="text-3xs uppercase px-1.5 py-0.5 rounded bg-slate-200 text-slate-600 font-bold">
                              Archived
                            </span>
                          )}
                        </div>
                        {c.notes && <div className="text-xs text-slate-400 mt-0.5">{c.notes}</div>}
                      </td>

                      <td className="py-3 px-4 text-slate-600 font-mono text-xs">
                        {c.phone_e164 || "—"}
                      </td>

                      <td className="py-3 px-4 text-right">
                        <span
                          className={`font-bold ${
                            bal > 0 ? "text-slate-900" : "text-emerald-600"
                          }`}
                        >
                          ₹{bal.toFixed(2)}
                        </span>
                        {overdue > 0 && (
                          <div className="text-3xs text-rose-600 font-medium">
                            ₹{overdue.toFixed(2)} overdue
                          </div>
                        )}
                      </td>

                      <td className="py-3 px-4">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                            c.aging_bucket === "NOT_DUE"
                              ? "bg-slate-100 text-slate-700"
                              : c.aging_bucket === "1_7_DAYS"
                              ? "bg-amber-100 text-amber-800"
                              : c.aging_bucket === "8_30_DAYS"
                              ? "bg-orange-100 text-orange-800"
                              : "bg-rose-100 text-rose-800"
                          }`}
                        >
                          {c.aging_bucket.replace(/_/g, " ")}
                        </span>
                      </td>

                      <td className="py-3 px-4 text-right text-xs">
                        {limit ? `₹${limit.toFixed(2)}` : <span className="text-slate-400">No Limit</span>}
                      </td>

                      <td className="py-3 px-4 text-center">
                        <div className="flex items-center justify-center gap-1">
                          <button
                            title="Give Udhar (Credit Sale)"
                            onClick={() => handleOpenCharge(c)}
                            disabled={!c.is_active}
                            className="p-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 rounded-md transition-colors disabled:opacity-40"
                          >
                            <ArrowUpRight className="w-4 h-4" />
                          </button>
                          <button
                            title="Receive Repayment"
                            onClick={() => handleOpenRepayment(c)}
                            disabled={!c.is_active || bal <= 0}
                            className="p-1.5 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 rounded-md transition-colors disabled:opacity-40"
                          >
                            <ArrowDownLeft className="w-4 h-4" />
                          </button>
                          <button
                            title="View Full Ledger"
                            onClick={() => handleOpenLedger(c)}
                            className="p-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-md transition-colors"
                          >
                            <BookOpen className="w-4 h-4" />
                          </button>
                          <button
                            title="Generate Statement"
                            onClick={() => handleOpenStatement(c)}
                            className="p-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-md transition-colors"
                          >
                            <FileSpreadsheet className="w-4 h-4" />
                          </button>
                          <button
                            title="Reminder Draft Preview"
                            onClick={() => handleOpenReminder(c)}
                            disabled={bal <= 0}
                            className="p-1.5 bg-sky-50 hover:bg-sky-100 text-sky-700 rounded-md transition-colors disabled:opacity-40"
                          >
                            <MessageSquare className="w-4 h-4" />
                          </button>
                          <button
                            title={c.is_active ? "Archive Customer" : "Restore Customer"}
                            onClick={() => handleToggleArchive(c)}
                            className="p-1.5 hover:bg-slate-100 text-slate-400 hover:text-slate-600 rounded-md transition-colors"
                          >
                            <Archive className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ========================================================= */}
      {/* MODAL 1: Add Customer                                      */}
      {/* ========================================================= */}
      {showAddCustomerModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <UserPlus className="w-5 h-5 text-indigo-600" />
                Add New Customer
              </h2>
              <button
                onClick={() => setShowAddCustomerModal(false)}
                className="text-slate-400 hover:text-slate-600 text-lg leading-none"
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleCreateCustomerSubmit} className="p-6 space-y-4">
              {duplicateWarnings.length > 0 && (
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-900">
                  <div className="font-semibold flex items-center gap-1 mb-1">
                    <ShieldAlert className="w-4 h-4 text-amber-600" />
                    Duplicate Warning:
                  </div>
                  Found existing customer(s):{" "}
                  {duplicateWarnings.map((d) => d.existing_display_name).join(", ")}.
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Customer Display Name <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={newCustName}
                  onChange={(e) => handleNameOrPhoneChange(e.target.value, newCustPhone)}
                  placeholder="e.g. Ramesh Kumar"
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Phone (Optional E.164)
                </label>
                <input
                  type="text"
                  value={newCustPhone}
                  onChange={(e) => handleNameOrPhoneChange(newCustName, e.target.value)}
                  placeholder="e.g. +919876543210"
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Credit Limit (₹)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={newCustLimit}
                    onChange={(e) => setNewCustLimit(e.target.value)}
                    placeholder="e.g. 5000"
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Opening Balance (₹)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={newCustOpeningBal}
                    onChange={(e) => setNewCustOpeningBal(e.target.value)}
                    placeholder="e.g. 1500"
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                  />
                </div>
              </div>

              {parseFloat(newCustOpeningBal) > 0 && (
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Opening Balance Due Date
                  </label>
                  <input
                    type="date"
                    value={newCustOpeningDue}
                    onChange={(e) => setNewCustOpeningDue(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                  />
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Notes / Address (Optional)
                </label>
                <textarea
                  rows={2}
                  value={newCustNotes}
                  onChange={(e) => setNewCustNotes(e.target.value)}
                  placeholder="e.g. Lane 3, near temple"
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddCustomerModal(false)}
                  className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm font-medium rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading || !newCustName.trim()}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg shadow-sm transition-colors disabled:opacity-50"
                >
                  Create Customer
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* MODAL 2: Give Udhar (Record Charge)                         */}
      {/* ========================================================= */}
      {showChargeModal && selectedCustomer && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                  <ArrowUpRight className="w-5 h-5 text-indigo-600" />
                  Give Udhar (Credit Sale)
                </h2>
                <p className="text-xs text-slate-500">
                  Customer: <span className="font-semibold text-slate-800">{selectedCustomer.display_name}</span> | Current Balance: ₹{selectedBalanceNum.toFixed(2)}
                </p>
              </div>
              <button
                onClick={() => setShowChargeModal(false)}
                className="text-slate-400 hover:text-slate-600 text-lg leading-none"
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleRecordChargeSubmit} className="p-6 space-y-4">
              {isOverLimit && (
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-900 flex items-start gap-2">
                  <ShieldAlert className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold">Credit Limit Warning:</span> New balance of ₹
                    {newEstimatedBalance.toFixed(2)} exceeds customer limit of ₹
                    {creditLimitNum?.toFixed(2)}. Owner confirmation permitted.
                  </div>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Amount (₹) <span className="text-rose-500">*</span>
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  required
                  value={chargeAmount}
                  onChange={(e) => setChargeAmount(e.target.value)}
                  placeholder="0.00"
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm font-semibold focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Due Date (Optional)
                </label>
                <input
                  type="date"
                  value={chargeDueDate}
                  onChange={(e) => setChargeDueDate(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Bill Reference / Invoice # (Optional)
                </label>
                <input
                  type="text"
                  value={chargeReference}
                  onChange={(e) => setChargeReference(e.target.value)}
                  placeholder="e.g. BILL-1029"
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Description / Items (Optional)
                </label>
                <input
                  type="text"
                  value={chargeDescription}
                  onChange={(e) => setChargeDescription(e.target.value)}
                  placeholder="e.g. 5kg Atta, 2L Mustard Oil"
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowChargeModal(false)}
                  className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm font-medium rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading || !chargeAmount || parseFloat(chargeAmount) <= 0}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg shadow-sm transition-colors disabled:opacity-50"
                >
                  Confirm Charge
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* MODAL 3: Receive Repayment                                 */}
      {/* ========================================================= */}
      {showRepaymentModal && selectedCustomer && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                  <ArrowDownLeft className="w-5 h-5 text-emerald-600" />
                  Receive Repayment
                </h2>
                <p className="text-xs text-slate-500">
                  Customer: <span className="font-semibold text-slate-800">{selectedCustomer.display_name}</span> | Outstanding: ₹{selectedBalanceNum.toFixed(2)}
                </p>
              </div>
              <button
                onClick={() => setShowRepaymentModal(false)}
                className="text-slate-400 hover:text-slate-600 text-lg leading-none"
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleRecordRepaymentSubmit} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Repayment Amount (₹) <span className="text-rose-500">*</span>
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  required
                  value={repayAmount}
                  onChange={(e) => setRepayAmount(e.target.value)}
                  placeholder="0.00"
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm font-semibold focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Payment Mode
                </label>
                <select
                  value={repayMode}
                  onChange={(e) =>
                    setRepayMode(
                      e.target.value as "CASH" | "UPI" | "BANK_TRANSFER" | "CHEQUE" | "OTHER"
                    )
                  }
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                >
                  <option value="CASH">Cash</option>
                  <option value="UPI">UPI (Google Pay / PhonePe / Paytm)</option>
                  <option value="BANK_TRANSFER">Bank Transfer / NEFT</option>
                  <option value="CHEQUE">Cheque</option>
                  <option value="OTHER">Other</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Reference / UPI Txn ID (Optional)
                </label>
                <input
                  type="text"
                  value={repayRef}
                  onChange={(e) => setRepayRef(e.target.value)}
                  placeholder="e.g. UPI-12345678"
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Notes (Optional)
                </label>
                <input
                  type="text"
                  value={repayDesc}
                  onChange={(e) => setRepayDesc(e.target.value)}
                  placeholder="e.g. Cleared bill 1029"
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                />
              </div>

              <div className="pt-1">
                <label className="flex items-center gap-2 text-xs font-medium text-slate-700 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={autoAllocate}
                    onChange={(e) => setAutoAllocate(e.target.checked)}
                    className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                  />
                  <span>Automatically allocate to oldest open charges (FIFO)</span>
                </label>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowRepaymentModal(false)}
                  className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm font-medium rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading || !repayAmount || parseFloat(repayAmount) <= 0}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium rounded-lg shadow-sm transition-colors disabled:opacity-50"
                >
                  Record Repayment
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* MODAL 4: Full Customer Ledger (Running Balance)            */}
      {/* ========================================================= */}
      {showLedgerModal && selectedCustomer && activeLedger && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-4xl w-full max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
              <div>
                <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                  <BookOpen className="w-5 h-5 text-indigo-600" />
                  Customer Ledger: {activeLedger.customer_name}
                </h2>
                <p className="text-xs text-slate-500">
                  Outstanding Balance: <span className="font-bold text-slate-900">₹{Number(activeLedger.outstanding_balance).toFixed(2)}</span>
                  {activeLedger.credit_limit && (
                    <span> | Credit Limit: ₹{Number(activeLedger.credit_limit).toFixed(2)}</span>
                  )}
                </p>
              </div>
              <button
                onClick={() => setShowLedgerModal(false)}
                className="text-slate-400 hover:text-slate-600 text-lg leading-none"
              >
                &times;
              </button>
            </div>

            <div className="p-6 overflow-y-auto flex-1">
              <div className="overflow-x-auto border border-slate-100 rounded-lg">
                <table className="w-full text-left text-xs text-slate-700">
                  <thead className="bg-slate-50 border-b border-slate-200 font-semibold text-slate-500 uppercase tracking-wider">
                    <tr>
                      <th className="py-2.5 px-3">Date</th>
                      <th className="py-2.5 px-3">Type</th>
                      <th className="py-2.5 px-3">Details / Reference</th>
                      <th className="py-2.5 px-3 text-right">Debit (+)</th>
                      <th className="py-2.5 px-3 text-right">Credit (-)</th>
                      <th className="py-2.5 px-3 text-right">Balance</th>
                      <th className="py-2.5 px-3 text-center">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {activeLedger.lines.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="text-center py-6 text-slate-400">
                          No transactions recorded yet.
                        </td>
                      </tr>
                    ) : (
                      activeLedger.lines.map((line) => {
                        const isReversal = line.transaction_type === "REVERSAL";
                        return (
                          <tr key={line.transaction_id} className="hover:bg-slate-50/75">
                            <td className="py-2.5 px-3 font-mono text-slate-500">
                              {new Date(line.transaction_at).toLocaleDateString("en-IN", {
                                day: "2-digit",
                                month: "short",
                                year: "numeric",
                              })}
                            </td>

                            <td className="py-2.5 px-3 font-medium">
                              <span
                                className={`inline-block px-1.5 py-0.5 rounded text-3xs font-bold uppercase ${
                                  line.transaction_type === "CHARGE"
                                    ? "bg-indigo-50 text-indigo-700"
                                    : line.transaction_type === "OPENING_BALANCE"
                                    ? "bg-purple-50 text-purple-700"
                                    : line.transaction_type === "REPAYMENT"
                                    ? "bg-emerald-50 text-emerald-700"
                                    : "bg-rose-50 text-rose-700"
                                }`}
                              >
                                {line.transaction_type}
                              </span>
                            </td>

                            <td className="py-2.5 px-3">
                              <div className="font-medium text-slate-800">
                                {line.description || "—"}
                              </div>
                              {line.reference && (
                                <div className="text-3xs text-slate-400 font-mono">
                                  Ref: {line.reference}
                                </div>
                              )}
                            </td>

                            <td className="py-2.5 px-3 text-right font-medium text-indigo-700">
                              {line.charge_amount ? `₹${Number(line.charge_amount).toFixed(2)}` : "—"}
                            </td>

                            <td className="py-2.5 px-3 text-right font-medium text-emerald-700">
                              {line.repayment_amount ? `₹${Number(line.repayment_amount).toFixed(2)}` : "—"}
                            </td>

                            <td className="py-2.5 px-3 text-right font-bold text-slate-900">
                              ₹{Number(line.running_balance).toFixed(2)}
                            </td>

                            <td className="py-2.5 px-3 text-center">
                              {!isReversal && (
                                <button
                                  onClick={() => handlePromptReverse(line)}
                                  title="Post Reversal"
                                  className="p-1 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded transition-colors"
                                >
                                  <RotateCcw className="w-3.5 h-3.5" />
                                </button>
                              )}
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="px-6 py-3 border-t border-slate-100 bg-slate-50 flex items-center justify-between text-xs text-slate-500">
              <span>Append-only financial ledger. Corrections require compensating reversal entries.</span>
              <button
                onClick={() => setShowLedgerModal(false)}
                className="px-4 py-1.5 bg-slate-200 hover:bg-slate-300 text-slate-800 font-medium rounded-lg transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* MODAL 5: Customer Statement                                */}
      {/* ========================================================= */}
      {showStatementModal && selectedCustomer && activeStatement && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-3xl w-full max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
              <div>
                <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                  <FileSpreadsheet className="w-5 h-5 text-indigo-600" />
                  Customer Statement: {activeStatement.customer_name}
                </h2>
                <p className="text-xs text-slate-500">
                  Phone: {activeStatement.phone || "N/A"} | Currency: {activeStatement.currency}
                </p>
              </div>
              <button
                onClick={() => setShowStatementModal(false)}
                className="text-slate-400 hover:text-slate-600 text-lg leading-none"
              >
                &times;
              </button>
            </div>

            <div className="p-6 overflow-y-auto space-y-4">
              {/* Date Filter Bar */}
              <div className="flex flex-wrap items-center gap-3 p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs">
                <div className="flex items-center gap-1.5">
                  <Calendar className="w-4 h-4 text-slate-500" />
                  <span className="font-semibold text-slate-700">Date Range:</span>
                </div>
                <input
                  type="date"
                  value={statementStartDate}
                  onChange={(e) => setStatementStartDate(e.target.value)}
                  className="px-2 py-1 bg-white border border-slate-200 rounded-md text-xs"
                />
                <span className="text-slate-400">to</span>
                <input
                  type="date"
                  value={statementEndDate}
                  onChange={(e) => setStatementEndDate(e.target.value)}
                  className="px-2 py-1 bg-white border border-slate-200 rounded-md text-xs"
                />
                <button
                  type="button"
                  onClick={handleFilterStatement}
                  className="px-3 py-1 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-md transition-colors"
                >
                  Apply Filter
                </button>
              </div>

              {/* Statement Summary Reconciliation Bar */}
              <div className="grid grid-cols-4 gap-2 text-center text-xs p-3 bg-indigo-50/50 border border-indigo-100 rounded-lg">
                <div>
                  <span className="text-slate-500 block">Opening Balance</span>
                  <span className="font-bold text-slate-800 text-sm">
                    ₹{Number(activeStatement.opening_balance).toFixed(2)}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block">+ Total Charges</span>
                  <span className="font-bold text-indigo-700 text-sm">
                    ₹{Number(activeStatement.total_charges).toFixed(2)}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block">- Total Repayments</span>
                  <span className="font-bold text-emerald-700 text-sm">
                    ₹{Number(activeStatement.total_repayments).toFixed(2)}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block">= Closing Balance</span>
                  <span className="font-bold text-slate-900 text-sm">
                    ₹{Number(activeStatement.closing_balance).toFixed(2)}
                  </span>
                </div>
              </div>

              {/* Line Items Table */}
              <div className="overflow-x-auto border border-slate-100 rounded-lg">
                <table className="w-full text-left text-xs text-slate-700">
                  <thead className="bg-slate-50 border-b border-slate-200 font-semibold text-slate-500 uppercase">
                    <tr>
                      <th className="py-2 px-3">Date</th>
                      <th className="py-2 px-3">Type</th>
                      <th className="py-2 px-3">Description</th>
                      <th className="py-2 px-3 text-right">Charge</th>
                      <th className="py-2 px-3 text-right">Payment</th>
                      <th className="py-2 px-3 text-right">Running Bal</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {activeStatement.lines.map((line) => (
                      <tr key={line.transaction_id}>
                        <td className="py-2 px-3 font-mono text-slate-500">
                          {new Date(line.transaction_at).toLocaleDateString("en-IN", {
                            day: "2-digit",
                            month: "short",
                            year: "numeric",
                          })}
                        </td>
                        <td className="py-2 px-3 font-medium">{line.transaction_type}</td>
                        <td className="py-2 px-3 text-slate-600">{line.description || "—"}</td>
                        <td className="py-2 px-3 text-right font-medium text-indigo-600">
                          {line.charge_amount ? `₹${Number(line.charge_amount).toFixed(2)}` : "—"}
                        </td>
                        <td className="py-2 px-3 text-right font-medium text-emerald-600">
                          {line.repayment_amount ? `₹${Number(line.repayment_amount).toFixed(2)}` : "—"}
                        </td>
                        <td className="py-2 px-3 text-right font-bold text-slate-900">
                          ₹{Number(line.running_balance).toFixed(2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="px-6 py-3 border-t border-slate-100 bg-slate-50 flex items-center justify-between">
              <span className="text-xs text-slate-500">
                Formula verified: Closing = Opening + Charges - Repayments
              </span>
              <button
                onClick={() => window.print()}
                className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-lg shadow-xs transition-colors"
              >
                Print / Save PDF
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* MODAL 6: Reminder Draft Preview                            */}
      {/* ========================================================= */}
      {showReminderModal && selectedCustomer && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                  <MessageSquare className="w-5 h-5 text-sky-600" />
                  Reminder Draft Preview
                </h2>
                <p className="text-xs text-slate-500">
                  Un-sent preview draft. No automated messages are dispatched.
                </p>
              </div>
              <button
                onClick={() => setShowReminderModal(false)}
                className="text-slate-400 hover:text-slate-600 text-lg leading-none"
              >
                &times;
              </button>
            </div>

            <div className="p-6 space-y-4">
              {/* Language Selector */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Draft Language
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {(["Hinglish", "Hindi", "English"] as const).map((lang) => (
                    <button
                      key={lang}
                      type="button"
                      onClick={() => setReminderLanguage(lang)}
                      className={`py-1.5 text-xs font-medium rounded-lg border transition-colors ${
                        reminderLanguage === lang
                          ? "bg-sky-50 border-sky-300 text-sky-800 font-semibold"
                          : "bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100"
                      }`}
                    >
                      {lang}
                    </button>
                  ))}
                </div>
              </div>

              {/* Message Preview Box */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Generated Draft Text
                </label>
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-800 whitespace-pre-wrap leading-relaxed">
                  {getDraftText()}
                </div>
              </div>

              {/* Disclaimer */}
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-900 flex items-start gap-2">
                <Info className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                <div>
                  <span className="font-semibold">Privacy & Consent Invariant:</span> DukesAI does not send automated outbound messages without verified WhatsApp/SMS integration and explicit customer consent.
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2 pt-2">
                <button
                  type="button"
                  onClick={handleCopyDraft}
                  className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-semibold rounded-lg transition-colors"
                >
                  <Copy className="w-4 h-4" />
                  {copiedDraft ? "Copied!" : "Copy Draft"}
                </button>

                {getWhatsAppLink() ? (
                  <a
                    href={getWhatsAppLink()!}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-lg shadow-sm transition-colors"
                  >
                    <Send className="w-4 h-4" />
                    Open WhatsApp
                  </a>
                ) : (
                  <button
                    disabled
                    title="Customer has no phone number on record"
                    className="flex-1 px-3 py-2 bg-slate-100 text-slate-400 text-xs font-semibold rounded-lg cursor-not-allowed"
                  >
                    No Phone Stored
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* MODAL 7: Reversal Confirmation                            */}
      {/* ========================================================= */}
      {showReverseModal && txToReverse && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-rose-50/50">
              <h2 className="text-lg font-bold text-rose-900 flex items-center gap-2">
                <RotateCcw className="w-5 h-5 text-rose-600" />
                Confirm Transaction Reversal
              </h2>
              <button
                onClick={() => setShowReverseModal(false)}
                className="text-slate-400 hover:text-slate-600 text-lg leading-none"
              >
                &times;
              </button>
            </div>

            <div className="p-6 space-y-4">
              <div className="text-xs text-slate-600 space-y-1">
                <div>
                  <span className="font-semibold text-slate-700">Transaction ID:</span> {txToReverse.transaction_id}
                </div>
                <div>
                  <span className="font-semibold text-slate-700">Type:</span> {txToReverse.transaction_type}
                </div>
                <div>
                  <span className="font-semibold text-slate-700">Amount:</span> ₹
                  {txToReverse.charge_amount || txToReverse.repayment_amount || "0.00"}
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Reason for Reversal <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={reversalReason}
                  onChange={(e) => setReversalReason(e.target.value)}
                  placeholder="e.g. Billed to wrong customer account"
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500"
                />
              </div>

              <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-600">
                A compensating <span className="font-semibold">REVERSAL</span> transaction will be permanently recorded in the ledger and linked to this transaction.
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowReverseModal(false)}
                  className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm font-medium rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={loading || !reversalReason.trim()}
                  onClick={handleConfirmReverse}
                  className="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white text-sm font-medium rounded-lg shadow-sm transition-colors disabled:opacity-50"
                >
                  Confirm Reversal
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
