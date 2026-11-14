"use client";

import { useCallback, useEffect, useState } from "react";
import { API_BASE_URL, getAuthToken, getDemoSession } from "@/lib/api";

type EventItem = { id: string; name: string; region: string; start_date: string; end_date: string; category_id?: string | null; source: string };

export function FestivalDashboard() {
  const [events, setEvents] = useState<EventItem[]>([]); const [error, setError] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [name, setName] = useState(""); const [region, setRegion] = useState("India"); const [start, setStart] = useState(""); const [end, setEnd] = useState(""); const [busy, setBusy] = useState(false);
  const auth = useCallback(async () => { let token = getAuthToken(); if (!token) token = (await getDemoSession()).accessToken; return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" }; }, []);
  const refresh = useCallback(async () => { try { const r = await fetch(`${API_BASE_URL}/api/v1/festivals/calendar`, { headers: await auth(), cache: "no-store" }); if (!r.ok) throw new Error("Could not load festival calendar"); setEvents(await r.json()); } catch (e) { setError(e instanceof Error ? e.message : "Request failed"); } }, [auth]);
  useEffect(() => { const timer = window.setTimeout(() => void refresh(), 0); return () => window.clearTimeout(timer); }, [refresh]);
  async function save(e: React.FormEvent) { e.preventDefault(); setBusy(true); setError(""); try { const r = await fetch(`${API_BASE_URL}/api/v1/festivals/calendar${editingId ? `/${editingId}` : ""}`, { method: editingId ? "PUT" : "POST", headers: await auth(), body: JSON.stringify({ name, region, start_date: start, end_date: end }) }); if (!r.ok) throw new Error("Could not save festival event"); setName(""); setEditingId(null); await refresh(); } catch (err) { setError(err instanceof Error ? err.message : "Save failed"); } finally { setBusy(false); } }
  return <section className="space-y-5"><header><h2 className="text-xl font-bold">Festival demand</h2><p className="text-sm text-slate-600">Add festival dates, then ask in AI Chat: “How much did sales grow last Diwali, and how much stock should I buy?” Recommendations use comparable sales history and current stock.</p></header>
    <form onSubmit={save} className="grid gap-3 rounded-xl border bg-white p-5 sm:grid-cols-3">
      <label className="text-sm">Festival name<input required className="mt-1 w-full rounded border p-2" value={name} onChange={e=>setName(e.target.value)} /></label>
      <label className="text-sm">Region<input required className="mt-1 w-full rounded border p-2" value={region} onChange={e=>setRegion(e.target.value)} /></label>
      <label className="text-sm">Start date<input required type="date" className="mt-1 w-full rounded border p-2" value={start} onChange={e=>setStart(e.target.value)} /></label>
      <label className="text-sm">End date<input required type="date" className="mt-1 w-full rounded border p-2" value={end} onChange={e=>setEnd(e.target.value)} /></label>
      <button disabled={busy} className="self-end rounded-lg bg-emerald-600 p-2 font-semibold text-white disabled:opacity-50">{busy ? "Saving…" : editingId ? "Update event" : "Add to calendar"}</button>
    </form>
    <div className="space-y-3">{events.map(event => <article key={event.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-white p-4"><div><h3 className="font-semibold">{event.name}</h3><p className="text-xs text-slate-500">{event.region} · {event.start_date} – {event.end_date}</p></div><button onClick={()=>{setEditingId(event.id);setName(event.name);setRegion(event.region);setStart(event.start_date);setEnd(event.end_date);window.scrollTo({top:0,behavior:"smooth"});}} className="rounded-lg border px-3 py-2 text-sm font-medium">Edit</button></article>)}</div>
    {!events.length && <p className="rounded border border-dashed p-8 text-center text-sm text-slate-500">No festival dates yet.</p>}
  </section>;
}
