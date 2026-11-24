"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useSession } from "@/components/Session";
import { Disclaimer } from "@/components/ui";
import { api } from "@/lib/api";

type CheckIn = { emotion: string; intensity: number; need: string; created_at: string };

const MODULES = [
  { href: "/app/bridge", title: "Say it to them", body: "Type rough scraps of what you want to say. CONVEAZY checks what you mean, then writes it around what your partner has told it about their triggers.", tone: "bg-clay" },
  { href: "/app/translate", title: "Message Translator", body: "Already wrote the message? Paste it in to see how it might land and get calmer versions, with your feelings and boundaries kept.", tone: "bg-dusk" },
  { href: "/app/partner", title: "Understand My Partner", body: "Ask why something lands the way it does. Answers are cited, and they're honest about what can't be known.", tone: "bg-sage" },
  { href: "/app/myself", title: "Understand Myself", body: "Situation, interpretation, emotion, need, words. A private walk-through before anything is said.", tone: "bg-ink" },
  { href: "/app/us", title: "About us", body: "Each of you writes about yourself: how you feel, what triggers you, what calms you. You choose what your partner and the AI can use.", tone: "bg-sage" },
];

function greeting() {
  const h = new Date().getHours();
  return h < 5 ? "Still up" : h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

export default function Home() {
  const { user } = useSession();
  const [last, setLast] = useState<CheckIn | null>(null);
  const [partner, setPartner] = useState<string | null>(null);
  useEffect(() => {
    api<{ checkins: CheckIn[] }>("/checkins").then((r) => setLast(r.checkins[0] ?? null)).catch(() => {});
    api<{ status: string; partner?: { name: string } }>("/relationship").then((r) => setPartner(r.partner?.name ?? null)).catch(() => {});
  }, []);

  return (
    <div>
      <p className="eyebrow mb-3">{greeting()}, {user.display_name}</p>
      <h1 className="h-display max-w-2xl">What do you want to say?</h1>
      <div className="mt-6 flex flex-wrap items-center gap-3">
        <Link href="/app/bridge" className="btn-primary">Say something to {partner ?? "your partner"}</Link>
        <Link href="/app/checkin" className="btn-ghost">Check in</Link>
        {last && <span className="text-sm text-muted">Last time: {last.emotion}, {last.intensity}/10, needing {last.need.replace("_", " ")}</span>}
      </div>

      <div className="mt-12 grid gap-4 sm:grid-cols-2">
        {MODULES.map((m) => (
          <Link key={m.href} href={m.href} className="card group transition hover:-translate-y-0.5 hover:border-ink/30">
            <span className={`mb-4 block h-1 w-10 rounded-full ${m.tone}`} />
            <h2 className="h-card mb-2">{m.title}</h2>
            <p className="text-sm leading-relaxed text-muted">{m.body}</p>
          </Link>
        ))}
      </div>

      <p className="mt-8 text-sm text-muted">
        {partner ? <>You&apos;re linked with <span className="text-ink">{partner}</span>. Your private space stays private.</>
          : <>Using CONVEAZY on your own works too. <Link href="/app/us" className="text-ink underline">Link with your partner</Link> whenever you&apos;re both ready.</>}
      </p>
      <Disclaimer />
    </div>
  );
}
