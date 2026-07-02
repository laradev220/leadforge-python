import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    container: {
      center: true,
      padding: "clamp(1rem, 4vw, 2rem)",
      screens: { "2xl": "1400px" },
    },
    extend: {
      colors: {
        // CSS variable-driven palette so dark mode just works
        paper: {
          DEFAULT: "hsl(var(--paper) / <alpha-value>)",
          deep: "hsl(var(--paper-deep) / <alpha-value>)",
          mute: "hsl(var(--paper-mute) / <alpha-value>)",
        },
        ink: {
          DEFAULT: "hsl(var(--ink) / <alpha-value>)",
          soft: "hsl(var(--ink-soft) / <alpha-value>)",
          mute: "hsl(var(--ink-mute) / <alpha-value>)",
          ghost: "hsl(var(--ink-ghost) / <alpha-value>)",
        },
        ember: {
          DEFAULT: "hsl(var(--ember) / <alpha-value>)",
          hover: "hsl(var(--ember) / <alpha-value>)",
          soft: "hsl(var(--ember-soft) / <alpha-value>)",
        },
        moss: {
          DEFAULT: "hsl(var(--moss) / <alpha-value>)",
          soft: "hsl(var(--moss) / <alpha-value>)",
        },
        line: "hsl(var(--line) / <alpha-value>)",
      },
      fontFamily: {
        // Distinctive serif + grotesk pairing - editorial
        display: ["var(--font-display)", "Georgia", "serif"],
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      fontSize: {
        // Fluid modular scale
        "display-xl": ["clamp(3.5rem, 9vw, 7.5rem)", { lineHeight: "0.92", letterSpacing: "-0.04em" }],
        "display-lg": ["clamp(2.5rem, 6vw, 4.5rem)", { lineHeight: "0.95", letterSpacing: "-0.035em" }],
        "display-md": ["clamp(1.75rem, 3vw, 2.5rem)", { lineHeight: "1.05", letterSpacing: "-0.025em" }],
      },
      borderRadius: {
        sm: "2px",
        DEFAULT: "4px",
        md: "6px",
        lg: "10px",
      },
      keyframes: {
        "fade-up": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "pulse-soft": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.4" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.6s cubic-bezier(0.16, 1, 0.3, 1) both",
        "fade-in": "fade-in 0.4s ease-out both",
        "pulse-soft": "pulse-soft 2s ease-in-out infinite",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;