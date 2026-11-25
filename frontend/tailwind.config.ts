import type { Config } from "tailwindcss";

const v = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: v("paper"), surface: v("surface"), ink: v("ink"), muted: v("muted"), line: v("line"),
        tag: v("tag"), clay: v("clay"), sage: v("sage"), dusk: v("dusk"), warn: v("warn"), blush: v("blush"),
      },
      fontFamily: {
        serif: ["'DM Sans'", "Arial", "sans-serif"],
        sans: ["'DM Sans'", "Arial", "sans-serif"],
        display: ["Epilogue", "Arial", "sans-serif"],
      },
      borderRadius: { xl2: "1.25rem" },
      maxWidth: { read: "42rem" },
    },
  },
  plugins: [],
} satisfies Config;
