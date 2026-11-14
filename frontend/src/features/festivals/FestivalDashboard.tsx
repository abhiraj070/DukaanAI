"use client";

import { useCallback, useEffect, useState } from "react";
import { API_BASE_URL, getAuthToken, getDemoSession } from "@/lib/api";

type EventItem = { id: string; name: string; region: string; start_date: string; end_date: string; category_id?: string | null; source: string };
type Uplift = { data: { observed_uplift_pct?: number | null; planning_uplift_pct?: number | null; quality: string; comparable_occurrences: number; assumptions: string[]; warnings: string[] }; evidence: { source_record_ids: string[]; calculation_method: string } };

export function FestivalDashboard() {
  const [events, setEvents] = useState<EventItem[]>([]); const [uplifts, setUplifts] = useState<Record<string, Uplift["data"]>>({}); const [error, setError] = useState(""); const [assumptions, setAssumptions] = useState<Record<string, string>>({});
  const [editingId, setEditingId] = useState<string | null>(null);
  const [name, setName] = useState(""); const [region, setRegion] = useState("India"); const [start, setStart] = useState(""); const [end, setEnd] = useState(""); const [category, setCategory] = useState(""); const [busy, setBusy] = useState(false);
  const auth = useCallback(async () => { let token = getAuthToken(); if (!token) token = (await getDemoSession()).accessToken; return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" }; }, []);
  const refresh = useCallback(async () => { try { const r = await fetch(`${API_BASE_URL}/api/v1/festivals/calendar`, { headers: await auth(), cache: "no-store" }); if (!r.ok) throw new Error("Could not load festival calendar"); setEvents(await r.json()); } catch (e) { setError(e instanceof Error ? e.message : "Request failed"); } }, [auth]);
  useEffect(() => { const timer = window.setTimeout(() => void refresh(), 0); return () => window.clearTimeout(timer); }, [refresh]);
  async function loadUplift(id: string) { const q = assumptions[id] ? `?assumed_uplift_pct=${encodeURIComponent(assumptions[id])}` : ""; const r = await fetch(`${API_BASE_URL}/api/v1/festivals/calendar/${id}/uplift${q}`, { headers: await auth() }); if (!r.ok) throw new Error("Could not calculate festival context"); const data: Uplift = await r.json(); setUplifts(old => ({ ...old, [id]: data.data })); }
  async function save(e: React.FormEvent) { e.preventDefault(); setBusy(true); setError(""); try { const r = await fetch(`${API_BASE_URL}/api/v1/festivals/calendar${editingId ? `/${editingId}` : ""}`, { method: editingId ? "PUT" : "POST", headers: await auth(), body: JSON.stringify({ name, region, start_date: start, end_date: end, category_id: category || null }) }); if (!r.ok) throw new Error("Could not save festival event"); setName(""); setEditingId(null); await refresh(); } catch (err) { setError(err instanceof Error ? err.message : "Save failed"); } finally { setBusy(false); } }
  const pct = (n?: number | null) => n == null ? "Unavailable" : `${Number(n).toFixed(1)}%`;
  return <section className="space-y-5"><header><h2 className="text-xl font-bold">Festival demand calendar</h2><p className="text-sm text-slate-600">Add regional festival dates and category mappings. Historical uplift needs comparable prior occurrences; otherwise provide a labelled planning assumption.</p></header>
    <form onSubmit={save} className="grid gap-3 rounded-xl border bg-white p-5 sm:grid-cols-3">
      <label className="text-sm">Festival name<input required className="mt-1 w-full rounded border p-2" value={name} onChange={e=>setName(e.target.value)} /></label>
      <label className="text-sm">Region<input required className="mt-1 w-full rounded border p-2" value={region} onChange={e=>setRegion(e.target.value)} /></label>
      <label className="text-sm">Category ID (optional)<input className="mt-1 w-full rounded border p-2" value={category} onChange={e=>setCategory(e.target.value)} /></label>
      <label className="text-sm">Start date<input required type="date" className="mt-1 w-full rounded border p-2" value={start} onChange={e=>setStart(e.target.value)} /></label>
      <label className="text-sm">End date<input required type="date" className="mt-1 w-full rounded border p-2" value={end} onChange={e=>setEnd(e.target.value)} /></label>
      <button disabled={busy} className="self-end rounded-lg bg-emerald-600 p-2 font-semibold text-white disabled:opacity-50">{busy ? "Saving…" : editingId ? "Update event" : "Add to calendar"}</button>
    </form>
    {error && <p role="alert" className="rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
    <div className="space-y-3">{events.map(event => { const uplift = uplifts[event.id]; return <article key={event.id} className="grid gap-3 rounded-xl border bg-white p-4 md:grid-cols-[1fr_220px_auto_auto] md:items-center"><div><h3 className="font-semibold">{event.name}</h3><p className="text-xs text-slate-500">{event.region} · {event.start_date} – {event.end_date}{event.category_id ? ` · Category ${event.category_id}` : " · All categories"}</p></div><label className="text-xs">Fallback assumption %<input type="number" min="-100" max="1000" className="mt-1 w-full rounded border p-2" value={assumptions[event.id] ?? ""} onChange={e=>setAssumptions(old=>({...old,[event.id]:e.target.value}))} placeholder="Optional" /></label><button onClick={()=>{setEditingId(event.id);setName(event.name);setRegion(event.region);setStart(event.start_date);setEnd(event.end_date);setCategory(event.category_id ?? "");window.scrollTo({top:0,behavior:"smooth"});}} className="rounded-lg border px-3 py-2 text-sm font-medium">Edit</button><button onClick={()=>void loadUplift(event.id).catch(e=>setError(e.message))} className="rounded-lg border px-3 py-2 text-sm font-medium">Estimate uplift</button>{uplift && <div className="rounded-lg bg-slate-50 p-3 text-sm md:col-span-4"><b>{uplift.quality}</b> · historical {pct(uplift.observed_uplift_pct)} · planning {pct(uplift.planning_uplift_pct)} · {uplift.comparable_occurrences} comparable occurrences<p className="mt-1 text-xs text-slate-600">{uplift.assumptions.join(" · ")}</p>{uplift.warnings.map((w,i)=><p key={i} className="mt-1 text-xs text-amber-800">{w}</p>)}</div>}</article>; })}</div>
    {!events.length && <p className="rounded border border-dashed p-8 text-center text-sm text-slate-500">No festival dates yet.</p>}
  </section>;
}
