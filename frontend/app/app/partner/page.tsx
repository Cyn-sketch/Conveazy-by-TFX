"use client";
import { useEffect, useRef, useState } from "react";
import { CrisisCard, Disclaimer, ErrorNote, ModeBadge, Notice, PageHeader, Sources, Spinner } from "@/components/ui";
import { api, isApiError, type AIEnvelope, type PartnerAnswer } from "@/lib/api";

const STARTERS = [
  "Why does my partner react so intensely sometimes?",
  "Why might silence feel like rejection?",
  "Why does my partner need repeated reassurance?",
  "Why does my partner withdraw during disagreements?",
  "How do I set boundaries without sounding dismissive?",
  "How can I support someone without becoming responsible for their mental health?",
];
const LEVEL = {
  established: { label: "Established evidence", cls: "bg-sage/10 text-sage" },
  possible: { label: "Possible explanation", cls: "bg-dusk/10 text-dusk" },
  individual: { label: "Only your partner knows", cls: "bg-clay/10 text-clay" },
} as const;

type Turn = { q: string; a: AIEnvelope<PartnerAnswer> };
type Conv = { id: string; title: string; created_at: string };
type Channel = { name: string; credential_claimed: string; topics: string[]; url: string; verified: boolean };

function Videos() {
  const [ch, setCh] = useState<Channel[]>([]);
  useEffect(() => { api<{ channels: Channel[] }>("/knowledge/videos").then((r) => setCh(r.channels)).catch(() => {}); }, []);
  if (!ch.length) return null;
  return (
    <section className="mt-10">
      <p className="eyebrow mb-2">Learn together on YouTube</p>
      <p className="mb-4 text-sm text-muted">Channels from qualified clinicians and recognised organisations. Each is still being checked: credentials confirmed from an independent source, and content checked as education rather than opinion.</p>
      <ul className="grid gap-2 sm:grid-cols-2">{ch.map((c) => (
        <li key={c.name} className="rounded-xl border border-line bg-surface px-4 py-3 text-sm">
          <a href={c.url} target="_blank" rel="noreferrer" className="font-medium underline decoration-line underline-offset-4">{c.name}</a>
          <span className="block text-muted">{c.credential_claimed}</span>
          <span className="mt-1 block text-xs text-muted">{c.topics.map((t) => t.replace("_", " ")).join(" · ")}{c.verified ? "" : " · pending check"}</span>
        </li>))}</ul>
    </section>
  );
}

function Answer({ a }: { a: AIEnvelope<PartnerAnswer> }) {
  if (a.status === "crisis" && a.crisis) return <CrisisCard crisis={a.crisis} />;
  if (a.status === "declined") return <Notice>{a.notice}</Notice>;
  const r = a.result!;
  const num = (id: string) => a.citations.findIndex((c) => c.id === id) + 1;
  return (
    <article className="card">
      {a.crisis && <div className="mb-5"><CrisisCard crisis={a.crisis} /></div>}
      <div className="mb-4 flex justify-end"><ModeBadge live={a.live} /></div>
      <div className="prose-calm text-[15.5px]">{r.answer.split(/\n\n+/).map((p, i) => <p key={i}>{p}</p>)}</div>

      {r.evidence.length > 0 && <section className="mt-6">
        <p className="eyebrow mb-3">How sure is this?</p>
        <ul className="space-y-3">{r.evidence.map((e, i) => (
          <li key={i} className="text-sm leading-relaxed">
            <span className={`mr-2 inline-block rounded-full px-2 py-0.5 text-xs font-medium ${LEVEL[e.level].cls}`}>{LEVEL[e.level].label}</span>
            {e.claim}{e.source_ids.map((s) => num(s) > 0 && <a key={s} href={`#src-${s}`} className="ml-1 align-super text-[10px] text-muted">[{num(s)}]</a>)}
          </li>))}</ul>
      </section>}

      <div className="mt-6 rounded-xl bg-clay/5 p-4 text-sm leading-relaxed"><span className="font-medium">What this can&apos;t tell you: </span>{r.what_cannot_be_inferred}</div>

      <div className="mt-6 grid gap-6 sm:grid-cols-2">
        {r.try_this.length > 0 && <section><p className="eyebrow mb-2">Try</p><ul className="list-disc space-y-1.5 pl-5 text-sm leading-relaxed">{r.try_this.map((t) => <li key={t}>{t}</li>)}</ul></section>}
        {r.avoid.length > 0 && <section><p className="eyebrow mb-2">Maybe avoid</p><ul className="list-disc space-y-1.5 pl-5 text-sm leading-relaxed">{r.avoid.map((t) => <li key={t}>{t}</li>)}</ul></section>}
      </div>
      {r.ask_your_partner.length > 0 && <section className="mt-6"><p className="eyebrow mb-2">Questions you could ask them</p>
        <ul className="space-y-1.5 font-serif text-[16px]">{r.ask_your_partner.map((q) => <li key={q}>&ldquo;{q}&rdquo;</li>)}</ul></section>}
      {r.professional_help_note && <p className="mt-6 text-sm leading-relaxed text-muted">{r.professional_help_note}</p>}
      <Sources citations={a.citations} />
    </article>
  );
}

