"use client";
import { useState, type ReactNode } from "react";
import type { Citation, Crisis } from "@/lib/api";

export function PageHeader({ eyebrow, title, children }: { eyebrow: string; title: string; children?: ReactNode }) {
  return (
    <header className="mb-8 max-w-read">
      <p className="eyebrow mb-3">{eyebrow}</p>
      <h1 className="h-page">{title}</h1>
      {children && <div className="mt-3 text-[15px] leading-relaxed text-muted">{children}</div>}
    </header>
  );
}

export function ModeBadge({ live }: { live: boolean }) {
  return live ? (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-sage/10 px-2.5 py-1 text-xs font-medium text-sage">
      <span className="h-1.5 w-1.5 rounded-full bg-sage" /> Live AI
    </span>
  ) : (
    <span title="Rule-based development responses. Not a language model."
      className="inline-flex items-center gap-1.5 rounded-full border border-dashed border-warn/50 px-2.5 py-1 text-xs font-medium text-warn">
      <span className="h-1.5 w-1.5 rounded-full bg-warn" /> Mock mode: not live AI
    </span>
  );
}

export function Chips<T extends string>({ options, value, onChange, multi = false, labels }: {
  options: readonly T[]; value: T[]; onChange: (v: T[]) => void; multi?: boolean; labels?: Partial<Record<T, string>>;
}) {
  return (
    <div className="flex flex-wrap gap-2" role="group">
      {options.map((o) => {
        const on = value.includes(o);
        return (
          <button key={o} type="button" aria-pressed={on} className={`chip ${on ? "chip-on" : ""}`}
            onClick={() => onChange(multi ? (on ? value.filter((x) => x !== o) : [...value, o]) : [o])}>
            {labels?.[o] ?? o.replace(/_/g, " ")}
          </button>
        );
      })}
    </div>
  );
}

export function ErrorNote({ message }: { message: string | null }) {
  if (!message) return null;
  return <p role="alert" className="mt-3 rounded-xl bg-warn/10 px-4 py-3 text-sm text-warn">{message}</p>;
}

export function CrisisCard({ crisis }: { crisis: Crisis }) {
  return (
    <section role="alert" className="rounded-xl2 border-2 border-warn/40 bg-warn/5 p-5 sm:p-6">
      <p className="eyebrow mb-2 !text-warn">{crisis.level === "urgent" ? "Your safety comes first" : "You don't have to carry this alone"}</p>
      <p className="mb-4 leading-relaxed">{crisis.message}</p>
      <ul className="grid gap-2 sm:grid-cols-2">
        {crisis.resources.map((r) => (
          <li key={r.name} className="rounded-xl bg-surface px-4 py-3 text-sm">
            <span className="block text-xs text-muted">{r.region}</span>
            <span className="font-medium">{r.name}</span>
            <span className="block">{r.contact.startsWith("http") ? <a className="underline" href={r.contact} target="_blank" rel="noreferrer">{r.contact}</a> : r.contact}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function Notice({ children }: { children: ReactNode }) {
  return <div className="rounded-xl2 border border-dusk/30 bg-dusk/5 p-5 leading-relaxed">{children}</div>;
}

export function Sources({ citations }: { citations: Citation[] }) {
  if (!citations.length) return null;
  return (
    <section className="mt-6 border-t border-line pt-5">
      <p className="eyebrow mb-3">Sources</p>
      <ol className="space-y-2.5 text-sm">
        {citations.map((c, i) => (
          <li key={c.id} id={`src-${c.id}`} className="flex gap-3">
            <span className="mt-0.5 font-serif text-muted">{i + 1}</span>
            <span>
              <a href={c.url} target="_blank" rel="noreferrer" className="font-medium underline decoration-line underline-offset-4 hover:decoration-ink">{c.title}</a>
              <span className="block text-muted">{c.publisher} · {kindLabel(c.kind)}</span>
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}

const kindLabel = (k: string) => ({ clinical_org: "Clinical organisation", peer_reviewed: "Peer-reviewed / academic", practice_based: "Practice-based guidance" }[k] ?? k);

export function CopyButton({ text }: { text: string }) {
  const [done, setDone] = useState(false);
  return (
    <button type="button" className="text-xs font-medium text-muted hover:text-ink"
      onClick={async () => { await navigator.clipboard.writeText(text); setDone(true); setTimeout(() => setDone(false), 1500); }}>
      {done ? "Copied" : "Copy"}
    </button>
  );
}

export function Disclaimer() {
  return (
    <p className="mt-10 max-w-read text-xs leading-relaxed text-muted">
      CONVEAZY offers communication support, not therapy, diagnosis or medical advice. It works alongside professional care and never replaces it.
      If you or someone else is in danger, contact local emergency services.
    </p>
  );
}

export function Spinner({ label }: { label: string }) {
  return <span className="inline-flex items-center gap-2 text-sm text-muted"><span className="h-3 w-3 animate-spin rounded-full border-2 border-muted border-t-transparent" />{label}</span>;
}
