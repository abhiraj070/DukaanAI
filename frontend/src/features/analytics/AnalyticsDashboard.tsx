"use client";

import React, { useEffect, useState } from "react";
import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Coins,
  FileQuestion,
  Info,
  Layers,
  Package,
  Percent,
  RefreshCw,
  Wallet,
} from "lucide-react";

import {
  getAnalyticsTrends,
  getCategoryBreakdown,
  getKPIs,
  getProductRankings,
} from "@/lib/api";
import type {
  AnalyticsTrendsResponse,
  CategoryBreakdownResponse,
  DomainResult,
  KPIOverview,
  ProductPerformanceItem,
  ProductRankingResponse,
} from "@/lib/types/analytics";

const PERIOD_OPTIONS = [
  { label: "Today", value: "TODAY" },
  { label: "Yesterday", value: "YESTERDAY" },
  { label: "Last 7 Days", value: "LAST_7_DAYS" },
  { label: "Last 30 Days", value: "LAST_30_DAYS" },
  { label: "This Month", value: "THIS_MONTH" },
  { label: "All Time", value: "ALL_TIME" },
];

export function AnalyticsDashboard() {
  const [period, setPeriod] = useState<string>("LAST_30_DAYS");
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [kpis, setKpis] = useState<DomainResult<KPIOverview> | null>(null);
  const [products, setProducts] = useState<DomainResult<ProductRankingResponse> | null>(null);
  const [categories, setCategories] = useState<DomainResult<CategoryBreakdownResponse> | null>(null);
  const [trends, setTrends] = useState<DomainResult<AnalyticsTrendsResponse> | null>(null);

  const [productRankingTab, setProductRankingTab] = useState<
    "revenue" | "units" | "profit" | "slow"
  >("revenue");
  const [showEvidenceModal, setShowEvidenceModal] = useState<boolean>(false);

  const refresh = (selectedPeriod: string) => {
    setLoading(true);
    setError(null);
    Promise.all([
      getKPIs(selectedPeriod),
      getProductRankings(selectedPeriod),
      getCategoryBreakdown(selectedPeriod),
      getAnalyticsTrends(selectedPeriod),
    ])
      .then(([kpiRes, prodRes, catRes, trendRes]) => {
        setKpis(kpiRes);
        setProducts(prodRes);
        setCategories(catRes);
        setTrends(trendRes);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load business analytics");
      })
      .finally(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    let isMounted = true;
    Promise.all([
      getKPIs(period),
      getProductRankings(period),
      getCategoryBreakdown(period),
      getAnalyticsTrends(period),
    ])
      .then(([kpiRes, prodRes, catRes, trendRes]) => {
        if (!isMounted) return;
        setKpis(kpiRes);
        setProducts(prodRes);
        setCategories(catRes);
        setTrends(trendRes);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (!isMounted) return;
        setError(err instanceof Error ? err.message : "Failed to load business analytics");
        setLoading(false);
      });
    return () => {
      isMounted = false;
    };
  }, [period]);

  const kpiData = kpis?.data;

  // Active products list according to ranking tab
  const activeProducts: ProductPerformanceItem[] = products?.data
    ? productRankingTab === "revenue"
      ? products.data.top_by_revenue
      : productRankingTab === "units"
      ? products.data.top_by_units
      : productRankingTab === "profit"
      ? products.data.top_by_profit
      : products.data.slow_moving
    : [];

  return (
    <div className="space-y-6">
      {/* Top Header & Period Selector */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 sm:p-5 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-base font-bold text-slate-900">Core Business Analytics</h2>
            <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800">
              Phase 4 Active
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Deterministic revenue, COGS, profit margins, inventory valuation & turnover in Asia/Kolkata
          </p>
        </div>

        <div className="flex items-center gap-2 self-start md:self-auto">
          {/* Period Pills */}
          <div className="flex items-center gap-1 p-1 rounded-lg bg-slate-100 border border-slate-200 text-xs font-semibold">
            {PERIOD_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setPeriod(opt.value)}
                className={`px-2.5 py-1 rounded-md transition-all ${
                  period === opt.value
                    ? "bg-white text-slate-900 shadow-xs"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          <button
            onClick={() => refresh(period)}
            disabled={loading}
            className="p-2 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-50"
            title="Refresh Analytics"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Missing Cost Price Invariant Warning Alert */}
      {kpiData && !kpiData.cost_data_available && (
        <div className="p-4 rounded-xl bg-amber-50 border border-amber-300 flex items-start gap-3">
          <FileQuestion className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <h4 className="text-xs font-bold text-amber-900">
              Data Coverage Warning: {kpiData.missing_cost_items_count} Sold Line Items Lack Cost Price
            </h4>
            <p className="text-xs text-amber-800 leading-relaxed">
              In strict accordance with DukaanAI correctness invariants, revenue is <strong>never</strong> labelled as profit.
              Because cost price records are missing for sold products, COGS and Gross Profit are reported as <strong>Unavailable</strong> rather than fabricating zero cost or misleading margins.
            </p>
          </div>
        </div>
      )}

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Gross & Net Revenue */}
        <div className="bg-white rounded-xl border border-slate-200 p-4 sm:p-5 shadow-xs space-y-3">
          <div className="flex items-center justify-between text-slate-500 text-xs">
            <span className="font-semibold uppercase tracking-wider">Gross Revenue</span>
            <div className="p-1.5 rounded-md bg-blue-50 text-blue-600">
              <Coins className="w-4 h-4" />
            </div>
          </div>

          <div className="space-y-1">
            <div className="text-2xl font-black text-slate-900 font-mono">
              ₹{kpiData ? Number(kpiData.gross_revenue).toLocaleString("en-IN", { minimumFractionDigits: 2 }) : "0.00"}
            </div>
            <div className="flex items-center justify-between text-[11px] text-slate-500">
              <span>Net: ₹{kpiData ? Number(kpiData.net_revenue).toLocaleString("en-IN", { minimumFractionDigits: 2 }) : "0.00"}</span>
              <span>{kpiData ? kpiData.total_units_sold : 0} units</span>
            </div>
          </div>

          <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
            <span>Bills: {kpiData?.transaction_count || 0}</span>
            {Number(kpiData?.sales_returns || 0) > 0 && (
              <span className="text-rose-600 font-medium">Returns: ₹{kpiData?.sales_returns}</span>
            )}
          </div>
        </div>

        {/* Card 2: Cost of Goods Sold (COGS) */}
        <div className="bg-white rounded-xl border border-slate-200 p-4 sm:p-5 shadow-xs space-y-3">
          <div className="flex items-center justify-between text-slate-500 text-xs">
            <span className="font-semibold uppercase tracking-wider">Cost of Goods (COGS)</span>
            <div className="p-1.5 rounded-md bg-purple-50 text-purple-600">
              <Package className="w-4 h-4" />
            </div>
          </div>

          <div className="space-y-1">
            <div className="text-2xl font-black text-slate-900 font-mono">
              {kpiData?.cogs !== null && kpiData?.cogs !== undefined
                ? `₹${Number(kpiData.cogs).toLocaleString("en-IN", { minimumFractionDigits: 2 })}`
                : "Unavailable"}
            </div>
            <div className="text-[11px] text-slate-500">
              {kpiData?.cost_data_available ? (
                <span className="text-emerald-700 font-semibold flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> 100% Costed
                </span>
              ) : (
                <span className="text-amber-700 font-semibold flex items-center gap-1">
                  <AlertTriangle className="w-3.5 h-3.5" /> Missing Cost Data
                </span>
              )}
            </div>
          </div>

          <div className="pt-2 border-t border-slate-100 text-[11px] text-slate-500">
            Calculated from verified purchase dispatch movements
          </div>
        </div>

        {/* Card 3: Gross Profit & Margin % */}
        <div className="bg-gradient-to-br from-indigo-900 to-slate-900 text-white rounded-xl p-4 sm:p-5 shadow-xs space-y-3">
          <div className="flex items-center justify-between text-indigo-200 text-xs">
            <span className="font-semibold uppercase tracking-wider">Gross Profit</span>
            <div className="p-1.5 rounded-md bg-white/10 text-indigo-300">
              <Percent className="w-4 h-4" />
            </div>
          </div>

          <div className="space-y-1">
            <div className="text-2xl font-black text-white font-mono">
              {kpiData?.gross_profit !== null && kpiData?.gross_profit !== undefined
                ? `₹${Number(kpiData.gross_profit).toLocaleString("en-IN", { minimumFractionDigits: 2 })}`
                : "Unavailable"}
            </div>
            <div className="flex items-center gap-2 text-xs font-semibold">
              {kpiData?.gross_margin_pct !== null && kpiData?.gross_margin_pct !== undefined ? (
                <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-400/20">
                  {kpiData.gross_margin_pct}% Margin
                </span>
              ) : (
                <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-400/20 text-[10px]">
                  Requires Product Cost
                </span>
              )}
            </div>
          </div>

          <div className="pt-2 border-t border-white/10 text-[11px] text-indigo-200">
            Formula: Net Revenue − COGS
          </div>
        </div>

        {/* Card 4: Inventory Valuation & Turnover */}
        <div className="bg-white rounded-xl border border-slate-200 p-4 sm:p-5 shadow-xs space-y-3">
          <div className="flex items-center justify-between text-slate-500 text-xs">
            <span className="font-semibold uppercase tracking-wider">Inventory Valuation</span>
            <div className="p-1.5 rounded-md bg-emerald-50 text-emerald-600">
              <Wallet className="w-4 h-4" />
            </div>
          </div>

          <div className="space-y-1">
            <div className="text-2xl font-black text-slate-900 font-mono">
              ₹{kpiData ? Number(kpiData.inventory_valuation).toLocaleString("en-IN", { minimumFractionDigits: 2 }) : "0.00"}
            </div>
            <div className="flex items-center justify-between text-[11px] text-slate-500">
              <span>Expenses: ₹{kpiData?.total_expenses || "0.00"}</span>
              <span>
                Turnover:{" "}
                <strong>
                  {kpiData?.inventory_turnover ? `${kpiData.inventory_turnover}x` : "—"}
                </strong>
              </span>
            </div>
          </div>

          <div className="pt-2 border-t border-slate-100 text-[11px] text-slate-500">
            Reconciled from physical movement balances
          </div>
        </div>
      </div>

      {/* Visual Timeline Trend Bars */}
      {trends?.data && trends.data.points.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-3">
            <div>
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-indigo-600" />
                Revenue & Expense Timeline ({trends.data.period_label})
              </h3>
              <p className="text-xs text-slate-500">Daily business revenue vs recorded operational costs</p>
            </div>
            <div className="flex items-center gap-4 text-xs font-semibold">
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded bg-indigo-600 inline-block" />
                Revenue
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded bg-rose-500 inline-block" />
                Expenses
              </span>
            </div>
          </div>

          {/* Timeline points display */}
          <div className="space-y-2 pt-2">
            <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 gap-2 max-h-48 overflow-y-auto">
              {trends.data.points.map((pt, idx) => (
                <div
                  key={idx}
                  className="p-2.5 rounded-lg border border-slate-100 bg-slate-50/50 hover:bg-slate-100 transition-colors text-xs space-y-1"
                >
                  <div className="text-[11px] text-slate-500 font-mono font-semibold truncate">
                    {pt.date}
                  </div>
                  <div className="font-bold text-slate-900 font-mono">
                    ₹{Number(pt.net_revenue).toLocaleString("en-IN")}
                  </div>
                  <div className="flex items-center justify-between text-[10px] text-slate-500">
                    <span>{pt.units_sold}u</span>
                    {Number(pt.expenses) > 0 && (
                      <span className="text-rose-600 font-semibold">₹{pt.expenses}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Main Analysis Section: Product Performance & Category Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Product Rankings Table */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden flex flex-col">
          <div className="p-4 sm:p-5 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-bold text-slate-900">Product Performance & SKU Rankings</h3>
              <p className="text-xs text-slate-500">Sales volume, revenue contribution, and margins</p>
            </div>

            {/* Ranking Switcher */}
            <div className="flex items-center gap-1 p-1 rounded-lg bg-slate-100 border border-slate-200 text-xs font-semibold">
              <button
                onClick={() => setProductRankingTab("revenue")}
                className={`px-2.5 py-1 rounded-md transition-all ${
                  productRankingTab === "revenue"
                    ? "bg-white text-slate-900 shadow-xs"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Top Revenue
              </button>
              <button
                onClick={() => setProductRankingTab("units")}
                className={`px-2.5 py-1 rounded-md transition-all ${
                  productRankingTab === "units"
                    ? "bg-white text-slate-900 shadow-xs"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Top Units
              </button>
              <button
                onClick={() => setProductRankingTab("profit")}
                className={`px-2.5 py-1 rounded-md transition-all ${
                  productRankingTab === "profit"
                    ? "bg-white text-slate-900 shadow-xs"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Profit Margin
              </button>
              <button
                onClick={() => setProductRankingTab("slow")}
                className={`px-2.5 py-1 rounded-md transition-all ${
                  productRankingTab === "slow"
                    ? "bg-white text-slate-900 shadow-xs"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Slow Moving
              </button>
            </div>
          </div>

          <div className="overflow-x-auto flex-1">
            {activeProducts.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500">
                No product transactions recorded in this date period.
              </div>
            ) : (
              <table className="w-full text-xs text-left">
                <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold">
                  <tr>
                    <th className="p-3">Product Name</th>
                    <th className="p-3">Units</th>
                    <th className="p-3">Revenue</th>
                    <th className="p-3">COGS</th>
                    <th className="p-3">Gross Profit</th>
                    <th className="p-3">Margin</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {activeProducts.map((p) => (
                    <tr key={p.product_id} className="hover:bg-slate-50/60">
                      <td className="p-3">
                        <div className="font-semibold text-slate-900">{p.product_name}</div>
                        <div className="text-[11px] text-slate-500 font-mono">
                          {p.sku || p.category_name || "General"}
                        </div>
                      </td>
                      <td className="p-3 font-mono font-medium">
                        {p.units_sold} {p.unit}
                      </td>
                      <td className="p-3 font-mono font-bold text-slate-900">
                        ₹{Number(p.revenue).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                      </td>
                      <td className="p-3 font-mono text-slate-600">
                        {p.cogs !== null ? `₹${p.cogs}` : "—"}
                      </td>
                      <td className="p-3 font-mono font-semibold text-slate-900">
                        {p.gross_profit !== null ? `₹${p.gross_profit}` : "—"}
                      </td>
                      <td className="p-3">
                        {p.gross_margin_pct !== null ? (
                          <span
                            className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                              Number(p.gross_margin_pct) >= 15
                                ? "bg-emerald-100 text-emerald-800"
                                : Number(p.gross_margin_pct) > 0
                                ? "bg-blue-100 text-blue-800"
                                : "bg-rose-100 text-rose-800"
                            }`}
                          >
                            {p.gross_margin_pct}%
                          </span>
                        ) : (
                          <span className="text-[10px] text-amber-700 font-medium">
                            No Cost
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Right 1 Col: Category Performance Breakdown */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-5 space-y-4 flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h3 className="text-sm font-bold text-slate-900 flex items-center gap-1.5">
                  <Layers className="w-4 h-4 text-emerald-600" />
                  Category Breakdown
                </h3>
                <p className="text-xs text-slate-500">Sales volume by department</p>
              </div>
              <span className="font-mono text-xs font-bold text-slate-800">
                ₹{categories?.data ? Number(categories.data.total_revenue).toLocaleString("en-IN") : "0"}
              </span>
            </div>

            <div className="space-y-3">
              {categories?.data?.categories.map((cat, idx) => {
                const totalRev = Number(categories.data.total_revenue) || 1;
                const catRev = Number(cat.revenue);
                const sharePct = Math.round((catRev / totalRev) * 100);

                return (
                  <div key={idx} className="space-y-1.5 p-2 rounded-lg bg-slate-50 border border-slate-100">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-slate-900">{cat.category_name}</span>
                      <span className="font-mono font-bold text-slate-800">
                        ₹{catRev.toLocaleString("en-IN")} ({sharePct}%)
                      </span>
                    </div>

                    {/* Progress Bar */}
                    <div className="w-full h-1.5 bg-slate-200 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-emerald-600 rounded-full transition-all"
                        style={{ width: `${Math.min(100, Math.max(0, sharePct))}%` }}
                      />
                    </div>

                    <div className="flex items-center justify-between text-[10px] text-slate-500">
                      <span>{cat.product_count} active items</span>
                      <span>{cat.units_sold} units sold</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Evidence Drawer Button */}
          <div className="pt-3 border-t border-slate-100">
            <button
              onClick={() => setShowEvidenceModal(!showEvidenceModal)}
              className="w-full py-2 px-3 rounded-lg border border-slate-300 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors flex items-center justify-center gap-1.5"
            >
              <Info className="w-3.5 h-3.5 text-indigo-600" />
              <span>{showEvidenceModal ? "Hide Evidence Details" : "View Calculation Provenance & Evidence"}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Evidence & Provenance Details Dropdown / Card */}
      {showEvidenceModal && kpis?.evidence && (
        <div className="p-5 bg-white rounded-xl border border-slate-200 shadow-xs space-y-3">
          <div className="flex items-center gap-2 text-xs font-bold text-slate-900 uppercase tracking-wider">
            <Info className="w-4 h-4 text-indigo-600" />
            Audit Provenance & Evidence Envelope
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
              <span className="text-slate-500 block text-[11px]">Method</span>
              <strong className="text-slate-800 font-mono">{kpis.evidence.calculation_method}</strong>
            </div>
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
              <span className="text-slate-500 block text-[11px]">Timezone</span>
              <strong className="text-slate-800 font-mono">Asia/Kolkata (IST)</strong>
            </div>
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
              <span className="text-slate-500 block text-[11px]">Freshness</span>
              <strong className="text-slate-800 font-mono truncate block">
                {new Date(kpis.evidence.freshness_timestamp).toLocaleTimeString()}
              </strong>
            </div>
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
              <span className="text-slate-500 block text-[11px]">Source Records Sampled</span>
              <strong className="text-slate-800 font-mono">
                {kpis.evidence.source_record_ids.length} transactions
              </strong>
            </div>
          </div>

          <div className="space-y-1 text-xs text-slate-600">
            <span className="font-semibold text-slate-700">Assumptions & Rules:</span>
            <ul className="list-disc list-inside space-y-0.5 text-[11px]">
              {kpis.evidence.assumptions.map((asm, idx) => (
                <li key={idx}>{asm}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
