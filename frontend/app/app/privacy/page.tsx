"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useSession } from "@/components/Session";
import { ErrorNote, PageHeader } from "@/components/ui";
import { api, isApiError } from "@/lib/api";

type Privacy = {
  retention_days: number; save_history: boolean;
  consents: { terms_and_care: boolean; ai_processing: boolean; model_training: boolean; share_checkin_signal: boolean };
  partner_can_see: { profile_fields: string[] };
  consent_history: { kind: string; granted: boolean; at: string }[];
};

export default function PrivacyPage() {
  const router = useRouter();
  const { refresh } = useSession();
  const [p, setP] = useState<Privacy | null>(null);
  const [pw, setPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { api<Privacy>("/privacy").then(setP); }, []);
  async function update(patch: Record<string, unknown>) { setP(await api<Privacy>("/privacy", { method: "PUT", json: patch })); refresh(); }
  async function del() {
    setError(null);
    try { await api("/account", { method: "DELETE", json: { password: pw, confirm } }); router.replace("/"); }
    catch (e) { setError(isApiError(e) ? e.message : "Couldn't delete the account."); }
  }
  async function signOutEverywhere() { await api("/auth/logout?everywhere=true", { method: "POST" }); router.replace("/login"); }
  if (!p) return null;

  const Row = ({ title, body, on, onChange }: { title: string; body: string; on: boolean; onChange: (v: boolean) => void }) => (
    <label className="flex cursor-pointer items-start justify-between gap-4 py-4">
      <span><span className="block font-medium">{title}</span><span className="mt-1 block text-sm leading-relaxed text-muted">{body}</span></span>
      <input type="checkbox" checked={on} onChange={(e) => onChange(e.target.checked)} className="mt-1 h-5 w-5 shrink-0 accent-[rgb(var(--ink))]" />
    </label>
  );

  return (
    <div className="max-w-read">
      <PageHeader eyebrow="Privacy & data" title="Your data, your call.">
        Sensitive text is encrypted at rest and sent over HTTPS in production. Your partner can only see profile answers you&apos;ve chosen to share.
      </PageHeader>

      <section className="card divide-y divide-line py-1">
        <Row title="AI processing" body="Needed for the Translator, Partner and Myself modules. Turning it off disables them." on={p.consents.ai_processing} onChange={(v) => update({ ai_processing: v })} />
        <Row title="Let my partner's messages adapt to how I'm doing" body="Shares only the feeling and intensity of your check-in from the last 6 hours with your partner's AI, never your note. Your partner doesn't see it, but the message they get may be shorter and gentler when you're at 7/10 or above." on={p.consents.share_checkin_signal} onChange={(v) => update({ share_checkin_signal: v })} />
        <Row title="Save my history" body="Keep conversations and reflections (encrypted) in your private space." on={p.save_history} onChange={(v) => update({ save_history: v })} />
        <Row title="Use anonymised data to improve CONVEAZY" body="Off unless you turn it on. Intimate content and mental-health information are never used for training without this." on={p.consents.model_training} onChange={(v) => update({ model_training: v })} />
        <label className="flex items-center justify-between gap-4 py-4"><span className="font-medium">Delete history older than</span>
          <select className="input w-auto py-2" value={p.retention_days} onChange={(e) => update({ retention_days: Number(e.target.value) })}>
            {[[30, "30 days"], [90, "90 days"], [365, "1 year"], [1095, "3 years"]].map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select></label>
      </section>

      <section className="mt-8">
        <p className="eyebrow mb-3">What your partner can see</p>
        <p className="text-sm leading-relaxed">{p.partner_can_see.profile_fields.length ? `${p.partner_can_see.profile_fields.length} profile answer(s) you've shared.` : "Nothing. You haven't shared any profile answers."} Never your check-ins, drafts, reflections or questions.</p>
      </section>

      <section className="mt-8 flex flex-wrap gap-3">
        <a className="btn-ghost" href="/api/privacy/export" download>Download all my data</a>
        <button className="btn-ghost" onClick={signOutEverywhere}>Sign out on all devices</button>
      </section>

      <details className="mt-8">
        <summary className="cursor-pointer text-sm text-muted">Consent history</summary>
        <ul className="mt-3 space-y-1 text-sm text-muted">{p.consent_history.map((c, i) => <li key={i}>{new Date(c.at).toLocaleString()}: {c.kind.replace(/_/g, " ")} {c.granted ? "granted" : "withdrawn"}</li>)}</ul>
      </details>

      <section className="mt-12 rounded-xl2 border border-warn/30 p-5">
        <p className="h-card mb-2 text-warn">Delete my account</p>
        <p className="mb-4 text-sm leading-relaxed text-muted">Permanently deletes your account, profile, check-ins, conversations and reflections, and ends any shared space. This can&apos;t be undone. Download your data first if you want a copy.</p>
        <div className="grid gap-3 sm:grid-cols-2">
          <input type="password" className="input" placeholder="Your password" value={pw} onChange={(e) => setPw(e.target.value)} aria-label="Password" />
          <input className="input" placeholder='Type "DELETE"' value={confirm} onChange={(e) => setConfirm(e.target.value)} aria-label="Confirmation" />
        </div>
        <ErrorNote message={error} />
        <button className="btn mt-4 bg-warn text-white hover:bg-warn/90" disabled={confirm !== "DELETE" || !pw} onClick={del}>Delete everything</button>
      </section>
    </div>
  );
}
