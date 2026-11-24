"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { CopyButton, CrisisCard, Disclaimer, ErrorNote, ModeBadge, Notice, PageHeader, Sources, Spinner } from "@/components/ui";
import { api, isApiError, type BridgeEnvelope } from "@/lib/api";

const GROUND = { their_profile: { label: "From their profile", cls: "bg-sage/10 text-sage" }, evidence: { label: "From the sources", cls: "bg-dusk/10 text-dusk" }, general: { label: "General guidance", cls: "bg-ink/5 text-muted" } } as const;

export default function Bridge() {
  const [partner, setPartner] = useState<string | null>(null);
  const [scraps, setScraps] = useState("");
  const [res, setRes] = useState<BridgeEnvelope | null>(null);
  const [stage, setStage] = useState<"write" | "confirm" | "message">("write");
  const [meaning, setMeaning] = useState("");
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"full" | "short" | number>("full");

  useEffect(() => { api<{ partner?: { name: string } }>("/relationship").then((r) => setPartner(r.partner?.name ?? null)).catch(() => {}); }, []);
  const who = partner ?? "your partner";

  async function call(confirmed: string | null) {
    setBusy(true); setError(null);
    try {
      const r = await api<BridgeEnvelope>("/bridge", { method: "POST", json: { scraps, confirmed_meaning: confirmed } });
      setRes(r); setMeaning(r.result?.understood_meaning ?? "");
      setStage(r.status !== "ok" ? "message" : confirmed ? "message" : "confirm"); setTab(r.result?.short_version ? "short" : "full"); setEditing(false);
    } catch (e) { setError(isApiError(e) ? e.message : "Something went wrong."); }
    finally { setBusy(false); }
  }

  const r = res?.result;
  const shown = r ? (tab === "full" ? r.message : tab === "short" ? r.short_version ?? r.message : r.alternatives[tab]?.text ?? r.message) : "";

  return (
    <div>
      <PageHeader eyebrow={`Say it to ${who}`} title="Just type what's in your head.">
        Scraps, half-sentences, typos, all of it. CONVEAZY works out what you mean, checks with you, then writes it in a way {who} can hear, using what {who} has shared about their triggers and what calms them. It changes how it&apos;s said, never what you mean.
      </PageHeader>

      <ol className="mb-8 flex flex-wrap gap-x-5 gap-y-1 text-sm" aria-label="Steps">
        {[["write", "1. Your scraps"], ["confirm", "2. Did I get you right?"], ["message", `3. Your message to ${who}`]].map(([k, l]) => <li key={k} className={stage === k ? "font-medium text-ink" : "text-muted"}>{l}</li>)}
      </ol>

      <div className="max-w-read space-y-6">
        {stage === "write" && <section>
          <label htmlFor="scraps" className="sr-only">What you want to say</label>
          <textarea id="scraps" rows={7} maxLength={4000} className="input font-serif text-[17px] leading-relaxed" value={scraps} onChange={(e) => setScraps(e.target.value)}
            placeholder={"work was bad. didnt reply cuz i was drained not cuz of u\nyou always think im mad\ni want us ok"} />
          <div className="mt-4 flex items-center gap-4"><button className="btn-primary" disabled={!scraps.trim() || busy} onClick={() => call(null)}>Understand me</button>{busy && <Spinner label="Listening…" />}</div>
          <ErrorNote message={error} />
          {!partner && <p className="mt-4 text-sm text-muted">You&apos;re not linked with a partner yet, so this uses general guidance. <Link className="text-ink underline" href="/app/us">Link up</Link> so it can use what they&apos;ve shared.</p>}
        </section>}

        {res?.status === "crisis" && res.crisis && <CrisisCard crisis={res.crisis} />}
        {res?.status === "declined" && <Notice>{res.notice}</Notice>}

        {stage === "confirm" && r && <section className="space-y-4">
          <div className="flex items-center justify-between"><p className="eyebrow">Here&apos;s what I think you&apos;re trying to say</p><ModeBadge live={res!.live} /></div>
          {editing
            ? <textarea aria-label="What you mean" rows={5} className="input font-serif text-[17px]" value={meaning} onChange={(e) => setMeaning(e.target.value)} />
            : <p className="card font-serif text-[18px] leading-relaxed">{r.understood_meaning}</p>}
          {r.clarifying_question && <Notice>{r.clarifying_question}</Notice>}
          <div className="flex flex-wrap items-center gap-3">
            {editing
              ? <button className="btn-primary" disabled={busy || !meaning.trim()} onClick={() => call(meaning)}>This is what I mean</button>
              : <><button className="btn-primary" disabled={busy} onClick={() => call(r.understood_meaning)}>Yes, that&apos;s it</button>
                <button className="btn-ghost" onClick={() => setEditing(true)}>Not quite, let me fix it</button></>}
            <button className="text-sm text-muted underline" onClick={() => setStage("write")}>Back to my scraps</button>
            {busy && <Spinner label="Writing it for them…" />}
          </div>
        </section>}

        {stage === "message" && r && <section className="space-y-5" aria-live="polite">
          {res!.crisis && <CrisisCard crisis={res!.crisis} />}
          <div className="flex items-center justify-between"><p className="eyebrow">Your message to {who}</p><ModeBadge live={res!.live} /></div>
          {r.timing_note && <Notice><span className="font-medium">Timing: </span>{r.timing_note}</Notice>}
          <div className="card">
            <div className="mb-4 flex gap-1 overflow-x-auto" role="tablist">
              {r.short_version && <button role="tab" aria-selected={tab === "short"} onClick={() => setTab("short")} className={`shrink-0 rounded-full px-3.5 py-1.5 text-sm ${tab === "short" ? "bg-ink text-paper" : "text-muted"}`}>Short, for now</button>}
              <button role="tab" aria-selected={tab === "full"} onClick={() => setTab("full")} className={`shrink-0 rounded-full px-3.5 py-1.5 text-sm ${tab === "full" ? "bg-ink text-paper" : "text-muted"}`}>Full message</button>
              {r.alternatives.map((a, i) => <button key={i} role="tab" aria-selected={tab === i} onClick={() => setTab(i)} className={`shrink-0 rounded-full px-3.5 py-1.5 text-sm capitalize ${tab === i ? "bg-ink text-paper" : "text-muted"}`}>{a.style.replace("_", " ")}</button>)}
            </div>
            <p className="whitespace-pre-wrap font-serif text-[18px] leading-relaxed">{shown}</p>
            <div className="mt-4 flex justify-end"><CopyButton text={shown} /></div>
          </div>

          {r.why_this_works.length > 0 && <div className="card"><p className="eyebrow mb-3">Why it&apos;s written this way</p>
            <ul className="space-y-3 text-sm leading-relaxed">{r.why_this_works.map((w, i) => <li key={i}><span className={`mr-2 rounded-full px-2 py-0.5 text-xs font-medium ${GROUND[w.grounded_in].cls}`}>{GROUND[w.grounded_in].label}</span><span className="font-medium">{w.choice}.</span> <span className="text-muted">{w.reason}</span></li>)}</ul></div>}
          {r.avoided.length > 0 && <details className="card"><summary className="cursor-pointer font-medium">What I left out, and why</summary>
            <ul className="mt-3 space-y-2 text-sm">{r.avoided.map((a, i) => <li key={i}><span className="font-medium">{a.pattern}</span> <span className="text-muted">{a.because}</span></li>)}</ul></details>}
          {r.kept_true.length > 0 && <div><p className="eyebrow mb-2">Kept true to you</p><ul className="flex flex-wrap gap-2">{r.kept_true.map((k) => <li key={k} className="rounded-full bg-sage/10 px-3 py-1 text-sm text-sage">{k}</li>)}</ul></div>}
          <p className="text-xs text-muted">Used {res!.recipient.profile_items_used} thing(s) {who} chose to share{res!.recipient.checkin_signal ? ", plus their recent check-in level" : ""}. You decide what to send.</p>
          <Sources citations={res!.citations} />
          <button className="btn-ghost" onClick={() => { setStage("write"); setScraps(""); setRes(null); }}>Write another</button>
        </section>}
      </div>
      <Disclaimer />
    </div>
  );
}
