"use client";

import { useEffect, useState } from "react";
import { approvePurchaseOrder, cancelPurchaseOrder, listPurchaseOrders, type PurchaseOrder } from "@/lib/api";

export default function PurchaseOrdersDashboard() {
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const refresh = async () => { try { setOrders(await listPurchaseOrders()); setError(""); } catch (e) { setError(e instanceof Error ? e.message : "Could not load purchase orders"); } };
  useEffect(() => { void refresh(); }, []);
  const run = async (id: string, action: "approve" | "cancel") => {
    setBusy(id);
    try { await (action === "approve" ? approvePurchaseOrder(id) : cancelPurchaseOrder(id)); await refresh(); }
    catch (e) { setError(e instanceof Error ? e.message : "Action failed"); }
    finally { setBusy(""); }
  };
  return <section className="space-y-4">
    <header><h2 className="text-xl font-bold">Purchase orders</h2><p className="text-sm text-slate-500">Review draft orders. Approval does not change stock; record receipts through the API when goods arrive.</p></header>
    {error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
    {orders.length === 0 ? <p className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500">No purchase orders yet.</p> : <div className="space-y-3">{orders.map(order => <article key={order.id} className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap justify-between gap-3"><div><p className="font-semibold">Order {order.id.slice(0, 8)}</p><p className="text-xs text-slate-500">{new Date(order.created_at).toLocaleDateString("en-IN")} · {order.items.length} items</p></div><div className="text-right"><p className="font-semibold">₹{Number(order.total_amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</p><p className="text-xs font-medium">{order.status.replaceAll("_", " ")}</p></div></div>
      <ul className="mt-3 divide-y text-sm">{order.items.map(item => <li key={item.id} className="flex justify-between py-2"><span>{item.product_name} · {item.quantity} @ ₹{item.unit_cost} <small className="text-slate-500">({item.unit_cost_source})</small></span><span>{item.received_quantity}/{item.quantity} received</span></li>)}</ul>
      {order.status === "DRAFT" && <div className="mt-3 flex gap-2"><button disabled={busy === order.id} onClick={() => void run(order.id, "approve")} className="rounded-lg bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50">Approve</button><button disabled={busy === order.id} onClick={() => void run(order.id, "cancel")} className="rounded-lg border px-3 py-2 text-sm disabled:opacity-50">Cancel</button></div>}
    </article>)}</div>}
  </section>;
}
