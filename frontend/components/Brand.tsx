export function Mark({ size = 28 }: { size?: number }) {
  // Two voices turned toward each other, with the space between them held open.
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <path d="M13 5.5a10.5 10.5 0 0 0 0 21" fill="none" stroke="rgb(var(--clay))" strokeWidth="3.2" strokeLinecap="round" />
      <path d="M19 5.5a10.5 10.5 0 0 1 0 21" fill="none" stroke="rgb(var(--sage))" strokeWidth="3.2" strokeLinecap="round" />
      <circle cx="16" cy="16" r="2.6" fill="rgb(var(--dusk))" />
    </svg>
  );
}

export function Wordmark({ withSignature = false }: { withSignature?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <Mark />
      <span className="leading-none">
        <span className="block font-serif text-[1.15rem] font-medium tracking-[0.14em]">CONVEAZY</span>
        {withSignature && <span className="mt-1 block text-[10px] uppercase tracking-[0.22em] text-muted">by TFX</span>}
      </span>
    </span>
  );
}
