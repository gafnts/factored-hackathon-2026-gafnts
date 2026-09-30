import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
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
