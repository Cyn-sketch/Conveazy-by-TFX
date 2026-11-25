"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { CrisisCard, Disclaimer, ErrorNote, ModeBadge, Notice, PageHeader, Spinner } from "@/components/ui";
import { api, isApiError, type BridgeEnvelope, type BridgeResult } from "@/lib/api";

function briefText(r: BridgeResult, sender: string, intensity: number) {
  const b = r.brief;
  if (!b) return "";
  return [
    `What ${sender} is really feeling (from CONVEAZY)`, b.feeling, `How strong it is: ${intensity}/10`, b.why,
    "To get a sense of it:", ...b.like.map((x) => `- ${x}`), b.need,
    ...(b.traits.length ? [`Patterns ${sender} chose to share (not a diagnosis):`, ...b.traits.map((t) => `- ${t.trait}${t.sign ? `: ${t.sign}` : ""}`)] : []),
  ].filter(Boolean).join("\n");
}

function Copy({ text, label, primary }: { text: string; label: string; primary?: boolean }) {
  const [done, setDone] = useState(false);
  return <button type="button" className={primary ? "btn-primary" : "text-sm text-muted hover:text-ink"}
    onClick={async () => { await navigator.clipboard.writeText(text); setDone(true); setTimeout(() => setDone(false), 1500); }}>{done ? "Copied" : label}</button>;
}

