"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Wordmark } from "@/components/Brand";
import Character from "@/components/Character";
import { SessionCtx, type AIStatus } from "@/components/Session";
import { ModeBadge } from "@/components/ui";
import { api, type User } from "@/lib/api";

const NAV = [
  { href: "/app", label: "Home", short: "Home" },
  { href: "/app/bridge", label: "Say it to them", short: "Say it" },
  { href: "/app/checkin", label: "Check in", short: "Check in" },
  { href: "/app/translate", label: "Message Translator", short: "Translate" },
  { href: "/app/partner", label: "Understand My Partner", short: "Partner" },
  { href: "/app/myself", label: "Understand Myself", short: "Myself" },
  { href: "/app/us", label: "About us", short: "Us" },
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
      <div className="lg:grid lg:min-h-dvh lg:grid-cols-[minmax(0,1fr)_minmax(0,0.9fr)]">
        <div className="min-w-0">
          <header className="flex flex-wrap items-center gap-3 px-5 pt-5 sm:px-8 lg:px-12 lg:pt-7">
            <Link href="/app"><Wordmark withSignature /></Link>
            <span className="ml-auto flex items-center gap-3">
              {ai && <ModeBadge live={ai.live} />}
              <button onClick={signOut} className="hidden text-sm text-muted hover:text-ink lg:inline">Sign out</button>
            </span>
            <nav className="-mx-1 hidden w-full gap-1 overflow-x-auto pt-3 lg:flex" aria-label="Main">
              {NAV.map((n) => (
                <Link key={n.href} href={n.href} aria-current={active(n.href) ? "page" : undefined}
                  className={`shrink-0 rounded-full px-3.5 py-1.5 text-[14px] transition ${active(n.href) ? "bg-blush text-ink" : "text-ink hover:bg-tag"}`}>{n.label}</Link>
              ))}
            </nav>
          </header>
          <main className="px-5 pb-10 pt-8 sm:px-8 lg:px-12 lg:pb-16 lg:pt-10">{children}</main>
          <Character className="relative mb-24 aspect-[4/3] w-full [mask-image:linear-gradient(to_bottom,transparent,#000_18%)] lg:hidden" />
        </div>
        <Character className="sticky top-0 hidden h-dvh [mask-image:linear-gradient(to_right,transparent,#000_14%)] lg:block" />

        <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-10 flex justify-around bg-paper px-1 pb-[max(env(safe-area-inset-bottom),0.5rem)] pt-2 lg:hidden">
          {NAV.filter((n) => !["/app/privacy", "/app/myself"].includes(n.href)).map((n) => (
            <Link key={n.href} href={n.href} aria-current={active(n.href) ? "page" : undefined}
              className={`rounded-full px-2.5 py-1.5 text-[12px] ${active(n.href) ? "bg-blush text-ink" : "text-muted"}`}>{n.short}</Link>
          ))}
        </nav>
      </div>
    </SessionCtx.Provider>
  );
}
