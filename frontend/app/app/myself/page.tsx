"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Chips, CrisisCard, Disclaimer, ErrorNote, ModeBadge, Notice, PageHeader, Spinner } from "@/components/ui";
import { api, isApiError, type AIEnvelope, type Reflection } from "@/lib/api";

const EMOTIONS = ["hurt", "angry", "anxious", "sad", "ashamed", "lonely", "overwhelmed", "jealous", "confused", "numb", "frustrated", "scared"] as const;
const NEEDS = ["reassurance", "affection", "clarity", "an apology", "space", "to be listened to", "practical help", "a solution"] as const;
const STAGES = ["Situation", "Interpretation", "Emotion", "Need", "Communication"];

type Conv = { id: string; title: string; created_at: string };

export default function Myself() {
  const [step, setStep] = useState(0);
  const [situation, setSituation] = useState("");
  const [interpretation, setInterpretation] = useState("");
  const [emotions, setEmotions] = useState<(typeof EMOTIONS)[number][]>([]);
  const [intensity, setIntensity] = useState(5);
  const [needs, setNeeds] = useState<(typeof NEEDS)[number][]>([]);
  const [res, setRes] = useState<AIEnvelope<Reflection> | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [past, setPast] = useState<Conv[]>([]);

  const loadPast = () => api<{ conversations: Conv[] }>("/conversations?module=myself").then((r) => setPast(r.conversations)).catch(() => {});
  useEffect(() => { loadPast(); }, []);

  async function reflect() {
    setBusy(true); setError(null);
    try {
      const r = await api<AIEnvelope<Reflection>>("/myself/reflect", { method: "POST", json: { situation, interpretation: interpretation || null, emotions, needs, intensity } });
      setRes(r); setStep(4); loadPast();
    } catch (e) { setError(isApiError(e) ? e.message : "Something went wrong."); }
    finally { setBusy(false); }
  }
  async function openPast(id: string) {
    const c = await api<{ messages: { role: string; content: any; meta: any }[] }>(`/conversations/${id}`);
    const input = JSON.parse(c.messages[0].content); const out = c.messages[1];
    setSituation(input.situation); setInterpretation(input.interpretation ?? ""); setEmotions(input.emotions); setNeeds(input.needs); setIntensity(input.intensity ?? 5);
    setRes({ ...out.content, ...out.meta, module: "myself" }); setStep(4);
  }
  function reset() { setStep(0); setSituation(""); setInterpretation(""); setEmotions([]); setNeeds([]); setRes(null); }

  const r = res?.result;
  return (
    <div>
      <PageHeader eyebrow="Understand Myself · private" title="What's underneath this?">
        A private walk from what happened to what you need. Your feelings are never treated as wrong. We only look gently at the story attached to them.
      </PageHeader>

      <ol className="mb-8 flex max-w-read flex-wrap gap-x-4 gap-y-2 text-sm" aria-label="Steps">
        {STAGES.map((s, i) => <li key={s} className={i === step ? "font-medium text-ink" : i < step ? "text-ink/70" : "text-muted"}>{i + 1}. {s}</li>)}
      </ol>

      <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_14rem]">
        <div className="max-w-read">
          {step === 0 && <section>
            <label className="h-card mb-1 block" htmlFor="sit">What happened?</label>
            <p className="mb-3 text-sm text-muted">Just the facts, as a camera would see them, if you can.</p>
            <textarea id="sit" rows={5} className="input" maxLength={3000} value={situation} onChange={(e) => setSituation(e.target.value)} placeholder="I told him I was having a hard day at 2pm. He replied at 7pm with 'ok'." />
            <button className="btn-primary mt-5" disabled={situation.trim().length < 3} onClick={() => setStep(1)}>Next</button>
          </section>}

          {step === 1 && <section>
            <label className="h-card mb-1 block" htmlFor="int">What did it mean to you?</label>
            <p className="mb-3 text-sm text-muted">The story your mind told about it. There&apos;s no wrong answer.</p>
            <textarea id="int" rows={4} className="input" maxLength={2000} value={interpretation} onChange={(e) => setInterpretation(e.target.value)} placeholder="That I'm not a priority. That he's pulling away." />
            <div className="mt-5 flex gap-3"><button className="btn-ghost" onClick={() => setStep(0)}>Back</button><button className="btn-primary" onClick={() => setStep(2)}>Next</button></div>
          </section>}

          {step === 2 && <section>
            <p className="h-card mb-3">What are you feeling?</p>
            <Chips options={EMOTIONS} value={emotions} onChange={setEmotions} multi />
            <label className="label mt-6" htmlFor="inten">How intense? <span className="font-serif text-lg">{intensity}</span>/10</label>
            <input id="inten" type="range" min={1} max={10} value={intensity} onChange={(e) => setIntensity(Number(e.target.value))} className="w-full accent-[rgb(var(--clay))]" />
            <div className="mt-5 flex gap-3"><button className="btn-ghost" onClick={() => setStep(1)}>Back</button><button className="btn-primary" onClick={() => setStep(3)}>Next</button></div>
          </section>}

          {step === 3 && <section>
            <p className="h-card mb-3">What might you need?</p>
            <p className="mb-3 text-sm text-muted">Choose any that resonate, or skip and we&apos;ll explore it together.</p>
            <Chips options={NEEDS} value={needs} onChange={setNeeds} multi />
            <div className="mt-6 flex items-center gap-3"><button className="btn-ghost" onClick={() => setStep(2)}>Back</button>
              <button className="btn-primary" disabled={busy} onClick={reflect}>Reflect with me</button>{busy && <Spinner label="Taking it slowly…" />}</div>
            <ErrorNote message={error} />
          </section>}

          {step === 4 && res && <section className="space-y-5" aria-live="polite">
            {res.status === "crisis" && res.crisis && <CrisisCard crisis={res.crisis} />}
            {res.status === "declined" && <Notice>{res.notice}</Notice>}
            {r && <>
              {res.crisis && <CrisisCard crisis={res.crisis} />}
              <div className="flex justify-end"><ModeBadge live={res.live} /></div>
              <p className="font-serif text-xl leading-snug">{r.validation}</p>
              {[
                ["Situation", r.situation],
                ["Interpretation", r.interpretation],
              ].map(([k, v]) => <div key={k} className="card"><p className="eyebrow mb-2">{k}</p><p className="leading-relaxed">{v}</p></div>)}
              <div className="card">
                <p className="eyebrow mb-2">Checking the story</p>
                <p className="leading-relaxed">{r.evidence_check}</p>
                {r.alternative_interpretations.length > 0 && <><p className="mb-2 mt-4 text-sm font-medium">Other things that could also be true</p>
                  <ul className="list-disc space-y-1 pl-5 text-sm text-muted">{r.alternative_interpretations.map((x) => <li key={x}>{x}</li>)}</ul></>}
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="card"><p className="eyebrow mb-2">Emotion</p><p>{r.emotions.join(", ")}</p></div>
                <div className="card"><p className="eyebrow mb-2">Need</p><p>{r.possible_needs.join(", ")}</p></div>
              </div>
              <div className="card border-ink/20">
                <p className="eyebrow mb-2">How you might say it</p>
                <p className="font-serif text-[18px] leading-relaxed">{r.communication}</p>
                <Link className="btn-ghost mt-4" href={`/app/translate?draft=${encodeURIComponent(r.communication.replace(/^"|"$/g, ""))}`}>Refine in the Translator</Link>
              </div>
              {r.escalation_signs.length > 0 && <div className="card"><p className="eyebrow mb-2">Early signs to notice next time</p>
                <ul className="list-disc space-y-1 pl-5 text-sm">{r.escalation_signs.map((x) => <li key={x}>{x}</li>)}</ul></div>}
              <Notice><span className="font-medium">A next step: </span>{r.next_step}</Notice>
            </>}
            <button className="btn-ghost" onClick={reset}>Start a new reflection</button>
          </section>}
        </div>
        <aside className="text-sm">
          <p className="eyebrow mb-3">Past reflections</p>
          {past.length === 0 ? <p className="text-muted">Only you can see these.</p> :
            <ul className="space-y-1">{past.map((c) => <li key={c.id}><button className="w-full truncate rounded-lg px-2 py-1.5 text-left text-muted hover:bg-ink/[0.04] hover:text-ink" onClick={() => openPast(c.id)}>{c.title}</button></li>)}</ul>}
        </aside>
      </div>
      <Disclaimer />
    </div>
  );
}