export default function Bridge() {
  const [me, setMe] = useState("You");
  const [partner, setPartner] = useState<string | null>(null);
  const [situation, setSituation] = useState("");
  const [scraps, setScraps] = useState("");
  const [res, setRes] = useState<BridgeEnvelope | null>(null);
  const [stage, setStage] = useState<"write" | "confirm" | "message">("write");
  const [meaning, setMeaning] = useState("");
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"full" | "short">("full");
  const [includeFeelings, setIncludeFeelings] = useState(true);
  const [intensity, setIntensity] = useState(6);
  const [shareTraits, setShareTraits] = useState(false);
  const [read, setRead] = useState<BridgeResult | null>(null); // the private read from step 2 (feelings, traits, calm)

  useEffect(() => {
    api<{ partner?: { name: string } }>("/relationship").then((r) => setPartner(r.partner?.name ?? null)).catch(() => {});
    api<{ display_name: string }>("/auth/me").then((u) => setMe(u.display_name)).catch(() => {});
  }, []);
  const who = partner ?? "your partner";

  async function call(confirmed: string | null) {
    setBusy(true); setError(null);
    try {
      const traits = read?.raw_feelings?.traits ?? [];
      const r = await api<BridgeEnvelope>("/bridge", { method: "POST", json: {
        situation, scraps, confirmed_meaning: confirmed, include_feelings: confirmed ? includeFeelings : false,
        intensity: confirmed ? intensity : null, share_traits: confirmed ? shareTraits : false, traits: confirmed ? traits : [] } });
      setRes(r); setMeaning(r.result?.understood_meaning ?? "");
      if (!confirmed && r.result) { setRead(r.result); setIntensity(r.result.raw_feelings?.intensity ?? 6); setShareTraits(false); }
      setStage(r.status !== "ok" ? "message" : confirmed ? "message" : "confirm"); setTab(r.result?.short_version ? "short" : "full"); setEditing(false);
    } catch (e) { setError(isApiError(e) ? e.message : "Something went wrong."); }
    finally { setBusy(false); }
  }

  const r = res?.result;
  const shown = r ? (tab === "short" ? r.short_version ?? r.message : r.message) : "";
  const rf = read?.raw_feelings;

  return (
    <div>
      <PageHeader eyebrow={`Say it to ${who}`} title="Tell me what happened.">
        Messy is fine. CONVEAZY works out what you want to say, checks with you, then words it so {who} can hear it, with a short note that makes sure they understand how you really feel.
      </PageHeader>

      <ol className="mb-8 flex flex-wrap gap-x-5 gap-y-1 text-sm" aria-label="Steps">
        {[["write", "1. What happened"], ["confirm", "2. Did I get you right?"], ["message", `3. Your message to ${who}`]].map(([k, l]) => <li key={k} className={stage === k ? "font-medium text-ink" : "text-muted"}>{l}</li>)}
      </ol>

      <div className="max-w-read space-y-6">
        {stage === "write" && <section className="space-y-5">
          <div>
            <label htmlFor="situation" className="mb-2 block text-sm font-medium">What happened</label>
            <textarea id="situation" rows={6} maxLength={6000} className="input" value={situation} onChange={(e) => setSituation(e.target.value)}
              placeholder="Tell CONVEAZY the situation in your own words: what happened, when, what was said, how it left you. This alone is enough to draft a message." />
          </div>
          <div>
            <label htmlFor="scraps" className="mb-2 block text-sm font-medium">What you want to say <span className="font-normal text-muted">(optional: rough words you want in the message)</span></label>
            <textarea id="scraps" rows={4} maxLength={4000} className="input font-serif text-[17px] leading-relaxed" value={scraps} onChange={(e) => setScraps(e.target.value)}
              placeholder="e.g. i'm not mad, i just need you to talk to me" />
          </div>
          <div className="flex items-center gap-4"><button className="btn-primary" disabled={(!situation.trim() && !scraps.trim()) || busy} onClick={() => call(null)}>Understand me</button>{busy && <Spinner label="Reading you…" />}</div>
          <ErrorNote message={error} />
          {!partner && <p className="text-sm text-muted">You&apos;re not linked with a partner yet, so this uses general guidance. <Link className="text-ink underline" href="/app/us">Link up</Link> so it can use what they&apos;ve shared.</p>}
        </section>}

        {res?.crisis && <CrisisCard crisis={res.crisis} />}
        {res?.status === "declined" && <Notice>{res.notice}</Notice>}

        {stage === "confirm" && rf && <section className="rounded-xl2 border border-clay/30 bg-clay/5 p-5 sm:p-6">
          <p className="eyebrow mb-2">What you&apos;re feeling right now · only you see this</p>
          <p className="font-serif text-[19px] leading-snug">{rf.right_now}</p>
          {rf.underneath && <p className="mt-3 font-serif text-[17px] italic leading-snug text-ink/80">{rf.underneath}</p>}
          <ul className="mt-4 flex flex-wrap gap-2">{rf.feelings.map((f) => <li key={f} className="rounded-full bg-clay/10 px-3 py-1 text-sm text-clay">{f}</li>)}</ul>
          <label className="mt-5 flex cursor-pointer items-start gap-3 text-sm">
            <input type="checkbox" className="mt-0.5 h-4 w-4 accent-[rgb(var(--ink))]" checked={includeFeelings} onChange={(e) => setIncludeFeelings(e.target.checked)} />
            <span>Put how I feel in the message: <em className="font-serif text-[15px]">&ldquo;{rf.feelings_line}&rdquo;</em></span>
          </label>
          <div className="mt-5">
            <label htmlFor="intensity" className="flex justify-between text-sm"><span>How intense is this for you right now?</span><b className="font-medium">{intensity}/10</b></label>
            <input id="intensity" type="range" min={1} max={10} value={intensity} onChange={(e) => setIntensity(+e.target.value)} className="w-full accent-[rgb(var(--clay))]" />
            <p className="mt-1 text-xs text-muted">{who} will see this number in the brief, so they know how much it&apos;s hurting.</p>
          </div>
        </section>}

        {stage === "confirm" && rf && rf.traits.length > 0 && <section className="card">
          <p className="eyebrow mb-2">Patterns you might be showing · private</p>
          <ul className="space-y-2 text-sm">{rf.traits.map((t) => <li key={t.trait}><span className="font-medium">{t.trait}.</span> <span className="text-muted">{t.sign}</span></li>)}</ul>
          <p className="mt-3 text-xs text-muted">These are suggestions to help you understand yourself. They&apos;re not a diagnosis, and only a qualified professional can diagnose. They stay with you unless you choose to share them.</p>
          <label className="mt-3 flex cursor-pointer items-center gap-3 text-sm">
            <input type="checkbox" className="h-4 w-4 accent-[rgb(var(--ink))]" checked={shareTraits} onChange={(e) => setShareTraits(e.target.checked)} />
            Share these with {who} in the brief
          </label>
        </section>}

        {stage === "confirm" && read && read.calm.length > 0 && <section className="card">
          <p className="eyebrow mb-2">Calm down first · only you see this</p>
          <p className="mb-3 text-sm text-muted">Doing one of these before you send can make the whole conversation go better.</p>
          <div className="space-y-2">{read.calm.map((c) => <details key={c.id} className="rounded-lg border border-line px-4 py-3">
            <summary className="cursor-pointer text-sm"><span className="font-medium">{c.exercise.name}</span> <span className="text-muted">· {c.why}</span></summary>
            <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm">{c.exercise.steps.map((s) => <li key={s}>{s}</li>)}</ol>
            {c.exercise.caution && <p className="mt-2 text-xs text-clay">{c.exercise.caution}</p>}
            <p className="mt-1 text-xs text-muted">From: {c.exercise.source}</p>
          </details>)}</div>
        </section>}

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
            <button className="text-sm text-muted underline" onClick={() => setStage("write")}>Back</button>
            {busy && <Spinner label="Writing it for them…" />}
          </div>
        </section>}

        {stage === "message" && r && <section className="space-y-5" aria-live="polite">
          <div className="flex items-center justify-between"><p className="eyebrow">Your message to {who}</p><ModeBadge live={res!.live} /></div>
          {r.timing_note && <Notice>{r.timing_note}</Notice>}
          <div className="card">
            {r.short_version && <div className="mb-4 flex gap-1" role="tablist">
              <button role="tab" aria-selected={tab === "short"} onClick={() => setTab("short")} className={`rounded-full px-3.5 py-1.5 text-sm ${tab === "short" ? "bg-blush text-ink" : "text-muted"}`}>Send now</button>
              <button role="tab" aria-selected={tab === "full"} onClick={() => setTab("full")} className={`rounded-full px-3.5 py-1.5 text-sm ${tab === "full" ? "bg-blush text-ink" : "text-muted"}`}>Full message</button>
            </div>}
            <p className="whitespace-pre-wrap font-serif text-[18px] leading-relaxed" data-testid="message">{shown}</p>
          </div>

          {r.brief && <section className="card border-clay/30" data-testid="brief">
            <p className="eyebrow mb-2">Goes with the message · what {me} is really feeling</p>
            <p className="font-serif text-[18px] leading-snug">{r.brief.feeling}</p>
            <div className="my-3 flex items-center gap-3 text-sm"><span className="text-muted">How strong it is</span>
              <span className="h-2 max-w-[12rem] flex-1 overflow-hidden rounded-full bg-line"><i className="block h-full bg-clay" style={{ width: `${intensity * 10}%` }} /></span><b className="font-medium">{intensity}/10</b></div>
            {r.brief.why && <p className="mb-3 text-sm">{r.brief.why}</p>}
            <p className="eyebrow mb-1">To get a sense of it</p>
            <ul className="mb-3 list-disc space-y-1 pl-5 text-sm">{r.brief.like.map((x) => <li key={x}>{x}</li>)}</ul>
            {r.brief.need && <p className="text-sm font-medium">{r.brief.need}</p>}
            {r.brief.traits.length > 0 && <><p className="eyebrow mb-1 mt-3">Patterns {me} chose to share · not a diagnosis</p>
              <ul className="list-disc space-y-1 pl-5 text-sm">{r.brief.traits.map((t) => <li key={t.trait}><span className="font-medium">{t.trait}</span>{t.sign ? `: ${t.sign}` : ""}</li>)}</ul></>}
          </section>}

          <div className="flex items-center justify-end gap-4">
            <Copy text={shown} label="Copy message only" />
            <Copy primary text={shown + (r.brief ? "\n\n" + briefText(r, me, intensity) : "")} label={r.brief ? "Copy message + brief" : "Copy message"} />
          </div>

          {(r.why_this_works.length > 0 || r.avoided.length > 0) && <details className="card"><summary className="cursor-pointer font-medium">Why it&apos;s written this way</summary>
            <ul className="mt-3 space-y-2 text-sm">
              {r.why_this_works.map((w, i) => <li key={`w${i}`}><span className="font-medium">{w.choice}.</span> <span className="text-muted">{w.reason}</span></li>)}
              {r.avoided.map((a, i) => <li key={`a${i}`}><span className="font-medium">Left out {a.pattern}.</span> <span className="text-muted">{a.because}</span></li>)}
            </ul></details>}
          <button className="btn-ghost" onClick={() => { setStage("write"); setSituation(""); setScraps(""); setRes(null); setRead(null); }}>Write another</button>
        </section>}
      </div>
      <Disclaimer />
    </div>
  );
}
