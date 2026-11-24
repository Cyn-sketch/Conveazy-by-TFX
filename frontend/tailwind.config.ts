import type { Config } from "tailwindcss";

const v = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: v("paper"), surface: v("surface"), ink: v("ink"), muted: v("muted"), line: v("line"),
        clay: v("clay"), sage: v("sage"), dusk: v("dusk"), warn: v("warn"),
      },
      fontFamily: {
        serif: ["'Fraunces Variable'", "Georgia", "serif"],
        sans: ["'Inter Variable'", "system-ui", "sans-serif"],
      },
      borderRadius: { xl2: "1.25rem" },
      maxWidth: { read: "42rem" },
    },
  },
  plugins: [],
} satisfies Config;
