export function Wordmark({ withSignature = false }: { withSignature?: boolean }) {
  return (
    <span className="inline-flex items-baseline gap-2">
      <span className="font-display text-[1.6rem] leading-none tracking-[-0.01em]">conveazy</span>
      {withSignature && <span className="rounded-full bg-tag px-2 py-0.5 text-[12px]">by TFX</span>}
    </span>
  );
}
