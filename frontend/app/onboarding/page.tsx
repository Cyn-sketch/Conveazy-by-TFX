"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Wordmark } from "@/components/Brand";
import { ErrorNote } from "@/components/ui";
import { api, isApiError } from "@/lib/api";

const STEPS = ["What this is", "Your privacy", "A little about you"];

function Toggle({ checked, onChange, title, children, id }: { checked: boolean; onChange: (v: boolean) => void; title: string; children: React.ReactNode; id: string }) {
  return (
    <label htmlFor={id} className="flex cursor-pointer gap-4 rounded-xl2 border border-line bg-surface p-4">
      <input id={id} type="checkbox" className="mt-1 h-4 w-4 accent-[rgb(var(--ink))]" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span><span className="block font-medium">{title}</span><span className="mt-1 block text-sm leading-relaxed text-muted">{children}</span></span>
    </label>
  );
}

export default function Onboarding() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [care, setCare] = useState(false);
  const [ai, setAi] = useState(true);
  const [training, setTraining] = useState(false);
  const [saveHistory, setSaveHistory] = useState(true);
  const [retention, setRetention] = useState(365);
  const [pronouns, setPronouns] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function finish() {
    try {
      await api("/onboarding", { method: "POST", json: {
        accept_terms_and_care: care, ai_processing: ai, model_training: training,
        retention_days: retention, save_history: saveHistory, pronouns: pronouns || null } });
      router.replace("/app");
    } catch (e) { setError(isApiError(e) ? e.message : "Something went wrong."); }
  }

  return (
    <main className="mx-auto min-h-dvh max-w-xl px-5 py-10">
      <Wordmark withSignature />
      <ol className="mb-10 mt-10 flex gap-2" aria-label="Progress">
        {STEPS.map((s, i) => <li key={s} className={`h-1 flex-1 rounded-full ${i <= step ? "bg-ink" : "bg-line"}`} aria-current={i === step ? "step" : undefined}><span className="sr-only">{s}</span></li>)}
      </ol>

      {step === 0 && (
        <section>
          <p className="eyebrow mb-3">Step 1 of 3</p>
          <h1 className="h-page mb-5">A bridge, not a referee.</h1>
          <div className="space-y-4 leading-relaxed text-muted">
            <p>CONVEAZY helps two people understand each other, especially when emotions run high or communication styles differ. It treats both of you as equally worth understanding.</p>
            <p><strong className="text-ink">What it is:</strong> a place to rewrite hard messages, learn why things land the way they do, and reflect on what you need.</p>
            <p><strong className="text-ink">What it isn&apos;t:</strong> therapy, a diagnosis, or a judge of who&apos;s right. It never decides that a diagnosis explains someone&apos;s behaviour, and it can&apos;t respond to emergencies.</p>
          </div>
          <div className="mt-6"><Toggle id="care" checked={care} onChange={setCare} title="I understand">CONVEAZY complements professional care. It doesn&apos;t replace a therapist, doctor or crisis service.</Toggle></div>
          <button className="btn-primary mt-8" disabled={!care} onClick={() => setStep(1)}>Continue</button>
        </section>
      )}

      {step === 1 && (
        <section>
          <p className="eyebrow mb-3">Step 2 of 3</p>
          <h1 className="h-page mb-3">Private by default.</h1>
          <p className="mb-6 leading-relaxed text-muted">Your partner can never see your drafts, reflections, check-ins or questions. If you link up later, you choose, one item at a time, what to share.</p>
          <div className="space-y-3">
            <Toggle id="ai" checked={ai} onChange={setAi} title="Let AI process what I write">Needed for the Translator, Understand My Partner and Understand Myself. Text is sent to the AI provider only to generate your response.</Toggle>
            <Toggle id="hist" checked={saveHistory} onChange={setSaveHistory} title="Save my history">Keeps past conversations and reflections in your private space (encrypted). Turn it off to keep nothing.</Toggle>
            <Toggle id="train" checked={training} onChange={setTraining} title="Allow anonymised use to improve CONVEAZY (optional)">Off by default. We never use intimate conversations or mental-health information for model training without this consent.</Toggle>
          </div>
          <div className="mt-5">
            <label className="label" htmlFor="ret">Automatically delete my history after</label>
            <select id="ret" className="input" value={retention} onChange={(e) => setRetention(Number(e.target.value))}>
              {[[30, "30 days"], [90, "90 days"], [365, "1 year"], [1095, "3 years"]].map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </div>
          <div className="mt-8 flex gap-3"><button className="btn-ghost" onClick={() => setStep(0)}>Back</button><button className="btn-primary" onClick={() => setStep(2)}>Continue</button></div>
        </section>
      )}

      {step === 2 && (
        <section>
          <p className="eyebrow mb-3">Step 3 of 3</p>
          <h1 className="h-page mb-3">Almost there.</h1>
          <p className="mb-6 leading-relaxed text-muted">We don&apos;t ask about diagnoses. If you ever want CONVEAZY to know about your health or life context, you can add it yourself in your profile, and keep it private.</p>
          <label className="label" htmlFor="pr">Pronouns (optional)</label>
          <input id="pr" className="input" maxLength={40} placeholder="e.g. she/her" value={pronouns} onChange={(e) => setPronouns(e.target.value)} />
          <ErrorNote message={error} />
          <div className="mt-8 flex gap-3"><button className="btn-ghost" onClick={() => setStep(1)}>Back</button><button className="btn-primary" onClick={finish}>Enter my space</button></div>
        </section>
      )}
    </main>
  );
}
