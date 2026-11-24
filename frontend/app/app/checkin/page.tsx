"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Chips, CrisisCard, Disclaimer, ErrorNote, Notice, PageHeader } from "@/components/ui";
import { api, isApiError, type Crisis } from "@/lib/api";

const EMOTIONS = ["calm", "anxious", "overwhelmed", "angry", "hurt", "disconnected", "numb", "confused", "frustrated"] as const;
const NEEDS = ["reassurance", "affection", "clarity", "apology", "space", "listening", "practical_help", "solution"] as const;
const INTENTS = ["communicate", "reflect", "break"] as const;
const INTENT_LABELS = { communicate: "Talk to my partner", reflect: "Reflect on my own", break: "Take a break" } as const;

type Row = { id: string; emotion: string; intensity: number; need: string; intent: string; note: string | null; created_at: string };
type Res = { checkin: Row; next: { label: string; href: string | null }; guidance: string | null; crisis: Crisis | null; disclaimer: string };

export default function CheckIn() {
  const [emotion, setEmotion] = useState<(typeof EMOTIONS)[number][]>([]);
  const [need, setNeed] = useState<(typeof NEEDS)[number][]>([]);
  const [intent, setIntent] = useState<(typeof INTENTS)[number][]>([]);
  const [intensity, setIntensity] = useState(5);
  const [note, setNote] = useState("");
  const [res, setRes] = useState<Res | null>(null);
  const [history, setHistory] = useState<Row[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = () => api<{ checkins: Row[] }>("/checkins").then((r) => setHistory(r.checkins)).catch(() => {});
  useEffect(() => { load(); }, []);

  async function submit() {
    setError(null);
    try {
      const r = await api<Res>("/checkins", { method: "POST", json: { emotion: emotion[0], need: need[0], intent: intent[0], intensity, note: note || null } });
      setRes(r); load();
    } catch (e) { setError(isApiError(e) ? e.message : "Couldn't save your check-in."); }
  }
  async function remove(id: string) { await api(`/checkins/${id}`, { method: "DELETE" }); load(); }

  if (res) return (
    <div className="max-w-read">
      <PageHeader eyebrow="Check-in saved" title="Thank you for noticing.">
        {res.checkin.emotion}, {res.checkin.intensity}/10, needing {res.checkin.need.replace("_", " ")}. {res.disclaimer}
      </PageHeader>
      <div className="space-y-4">
        {res.crisis && <CrisisCard crisis={res.crisis} />}
        {res.guidance && <Notice>{res.guidance}</Notice>}
        {res.checkin.intent === "break" ? (
          <Notice>
            <p className="h-card mb-2">Taking a break is a skill, not avoidance.</p>
            <p className="text-muted">If you can, let your partner know you&apos;re stepping away and when you&apos;ll be back, e.g. <em>&quot;I need 20 minutes to settle. I&apos;m not leaving the conversation.&quot;</em> Then do something that brings your body down a notch: water, a walk, slow breathing, music.</p>
          </Notice>
        ) : res.next.href && <Link href={res.next.href} className="btn-primary">{res.next.label}</Link>}
        <button className="btn-ghost ml-0 sm:ml-3" onClick={() => setRes(null)}>New check-in</button>
      </div>
    </div>
  );

  return (
    <div>
      <PageHeader eyebrow="Emotional check-in" title="Where are you at?">
        A private note to yourself. It isn&apos;t an assessment, and your partner never sees it. It helps CONVEAZY respond to you with care for the next few hours.
      </PageHeader>
      <div className="max-w-read space-y-8">
        <section><p className="label">I&apos;m feeling</p><Chips options={EMOTIONS} value={emotion} onChange={setEmotion} /></section>
        <section>
          <label className="label" htmlFor="int">How strong is it? <span className="font-serif text-lg">{intensity}</span><span className="text-muted">/10</span></label>
          <input id="int" type="range" min={1} max={10} value={intensity} onChange={(e) => setIntensity(Number(e.target.value))} className="w-full accent-[rgb(var(--clay))]" />
          <div className="flex justify-between text-xs text-muted"><span>barely there</span><span>all-consuming</span></div>
        </section>
        <section><label className="label" htmlFor="note">What happened? <span className="font-normal text-muted">(optional)</span></label>
          <textarea id="note" rows={3} className="input" maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)} placeholder="A sentence is enough." /></section>
        <section><p className="label">What would help most right now?</p><Chips options={NEEDS} value={need} onChange={setNeed} /></section>
        <section><p className="label">I want to</p><Chips options={INTENTS} value={intent} onChange={setIntent} labels={INTENT_LABELS} /></section>
        <ErrorNote message={error} />
        <button className="btn-primary" disabled={!emotion[0] || !need[0] || !intent[0]} onClick={submit}>Save check-in</button>
      </div>

      {history.length > 0 && (
        <section className="mt-14 max-w-read">
          <p className="eyebrow mb-3">Your recent check-ins</p>
          <ul className="divide-y divide-line rounded-xl2 border border-line bg-surface">
            {history.slice(0, 10).map((h) => (
              <li key={h.id} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
                <span><span className="font-medium capitalize">{h.emotion}</span> · {h.intensity}/10 · {h.need.replace("_", " ")}
                  <span className="block text-xs text-muted">{new Date(h.created_at).toLocaleString()}</span></span>
                <button className="text-xs text-muted hover:text-warn" onClick={() => remove(h.id)} aria-label="Delete check-in">Delete</button>
              </li>
            ))}
          </ul>
        </section>
      )}
      <Disclaimer />
    </div>
  );
}
