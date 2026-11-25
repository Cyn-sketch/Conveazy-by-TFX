"use client";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Chips, CopyButton, CrisisCard, Disclaimer, ErrorNote, ModeBadge, Notice, PageHeader, Spinner } from "@/components/ui";
import { api, isApiError, type AIEnvelope, type TranslatorResult } from "@/lib/api";

const STYLES = ["gentle", "direct", "reassuring", "boundary", "apologetic", "emotionally_honest"] as const;
const STYLE_LABELS = { gentle: "Gentle", direct: "Direct", reassuring: "Reassuring", boundary: "Boundary-setting", apologetic: "Apologetic", emotionally_honest: "Emotionally honest" } as const;
const CAT_LABELS: Record<string, string> = { accusatory: "Accusatory", absolute: "Absolute", dismissive: "Dismissive", defensive: "Defensive", invalidating: "Invalidating", escalating: "Escalating", mind_reading: "Mind-reading", sarcasm: "Sarcasm", threat: "Threat", contempt: "Contempt" };

function Highlighted({ text, phrases }: { text: string; phrases: string[] }) {
  if (!phrases.length) return <>{text}</>;
  const esc = phrases.filter(Boolean).map((p) => p.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const parts = text.split(new RegExp(`(${esc.join("|")})`, "gi"));
  return <>{parts.map((p, i) => esc.some((e) => new RegExp(`^${e}$`, "i").test(p))
    ? <mark key={i} className="rounded bg-clay/15 px-0.5 text-ink underline decoration-clay decoration-wavy decoration-1 underline-offset-4">{p}</mark> : <span key={i}>{p}</span>)}</>;
}

function Translator() {
  const params = useSearchParams();
  const [draft, setDraft] = useState("");
  const [styles, setStyles] = useState<(typeof STYLES)[number][]>([]);
  const [save, setSave] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [res, setRes] = useState<AIEnvelope<TranslatorResult> | null>(null);
  const [sent, setSent] = useState("");
  const [tab, setTab] = useState(0);

  useEffect(() => { const d = params.get("draft"); if (d) setDraft(d); }, [params]);

  async function run() {
    setBusy(true); setError(null); setRes(null);
    try {
      const r = await api<AIEnvelope<TranslatorResult>>("/translate", { method: "POST", json: { draft, styles: styles.length ? styles : null, save } });
      setRes(r); setSent(draft); setTab(0);
    } catch (e) { setError(isApiError(e) ? e.message : "Something went wrong."); }
    finally { setBusy(false); }
  }

  const r = res?.result;
  return (
    <div>
      <PageHeader eyebrow="Message Translator" title="Say it the way you mean it.">
        Write it exactly as it is in your head: angry, messy, half-finished. Nothing is sent anywhere. You get versions that keep your feelings and boundaries, and drop the parts that might start a fight you don&apos;t want.
      </PageHeader>

      <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <section className="space-y-5">
          <div>
            <label htmlFor="draft" className="label">Your unfiltered message</label>
            <textarea id="draft" rows={8} className="input font-serif text-[17px] leading-relaxed" maxLength={4000} value={draft} onChange={(e) => setDraft(e.target.value)}
              placeholder="You never text back when you say you will. Whatever, I'm used to it." />
            <p className="mt-1 text-right text-xs text-muted">{draft.length}/4000</p>
          </div>
          <div><p className="label">Versions you&apos;d like <span className="font-normal text-muted">(optional, we&apos;ll pick if you don&apos;t)</span></p>
            <Chips options={STYLES} value={styles} onChange={setStyles} multi labels={STYLE_LABELS} /></div>
          <label className="flex items-center gap-2 text-sm text-muted"><input type="checkbox" checked={save} onChange={(e) => setSave(e.target.checked)} className="accent-[rgb(var(--ink))]" /> Save to my private history</label>
          <div className="flex items-center gap-4">
            <button className="btn-primary" disabled={!draft.trim() || busy} onClick={run}>Translate</button>
            {busy && <Spinner label="Reading between the lines…" />}
          </div>
          <ErrorNote message={error} />
        </section>

        <section aria-live="polite" className="min-w-0">
          {!res && !busy && <div className="card border-dashed text-sm leading-relaxed text-muted">Your versions will appear here. You&apos;ll also see which phrases might land differently than you intend, and why.</div>}
          {res?.status === "crisis" && res.crisis && <CrisisCard crisis={res.crisis} />}
          {res?.status === "declined" && <Notice>{res.notice}</Notice>}
          {r && (
            <div className="space-y-5">
              {res.crisis && <CrisisCard crisis={res.crisis} />}
              <div className="flex items-center justify-between gap-3"><p className="eyebrow">What you&apos;re saying underneath</p><ModeBadge live={res.live} /></div>
              <p className="font-serif text-xl leading-snug">{r.intent_summary}</p>

              <div className="card">
                <div className="mb-4 flex gap-1 overflow-x-auto" role="tablist">
                  {r.versions.map((v, i) => (
                    <button key={v.style} role="tab" aria-selected={tab === i} onClick={() => setTab(i)}
                      className={`shrink-0 rounded-full px-3.5 py-1.5 text-sm ${tab === i ? "bg-blush text-ink" : "text-muted hover:text-ink"}`}>
                      {STYLE_LABELS[v.style as keyof typeof STYLE_LABELS] ?? v.style}</button>
                  ))}
                </div>
                {r.versions[tab] && <>
                  <p className="whitespace-pre-wrap font-serif text-[18px] leading-relaxed">{r.versions[tab].text}</p>
                  <div className="mt-4 flex justify-end"><CopyButton text={r.versions[tab].text} /></div>
                </>}
              </div>

              {r.boundary_note && <Notice><span className="font-medium">Your boundary stays.</span> <span className="text-muted">{r.boundary_note}</span></Notice>}

              <details className="card" open>
                <summary className="cursor-pointer font-medium">How the original might land</summary>
                <blockquote className="mt-4 border-l-2 border-line pl-4 font-serif leading-relaxed text-muted"><Highlighted text={sent} phrases={r.flags.map((f) => f.phrase)} /></blockquote>
                <p className="mt-4 leading-relaxed">{r.how_original_may_land}</p>
                {r.flags.length > 0 && <ul className="mt-4 space-y-3">
                  {r.flags.map((f, i) => (
                    <li key={i} className="text-sm leading-relaxed"><span className="mr-2 rounded-full bg-clay/10 px-2 py-0.5 text-xs font-medium text-clay">{CAT_LABELS[f.category] ?? f.category}</span>
                      <span className="font-medium">&ldquo;{f.phrase}&rdquo;</span> <span className="text-muted">{f.how_it_may_land}</span></li>))}
                </ul>}
              </details>

              <details className="card">
                <summary className="cursor-pointer font-medium">What changed, and what we kept</summary>
                <ul className="mt-4 space-y-2 text-sm">{r.changes.map((c, i) => <li key={i}><span className="font-medium">{c.what}.</span> <span className="text-muted">{c.why}</span></li>)}</ul>
                {r.preserved.length > 0 && <><p className="eyebrow mb-2 mt-5">Kept on purpose</p>
                  <ul className="flex flex-wrap gap-2">{r.preserved.map((p) => <li key={p} className="rounded-full bg-sage/10 px-3 py-1 text-sm text-sage">{p}</li>)}</ul></>}
              </details>
              <p className="text-xs text-muted">You decide what to send, if anything. Prompt {res.prompt_version} · {res.provider}</p>
            </div>
          )}
        </section>
      </div>
      <Disclaimer />
    </div>
  );
}

export default function Page() { return <Suspense><Translator /></Suspense>; }
