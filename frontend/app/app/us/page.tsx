"use client";
import { useEffect, useState } from "react";
import { Disclaimer, ErrorNote, PageHeader } from "@/components/ui";
import { api, isApiError } from "@/lib/api";

type Field = { key: string; label: string; value: string | null; share_with_partner: boolean; use_in_ai: boolean };
type Rel = { status: "none" | "pending" | "linked"; invite_code?: string; partner?: { name: string; pronouns: string | null }; partner_shared?: { key: string; label: string; value: string }[] };

function Switch({ on, onChange, label }: { on: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button type="button" role="switch" aria-checked={on} onClick={() => onChange(!on)} className="flex items-center gap-2 text-xs text-muted">
      <span className={`relative h-5 w-9 rounded-full transition ${on ? "bg-ink" : "bg-line"}`}><span className={`absolute top-0.5 h-4 w-4 rounded-full bg-surface shadow transition ${on ? "left-[1.15rem]" : "left-0.5"}`} /></span>
      {label}
    </button>
  );
}

function FieldEditor({ f, onSaved }: { f: Field; onSaved: () => void }) {
  const [value, setValue] = useState(f.value ?? "");
  const [share, setShare] = useState(f.share_with_partner);
  const [ai, setAi] = useState(f.use_in_ai);
  const [state, setState] = useState<"idle" | "saving" | "saved">("idle");
  const [base, setBase] = useState({ value: f.value ?? "", share: f.share_with_partner, ai: f.use_in_ai });
  const dirty = value !== base.value || share !== base.share || ai !== base.ai;

  async function save() {
    setState("saving");
    if (value.trim()) await api(`/profile/${f.key}`, { method: "PUT", json: { value, share_with_partner: share, use_in_ai: ai } });
    else await api(`/profile/${f.key}`, { method: "DELETE" });
    setBase({ value, share, ai }); setState("saved"); onSaved(); setTimeout(() => setState("idle"), 1500);
  }
  return (
    <div className="card">
      <label className="mb-2 block font-medium" htmlFor={f.key}>{f.label}</label>
      <textarea id={f.key} rows={2} maxLength={2000} className="input text-sm" value={value} onChange={(e) => setValue(e.target.value)} />
      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2">
        <Switch on={share} onChange={setShare} label="Share with partner" />
        <Switch on={ai} onChange={setAi} label="Let AI use this" />
        <button className="ml-auto text-sm font-medium disabled:text-muted" disabled={!dirty || state === "saving"} onClick={save}>{state === "saved" ? "Saved" : state === "saving" ? "Saving…" : "Save"}</button>
      </div>
    </div>
  );
}

export default function Us() {
  const [rel, setRel] = useState<Rel | null>(null);
  const [fields, setFields] = useState<Field[]>([]);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    api<Rel>("/relationship").then(setRel);
    api<{ fields: Field[] }>("/profile").then((r) => setFields(r.fields));
  };
  useEffect(load, []);

  async function act(fn: () => Promise<unknown>) { setError(null); try { await fn(); load(); } catch (e) { setError(isApiError(e) ? e.message : "Something went wrong."); } }

  return (
    <div>
      <PageHeader eyebrow="About us" title="Tell CONVEAZY who you are.">
        Write about yourself in your own words: how you feel, what triggers you, what calms you down, and any diagnoses you want it to know about. The more you share, the better it can write for you and to you. Your answers come from you, never guessed from a diagnosis. Everything is private until you switch on &ldquo;Share with partner&rdquo;. The AI only uses an answer when you switch on &ldquo;Let AI use this&rdquo;.
      </PageHeader>

      <section className="card mb-10 max-w-read">
        <p className="eyebrow mb-3">Shared space</p>
        {rel?.status === "none" && <>
          <p className="mb-4 leading-relaxed text-muted">Link with your partner to see what each of you chooses to share. Your private spaces stay private either way.</p>
          <div className="flex flex-col gap-3 sm:flex-row">
            <button className="btn-primary" onClick={() => act(() => api("/relationship/invite", { method: "POST" }))}>Create an invite code</button>
            <form className="flex flex-1 gap-2" onSubmit={(e) => { e.preventDefault(); act(() => api("/relationship/join", { method: "POST", json: { code } })); }}>
              <label htmlFor="code" className="sr-only">Invite code</label>
              <input id="code" className="input py-2.5 uppercase" placeholder="ABCD-EF23" value={code} onChange={(e) => setCode(e.target.value)} />
              <button className="btn-ghost" disabled={code.length < 4}>Join</button>
            </form>
          </div>
        </>}
        {rel?.status === "pending" && <>
          <p className="mb-3 text-muted">Share this code with your partner. It works once.</p>
          <p className="font-serif text-3xl tracking-[0.2em]" data-testid="invite-code">{rel.invite_code}</p>
          <button className="mt-4 text-sm text-muted underline" onClick={() => act(() => api("/relationship", { method: "DELETE" }))}>Cancel invite</button>
        </>}
        {rel?.status === "linked" && <>
          <p className="h-card">You&apos;re linked with {rel.partner?.name}{rel.partner?.pronouns ? ` (${rel.partner.pronouns})` : ""}.</p>
          <p className="mt-2 text-sm text-muted">Either of you can end the shared space at any time. Your drafts, check-ins, reflections and questions are never shared.</p>
          <button className="mt-4 text-sm text-warn underline" onClick={() => { if (confirm("End the shared space? You'll both stop seeing each other's shared answers.")) act(() => api("/relationship", { method: "DELETE" })); }}>End shared space</button>
        </>}
        <ErrorNote message={error} />
      </section>

      {rel?.status === "linked" && (
        <section className="mb-12 max-w-read">
          <p className="eyebrow mb-3">What {rel.partner?.name} has chosen to share</p>
          {rel.partner_shared?.length ? (
            <dl className="divide-y divide-line rounded-xl2 border border-sage/30 bg-sage/5">
              {rel.partner_shared.map((s) => <div key={s.key} className="px-5 py-4"><dt className="text-sm text-muted">{s.label}</dt><dd className="mt-1 font-serif text-[17px]">{s.value}</dd></div>)}
            </dl>
          ) : <p className="text-sm text-muted">Nothing yet. That&apos;s their choice to make, in their own time.</p>}
        </section>
      )}

      <section className="max-w-read">
        <p className="eyebrow mb-3">Your communication profile</p>
        <div className="space-y-3">{fields.map((f) => <FieldEditor key={f.key} f={f} onSaved={() => api<Rel>("/relationship").then(setRel)} />)}</div>
      </section>
      <Disclaimer />
    </div>
  );
}
