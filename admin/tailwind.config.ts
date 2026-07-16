import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#f6f7f4",
        foreground: "#1e1f1a",
        muted: "#6b7060",
        card: "#ffffff",
        border: "#d8dccf",
        primary: "#1f5d45",
        primaryForeground: "#f4f6f0",
        accent: "#d9a441",
        destructive: "#b93827",
        success: "#1f7a46",
      },
      boxShadow: {
        panel: "0 12px 40px rgba(31, 40, 26, 0.08)",
      },
      borderRadius: {
        xl: "1rem",
      },
    },
  },
  plugins: [],
} satisfies Config;
