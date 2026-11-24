import "@fontsource-variable/fraunces/full.css";
import "@fontsource-variable/inter";
import "./globals.css";
import type { Metadata, Viewport } from "next";

export const metadata: Metadata = {
  title: "CONVEAZY by TFX",
  description: "Understand beyond words. A relationship communication companion.",
  robots: { index: false },
};
export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: [
  { media: "(prefers-color-scheme: light)", color: "#F7F3ED" }, { media: "(prefers-color-scheme: dark)", color: "#161418" }] };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-dvh">{children}</body>
    </html>
  );
}