export default function Partner() {
  const [q, setQ] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [convId, setConvId] = useState<string | null>(null);
  const [convs, setConvs] = useState<Conv[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  const loadConvs = () => api<{ conversations: Conv[] }>("/conversations?module=partner").then((r) => setConvs(r.conversations)).catch(() => {});
  useEffect(() => { loadConvs(); }, []);
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [turns.length]);

  async function ask(question: string) {
    if (!question.trim()) return;
    setBusy(true); setError(null);
    try {
      const a = await api<AIEnvelope<PartnerAnswer>>("/partner/ask", { method: "POST", json: { question, conversation_id: convId } });
      setTurns((t) => [...t, { q: question, a }]); setQ("");
      if (a.conversation_id && !convId) { setConvId(a.conversation_id); loadConvs(); }
    } catch (e) { setError(isApiError(e) ? e.message : "Something went wrong."); }
    finally { setBusy(false); }
  }

  async function open(id: string) {
    const c = await api<{ messages: { role: string; content: any }[] }>(`/conversations/${id}`);
    const t: Turn[] = [];
    for (let i = 0; i + 1 < c.messages.length; i += 2) {
      const a = c.messages[i + 1];
      t.push({ q: c.messages[i].content, a: { ...a.content, live: (a as any).meta?.live, provider: (a as any).meta?.provider, status: (a as any).meta?.status, module: "partner", prompt_version: (a as any).meta?.prompt_version } });
    }
    setTurns(t); setConvId(id);
  }
  async function remove(id: string) { await api(`/conversations/${id}`, { method: "DELETE" }); if (id === convId) { setTurns([]); setConvId(null); } loadConvs(); }

  return (
    <div>
      <PageHeader eyebrow="Understand My Partner" title="Why does it land like that?">
        Answers draw on clinical and research sources and say how sure they are. Nobody can know your partner from a diagnosis, so the best answers often end with a question for them.
      </PageHeader>

      <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_14rem]">
        <div className="min-w-0 max-w-read space-y-8">
          {turns.length === 0 && (
            <div><div className="flex flex-wrap gap-2">{STARTERS.map((s) => <button key={s} className="chip text-left" onClick={() => ask(s)} disabled={busy}>{s}</button>)}</div><Videos /></div>
          )}
          {turns.map((t, i) => (
            <div key={i} className="space-y-4">
              <p className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md bg-blush px-4 py-2.5 text-ink">{t.q}</p>
              <Answer a={t.a} />
            </div>
          ))}
          <div ref={bottom} />
          <form onSubmit={(e) => { e.preventDefault(); ask(q); }} className="sticky bottom-20 rounded-xl2 border border-line bg-surface p-2 shadow-sm lg:bottom-4">
            <div className="flex items-end gap-2">
              <label htmlFor="q" className="sr-only">Your question</label>
              <textarea id="q" rows={2} maxLength={2000} className="min-h-[3rem] flex-1 resize-none bg-transparent px-3 py-2 text-[15px] focus:outline-none" placeholder={turns.length ? "Ask a follow-up…" : "Ask anything about how your partner might experience something…"}
                value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(q); } }} />
              <button className="btn-primary" disabled={busy || !q.trim()}>Ask</button>
            </div>
          </form>
          {busy && <Spinner label="Checking the sources…" />}
          <ErrorNote message={error} />
        </div>

        <aside className="text-sm">
          <div className="mb-3 flex items-center justify-between"><p className="eyebrow">Your questions</p>
            <button className="text-xs text-muted underline" onClick={() => { setTurns([]); setConvId(null); }}>New</button></div>
          {convs.length === 0 ? <p className="text-muted">Private to you.</p> : (
            <ul className="space-y-1">{convs.map((c) => (
              <li key={c.id} className={`group flex items-center justify-between gap-2 rounded-lg px-2 py-1.5 ${c.id === convId ? "bg-ink/[0.06]" : ""}`}>
                <button className="truncate text-left text-muted hover:text-ink" onClick={() => open(c.id)}>{c.title}</button>
                <button className="text-xs text-muted opacity-60 hover:text-warn group-hover:opacity-100" onClick={() => remove(c.id)} aria-label="Delete">×</button>
              </li>))}</ul>)}
        </aside>
      </div>
      <Disclaimer />
    </div>
  );
}
