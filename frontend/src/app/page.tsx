"use client";

import { useState } from "react";
import {
  ArrowRight,
  BarChart3,
  BookOpen,
  FileSpreadsheet,
  MessageCircle,
  ShieldCheck,
  Store,
} from "lucide-react";

import { AnalyticsDashboard } from "@/features/analytics/AnalyticsDashboard";
import { DataCentreView } from "@/features/data-centre/DataCentreView";
import { UdharDashboard } from "@/features/udhar/UdharDashboard";
import { SimulationDashboard } from "@/features/simulation/SimulationDashboard";
import { FestivalDashboard } from "@/features/festivals/FestivalDashboard";
import { OptimizationDashboard } from "@/features/optimization/OptimizationDashboard";
import PurchaseOrdersDashboard from "@/features/purchase-orders/PurchaseOrdersDashboard";
import { AIChat } from "@/features/chat/AIChat";

export default function Home() {
  const [mainTab, setMainTab] = useState<"analytics" | "udhar" | "simulation" | "festivals" | "optimization" | "datacentre" | "purchaseorders" | "aichat">("analytics");

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
              </div>
              <p className="text-xs text-slate-500 font-medium">
                Agentic Decision Intelligence Platform • Indian Retail
              </p>
            </div>
          </div>

          {/* Navigation Pill Switches */}
          <div className="flex items-center gap-1.5 p-1 rounded-lg bg-slate-100 border border-slate-200 text-xs font-semibold self-start sm:self-auto overflow-x-auto max-w-full">
            <button
              onClick={() => setMainTab("analytics")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-all whitespace-nowrap ${
                mainTab === "analytics"
                  ? "bg-white text-slate-900 shadow-xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <BarChart3 className="w-3.5 h-3.5 text-blue-600" />
              <span>Core Analytics</span>
            </button>
            <button
              onClick={() => setMainTab("udhar")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-all whitespace-nowrap ${
                mainTab === "udhar"
                  ? "bg-white text-slate-900 shadow-xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <BookOpen className="w-3.5 h-3.5 text-indigo-600" />
              <span>Udhar (Khata)</span>
            </button>
            <button
              onClick={() => setMainTab("simulation")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-all whitespace-nowrap ${mainTab === "simulation" ? "bg-white text-slate-900 shadow-xs" : "text-slate-600 hover:text-slate-900"}`}
            >
              <ArrowRight className="w-3.5 h-3.5 text-violet-600" /><span>What-if</span>
            </button>
            <button
              onClick={() => setMainTab("festivals")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-all whitespace-nowrap ${mainTab === "festivals" ? "bg-white text-slate-900 shadow-xs" : "text-slate-600 hover:text-slate-900"}`}
            >
              <BookOpen className="w-3.5 h-3.5 text-amber-600" /><span>Festivals</span>
            </button>
            <button
              onClick={() => setMainTab("optimization")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-all whitespace-nowrap ${mainTab === "optimization" ? "bg-white text-slate-900 shadow-xs" : "text-slate-600 hover:text-slate-900"}`}
            >
              <BarChart3 className="w-3.5 h-3.5 text-blue-600" /><span>Optimize</span>
            </button>
            <button
              onClick={() => setMainTab("datacentre")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-all whitespace-nowrap ${
                mainTab === "datacentre"
                  ? "bg-white text-slate-900 shadow-xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-600" />
              <span>Data Centre</span>
            </button>
            <button
              onClick={() => setMainTab("purchaseorders")}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md whitespace-nowrap ${mainTab === "purchaseorders" ? "bg-white text-slate-900 shadow-xs" : "text-slate-600 hover:text-slate-900"}`}
            >
              <Store className="w-3.5 h-3.5 text-amber-600" /><span>Purchase Orders</span>
            </button>
            <button
              onClick={() => setMainTab("aichat")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-all whitespace-nowrap ${mainTab === "aichat" ? "bg-white text-slate-900 shadow-xs" : "text-slate-600 hover:text-slate-900"}`}
            >
              <MessageCircle className="w-3.5 h-3.5 text-emerald-600" /><span>AI Chat</span>
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
              DukaanAI empowers Indian kiranas with authoritative historical analytics, multimodal data ingestion,
              predictive inventory intelligence, and an auditable Udhar credit ledger.
            </p>
          </div>
        </div>

        {/* View Switching */}
        {mainTab === "analytics" ? (
          <AnalyticsDashboard />
        ) : mainTab === "udhar" ? (
          <UdharDashboard />
        ) : mainTab === "simulation" ? (
          <SimulationDashboard />
        ) : mainTab === "festivals" ? (
          <FestivalDashboard />
        ) : mainTab === "optimization" ? (
          <OptimizationDashboard />
        ) : mainTab === "datacentre" ? (
          <DataCentreView />
        ) : mainTab === "purchaseorders" ? (
          <PurchaseOrdersDashboard />
        ) : mainTab === "aichat" ? (
          <AIChat />
        ) : null}

        {/* Phase Progress Footer */}
        <div className="p-4 rounded-xl bg-slate-100 border border-slate-200 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-600 gap-3">
          <span>
            Phase 4 (Core Business Analytics) Complete & Verified • Next: Phase 5 (Udhar Management)
          </span>
          <div className="flex items-center gap-1 font-semibold text-slate-800">
            <span>Next: Phase 5 (Udhar Management)</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </div>
        </div>
      </main>
    </div>
  );
}
