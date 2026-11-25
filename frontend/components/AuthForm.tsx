"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, isApiError, type User } from "@/lib/api";
import { Wordmark } from "./Brand";
import { ErrorNote } from "./ui";
import { Grievance } from "./Grievance";

export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const [form, setForm] = useState({ email: "", password: "", display_name: "" });
  const [adult, setAdult] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      const body = mode === "signup" ? { ...form, confirm_adult: adult } : { email: form.email, password: form.password };
      const u = await api<User>(`/auth/${mode}`, { method: "POST", json: body });
      router.replace(u.onboarded ? "/app" : "/onboarding");
    } catch (err) {
      setError(isApiError(err) ? err.message : "Couldn't reach CONVEAZY. Is the API running?");
    } finally { setBusy(false); }
  }

  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center px-5 py-10">
      <Link href="/" className="mb-10"><Wordmark withSignature /></Link>
      <h1 className="h-page mb-2">{mode === "signup" ? "Create your space" : "Welcome back"}</h1>
      <p className="mb-8 text-muted">{mode === "signup" ? "Your space is private. You decide later whether to share anything with your partner." : "Sign in to your private space."}</p>
      <form onSubmit={submit} className="space-y-4">
        {mode === "signup" && (
          <div><label className="label" htmlFor="name">What should we call you?</label>
            <input id="name" className="input" required maxLength={80} value={form.display_name} onChange={set("display_name")} autoComplete="given-name" /></div>
        )}
        <div><label className="label" htmlFor="email">Email</label>
          <input id="email" type="email" className="input" required value={form.email} onChange={set("email")} autoComplete="email" /></div>
        <div><label className="label" htmlFor="password">Password</label>
          <input id="password" type="password" className="input" required minLength={mode === "signup" ? 10 : 1} value={form.password} onChange={set("password")}
            autoComplete={mode === "signup" ? "new-password" : "current-password"} />
          {mode === "signup" && <p className="mt-1.5 text-xs text-muted">At least 10 characters.</p>}</div>
        {mode === "signup" && (
          <label className="flex items-start gap-2.5 text-sm text-muted">
            <input type="checkbox" required checked={adult} onChange={(e) => setAdult(e.target.checked)} className="mt-0.5 h-4 w-4 accent-[rgb(var(--clay))]" />
            <span>I&apos;m 18 or older. CONVEAZY is made for adults.</span>
          </label>
        )}
        <ErrorNote message={error} />
        <button className="btn-primary w-full py-3" disabled={busy}>{busy ? "One moment…" : mode === "signup" ? "Create account" : "Sign in"}</button>
      </form>
      <p className="mt-6 text-sm text-muted">
        {mode === "signup" ? <>Already have an account? <Link className="text-ink underline" href="/login">Sign in</Link></>
          : <>New here? <Link className="text-ink underline" href="/signup">Create your space</Link></>}
      </p>
      <Grievance className="mt-10" />
    </main>
  );
}
