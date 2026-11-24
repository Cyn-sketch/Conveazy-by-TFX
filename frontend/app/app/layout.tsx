"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Wordmark } from "@/components/Brand";
import { SessionCtx, type AIStatus } from "@/components/Session";
import { ModeBadge } from "@/components/ui";
import { api, type User } from "@/lib/api";

const NAV = [
  { href: "/app", label: "Home", short: "Home" },
  { href: "/app/checkin", label: "Check in", short: "Check in" },
  { href: "/app/translate", label: "Message Translator", short: "Translate" },
  { href: "/app/partner", label: "Understand My Partner", short: "Partner" },
  { href: "/app/myself", label: "Understand Myself", short: "Myself" },
  { href: "/app/us", label: "Us & profile", short: "Us" },
  { href: "/app/privacy", label: "Privacy & data", short: "Privacy" },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const path = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [ai, setAi] = useState<AIStatus | null>(null);

  const refresh = useCallback(() => {
    api<User>("/auth/me").then((u) => {
      if (!u.onboarded) router.replace("/onboarding"); else setUser(u);
    }).catch(() => router.replace("/login"));
    api<AIStatus>("/ai/status").then(setAi).catch(() => setAi(null));
  }, [router]);
  useEffect(refresh, [refresh]);

  if (!user) return <div className="grid min-h-dvh place-items-center text-sm text-muted">Opening your space…</div>;

  async function signOut() { await api("/auth/logout", { method: "POST" }); router.replace("/login"); }
  const active = (href: string) => (href === "/app" ? path === "/app" : path.startsWith(href));

  return (
    <SessionCtx.Provider value={{ user, ai, refresh }}>
      <div className="mx-auto flex max-w-6xl">
        <aside className="sticky top-0 hidden h-dvh w-64 shrink-0 flex-col border-r border-line px-5 py-7 lg:flex">
          <Link href="/app"><Wordmark withSignature /></Link>
          <nav className="mt-10 flex flex-col gap-1" aria-label="Main">
            {NAV.map((n) => (
              <Link key={n.href} href={n.href} aria-current={active(n.href) ? "page" : undefined}
                className={`rounded-lg px-3 py-2 text-[14px] transition ${active(n.href) ? "bg-ink/[0.06] font-medium text-ink" : "text-muted hover:text-ink"}`}>{n.label}</Link>
            ))}
          </nav>
          <div className="mt-auto space-y-3 text-sm">
            {ai && <ModeBadge live={ai.live} />}
            <p className="text-muted">Signed in as <span className="text-ink">{user.display_name}</span></p>
            <button onClick={signOut} className="text-muted underline hover:text-ink">Sign out</button>
          </div>
        </aside>

        <div className="min-w-0 flex-1">
          <header className="flex items-center justify-between border-b border-line px-5 py-4 lg:hidden">
            <Link href="/app"><Wordmark /></Link>
            {ai && <ModeBadge live={ai.live} />}
          </header>
          <main className="px-5 pb-28 pt-8 sm:px-8 lg:px-12 lg:pb-16 lg:pt-12">{children}</main>
        </div>

        <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-10 flex justify-around border-t border-line bg-paper/95 px-1 pb-[max(env(safe-area-inset-bottom),0.5rem)] pt-2 backdrop-blur lg:hidden">
          {NAV.filter((n) => n.href !== "/app/privacy").map((n) => (
            <Link key={n.href} href={n.href} aria-current={active(n.href) ? "page" : undefined}
              className={`rounded-lg px-2 py-1.5 text-[11px] font-medium ${active(n.href) ? "text-ink" : "text-muted"}`}>{n.short}</Link>
          ))}
        </nav>
      </div>
    </SessionCtx.Provider>
  );
}
