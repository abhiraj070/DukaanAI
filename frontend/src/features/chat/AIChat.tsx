"use client";

import { useEffect, useRef, useState } from "react";
import { Bot, Check, Copy, MessageSquarePlus, Send, Shield, Sparkles, Trash2 } from "lucide-react";
import { API_BASE_URL, getAuthenticatedHeaders } from "@/lib/api";

type Mode = "general" | "business";
type Message = { id: string; role: "user" | "assistant"; content: string };
type Conversation = { id: string; title: string; mode: Mode; updated_at: string };

async function request<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const headers = await getAuthenticatedHeaders() as Record<string, string>;
  headers.Accept = "application/json";
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const response = await fetch(`${API_BASE_URL}/api/v1/chat${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body), cache: "no-store" });
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(data?.error?.message || `Chat request failed (${response.status})`);
  return data as T;
}

function MessageBody({ content }: { content: string }) {
  const chunks = content.split(/```([\w-]*)\n([\s\S]*?)```/g);
  return <div className="space-y-3 text-sm leading-7">{chunks.map((part, index) => index % 3 === 2 ? <pre key={index} className="overflow-x-auto rounded-xl bg-slate-950 p-4 text-xs leading-6 text-emerald-100"><code>{part}</code></pre> : index % 3 === 1 ? null : part.split("\n").map((line, i) => line.startsWith("- ") || line.startsWith("* ") ? <div key={`${index}-${i}`} className="ml-4 list-item list-disc">{line.slice(2)}</div> : <p key={`${index}-${i}`} className={line.trim() ? "whitespace-pre-wrap" : "h-2"}>{line.replace(/^#{1,4}\s/, "")}</p>))}</div>;
}

export function AIChat() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [mode, setMode] = useState<Mode>("business");
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState<string | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const tempSequence = useRef(0);

  const loadHistory = async () => { try { setConversations(await request<Conversation[]>("/conversations")); } catch (e) { setError(e instanceof Error ? e.message : "Could not load chat history"); } };
  useEffect(() => { request<Conversation[]>("/conversations").then(setConversations).catch((e: unknown) => setError(e instanceof Error ? e.message : "Could not load chat history")); }, []);
  useEffect(() => { scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" }); }, [messages, busy]);

  const openConversation = async (id: string) => {
    setError("");
    try { const data = await request<{ id: string; mode: Mode; messages: Message[] }>(`/conversations/${id}`); setActiveId(id); setMode(data.mode); setMessages(data.messages); setHistoryOpen(false); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not open conversation"); }
  };
  const newChat = () => { setActiveId(null); setMessages([]); setDraft(""); setError(""); setHistoryOpen(false); };

  const send = async (text = draft) => {
    const content = text.trim(); if (!content || busy) return;
    setDraft(""); setError(""); setBusy(true);
    tempSequence.current += 1;
    const optimistic: Message = { id: `temp-${tempSequence.current}`, role: "user", content };
    setMessages((current) => [...current, optimistic]);
    try {
      let id = activeId;
      if (!id) { const created = await request<{ id: string }>("/conversations", "POST", { mode }); id = created.id; setActiveId(id); }
      const result = await request<{ message: Message }>(`/conversations/${id}/messages`, "POST", { content, mode });
      setMessages((current) => [...current.filter((item) => item.id !== optimistic.id), optimistic, result.message]);
      await loadHistory();
    } catch (e) { setMessages((current) => current.filter((item) => item.id !== optimistic.id)); setDraft(content); setError(e instanceof Error ? e.message : "Message failed. Please retry."); }
    finally { setBusy(false); }
  };

  const deleteConversation = async (id: string) => { try { await request(`/conversations/${id}`, "DELETE"); if (activeId === id) newChat(); await loadHistory(); } catch (e) { setError(e instanceof Error ? e.message : "Could not delete conversation"); } };
  const examples = ["What was the growth during the last Diwali? How much stock should I buy this year?", "Which products are running low?", "Summarize my recent business performance.", "Give me ideas for growing my shop."];

  return <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
    <div className="flex min-h-[680px] h-[calc(100vh-190px)] max-h-[900px]">
      <aside className={`${historyOpen ? "absolute inset-0 z-10 flex w-full" : "hidden"} md:static md:flex md:w-64 shrink-0 flex-col border-r border-slate-200 bg-slate-50`}>
        <div className="flex items-center justify-between border-b border-slate-200 p-4"><span className="text-sm font-semibold">Your chats</span><button onClick={() => setHistoryOpen(false)} className="text-xs text-slate-500 md:hidden">Close</button></div>
        <button onClick={newChat} className="m-3 flex items-center justify-center gap-2 rounded-xl bg-slate-900 px-3 py-2.5 text-sm font-semibold text-white hover:bg-slate-700"><MessageSquarePlus size={16}/> New chat</button>
        <div className="flex-1 space-y-1 overflow-y-auto px-2 pb-3">{conversations.map((chat) => <div key={chat.id} className={`group flex items-center rounded-lg ${activeId === chat.id ? "bg-white shadow-sm" : "hover:bg-white"}`}><button onClick={() => void openConversation(chat.id)} className="min-w-0 flex-1 truncate px-3 py-2.5 text-left text-sm text-slate-700">{chat.title}</button><button aria-label="Delete conversation" onClick={() => void deleteConversation(chat.id)} className="mr-2 rounded p-1 text-slate-400 hover:text-rose-600"><Trash2 size={14}/></button></div>)}</div>
        <div className="border-t border-slate-200 p-3 text-xs text-slate-500">Private to your account</div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-4 py-3 sm:px-6">
          <div className="flex items-center gap-2"><button onClick={() => setHistoryOpen(true)} className="rounded-lg border px-2.5 py-1.5 text-xs font-medium md:hidden">History</button><div className={`rounded-lg p-2 ${mode === "business" ? "bg-indigo-100 text-indigo-700" : "bg-emerald-100 text-emerald-700"}`}>{mode === "business" ? <Shield size={17}/> : <Sparkles size={17}/>}</div><div><p className="text-sm font-semibold">AI Chat</p><p className="text-xs text-slate-500">{mode === "business" ? "Business context enabled" : "General assistant"}</p></div></div>
          <label className="flex cursor-pointer items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-xs font-medium text-slate-700"><input type="checkbox" checked={mode === "business"} onChange={(e) => setMode(e.target.checked ? "business" : "general")} className="accent-indigo-600"/> Business Context</label>
        </div>
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6 sm:px-8">
          {messages.length === 0 ? <div className="mx-auto flex min-h-full max-w-2xl flex-col justify-center"><div className="mb-5 inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700"><Bot size={26}/></div><h2 className="text-3xl font-bold tracking-tight text-slate-900">What can I help you with?</h2><p className="mt-2 text-slate-500">Ask anything. Explore ideas, solve problems, learn something new or get work done.</p><div className="mt-7 grid gap-2 sm:grid-cols-2">{examples.map((example) => <button key={example} onClick={() => void send(example)} className="rounded-xl border border-slate-200 p-3 text-left text-sm text-slate-700 hover:border-emerald-300 hover:bg-emerald-50">{example}</button>)}</div></div> : <div className="mx-auto max-w-3xl space-y-7">{messages.map((message, index) => <article key={message.id} className={`flex gap-3 ${message.role === "user" ? "justify-end" : "justify-start"}`}><div className={`max-w-[88%] rounded-2xl px-4 py-3 ${message.role === "user" ? "bg-slate-900 text-white" : "bg-slate-50 text-slate-800"}`}><MessageBody content={message.content}/>{message.role === "assistant" && <div className="mt-3 flex gap-2 border-t border-slate-200 pt-2"><button onClick={() => { void navigator.clipboard.writeText(message.content); setCopied(message.id); }} className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-900">{copied === message.id ? <Check size={13}/> : <Copy size={13}/>} {copied === message.id ? "Copied" : "Copy"}</button>{index === messages.length - 1 && <button onClick={() => void send(messages.filter((m) => m.role === "user").at(-1)?.content ?? "")} className="text-xs text-slate-500 hover:text-slate-900">Retry</button>}</div>}</div></article>)}</div>}
          {busy && <div className="mx-auto mt-5 max-w-3xl text-sm text-slate-500"><span className="inline-flex animate-pulse items-center gap-2"><span className="h-2 w-2 rounded-full bg-emerald-500"/>Thinking…</span></div>}
        </div>
        <form onSubmit={(e) => { e.preventDefault(); void send(); }} className="border-t border-slate-100 px-4 py-4 sm:px-8"><div className="mx-auto max-w-3xl"><div className="flex items-end gap-2 rounded-2xl border border-slate-300 bg-white p-2 shadow-sm focus-within:border-emerald-500"><textarea value={draft} onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send(); } }} placeholder="Ask anything..." rows={1} className="max-h-36 min-h-10 flex-1 resize-y bg-transparent px-2 py-2 text-sm outline-none"/><button disabled={busy || !draft.trim()} aria-label="Send message" className="rounded-xl bg-emerald-600 p-2.5 text-white hover:bg-emerald-700 disabled:opacity-40"><Send size={17}/></button></div><p className="mt-2 text-center text-[11px] text-slate-400">Shift + Enter for a new line · {mode === "business" ? "Uses authorized business information" : "Does not access your business data"}</p></div></form>
      </div>
    </div>
  </section>;
}
