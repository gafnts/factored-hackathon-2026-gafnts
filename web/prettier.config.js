import * as tailwind from "prettier-plugin-tailwindcss";

// The plugin is imported rather than named, so Prettier finds it when the hooks run it from the repository's root.
export default {
  plugins: [tailwind],
  tailwindStylesheet: "./src/styles.css",
};
