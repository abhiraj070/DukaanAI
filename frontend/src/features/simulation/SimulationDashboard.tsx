"use client";

import { useCallback, useEffect, useState } from "react";
import { API_BASE_URL, getAuthToken, getDemoSession } from "@/lib/api";

type Scenario = {
  id: string; scenario_name: string; model_version: string; created_at: string;
  result: { revenue?: { simulated: number; delta_amount: number } | null; gross_profit?: { simulated: number; delta_amount: number } | null; cash_collected_estimate: number; purchase_cash_outflow: number; assumptions_applied: string[]; constraints_and_risks: string[] };
};
const money = (n?: number | null) => n == null ? "Unavailable" : `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;

export function SimulationDashboard() {
  const [rows, setRows] = useState<Scenario[]>([]); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const [name, setName] = useState("Festival demand"); const [uplift, setUplift] = useState(15); const [days, setDays] = useState(30); const [collections, setCollections] = useState(0); const [purchase, setPurchase] = useState(0); const [delay, setDelay] = useState(0);
  const [productId, setProductId] = useState(""); const [priceDelta, setPriceDelta] = useState(0); const [costDelta, setCostDelta] = useState(0); const [productDemandDelta, setProductDemandDelta] = useState(0);
  const [festivalEventId, setFestivalEventId] = useState(""); const [festivalAssumption, setFestivalAssumption] = useState("");
  async function authHeaders() { let token = getAuthToken(); if (!token) token = (await getDemoSession()).accessToken; return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" }; }
  const reload = useCallback(async () => { try { const r = await fetch(`${API_BASE_URL}/api/v1/simulation/scenarios`, { headers: await authHeaders(), cache: "no-store" }); if (!r.ok) throw new Error("Could not load scenarios"); setRows(await r.json()); } catch (e) { setError(e instanceof Error ? e.message : "Could not load scenarios"); } }, []);
  useEffect(() => { const timer = window.setTimeout(() => void reload(), 0); return () => window.clearTimeout(timer); }, [reload]);
  async function submit(e: React.FormEvent) { e.preventDefault(); setBusy(true); setError(""); try { const r = await fetch(`${API_BASE_URL}/api/v1/simulation/scenarios`, { method: "POST", headers: await authHeaders(), body: JSON.stringify({ scenario_name: name, time_horizon_days: days, general_demand_uplift_pct: uplift, expected_udhar_collections: collections, purchase_cash_outflow: purchase, supply_delay_days: delay, festival_event_id: festivalEventId.trim() || null, festival_assumed_uplift_pct: festivalAssumption === "" ? null : Number(festivalAssumption), items: productId.trim() ? [{ product_id: productId.trim(), price_delta_pct: priceDelta, cost_delta_pct: costDelta, demand_delta_pct: productDemandDelta }] : [] }) }); if (!r.ok) throw new Error("Scenario could not be calculated"); await reload(); } catch (err) { setError(err instanceof Error ? err.message : "Scenario failed"); } finally { setBusy(false); } }
  return <section className="space-y-5"><header><h2 className="text-xl font-bold">What-if simulation</h2><p className="text-sm text-slate-600">Compare baseline projections with explicit scenario assumptions.</p></header>
    <form onSubmit={submit} className="grid gap-3 rounded-xl border bg-white p-5 sm:grid-cols-3">
      <label className="text-sm">Scenario<input className="mt-1 w-full rounded border p-2" value={name} onChange={e=>setName(e.target.value)} required /></label>
      <label className="text-sm">Horizon days<input className="mt-1 w-full rounded border p-2" type="number" min="1" max="365" value={days} onChange={e=>setDays(+e.target.value)} /></label>
      <label className="text-sm">Demand change %<input className="mt-1 w-full rounded border p-2" type="number" min="-99.99" value={uplift} onChange={e=>setUplift(+e.target.value)} /></label>
      <label className="text-sm">Udhar collection estimate ₹<input className="mt-1 w-full rounded border p-2" type="number" min="0" value={collections} onChange={e=>setCollections(+e.target.value)} /></label>
      <label className="text-sm">Purchase cash outflow ₹<input className="mt-1 w-full rounded border p-2" type="number" min="0" value={purchase} onChange={e=>setPurchase(+e.target.value)} /></label>
      <label className="text-sm">Supply delay days<input className="mt-1 w-full rounded border p-2" type="number" min="0" max="365" value={delay} onChange={e=>setDelay(+e.target.value)} /></label>
      <label className="text-sm">Optional product ID<input className="mt-1 w-full rounded border p-2" value={productId} onChange={e=>setProductId(e.target.value)} placeholder="Paste a product ID" /></label>
      <label className="text-sm">Product price / discount change %<input className="mt-1 w-full rounded border p-2" type="number" min="-99.99" value={priceDelta} onChange={e=>setPriceDelta(+e.target.value)} /></label>
      <label className="text-sm">Product cost change %<input className="mt-1 w-full rounded border p-2" type="number" min="-99.99" value={costDelta} onChange={e=>setCostDelta(+e.target.value)} /></label>
      <label className="text-sm">Product demand assumption %<input className="mt-1 w-full rounded border p-2" type="number" min="-99.99" value={productDemandDelta} onChange={e=>setProductDemandDelta(+e.target.value)} /></label>
      <label className="text-sm">Festival calendar event ID<input className="mt-1 w-full rounded border p-2" value={festivalEventId} onChange={e=>setFestivalEventId(e.target.value)} placeholder="Optional" /></label>
      <label className="text-sm">Festival uplift fallback %<input className="mt-1 w-full rounded border p-2" type="number" min="-100" max="1000" value={festivalAssumption} onChange={e=>setFestivalAssumption(e.target.value)} placeholder="Used if history is sparse" /></label>
      <button disabled={busy} className="rounded-lg bg-indigo-600 p-2 font-semibold text-white disabled:opacity-50 sm:col-span-3">{busy ? "Calculating…" : "Run and save scenario"}</button>
    </form>
    <div className="grid gap-4 lg:grid-cols-2">{rows.map(s=><article key={s.id} className="space-y-3 rounded-xl border bg-white p-5"><h3 className="font-bold">{s.scenario_name}</h3><p className="text-xs text-slate-500">{new Date(s.created_at).toLocaleString()} · {s.model_version}</p><div className="grid grid-cols-2 gap-2 text-sm"><p>Revenue {money(s.result.revenue?.simulated)} <span className="text-slate-500">({money(s.result.revenue?.delta_amount)})</span></p><p>Gross profit {money(s.result.gross_profit?.simulated)} <span className="text-slate-500">({money(s.result.gross_profit?.delta_amount)})</span></p><p>Collections estimate {money(s.result.cash_collected_estimate)}</p><p>Purchase outflow {money(s.result.purchase_cash_outflow)}</p></div><p className="text-xs text-slate-600"><b>Assumptions:</b> {s.result.assumptions_applied.join(" · ")}</p>{s.result.constraints_and_risks.map((risk,i)=><p key={i} className="rounded bg-amber-50 p-2 text-xs text-amber-900">{risk}</p>)}</article>)}</div>
    {!rows.length && <p className="rounded border border-dashed p-8 text-center text-sm text-slate-500">No saved scenario comparisons.</p>}
  </section>;
}
