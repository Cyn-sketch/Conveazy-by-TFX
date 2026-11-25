// Who to contact with a complaint (India's IT Rules 2021 expect a named grievance officer).
// Set NEXT_PUBLIC_GRIEVANCE_NAME and NEXT_PUBLIC_GRIEVANCE_EMAIL in the host's settings; nothing shows until they are set.
const NAME = process.env.NEXT_PUBLIC_GRIEVANCE_NAME;
const EMAIL = process.env.NEXT_PUBLIC_GRIEVANCE_EMAIL;

export function Grievance({ className = "" }: { className?: string }) {
  if (!EMAIL) return null;
  return (
    <p className={`text-xs text-muted ${className}`}>
      Complaints or concerns: {NAME ? `${NAME}, grievance officer, ` : "our grievance officer, "}
      <a className="text-ink underline" href={`mailto:${EMAIL}`}>{EMAIL}</a>. We reply within 15 days.
    </p>
  );
}
