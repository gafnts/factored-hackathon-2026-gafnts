import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// make web-dev names the deployed site, whose /api the console calls on its own origin (ADR-0007).
const site = process.env.SITE_URL;

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: site
    ? { proxy: { "/api": { target: site, changeOrigin: true } } }
    : {},
  // The content security policy allows no inline script, and the source is public anyway.
  build: { modulePreload: { polyfill: false }, sourcemap: false },
  test: {
    environment: "jsdom",
    include: ["tests/**/*.test.{ts,tsx}"],
    setupFiles: ["tests/setup.ts"],
    coverage: {
      provider: "v8",
      include: ["src/**"],
      exclude: ["src/main.tsx", "src/contracts/**"],
      thresholds: { lines: 80, branches: 80 },
    },
  },
});
