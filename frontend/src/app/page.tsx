"use client";

import { useEffect, useState } from "react";
import {
  Activity,
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Database,
  FileSpreadsheet,
  Layers,
  RefreshCw,
  Server,
  ShieldCheck,
  Store,
  Terminal,
} from "lucide-react";

import { DataCentreView } from "@/features/data-centre/DataCentreView";
import {
  API_BASE_URL,
  checkBackendHealth,
  type ConnectivityResult,
} from "@/lib/api";

export default function Home() {
  const [result, setResult] = useState<ConnectivityResult | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [mainTab, setMainTab] = useState<"datacentre" | "system">("datacentre");

  const runCheck = async () => {
    setLoading(true);
    const res = await checkBackendHealth();
    setResult(res);
    setLoading(false);
  };

  useEffect(() => {
    let isMounted = true;
    checkBackendHealth().then((res) => {
      if (isMounted) {
        setResult(res);
        setLoading(false);
      }
    });
    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      {/* Top Header */}
      <header className="border-b border-slate-200 bg-white sticky top-0 z-20 shadow-xs">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-600 text-white rounded-lg shadow-xs">
              <Store className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold tracking-tight text-slate-900">
                  DukaanAI
                </h1>
                <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-800">
                  Phase 3 Verified
                </span>
              </div>
              <p className="text-xs text-slate-500 font-medium">
                Agentic Decision Intelligence Platform • Indian Retail
              </p>
            </div>
          </div>

          {/* Navigation Pill Switches */}
          <div className="flex items-center gap-1.5 p-1 rounded-lg bg-slate-100 border border-slate-200 text-xs font-semibold self-start sm:self-auto">
            <button
              onClick={() => setMainTab("datacentre")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-all ${
                mainTab === "datacentre"
                  ? "bg-white text-slate-900 shadow-xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <FileSpreadsheet className="w-3.5 h-3.5 text-indigo-600" />
              <span>Data Centre & Ingestion</span>
            </button>
            <button
              onClick={() => setMainTab("system")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-all ${
                mainTab === "system"
                  ? "bg-white text-slate-900 shadow-xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <Activity className="w-3.5 h-3.5 text-blue-600" />
              <span>System & Diagnostics</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-8 space-y-8">
        {/* Hero Section */}
        <div className="bg-gradient-to-r from-slate-900 via-slate-800 to-indigo-950 text-white rounded-2xl p-6 sm:p-8 shadow-sm">
          <div className="max-w-3xl space-y-3">
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-indigo-500/20 text-indigo-300 text-xs font-medium border border-indigo-400/20">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>Deterministic Core • Trusted Business Facts</span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
              From business data to better business decisions.
            </h2>
            <p className="text-sm sm:text-base text-slate-300 leading-relaxed">
              DukaanAI empowers Indian kiranas with multimodal ingestion (CSV, Excel, PDF, Hindi/Hinglish notes),
              predictive inventory intelligence, what-if simulations, and an auditable Udhar credit ledger.
            </p>
          </div>
        </div>

        {/* View Switching */}
        {mainTab === "datacentre" ? (
          <DataCentreView />
        ) : (
          <div className="space-y-8">
            {/* Connectivity Check Card */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
              <div className="p-5 sm:p-6 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-lg bg-blue-50 text-blue-600">
                    <Server className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-slate-900">
                      Backend API Connectivity Check
                    </h3>
                    <p className="text-xs text-slate-500">
                      Target: <code className="bg-slate-100 px-1 py-0.5 rounded text-slate-700">{API_BASE_URL}</code>
                    </p>
                  </div>
                </div>

                <button
                  onClick={runCheck}
                  disabled={loading}
                  className="inline-flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-slate-900 text-white hover:bg-slate-800 disabled:opacity-50 transition-colors shadow-xs"
                >
                  <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
                  <span>{loading ? "Checking..." : "Recheck Status"}</span>
                </button>
              </div>

              <div className="p-5 sm:p-6">
                {loading && !result ? (
                  <div className="py-8 flex flex-col items-center justify-center text-slate-500 gap-2">
                    <RefreshCw className="w-6 h-6 animate-spin text-blue-600" />
                    <p className="text-sm">Connecting to backend /api/v1/health...</p>
                  </div>
                ) : result?.ok ? (
                  <div className="space-y-6">
                    <div className="flex flex-wrap items-center gap-3">
                      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                        <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                        Operational (200 OK)
                      </span>
                      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200">
                        <Activity className="w-3.5 h-3.5" />
                        Round-trip: {result.latencyMs} ms
                      </span>
                      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono bg-slate-100 text-slate-700 border border-slate-200">
                        Trace: {result.requestId}
                      </span>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                      <div className="bg-slate-50 rounded-lg p-3.5 border border-slate-100">
                        <span className="text-xs text-slate-500 block">Service</span>
                        <span className="text-sm font-semibold text-slate-800">
                          {result.data?.app} v{result.data?.version}
                        </span>
                      </div>
                      <div className="bg-slate-50 rounded-lg p-3.5 border border-slate-100">
                        <span className="text-xs text-slate-500 block">Environment</span>
                        <span className="text-sm font-semibold text-slate-800 capitalize">
                          {result.data?.environment}
                        </span>
                      </div>
                      <div className="bg-slate-50 rounded-lg p-3.5 border border-slate-100">
                        <span className="text-xs text-slate-500 block">Business Timezone</span>
                        <span className="text-sm font-semibold text-slate-800">
                          {result.data?.timezone}
                        </span>
                      </div>
                      <div className="bg-slate-50 rounded-lg p-3.5 border border-slate-100">
                        <span className="text-xs text-slate-500 block">UTC Timestamp</span>
                        <span className="text-xs font-mono text-slate-800 truncate block">
                          {result.data?.timestamp}
                        </span>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="p-4 rounded-lg bg-rose-50 border border-rose-200 flex items-start gap-3">
                      <AlertCircle className="w-5 h-5 text-rose-600 mt-0.5 shrink-0" />
                      <div className="space-y-1">
                        <h4 className="text-sm font-semibold text-rose-900">
                          Backend Unreachable
                        </h4>
                        <p className="text-xs text-rose-700">
                          {result?.error || "Could not establish connection to the FastAPI server."}
                        </p>
                      </div>
                    </div>

                    <div className="bg-slate-900 text-slate-200 rounded-lg p-4 font-mono text-xs space-y-2">
                      <div className="flex items-center gap-1.5 text-slate-400">
                        <Terminal className="w-3.5 h-3.5" />
                        <span>To start the backend server locally:</span>
                      </div>
                      <div className="text-emerald-400">
                        cd backend<br />
                        uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Architectural Invariants */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs space-y-2">
                <div className="flex items-center gap-2 text-indigo-600 font-semibold text-sm">
                  <Database className="w-4 h-4" />
                  <h4>Deterministic Numbers</h4>
                </div>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Revenue, gross margins, stock, and udhar balances are calculated exclusively
                  by PostgreSQL and Python domain services—never fabricated by the LLM.
                </p>
              </div>

              <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs space-y-2">
                <div className="flex items-center gap-2 text-emerald-600 font-semibold text-sm">
                  <Layers className="w-4 h-4" />
                  <h4>Auditable Udhar Ledger</h4>
                </div>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Append-only customer credit accounting. Repayments allocate to charges;
                  receivables are never treated as cash, and repayments are not sales revenue.
                </p>
              </div>

              <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs space-y-2">
                <div className="flex items-center gap-2 text-blue-600 font-semibold text-sm">
                  <ShieldCheck className="w-4 h-4" />
                  <h4>Strict Tenant Security</h4>
                </div>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Every query, mutation, and vector retrieval is server-authorized and scoped
                  to the authenticated business membership.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Phase Progress Footer */}
        <div className="p-4 rounded-xl bg-slate-100 border border-slate-200 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-600 gap-3">
          <span>
            Phase 0, Phase 1, Phase 2, & Phase 3 Complete • Ingestion & Data Centre Fully Verified
          </span>
          <div className="flex items-center gap-1 font-semibold text-slate-800">
            <span>Next: Phase 4 (Core Business Analytics)</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </div>
        </div>
      </main>
    </div>
  );
}
