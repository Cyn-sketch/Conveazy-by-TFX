import Link from "next/link";
import { Wordmark } from "@/components/Brand";
import Character from "@/components/Character";
import { Grievance } from "@/components/Grievance";

export default function Landing() {
  return (
    <div className="lg:grid lg:min-h-dvh lg:grid-cols-[minmax(0,1fr)_auto]">
    <main className="flex min-h-dvh min-w-0 flex-col px-5 sm:px-8 lg:mx-auto lg:w-full lg:max-w-5xl lg:px-12">
      <nav className="flex items-center justify-between py-6">
        <Wordmark withSignature />
        <Link href="/login" className="text-sm font-medium text-muted hover:text-ink">Sign in</Link>
      </nav>

      <section className="flex flex-1 flex-col justify-center py-12">
        <p className="eyebrow mb-5 w-fit">A MadAutomate tool</p>
        <h1 className="h-display max-w-3xl">Understand beyond words.</h1>
        <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted">
          A private space for each of you, and a shared one when you choose it. CONVEAZY helps you say what you mean,
          hear what your partner means, and notice the difference between a reaction, an interpretation and a need.
        </p>
        <div className="mt-9 flex flex-wrap gap-3">
          <Link href="/signup" className="btn-primary px-6 py-3">Create your space</Link>
          <Link href="/login" className="btn-ghost px-6 py-3">I have an account</Link>
        </div>

        <div className="mt-16 grid gap-3 sm:grid-cols-3">
          {[
            ["Translate", "Turn a raw message into one your partner can hear, without losing your feelings or your boundaries."],
            ["Understand", "Ask why something lands the way it does. Answers come with sources and are honest about uncertainty."],
            ["Reflect", "Work through situation, interpretation, emotion and need, in private, before anything is said."],
          ].map(([t, d]) => (
            <div key={t} className="rounded-[1.5rem] bg-surface p-6">
              <h2 className="h-card mb-2">{t}</h2>
              <p className="text-sm leading-relaxed text-muted">{d}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="flex flex-col gap-3 py-8 text-xs text-muted sm:flex-row sm:items-center sm:justify-between">
        <span className="inline-flex items-center gap-2">“Two people should not have to speak the same emotional language to understand each other.”</span>
        <span>Not therapy. Works alongside professional care.</span>
        <Grievance />
      </footer>
    </main>
    <Character className="relative aspect-[4/3] w-full [mask-image:linear-gradient(to_bottom,transparent,#000_18%)] lg:sticky lg:top-0 lg:aspect-auto lg:h-dvh lg:w-[42vw] lg:[mask-image:linear-gradient(to_right,transparent,#000_14%)]" />
    </div>
  );
}
