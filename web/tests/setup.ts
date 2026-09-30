import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// jsdom lacks what assistant-ui's viewport measures and scrolls with.
globalThis.ResizeObserver = class {
  observe = () => undefined;
  unobserve = () => undefined;
  disconnect = () => undefined;
};
Element.prototype.scrollTo = () => undefined;
Element.prototype.scrollIntoView = () => undefined;

afterEach(() => {
  cleanup();
  window.sessionStorage.clear();
});
